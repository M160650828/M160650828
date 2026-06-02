import json
import time
from uvtest.testlog import TestLog
from uvtest.syslog import output_log
from common.context import ctx
from env.config import DEFAULT_CAN_CHANNELS, MESSAGE_COUNT_OUTPUT_INTERVAL
from slplus.can import sl_can, register_canmsg_handler, unregister_canmsg_handler
from slplus.runtime import sl_runtime

#from sl.sl_event import register_busevent_handler, unregister_busevent_handler, EventType
from slplus.can import register_busevent_handler,unregister_busevent_handler,EventType
from slplus.event import TextEvents
from slplus.time import sl_time

from common.params import P
from common.signal_parser import sig

'''
variable
'''
gCanTextEvent_RX = "CAN Frame is Received"
gCanTextEvent_TX = "CAN Frame is Transmitted"


class CanCommChecker:
    def set_and_check(self, voltage: float, delay: float):
        ctx.power_ctrl.set_voltage(voltage)
        ctx.can.clear_messages()
        ctx.can.set_info("gErrorFrameCount", 0)
        if delay and delay > 0:
            sl_time().sleep(int(delay * 1000))
        has_comm = bool(ctx.can.messages)
        return True, has_comm, False

'''
事件处理
'''
def _on_canmsg(bustype, busid, msg, cookie):
    dirv = getattr(msg, 'dirv', 0)
    dir_str = 'TX' if dirv == 1 else 'RX'

    try:
        ts_ns = getattr(msg, 'timestamp_ns', None)
        if ts_ns is not None:
            current_time = float(ts_ns) / 1_000_000.0  # ns -> ms
        else:
            current_time = time.time() * 1000.0

        msg_id = getattr(msg, 'msgid', 0)
        msg_dlc = getattr(msg, 'dlc', 8)
        is_canfd_msg = bool(getattr(msg, 'is_fd', False))
        payload_bytes = getattr(msg, 'payload', b"") or b""

        # 过滤唤醒报文
        if msg_id == P.ECUInfo.WakeupMsgID_int:
            return

        try:
            event_name = gCanTextEvent_TX if dir_str == "TX" else gCanTextEvent_RX
            TextEvents().supply(event_name)
        except Exception:
            pass

        data_len = len(payload_bytes)
        payload_hex = payload_bytes.hex().upper()

        ctx.can.add_message(
            id=msg_id,
            time_ms=current_time,
            dlc=msg_dlc,
            channel=busid,
            payload_hex=payload_hex,
            direction=dirv,
        )

        sig.update(msg)

        total_count = len(ctx.can.messages)
        if MESSAGE_COUNT_OUTPUT_INTERVAL and total_count % MESSAGE_COUNT_OUTPUT_INTERVAL == 1:
            msg_type = "CANFD" if is_canfd_msg else "CAN"
            if payload_hex:
                payload_display = " ".join(
                    [payload_hex[i : i + 2] for i in range(0, len(payload_hex), 2)]
                )
            else:
                payload_display = "无数据"

            action = (
                "接收"
                if (dir_str is None or dir_str == "RX")
                else ("发送" if dir_str == "TX" else "未知")
            )
            print(
                f"{action}{msg_type}报文 - 通道: {busid}, ID: 0x{msg_id:x}, DLC: {msg_dlc}, "
                f"数据长度: {data_len}, 数据: [{payload_display}], 总计数: {total_count}"
            )

    except Exception as e:
        print(f"消息回调处理错误: {e}")
        error_count = ctx.can.get_info("gErrorFrameCount") or 0
        ctx.can.set_info("gErrorFrameCount", error_count + 1)

def _on_busevent(bustype, busid, value, cookie):
    try:
        if bustype != 2:
            return
        event_kind, value = value
        if event_kind == EventType.UG_BUS_STATE.value:
            handle_can_state(value, busid, cookie)
        elif event_kind == EventType.UG_BUS_ERROR.value:
            handle_can_error(value, busid, cookie)
    except Exception as e:
        TestLog("WARNING", "事件处理", f"处理CAN错误/状态事件失败: {e}")


def handle_can_error(error_value, bus_id, user_data):
    """
    处理CAN错误事件
    """
    try:
        errors = ("unknown", "bit", "format", "stuff", "crc", "ack", "arb")
        error_name = errors[error_value] if error_value < len(errors) else f"unknown({error_value})"

        if bus_id == DEFAULT_CAN_CHANNELS[0]:
            error_count = ctx.can.get_info('gErrorFrameCount') or 0
            ctx.can.set_info('gErrorFrameCount', error_count + 1)
            TestLog("WARNING", "错误帧", f"ECU通信总线 {bus_id} 错误: {error_name}")
        else:
            TestLog("DEBUG", "错误帧", f"CAN通道 {bus_id} 错误: {error_name}")
    except Exception as e:
        TestLog("WARNING", "错误处理", f"处理CAN错误失败: {e}")

def handle_can_state(state_value, bus_id, user_data):
    """
    处理CAN总线状态变化
    """
    try:
        if 0 <= state_value <= 2:
            states = ["passive_error", "active_error", "bus_off"]
            state_name = states[state_value]
            TestLog("WARNING", "总线状态", f"总线 {bus_id} 状态: {state_name}")
    except Exception as e:
        TestLog("WARNING", "状态处理", f"处理CAN状态失败: {e}")


'''
报文分析
'''
def _load_and_parse_database(msg_type: str = 'tx'):
    from common.db_parser import DB
    from common.params import P

    if msg_type == 'all':
        result = DB.can()
        return result.messages if result.success else {}

    ecu_name = (P.ECUInfo.ECUName or '').strip()
    result = DB.can(ecu_name)
    if not result.success:
        return {}
    if msg_type == 'rx':
        return result.rx
    return result.tx


def build_rx_msg_info(messages):
    """
	构建按 ID 聚合的统计信息
    """
    stats = {}

    for m in messages:
        msg_id = m.id
        info = stats.get(msg_id)
        if info is None:
            info = {
                "count": 0,
                "dlc": m.dlc,
                "channel": m.channel,
                "msgId": msg_id,
                "time": m.time_ms,
                "periodSum": 0.0,
                "lastPayload": "",
            }
            stats[msg_id] = info
        else:
            prev_time = info["time"]
            period = m.time_ms - prev_time
            info["periodSum"] += period
            info["time"] = m.time_ms

        info["count"] += 1
        info["lastPayload"] = m.payload_hex

    return stats


def analyze_messages(rx_msg_stats, can_db_msg_defs):
    """分析接收与数据库定义的报文
    - MsgReceivedList: 数据库定义且收到
    - MsgNotReceivedList: 数据库定义但未收到
    - MsgUndefinedList: 实际收到但数据库未定义
    """
    MsgNotReceivedList = {}
    MsgReceivedList = {}
    MsgUndefinedList = {}

    for msg_id in rx_msg_stats:
        MsgUndefinedList[msg_id] = msg_id

    for msg_id in can_db_msg_defs:
        rx = rx_msg_stats.get(msg_id)
        if not rx or rx.get("count", 0) == 0:
            MsgNotReceivedList[msg_id] = msg_id
        else:
            MsgReceivedList[msg_id] = msg_id
        if msg_id in MsgUndefinedList:
            del MsgUndefinedList[msg_id]

    return MsgReceivedList, MsgNotReceivedList, MsgUndefinedList


def _report_missing_and_undefined(test_title, MsgNotReceivedList, MsgUndefinedList, can_db_msg_defs, include_names=False):
    """
	数据库定义未收到 + 实际收到但数据库未定义
    """
    if len(MsgNotReceivedList) > 0:
        TestLog("INFO", "", "以下报文数据库中定义，实际未收到")
        for msg_id in MsgNotReceivedList:
            info = can_db_msg_defs.get(msg_id, {})
            msg_cycle = info.get("cycle", 0)
            msg_dlc = info.get("dlc", 0)
            if include_names:
                msg_name = info.get("name", f"Unknown_{msg_id:x}")
                id_str = f"0x{msg_id:x} ({msg_name})"
            else:
                id_str = f"0x{msg_id:x}"
            if msg_cycle == 0:
                TestLog("WARNING", " ", f"数据库中定义，发送周期为0，实际未收到:{id_str} (DLC={msg_dlc})")
            else:
                TestLog("FAIL", " ",
                        f"期望结果：所有接收报文ID与数据库定义一致。实际结果：数据库中定义，发送周期不为0，实际未收到:{id_str} (DLC={msg_dlc}, Cycle={msg_cycle}ms)")

    if len(MsgUndefinedList) > 0:
        TestLog("FAIL", " ", f"期望结果：所有接收报文ID与数据库定义一致。实际结果：接收报文ID与数据库定义不一致,不一致的id为{MsgUndefinedList}, 以下报文数据库中未定义")
        for msg_id in MsgUndefinedList:
            TestLog("INFO", "", f"0x{msg_id:x}")

    has_missing_periodic = any(can_db_msg_defs.get(msg_id, {}).get("cycle", 0) != 0 for msg_id in MsgNotReceivedList)
    has_undefined = len(MsgUndefinedList) > 0
    return has_missing_periodic, has_undefined


def report_message_tests(
        MsgReceivedList,
        MsgNotReceivedList,
        MsgUndefinedList,
        rx_msg_stats,
        can_db_msg_defs,
        tests=("id",),
        period_thresholds=(10.0, 5.0),
        include_names=False,
):
    results = {"id": None, "dlc": None, "period": None}
    tests = tuple(tests) if isinstance(tests, (list, tuple)) else (str(tests),)
    label = "报文"

    # 1) ID 测试
    if "id" in tests:
        title = f"{label}ID测试"
        if len(MsgReceivedList) > 0:
            TestLog("PASS", "", f"期望结果：以下接收{label}ID与数据库定义一致，实际结果：以下接收{label}ID与数据库定义一致")
            for msg_id in MsgReceivedList:
                if include_names:
                    msg_name = can_db_msg_defs.get(msg_id, {}).get("name", f"Unknown_{msg_id:x}")
                    # TestLog("INFO", " ", f"0x{msg_id:x} ({msg_name})")
                else:
                    pass
                    # TestLog("INFO", " ", f"0x{msg_id:x}")
        miss, undef = _report_missing_and_undefined(title, MsgNotReceivedList, MsgUndefinedList, can_db_msg_defs,
                                                    include_names)
        if miss or undef:
            TestLog("FAIL", "", "测试失败")
            results["id"] = False
        else:
            TestLog("PASS", "", "测试通过")
            results["id"] = True

    # 2) DLC 测试
    if "dlc" in tests:
        title = f"{label}DLC测试"
        dlc_mismatch = False
        if len(MsgReceivedList) > 0:
            for msg_id in MsgReceivedList:
                rx_dlc = rx_msg_stats.get(msg_id, {}).get("dlc")
                exp_dlc = can_db_msg_defs.get(msg_id, {}).get("dlc")
                if rx_dlc == exp_dlc:
                    TestLog("PASS", " ", f"期望结果：接收{label}ID与数据库定义ID的DLC一致:0x{msg_id:x}，实际结果：接收{label}ID与数据库定义ID的DLC一致:0x{msg_id:x}")
                else:
                    TestLog("FAIL", " ",
                            f"期望结果：接收{label}ID与数据库定义ID的DLC一致:0x{msg_id:x}，实际结果：接收{label}ID与数据库定义ID一致、DLC不一致:0x{msg_id:x} (期望:{exp_dlc}, 实际:{rx_dlc})")
                    dlc_mismatch = True
        miss, undef = _report_missing_and_undefined(title, MsgNotReceivedList, MsgUndefinedList, can_db_msg_defs,
                                                    include_names)
        if dlc_mismatch or miss or undef:
            TestLog("FAIL", " ", "测试失败")
            results["dlc"] = False
        else:
            TestLog("PASS", " ", "测试通过")
            results["dlc"] = True

    # 3) 周期偏移 测试
    if "period" in tests:
        title = f"{label}周期偏移测试"
        low_pct, high_pct = (period_thresholds[0], period_thresholds[1]) if isinstance(period_thresholds,
                                                                                       (list, tuple)) and len(
            period_thresholds) >= 2 else (10.0, 5.0)
        period_fail = False
        TestLog("INFO", " ", f"开始分析 {len(MsgReceivedList)} 个接收到的{label}")
        TestLog("INFO", " ", f"偏移阈值: <=20ms报文<{low_pct}%, >20ms报文<{high_pct}%")
        if len(MsgReceivedList) > 0:
            for msg_id in MsgReceivedList:
                expected_cycle = can_db_msg_defs.get(msg_id, {}).get("cycle", 0)
                if expected_cycle == 0:
                    continue
                rx = rx_msg_stats.get(msg_id, {})
                cnt = rx.get("count", 0)
                if cnt <= 1:
                    TestLog("WARNING", " ", f"0x{msg_id:x} 报文接收次数不足，无法计算周期偏移")
                    continue
                period_avg = rx.get("periodSum", 0) / (cnt - 1)
                deviation = abs(period_avg - expected_cycle) / expected_cycle if expected_cycle else 0.0
                if expected_cycle <= 20:
                    threshold = low_pct / 100.0
                    if deviation < threshold:
                        TestLog("PASS", " ", f"期望结果：0x{msg_id:x}满足要求: 周期<=20ms，周期偏移率<{low_pct}% 要求。实际结果：0x{msg_id:x}满足要求: 周期<=20ms，周期偏移率<{low_pct}% 要求")
                    else:
                        TestLog("FAIL", " ", f"期望结果：0x{msg_id:x}满足要求: 周期<=20ms，周期偏移率<{low_pct}% 要求。实际结果：0x{msg_id:x}不满足要求: 周期<=20ms，周期偏移率<{low_pct}% 要求")
                        period_fail = True
                else:
                    threshold = high_pct / 100.0
                    if deviation < threshold:
                        TestLog("PASS", " ", f"期望结果：0x{msg_id:x}满足要求: 周期>20ms，周期偏移率<{high_pct}% 要求。实际结果：0x{msg_id:x}满足要求: 周期>20ms，周期偏移率<{high_pct}% 要求")
                    else:
                        TestLog("FAIL", " ", f"期望结果：0x{msg_id:x}满足要求: 周期>20ms，周期偏移率<{high_pct}% 要求。实际结果：0x{msg_id:x}不满足要求: 周期>20ms，周期偏移率<{high_pct}% 要求")
                        period_fail = True
        miss, undef = _report_missing_and_undefined(title, MsgNotReceivedList, MsgUndefinedList, can_db_msg_defs,
                                                    include_names)
        if period_fail or miss or undef:
            TestLog("FAIL", " ", "测试失败")
            results["period"] = False
        else:
            TestLog("PASS", " ", "测试通过")
            results["period"] = True

    return results

def report_max_cycle_not_exceed_2x(
        MsgReceivedList,
        MsgNotReceivedList,
        MsgUndefinedList,
        rx_msg_stats,
        can_db_msg_defs,
        include_names: bool = False,
) -> bool:
    """
    校验：
    1. 所有周期报文最大周期 ≤ 2×DB 定义值；
    2. 不存在数据库定义却未收到（miss）；
    3. 不存在收到但数据库未定义（undef）。
    返回 True/False  整体通过/失败
    """
    title = " "
    period_fail = False
    if len(MsgReceivedList) > 0:
        for msg_id in MsgReceivedList:
            db_cycle = can_db_msg_defs.get(msg_id, {}).get("cycle", 0)
            if db_cycle == 0:
                continue
            max_period = rx_msg_stats.get(msg_id, {}).get("max", 0.0)
            if max_period > db_cycle * 2.0:
                TestLog("FAIL", " ", f"0x{msg_id:03X} 最大周期={max_period:.2f} ms "
                                     f"(DB={db_cycle} ms, 上限={db_cycle*2:.2f} ms)")
                period_fail = True

    # 统一打印缺失/未定义，并返回总结果
    miss, undef = _report_missing_and_undefined(title, MsgNotReceivedList, MsgUndefinedList,
                                                can_db_msg_defs, include_names)
    if period_fail or miss or undef:
        TestLog("FAIL", " ", "测试失败")
        return False
    else:
        TestLog("PASS", " ", "测试通过")
        return True
'''
过程控制
'''
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
        "INFO",
        "CAN通信状态检查",
        f"先最多等待3s事件预热，再等待 {wait_time:.3f}s 统计通信状态",
    )

    try:
        TextEvents().wait(gCanTextEvent_RX, 3000)
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
        ctx.can.set_info('gErrorFrameCount', 0)
    except Exception:
        pass

    total_ms = max(0, int(wait_time * 1000))
    try:
        from slplus.time import sl_time
        sl_time().sleep(total_ms)
    except Exception:
        time.sleep(total_ms / 1000.0)

    frame_cnt = len(ctx.can.messages)
    err_cnt = ctx.can.get_info('gErrorFrameCount') or 0

    TestLog(
        "INFO",
        "CAN通信状态",
        f"统计窗口结果: frame_cnt = {frame_cnt}, gErrorFrameCount = {err_cnt}",
    )

    if frame_cnt > 0 and err_cnt == 0:
        TestLog("PASS", " ", "期望结果：CAN通信状态检查, 实际结果：DUT通信正常，总线上有报文的传输，且无错误帧")
        return 0
    elif frame_cnt > 0 and err_cnt > 0:
        TestLog("WARNING", " ", "期望结果：CAN通信状态检查, 实际结果：DUT通信正常，总线上有报文的传输，但有错误帧")
        return 0
    elif frame_cnt == 0 and err_cnt > 0:
        TestLog("FAIL", " ", "期望结果：CAN通信状态检查, 实际结果：DUT通信不正常，总线上无报文的传输，有错误帧")
        return -1
    else:
        TestLog("FAIL", " ", "期望结果：CAN通信状态检查, 实际结果：DUT通信未恢复")
        return -1


def setup_can_channels_and_callbacks(purpose="通用"):
    """
    CAN通道配置函数
    """

    try:
        # 获取CAN通道配置
        cans = DEFAULT_CAN_CHANNELS
        if not cans:
            TestLog("FAIL", "", "CAN通道配置失败")
            return False

        max_channels = min(len(cans), len(DEFAULT_CAN_CHANNELS))
        TestLog("INFO", "", f"激活所有DEFAULT_CAN_CHANNELS通道")

        register_canmsg_handler(_on_canmsg)
        register_busevent_handler(_on_busevent)

        activated_count = 0

        for i in range(max_channels):
            can_ch = cans[i]
            try:
                print(f"[DEBUG] 激活CAN通道 {can_ch}")
                sl_can(can_ch).active()
                print(f"[DEBUG] CAN通道 {can_ch} 激活成功")

                activated_count += 1
                TestLog("INFO", "通道激活", f"成功激活CAN通道 {can_ch}")

            except Exception as e:
                TestLog("WARNING", "通道激活", f"激活CAN通道 {can_ch} 失败: {e}")
                import traceback
                print(f"[DEBUG] 通道激活异常详情: {traceback.format_exc()}")

        if activated_count > 0:
            TestLog("PASS", "", f"成功激活{activated_count}个CAN通道用于{purpose}")
            return True
        else:
            TestLog("FAIL", "", f"未能激活任何CAN通道用于{purpose}")
            return False

    except Exception as e:
        TestLog("FAIL", "", f"CAN通道设置失败: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
        return False

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
        TestLog("INFO", "", "开始CAN测试设置和通信检查")

        # Step1: 设置DUT供电电压
        TestLog("INFO", "", f"设置DUT供电电压为 {normal_voltage:.2f}V")
        ctx.power_ctrl.set_voltage(normal_voltage)
        ctx.power_ctrl.on()

        # Step2: 执行KL30上电
        TestLog("INFO", "", "执行KL30上电")
        ctx.bob_ctrl.set_power('KL30', True)

        # Step3: 根据DUT通信唤醒方式启动唤醒
        TestLog("INFO", "", "根据DUT通信唤醒方式，启动ECU唤醒")
        WakeupStart()

        # Step5: 等待通信稳定并检查通信状态
        TestLog("INFO", "", f"等待 {stable_time}s 至CAN通信稳定")
        ret = check_can_communication_state(stable_time)

        if ret != 0:
            TestLog("FAIL", "", "CAN通信状态检查失败")
            return -1

        TestLog("PASS", "", "CAN测试设置和通信检查完成")
        return 0

    except Exception as e:
        TestLog("FAIL", "", f"CAN测试设置失败: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
        return -1


'''
模块初始化
'''
def can_initialization(session_dir=None):
    """
    CAN测试初始化函数
    """
    try:
        TestLog("INFO", "", "开始CAN相关初始化")

        # 1. 清空全局上下文
        TestLog("INFO", "Step1", "初始化全局上下文")
        ctx.can.reset_all()
        ctx.can.clear_messages()
        # 初始化必要的字段
        ctx.can.set_info('gErrorFrameCount', 0)
        ctx.can.set_info('can_db_msg_defs', {})

        # 2. 配置和激活CAN通道
        TestLog("INFO", "Step2", "配置和激活CAN通道")
        if not setup_can_channels_and_callbacks(purpose="CAN测试初始化"):
            TestLog("FAIL", "", "CAN通道配置失败")
            return False


        # 3. 读取数据库文件数据
        TestLog("INFO", "Step3", "读取数据库文件数据")
        can_db_msg_defs = _load_and_parse_database()
        if not can_db_msg_defs:
            TestLog("FAIL", "", "数据库文件解析失败")
            return False

        ctx.can.set_info('can_db_msg_defs', can_db_msg_defs)

        TestLog("INFO", "Step4", "启动运行时环境")
        sl_runtime.start()

        ecu_name = (P.ECUInfo.ECUName or '').strip()
        TestLog("INFO", "", f"初始化完成 - 配置通道: {len(DEFAULT_CAN_CHANNELS)}, ECU [{ecu_name}] TX报文: {len(can_db_msg_defs)} 条")
        return True

    except Exception as e:
        TestLog("FAIL", "", f"初始化失败: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
        return False

def can_deinitialization():
    """
    CAN测试去初始化函数
    """
    TestLog("INFO", "CAN测试去初始化", "开始CAN测试去初始化...")

    try:
        try:
            TestLog("INFO", "Step0", "取消注册CAN事件回调")
            unregister_canmsg_handler(_on_canmsg)
            unregister_busevent_handler(_on_busevent)
            TestLog("INFO", "", f"已取消注册")
        except Exception as e:
            TestLog("WARNING", "事件回调", f"取消注册失败: {e}")

        # 1. 停用通道
        TestLog("INFO", "Step1", "停用CAN通道")
        for can_ch in DEFAULT_CAN_CHANNELS:
            try:
                sl_can(can_ch).deactive()
                TestLog("INFO", "", f"成功停用CAN通道 {can_ch}")
            except Exception as e:
                TestLog("WARNING", "通道停用", f"停用CAN通道 {can_ch} 失败: {e}")

        # 2. 停止运行时环境
        TestLog("INFO", "Step2", "停止运行时环境")
        sl_runtime.stop()

        # 3. 清理全局上下文
        TestLog("INFO", "Step2", "清理全局上下文")
        ctx.can.reset_all()

        TestLog("INFO", "", "去初始化完成")
        return True

    except Exception as e:
        TestLog("FAIL", "", f"去初始化失败: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
        return False


# ========== 故障注入和通信检查功能 ==========
def can_fault_injection(fault_type, target_can_channel, duration_ms=60000):
    """模拟CAN总线故障注入"""
    try:
        FAULT_MAP = {
            'CAN_H_short_power': ('_H', 'SHORT_KL30', "CAN_H对电源短路"),
            'CAN_L_short_power': ('_L', 'SHORT_KL30', "CAN_L对电源短路"),
            'CAN_H_short_GND':   ('_H', 'SHORT_GND',  "CAN_H对地短路"),
            'CAN_L_short_GND':   ('_L', 'SHORT_GND',  "CAN_L对地短路"),
            'CAN_H_L_short':     ('_HL',   'SHORT',      "CAN_H与CAN_L短路"),
            'CAN_H_Open':        ('_H', 'OPEN',       "CAN_H断开"),
            'CAN_L_Open':        ('_L', 'OPEN',       "CAN_L断开"),
        }

        fault_info = FAULT_MAP.get(fault_type)
        if fault_info is None:
            TestLog("FAIL", "", f"未知故障类型: {fault_type}")
            return False

        suffix, kind, fault_desc = fault_info
        target = f"CAN{target_can_channel}{suffix}"

        TestLog("INFO", "", f"开始注入{fault_desc}，目标={target}，持续时间={duration_ms}ms")

        # 注入故障
        success, status = ctx.bob_ctrl.set_fault(target, kind, enable=True)
        if not success:
            TestLog("FAIL", "", f"{fault_desc}注入失败: {status}")
            return False

        TestLog("INFO", "", f"{fault_desc}注入成功，等待{duration_ms}ms")
        time.sleep(duration_ms / 1000.0)
        return True
    except Exception as e:
        TestLog("ERROR", "", f"故障注入异常: {e}")
        return False

def can_clear_injection(fault_type, target_can_channel):
    """模拟CAN总线故障注入"""
    try:
        FAULT_MAP = {
            'CAN_H_short_power': ('_H', 'SHORT_KL30', "CAN_H对电源短路"),
            'CAN_L_short_power': ('_L', 'SHORT_KL30', "CAN_L对电源短路"),
            'CAN_H_short_GND':   ('_H', 'SHORT_GND',  "CAN_H对地短路"),
            'CAN_L_short_GND':   ('_L', 'SHORT_GND',  "CAN_L对地短路"),
            'CAN_H_L_short':     ('_HL',   'SHORT',      "CAN_H与CAN_L短路"),
            'CAN_H_Open':        ('_H', 'OPEN',       "CAN_H断开"),
            'CAN_L_Open':        ('_L', 'OPEN',       "CAN_L断开"),
        }

        fault_info = FAULT_MAP.get(fault_type)
        if fault_info is None:
            TestLog("FAIL", "", f"未知故障类型: {fault_type}")
            return False

        suffix, kind, fault_desc = fault_info
        target = f"CAN{target_can_channel}{suffix}"

        TestLog("INFO", "", f"开始注入{fault_desc}，目标={target}")

        # 清除故障
        t1 = time.time()
        success, status = ctx.bob_ctrl.set_fault(target, kind, enable=False)
        if not success:
            TestLog("FAIL", "", f"{fault_desc}清除失败: {status}")
        else:
            TestLog("INFO", "", f"{fault_desc}已清除")
            sl_can(target_can_channel).deactive()
            sl_can(target_can_channel).active()
        return True, t1

    except Exception as e:
        TestLog("ERROR", "", f"故障注入异常: {e}")
        return False


def check_communication_recovery_time(start_time_t1, timeout_ms=2000):
    """故障恢复后规定时间内检查通信恢复时间"""
    error_count_before = ctx.can.get_info('gErrorFrameCount') or 0
    msg_count_before = len(ctx.can.messages)

    TestLog("INFO", "", f"开始监控通信恢复，超时时间{timeout_ms}ms")

    while (time.time() - start_time_t1) * 1000 < timeout_ms:
        # 检查是否有新的CAN报文接收
        current_msg_count = len(ctx.can.messages)
        current_error_count = ctx.can.get_info('gErrorFrameCount') or 0

        if current_msg_count > msg_count_before and current_error_count <= error_count_before:
            recovery_time = (time.time() - start_time_t1) * 1000
            TestLog("INFO", "", f"通信已恢复，恢复时间: {recovery_time:.2f}ms")
            return True, recovery_time

        time.sleep(0.001)

    TestLog("WARNING", "", f"在{timeout_ms}ms内通信未恢复")
    return False, timeout_ms

def get_all_id_time(messages):
    id_timems = {}
    ret = {}
    for m in messages:
        if m.id not in id_timems:
            id_timems[m.id] = []
        id_timems[m.id].append(m.time_ms)

    for can_id, ts in id_timems.items():
        ts.sort()  # 保险起见再排一次序
        if len(ts) < 2:  # 只有 1 帧，算不出周期
            TestLog("DEBUG", "", f"0x{can_id:x}, Tmin=N/A, Tmax=N/A, Tavg=N/A")
            continue

        deltas = [ts[i] - ts[i - 1] for i in range(1, len(ts))]
        t_min = min(deltas)
        t_max = max(deltas)
        t_avg = sum(deltas) / len(deltas)
        ret[can_id] = (t_min, t_max, t_avg)

    return ret




