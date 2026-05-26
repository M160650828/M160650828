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
    check_routing, net_to_channel,
    SEND_MODE_INCREMENT,
    get_all_networks, send_error_frames, stop_error_frames,
    set_busoff_fault, send_extended_frame_increment,
    check_frame_received, send_remote_frame,
)


class RoutingFaultTestFixture(TestFixture):
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


def test_TG4_TC1_Routing_ErrorFrame_Check():
    """
    错误帧测试
    """
    sender = None
    error_timer_id = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        networks = get_all_networks(cfg)
        if len(networks) < 2:
            TestLog("WARNING", "", "网段数量少于2，无法执行测试")
            return

        ret = True

        # TODO: 目前硬件/底层不支持发送错误帧，暂时跳过此测试
        TestLog("WARNING", "",
                "TODO: 目前接口卡不支持发送错误帧，测试跳过")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if error_timer_id:
            stop_error_frames(error_timer_id)
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")



def test_TG4_TC2_Routing_BusOFF_Check():
    """
    BusOFF故障测试
    """
    sender = None
    fault_channel = None
    fault_net = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        networks = get_all_networks(cfg)
        if len(networks) < 3:
            TestLog("WARNING", "", "网段数量少于3，无法执行完整测试")
            if len(networks) < 2:
                return

        ret = True

        for fault_net in networks:
            fault_channel = net_to_channel(fault_net)
            TestLog("INFO", "Step2", f"制造故障网段: {fault_net} (通道{fault_channel})")

            if not set_busoff_fault(fault_channel, fault_net, enable=True):
                TestLog("FAIL", "Step2", f"无法注入故障到网段{fault_net}")
                ret = False
                continue

            time.sleep(0.5)

            cycle_entries = cfg.iter_entries_by_type("CycleMsg")
            tested_net_pairs = set() 
            route_tested = False

            for idx, e in cycle_entries:
                src_net = e.get('SrcNet', '')
                dest_net = e.get('DestNet', '')

                if src_net == fault_net or dest_net == fault_net:
                    continue

                net_pair = (src_net, dest_net)
                if net_pair in tested_net_pairs:
                    continue
                tested_net_pairs.add(net_pair)

                route_tested = True
                src_id = int(e.get('SrcMsgId', 0))
                dest_id = int(e.get('DestMsgId', 0))
                src_period_ms = int(e.get('SrcMsgCycleTime', 10) or 10)
                dest_period_ms = int(e.get('DestMsgCycleTime', src_period_ms) or src_period_ms)
                duration_ms = dest_period_ms * 10

                ctx.can.set_info('routing_src_records', [])
                ctx.can.set_info('routing_dest_records', [])

                TestLog("INFO", "",
                        f"Step3: 验证路由 源网段={src_net} 目标网段={dest_net} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x}")

                sender.send(idx, e, mode=SEND_MODE_INCREMENT, duration_ms=duration_ms, step="Step3")

                expect_count = max(5, duration_ms // dest_period_ms // 2)
                ret, _ = check_routing(e, expect_count=expect_count)
                expected = f"故障网段={fault_net}时，其他网段路由功能正常"
                if ret == 0:
                    TestLog("PASS", "",
                            f"期望结果：{expected}实际结果路由功能正常 "
                            f"(源网段={src_net}, 目标网段={dest_net}, 源ID=0x{src_id:x})")
                else:
                    TestLog("FAIL", "",
                            f"期望结果：{expected}实际结果路由功能异常 "
                            f"(源网段={src_net}, 目标网段={dest_net}, 源ID=0x{src_id:x})")
                    ret = False

            if not route_tested:
                TestLog("WARNING", "",
                        f"没有找到不涉及故障网段{fault_net}的CycleMsg路由条目")

            TestLog("INFO", "Step5", f"移除故障网段{fault_net}的故障")
            set_busoff_fault(fault_channel, fault_net, enable=False)
            time.sleep(1)

            recovery_entry = None
            recovery_idx = None
            for idx, e in cfg.iter_entries_by_type("CycleMsg"):
                if e.get('SrcNet', '') == fault_net:
                    recovery_entry = e
                    recovery_idx = idx
                    break

            if recovery_entry:
                src_id = int(recovery_entry.get('SrcMsgId', 0))
                dest_id = int(recovery_entry.get('DestMsgId', 0))
                dest_net = recovery_entry.get('DestNet', '')
                src_period_ms = int(recovery_entry.get('SrcMsgCycleTime', 10) or 10)
                dest_period_ms = int(recovery_entry.get('DestMsgCycleTime', src_period_ms) or src_period_ms)
                duration_ms = dest_period_ms * 10

                ctx.can.set_info('routing_src_records', [])
                ctx.can.set_info('routing_dest_records', [])

                TestLog("INFO", "",
                        f"验证故障恢复: 源网段={fault_net} 目标网段={dest_net} "
                        f"源ID=0x{src_id:x} 目标ID=0x{dest_id:x}")
                sender.send(recovery_idx, recovery_entry, mode=SEND_MODE_INCREMENT, duration_ms=duration_ms)

                expect_count = max(5, duration_ms // dest_period_ms // 2)
                ret, _ = check_routing(recovery_entry, expect_count=expect_count)
                expected = f"故障网段{fault_net}恢复后路由功能正常"
                if ret == 0:
                    TestLog("PASS", "",
                            f"期望结果：{expected}实际结果路由功能正常")
                else:
                    TestLog("FAIL", "",
                            f"期望结果：{expected}实际结果路由功能异常")
                    ret = False
            else:
                TestLog("WARNING", "",
                        f"没有找到以{fault_net}为源网段的CycleMsg路由，跳过恢复验证")

            fault_channel = None

        if ret:
            TestLog("PASS", "", "所有网段测试通过，BusOFF故障不影响其他网段路由功能")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if fault_channel is not None and fault_net is not None:
            set_busoff_fault(fault_channel, fault_net, enable=False)
        if sender is not None:
            sender.routing_cleanup()
        TestEnd("")


def test_TG4_TC3_Routing_ExtendedFrame_Check():
    """
    扩展帧路由行为测试
    """
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        cfg = get_routing_config()

        networks = get_all_networks(cfg)
        if len(networks) < 2:
            TestLog("WARNING", "", "网段数量少于2，无法执行测试")
            TestEnd("")
            return

        ret = True
        tested_count = 0

        for test_net in networks:
            test_channel = net_to_channel(test_net)
            other_networks = [n for n in networks if n != test_net]

            TestLog("INFO", "", f"测试网段: {test_net} (通道{test_channel})")

            entries = list(cfg.iter_entries_by_type("EventMsg"))
            route_entry = None
            for _, e in entries:
                if e.get('SrcNet', '') == test_net:
                    route_entry = e
                    break

            if not route_entry:
                TestLog("INFO", "", f"网段{test_net}没有作为源网段的EventMsg路由")
                continue

            src_id = route_entry.get('SrcMsgId', 0)
            dlc = int(route_entry.get('SrcMsgDLC', 8))
            period_ms = int(route_entry.get('SrcMsgCycleTime', 10) or 10)
            dest_period_ms = int(route_entry.get('DestMsgCycleTime', period_ms) or period_ms)
            duration_ms = dest_period_ms * 10
            fdf = 1 if route_entry.get('SrcMsgFrameType') == 'CANFD' else 0
            brs = 1 if fdf else 0
            tested_count += 1

            TestLog("INFO", "Step2",
                    "根据路由表定义，选取其中一个网段，在该网段选择一条周期路由报文，"
                    "在源网段仿真发送源报文，报文IDE位设置为1，报文ID为源报文ID")

            ctx.can.messages.clear() if hasattr(ctx.can.messages, 'clear') else None
            send_extended_frame_increment(test_channel, src_id, dlc, period_ms, duration_ms, fdf, brs)

            ext_found_in_other = False
            for other_net in other_networks:
                other_ch = net_to_channel(other_net)
                if check_frame_received(other_ch, 'extended'):
                    TestLog("FAIL", "Step3",
                            f"检测其他网段是否接收到扩展帧 期望结果: 目标网段未接收到扩展帧，实际结果: 源网段（{test_net}）"
                            f"发送周期报文（0x{src_id:x}），其他网段（{other_net}）接收到扩展帧")
                    ext_found_in_other = True
                    ret = False

            if not ext_found_in_other:
                TestLog("PASS", "Step3",
                        f"检测其他网段是否接收到扩展帧 期望结果: 目标网段未接收到扩展帧，实际结果: 源网段（{test_net}）"
                        f"发送周期报文（0x{src_id:x}），其他网段未接收到扩展帧")

        if tested_count == 0:
            TestLog("INFO", "", "未找到EventMsg路由条目，跳过测试")
        elif ret:
            TestLog("PASS", "", "所有网段测试通过，DUT不转发扩展帧")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        TestEnd("")


def test_TG4_TC4_Routing_RemoteFrame_Check():
    """
    远程帧路由行为测试
    """
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            TestEnd("")
            return

        cfg = get_routing_config()

        networks = get_all_networks(cfg)
        if len(networks) < 2:
            TestLog("WARNING", "", "网段数量少于2，无法执行测试")
            TestEnd("")
            return

        ret = True
        tested_count = 0

        for test_net in networks:
            test_channel = net_to_channel(test_net)
            other_networks = [n for n in networks if n != test_net]

            TestLog("INFO", "", f"测试网段: {test_net} (通道{test_channel})")

            route_entry = None
            for e in cfg.routing_table():
                if e.get('SrcNet', '') == test_net and e.get('SrcMsgFrameType') == 'CAN':
                    route_entry = e
                    break

            if not route_entry:
                TestLog("INFO", "",
                        f"网段{test_net}没有作为源网段的CAN路由（CANFD不支持远程帧）")
                continue

            src_id = route_entry.get('SrcMsgId', 0)
            tested_count += 1

            TestLog("INFO", "Step2",
                    "根据路由表定义，选取其中一个网段，在该网段选择一条周期路由报文，"
                    "在源网段仿真发送源报文，报文RTR位设置为1，报文ID为源报文ID")

            ctx.can.messages.clear() if hasattr(ctx.can.messages, 'clear') else None

            if not send_remote_frame(test_channel, src_id):
                TestLog("FAIL", "", f"发送远程帧失败")
                ret = False
                continue

            time.sleep(0.5)

            remote_found_in_other = False
            for other_net in other_networks:
                other_ch = net_to_channel(other_net)
                if check_frame_received(other_ch, 'remote'):
                    TestLog("FAIL", "Step3",
                            f"检测其他网段是否接收到远程帧 期望结果: 目标网段未接收到远程帧，实际结果: 源网段（{test_net}）"
                            f"发送周期报文（0x{src_id:x}），其他网段（{other_net}）接收到远程帧")
                    remote_found_in_other = True
                    ret = False

            if not remote_found_in_other:
                TestLog("PASS", "Step3",
                        f"检测其他网段是否接收到远程帧 期望结果: 目标网段未接收到远程帧，实际结果: 源网段（{test_net}）"
                        f"发送周期报文（0x{src_id:x}），其他网段未接收到远程帧")

        if tested_count == 0:
            TestLog("INFO", "", "未找到CAN类型的路由条目（CANFD不支持远程帧），跳过测试")
        elif ret:
            TestLog("PASS", "", "所有网段测试通过，DUT不转发远程帧")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        TestEnd("")
