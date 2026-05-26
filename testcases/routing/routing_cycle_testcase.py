import time
import traceback
from common.wakeup import WakeupStop, WakeupStart
from uvtest.testlog import TestLog
from uvtest.framework import TestFixture
from common.control import TestStart, TestEnd
from common.context import ctx
from .routing_module import (
    routing_initialization, routing_deinitialization,
    get_routing_config, get_routing_sender,
    can_power_setup_and_communication_check,
    check_routing, analyze_dest_cycle, analyze_routing_delay,
    CHECK_MODE_DLC, CHECK_MODE_FRAMETYPE, CHECK_MODE_DATA,
    SEND_MODE_INCREMENT,
)


class RoutingCycleTestFixture(TestFixture):
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


def test_TG1_TC1_Routing_DestNetwork_Check_Cycle():
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
        ctx.can.set_info('routing_dest_records', [])

        entries = cfg.iter_entries_by_type("CycleMsg")
        found = False
        for idx, e in entries:
            found = True
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')

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
                TestLog("FAIL", "Step3",
                        f"期望结果：{expected}  "
                        f"实际结果：目标网段未接收到目标报文"
                        f"(源网段={src_net}, 源ID=0x{src_id:x})")

        if not found:
            TestLog("WARNING", "",
                    "未找到 RoutingType 为 CycleMsg 的路由表项")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG1_TC2_Routing_FrameType_Check_Cycle():
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
        ctx.can.set_info('routing_dest_records', [])

        entries = cfg.iter_entries_by_type("CycleMsg")
        found = False
        for idx, e in entries:
            found = True
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            expected_type = e.get('DestMsgFrameType', 'CAN')

            ctx.can.set_info('sRxMsgInfoList', {})  
            sender.send(idx, e, mode=SEND_MODE_INCREMENT, step="Step2")

            ret, details_list = check_routing(e, expect_count=10, mode=CHECK_MODE_FRAMETYPE)
            details = details_list[0] if details_list else {}
            actual_type = details.get('actual_frametype', 'Unknown')

            if ret == 0:
                TestLog("PASS", "Step3",
                        f"期望结果：报文类型={expected_type}"
                        f"实际结果：报文类型={actual_type}"
                        f"(源网={e.get('SrcNet')}, 目标网={e.get('DestNet')}, 源ID=0x{src_id:x}, 目标ID=0x{dest_id:x})")
            else:
                TestLog("FAIL", "Step3",
                        f"期望结果：报文类型={expected_type}"
                        f"实际结果：报文类型={actual_type}"
                        f"(源网={e.get('SrcNet')}, 目标网={e.get('DestNet')}, 源ID=0x{src_id:x}, 目标ID=0x{dest_id:x})")

        if not found:
            TestLog("WARNING", "",
                    "未找到 RoutingType 为 CycleMsg 的路由表项")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG1_TC3_Routing_ID_Check_Cycle():
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
        ctx.can.set_info('routing_dest_records', [])

        entries = cfg.iter_entries_by_type("CycleMsg")
        found = False
        for idx, e in entries:
            found = True
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)

            ctx.can.set_info('sRxMsgInfoList', {}) 
            sender.send(idx, e, mode=SEND_MODE_INCREMENT, step="Step2")

            ret, _ = check_routing(e, expect_count=10)
            if ret == 0:
                TestLog("PASS", "Step3",
                        f"源网={e.get('SrcNet')} 目标网={e.get('DestNet')} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"目标网段接收的报文ID与路由表定义一致")
            else:
                TestLog("FAIL", "Step3",
                        f"源网={e.get('SrcNet')} 目标网={e.get('DestNet')} "
                        f"源ID=0x{src_id:x} 期望目标ID=0x{dest_id:x} "
                        f"目标网段未接收到正确ID的报文")

        if not found:
            TestLog("WARNING", "",
                    "未找到 RoutingType 为 CycleMsg 的路由表项")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG1_TC4_Routing_DLC_Check_Cycle():
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
        ctx.can.set_info('routing_dest_records', [])

        entries = cfg.iter_entries_by_type("CycleMsg")
        found = False
        for idx, e in entries:
            found = True
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            expected_dlc = int(e.get('DestMsgDLC', 8) or 8)

            ctx.can.set_info('sRxMsgInfoList', {})  
            sender.send(idx, e, mode=SEND_MODE_INCREMENT, step="Step2")

            ret, details_list = check_routing(e, expect_count=10, mode=CHECK_MODE_DLC)
            details = details_list[0] if details_list else {}
            actual_dlc = details.get('actual_dlc', -1)

            if ret == 0:
                TestLog("PASS", "Step3",
                        f"期望结果：DLC={expected_dlc}实际结果：DLC={actual_dlc}"
                        f"(源网={e.get('SrcNet')}, 目标网={e.get('DestNet')}, 源ID=0x{src_id:x}, 目标ID=0x{dest_id:x})")
            else:
                TestLog("FAIL", "Step3",
                        f"期望结果：DLC={expected_dlc}实际结果：DLC={actual_dlc}"
                        f"(源网={e.get('SrcNet')}, 目标网={e.get('DestNet')}, 源ID=0x{src_id:x}, 目标ID=0x{dest_id:x})")

        if not found:
            TestLog("WARNING", "",
                    "未找到 RoutingType 为 CycleMsg 的路由表项")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG1_TC5_Routing_Data_Check_Cycle():
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

        entries = cfg.iter_entries_by_type("CycleMsg")
        found = False
        for idx, e in entries:
            found = True
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})  

            sender.send(idx, e, mode=SEND_MODE_INCREMENT, step="Step2")

            ret, results = check_routing(e, expect_count=10, mode=CHECK_MODE_DATA, compare_from_byte=0)

            match_count = sum(1 for r in results if r.get('match', False)) if results else 0
            total_count = len(results) if results else 0

            if ret == 0:
                TestLog("PASS", "Step3",
                        f"源网={e.get('SrcNet')} 目标网={e.get('DestNet')} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"数据内容一致 (匹配数={match_count}/{total_count})")
            else:
                TestLog("FAIL", "Step3",
                        f"源网={e.get('SrcNet')} 目标网={e.get('DestNet')} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"数据内容不一致 (匹配数={match_count}/{total_count})")

        if not found:
            TestLog("WARNING", "",
                    "未找到 RoutingType 为 CycleMsg 的路由表项")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG1_TC11_Routing_Cycle_Check_Cycle():
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
        ctx.can.set_info('routing_dest_records', [])

        entries = cfg.iter_entries_by_type("CycleMsg")
        found = False
        for idx, e in entries:
            found = True
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            dest_cycle = int(e.get('DestMsgCycleTime', 0) or 0)

            sender.send(idx, e, mode=SEND_MODE_INCREMENT, step="Step2")

            base_ret, _ = check_routing(e, expect_count=10)
            if base_ret != 0:
                TestLog("FAIL", "",
                        f"源网={e.get('SrcNet')} 目标网={e.get('DestNet')} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} 基础检查失败")
                continue

            ret, results = analyze_dest_cycle(dest_id, dest_cycle, tol_ratio=0.10)
            if not results:
                TestLog("WARNING", "",
                        f"目标ID=0x{dest_id:x} 接收次数不足，无法计算周期")
                continue

            expected_range = f"周期在[{dest_cycle*0.9:.1f}ms, {dest_cycle*1.1:.1f}ms]范围内"
            for n, (p_ms, ok, mn, mx) in enumerate(results, start=1):
                if ok:
                    TestLog("PASS", "",
                            f"期望结果:{expected_range}实际结果：第{n}段周期={p_ms:.1f}ms"
                            f"(目标ID=0x{dest_id:x}, 允许范围=[{mn:.1f},{mx:.1f}]ms)")
                else:
                    TestLog("FAIL", "",
                            f"期望结果:{expected_range}实际结果：第{n}段周期={p_ms:.1f}ms"
                            f"(目标ID=0x{dest_id:x}, 超出范围=[{mn:.1f},{mx:.1f}]ms)")

            if ret:
                TestLog("PASS", "",
                        f"期望结果：周期与路由表定义一致实际结果：所有段周期均在允许范围内"
                        f"(源网={e.get('SrcNet')}, 目标网={e.get('DestNet')}, 目标ID=0x{dest_id:x})")

        if not found:
            TestLog("WARNING", "",
                    "未找到 RoutingType 为 CycleMsg 的路由表项")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")



def test_TG1_TC6_Routing_Delay_Check_Cycle():
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

        entries = cfg.iter_entries_by_type("CycleMsg")
        found = False
        for idx, e in entries:
            found = True
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            max_delay_ms = float(e.get('RoutingDelayTime', 10) or 10)

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {}) 

            sender.send(idx, e, mode=SEND_MODE_INCREMENT, step="Step2")

            ret, _ = check_routing(e, expect_count=10)
            if ret != 0:
                TestLog("FAIL", "",
                        f"源网={e.get('SrcNet')} 目标网={e.get('DestNet')} "
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
                        f"期望结果:{expected_delay}实际结果{actual_delay_info}"
                        f"(源网={e.get('SrcNet')}, 目标网={e.get('DestNet')}, 源ID=0x{src_id:x}, 目标ID=0x{dest_id:x})")
            else:
                TestLog("FAIL", "Step3",
                        f"期望结果:{expected_delay}实际结果{actual_delay_info}"
                        f"(源网={e.get('SrcNet')}, 目标网={e.get('DestNet')}, 源ID=0x{src_id:x}, 目标ID=0x{dest_id:x})")

        if not found:
            TestLog("WARNING", "",
                    "未找到 RoutingType 为 CycleMsg 的路由表项")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG1_TC7_Routing_HighLoad_Check_Cycle():
    """
    总线高负载路由测试
    """
    import time
    sender = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        entries = list(cfg.iter_entries_by_type("CycleMsg"))
        if not entries:
            TestLog("WARNING", "",
                    "未找到 RoutingType 为 CycleMsg 的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            max_delay_ms = float(e.get('RoutingDelayTime', 10) or 10)

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})  

            sender.send_high_load(idx, e, load_percent=80)
            TestLog("INFO", "", "在目标网段模拟高负载，等待10s")
            time.sleep(10)

            sender.send(idx, e, mode=SEND_MODE_INCREMENT, step="Step2")

            ret_basic, _ = check_routing(e, expect_count=10)

            ret_type, type_details = check_routing(e, expect_count=10, mode=CHECK_MODE_FRAMETYPE)
            actual_type = type_details[0].get('actual_frametype', 'Unknown') if type_details else 'Unknown'

            ret_dlc, dlc_details = check_routing(e, expect_count=10, mode=CHECK_MODE_DLC)
            actual_dlc = dlc_details[0].get('actual_dlc', -1) if dlc_details else -1

            ret_data, data_results = check_routing(e, expect_count=10, mode=CHECK_MODE_DATA, compare_from_byte=0)

            delay_pass, delay_results = analyze_routing_delay(dest_id, max_delay_ms)
            max_actual_delay = max([r['delay_ms'] for r in delay_results]) if delay_results else 0

            ret = (ret_basic == 0 and ret_type == 0 and ret_dlc == 0 and
                        ret_data == 0 and delay_pass)

            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            max_delay_ms = float(e.get('TransmitDelayTime', 10) or 10)
            if ret:
                TestLog("PASS", "Step3",
                        f"源网={src_net} 目标网={dest_net} "
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
                TestLog("FAIL", "Step3",
                        f"源网={src_net} 目标网={dest_net} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"高负载下路由异常: {fail_desc}")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")



def test_TG1_TC8_Routing_InvalidID_Check_Cycle():
    """
    无效报文ID测试
    """
    import time
    sender = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        entries = list(cfg.iter_entries_by_type("CycleMsg"))
        if not entries:
            TestLog("WARNING", "",
                    "未找到 RoutingType 为 CycleMsg 的路由表项")
            return

        src_nets = set()
        for _, e in entries:
            src_nets.add(e.get('SrcNet', ''))

        invalid_id = 0x7FF
        ret = True

        for src_net in src_nets:
            entry_for_net = None
            for _, e in entries:
                if e.get('SrcNet') == src_net:
                    entry_for_net = e
                    break

            if entry_for_net is None:
                continue

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})  

            sender.send_invalid_id(entry_for_net, invalid_id, duration_ms=3000)

            time.sleep(0.5)

            dest_records = ctx.can.get_info('routing_dest_records') or []
            forwarded_count = sum(1 for r in dest_records
                                  if int(r.get('MsgId', -1)) == invalid_id)

            if forwarded_count == 0:
                TestLog("PASS", "",
                        f"源网段={src_net} 无效ID=0x{invalid_id:x} "
                        f"未被转发到其他网段 (符合预期)")
            else:
                TestLog("FAIL", "",
                        f"源网段={src_net} 无效ID=0x{invalid_id:x} "
                        f"被错误地转发了 {forwarded_count} 次")
                ret = False

        if ret:
            TestLog("PASS", "", "所有网段测试通过，DUT不转发无效ID报文")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG1_TC9_Routing_DLCLessThan_Check_Cycle():
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

        entries = list(cfg.iter_entries_by_type("CycleMsg"))
        if not entries:
            TestLog("WARNING", "",
                    "未找到 RoutingType 为 CycleMsg 的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            expected_dlc = int(e.get('SrcMsgDLC', 8) or 8)

            if expected_dlc <= 1:
                TestLog("INFO", "",
                        f"源ID=0x{src_id:x} DLC=1，跳过此条目")
                continue

            reduced_dlc = expected_dlc - 1

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})  

            sender.send_with_custom_dlc(idx, e, custom_dlc=reduced_dlc)

            dest_records = ctx.can.get_info('routing_dest_records') or []
            received_count = sum(1 for r in dest_records
                                 if int(r.get('MsgId', -1)) == dest_id)

            if received_count == 0:
                TestLog("PASS", "",
                        f"源网={e.get('SrcNet')} 目标网={e.get('DestNet')} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"发送DLC={reduced_dlc} 预期DLC={expected_dlc} "
                        f"DUT正确丢弃DLC小于预期的报文")
            else:
                TestLog("FAIL", "",
                        f"源网={e.get('SrcNet')} 目标网={e.get('DestNet')} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"发送DLC={reduced_dlc} 预期DLC={expected_dlc} "
                        f"DUT错误地转发了DLC小于预期的报文 (收到{received_count}帧)")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")



def test_TG1_TC10_Routing_DLCGreaterThan_Check_Cycle():
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

        entries = list(cfg.iter_entries_by_type("CycleMsg"))
        if not entries:
            TestLog("WARNING", "",
                    "未找到 RoutingType 为 CycleMsg 的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            expected_dlc = int(e.get('SrcMsgDLC', 8) or 8)
            is_canfd = e.get('SrcMsgFrameType') == 'CANFD'

            if is_canfd and expected_dlc >= 15:
                TestLog("INFO", "",
                        f"源ID=0x{src_id:x} CANFD DLC=15，跳过此条目")
                continue
            if not is_canfd and expected_dlc >= 8:
                TestLog("INFO", "",
                        f"源ID=0x{src_id:x} CAN DLC=8，跳过此条目")
                continue

            increased_dlc = expected_dlc + 1

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})  

            sender.send_with_custom_dlc(idx, e, custom_dlc=increased_dlc)

            dest_records = ctx.can.get_info('routing_dest_records') or []
            received_msgs = [r for r in dest_records
                             if int(r.get('MsgId', -1)) == dest_id]
            received_count = len(received_msgs)

            if received_count == 0:
                TestLog("PASS", "",
                        f"源网={e.get('SrcNet')} 目标网={e.get('DestNet')} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"发送DLC={increased_dlc} 预期DLC={expected_dlc} "
                        f"DUT正确丢弃DLC大于预期的报文")
            else:
                actual_dlc = received_msgs[0].get('dlc', -1) if received_msgs else -1
                TestLog("FAIL", "",
                        f"源网={e.get('SrcNet')} 目标网={e.get('DestNet')} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"发送DLC={increased_dlc} 预期DLC={expected_dlc} "
                        f"接收DLC={actual_dlc} DUT错误地转发了DLC大于预期的报文")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG1_TC12_Routing_NetworkWakeup_Check_Cycle():
    """
    网络唤醒测试
    """
    import time
    sender = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        TestLog("INFO", "", "等待DUT进入睡眠模式...")
        WakeupStop()

        TestLog("INFO", "", "发送唤醒信号...")
        WakeupStart()

        ctx.can.set_info('routing_src_records', [])
        ctx.can.set_info('routing_dest_records', [])
        ctx.can.set_info('sRxMsgInfoList', {})  

        TestLog("INFO", "", "等待3s记录所有网段报文...")
        time.sleep(3)

        entries = list(cfg.iter_entries_by_type("CycleMsg"))
        if not entries:
            TestLog("WARNING", "",
                    "未找到 RoutingType 为 CycleMsg 的路由表项")
            return

        ret = True
        for idx, e in entries:
            trigger_mode = e.get('TriggerMode', '')
            if trigger_mode != 'Trigger always':
                continue

            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')

            dest_records = ctx.can.get_info('routing_dest_records') or []
            received_count = sum(1 for r in dest_records
                                 if int(r.get('MsgId', -1)) == dest_id)

            if received_count > 0:
                TestLog("PASS", "",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"唤醒后正确发送报文 (收到{received_count}帧)")
            else:
                TestLog("FAIL", "",
                        f"源网段={src_net} 目标网段={dest_net} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x} "
                        f"唤醒后未接收到目标报文")
                ret = False

        if ret:
            TestLog("PASS", "", "所有Trigger always报文唤醒后正确发送")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG1_TC13_Routing_TimeoutState_Check_Cycle():
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

        entries = list(cfg.iter_entries_by_type("CycleMsg"))
        if not entries:
            TestLog("WARNING", "",
                    "未找到 RoutingType 为 CycleMsg 的路由表项")
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
                    f"根据路由表定义，选取其中一条周期路由报文，记录 DUT 发送第一帧报文的时间 t1 "
                    f"[源网段={src_net}, 目标网段={dest_net}, 源ID=0x{src_id:x}, 目标ID=0x{dest_id:x}]")

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
                    f"利用 CANoe 检测此报文中的信号更新的时间 t2，计算超时时间 t2-t1 "
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
                    f"根据路由表定义，选取其中一条周期路由报文，在源网段仿真发送源报文，"
                    f"报文ID为源报文ID，周期为源报文周期，DLC为源报文DLC，数据内容从0x01依次增加，"
                    f"持续发送10倍目标报文周期时间 "
                    f"[源网段={src_net}, 目标网段={dest_net}, 源ID=0x{src_id:x}, 目标ID=0x{dest_id:x}]")

            sender.send(idx, e, mode=SEND_MODE_INCREMENT, duration_ms=duration_ms, step="")

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
                    f"利用 CANoe 检测此报文中的信号更新成超时值的时间 t2，计算超时时间 t2-t1 "
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
