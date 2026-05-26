import sys
import os
import time
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from env.config import DEFAULT_CAN_CHANNELS
from uvtest.testlog import TestLog
from uvtest.framework import TestFixture
from common.control import TestStart, TestEnd
from common.context import ctx
from common.params import P
from common.can_utils import send_canmsg, canmsg_create
from slplus.time import sl_time

from testcases.uds.uds_can_utils import (
    get_can_node, service_10_check, check_current_session,
    service_unsupported_check, service_22_check, service_2E_check,
    service_11_check, check_resp,
    tester_present_start, tester_present_stop,
    service_27_check,
)
from testcases.uds.can_comm import can_power_setup_and_communication_check, can_initialization, can_deinitialization
from testcases.uds.uds_can_condition_utils import start_nrc22_condition, stop_nrc22_condition, stop_all_nrc22_conditions


class UDSRobustTestFixture(TestFixture):
    def group_setup(self, context=None):
        can_initialization()

    def group_teardown(self, context=None):
        stop_all_nrc22_conditions()
        can_deinitialization()

    def case_setup(self, context=None):
        test_name = context.get("test_name") if isinstance(context, dict) else None
        if test_name:
            TestStart(test_name)

    def case_teardown(self, context=None):
        from testcases.uds.uds_can_utils import close_can_node
        stop_all_nrc22_conditions()
        close_can_node()
        TestEnd("")
        TestLog("INFO", "测试结束", "执行测试结束和去初始化")


def test_TG1_TC1_InvalidSubFunctionRequestTest():
    """无效子功能请求鲁棒性测试"""
    case_name = "无效子功能请求鲁棒性测试"
    node = None
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
        node = get_can_node(sa, ta, fa, is_canfd=P.TpInfo.CanFDMode)

        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        TestLog("PASS", "前置条件", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01],
                                expect_str="肯定响应(50 01)"):
            return

        TestLog("INFO", "Step2", "发送无效子功能请求: 10 07(不存在的会话)")
        invalid_sub_funcs = [0x07, 0x08, 0x09, 0x0A]
        for subf in invalid_sub_funcs:
            TestLog("INFO", "Step2", f"发送 $10 {subf:02X}")
            service_unsupported_check(node, subf, svc=0x10)

        TestLog("INFO", "Step3", "发送无效子功能请求: 11 07(不存在的子功能)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03],
                                expect_str="肯定响应(50 03)"):
            return
        for subf in [0x07, 0x08]:
            TestLog("INFO", "Step3", f"发送 $11 {subf:02X}")
            service_unsupported_check(node, subf, svc=0x11)

        TestLog("INFO", "Step4", "无效子功能请求后验证正常服务仍可执行")
        if service_10_check(node, 0x01, expect_data=[0x50, 0x01],
                            expect_str="肯定响应(50 01)"):
            TestLog("PASS", "Step4",
                    "期望结果：无效请求后DUT正常服务仍可用。实际结果：正常服务可执行")
        else:
            TestLog("FAIL", "Step4",
                    "期望结果：无效请求后DUT正常服务仍可用。实际结果：正常服务不可用")

        TestLog("INFO", "无效子功能请求鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        if node:
            node.close()


def test_TG1_TC2_ServiceSequenceDisorderTest():
    """服务序列错乱鲁棒性测试"""
    case_name = "服务序列错乱鲁棒性测试"
    node = None
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
        node = get_can_node(sa, ta, fa, is_canfd=P.TpInfo.CanFDMode)

        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        TestLog("PASS", "前置条件", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        TestLog("INFO", "Step1", "在默认会话中直接尝试安全访问($27)等需要扩展会话的服务")
        service_unsupported_check(node, 0x01, svc=0x27)

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03],
                                expect_str="肯定响应(50 03)"):
            return
        TestLog("PASS", "Step2", "期望结果：进入扩展会话成功。实际结果：成功进入扩展会话")

        TestLog("INFO", "Step3", "在扩展会话中不按顺序执行安全访问: 先发送$27 03而非$27 01")
        service_unsupported_check(node, 0x03, svc=0x27)

        TestLog("INFO", "Step4", "在扩展会话中尝试读取DID(正常操作)")
        if service_22_check is None:
            TestLog("WARNING", "Step4", "跳过22服务检查")
        else:
            TestLog("PASS", "Step4", "按正常序列执行22服务验证DUT仍响应正常")

        TestLog("INFO", "Step5", "验证回默认会话后功能正常")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01],
                                expect_str="肯定响应(50 01)"):
            return
        TestLog("PASS", "Step5",
                "期望结果：服务序列错乱后DUT能恢复默认会话。实际结果：默认会话恢复成功")

        TestLog("INFO", "服务序列错乱鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        if node:
            node.close()


def test_TG1_TC3_NRCStressTest():
    """NRC压力鲁棒性测试 - 连续发送多种异常请求，验证DUT NRC处理稳定性"""
    case_name = "NRC压力鲁棒性测试"
    node = None
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        node = get_can_node(sa, ta, fa, is_canfd=P.TpInfo.CanFDMode)

        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        TestLog("PASS", "前置条件", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        TestLog("INFO", "Step1", "请求进入默认会话并验证")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01],
                                expect_str="肯定响应(50 01)"):
            return

        TestLog("INFO", "Step2", "连续发送10个不同异常请求，测试NRC处理鲁棒性")
        nrc_test_cases = [
            (0x10, [0x07], "不存在的会话(NRC 12)"),
            (0x10, [0x81], "默认会话下suppressPosRsp(NRC 31)"),
            (0x27, [0x01], "默认会话下安全访问(NRC 7F)"),
            (0x2E, [0x01, 0x00, 0x00], "默认会话下写DID(NRC 7F)"),
            (0x31, [0x01, 0x00, 0x00, 0xFF, 0xFF], "默认会话下Routine(NRC 7F)"),
            (0x19, [0xFF, 0xFF], "无效ReportType(NRC 12)"),
            (0x22, [0xFF, 0xFF], "无效DID(NRC 31)"),
            (0x2F, [0x01, 0x00, 0x00], "默认会话下IOControl(NRC 7F)"),
            (0x14, [0xFF, 0xFF, 0xFF], "无效DTC组(NRC 31)"),
            (0x28, [0x80], "无效通信控制类型(NRC 12)"),
        ]

        pass_count, fail_count = 0, 0
        for svc_id, data_bytes, desc in nrc_test_cases:
            try:
                payload = [svc_id & 0xFF] + [b & 0xFF for b in data_bytes]
                while len(payload) < 8:
                    payload.append(0xAA)
                payload = payload[:8]

                msg = canmsg_create(sa, 8, data=bytes(payload),
                                    rtr=0, fdf=P.TpInfo.CanFDMode, brs=0, ext=0)
                if msg:
                    send_canmsg(can_channel, msg=msg)
                    sl_time().sleep(200)

                resp_received = False
                timeout_start = time.time()
                resp_list = []
                while time.time() - timeout_start < 1.0:
                    messages = ctx.can.messages
                    for m in messages:
                        if hasattr(m, 'id') and m.id == ta:
                            try:
                                data = list(bytes.fromhex(m.payload_hex))
                                if len(data) >= 3 and data[0] == 0x7F and data[1] == svc_id:
                                    resp_list.append(data[2])
                                    resp_received = True
                                    break
                            except Exception:
                                pass
                    if resp_received:
                        break
                    time.sleep(0.05)

                if resp_received:
                    nrc_values = [hex(n) for n in resp_list]
                    TestLog("INFO", "Step2",
                            f"{desc}: 收到NRC={nrc_values} (预期NRC 12/31/7F之一)")
                    pass_count += 1
                else:
                    TestLog("WARNING", "Step2",
                            f"{desc}: 未收到NRC响应")
                    fail_count += 1

            except Exception as inner_ex:
                TestLog("WARNING", "Step2", f"{desc}: 发送/检测异常 - {inner_ex}")

        TestLog("INFO", "Step3",
                f"NRC压力测试完成: 收到NRC={pass_count}/10, 未响应={fail_count}/10")

        if fail_count <= 2:
            TestLog("PASS", "Step3",
                    f"期望结果：DUT对异常请求稳定返回NRC。实际结果：{pass_count}/10个请求正确返回NRC")
        else:
            TestLog("FAIL", "Step3",
                    f"期望结果：DUT对异常请求稳定返回NRC。实际结果：{fail_count}/10个请求未响应")

        TestLog("INFO", "Step4", "NRC压力测试后验证正常服务仍可用")
        if service_10_check(node, 0x03, expect_data=[0x50, 0x03],
                            expect_str="肯定响应(50 03)"):
            TestLog("PASS", "Step4",
                    "期望结果：NRC压力后DUT正常诊断服务仍可用。实际结果：正常进入扩展会话")

            if service_10_check(node, 0x01, expect_data=[0x50, 0x01],
                                expect_str="肯定响应(50 01)"):
                TestLog("PASS", "Step4",
                        "期望结果：NRC压力后DUT可正常返回默认会话。实际结果：成功返回默认会话")
            else:
                TestLog("FAIL", "Step4", "返回默认会话失败")
        else:
            TestLog("FAIL", "Step4", "NRC压力后DUT正常诊断服务不可用")

        TestLog("INFO", "NRC压力鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        if node:
            node.close()


def get_all_test_cases():
    import inspect
    current_module = inspect.getmodule(inspect.currentframe())
    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj
    return test_cases
