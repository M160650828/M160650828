import time
import random

from common.context import ctx
from common.utils import TimerCyclic
from common.can_utils import send_canmsg, canmsg_create
from uvtest.testlog import TestLog
from slplus.time import sl_time


def check_expected_response(response_id, expect_response_start_pos, expect_response_data, timeout=5):
    """
        @brief: 校验是否能从接收缓存中提取期望报文
        @param response_id: 指定响应报文ID
        @param expect_response_start_pos: 响应的CAN报文的数据开始比较的位置
        @param expect_response_data: 期望收到的响应报文
        @param timeout: 等待一段时间
        @usage:
            # 检测5s
            # 检测接收报文中是否有id=0x772，并且从第2个字节开始的数据是[0x50, 0x01]的报文
            if check_expected_response(0x772, 1, [0x50, 0x01], timeout=5)]) is True:
                print("检测到")
            else:
                print("未检测到")
    """
    start_time = time.time()
    seen_count = 0

    while True:
        if time.time() - start_time > timeout:
            return False

        messages = ctx.can.messages
        total = len(messages)
        if total <= seen_count:
            time.sleep(0.01)
            continue
        for index, msg in enumerate(messages):
            if index < seen_count:
                continue
            if msg.id != response_id:
                continue

            data_hex = msg.payload_hex or ""
            if not data_hex:
                continue

            try:
                data_bytes = bytes.fromhex(data_hex)
            except ValueError:
                continue

            start_pos = expect_response_start_pos
            end_pos = expect_response_start_pos + len(expect_response_data)
            if len(data_bytes) >= end_pos and list(data_bytes[start_pos:end_pos]) == expect_response_data:
                return True

        seen_count = total
        time.sleep(0.01)


def start_simulation_msgs(msg_defs, timer_id_base, can_channel, fill_byte=0x00):
    """
    启动仿真报文发送
    @param msg_defs: 报文定义字典 {msg_id: msg_info}
    @param timer_id_base: 定时器ID
    @param can_channel: CAN通道
    @param fill_byte: 填充字节，当msg_info中无data时使用，默认0x00
    @return: 已启动的定时器ID列表

    msg_info 支持的字段：
        - dlc: 报文长度，默认8
        - cycle: 发送周期(ms)，0或不存在则跳过
        - is_fd/fdf: 是否CANFD
        - brs: 是否BRS
        - data: 报文数据(bytes)，优先使用
    """
    started_ids = []
    for idx, (msg_id, msg_info) in enumerate(msg_defs.items()):
        try:
            msg_dlc = msg_info.get('dlc', 8)
            msg_cycle = msg_info.get('cycle', 0)
            if msg_cycle <= 0:
                continue
            is_canfd = msg_info.get('is_fd', False) or msg_info.get('fdf', False)
            brs = msg_info.get('brs', False)

            # 优先使用msg_info中的data，否则用fill_byte填充
            if 'data' in msg_info and msg_info['data'] is not None:
                msg_data = msg_info['data']
            else:
                msg_data = bytes([fill_byte] * msg_dlc)

            msg = canmsg_create(msg_id, msg_dlc, data=msg_data, rtr=0,
                                fdf=1 if is_canfd else 0, brs=1 if (is_canfd and brs) else 0, ext=0)
            if msg is None:
                continue
            timer_id = timer_id_base + idx
            if TimerCyclic.start(timer_id, msg_cycle, send_canmsg, can_channel, msg=msg):
                started_ids.append(timer_id)
        except Exception:
            pass
    return started_ids


POWERMODE_TIMER_ID = 9999
def simulation_powermode_signal(msg_id: int, value: int, can_channel: int = None):
    from common.db_parser import sigdb
    from common.params import P

    if can_channel is None:
        try:
            from env.config import DEFAULT_CAN_CHANNELS
            can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        except Exception:
            can_channel = 1

    msg_def = sigdb.get_msg_def(msg_id)
    if msg_def is None:
        TestLog("WARNING", "", f"DBC中未找到报文 0x{msg_id:X}，使用默认值")
        msg_dlc = 8
        msg_cycle = 100  
    else:
        msg_dlc = msg_def.get('dlc', 8)
        msg_cycle = msg_def.get('cycle', 100)
        if msg_cycle <= 0:
            msg_cycle = 100

    signal_name = P.CANInfo.EnableDTCSignalName
    signal_start_bit = P.CANInfo.EnableDTCSignalStartBit
    signal_bit_length = P.CANInfo.EnableDTCSignalBitLength

    sig_def = sigdb.get_signal_def(signal_name)
    if sig_def is not None:
        signal_byte_order = sig_def.byte_order
    else:
        signal_byte_order = 'little_endian'
        TestLog("WARNING", "", f"DBC中未找到信号 {signal_name}，使用默认小端序")

    if signal_start_bit == 0 and signal_bit_length == 0:
        TestLog("WARNING", "",
                f"报文 0x{msg_id:X} 的信号起始位和位长度均为0，请检查配置")

    # TODO: 检查报文是否包含 Checksum 信号，若有则需实现 E2E 保护（Rolling Counter + CRC）

    msg_data = sigdb.encode_msg_with_init_values(msg_id, 0x00)
    msg_data = bytearray(msg_data)

    if len(msg_data) < msg_dlc:
        msg_data.extend([0x00] * (msg_dlc - len(msg_data)))

    if signal_byte_order == 'big_endian':
        sigdb._encode_big_endian(msg_data, signal_start_bit, signal_bit_length, value)
    else:
        sigdb._encode_little_endian(msg_data, signal_start_bit, signal_bit_length, value)

    TestLog("INFO", "",
            f"启动 PowerMode 信号仿真: MsgID=0x{msg_id:X}, Value={value}, "
            f"StartBit={signal_start_bit}, BitLen={signal_bit_length}, Cycle={msg_cycle}ms")

    msg = canmsg_create(msg_id, msg_dlc, data=bytes(msg_data), rtr=0, fdf=P.TpInfo.CanFDMode, brs=0, ext=0)
    if msg is None:
        TestLog("FAIL", "", f"创建报文 0x{msg_id:X} 失败")
        return False

    if TimerCyclic.start(POWERMODE_TIMER_ID, msg_cycle, send_canmsg, can_channel, msg=msg):
        TestLog("INFO", "", f"周期定时器启动成功，周期={msg_cycle}ms")
        return True
    else:
        TestLog("FAIL", "", "周期定时器启动失败")
        return False


def stop_powermode_signal():
    try:
        TimerCyclic.stop(POWERMODE_TIMER_ID)
        TestLog("INFO", "", "已停止 PowerMode 信号仿真")
    except Exception:
        pass



PARTNER_MSG_TIMER_ID = 9999
def simulation_special_message(msg_id: int, can_channel: int = None):
    from common.db_parser import sigdb

    if can_channel is None:
        try:
            from env.config import DEFAULT_CAN_CHANNELS
            can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        except Exception:
            can_channel = 1

    msg_def = sigdb.get_msg_def(msg_id)
    if msg_def is None:
        TestLog("WARNING", "伙伴节点仿真", f"DBC中未找到报文 0x{msg_id:X}，使用默认值")
        msg_dlc = 8
        msg_cycle = 100
    else:
        msg_dlc = msg_def.get('dlc', 8)
        msg_cycle = msg_def.get('cycle', 100)
        if msg_cycle <= 0:
            msg_cycle = 100

    # TODO: 检查报文是否包含 Checksum 信号，若有则需实现 E2E 保护（Rolling Counter + CRC）

    msg_data = sigdb.encode_msg_with_init_values(msg_id, 0x00)
    msg_data = bytearray(msg_data)

    if len(msg_data) < msg_dlc:
        msg_data.extend([0x00] * (msg_dlc - len(msg_data)))

    TestLog("INFO", "伙伴节点仿真",
            f"启动伙伴节点报文仿真: MsgID=0x{msg_id:X}, DLC={msg_dlc}, Cycle={msg_cycle}ms")

    msg = canmsg_create(msg_id, msg_dlc, data=bytes(msg_data), rtr=0, fdf=0, brs=0, ext=0)
    if msg is None:
        TestLog("FAIL", "伙伴节点仿真", f"创建报文 0x{msg_id:X} 失败")
        return False

    if TimerCyclic.start(PARTNER_MSG_TIMER_ID, msg_cycle, send_canmsg, can_channel, msg=msg):
        TestLog("INFO", "伙伴节点仿真", f"周期定时器启动成功，周期={msg_cycle}ms")
        return True
    else:
        TestLog("FAIL", "伙伴节点仿真", "周期定时器启动失败")
        return False


def stop_special_message():
    try:
        TimerCyclic.stop(PARTNER_MSG_TIMER_ID)
        TestLog("INFO", "伙伴节点仿真", "已停止伙伴节点报文仿真")
    except Exception:
        pass


def stop_simulation_msgs(timer_ids):
    """
    停止仿真报文发送
    @param timer_ids: 定时器ID列表
    """
    for tid in timer_ids:
        try:
            TimerCyclic.stop(tid)
        except Exception:
            pass


def send_random_data_msg(can_ch, msg_id, msg_dlc, is_canfd, brs):
    """
    发送随机数据的报文
    @param can_ch: CAN通道
    @param msg_id: 报文ID
    @param msg_dlc: 报文DLC
    @param is_canfd: 是否CANFD
    @param brs: 是否BRS
    """
    random_data = bytes([random.randint(0, 255) for _ in range(msg_dlc)])
    msg = canmsg_create(msg_id, msg_dlc, data=random_data, rtr=0,
                        fdf=1 if is_canfd else 0, brs=1 if (is_canfd and brs) else 0, ext=0)
    if msg:
        send_canmsg(can_ch, msg=msg)


def check_bus_error_frames(step_name=""):
    """
    校验总线错误帧
    @param step_name: 步骤名称，用于日志输出
    @return: True表示无错误帧，False表示有错误帧
    """
    error_count = ctx.can.get_info('gErrorFrameCount') or 0
    no_error = error_count == 0
    if no_error:
        TestLog("PASS", step_name, "期望结果：总线无错误帧。实际结果：总线无错误帧")
    else:
        TestLog("FAIL", step_name, f"期望结果：总线无错误帧。实际结果：存在 {error_count} 个错误帧")
    return no_error


def kl30_power_cycle(count, voltage, interval_s=0.1, step_name="Step1"):
    """
    KL30上下电压力循环
    @param count: 循环次数
    @param voltage: 电压值
    @param interval_s: 每次循环间隔时间(秒)
    @param step_name: 步骤名称，用于日志输出
    """
    TestLog("INFO", step_name, f"开始执行 {count} 次KL30快速上下电循环")
    for i in range(1, count + 1):
        TestLog("INFO", step_name, f"第 {i}/{count} 次快速上下电")
        ctx.power_ctrl.set_voltage(voltage)
        ctx.bob_ctrl.set_power('KL30', True)
        ctx.bob_ctrl.set_power('KL30', False)
        ctx.power_ctrl.set_voltage(0)
        time.sleep(interval_s)
    TestLog("INFO", step_name, f"完成 {count} 次KL30快速上下电循环")


def voltage_step_test(target_voltage, delay_ms, recover_voltage, monitor_time_ms, can_channel):
    """
    电压阶跃测试
    @param target_voltage: 目标电压(跳变到的电压)
    @param delay_ms: 在目标电压停留时间(毫秒)
    @param recover_voltage: 恢复电压
    @param monitor_time_ms: 恢复后监控时间(毫秒)
    @param can_channel: CAN通道
    @return: (messages, rx_stats) 收集到的报文和统计信息
    """
    from .can_module import build_rx_msg_info

    ctx.can.clear_messages()
    ctx.can.set_filter_by_channel(can_channel)

    TestLog("INFO", "", f"电压跳变到 {target_voltage}V，保持 {delay_ms}ms")
    ctx.power_ctrl.set_voltage(target_voltage)
    sl_time().sleep(delay_ms)

    TestLog("INFO", "", f"电压恢复到 {recover_voltage}V，监控 {monitor_time_ms}ms")
    ctx.power_ctrl.set_voltage(recover_voltage)
    sl_time().sleep(monitor_time_ms)

    messages = ctx.can.messages
    rx_stats = build_rx_msg_info(messages)
    TestLog("INFO", "", f"监控完成，共接收到 {len(rx_stats)} 种不同ID的报文")

    return messages, rx_stats


def dut_force_sleep(wait_time_s=5):
    """
    强制DUT进入休眠
    @param wait_time_s: 等待DUT进入休眠的时间(秒)
    """
    from common.wakeup import WakeupStop

    TestLog("INFO", "", "强制DUT进入休眠状态")
    ctx.bob_ctrl.set_power('KL30', False)
    ctx.power_ctrl.set_voltage(0)
    WakeupStop()
    time.sleep(wait_time_s)
    TestLog("INFO", "", f"等待 {wait_time_s}s，DUT应已进入休眠")