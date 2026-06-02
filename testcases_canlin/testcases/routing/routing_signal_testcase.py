import time
import traceback
from uvtest.testlog import TestLog
from uvtest.framework import TestFixture
from common.control import TestStart, TestEnd
from common.context import ctx
from .routing_module import (
    routing_initialization, routing_deinitialization,
    get_routing_config, get_routing_sender,
    can_power_setup_and_communication_check,
    check_routing, analyze_dest_cycle, analyze_routing_delay,
    SEND_MODE_SIGNAL, CHECK_MODE_SIGNAL, SEND_MODE_INCREMENT,
    CHECK_MODE_BASIC, CHECK_MODE_DLC, CHECK_MODE_FRAMETYPE, CHECK_MODE_DATA,
)


class RoutingSignalTestFixture(TestFixture):
    def group_setup(self, context=None):
        routing_initialization()

    def group_teardown(self, context=None):
        routing_deinitialization()

    def case_setup(self, context=None):
        if context:
            TestStart(context["test_name"])
    def case_teardown(self, context=None):
        TestEnd("")
        TestLog("INFO", "", "执行测试结束和去初始化")



def test_TG3_TC1_Routing_DestNetwork_Check_Signal():
    """
    目标网络检查
    """
    sender = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        entries = list(cfg.iter_signal_entries())
        if not entries:
            TestLog("WARNING", "",
                    "未找到信号路由类型的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            src_signal_name = e.get('SrcSignalName', '')
            dest_signal_name = e.get('DestSignalName', '')

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})  

            duration_ms = cfg.get_duration_ms(e)
            sender.send(idx, e, mode=SEND_MODE_SIGNAL, duration_ms=duration_ms, step="Step2")

            ret, _ = check_routing(e, expect_count=10, mode=CHECK_MODE_SIGNAL)

            expected = f"目标网段({dest_net})接收到目标报文(ID=0x{dest_id:x})"
            if ret == 0:
                TestLog("PASS", "Step3",
                        f"期望结果：{expected}  "
                        f"实际结果目标网段正常接收到目标报文 "
                        f"(源信号={src_signal_name}, 目标信号={dest_signal_name})")
            else:
                TestLog("FAIL", "Step3",
                        f"期望结果：{expected}  "
                        f"实际结果目标网段未接收到目标报文 "
                        f"(源信号={src_signal_name}, 目标信号={dest_signal_name})")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG3_TC2_Routing_FrameType_Check_Signal():
    """
    报文类型检查
    """
    sender = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        entries = list(cfg.iter_signal_entries())
        if not entries:
            TestLog("WARNING", "",
                    "未找到信号路由类型的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            src_signal_name = e.get('SrcSignalName', '')
            dest_signal_name = e.get('DestSignalName', '')
            expected_type = e.get('DestMsgFrameType', 'CAN')

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})  

            duration_ms = cfg.get_duration_ms(e)
            sender.send(idx, e, mode=SEND_MODE_SIGNAL, duration_ms=duration_ms, step="Step2")

            ret, details = check_routing(e, expect_count=10, mode=CHECK_MODE_FRAMETYPE)
            actual_type = details[0].get('actual_frametype', 'Unknown') if details else 'Unknown'

            if ret == 0:
                TestLog("PASS", "Step3",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"帧类型={actual_type} 与路由表定义一致")
            else:
                TestLog("FAIL", "Step3",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"帧类型不一致: 期望={expected_type} 实际={actual_type}")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG3_TC3_Routing_ID_Check_Signal():
    """
    ID检查
    """
    sender = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        entries = list(cfg.iter_signal_entries())
        if not entries:
            TestLog("WARNING", "",
                    "未找到信号路由类型的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            src_signal_name = e.get('SrcSignalName', '')
            dest_signal_name = e.get('DestSignalName', '')

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})  

            duration_ms = cfg.get_duration_ms(e)
            sender.send(idx, e, mode=SEND_MODE_SIGNAL, duration_ms=duration_ms, step="Step2")

            ret, _ = check_routing(e, expect_count=10, mode=CHECK_MODE_BASIC)

            if ret == 0:
                TestLog("PASS", "Step3",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"目标网段接收的报文ID与路由表定义一致")
            else:
                TestLog("FAIL", "Step3",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"源ID=0x{src_id:x} 期望目标ID=0x{dest_id:x} "
                        f"目标网段未接收到正确ID的报文")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")



def test_TG3_TC4_Routing_DLC_Check_Signal():
    """
    DLC检查
    """
    sender = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        entries = list(cfg.iter_signal_entries())
        if not entries:
            TestLog("WARNING", "",
                    "未找到信号路由类型的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            src_signal_name = e.get('SrcSignalName', '')
            dest_signal_name = e.get('DestSignalName', '')
            expected_dlc = int(e.get('DestMsgDLC', 8) or 8)

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})  

            duration_ms = cfg.get_duration_ms(e)
            sender.send(idx, e, mode=SEND_MODE_SIGNAL, duration_ms=duration_ms, step="Step2")

            ret, details = check_routing(e, expect_count=10, mode=CHECK_MODE_DLC)
            actual_dlc = details[0].get('actual_dlc', -1) if details else -1

            if ret == 0:
                TestLog("PASS", "Step3",
                        f"期望结果:DLC={expected_dlc}实际结果DLC={actual_dlc} "
                        f"(源信号={src_signal_name}, 目标信号={dest_signal_name}, 目标ID=0x{dest_id:x})")
            else:
                TestLog("FAIL", "Step3",
                        f"期望结果:DLC={expected_dlc}实际结果DLC={actual_dlc} "
                        f"(源信号={src_signal_name}, 目标信号={dest_signal_name}, 目标ID=0x{dest_id:x})")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG3_TC5_Routing_Data_Check_Signal():
    """
    信号值检查
    """
    sender = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        entries = list(cfg.iter_signal_entries())
        if not entries:
            TestLog("WARNING", "",
                    "未找到信号路由类型的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            src_signal_name = e.get('SrcSignalName', '')
            dest_signal_name = e.get('DestSignalName', '')

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {}) 

            duration_ms = cfg.get_duration_ms(e)
            sender.send(idx, e, mode=SEND_MODE_SIGNAL, duration_ms=duration_ms, step="Step2")

            ret, _ = check_routing(e, expect_count=10, mode=CHECK_MODE_SIGNAL)

            if ret == 0:
                TestLog("PASS", "Step3",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"信号值与源网段发送的一致")
            else:
                TestLog("FAIL", "Step3",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"信号值与源网段发送的不一致")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")



def test_TG3_TC6_Routing_Delay_Check_Signal():
    """
    路由延迟时间检查
    """
    sender = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        entries = list(cfg.iter_signal_entries())
        if not entries:
            TestLog("WARNING", "",
                    "未找到信号路由类型的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            src_signal_name = e.get('SrcSignalName', '')
            dest_signal_name = e.get('DestSignalName', '')
            max_delay_ms = float(e.get('TransmitDelayTime', 30) or 30)

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})  

            duration_ms = cfg.get_duration_ms(e)
            sender.send(idx, e, mode=SEND_MODE_SIGNAL, duration_ms=duration_ms, step="Step2")

            ret, _ = check_routing(e, expect_count=10, mode=CHECK_MODE_SIGNAL)
            if ret != 0:
                TestLog("FAIL", "",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} 基础检查失败")
                continue

            ret, delay_results = analyze_routing_delay(dest_id, max_delay_ms)

            if not delay_results:
                TestLog("WARNING", "",
                        f"目标ID=0x{dest_id:x} 无法计算延迟时间")
                continue

            delays = [r['delay_ms'] for r in delay_results]
            avg_delay = sum(delays) / len(delays) if delays else 0
            max_actual_delay = max(delays) if delays else 0

            expected_delay = f"延迟时间<={max_delay_ms:.1f}ms"
            actual_delay_info = f"平均={avg_delay:.2f}ms, 最大={max_actual_delay:.2f}ms"
            if ret:
                TestLog("PASS", "Step3",
                        f"期望结果：{expected_delay}实际结果{actual_delay_info} "
                        f"(源信号={src_signal_name}, 目标信号={dest_signal_name}, 目标ID=0x{dest_id:x})")
            else:
                TestLog("FAIL", "Step3",
                        f"期望结果：{expected_delay}实际结果{actual_delay_info} "
                        f"(源信号={src_signal_name}, 目标信号={dest_signal_name}, 目标ID=0x{dest_id:x})")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG3_TC7_Routing_HighLoad_Check_Signal():
    """
    总线高负载路由测试
    """
    sender = None
    high_load_timer_ids = []
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        entries = list(cfg.iter_signal_entries())
        if not entries:
            TestLog("WARNING", "",
                    "未找到信号路由类型的路由表项")
            return

        from common.params import P
        busload_high = P.CANInfo.BusloadHigh_pct if hasattr(P.CANInfo, 'BusloadHigh_pct') else 90.0

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            src_signal_name = e.get('SrcSignalName', '')
            dest_signal_name = e.get('DestSignalName', '')
            max_delay_ms = float(e.get('TransmitDelayTime', 30) or 30)

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})

            TestLog("INFO", "Step2",
                    f"在目标网段={dest_net}模拟发送最低优先级报文(ID=0x7FF)，"
                    f"目标负载={busload_high}%")

            high_load_timer_ids, actual_busload = sender.send_high_load(
                idx, e, load_percent=int(busload_high), target_busload=busload_high
            )

            if actual_busload < busload_high:
                TestLog("WARNING", "",
                        f"未能达到目标负载: 实际={actual_busload}% < 目标={busload_high}%")

            TestLog("INFO", "",
                    f"高负载已建立(负载={actual_busload}%)，等待10s...")
            time.sleep(10)

            TestLog("INFO", "Step3",
                    f"在源网段={src_net}发送信号报文 ID=0x{src_id:x}")
            duration_ms = cfg.get_duration_ms(e)
            sender.send(idx, e, mode=SEND_MODE_SIGNAL, duration_ms=duration_ms)

            ret_basic, _ = check_routing(e, expect_count=10, mode=CHECK_MODE_SIGNAL)

            ret_type, type_details = check_routing(e, expect_count=10, mode=CHECK_MODE_FRAMETYPE)
            actual_type = type_details[0].get('actual_frametype', 'Unknown') if type_details else 'Unknown'

            ret_dlc, dlc_details = check_routing(e, expect_count=10, mode=CHECK_MODE_DLC)
            actual_dlc = dlc_details[0].get('actual_dlc', -1) if dlc_details else -1

            delay_pass, delay_results = analyze_routing_delay(dest_id, max_delay_ms)
            max_actual_delay = max([r['delay_ms'] for r in delay_results]) if delay_results else 0

            ret = (ret_basic == 0 and ret_type == 0 and ret_dlc == 0 and delay_pass)

            sender.stop_high_load(high_load_timer_ids)
            high_load_timer_ids = []

            if ret:
                TestLog("PASS", "Step4",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"高负载({actual_busload}%)下路由正常: 帧类型={actual_type} DLC={actual_dlc} "
                        f"最大延迟={max_actual_delay:.2f}ms")
            else:
                fail_reasons = [msg for cond, msg in [
                    (ret_basic != 0, "未收到目标报文"),
                    (ret_type != 0, f"帧类型不匹配(实际={actual_type})"),
                    (ret_dlc != 0, f"DLC不匹配(实际={actual_dlc})"),
                    (not delay_pass, f"延迟超限(实际={max_actual_delay:.2f}ms,限值={max_delay_ms}ms)"),
                ] if cond]
                fail_desc = ", ".join(fail_reasons) or "未知错误"
                TestLog("FAIL", "Step4",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"高负载({actual_busload}%)下路由异常: {fail_desc}")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if high_load_timer_ids and sender is not None:
            sender.stop_high_load(high_load_timer_ids)
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")



def test_TG3_TC8_Routing_DLCLessThan_Check_Signal():
    """
    DLC小于预期测试
    """
    sender = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        entries = list(cfg.iter_signal_entries())
        if not entries:
            TestLog("WARNING", "",
                    "未找到信号路由类型的路由表项")
            return

        dlc_less_than_expected = 1

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            src_signal_name = e.get('SrcSignalName', '')
            dest_signal_name = e.get('DestSignalName', '')
            expected_dlc = int(e.get('SrcMsgDLC', 8) or 8)

            if expected_dlc <= 1:
                TestLog("INFO", "",
                        f"源网段={src_net} 源ID=0x{src_id:x} DLC=1，跳过此条目")
                continue

            reduced_dlc = expected_dlc - 1

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})  

            duration_ms = cfg.get_duration_ms(e)
            sender.send_with_custom_dlc(idx, e, custom_dlc=reduced_dlc, duration_ms=duration_ms)

            dest_records = ctx.can.get_info('routing_dest_records') or []
            received_count = sum(1 for r in dest_records
                                 if int(r.get('MsgId', -1)) == dest_id)

            if dlc_less_than_expected == 0:
                if received_count == 0:
                    TestLog("PASS", "Step3",
                            f"源网段={src_net} 目标网段={dest_net} "
                            f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                            f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                            f"DLC={reduced_dlc}(<{expected_dlc}) 未转发，符合预期")
                else:
                    TestLog("FAIL", "Step3",
                            f"源网段={src_net} 目标网段={dest_net} "
                            f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                            f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                            f"DLC={reduced_dlc}(<{expected_dlc}) 被转发，不符合预期")
            else:
                if received_count > 0:
                    TestLog("PASS", "Step3",
                            f"源网段={src_net} 目标网段={dest_net} "
                            f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                            f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                            f"DLC={reduced_dlc}(<{expected_dlc}) 已转发，符合预期")
                else:
                    TestLog("FAIL", "Step3",
                            f"源网段={src_net} 目标网段={dest_net} "
                            f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                            f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                            f"DLC={reduced_dlc}(<{expected_dlc}) 未转发，不符合预期")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG3_TC9_Routing_DLCGreaterThan_Check_Signal():
    """
    DLC大于预期测试
    """
    sender = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        entries = list(cfg.iter_signal_entries())
        if not entries:
            TestLog("WARNING", "",
                    "未找到信号路由类型的路由表项")
            return

        dlc_larger_than_expected = 1

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            src_signal_name = e.get('SrcSignalName', '')
            dest_signal_name = e.get('DestSignalName', '')
            expected_dlc = int(e.get('SrcMsgDLC', 8) or 8)
            is_canfd = e.get('SrcMsgFrameType') == 'CANFD'

            if is_canfd and expected_dlc >= 15:
                TestLog("INFO", "",
                        f"源网段={src_net} 源ID=0x{src_id:x} CANFD DLC=15，跳过此条目")
                continue
            if not is_canfd and expected_dlc >= 8:
                TestLog("INFO", "",
                        f"源网段={src_net} 源ID=0x{src_id:x} CAN DLC=8，跳过此条目")
                continue

            increased_dlc = expected_dlc + 1

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {}) 

            duration_ms = cfg.get_duration_ms(e)
            sender.send_with_custom_dlc(idx, e, custom_dlc=increased_dlc, duration_ms=duration_ms)

            dest_records = ctx.can.get_info('routing_dest_records') or []
            received_count = sum(1 for r in dest_records
                                 if int(r.get('MsgId', -1)) == dest_id)

            if dlc_larger_than_expected == 0:
                if received_count == 0:
                    TestLog("PASS", "Step3",
                            f"源网段={src_net} 目标网段={dest_net} "
                            f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                            f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                            f"DLC={increased_dlc}(>{expected_dlc}) 未转发，符合预期")
                else:
                    TestLog("FAIL", "Step3",
                            f"源网段={src_net} 目标网段={dest_net} "
                            f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                            f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                            f"DLC={increased_dlc}(>{expected_dlc}) 被转发，不符合预期")
            else:
                if received_count > 0:
                    TestLog("PASS", "Step3",
                            f"源网段={src_net} 目标网段={dest_net} "
                            f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                            f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                            f"DLC={increased_dlc}(>{expected_dlc}) 已转发，符合预期")
                else:
                    TestLog("FAIL", "Step3",
                            f"源网段={src_net} 目标网段={dest_net} "
                            f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                            f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                            f"DLC={increased_dlc}(>{expected_dlc}) 未转发，不符合预期")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")



def test_TG3_TC10_Routing_PowerOnInitValue_Check_Signal():
    """
    路由上电初始值测试
    """
    sender = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        TestLog("INFO", "", "等待3s记录唤醒后所有网段接收到的报文...")
        ctx.can.set_info('routing_dest_records', [])
        ctx.can.set_info('sRxMsgInfoList', {})

        time.sleep(3)

        TestLog("INFO", "", "遍历路由表，比较信号初始值...")

        dest_records = ctx.can.get_info('routing_dest_records') or []
        dest_records_sorted = sorted(dest_records, key=lambda r: float(r.get('time_ms', 0)))
        first_received = {}
        for r in dest_records_sorted:
            msg_id = int(r.get('MsgId', -1))
            if msg_id not in first_received:
                first_received[msg_id] = r

        TestLog("INFO", "",
                f"共记录到 {len(dest_records)} 帧报文，涉及 {len(first_received)} 个不同ID")

        entries = list(cfg.iter_signal_entries())
        if not entries:
            TestLog("WARNING", "", "未找到信号路由类型的路由表项")
            return

        pass_count = 0
        fail_count = 0
        skip_count = 0

        for _, e in entries:
            src_id = int(e.get('SrcMsgId', 0))
            dest_id = int(e.get('DestMsgId', 0))
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            src_signal_name = e.get('SrcSignalName', '')
            dest_signal_name = e.get('DestSignalName', '')
            init_value_str = e.get('DestInitValue', None)

            if init_value_str is None:
                TestLog("INFO", "",
                        f"信号={dest_signal_name} 未定义初始值(DestInitValue)，跳过")
                skip_count += 1
                continue

            if isinstance(init_value_str, str):
                init_value = int(init_value_str, 16) if init_value_str.lower().startswith('0x') else int(init_value_str)
            else:
                init_value = int(init_value_str) if init_value_str is not None else 0

            if dest_id not in first_received:
                TestLog("FAIL", "Step3",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"目标ID=0x{dest_id:x} 未收到报文")
                fail_count += 1
                continue

            received_msg = first_received[dest_id]
            actual_signal_value = cfg.extract_signal_value(received_msg, e)
            dest_time_ms = float(received_msg.get('time_ms', 0))

            src_first_time_ms = None
            if src_id in first_received:
                src_first_time_ms = float(first_received[src_id].get('time_ms', 0))

            src_before_dest = (src_first_time_ms is not None and src_first_time_ms < dest_time_ms)

            if actual_signal_value == init_value:
                TestLog("PASS", "Step3",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"目标ID=0x{dest_id:x} 第1帧信号值={actual_signal_value} "
                        f"与初始值={init_value}一致")
                pass_count += 1
            else:
                payload_hex = received_msg.get('payload_hex', '')
                if src_before_dest:
                    TestLog("WARNING", "Step3",
                            f"源网段={src_net} 目标网段={dest_net} "
                            f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                            f"目标ID=0x{dest_id:x} 源ID=0x{src_id:x} "
                            f"源报文({src_first_time_ms:.3f}ms)先于目标报文({dest_time_ms:.3f}ms)出现 "
                            f"DUT可能已收到源报文，信号值={actual_signal_value}(非初始值{init_value})")
                    skip_count += 1
                else:
                    TestLog("FAIL", "Step3",
                            f"源网段={src_net} 目标网段={dest_net} "
                            f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                            f"目标ID=0x{dest_id:x} 第1帧信号值={actual_signal_value} "
                            f"期望初始值={init_value} 数据={payload_hex}")
                    fail_count += 1

        TestLog("INFO", "",
                f"测试完成: PASS={pass_count}, FAIL={fail_count}, SKIP={skip_count}")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG3_TC11_Routing_LastValue_Check_Signal():
    """
    路由上次值测试
    """
    sender = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        entries = list(cfg.iter_signal_entries())
        if not entries:
            TestLog("WARNING", "",
                    "未找到信号路由类型的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            src_signal_name = e.get('SrcSignalName', '')
            dest_signal_name = e.get('DestSignalName', '')
            timeout_ms = float(e.get('Ttimeout', 1000) or 1000)

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})  

            duration_ms = cfg.get_duration_ms(e)
            last_signal_value = sender.send(idx, e, mode=SEND_MODE_SIGNAL, duration_ms=duration_ms, step="Step2")

            sender.stop_send(idx, e)
            wait_time_s = (timeout_ms * 0.8) / 1000.0
            TestLog("INFO", "",
                    f"停止发送，等待{wait_time_s:.2f}s（0.8倍超时时间）")
            time.sleep(wait_time_s)

            dest_records = ctx.can.get_info('routing_dest_records') or []
            last_received = None
            for r in reversed(dest_records):
                if int(r.get('MsgId', -1)) == dest_id:
                    last_received = r
                    break

            if last_received is None:
                TestLog("FAIL", "",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"目标ID=0x{dest_id:x} 未收到报文")
                continue

            actual_signal_value = cfg.extract_signal_value(last_received, e)

            if actual_signal_value == last_signal_value:
                TestLog("PASS", "Step3",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"目标ID=0x{dest_id:x} 信号值={actual_signal_value} 与上次发送值一致")
            else:
                TestLog("FAIL", "Step3",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"目标ID=0x{dest_id:x} 实际值={actual_signal_value} 期望值={last_signal_value}")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")



def test_TG3_TC12_Routing_TimeoutValue_Check_Signal():
    """
    路由超时值测试
    """
    sender = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        entries = list(cfg.iter_signal_entries())
        if not entries:
            TestLog("WARNING", "",
                    "未找到信号路由类型的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            src_signal_name = e.get('SrcSignalName', '')
            dest_signal_name = e.get('DestSignalName', '')
            timeout_ms = float(e.get('Ttimeout', 1000) or 1000)
            timeout_value = e.get('TimeOutValue', None)

            if timeout_value is None or timeout_value == 0:
                TestLog("INFO", "",
                        f"信号={dest_signal_name} 未定义超时值(TimeOutValue=0)，跳过")
                continue

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {}) 

            duration_ms = cfg.get_duration_ms(e)
            sender.send(idx, e, mode=SEND_MODE_SIGNAL, duration_ms=duration_ms, step="Step2")

            sender.stop_send(idx, e)
            wait_time_s = (timeout_ms * 1.2) / 1000.0
            TestLog("INFO", "",
                    f"停止发送，等待{wait_time_s:.2f}s（1.2倍超时时间）")
            time.sleep(wait_time_s)

            dest_records = ctx.can.get_info('routing_dest_records') or []
            last_received = None
            for r in reversed(dest_records):
                if int(r.get('MsgId', -1)) == dest_id:
                    last_received = r
                    break

            if last_received is None:
                TestLog("FAIL", "",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} 未收到报文")
                continue

            actual_signal_value = cfg.extract_signal_value(last_received, e)

            if actual_signal_value == timeout_value:
                TestLog("PASS", "Step3",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"超时后信号值={actual_signal_value} 与路由表定义一致")
            else:
                TestLog("FAIL", "Step3",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"实际值={actual_signal_value} 期望超时值={timeout_value}")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG3_TC13_Routing_CycleConsistency_Check_Signal():
    """
    周期一致性测试
    """
    sender = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        entries = list(cfg.iter_signal_entries())
        if not entries:
            TestLog("WARNING", "",
                    "未找到信号路由类型的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            src_signal_name = e.get('SrcSignalName', '')
            dest_signal_name = e.get('DestSignalName', '')
            expected_cycle_ms = float(e.get('DestMsgCycleTime', 100) or 100)

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})  

            duration_ms = cfg.get_duration_ms(e)
            sender.send(idx, e, mode=SEND_MODE_SIGNAL, duration_ms=duration_ms, step="Step2")

            cycle_pass, cycle_details = analyze_dest_cycle(dest_id, expected_cycle_ms)
            if not cycle_details:
                TestLog("WARNING", "",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} 无法计算周期")
                continue

            avg_cycle = sum([d[0] for d in cycle_details]) / len(cycle_details) 

            if cycle_pass:
                TestLog("PASS", "Step3",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"平均周期={avg_cycle:.2f}ms 期望周期={expected_cycle_ms:.1f}ms")
            else:
                TestLog("FAIL", "Step3",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"平均周期={avg_cycle:.2f}ms 与期望周期={expected_cycle_ms:.1f}ms不一致")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")



def test_TG3_TC14_Routing_NetworkWakeup_Check_Signal():
    """
    网络唤醒测试
    """
    sender = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        TestLog("INFO", "Step2", "等待3s记录唤醒后所有网段接收到的报文...")
        ctx.can.set_info('routing_dest_records', [])
        time.sleep(3)

        dest_records = ctx.can.get_info('routing_dest_records') or []
        received_msg_ids = set(int(r.get('MsgId', -1)) for r in dest_records)

        entries = list(cfg.iter_signal_entries())
        if not entries:
            TestLog("WARNING", "",
                    "未找到信号路由类型的路由表项")
            return

        ret = True
        for _, e in entries:
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            src_signal_name = e.get('SrcSignalName', '')
            dest_signal_name = e.get('DestSignalName', '')

            if dest_id in received_msg_ids:
                TestLog("PASS", "Step3",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"目标ID=0x{dest_id:x} 唤醒后正确发送")
            else:
                TestLog("FAIL", "Step3",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"目标ID=0x{dest_id:x} 唤醒后未收到报文")
                ret = False

        if ret:
            TestLog("PASS", "", "所有目标信号所属报文唤醒后正确发送")
        else:
            TestLog("FAIL", "", "部分目标信号所属报文唤醒后未发送")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG3_TC15_Routing_TimeoutState_Check_Signal():
    """
    超时状态时间测试
    """
    sender = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        entries = list(cfg.iter_signal_entries())
        if not entries:
            TestLog("WARNING", "",
                    "未找到信号路由类型的路由表项")
            return

        TestLog("INFO", "", "========== Subcase1：上电初始化状态 ==========")
        TestLog("INFO", "Step1",
                "设置电源电压为Vnormal，执行KL30上电，根据DUT通信唤醒方式，"
                "使用KL15或网络管理报文唤醒网络")

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            src_cycle_ms = int(e.get('SrcMsgCycleTime', 10) or 10)
            timeout_value = e.get('TimeOutValue', None)
            src_signal_name = e.get('SrcSignalName', '')
            dest_signal_name = e.get('DestSignalName', '')

            if timeout_value is None or timeout_value == 0:
                TestLog("INFO", "",
                        f"信号={dest_signal_name} 未定义超时值(TimeOutValue=0)，跳过")
                continue

            expected_timeout_ms = src_cycle_ms * 10
            tolerance_ratio = 0.10  # ±10%偏差

            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})

            TestLog("INFO", "Step2",
                    f"根据路由表定义，选取其中一条周期信号路由，记录 DUT 发送第一帧报文的时间 t1 "
                    f"[源网段={src_net}, 目标网段={dest_net}, 源信号={src_signal_name}, "
                    f"目标信号={dest_signal_name}, 目标ID=0x{dest_id:x}]")

            wait_time_s = (expected_timeout_ms * 1.5) / 1000.0
            time.sleep(wait_time_s)

            dest_records = ctx.can.get_info('routing_dest_records') or []
            dest_msgs = [r for r in dest_records if int(r.get('MsgId', -1)) == dest_id]

            if len(dest_msgs) < 2:
                TestLog("FAIL", "Step3",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"目标ID=0x{dest_id:x} 接收报文数量不足，无法计算超时时间")
                continue

            first_msg_time_ms = float(dest_msgs[0].get('time_ms', 0))

            timeout_detected_time_ms = None
            for msg in dest_msgs:
                signal_value = cfg.extract_signal_value(msg, e)
                if signal_value == timeout_value:
                    timeout_detected_time_ms = float(msg.get('time_ms', 0))
                    break

            if timeout_detected_time_ms is None:
                TestLog("FAIL", "Step3",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"目标ID=0x{dest_id:x} 未检测到信号更新为超时值")
                continue

            actual_timeout_ms = timeout_detected_time_ms - first_msg_time_ms
            min_timeout_ms = expected_timeout_ms * (1.0 - tolerance_ratio)
            max_timeout_ms = expected_timeout_ms * (1.0 + tolerance_ratio)

            TestLog("INFO", "Step3",
                    f"利用 CANoe 检测此信号更新成超时值的时间 t2，计算超时时间 t2-t1 "
                    f"[实际超时时间={actual_timeout_ms:.2f}ms, 期望范围={min_timeout_ms:.2f}~{max_timeout_ms:.2f}ms]")

            if min_timeout_ms <= actual_timeout_ms <= max_timeout_ms:
                TestLog("PASS", "",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"目标ID=0x{dest_id:x} DUT进入超时状态的时间={actual_timeout_ms:.2f}ms "
                        f"满足要求（源网段报文的10倍周期±10%）")
            else:
                TestLog("FAIL", "",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"目标ID=0x{dest_id:x} DUT进入超时状态的时间={actual_timeout_ms:.2f}ms "
                        f"不满足要求（期望范围={min_timeout_ms:.2f}~{max_timeout_ms:.2f}ms）")

        TestLog("INFO", "", "========== Subcase2：源网段信号丢失状态 ==========")
        TestLog("INFO", "Step1",
                "设置电源电压为Vnormal，执行KL30上电，根据DUT通信唤醒方式，"
                "使用KL15或网络管理报文唤醒网络，等待Tstable时间至通信稳定")

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            src_cycle_ms = int(e.get('SrcMsgCycleTime', 10) or 10)
            timeout_value = e.get('TimeOutValue', None)
            src_signal_name = e.get('SrcSignalName', '')
            dest_signal_name = e.get('DestSignalName', '')

            if timeout_value is None or timeout_value == 0:
                continue

            expected_timeout_ms = src_cycle_ms * 10
            tolerance_ratio = 0.10  # ±10%偏差

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})

            duration_ms = cfg.get_duration_ms(e)
            TestLog("INFO", "Step2",
                    f"根据路由表定义，选取其中一条信号路由，在源网段仿真发送信号所属源报文，"
                    f"设置信号值为最大值或最小值（与DUT发送的当前信号值不同），持续发送10倍目标信号所属报文周期时间 "
                    f"[源网段={src_net}, 目标网段={dest_net}, 源信号={src_signal_name}, "
                    f"目标信号={dest_signal_name}, 目标ID=0x{dest_id:x}]")

            sender.send(idx, e, mode=SEND_MODE_SIGNAL, duration_ms=duration_ms, step="")

            sender.stop_send(idx, e)
            stop_time_ms = time.time() * 1000
            TestLog("INFO", "Step3",
                    f"待通信正常之后，停止仿真此报文，使 DUT 进入源网段丢失状态，记录此时刻 t1")

            wait_time_s = (expected_timeout_ms * 1.5) / 1000.0
            time.sleep(wait_time_s)

            dest_records = ctx.can.get_info('routing_dest_records') or []
            dest_msgs_after_stop = [r for r in dest_records
                                    if int(r.get('MsgId', -1)) == dest_id
                                    and float(r.get('time_ms', 0)) > stop_time_ms]

            if not dest_msgs_after_stop:
                TestLog("FAIL", "Step4",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"目标ID=0x{dest_id:x} 停止发送后未接收到报文")
                continue

            timeout_detected_time_ms = None
            for msg in dest_msgs_after_stop:
                signal_value = cfg.extract_signal_value(msg, e)
                if signal_value == timeout_value:
                    timeout_detected_time_ms = float(msg.get('time_ms', 0))
                    break

            if timeout_detected_time_ms is None:
                TestLog("FAIL", "Step4",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"目标ID=0x{dest_id:x} 未检测到信号更新为超时值")
                continue

            actual_timeout_ms = timeout_detected_time_ms - stop_time_ms
            min_timeout_ms = expected_timeout_ms * (1.0 - tolerance_ratio)
            max_timeout_ms = expected_timeout_ms * (1.0 + tolerance_ratio)

            TestLog("INFO", "Step4",
                    f"利用 CANoe 检测此信号更新成超时值的时间 t2，计算超时时间 t2-t1 "
                    f"[实际超时时间={actual_timeout_ms:.2f}ms, 期望范围={min_timeout_ms:.2f}~{max_timeout_ms:.2f}ms]")

            if min_timeout_ms <= actual_timeout_ms <= max_timeout_ms:
                TestLog("PASS", "",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"目标ID=0x{dest_id:x} DUT进入超时状态的时间={actual_timeout_ms:.2f}ms "
                        f"满足要求（源网段报文的10倍周期±10%）")
            else:
                TestLog("FAIL", "",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源信号={src_signal_name} 目标信号={dest_signal_name} "
                        f"目标ID=0x{dest_id:x} DUT进入超时状态的时间={actual_timeout_ms:.2f}ms "
                        f"不满足要求（期望范围={min_timeout_ms:.2f}~{max_timeout_ms:.2f}ms）")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")
