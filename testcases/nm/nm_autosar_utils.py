import threading
import time
import traceback

from uvtest.testlog import TestLog

from common.can_utils import canmsg_create, send_canmsg
from common.context import ctx, Direction
from common.utils import TimerCyclic
from env.config import DEFAULT_CAN_CHANNELS
from common.params import P
from collections import Counter
from testcases.nm.nm_module import nmctx
from slplus.time import sl_time


class NMAutoSarConstants:
    wakeup_msg_send_flag = True


def wakeup_active_start():
    """
        主动唤醒
    """
    ctx.bob_ctrl.set_power('KL15', True)


def wakeup_active_stop():
    ctx.bob_ctrl.set_power('KL15', False)


def wakeup_passive_start():
    def run():
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms  # 重复发送报文状态的保持时间
        rNimmediateSend = P.NMInfo.NimmediateSend  # 快速发送NM报文的帧数
        rTnormalCycle_ms = P.NMInfo.TnormalCycle_ms  # 正常发送NM报文的周期
        rTimmediateCycle_ms = P.NMInfo.TimmediateCycle_ms  # 快速发送NM报文的周期
        rWakeupMsgID = P.ECUInfo.WakeupMsgID_int
        rWakeupMsgDLC = P.ECUInfo.WakeupMsgDLC
        rWakeupMsgData = bytearray(P.ECUInfo.WakeupMsgData_bytes)[
            :rWakeupMsgDLC]  # [0x7F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        rReptMsgBit0 = P.NMInfo.RepeatMessageBit0
        rActWupBit4 = 1

        if rReptMsgBit0 == 1:
            rWakeupMsgData[1] |= 0x01  # RepeatMessageBitRequest = 1
        if rActWupBit4 == 1:
            rWakeupMsgData[1] &= 0xEF  # ActiveWakeupBit = 0

        TestLog("INFO", "", f"开始触发被动唤醒请求")

        # 快发NimmediateSend唤醒报文之后，切换到正常周期发送唤醒报文
        wakeup_msg_send_start_time = time.time()
        send_cycle_ms = rTimmediateCycle_ms  # 使用快发的周期
        wakeup_send_counter = 0  # 已发的报文计数器
        msg = canmsg_create(rWakeupMsgID, rWakeupMsgDLC, data=rWakeupMsgData, rtr=0, fdf=0, brs=0, ext=0)
        while NMAutoSarConstants.wakeup_msg_send_flag is True:
            send_canmsg(can_channel, msg)
            wakeup_send_counter += 1
            if wakeup_send_counter == rNimmediateSend:
                # 达到指定报文数量收，切换到正常周期
                send_cycle_ms = rTnormalCycle_ms

            if rReptMsgBit0 == 1:
                if msg.payload[1] & 0x01 != 0:
                    repeat_message_bit_request = 1
                else:
                    repeat_message_bit_request = 0
                time_internal = time.time() - wakeup_msg_send_start_time
                time_internal_ms = time_internal * 1000  # s -> ms
                if repeat_message_bit_request == 1 and time_internal_ms >= rTrepeatMessage_ms:
                    payload = list(msg.payload)
                    payload[1] &= 0xFE
                    msg.payload = bytes(payload)  # 修改发送的CAN报文的第一个字节

            time.sleep(send_cycle_ms / 1000.0)

    NMAutoSarConstants.wakeup_msg_send_flag = True
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread

def wakeup_passive_stop():
    TestLog("INFO", "", "取消被动唤醒请求")
    NMAutoSarConstants.wakeup_msg_send_flag = False



def wakeup_passive_normal_cycle_start():
    can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
    rWakeupMsgID = P.ECUInfo.WakeupMsgID_int
    rWakeupMsgDLC = P.ECUInfo.WakeupMsgDLC
    rWakeupMsgData = bytearray(P.ECUInfo.WakeupMsgData_bytes)[:rWakeupMsgDLC]
    rReptMsgBit0 = P.NMInfo.RepeatMessageBit0  # 是否支持RepeatMessageRequestBit状态位，1，支持，0，不支持
    rActWupBit4 = 1
    rNimmediateSend = P.NMInfo.NimmediateSend  # 快速发送NM报文的帧数
    rTimmediateCycle_ms = P.NMInfo.TimmediateCycle_ms  # 快速发送NM报文的周期
    rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms  # 重复发送报文状态的保持时间
    rTnormalCycle_ms = P.NMInfo.TnormalCycle_ms  # 正常发送NM报文的周期


    rWakeupMsgData[1] &= 0xFE  # RepeatMessageBitRequest = 0
    msg = canmsg_create(rWakeupMsgID, rWakeupMsgDLC, data=rWakeupMsgData, rtr=0, fdf=0, brs=0, ext=0)

    TestLog("INFO", "", f"开始触发被动唤醒请求")
    # 正常发
    TimerCyclic.start(1, rTnormalCycle_ms, send_canmsg, can_channel, msg=msg)


def wakeup_passive_normal_cycle_stop():
    TestLog("INFO", "", "取消被动唤醒请求")
    TimerCyclic.stop(1)


def wait_dut_send_first_msg(timeout_s=60):
    start_time = time.time()
    try:
        base_len = len(build_rx_ecuCanChl_msg(ctx.can.messages))
    except Exception:
        base_len = 0
    while True:
        if time.time() - start_time > timeout_s:
            return False
        try:
            cur_len = len(build_rx_ecuCanChl_msg(ctx.can.messages))
        except Exception:
            cur_len = 0
        if cur_len > base_len:
            return True
        time.sleep(0.01)


def wait_nm_message(timeout_ms=60000):
    start_time = sl_time().timestamp()
    timeout_s = timeout_ms / 1000.0
    nm_messages = []
    while time.time() - start_time < timeout_s:
        nm_messages = get_nm_message_list()
        if len(nm_messages) > 0:
            return True, nm_messages
        time.sleep(0.1)
    return False, []


def wait_nm_message_stop(timeout_ms=60000):
    start_time = sl_time().timestamp()
    timeout_s = (timeout_ms + P.NMInfo.TnormalCycle_ms * 1.2) / 1000.0
    while time.time() - start_time < timeout_s:
        nm_messages_before = len(get_nm_message_list())
        time.sleep(P.NMInfo.TnormalCycle_ms / 1000.0)
        nm_messages_after = len(get_nm_message_list())
        if nm_messages_after <= nm_messages_before:
            return True, time.time()
    #
    #
    #     time.sleep(0.5)
    #     nm_messages = get_nm_message_list()
    #     if len(nm_messages) == 0:
    #         return True, time.time()
    #
    # time.sleep(2)
    # nm_messages_before = len(get_nm_message_list())
    # time.sleep(2)
    # nm_messages_after = len(get_nm_message_list())
    # if nm_messages_after <= nm_messages_before:
    #     return True, time.time()

    return False, None

def wait_app_message_stop(timeout_ms=60000):
    start_time = sl_time().timestamp()
    timeout_s = (timeout_ms + P.NMInfo.TnormalCycle_ms * 1.2) / 1000.0
    while time.time() - start_time < timeout_s:
        app_messages_before = len(get_app_message_list())
        time.sleep(0.2)
        app_messages_after = len(get_app_message_list())
        if app_messages_after <= app_messages_before:
            return True, get_app_message_list()[-1].time_ms
    return False, None


def wait_dut_enter_sleep(Isleep_A, timeout_s=60):
    time.sleep(2)
    tnormal_cycle_ms = float(P.NMInfo.TnormalCycle_ms)
    tnm_timeout_ms = float(P.NMInfo.TNMtimeout_ms)
    twait_bus_sleep_ms = float(getattr(P.NMInfo, "TwaitBusSleep_ms", 0) or 0)
    quiet_time_ms = max(1000.0, tnormal_cycle_ms * 1.2)
    comm_stop_timeout_s = max(float(timeout_s), (tnm_timeout_ms + quiet_time_ms) / 1000.0)

    TestLog("INFO", "", f"等待通信停止: TNMtimeout={tnm_timeout_ms:.0f}ms, "
                         f"静默窗口={quiet_time_ms:.0f}ms, 超时={comm_stop_timeout_s:.1f}s")

    current_time = time.time()
    last_activity_time = time.time()
    last_msg_signature = None
    while True:
        if time.time() - current_time > comm_stop_timeout_s:
            TestLog("FAIL", "", f"超时通信未停止")
            return False, f"超时{comm_stop_timeout_s:.1f}s通信未停止"
        try:
            rx_messages = build_rx_ecuCanChl_msg(ctx.can.messages)
        except Exception:
            rx_messages = []

        if rx_messages:
            last_msg = rx_messages[-1]
            msg_signature = (len(rx_messages), last_msg.id, last_msg.time_ms, last_msg.payload_hex)
        else:
            msg_signature = (0, None, None, None)

        if msg_signature != last_msg_signature:
            last_msg_signature = msg_signature
            last_activity_time = time.time()

        silent_time_ms = (time.time() - last_activity_time) * 1000.0
        if silent_time_ms >= quiet_time_ms:
            TestLog("PASS", "", f"通信停止，RX报文静默{silent_time_ms:.0f}ms")
            break

        time.sleep(0.05)

    # 2、等待Prepare Bus Sleep/Bus Sleep过程完成
    if twait_bus_sleep_ms > 0:
        TestLog("INFO", "", f"通信停止后等待TwaitBusSleep={twait_bus_sleep_ms:.0f}ms，再检测睡眠电流")
        time.sleep(twait_bus_sleep_ms / 1000.0)

    # 3、静态电流 < Isleep_A
    current_time = time.time()
    current_sample_count = 10
    current_sample_interval_s = 0.1

    while True:
        if time.time() - current_time > timeout_s:
            return False, f"超时{timeout_s}s未达到睡眠电流"
        sum_current = []
        for _ in range(current_sample_count):
            try:
                status, current = ctx.power_ctrl.get_current()
                if status is True:
                    sum_current.append(current)
            except Exception:
                TestLog("", "读取电流", f"读取失败: {traceback.format_exc()}")
                continue
            time.sleep(current_sample_interval_s)
        TestLog("", "len(sum_current)", len(sum_current))
        TestLog("", "sum_current", sum_current)
        if not sum_current:
            TestLog("WARNING", "", "未读取到有效电流值，继续等待")
            continue
        avg_current = sum(sum_current) / len(sum_current)  # 计算最近约1s内有效采样平均值
        TestLog("", "avg_current", avg_current)
        if avg_current <= Isleep_A:
            return True, "达到睡眠电流"


def build_rx_ecuCanChl_msg(messages):
    """
	筛选ctx.can.messages中，ECU CAN通道上接收的CAN报文
    """
    msg = [m for m in messages if m.channel == P.ECUInfo.CommCANChannelNum and m.direction == Direction.RX]
    return msg


def get_nm_message_list():
    """
        从接收到的报文中，将NM报文过滤出来
    """
    rNMmsgIDMin = 0x400  # NM报文ID范围最小值
    rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
    msg_list = []
    for msg in (build_rx_ecuCanChl_msg(nmctx.can.messages)):
        # if not (rNMmsgIDMin <= msg.id <= rNMmsgIDMax):
        if not (msg.id == P.ECUInfo.NMMsgID_int):
            continue
        msg_list.append(msg)
    return msg_list


def check_unused_user_data_bytes(nm_msgs) -> bool:
    for nm_msg in nm_msgs:
        payload = bytes.fromhex(nm_msg.payload_hex)
        if len(payload) >= 8:
            for byte_idx in range(3, 8):
                if payload[byte_idx] != 0:
                    TestLog("FAIL", "", f"NM报文Byte{byte_idx}不为0，实际值: {hex(payload[byte_idx])}")
                    return False
    return True


def check_wakeup_source_bit(nm_msgs, expected_value: int) -> bool:
    for nm_msg in nm_msgs:
        payload = bytes.fromhex(nm_msg.payload_hex)
        if len(payload) >= 2:
            active_wakeup_bit = (payload[1] >> 4) & 0x01
            if active_wakeup_bit == expected_value:
                return True
    return False


def get_tx_and_rx_nm_message_list():
    """
        从接收到的报文中，将NM报文过滤出来
    """
    rNMmsgIDMin = 0x400  # NM报文ID范围最小值
    rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
    msg_list = []
    for msg in ctx.can.messages:
        if not (rNMmsgIDMin <= msg.id <= rNMmsgIDMax):
            continue
        msg_list.append(msg)
    return msg_list


def get_nm_message_period_ms():
    """
        从接收到的报文中，将NM报文的间隔
    """
    rNMmsgIDMin = 0x400  # NM报文ID范围最小值
    rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
    msg_list = []
    for msg in (build_rx_ecuCanChl_msg(nmctx.can.messages)):
        if not (msg.id == P.ECUInfo.NMMsgID_int):
            continue
        msg_list.append(msg.time_ms)

    if len(msg_list) == 0:
        return 0
    return sum(msg_list) / len(msg_list)


def get_app_message_list():
    """
        从接收到的报文中，将应用报文过滤出来
    """
    rNMmsgIDMin = 0x400  # NM报文ID范围最小值
    rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
    msg_list = []
    for msg in (build_rx_ecuCanChl_msg(ctx.can.messages)):
        if rNMmsgIDMin <= msg.id <= rNMmsgIDMax:
            continue
        msg_list.append(msg)
    return msg_list

def get_select_message_list(id):
    msg_list = []
    for msg in (build_rx_ecuCanChl_msg(ctx.can.messages)):
        if msg.id != id:
            continue
        msg_list.append(msg)
    return msg_list

def get_rx_message_list():
    """
        从获取到的报文中，将接收报文过滤出来
    """
    msg_list = []
    for msg in (build_rx_ecuCanChl_msg(ctx.can.messages)):
        msg_list.append(msg)
    return msg_list


def get_message_id_list():
    msg_id_list = []
    seen_ids = set()
    for msg in reversed(build_rx_ecuCanChl_msg(ctx.can.messages)):
        if msg.id not in seen_ids:
            msg_id_list.append(msg)
            seen_ids.add(msg.id)
    msg_id_list.reverse()
    return msg_id_list

def get__message_id():
    for msg in build_rx_ecuCanChl_msg(ctx.can.messages):
        pass
    return msg


def check_repeat_message_request_bit(nm_messages):
    # TODO 需要保存所有的报文
    rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms  # TODO 读配置表
    bit_change_flag = 1
    bit_change_time = 0
    for item in nm_messages:
        repeat_msg_req_bit = 1 if bytes.fromhex(item.payload_hex)[1] & 0x01 else 0
        internal_time = item.time_ms - nm_messages[0].time_ms
        if bit_change_flag == 1 and repeat_msg_req_bit == 0:
            bit_change_flag = 0
            bit_change_time = internal_time
        if internal_time > 1.1 * rTrepeatMessage_ms:
            if repeat_msg_req_bit != 0:
                TestLog("FAIL", "", f"期望结果:RepeatMessageRequestBit在TrepeatMessage时间之内一直为1，之后一直为0，"
                                    f"实际结果:RepeatMessageRequestBit = 1(TimeStamp = {internal_time} ms)，不满足要求")
                return -1
        else:
            if repeat_msg_req_bit != 1:
                TestLog("FAIL", "", f"期望结果:RepeatMessageRequestBit在TrepeatMessage时间之内一直为1，之后一直为0，"
                                    f"实际结果:RepeatMessageRequestBit = 1(TimeStamp = {internal_time} ms)，不满足要求")
                return -1

        # if internal_time * 1000 > 1.1 * rTrepeatMessage_ms:
        #     if repeat_msg_req_bit != 0:
        #         TestLog("FAIL", "", f"期望结果:RepeatMessageRequestBit在TrepeatMessage时间之内一直为1，之后一直为0，"
        #                             f"实际结果:RepeatMessageRequestBit = 1(TimeStamp = {internal_time * 1000} S)，不满足要求")
        #         return -1
        # else:
        #     if repeat_msg_req_bit != bit_change_flag:
        #         TestLog("FAIL", "", f"期望结果:RepeatMessageRequestBit在TrepeatMessage时间之内一直为1，之后一直为0，"
        #                             f"实际结果:RepeatMessageRequestBit = 1(TimeStamp = {internal_time * 1000} S)，不满足要求")
        #         return -1
    TestLog("PASS", "",
            f"期望结果:RepeatMessageRequestBit在TrepeatMessage({rTrepeatMessage_ms} ms)时间之内一直为1，之后一直为0，"
            f"实际结果:在{bit_change_time} ms之内为1,之后一直为0，满足要求")
    return 0


def check_UserData0_bit0(nm_messages):
    # TODO 需要保存所有的报文
    rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms  # TODO 读配置表
    bit_change_flag = 1
    bit_change_time = 0
    for item in nm_messages:
        UserData0_bit0 = 1 if bytes.fromhex(item.payload_hex)[2] & 0x01 else 0
        internal_time = item.time_ms - nm_messages[0].time_ms
        if bit_change_flag == 1 and UserData0_bit0 == 0:
            bit_change_flag = 0
            bit_change_time = internal_time
        if internal_time > 1.1 * rTrepeatMessage_ms:
            if UserData0_bit0 != 0:
                TestLog("FAIL", "", f"期望结果:UserData0 bit0在TrepeatMessage时间之内一直为1，之后一直为0，"
                                    f"实际结果:UserData0 bit0 = 1(持续时间TimeStamp = {internal_time} ms)，不满足要求")
                return -1
        else:
            if UserData0_bit0 != 1:
                TestLog("FAIL", "", f"期望结果:UserData0 bit0在TrepeatMessage时间之内一直为1，之后一直为0，"
                                    f"实际结果:UserData0 bit0 = 1(持续时间TimeStamp = {internal_time} ms)，不满足要求")
                return -1

    TestLog("PASS", "", f"期望结果UserData0 bit0在TrepeatMessage({rTrepeatMessage_ms} ms)时间之内一直为1，之后一直为0，"
                        f"实际结果:在{bit_change_time} ms之内为1,之后一直为0，满足要求")
    return 0


def check_active_wakeup_bit(nm_messages, expect_value):
    active_wakeup_bit = 0
    for item in nm_messages:
        active_wakeup_bit = 1 if bytes.fromhex(item.payload_hex)[1] & 0x10 else 0
        if active_wakeup_bit != expect_value:
            TestLog("FAIL", "", f"期望结果:ActiveWakeupBit = {expect_value}，"
                                f"实际结果:ActiveWakeupBit = {active_wakeup_bit}(TimeStamp = {item.time_ms} S)，不满足要求")
            return -1
    TestLog("PASS", "", f"期望结果:ActiveWakeupBit = {expect_value}，"
                        f"实际结果:ActiveWakeupBit = {active_wakeup_bit} 且保持不变，满足要求")
    return 0


def check_all_reserve_bit(nm_messages, expect_value):
    rBit1_CAL = P.NMInfo.ReserveBit1  # 是否支持ReserveBit1状态位，1，支持，0，不支持
    rBit2_CAL = P.NMInfo.ReserveBit2  # 是否支持ReserveBit2状态位，1，支持，0，不支持
    rBit3_CAL = P.NMInfo.ReserveBit3  # 是否支持ReserveBit3状态位，1，支持，0，不支持
    rBit5_CAL = P.NMInfo.ReserveBit5  # 是否支持ReserveBit5状态位，1，支持，0，不支持
    rBit6_CAL = P.NMInfo.ReserveBit6  # 是否支持ReserveBit6状态位，1，支持，0，不支持
    rBit7_CAL = P.NMInfo.ReserveBit7  # 是否支持ReserveBit7状态位，1，支持，0，不支持

    # 比较所有接收NM报文的ActiveWakeupBit是否与定义一致
    Bit1_Error = 0
    Bit2_Error = 0
    Bit3_Error = 0
    Bit5_Error = 0
    Bit6_Error = 0
    Bit7_Error = 0

    for item in nm_messages:
        ReserveBit1 = 1 if bytes.fromhex(item.payload_hex)[1] & 0x02 else 0
        ReserveBit2 = 1 if bytes.fromhex(item.payload_hex)[1] & 0x04 else 0
        ReserveBit3 = 1 if bytes.fromhex(item.payload_hex)[1] & 0x08 else 0
        ReserveBit5 = 1 if bytes.fromhex(item.payload_hex)[1] & 0x20 else 0
        ReserveBit6 = 1 if bytes.fromhex(item.payload_hex)[1] & 0x40 else 0
        ReserveBit7 = 1 if bytes.fromhex(item.payload_hex)[1] & 0x80 else 0
        if rBit1_CAL and not Bit1_Error and ReserveBit1 != 0 != expect_value:
            Bit1_Error = 1
            TestLog("FAIL", "", f"期望结果:ReserveBit(1) = {expect_value}，"
                                f"实际结果:ReserveBit(1) = {ReserveBit1}(TimeStamp = {item['timestamp']} S)，不满足要求")
        if rBit2_CAL and not Bit2_Error and ReserveBit2 != 0 != expect_value:
            Bit2_Error = 1
            TestLog("FAIL", "", f"期望结果:ReserveBit(2) = {expect_value}，"
                                f"实际结果:ReserveBit(2) = {ReserveBit2}(TimeStamp = {item['timestamp']} S)，不满足要求")
        if rBit3_CAL and not Bit3_Error and ReserveBit3 != 0 != expect_value:
            Bit3_Error = 1
            TestLog("FAIL", "", f"期望结果:ReserveBit(3) = {expect_value}，"
                                f"实际结果:ReserveBit(3) = {ReserveBit3}(TimeStamp = {item['timestamp']} S)，不满足要求")
        if rBit5_CAL and not Bit5_Error and ReserveBit5 != 0 != expect_value:
            Bit5_Error = 1
            TestLog("FAIL", "", f"期望结果:ReserveBit(5) = {expect_value}，"
                                f"实际结果:ReserveBit(5) = {ReserveBit5}(TimeStamp = {item['timestamp']} S)，不满足要求")
        if rBit6_CAL and not Bit6_Error and ReserveBit6 != 0 != expect_value:
            Bit6_Error = 1
            TestLog("FAIL", "", f"期望结果:ReserveBit(6) = {expect_value}，"
                                f"实际结果:ReserveBit(6) = {ReserveBit6}(TimeStamp = {item['timestamp']} S)，不满足要求")
        if rBit7_CAL and not Bit7_Error and ReserveBit7 != 0 != expect_value:
            Bit7_Error = 1
            TestLog("FAIL", "", f"期望结果:ReserveBit(7) = {expect_value}，"
                                f"实际结果:ReserveBit(7) = {ReserveBit7}(TimeStamp = {item['timestamp']} S)，不满足要求")

    if Bit1_Error or Bit2_Error or Bit3_Error or Bit5_Error or Bit6_Error or Bit7_Error:
        return -1
    else:
        if rBit1_CAL:
            TestLog("PASS", "", f"期望结果:ReserveBit(1) = {expect_value}，"
                                f"实际结果:ReserveBit(1) 一直为 {expect_value} 且保持不变，满足要求")
        if rBit2_CAL:
            TestLog("PASS", "", f"期望结果:ReserveBit(2) = {expect_value}，"
                                f"实际结果:ReserveBit(2) 一直为 {expect_value} 且保持不变，满足要求")
        if rBit3_CAL:
            TestLog("PASS", "", f"期望结果:ReserveBit(3) = {expect_value}，"
                                f"实际结果:ReserveBit(3) 一直为 {expect_value} 且保持不变，满足要求")
        if rBit5_CAL:
            TestLog("PASS", "", f"期望结果:ReserveBit(5) = {expect_value}，"
                                f"实际结果:ReserveBit(5) 一直为 {expect_value} 且保持不变，满足要求")
        if rBit6_CAL:
            TestLog("PASS", "", f"期望结果:ReserveBit(6) = {expect_value}，"
                                f"实际结果:ReserveBit(6) 一直为 {expect_value} 且保持不变，满足要求")
        if rBit7_CAL:
            TestLog("PASS", "", f"期望结果:ReserveBit(7) = {expect_value}，"
                                f"实际结果:ReserveBit(7) 一直为 {expect_value} 且保持不变，满足要求")
        return 0


def send_period(can_channel, msg, send_count, send_cycle_ms):
    def run():
        wakeup_send_counter = 0  # 已发的报文计数器
        while True:
            send_canmsg(can_channel, msg)
            wakeup_send_counter += 1
            if wakeup_send_counter == send_count:
                break
            time.sleep(send_cycle_ms / 1000.0)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join()
    return thread


def get_msg_first_ms(msg_id):
    # 获取指定id的首帧消息的周期
    tm = 0
    for index, msg in enumerate(build_rx_ecuCanChl_msg(ctx.can.messages)):
        if msg.id == msg_id:
            tm = msg.time_ms
            break
    return tm


def get_msg_first_app_msg_ms():
    rNMmsgIDMin = 0x400  # NM报文ID范围最小值
    rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
    # 获取指定id的首帧消息的周期
    tm = 0
    for index, msg in enumerate(build_rx_ecuCanChl_msg(ctx.can.messages)):
        if rNMmsgIDMin <= msg.id <= rNMmsgIDMax:
            continue
        tm = msg.time_ms
        break
    return tm


def get_msg_period_ms(msg_id):
    # 获取指定消息的周期
    tm_list = []
    for index, msg in enumerate(build_rx_ecuCanChl_msg(ctx.can.messages)):
        if msg.id == msg_id:
            tm_list.append(msg.time_ms)
            if len(tm_list) >= 3:
                break
    if len(tm_list) == 0 or len(tm_list) == 1:
        return 0
    if len(tm_list) == 2:
        return tm_list[1] - tm_list[0]

    intv1 = tm_list[1] - tm_list[0]
    intv2 = tm_list[2] - tm_list[1]
    return (intv1 + intv2) / 2


def check_repeat_message_state_after_active_wakeup(*args, **kwargs):
    rNMmsgIDMin = 0x400  # NM报文ID范围最小值
    rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
    rReptMsgBit0 = P.NMInfo.RepeatMessageBit0  # 是否支持RepeatMessageRequestBit状态位，1，支持，0，不支持
    rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms  # 重复发送报文状态的保持时间
    rTimmediateDeviation = P.NMInfo.TimmediateDeviation_pct  # 快速发送NM报文的周期偏移范围
    rTnormalDeviation = P.NMInfo.TnormalDeviation_pct  # 正常发送NM报文的周期偏移范围
    rTimmediateCycle_ms = P.NMInfo.TimmediateCycle_ms  # 快速发送NM报文的周期
    rNimmediateSend = P.NMInfo.NimmediateSend  # 快速发送NM报文的帧数
    rTnormalCycle_ms = P.NMInfo.TnormalCycle_ms  # 正常发送NM报文的周期
    rTimmediateSendMin_ms = rTimmediateCycle_ms * (1 - rTimmediateDeviation / 100)
    rTimmediateSendMax_ms = rTimmediateCycle_ms * (1 + rTimmediateDeviation / 100)
    rTnormalCycleMin_ms = rTnormalCycle_ms * (1 - rTnormalDeviation / 100)
    rTnormalCycleMax_ms = rTnormalCycle_ms * (1 + rTnormalDeviation / 100)

    PeriodError = 0
    RepeatBitError = 0
    PeriodErrorCountPrint = 0
    RepeatBitErrorCountPrint = 0
    DefaultErrorCount = 3  # 默认只打印3次错误

    nm_message = get_nm_message_list()
    if len(nm_message) == 0:
        TestLog("WARNING", "", f"期望结果:DUT首先快发 {rNimmediateSend} 帧NM报文，然后以正常周期发送NM报文，"
                        f"实际结果:总线未收到DUT发送的NM报文，无法判断")
        return 0
    for index, msg in enumerate(nm_message):
        internal_time_ms = msg.time_ms - nm_message[0].time_ms
        if internal_time_ms > rTrepeatMessage_ms:
            break

        period_ms = msg.time_ms - nm_message[index-1].time_ms
        if index > 0 and index < rNimmediateSend:
            if rTimmediateSendMin_ms <= period_ms <= rTimmediateSendMax_ms:
                TestLog("PASS", "",
                        f"期望结果:前 {rNimmediateSend} 帧NM报文，发送间隔满足快发周期({rTimmediateCycle_ms} ms)，"
                        f"实际结果:第 {index+1} 帧NM报文周期为{period_ms} ms(TimeStamp = {msg.time_ms / 1000} S)，满足要求")
            else:
                PeriodError = 1
                TestLog("FAIL", "",
                        f"期望结果:前 {rNimmediateSend} 帧NM报文，发送间隔满足快发周期({rTimmediateCycle_ms} ms)，"
                        f"实际结果:第 {index+1} 帧NM报文周期为{period_ms} ms(TimeStamp = {msg.time_ms / 1000} S)，不满足要求")

        elif index >= rNimmediateSend:
            if rTnormalCycleMin_ms <= period_ms <= rTnormalCycleMax_ms:
                TestLog("PASS", "",
                        f"期望结果:第 {rNimmediateSend} 帧NM报文之后，发送间隔满足正常发送周期({rTnormalCycle_ms} ms)，"
                        f"实际结果:第 {index+1} 帧NM报文周期为{period_ms} ms(TimeStamp = {msg.time_ms / 1000} S)，满足要求")
            else:
                PeriodError = 1
                PeriodErrorCountPrint += 1
                if PeriodErrorCountPrint <= DefaultErrorCount:
                    TestLog("FAIL", "",
                            f"期望结果:第 {rNimmediateSend} 帧NM报文之后，发送间隔满足正常发送周期({rTnormalCycle_ms} ms)，"
                            f"实际结果:第 {index+1} 帧NM报文周期为{period_ms} ms(TimeStamp = {msg.time_ms / 1000} S)，不满足要求")
        if rReptMsgBit0 == 1:
            RepeatMsgReqBit = 1 if bytes.fromhex(msg.payload_hex)[1] & 0x01 else 0
            if internal_time_ms < 0.9 * rTrepeatMessage_ms:
                if RepeatMsgReqBit == 1:
                    TestLog("PASS", "", f"期望结果:RepeatMessageRequestBit在{rTrepeatMessage_ms} ms 时间之内一直为1，"
                                        f"实际结果:RepeatMessageRequestBit在{internal_time_ms} ms 时间之内为1(TimeStamp = {msg.time_ms / 1000} S)，满足要求")
                else:
                    RepeatBitError = 1
                    RepeatBitErrorCountPrint += 1
                    TestLog("FAIL", "", f"期望结果:RepeatMessageRequestBit在{rTrepeatMessage_ms} ms 时间之内一直为1，"
                                        f"实际结果:RepeatMessageRequestBit在{internal_time_ms} ms 时间之内变为0(TimeStamp = {msg.time_ms / 1000} S)，不满足要求")
    if not PeriodError and not RepeatBitError:
        if rReptMsgBit0 == 1:
            TestLog("PASS", "",
                    f"期望结果:DUT首先快发 {rNimmediateSend} 帧NM报文，然后以正常周期发送NM报文，NM报文RepeatMessageRequestBit一直为1，"
                    "实际结果:与期望结果一致，满足要求")
        else:
            TestLog("PASS", "", f"期望结果:DUT首先快发 {rNimmediateSend} 帧NM报文，然后以正常周期发送NM报文，"
                                f"实际结果:与期望结果一致，满足要求")
        return 0
    return -1


def check_repeat_message_state_after_passive_wakeup(*args, **kwargs):
    rNMmsgIDMin = 0x400  # NM报文ID范围最小值
    rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
    rReptMsgBit0 = P.NMInfo.RepeatMessageBit0  # 是否支持RepeatMessageRequestBit状态位，1，支持，0，不支持
    rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms  # 重复发送报文状态的保持时间
    rTimmediateDeviation = P.NMInfo.TimmediateDeviation_pct  # 快速发送NM报文的周期偏移范围
    rTnormalDeviation = P.NMInfo.TnormalDeviation_pct  # 正常发送NM报文的周期偏移范围
    rTimmediateCycle_ms = P.NMInfo.TimmediateCycle_ms  # 快速发送NM报文的周期
    rNimmediateSend = P.NMInfo.NimmediateSend  # 快速发送NM报文的帧数
    rTnormalCycle_ms = P.NMInfo.TnormalCycle_ms  # 正常发送NM报文的周期
    rTimmediateSendMin_ms = rTimmediateCycle_ms * (1 - rTimmediateDeviation / 100)
    rTimmediateSendMax_ms = rTimmediateCycle_ms * (1 + rTimmediateDeviation / 100)
    rTnormalCycleMin_ms = rTnormalCycle_ms * (1 - rTnormalDeviation / 100)
    rTnormalCycleMax_ms = rTnormalCycle_ms * (1 + rTnormalDeviation / 100)

    PeriodError = 0
    RepeatBitError = 0
    PeriodErrorCountPrint = 0
    RepeatBitErrorCountPrint = 0
    DefaultErrorCount = 3  # 默认只打印3次错误

    nm_message = get_nm_message_list()
    if len(nm_message) == 0:
        TestLog("WARNING", "", f"期望结果:DUT以正常周期发送NM报文，"
                        f"实际结果:总线未收到DUT发送的NM报文，无法判断")
        return 0
    for index, msg in enumerate(get_nm_message_list()):
        internal_time_ms = msg.time_ms - nm_message[0].time_ms
        if internal_time_ms > rTrepeatMessage_ms:
            TestLog("INFO", "", f"超出rTrepeatMessage_ms，{internal_time_ms} = {msg.time_ms} - {nm_message[0].time_ms}")
            break

        period_ms = msg.time_ms - nm_message[index - 1].time_ms
        if index > 0:
            if rTnormalCycleMin_ms <= period_ms <= rTnormalCycleMax_ms:
                TestLog("PASS", "", f"期望结果:所有NM报文周期发送间隔均满足正常发送周期({rTnormalCycle_ms} ms)，"
                                    f"实际结果:第 {index+1} 帧NM报文周期为{period_ms} ms(TimeStamp = {msg.time_ms / 1000} S)，满足要求")
            else:
                PeriodError = 1
                PeriodErrorCountPrint += 1
                if PeriodErrorCountPrint <= DefaultErrorCount:
                    TestLog("FAIL", "", f"期望结果:所有NM报文周期发送间隔均满足正常发送周期({rTnormalCycle_ms} ms)，"
                                        f"实际结果:第 {index+1} 帧NM报文周期为{period_ms} ms(TimeStamp = {msg.time_ms / 1000} S)，不满足要求")
        if rReptMsgBit0 == 1:
            RepeatMsgReqBit = 1 if bytes.fromhex(msg.payload_hex)[1] & 0x01 else 0
            if internal_time_ms < 0.9 * rTrepeatMessage_ms:
                if RepeatMsgReqBit == 1:
                    TestLog("PASS", "", f"期望结果:RepeatMessageRequestBit在{rTrepeatMessage_ms} ms 时间之内一直为1，"
                                        f"实际结果:RepeatMessageRequestBit在{internal_time_ms} ms 时间之内为1(TimeStamp = {msg.time_ms / 1000} S)，满足要求")
                else:
                    RepeatBitError = 1
                    RepeatBitErrorCountPrint += 1
                    TestLog("FAIL", "", f"期望结果:RepeatMessageRequestBit在{rTrepeatMessage_ms} ms 时间之内一直为1，"
                                        f"实际结果:RepeatMessageRequestBit在{internal_time_ms} ms 时间之内变为0(TimeStamp = {msg.time_ms / 1000} S)，不满足要求")
    if not PeriodError and not RepeatBitError:
        if rReptMsgBit0 == 1:
            TestLog("PASS", "", f"期望结果:DUT以正常周期发送NM报文，NM报文RepeatMessageRequestBit一直为1，"
                                "实际结果:所有NM报文发送间隔均满足正常发送周期，NM报文RepeatMessageRequestBit一直为1")
        else:
            TestLog("PASS", "", f"期望结果:DUT以正常周期发送NM报文，"
                                f"实际结果:所有NM报文发送间隔均满足正常发送周期")
        return 0
    return -1


def check_normal_state(*args, **kwargs):
    rNMmsgIDMin = 0x400  # NM报文ID范围最小值
    rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
    rReptMsgBit0 = P.NMInfo.RepeatMessageBit0  # 是否支持RepeatMessageRequestBit状态位，1，支持，0，不支持
    rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms  # 重复发送报文状态的保持时间
    rTimmediateDeviation = P.NMInfo.TimmediateDeviation_pct  # 快速发送NM报文的周期偏移范围
    rTnormalDeviation = P.NMInfo.TnormalDeviation_pct  # 正常发送NM报文的周期偏移范围
    rTimmediateCycle_ms = P.NMInfo.TimmediateCycle_ms  # 快速发送NM报文的周期
    rNimmediateSend = P.NMInfo.NimmediateSend  # 快速发送NM报文的帧数
    rTnormalCycle_ms = P.NMInfo.TnormalCycle_ms  # 正常发送NM报文的周期
    rTimmediateSendMin_ms = rTimmediateCycle_ms * (1 - rTimmediateDeviation / 100)
    rTimmediateSendMax_ms = rTimmediateCycle_ms * (1 + rTimmediateDeviation / 100)
    rTnormalCycleMin_ms = rTnormalCycle_ms * (1 - rTnormalDeviation / 100)
    rTnormalCycleMax_ms = rTnormalCycle_ms * (1 + rTnormalDeviation / 100)

    PeriodError = 0
    RepeatBitError = 0
    PeriodErrorCountPrint = 0
    RepeatBitErrorCountPrint = 0
    DefaultErrorCount = 3  # 默认只打印3次错误

    nm_message = get_nm_message_list()
    if len(nm_message) == 0:
        TestLog("WARNING", "", f"期望结果:DUT以正常周期发送NM报文，"
                        f"实际结果:总线未收到DUT发送的NM报文，无法判断")
        return 0
    for index, msg in enumerate(nm_message):
        internal_time_ms = msg.time_ms - nm_message[0].time_ms

        # 1.1*rTrepeatMessage之内的NM报文不检测
        if internal_time_ms < 1.1 * rTrepeatMessage_ms:
            continue

        if index > 0:
            period_ms = msg.time_ms - nm_message[index - 1].time_ms
            if rTnormalCycleMin_ms <= period_ms <= rTnormalCycleMax_ms:
                TestLog("PASS", "", f"期望结果:所有NM报文发送间隔均满足正常发送周期({rTnormalCycle_ms} ms)，"
                                    f"实际结果:第 {index+1} 帧NM报文周期为{period_ms} ms(TimeStamp = {msg.time_ms / 1000} S)，满足要求")
            else:
                PeriodError = 1
                PeriodErrorCountPrint += 1
                if PeriodErrorCountPrint <= DefaultErrorCount:
                    TestLog("FAIL", "", f"期望结果:所有NM报文周期发送间隔均满足正常发送周期({rTnormalCycle_ms} ms)，"
                                        f"实际结果:第 {index+1} 帧NM报文周期为{period_ms} ms(TimeStamp = {msg.time_ms / 1000} S)，不满足要求")
        if rReptMsgBit0 == 1:
            RepeatMsgReqBit = 1 if bytes.fromhex(msg.payload_hex)[1] & 0x01 else 0
            if RepeatMsgReqBit == 0:
                TestLog("PASS", "", f"期望结果:RepeatMessageRequestBit在{rTrepeatMessage_ms} ms 时间之后一直为0，"
                                    f"实际结果:RepeatMessageRequestBit在{internal_time_ms} ms 时间之后为0(TimeStamp = {msg.time_ms / 1000} S)，满足要求")
            else:
                RepeatBitError = 1
                RepeatBitErrorCountPrint += 1
                TestLog("FAIL", "", f"期望结果:RepeatMessageRequestBit在{rTrepeatMessage_ms} ms 时间之后一直为0，"
                                    f"实际结果:RepeatMessageRequestBit在{internal_time_ms} ms 时间之后变为1(TimeStamp = {msg.time_ms / 1000} S)，不满足要求")
    if not PeriodError and not RepeatBitError:
        if rReptMsgBit0 == 1:
            TestLog("PASS", "", f"期望结果:DUT以正常周期发送NM报文，NM报文RepeatMessageRequestBit一直为0，"
                                "实际结果:所有NM报文发送间隔均满足正常发送周期，NM报文RepeatMessageRequestBit一直为0")
        else:
            TestLog("PASS", "", f"期望结果:DUT以正常周期发送NM报文，"
                                f"实际结果:所有NM报文发送间隔均满足正常发送周期")
        return 0
    return -1

def check_readySleep_to_normal_state(*args, **kwargs):
    rNMmsgIDMin = 0x400  # NM报文ID范围最小值
    rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
    rReptMsgBit0 = P.NMInfo.RepeatMessageBit0  # 是否支持RepeatMessageRequestBit状态位，1，支持，0，不支持
    rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms  # 重复发送报文状态的保持时间
    rTimmediateDeviation = P.NMInfo.TimmediateDeviation_pct  # 快速发送NM报文的周期偏移范围
    rTnormalDeviation = P.NMInfo.TnormalDeviation_pct  # 正常发送NM报文的周期偏移范围
    rTimmediateCycle_ms = P.NMInfo.TimmediateCycle_ms  # 快速发送NM报文的周期
    rNimmediateSend = P.NMInfo.NimmediateSend  # 快速发送NM报文的帧数
    rTnormalCycle_ms = P.NMInfo.TnormalCycle_ms  # 正常发送NM报文的周期
    rTimmediateSendMin_ms = rTimmediateCycle_ms * (1 - rTimmediateDeviation / 100)
    rTimmediateSendMax_ms = rTimmediateCycle_ms * (1 + rTimmediateDeviation / 100)
    rTnormalCycleMin_ms = rTnormalCycle_ms * (1 - rTnormalDeviation / 100)
    rTnormalCycleMax_ms = rTnormalCycle_ms * (1 + rTnormalDeviation / 100)

    PeriodError = 0
    RepeatBitError = 0
    PeriodErrorCountPrint = 0
    RepeatBitErrorCountPrint = 0
    DefaultErrorCount = 3  # 默认只打印3次错误

    nm_message = get_nm_message_list()
    if len(nm_message) == 0:
        TestLog("WARNING", "", f"期望结果:DUT以正常周期发送NM报文，"
                        f"实际结果:总线未收到DUT发送的NM报文，无法判断")
        return 0

    for index, msg in enumerate(nm_message):
        if index > 0:
            period_ms = msg.time_ms - nm_message[index - 1].time_ms
            if rTnormalCycleMin_ms <= period_ms <= rTnormalCycleMax_ms:
                TestLog("PASS", "", f"期望结果:所有NM报文发送间隔均满足正常发送周期({rTnormalCycle_ms} ms)，"
                                    f"实际结果:第 {index+1} 帧NM报文周期为{period_ms} ms(TimeStamp = {msg.time_ms / 1000} S)，满足要求")
            else:
                PeriodError = 1
                PeriodErrorCountPrint += 1
                if PeriodErrorCountPrint <= DefaultErrorCount:
                    TestLog("FAIL", "", f"期望结果:所有NM报文周期发送间隔均满足正常发送周期({rTnormalCycle_ms} ms)，"
                                        f"实际结果:第 {index+1} 帧NM报文周期为{period_ms} ms(TimeStamp = {msg.time_ms / 1000} S)，不满足要求")

    if not PeriodError:
        TestLog("PASS", "", f"期望结果:DUT以正常周期发送NM报文，"
                            f"实际结果:所有NM报文发送间隔均满足正常发送周期")
        return 0
    return -1

def check_nmPdu_send_and_appMsg_send(*args, **kwargs):
    rNMmsgIDMin = 0x400  # NM报文ID范围最小值
    rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
    rReptMsgBit0 = P.NMInfo.RepeatMessageBit0  # 是否支持RepeatMessageRequestBit状态位，1，支持，0，不支持
    rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms  # 重复发送报文状态的保持时间
    rTimmediateDeviation = P.NMInfo.TimmediateDeviation_pct  # 快速发送NM报文的周期偏移范围
    rTnormalDeviation = P.NMInfo.TnormalDeviation_pct  # 正常发送NM报文的周期偏移范围
    rTimmediateCycle_ms = P.NMInfo.TimmediateCycle_ms  # 快速发送NM报文的周期
    rNimmediateSend = P.NMInfo.NimmediateSend  # 快速发送NM报文的帧数
    rTnormalCycle_ms = P.NMInfo.TnormalCycle_ms  # 正常发送NM报文的周期
    rTimmediateSendMin_ms = rTimmediateCycle_ms * (1 - rTimmediateDeviation / 100)
    rTimmediateSendMax_ms = rTimmediateCycle_ms * (1 + rTimmediateDeviation / 100)
    rTnormalCycleMin_ms = rTnormalCycle_ms * (1 - rTnormalDeviation / 100)
    rTnormalCycleMax_ms = rTnormalCycle_ms * (1 + rTnormalDeviation / 100)
    rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms

    TestEndTime = time.time() * 1000
    SelectAppMsg = 0
    MaxSendCount = 0

    messages = build_rx_ecuCanChl_msg(ctx.can.messages)
    # 过滤掉在 rNMmsgIDMin 和 rNMmsgIDMax 之间的消息
    filtered_ids = [
        msg.id for msg in messages
        if not (rNMmsgIDMin <= msg.id <= rNMmsgIDMax)
    ]
    # 统计出现次数最多的 msg.id
    SelectAppMsg, MaxSendCount = Counter(filtered_ids).most_common(1)[0]
    TestLog("INFO", "", f"选取发送帧数最多(Count = {MaxSendCount})的报文(ID = {SelectAppMsg: #x})")

    # 获取最后一帧NM报文的时间
    nm_message = get_nm_message_list()
    lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else 0

    # 获取最后一帧APP报文的时间
    lastRxAPPMsgTimeStamp_ms = 0
    for msg in reversed(build_rx_ecuCanChl_msg(ctx.can.messages)):
        if msg.id == SelectAppMsg:
            lastRxAPPMsgTimeStamp_ms = msg.time_ms
            break

    NMMsgInternal = TestEndTime - lastRxNMMsgTimeStamp_ms
    AppMsgInternal = TestEndTime - lastRxAPPMsgTimeStamp_ms

    # 在rTNMtimeout时间内收到了NM报文和应用报文

    DefaultErrorCount = 3  # 默认只打印3次错误
    nm_message = get_nm_message_list()
    select_app_message = get_select_message_list(SelectAppMsg)
    if NMMsgInternal <= rTNMtimeout_ms and AppMsgInternal <= rTNMtimeout_ms:
        PeriodError = 0
        PeriodErrorCountPrint = 0
        for index, msg in enumerate(nm_message):
            if index == 0:
                continue
            period_ms = msg.time_ms - nm_message[index - 1].time_ms
            if not(rTnormalCycleMin_ms <= period_ms <= rTnormalCycleMax_ms):
                PeriodError = 1
                PeriodErrorCountPrint += 1
                if PeriodErrorCountPrint <= DefaultErrorCount:
                    TestLog("FAIL", "", f"期望结果:所有NM报文周期发送间隔均满足正常发送周期({rTnormalCycle_ms} ms)，"
                                        f"实际结果:第 {index + 1} 帧NM报文周期为{period_ms} ms(TimeStamp = {msg.time_ms / 1000} S)，不满足要求")
        if not PeriodError:
            TestLog("PASS", "", f"期望结果:DUT以正常周期发送NM报文，"
                                f"实际结果:所有NM报文发送间隔均满足正常发送周期")

        PeriodError = 0
        PeriodErrorCountPrint = 0
        periodAvg = 0
        periodAvg = get_msg_period_ms(SelectAppMsg)
        for index, msg in enumerate(select_app_message):
            if index == 0:
                continue
            period_ms = msg.time_ms - select_app_message[index - 1].time_ms
            if not(period_ms <= 2 * periodAvg):
                PeriodError = 1
                PeriodErrorCountPrint += 1
                if PeriodErrorCountPrint <= DefaultErrorCount:
                    TestLog("FAIL", "", f"期望结果:所有NM报文周期发送间隔均满足正常发送周期({rTnormalCycle_ms} ms)，"
                                        f"实际结果:第 {index + 1} 帧NM报文周期为{period_ms} ms(TimeStamp = {msg.time_ms / 1000} S)，不满足要求")
        if not PeriodError:
            TestLog("PASS", "", f"期望结果:DUT以正常周期发送APP报文，"
                                f"实际结果:所有APP报文{SelectAppMsg: #x}发送间隔均满足正常发送周期")

def check_appMsg_send(*args, **kwargs):
    rNMmsgIDMin = 0x400  # NM报文ID范围最小值
    rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
    rReptMsgBit0 = P.NMInfo.RepeatMessageBit0  # 是否支持RepeatMessageRequestBit状态位，1，支持，0，不支持
    rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms  # 重复发送报文状态的保持时间
    rTimmediateDeviation = P.NMInfo.TimmediateDeviation_pct  # 快速发送NM报文的周期偏移范围
    rTnormalDeviation = P.NMInfo.TnormalDeviation_pct  # 正常发送NM报文的周期偏移范围
    rTimmediateCycle_ms = P.NMInfo.TimmediateCycle_ms  # 快速发送NM报文的周期
    rNimmediateSend = P.NMInfo.NimmediateSend  # 快速发送NM报文的帧数
    rTnormalCycle_ms = P.NMInfo.TnormalCycle_ms  # 正常发送NM报文的周期
    rTimmediateSendMin_ms = rTimmediateCycle_ms * (1 - rTimmediateDeviation / 100)
    rTimmediateSendMax_ms = rTimmediateCycle_ms * (1 + rTimmediateDeviation / 100)
    rTnormalCycleMin_ms = rTnormalCycle_ms * (1 - rTnormalDeviation / 100)
    rTnormalCycleMax_ms = rTnormalCycle_ms * (1 + rTnormalDeviation / 100)
    rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms

    TestEndTime = time.time() * 1000
    SelectAppMsg = 0
    MaxSendCount = 0

    messages = build_rx_ecuCanChl_msg(ctx.can.messages)
    # 过滤掉在 rNMmsgIDMin 和 rNMmsgIDMax 之间的消息
    filtered_ids = [
        msg.id for msg in messages
        if not (rNMmsgIDMin <= msg.id <= rNMmsgIDMax)
    ]
    # 统计出现次数最多的 msg.id
    SelectAppMsg, MaxSendCount = Counter(filtered_ids).most_common(1)[0]
    TestLog("INFO", "", f"选取发送帧数最多(Count = {MaxSendCount})的报文(ID = {SelectAppMsg: #x})")

    # 获取最后一帧APP报文的时间
    lastRxAPPMsgTimeStamp_ms = 0
    for msg in reversed(build_rx_ecuCanChl_msg(ctx.can.messages)):
        if msg.id == SelectAppMsg:
            lastRxAPPMsgTimeStamp_ms = msg.time_ms
            break

    AppMsgInternal = TestEndTime - lastRxAPPMsgTimeStamp_ms

    # 在rTNMtimeout时间内收到了NM报文和应用报文

    DefaultErrorCount = 3  # 默认只打印3次错误
    nm_message = get_nm_message_list()
    select_app_message = get_select_message_list(SelectAppMsg)
    if AppMsgInternal <= rTNMtimeout_ms:
        PeriodError = 0
        PeriodErrorCountPrint = 0
        periodAvg = 0
        periodAvg = get_msg_period_ms(SelectAppMsg)
        for index, msg in enumerate(select_app_message):
            if index == 0:
                continue
            period_ms = msg.time_ms - select_app_message[index - 1].time_ms
            if not (period_ms <= 2 * periodAvg):
                PeriodError = 1
                PeriodErrorCountPrint += 1
                if PeriodErrorCountPrint <= DefaultErrorCount:
                    TestLog("FAIL", "", f"期望结果:所有NM报文周期发送间隔均满足正常发送周期({rTnormalCycle_ms} ms)，"
                                        f"实际结果:第 {index + 1} 帧NM报文周期为{period_ms} ms(TimeStamp = {msg.time_ms / 1000} S)，不满足要求")
        if not PeriodError:
            TestLog("PASS", "", f"期望结果:DUT以正常周期发送APP报文，"
                                f"实际结果:所有APP报文{SelectAppMsg: #x}发送间隔均满足正常发送周期")

    #
    # PeriodError = 0
    # PeriodErrorCountPrint = 0
    # DefaultErrorCount = 3  # 默认只打印3次错误
    #
    # nm_message = get_nm_message_list()
    # if len(nm_message)
    # for index, msg in enumerate(nm_message):
    #     if index > 0:
    #         period_ms = msg.time_ms - nm_message[index - 1].time_ms
    #         if rTnormalCycleMin_ms <= period_ms <= rTnormalCycleMax_ms:
    #             TestLog("PASS", "", f"期望结果:所有NM报文发送间隔均满足正常发送周期({rTnormalCycle_ms} ms)，"
    #                                 f"实际结果:第 {index+1} 帧NM报文周期为{period_ms} ms(TimeStamp = {msg.time_ms / 1000} S)，满足要求")
    #         else:
    #             PeriodError = 1
    #             PeriodErrorCountPrint += 1
    #             if PeriodErrorCountPrint <= DefaultErrorCount:
    #                 TestLog("FAIL", "", f"期望结果:所有NM报文周期发送间隔均满足正常发送周期({rTnormalCycle_ms} ms)，"
    #                                     f"实际结果:第 {index+1} 帧NM报文周期为{period_ms} ms(TimeStamp = {msg.time_ms / 1000} S)，不满足要求")
    #
    # if not PeriodError:
    #     TestLog("PASS", "", f"期望结果:DUT以正常周期发送NM报文，"
    #                         f"实际结果:所有NM报文发送间隔均满足正常发送周期")
    #     return 0
    # return -1


def check_repeat_message_state(testStartTime_ms, testEndTime_ms):
    rNMmsgIDMin = 0x400  # NM报文ID范围最小值
    rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
    rReptMsgBit0 = P.NMInfo.RepeatMessageBit0  # 是否支持RepeatMessageRequestBit状态位，1，支持，0，不支持
    rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms  # 重复发送报文状态的保持时间
    rTimmediateDeviation = P.NMInfo.TimmediateDeviation_pct  # 快速发送NM报文的周期偏移范围
    rTnormalDeviation = P.NMInfo.TnormalDeviation_pct  # 正常发送NM报文的周期偏移范围
    rTimmediateCycle_ms = P.NMInfo.TimmediateCycle_ms  # 快速发送NM报文的周期
    rNimmediateSend = P.NMInfo.NimmediateSend  # 快速发送NM报文的帧数
    rTnormalCycle_ms = P.NMInfo.TnormalCycle_ms  # 正常发送NM报文的周期
    rTimmediateSendMin_ms = rTimmediateCycle_ms * (1 - rTimmediateDeviation / 100)
    rTimmediateSendMax_ms = rTimmediateCycle_ms * (1 + rTimmediateDeviation / 100)
    rTnormalCycleMin_ms = rTnormalCycle_ms * (1 - rTnormalDeviation / 100)
    rTnormalCycleMax_ms = rTnormalCycle_ms * (1 + rTnormalDeviation / 100)

    PeriodError = 0
    RepeatBitError = 0
    PeriodErrorCountPrint = 0
    RepeatBitErrorCountPrint = 0
    DefaultErrorCount = 3  # 默认只打印3次错误

    nm_message = get_nm_message_list()
    for index, msg in enumerate(nm_message):
        internal_time_ms = msg.time_ms - nm_message[0].time_ms

        # 只判断（StartTime，EndTime）时间之内的报文
        if internal_time_ms < testStartTime_ms or internal_time_ms > testEndTime_ms:
            continue

        period_ms = msg.time_ms - nm_message[index-1].time_ms
        if rTnormalCycleMin_ms <= period_ms <= rTnormalCycleMax_ms:
            TestLog("PASS", "", f"期望结果:DUT以正常周期({rTnormalCycle_ms} ms)发送NM报文，"
                                f"实际结果:第 {index+1} 帧NM报文周期为{period_ms} ms(TimeStamp = {msg.time_ms / 1000} S)，满足要求")
        else:
            PeriodError = 1
            PeriodErrorCountPrint += 1
            if PeriodErrorCountPrint <= DefaultErrorCount:
                TestLog("FAIL", "", f"期望结果:DUT以正常周期({rTnormalCycle_ms} ms)发送NM报文，"
                                    f"实际结果:第 {index+1} 帧NM报文周期为{period_ms} ms(TimeStamp = {msg.time_ms / 1000} S)，不满足要求")
        if rReptMsgBit0 == 1:
            RepeatMsgReqBit = 1 if bytes.fromhex(msg.payload_hex)[1] & 0x01 else 0
            if RepeatMsgReqBit == 1:
                TestLog("PASS", "", f"期望结果:RepeatMessageRequestBit在{rTrepeatMessage_ms} ms 时间之内一直为1，"
                                    f"实际结果:RepeatMessageRequestBit在{internal_time_ms} ms 时间之内变为0(TimeStamp = {msg.time_ms / 1000} S)，满足要求")
            else:
                RepeatBitError = 1
                RepeatBitErrorCountPrint += 1
                TestLog("FAIL", "", f"期望结果:RepeatMessageRequestBit在{rTrepeatMessage_ms} ms 时间之内一直为1，"
                                    f"实际结果:所有NM报文发送间隔均满足正常发送周期，NM报文RepeatMessageRequestBit一直为1")
    if not PeriodError and not RepeatBitError:
        if rReptMsgBit0 == 1:
            TestLog("PASS", "", f"期望结果:DUT以正常周期发送NM报文，RepeatMessageRequestBit一直为1，"
                                "实际结果:所有NM报文发送间隔均满足正常发送周期，NM报文RepeatMessageRequestBit一直为1")
        else:
            TestLog("PASS", "", f"期望结果:DUT以正常周期发送NM报文，"
                                f"实际结果:所有NM报文发送间隔均满足正常发送周期")
        return 0
    return -1


def check_ready_sleep_state():
    app_msgs = get_app_message_list()
    nm_msgs = get_nm_message_list()

    if len(nm_msgs) == 0:
        if len(app_msgs) > 0:
            TestLog("PASS", "", "期望结果:DUT停止发送NM报文，正常发送应用报文，"
                                "实际结果:总线未接收到NM报文，接收到DUT发送的应用报文")
            return 0
        else:
            TestLog("FAIL", "", "期望结果:DUT停止发送NM报文，正常发送应用报文，"
                                "实际结果:总线未接收到任何报文")
            return -1
    else:
        TestLog("FAIL", "", "期望结果:DUT停止发送NM报文，正常发送应用报文，"
                            "实际结果:总线接收到DUT发送的NM报文")
        return -1


def repeat_msg_state_req_start():
    can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
    rWakeupMsgID = P.ECUInfo.WakeupMsgID_int
    rWakeupMsgDLC = P.ECUInfo.WakeupMsgDLC
    rWakeupMsgData = bytearray(P.ECUInfo.WakeupMsgData_bytes)[:rWakeupMsgDLC]
    rReptMsgBit0 = P.NMInfo.RepeatMessageBit0  # 是否支持RepeatMessageRequestBit状态位，1，支持，0，不支持
    rActWupBit4 = 1
    rNimmediateSend = P.NMInfo.NimmediateSend  # 快速发送NM报文的帧数
    rTimmediateCycle_ms = P.NMInfo.TimmediateCycle_ms  # 快速发送NM报文的周期
    rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms  # 重复发送报文状态的保持时间
    rTnormalCycle_ms = P.NMInfo.TnormalCycle_ms  # 正常发送NM报文的周期

    #
    # if rReptMsgBit0 == 1:
    #     rWakeupMsgData[1] |= 0x01  # RepeatMessageBitRequest = 1
    # if rActWupBit4 == 1:
    #     rWakeupMsgData[1] &= 0xEF  # ActiveWakeupBit = 0
    rWakeupMsgData[1] |= 0x01  # RepeatMessageBitRequest = 1
    msg = canmsg_create(rWakeupMsgID, rWakeupMsgDLC, data=rWakeupMsgData, rtr=0, fdf=0, brs=0, ext=0)

    TestLog("INFO", "", "开始触发重复报文模式请求")
    repeatMsgStateReqSendStartTime = time.time()
    # 先快发
    send_period(can_channel, msg, rNimmediateSend, rTimmediateCycle_ms)

    if rReptMsgBit0 == 1:
        RepeatMessageBitRequest = 1 if rWakeupMsgData[1] & 0x01 else 0
        TimeInternal_ms = (time.time() - repeatMsgStateReqSendStartTime) * 1000
        if RepeatMessageBitRequest == 1 and TimeInternal_ms > rTrepeatMessage_ms:
            rWakeupMsgData[1] &= 0xFE  # RepeatMessageBitRequest = 1
        msg.payload = bytes(rWakeupMsgData)
    # 正常发
    TimerCyclic.start(1, rTnormalCycle_ms, send_canmsg, can_channel, msg=msg)


def repeat_msg_state_req_stop():
    TestLog("INFO", "", "取消重复报文模式请求")
    TimerCyclic.stop(1)


def check_repeat_message_state_after_repeat_msg_request():
    rNMmsgIDMin = 0x400  # NM报文ID范围最小值
    rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
    rReptMsgBit0 = P.NMInfo.RepeatMessageBit0  # 是否支持RepeatMessageRequestBit状态位，1，支持，0，不支持
    rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms  # 重复发送报文状态的保持时间
    rTimmediateDeviation = P.NMInfo.TimmediateDeviation_pct  # 快速发送NM报文的周期偏移范围
    rTnormalDeviation = P.NMInfo.TnormalDeviation_pct  # 正常发送NM报文的周期偏移范围
    rTimmediateCycle_ms = P.NMInfo.TimmediateCycle_ms  # 快速发送NM报文的周期
    rNimmediateSend = P.NMInfo.NimmediateSend  # 快速发送NM报文的帧数
    rTnormalCycle_ms = P.NMInfo.TnormalCycle_ms  # 正常发送NM报文的周期
    rTimmediateSendMin_ms = rTimmediateCycle_ms * (1 - rTimmediateDeviation / 100)
    rTimmediateSendMax_ms = rTimmediateCycle_ms * (1 + rTimmediateDeviation / 100)
    rTnormalCycleMin_ms = rTnormalCycle_ms * (1 - rTnormalDeviation / 100)
    rTnormalCycleMax_ms = rTnormalCycle_ms * (1 + rTnormalDeviation / 100)

    PeriodError = 0
    RepeatBitError = 0
    PeriodErrorCountPrint = 0
    RepeatBitErrorCountPrint = 0
    DefaultErrorCount = 3  # 默认只打印3次错误

    nm_message = get_nm_message_list()
    if len(nm_message) == 0:
        if rReptMsgBit0 == 1:
            TestLog("WARNING", "", f"期望结果:DUT以正常周期发送NM报文，NM报文RepeatMessageRequestBit一直为1，"
                                "实际结果:总线未收到DUT发送的NM报文，无法判断")
        else:
            TestLog("WARNING", "", f"期望结果:DUT以正常周期发送NM报文，"
                                f"实际结果:总线未收到DUT发送的NM报文，无法判断")
        return 0

    for index, msg in enumerate(nm_message):
        internal_time_ms = msg.time_ms - nm_message[0].time_ms
        if internal_time_ms > rTrepeatMessage_ms:
            break

        if index > 0:
            period_ms = msg.time_ms - nm_message[index-1].time_ms
            if rTnormalCycleMin_ms <= period_ms <= rTnormalCycleMax_ms:
                TestLog("PASS", "", f"期望结果:所有NM报文发送间隔均满足正常发送周期({rTnormalCycle_ms} ms)，"
                                    f"实际结果:NM报文周期为{period_ms} ms(TimeStamp = {msg.time_ms / 1000} S)，满足要求")
            else:
                PeriodError = 1
                PeriodErrorCountPrint += 1
                if PeriodErrorCountPrint <= DefaultErrorCount:
                    TestLog("FAIL", "", f"期望结果:所有NM报文发送间隔均满足正常发送周期({rTnormalCycle_ms} ms)，"
                                        f"实际结果:NM报文周期为{period_ms} ms(TimeStamp = {msg.time_ms / 1000} S)，不满足要求")
        if rReptMsgBit0 == 1:
            RepeatMsgReqBit = 1 if bytes.fromhex(msg.payload_hex)[1] & 0x01 else 0
            if internal_time_ms < 0.9 * rTrepeatMessage_ms:
                if RepeatMsgReqBit == 1:
                    TestLog("PASS", "", f"期望结果:RepeatMessageRequestBit在{rTrepeatMessage_ms} ms 时间之内一直为1，"
                                        f"实际结果:RepeatMessageRequestBit在{internal_time_ms} ms 时间之内为1(TimeStamp = {msg.time_ms / 1000} S)，满足要求")
                else:
                    RepeatBitError = 1
                    RepeatBitErrorCountPrint += 1
                    TestLog("FAIL", "", f"期望结果:RepeatMessageRequestBit在{rTrepeatMessage_ms} ms 时间之内一直为1，"
                                        f"实际结果:RepeatMessageRequestBit在{internal_time_ms} ms 时间之内变为0(TimeStamp = {msg.time_ms / 1000} S)，不满足要求")
    if not PeriodError and not RepeatBitError:
        if rReptMsgBit0 == 1:
            TestLog("PASS", "", f"期望结果:DUT以正常周期发送NM报文，NM报文RepeatMessageRequestBit一直为1，"
                                "实际结果:所有NM报文发送间隔均满足正常发送周期，NM报文RepeatMessageRequestBit一直为1")
        else:
            TestLog("PASS", "", f"期望结果:DUT以正常周期发送NM报文，"
                                f"实际结果:所有NM报文发送间隔均满足正常发送周期")
        return 0
    return -1


def check_ready_sleep_state_rx_msg(testTime_ms):
    rNMmsgID = P.ECUInfo.NMMsgID_int

    # 获取最后一帧NM报文的时间
    nm_message = get_nm_message_list()
    lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else 0

    errorCount = 0

    rx_message_id_list = get_message_id_list()
    for msg in rx_message_id_list:
        if msg.id == rNMmsgID:
            continue

        internamTime_ms = msg.time_ms - lastRxNMMsgTimeStamp_ms
        periodAvg = get_msg_period_ms(msg.id)
        if 2 <= periodAvg <= 0.9 * testTime_ms:
            if internamTime_ms >= 0.1 * testTime_ms:
                TestLog("PASS", "", f"期望结果:DUT停止发送NM报文，正常发送应用报文，"
                                    f"实际结果:DUT停止发送NM报文之后({internamTime_ms} ms)，总线收到DUT发送的应用报文：{hex(msg.id)}")
            else:
                errorCount += 1
                TestLog("FAIL", "", f"期望结果:DUT停止发送NM报文，正常发送应用报文，"
                                    f"实际结果:DUT停止发送NM报文之后({internamTime_ms} ms)，总线未收到DUT发送的应用报文：{hex(msg.id)}")
        else:
            TestLog("WARNING", "", f"期望结果:DUT停止发送NM报文，正常发送应用报文，"
                                   f"实际结果:报文({hex(msg.id)})周期大于0.9倍监控时间({0.9 * testTime_ms} ms)，该报文无法判断")

    if errorCount > 0:
        return -1
    return 0


def check_ready_sleep_state_rx_app_msg():
    rNMmsgID = P.ECUInfo.NMMsgID_int
    rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms  # NM Timeout Timer时间
    rNMmsgIDMin = 0x400  # NM报文ID范围最小值
    rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值

    # 获取最后一帧NM报文的时间
    nm_message = get_nm_message_list()
    lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else 0

    errorCount = 0

    rx_message_id_list = get_message_id_list()
    for msg in rx_message_id_list:
        if rNMmsgIDMin <= msg.id <= rNMmsgIDMax:
            continue

        internamTime_ms = msg.time_ms - lastRxNMMsgTimeStamp_ms
        periodAvg = get_msg_period_ms(msg.id)
        if 2 <= periodAvg <= 0.9 * rTNMtimeout_ms:
            if internamTime_ms >= 0.1 * rTNMtimeout_ms:
                TestLog("PASS", "", f"期望结果:DUT停止发送NM报文，正常发送应用报文，"
                                    f"实际结果:DUT停止发送NM报文之后({internamTime_ms} ms)，总线收到DUT发送的应用报文：{hex(msg.id)}")
            else:
                errorCount += 1
                TestLog("FAIL", "", f"期望结果:DUT停止发送NM报文，正常发送应用报文，"
                                    f"实际结果:DUT停止发送NM报文之后({internamTime_ms} ms)，总线未收到DUT发送的应用报文：{hex(msg.id)}")
        # 报文周期大于0.9*rTNMtimeout时，是否发送，不作判断
        else:
            TestLog("WARNING", "", f"期望结果:DUT停止发送NM报文，正常发送应用报文，"
                                   f"实际结果:应用报文({hex(msg.id)})周期大于0.9倍监控时间({0.9 * rTNMtimeout_ms} ms)，该报文无法判断")

    if errorCount > 0:
        return -1
    return 0


def prepare_sleep_state_test_start():
    can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
    msg_id = 0x01
    msg_dlc = 8
    msg_data = [0x55] * 8
    msg_cyclic_ms = 1
    msg = canmsg_create(msg_id, msg_dlc, data=msg_data, rtr=0, fdf=0, brs=0, ext=0)
    TestLog("INFO", "", "开始仿真发送应用报文")
    send_canmsg(can_channel, msg)
    TimerCyclic.start(0x55, msg_cyclic_ms, send_canmsg, can_channel, msg=msg)


def prepare_sleep_state_test_stop():
    TestLog("INFO", "", "停止仿真发送应用报文")
    TimerCyclic.stop(0x55)


def check_prepare_sleep_state():
    gEcuMsgIdCount = len(build_rx_ecuCanChl_msg(ctx.can.messages))
    gErrorFrameCount = ctx.can.get_info("gErrorFrameCount")
    if gErrorFrameCount == 0:
        if gEcuMsgIdCount == 0:
            TestLog("PASS", "", "期望结果：DUT停止发送NM报文和应用报文，总线无错误帧，"
                                "实际结果:总线未接收到任何报文，并且总线无错误帧")
            return 0
        else:
            TestLog("FAIL", "", "期望结果：DUT停止发送NM报文和应用报文，总线无错误帧，"
                                "实际结果:总线无错误帧，但接收到报文")
            return -1
    else:
        if gEcuMsgIdCount == 0:
            TestLog("FAIL", "", "期望结果：DUT停止发送NM报文和应用报文，总线无错误帧，"
                                "实际结果:总线未接收到任何报文，但总线出现错误帧")
            return 0
        else:
            TestLog("FAIL", "", "期望结果：DUT停止发送NM报文和应用报文，总线无错误帧，"
                                "实际结果:总线出现错误帧，并且接收到报文")
            return -1


def check_bus_sleep_state():
    gEcuMsgIdCount = len(build_rx_ecuCanChl_msg(ctx.can.messages))
    gErrorFrameCount = ctx.can.get_info("gErrorFrameCount")
    if gErrorFrameCount > 0:
        if gEcuMsgIdCount == 0:
            TestLog("PASS", "", "期望结果：DUT停止发送NM报文和应用报文，总线出现错误帧，"
                                "实际结果:总线未接收到任何报文，并且总线出现错误帧")
            return 0
        else:
            TestLog("FAIL", "", "期望结果：DUT停止发送NM报文和应用报文，总线出现错误帧，"
                                "实际结果:总线出现错误帧，但接收到报文")
            return -1
    else:
        if gEcuMsgIdCount == 0:
            TestLog("FAIL", "", "期望结果：DUT停止发送NM报文和应用报文，总线出现错误帧，"
                                "实际结果:总线未接收到任何报文，但总线无错误帧")
            return 0
        else:
            TestLog("FAIL", "", "期望结果：DUT停止发送NM报文和应用报文，总线出现错误帧，"
                                "实际结果:总线无错误帧，并且接收到报文")
            return -1


def check_first_frame_isNm():
    """
        从接收到的报文中，判断首帧报文是NM报文
    """
    rNMmsgIDMin = 0x400  # NM报文ID范围最小值
    rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
    msg = build_rx_ecuCanChl_msg(ctx.can.messages)[0]
    if rNMmsgIDMin <= msg.id <= rNMmsgIDMax:
        TestLog("PASS", "", "期望结果：DUT唤醒后的首帧报文是NM报文，"
                            "实际结果: DUT唤醒后的首帧报文是NM报文")
        return 0
    else:
        TestLog("PASS", "", "期望结果：DUT唤醒后的首帧报文是NM报文，"
                            "实际结果: DUT唤醒后的首帧报文不是NM报文")
        return -1

def check_app_msg_send():
    pass

def clear_ctx_can_messages():
    """清空 CAN 消息"""
    ctx.can.clear_messages()
    nmctx.can.clear_messages()
    ctx.can.set_info("gErrorFrameCount", 0)
    time.sleep(0.002)
