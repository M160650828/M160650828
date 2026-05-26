import bisect
import time
from typing import Any, Dict, List, Optional, Tuple
from functools import lru_cache

from uvtest.testlog import TestLog
from common.utils import TimerCyclic
from common.context import ctx
from common.can_utils import canmsg_create, send_canmsg
from env.config import DEFAULT_CAN_CHANNELS, ROUTING_CAN_CHANNELS, NET_TO_CHANNEL
from slplus.can import sl_can, register_canmsg_handler, unregister_canmsg_handler
from slplus.event import TextEvents
from common.params import P
from slplus.runtime import sl_runtime
from slplus.busstatis import sl_busstatis  


CAN_EVENT_RX = "CAN Frame is Received"
CAN_EVENT_TX = "CAN Frame is Transmitted"
ROUTING_CAN_EVENT_RX = "Routing CAN Frame is Received"  

_DLC_TO_BYTES = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8,
                 9: 12, 10: 16, 11: 20, 12: 24, 13: 32, 14: 48, 15: 64}

CHECK_MODE_BASIC = 'basic'
CHECK_MODE_DATA = 'data'
CHECK_MODE_SIGNAL = 'signal'
CHECK_MODE_DLC = 'dlc'
CHECK_MODE_FRAMETYPE = 'frametype'
SEND_MODE_MSG = 'msg'
SEND_MODE_SIGNAL = 'signal'
SEND_MODE_INCREMENT = 'increment' 


class RoutingConfig:
    def __init__(self) -> None:
        self._caninfo: Optional[Dict[str, Any]] = None
        self._channel_map: Optional[Dict[str, int]] = None
        self._routing_table: Optional[List[Dict[str, Any]]] = None

    def can_params(self) -> Tuple[float, float, float]:
        return P.CANInfo.Vnormal, P.CANInfo.Tstable_s, P.CANInfo.TdefaultWait_s

    def channel_map(self) -> Dict[str, int]:
        return dict(NET_TO_CHANNEL) if NET_TO_CHANNEL else dict(P.ChannelMapping.map_net_to_channel)

    def routing_table(self) -> List[Dict[str, Any]]:
        return list(P.RoutingInfo.normalized_entries)

    def iter_entries_by_type(self, prefix: str) -> List[Tuple[int, Dict[str, Any]]]:
        prefix = str(prefix).strip()
        return [(idx, e) for idx, e in enumerate(self.routing_table())
                if str(e.get('RoutingType', '')).strip().startswith(prefix)]

    def iter_signal_entries(self) -> List[Tuple[int, Dict[str, Any]]]:
        items = self.iter_entries_by_type("CycleSignal")
        items.extend(self.iter_entries_by_type("EventSignal"))
        return items

    def get_duration_ms(self, entry: Dict[str, Any]) -> int:
        try:
            cycle = int(entry.get('SrcMsgCycleTime', 0) or 0)
            if cycle > 0:
                return max(200, cycle * 20)
        except Exception:
            pass
        return 2000

    def get_param(self, name: str, default: Any = None) -> Any:
        if hasattr(P, 'RoutingInfo') and hasattr(P.RoutingInfo, name):
            return getattr(P.RoutingInfo, name, default)
        if hasattr(P, 'CANInfo') and hasattr(P.CANInfo, name):
            return getattr(P.CANInfo, name, default)
        return default

    def extract_signal_value(self, received_msg: Dict[str, Any], entry: Dict[str, Any]) -> int:
        payload = received_msg.get('payload', b'')
        if isinstance(payload, str):
            payload = bytes.fromhex(payload)

        start_bit = int(entry.get('DestStartBit') or 0)
        bit_length = int(entry.get('DestBitLength') or 0)
        byte_order = str(entry.get('DestByteOrder') or 'intel')

        if not payload or bit_length <= 0:
            return 0

        return _get_signal_value(bytes(payload), start_bit, bit_length, byte_order)


class RoutingSender:
    def __init__(self) -> None:
        self._active_timer_ids: List[str] = []

    def routing_cleanup(self) -> None:
        for tid in list(self._active_timer_ids):
            try:
                TimerCyclic.stop(tid)
            except Exception:
                pass
        self._active_timer_ids.clear()

    def stop_send(self, index: int, entry: Dict[str, Any] = None) -> bool:
        possible_timer_ids = [
            f"routing_msg_{index}",
            f"routing_signal_msg_{index}",
            f"routing_increment_msg_{index}",
            f"routing_lastvalue_msg_{index}",
        ]

        stopped = False
        for timer_id in possible_timer_ids:
            try:
                if timer_id in self._active_timer_ids:
                    TimerCyclic.stop(timer_id)
                    self._active_timer_ids.remove(timer_id)
                    stopped = True
                else:
                    TimerCyclic.stop(timer_id)
                    stopped = True
            except Exception:
                pass

        return stopped

    def send(self, index: int, entry: Dict[str, Any], data_byte: int = 0x00,
             mode: str = SEND_MODE_MSG, duration_ms: Optional[int] = None,
             step: Optional[str] = None) -> str:
        src_id = int(entry.get('SrcMsgId', 0))
        ch = net_to_channel(entry.get('SrcNet', ''))
        dlc_raw = int(entry.get('SrcMsgDLC', 8))
        fdf = 1 if entry.get('SrcMsgFrameType') == 'CANFD' else 0
        brs = 1 if fdf else 0
        period_ms = int(entry.get('SrcMsgCycleTime', 10) or 10)

        if fdf:
            dlc = min(max(dlc_raw, 0), 15)
            data_len = _DLC_TO_BYTES.get(dlc, 8)
        else:
            dlc = min(dlc_raw, 8)
            data_len = dlc

        if mode == SEND_MODE_SIGNAL:
            start_bit = int(entry.get('SrcStartBit') or 0)
            bit_length = int(entry.get('SrcBitLength') or 0)
            byte_order = str(entry.get('SrcByteOrder') or 'intel')
            signal_max = (1 << bit_length) - 1 if bit_length > 0 else 0

            duration_ms = duration_ms or (period_ms * 10)
            dest_period_ms = int(entry.get('DestMsgCycleTime', period_ms) or period_ms)
            src_signal_name = entry.get('SrcSignalName', '')
            dest_signal_name = entry.get('DestSignalName', '')
            TestLog("INFO", step or "",
                    f"根据路由表定义，选取其中一条信号路由，在源网段仿真发送信号所属源报文，"
                    f"周期为源报文周期({period_ms}ms)，ID为源报文ID(0x{src_id:X})，DLC为源报文DLC({dlc})，"
                    f"设置信号值为最大值({signal_max})（与DUT发送的当前信号值不同），"
                    f"持续发送10倍目标信号所属报文周期时间({dest_period_ms * 10}ms) "
                    f"[源信号={src_signal_name}, 目标信号={dest_signal_name}]")
            ctx.can.set_info('routing_src_records', [])
            signal_value = signal_max
            timer_id = f"routing_signal_msg_{index}"

            payload = bytearray(data_len)
            _set_signal_value(payload, start_bit, bit_length, byte_order, signal_value)
            msg = canmsg_create(src_id, dlc, data=0x00, rtr=0, fdf=fdf, brs=brs, ext=0)
            if hasattr(msg, 'payload'):
                msg.payload = bytes(payload)

            src_records = ctx.can.get_info('routing_src_records') or []
            src_records.append({
                'index': index, 'MsgId': src_id, 'time_ms': time.time() * 1000,
                'hw_time_ms': None,
                'dlc': dlc, 'payload': bytes(payload), 'payload_hex': payload.hex().upper(),
                'signal_value': signal_value,
            })
            ctx.can.set_info('routing_src_records', src_records)

            try:
                sl_can(ch).send_canmsg(msg)
            except Exception as e:
                TestLog("WARNING", "", f"首次发送失败: {e}")

            if TimerCyclic.start(timer_id, period_ms, send_canmsg, ch, msg=msg):
                self._active_timer_ids.append(timer_id)
            else:
                TestLog("FAIL", "", f"启动失败: index={index}")

            if duration_ms and duration_ms > 0:
                time.sleep(max(0.0, duration_ms / 1000.0))

            return signal_value

        if mode == SEND_MODE_INCREMENT:
            dest_period_ms = int(entry.get('DestMsgCycleTime', period_ms) or period_ms)
            duration_ms = duration_ms or (dest_period_ms * 10)
            frame_count = max(1, duration_ms // period_ms)
            src_net = entry.get('SrcNet', '')
            dest_net = entry.get('DestNet', '')
            dest_id = int(entry.get('DestMsgId', 0))
            TestLog("INFO", step or "",
                    f"根据路由表定义，选取其中一条直接路由报文，在源网段仿真发送源报文，"
                    f"报文ID为源报文ID(0x{src_id:X})，周期为源报文最小更新时间({period_ms}ms)，"
                    f"DLC为源报文DLC({dlc})，数据内容从0x01依次增加，"
                    f"持续发送10倍目标报文最小更新时间({dest_period_ms * 10}ms) "
                    f"[源网段={src_net}, 目标网段={dest_net}, 目标ID=0x{dest_id:X}]")
            ctx.can.set_info('routing_src_records', [])
            timer_id = f"routing_increment_msg_{index}"

            for i in range(frame_count):
                data_val = ((i + 1) & 0xFF) or 0x01
                payload = bytes([data_val] * data_len)
                msg = canmsg_create(src_id, dlc, data=data_val, rtr=0, fdf=fdf, brs=brs, ext=0)
                if hasattr(msg, 'payload'):
                    msg.payload = payload
                src_records = ctx.can.get_info('routing_src_records') or []
                src_records.append({
                    'index': index, 'MsgId': src_id, 'time_ms': time.time() * 1000,
                    'dlc': dlc, 'payload': payload, 'payload_hex': payload.hex().upper(),
                    'data_byte': data_val,
                })
                ctx.can.set_info('routing_src_records', src_records)
                try:
                    sl_can(ch).send_canmsg(msg)
                except Exception as e:
                    TestLog("WARNING", "", f"递增发送失败: {e}")
                if i < frame_count - 1:
                    time.sleep(period_ms / 1000.0)

            return timer_id

        msg = canmsg_create(src_id, dlc, data=data_byte & 0xFF, rtr=0, fdf=fdf, brs=brs, ext=0)
        timer_id = f"routing_msg_{index}"

        payload = getattr(msg, 'payload', b"") or b""
        src_records = ctx.can.get_info('routing_src_records') or []
        src_records.append({
            'index': index, 'MsgId': src_id, 'time_ms': time.time() * 1000,
            'dlc': getattr(msg, 'dlc', 8), 'payload': payload,
            'payload_hex': payload.hex().upper() if payload else '', 'dataByte': data_byte,
        })
        ctx.can.set_info('routing_src_records', src_records)

        try:
            sl_can(ch).send_canmsg(msg)
        except Exception as e:
            TestLog("WARNING", "", f"首次发送失败: {e}")

        if TimerCyclic.start(timer_id, period_ms, msg, ch):
            self._active_timer_ids.append(timer_id)
        else:
            TestLog("FAIL", "", f"启动失败: index={index}")
            return timer_id

        if duration_ms and duration_ms > 0:
            time.sleep(max(0.0, (duration_ms + 1) / 1000.0))
            try:
                TimerCyclic.stop(timer_id)
                if timer_id in self._active_timer_ids:
                    self._active_timer_ids.remove(timer_id)
            except Exception:
                pass

        return timer_id

    def send_with_custom_dlc(self, index: int, entry: Dict[str, Any],
                              custom_dlc: int, duration_ms: Optional[int] = None,
                              use_signal_max: bool = True,
                              step: Optional[str] = None) -> str:
        src_id = int(entry.get('SrcMsgId', 0))
        src_net = entry.get('SrcNet', '')
        dest_net = entry.get('DestNet', '')
        dest_id = int(entry.get('DestMsgId', 0))
        ch = net_to_channel(src_net)
        src_dlc = int(entry.get('SrcMsgDLC', 8))
        fdf = 1 if entry.get('SrcMsgFrameType') == 'CANFD' else 0
        brs = 1 if fdf else 0
        period_ms = int(entry.get('SrcMsgCycleTime', 10) or 10)
        dest_period_ms = int(entry.get('DestMsgCycleTime', period_ms) or period_ms)
        duration_ms = duration_ms or (dest_period_ms * 10)

        if fdf:
            data_len = _DLC_TO_BYTES.get(custom_dlc, custom_dlc)
        else:
            data_len = min(custom_dlc, 8)

        frame_count = max(1, duration_ms // period_ms)

        if custom_dlc < src_dlc:
            dlc_change_desc = f"DLC为源报文DLC-{src_dlc - custom_dlc}（{custom_dlc}）"
        elif custom_dlc > src_dlc:
            dlc_change_desc = f"DLC为源报文DLC+{custom_dlc - src_dlc}（{custom_dlc}）"
        else:
            dlc_change_desc = f"DLC为源报文DLC（{custom_dlc}）"

        TestLog("INFO", step or "",
                f"根据路由表定义，选取其中一条直接路由报文，在源网段仿真发送源报文，"
                f"报文ID为源报文ID(0x{src_id:X})，周期为源报文最小更新时间({period_ms}ms)，"
                f"{dlc_change_desc}，数据内容从0x01依次增加，"
                f"持续发送10倍目标报文最小更新时间({duration_ms}ms) "
                f"[源网段={src_net}, 目标网段={dest_net}, 目标ID=0x{dest_id:X}]")

        ctx.can.set_info('routing_src_records', [])
        timer_id = f"routing_custom_dlc_{index}"

        routing_type = str(entry.get('RoutingType', '')).lower()
        is_signal_routing = 'signal' in routing_type

        if is_signal_routing and use_signal_max:
            start_bit = int(entry.get('SrcStartBit') or 0)
            bit_length = int(entry.get('SrcBitLength') or 0)
            byte_order = str(entry.get('SrcByteOrder') or 'intel')
            signal_max = (1 << bit_length) - 1 if bit_length > 0 else 0xFF

            payload = bytearray(data_len)
            _set_signal_value(payload, start_bit, bit_length, byte_order, signal_max)
            payload = bytes(payload)
            signal_value = signal_max
        else:
            payload = None
            signal_value = None

        for i in range(frame_count):
            if payload is None:
                data_val = ((i + 1) & 0xFF) or 0x01
                current_payload = bytes([data_val] * data_len)
            else:
                current_payload = payload
                data_val = signal_value

            msg = canmsg_create(src_id, custom_dlc, data=0x00, rtr=0, fdf=fdf, brs=brs, ext=0)
            if hasattr(msg, 'payload'):
                msg.payload = current_payload
            src_records = ctx.can.get_info('routing_src_records') or []
            src_records.append({
                'index': index, 'MsgId': src_id, 'time_ms': time.time() * 1000,
                'dlc': custom_dlc, 'payload': current_payload, 'payload_hex': current_payload.hex().upper(),
                'signal_value': signal_value if is_signal_routing else None,
            })
            ctx.can.set_info('routing_src_records', src_records)
            try:
                sl_can(ch).send_canmsg(msg)
            except Exception as e:
                TestLog("WARNING", "", f"自定义DLC发送失败: {e}")
            if i < frame_count - 1:
                time.sleep(period_ms / 1000.0)

        return timer_id

    def send_high_load(self, index: int, entry: Dict[str, Any],
                       load_percent: int = 80, duration_ms: Optional[int] = None,
                       target_busload: Optional[float] = None) -> Tuple[List[str], float]:
        timer_ids = []
        src_net = entry.get('SrcNet', '')
        dest_net = entry.get('DestNet', '')
        dest_ch = net_to_channel(dest_net)  
        fdf = 1 if entry.get('SrcMsgFrameType') == 'CANFD' else 0
        brs = 0

        if target_busload is None:
            target_busload = P.CANInfo.BusloadHigh_pct if hasattr(P.CANInfo, 'BusloadHigh_pct') else 90.0

        if fdf:
            data_len = 15  
        else:
            data_len = 8   

        HIGH_LOAD_MSG_ID = 0x7FF
        load_msg = canmsg_create(HIGH_LOAD_MSG_ID, data_len, data=0xAA, rtr=0, fdf=fdf, brs=brs, ext=0)

        initial_period_ms = max(1, int(100 / max(load_percent, 1)))
        current_period_ms = initial_period_ms

        load_timer_base_id = f"routing_highload_{index}"
        active_load_timers = []

        def start_load_timer(timer_idx: int, period: int) -> Optional[str]:
            tid = f"{load_timer_base_id}_{timer_idx}"
            if TimerCyclic.start(tid, period, send_canmsg, dest_ch, msg=load_msg):
                self._active_timer_ids.append(tid)
                active_load_timers.append(tid)
                timer_ids.append(tid)
                return tid
            return None

        timer_count = 1
        start_load_timer(0, current_period_ms)

        actual_busload = 0.0
        max_adjust_iterations = 30 
        stabilize_time_s = 0.3  
        target_upper = target_busload + 5.0  

        TestLog("INFO", "",
                f"源网段={src_net} 目标网段={dest_net}(ch={dest_ch}) "
                f"目标负载={target_busload}%~{target_upper}% ID=0x{HIGH_LOAD_MSG_ID:03X}")

        def get_current_busload() -> float:
            try:
                busstat = sl_busstatis().get_can_stat_by_ch(dest_ch)
                return round(busstat.get("busload", {}).get("cur", 0) * 100, 2)
            except Exception:
                return 0.0

        for _ in range(max_adjust_iterations):
            time.sleep(stabilize_time_s)
            busload_cur = get_current_busload()

            if busload_cur >= target_busload:
                break

            gap = target_busload - busload_cur
            timer_count += 1
            period_offset = 0 if gap > 50 else (2 if gap > 20 else 5)
            start_load_timer(timer_count, current_period_ms + period_offset)

        time.sleep(1.0)
        final_cur = get_current_busload()

        if final_cur < target_busload:
            TestLog("WARNING", "", f"负载未达标: {final_cur}% < 目标{target_busload}%")
        else:
            TestLog("PASS", "", f"负载已达标: {final_cur}%")

        return timer_ids, final_cur

    def stop_high_load(self, timer_ids: List[str]) -> None:
        for tid in timer_ids:
            try:
                TimerCyclic.stop(tid)
                if tid in self._active_timer_ids:
                    self._active_timer_ids.remove(tid)
            except Exception:
                pass

    def send_invalid_id(self, entry: Dict[str, Any], invalid_id: int,
                        duration_ms: Optional[int] = None) -> str:
        ch = net_to_channel(entry.get('SrcNet', ''))
        dlc_raw = int(entry.get('SrcMsgDLC', 8))
        fdf = 1 if entry.get('SrcMsgFrameType') == 'CANFD' else 0
        brs = 1 if fdf else 0
        period_ms = int(entry.get('SrcMsgCycleTime', 10) or 10)
        dest_period_ms = int(entry.get('DestMsgCycleTime', period_ms) or period_ms)
        duration_ms = duration_ms or (dest_period_ms * 10)

        if fdf:
            dlc = min(max(dlc_raw, 0), 15)
            data_len = _DLC_TO_BYTES.get(dlc, 8)
        else:
            dlc = min(dlc_raw, 8)
            data_len = dlc

        frame_count = max(1, duration_ms // period_ms)
        ctx.can.set_info('routing_src_records', [])
        timer_id = f"routing_invalid_id"

        for i in range(frame_count):
            data_val = ((i + 1) & 0xFF) or 0x01
            payload = bytes([data_val] * data_len)
            msg = canmsg_create(invalid_id, dlc, data=data_val, rtr=0, fdf=fdf, brs=brs, ext=0)
            if hasattr(msg, 'payload'):
                msg.payload = payload
            src_records = ctx.can.get_info('routing_src_records') or []
            src_records.append({
                'index': -1, 'MsgId': invalid_id, 'time_ms': time.time() * 1000,
                'dlc': dlc, 'payload': payload, 'payload_hex': payload.hex().upper(),
                'data_byte': data_val,
            })
            ctx.can.set_info('routing_src_records', src_records)
            try:
                sl_can(ch).send_canmsg(msg)
            except Exception as e:
                TestLog("WARNING", "", f"无效ID发送失败: {e}")
            if i < frame_count - 1:
                time.sleep(period_ms / 1000.0)

        return timer_id


@lru_cache(maxsize=1)
def get_routing_config() -> RoutingConfig:
    return RoutingConfig()

@lru_cache(maxsize=1)
def get_routing_sender() -> RoutingSender:
    return RoutingSender()


def net_to_channel(net: str) -> int:
    ch = NET_TO_CHANNEL.get(str(net)) if NET_TO_CHANNEL else None
    if ch is None:
        ch = P.ChannelMapping.map_net_to_channel.get(str(net))
    return ch if ch is not None else (DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1)


def _get_signal_value(byte_data, start_bit: int, bit_length: int, byte_order: str) -> int:
    if isinstance(byte_data, str):
        try:
            byte_data = bytes.fromhex(byte_data)
        except Exception:
            return 0
    elif isinstance(byte_data, (list, tuple)):
        byte_data = bytes(byte_data)
    elif not byte_data:
        return 0

    if bit_length <= 0:
        return 0

    is_motorola = str(byte_order).lower().strip() in ('motorola', 'big', 'big_endian', 'msb')

    if is_motorola:
        value = 0
        bits_remaining = bit_length
        current_bit = start_bit

        while bits_remaining > 0:
            byte_idx = current_bit // 8
            bit_in_byte = current_bit % 8
            if byte_idx >= len(byte_data):
                break
            bits_in_this_byte = bit_in_byte + 1
            bits_to_extract = min(bits_in_this_byte, bits_remaining)
            mask = (1 << bits_to_extract) - 1
            shift = bit_in_byte - bits_to_extract + 1
            extracted = (byte_data[byte_idx] >> shift) & mask
            value = (value << bits_to_extract) | extracted
            bits_remaining -= bits_to_extract
            current_bit = (byte_idx + 1) * 8 + 7
        return value
    else:
        # Intel 
        value = 0
        bits_remaining = bit_length
        current_bit = start_bit
        bit_offset = 0

        while bits_remaining > 0:
            byte_idx = current_bit // 8
            bit_in_byte = current_bit % 8
            if byte_idx >= len(byte_data):
                break
            bits_in_this_byte = 8 - bit_in_byte
            bits_to_extract = min(bits_in_this_byte, bits_remaining)
            mask = (1 << bits_to_extract) - 1
            extracted = (byte_data[byte_idx] >> bit_in_byte) & mask
            value |= (extracted << bit_offset)
            bit_offset += bits_to_extract
            bits_remaining -= bits_to_extract
            current_bit = (byte_idx + 1) * 8
        return value



def _set_signal_value(byte_data: bytearray, start_bit: int, bit_length: int,
                      byte_order: str, value: int) -> None:
    if not byte_data or bit_length <= 0:
        return

    is_motorola = str(byte_order).lower().strip() in ('motorola', 'big', 'big_endian', 'msb')

    if is_motorola:
        # Motorola 
        bits_remaining = bit_length
        current_bit = start_bit
        value_shift = bit_length

        while bits_remaining > 0:
            byte_idx = current_bit // 8
            bit_in_byte = current_bit % 8
            if byte_idx >= len(byte_data):
                break
            bits_in_this_byte = bit_in_byte + 1
            bits_to_set = min(bits_in_this_byte, bits_remaining)
            value_shift -= bits_to_set
            mask = (1 << bits_to_set) - 1
            bits_value = (value >> value_shift) & mask
            shift = bit_in_byte - bits_to_set + 1
            clear_mask = ~(mask << shift) & 0xFF
            byte_data[byte_idx] = (byte_data[byte_idx] & clear_mask) | (bits_value << shift)
            bits_remaining -= bits_to_set
            current_bit = (byte_idx + 1) * 8 + 7
    else:
        # Intel 
        bits_remaining = bit_length
        current_bit = start_bit
        bit_offset = 0

        while bits_remaining > 0:
            byte_idx = current_bit // 8
            bit_in_byte = current_bit % 8
            if byte_idx >= len(byte_data):
                break
            bits_in_this_byte = 8 - bit_in_byte
            bits_to_set = min(bits_in_this_byte, bits_remaining)
            mask = (1 << bits_to_set) - 1
            bits_value = (value >> bit_offset) & mask
            clear_mask = ~(mask << bit_in_byte) & 0xFF
            byte_data[byte_idx] = (byte_data[byte_idx] & clear_mask) | (bits_value << bit_in_byte)
            bit_offset += bits_to_set
            bits_remaining -= bits_to_set
            current_bit = (byte_idx + 1) * 8


def check_routing(entry: Dict[str, Any], expect_count: int, *,
                  mode: str = CHECK_MODE_BASIC,
                  timeout_s: Optional[float] = None,
                  compare_from_byte: int = 3) -> Tuple[int, List[Dict[str, Any]]]:
    """
    - CHECK_MODE_BASIC: 基础检查（ID + DLC + 计数）
    - CHECK_MODE_DLC: DLC 检查
    - CHECK_MODE_FRAMETYPE: 帧类型检查
    - CHECK_MODE_DATA: 数据内容检查
    - CHECK_MODE_SIGNAL: 信号值检查
    """
    dest_id = int(entry.get('DestMsgId') or 0)
    _, _, twait_s = get_routing_config().can_params()
    to = float(timeout_s) if timeout_s is not None else float(twait_s)

    if mode in (CHECK_MODE_BASIC, CHECK_MODE_DLC, CHECK_MODE_FRAMETYPE):
        dest_dlc_cfg = int(entry.get('DestMsgDLC', 8) or 8)
        dest_frame_type = str(entry.get('DestMsgFrameType', 'CAN'))
        is_expected_fd = dest_frame_type.upper() in ('CANFD', 'CAN_FD', 'FD')
        expected_data_len = _DLC_TO_BYTES.get(dest_dlc_cfg, dest_dlc_cfg) if is_expected_fd else min(dest_dlc_cfg, 8)

        t0, result = time.time(), -1
        details = {}

        while (time.time() - t0) < to:
            sRxMsgInfoList = ctx.can.get_info('sRxMsgInfoList') or {}
            rx = sRxMsgInfoList.get(dest_id)
            if rx:
                rx_dlc = int(rx.get('dlc', -1))
                is_fd = int(rx.get('canfdType', 0)) == 1
                rx_count = int(rx.get('count', 0))
                actual_data_len = _DLC_TO_BYTES.get(rx_dlc, rx_dlc) if is_fd else min(rx_dlc, 8)

                details = {
                    'expected_dlc': dest_dlc_cfg,
                    'expected_data_len': expected_data_len,
                    'actual_dlc': rx_dlc,
                    'actual_data_len': actual_data_len,
                    'expected_frametype': 'CANFD' if is_expected_fd else 'CAN',
                    'actual_frametype': 'CANFD' if is_fd else 'CAN',
                    'count': rx_count,
                    'dlc_match': rx_dlc == dest_dlc_cfg,
                    'data_len_match': actual_data_len == expected_data_len,
                    'frametype_match': is_fd == is_expected_fd,
                }

                if mode == CHECK_MODE_DLC:
                    if rx_dlc == dest_dlc_cfg and rx_count >= expect_count:
                        result = 0
                        break
                elif mode == CHECK_MODE_FRAMETYPE:
                    if is_fd == is_expected_fd and rx_count >= expect_count:
                        result = 0
                        break
                else:  # CHECK_MODE_BASIC
                    if rx_count >= expect_count:
                        result = 0
                        break
            time.sleep(0.05)

        return result, [details] if details else []

    time.sleep(max(0.0, to))
    src_recs = ctx.can.get_info('routing_src_records') or []
    dest_recs = ctx.can.get_info('routing_dest_records') or []
    dest_msgs = [r for r in dest_recs if int(r.get('MsgId', -1)) == dest_id]

    if not dest_msgs:
        TestLog("FAIL", "",
                f"期望结果：目标网段接收到目标报文 实际结果：未收到目标报文(ID=0x{dest_id:x})")
        return -1, []

    if mode == CHECK_MODE_DATA:
        src_map = {rec['payload'][compare_from_byte]: rec for rec in src_recs
                   if len(rec.get('payload', b'')) > compare_from_byte}
        results, checked = [], set()
        pass_cnt = fail_cnt = 0

        for rec in dest_msgs:
            payload = rec.get('payload', b'')
            if len(payload) <= compare_from_byte:
                continue
            key = payload[compare_from_byte]
            if key in checked or key not in src_map:
                continue
            checked.add(key)
            src_payload = src_map[key].get('payload', b'')
            match = all(src_payload[i] == payload[i]
                        for i in range(compare_from_byte, min(len(src_payload), len(payload))))
            results.append({'key': key, 'match': match})
            pass_cnt += match
            fail_cnt += not match

        return (-1 if fail_cnt > 0 or pass_cnt == 0 else 0), results

    # CHECK_MODE_SIGNAL
    if not src_recs:
        TestLog("WARNING", "",
                "期望结果：存在发送记录 实际结果：无发送记录")
        return -1, []

    src_cfg = (int(entry.get('SrcStartBit') or 0), int(entry.get('SrcBitLength') or 0),
               str(entry.get('SrcByteOrder') or 'intel'))
    dest_cfg = (int(entry.get('DestStartBit') or 0), int(entry.get('DestBitLength') or 0),
                str(entry.get('DestByteOrder') or 'intel'))

    src_signals = {_get_signal_value(r['payload'], *src_cfg): r for r in src_recs if r.get('payload')}
    results, checked, pass_cnt = [], set(), 0

    for rec in dest_msgs:
        payload = rec.get('payload', b'')
        if not payload:
            continue
        val = _get_signal_value(payload, *dest_cfg)
        if val in checked:
            continue
        checked.add(val)
        if val in src_signals:
            pass_cnt += 1
            results.append({'src_signal': val, 'dest_signal': val, 'match': True})

    if pass_cnt > 0:
        TestLog("INFO", "",
                f"期望结果：信号值正确转发  实际结果：成功匹配{pass_cnt}个信号值")
    else:
        TestLog("INFO", "",
                f"期望结果：信号值正确转发  实际结果：未匹配到信号值")

    return (0 if pass_cnt > 0 else -1), results


def analyze_dest_cycle(dest_msg_id: int, expect_cycle_ms: int,
                       tol_ratio: float = 0.10) -> Tuple[bool, List[Tuple[float, bool, float, float]]]:
    recs = ctx.can.get_info('routing_dest_records') or []
    times_ms = sorted([float(r['time_ms']) for r in recs if int(r.get('MsgId', -1)) == int(dest_msg_id)])

    if not times_ms or len(times_ms) <= 1:
        return False, []
    mn = float(expect_cycle_ms) * (1.0 - tol_ratio)
    mx = float(expect_cycle_ms) * (1.0 + tol_ratio)
    results = [(times_ms[i] - times_ms[i-1], mn <= times_ms[i] - times_ms[i-1] <= mx, mn, mx)
               for i in range(1, len(times_ms))]
    ret = all(r[1] for r in results) if results else False
    return ret, results


def analyze_routing_delay(dest_msg_id: int, max_delay_ms: float = 10.0) -> Tuple[bool, List[Dict[str, Any]]]:
    src_recs = ctx.can.get_info('routing_src_records') or []
    dest_recs = ctx.can.get_info('routing_dest_records') or []

    dest_times = sorted([
        {'time_ms': float(r['time_ms']), 'payload': r.get('payload', b'')}
        for r in dest_recs if int(r.get('MsgId', -1)) == int(dest_msg_id)
    ], key=lambda x: x['time_ms'])

    if not dest_times or not src_recs:
        return False, []

    results = []
    src_times_with_hw = [
        float(r.get('hw_time_ms'))
        for r in src_recs if r.get('hw_time_ms') is not None
    ]

    if not src_times_with_hw:
        total_src = len(src_recs)
        TestLog("WARNING", "",
                f"源报文没有硬件时间戳(hw_time_ms)，共{total_src}条记录，TX回调可能未被调用")
        return False, []

    src_times = sorted(src_times_with_hw)

    dest_time_list = [d['time_ms'] for d in dest_times]
    no_match_count = 0

    for src_time in src_times:
        idx = bisect.bisect_left(dest_time_list, src_time)
        if idx < len(dest_time_list):
            dest_time = dest_time_list[idx]
            delay = dest_time - src_time
            if delay <= max_delay_ms * 2:
                results.append({
                    'delay_ms': delay,
                    'pass': delay <= max_delay_ms,
                    'src_time': src_time,
                    'dest_time': dest_time,
                    'max_delay_ms': max_delay_ms
                })
            else:
                no_match_count += 1
        else:
            no_match_count += 1

    ret = all(r['pass'] for r in results) if results else False
    return ret, results


def check_can_communication_state(wait_time=5):
    """
    检查CAN通信状态
    """
    if wait_time is None:
        wait_time = 5
    try:
        wait_time = float(wait_time)
    except Exception:
        wait_time = 5.0

    TestLog(
        "DEBUG",
        "",
        f"先最多等待3s，再等待 {wait_time:.3f}s 统计路由通道通信状态",
    )

    try:
        TextEvents().wait(ROUTING_CAN_EVENT_RX, 3000)
    except Exception:
        try:
            from slplus.time import sl_time
            sl_time().sleep(3000)
        except Exception:
            time.sleep(3)

    try:
        ctx.can.clear_messages()
    except Exception:
        pass

    try:
        ctx.can.set_info('gRoutingFrameCount', 0)
        ctx.can.set_info('gRoutingErrorFrameCount', 0)
    except Exception:
        pass

    total_ms = max(0, int(wait_time * 1000))
    try:
        from slplus.time import sl_time
        sl_time().sleep(total_ms)
    except Exception:
        time.sleep(total_ms / 1000.0)

    frame_cnt = ctx.can.get_info('gRoutingFrameCount') or 0
    err_cnt = ctx.can.get_info('gRoutingErrorFrameCount') or 0

    expected_result = "DUT正常通信（报文数>0且错误帧=0）"
    actual_result = f"报文数={frame_cnt}, 错误帧数={err_cnt}"

    TestLog(
        "INFO",
        "",
        f"通信窗口检查: {actual_result}",
    )

    if frame_cnt > 0 and err_cnt == 0:
        TestLog("PASS", "",
                f"期望结果{expected_result} 实际结果：DUT正常通信")
        return 0
    elif frame_cnt > 0 and err_cnt > 0:
        TestLog("WARNING", "",
                f"期望结果{expected_result} 实际结果：DUT通信正常但有错误帧({err_cnt}帧)")
        return 0
    elif frame_cnt == 0 and err_cnt > 0:
        TestLog("FAIL", "",
                f"期望结果{expected_result} 实际结果：DUT通信异常(无报文，有{err_cnt}个错误帧)")
        return -1
    else:
        TestLog("FAIL", "",
                f"期望结果{expected_result} 实际结果：DUT通信未恢复(报文数=0)")
        return -1

def can_power_setup_and_communication_check(normal_voltage=None, stable_time=None):
    """
    CAN电源设置与通信检查
    包括：电源设置、KL30上电、唤醒启动、CAN通信状态检查
    """
    from common.wakeup import WakeupStart

    try:
        if normal_voltage is None:
            normal_voltage = P.CANInfo.Vnormal
        if stable_time is None:
            stable_time = P.CANInfo.Tstable_s
        TestLog("INFO", "Step1",
                f"开始CAN测试设置和通信检查 (目标电压={normal_voltage:.2f}V, 稳定时间={stable_time}s)")

        # Step1: 设置DUT供电电压
        TestLog("DEBUG", "",
                f"设置电源电压为Vnormal={normal_voltage:.2f}V，执行KL30上电")
        ctx.power_ctrl.set_voltage(normal_voltage)
        ctx.power_ctrl.on()

        # Step2: 执行KL30上电
        TestLog("INFO", "", "执行KL30上电")
        ctx.bob_ctrl.set_power('KL30', True)

        # Step3: 根据DUT通信唤醒方式启动唤醒
        TestLog("INFO", "", "根据DUT通信唤醒方式，使用KL15或网络管理报文唤醒网络")
        WakeupStart()

        # Step4: 等待通信稳定并检查通信状态
        TestLog("INFO", "",
                f"等待Tstable={stable_time}s时间至通信稳定，检查DUT通信状态")
        ret = check_can_communication_state(stable_time)

        # expected_result = "DUT正常通信"
        # if ret != 0:
        #     TestLog("FAIL", "Step1",
        #             f"期望结果{expected_result}  实际结果：DUT通信异常")
        #     return -1

        # TestLog("PASS", "Step1",
        #         f"期望结果{expected_result}  实际结果：DUT正常通信")
        return 0

    except Exception as e:
        TestLog("FAIL", "",
                f"期望结果：DUT正常通信 | 实际结果：测试设置异常({e})")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
        return -1

def on_canmsg(bustype, busid, msg, cookie):
    del bustype, cookie  # unused
    try:
        obj = msg
        is_tx = (getattr(obj, 'dirv', 0) == 1)

        is_routing_channel = busid in ROUTING_CAN_CHANNELS

        try:
            TextEvents().supply(CAN_EVENT_TX if is_tx else CAN_EVENT_RX)
            if is_routing_channel and not is_tx:
                TextEvents().supply(ROUTING_CAN_EVENT_RX)
        except Exception:
            pass

        if is_tx:
            ts_ns = float(getattr(obj, 'timestamp_ns', 0))
            now_ms = ts_ns / 1_000_000.0
            msg_id = getattr(obj, 'msgid', None)
            if msg_id is not None:
                payload_bytes = getattr(obj, 'payload', b"") or b""
                payload_hex = payload_bytes.hex().upper()
                src_records = ctx.can.get_info('routing_src_records') or []
                for rec in reversed(src_records):
                    if rec.get('MsgId') == int(msg_id) and rec.get('hw_time_ms') is None:
                        rec['hw_time_ms'] = now_ms
                        rec['hw_payload'] = payload_bytes
                        rec['hw_payload_hex'] = payload_hex
                        break
                ctx.can.set_info('routing_src_records', src_records)
            return

        if is_routing_channel:
            routing_frame_cnt = ctx.can.get_info('gRoutingFrameCount') or 0
            ctx.can.set_info('gRoutingFrameCount', routing_frame_cnt + 1)

        ts_ns = float(getattr(obj, 'timestamp_ns', 0))
        now_ms = ts_ns / 1_000_000.0
        msg_id = getattr(obj, 'msgid', None)
        if msg_id is None:
            return

        msg_dlc = getattr(obj, 'dlc', 8)
        is_fd = bool(getattr(obj, 'is_fd', False))
        payload_bytes = getattr(obj, 'payload', b"") or b""
        payload_hex = payload_bytes.hex().upper()

        dest_records = ctx.can.get_info('routing_dest_records') or []
        dest_records.append({
            'MsgId': int(msg_id), 'time_ms': now_ms, 'bus': busid, 'dlc': msg_dlc,
            'payload': payload_bytes, 'payload_hex': payload_hex
        })
        ctx.can.set_info('routing_dest_records', dest_records)

        sRx = ctx.can.get_info('sRxMsgInfoList') or {}
        if msg_id not in sRx:
            sRx[msg_id] = {"count": 0, "dlc": msg_dlc, "channel": busid, "msgId": msg_id,
                           "time": 0.0, "periodMin": 5e8, "periodMax": 0.0, "periodSum": 0.0,
                           "canfdType": (1 if is_fd else 0), "lastPayload": payload_hex}
        if sRx[msg_id]["time"] == 0:
            sRx[msg_id]["time"] = now_ms
        else:
            p = now_ms - sRx[msg_id]["time"]
            if p > sRx[msg_id]["periodMax"]: sRx[msg_id]["periodMax"] = p
            if p < sRx[msg_id]["periodMin"]: sRx[msg_id]["periodMin"] = p
            sRx[msg_id]["periodSum"] += p
            sRx[msg_id]["time"] = now_ms
        sRx[msg_id]["count"] += 1
        sRx[msg_id]["canfdType"] = (1 if is_fd else 0)
        sRx[msg_id]["lastPayload"] = payload_hex
        ctx.can.set_info('sRxMsgInfoList', sRx)
        ctx.can.set_info('gECUMsgIDCount', len(sRx))
    except Exception:
        if busid in ROUTING_CAN_CHANNELS:
            err_cnt = ctx.can.get_info('gRoutingErrorFrameCount') or 0
            ctx.can.set_info('gRoutingErrorFrameCount', err_cnt + 1)


def routing_initialization(session_dir=None):
    _ = session_dir
    try:
        TestLog("INFO", "", "开始路由相关初始化")

        ctx.can.set_info('gErrorFrameCount', 0)
        ctx.can.set_info('gECUMsgIDCount', 0)
        ctx.can.set_info('active_channels', [])
        ctx.can.set_info('sRxMsgInfoList', {})

        try:
            register_canmsg_handler(on_canmsg)
            ctx.can.set_info('routing_can_cb', on_canmsg)
        except Exception as e:
            TestLog("WARNING", "", f"注册路由回调失败: {e}")

        # 激活默认通道
        activated = 0
        active_channels = ctx.can.get_info('active_channels') or []
        for ch in DEFAULT_CAN_CHANNELS:
            try:
                sl_can(ch).active()
                if ch not in active_channels:
                    active_channels.append(ch)
                    ctx.can.set_info('active_channels', active_channels)
                activated += 1
                TestLog("INFO", "", f"成功激活默认CAN通道 {ch}")
            except Exception as e:
                TestLog("WARNING", "", f"激活默认CAN通道 {ch} 失败: {e}")

        routing_channels = ROUTING_CAN_CHANNELS if ROUTING_CAN_CHANNELS else []
        for ch in routing_channels:
            try:
                active_channels = ctx.can.get_info('active_channels') or []
                if ch and ch not in active_channels:
                    sl_can(ch).active()
                    active_channels.append(ch)
                    ctx.can.set_info('active_channels', active_channels)
                    activated += 1
                    TestLog("INFO", "", f"成功激活路由CAN通道 {ch}")
            except Exception as e:
                TestLog("WARNING", "", f"激活路由CAN通道 {ch} 失败: {e}")

        if activated == 0:
            TestLog("FAIL", "", "未能激活任何CAN通道")
            return False
        active_channels = ctx.can.get_info('active_channels') or []
        TestLog("INFO", "", f"完成 - 激活通道总数: {len(active_channels)}")

        TestLog("INFO", "Step4", "启动运行时环境")
        sl_runtime.start()
        return True
    except Exception as e:
        TestLog("FAIL", "", f"初始化失败: {e}")
        return False


def routing_deinitialization():
    """路由去初始化"""
    TestLog("INFO", "", "开始...")
    try:
        # 注销回调
        try:
            cb = ctx.can.get_info('routing_can_cb')
            if cb:
                unregister_canmsg_handler(cb)
            ctx.can.set_info('routing_can_cb', None)
        except Exception as e:
            TestLog("WARNING", "", f"失败: {e}")

        get_routing_sender().routing_cleanup()
        ctx.can.set_info('routing_src_records', None)
        ctx.can.set_info('routing_dest_records', None)

        # 停用通道
        active_channels = ctx.can.get_info('active_channels') or []
        for ch in active_channels:
            try:
                sl_can(ch).deactive()
            except Exception as e:
                TestLog("WARNING", "", f"通道 {ch} 失败: {e}")

        TestLog("INFO", "Step2", "停止运行时环境")
        sl_runtime.stop()

        # 清理上下文
        sRxMsgInfoList = ctx.can.get_info('sRxMsgInfoList') or {}
        sRxMsgInfoList.clear()
        ctx.can.set_info('sRxMsgInfoList', {})
        ctx.can.set_info('active_channels', [])
        ctx.can.set_info('gErrorFrameCount', 0)
        ctx.can.set_info('gECUMsgIDCount', 0)
        TestLog("INFO", "", "完成")
        return True
    except Exception as e:
        TestLog("FAIL", "", f"失败: {e}")
        return False


def get_all_networks(cfg):
    networks = set()
    for _, e in enumerate(cfg.routing_table()):
        for key in ('SrcNet', 'DestNet'):
            net = e.get(key, '')
            if net and net is not None and str(net).lower() != 'none':
                networks.add(net)
    return list(networks)


def send_error_frames(channel: int, period_ms: int = 10) -> str:
    timer_id = f"error_frame_{channel}"
    msg = canmsg_create(0x7FF, 8, data=0xFF, rtr=0, fdf=0, brs=0, ext=0)
    if msg is not None:
        TimerCyclic.start(timer_id, period_ms, send_canmsg, channel, msg=msg)
    TestLog("INFO", "", f"通道{channel}开始发送，周期={period_ms}ms")
    return timer_id


def stop_error_frames(timer_id: str):
    try:
        TimerCyclic.stop(timer_id)
    except Exception:
        pass


def set_busoff_fault(channel: int, net_name: str, enable: bool = True) -> bool:
    target = f"CAN{channel}_H"
    action = "注入" if enable else "移除"
    try:
        success, status = ctx.bob_ctrl.set_fault(target, "SHORT_GND", enable=enable)
        if not success:
            TestLog("FAIL", "", f"{action}失败: {status}")
            return False
        if not enable:
            try:
                sl_can(channel).deactive()
                sl_can(channel).active()
            except Exception:
                pass
        TestLog("PASS", "", f"{action}成功: 网段={net_name}")
        return True
    except Exception as e:
        TestLog("FAIL", "", f"{action}异常: {e}")
        return False


def send_extended_frame_increment(channel: int, msg_id: int, dlc: int, period_ms: int,
                                   duration_ms: int, fdf: int = 0, brs: int = 0) -> bool:
    frame_count = max(1, duration_ms // period_ms)
    for i in range(frame_count):
        data_val = ((i + 1) & 0xFF) or 0x01
        msg = canmsg_create(msg_id, dlc, data=data_val, rtr=0, fdf=fdf, brs=brs, ext=1)
        if msg is None:
            return False
        try:
            sl_can(channel).send_canmsg(msg)
        except Exception:
            pass
        if i < frame_count - 1:
            time.sleep(period_ms / 1000.0)
    return True


def check_frame_received(channel: int, frame_type: str = None) -> bool:
    messages = ctx.can.messages or []
    for msg in messages:
        if hasattr(msg, 'channel') and msg.channel == channel:
            if frame_type == 'extended' and hasattr(msg, 'ide') and msg.ide:
                return True
            elif frame_type == 'remote' and hasattr(msg, 'rtr') and msg.rtr:
                return True
            elif frame_type is None:
                return True
    return False


def send_remote_frame(channel: int, msg_id: int) -> bool:
    msg = canmsg_create(msg_id, 8, data=b"", rtr=1, fdf=0, brs=0, ext=0)
    if msg is None:
        TestLog("FAIL", "", f"创建失败: ID=0x{msg_id:x}")
        return False
    try:
        sl_can(channel).send_canmsg(msg)
        TestLog("INFO", "", f"通道{channel}发送: ID=0x{msg_id:x}")
        return True
    except Exception as e:
        TestLog("FAIL", "", f"发送失败: {e}")
        return False


def send_diag_request(channel: int, req_id: int, data: list, timeout_ms: int = 1000) -> Tuple[bool, Any]:
    msg = canmsg_create(req_id, 8, data=data, rtr=0, fdf=0, brs=0, ext=0)
    if msg is None:
        return False, None

    ctx.can.set_info('sRxMsgInfoList', {})

    send_canmsg(channel, msg)

    time.sleep(timeout_ms / 1000.0)

    rx_list = ctx.can.get_info('sRxMsgInfoList') or {}
    resp_id = P.ECUInfo.DiagRespID_int

    for msg_id, info in rx_list.items():
        if msg_id == resp_id:
            return True, info
        if msg_id == req_id + 8:
            return True, info

    return False, None

