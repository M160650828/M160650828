import time
from uvtest.testlog import TestLog
from common.context import ctx
from env.config import DEFAULT_CAN_CHANNELS, MESSAGE_COUNT_OUTPUT_INTERVAL
from slplus.can import sl_can, register_canmsg_handler, unregister_canmsg_handler
from slplus.runtime import sl_runtime

from sl.sl_event import register_busevent_handler, unregister_busevent_handler, EventType
from slplus.event import TextEvents
from slplus.time import sl_time

from common.params import P
from common.signal_parser import sig

'''
variable
'''
gCanTextEvent_RX = "CAN Frame is Received"
gCanTextEvent_TX = "CAN Frame is Transmitted"


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

        TestLog("INFO", "", "CAN协议相关清理完成")

        TestLog("INFO", "", "去初始化完成")
        return True

    except Exception as e:
        TestLog("FAIL", "", f"去初始化失败: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
        return False

