import time
from dataclasses import dataclass
import traceback
from typing import Dict, List, Optional, Tuple

from uvtest.testlog import TestLog

from env.config import DEFAULT_CAN_CHANNELS, DEFAULT_LIN_CHANNEL
from slplus.can import register_canmsg_handler, unregister_canmsg_handler
from slplus.lin import register_linmsg_handler, unregister_linmsg_handler
from slplus.can import sl_can
from slplus.event import TextEvents
from .uds_can_utils import (
    get_can_node, clear_dtc, read_dtc,
    DTC_COMM_ERROR, DTC_NO_DTC, DTC_OTHER_DTC, DTC_E2E_DTC
)

from .lin_comm import (
    lin_initialization as lin_util_initialization,
    lin_deinitialization as lin_util_deinitialization,
    ActivateDut,
    stop_lin_simulation,
    check_lin_communication_state,
    _current_dut_mode,
    gLinTextEvent_RX,
    gLinTextEvent_TX,
)

from common.context import ctx
from common.params import P
from library.e2e import crc8_saej1850, crc16_ccitt

@dataclass
class E2EFrameInfo:
    name: str
    id: int
    datalength: int
    cycle: int
    canfd: int  # 0/1

@dataclass
class E2ESignalGroupInfo:
    name: str
    startByte: int
    length: int
    dataid: int
    max_delta_counter_init: int

@dataclass
class E2EConfig:
    frames: Dict[str, E2EFrameInfo]
    groups: Dict[str, E2ESignalGroupInfo]
    sender_groups: List[str]

PROFILE_1A = "Profile1A"
PROFILE_5 = "Profile5"

Counter_Miss_Error='Counter丢失'
Counter_Repeated_Error='Counter重复'
Counter_Unorder_Error='Counter顺序错误'


PROFILE_COUNTER_MAX = {
    PROFILE_1A: 14,
    PROFILE_5: 0xFF,
}

CANFD_DLC_TO_BYTES = {
    0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8,
    9: 12, 10: 16, 11: 20, 12: 24, 13: 32, 14: 48, 15: 64,
}


def payload_len_to_dlc(payload_len: int, is_canfd: bool = False) -> int:
    payload_len = int(payload_len)
    if payload_len < 0:
        raise ValueError(f"payload长度非法: {payload_len}")

    if not is_canfd:
        if payload_len > 8:
            TestLog("WARNING", "E2E报文", f"普通CAN最大8字节，当前{payload_len}字节将按DLC=8发送")
        return min(payload_len, 8)

    for dlc, byte_len in CANFD_DLC_TO_BYTES.items():
        if payload_len <= byte_len:
            if payload_len != byte_len and payload_len > 8:
                TestLog("WARNING", "E2E报文", f"CANFD长度{payload_len}字节非标准DLC长度，按DLC={dlc}({byte_len}字节)发送")
            return dlc
    raise ValueError(f"CANFD payload长度超过64字节: {payload_len}")

class TxCtrl:
    counter = 0
    crc_correct = True
    counter_delta = 0,  # Counter偏差：0=正常, >0=跳跃, -1=重复, -2=倒退
    timer_id = None  # f"e2e_tx_{msg_id:x}"

def load_e2e_config() -> Optional[E2EConfig]:
    cached = ctx.can.get_info('e2e_config')
    if isinstance(cached, E2EConfig):
        return cached

    try:
        frames: Dict[str, E2EFrameInfo] = {}
        groups: Dict[str, E2ESignalGroupInfo] = {}
        sender_groups: List[str] = []

        for e2e in P.E2EInfo.normalized_entries:
            if not isinstance(e2e, dict):
                continue

            name = e2e.get("SignalName")
            if not name:
                raise RuntimeError('E2EInfo.SignalName 缺失')
            start_byte = e2e['StartByte']
            signal_len = e2e['SignalLength']
            data_id = e2e['DataID']

            frame_name = e2e['FrameName']
            can_id = e2e['CANID_int']
            data_len = e2e['DataLength']
            cycle = e2e['Cycle']
            canfd = e2e['CANFD']

            frames[name] = E2EFrameInfo(
                name=frame_name,
                id=can_id,
                datalength=data_len,
                cycle=cycle,
                canfd=canfd,
            )
            groups[name] = E2ESignalGroupInfo(
                name=name,
                startByte=start_byte,
                length=signal_len,
                dataid=data_id,
                max_delta_counter_init=0,
            )
            sender_groups.append(name)

        if len(frames) == 0:
            raise RuntimeError("E2EInfo 为空")

        cfg = E2EConfig(frames=frames, groups=groups, sender_groups=sender_groups)
        ctx.can.set_info('e2e_config', cfg)
        return cfg
    except Exception as e:
        TestLog('FAIL', 'E2E配置', f'JSON E2EInfo 读取失败: {e}')
        return None

# 计算 E2E 字段
def set_profile(use_canfd: bool) -> Tuple[str, int]:
    profile = PROFILE_5 if use_canfd else PROFILE_1A
    gCntrMax = PROFILE_COUNTER_MAX[profile]
    return profile, gCntrMax

def e2e_crc_get(payload: bytes, sig: E2ESignalGroupInfo, profile: str) -> int:
    sb = sig.startByte
    if profile == PROFILE_1A:
        return payload[sb]
    else:  # PROFILE_5
        return ((payload[sb] << 8) | payload[sb + 1])

def e2e_counter_get(payload: bytes, sig: E2ESignalGroupInfo, profile: str) -> int:
    sb = sig.startByte
    offset = 1 if profile == PROFILE_1A else 2
    value = payload[sb + offset]
    if profile == PROFILE_1A:
        value &= 0x0F
    return value

def e2e_checksum_for_payload(payload: bytes, sig: E2ESignalGroupInfo, profile: str) -> int:
    sb = sig.startByte
    if profile == PROFILE_1A:
        offset = 1
        try:
            total_len = int(getattr(sig, 'length', 0))
        except Exception:
            total_len = 0
        avail = max(len(payload) - (sb + offset), 0)
        protected_max = max(total_len - offset, 0)
        bytelength = min(protected_max, avail) if protected_max > 0 else avail
        chk = bytearray()
        chk.append(sig.dataid & 0xFF)
        chk.append((sig.dataid >> 8) & 0xFF)
        chk.extend(payload[sb + offset: sb + offset + bytelength])
        return crc8_saej1850(bytes(chk))
    else:
        offset = 2
        bytelength = max(len(payload) - (sb + offset), 0)
        chk = bytearray()
        chk.extend(payload[sb + offset: sb + offset + bytelength])
        chk.append(sig.dataid & 0xFF)
        chk.append((sig.dataid >> 8) & 0xFF)
        return crc16_ccitt(bytes(chk))

def e2e_counter_check(prev_cntr: int, curr_cntr: int, max_delta_cntr: int, gCntrMax: int) -> int:
    if prev_cntr > gCntrMax or curr_cntr > gCntrMax:
        return 0
    if prev_cntr + max_delta_cntr + 1 > gCntrMax:
        if curr_cntr <= gCntrMax and curr_cntr > prev_cntr:
            return 1
        elif prev_cntr >= gCntrMax - max_delta_cntr + curr_cntr:
            return 1
        else:
            return 2
    else:
        if (curr_cntr <= prev_cntr + max_delta_cntr + 1) and (curr_cntr > prev_cntr):
            return 1
        else:
            return 2

def e2e_counter_check_with_time(Cntr_prev:int, curr_Cntr:int, MaxDeltaCntr:int, t1, t2, cycle:int, gCntrMax:int):
    """带时间补偿的计数器检查函数"""
    
    # 计算时间间隔对应的计数器增量
    time_interval = (t2 - t1) / cycle - 1
    cntr_increment = int(time_interval) % (gCntrMax + 1)
    # 计算期望的计数器值（考虑回绕）
    CntrInterval = (cntr_increment + Cntr_prev) % (gCntrMax + 1)
    # 调用基础检查函数
    return e2e_counter_check(CntrInterval, curr_Cntr, MaxDeltaCntr, gCntrMax)

# 报文采集
def handle_can_message(busid, msg, cookie):
    try:
        # 过滤掉机柜内部的通信报文
        if busid == DEFAULT_CAN_CHANNELS[1]:
            return

        obj = msg 
        msg_id = getattr(obj, 'msgid', None)
        if msg_id is None:
            return
        dlc = getattr(obj, 'dlc', 8)
        is_fd = bool(getattr(obj, 'is_fd', False))
        payload = getattr(obj, 'payload', b"") or b""

        store = ctx.can.get_info('e2e_can_msgs')
        if store is None:
            store = {}
            ctx.can.set_info('e2e_can_msgs', store)
        if msg_id not in store:
            store[msg_id] = []
        store[msg_id].append({
            'time': time.time(),
            'id': msg_id,
            'dlc': dlc,
            'is_fd': 1 if is_fd else 0,
            'payload': bytes(payload),
            'channel': busid,
        })
        if len(store[msg_id]) > 1000:
            store[msg_id] = store[msg_id][-1000:]
        try:
            dirv = getattr(obj, 'dirv', 0)
            try:
                mon_ch = DEFAULT_CAN_CHANNELS[0]
            except Exception:
                mon_ch = None
            if (mon_ch is not None) and (busid == mon_ch):
                TextEvents().supply(gCanTextEvent_TX if dirv == 1 else gCanTextEvent_RX)
        except Exception:
            pass

        try:
            ts_ns = getattr(obj, 'timestamp_ns', None)
            current_time = (float(ts_ns) / 1_000_000.0) if ts_ns is not None else (time.time() * 1000.0)
            sRx = ctx.can.get_info('sRxMsgInfoList')
            if sRx is None:
                sRx = {}
                ctx.can.set_info('sRxMsgInfoList', sRx)
            payload_hex = (bytes(payload).hex().upper()) if payload else ""
            fdf = 1 if is_fd else 0

            if msg_id not in sRx:
                sRx[msg_id] = {
                    "count": 0,
                    "dlc": dlc,
                    "channel": busid,
                    "msgId": msg_id,
                    "time": 0,
                    "periodMin": 500000000,
                    "periodMax": 0,
                    "periodSum": 0,
                    "canfdType": fdf,
                    "lastPayload": payload_hex
                }

            if sRx[msg_id]["time"] == 0:
                sRx[msg_id]["time"] = current_time
            else:
                period = current_time - sRx[msg_id]["time"]
                if period > sRx[msg_id]["periodMax"]:
                    sRx[msg_id]["periodMax"] = period
                if period < sRx[msg_id]["periodMin"]:
                    sRx[msg_id]["periodMin"] = period
                sRx[msg_id]["periodSum"] += period
                sRx[msg_id]["time"] = current_time

            sRx[msg_id]["count"] += 1
            sRx[msg_id]["canfdType"] = fdf
            sRx[msg_id]["lastPayload"] = payload_hex
            ctx.can.set_info('gECUMsgIDCount', len(sRx))
        except Exception:
            pass


    except Exception:
        try:
            err_cnt = ctx.can.get_info('gErrorFrameCount') or 0
            ctx.can.set_info('gErrorFrameCount', err_cnt + 1)
        except Exception:
            pass
        pass


def handle_lin_message(busid, msg, cookie):
    try:
        ts_ns = getattr(msg, 'timestamp_ns', None)
        ts = (float(ts_ns) / 1_000_000.0) if ts_ns is not None else (time.time() * 1000.0)

        pid = int(getattr(msg, 'pid', 0))
        frame_id = int(getattr(msg, 'id', pid & 0x3F))
        dlc = int(getattr(msg, 'dlc', 8))
        data_bytes = bytes(getattr(msg, 'data', b"") or b"")

        store = ctx.can.get_info('e2e_lin_msgs')
        if store is None:
            store = {}
            ctx.can.set_info('e2e_lin_msgs', store)
        store.setdefault(frame_id, []).append({
            'time': ts,
            'id': frame_id,
            'dlc': dlc,
            'payload': data_bytes,
            'channel': busid,
        })
        if len(store[frame_id]) > 1000:
            store[frame_id] = store[frame_id][-1000:]

        sLin = ctx.can.get_info('sLinMsgInfoList')
        if sLin is None:
            sLin = {}
            ctx.can.set_info('sLinMsgInfoList', sLin)

        rx_list = ctx.can.get_info('sLinRXMsgInfoList')
        if rx_list is None:
            rx_list = {}
            ctx.can.set_info('sLinRXMsgInfoList', rx_list)

        tx_list = ctx.can.get_info('sLinTXMsgInfoList')
        if tx_list is None:
            tx_list = {}
            ctx.can.set_info('sLinTXMsgInfoList', tx_list)

        is_tx = bool(getattr(msg, 'dirv', 0) == 1)  # 1=TX, 0=RX
        try:
            TextEvents().supply(gLinTextEvent_TX if is_tx else gLinTextEvent_RX)
        except Exception:
            pass

        if frame_id in [0x3C, 0x3D]:
            return

        msg_info = {
            "pid": pid,
            "id": frame_id,
            "dlc": dlc,
            "err_type": int(getattr(msg, 'err_type', 0) or 0),
            "checksum": int(getattr(msg, 'checksum', 0) or 0),
            "data": [b for b in data_bytes],
            "time": ts,
            "channel": busid,
            "direction": ("TX" if is_tx else "RX"),
        }
        sLin.setdefault(frame_id, []).append(msg_info)

        target = tx_list if is_tx else rx_list
        target.setdefault(frame_id, []).append(msg_info)

        ctx.can.set_info('gLinFrameIDCount', len(sLin))

    except Exception:
        pass


def _on_can_e2e(bustype, busid, msg, cookie):
    _ = bustype
    _ = cookie
    try:
        handle_can_message(busid, msg, cookie)
    except Exception:
        pass


def _on_lin_e2e(bustype, busid, msg, cookie):
    _ = bustype
    _ = cookie
    try:
        handle_lin_message(busid, msg, cookie)
    except Exception:
        pass


# 初始化/去初始化
def e2e_initialization(session_dir=None):
    try:
        TestLog("INFO", "E2E初始化", "开始E2E相关初始化")
        purpose = "E2E初始化"

        ctx.can.reset_all()
        ctx.can.set_info('active_channels', [])
        ctx.can.set_info('e2e_can_msgs', {})
        ctx.can.set_info('e2e_lin_msgs', {})
        ctx.can.set_info('sLinMsgInfoList', {})
        ctx.can.set_info('sLinRXMsgInfoList', {})
        ctx.can.set_info('sLinTXMsgInfoList', {})
        ctx.can.set_info('gLinErrorFrameCount', 0)
        ctx.can.set_info('gLinFrameIDCount', 0)

        # 1) CAN初始化
        cans = DEFAULT_CAN_CHANNELS
        try:
            ctx.can.set_info('monitor_channels', [DEFAULT_CAN_CHANNELS[0]])
        except Exception:
            ctx.can.set_info('monitor_channels', [])

        if not cans:
            TestLog("FAIL", "CAN通道设置", "CAN通道配置失败")
            return False

        register_canmsg_handler(_on_can_e2e, bus=0)
        register_linmsg_handler(_on_lin_e2e, bus=0)

        max_channels = min(len(cans), len(DEFAULT_CAN_CHANNELS))
        activated_count = 0
        for i in range(max_channels):
            can_ch = cans[i]
            try:
                sl_can(can_ch).active()
                active_channels = ctx.can.get_info('active_channels') or []
                if can_ch not in active_channels:
                    active_channels.append(can_ch)
                    ctx.can.set_info('active_channels', active_channels)
                activated_count += 1
                TestLog("INFO", "通道激活", f"成功激活CAN通道 {can_ch}")
            except Exception as e:
                TestLog("WARNING", "通道激活", f"激活CAN通道 {can_ch} 失败: {e}")

        if activated_count > 0:
            TestLog("PASS", "CAN通道设置", f"成功激活{activated_count}个CAN通道用于{purpose}")
        else:
            TestLog("FAIL", "CAN通道设置", f"未能激活任何CAN通道用于{purpose}")
            return False

        # 2) LIN初始化
        try:
            ret = lin_util_initialization(session_dir)
            if not ret:
                TestLog("WARNING", "LIN初始化", "LIN初始化失败（继续运行E2E）")
        except Exception as e:
            TestLog("WARNING", "LIN初始化", f"LIN初始化异常（继续运行E2E）: {e}")

        # 3) 读取E2E配置
        load_e2e_config()
        return True
    except Exception as e:
        TestLog("FAIL", "E2E初始化", f"异常: {e}")
        return False

def e2e_deinitialization():
    try:
        TestLog("INFO", "E2E去初始化", "开始E2E相关去初始化")

        # 停止LIN仿真
        try:
            stop_lin_simulation()
        except Exception:
            pass

        try:
            unregister_canmsg_handler(_on_can_e2e)
        except Exception:
            pass
        try:
            unregister_linmsg_handler(_on_lin_e2e)
        except Exception:
            pass

        # 1. 停用CAN通道
        TestLog("INFO", "Step1", "停用CAN通道")
        for can_ch in (ctx.can.get_info('active_channels') or []):
            try:
                sl_can(can_ch).deactive()
                TestLog("INFO", "通道停用", f"成功停用CAN通道 {can_ch}")
            except Exception as e:
                TestLog("WARNING", "通道停用", f"停用CAN通道 {can_ch} 失败: {e}")
        return True
    except Exception as e:
        TestLog("FAIL", "E2E去初始化", f"异常: {e}")
        return False

# 读取报文
def _collect_can_frames(msg_id: int, channel: Optional[int], duration_ms: int) -> List[bytes]:
    store = ctx.can.get_info('e2e_can_msgs') or {}
    po_ts = ctx.can.get_info('e2e_power_on_time')
    time.sleep(max(duration_ms, 0) / 1000.0)
    frames: List[bytes] = []
    for rec in store.get(msg_id, []):
        try:
            if (po_ts is not None) and (float(rec.get('time', 0)) < float(po_ts)):
                continue
            if (channel is None) or (rec.get('channel') == channel):
                payload = rec.get('payload') or b""
                frames.append(bytes(payload))
        except Exception:
            continue
    return frames

def _collect_lin_frames(frame_id: int, duration_ms: int) -> List[bytes]:
    store = ctx.can.get_info('e2e_lin_msgs') or {}
    po_ts = ctx.can.get_info('e2e_power_on_time')
    time.sleep(max(duration_ms, 0) / 1000.0)
    frames: List[bytes] = []
    for rec in store.get(frame_id, []):
        try:
            if (po_ts is not None) and (float(rec.get('time', 0)) < float(po_ts)):
                continue
            payload = rec.get('payload') or b""
            frames.append(bytes(payload))
        except Exception:
            continue
    return frames

# 验证
def verify_can_crc(profile_1a: bool):
    cfg = load_e2e_config()
    if not cfg:
        TestLog("INFO", "", "E2E配置加载失败")
        return

    if can_power_setup_and_communication_check() != 0:
        TestLog("FAIL", "CAN E2E", "CAN 通信检查失败，停止测试")
        return

    for idx, name in enumerate(cfg.sender_groups, start=1):
        f = cfg.frames.get(name)
        g = cfg.groups.get(name)
        if not f or not g:
            if not f: TestLog("FAIL", "", "E2EInfo中，Frame未配置")
            if not g: TestLog("FAIL", "", "E2EInfo中，SignalGroupName未配置")
            continue
        if profile_1a and f.canfd == 1:
            TestLog("FAIL", "", "参数配置有误：当前测试[CAN]，E2EInfo中配置为了 CANFD")
            continue
        if (not profile_1a) and f.canfd != 1:
            TestLog("FAIL", "", "参数配置有误：当前测试[CANFD]，E2EInfo中配置为了 CAN")
            continue

        profile, gCntrMax = set_profile(bool(f.canfd))
        ch = (DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1)
        TestLog("INFO", "E2E-CAN", f"E2E组#{idx}: {name}, Frame={f.name}, Ch={ch}, ID=0x{f.id:x}, DLC={f.datalength}, Cycle={f.cycle}, CANFD={f.canfd}")

        cycle = f.cycle if f.cycle and f.cycle > 0 else 1000
        if f.cycle in (None, 0):
            TestLog("WARNING", "E2E-CAN", "帧周期为0，按1000ms处理")
        
        # mapping = {0x122: 22, 0x123: 12}
        # frame_index = mapping.get(f.id, 0)
        frame_index = 0
        if profile == PROFILE_5:  # CANFD
            wait_crc_ms = (frame_index + 22) * cycle
            timeout_ms = int(wait_crc_ms * 3 / 2)
            deadline = time.time() + timeout_ms / 1000.0
            frames_crc: List[bytes] = []
            while time.time() < deadline and len(frames_crc) < (frame_index + 22):
                frames_crc = _collect_can_frames(f.id, ch, 0)
                time.sleep(0.02)
            if len(frames_crc) > (frame_index + 22):
                frames_crc = frames_crc[frame_index:(frame_index + 22)]
            if len(frames_crc) == 0:
                TestLog("FAIL", "E2E-CAN", f"未采集到满足条件(帧数<{frame_index + 22})的任何帧(CRC段)")
            else:
                # CRC 校验（首帧+所有帧）
                first_frame = frames_crc[frame_index]
                cal = e2e_checksum_for_payload(first_frame, g, profile)
                getv = e2e_crc_get(first_frame, g, profile)
                hex0 = ' '.join(f"{b:02X}" for b in first_frame)
                TestLog("INFO", "E2E-CAN CRC", f"收到的报文数据场：{hex0}")
                if cal == getv:
                    TestLog("PASS", "E2E-CAN CRC", f"第1帧CRC计算值与报文一致: CRCCal=0x{cal:x} CRCGET=0x{getv:x}")
                else:
                    TestLog("FAIL", "E2E-CAN CRC", f"第1帧报文中CRC值和计算值不匹配：CRCCal=0x{cal:x} CRCGET=0x{getv:x}")

                for i in range(frame_index + 1, len(frames_crc)):
                    cal = e2e_checksum_for_payload(frames_crc[i], g, profile)
                    getv = e2e_crc_get(frames_crc[i], g, profile)
                    hexi = ' '.join(f"{b:02X}" for b in frames_crc[i])
                    TestLog("INFO", "E2E-CAN CRC", f"收到的报文数据场：{hexi}")
                    if cal == getv:
                        TestLog("PASS", "E2E-CAN CRC", f"第{i+1}帧CRC一致: 0x{cal:x}")
                    else:
                        TestLog("FAIL", "E2E-CAN CRC", f"第{i+1}帧报文中CRC值和计算值不匹配：CRCCal=0x{cal:x} CRCGET=0x{getv:x}")
                if len(frames_crc) < 22:
                    TestLog("WARNING", "E2E-CAN CRC", "采集帧数不足22，无法对第22帧进行CRC检查")
        else:
            wait_ms = 22 * cycle
            timeout_ms = int(wait_ms * 3 / 2)
            deadline = time.time() + timeout_ms / 1000.0
            frames: List[bytes] = []
            while time.time() < deadline and len(frames) < 22:
                frames = _collect_can_frames(f.id, ch, 0)
                time.sleep(0.02)
            if len(frames) > 22:
                frames = frames[:22]
            if len(frames) == 0:
                TestLog("FAIL", "E2E-CAN", "未采集到任何帧")
                continue
            if len(frames) < 20:
                TestLog("WARNING", "E2E-CAN", "实际接收少于20帧，与arxml不一致(提示)")

            # CRC 校验（首帧+所有帧）
            cal = e2e_checksum_for_payload(frames[0], g, profile)
            getv = e2e_crc_get(frames[0], g, profile)
            hex0 = ' '.join(f"{b:02X}" for b in frames[0])
            TestLog("INFO", "E2E-CAN CRC", f"收到的报文数据场：{hex0}")
            if cal == getv:
                TestLog("PASS", "E2E-CAN CRC", f"第1帧CRC计算值与报文一致: CRCCal=0x{cal:x} CRCGET=0x{getv:x}")
            else:
                TestLog("FAIL", "E2E-CAN CRC", f"第1帧报文中CRC值和计算值不匹配：CRCCal=0x{cal:x} CRCGET=0x{getv:x}")
            for i in range(1, len(frames)):
                cal = e2e_checksum_for_payload(frames[i], g, profile)
                getv = e2e_crc_get(frames[i], g, profile)
                hexi = ' '.join(f"{b:02X}" for b in frames[i])
                TestLog("INFO", "E2E-CAN CRC", f"收到的报文数据场：{hexi}")
                if cal == getv:
                    TestLog("PASS", "E2E-CAN CRC", f"第{i+1}帧CRC一致: 0x{cal:x}")
                else:
                    TestLog("FAIL", "E2E-CAN CRC", f"第{i+1}帧报文中CRC值和计算值不匹配：CRCCal=0x{cal:x} CRCGET=0x{getv:x}")
            if len(frames) < 22:
                TestLog("WARNING", "E2E-CAN CRC", "采集帧数不足22，无法对第22帧进行CRC检查")


def verify_can_counter(profile_1a: bool):
    cfg = load_e2e_config()
    if not cfg:
        return

    if can_power_setup_and_communication_check() != 0:
        TestLog("FAIL", "CAN E2E", "CAN 通信检查失败，停止测试")
        return

    for idx, name in enumerate(cfg.sender_groups, start=1):
        f = cfg.frames.get(name)
        g = cfg.groups.get(name)
        if not f or not g:
            continue
        if profile_1a and f.canfd == 1:
            continue
        if (not profile_1a) and f.canfd != 1:
            continue

        profile, gCntrMax = set_profile(bool(f.canfd))
        ch = (DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1)
        TestLog("INFO", "E2E-CAN", f"E2E组#{idx}: {name}, Frame={f.name}, Ch={ch}, ID=0x{f.id:x}, DLC={f.datalength}, CANFD={f.canfd}")

        cycle = f.cycle if f.cycle and f.cycle > 0 else 1000
        if f.cycle in (None, 0):
            TestLog("WARNING", "E2E-CAN", "帧周期为0，按1000ms处理")

        # mapping = {0x122: 23, 0x123: 12}
        # frame_index = mapping.get(f.id, 0)
        frame_index = 0
        if profile == PROFILE_5:
            wait_cnt_ms = (261 + frame_index) * cycle
            po_ts = ctx.can.get_info('e2e_power_on_time') or 0
            store = ctx.can.get_info('e2e_can_msgs') or {}
            frames_cnt: List[bytes] = []
            deadline = time.time() + (wait_cnt_ms * 1.2) / 1000.0
            while time.time() < deadline:
                frames_po: List[bytes] = []
                try:
                    for rec in store.get(f.id, []):
                        try:
                            if (rec.get('channel') == ch) and (float(rec.get('time', 0)) >= float(po_ts)):
                                payload = rec.get('payload') or b""
                                frames_po.append(bytes(payload))
                        except Exception:
                            continue
                except Exception:
                    pass
                idx0 = -1
                for i, p in enumerate(frames_po):
                    try:
                        if e2e_counter_get(p, g, profile) == 0:
                            idx0 = i
                            break
                    except Exception:
                        continue
                if idx0 >= 0 and len(frames_po) >= idx0 + 1:
                    end = min(idx0 + (261 + frame_index), len(frames_po))
                    frames_cnt = frames_po[idx0:end]
                    if len(frames_cnt) >= (261 + frame_index):
                        break
                time.sleep(min(max(cycle/1000.0*0.25, 0.005), 0.03))

            if len(frames_cnt) == 0:
                TestLog("FAIL", "E2E-CAN", "未采集到任何帧(Counter段)")
                continue
            if len(frames_cnt) < (260 + frame_index):
                TestLog("WARNING", "E2E-CAN", f"从首个Counter=0起仅采集到{len(frames_cnt)}帧(<{(260 + frame_index)})，与arxml不一致")

            max_delta = g.max_delta_counter_init
            counters: List[int] = []
            for p in frames_cnt:
                counters.append(e2e_counter_get(p, g, profile))
            if len(counters) > 0:
                if counters[frame_index] == 0:
                    TestLog("PASS", "E2E-CAN Counter", f"首帧Counter初始为0: {counters[frame_index]}")
                else:
                    TestLog("FAIL", "E2E-CAN Counter", f"首帧Counter期望0，实际{counters[frame_index]}")
                c0 = counters[frame_index]
                c1 = (counters[frame_index + 1] if len(counters) > 1 else None)
                TestLog("INFO", "E2E-CAN Counter", f"第1帧报文中counter值等于{c0}，第2帧报文中counter值等于{(c1 if c1 is not None else 'N/A')}，期望相邻两帧counter增加不超过1")
            for i in range(frame_index + 1, len(counters)):
                ret = e2e_counter_check(counters[i-1], counters[i], max_delta, gCntrMax)
                if ret == 1:
                    TestLog("PASS", "E2E-CAN Counter", f"第{i}帧报文中counter值等于{counters[i-1]}，第{i+1}帧报文中counter值等于{counters[i]}，期望相邻两帧counter增加不超过1 — 满足")
                elif ret == 2:
                    TestLog("FAIL", "E2E-CAN Counter", f"第{i}帧报文中counter值等于{counters[i-1]}，第{i+1}帧报文中counter值等于{counters[i]}，期望相邻两帧counter增加不超过1 — 不满足")
                else:
                    TestLog("FAIL", "E2E-CAN Counter", f"帧{i}/{i+1} Counter非法(超过最大{gCntrMax})")
        else:
            wait_ms = 22 * cycle
            timeout_ms = int(wait_ms * 3 / 2)
            deadline = time.time() + timeout_ms / 1000.0
            frames: List[bytes] = []
            while time.time() < deadline and len(frames) < 22:
                frames = _collect_can_frames(f.id, ch, 0)
                time.sleep(0.02)
            if len(frames) > 22:
                frames = frames[:22]
            if len(frames) == 0:
                TestLog("FAIL", "E2E-CAN", "未采集到任何帧")
                continue
            if len(frames) < 20:
                TestLog("WARNING", "E2E-CAN", "实际接收少于20帧，与arxml不一致(提示)")

            # Counter 校验
            max_delta = g.max_delta_counter_init
            counters: List[int] = []
            for p in frames:
                counters.append(e2e_counter_get(p, g, profile))
            if len(counters) > 0:
                if counters[0] == 0:
                    TestLog("PASS", "E2E-CAN Counter", f"首帧Counter初始为0: {counters[0]}")
                else:
                    TestLog("FAIL", "E2E-CAN Counter", f"首帧Counter期望0，实际{counters[0]}")
                c0 = counters[0]
                c1 = (counters[1] if len(counters) > 1 else None)
                TestLog("INFO", "E2E-CAN Counter", f"第1帧报文中counter值等于{c0}，第2帧报文中counter值等于{(c1 if c1 is not None else 'N/A')}，期望相邻两帧counter增加不超过1")
            for i in range(1, len(counters)):
                ret = e2e_counter_check(counters[i-1], counters[i], max_delta, gCntrMax)
                if ret == 1:
                    TestLog("PASS", "E2E-CAN Counter", f"第{i}帧报文中counter值等于{counters[i-1]}，第{i+1}帧报文中counter值等于{counters[i]}，期望相邻两帧counter增加不超过1 — 满足")
                elif ret == 2:
                    TestLog("FAIL", "E2E-CAN Counter", f"第{i}帧报文中counter值等于{counters[i-1]}，第{i+1}帧报文中counter值等于{counters[i]}，期望相邻两帧counter增加不超过1 — 不满足")
                else:
                    TestLog("FAIL", "E2E-CAN Counter", f"帧{i}/{i+1} Counter非法(超过最大{gCntrMax})")

def verify_can_busoff_counter(profile_1a: bool):
    cfg = load_e2e_config()
    if not cfg:
        return

    if can_power_setup_and_communication_check() != 0:
        TestLog("FAIL", "CANFD E2E", "CAN 通信检查失败，停止测试")
        return

    for idx, name in enumerate(cfg.sender_groups, start=1):
        f = cfg.frames.get(name)
        g = cfg.groups.get(name)
        if not f or not g:
            continue
        if profile_1a and f.canfd == 1:
            continue
        if (not profile_1a) and f.canfd != 1:
            continue

        profile, gCntrMax = set_profile(bool(f.canfd))
        ch = (DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1)
        TestLog("INFO", "E2E-CANFD", f"E2E组#{idx}: {name}, Frame={f.name}, Ch={ch}, ID=0x{f.id:x}, DLC={f.datalength}, CANFD={f.canfd}")

        cycle = f.cycle if f.cycle and f.cycle > 0 else 1000
        if f.cycle in (None, 0):
            TestLog("WARNING", "E2E-CANFD", "帧周期为0，按1000ms处理")

        if profile == PROFILE_5:
            # 等待15s以上，记录最后一帧Counter值C1
            TestLog("INFO", "E2E-CANFD", "等待15s，记录正常通信时的Counter")
            time.sleep(15)
            
            # 获取最后一帧的Counter值C1
            normal_frames = _collect_can_frames(f.id, ch, cycle+100)
            if not normal_frames:
                TestLog("FAIL", "E2E-CANFD", "未采集到正常通信帧")
                continue
                
            c1 = e2e_counter_get(normal_frames[-1], g, profile)  # 最后一帧的Counter
            TestLog("INFO", "E2E-CACANFDN", f"正常通信最后一帧Counter值C1 = {c1}")
            t1_ms=time.time()*1000
            can_channel_short(ch,2000)
            TestLog("INFO","E2E-CANFD","短路CANH和CANL，持续2秒后恢复")
            t2_ms=time.time()*1000
            wait_ms = 22 * cycle
            timeout_ms = int(wait_ms * 3 / 2)
            deadline = time.time() + timeout_ms / 1000.0
            frames: List[bytes] = []
            while time.time() < deadline and len(frames) < 22:
                frames = _collect_can_frames(f.id, ch, 0)
                time.sleep(0.02)
            if len(frames) > 22:
                frames = frames[:22]
            if len(frames) == 0:
                TestLog("FAIL", "E2E-CANFD", "未采集到任何帧")
                continue
            if len(frames) < 20:
                TestLog("WARNING", "E2E-CANFD", "实际接收少于20帧，与arxml不一致(提示)")

            # Counter 校验
            max_delta = g.max_delta_counter_init
            counters: List[int] = []
            for p in frames:
                counters.append(e2e_counter_get(p, g, profile))
            print(f"{counters=}")
            if len(counters) > 0:
                TestLog("INFO", "E2E-CANFD", "检查恢复通信后的第一帧Counter")
                c2 = e2e_counter_get(frames[0], g, profile)
                TestLog("INFO", "E2E-CANFD", f"恢复通信第一帧Counter值C2 = {c2}")
            if e2e_counter_check_with_time(c1,c2,max_delta,t1_ms,t2_ms,cycle,gCntrMax):
                TestLog("PASS", "E2E-CANFD Counter", f"Busoff前Counter为{c1},恢复后Counter初始值为{c2}, 时间间隔为{t2_ms-t1_ms}")
            else:
                TestLog("FAIL", "E2E-CANFD Counter", f"Busoff前Counter为{c1},恢复后Counter初始值为{c2}, 时间间隔为{t2_ms-t1_ms}")
            for i in range(1, len(counters)):
                ret = e2e_counter_check(counters[i-1], counters[i], max_delta, gCntrMax)
                if ret == 1:
                    TestLog("PASS", "E2E-CANFD Counter", f"第{i}帧报文中counter值等于{counters[i-1]}，第{i+1}帧报文中counter值等于{counters[i]}，期望相邻两帧counter增加不超过1 — 满足")
                elif ret == 2:
                    TestLog("FAIL", "E2E-CANFD Counter", f"第{i}帧报文中counter值等于{counters[i-1]}，第{i+1}帧报文中counter值等于{counters[i]}，期望相邻两帧counter增加不超过1 — 不满足")
                else:
                    TestLog("FAIL", "E2E-CANFD Counter", f"帧{i}/{i+1} Counter非法(超过最大{gCntrMax})")
        else:
            # 等待15s以上，记录最后一帧Counter值C1
            TestLog("INFO", "E2E-CAN", "等待15s，记录正常通信时的Counter")
            time.sleep(15)
            
            # 获取最后一帧的Counter值C1
            normal_frames = _collect_can_frames(f.id, ch, 100)  # 采集100ms内的帧
            if not normal_frames:
                TestLog("FAIL", "E2E-CAN", "未采集到正常通信帧")
                continue
                
            c1 = e2e_counter_get(normal_frames[-1], g, profile)  # 最后一帧的Counter
            TestLog("INFO", "E2E-CAN", f"正常通信最后一帧Counter值C1 = {c1}")
            t1_ms=time.time()*1000
            can_channel_short(ch,2000)
            TestLog("INFO","E2E-CAN","短路CANH和CANL，持续1-2秒后恢复")
            t2_ms=time.time()*1000
            wait_ms = 22 * cycle
            timeout_ms = int(wait_ms * 3 / 2)
            deadline = time.time() + timeout_ms / 1000.0
            frames: List[bytes] = []
            while time.time() < deadline and len(frames) < 22:
                frames = _collect_can_frames(f.id, ch, 0)
                time.sleep(0.02)
            if len(frames) > 22:
                frames = frames[:22]
            if len(frames) == 0:
                TestLog("FAIL", "E2E-CAN", "未采集到任何帧")
                continue
            if len(frames) < 20:
                TestLog("WARNING", "E2E-CAN", "实际接收少于20帧，与arxml不一致(提示)")

            # Counter 校验
            max_delta = g.max_delta_counter_init
            counters: List[int] = []
            for p in frames:
                counters.append(e2e_counter_get(p, g, profile))
            if len(counters) > 0:
                TestLog("INFO", "E2E-CAN", "检查恢复通信后的第一帧Counter")
                c2 = e2e_counter_get(counters[0], g, profile)
                TestLog("INFO", "E2E-CAN", f"恢复通信第一帧Counter值C2 = {c2}")
            if e2e_counter_check_with_time(c1,c2,max_delta,t1_ms,t2_ms,cycle,gCntrMax):
                TestLog("PASS", "E2E-CAN Counter", f"Busoff前Counter为{c1},恢复后Counter初始值为{c2}, 时间间隔为{t2_ms-t1_ms}")
            else:
                TestLog("FAIL", "E2E-CAN Counter", f"Busoff前Counter为{c1},恢复后Counter初始值为{c2}, 时间间隔为{t2_ms-t1_ms}")
            for i in range(1, len(counters)):
                ret = e2e_counter_check(counters[i-1], counters[i], max_delta, gCntrMax)
                if ret == 1:
                    TestLog("PASS", "E2E-CAN Counter", f"第{i}帧报文中counter值等于{counters[i-1]}，第{i+1}帧报文中counter值等于{counters[i]}，期望相邻两帧counter增加不超过1 — 满足")
                elif ret == 2:
                    TestLog("FAIL", "E2E-CAN Counter", f"第{i}帧报文中counter值等于{counters[i-1]}，第{i+1}帧报文中counter值等于{counters[i]}，期望相邻两帧counter增加不超过1 — 不满足")
                else:
                    TestLog("FAIL", "E2E-CAN Counter", f"帧{i}/{i+1} Counter非法(超过最大{gCntrMax})")

def verify_lin_crc_and_counter(profile_1a: bool,crc_check:bool=True,counter_check:bool =True):
    cfg = load_e2e_config()
    if not cfg:
        return

    # 激活DUT（LIN）
    rSimulationActivate = P.LINInfo.SimulationActivate
    rTdefaultWait = P.LINInfo.TdefaultWait_s
    if ActivateDut(rSimulationActivate, rTdefaultWait) != 0:
        TestLog("FAIL", "LIN E2E", "LIN ActivateDut 失败，停止测试")
        return

    for idx, name in enumerate(cfg.sender_groups, start=1):
        f = cfg.frames.get(name)
        g = cfg.groups.get(name)
        if not f or not g:
            continue
        profile, gCntrMax = set_profile(use_canfd=not profile_1a)
        TestLog("INFO", "E2E-LIN", f"E2E组#{idx}: {name}, Frame={f.name}, LIN Ch={DEFAULT_LIN_CHANNEL}, ID=0x{f.id:x}, DLC={f.datalength}")

        cycle = f.cycle if f.cycle and f.cycle > 0 else 1000
        if f.cycle in (None, 0):
            TestLog("WARNING", "E2E-LIN", "帧周期为0，按1000ms处理")

        if profile == PROFILE_5:
            if crc_check==True:
                # LIN CRC16：CRC=21×cycle，Counter=261×cycle
                # 1) CRC 段
                wait_crc_ms = 21 * cycle
                frames_crc = _collect_lin_frames(f.id, wait_crc_ms)
                if len(frames_crc) > 21:
                    frames_crc = frames_crc[:21]
                if len(frames_crc) == 0:
                    TestLog("FAIL", "E2E-LIN", "未采集到任何帧(CRC段)")
                else:
                    cal = e2e_checksum_for_payload(frames_crc[0], g, profile)
                    getv = e2e_crc_get(frames_crc[0], g, profile)
                    hex0 = ' '.join(f"{b:02X}" for b in frames_crc[0])
                    TestLog("INFO", "E2E-LIN CRC", f"收到的报文数据场：{hex0}")
                    if cal == getv:
                        TestLog("PASS", "E2E-LIN CRC", f"第1帧CRC一致: 0x{cal:x}")
                    else:
                        TestLog("FAIL", "E2E-LIN CRC", f"第1帧报文中CRC值和计算值不匹配：CRCCal=0x{cal:x} CRCGET=0x{getv:x}")
                    for i in range(1, len(frames_crc)):
                        cal = e2e_checksum_for_payload(frames_crc[i], g, profile)
                        getv = e2e_crc_get(frames_crc[i], g, profile)
                        hexi = ' '.join(f"{b:02X}" for b in frames_crc[i])
                        TestLog("INFO", "E2E-LIN CRC", f"收到的报文数据场：{hexi}")
                        if cal == getv:
                            TestLog("PASS", "E2E-LIN CRC", f"第{i+1}帧CRC一致: 0x{cal:x}")
                        else:
                            TestLog("FAIL", "E2E-LIN CRC", f"第{i+1}帧报文中CRC值和计算值不匹配：CRCCal=0x{cal:x} CRCGET=0x{getv:x}")
            if counter_check==True:
                # 2) Counter 段
                wait_cnt_ms = 261 * cycle
                po_ts = ctx.can.get_info('e2e_power_on_time') or 0
                store_lin = ctx.can.get_info('e2e_lin_msgs') or {}
                frames_cnt: List[bytes] = []
                deadline = time.time() + (wait_cnt_ms * 1.2) / 1000.0
                while time.time() < deadline:
                    frames_po: List[bytes] = []
                    try:
                        for rec in store_lin.get(f.id, []):
                            try:
                                if float(rec.get('time', 0)) >= float(po_ts):
                                    payload = rec.get('payload') or b""
                                    frames_po.append(bytes(payload))
                            except Exception:
                                continue
                    except Exception:
                        pass
                    idx0 = -1
                    for i, p in enumerate(frames_po):
                        try:
                            if e2e_counter_get(p, g, profile) == 0:
                                idx0 = i
                                break
                        except Exception:
                            continue
                    if idx0 >= 0 and len(frames_po) >= idx0 + 1:
                        end = min(idx0 + 261, len(frames_po))
                        frames_cnt = frames_po[idx0:end]
                        if len(frames_cnt) >= 261:
                            break
                    time.sleep(min(max(cycle/1000.0*0.25, 0.005), 0.03))
                if len(frames_cnt) == 0:
                    TestLog("FAIL", "E2E-LIN", "未采集到任何帧(Counter段)")
                    continue
                if len(frames_cnt) < 260:
                    TestLog("WARNING", "E2E-LIN", f"从首个Counter=0起仅采集到{len(frames_cnt)}帧(<260)，与LDF不一致")

                max_delta = g.max_delta_counter_init
                counters: List[int] = []
                for p in frames_cnt:
                    counters.append(e2e_counter_get(p, g, profile))
                if len(counters) > 0:
                    if counters[0] == 0:
                        TestLog("PASS", "E2E-LIN Counter", f"首帧Counter初始为0: {counters[0]}")
                    else:
                        TestLog("FAIL", "E2E-LIN Counter", f"首帧Counter期望0，实际{counters[0]}")
                    c0 = counters[0]
                    c1 = (counters[1] if len(counters) > 1 else None)
                    TestLog("INFO", "E2E-LIN Counter", f"第1帧报文中counter值等于{c0}，第2帧报文中counter值等于{(c1 if c1 is not None else 'N/A')}，期望相邻两帧counter增加不超过1")
                for i in range(1, len(counters)):
                    ret = e2e_counter_check(counters[i-1], counters[i], max_delta, gCntrMax)
                    if ret == 1:
                        TestLog("PASS", "E2E-LIN Counter", f"第{i}帧报文中counter值等于{counters[i-1]}，第{i+1}帧报文中counter值等于{counters[i]}，期望相邻两帧counter增加不超过1 — 满足")
                    elif ret == 2:
                        TestLog("FAIL", "E2E-LIN Counter", f"第{i}帧报文中counter值等于{counters[i-1]}，第{i+1}帧报文中counter值等于{counters[i]}，期望相邻两帧counter增加不超过1 — 不满足")
                    else:
                        TestLog("FAIL", "E2E-LIN Counter", f"帧{i}/{i+1} Counter非法(超过最大{gCntrMax})")
        else:
            # LIN CRC8：CRC+Counter 均使用 21×cycle 窗口
            wait_ms = 21 * cycle
            frames = _collect_lin_frames(f.id, wait_ms)
            if len(frames) > 21:
                frames = frames[:21]
            if len(frames) == 0:
                TestLog("FAIL", "E2E-LIN", "未采集到任何帧")
                continue
            if len(frames) < 20:
                TestLog("WARNING", "E2E-LIN", "实际接收少于20帧，与LDF不一致")
            if crc_check==True:
            # CRC 校验
                cal = e2e_checksum_for_payload(frames[0], g, profile)
                getv = e2e_crc_get(frames[0], g, profile)
                hex0 = ' '.join(f"{b:02X}" for b in frames[0])
                TestLog("INFO", "E2E-LIN CRC", f"收到的报文数据场：{hex0}")
                if cal == getv:
                    TestLog("PASS", "E2E-LIN CRC", f"第1帧CRC一致: 0x{cal:x}")
                else:
                    TestLog("FAIL", "E2E-LIN CRC", f"第1帧报文中CRC值和计算值不匹配：CRCCal=0x{cal:x} CRCGET=0x{getv:x}")
                for i in range(1, len(frames)):
                    cal = e2e_checksum_for_payload(frames[i], g, profile)
                    getv = e2e_crc_get(frames[i], g, profile)
                    hexi = ' '.join(f"{b:02X}" for b in frames[i])
                    TestLog("INFO", "E2E-LIN CRC", f"收到的报文数据场：{hexi}")
                    if cal == getv:
                        TestLog("PASS", "E2E-LIN CRC", f"第{i+1}帧CRC一致: 0x{cal:x}")
                    else:
                        TestLog("FAIL", "E2E-LIN CRC", f"第{i+1}帧报文中CRC值和计算值不匹配：CRCCal=0x{cal:x} CRCGET=0x{getv:x}")
            if counter_check==True: 
                # Counter 校验
                max_delta = g.max_delta_counter_init
                counters: List[int] = []
                for p in frames:
                    counters.append(e2e_counter_get(p, g, profile))
                if len(counters) > 0:
                    if counters[0] == 0:
                        TestLog("PASS", "E2E-LIN Counter", f"首帧Counter初始为0: {counters[0]}")
                    else:
                        TestLog("FAIL", "E2E-LIN Counter", f"首帧Counter期望0，实际{counters[0]}")
                    c0 = counters[0]
                    c1 = (counters[1] if len(counters) > 1 else None)
                    TestLog("INFO", "E2E-LIN Counter", f"第1帧报文中counter值等于{c0}，第2帧报文中counter值等于{(c1 if c1 is not None else 'N/A')}，期望相邻两帧counter增加不超过1")
                for i in range(1, len(counters)):
                    ret = e2e_counter_check(counters[i-1], counters[i], max_delta, gCntrMax)
                    if ret == 1:
                        TestLog("PASS", "E2E-LIN Counter", f"第{i}帧报文中counter值等于{counters[i-1]}，第{i+1}帧报文中counter值等于{counters[i]}，期望相邻两帧counter增加不超过1 — 满足")
                    elif ret == 2:
                        TestLog("FAIL", "E2E-LIN Counter", f"第{i}帧报文中counter值等于{counters[i-1]}，第{i+1}帧报文中counter值等于{counters[i]}，期望相邻两帧counter增加不超过1 — 不满足")
                    else:
                        TestLog("FAIL", "E2E-LIN Counter", f"帧{i}/{i+1} Counter非法(超过最大{gCntrMax})")

#CAN/LIN通信
gCanTextEvent_RX = "CAN Frame is Received"
gCanTextEvent_TX = "CAN Frame is Transmitted"

def can_channel_short(can_channel: Optional[int], duration_ms=15000):
    """模拟CAN总线故障注入"""
    try:
        FAULT_MAP = {
            'CAN_H_L_short':     ('',   'SHORT',      "CAN_H与CAN_L短路")
        }

        fault_info = FAULT_MAP.get('CAN_H_L_short')

        suffix, kind, fault_desc = fault_info
        target = f"CAN{can_channel}{suffix}"

        TestLog("INFO", "故障注入", f"开始注入{fault_desc}，目标={target}，持续时间={duration_ms}ms")

        # 注入故障
        success, status = ctx.bob_ctrl.set_fault(target, kind, enable=True)
        if not success:
            TestLog("FAIL", "故障注入", f"{fault_desc}注入失败: {status}")
            return False

        TestLog("INFO", "故障注入", f"{fault_desc}注入成功，等待{duration_ms}ms")
        time.sleep(duration_ms / 1000.0)

        # 清除故障
        t1 = time.time()
        success, status = ctx.bob_ctrl.set_fault(target, kind, enable=False)
        if not success:
            TestLog("FAIL", "故障注入", f"{fault_desc}清除失败: {status}")
        else:
            TestLog("INFO", "故障注入", f"{fault_desc}已清除")
            sl_can(can_channel).deactive()
            sl_can(can_channel).active()
        return True, t1

    except Exception as e:
        TestLog("ERROR", "故障注入", f"故障注入异常: {e}")
        return False

def check_can_communication_state(wait_time=5):
    """
    检查CAN通信状态
    """
    TestLog("INFO", "CAN通信状态检查", f"等待 {wait_time}s 检查通信状态")

    try:
        ms = max(0, int(wait_time * 1000))
        event_detected = bool(TextEvents().wait(gCanTextEvent_RX, ms))
    except Exception:
        from slplus.time import sl_time
        sl_time().sleep(int(wait_time * 1000))
        event_detected = False


    try:
        po_ts = ctx.can.get_info('e2e_power_on_time')
        store = ctx.can.get_info('e2e_can_msgs')
        mon_ch = (DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else None)
        if po_ts is not None and isinstance(store, dict) and store:
            first_frames = ctx.can.get_info('e2e_first_frames')
            if first_frames is None:
                first_frames = {}
            ctx.can.set_info('e2e_first_frames', first_frames)
            cfg = load_e2e_config()
            desired_ids = set()
            try:
                if cfg:
                    for name in cfg.sender_groups:
                        f = cfg.frames.get(name)
                        if f:
                            desired_ids.add(f.id)
            except Exception:
                desired_ids = set()

            for mid in desired_ids:
                if mid in first_frames:
                    continue
                for rec in store.get(mid, []):
                    try:
                        if (mon_ch is not None) and (rec.get('channel') == mon_ch) and (float(rec.get('time', 0)) >= float(po_ts)):
                            first_frames[mid] = rec
                            break
                    except Exception:
                        continue

            if ctx.can.get_info('e2e_first_any') is None:
                earliest = None
                for arr in store.values():
                    for rec in arr:
                        try:
                            if (mon_ch is not None) and (rec.get('channel') == mon_ch) and (float(rec.get('time', 0)) >= float(po_ts)):
                                if earliest is None or rec['time'] < earliest['time']:
                                    earliest = rec
                                break
                        except Exception:
                            continue
                if earliest is not None:
                    ctx.can.set_info('e2e_first_any', earliest)
                    try:
                        TestLog("INFO", "E2E首帧捕获", f"KL30上电后首帧: ID=0x{earliest['id']:X}, Ch={earliest['channel']}")
                    except Exception:
                        pass
    except Exception:
        pass

    # 更新消息计数
    sRx = ctx.can.get_info('sRxMsgInfoList') or {}
    ctx.can.set_info('gECUMsgIDCount', len(sRx))

    frame_cnt = ctx.can.get_info('gECUMsgIDCount') or 0
    err_cnt = ctx.can.get_info('gErrorFrameCount') or 0

    TestLog("INFO", "CAN通信状态", f"gECUMsgIDCount = {frame_cnt}, event_detected = {event_detected}, gErrorFrameCount = {err_cnt}")

    if (frame_cnt > 0 or event_detected) and err_cnt == 0:
        TestLog("PASS", "CAN通信状态检查", "DUT通信正常，总线上有报文的传输，且无错误帧")
        return 0
    elif (frame_cnt > 0 or event_detected) and err_cnt > 0:
        TestLog("WARNING", "CAN通信状态检查", "DUT通信正常，总线上有报文的传输，但有错误帧")
        return 0
    elif frame_cnt == 0 and err_cnt > 0:
        TestLog("FAIL", "CAN通信状态检查", "DUT通信不正常，总线上无报文的传输，有错误帧")
        return -1
    else:
        TestLog("FAIL", "CAN通信状态检查", "DUT通信未恢复")
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
        TestLog("INFO", "CAN测试设置", "开始CAN测试设置和通信检查")

        # Step1: 设置DUT供电电压
        TestLog("INFO", "Step1", f"设置DUT供电电压为 {normal_voltage:.2f}V")
        ctx.power_ctrl.set_voltage(normal_voltage)
        ctx.power_ctrl.on()

        # Step2: 执行KL30上电
        TestLog("INFO", "Step2", "执行KL30上电")
        ctx.bob_ctrl.set_power('KL30', True)

        try:
            ctx.can.set_info('e2e_power_on_time', time.time())
            first_frames = ctx.can.get_info('e2e_first_frames')
            if first_frames is None:
                ctx.can.set_info('e2e_first_frames', {})
        except Exception:
            pass


        # Step3: 根据DUT通信唤醒方式启动唤醒
        TestLog("INFO", "Step3", "根据DUT通信唤醒方式，启动ECU唤醒")
        WakeupStart()

        # Step5: 等待通信稳定并检查通信状态
        TestLog("INFO", "Step5", f"等待 {stable_time}s 至CAN通信稳定")
        ret = check_can_communication_state(stable_time)

        if ret != 0:
            TestLog("FAIL", "CAN通信检查", "CAN通信状态检查失败")
            return -1

        TestLog("PASS", "CAN测试设置", "CAN测试设置和通信检查完成")
        return 0

    except Exception as e:
        TestLog("FAIL", "CAN测试设置", f"CAN测试设置失败: {e}")
        import traceback
        TestLog("DEBUG", "CAN测试设置", f"详细错误: {traceback.format_exc()}")
        return -1



def get_e2e_dtc(signal_group_name: str, dtc_type: str = "CRC") -> Optional[int]:
    try:
        print(f"{signal_group_name=}, {dtc_type=}")
        for item in P.E2E_DTCs:
            print(f"{item=}")
            if item.SignalGroupName == signal_group_name and dtc_type in item.TYPE:
                dtc = item.DTC_int
                TestLog("INFO", "E2E DTC", f"匹配到DTC: {signal_group_name}, Type={dtc_type}, DTC=0x{dtc:06X}")
                return dtc
        TestLog("WARNING", "E2E DTC", f"未找到匹配的DTC: {signal_group_name}, Type={dtc_type}")
        return None
    except Exception as e:
        TestLog("WARNING", "E2E DTC", f"获取DTC失败: {e}")
        return None


def build_e2e_payload(sig: E2ESignalGroupInfo, profile: str,
                       data_len: int) -> bytes:
    counter = TxCtrl.counter
    crc_correct = TxCtrl.crc_correct
    counter_delta = TxCtrl.counter_delta
            
    payload = bytearray(data_len)
    sb = sig.startByte

    if counter_delta == 0:
        actual_counter = counter
    elif counter_delta > 0:
        # Counter += delta 
        actual_counter = counter + counter_delta
    elif counter_delta == -1:
        # 重复 Counter不变 
        actual_counter = counter - 1
    else:  # counter_delta == -2
        # 倒退 Counter -= 1
        actual_counter = counter - 2

    if profile == PROFILE_1A:
        # Profile1A: [CRC(1B)][Counter(4bit)+Data(4bit)][Data...]
        # Counter范围: 0-14
        if actual_counter < 0:
            actual_counter = 14
        counter_val = actual_counter % 15
        payload[sb + 1] = (counter_val & 0x0F)  # Counter在低4位

        for i in range(sb + 2, data_len):
            payload[i] = 0xAA

        if crc_correct:
            crc = e2e_checksum_for_payload(bytes(payload), sig, profile)
        else:
            # 使用错误的CRC值
            crc = (e2e_checksum_for_payload(bytes(payload), sig, profile) + 0x55) & 0xFF
        payload[sb] = crc

    else:  # PROFILE_5
        # Profile5: [CRC_H(1B)][CRC_L(1B)][Counter(1B)][Data...]
        # Counter范围: 0-255
        if actual_counter < 0:
            actual_counter = 0xFF
        counter_val = actual_counter & 0xFF
        payload[sb + 2] = counter_val

        for i in range(sb + 3, data_len):
            payload[i] = 0xAA  # 填充测试数据

        if crc_correct:
            crc = e2e_checksum_for_payload(bytes(payload), sig, profile)
        else:
            # 使用错误的CRC值
            crc = (e2e_checksum_for_payload(bytes(payload), sig, profile) + 0x5555) & 0xFFFF
        payload[sb] = (crc >> 8) & 0xFF
        payload[sb + 1] = crc & 0xFF

    return actual_counter, bytes(payload)


def send_e2e_frame(channel: int, msg_id: int, payload: bytes,
                    is_canfd: bool = False) -> bool:
    try:
        from common.can_utils import send_canmsg

        dlc = payload_len_to_dlc(len(payload), is_canfd)
        fdf = 1 if is_canfd else 0
        brs = 1 if is_canfd else 0

        msg = send_canmsg(channel, msg_id=msg_id, dlc=dlc,
                         data=payload, fdf=fdf, brs=brs)
        return msg is not None
    except Exception as e:
        TestLog("FAIL", "发送E2E报文", f"发送失败: {e}")
        return False


def start_e2e_send_timer(channel: int, msg_id: int, sig: E2ESignalGroupInfo,
                        profile: str, data_len: int, cycle_ms: int,
                        is_canfd: bool = False) -> dict:
    from common.utils import TimerCyclic

    TxCtrl.counter = 0
    TxCtrl.crc_correct = True
    TxCtrl.counter_delta = 0  # Counter偏差：0=正常, >0=跳跃, -1=重复, -2=倒退
    TxCtrl.timer_id = f"e2e_tx_{msg_id:x}"

    def send_fn():
        actual_counter, payload = build_e2e_payload(sig, profile, data_len)
        send_e2e_frame(channel, msg_id, payload, is_canfd)
        max_counter = PROFILE_COUNTER_MAX[profile]
        TxCtrl.counter = actual_counter + 1

    TimerCyclic.start(TxCtrl.timer_id, cycle_ms, send_fn)
    return TxCtrl


def stop_e2e_send_timer():
    try:
        from common.utils import TimerCyclic
        TimerCyclic.stop(TxCtrl.timer_id)
    except:
        pass


def verify_can_crc_receive(profile_1a: bool):
    cfg = load_e2e_config()
    if not cfg:
        TestLog("FAIL", "E2E配置", "加载E2E配置失败")
        return

    if can_power_setup_and_communication_check() != 0:
        TestLog("FAIL", "CAN E2E", "CAN通信检查失败")
        return

    is_canfd = not profile_1a
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    uds_node = get_can_node(sa, ta, fa, is_canfd=is_canfd)

    try:
        for idx, name in enumerate(cfg.sender_groups, start=1):
            f, g = cfg.frames.get(name), cfg.groups.get(name)
            if not f or not g:
                continue

            stop_e2e_send_timer()

            # 根据profile过滤
            if profile_1a and f.canfd == 1:
                continue
            if (not profile_1a) and f.canfd != 1:
                continue

            profile, _ = set_profile(bool(f.canfd))
            ch = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
            cycle = f.cycle if f.cycle and f.cycle > 0 else 100
            wait_sec = max(cycle * 20, 3000) / 1000.0  # DTC检测等待时间

            e2e_dtc = get_e2e_dtc(name, "CRC")

            TestLog("INFO", "E2E CRC接收",
                   f"组#{idx}: {name}, ID=0x{f.id:x}, DLC={f.datalength}, DTC=0x{e2e_dtc:06X}" if e2e_dtc else
                   f"组#{idx}: {name}, ID=0x{f.id:x}, DLC={f.datalength}, DTC=未配置")

            if e2e_dtc is None:
                TestLog("WARNING", "E2E CRC接收", f"信号组 {name} 未配置E2E DTC，跳过该组测试")
                continue

            # Step1: 启动DUT，发送正确E2E报文
            TestLog("INFO", "Step1", f"开始发送正确的E2E_RxMsg({cycle=}ms)")
            start_e2e_send_timer(ch, f.id, g, profile, f.datalength, cycle, is_canfd)
            time.sleep(6.0)  # 等待通信稳定

            # Step2: 清除DTC
            TestLog("INFO", "Step2", "清除DTC")
            if not clear_dtc(uds_node):
                stop_e2e_send_timer()
                continue

            # Step3-4: 等待后读取DTC，期望无DTC
            TestLog("INFO", "Step3-4", f"等待{wait_sec:.1f}s后读取DTC")
            time.sleep(wait_sec)
            ret = read_dtc(uds_node, e2e_dtc)
            if ret == DTC_COMM_ERROR:
                stop_e2e_send_timer()
                continue
            elif ret == DTC_NO_DTC:
                TestLog("PASS", "E2E CRC接收", "正确CRC：DUT未记录DTC（符合预期）")
            elif ret == DTC_E2E_DTC:
                TestLog("FAIL", "E2E CRC接收", "正确CRC：DUT记录了E2E DTC（不符合预期）")
            else:  # DTC_OTHER_DTC
                TestLog("WARNING", "E2E CRC接收", "正确CRC：DUT记录了其他DTC（非E2E相关）")

            # Step5-7: 发送错误CRC，等待后读取DTC，期望有E2E DTC
            TestLog("INFO", "Step5-7", "发送错误CRC的E2E报文")
            TxCtrl.crc_correct = False
            time.sleep(wait_sec)
            ret = read_dtc(uds_node, e2e_dtc)
            if ret == DTC_COMM_ERROR:
                stop_e2e_send_timer()
                continue
            elif ret == DTC_E2E_DTC:
                TestLog("PASS", "E2E CRC接收", "错误CRC：DUT记录了E2E DTC（符合预期）")
            elif ret == DTC_NO_DTC:
                TestLog("FAIL", "E2E CRC接收", "错误CRC：DUT未记录任何DTC（不符合预期）")
            else:  # DTC_OTHER_DTC
                TestLog("FAIL", "E2E CRC接收", "错误CRC：DUT记录了其他DTC但非E2E DTC（不符合预期）")

            # Step8-9: 恢复正确CRC，清除DTC
            TestLog("INFO", "Step8-9", "恢复正确CRC，清除DTC")
            TxCtrl.crc_correct = True
            time.sleep(wait_sec)
            clear_dtc(uds_node)

            # Step10-11: 间歇性CRC错误测试（重复5次）
            TestLog("INFO", "Step10-11", "间歇性CRC错误测试（5次）")
            for _ in range(5):
                TxCtrl.crc_correct = False
                time.sleep(cycle * 5 / 1000.0)
                TxCtrl.crc_correct = True
                time.sleep(cycle * 5 / 1000.0)

            # Step12: 最终读取DTC
            TestLog("INFO", "Step12", "读取DTC")
            ret = read_dtc(uds_node, e2e_dtc)
            if ret == DTC_E2E_DTC:
                TestLog("INFO", "E2E CRC接收", "间歇性错误测试：检测到E2E DTC")
            elif ret == DTC_OTHER_DTC:
                TestLog("INFO", "E2E CRC接收", "间歇性错误测试：检测到其他DTC")
            else:
                TestLog("INFO", "E2E CRC接收", "间歇性错误测试：未检测到DTC")

            stop_e2e_send_timer()
            TestLog("INFO", "E2E CRC接收", f"信号组 {name} 测试完成")

    except Exception as e:
        TestLog("FAIL", "E2E CRC接收", f"测试异常: {traceback.format_exc()}")
    finally:
        if uds_node:
            try:
                uds_node.close()
            except Exception:
                pass

def verify_can_counter_receive(profile_1a: bool,counter_error_type:str):
    cfg = load_e2e_config()
    if not cfg:
        TestLog("FAIL", "E2E配置", "加载E2E配置失败")
        return

    if can_power_setup_and_communication_check() != 0:
        TestLog("FAIL", "CAN E2E", "CAN通信检查失败")
        return

    is_canfd = not profile_1a
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    uds_node = get_can_node(sa, ta, fa, is_canfd=is_canfd)

    try:
        for idx, name in enumerate(cfg.sender_groups, start=1):
            f, g = cfg.frames.get(name), cfg.groups.get(name)
            if not f or not g:
                continue

            stop_e2e_send_timer()

            # 根据profile过滤
            if profile_1a and f.canfd == 1:
                continue
            if (not profile_1a) and f.canfd != 1:
                continue

            profile, _ = set_profile(bool(f.canfd))
            ch = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
            cycle = f.cycle if f.cycle and f.cycle > 0 else 100
            wait_sec = max(cycle * 20, 3000) / 1000.0  # DTC检测等待时间
            max_delta = g.max_delta_counter_init
            e2e_dtc = get_e2e_dtc(name, "Counter")

            TestLog("INFO", "E2E "+counter_error_type,
                   f"组#{idx}: {name}, ID=0x{f.id:x}, DLC={f.datalength}, DTC=0x{e2e_dtc:06X}" if e2e_dtc else
                   f"组#{idx}: {name}, ID=0x{f.id:x}, DLC={f.datalength}, DTC=未配置")

            if e2e_dtc is None:
                TestLog("WARNING", "E2E "+counter_error_type, f"信号组 {name} 未配置E2E DTC，跳过该组测试")
                continue

            # Step1: 启动DUT，发送正确E2E报文
            TestLog("INFO", "Step1", "开始发送正确的E2E_RxMsg")
            start_e2e_send_timer(ch, f.id, g, profile, f.datalength, cycle, is_canfd)
            time.sleep(6.0)  # 等待通信稳定

            # Step2: 清除DTC
            TestLog("INFO", "Step2", "清除DTC")
            if not clear_dtc(uds_node):
                stop_e2e_send_timer()
                continue

            # Step3-4: 等待后读取DTC，期望无DTC
            TestLog("INFO", "Step3-4", f"等待{wait_sec:.1f}s后读取DTC")
            time.sleep(wait_sec)
            ret = read_dtc(uds_node, e2e_dtc)
            if ret == DTC_COMM_ERROR:
                stop_e2e_send_timer()
                continue
            elif ret == DTC_NO_DTC:
                TestLog("PASS", f"E2E {counter_error_type}", "DUT未记录DTC（符合预期）")
            elif ret == DTC_E2E_DTC:
                TestLog("FAIL", f"E2E {counter_error_type}", "DUT记录了E2E DTC（不符合预期）")
            else:  # DTC_OTHER_DTC
                TestLog("WARNING", f"E2E {counter_error_type}", "DUT记录了其他DTC（非E2E相关）")

            # Step5-7: 发送错误Counter，等待后读取DTC，期望有E2E DTC
            TestLog("INFO", "Step5-7", "发送Counter丢失的E2E报文")
            TxCtrl.counter_delta =get_counter_delta(counter_error_type,max_delta)
            print(f"{TxCtrl.counter_delta=}")
            time.sleep(wait_sec)

            ret = read_dtc(uds_node, e2e_dtc)
            if ret == DTC_COMM_ERROR:
                stop_e2e_send_timer()
                continue
            elif ret == DTC_E2E_DTC:
                TestLog("PASS", f"E2E {counter_error_type}", "Counter丢失：DUT记录了E2E DTC（符合预期）")
            elif ret == DTC_NO_DTC:
                TestLog("FAIL", f"E2E {counter_error_type}", "Counter丢失：DUT未记录任何DTC（不符合预期）")
            else:  # DTC_OTHER_DTC
                TestLog("FAIL", f"E2E {counter_error_type}", "Counter丢失：DUT记录了其他DTC但非E2E DTC（不符合预期）")

            # Step8-9: 恢复正确Counter，清除DTC
            TestLog("INFO", "Step8-9", "恢复正确Counter，清除DTC")
            TxCtrl.counter_delta = 0
            time.sleep(wait_sec)
            clear_dtc(uds_node)

            if counter_error_type==Counter_Miss_Error:
                # Step10-12: 发送错误Counter（Counter的偏差=MaxDeltaCounter），等待后读取DTC，期望无E2E DTC
                TestLog("INFO", "Step10-12", "发送Counter丢失的E2E报文")
                TxCtrl.counter_delta =max_delta
                time.sleep(wait_sec)
                ret = read_dtc(uds_node, e2e_dtc)
                if ret == DTC_COMM_ERROR:
                    stop_e2e_send_timer()
                    continue
                elif ret == DTC_NO_DTC:
                    TestLog("PASS", f"E2E {counter_error_type}", "DUT未记录DTC（符合预期）")
                elif ret == DTC_E2E_DTC:
                    TestLog("FAIL", f"E2E {counter_error_type}", "DUT记录了E2E DTC（不符合预期）")
                else:  # DTC_OTHER_DTC
                    TestLog("WARNING", f"E2E {counter_error_type}", "DUT记录了其他DTC（非E2E相关）")

            stop_e2e_send_timer()
            TestLog("INFO", f"E2E {counter_error_type}", f"信号组 {name} 测试完成")

    except Exception as e:
        TestLog("FAIL", f"E2E {counter_error_type}", f"测试异常: {e}")
    finally:
        if uds_node:
            try:
                uds_node.close()
            except Exception:
                pass

def get_counter_delta(counter_err_type:str,max_delta:int=0):
    if counter_err_type==Counter_Miss_Error:
        return max_delta+1
    elif counter_err_type==Counter_Repeated_Error:
        return -1
    elif counter_err_type==Counter_Unorder_Error:
        return -2
    else:
        return 0