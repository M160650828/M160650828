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
    check_routing, analyze_routing_delay,
    CHECK_MODE_BASIC, CHECK_MODE_DLC, CHECK_MODE_FRAMETYPE, CHECK_MODE_DATA,
    SEND_MODE_INCREMENT,
)


class RoutingEventTestFixture(TestFixture):
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


def test_TG2_TC1_Routing_DestNetwork_Check_Event():
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

        entries = list(cfg.iter_entries_by_type("EventMsg"))
        if not entries:
            TestLog("WARNING", "",
                    "未找到 RoutingType 为 EventMsg 的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {}) 

            sender.send(idx, e, mode=SEND_MODE_INCREMENT, step="Step2")

            ret, _ = check_routing(e, expect_count=10)
            expected = f"目标网段({dest_net})接收到目标报文(ID=0x{dest_id:x})"
            if ret == 0:
                TestLog("PASS", "Step3",
                        f"期望结果：{expected}  "
                        f"实际结果：目标网段正常接收到目标报文"
                        f"(源网段={src_net}, 源ID=0x{src_id:x})")
            else:
                TestLog("FAIL", "",
                        f"期望结果：{expected}  "
                        f"实际结果：目标网段未接收到目标报文"
                        f"(源网段={src_net}, 源ID=0x{src_id:x})")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG2_TC2_Routing_FrameType_Check_Event():
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

        entries = list(cfg.iter_entries_by_type("EventMsg"))
        if not entries:
            TestLog("WARNING", "",
                    "未找到 RoutingType 为 EventMsg 的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            expected_type = e.get('DestMsgFrameType', 'CAN')

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})  

            sender.send(idx, e, mode=SEND_MODE_INCREMENT, step="Step2")

            ret, details = check_routing(e, expect_count=10, mode=CHECK_MODE_FRAMETYPE)
            actual_type = details[0].get('actual_frametype', 'Unknown') if details else 'Unknown'

            if ret == 0:
                TestLog("PASS", "Step3",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"帧类型={actual_type} 与路由表定义一致")
            else:
                TestLog("FAIL", "",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"帧类型不一致: 期望={expected_type} 实际={actual_type}")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG2_TC3_Routing_ID_Check_Event():
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

        entries = list(cfg.iter_entries_by_type("EventMsg"))
        if not entries:
            TestLog("WARNING", "",
                    "未找到 RoutingType 为 EventMsg 的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})  

            sender.send(idx, e, mode=SEND_MODE_INCREMENT, step="Step2")

            ret, _ = check_routing(e, expect_count=10, mode=CHECK_MODE_BASIC)

            if ret == 0:
                TestLog("PASS", "Step3",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"目标网段接收的报文ID与路由表定义一致")
            else:
                TestLog("FAIL", "",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源ID=0x{src_id:x} 期望目标ID=0x{dest_id:x} "
                        f"目标网段未接收到正确ID的报文")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG2_TC4_Routing_DLC_Check_Event():
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

        entries = list(cfg.iter_entries_by_type("EventMsg"))
        if not entries:
            TestLog("WARNING", "",
                    "未找到 RoutingType 为 EventMsg 的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            expected_dlc = int(e.get('DestMsgDLC', 8) or 8)

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})  

            sender.send(idx, e, mode=SEND_MODE_INCREMENT, step="Step2")

            ret, details = check_routing(e, expect_count=10, mode=CHECK_MODE_DLC)
            actual_dlc = details[0].get('actual_dlc', -1) if details else -1

            if ret == 0:
                TestLog("PASS", "Step3",
                        f"期望结果：DLC={expected_dlc}实际结果：DLC={actual_dlc}"
                        f"(源网段={src_net}, 目标网段={dest_net}, 源ID=0x{src_id:x}, 目标ID=0x{dest_id:x})")
            else:
                TestLog("FAIL", "",
                        f"期望结果：DLC={expected_dlc}实际结果：DLC={actual_dlc}"
                        f"(源网段={src_net}, 目标网段={dest_net}, 源ID=0x{src_id:x}, 目标ID=0x{dest_id:x})")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG2_TC5_Routing_Data_Check_Event():
    """
    数据内容检查
    """
    sender = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        entries = list(cfg.iter_entries_by_type("EventMsg"))
        if not entries:
            TestLog("WARNING", "",
                    "未找到 RoutingType 为 EventMsg 的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {}) 

            sender.send(idx, e, mode=SEND_MODE_INCREMENT, step="Step2")

            ret, _ = check_routing(e, expect_count=10, mode=CHECK_MODE_DATA, compare_from_byte=0)

            if ret == 0:
                TestLog("PASS", "Step3",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"数据内容与源网段发送的一致")
            else:
                TestLog("FAIL", "",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"数据内容与源网段发送的不一致")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")




def test_TG2_TC6_Routing_Delay_Check_Event():
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

        entries = list(cfg.iter_entries_by_type("EventMsg"))
        if not entries:
            TestLog("WARNING", "",
                    "未找到 RoutingType 为 EventMsg 的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            max_delay_ms = float(e.get('TransmitDelayTime', 10) or 10)

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {}) 

            sender.send(idx, e, mode=SEND_MODE_INCREMENT, step="Step2")

            ret, _ = check_routing(e, expect_count=10)
            if ret != 0:
                TestLog("FAIL", "",
                        f"源网段={src_net} 目标网段={dest_net} "
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
                        f"期望结果：{expected_delay}实际结果{actual_delay_info}"
                        f"(源网段={src_net}, 目标网段={dest_net}, 源ID=0x{src_id:x}, 目标ID=0x{dest_id:x})")
            else:
                TestLog("FAIL", "Step3",
                        f"期望结果：{expected_delay}实际结果{actual_delay_info}"
                        f"(源网段={src_net}, 目标网段={dest_net}, 源ID=0x{src_id:x}, 目标ID=0x{dest_id:x})")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG2_TC7_Routing_HighLoad_Check_Event():
    """
    总线高负载路由测试
    """
    sender = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        entries = list(cfg.iter_entries_by_type("EventMsg"))
        if not entries:
            TestLog("WARNING", "",
                    "未找到 RoutingType 为 EventMsg 的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            max_delay_ms = float(e.get('TransmitDelayTime', 10) or 10)

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})  

            sender.send_high_load(idx, e, load_percent=80)
            TestLog("INFO", "Step2",
                    f"在目标网段={dest_net}模拟高负载(ID=0x7FF)，等待10s")
            time.sleep(10)

            sender.send(idx, e, mode=SEND_MODE_INCREMENT, step="Step3")

            ret_basic, _ = check_routing(e, expect_count=10)

            ret_type, type_details = check_routing(e, expect_count=10, mode=CHECK_MODE_FRAMETYPE)
            actual_type = type_details[0].get('actual_frametype', 'Unknown') if type_details else 'Unknown'

            ret_dlc, dlc_details = check_routing(e, expect_count=10, mode=CHECK_MODE_DLC)
            actual_dlc = dlc_details[0].get('actual_dlc', -1) if dlc_details else -1

            ret_data, _ = check_routing(e, expect_count=10, mode=CHECK_MODE_DATA, compare_from_byte=0)

            delay_pass, delay_results = analyze_routing_delay(dest_id, max_delay_ms)
            max_actual_delay = max([r['delay_ms'] for r in delay_results]) if delay_results else 0

            ret = (ret_basic == 0 and ret_type == 0 and ret_dlc == 0 and
                        ret_data == 0 and delay_pass)

            if ret:
                TestLog("PASS", "Step4",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"高负载下路由正常: 帧类型={actual_type} DLC={actual_dlc} "
                        f"最大延迟={max_actual_delay:.2f}ms")
            else:
                fail_reasons = [msg for cond, msg in [
                    (ret_basic != 0, "未收到目标报文"),
                    (ret_type != 0, f"帧类型不匹配(实际={actual_type})"),
                    (ret_dlc != 0, f"DLC不匹配(实际={actual_dlc})"),
                    (ret_data != 0, "数据内容不匹配"),
                    (not delay_pass, f"延迟超限(实际={max_actual_delay:.2f}ms,限值={max_delay_ms}ms)"),
                ] if cond]
                fail_desc = ", ".join(fail_reasons) or "未知错误"
                TestLog("FAIL", "Step4",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"高负载下路由异常: {fail_desc}")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")



def test_TG2_TC8_Routing_DLC_LessThanExpected_Event():
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

        dlc_less_than_expected = 0

        entries = list(cfg.iter_entries_by_type("EventMsg"))
        if not entries:
            TestLog("WARNING", "",
                    "未找到 RoutingType 为 EventMsg 的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            src_dlc = int(e.get('SrcMsgDLC', 8) or 8)

            # 若DLC=1，则跳过此条报文
            if src_dlc <= 1:
                TestLog("INFO", "",
                        f"跳过 源ID=0x{src_id:x} DLC={src_dlc} (DLC太小无法减1)")
                continue

            # 使用DLC-1发送
            custom_dlc = src_dlc - 1

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})

            sender.send_with_custom_dlc(idx, e, custom_dlc=custom_dlc, step="Step2")

            ret, _ = check_routing(e, expect_count=10)
            received = (ret == 0)

            if dlc_less_than_expected == 0:
                # 期望不转发
                if not received:
                    TestLog("PASS", "Step3",
                            f"源网段={src_net} 目标网段={dest_net} "
                            f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                            f"DLC={custom_dlc}(<{src_dlc}) 未转发，符合预期")
                else:
                    TestLog("FAIL", "Step3",
                            f"源网段={src_net} 目标网段={dest_net} "
                            f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                            f"DLC={custom_dlc}(<{src_dlc}) 被转发，不符合预期")
            else:
                # 期望转发
                if received:
                    TestLog("PASS", "Step3",
                            f"源网段={src_net} 目标网段={dest_net} "
                            f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                            f"DLC={custom_dlc}(<{src_dlc}) 已转发，符合预期")
                else:
                    TestLog("FAIL", "Step3",
                            f"源网段={src_net} 目标网段={dest_net} "
                            f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                            f"DLC={custom_dlc}(<{src_dlc}) 未转发，不符合预期")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG2_TC9_Routing_DLC_LargerThanExpected_Event():
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

        dlc_larger_than_expected = 0

        entries = list(cfg.iter_entries_by_type("EventMsg"))
        if not entries:
            TestLog("WARNING", "",
                    "未找到 RoutingType 为 EventMsg 的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            src_dlc = int(e.get('SrcMsgDLC', 8) or 8)
            src_frame_type = str(e.get('SrcMsgFrameType', 'CAN') or 'CAN').upper()

            is_canfd = 'FD' in src_frame_type
            max_dlc = 15 if is_canfd else 8

            if src_dlc >= max_dlc:
                TestLog("INFO", "",
                        f"跳过 源ID=0x{src_id:x} DLC={src_dlc} "
                        f"(已达{'CANFD' if is_canfd else 'CAN'}最大DLC={max_dlc})")
                continue

            custom_dlc = src_dlc + 1

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})

            sender.send_with_custom_dlc(idx, e, custom_dlc=custom_dlc, step="Step2")

            ret, _ = check_routing(e, expect_count=10)
            received = (ret == 0)

            if dlc_larger_than_expected == 1:
                if received:
                    TestLog("PASS", "Step3",
                            f"源网段={src_net} 目标网段={dest_net} "
                            f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                            f"DLC={custom_dlc}(>{src_dlc}) 已转发，符合预期")
                else:
                    TestLog("FAIL", "Step3",
                            f"源网段={src_net} 目标网段={dest_net} "
                            f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                            f"DLC={custom_dlc}(>{src_dlc}) 未转发，不符合预期")
            else:
                if not received:
                    TestLog("PASS", "Step3",
                            f"源网段={src_net} 目标网段={dest_net} "
                            f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                            f"DLC={custom_dlc}(>{src_dlc}) 未转发，符合预期")
                else:
                    TestLog("FAIL", "Step3",
                            f"源网段={src_net} 目标网段={dest_net} "
                            f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                            f"DLC={custom_dlc}(>{src_dlc}) 被转发，不符合预期")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")
