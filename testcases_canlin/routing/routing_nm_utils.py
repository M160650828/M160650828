import threading
import time

from uvtest.testlog import TestLog
from common.can_utils import canmsg_create, send_canmsg
from common.context import ctx, Direction
from common.utils import TimerCyclic
from env.config import DEFAULT_CAN_CHANNELS
from common.params import P
from slplus.time import sl_time


class NMWakeupState:
    wakeup_msg_send_flag = True  
    net_wakeup_flags = {}  

    @classmethod
    def set_flag(cls, net_name: str = None, value: bool = True):
        if net_name is None:
            cls.wakeup_msg_send_flag = value
        else:
            cls.net_wakeup_flags[net_name] = value

    @classmethod
    def get_flag(cls, net_name: str = None) -> bool:
        if net_name is None:
            return cls.wakeup_msg_send_flag
        return cls.net_wakeup_flags.get(net_name, False)

    @classmethod
    def stop_all(cls):
        cls.wakeup_msg_send_flag = False
        for net in list(cls.net_wakeup_flags.keys()):
            cls.net_wakeup_flags[net] = False

def wakeup_active_start():
    ctx.bob_ctrl.set_power('KL15', True)


def wakeup_active_stop():
    ctx.bob_ctrl.set_power('KL15', False)


def get_net_wakeup_config(net_name: str) -> dict:
    entries = P.ChannelMapping.normalized_entries
    for entry in entries:
        if entry.get('Net') == net_name:
            return {
                'WakeupMsgId': entry.get('WakeupMsgId_int', 0),
                'WakeupMsgDLC': entry.get('WakeupMsgDLC', 8),
                'WakeupMsgData': entry.get('WakeupMsgData_bytes', bytes(8)),
                'WakeupMsgPeriod_ms': entry.get('WakeupMsgPeriod_ms', 500),
                'CANoeCANChannel': entry.get('CANoeCANChannel', 1),
                'WakeupMsgCANType': entry.get('WakeupMsgCANType', 'CAN'),
                'NMMsgID': entry.get('NMMsgID_int', 0),
            }
    return None


def wakeup_passive_start(net_name: str = None):
    if net_name is not None:
        net_config = get_net_wakeup_config(net_name)
        if net_config is None:
            TestLog("WARNING", "", f"未找到网段 {net_name} 的唤醒配置，使用全局配置")
            net_name = None  

    def run():
        if net_name is not None:
            config = get_net_wakeup_config(net_name)
            can_channel = config['CANoeCANChannel']
            rWakeupMsgID = config['WakeupMsgId']
            rWakeupMsgDLC = config['WakeupMsgDLC']
            rWakeupMsgData = bytearray(config['WakeupMsgData'])[:rWakeupMsgDLC]
            send_cycle_ms = config['WakeupMsgPeriod_ms']
            is_canfd = config['WakeupMsgCANType'].upper() == 'CANFD'

            use_repeat_message = False
            rNimmediateSend = 0
            rTrepeatMessage_ms = 0

            TestLog("INFO", "", f"开始触发网段 {net_name} 的被动唤醒请求 (通道={can_channel}, ID=0x{rWakeupMsgID:X})")
        else:
            can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
            rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
            rNimmediateSend = P.NMInfo.NimmediateSend
            rTnormalCycle_ms = P.NMInfo.TnormalCycle_ms
            rTimmediateCycle_ms = P.NMInfo.TimmediateCycle_ms
            rWakeupMsgID = P.ECUInfo.WakeupMsgID_int
            rWakeupMsgDLC = P.ECUInfo.WakeupMsgDLC
            rWakeupMsgData = bytearray(P.ECUInfo.WakeupMsgData_bytes)[:rWakeupMsgDLC]
            rReptMsgBit0 = P.NMInfo.RepeatMessageBit0
            rActWupBit4 = 1
            is_canfd = False
            use_repeat_message = True
            send_cycle_ms = rTimmediateCycle_ms

            if rReptMsgBit0 == 1:
                rWakeupMsgData[1] |= 0x01  # RepeatMessageBitRequest = 1
            if rActWupBit4 == 1:
                rWakeupMsgData[1] &= 0xEF  # ActiveWakeupBit = 0

            TestLog("INFO", "", "开始触发被动唤醒请求")

        wakeup_msg_send_start_time = time.time()
        wakeup_send_counter = 0
        msg = canmsg_create(rWakeupMsgID, rWakeupMsgDLC, data=rWakeupMsgData,
                           rtr=0, fdf=1 if is_canfd else 0, brs=1 if is_canfd else 0, ext=0)

        while NMWakeupState.get_flag(net_name):
            send_canmsg(can_channel, msg)
            wakeup_send_counter += 1

            if net_name is None and use_repeat_message:
                if wakeup_send_counter == rNimmediateSend:
                    send_cycle_ms = rTnormalCycle_ms

                rReptMsgBit0 = P.NMInfo.RepeatMessageBit0
                if rReptMsgBit0 == 1:
                    if msg.payload[1] & 0x01 != 0:
                        repeat_message_bit_request = 1
                    else:
                        repeat_message_bit_request = 0
                    time_internal = time.time() - wakeup_msg_send_start_time
                    time_internal_ms = time_internal * 1000
                    if repeat_message_bit_request == 1 and time_internal_ms >= rTrepeatMessage_ms:
                        payload = list(msg.payload)
                        payload[1] &= 0xFE
                        msg.payload = bytes(payload)

            time.sleep(send_cycle_ms / 1000.0)

    NMWakeupState.set_flag(net_name, True)
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def wakeup_passive_stop(net_name: str = None):
    NMWakeupState.set_flag(net_name, False)


def wakeup_passive_stop_all():
    NMWakeupState.stop_all()


def build_rx_ecuCanChl_msg(messages):
    msg_list = [m for m in messages if m.channel == P.ECUInfo.CommCANChannelNum and m.direction == Direction.RX]
    return msg_list


def get_nm_message_list():
    msg_list = []
    for msg in build_rx_ecuCanChl_msg(ctx.can.messages):
        if msg.id == P.ECUInfo.NMMsgID_int:
            msg_list.append(msg)
    return msg_list


def check_all_networks_nm_messages(wait_time_s: float = 5.0) -> tuple:
    from .routing_module import TestLog

    results = []
    all_pass = True

    entries = P.ChannelMapping.normalized_entries

    for entry in entries:
        net_name = entry.get('Net', '')
        nm_msg_id = entry.get('NMMsgID_int', 0)
        channel = entry.get('CANoeCANChannel', 0)

        if nm_msg_id == 0:
            continue

        ctx.can.clear_messages()
        time.sleep(wait_time_s)

        msg_count = 0
        for msg in ctx.can.messages:
            if msg.id == nm_msg_id and msg.channel == channel:
                msg_count += 1

        received = msg_count > 0
        results.append({
            'net': net_name,
            'nm_msg_id': nm_msg_id,
            'channel': channel,
            'received': received,
            'msg_count': msg_count,
        })

        if received:
            TestLog("PASS", "", f"接收到DUT发送NM报文, Bus: {net_name}, ID: 0x{nm_msg_id:X}, 数量: {msg_count}")
        else:
            TestLog("FAIL", "", f"未接收到DUT发送NM报文, Bus: {net_name}, ID: 0x{nm_msg_id:X}")
            all_pass = False

    return all_pass, results


def wait_nm_message(timeout_ms=60000):
    start_time = sl_time().timestamp()
    timeout_s = timeout_ms / 1000.0
    while time.time() - start_time < timeout_s:
        nm_messages = get_nm_message_list()
        if len(nm_messages) > 0:
            return True, nm_messages
        time.sleep(0.1)
    return False, []


def wait_nm_message_stop(timeout_ms=60000):
    start_time = sl_time().timestamp()
    timeout_s = timeout_ms / 1000.0
    while time.time() - start_time < timeout_s:
        time.sleep(0.5)
        nm_messages = get_nm_message_list()
        if len(nm_messages) == 0:
            return True, time.time()

    time.sleep(2)
    nm_messages_before = len(get_nm_message_list())
    time.sleep(2)
    nm_messages_after = len(get_nm_message_list())
    if nm_messages_after <= nm_messages_before:
        return True, time.time()

    return False, None


def wait_dut_enter_sleep(Isleep_A, timeout_s=60):
    import traceback
    time.sleep(2)
    current_time = time.time()
    while True:
        if time.time() - current_time > timeout_s:
            TestLog("FAIL", "", f"超时通信未停止")
            return False, f"超时{timeout_s}s通信未停止"
        try:
            base_len = len(build_rx_ecuCanChl_msg(ctx.can.messages))
        except Exception:
            base_len = 0
        time.sleep(5)
        try:
            cur_len = len(build_rx_ecuCanChl_msg(ctx.can.messages))
        except Exception:
            cur_len = base_len
        if cur_len == base_len:
            TestLog("PASS", "", "通信停止")
            break

    current_time = time.time()
    while True:
        if time.time() - current_time > timeout_s:
            return False, f"超时{timeout_s}s未达到睡眠电流"
        sum_current = []
        for i in range(10):
            try:
                status, current = ctx.power_ctrl.get_current()
                if status is True:
                    sum_current.append(current)
            except Exception as e:
                TestLog("", "读取电流", f"读取失败: {traceback.format_exc()}")
                sum_current.append(99)
                continue
            time.sleep(0.001)
        if len(sum_current) > 0:
            avg_current = sum(sum_current) / len(sum_current)
            if avg_current <= Isleep_A:
                return True, "达到睡眠电流"
    return False, "未达到睡眠电流"

def get_nm_params():
    return {
        'Vnormal': P.NMInfo.Vnormal,
        'TNMtimeout_ms': P.NMInfo.TNMtimeout_ms,
        'TnormalCycle_ms': P.NMInfo.TnormalCycle_ms,
        'TpowerOnInitial_s': P.NMInfo.TpowerOnInitial_s,
        'NMmsgIDMin': P.NMInfo.NMmsgIDMin_int,
        'NMmsgIDMax': P.NMInfo.NMmsgIDMax_int,
        'WakeupMsgID': P.ECUInfo.WakeupMsgID_int,
        'WakeupMsgDLC': P.ECUInfo.WakeupMsgDLC,
        'WakeupMsgData': P.ECUInfo.WakeupMsgData_bytes,
        'ISleep': P.ECUInfo.ISleep,
    }


def send_and_check_routing_all_entries(routing_type: str, sender, cfg, step_name: str = "") -> bool:
    from .routing_module import check_routing, SEND_MODE_INCREMENT, SEND_MODE_SIGNAL

    all_passed = True
    entries = list(cfg.iter_entries_by_type(routing_type))

    if not entries:
        TestLog("WARNING", step_name, f"未找到 RoutingType 为 {routing_type} 的路由表项")
        return True  

    for idx, e in entries:
        src_id = e.get('SrcMsgId', 0)
        dest_id = e.get('DestMsgId', 0)
        src_net = e.get('SrcNet', '')
        dest_net = e.get('DestNet', '')

        ctx.can.set_info('routing_src_records', [])
        ctx.can.set_info('routing_dest_records', [])
        ctx.can.set_info('sRxMsgInfoList', {})

        if routing_type == "SignalRouting":
            sender.send(idx, e, mode=SEND_MODE_SIGNAL, step=step_name)
        else:
            sender.send(idx, e, mode=SEND_MODE_INCREMENT, step=step_name)

        ret, _ = check_routing(e, expect_count=5)

        if ret == 0:
            TestLog("PASS", step_name,
                    f"路由正常: 源网段={src_net} 源ID=0x{src_id:x} -> "
                    f"目标网段={dest_net} 目标ID=0x{dest_id:x}")
        else:
            TestLog("FAIL", step_name,
                    f"路由失败: 源网段={src_net} 源ID=0x{src_id:x} -> "
                    f"目标网段={dest_net} 目标ID=0x{dest_id:x}")
            all_passed = False

    return all_passed


def check_routing_stopped(sender, cfg, step_name: str = "") -> bool:
    from .routing_module import check_routing, SEND_MODE_INCREMENT

    all_stopped = True
    for routing_type in ["CycleMsg", "EventMsg"]:
        entries = list(cfg.iter_entries_by_type(routing_type))
        for idx, e in entries[:3]:  # 只检查前3个条目
            ctx.can.set_info('routing_dest_records', [])
            sender.send(idx, e, mode=SEND_MODE_INCREMENT, step=step_name)
            ret, _ = check_routing(e, expect_count=1, timeout_s=2.0)
            if ret == 0:
                TestLog("FAIL", step_name,
                        f"路由未停止: 目标ID=0x{e.get('DestMsgId', 0):x} 仍在接收")
                all_stopped = False
            break  

    return all_stopped


def send_nm_msg_on_channel(channel: int, duration_s: float = 5.0):
    nm_params = get_nm_params()
    msg = canmsg_create(
        nm_params['WakeupMsgID'],
        nm_params['WakeupMsgDLC'],
        data=nm_params['WakeupMsgData'],
        rtr=0, fdf=0, brs=0, ext=0
    )
    timer_id = f"nm_wakeup_{channel}"
    TimerCyclic.start(timer_id, nm_params['TnormalCycle_ms'], send_canmsg, channel, msg=msg)
    time.sleep(duration_s)
    TimerCyclic.stop(timer_id)


def send_app_msg_on_channel(channel: int, msg_id: int = 0x123, duration_s: float = 2.0):
    msg = canmsg_create(msg_id, 8, data=bytes([0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88]),
                        rtr=0, fdf=1, brs=1, ext=0)
    timer_id = f"app_wakeup_{channel}"
    TimerCyclic.start(timer_id, 100, send_canmsg, channel, msg=msg)
    time.sleep(duration_s)
    TimerCyclic.stop(timer_id)

def clear_routing_records():
    ctx.can.set_info('routing_src_records', [])
    ctx.can.set_info('routing_dest_records', [])
    ctx.can.set_info('sRxMsgInfoList', {})


def dut_power_on_and_wait_stable(voltage: float, tstable_s: float, kl15_on: bool = True,
                                  step_name: str = "Step1") -> bool:
    from common.wakeup import WakeupStart
    from .routing_module import check_can_communication_state

    ctx.power_ctrl.set_voltage(voltage)
    ctx.power_ctrl.on()
    ctx.bob_ctrl.set_power('KL30', True)
    ctx.bob_ctrl.set_power('KL15', kl15_on)

    if kl15_on:
        WakeupStart()

    time.sleep(tstable_s)

    ret = check_can_communication_state(tstable_s)
    if ret == 0:
        TestLog("PASS", step_name, "DUT正常通信")
        return True
    else:
        TestLog("WARNING", step_name, "DUT通信异常")
        return False


def prepare_dut_sleep(timeout_ms: int = 60000, wait_after_stop_s: float = 5.0,
                       step_name: str = "") -> bool:
    from common.wakeup import WakeupStop

    ctx.bob_ctrl.set_power('KL15', False)
    WakeupStop()
    wakeup_passive_stop()

    ret, _ = wait_nm_message_stop(timeout_ms=timeout_ms)
    if ret:
        TestLog("INFO", step_name, "DUT NM报文已停发，等待进入睡眠")
        time.sleep(wait_after_stop_s)
        return True
    else:
        TestLog("WARNING", step_name, "等待NM报文停发超时")
        return False


def send_and_check_signal_routing_all_entries(sender, cfg, step_name: str = "",
                                                expect_count: int = 5) -> bool:
    from .routing_module import check_routing, SEND_MODE_SIGNAL

    signal_routing_pass = True
    signal_entries = list(cfg.iter_signal_entries())

    if not signal_entries:
        TestLog("WARNING", step_name, "未找到信号路由类型的路由表项")
        return True 

    for idx, e in signal_entries:
        src_id = e.get('SrcMsgId', 0)
        dest_id = e.get('DestMsgId', 0)
        src_net = e.get('SrcNet', '')
        dest_net = e.get('DestNet', '')

        clear_routing_records()

        duration_ms = cfg.get_duration_ms(e)
        sender.send(idx, e, mode=SEND_MODE_SIGNAL, duration_ms=duration_ms, step=step_name)

        ret, _ = check_routing(e, expect_count=expect_count)
        if ret == 0:
            TestLog("PASS", step_name,
                    f"信号路由正常: 源网段={src_net} 源ID=0x{src_id:x} -> "
                    f"目标网段={dest_net} 目标ID=0x{dest_id:x}")
        else:
            TestLog("FAIL", step_name,
                    f"信号路由失败: 源网段={src_net} 源ID=0x{src_id:x} -> "
                    f"目标网段={dest_net} 目标ID=0x{dest_id:x}")
            signal_routing_pass = False

    return signal_routing_pass


def wakeup_by_nm_and_check_routing(net_name: str, route_entry: dict, sender, cfg,
                                    step_prefix: str = "") -> tuple:
    from common.wakeup import WakeupStop
    from .routing_module import check_routing, check_can_communication_state, SEND_MODE_INCREMENT

    net_config = get_net_wakeup_config(net_name)
    if net_config is None or net_config.get('WakeupMsgId', 0) == 0:
        TestLog("WARNING", "", f"网段 {net_name} 未配置WakeupMsgId，跳过")
        return False, False

    prepare_dut_sleep(timeout_ms=60000, wait_after_stop_s=5.0, step_name=f"{step_prefix}Step1")

    TestLog("INFO", f"{step_prefix}Step2",
            f"在网段 {net_name} 发送NM报文(ID=0x{net_config['WakeupMsgId']:X})唤醒DUT")
    wakeup_passive_start(net_name)
    time.sleep(3)

    ret = check_can_communication_state(wait_time=1)
    if ret != 0:
        TestLog("FAIL", "", f"网段 {net_name} NM报文无法唤醒网关")
        wakeup_passive_stop(net_name)
        return False, False

    TestLog("PASS", f"{step_prefix}Step2", f"网段 {net_name} NM报文唤醒成功，检测到DUT通信恢复")

    src_id = route_entry.get('SrcMsgId', 0)
    dest_id = route_entry.get('DestMsgId', 0)
    dest_net = route_entry.get('DestNet', '')

    TestLog("INFO", f"{step_prefix}Step3",
            f"发送报文: 源网段={net_name}, 源ID=0x{src_id:X}, 目标网段={dest_net}, 目标ID=0x{dest_id:X}")

    clear_routing_records()

    route_idx = 0
    for idx, e in cfg.iter_entries_by_type("CycleMsg"):
        if e.get('SrcMsgId') == src_id and e.get('SrcNet') == net_name:
            route_idx = idx
            break
    else:
        for idx, e in cfg.iter_entries_by_type("EventMsg"):
            if e.get('SrcMsgId') == src_id and e.get('SrcNet') == net_name:
                route_idx = idx
                break

    sender.send(route_idx, route_entry, mode=SEND_MODE_INCREMENT, step=f"{step_prefix}Step3")
    ret, _ = check_routing(route_entry, expect_count=10)

    wakeup_passive_stop(net_name)
    time.sleep(1)

    if ret == 0:
        TestLog("PASS", "", f"网段 {net_name} NM唤醒后路由功能正常")
        return True, True
    else:
        TestLog("FAIL", "", f"网段 {net_name} NM唤醒后路由功能异常")
        return True, False


def iter_valid_nm_networks_with_routing(channel_entries: list, msg_routing_entries: list,
                                         tested_nets: set = None, log_skipped: bool = True):
    if tested_nets is None:
        tested_nets = set()

    for ch_entry in channel_entries:
        net_name = ch_entry.get('Net', '')
        wakeup_msg_id = ch_entry.get('WakeupMsgId_int', 0)

        if net_name in tested_nets:
            continue

        if wakeup_msg_id == 0:
            if log_skipped:
                TestLog("WARNING", "", f"网段 {net_name} 不支持或未填写NM唤醒报文，跳过")
            tested_nets.add(net_name)
            continue

        route_entry = None
        for e in msg_routing_entries:
            if e.get('SrcNet', '') == net_name:
                route_entry = e
                break 

        if route_entry is None:
            if log_skipped:
                TestLog("INFO", "", f"网段 {net_name} 没有作为源网段的报文路由，跳过")
            tested_nets.add(net_name)
            continue

        tested_nets.add(net_name)
        net_config = get_net_wakeup_config(net_name)

        yield net_name, net_config, route_entry

