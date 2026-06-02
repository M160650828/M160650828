import time
import traceback

from uvtest.testlog import TestLog
from uvtest.framework import TestFixture
from common.control import TestStart, TestEnd
from common.wakeup import WakeupStart, WakeupStop
from common.params import P
from .routing_module import (
    routing_initialization, routing_deinitialization,
    get_routing_config, get_routing_sender,
    net_to_channel, get_all_networks,
    send_diag_request,
)
from .routing_nm_utils import (
    send_and_check_routing_all_entries, check_routing_stopped,
    dut_power_on_and_wait_stable,
)


class RoutingDiagTestFixture(TestFixture):
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

def test_TG6_TC1_Gateway_Diag_Network():
    try:
        cfg = get_routing_config()
        v, tstable_s, _ = cfg.can_params()

        TestLog("INFO", "Step1", "DUT上电，等待1s至总线通信稳定")
        dut_power_on_and_wait_stable(v, tstable_s, kl15_on=True, step_name="Step1")

        TestLog("INFO", "Step2", "利用CANoe向网关的每一个网段发送诊断请求")

        all_networks = get_all_networks(cfg)
        diag_req_id = P.ECUInfo.DiagReqID_int
        expected_diag_channel = P.ECUInfo.DiagCANChannelNum
        expected_diag_network = P.ECUInfo.DiagCANChannelName

        TestLog("INFO", "", f"检测到网段数量: {len(all_networks)}，网段: {all_networks}")
        TestLog("INFO", "", f"期望诊断网段: {expected_diag_network} (通道{expected_diag_channel})")

        responding_networks = []
        for net in all_networks:
            channel = net_to_channel(net)
            TestLog("INFO", "", f"向网段 {net} (通道{channel}) 发送诊断请求 0x10 01 (SessionControl)")

            diag_data = [0x02, 0x10, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]
            has_response, _ = send_diag_request(channel, diag_req_id, diag_data, timeout_ms=2000)

            if has_response:
                TestLog("INFO", "", f"网段 {net} 收到肯定响应")
                responding_networks.append(net)
            else:
                TestLog("INFO", "", f"网段 {net} 无响应")

        if len(responding_networks) == 1:
            if responding_networks[0] == expected_diag_network or net_to_channel(responding_networks[0]) == expected_diag_channel:
                TestLog("PASS", "", f"网关只有一个指定网段({responding_networks[0]})给肯定响应")
            else:
                TestLog("FAIL", "", f"响应的网段({responding_networks[0]})与期望的诊断网段({expected_diag_network})不一致")
        elif len(responding_networks) == 0:
            TestLog("FAIL", "", "没有任何网段响应诊断请求")
        else:
            TestLog("FAIL", "", f"多个网段响应了诊断请求: {responding_networks}，应只有一个网段响应")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        WakeupStop()
        TestEnd("")

def test_TG6_TC2_Gateway_Diag_Routing():
    sender = None
    try:
        cfg = get_routing_config()
        v, tstable_s, _ = cfg.can_params()

        TestLog("INFO", "Step1", "DUT上电，等待1s至总线通信稳定")
        dut_power_on_and_wait_stable(v, tstable_s, kl15_on=True, step_name="Step1")

        TestLog("INFO", "Step2", "根据路由表定义，仿真需要路由的应用报文发送给DUT对应的源网段")
        sender = get_routing_sender()
        TestLog("INFO", "", "DUT正确接收报文")

        TestLog("INFO", "Step3", "利用CANoe监测目标网段是否转发需要路由的报文")

        cycle_msg_pass = send_and_check_routing_all_entries("CycleMsg", sender, cfg, "Step3")
        event_msg_pass = send_and_check_routing_all_entries("EventMsg", sender, cfg, "Step3")

        msg_routing_pass = cycle_msg_pass and event_msg_pass
        if msg_routing_pass:
            TestLog("PASS", "Step3", "DUT正常转发应用报文")
        else:
            TestLog("FAIL", "Step3", "DUT未正常转发应用报文")

        TestLog("INFO", "Step4", "利用CANoe仿真停止通信($28)的诊断指令")
        diag_channel = P.ECUInfo.DiagCANChannelNum
        diag_req_id = P.ECUInfo.DiagReqID_int  # 使用物理寻址

        TestLog("INFO", "", f"发送SessionControl(10 01)到诊断通道{diag_channel}, 物理地址0x{diag_req_id:X}")
        session_data = [0x02, 0x10, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]
        has_response, _ = send_diag_request(diag_channel, diag_req_id, session_data, timeout_ms=2000)
        if has_response:
            TestLog("PASS", "", "SessionControl(10 01)收到肯定响应")
        else:
            TestLog("WARNING", "", "SessionControl(10 01)未收到响应")

        TestLog("INFO", "", f"发送CommunicationControl(28 03 03)到诊断通道{diag_channel}")
        comm_ctrl_data = [0x03, 0x28, 0x03, 0x03, 0x00, 0x00, 0x00, 0x00]
        has_response, _ = send_diag_request(diag_channel, diag_req_id, comm_ctrl_data, timeout_ms=2000)

        if has_response:
            TestLog("PASS", "Step4", "发送0x28诊断指令成功，收到响应")
        else:
            TestLog("WARNING", "Step4", "发送0x28诊断指令，未收到响应")

        time.sleep(1.0) 

        TestLog("INFO", "Step5", "利用CANoe监测目标网段是否转发应用报文")
        routing_stopped = check_routing_stopped(sender, cfg, "Step5")

        if routing_stopped:
            TestLog("PASS", "Step5", "目标网段停止转发应用报文")
            TestLog("PASS", "", "评价标准满足：当网关接收到停止通信($28)的诊断指令时，目标网段停止转发应用报文")
        else:
            TestLog("FAIL", "Step5", "目标网段仍在转发应用报文")

        TestLog("INFO", "", "恢复通信")
        send_diag_request(diag_channel, diag_req_id, session_data, timeout_ms=2000)
        comm_enable_data = [0x03, 0x28, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00]
        send_diag_request(diag_channel, diag_req_id, comm_enable_data, timeout_ms=2000)

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()
        WakeupStop()
        TestEnd("")


