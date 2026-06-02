import time
import traceback

from uvtest.testlog import TestLog
from uvtest.framework import TestFixture
from common.control import TestStart, TestEnd
from common.context import ctx
from common.wakeup import WakeupStart, WakeupStop
from common.params import P
from common.can_utils import canmsg_create, send_canmsg
from common.utils import TimerCyclic
from env.config import DEFAULT_CAN_CHANNELS
from slplus.time import sl_time
from .routing_module import (
    routing_initialization, routing_deinitialization,
    get_routing_config, get_routing_sender,
    can_power_setup_and_communication_check, check_can_communication_state,
    check_routing, net_to_channel, get_all_networks,
    CHECK_MODE_BASIC, SEND_MODE_INCREMENT,
)
from .routing_nm_utils import (
    wakeup_active_start, wakeup_active_stop,
    wakeup_passive_start, wakeup_passive_stop, wakeup_passive_stop_all,
    get_net_wakeup_config,
    wait_nm_message, wait_nm_message_stop,
    wait_dut_enter_sleep, get_nm_message_list,
    check_all_networks_nm_messages,
    build_rx_ecuCanChl_msg,
    get_nm_params, send_and_check_routing_all_entries, check_routing_stopped,
    send_nm_msg_on_channel, send_app_msg_on_channel,
    clear_routing_records, dut_power_on_and_wait_stable, prepare_dut_sleep,
    send_and_check_signal_routing_all_entries,
    iter_valid_nm_networks_with_routing,
)


class RoutingNMTestFixture(TestFixture):
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

def test_TG5_TC1_Gateway_Wakeup_Condition():
    sender = None
    cfg = None
    try:
        cfg = get_routing_config()
        v, tstable_s, _ = cfg.can_params()
        nm_params = get_nm_params()

        TestLog("INFO", "SubCase1", "KL15唤醒+报文路由测试")

        TestLog("INFO", "Step1", "DUT处于断电或者睡眠状态")
        ctx.power_ctrl.off()
        time.sleep(1)

        TestLog("INFO", "Step2", "KL15 ON，将网关唤醒，等待1s至总线通信稳定")
        dut_power_on_and_wait_stable(v, tstable_s, kl15_on=True, step_name="Step2")

        sender = get_routing_sender()
        TestLog("INFO", "Step3", "根据路由表定义，仿真基于报文路由的报文发送给DUT对应的源网段接口")

        TestLog("INFO", "Step4", "监测目标网段报文是否被路由")
        cycle_pass = send_and_check_routing_all_entries("CycleMsg", sender, cfg, "Step4")
        event_pass = send_and_check_routing_all_entries("EventMsg", sender, cfg, "Step4")
        msg_routing_pass = cycle_pass and event_pass

        if msg_routing_pass:
            TestLog("PASS", "SubCase1", "KL15 ON可唤醒网关，网关能够按照路由表的定义将报文路由到所有目标网段")
        else:
            TestLog("FAIL", "SubCase1", "KL15唤醒后报文路由功能异常")

        TestLog("INFO", "SubCase2", "KL15唤醒+信号路由测试")

        TestLog("INFO", "Step1", "DUT处于断电或者睡眠状态")
        ctx.power_ctrl.off()
        ctx.bob_ctrl.set_power('KL15', False)
        time.sleep(2)

        TestLog("INFO", "Step2", "KL15 ON，将网关唤醒，等待1s至总线通信稳定")
        dut_power_on_and_wait_stable(v, tstable_s, kl15_on=True, step_name="Step2")

        TestLog("INFO", "Step3", "根据路由表定义，仿真基于信号路由的报文发送给DUT对应的源网段接口")

        TestLog("INFO", "Step4", "监测目标网段报文是否被路由")
        signal_routing_pass = send_and_check_signal_routing_all_entries(sender, cfg, "Step4")

        if signal_routing_pass:
            TestLog("PASS", "SubCase2", "KL15 ON可唤醒网关，网关能够按照路由表的定义将信号路由到所有目标网段")
        else:
            TestLog("FAIL", "SubCase2", "KL15唤醒后信号路由功能异常")

        TestLog("INFO", "SubCase3", "NM报文唤醒+报文路由测试")

        channel_entries = P.ChannelMapping.normalized_entries
        from .routing_module import check_routing, SEND_MODE_INCREMENT
        msg_routing_entries = [e for _, e in cfg.iter_entries_by_type("CycleMsg")]
        msg_routing_entries += [e for _, e in cfg.iter_entries_by_type("EventMsg")]

        if not msg_routing_entries:
            TestLog("WARNING", "SubCase3", "未找到报文路由类型的路由表项")
        else:
            subcase3_pass = True
            tested_nets = set() 

            for net_name, net_config, route_entry in iter_valid_nm_networks_with_routing(
                    channel_entries, msg_routing_entries, tested_nets):

                src_id = route_entry.get('SrcMsgId', 0)
                dest_id = route_entry.get('DestMsgId', 0)
                dest_net = route_entry.get('DestNet', '')

                TestLog("INFO", "", f"测试网段 {net_name} 的NM报文唤醒+报文路由")

                TestLog("INFO", "Step1", "满足DUT睡眠条件(KL15 OFF)，等待DUT进入睡眠状态(NM报文停发后等待5s)")
                prepare_dut_sleep(timeout_ms=60000, wait_after_stop_s=5.0, step_name="Step1")

                TestLog("INFO", "Step2", f"在网段 {net_name} 发送NM报文(ID=0x{net_config['WakeupMsgId']:X})唤醒DUT")
                wakeup_passive_start(net_name)
                time.sleep(3) 

                ret = check_can_communication_state(wait_time=1)
                if ret == 0:
                    TestLog("PASS", "Step2", f"网段 {net_name} NM报文唤醒成功，检测到DUT通信恢复")

                    TestLog("INFO", "Step3", f"发送报文: 源网段={net_name}, 源ID=0x{src_id:X}, 目标网段={dest_net}, 目标ID=0x{dest_id:X}")

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

                    sender.send(route_idx, route_entry, mode=SEND_MODE_INCREMENT, step="Step3")
                    ret, _ = check_routing(route_entry, expect_count=10)

                    if ret == 0:
                        TestLog("PASS", "", f"网段 {net_name} NM唤醒后报文路由功能正常")
                    else:
                        TestLog("FAIL", "", f"网段 {net_name} NM唤醒后报文路由功能异常")
                        subcase3_pass = False
                else:
                    TestLog("FAIL", "", f"网段 {net_name} NM报文无法唤醒网关")
                    subcase3_pass = False

                wakeup_passive_stop(net_name)
                time.sleep(1)

            if subcase3_pass:
                TestLog("PASS", "SubCase3", "所有网段NM报文均可唤醒网关，报文路由功能正常")
            else:
                TestLog("FAIL", "SubCase3", "部分网段NM报文唤醒或报文路由功能异常")

        TestLog("INFO", "SubCase4", "NM报文唤醒+信号路由测试")

        from .routing_module import check_routing, SEND_MODE_SIGNAL
        signal_entries = list(cfg.iter_signal_entries())

        if not signal_entries:
            TestLog("WARNING", "SubCase4", "未找到信号路由类型的路由表项，跳过此子用例")
        else:
            subcase4_pass = True
            tested_nets = set()  

            for idx, e in signal_entries:
                src_net = e.get('SrcNet', '')

                if src_net in tested_nets:
                    continue

                net_config = get_net_wakeup_config(src_net)
                if net_config is None or net_config.get('NMMsgID', 0) == 0:
                    TestLog("WARNING", "", f"网段 {src_net} 不支持NM，跳过")
                    tested_nets.add(src_net)
                    continue

                tested_nets.add(src_net)

                src_id = e.get('SrcMsgId', 0)
                dest_id = e.get('DestMsgId', 0)
                dest_net = e.get('DestNet', '')

                TestLog("INFO", "", f"测试网段 {src_net} 的NM报文唤醒+信号路由")

                TestLog("INFO", "Step1", "满足DUT睡眠条件(KL15 OFF)，等待DUT进入睡眠状态(NM报文停发后等待5s)")
                prepare_dut_sleep(timeout_ms=60000, wait_after_stop_s=5.0, step_name="Step1")

                wakeup_msg_id = net_config.get('WakeupMsgId', net_config.get('NMMsgID', 0))
                TestLog("INFO", "Step2", f"在网段 {src_net} 发送NM报文(ID=0x{wakeup_msg_id:X})唤醒DUT")
                wakeup_passive_start(src_net)
                time.sleep(3)

                ret = check_can_communication_state(wait_time=1)
                if ret == 0:
                    TestLog("PASS", "Step2", f"网段 {src_net} NM报文唤醒成功，检测到DUT通信恢复")
                    TestLog("INFO", "Step3", f"发送信号报文: 源网段={src_net}, 源ID=0x{src_id:X}, 目标网段={dest_net}, 目标ID=0x{dest_id:X}")

                    clear_routing_records()

                    duration_ms = cfg.get_duration_ms(e)
                    sender.send(idx, e, mode=SEND_MODE_SIGNAL, duration_ms=duration_ms, step="Step3")

                    ret, _ = check_routing(e, expect_count=10)
                    if ret == 0:
                        TestLog("PASS", "", f"网段 {src_net} NM唤醒后信号路由功能正常")
                    else:
                        TestLog("FAIL", "", f"网段 {src_net} NM唤醒后信号路由功能异常")
                        subcase4_pass = False
                else:
                    TestLog("FAIL", "", f"网段 {src_net} NM报文无法唤醒网关")
                    subcase4_pass = False

                wakeup_passive_stop(src_net)
                time.sleep(1)

            if subcase4_pass:
                TestLog("PASS", "SubCase4", "所有网段NM报文均可唤醒网关，信号路由功能正常")
            else:
                TestLog("FAIL", "SubCase4", "部分网段NM报文唤醒或信号路由功能异常")

        TestLog("INFO", "SubCase5", "应用报文唤醒测试 - 验证应用报文不能唤醒网关")

        nm_supported_nets = [e['Net'] for e in channel_entries if e.get('NMMsgID_int', 0) != 0]

        if not nm_supported_nets:
            TestLog("WARNING", "SubCase5", "未找到支持NM的网段")
        else:
            subcase5_pass = True
            tested_nets = set()

            for net_name in nm_supported_nets:
                if net_name in tested_nets:
                    continue
                tested_nets.add(net_name)

                net_config = get_net_wakeup_config(net_name)
                if net_config is None:
                    continue

                can_channel = net_config['CANoeCANChannel']
                TestLog("INFO", "", f"测试网段 {net_name} (通道={can_channel}) 的应用报文唤醒")

                TestLog("INFO", "Step1", "满足DUT睡眠条件(KL15 OFF)，等待DUT进入睡眠状态(NM报文停发后等待5s)")
                wakeup_passive_stop_all() 
                prepare_dut_sleep(timeout_ms=60000, wait_after_stop_s=5.0, step_name="Step1")

                ctx.can.messages.clear()

                entries = list(cfg.iter_entries_by_type("CycleMsg"))
                app_msg_id = 0x123 
                for _, e in entries:
                    if e.get('SrcNet', '') == net_name:
                        app_msg_id = e.get('SrcMsgId', 0x123)
                        break

                TestLog("INFO", "Step2", f"在网段 {net_name} 发送应用报文(ID=0x{app_msg_id:X})，监测网关是否被唤醒")
                send_app_msg_on_channel(can_channel, msg_id=app_msg_id, duration_s=3)

                ret = check_can_communication_state(wait_time=1)
                if ret == -1: 
                    TestLog("PASS", "", f"网段 {net_name} 应用报文无法唤醒DUT，符合预期")
                else:
                    TestLog("FAIL", "", f"网段 {net_name} 应用报文错误地唤醒了DUT，不符合预期")
                    subcase5_pass = False

                time.sleep(1)

            if subcase5_pass:
                TestLog("PASS", "SubCase5", "所有网段应用报文均无法唤醒DUT，符合预期")
            else:
                TestLog("FAIL", "SubCase5", "部分网段应用报文错误地唤醒了DUT")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        wakeup_passive_stop_all()  
        WakeupStop()  
        TestEnd("")


def test_TG5_TC2_PostRun_Behavior():
    sender = None
    cfg = None
    try:
        cfg = get_routing_config()
        v, tstable_s, _ = cfg.can_params()
        nm_params = get_nm_params()

        TestLog("INFO", "Step1", "DUT上电，等待1s至总线通信稳定")
        dut_power_on_and_wait_stable(v, tstable_s, kl15_on=True, step_name="Step1")

        TestLog("INFO", "Step2", "将KL15 OFF")
        ctx.bob_ctrl.set_power('KL15', False)

        TestLog("INFO", "Step3", "网关进入Post Run状态")
        time.sleep(0.5)  

        TestLog("INFO", "Step4", "仿真需要路由的报文发送给DUT")
        sender = get_routing_sender()

        TestLog("INFO", "Step5", "检测目标网段是否将报文转发")

        cycle_pass = send_and_check_routing_all_entries("CycleMsg", sender, cfg, "Step5")
        event_pass = send_and_check_routing_all_entries("EventMsg", sender, cfg, "Step5")
        msg_routing_pass = cycle_pass and event_pass

        if msg_routing_pass:
            TestLog("PASS", "", "KL15 OFF后，网关在Post Run状态下路由功能正常")
        else:
            TestLog("FAIL", "", "KL15 OFF后，网关在Post Run状态下路由功能异常")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        WakeupStop()
        TestEnd("")

def test_TG5_TC3_Gateway_Route_Maintenance_AutoSarNM():
    sender = None
    cfg = None
    diag_timer_id = "diag_3e80_timer"
    nm_timer_id = "nm_maintain_timer"

    try:
        cfg = get_routing_config()
        v, tstable_s, _ = cfg.can_params()
        nm_params = get_nm_params()
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        diag_func_id = 0x7DF 
        diag_can_channel = P.ECUInfo.DiagCANChannelNum

        TestLog("INFO", "SubCase1", "NM报文+报文路由测试")

        TestLog("INFO", "Step1", "DUT上电，等待1s至总线通信稳定")
        dut_power_on_and_wait_stable(v, tstable_s, kl15_on=True, step_name="Step1")
        sender = get_routing_sender()

        TestLog("INFO", "Step2", "根据路由表定义，仿真基于报文路由的报文发送给DUT对应的源网段")

        TestLog("INFO", "Step3", "根据通信矩阵定义，CANoe在某一源网段仿真某NM报文")
        nm_msg = canmsg_create(
            nm_params['WakeupMsgID'],
            nm_params['WakeupMsgDLC'],
            data=nm_params['WakeupMsgData'],
            rtr=0, fdf=0, brs=0, ext=0
        )
        TimerCyclic.start(nm_timer_id, nm_params['TnormalCycle_ms'], send_canmsg, can_channel, msg=nm_msg)

        TestLog("INFO", "Step4", "满足DUT本地睡眠条件(KL15 OFF)")
        ctx.bob_ctrl.set_power('KL15', False)

        TestLog("INFO", "Step5", "等待6000ms，查看DUT报文路由(源网段->目标网段)功能是否正常")
        time.sleep(6.0)

        cycle_pass = send_and_check_routing_all_entries("CycleMsg", sender, cfg, "Step5")
        event_pass = send_and_check_routing_all_entries("EventMsg", sender, cfg, "Step5")
        msg_routing_pass = cycle_pass and event_pass

        if msg_routing_pass:
            TestLog("PASS", "SubCase1", "KL15 OFF且处于唤醒状态时，网关报文路由功能正常")
        else:
            TestLog("FAIL", "SubCase1", "KL15 OFF且处于唤醒状态时，网关报文路由功能异常")

        TimerCyclic.stop(nm_timer_id)

        TestLog("INFO", "SubCase2", "NM报文+信号路由测试")

        TestLog("INFO", "Step1", "DUT上电，等待1s至总线通信稳定")
        ctx.bob_ctrl.set_power('KL15', True)
        time.sleep(tstable_s)

        TestLog("INFO", "Step2", "根据路由表定义，仿真基于信号路由的报文发送给DUT对应的源网段")

        TestLog("INFO", "Step3", "根据通信矩阵定义，CANoe在某一源网段仿真发送某NM报文")
        TimerCyclic.start(nm_timer_id, nm_params['TnormalCycle_ms'], send_canmsg, can_channel, msg=nm_msg)

        TestLog("INFO", "Step4", "满足DUT本地睡眠条件(KL15 OFF)")
        ctx.bob_ctrl.set_power('KL15', False)

        TestLog("INFO", "Step5", "等待6000ms，查看DUT在该源网段端口的信号路由功能是否正常")
        time.sleep(6.0)

        signal_routing_pass = send_and_check_signal_routing_all_entries(sender, cfg, "Step5")

        if signal_routing_pass:
            TestLog("PASS", "SubCase2", "KL15 OFF且处于唤醒状态时，网关信号路由功能正常")
        else:
            TestLog("FAIL", "SubCase2", "KL15 OFF且处于唤醒状态时，网关信号路由功能异常")

        TimerCyclic.stop(nm_timer_id)

        TestLog("INFO", "SubCase3", "诊断报文+报文路由测试")

        TestLog("INFO", "Step1", "DUT上电，等待1s至总线通信稳定")
        ctx.bob_ctrl.set_power('KL15', True)
        time.sleep(tstable_s)

        TestLog("INFO", "Step2", "根据路由表定义，仿真基于报文路由的报文发送给DUT对应的源网段")

        TestLog("INFO", "Step3", f"在诊断通道{diag_can_channel}发送诊断报文(功能寻址ID=0x{diag_func_id:X}, 3E 80)，按周期2s发送")
        diag_data = [0x02, 0x3E, 0x80] + [0x00] * 5  # 3E 80: TesterPresent-抑制正响应
        diag_msg = canmsg_create(diag_func_id, 8, data=bytes(diag_data), rtr=0, fdf=0, brs=0, ext=0)
        TimerCyclic.start(diag_timer_id, 2000, send_canmsg, diag_can_channel, msg=diag_msg)

        TestLog("INFO", "Step4", "满足DUT本地睡眠条件(KL15 OFF)")
        ctx.bob_ctrl.set_power('KL15', False)

        TestLog("INFO", "Step5", "等待6000ms，查看DUT在该源网段端口的报文路由功能是否正常")
        time.sleep(6.0)

        cycle_pass = send_and_check_routing_all_entries("CycleMsg", sender, cfg, "Step5")
        event_pass = send_and_check_routing_all_entries("EventMsg", sender, cfg, "Step5")
        msg_routing_pass = cycle_pass and event_pass

        if msg_routing_pass:
            TestLog("PASS", "SubCase3", "KL15 OFF且周期发送诊断报文维持唤醒时，网关报文路由功能正常")
        else:
            TestLog("FAIL", "SubCase3", "KL15 OFF且周期发送诊断报文维持唤醒时，网关报文路由功能异常")

        TimerCyclic.stop(diag_timer_id)

        TestLog("INFO", "SubCase4", "诊断报文+信号路由测试")

        TestLog("INFO", "Step1", "DUT上电，等待1s至总线通信稳定")
        ctx.bob_ctrl.set_power('KL15', True)
        time.sleep(tstable_s)

        TestLog("INFO", "Step2", "根据路由表定义，仿真基于信号路由的报文发送给DUT对应的源网段")

        TestLog("INFO", "Step3", f"在诊断通道{diag_can_channel}发送诊断报文(功能寻址ID=0x{diag_func_id:X}, 3E 80)，按周期2s发送")
        TimerCyclic.start(diag_timer_id, 2000, send_canmsg, diag_can_channel, msg=diag_msg)

        TestLog("INFO", "Step4", "满足DUT本地睡眠条件(KL15 OFF)")
        ctx.bob_ctrl.set_power('KL15', False)

        TestLog("INFO", "Step5", "等待6000ms，查看DUT在该源网段端口的信号路由功能是否正常")
        time.sleep(6.0)

        signal_routing_pass = send_and_check_signal_routing_all_entries(sender, cfg, "Step5")

        if signal_routing_pass:
            TestLog("PASS", "SubCase4", "KL15 OFF且周期发送诊断报文维持唤醒时，网关信号路由功能正常")
        else:
            TestLog("FAIL", "SubCase4", "KL15 OFF且周期发送诊断报文维持唤醒时，网关信号路由功能异常")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        TimerCyclic.stop(nm_timer_id)
        TimerCyclic.stop(diag_timer_id)
        if sender is not None:
            sender.routing_cleanup()
        WakeupStop()
        TestEnd("")


def test_TG5_TC4_Gateway_Route_Shutdown_PostRun():
    sender = None
    cfg = None
    try:
        cfg = get_routing_config()
        v, tstable_s, _ = cfg.can_params()

        postrun_timeout_ms = P.NMInfo.TNMtimeout_ms if hasattr(P.NMInfo, 'TNMtimeout_ms') else 10000
        postrun_timeout_s = postrun_timeout_ms / 1000.0

        TestLog("INFO", "SubCase1", "Post Run模式下路由功能关闭测试")

        TestLog("INFO", "Step1", "DUT上电，等待1s至总线通信稳定")
        dut_power_on_and_wait_stable(v, tstable_s, kl15_on=True, step_name="Step1")

        TestLog("INFO", "Step2", "根据路由表定义，仿真需要路由的报文发送给DUT对应的源网段")
        sender = get_routing_sender()

        cycle_pass = send_and_check_routing_all_entries("CycleMsg", sender, cfg, "Step2")
        event_pass = send_and_check_routing_all_entries("EventMsg", sender, cfg, "Step2")
        msg_routing_pass = cycle_pass and event_pass
        if msg_routing_pass:
            TestLog("PASS", "Step2", "DUT正确接收仿真报文")
        else:
            TestLog("WARNING", "Step2", "DUT可能未正确接收仿真报文")

        TestLog("INFO", "Step3", "KL15 OFF")
        ctx.bob_ctrl.set_power('KL15', False)
        WakeupStop()

        TestLog("INFO", "Step4", "利用CANoe持续仿真报文路由的报文发送给DUT对应的源网段")

        wait_time = postrun_timeout_s + 5.0
        TestLog("INFO", "Step5", f"一段时间后(>{postrun_timeout_s}s)，检测目标网段报文是否消失")
        time.sleep(wait_time)

        routing_stopped = check_routing_stopped(sender, cfg, "Step5")

        if routing_stopped:
            TestLog("PASS", "SubCase1", f"KL15 OFF一段时间后(>{postrun_timeout_s}s)，网关路由功能已正确关闭")
        else:
            TestLog("FAIL", "SubCase1", f"KL15 OFF一段时间后(>{postrun_timeout_s}s)，网关路由功能仍在工作，不符合预期")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        WakeupStop()
        TestEnd("")

def test_TG5_TC5_Gateway_Route_Shutdown_AutoSarNM():
    sender = None
    cfg = None
    try:
        cfg = get_routing_config()
        v, tstable_s, _ = cfg.can_params()
        nm_params = get_nm_params()
        tnm_timeout_ms = nm_params['TNMtimeout_ms']
        tnm_timeout_s = tnm_timeout_ms / 1000.0

        TestLog("INFO", "SubCase1", "报文路由关闭测试")

        TestLog("INFO", "Step1", "DUT上电，等待1s至总线通信稳定")
        dut_power_on_and_wait_stable(v, tstable_s, kl15_on=True, step_name="Step1")

        TestLog("INFO", "Step2", "根据路由表定义，仿真基于报文路由的报文发送给DUT某一源网段")
        sender = get_routing_sender()

        TestLog("INFO", "Step3", "满足DUT本地睡眠条件(KL15 OFF)，等待DUT停止发送NM报文，记录此时刻")
        ctx.bob_ctrl.set_power('KL15', False)
        WakeupStop()

        ret, _ = wait_nm_message_stop(timeout_ms=60000)
        if ret:
            TestLog("INFO", "", "DUT NM报文已停发，记录此时刻")
        else:
            TestLog("WARNING", "", "等待NM报文停发超时")

        TestLog("INFO", "Step4", f"{tnm_timeout_ms}ms(T_NM_TIMEOUT)内，查看DUT报文路由功能是否正常")

        cycle_pass = send_and_check_routing_all_entries("CycleMsg", sender, cfg, "Step4")
        event_pass = send_and_check_routing_all_entries("EventMsg", sender, cfg, "Step4")
        msg_routing_pass = cycle_pass and event_pass

        if msg_routing_pass:
            TestLog("PASS", "Step4", "T_NM_TIMEOUT内，报文路由功能正常")
        else:
            TestLog("WARNING", "Step4", "T_NM_TIMEOUT内，报文路由功能可能已停止")

        TestLog("INFO", "Step5", f"{tnm_timeout_ms}ms后，查看DUT是否停止报文路由功能")
        time.sleep(tnm_timeout_s + 1.0) 

        routing_stopped = check_routing_stopped(sender, cfg, "Step5")

        if routing_stopped:
            TestLog("PASS", "SubCase1", f"KL15 OFF且进入Prepare Bus Sleep Mode后，网关报文路由功能已正确关闭")
        else:
            TestLog("FAIL", "SubCase1", f"KL15 OFF且进入Prepare Bus Sleep Mode后，网关报文路由功能仍在工作")

        TestLog("INFO", "SubCase2", "信号路由关闭测试")

        TestLog("INFO", "Step1", "DUT上电，等待1s至总线通信稳定")
        ctx.bob_ctrl.set_power('KL15', True)
        WakeupStart()
        time.sleep(tstable_s)

        if check_can_communication_state(tstable_s) == 0:
            TestLog("PASS", "Step1", "DUT正常通信")
        else:
            TestLog("WARNING", "Step1", "DUT通信异常")

        TestLog("INFO", "Step2", "满足DUT本地睡眠条件(KL15 OFF)，等待DUT停止发送NM报文，纪录此时刻")
        ctx.bob_ctrl.set_power('KL15', False)
        WakeupStop()

        ret, _ = wait_nm_message_stop(timeout_ms=60000)
        if ret:
            TestLog("INFO", "", "DUT NM报文已停发，记录此时刻")

        TestLog("INFO", "Step3", f"{tnm_timeout_ms}ms(T_NM_TIMEOUT)内，查看DUT某一端口是否正常发送信号路由的报文")
        signal_routing_pass = send_and_check_signal_routing_all_entries(sender, cfg, "Step3")

        if signal_routing_pass:
            TestLog("PASS", "Step3", "T_NM_TIMEOUT内，信号路由功能正常")
        else:
            TestLog("WARNING", "Step3", "T_NM_TIMEOUT内，信号路由功能可能已停止")

        TestLog("INFO", "Step4", f"{tnm_timeout_ms}ms后，查看DUT该端口是否停止信号路由的报文")
        time.sleep(tnm_timeout_s + 1.0)

        routing_stopped = check_routing_stopped(sender, cfg, "Step4")

        if routing_stopped:
            TestLog("PASS", "SubCase2", f"KL15 OFF且进入Prepare Bus Sleep Mode后，网关信号路由功能已正确关闭")
        else:
            TestLog("FAIL", "SubCase2", f"KL15 OFF且进入Prepare Bus Sleep Mode后，网关信号路由功能仍在工作")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        WakeupStop()
        TestEnd("")


def test_TG5_TC6_PostRun_Time():
    sender = None
    cfg = None
    try:
        cfg = get_routing_config()
        v, tstable_s, _ = cfg.can_params()

        TestLog("INFO", "SubCase1", "Post Run时间测试")

        TestLog("INFO", "Step1", "DUT上电，等待1s至总线通信稳定")
        dut_power_on_and_wait_stable(v, tstable_s, kl15_on=True, step_name="Step1")

        TestLog("INFO", "Step2", "根据路由表定义，仿真报文路由的报文发送给DUT对应的源网段接口")
        sender = get_routing_sender()

        cycle_pass = send_and_check_routing_all_entries("CycleMsg", sender, cfg, "Step2")
        event_pass = send_and_check_routing_all_entries("EventMsg", sender, cfg, "Step2")
        msg_routing_pass = cycle_pass and event_pass
        if msg_routing_pass:
            TestLog("PASS", "Step2", "DUT正确接收仿真报文")
        else:
            TestLog("WARNING", "Step2", "DUT可能未正确接收仿真报文")

        TestLog("INFO", "Step3", "KL15 OFF，记录下电时间T1")
        ctx.bob_ctrl.set_power('KL15', False)
        WakeupStop()
        t1 = time.time()
        TestLog("INFO", "", f"记录下电时间T1: {t1:.3f}")

        TestLog("INFO", "Step4", "持续发送仿真报文，直到目标网段报文消失，记录最后一帧被路由报文的时间T2")

        max_wait_time = 120.0
        check_interval = 0.5
        t2 = None
        last_routing_time = t1

        entries = list(cfg.iter_entries_by_type("CycleMsg"))
        if not entries:
            entries = list(cfg.iter_entries_by_type("EventMsg"))

        if entries:
            idx, e = entries[0]
            start_check_time = time.time()

            while time.time() - start_check_time < max_wait_time:
                ctx.can.set_info('routing_dest_records', [])
                sender.send(idx, e, mode=SEND_MODE_INCREMENT, step="Step4")
                ret, _ = check_routing(e, expect_count=1, timeout_s=1.0)

                if ret == 0:
                    last_routing_time = time.time()
                else:
                    t2 = last_routing_time
                    TestLog("INFO", "", f"检测到路由停止，记录最后一帧被路由报文的时间T2: {t2:.3f}")
                    break

                time.sleep(check_interval)

            if t2 is None:
                t2 = time.time()
                TestLog("WARNING", "", f"等待超时，路由仍未停止，使用当前时间作为T2: {t2:.3f}")

        TestLog("INFO", "Step5", "计算具有转发能力的时间范围(T2-T1)")
        routing_duration = t2 - t1 if t2 else 0
        TestLog("INFO", "", f"Post Run具有路由能力的时间: {routing_duration:.3f}秒 ({routing_duration*1000:.1f}ms)")
        
        postrun_timeout_ms = P.NMInfo.TNMtimeout_ms if hasattr(P.NMInfo, 'TNMtimeout_ms') else 10000
        expected_max_time = postrun_timeout_ms / 1000.0 + 5.0  # 允许一定余量

        if routing_duration > 0:
            TestLog("PASS", "", f"KL15 OFF后，网关具备转发能力的时间为{routing_duration:.3f}秒")
        else:
            TestLog("FAIL", "", "无法测量Post Run路由时间")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        WakeupStop()
        TestEnd("")

def test_TG5_TC7_Network_Sync_Sleep_Policy():
    nm_timer_ids = []
    net_nm_msgs = {} 
    try:
        cfg = get_routing_config()
        v, tstable_s, _ = cfg.can_params()

        all_networks = get_all_networks(cfg)
        n_networks = len(all_networks)

        if n_networks < 2:
            TestLog("WARNING", "", f"检测到网段数量({n_networks})少于2，无法完成同步睡眠测试")

        TestLog("INFO", "", f"检测到DUT支持NM的网段数量N={n_networks}，网段: {all_networks}")

        TestLog("INFO", "SubCase1", "任意某一网段停发NM报文时，DUT仍工作在NOS状态")

        TestLog("INFO", "Step1", "DUT上电，等待1s至总线通信稳定")
        dut_power_on_and_wait_stable(v, tstable_s, kl15_on=True, step_name="Step1")

        TestLog("INFO", "Step2", f"CANoe在{n_networks}个网段上开始分别发送NM报文，NM报文的地址与DUT的NM地址不同")
        nm_timer_ids = []
        for net in all_networks:
            net_config = get_net_wakeup_config(net)
            if net_config is None or net_config['WakeupMsgId'] == 0:
                TestLog("WARNING", "", f"网段 {net} 未配置WakeupMsgId，跳过")
                continue

            channel = net_config['CANoeCANChannel']
            period_ms = net_config['WakeupMsgPeriod_ms']
            nm_msg = canmsg_create(
                net_config['WakeupMsgId'],
                net_config['WakeupMsgDLC'],
                data=net_config['WakeupMsgData'],
                rtr=0, fdf=0, brs=0, ext=0
            )
            net_nm_msgs[net] = (nm_msg, period_ms, channel)

            timer_id = f"nm_sync_sleep_{net}_{channel}"
            TimerCyclic.start(timer_id, period_ms, send_canmsg, channel, msg=nm_msg)
            nm_timer_ids.append(timer_id)
            TestLog("INFO", "", f"网段 {net}: 发送WakeupMsgId=0x{net_config['WakeupMsgId']:X}, 通道={channel}, 周期={period_ms}ms")

        time.sleep(2.0)  

        TestLog("INFO", "Step3", "KL15下电")
        ctx.bob_ctrl.set_power('KL15', False)

        TestLog("INFO", "Step4", "CANoe监测总线数据1min，监测DUT的工作状态")
        time.sleep(60.0)

        ret = check_can_communication_state(wait_time=5)
        if ret == 0:
            TestLog("PASS", "Step4", "DUT停留在NOS状态，继续发送NM报文")
        else:
            TestLog("FAIL", "Step4", "DUT未继续发送NM报文")

        TestLog("INFO", "Step5", "使第一个网段停发NM报文，其余N-1个网段继续发送NM报文，监测DUT的工作状态")

        subcase1_pass = True
        valid_networks = [net for net in all_networks if net in net_nm_msgs]
        for i, net in enumerate(valid_networks):
            if i >= len(nm_timer_ids):
                break

            timer_id = nm_timer_ids[i]
            TimerCyclic.stop(timer_id)
            TestLog("INFO", "", f"停止网段{net}的NM报文发送")

            if i > 0:
                prev_net = valid_networks[i-1]
                if prev_net in net_nm_msgs:
                    prev_nm_msg, prev_period_ms, prev_channel = net_nm_msgs[prev_net]
                    prev_timer_id = f"nm_sync_sleep_{prev_net}_{prev_channel}"
                    TimerCyclic.start(prev_timer_id, prev_period_ms, send_canmsg, prev_channel, msg=prev_nm_msg)
                    nm_timer_ids[i-1] = prev_timer_id
                    TestLog("INFO", "", f"恢复网段{prev_net}的NM报文发送")

            time.sleep(5.0) 

            ret = check_can_communication_state(wait_time=5)
            if ret == 0:
                TestLog("PASS", "", f"网段{net}停发NM后，DUT仍停留在NOS状态，继续发送NM报文")
            else:
                TestLog("FAIL", "", f"网段{net}停发NM后，DUT停止了NM报文发送")
                subcase1_pass = False

        if subcase1_pass:
            TestLog("PASS", "SubCase1", "任意某一网段的NM报文停止发送之后，DUT仍然工作在NOS状态，继续发送NM报文")
        else:
            TestLog("FAIL", "SubCase1", "DUT未能保持NOS状态")

        for tid in nm_timer_ids:
            try:
                TimerCyclic.stop(tid)
            except Exception:
                pass

        TestLog("INFO", "SubCase2", "所有网段停发NM报文后，DUT进入RSS状态")

        ctx.bob_ctrl.set_power('KL15', True)
        WakeupStart()
        time.sleep(tstable_s)

        TestLog("INFO", "Step1", "DUT上电，等待1s至总线通信稳定")
        TestLog("INFO", "Step2", f"CANoe在{n_networks}个网段上开始分别发送NM报文")
        nm_timer_ids = []
        for net in all_networks:
            if net not in net_nm_msgs:
                continue
            nm_msg, period_ms, channel = net_nm_msgs[net]
            timer_id = f"nm_sync_sleep2_{net}_{channel}"
            TimerCyclic.start(timer_id, period_ms, send_canmsg, channel, msg=nm_msg)
            nm_timer_ids.append(timer_id)

        time.sleep(2.0)

        TestLog("INFO", "Step3", "KL15下电")
        ctx.bob_ctrl.set_power('KL15', False)

        TestLog("INFO", "Step4", "CANoe监测总线数据1min，监测DUT的工作状态")
        time.sleep(60.0)

        ret = check_can_communication_state(wait_time=5)
        if ret == 0:
            TestLog("PASS", "Step4", "DUT停留在NOS状态，继续发送NM报文")
        else:
            TestLog("WARNING", "Step4", "DUT未继续发送NM报文")

        TestLog("INFO", "Step5", "依次使N个网段停发NM报文，监测DUT的工作状态")
        for i, tid in enumerate(nm_timer_ids):
            TimerCyclic.stop(tid)
            TestLog("INFO", "", f"停止网段{all_networks[i]}的NM报文发送")

        ret, _ = wait_nm_message_stop(timeout_ms=120000)
        if ret:
            TestLog("PASS", "Step5", "DUT进入RSS状态，停止发送NM报文")
            TestLog("PASS", "SubCase2", "在其连接的N个网段都停发NM报文后，DUT才满足睡眠条件进入RSS状态，停止发送NM报文")
        else:
            TestLog("FAIL", "Step5", "DUT未进入RSS状态，仍在发送NM报文")
            TestLog("FAIL", "SubCase2", "DUT未能在所有网段停发NM后进入RSS状态")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        for tid in nm_timer_ids:
            try:
                TimerCyclic.stop(tid)
            except Exception:
                pass
        WakeupStop()
        TestEnd("")

def test_TG5_TC8_Network_Sync_Wakeup_Policy():
    nm_timer_ids = []
    try:
        cfg = get_routing_config()
        v, tstable_s, _ = cfg.can_params()
        nm_params = get_nm_params()

        all_networks = get_all_networks(cfg)
        n_networks = len(all_networks)

        if n_networks < 1:
            TestLog("WARNING", "", f"检测到网段数量({n_networks})少于1，无法完成同步唤醒测试")
            TestEnd("")
            return

        TestLog("INFO", "", f"检测到DUT支持NM的网段数量N={n_networks}，网段: {all_networks}")

        nm_msg = canmsg_create(
            nm_params['WakeupMsgID'],
            nm_params['WakeupMsgDLC'],
            data=nm_params['WakeupMsgData'],
            rtr=0, fdf=0, brs=0, ext=0
        )

        TestLog("INFO", "SubCase1", "KL15 ON唤醒，所有网段都被唤醒并发送NM报文")

        TestLog("INFO", "Step1", "DUT上电，等待1s至总线通信稳定")
        ctx.power_ctrl.set_voltage(v)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)
        ctx.bob_ctrl.set_power('KL15', False) 
        time.sleep(1.0)

        TestLog("INFO", "Step2", "KL15 ON")
        ctx.bob_ctrl.set_power('KL15', True)
        WakeupStart()
        time.sleep(tstable_s)

        TestLog("INFO", "Step3", "检测DUT是否被唤醒")
        ret = check_can_communication_state(wait_time=3)
        if ret == 0:
            TestLog("PASS", "SubCase1", "KL15 ON唤醒DUT后，DUT被唤醒")
        else:
            TestLog("FAIL", "SubCase1", "KL15 ON后DUT未被唤醒")

        TestLog("INFO", "SubCase2", "应用报文唤醒测试，DUT无法被应用报文唤醒")

        TestLog("INFO", "Step1", "使DUT进入睡眠状态")
        ctx.bob_ctrl.set_power('KL15', False)
        WakeupStop()

        ret, _ = wait_nm_message_stop(timeout_ms=120000)
        if ret:
            TestLog("INFO", "", "DUT已进入睡眠状态")
        else:
            TestLog("WARNING", "", "等待DUT进入睡眠超时")

        time.sleep(5.0)  

        app_net = all_networks[0] if all_networks else None
        if app_net:
            app_net_config = get_net_wakeup_config(app_net)
            app_channel = app_net_config['CANoeCANChannel'] if app_net_config else 1
            TestLog("INFO", "Step2", f"在网段 {app_net} (通道={app_channel}) 发送应用报文")
            send_app_msg_on_channel(app_channel)
        else:
            TestLog("WARNING", "Step2", "未找到有效网段，跳过应用报文发送")
        time.sleep(2.0)

        TestLog("INFO", "Step3", "检测DUT是否被唤醒")
        ret = check_can_communication_state(wait_time=3)
        if ret == -1:  
            TestLog("PASS", "SubCase2", "应用报文无法唤醒DUT")
        else:
            TestLog("FAIL", "SubCase2", "应用报文错误地唤醒了DUT")

        TestLog("INFO", "SubCase3", "NM报文唤醒测试，任意网段收到NM报文后所有网段都被唤醒")

        WakeupStop()
        time.sleep(5.0)

        subcase3_pass = True
        tested_nets = set()

        for net in all_networks:
            if net in tested_nets:
                continue

            net_config = get_net_wakeup_config(net)
            if net_config is None or net_config['WakeupMsgId'] == 0:
                TestLog("WARNING", "", f"网段 {net} 未配置WakeupMsgId，跳过")
                tested_nets.add(net)
                continue

            tested_nets.add(net)
            TestLog("INFO", "", f"测试网段 {net} 的NM报文唤醒能力")

            WakeupStop()
            ret, _ = wait_nm_message_stop(timeout_ms=60000)
            time.sleep(3.0)

            channel = net_config['CANoeCANChannel']
            period_ms = net_config['WakeupMsgPeriod_ms']
            nm_msg = canmsg_create(
                net_config['WakeupMsgId'],
                net_config['WakeupMsgDLC'],
                data=net_config['WakeupMsgData'],
                rtr=0, fdf=0, brs=0, ext=0
            )
            TestLog("INFO", "Step1", f"在网段 {net} 发送NM报文 (WakeupMsgId=0x{net_config['WakeupMsgId']:X}, 通道={channel})")

            timer_id = f"nm_wakeup_{net}_{channel}"
            TimerCyclic.start(timer_id, period_ms, send_canmsg, channel, msg=nm_msg)
            nm_timer_ids.append(timer_id)

            time.sleep(3.0)  # 等待DUT响应

            TestLog("INFO", "Step2", "检测DUT所有网段是否都被唤醒，并发送NM报文")
            all_pass, results = check_all_networks_nm_messages(wait_time_s=5.0)

            if all_pass:
                TestLog("PASS", "", f"网段 {net} 收到NM报文后，DUT所有网段都被唤醒并发送NM报文")
            else:
                TestLog("FAIL", "", f"网段 {net} 收到NM报文后，部分网段未发送NM报文")
                subcase3_pass = False

            TimerCyclic.stop(timer_id)
            nm_timer_ids.remove(timer_id)

        if subcase3_pass:
            TestLog("PASS", "SubCase3", "任意网段收到NM报文后，所有网段都被唤醒并发送NM报文")
        else:
            TestLog("FAIL", "SubCase3", "部分网段NM报文唤醒测试失败")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        for tid in nm_timer_ids:
            try:
                TimerCyclic.stop(tid)
            except Exception:
                pass
        WakeupStop()
        TestEnd("")

