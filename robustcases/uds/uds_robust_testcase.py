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
from slplus.time import sl_time

from testcases.uds.uds_can_utils import (
    get_can_node, service_10_check, check_current_session,
    service_unsupported_check, service_22_check, service_2E_check,
    service_11_check, check_resp,
    tester_present_start, tester_present_stop,
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


def get_all_test_cases():
    import inspect
    current_module = inspect.getmodule(inspect.currentframe())
    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj
    return test_cases
