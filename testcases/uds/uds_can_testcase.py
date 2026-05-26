import copy
import inspect
import sys
import os
import time
import traceback
from env.config import *

from common.context import ctx

from uvtest.testlog import TestLog
from common.control import TestStart, TestEnd
from library.security.generate_key import *
from uvtest.framework import TestFixture
from slplus.time import sl_time

from .uds_can_utils import RunTimeInfo, check_msg_thread_start, check_msg_thread_stop, check_msg_time_diff_ms, \
    check_msg_time_diff_ms_with_78_flag, clear_27_error_timer, get_can_node, check_expect_response, UDSTestParams, get_seed_from_27_resp, \
    calc_key_by_seed, \
    service_10_check, check_current_session, service_27_check, service_27_xx_check, AlgorithmType, service_11_check, \
    service_28_check, service_3E_check, service_85_check, \
    tester_present_start, \
    tester_present_stop, service_19_check, get_dtc_from_19_resp, service_14_check, service_2E_check, service_22_check, \
    service_2F_check, service_31_check, get_info_from_22_resp, service_unsupported_check, check_app_communication, \
    get_app_msg_count, get_nm_msg_count
from .can_comm import can_power_setup_and_communication_check, can_initialization, can_deinitialization
from .uds_can_condition_utils import start_nrc22_condition, stop_nrc22_condition, stop_all_nrc22_conditions

workdir_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(workdir_path)


class UDSCANTestFixture(TestFixture):
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
        from .uds_can_utils import close_can_node
        stop_all_nrc22_conditions()
        close_can_node()
        TestEnd("")
        TestLog("INFO", "测试结束", "执行测试结束和去初始化")


def test_TG1_TC1_phyRequest_10_Positive():
    case_name = "10服务肯定响应与功能检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送抑制肯定响应的请求进入默认会话(10 81)")
        if not service_10_check(node, 0x81, expect_data=None, expect_str="无响应"): return

        time.sleep(1)

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step6", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step7", "发送抑制肯定响应的请求进入扩展会话(10 83)")
        if not service_10_check(node, 0x83, expect_data=None, expect_str="无响应"): return

        time.sleep(1)

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step9", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step10", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step11", "发送抑制肯定响应的请求进入扩展会话(10 83)")
        if not service_10_check(node, 0x83, expect_data=None, expect_str="无响应"): return

        time.sleep(1)

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step13", "发送抑制肯定响应的请求进入默认会话(10 81)")
        if not service_10_check(node, 0x81, expect_data=None, expect_str="无响应"): return

        time.sleep(1)

        TestLog("INFO", "Step14", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step15", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step16", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step17", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step18", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step19", "发送抑制肯定响应的请求进入刷新会话(10 82)")
        if not service_10_check(node, 0x82, expect_data=None, expect_str="无响应"): return

        TestLog("INFO", "Step20", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step21", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        time.sleep(1)

        TestLog("INFO", "Step22", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step23", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        time.sleep(1)

        TestLog("INFO", "Step24", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step25", "发送抑制肯定响应的请求进入刷新会话(10 82)")
        if not service_10_check(node, 0x82, expect_data=None, expect_str="无响应"): return

        time.sleep(1)

        TestLog("INFO", "Step26", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step27", "发送抑制肯定响应的请求进入默认会话(10 81)")
        if not service_10_check(node, 0x81, expect_data=None, expect_str="无响应"): return

        time.sleep(1)

        TestLog("INFO", "Step28", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return
    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC2_funRequest_10_Positive():
    case_name = "10服务肯定响应与功能检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)", func_req=True): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送抑制肯定响应的请求进入默认会话(10 81)")
        if not service_10_check(node, 0x81, expect_data=None, expect_str="无响应", func_req=True): return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)", func_req=True): return

        TestLog("INFO", "Step6", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step7", "发送抑制肯定响应的请求进入扩展会话(10 83)")
        if not service_10_check(node, 0x83, expect_data=None, expect_str="无响应", func_req=True): return

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step9", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)", func_req=True): return

        TestLog("INFO", "Step10", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step11", "发送抑制肯定响应的请求进入扩展会话(10 83)")
        if not service_10_check(node, 0x83, expect_data=None, expect_str="无响应", func_req=True): return

        time.sleep(1)

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step13", "发送抑制肯定响应的请求进入默认会话(10 81)")
        if not service_10_check(node, 0x81, expect_data=None, expect_str="无响应", func_req=True): return

        TestLog("INFO", "Step14", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step15", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)", func_req=True): return

        TestLog("INFO", "Step16", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step17", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)", func_req=True): return

        TestLog("INFO", "Step18", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step19", "发送抑制肯定响应的请求进入刷新会话(10 82)")
        if not service_10_check(node, 0x82, expect_data=None, expect_str="无响应", func_req=True): return

        time.sleep(1)

        TestLog("INFO", "Step20", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step21", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)", func_req=True): return

        time.sleep(1)

        TestLog("INFO", "Step22", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step23", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)", func_req=True): return

        time.sleep(1)

        TestLog("INFO", "Step24", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step25", "发送抑制肯定响应的请求进入刷新会话(10 82)")
        if not service_10_check(node, 0x82, expect_data=None, expect_str="无响应", func_req=True): return

        time.sleep(1)

        TestLog("INFO", "Step26", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step27", "发送抑制肯定响应的请求进入默认会话(10 81)")
        if not service_10_check(node, 0x81, expect_data=None, expect_str="无响应", func_req=True): return

        time.sleep(1)

        TestLog("INFO", "Step28", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC3_phyRequest_10_NRC12():
    case_name = "10服务NRC12检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    min_sn, max_sn = UDSTestParams.MinSubID, UDSTestParams.MaxSubID
    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3~6",
                "令SN=0x00;如果SN为当前会话状态支持的物理寻址子功能且SN<0xFF，则SN+=1,直到SN为当前会话不支持的子功能或SN=0xFF")
        for sn in range(min_sn, max_sn + 1):
            if sn in UDSTestParams.Services10SubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)}，在10服务支持的范围内，跳过该SN")
                continue
            TestLog("INFO", "", f"SN={hex(sn)}，不在10服务支持的范围内，测试该SN")
            if not service_10_check(node, sn, expect_data=[0x7F, 0x10, 0x12], expect_str="否定响应(7F 10 12)"):
                return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step8", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step10~13",
                "令SN=0x00;如果SN为当前会话状态支持的物理寻址子功能且SN<0xFF，则SN+=1,直到SN为当前会话不支持的子功能或SN=0xFF")
        for sn in range(min_sn, max_sn + 1):
            if sn in UDSTestParams.Services10SubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)}，在10服务支持的范围内，跳过该SN")
                continue
            TestLog("INFO", "", f"SN={hex(sn)}，不在10服务支持的范围内，测试该SN")
            if not service_10_check(node, sn, expect_data=[0x7F, 0x10, 0x12], expect_str="否定响应(7F 10 12)"):
                return

        TestLog("INFO", "Step14", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step15", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step16", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step17~20",
                "令SN=0x00;如果SN为当前会话状态支持的物理寻址子功能且SN<0xFF，则SN+=1,直到SN为当前会话不支持的子功能或SN=0xFF")
        for sn in range(min_sn, max_sn + 1):
            if sn in UDSTestParams.Services10SubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)}，在10服务支持的范围内，跳过该SN")
                continue
            TestLog("INFO", "", f"SN={hex(sn)}，不在10服务支持的范围内，测试该SN")
            if not service_10_check(node, sn, expect_data=[0x7F, 0x10, 0x12], expect_str="否定响应(7F 10 12)"):
                return

        TestLog("INFO", "Step21", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC4_funRequest_10_NRC12():
    case_name = "10服务NRC12检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    min_sn, max_sn = UDSTestParams.MinSubID, UDSTestParams.MaxSubID
    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)",
                                func_req=True): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return
        TestLog("INFO", "Step3~6",
                "令SN=0x00;如果SN为当前会话状态支持的物理寻址子功能且SN<0xFF，则SN+=1,直到SN为当前会话不支持的子功能或SN=0xFF")
        for sn in range(min_sn, max_sn + 1):
            if sn in UDSTestParams.Services10SubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)}，在10服务支持的范围内，跳过该SN")
                continue
            TestLog("INFO", "", f"SN={hex(sn)}，不在10服务支持的范围内，测试该SN")
            if not service_10_check(node, sn, expect_data=None, expect_str="无响应", func_req=True, timeout=0.1): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step8", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)",
                                func_req=True): return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step10~13",
                "令SN=0x00;如果SN为当前会话状态支持的物理寻址子功能且SN<0xFF，则SN+=1,直到SN为当前会话不支持的子功能或SN=0xFF")
        for sn in range(min_sn, max_sn + 1):
            if sn in UDSTestParams.Services10SubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)}，在10服务支持的范围内，跳过该SN")
                continue
            TestLog("INFO", "", f"SN={hex(sn)}，不在10服务支持的范围内，测试该SN")
            if not service_10_check(node, sn, expect_data=None, expect_str="无响应", func_req=True, timeout=0.1): return

        TestLog("INFO", "Step14", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step15", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)",
                                func_req=True): return

        TestLog("INFO", "Step16", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step17~20",
                "令SN=0x00;如果SN为当前会话状态支持的物理寻址子功能且SN<0xFF，则SN+=1,直到SN为当前会话不支持的子功能或SN=0xFF")
        for sn in range(min_sn, max_sn + 1):
            if sn in UDSTestParams.Services10SubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)}，在10服务支持的范围内，跳过该SN")
                continue
            TestLog("INFO", "", f"SN={hex(sn)}，不在10服务支持的范围内，测试该SN")
            if not service_10_check(node, sn, expect_data=None, expect_str="无响应", func_req=True, timeout=0.1): return

        TestLog("INFO", "Step21", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC5_phyRequest_10_NRC13():
    case_name = "10服务NRC13检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    min_sn, max_sn = UDSTestParams.MinSubID, UDSTestParams.MaxSubID
    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送长度较短10请求")
        if not service_10_check(node, None, expect_data=[0x7F, 0x10, 0x13],
                                expect_str="NRC=0x13的否定响应(7F 10 13)"): return

        TestLog("INFO", "Step4", "令SN=0x01")

        TestLog("INFO", "Step5-6", "使用配置支持的SN发送DL=3,4,5,6,7的10请求")
        for sn in UDSTestParams.Services10LengthCheckSubFunList:
            if sn < min_sn or sn > max_sn:
                continue
            for dl in [3, 4, 5, 6, 7]:
                TestLog("INFO", "", f"发送SN={hex(sn)},DL={dl}的10请求")
                if not service_10_check(node, sn, dl=dl, dl_padding=0x00, expect_data=[0x7F, 0x10, 0x13],
                                        expect_str="NRC=0x13的否定响应(7F 10 13)"):
                    return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step8", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step10", "发送长度较短10请求")
        if not service_10_check(node, None, expect_data=[0x7F, 0x10, 0x13],
                                expect_str="NRC=0x13的否定响应(7F 10 13)"): return

        TestLog("INFO", "Step11", "令SN=0x01")

        TestLog("INFO", "Step12-13", "使用配置支持的SN发送DL=3,4,5,6,7的10请求")
        for sn in UDSTestParams.Services10LengthCheckSubFunList:
            if sn < min_sn or sn > max_sn:
                continue
            for dl in [3, 4, 5, 6, 7]:
                TestLog("INFO", "", f"发送SN={hex(sn)},DL={dl}的10请求")
                if not service_10_check(node, sn, dl=dl, dl_padding=0x00, expect_data=[0x7F, 0x10, 0x13],
                                        expect_str="NRC=0x13的否定响应(7F 10 13)"):
                    return

        TestLog("INFO", "Step14", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step15", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step16", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step17", "发送长度较短10请求")
        if not service_10_check(node, None, expect_data=[0x7F, 0x10, 0x13],
                                expect_str="NRC=0x13的否定响应(7F 10 13)"): return

        TestLog("INFO", "Step18", "令SN=0x01")

        TestLog("INFO", "Step19-20", "使用配置支持的SN发送DL=3,4,5,6,7的10请求")
        for sn in UDSTestParams.Services10LengthCheckSubFunList:
            if sn < min_sn or sn > max_sn:
                continue
            for dl in [3, 4, 5, 6, 7]:
                TestLog("INFO", "", f"发送SN={hex(sn)},DL={dl}的10请求")
                if not service_10_check(node, sn, dl=dl, dl_padding=0x00, expect_data=[0x7F, 0x10, 0x13],
                                        expect_str="NRC=0x13的否定响应(7F 10 13)"):
                    return

        TestLog("INFO", "Step21", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC6_funRequest_10_NRC13():
    case_name = "10服务NRC13检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    min_sn, max_sn = UDSTestParams.MinSubID, UDSTestParams.MaxSubID
    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)",
                                func_req=True): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送长度较短10请求")
        if not service_10_check(node, None, expect_data=[0x7F, 0x10, 0x13], expect_str="NRC=0x13的否定响应(7F 10 13)",
                                func_req=True): return

        TestLog("INFO", "Step4", "令SN=0x01")

        TestLog("INFO", "Step5-6", "使用配置支持的SN发送DL=3,4,5,6,7的10请求")
        for sn in UDSTestParams.Services10LengthCheckSubFunList:
            if sn < min_sn or sn > max_sn:
                continue
            for dl in [3, 4, 5, 6, 7]:
                TestLog("INFO", "", f"发送SN={hex(sn)},DL={dl}的10请求")
                if not service_10_check(node, sn, dl=dl, dl_padding=0x00, expect_data=[0x7F, 0x10, 0x13],
                                        expect_str="NRC=0x13的否定响应(7F 10 13)", func_req=True):
                    return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step8", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)",
                                func_req=True): return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step10", "发送长度较短10请求")
        if not service_10_check(node, None, expect_data=[0x7F, 0x10, 0x13], expect_str="NRC=0x13的否定响应(7F 10 13)",
                                func_req=True): return

        TestLog("INFO", "Step11", "令SN=0x01")

        TestLog("INFO", "Step12-13", "使用配置支持的SN发送DL=3,4,5,6,7的10请求")
        for sn in UDSTestParams.Services10LengthCheckSubFunList:
            if sn < min_sn or sn > max_sn:
                continue
            for dl in [3, 4, 5, 6, 7]:
                TestLog("INFO", "", f"发送SN={hex(sn)},DL={dl}的10请求")
                if not service_10_check(node, sn, dl=dl, dl_padding=0x00, expect_data=[0x7F, 0x10, 0x13],
                                        expect_str="NRC=0x13的否定响应(7F 10 13)", func_req=True):
                    return

        TestLog("INFO", "Step14", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step15", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)",
                                func_req=True): return

        TestLog("INFO", "Step16", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step17", "发送长度较短10请求")
        if not service_10_check(node, None, expect_data=[0x7F, 0x10, 0x13], expect_str="NRC=0x13的否定响应(7F 10 13)",
                                func_req=True): return

        TestLog("INFO", "Step18", "令SN=0x01")

        TestLog("INFO", "Step19-20", "使用配置支持的SN发送DL=3,4,5,6,7的10请求")
        for sn in UDSTestParams.Services10LengthCheckSubFunList:
            if sn < min_sn or sn > max_sn:
                continue
            for dl in [3, 4, 5, 6, 7]:
                TestLog("INFO", "", f"发送SN={hex(sn)},DL={dl}的10请求")
                if not service_10_check(node, sn, dl=dl, dl_padding=0x00, expect_data=[0x7F, 0x10, 0x13],
                                        expect_str="NRC=0x13的否定响应(7F 10 13)", func_req=True):
                    return

        TestLog("INFO", "Step21", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC7_phyRequest_10_NRC22():
    case_name = "10服务NRC22检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step5",
                "遍历触发NRC22的所有条件并发送10 02请求，如果满足条件之一则对10 02请求返回NRC=0x22的否定响应(触发条件需要根据供应商要求添加) ")
        conditions = UDSTestParams.get_nrc22_conditions_for_service(0x10)
        if not conditions:
            TestLog("WARNING", "Step5", "未配置10服务可执行的NRC22条件，跳过该测试")
            return
        condition = conditions[0]
        if not start_nrc22_condition(condition): return
        try:
            if not service_10_check(node, 0x02, expect_data=[0x7F, 0x10, 0x22], expect_str="否定响应(7F 10 22)"): return
        finally:
            stop_nrc22_condition(condition)

        TestLog("INFO", "Step6", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC8_funRequest_10_NRC22():
    case_name = "10服务NRC22检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)",
                                func_req=True): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)",
                                func_req=True): return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step5",
                "遍历触发NRC22的所有条件并发送10 02请求，如果满足条件之一则对10 02请求返回NRC=0x22的否定响应(触发条件需要根据供应商要求添加) ")
        conditions = UDSTestParams.get_nrc22_conditions_for_service(0x10)
        if not conditions:
            TestLog("WARNING", "Step5", "未配置10服务可执行的NRC22条件，跳过该测试")
            return
        condition = conditions[0]
        if not start_nrc22_condition(condition): return
        try:
            if not service_10_check(node, 0x02, expect_data=[0x7F, 0x10, 0x22], expect_str="否定响应(7F 10 22)",
                                    func_req=True): return
        finally:
            stop_nrc22_condition(condition)

        TestLog("INFO", "Step6", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC9_phyRequest_10_NRC7E():
    case_name = "10服务NRC7E检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x7F, 0x10, 0x7E], expect_str="否定响应(7F 10 7E)"): return

        TestLog("INFO", "Step3", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step5", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step6", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x7F, 0x10, 0x7E], expect_str="否定响应(7F 10 7E)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC10_funRequest_10_NRC7E():
    case_name = "10服务NRC7E检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)", func_req=True): return

        TestLog("INFO", "Step2", "请求进入刷新会话(10 02)，期望无响应")
        if not service_10_check(node, 0x02, expect_data=None, expect_str="无响应", func_req=True, timeout=0.1): return

        TestLog("INFO", "Step3", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)", func_req=True): return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step5", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)", func_req=True): return

        TestLog("INFO", "Step6", "请求进入扩展会话(10 03)，期望无响应")
        if not service_10_check(node, 0x03, expect_data=None, expect_str="无响应", func_req=True, timeout=0.1): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC11_phyRequest_10_PowerOnOff():
    case_name = "10服务重新上电检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "DUT重新上电，之后等待2000ms")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        time.sleep(2)

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step6", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step7", "DUT重新上电，之后等待2000ms")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        time.sleep(2)

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step9", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step10", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step11", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step13", "DUT重新上电，之后等待2000ms")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        time.sleep(2)

        TestLog("INFO", "Step14", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return
    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC12_funRequest_10_PowerOnOff():
    case_name = "10服务重新上电检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)",
                                func_req=True): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "DUT重新上电，之后等待2000ms")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        time.sleep(2)

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)",
                                func_req=True): return

        TestLog("INFO", "Step6", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step7", "DUT重新上电，之后等待2000ms")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        time.sleep(2)

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step9", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)",
                                func_req=True): return
        TestLog("INFO", "Step10", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step11", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)",
                                func_req=True): return

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step13", "DUT重新上电，之后等待2000ms")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        time.sleep(2)

        TestLog("INFO", "Step14", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return
    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC13_phyRequest_10_HardReset():
    case_name = "10服务硬件复位检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "发送请求使DUT进行硬件复位(11 01)，之后等待2000ms")
        if not service_11_check(node, 0x01, expect_data=[0x51, 0x01], expect_str="肯定响应(51 01)"): return
        time.sleep(2)

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step6", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step10", "发送请求使DUT进行硬件复位(11 01)，之后等待2000ms")
        if not service_11_check(node, 0x01, expect_data=[0x51, 0x01], expect_str="肯定响应(51 01)"): return
        time.sleep(2)

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC14_funRequest_10_HardReset():
    case_name = "10服务硬件复位检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)", func_req=True): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送请求使DUT进行硬件复位(11 01)，之后等待2000ms")
        if not service_11_check(node, 0x01, expect_data=[0x51, 0x01], expect_str="肯定响应(51 01)"): return
        time.sleep(2)

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)", func_req=True): return

        TestLog("INFO", "Step6", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step7", "发送请求使DUT进行硬件复位(11 01)，之后等待2000ms")
        if not service_11_check(node, 0x01, expect_data=[0x51, 0x01], expect_str="肯定响应(51 01)"): return
        time.sleep(2)

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step9", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)", func_req=True): return

        TestLog("INFO", "Step10", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step11", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)", func_req=True): return

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step13", "发送请求使DUT进行硬件复位(11 01)，之后等待2000ms")
        if not service_11_check(node, 0x01, expect_data=[0x51, 0x01], expect_str="肯定响应(51 01)"): return
        time.sleep(2)

        TestLog("INFO", "Step14", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return


    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC15_phyRequest_10_NRCPriorityCheck():
    case_name = "10服务NRC优先级检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "触发NRC22的条件之一并发送10 02请求，如满足条件则对10 02请求返回NRC=0x22的否定响应")
        conditions = UDSTestParams.get_nrc22_conditions_for_service(0x10)
        if conditions:
            condition = conditions[0]
            if not start_nrc22_condition(condition): return
            try:
                if not service_10_check(node, 0x02, expect_data=[0x7F, 0x10, 0x22], expect_str="否定响应(7F 10 22)"): return
            finally:
                stop_nrc22_condition(condition)
        else:
            TestLog("WARNING", "Step4", "未配置10服务可执行的NRC22条件，跳过NRC22优先级子步骤")

        TestLog("INFO", "Step5", "发送10请求(10)")
        if not service_10_check(node, None, expect_data=[0x7F, 0x10, 0x13], expect_str="NRC=0x13的否定响应(7F 10 13)"): return

        TestLog("INFO", "Step6", "发送10请求(10 04)")
        if not service_10_check(node, 0x04, expect_data=[0x7F, 0x10, 0x12], expect_str="NRC=0x13的否定响应(7F 10 12)"): return

        TestLog("INFO", "Step7", "发送10请求(10 01 00)")
        if not service_10_check(node, 0x01, dl=3, expect_data=[0x7F, 0x10, 0x13], expect_str="否定响应(7F 10 13)"): return

        TestLog("INFO", "Step7", "发送10请求(10 04 00)")
        if not service_10_check(node, 0x04, dl=3, expect_data=[0x7F, 0x10, 0x12], expect_str="否定响应(7F 10 12)"): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC16_funRequest_10_NRCPriorityCheck():
    case_name = "10服务NRC优先级检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)", func_req=True): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)", func_req=True): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "触发NRC22的条件之一并发送10 02请求，如满足条件则对10 02请求返回NRC=0x22的否定响应")
        conditions = UDSTestParams.get_nrc22_conditions_for_service(0x10)
        if conditions:
            condition = conditions[0]
            if not start_nrc22_condition(condition): return
            try:
                if not service_10_check(node, 0x02, expect_data=[0x7F, 0x10, 0x22], expect_str="否定响应(7F 10 22)", func_req=True): return
            finally:
                stop_nrc22_condition(condition)
        else:
            TestLog("WARNING", "Step4", "未配置10服务可执行的NRC22条件，跳过NRC22优先级子步骤")

        TestLog("INFO", "Step5", "发送10请求(10)")
        if not service_10_check(node, None, expect_data=[0x7F, 0x10, 0x13], expect_str="NRC=0x13的否定响应(7F 10 13)", func_req=True): return

        TestLog("INFO", "Step6", "发送10请求(10 04)")
        if not service_10_check(node, 0x04, expect_data=[0x7F, 0x10, 0x12], expect_str="NRC=0x13的否定响应(7F 10 12)", func_req=True): return

        TestLog("INFO", "Step7", "发送10请求(10 01 00)")
        if not service_10_check(node, 0x01, dl=3, expect_data=[0x7F, 0x10, 0x13], expect_str="否定响应(7F 10 13)", func_req=True): return

        TestLog("INFO", "Step7", "发送10请求(10 04 00)")
        if not service_10_check(node, 0x04, dl=3, expect_data=[0x7F, 0x10, 0x12], expect_str="否定响应(7F 10 12)", func_req=True): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return


    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC1_phyRequest_11_Positive():
    """
    11服务肯定响应与功能检查(物理寻址)
    """
    case_name = "11服务肯定响应与功能检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        reset_time = P.DiagServiceInfo.ResetTime / 1000

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        # Step1: 若默认会话下不支持物理寻址11 01请求，跳转至Step10
        if P.DiagServiceInfo.SID11_DefaultSession:
            TestLog("INFO", "Step1", "默认会话支持11服务，执行默认会话测试")

            TestLog("INFO", "Step2", "进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step3", "发送11 01硬复位请求(物理寻址)")
            if not service_11_check(node, 0x01, [0x51, 0x01], "肯定响应(51 01)"): return

            TestLog("INFO", "Step4", f"等待复位完成 {reset_time}s")
            time.sleep(reset_time)

            TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

            TestLog("INFO", "Step6", "进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step7", "发送11 81带抑制位的硬复位请求(物理寻址)")
            node.Service_0x11_ECUReset(0x81)

            TestLog("INFO", "Step8", f"等待复位完成 {reset_time}s")
            time.sleep(reset_time)

            TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return
        else:
            TestLog("INFO", "Step1", "默认会话不支持11服务，跳过Step2-9，跳转至Step10")

        # Step10: 进入扩展会话测试
        TestLog("INFO", "Step10", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step11", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step13", "发送11 01硬复位请求(物理寻址)")
        if not service_11_check(node, 0x01, [0x51, 0x01], "肯定响应(51 01)"): return

        TestLog("INFO", "Step14", f"等待复位完成 {reset_time}s")
        time.sleep(reset_time)

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step16", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step17", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step18", "发送11 81带抑制位的硬复位请求(物理寻址)")
        node.Service_0x11_ECUReset(0x81)

        TestLog("INFO", "Step19", f"等待复位完成 {reset_time}s")
        time.sleep(reset_time)

        TestLog("INFO", "Step20", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        # Step21-34: 刷新会话测试
        TestLog("INFO", "Step21", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step22", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step23", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step24", "进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        time.sleep(1)

        TestLog("INFO", "Step25", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step26", "发送11 01硬复位请求(物理寻址)")
        if not service_11_check(node, 0x01, [0x51, 0x01], "肯定响应(51 01)"): return

        TestLog("INFO", "Step27", f"等待复位完成 {reset_time}s")
        time.sleep(reset_time)

        TestLog("INFO", "Step28", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step29", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step30", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step31", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step32", "进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        time.sleep(1)

        TestLog("INFO", "Step33", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step34", "发送11 81带抑制位的硬复位请求(物理寻址)")
        resp = node.Service_0x11_ECUReset(0x81)
        if resp is not None: TestLog("FAIL", "", f"期望: 无响应; 实际:收到响应"); return
        TestLog("PASS", "", f"期望: 无响应; 实际:无响应")

        TestLog("INFO", "Step35", f"等待复位完成 {reset_time}s")
        time.sleep(reset_time)

        TestLog("INFO", "Step36", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        # Step35: 若不支持11 02子功能，跳转至Step52
        if 0x02 in UDSTestParams.Services11SubFunSupportList:
            TestLog("INFO", "Step37", "11 02在支持列表中，执行Step36-51")

            TestLog("INFO", "Step38", "进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step39", "进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            TestLog("INFO", "Step40", "发送11 02 KeyOffOnReset请求(物理寻址)")
            if not service_11_check(node, 0x02, [0x51, 0x02], "肯定响应(51 02)"): return

            TestLog("INFO", "Step41", f"等待复位完成 {reset_time}s")
            time.sleep(reset_time)

            TestLog("INFO", "Step41", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

            TestLog("INFO", "Step42", "进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step43", "进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            TestLog("INFO", "Step44", "发送11 82带抑制位的KeyOffOnReset请求(物理寻址)")
            resp = node.Service_0x11_ECUReset(0x82)
            if resp is not None: TestLog("FAIL", "", f"期望: 无响应; 实际:收到响应"); return
            TestLog("PASS", "", f"期望: 无响应; 实际:无响应")

            TestLog("INFO", "Step45", f"等待复位完成 {reset_time}s")
            time.sleep(reset_time)

            TestLog("INFO", "Step46", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

            #11 02 刷新会话测试
            TestLog("INFO", "Step47", "进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step48", "进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            TestLog("INFO", "Step49", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step50", "进入刷新会话(10 02)")
            if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

            time.sleep(1)

            TestLog("INFO", "Step51", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

            TestLog("INFO", "Step52", "发送11 02 KeyOffOnReset请求(物理寻址)")
            if not service_11_check(node, 0x02, [0x51, 0x02], "肯定响应(51 02)"): return

            TestLog("INFO", "Step53", f"等待复位完成 {reset_time}s")
            time.sleep(reset_time)

            TestLog("INFO", "Step54", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

            TestLog("INFO", "Step55", "进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step56", "进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            TestLog("INFO", "Step57", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step58", "进入刷新会话(10 02)")
            if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

            time.sleep(1)

            TestLog("INFO", "Step59", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

            TestLog("INFO", "Step60", "发送11 82带抑制位的KeyOffOnReset请求(物理寻址)")
            resp = node.Service_0x11_ECUReset(0x82)
            if resp is not None: TestLog("FAIL", "", f"期望: 无响应; 实际:收到响应"); return
            TestLog("PASS", "", f"期望: 无响应; 实际:无响应")

            TestLog("INFO", "Step61", f"等待复位完成 {reset_time}s")
            time.sleep(reset_time)

            TestLog("INFO", "Step62", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return
        else:
            TestLog("INFO", "Step63", "11 02 KeyOffOnReset 不在支持列表中，跳转至Step61")

        # Step61: 若不支持11 03子功能，测试结束
        if 0x03 in UDSTestParams.Services11SubFunSupportList:
            TestLog("INFO", "Step64", "11 03在支持列表中，执行Step62-86")

            TestLog("INFO", "Step65", "进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step66", "进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            TestLog("INFO", "Step67", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step68", "发送11 03 SoftReset请求(物理寻址)")
            if not service_11_check(node, 0x03, [0x51, 0x03], "肯定响应(51 03)"): return

            TestLog("INFO", "Step69", f"等待复位完成 {reset_time}s")
            time.sleep(reset_time)

            TestLog("INFO", "Step70", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

            TestLog("INFO", "Step71", "进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            TestLog("INFO", "Step72", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step73", "发送11 83带抑制位的SoftReset请求(物理寻址)")
            resp = node.Service_0x11_ECUReset(0x83)
            if resp is not None: TestLog("FAIL", "", f"期望: 无响应; 实际:收到响应"); return
            TestLog("PASS", "", f"期望: 无响应; 实际:无响应")

            TestLog("INFO", "Step74", f"等待复位完成 {reset_time}s")
            time.sleep(reset_time)

            TestLog("INFO", "Step75", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

            #11 03 刷新会话测试
            TestLog("INFO", "Step76", "进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step77", "进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            TestLog("INFO", "Step78", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step79", "进入刷新会话(10 02)")
            if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

            time.sleep(1)

            TestLog("INFO", "Step80", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

            TestLog("INFO", "Step81", "发送11 03 SoftReset请求(物理寻址)")
            if not service_11_check(node, 0x03, [0x51, 0x03], "肯定响应(51 03)"): return

            TestLog("INFO", "Step82", f"等待复位完成 {reset_time}s")
            time.sleep(reset_time)

            TestLog("INFO", "Step83", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

            TestLog("INFO", "Step84", "进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step85", "进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            TestLog("INFO", "Step86", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step87", "进入刷新会话(10 02)")
            if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

            time.sleep(1)

            TestLog("INFO", "Step88", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

            TestLog("INFO", "Step89", "发送11 83带抑制位的SoftReset请求(物理寻址)")
            resp = node.Service_0x11_ECUReset(0x83)
            if resp is not None: TestLog("FAIL", "", f"期望: 无响应; 实际:收到响应"); return
            TestLog("PASS", "", f"期望: 无响应; 实际:无响应")

            TestLog("INFO", "Step90", f"等待复位完成 {reset_time}s")
            time.sleep(reset_time)

            TestLog("INFO", "Step91", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return
        else:
            TestLog("INFO", "Step61", "11 03 SoftReset 不在支持列表中，测试用例结束")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC2_funRequest_11_Positive():
    """
    11服务肯定响应与功能检查(功能寻址)
    """
    case_name = "11服务肯定响应与功能检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        reset_time = P.DiagServiceInfo.ResetTime / 1000

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送11 01硬复位请求(功能寻址)")
        if not service_11_check(node, 0x01, [0x51, 0x01], "肯定响应(51 01)", func_req=True): return

        TestLog("INFO", "Step4", f"等待复位完成 {reset_time}s")
        time.sleep(reset_time)

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step6", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step8", "发送11 81带抑制位的硬复位请求(功能寻址)")
        node.Service_0x11_ECUReset(0x81, func_req=True)

        TestLog("INFO", "Step9", f"等待复位完成 {reset_time}s")
        time.sleep(reset_time)

        TestLog("INFO", "Step10", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step11", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step12", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step13", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step14", "发送11 01硬复位请求(功能寻址)")
        if not service_11_check(node, 0x01, [0x51, 0x01], "肯定响应(51 01)", func_req=True): return

        TestLog("INFO", "Step15", f"等待复位完成 {reset_time}s")
        time.sleep(reset_time)

        TestLog("INFO", "Step16", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step17", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step18", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step19", "发送11 81带抑制位的硬复位请求(功能寻址)")
        node.Service_0x11_ECUReset(0x81, func_req=True)

        TestLog("INFO", "Step20", f"等待复位完成 {reset_time}s")
        time.sleep(reset_time)

        TestLog("INFO", "Step21", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step22", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step23", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step18", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step24", "进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        time.sleep(1)

        TestLog("INFO", "Step25", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step26", "发送11 01硬复位请求(功能寻址)")
        if not service_11_check(node, 0x01, [0x51, 0x01], "肯定响应(51 01)", func_req=True): return

        TestLog("INFO", "Step27", f"等待复位完成 {reset_time}s")
        time.sleep(reset_time)

        TestLog("INFO", "Step28", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step29", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step30", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step18", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step31", "进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        time.sleep(1)

        TestLog("INFO", "Step32", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step33", "发送11 81带抑制位的硬复位请求(功能寻址)")
        node.Service_0x11_ECUReset(0x81, func_req=True)

        TestLog("INFO", "Step34", f"等待复位完成 {reset_time}s")
        time.sleep(reset_time)

        TestLog("INFO", "Step35", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        # 11 02 (KeyOffOnReset) 测试
        if 0x02 in UDSTestParams.Services11SubFunSupportList:
            TestLog("INFO", "Step36", "11 02在支持列表中，执行Step37-71")

            TestLog("INFO", "Step37", "进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step38", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

            TestLog("INFO", "Step39", "发送11 02 KeyOffOnReset请求(功能寻址)")
            if not service_11_check(node, 0x02, [0x51, 0x02], "肯定响应(51 02)", func_req=True): return

            TestLog("INFO", "Step40", f"等待复位完成 {reset_time}s")
            time.sleep(reset_time)

            TestLog("INFO", "Step41", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

            TestLog("INFO", "Step42", "进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step43", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

            TestLog("INFO", "Step44", "发送11 82带抑制位的KeyOffOnReset请求(功能寻址)")
            node.Service_0x11_ECUReset(0x82, func_req=True)

            TestLog("INFO", "Step45", f"等待复位完成 {reset_time}s")
            time.sleep(reset_time)

            TestLog("INFO", "Step46", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

            # 11 02 扩展会话测试
            TestLog("INFO", "Step47", "进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step48", "进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            TestLog("INFO", "Step49", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step50", "发送11 02 KeyOffOnReset请求(功能寻址)")
            if not service_11_check(node, 0x02, [0x51, 0x02], "肯定响应(51 02)", func_req=True): return

            TestLog("INFO", "Step51", f"等待复位完成 {reset_time}s")
            time.sleep(reset_time)

            TestLog("INFO", "Step52", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

            TestLog("INFO", "Step53", "进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            TestLog("INFO", "Step54", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step55", "发送11 82带抑制位的KeyOffOnReset请求(功能寻址)")
            node.Service_0x11_ECUReset(0x82, func_req=True)

            TestLog("INFO", "Step56", f"等待复位完成 {reset_time}s")
            time.sleep(reset_time)

            TestLog("INFO", "Step57", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

            # 11 02 刷新会话测试
            TestLog("INFO", "Step58", "进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step59", "进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            TestLog("INFO", "Step18", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step60", "进入刷新会话(10 02)")
            if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

            time.sleep(1)

            TestLog("INFO", "Step61", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

            TestLog("INFO", "Step62", "发送11 02 KeyOffOnReset请求(功能寻址)")
            if not service_11_check(node, 0x02, [0x51, 0x02], "肯定响应(51 02)", func_req=True): return

            TestLog("INFO", "Step63", f"等待复位完成 {reset_time}s")
            time.sleep(reset_time)

            TestLog("INFO", "Step64", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

            TestLog("INFO", "Step65", "进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step66", "进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            TestLog("INFO", "Step18", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step67", "进入刷新会话(10 02)")
            if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

            time.sleep(1)

            TestLog("INFO", "Step68", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

            TestLog("INFO", "Step69", "发送11 82带抑制位的KeyOffOnReset请求(功能寻址)")
            node.Service_0x11_ECUReset(0x82, func_req=True)

            TestLog("INFO", "Step70", f"等待复位完成 {reset_time}s")
            time.sleep(reset_time)

            TestLog("INFO", "Step71", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return
        else:
            TestLog("INFO", "Step36", "11 02 KeyOffOnReset 不在支持列表中，跳转至Step72")

        if 0x03 in UDSTestParams.Services11SubFunSupportList:
            TestLog("INFO", "Step72", "11 03在支持列表中，执行Step73-107")

            # 11 03 默认会话测试
            TestLog("INFO", "Step73", "进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step74", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

            TestLog("INFO", "Step75", "发送11 03 SoftReset请求(功能寻址)")
            if not service_11_check(node, 0x03, [0x51, 0x03], "肯定响应(51 03)", func_req=True): return

            TestLog("INFO", "Step76", f"等待复位完成 {reset_time}s")
            time.sleep(reset_time)

            TestLog("INFO", "Step77", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

            TestLog("INFO", "Step78", "进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step79", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

            TestLog("INFO", "Step80", "发送11 83带抑制位的SoftReset请求(功能寻址)")
            node.Service_0x11_ECUReset(0x83, func_req=True)

            TestLog("INFO", "Step81", f"等待复位完成 {reset_time}s")
            time.sleep(reset_time)

            TestLog("INFO", "Step82", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

            # 11 03 扩展会话测试
            TestLog("INFO", "Step83", "进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step84", "进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            TestLog("INFO", "Step85", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step86", "发送11 03 SoftReset请求(功能寻址)")
            if not service_11_check(node, 0x03, [0x51, 0x03], "肯定响应(51 03)", func_req=True): return

            TestLog("INFO", "Step87", f"等待复位完成 {reset_time}s")
            time.sleep(reset_time)

            TestLog("INFO", "Step88", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

            TestLog("INFO", "Step89", "进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            TestLog("INFO", "Step90", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step91", "发送11 83带抑制位的SoftReset请求(功能寻址)")
            node.Service_0x11_ECUReset(0x83, func_req=True)

            TestLog("INFO", "Step92", f"等待复位完成 {reset_time}s")
            time.sleep(reset_time)

            TestLog("INFO", "Step93", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

            # 11 03 刷新会话测试
            TestLog("INFO", "Step94", "进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step95", "进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            TestLog("INFO", "Step18", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step96", "进入刷新会话(10 02)")
            if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

            time.sleep(1)

            TestLog("INFO", "Step97", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

            TestLog("INFO", "Step98", "发送11 03 SoftReset请求(功能寻址)")
            if not service_11_check(node, 0x03, [0x51, 0x03], "肯定响应(51 03)", func_req=True): return

            TestLog("INFO", "Step99", f"等待复位完成 {reset_time}s")
            time.sleep(reset_time)

            TestLog("INFO", "Step100", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

            TestLog("INFO", "Step101", "进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step102", "进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            TestLog("INFO", "Step18", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step103", "进入刷新会话(10 02)")
            if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

            time.sleep(1)

            TestLog("INFO", "Step104", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

            TestLog("INFO", "Step105", "发送11 83带抑制位的SoftReset请求(功能寻址)")
            node.Service_0x11_ECUReset(0x83, func_req=True)

            TestLog("INFO", "Step106", f"等待复位完成 {reset_time}s")
            time.sleep(reset_time)

            TestLog("INFO", "Step107", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return
        else:
            TestLog("INFO", "Step72", "11 03 SoftReset 不在支持列表中，测试用例结束")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC3_phyRequest_11_NRC12():
    """
    11服务NRC12检查(物理寻址)
    """
    case_name = "11服务NRC12检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    min_sn, max_sn = UDSTestParams.MinSubID, UDSTestParams.MaxSubID
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        time.sleep(1)

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4~7", "遍历不支持的子功能，验证返回NRC12")
        for sn in range(min_sn, max_sn + 1):
            if sn in UDSTestParams.Services11SubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)}，在11服务支持的范围内，跳过该SN")
                continue
            TestLog("INFO", "", f"SN={hex(sn)}，不在11服务支持的范围内，测试该SN")
            if not service_11_check(node, sn, [0x7F, 0x11, 0x12], "否定响应(7F 11 12)"): return

        time.sleep(1)

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step9", "进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        time.sleep(1)

        TestLog("INFO", "Step10", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step11~14", "遍历不支持的子功能，验证返回NRC12")
        for sn in range(min_sn, max_sn + 1):
            if sn in UDSTestParams.Services11SubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)}，在11服务支持的范围内，跳过该SN")
                continue
            TestLog("INFO", "", f"SN={hex(sn)}，不在11服务支持的范围内，测试该SN")
            if not service_11_check(node, sn, [0x7F, 0x11, 0x12], "否定响应(7F 11 12)"): return

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC4_funRequest_11_NRC12():
    """
    11服务NRC12检查(功能寻址)
    """
    case_name = "11服务NRC12检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    min_sn, max_sn = UDSTestParams.MinSubID, UDSTestParams.MaxSubID
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        # 默认会话测试
        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3~6", "遍历不支持的子功能，验证无响应(功能寻址)")
        for sn in range(min_sn, max_sn + 1):
            if sn in UDSTestParams.Services11SubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)}，在11服务支持的范围内，跳过该SN")
                continue
            TestLog("INFO", "", f"SN={hex(sn)}，不在11服务支持的范围内，测试该SN")
            resp = node.Service_0x11_ECUReset(sn, func_req=True, timeout=0.1)
            if resp is not None:
                TestLog("FAIL", "", f"期望: 无响应; 实际:收到响应")
            else:
                TestLog("PASS", "", f"期望: 无响应; 实际:无响应")

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        # 扩展会话测试
        TestLog("INFO", "Step8", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step9", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step10", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step11~14", "遍历不支持的子功能，验证无响应(功能寻址)")
        for sn in range(min_sn, max_sn + 1):
            if sn in UDSTestParams.Services11SubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)}，在11服务支持的范围内，跳过该SN")
                continue
            TestLog("INFO", "", f"SN={hex(sn)}，不在11服务支持的范围内，测试该SN")
            resp = node.Service_0x11_ECUReset(sn, func_req=True, timeout=0.1)
            if resp is not None:
                TestLog("FAIL", "", f"期望: 无响应; 实际:收到响应")
            else:
                TestLog("PASS", "", f"期望: 无响应; 实际:无响应")

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        # 刷新会话测试
        TestLog("INFO", "Step16", "进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        time.sleep(1)

        TestLog("INFO", "Step17", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step18~21", "遍历不支持的子功能，验证无响应(功能寻址)")
        for sn in range(min_sn, max_sn + 1):
            if sn in UDSTestParams.Services11SubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)}，在11服务支持的范围内，跳过该SN")
                continue
            TestLog("INFO", "", f"SN={hex(sn)}，不在11服务支持的范围内，测试该SN")
            resp = node.Service_0x11_ECUReset(sn, func_req=True, timeout=0.1)
            if resp is not None:
                TestLog("FAIL", "", f"期望: 无响应; 实际:收到响应")
            else:
                TestLog("PASS", "", f"期望: 无响应; 实际:无响应")

        TestLog("INFO", "Step22", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC5_phyRequest_11_NRC13():
    """
    11服务NRC13检查(物理寻址)
    """
    case_name = "11服务NRC13检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step6", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "发送长度过短的11请求(DL=1，只有SID)")
        if not service_11_check(node, None, [0x7F, 0x11, 0x13], "NRC=0x13的否定响应(7F 11 13)"): return

        TestLog("INFO", "Step9", "发送长度过长的11请求(DL=3~7)")
        for dl in range(3, 8):
            TestLog("INFO", "", f"发送DL={dl}的请求: 11 01 字节填充")
            if not service_11_check(node, 0x01, [0x7F, 0x11, 0x13], f"DL={dl} NRC=0x13的否定响应(7F 11 13)", dl=dl, dl_padding=0x00): return

        TestLog("INFO", "Step10", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        # 刷新会话模式下测试
        TestLog("INFO", "Step11", "进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        time.sleep(1)

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step13", "发送长度过短的11请求(DL=1，只有SID)")
        if not service_11_check(node, None, [0x7F, 0x11, 0x13], "NRC=0x13的否定响应(7F 11 13)"): return

        TestLog("INFO", "Step14", "发送长度过长的11请求(DL=3~7)")
        for dl in range(3, 8):
            TestLog("INFO", "", f"发送DL={dl}的请求: 11 01 字节填充")
            if not service_11_check(node, 0x01, [0x7F, 0x11, 0x13], f"DL={dl} NRC=0x13的否定响应(7F 11 13)", dl=dl, dl_padding=0x00): return

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC6_funRequest_11_NRC13():
    """
    11服务NRC13检查(功能寻址)
    """
    case_name = "11服务NRC13检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        # 默认会话测试
        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送长度过短的11请求(DL=1，只有SID)(功能寻址)")
        if not service_11_check(node, None, [0x7F, 0x11, 0x13], "否定响应(7F 11 13)", func_req=True, timeout=2): return

        TestLog("INFO", "Step4", "发送长度过长的11请求(DL=3~7)(功能寻址)")
        for dl in range(3, 8):
            TestLog("INFO", "", f"发送DL={dl}的请求: 11 01 字节填充")
            if not service_11_check(node, 0x01, [0x7F, 0x11, 0x13], f"DL={dl} 否定响应(7F 11 13)", func_req=True, dl=dl, dl_padding=0x00, timeout=2): return

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        # 扩展会话测试
        TestLog("INFO", "Step6", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "发送长度过短的11请求(DL=1，只有SID)(功能寻址)")
        if not service_11_check(node, None, [0x7F, 0x11, 0x13], "否定响应(7F 11 13)", func_req=True, timeout=2): return

        TestLog("INFO", "Step9", "发送长度过长的11请求(DL=3~7)(功能寻址)")
        for dl in range(3, 8):
            TestLog("INFO", "", f"发送DL={dl}的请求: 11 01 字节填充")
            if not service_11_check(node, 0x01, [0x7F, 0x11, 0x13], f"DL={dl} 否定响应(7F 11 13)", func_req=True, dl=dl, dl_padding=0x00, timeout=2): return

        TestLog("INFO", "Step10", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        # 刷新会话测试
        TestLog("INFO", "Step11", "进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        time.sleep(1)

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step13", "发送长度过短的11请求(DL=1，只有SID)(功能寻址)")
        if not service_11_check(node, None, [0x7F, 0x11, 0x13], "否定响应(7F 11 13)", func_req=True, timeout=2): return

        TestLog("INFO", "Step14", "发送长度过长的11请求(DL=3~7)(功能寻址)")
        for dl in range(3, 8):
            TestLog("INFO", "", f"发送DL={dl}的请求: 11 01 + {dl-2}字节填充")
            if not service_11_check(node, 0x01, [0x7F, 0x11, 0x13], f"DL={dl} 否定响应(7F 11 13)", func_req=True, dl=dl, dl_padding=0x00, timeout=2): return

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC7_phyRequest_11_NRC22():
    """
    11服务NRC22检查(物理寻址)
    """
    case_name = "11服务NRC22检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x11)
        if len(condition_list) == 0:
            TestLog("WARNING", case_name, "未配置11服务可执行的NRC22条件，跳过该测试")
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "遍历NRC22条件，验证返回NRC22")
        for condition in condition_list:
            TestLog("INFO", "", f"设置NRC22条件: {getattr(condition, 'ConditionName', 'unknown')}")
            if not start_nrc22_condition(condition): continue
            try:
                service_11_check(node, 0x01, [0x7F, 0x11, 0x22], "NRC22响应(7F 11 22)")
            finally:
                stop_nrc22_condition(condition)
            time.sleep(1)

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        # 刷新会话测试
        TestLog("INFO", "Step6", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step7", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step9", "进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        time.sleep(1)

        TestLog("INFO", "Step10", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step11", "遍历NRC22条件，验证返回NRC22")
        for condition in condition_list:
            TestLog("INFO", "", f"设置NRC22条件: {getattr(condition, 'ConditionName', 'unknown')}")
            if not start_nrc22_condition(condition): continue
            try:
                service_11_check(node, 0x01, [0x7F, 0x11, 0x22], "NRC22响应(7F 11 22)")
            finally:
                stop_nrc22_condition(condition)
            time.sleep(1)

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC8_funRequest_11_NRC22():
    """
    11服务NRC22检查(功能寻址)
    """
    case_name = "11服务NRC22检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x11)
        if len(condition_list) == 0:
            TestLog("WARNING", case_name, "未配置11服务可执行的NRC22条件，跳过该测试")
            return

        # 扩展会话测试
        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)", func_req=True): return

        TestLog("INFO", "Step2", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)", func_req=True): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "遍历NRC22条件，验证返回NRC22(功能寻址)")
        for condition in condition_list:
            TestLog("INFO", "", f"设置NRC22条件: {getattr(condition, 'ConditionName', 'unknown')}")
            if not start_nrc22_condition(condition): continue
            try:
                service_11_check(node, 0x01, [0x7F, 0x11, 0x22], "否定响应(7F 11 22)", func_req=True)
            finally:
                stop_nrc22_condition(condition)
            time.sleep(1)

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        # 刷新会话测试
        TestLog("INFO", "Step6", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)", func_req=True): return

        TestLog("INFO", "Step7", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)", func_req=True): return

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step9", "进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=True): return

        time.sleep(1)

        TestLog("INFO", "Step10", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step11", "遍历NRC22条件，验证返回NRC22(功能寻址)")
        for condition in condition_list:
            TestLog("INFO", "", f"设置NRC22条件: {getattr(condition, 'ConditionName', 'unknown')}")
            if not start_nrc22_condition(condition): continue
            try:
                service_11_check(node, 0x01, [0x7F, 0x11, 0x22], "否定响应(7F 11 22)", func_req=True)
            finally:
                stop_nrc22_condition(condition)
            time.sleep(1)

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC9_phyRequest_11_NRC7F():
    """
    11服务NRC7F检查(物理寻址)
    """
    case_name = "11服务NRC7F检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        # TestLog("INFO", "Step3~6", "默认会话不支持11服务，遍历SN=0x00~0xFF测试NRC7F响应")
        # for sn in range(0x00, 0x100):
        #     TestLog("INFO", "", f"发送11 {hex(sn)[2:].zfill(2).upper()}复位请求(物理寻址)")
        #     if not service_11_check(node, sn, [0x7F, 0x11, 0x7F], "NRC7F响应(7F 11 7F)"): return
        TestLog("INFO", "", "所有会话下，11服务的支持情况一致，没有NRC7F的检测条件")

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC10_phyRequest_11_NRCPriorityCheck():
    """
    11服务NRC优先级检查(物理寻址)
    """
    case_name = "11服务NRC优先级检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x11)
        condition = condition_list[0] if len(condition_list) > 0 else None
        condition_active = False
        try:
            if condition is not None:
                TestLog("INFO", "Step3", f"触发NRC22条件并发送11 01请求: {getattr(condition, 'ConditionName', 'unknown')}")
                if not start_nrc22_condition(condition): return
                condition_active = True
                service_11_check(node, 0x01, [0x7F, 0x11, 0x22], "NRC22响应(7F 11 22)")
            else:
                TestLog("WARNING", "Step3", "未配置11服务可执行的NRC22条件，跳过NRC22测试")

            TestLog("INFO", "Step4", "发送长度错误的11请求(DL=1)，验证NRC13优先级")
            service_11_check(node, None, [0x7F, 0x11, 0x13], "NRC13响应(7F 11 13)", timeout=2)

            TestLog("INFO", "Step5", "发送不支持的子功能请求(11 04)，验证NRC12优先级")
            service_11_check(node, 0x04, [0x7F, 0x11, 0x12], "NRC12响应(7F 11 12)")

            TestLog("INFO", "Step6", "发送11 01 00请求(DL=3)，验证NRC13优先级")
            service_11_check(node, 0x01, [0x7F, 0x11, 0x13], "NRC13响应(7F 11 13)", dl=3, dl_padding=0x00)

            TestLog("INFO", "Step7", "发送11 04 00请求(DL=3)，验证NRC12优先级")
            service_11_check(node, 0x04, [0x7F, 0x11, 0x12], "NRC12响应(7F 11 12)", dl=3, dl_padding=0x00)
        finally:
            if condition_active:
                stop_nrc22_condition(condition)

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC11_funRequest_11_NRCPriorityCheck():
    """
    11服务NRC优先级检查(功能寻址)
    """
    case_name = "11服务NRC优先级检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x11)
        condition = condition_list[0] if len(condition_list) > 0 else None
        condition_active = False
        try:
            if condition is not None:
                TestLog("INFO", "Step3", f"触发NRC22条件并发送11 01请求(功能寻址): {getattr(condition, 'ConditionName', 'unknown')}")
                if not start_nrc22_condition(condition): return
                condition_active = True
                service_11_check(node, 0x01, [0x7F, 0x11, 0x22], "NRC22响应(7F 11 22)", func_req=True)
            else:
                TestLog("WARNING", "Step3", "未配置11服务可执行的NRC22条件，跳过NRC22测试")

            TestLog("INFO", "Step4", "发送长度错误的11请求(DL=1)(功能寻址)，验证NRC13")
            service_11_check(node, None, [0x7F, 0x11, 0x13], "NRC13响应(7F 11 13)", func_req=True, timeout=2)

            TestLog("INFO", "Step5", "发送不支持的子功能请求(11 04)(功能寻址)，验证NRC12")
            service_11_check(node, 0x04, [0x7F, 0x11, 0x12], "NRC12响应(7F 11 12)", func_req=True)

            TestLog("INFO", "Step6", "发送11 01 00请求(DL=3)(功能寻址)，验证NRC13")
            service_11_check(node, 0x01, [0x7F, 0x11, 0x13], "NRC13响应(7F 11 13)", func_req=True, dl=3, dl_padding=0x00)

            TestLog("INFO", "Step7", "发送11 04 00请求(DL=3)(功能寻址)，验证NRC12")
            service_11_check(node, 0x04, [0x7F, 0x11, 0x12], "NRC12响应(7F 11 12)", func_req=True, dl=3, dl_padding=0x00)
        finally:
            if condition_active:
                stop_nrc22_condition(condition)

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG3_TC1_phyRequest_27_Positive():
    case_name = "27服务肯定响应与功能检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        
        # 清除错误计数器
        if not clear_27_error_timer(node): return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        time.sleep(1)

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        time.sleep(1)

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        tester_present_start(node)
        TestLog("INFO", "Step4", "等待12s")
        time.sleep(12)
        tester_present_stop()

        TestLog("INFO", "Step5", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step6", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x67, LEVEL_EXT_2], f"肯定响应(67 {LEVEL_EXT_2_STR})",
                                   alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) != 0:
            TestLog("FAIL", "", f"期望: 肯定响应且种子为全00; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子为全00; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step10", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step11", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step12", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step13", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        tester_present_start(node)
        TestLog("INFO", "Step14", "等待12s")
        time.sleep(12)
        tester_present_stop()

        TestLog("INFO", "Step15", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step16", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x67, LEVEL_PRO_12], f"肯定响应(67 {LEVEL_PRO_12_STR})",
                                   alg_type=AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step17", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step18", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) != 0:
            TestLog("FAIL", "", f"期望: 肯定响应且种子为全00; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子为全00; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step19", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC2_phyRequest_27_AlgorithmCheck():
    case_name = "27服务算法检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        
        # 清除错误计数器
        if not clear_27_error_timer(node): return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return
        time.sleep(1)

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return
        time.sleep(1)

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step5", f"发送刷新安全级算法得出的解锁密钥(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x7F, 0x27, 0x35], "否定响应(7F 27 35)",
                                   alg_type=AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step6", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step7", f"发送刷新安全级算法得出的解锁密钥(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x7F, 0x27, 0x35], "否定响应(7F 27 35)",
                                   alg_type=AlgorithmType.PROGRAMMING): return

        # TestLog("INFO", "Step8", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        # status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        # if not status: return
        #
        # seed_list = get_seed_from_27_resp(resp)
        # if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
        #     TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
        #     return
        # TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        # TestLog("INFO", "Step9", f"发送防盗安全级算法得出的解锁密钥(27 {LEVEL_EXT_2})")
        # if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x7F, 0x27, 0x36], "否定响应(7F 27 36)",
        #                            alg_type=AlgorithmType.IMMOBILIZER): return

        TestLog("INFO", "Step10", "等待10.5s(3E服务启动)")
        tester_present_start(node)
        time.sleep(10.5)
        tester_present_stop()

        TestLog("INFO", "Step11", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status:
            return

        seed_list = get_seed_from_27_resp(resp)
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step12", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT_2})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x67, LEVEL_EXT_2], f"肯定响应(67 {LEVEL_EXT_2_STR})",
                                   alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step13", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step14", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step15", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step16", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step17", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step18", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step19", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status:
            return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step20", f"发送扩展安全级的解锁密钥(27 {LEVEL_PRO_12})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x7F, 0x27, 0x35], f"否定响应(7F 27 35)",
                                   alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step21", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status:
            return

        seed_list = get_seed_from_27_resp(resp)
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step22", f"发送扩展安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x7F, 0x27, 0x35], f"否定响应(7F 27 35)",
                                   alg_type=AlgorithmType.EXTENDED): return

        # TestLog("INFO", "Step23", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        # status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        # if not status:
        #     return
        #
        # seed_list = get_seed_from_27_resp(resp)
        # if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
        #     TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
        #     return
        # TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        # TestLog("INFO", "Step24", f"发送防盗安全级的解锁密钥(27 {LEVEL_PRO_12})")
        # if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x7F, 0x27, 0x36], f"否定响应(7F 27 36)",
        #                            alg_type=AlgorithmType.IMMOBILIZER): return

        TestLog("INFO", "Step25", "等待10.5s(3E服务启动)")
        tester_present_start(node)
        time.sleep(10.5)
        tester_present_stop()

        TestLog("INFO", "Step26", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status:
            return

        seed_list = get_seed_from_27_resp(resp)
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step27", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x67, LEVEL_PRO_12], f"肯定响应(67 {LEVEL_PRO_12_STR})",
                                   alg_type=AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step28", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status:
            return

        seed_list = get_seed_from_27_resp(resp)
        if sum(seed_list) != 0:
            TestLog("FAIL", "", f"期望: 肯定响应且种子是全00; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子是全00; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step29", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC3_phyRequest_27_NRC37():
    case_name = "27服务切换会话延时机制与锁定检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        
        # 清除错误计数器
        if not clear_27_error_timer(node): return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        sl_time().sleep(int(1*1000))

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        sl_time().sleep(int(1*1000))

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step5", f"发送错误的扩展安全级的解锁密钥(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x7F, 0x27, 0x35], "否定响应(7F 27 35)",
                                   alg_type=AlgorithmType.EXTENDED_ERROR): return

        TestLog("INFO", "Step6", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step7", f"发送错误的扩展安全级的解锁密钥(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x7F, 0x27, 0x35], "否定响应(7F 27 35)",
                                   alg_type=AlgorithmType.EXTENDED_ERROR): return

        TestLog("INFO", "Step8", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step9", f"发送错误的扩展安全级的解锁密钥(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x7F, 0x27, 0x36], "否定响应(7F 27 36)",
                                   alg_type=AlgorithmType.EXTENDED_ERROR): return

        TestLog("INFO", "Step10", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)")
        if not status: return

        TestLog("INFO", "Step11", f"等待9s(3E服务启动)")
        tester_present_start(node)
        sl_time().sleep(int(9*1000))
        tester_present_stop()

        TestLog("INFO", "Step12", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)")
        if not status: return

        TestLog("INFO", "Step13", f"等待1s(3E服务启动)")
        tester_present_start(node)
        sl_time().sleep(int(1*1000))
        tester_present_stop()

        TestLog("INFO", "Step14", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step15", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x67, LEVEL_EXT_2], f"肯定响应(67 {LEVEL_EXT_2_STR})",
                                   alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step16", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step17", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step18", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step19", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step20", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step21", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return
        
        tester_present_start(node)
        time.sleep(15)
        tester_present_stop()

        TestLog("INFO", "Step22", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status:
            return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step23", f"发送扩展安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x7F, 0x27, 0x35], f"否定响应(7F 27 35)",
                                   alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step24", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status:
            return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step25", f"发送扩展安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x7F, 0x27, 0x35], f"否定响应(7F 27 35)",
                                   alg_type=AlgorithmType.EXTENDED): return

        # TestLog("INFO", "Step26", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        # status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        # if not status:
        #     return
        #
        # seed_list = get_seed_from_27_resp(resp)
        # TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        # if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
        #     TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
        #     return
        # TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
        #
        # TestLog("INFO", "Step27", f"发送防盗安全级的解锁密钥(27 {LEVEL_PRO_12})")
        # if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x7F, 0x27, 0x36], f"否定响应(7F 27 36)",
        #                            alg_type=AlgorithmType.IMMOBILIZER): return
        # 
        # TestLog("INFO", "Step28", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        # status, resp = service_27_check(node, LEVEL_PRO_11, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)")
        # if not status:
        #     return

        # TestLog("INFO", "Step29", f"等待9s(3E服务启动)")
        # tester_present_start(node)
        # sl_time().sleep(int(9*1000))
        # tester_present_stop()

        # TestLog("INFO", "Step30", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        # status, resp = service_27_check(node, LEVEL_PRO_11, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)")
        # if not status:
        #     return

        TestLog("INFO", "Step31", f"等待1s(3E服务启动)")
        tester_present_start(node)
        sl_time().sleep(int(1*1000))
        tester_present_stop()

        TestLog("INFO", "Step32", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status:
            return

        seed_list = get_seed_from_27_resp(resp)
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step33", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x67, 0x12], f"肯定响应(67 12)",
                                   alg_type=AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step34", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC4_phyRequest_27_NRC12():
    case_name = "27服务NRC12检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    min_subid, max_subid = UDSTestParams.MinSubID, UDSTestParams.MaxSubID
    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        
        # 清除错误计数器
        if not clear_27_error_timer(node): return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        time.sleep(1)

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        time.sleep(1)

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "令SN=0x00")
        TestLog("INFO", "Step5", "如果SN为支持的物理寻址子功能，则SN+=1，直到不支持的物理寻址子功能")
        for subid in range(min_subid, max_subid + 1):
            if subid in UDSTestParams.Services27SubFunSupportList:
                # 跳过支持的SubID
                continue
            TestLog("INFO", "Step6", f"发送子功能为{hex(subid)}的27服务请求(27 {hex(subid)})")
            status, resp = service_27_check(node, subid, [0x7F, 0x27, 0x12], f"否定响应(7F 27 12)")
            if not status: return

            TestLog("INFO", "Step7", "如果SN<0xFF，SN+=1，然后跳转至步骤5")

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step9", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step10", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step12", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step13", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step14", "令SN=0x00")
        TestLog("INFO", "Step15", "如果SN为支持的物理寻址子功能，则SN+=1，直到不支持的物理寻址子功能")
        for subid in range(min_subid, max_subid + 1):
            if subid in UDSTestParams.Services27SubFunSupportList:
                # 跳过支持的SubID
                continue
            TestLog("INFO", "Step16", f"发送子功能为{hex(subid)}的27服务请求(27 {hex(subid)})")
            status, resp = service_27_check(node, subid, [0x7F, 0x27, 0x12], f"否定响应(7F 27 12)")
            if not status: return
        TestLog("INFO", "Step17", "如果SN<0xFF，SN+=1，然后跳转至步骤14")

        TestLog("INFO", "Step18", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC5_phyRequest_27_NRC13():
    case_name = "27服务NRC12检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        
        # 清除错误计数器
        if not clear_27_error_timer(node): return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        time.sleep(1)

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        time.sleep(1)

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "发送长度较短27请求")
        status, resp = service_27_check(node, None, [0x7F, 0x27, 0x13], f"否定响应(7F 27 13)")
        if not status:
            return

        TestLog("INFO", "Step5", "发送DL=3、4、5、6、7的 27 01请求，其有效数据填充部分填充0x00")
        for dl in [3, 4, 5, 6, 7]:
            TestLog("INFO", "", f"发送DL={dl}的 27 01请求")
            status, resp = service_27_check(node, LEVEL_EXT, [0x7F, 0x27, 0x13], f"否定响应(7F 27 13)", dl=dl,
                                            dl_padding=0x00)
            if not status:
                return

        TestLog("INFO", "Step6", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step7", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step8", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step10", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step12", "发送长度较短27请求")
        status, resp = service_27_check(node, None, [0x7F, 0x27, 0x13], f"否定响应(7F 27 13)")
        if not status:
            return

        TestLog("INFO", "Step13", "发送DL=3、4、5、6、7的 27 11请求，其有效数据填充部分填充0x00")
        for dl in [3, 4, 5, 6, 7]:
            TestLog("INFO", "", f"发送DL={dl}的 27 11请求")
            status, resp = service_27_check(node, 0x11, [0x7F, 0x27, 0x13], f"否定响应(7F 27 13)", dl=dl,
                                            dl_padding=0x00)
            if not status:
                return

        TestLog("INFO", "Step14", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return


    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC6_phyRequest_27_NRC24():
    case_name = "27服务NRC12检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        
        # 清除错误计数器
        if not clear_27_error_timer(node): return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        time.sleep(1)

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        time.sleep(1)

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "直接发送27 02请求")
        if not service_27_xx_check(node, LEVEL_EXT_2, [], [0x7F, 0x27, 0x24], expect_str="否定响应(7F 27 24)",
                                   alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step6", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step7", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step9", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step10", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step11", "直接发送27 12请求")
        if not service_27_xx_check(node, LEVEL_PRO_12, [], [0x7F, 0x27, 0x24], expect_str="否定响应(7F 27 24)",
                                   alg_type=AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC7_phyRequest_27_NRC7E_7F():
    case_name = "27服务NRC7E、NRC7F检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        
        # 清除错误计数器
        if not clear_27_error_timer(node): return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        time.sleep(1)

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        time.sleep(1)

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})，NRC=7E 或 12 均接受，因ECU可不支持 27 11 子功能")
        resp = node.Service_0x27_SecurityAccess(LEVEL_PRO_11)
        status_7e, msg_7e = check_expect_response(resp, [0x7F, 0x27, 0x7E])
        status_12, msg_12 = check_expect_response(resp, [0x7F, 0x27, 0x12])
        if not (status_7e or status_12):
            TestLog("FAIL", "", f"期望: NRC=7E 或 12 均接受，因ECU可不支持 27 11 子功能; 实际:{msg_7e}")
            return
        TestLog("PASS", "", f"期望: NRC=7E 或 12 均接受，因ECU可不支持 27 11 子功能; 实际:{msg_7e if status_7e else msg_12}")

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step6", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step7", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step8", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step10", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x7F, 0x27, 0x7E], f"否定响应(7F 27 7E)")
        if not status: return

        TestLog("INFO", "Step11", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        time.sleep(1)

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step13", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x7F, 0x27, 0x7F], f"否定响应(7F 27 7F)")
        if not status: return

        TestLog("INFO", "Step14", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x7F, 0x27, 0x7F], f"否定响应(7F 27 7F)")
        if not status: return

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC8_phyRequest_27_NRC22():
    case_name = "27服务NRC22检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        
        # 清除错误计数器
        if not clear_27_error_timer(node): return
        nrc22_condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x27)
        if len(nrc22_condition_list) == 0:
            TestLog("WARNING", case_name, "未配置27服务可执行的NRC22条件，跳过该测试")
            return
        condition = nrc22_condition_list[0]

        TestLog("INFO", "Step1", "已从Conditions配置确认27服务存在可执行NRC22触发条件")

        TestLog("INFO", "Step2", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        time.sleep(1)

        TestLog("INFO", "Step3", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        time.sleep(1)

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step5", f"遍历触发NRC22的所有条件并发送27 01")
        if not start_nrc22_condition(condition): return
        try:
            status, resp = service_27_check(node, LEVEL_EXT, [0x7F, 0x27, 0x22], f"否定响应(7F 27 22)")
        finally:
            stop_nrc22_condition(condition)
        if not status: return

        TestLog("INFO", "Step6", f"NRC22条件已清理，发送27 01确认可正常获取扩展安全访问种子")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, 0x01], f"肯定响应(67 01)")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step7", f"遍历触发NRC22的所有条件并发送27 02")
        if not start_nrc22_condition(condition): return
        try:
            if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x7F, 0x27, 0x22], expect_str="否定响应(7F 27 22)",
                                       alg_type=AlgorithmType.EXTENDED): return
        finally:
            stop_nrc22_condition(condition)
        if not status: return

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step9", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step10", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step12", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step13", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step14", f"遍历触发NRC22的所有条件并发送27 11")
        if not start_nrc22_condition(condition): return
        try:
            status, resp = service_27_check(node, LEVEL_PRO_11, [0x7F, 0x27, 0x22], f"否定响应(7F 27 22)")
        finally:
            stop_nrc22_condition(condition)
        if not status: return

        TestLog("INFO", "Step15", f"NRC22条件已清理，发送27 11确认可正常获取刷新安全访问种子")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return
        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step16", f"遍历触发NRC22的所有条件并发送27 12")
        if not start_nrc22_condition(condition): return
        try:
            if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x7F, 0x27, 0x22], expect_str="否定响应(7F 27 22)",
                                       alg_type=AlgorithmType.PROGRAMMING): return
        finally:
            stop_nrc22_condition(condition)
        if not status: return

        TestLog("INFO", "Step17", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC9_phyRequest_27_SessionChangeCheck():
    case_name = "27服务会话切换检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        
        # 清除错误计数器
        if not clear_27_error_timer(node): return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        time.sleep(1)

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        time.sleep(1)

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step5", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x67, LEVEL_EXT_2], f"肯定响应(67 {LEVEL_EXT_2_STR})",
                                   alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step6", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) != 0:
            TestLog("FAIL", "", f"期望: 肯定响应且种子为全00; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子为全00; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step10", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step11", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x67, LEVEL_EXT_2], f"肯定响应(67 {LEVEL_EXT_2_STR})",
                                   alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step13", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step14", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step15", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step16", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step17", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step18", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x67, LEVEL_PRO_12], f"肯定响应(67 {LEVEL_PRO_12_STR})",
                                   alg_type=AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step19", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) != 0:
            TestLog("FAIL", "", f"期望: 肯定响应且种子为全00; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子为全00; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step20", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step21", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step22", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step23", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step24", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step25", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step26", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x67, LEVEL_PRO_12], f"肯定响应(67 {LEVEL_PRO_12_STR})",
                                   alg_type=AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step27", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG3_TC10_phyRequest_27_ResetCheck():
    case_name = "27服务复位检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_5, LEVEL_PRO_5_STR = 0x05, "05"  # 刷新等级
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1

    min_subid, max_subid = UDSTestParams.MinSubID, UDSTestParams.MaxSubID
    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        
        # 清除错误计数器
        if not clear_27_error_timer(node): return

        TestLog("INFO", "Step1", "令SN=0x01")
        for sn in range(min_subid, max_subid + 1):
            if sn not in UDSTestParams.Services11SubFunSupportList:
                continue
            TestLog("INFO", "Step2", "如果SN为扩展会话状态11服务不支持的物理寻址子功能，则SN+=1，直到SN为扩展会话支持的物理寻址的子功能；如果SN=0xFF，则跳转到步骤18")

            TestLog("INFO", "Step3", "请求进入默认会话(10 01)")
            if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

            time.sleep(1)

            TestLog("INFO", "Step4", "请求进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

            time.sleep(1)

            TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                         expect_str="位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step6", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
            status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
            if not status: return

            seed_list = get_seed_from_27_resp(resp)
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
            if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
                TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
                return
            TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

            TestLog("INFO", "Step7", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT_2_STR})")
            if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x67, LEVEL_EXT_2], f"肯定响应(67 {LEVEL_EXT_2_STR})",
                                       alg_type=AlgorithmType.EXTENDED): return

            TestLog("INFO", "Step8", f"发送扩展安全级的请求种子(27 {LEVEL_EXT_STR})")
            status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
            if not status: return

            seed_list = get_seed_from_27_resp(resp)
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
            if sum(seed_list) != 0:
                TestLog("FAIL", "", f"期望: 肯定响应且种子为全00; 实际: 种子={[hex(item) for item in seed_list]}")
                return
            TestLog("PASS", "", f"期望: 肯定响应且种子为全00; 实际: 种子={[hex(item) for item in seed_list]}")

            TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                         expect_str="位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step10", "请求复位，等待2s(11 01)")
            if not service_11_check(node, 0x01, expect_data=[0x51, 0x01], expect_str="肯定响应(51 01)"): return
            time.sleep(2)

            TestLog("INFO", "Step11", "请求进入默认会话(10 01)")
            if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

            TestLog("INFO", "Step12", "请求进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

            TestLog("INFO", "Step13", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                         expect_str="位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step14", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
            status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
            if not status: return

            seed_list = get_seed_from_27_resp(resp)
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
            if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
                TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
                return
            TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

            TestLog("INFO", "Step15", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT_2_STR})")
            if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x67, LEVEL_EXT_2], f"肯定响应(67 {LEVEL_EXT_2_STR})",
                                       alg_type=AlgorithmType.EXTENDED): return

            TestLog("INFO", "Step16", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                         expect_str="位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step17", f"若SN={sn}<0xFF，SN+=1，跳转至步骤2")

        TestLog("INFO", "Step18", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step19", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step20", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step21", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step22", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step23", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x67, LEVEL_PRO_12], f"肯定响应(67 {LEVEL_PRO_12_STR})",
                                   alg_type=AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step24", f"发送刷新安全级的请求种子(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) != 0:
            TestLog("FAIL", "", f"期望: 肯定响应且种子为全00; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子为全00; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step25", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step26", f"请求复位，等待2s(11 01)")
        if not service_11_check(node, 0x01, expect_data=[0x51, 0x01], expect_str=f"肯定响应(51 01)"): return
        time.sleep(2)

        TestLog("INFO", "Step27", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step28", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step29", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                        expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step30", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step31", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step32", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step33", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x67, LEVEL_PRO_12], f"肯定响应(67 {LEVEL_PRO_12_STR})",
                                   alg_type=AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step34", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG3_TC11_phyRequest_27_PowerOnOff():
    case_name = "27服务重新上电检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_5, LEVEL_PRO_5_STR = 0x05, "05"  # 刷新等级
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        
        # 清除错误计数器
        if not clear_27_error_timer(node): return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        time.sleep(1)

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        time.sleep(1)

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step5", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x67, LEVEL_EXT_2], f"肯定响应(67 {LEVEL_EXT_2_STR})",
                                   alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step6", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) != 0:
            TestLog("FAIL", "", f"期望: 肯定响应且种子为全00; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子为全00; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "DUT重新上电")
        ctx.power_ctrl.off()
        time.sleep(3)
        ctx.power_ctrl.on()
        time.sleep(3)

        TestLog("INFO", "Step9", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step10", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step12", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step13", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x67, LEVEL_EXT_2], f"肯定响应(67 {LEVEL_EXT_2_STR})",
                                   alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step14", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step15", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step16", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step17", "编程条件检查(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step18", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step19", "编程条件检查(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step20", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step21", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x67, LEVEL_PRO_12], f"肯定响应(67 {LEVEL_PRO_12_STR})",
                                   alg_type=AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step22", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) != 0:
            TestLog("FAIL", "", f"期望: 肯定响应且种子为全00; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子为全00; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step23", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step24", "DUT重新上电")
        ctx.power_ctrl.off()
        time.sleep(3)
        ctx.power_ctrl.on()
        time.sleep(3)

        TestLog("INFO", "Step25", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step26", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step27", "编程条件检查(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step28", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step29", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step30", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step31", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x67, LEVEL_PRO_12], f"肯定响应(67 {LEVEL_PRO_12_STR})",
                                   alg_type=AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step32", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG3_TC12_phyRequest_27_ResetNRC37Check():
    case_name = "27复位延时机制与锁定检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_5, LEVEL_PRO_5_STR = 0x05, "05"  # 刷新等级
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1

    min_subid, max_subid = UDSTestParams.MinSubID, UDSTestParams.MaxSubID
    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        
        # 清除错误计数器
        if not clear_27_error_timer(node): return

        TestLog("INFO", "Step1", "令SN=0x01")
        for sn in range(min_subid, max_subid + 1):
            if sn not in UDSTestParams.Services11SubFunSupportList:
                continue
            TestLog("INFO", "Step2", "如果SN为扩展会话状态11服务不支持的物理寻址子功能，则SN+=1，直到SN为扩展会话支持的物理寻址的子功能；如果SN=0xFF，则跳转到步骤26")

            TestLog("INFO", "Step3", "请求进入默认会话(10 01)")
            if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

            sl_time().sleep(int(1*1000))

            TestLog("INFO", "Step4", "请求进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

            sl_time().sleep(int(1*1000))

            TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                        expect_str="位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step6", "发送扩展安全级的请求种子请求(27 01)")
            status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 01)")
            if not status: return
            seed_list = get_seed_from_27_resp(resp)
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
            if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
                TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
                return
            TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

            TestLog("INFO", "Step7", "发送错误的扩展安全级的解锁密钥(27 02)")
            if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x7F, 0x27, 0x35], f"否定响应(7F 27 35)",
                                    alg_type=AlgorithmType.EXTENDED_ERROR): return

            TestLog("INFO", "Step8", "发送扩展安全级的请求种子请求(27 01)")
            status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 01)")
            if not status: return
            seed_list = get_seed_from_27_resp(resp)
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
            if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
                TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
                return
            TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            
            TestLog("INFO", "Step9", f"发送错误的扩展安全级的解锁密钥(27 {LEVEL_EXT_2_STR})")
            if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x7F, 0x27, 0x35], f"否定响应(7F 27 35)",
                                    alg_type=AlgorithmType.EXTENDED_ERROR): return

            TestLog("INFO", "Step10", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
            status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 01)")
            if not status: return
            seed_list = get_seed_from_27_resp(resp)
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
            if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
                TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
                return
            TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            
            TestLog("INFO", "Step11", f"发送错误的扩展安全级的解锁密钥(27 {LEVEL_EXT_2_STR})")
            if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x7F, 0x27, 0x36], f"否定响应(7F 27 36)",
                                    alg_type=AlgorithmType.EXTENDED_ERROR): return

            TestLog("INFO", "Step12", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
            status, resp = service_27_check(node, LEVEL_EXT, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)")
            if not status: return

            TestLog("INFO", "Step13", f"等待9s(3E服务启动)")
            tester_present_start(node)
            sl_time().sleep(int(9*1000))
            tester_present_stop()

            TestLog("INFO", "Step14", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
            status, resp = service_27_check(node, LEVEL_EXT, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)")
            if not status: return

            TestLog("INFO", "Step15", f"请求复位")
            if not service_11_check(node, sn, expect_data=[0x51, sn], expect_str=f"肯定响应(51 {sn})"): return

            sl_time().sleep(int(P.DiagServiceInfo.ResetTime))

            TestLog("INFO", "Step16", "请求进入默认会话(10 01)")
            if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

            sl_time().sleep(int(1*1000))

            TestLog("INFO", "Step17", "请求进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

            TestLog("INFO", "Step18", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                        expect_str="位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step19", f"等待复位后9s(3E服务启动)")
            tester_present_start(node)
            sl_time().sleep(int(5*1000))
            tester_present_stop()

            TestLog("INFO", "Step20", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
            status, resp = service_27_check(node, LEVEL_EXT, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)")
            if not status: return
                                        
            TestLog("INFO", "Step21", f"等待复位后1s(3E服务启动)")
            tester_present_start(node)
            sl_time().sleep(int(6*1000))
            tester_present_stop()

            TestLog("INFO", "Step22", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
            status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 01)")
            if not status: return
            seed_list = get_seed_from_27_resp(resp)
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
            if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
                TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
                return
            TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

            TestLog("INFO", "Step23", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT_2_STR})")
            if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x67, LEVEL_EXT_2], f"肯定响应(67 {LEVEL_EXT_2_STR})",
                                    alg_type=AlgorithmType.EXTENDED): return

            TestLog("INFO", "Step24", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                        expect_str="位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step25", "若SN<0xFF，则SN+=1，返回步骤2")

        TestLog("INFO", "Step26", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step27", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step18", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                    expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step28", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step29", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step30", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return
        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step31", f"发送错误的刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x7F, 0x27, 0x35], f"否定响应(7F 27 35)",
                                   alg_type=AlgorithmType.PRO_ERROR): return

        TestLog("INFO", "Step32", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return
        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step33", f"发送错误的刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x7F, 0x27, 0x35], f"否定响应(7F 27 35)",
                                   alg_type=AlgorithmType.PRO_ERROR): return

        TestLog("INFO", "Step34", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return
        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step35", f"发送错误的刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x7F, 0x27, 0x36], f"否定响应(7F 27 36)",
                                   alg_type=AlgorithmType.PRO_ERROR): return

        TestLog("INFO", "Step36", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)")
        if not status: return

        TestLog("INFO", "Step37", f"等待9s(3E服务启动)")
        tester_present_start(node)
        sl_time().sleep(int(9*1000))
        tester_present_stop()

        TestLog("INFO", "Step38", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)")
        if not status: return

        TestLog("INFO", "Step39", f"请求复位")
        if not service_11_check(node, sn, expect_data=[0x51, 0x01], expect_str=f"肯定响应(51 01)"): return
        sl_time().sleep(int(P.DiagServiceInfo.ResetTime))

        TestLog("INFO", "Step40", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step41", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step18", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                    expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step42", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step43", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step44", f"等待复位后9s(3E服务启动)")
        tester_present_start(node)
        sl_time().sleep(int(5*1000))
        tester_present_stop()

        TestLog("INFO", "Step45", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)")
        if not status: return

        TestLog("INFO", "Step46", f"等待1s(3E服务启动)")
        tester_present_start(node)
        sl_time().sleep(int(6*1000))
        tester_present_stop()

        TestLog("INFO", "Step47", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step48", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x67, LEVEL_PRO_12], f"肯定响应(67 {LEVEL_PRO_12_STR})",
                                   alg_type=AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step49", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC13_phyRequest_27_PowerOnNRC37Check():
    case_name = "27服务重新上电延时机制与锁定检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rSessionTime_ms = int(P.DiagServiceInfo.SessionTime)
        power_cycle_wait_s = 2
        nrc37_check_after_power_s = 5
        nrc37_release_wait_s = 6

        if rSessionTime_ms > 1000:
            TestLog("FAIL", case_name, "检查到配置的SessionTime时间 > 1000ms，不执行该测试用例")
            return

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        # 清除错误计数器
        if not clear_27_error_timer(node): return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        sl_time().sleep(rSessionTime_ms)

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step5", f"发送错误的扩展安全级的解锁密钥(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x7F, 0x27, 0x35], f"否定响应(7F 27 35)",
                                   alg_type=AlgorithmType.EXTENDED_ERROR): return

        TestLog("INFO", "Step6", f"发送错误的扩展安全级的解锁密钥(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x7F, 0x27, 0x36], f"否定响应(7F 27 36)",
                                   alg_type=AlgorithmType.EXTENDED_ERROR): return

        TestLog("INFO", "Step7", f"发送错误的扩展安全级的解锁密钥(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)",
                                   alg_type=AlgorithmType.EXTENDED_ERROR): return

        TestLog("INFO", "Step8", f"等待9s(3E服务启动)")
        tester_present_start(node)
        sl_time().sleep(int(9*1000))
        tester_present_stop()

        TestLog("INFO", "Step9", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)")
        if not status: return

        TestLog("INFO", "Step10", "DUT重新上电")
        ctx.power_ctrl.off()
        time.sleep(power_cycle_wait_s)
        ctx.power_ctrl.on()
        time.sleep(power_cycle_wait_s)
        begin_time_s = time.perf_counter()

        TestLog("INFO", "Step11", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        sl_time().sleep(rSessionTime_ms)

        TestLog("INFO", "Step12", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step13", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step14", "补足到重新上电后5s(3E服务启动)")
        elapsed_s = time.perf_counter() - begin_time_s
        if elapsed_s <= nrc37_check_after_power_s:
            tester_present_start(node)
            try:
                # 等待实现按CAPL动态补偿到NRC37检查点，Step描述保持与规范一致
                remain_s = nrc37_check_after_power_s - elapsed_s
                if remain_s > 0:
                    sl_time().sleep(int(remain_s * 1000))

                TestLog("INFO", "Step15", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
                status, resp = service_27_check(node, LEVEL_EXT, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)")
            finally:
                tester_present_stop()
            if not status: return
        else:
            TestLog("WARNING", "Step15", f"重新上电后进入扩展会话耗时{elapsed_s:.3f}s，超过CAPL 5s检查点，跳过NRC37检查")

        TestLog("INFO", "Step16", f"等待{nrc37_release_wait_s}s(3E服务启动)")
        tester_present_start(node)
        sl_time().sleep(int(nrc37_release_wait_s * 1000))
        tester_present_stop()

        TestLog("INFO", "Step17", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step18", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x67, LEVEL_EXT_2], f"肯定响应(67 {LEVEL_EXT_2_STR})",
                                   alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step19", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step20", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        sl_time().sleep(rSessionTime_ms)

        TestLog("INFO", "Step21", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step22", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step23", f"发送错误的刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x7F, 0x27, 0x35], f"否定响应(7F 27 35)",
                                   alg_type=AlgorithmType.PROGRAMMING_ERROR): return

        TestLog("INFO", "Step24", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step25", f"发送错误的刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x7F, 0x27, 0x35], f"否定响应(7F 27 35)",
                                   alg_type=AlgorithmType.PROGRAMMING_ERROR): return

        TestLog("INFO", "Step26", f"发送错误的刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x7F, 0x27, 0x36], f"否定响应(7F 27 36)",
                                   alg_type=AlgorithmType.PROGRAMMING_ERROR): return

        TestLog("INFO", "Step27", f"发送错误的刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)",
                                   alg_type=AlgorithmType.PROGRAMMING_ERROR): return

        TestLog("INFO", "Step28", f"等待9s(3E服务启动)")
        tester_present_start(node)
        sl_time().sleep(int(9*1000))
        tester_present_stop()

        TestLog("INFO", "Step29", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)")
        if not status: return

        TestLog("INFO", "Step30", "DUT重新上电")
        ctx.power_ctrl.off()
        time.sleep(power_cycle_wait_s)
        ctx.power_ctrl.on()
        time.sleep(power_cycle_wait_s)

        TestLog("INFO", "Step31", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step32", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step33", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        sl_time().sleep(rSessionTime_ms)
        begin_time_s = time.perf_counter()

        TestLog("INFO", "Step34", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step35", "补足到进入刷新会话后5s(3E服务启动)")
        elapsed_s = time.perf_counter() - begin_time_s
        if elapsed_s <= nrc37_check_after_power_s:
            tester_present_start(node)
            try:
                # 等待实现按CAPL动态补偿到NRC37检查点，Step描述保持与规范一致
                remain_s = nrc37_check_after_power_s - elapsed_s
                if remain_s > 0:
                    sl_time().sleep(int(remain_s * 1000))

                TestLog("INFO", "Step36", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
                status, resp = service_27_check(node, LEVEL_PRO_11, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)")
            finally:
                tester_present_stop()
            if not status: return
        else:
            TestLog("WARNING", "Step36", f"进入刷新会话后耗时{elapsed_s:.3f}s，超过CAPL 5s检查点，跳过NRC37检查")

        TestLog("INFO", "Step37", f"等待{nrc37_release_wait_s}s(3E服务启动)")
        tester_present_start(node)
        sl_time().sleep(int(nrc37_release_wait_s * 1000))
        tester_present_stop()

        TestLog("INFO", "Step38", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step39", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x67, LEVEL_PRO_12], f"肯定响应(67 {LEVEL_PRO_12_STR})",
                                   alg_type=AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step40", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC14_phyRequest_27_SessionChangeNRC37Check():
    case_name = "27服务切换会话延时机制独立性检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_5, LEVEL_PRO_5_STR = 0x05, "05"  # 刷新等级
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        
        # 清除错误计数器
        if not clear_27_error_timer(node): return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        sl_time().sleep(int(1*1000))

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        sl_time().sleep(int(1*1000))

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "发送扩展安全级的请求种子请求(27 01)")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 01)")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step5", "发送错误的扩展安全级的解锁密钥(27 02)")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x7F, 0x27, 0x35], f"否定响应(7F 27 35)",
                                   alg_type=AlgorithmType.EXTENDED_ERROR): return

        TestLog("INFO", "Step6", "发送扩展安全级的请求种子请求(27 01)")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 01)")
        if not status: return
        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step7", "发送错误的扩展安全级的解锁密钥(27 02)")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x7F, 0x27, 0x35], f"否定响应(7F 27 35)",
                                   alg_type=AlgorithmType.EXTENDED_ERROR): return

        TestLog("INFO", "Step8", "发送扩展安全级的请求种子请求(27 01)")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 01)")
        if not status: return
        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step9", "发送错误的扩展安全级的解锁密钥(27 02)")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x7F, 0x27, 0x36], f"否定响应(7F 27 36)",
                                   alg_type=AlgorithmType.EXTENDED_ERROR): return

        TestLog("INFO", "Step10", "发送扩展安全级的请求种子请求(27 01)")
        status, resp = service_27_check(node, LEVEL_EXT, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)")
        if not status: return

        TestLog("INFO", "Step11", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step12", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step13", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step14", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step16", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step17", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x67, LEVEL_PRO_12], f"肯定响应(67 {LEVEL_PRO_12_STR})",
                                   alg_type=AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step18", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step19", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step20", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step21", f"等待9s(3E服务启动)")
        tester_present_start(node)
        sl_time().sleep(int(9*1000))
        tester_present_stop()

        TestLog("INFO", "Step22", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)")
        if not status: return

        TestLog("INFO", "Step23", f"等待1s(3E服务启动)")
        tester_present_start(node)
        sl_time().sleep(int(1*1000))
        tester_present_stop()

        TestLog("INFO", "Step24", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return
        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
        
        TestLog("INFO", "Step25", f"发送的扩展安全级的解锁密钥(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x67, LEVEL_EXT_2], f"肯定响应(67 {LEVEL_EXT_2_STR})",
                                   alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step26", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step27", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step28", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step29", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step30", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step31", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step32", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)")
        if not status: return
        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step33", f"发送错误的刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x7F, 0x27, 0x35], f"否定响应(7F 27 35)",
                                   alg_type=AlgorithmType.PROGRAMMING_ERROR): return

        TestLog("INFO", "Step34", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)")
        if not status: return
        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step35", f"发送错误的刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x7F, 0x27, 0x35], f"否定响应(7F 27 35)",
                                   alg_type=AlgorithmType.PROGRAMMING_ERROR): return

        TestLog("INFO", "Step36", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)")
        if not status: return
        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step37", f"发送错误的刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x7F, 0x27, 0x36], f"否定响应(7F 27 36)",
                                   alg_type=AlgorithmType.PROGRAMMING_ERROR): return

        TestLog("INFO", "Step38", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)")
        if not status: return

        TestLog("INFO", "Step39", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step40", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step41", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step42", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return
        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
        
        TestLog("INFO", "Step43", f"发送的扩展安全级的解锁密钥(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x67, LEVEL_EXT_2], f"肯定响应(67 {LEVEL_EXT_2_STR})",
                                   alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step44", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step45", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step46", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step48", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step49", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step50", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)")
        if not status: return

        TestLog("INFO", "Step51", f"等待1s(3E服务启动)")
        tester_present_start(node)
        sl_time().sleep(int(1*1000))
        tester_present_stop()

        TestLog("INFO", "Step52", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return
        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
        
        TestLog("INFO", "Step53", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x67, LEVEL_PRO_12], f"肯定响应(67 {LEVEL_PRO_12_STR})",
                                   alg_type=AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step54", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG3_TC15_phyRequest_27_NRCPriorityCheck():
    case_name = "27服务NRC优先级检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_5, LEVEL_PRO_5_STR = 0x05, "05"  # 刷新等级
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        nrc22_condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x27)

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        if len(nrc22_condition_list) > 0:
            TestLog("INFO", "Step3", "触发NRC22的条件之一，并发送27 01请求，如果满足条件，则对27 01请求返回NRC=0x22的否定响应")
            condition = nrc22_condition_list[0]
            if not start_nrc22_condition(condition): return
            try:
                status, resp = service_27_check(node, LEVEL_EXT, [0x7F, 0x27, 0x22], f"否定响应(7F 27 22)")
            finally:
                stop_nrc22_condition(condition)
            if not status: return
        else:
            TestLog("INFO", "Step3", "配置表未配置27服务NRC22触发条件，跳过NRC22检查")

        TestLog("INFO", "Step4", "发送27 01 00")
        status, resp = service_27_check(node, LEVEL_EXT, [0x7F, 0x27, 0x7F], f"否定响应(7F 27 7F)", dl=3, dl_paddding=0x00)
        if not status: return

        TestLog("INFO", "Step5", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step6", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step7", "发送27请求")
        status, resp = service_27_check(node, None, [0x7F, 0x27, 0x13], f"否定响应(7F 27 13)")
        if not status: return

        TestLog("INFO", "Step8", "发送27 19请求")
        status, resp = service_27_check(node, 0x19, [0x7F, 0x27, 0x12], f"否定响应(7F 27 12)")
        if not status: return

        TestLog("INFO", "Step9", "发送27 02 00")
        status, resp = service_27_check(node, LEVEL_EXT_2, [0x7F, 0x27, 0x13], f"否定响应(7F 27 13)", dl=3, dl_paddding=0x00)
        if not status: return

        TestLog("INFO", "Step10", "发送27 19 00")
        status, resp = service_27_check(node, 0x19, [0x7F, 0x27, 0x12], f"否定响应(7F 27 12)", dl=3, dl_paddding=0x00)
        if not status: return

        TestLog("INFO", "Step11", "发送27 01")
        status, resp = service_27_check(node, LEVEL_EXT, [0x7F, 0x27, 0x37], f"否定响应(7F 27 37)")
        if not status: return

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG4_TC1_phyRequest_28_Positive():
    """
    28服务肯定响应检查(物理寻址)
    """
    case_name = "28服务肯定响应检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        sub_fun_list = UDSTestParams.Services28SubFunSupportList
        comm_type_list = UDSTestParams.Services28CommTypeSupportList

        step_num = 1

        TestLog("INFO", f"Step{step_num}", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return
        step_num += 1

        TestLog("INFO", f"Step{step_num}", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return
        step_num += 1

        TestLog("INFO", f"Step{step_num}", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return
        step_num += 1

        for sub_fun in sub_fun_list:
            for comm_type in comm_type_list:
                # 发送28服务请求(不带抑制位)
                TestLog("INFO", f"Step{step_num}", f"发送28 {sub_fun:02X} {comm_type:02X}请求")
                if not service_28_check(node, sub_fun, comm_type, [0x68, sub_fun], f"肯定响应(68 {sub_fun:02X})"): return
                step_num += 1

                # 发送28服务请求(带抑制位)
                sub_fun_with_suppress = sub_fun | 0x80
                TestLog("INFO", f"Step{step_num}", f"发送28 {sub_fun_with_suppress:02X} {comm_type:02X}请求(带抑制位)")
                if not service_28_check(node, sub_fun_with_suppress, comm_type, None, "无响应"): return
                step_num += 1

        TestLog("INFO", f"Step{step_num}", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC2_funRequest_28_Positive():
    """
    28服务肯定响应检查(功能寻址)
    """
    case_name = "28服务肯定响应检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        sub_fun_list = UDSTestParams.Services28SubFunSupportList
        comm_type_list = UDSTestParams.Services28CommTypeSupportList

        step_num = 1

        TestLog("INFO", f"Step{step_num}", "请求进入默认会话(10 01)(功能寻址)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return
        step_num += 1

        TestLog("INFO", f"Step{step_num}", "请求进入扩展会话(10 03)(功能寻址)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return
        step_num += 1

        TestLog("INFO", f"Step{step_num}", "检查当前会话状态(31 01 02 03)(功能寻址)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return
        step_num += 1

        for sub_fun in sub_fun_list:
            for comm_type in comm_type_list:
                # 发送28服务请求(功能寻址，不带抑制位)
                TestLog("INFO", f"Step{step_num}", f"发送28 {sub_fun:02X} {comm_type:02X}请求(功能寻址)")
                if not service_28_check(node, sub_fun, comm_type, [0x68, sub_fun], f"肯定响应(68 {sub_fun:02X})", func_req=True): return
                step_num += 1

                # 发送28服务请求(功能寻址，带抑制位)
                sub_fun_with_suppress = sub_fun | 0x80
                TestLog("INFO", f"Step{step_num}", f"发送28 {sub_fun_with_suppress:02X} {comm_type:02X}请求(功能寻址,带抑制位)")
                if not service_28_check(node, sub_fun_with_suppress, comm_type, None, "无响应", func_req=True): return
                step_num += 1

        TestLog("INFO", f"Step{step_num}", "检查当前会话状态(31 01 02 03)(功能寻址)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC3_phyRequest_28_ExitFunction():
    """
    28服务退出功能检查(物理寻址)
    """
    case_name = "28服务退出功能检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        s3_timeout = P.TpInfo.S3Server / 1000 + 1

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "发送28 03 01请求关闭报文发送和接收")
        if not service_28_check(node, 0x03, 0x01, [0x68, 0x03], "肯定响应(68 03)"): return

        TestLog("INFO", "Step5", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step6", "检查当前会话状态及报文是否能正常收发(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step7", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step8", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step10", "发送28 03 01请求关闭报文发送和接收")
        if not service_28_check(node, 0x03, 0x01, [0x68, 0x03], "肯定响应(68 03)"): return

        TestLog("INFO", "Step11", "请求复位，等待2s(11 01)")
        if not service_11_check(node, 0x01, [0x51, 0x01], "肯定响应(51 01)"): return
        time.sleep(2)

        TestLog("INFO", "Step12", "检查当前会话状态及报文是否能正常收发(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step13", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step14", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step16", "发送28 03 01请求关闭报文发送和接收")
        if not service_28_check(node, 0x03, 0x01, [0x68, 0x03], "肯定响应(68 03)"): return

        TestLog("INFO", "Step17", "DUT重新上电")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        time.sleep(2)

        TestLog("INFO", "Step18", "检查当前会话状态及报文是否能正常收发(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step19", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step20", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step21", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step22", "发送28 03 01请求关闭报文发送和接收")
        if not service_28_check(node, 0x03, 0x01, [0x68, 0x03], "肯定响应(68 03)"): return

        TestLog("INFO", "Step23", f"等待S3server超时({s3_timeout}秒)")
        time.sleep(s3_timeout)

        TestLog("INFO", "Step24", "检查当前会话状态及报文是否能正常收发(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC4_funRequest_28_ExitFunction():
    """
    28服务退出功能检查(功能寻址)
    """
    case_name = "28服务退出功能检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        s3_timeout = P.TpInfo.S3Server / 1000 + 1

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)(功能寻址)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)(功能寻址)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)(功能寻址)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "发送28 03 01请求关闭报文发送和接收(功能寻址)")
        if not service_28_check(node, 0x03, 0x01, [0x68, 0x03], "肯定响应(68 03)", func_req=True): return

        TestLog("INFO", "Step5", "请求进入默认会话(10 01)(功能寻址)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step6", "检查当前会话状态及报文是否能正常收发(31 01 02 03)(功能寻址)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step7", "请求进入默认会话(10 01)(功能寻址)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step8", "请求进入扩展会话(10 03)(功能寻址)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)(功能寻址)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step10", "发送28 03 01请求关闭报文发送和接收(功能寻址)")
        if not service_28_check(node, 0x03, 0x01, [0x68, 0x03], "肯定响应(68 03)", func_req=True): return

        TestLog("INFO", "Step11", "请求复位，等待2s(11 01)(功能寻址)")
        if not service_11_check(node, 0x01, [0x51, 0x01], "肯定响应(51 01)"): return
        time.sleep(2)

        TestLog("INFO", "Step12", "检查当前会话状态及报文是否能正常收发(31 01 02 03)(功能寻址)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step13", "请求进入默认会话(10 01)(功能寻址)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step14", "请求进入扩展会话(10 03)(功能寻址)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)(功能寻址)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step16", "发送28 03 01请求关闭报文发送和接收(功能寻址)")
        if not service_28_check(node, 0x03, 0x01, [0x68, 0x03], "肯定响应(68 03)", func_req=True): return

        TestLog("INFO", "Step17", "DUT重新上电")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        time.sleep(2)

        TestLog("INFO", "Step18", "检查当前会话状态及报文是否能正常收发(31 01 02 03)(功能寻址)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step19", "请求进入默认会话(10 01)(功能寻址)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step20", "请求进入扩展会话(10 03)(功能寻址)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step21", "检查当前会话状态(31 01 02 03)(功能寻址)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step22", "发送28 03 01请求关闭报文发送和接收(功能寻址)")
        if not service_28_check(node, 0x03, 0x01, [0x68, 0x03], "肯定响应(68 03)", func_req=True): return

        TestLog("INFO", "Step23", f"等待S3server超时({s3_timeout}秒)")
        time.sleep(s3_timeout)

        TestLog("INFO", "Step24", "检查当前会话状态及报文是否能正常收发(31 01 02 03)(功能寻址)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC5_phyRequest_28_NRC12():
    """
    28服务NRC12检查(物理寻址)
    """
    case_name = "28服务NRC12检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        supported_sub_funs = UDSTestParams.Services28SubFunSupportList
        comm_type_list = UDSTestParams.Services28CommTypeSupportList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        for sub_fun in range(0x00, 0x100):
            if sub_fun in supported_sub_funs:
                continue

            for comm_type in comm_type_list:
                TestLog("INFO", f"Step4", f"发送不支持的子功能请求(28 {sub_fun:02X} {comm_type:02X})")
                if not service_28_check(node, sub_fun, comm_type, [0x7F, 0x28, 0x12], "否定响应(7F 28 12)"): return

        TestLog("INFO", f"Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC6_funRequest_28_NRC12():
    """
    28服务NRC12检查(功能寻址)
    """
    case_name = "28服务NRC12检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        supported_sub_funs = UDSTestParams.Services28SubFunSupportList
        comm_type_list = UDSTestParams.Services28CommTypeSupportList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)(功能寻址)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)(功能寻址)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)(功能寻址)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        for sub_fun in range(0x00, 0x100):
            if sub_fun in supported_sub_funs:
                continue

            for comm_type in comm_type_list:
                TestLog("INFO", f"Step4", f"发送不支持的子功能请求(功能寻址)(28 {sub_fun:02X} {comm_type:02X})")
                if not service_28_check(node, sub_fun, comm_type, None, "无响应", func_req=True, timeout=0.1): return

        TestLog("INFO", f"Step5", "检查当前会话状态(31 01 02 03)(功能寻址)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC7_phyRequest_28_NRC13():
    """
    28服务NRC13检查(物理寻址)
    """
    case_name = "28服务NRC13检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        supported_sub_funs = UDSTestParams.Services28SubFunSupportList
        comm_type_list = UDSTestParams.Services28CommTypeSupportList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "发送长度错误的28请求(DL=1, 只有SID)")
        if not service_28_check(node, None, None, [0x7F, 0x28, 0x13], "否定响应(7F 28 13)"): return

        # DL=2,4,5,6,7
        for sub_fun in supported_sub_funs:
            # DL=2: 28 sub_fun (无通信类型)
            TestLog("INFO", f"Step5", f"发送长度错误的28请求(DL=2, 28 {sub_fun:02X})")
            if not service_28_check(node, None, None, [0x7F, 0x28, 0x13], "否定响应(7F 28 13)", dl=2, dl_padding=sub_fun): return

            # DL=4,5,6,7: 
            for comm_type in comm_type_list:
                for dl in [4, 5, 6, 7]:
                    TestLog("INFO", f"Step6", f"发送长度错误的28请求(DL={dl}, 28 {sub_fun:02X} {comm_type:02X} ...)")
                    if not service_28_check(node, sub_fun, comm_type, [0x7F, 0x28, 0x13], "否定响应(7F 28 13)", dl=dl): return

        TestLog("INFO", f"Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC8_funRequest_28_NRC13():
    """
    28服务NRC13检查(功能寻址)
    """
    case_name = "28服务NRC13检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        supported_sub_funs = UDSTestParams.Services28SubFunSupportList
        comm_type_list = UDSTestParams.Services28CommTypeSupportList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)(功能寻址)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)(功能寻址)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)(功能寻址)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "发送长度错误的28请求(功能寻址)(DL=1, 只有SID)")
        if not service_28_check(node, None, None, [0x7F, 0x28, 0x13], "否定响应(7F 28 13)", func_req=True): return

        # DL=2,4,5,6,7
        for sub_fun in supported_sub_funs:
            # DL=2: 28 sub_fun (无通信类型)
            TestLog("INFO", f"Step5", f"发送长度错误的28请求(功能寻址)(DL=2, 28 {sub_fun:02X})")
            if not service_28_check(node, None, None, [0x7F, 0x28, 0x13], "否定响应(7F 28 13)", func_req=True, dl=2, dl_padding=sub_fun): return

            # DL=4,5,6,7
            for comm_type in comm_type_list:
                for dl in [4, 5, 6, 7]:
                    TestLog("INFO", f"Step6", f"发送长度错误的28请求(功能寻址)(DL={dl}, 28 {sub_fun:02X} {comm_type:02X} ...)")
                    if not service_28_check(node, sub_fun, comm_type, [0x7F, 0x28, 0x13], "否定响应(7F 28 13)", func_req=True, dl=dl): return

        TestLog("INFO", f"Step7", "检查当前会话状态(31 01 02 03)(功能寻址)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC9_phyRequest_28_NRC7F():
    """
    28服务NRC7F检查(物理寻址)
    """
    case_name = "28服务NRC7F检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        supported_sub_funs = UDSTestParams.Services28SubFunSupportList
        comm_type_list = UDSTestParams.Services28CommTypeSupportList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        for sub_fun in supported_sub_funs:
            for comm_type in comm_type_list:
                TestLog("INFO", f"Step3", f"在默认会话下发送28 {sub_fun:02X} {comm_type:02X}请求")
                if not service_28_check(node, sub_fun, comm_type, [[0x7F, 0x28, 0x7F], [0x7F, 0x28, 0x11]], "否定响应(7F 28 7F)或(7F 28 11)"): return

        TestLog("INFO", f"Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", f"Step6", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", f"Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", f"Step8", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        TestLog("INFO", f"Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        for sub_fun in supported_sub_funs:
            for comm_type in comm_type_list:
                TestLog("INFO", f"Step10", f"在刷新会话下发送28 {sub_fun:02X} {comm_type:02X}请求")
                if not service_28_check(node, sub_fun, comm_type, [[0x7F, 0x28, 0x7F], [0x7F, 0x28, 0x11]], "否定响应(7F 28 7F)或(7F 28 11)"): return

        TestLog("INFO", f"Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC10_funRequest_28_NRC7F():
    """
    28服务NRC7F检查(功能寻址)
    """
    case_name = "28服务NRC7F检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        supported_sub_funs = UDSTestParams.Services28SubFunSupportList
        comm_type_list = UDSTestParams.Services28CommTypeSupportList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        for sub_fun in supported_sub_funs:
            for comm_type in comm_type_list:
                TestLog("INFO", f"Step3", f"在默认会话下发送28 {sub_fun:02X} {comm_type:02X}请求(功能寻址)")
                if not service_28_check(node, sub_fun, comm_type, None, "无响应", func_req=True, timeout=0.1): return

        TestLog("INFO", f"Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", f"Step5", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", f"Step6", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", f"Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", f"Step7", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        TestLog("INFO", f"Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        for sub_fun in supported_sub_funs:
            for comm_type in comm_type_list:
                TestLog("INFO", f"Step10", f"在刷新会话下发送28 {sub_fun:02X} {comm_type:02X}请求(功能寻址)")
                if not service_28_check(node, sub_fun, comm_type, None, "无响应", func_req=True, timeout=0.1): return

        TestLog("INFO", f"Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC11_phyRequest_28_NRC22():
    """
    28服务NRC22检查(物理寻址)
    """
    case_name = "28服务NRC22检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x28)
        if len(condition_list) == 0:
            TestLog("WARNING", case_name, "未配置28服务可执行的NRC22条件，跳过该测试")
            return

        supported_sub_funs = UDSTestParams.Services28SubFunSupportList
        comm_type_list = UDSTestParams.Services28CommTypeSupportList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "遍历NRC22条件，验证返回NRC22(物理寻址)")
        for condition in condition_list:
            TestLog("INFO", "", f"设置NRC22条件: {getattr(condition, 'ConditionName', 'unknown')}")
            if not start_nrc22_condition(condition): continue

            try:
                for sub_fun in supported_sub_funs:
                    for comm_type in comm_type_list:
                        service_28_check(node, sub_fun, comm_type, [0x7F, 0x28, 0x22], f"NRC22响应(7F 28 22)")
            finally:
                stop_nrc22_condition(condition)

            time.sleep(0.5)

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC12_funRequest_28_NRC22():
    """
    28服务NRC22检查(功能寻址)
    """
    case_name = "28服务NRC22检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x28)
        if len(condition_list) == 0:
            TestLog("WARNING", case_name, "未配置28服务可执行的NRC22条件，跳过该测试")
            return

        supported_sub_funs = UDSTestParams.Services28SubFunSupportList
        comm_type_list = UDSTestParams.Services28CommTypeSupportList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "遍历NRC22条件，验证返回NRC22(功能寻址)")
        for condition in condition_list:
            TestLog("INFO", "", f"设置NRC22条件: {getattr(condition, 'ConditionName', 'unknown')}")
            if not start_nrc22_condition(condition): continue

            try:
                for sub_fun in supported_sub_funs:
                    for comm_type in comm_type_list:
                        service_28_check(node, sub_fun, comm_type, [0x7F, 0x28, 0x22], "NRC22响应(7F 28 22)", func_req=True)
            finally:
                stop_nrc22_condition(condition)

            time.sleep(0.5)

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC13_phyRequest_28_Function():
    """
    28服务功能检查(物理寻址)
    """
    case_name = "28服务功能检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        normal_app_id_list = UDSTestParams.AppFrameIDList  # 正常应用报文 0x01
        nm_id_list = UDSTestParams.NMFrameIDList  # 网络管理报文 0x02
        normal_app_and_nm_id_list = set(normal_app_id_list + nm_id_list)  # 应用与网管报文 0x03

        wait_time_s = 2
        check_time_s = 1

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        supported_sub_funs = UDSTestParams.Services28SubFunSupportList
        comm_type_list = UDSTestParams.Services28CommTypeSupportList

        sn_mapping = {0x00:"使能收发", 0x01:"使能接收，禁用发送", 0x02:"使能发送,禁用接收", 0x03:"禁用收发"}
        commtype_mapping = {0x01:"常规应用报文", 0x02:"网络管理报文", 0x03:"常规应用报文和网络管理报文"}
        check_id_list_mapping = {0x01:normal_app_id_list, 0x02:nm_id_list, 0x03:normal_app_and_nm_id_list}

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        time.sleep(2)

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return


        TestLog("INFO", "Step4", "如果ECU不支持0x01子功能，跳转至步骤11")
        for sn in [0x01, 0x02, 0x03]:
            sn_str = sn_mapping[sn]
            if sn in supported_sub_funs:
                for comm_type in [0x01, 0x02, 0x03]:
                    comm_type_str = commtype_mapping[comm_type]
                    TestLog("INFO", "功能测试", f"发送28 {sn} {comm_type}请求（如果ECU不支持{comm_type}通信类型，跳到下一个通信类型）")
                    check_id_list = check_id_list_mapping[comm_type]

                    if comm_type in comm_type_list:
                        if not service_28_check(node, 0x01, comm_type, [0x68, 0x01], f"肯定响应(68 01)"): pass

                        TestLog("INFO", "", f"检查通信({comm_type_str}的{sn_str})")
                        if check_app_communication(check_id_list=check_id_list, wait_time_s=wait_time_s, check_time_s=check_time_s) is False:
                            TestLog("PASS", "", f"期望: 检测不到{comm_type_str}; 实际: 未检测到{comm_type_str}")
                        else:
                            TestLog("FAIL", "", f"期望: 检测不到{comm_type_str}; 实际: 检测到{comm_type_str}")
                            return

                        TestLog("INFO", "功能恢复测试", f"发送28 00 {comm_type}请求")
                        if not service_28_check(node, 0x00, comm_type, [0x68, 0x00], f"肯定响应(68 00)"): pass

                        TestLog("INFO", "", f"检查通信({comm_type_str}的收发正常)")
                        if check_app_communication(check_id_list=check_id_list, wait_time_s=wait_time_s, check_time_s=check_time_s) is False:
                            TestLog("FAIL", "", f"期望: 检测到{comm_type_str}; 实际: 未检测到{comm_type_str}")
                            return
                        else:
                            TestLog("PASS", "", f"期望: 检测到{comm_type_str}; 实际: 检测到{comm_type_str}")

        TestLog("INFO", f"Step25", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC14_funRequest_28_Function():
    """
    28服务功能检查(功能寻址)
    """
    case_name = "28服务功能检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        normal_app_id_list = UDSTestParams.AppFrameIDList  # 正常应用报文 0x01
        nm_id_list = UDSTestParams.NMFrameIDList  # 网络管理报文 0x02
        normal_app_and_nm_id_list = set(normal_app_id_list + nm_id_list)  # 应用与网管报文 0x03

        wait_time_s = 2
        check_time_s = 1

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        supported_sub_funs = UDSTestParams.Services28SubFunSupportList
        comm_type_list = UDSTestParams.Services28CommTypeSupportList

        sn_mapping = {0x00:"使能收发", 0x01:"使能接收，禁用发送", 0x02:"使能发送,禁用接收", 0x03:"禁用收发"}
        commtype_mapping = {0x01:"常规应用报文", 0x02:"网络管理报文", 0x03:"常规应用报文和网络管理报文"}
        check_id_list_mapping = {0x01:normal_app_id_list, 0x02:nm_id_list, 0x03:normal_app_and_nm_id_list}

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        time.sleep(2)

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return


        TestLog("INFO", "Step4", "如果ECU不支持0x01子功能，跳转至步骤11")
        for sn in [0x01, 0x02, 0x03]:
            sn_str = sn_mapping[sn]
            if sn in supported_sub_funs:
                for comm_type in [0x01, 0x02, 0x03]:
                    comm_type_str = commtype_mapping[comm_type]
                    TestLog("INFO", "功能测试", f"发送28 {sn} {comm_type}请求（如果ECU不支持{comm_type}通信类型，跳到下一个通信类型）")
                    check_id_list = check_id_list_mapping[comm_type]

                    if comm_type in comm_type_list:
                        if not service_28_check(node, 0x01, comm_type, [0x68, 0x01], f"肯定响应(68 01)", func_req=True): pass

                        TestLog("INFO", "", f"检查通信({comm_type_str}的{sn_str})")
                        if check_app_communication(check_id_list=check_id_list, wait_time_s=wait_time_s, check_time_s=check_time_s) is False:
                            TestLog("PASS", "", f"期望: 检测不到{comm_type_str}; 实际: 未检测到{comm_type_str}")
                        else:
                            TestLog("FAIL", "", f"期望: 检测不到{comm_type_str}; 实际: 检测到{comm_type_str}")
                            return

                        TestLog("INFO", "功能恢复测试", f"发送28 00 {comm_type}请求")
                        if not service_28_check(node, 0x00, comm_type, [0x68, 0x00], f"肯定响应(68 00)", func_req=True): pass

                        TestLog("INFO", "", f"检查通信({comm_type_str}的收发正常)")
                        if check_app_communication(check_id_list=check_id_list, wait_time_s=wait_time_s, check_time_s=check_time_s) is False:
                            TestLog("FAIL", "", f"期望: 检测到{comm_type_str}; 实际: 未检测到{comm_type_str}")
                            return
                        else:
                            TestLog("PASS", "", f"期望: 检测到{comm_type_str}; 实际: 检测到{comm_type_str}")

        TestLog("INFO", f"Step25", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC15_phyRequest_28_NRC31():
    """
    28服务NRC31检查(物理寻址)
    """
    case_name = "28服务NRC31检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        supported_sub_funs = UDSTestParams.Services28SubFunSupportList
        supported_comm_types = UDSTestParams.Services28CommTypeSupportList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        time.sleep(2)

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        for sub_fun in [0x01, 0x02, 0x03]:
            if sub_fun not in supported_sub_funs:
                continue
            for comm_type in range(0x00, 0x11):
                if comm_type in supported_comm_types:  # [1, 2, 3]
                    continue
                TestLog("INFO", f"Step4", f"发送28 {sub_fun:02X} {comm_type:02X}请求(不支持的通信类型)")
                # 如果使用scapy的接口，是无法构造期望的报文，因此需要使用spec_data，指定发送的数据
                if not service_28_check(node, None, None, [0x7F, 0x28, 0x31], "NRC31响应(7F 28 31)", spec_data=[sub_fun, comm_type]): return

        TestLog("INFO", f"Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC16_funRequest_28_NRC31():
    """
    28服务NRC31检查(功能寻址)
    """
    case_name = "28服务NRC31检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        supported_sub_funs = UDSTestParams.Services28SubFunSupportList
        supported_comm_types = UDSTestParams.Services28CommTypeSupportList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        for sub_fun in [0x01, 0x02, 0x03]:
            if sub_fun not in supported_sub_funs:
                continue
            for comm_type in range(0x00, 0x11):
                if comm_type in supported_comm_types:
                    continue
                TestLog("INFO", f"Step4", f"发送28 {sub_fun:02X} {comm_type:02X}请求(功能寻址,不支持的通信类型)")
                if not service_28_check(node, None, None, None, "无响应", spec_data=[sub_fun, comm_type], func_req=True, timeout=0.1): return

        TestLog("INFO", f"Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC17_phyRequest_28_NRCPriority():
    """
    28服务NRC优先级检查(物理寻址)
    """
    case_name = "28服务NRC优先级检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x28)

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        if len(condition_list) > 0:
            TestLog("INFO", "Step3", f"触发NRC22条件并发送28 00 01请求")
            condition = condition_list[0]
            if start_nrc22_condition(condition):
                try:
                    if not service_28_check(node, 0x00, 0x01, [0x7F, 0x28, 0x22], "NRC22响应(7F 28 22)"): return
                finally:
                    stop_nrc22_condition(condition)
        else:
            TestLog("WARNING", "Step3", "未配置28服务可执行的NRC22条件，跳过NRC22测试")

        TestLog("INFO", "Step4", "发送28 00 01 00请求(默认会话，长度多余)")
        if not service_28_check(node, 0x00, 0x01, [0x7F, 0x28, 0x7F], "NRC7F响应(7F 28 7F)", dl=4): return

        TestLog("INFO", "Step5", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step6", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step7", "发送28请求(DL=1)，验证NRC13")
        if not service_28_check(node, None, None, [0x7F, 0x28, 0x13], "NRC13响应(7F 28 13)"): return

        TestLog("INFO", "Step8", "发送28 06 00请求(不支持的子功能)，验证NRC12")
        if not service_28_check(node, 0x06, 0x00, [0x7F, 0x28, 0x12], "NRC12响应(7F 28 12)"): return

        TestLog("INFO", "Step9", "发送28 04 01请求(SubFun=04不支持)，验证NRC12")
        if not service_28_check(node, 0x04, 0x01, [0x7F, 0x28, 0x12], "NRC13响应(7F 28 12)"): return

        TestLog("INFO", "Step10", "发送28 06 01请求(SubFun=06不支持)，验证NRC12")
        if not service_28_check(node, 0x06, 0x01, [0x7F, 0x28, 0x12], "NRC12响应(7F 28 12)"): return

        TestLog("INFO", "Step11", "发送28 00 04请求(通信类型=04不支持)，验证NRC31")
        if not service_28_check(node, 0x00, 0x04, [0x7F, 0x28, 0x31], "NRC31响应(7F 28 31)"): return

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC18_funRequest_28_NRCPriority():
    """
    28服务NRC优先级检查(功能寻址)
    """
    case_name = "28服务NRC优先级检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x28)

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        if len(condition_list) > 0:
            TestLog("INFO", "Step3", f"触发NRC22条件并发送28 00 01请求(功能寻址)")
            condition = condition_list[0]
            if start_nrc22_condition(condition):
                try:
                    if not service_28_check(node, 0x00, 0x01, [0x7F, 0x28, 0x22], "NRC22响应(7F 28 22)", func_req=True): return
                finally:
                    stop_nrc22_condition(condition)
        else:
            TestLog("WARNING", "Step3", "未配置28服务可执行的NRC22条件，跳过NRC22测试")

        TestLog("INFO", "Step4", "发送28 00 01 00请求(功能寻址，默认会话，长度多余)")
        if not service_28_check(node, 0x00, 0x01, None, "无响应", func_req=True, dl=4): return

        TestLog("INFO", "Step5", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step6", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step7", "发送28请求(功能寻址,DL=1)，验证NRC13")
        if not service_28_check(node, None, None, [0x7F, 0x28, 0x13], "NRC13响应(7F 28 13)", func_req=True): return

        TestLog("INFO", "Step8", "发送28 06 00请求(功能寻址,不支持的子功能)，验证NRC12")
        if not service_28_check(node, 0x06, 0x00, None, "无响应", func_req=True): return

        TestLog("INFO", "Step9", "发送28 04 01请求(功能寻址,SubFun=04)，验证NRC12")
        if not service_28_check(node, 0x04, 0x01, None, "无响应", func_req=True): return

        TestLog("INFO", "Step10", "发送28 06 01请求(功能寻址,SubFun=06不支持)，验证NRC12")
        if not service_28_check(node, 0x06, 0x01, None, "无响应", func_req=True): return

        TestLog("INFO", "Step11", "发送28 00 04请求(功能寻址,通信类型=04不支持)，验证NRC31")
        if not service_28_check(node, 0x00, 0x04, None, "无响应", func_req=True): return

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG5_TC1_phyRequest_3E_Positive():
    """
    3E服务肯定响应与功能检查(物理寻址)
    """
    case_name = "3E服务肯定响应与功能检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "等待4.5s")
        time.sleep(4.5)

        TestLog("INFO", "Step4", "发送3E 00请求")
        if not service_3E_check(node, 0x00, expect_data=[0x7E, 0x00], expect_str="肯定响应(7E 00)"): return

        TestLog("INFO", "Step5", "等待4.5s")
        time.sleep(4.5)

        TestLog("INFO", "Step6", "发送3E 80请求(抑制肯定响应)")
        if not service_3E_check(node, 0x80, expect_data=None, expect_str="无响应"): return

        TestLog("INFO", "Step7", "等待4.5s")
        time.sleep(4.5)

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step9", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step10", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step12", "等待4.5s")
        time.sleep(4.5)

        TestLog("INFO", "Step13", "发送3E 00请求")
        if not service_3E_check(node, 0x00, expect_data=[0x7E, 0x00], expect_str="肯定响应(7E 00)"): return

        TestLog("INFO", "Step14", "等待4.5s")
        time.sleep(4.5)

        TestLog("INFO", "Step15", "发送3E 80请求(抑制肯定响应)")
        if not service_3E_check(node, 0x80, expect_data=None, expect_str="无响应"): return

        TestLog("INFO", "Step16", "等待4.5s")
        time.sleep(4.5)

        TestLog("INFO", "Step17", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step18", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step19", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step20", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step21", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step22", "等待4.5s")
        time.sleep(4.5)

        TestLog("INFO", "Step23", "发送3E 00请求")
        if not service_3E_check(node, 0x00, expect_data=[0x7E, 0x00], expect_str="肯定响应(7E 00)"): return

        TestLog("INFO", "Step24", "等待4.5s")
        time.sleep(4.5)

        TestLog("INFO", "Step25", "发送3E 80请求(抑制肯定响应)")
        if not service_3E_check(node, 0x80, expect_data=None, expect_str="无响应"): return

        TestLog("INFO", "Step26", "等待4.5s")
        time.sleep(4.5)

        TestLog("INFO", "Step27", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG5_TC2_funRequest_3E_Positive():
    """
    3E服务肯定响应与功能检查(功能寻址)
    """
    case_name = "3E服务肯定响应与功能检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "等待4.5s")
        time.sleep(4.5)

        TestLog("INFO", "Step4", "发送3E 00请求(功能寻址)")
        if not service_3E_check(node, 0x00, expect_data=[0x7E, 0x00], expect_str="肯定响应(7E 00)", func_req=True): return

        TestLog("INFO", "Step5", "等待4.5s")
        time.sleep(4.5)

        TestLog("INFO", "Step6", "发送3E 80请求(功能寻址，抑制肯定响应)")
        if not service_3E_check(node, 0x80, expect_data=None, expect_str="无响应", func_req=True): return

        TestLog("INFO", "Step7", "等待4.5s")
        time.sleep(4.5)

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step9", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step10", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step12", "等待4.5s")
        time.sleep(4.5)

        TestLog("INFO", "Step13", "发送3E 00请求(功能寻址)")
        if not service_3E_check(node, 0x00, expect_data=[0x7E, 0x00], expect_str="肯定响应(7E 00)", func_req=True): return

        TestLog("INFO", "Step14", "等待4.5s")
        time.sleep(4.5)

        TestLog("INFO", "Step15", "发送3E 80请求(功能寻址，抑制肯定响应)")
        if not service_3E_check(node, 0x80, expect_data=None, expect_str="无响应", func_req=True): return

        TestLog("INFO", "Step16", "等待4.5s")
        time.sleep(4.5)

        TestLog("INFO", "Step17", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step18", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step19", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step20", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step21", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step22", "等待4.5s")
        time.sleep(4.5)

        TestLog("INFO", "Step23", "发送3E 00请求(功能寻址)")
        if not service_3E_check(node, 0x00, expect_data=[0x7E, 0x00], expect_str="肯定响应(7E 00)", func_req=True): return

        TestLog("INFO", "Step24", "等待4.5s")
        time.sleep(4.5)

        TestLog("INFO", "Step25", "发送3E 80请求(功能寻址，抑制肯定响应)")
        if not service_3E_check(node, 0x80, expect_data=None, expect_str="无响应", func_req=True): return

        TestLog("INFO", "Step26", "等待4.5s")
        time.sleep(4.5)

        TestLog("INFO", "Step27", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG5_TC3_phyRequest_3E_NRC12():
    """
    3E服务NRC12检查(物理寻址)
    """
    case_name = "3E服务NRC12检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    min_sn, max_sn = UDSTestParams.MinSubID, UDSTestParams.MaxSubID
    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3~6", "遍历不支持的子功能，发送3E SN请求，期望NRC12响应")
        for sn in range(min_sn, max_sn + 1):
            if sn in UDSTestParams.Services3ESubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)}，在3E服务支持的范围内，跳过该SN")
                continue
            TestLog("INFO", "", f"SN={hex(sn)}，不在3E服务支持的范围内，测试该SN")
            if not service_3E_check(node, sn, expect_data=[0x7F, 0x3E, 0x12], expect_str="否定响应(7F 3E 12)", force_recv=True): return

        TestLog("INFO", "Step7", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step8", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step10~13", "遍历不支持的子功能，发送3E SN请求，期望NRC12响应")
        for sn in range(min_sn, max_sn + 1):
            if sn in UDSTestParams.Services3ESubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)}，在3E服务支持的范围内，跳过该SN")
                continue
            TestLog("INFO", "", f"SN={hex(sn)}，不在3E服务支持的范围内，测试该SN")
            # force_recv=True，强制处理接收
            if not service_3E_check(node, sn, expect_data=[0x7F, 0x3E, 0x12], expect_str="否定响应(7F 3E 12)", force_recv=True): return

        TestLog("INFO", "Step14", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step15", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step16", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step17", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step18", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step19~22", "遍历不支持的子功能，发送3E SN请求，期望NRC12响应")
        for sn in range(min_sn, max_sn + 1):
            if sn in UDSTestParams.Services3ESubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)}，在3E服务支持的范围内，跳过该SN")
                continue
            TestLog("INFO", "", f"SN={hex(sn)}，不在3E服务支持的范围内，测试该SN")
            # force_recv=True，强制处理接收
            if not service_3E_check(node, sn, expect_data=[0x7F, 0x3E, 0x12], expect_str="否定响应(7F 3E 12)", force_recv=True): return

        TestLog("INFO", "Step23", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG5_TC4_funRequest_3E_NRC12():
    """
    3E服务NRC12检查(功能寻址)
    """
    case_name = "3E服务NRC12检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    min_sn, max_sn = UDSTestParams.MinSubID, UDSTestParams.MaxSubID
    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3~6", "遍历不支持的子功能，发送3E SN请求(功能寻址)，期望无响应")
        for sn in range(min_sn, max_sn + 1):
            if sn in UDSTestParams.Services3ESubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)}，在3E服务支持的范围内，跳过该SN")
                continue
            TestLog("INFO", "", f"SN={hex(sn)}，不在3E服务支持的范围内，测试该SN")
            if not service_3E_check(node, sn, expect_data=None, expect_str="无响应", func_req=True, force_recv=True, timeout=0.1): return

        TestLog("INFO", "Step7", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step8", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step10~13", "遍历不支持的子功能，发送3E SN请求(功能寻址)，期望无响应")
        for sn in range(min_sn, max_sn + 1):
            if sn in UDSTestParams.Services3ESubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)}，在3E服务支持的范围内，跳过该SN")
                continue
            TestLog("INFO", "", f"SN={hex(sn)}，不在3E服务支持的范围内，测试该SN")
            if not service_3E_check(node, sn, expect_data=None, expect_str="无响应", func_req=True, force_recv=True, timeout=0.1): return

        TestLog("INFO", "Step14", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step15", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step16", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step17", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step18", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step19~22", "遍历不支持的子功能，发送3E SN请求(功能寻址)，期望无响应")
        for sn in range(min_sn, max_sn + 1):
            if sn in UDSTestParams.Services3ESubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)}，在3E服务支持的范围内，跳过该SN")
                continue
            TestLog("INFO", "", f"SN={hex(sn)}，不在3E服务支持的范围内，测试该SN")
            if not service_3E_check(node, sn, expect_data=None, expect_str="无响应", func_req=True, force_recv=True, timeout=0.1): return

        TestLog("INFO", "Step23", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG5_TC5_phyRequest_3E_NRC13():
    """
    3E服务NRC13检查(物理寻址)
    """
    case_name = "3E服务NRC13检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送3E请求(DL=1)，期望NRC13响应")
        if not service_3E_check(node, None, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)", dl=1): return

        TestLog("INFO", "Step4", "发送3E 00请求(DL=3,4,5,6,7)，期望NRC13响应")
        for dl in [3, 4, 5, 6, 7]:
            TestLog("INFO", "", f"发送3E 00请求(DL={dl})")
            if not service_3E_check(node, 0x00, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)", dl=dl): return

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step6", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step7", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step9", "发送3E请求(DL=1)，期望NRC13响应")
        if not service_3E_check(node, None, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)", dl=1): return

        TestLog("INFO", "Step10", "发送3E 00请求(DL=3,4,5,6,7)，期望NRC13响应")
        for dl in [3, 4, 5, 6, 7]:
            TestLog("INFO", "", f"发送3E 00请求(DL={dl})")
            if not service_3E_check(node, 0x00, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)", dl=dl): return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step12", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step13", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step14", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step16", "发送3E请求(DL=1)，期望NRC13响应")
        if not service_3E_check(node, None, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)", dl=1): return

        TestLog("INFO", "Step17", "发送3E 00请求(DL=3,4,5,6,7)，期望NRC13响应")
        for dl in [3, 4, 5, 6, 7]:
            TestLog("INFO", "", f"发送3E 00请求(DL={dl})")
            if not service_3E_check(node, 0x00, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)", dl=dl): return

        TestLog("INFO", "Step18", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG5_TC6_funRequest_3E_NRC13():
    """
    3E服务NRC13检查(功能寻址)
    """
    case_name = "3E服务NRC13检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送3E请求(DL=1，功能寻址)，期望NRC13响应")
        if not service_3E_check(node, None, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)", dl=1, func_req=True): return

        TestLog("INFO", "Step4", "发送3E 00请求(DL=3,4,5,6,7，功能寻址)，期望NRC13响应")
        for dl in [3, 4, 5, 6, 7]:
            TestLog("INFO", "", f"发送3E 00请求(DL={dl}，功能寻址)")
            if not service_3E_check(node, 0x00, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)", dl=dl, func_req=True): return

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step6", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step7", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step9", "发送3E请求(DL=1，功能寻址)，期望NRC13响应")
        if not service_3E_check(node, None, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)", dl=1, func_req=True): return

        TestLog("INFO", "Step10", "发送3E 00请求(DL=3,4,5,6,7，功能寻址)，期望NRC13响应")
        for dl in [3, 4, 5, 6, 7]:
            TestLog("INFO", "", f"发送3E 00请求(DL={dl}，功能寻址)")
            if not service_3E_check(node, 0x00, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)", dl=dl, func_req=True): return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step12", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step13", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step14", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step16", "发送3E请求(DL=1，功能寻址)，期望NRC13响应")
        if not service_3E_check(node, None, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)", dl=1, func_req=True): return

        TestLog("INFO", "Step17", "发送3E 00请求(DL=3,4,5,6,7，功能寻址)，期望NRC13响应")
        for dl in [3, 4, 5, 6, 7]:
            TestLog("INFO", "", f"发送3E 00请求(DL={dl}，功能寻址)")
            if not service_3E_check(node, 0x00, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)", dl=dl, func_req=True): return

        TestLog("INFO", "Step18", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG5_TC7_phyRequest_3E_NRCPriority():
    """
    3E服务NRC优先级检查(物理寻址)
    """
    case_name = "3E服务NRC优先级检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送3E请求(DL=1)，期望NRC13响应")
        if not service_3E_check(node, None, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)", dl=1): return

        TestLog("INFO", "Step4", "发送3E 01 00请求(DL=3，不支持的子功能)，期望NRC12响应")
        if not service_3E_check(node, 0x01, expect_data=[0x7F, 0x3E, 0x12], expect_str="否定响应(7F 3E 12)", dl=3): return

        TestLog("INFO", "Step5", "发送3E 00 00请求(DL=3，支持的子功能+错误长度)，期望NRC13响应")
        if not service_3E_check(node, 0x00, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)", dl=3): return

        TestLog("INFO", "Step6", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG5_TC8_funRequest_3E_NRCPriority():
    """
    3E服务NRC优先级检查(功能寻址)
    """
    case_name = "3E服务NRC优先级检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送3E请求(DL=1，功能寻址)，期望NRC13响应")
        if not service_3E_check(node, None, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)", dl=1, func_req=True): return

        TestLog("INFO", "Step4", "发送3E 01 00请求(DL=3，功能寻址，不支持的子功能)，期望无响应")
        if not service_3E_check(node, 0x01, expect_data=None, expect_str="功能寻址NRC12抑制，无响应", dl=3, func_req=True): return

        TestLog("INFO", "Step5", "发送3E 00 00请求(DL=3，功能寻址，支持的子功能+错误长度)，期望NRC13响应")
        if not service_3E_check(node, 0x00, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)", dl=3, func_req=True): return

        TestLog("INFO", "Step6", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG6_TC1_phyRequest_85_Positive():
    case_name = "TG6_TC1_85服务肯定响应检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "发送85 02请求关闭DTC记录")
        if not service_85_check(node, 0x02, [0xC5, 0x02], "肯定响应(C5 02)"): return

        TestLog("INFO", "Step5", "发送85 01请求关闭DTC记录")
        if not service_85_check(node, 0x01, [0xC5, 0x01], "肯定响应(C5 01)"): return

        TestLog("INFO", "Step6", "发送85 82请求关闭DTC记录")
        if not service_85_check(node, 0x82, None, "无响应"): return

        TestLog("INFO", "Step7", "发送85 81请求关闭DTC记录")
        if not service_85_check(node, 0x81, None, "无响应"): return

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG6_TC2_funRequest_85_Positive():
    case_name = "TG6_TC1_85服务肯定响应检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "发送85 02请求关闭DTC记录")
        if not service_85_check(node, 0x02, [0xC5, 0x02], "肯定响应(C5 02)", func_req=True): return

        TestLog("INFO", "Step5", "发送85 01请求关闭DTC记录")
        if not service_85_check(node, 0x01, [0xC5, 0x01], "肯定响应(C5 01)", func_req=True): return

        TestLog("INFO", "Step6", "发送85 82请求关闭DTC记录")
        if not service_85_check(node, 0x82, None, "无响应", func_req=True): return

        TestLog("INFO", "Step7", "发送85 81请求关闭DTC记录")
        if not service_85_check(node, 0x81, None, "无响应", func_req=True): return

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return


    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG6_TC3_phyRequest_85_FunctionCheck():
    case_name = "TG6_TC3_85服务功能检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rVlow = 8
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        time.sleep(1)

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "开启3E服务")
        tester_present_start(node, period_ms=2000)

        TestLog("INFO", "Step5", "制造低压故障")
        ctx.power_ctrl.set_voltage(rVlow)
        time.sleep(5)

        TestLog("INFO", "Step6", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step7", "检查低压DTC是否被成功存储，若不成功，则终止测试项")
        # TODO 校验低压DTC

        TestLog("INFO", "Step8", "恢复正常供电电压")
        ctx.power_ctrl.set_voltage(rVnormal)
        time.sleep(1)

        TestLog("INFO", "Step9", "清除DUT中的DTC(14 FF FF FF)")
        status, _ = service_14_check(node, 0xFFFFFF, [0x54], "肯定响应(54)", timeout=100)
        if not status: return

        TestLog("INFO", "Step10", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step11", "检查低压DTC是否被成功清除")
        # TODO 校验低压DTC是否被清除

        TestLog("INFO", "Step12", "发送85 02请求关闭DTC记录")
        if not service_85_check(node, 0x02, [0xC5, 0x02], "肯定响应(C5 02)"): return

        TestLog("INFO", "Step13", "制造低压故障")
        ctx.power_ctrl.set_voltage(rVlow)
        time.sleep(5)

        TestLog("INFO", "Step14", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step15", "检查低压DTC是否被成功存储")
        # TODO 校验低压DTC

        TestLog("INFO", "Step16", "发送85 01请求开启DTC记录")
        if not service_85_check(node, 0x01, [0xC5, 0x01], "肯定响应(C5 01)"): return

        TestLog("INFO", "Step17", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step18", "检查低压DTC是否被成功存储")
        # TODO 校验低压DTC

        TestLog("INFO", "Step19", "恢复正常供电电压")
        ctx.power_ctrl.set_voltage(rVnormal)
        time.sleep(1)

        TestLog("INFO", "Step20", "清除DUT中的DTC(14 FF FF FF)")
        status, _ = service_14_check(node, 0xFFFFFF, [0x54], "肯定响应(54)", timeout=100)
        if not status: return

        TestLog("INFO", "Step21", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step22", "检查低压DTC是否被成功清除")
        # TODO 校验低压DTC是否被清除

        TestLog("INFO", "Step23", "发送85 82请求关闭DTC记录")
        service_85_check(node, 0x82, None, "无响应")
        time.sleep(1)

        TestLog("INFO", "Step24", "制造低压故障")
        ctx.power_ctrl.set_voltage(rVlow)
        time.sleep(5)

        TestLog("INFO", "Step25", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step26", "检查低压DTC是否被存储")
        # TODO 校验低压DTC是否被存储

        TestLog("INFO", "Step27", "发送85 81请求开启DTC记录")
        service_85_check(node, 0x81, None, "无响应")
        time.sleep(1)

        TestLog("INFO", "Step28", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step29", "检查低压DTC是否被存储")
        # TODO 校验低压DTC是否被存储

        TestLog("INFO", "Step30", "恢复正常供电电压")
        ctx.power_ctrl.set_voltage(rVnormal)
        time.sleep(1)

        TestLog("INFO", "Step31", "清除DUT中的DTC(14 FF FF FF)")
        status, _ = service_14_check(node, 0xFFFFFF, [0x54], "肯定响应(54)", timeout=100)
        if not status: return

        TestLog("INFO", "Step32", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step33", "检查低压DTC是否被成功清除")
        # TODO 校验低压DTC是否被清除

        TestLog("INFO", "Step34", "发送85 02请求关闭DTC记录")
        if not service_85_check(node, 0x02, [0xC5, 0x02], "肯定响应(C5 02)"): return

        TestLog("INFO", "Step35", "制造低压故障")
        ctx.power_ctrl.set_voltage(rVlow)
        time.sleep(5)

        TestLog("INFO", "Step36", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step37", "检查低压DTC是否被存储")
        # TODO 校验低压DTC是否被存储

        TestLog("INFO", "Step38", "发送10 01请求进入默认会话(跳转到默认会话使85服务功能失效)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step39", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step40", "检查低压DTC是否被存储")
        # TODO 校验低压DTC是否被存储

        TestLog("INFO", "Step41", "恢复正常供电电压")
        ctx.power_ctrl.set_voltage(rVnormal)
        time.sleep(1)

        TestLog("INFO", "Step42", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step43", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step44", "清除DUT中的DTC(14 FF FF FF)")
        status, _ = service_14_check(node, 0xFFFFFF, [0x54], "肯定响应(54)", timeout=100)
        if not status: return

        TestLog("INFO", "Step45", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step46", "检查低压DTC是否被成功清除")
        # TODO 校验低压DTC是否被清除

        TestLog("INFO", "Step47", "发送85 02请求关闭DTC记录")
        if not service_85_check(node, 0x02, [0xC5, 0x02], "肯定响应(C5 02)"): return

        TestLog("INFO", "Step48", "制造低压故障")
        ctx.power_ctrl.set_voltage(rVlow)
        time.sleep(5)

        TestLog("INFO", "Step49", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step50", "检查低压DTC是否被存储")
        # TODO 校验低压DTC是否被存储

        TestLog("INFO", "Step51", "发送11 01请求复位（复位使85服务功能失效）")
        if not service_11_check(node, 0x01, [0x51, 0x01], expect_str="肯定响应(51 01)"): return

        time.sleep(3)

        TestLog("INFO", "Step52", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09, timeout=100)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step53", "检查低压DTC是否被存储")
        # TODO 校验低压DTC是否被存储

        TestLog("INFO", "Step54", "恢复正常供电电压")
        ctx.power_ctrl.set_voltage(rVnormal)
        time.sleep(1)

        TestLog("INFO", "Step55", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step56", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step57", "清除DUT中的DTC(14 FF FF FF)")
        status, _ = service_14_check(node, 0xFFFFFF, [0x54], "肯定响应(54)", timeout=100)
        if not status: return

        TestLog("INFO", "Step58", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step59", "检查低压DTC是否被成功清除")
        # TODO 校验低压DTC是否被清除

        TestLog("INFO", "Step60", "发送85 02请求关闭DTC记录")
        if not service_85_check(node, 0x02, [0xC5, 0x02], "肯定响应(C5 02)"): return

        TestLog("INFO", "Step61", "制造低压故障")
        ctx.power_ctrl.set_voltage(rVlow)
        time.sleep(5)

        TestLog("INFO", "Step62", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step63", "检查低压DTC是否被存储")
        # TODO 校验低压DTC是否被存储

        TestLog("INFO", "Step64", "等待6s（S3 Server超时使85服务功能失效）")
        time.sleep(6)

        TestLog("INFO", "Step65", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step66", "检查低压DTC是否被存储")
        # TODO 校验低压DTC是否被存储

        TestLog("INFO", "Step67", "恢复正常供电电压")
        ctx.power_ctrl.set_voltage(rVnormal)
        time.sleep(1)

        TestLog("INFO", "Step68", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step69", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step70", "清除DUT中的DTC(14 FF FF FF)")
        status, _ = service_14_check(node, 0xFFFFFF, [0x54], "肯定响应(54)", timeout=100)
        if not status: return

        TestLog("INFO", "Step71", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step72", "检查低压DTC是否被成功清除")
        # TODO 校验低压DTC是否被清除

        TestLog("INFO", "Step73", "发送85 02请求关闭DTC记录")
        if not service_85_check(node, 0x02, [0xC5, 0x02], "肯定响应(C5 02)"): return

        TestLog("INFO", "Step74", "制造低压故障")
        ctx.power_ctrl.set_voltage(rVlow)
        time.sleep(5)

        TestLog("INFO", "Step75", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step76", "检查低压DTC是否被存储")
        # TODO 校验低压DTC是否被存储

        TestLog("INFO", "Step77", "DUT重新上电（重新上下电使85服务功能失效）")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        time.sleep(1)

        TestLog("INFO", "Step78", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step79", "检查低压DTC是否被存储")
        # TODO 校验低压DTC是否被存储

        TestLog("INFO", "Step80", "恢复正常供电电压")
        ctx.power_ctrl.set_voltage(rVnormal)
        time.sleep(1)

        TestLog("INFO", "Step81", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()


def test_TG6_TC4_funRequest_85_FunctionCheck():
    case_name = "TG6_TC4_85服务功能检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rVlow = P.CANInfo.VlowStand
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "开启3E服务")
        tester_present_start(node, period_ms=2000)

        TestLog("INFO", "Step5", "制造低压故障")
        ctx.power_ctrl.set_voltage(rVlow)
        time.sleep(5)

        TestLog("INFO", "Step6", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step7", "检查低压DTC是否被成功存储，若不成功，则终止测试项")
        # TODO 校验低压DTC

        TestLog("INFO", "Step8", "恢复正常供电电压")
        ctx.power_ctrl.set_voltage(rVnormal)
        time.sleep(1)

        TestLog("INFO", "Step9", "清除DUT中的DTC(14 FF FF FF)")
        status, _ = service_14_check(node, 0xFFFFFF, [0x54], "肯定响应(54)", timeout=100)
        if not status: return

        TestLog("INFO", "Step10", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step11", "检查低压DTC是否被成功清除")
        # TODO 校验低压DTC是否被清除

        TestLog("INFO", "Step12", "发送85 02请求关闭DTC记录")
        if not service_85_check(node, 0x02, [0xC5, 0x02], "肯定响应(C5 02)", func_req=True): return

        TestLog("INFO", "Step13", "制造低压故障")
        ctx.power_ctrl.set_voltage(rVlow)
        time.sleep(5)

        TestLog("INFO", "Step14", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step15", "检查低压DTC是否被成功存储")
        # TODO 校验低压DTC

        TestLog("INFO", "Step16", "发送85 01请求开启DTC记录")
        if not service_85_check(node, 0x01, [0xC5, 0x01], "肯定响应(C5 01)", func_req=True): return

        TestLog("INFO", "Step17", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step18", "检查低压DTC是否被成功存储")
        # TODO 校验低压DTC

        TestLog("INFO", "Step19", "恢复正常供电电压")
        ctx.power_ctrl.set_voltage(rVnormal)
        time.sleep(1)

        TestLog("INFO", "Step20", "清除DUT中的DTC(14 FF FF FF)")
        status, _ = service_14_check(node, 0xFFFFFF, [0x54], "肯定响应(54)", timeout=100)
        if not status: return

        TestLog("INFO", "Step21", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step22", "检查低压DTC是否被成功清除")
        # TODO 校验低压DTC是否被清除

        TestLog("INFO", "Step23", "发送85 82请求关闭DTC记录")
        if not service_85_check(node, 0x82, None, "无响应", func_req=True): return

        TestLog("INFO", "Step24", "制造低压故障")
        ctx.power_ctrl.set_voltage(rVlow)
        time.sleep(5)

        TestLog("INFO", "Step25", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step26", "检查低压DTC是否被存储")
        # TODO 校验低压DTC是否被存储

        TestLog("INFO", "Step27", "发送85 81请求开启DTC记录")
        if not service_85_check(node, 0x81, None, "无响应", func_req=True): return

        TestLog("INFO", "Step28", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step29", "检查低压DTC是否被存储")
        # TODO 校验低压DTC是否被存储

        TestLog("INFO", "Step30", "恢复正常供电电压")
        ctx.power_ctrl.set_voltage(rVnormal)
        time.sleep(1)

        TestLog("INFO", "Step31", "清除DUT中的DTC(14 FF FF FF)")
        status, _ = service_14_check(node, 0xFFFFFF, [0x54], "肯定响应(54)", timeout=100)
        if not status: return

        TestLog("INFO", "Step32", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step33", "检查低压DTC是否被成功清除")
        # TODO 校验低压DTC是否被清除

        TestLog("INFO", "Step34", "发送85 02请求关闭DTC记录")
        if not service_85_check(node, 0x02, [0xC5, 0x02], "肯定响应(C5 02)", func_req=True): return

        TestLog("INFO", "Step35", "制造低压故障")
        ctx.power_ctrl.set_voltage(rVlow)
        time.sleep(5)

        TestLog("INFO", "Step36", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step37", "检查低压DTC是否被存储")
        # TODO 校验低压DTC是否被存储

        TestLog("INFO", "Step38", "发送10 01请求进入默认会话(跳转到默认会话使85服务功能失效)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step39", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step40", "检查低压DTC是否被存储")
        # TODO 校验低压DTC是否被存储

        TestLog("INFO", "Step41", "恢复正常供电电压")
        ctx.power_ctrl.set_voltage(rVnormal)
        time.sleep(1)

        TestLog("INFO", "Step42", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step43", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step44", "清除DUT中的DTC(14 FF FF FF)")
        status, _ = service_14_check(node, 0xFFFFFF, [0x54], "肯定响应(54)", timeout=100)
        if not status: return

        TestLog("INFO", "Step45", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step46", "检查低压DTC是否被成功清除")
        # TODO 校验低压DTC是否被清除

        TestLog("INFO", "Step47", "发送85 02请求关闭DTC记录")
        if not service_85_check(node, 0x02, [0xC5, 0x02], "肯定响应(C5 02)", func_req=True): return

        TestLog("INFO", "Step48", "制造低压故障")
        ctx.power_ctrl.set_voltage(rVlow)
        time.sleep(5)

        TestLog("INFO", "Step49", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step50", "检查低压DTC是否被存储")
        # TODO 校验低压DTC是否被存储

        TestLog("INFO", "Step51", "发送11 01请求复位（复位使85服务功能失效）")
        if not service_11_check(node, 0x01, [0x51, 0x01], expect_str="肯定响应(51 01)"): return

        TestLog("INFO", "Step52", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step53", "检查低压DTC是否被存储")
        # TODO 校验低压DTC是否被存储

        TestLog("INFO", "Step54", "恢复正常供电电压")
        ctx.power_ctrl.set_voltage(rVnormal)
        time.sleep(1)

        TestLog("INFO", "Step55", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step56", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step57", "清除DUT中的DTC(14 FF FF FF)")
        status, _ = service_14_check(node, 0xFFFFFF, [0x54], "肯定响应(54)", timeout=100)
        if not status: return

        TestLog("INFO", "Step58", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step59", "检查低压DTC是否被成功清除")
        # TODO 校验低压DTC是否被清除

        TestLog("INFO", "Step60", "发送85 02请求关闭DTC记录")
        if not service_85_check(node, 0x02, [0xC5, 0x02], "肯定响应(C5 02)", func_req=True): return

        TestLog("INFO", "Step61", "制造低压故障")
        ctx.power_ctrl.set_voltage(rVlow)
        time.sleep(5)

        TestLog("INFO", "Step62", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step63", "检查低压DTC是否被存储")
        # TODO 校验低压DTC是否被存储

        TestLog("INFO", "Step64", "等待6s（S3 Server超时使85服务功能失效）")
        time.sleep(6)

        TestLog("INFO", "Step65", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step66", "检查低压DTC是否被存储")
        # TODO 校验低压DTC是否被存储

        TestLog("INFO", "Step67", "恢复正常供电电压")
        ctx.power_ctrl.set_voltage(rVnormal)
        time.sleep(1)

        TestLog("INFO", "Step68", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step69", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step70", "清除DUT中的DTC(14 FF FF FF)")
        status, _ = service_14_check(node, 0xFFFFFF, [0x54], "肯定响应(54)", timeout=100)
        if not status: return

        TestLog("INFO", "Step71", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step72", "检查低压DTC是否被成功清除")
        # TODO 校验低压DTC是否被清除

        TestLog("INFO", "Step73", "发送85 02请求关闭DTC记录")
        if not service_85_check(node, 0x02, [0xC5, 0x02], "肯定响应(C5 02)", func_req=True): return

        TestLog("INFO", "Step74", "制造低压故障")
        ctx.power_ctrl.set_voltage(rVlow)
        time.sleep(5)

        TestLog("INFO", "Step75", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step76", "检查低压DTC是否被存储")
        # TODO 校验低压DTC是否被存储

        TestLog("INFO", "Step77", "DUT重新上电（重新上下电使85服务功能失效）")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        time.sleep(1)

        TestLog("INFO", "Step78", "发送19 02 09")
        status, resp = service_19_check(node, 0x02, expect_data=[0x59], expect_str="肯定响应(0x59)", DTCStatusMask=0x09)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        TestLog("INFO", "Step79", "检查低压DTC是否被存储")
        # TODO 校验低压DTC是否被存储

        TestLog("INFO", "Step80", "恢复正常供电电压")
        ctx.power_ctrl.set_voltage(rVnormal)
        time.sleep(1)

        TestLog("INFO", "Step81", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        # 停止3E 80
        tester_present_stop()


def test_TG6_TC5_phyRequest_85_NRC12():
    case_name = "TG6_TC5_85服务NRC12检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    min_sn, max_sn = UDSTestParams.MinSubID, UDSTestParams.MaxSubID
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        time.sleep(2)

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "令SN=0x00")
        TestLog("INFO", "Step5", "如果SN为支持的物理寻址子功能且SN<0xFF，则SN+=1，直到SN为不支持的物理寻址子功能")
        for sn in range(min_sn, max_sn + 1):
            if sn in UDSTestParams.Services85SubFunSupportList:
                continue
            TestLog("INFO", "Step6", f"发送子功能={sn}的85服务请求")
            if not service_85_check(node, sn, expect_data=[0x7F, 0x85, 0x12], expect_str="否定响应(7F 85 12)"): return
            TestLog("INFO", "Step7", f"如果SN<0xFF，SN+=1，然后跳转到步骤5")

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG6_TC6_funRequest_85_NRC12():
    case_name = "TG6_TC6_85服务NRC12检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    min_sn, max_sn = UDSTestParams.MinSubID, UDSTestParams.MaxSubID
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        time.sleep(2)

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "令SN=0x00")
        TestLog("INFO", "Step5", "如果SN为支持的物理寻址子功能且SN<0xFF，则SN+=1，直到SN为不支持的物理寻址子功能")
        for sn in range(min_sn, max_sn + 1):
            if sn in UDSTestParams.Services85SubFunSupportList:
                continue
            TestLog("INFO", "Step6", f"发送子功能={sn}的85服务请求")
            if not service_85_check(node, sn, None, expect_str="无响应", func_req=True, timeout=0.1): return
            TestLog("INFO", "Step7", f"如果SN<0xFF，SN+=1，然后跳转到步骤5")

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return


    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG6_TC7_phyRequest_85_NRC13():
    case_name = "TG6_TC7_85服务NRC13检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "发送长度为1的85请求")
        if not service_85_check(node, None, expect_data=[0x7F, 0x85, 0x13], expect_str="否定响应(7F 85 13)"): return

        TestLog("INFO", "Step5", "发送DL=3、4、5、6、7的85 01请求")
        for dl in [3, 4, 5, 6, 7]:
            if not service_85_check(node, 0x01, expect_data=[0x7F, 0x85, 0x13], expect_str="否定响应(7F 85 13)", dl=dl, dl_padding=0x00): return

        TestLog("INFO", "Step6", "发送DL=3、4、5、6、7的85 02请求")
        for dl in [3, 4, 5, 6, 7]:
            if not service_85_check(node, 0x02, expect_data=[0x7F, 0x85, 0x13], expect_str="否定响应(7F 85 13)", dl=dl, dl_padding=0x00): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG6_TC8_funRequest_85_NRC13():
    case_name = "TG6_TC8_85服务NRC13检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "发送长度为1的85请求")
        if not service_85_check(node, None, expect_data=[0x7F, 0x85, 0x13], expect_str="否定响应(7F 85 13)", func_req=True): return

        TestLog("INFO", "Step5", "发送DL=3、4、5、6、7的85 01请求")
        for dl in [3, 4, 5, 6, 7]:
            if not service_85_check(node, 0x01, expect_data=[0x7F, 0x85, 0x13], expect_str="否定响应(7F 85 13)", dl=dl, dl_padding=0x00, func_req=True): return

        TestLog("INFO", "Step6", "发送DL=3、4、5、6、7的85 02请求")
        for dl in [3, 4, 5, 6, 7]:
            if not service_85_check(node, 0x02, expect_data=[0x7F, 0x85, 0x13], expect_str="否定响应(7F 85 13)", dl=dl, dl_padding=0x00, func_req=True): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG6_TC9_phyRequest_85_NRC7F():
    case_name = "TG6_TC9_85服务NRC7F检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送子功能为0x01、0x02的85服务请求")
        for sn in [0x01, 0x02]:
            if not service_85_check(node, sn, expect_data=[0x7F, 0x85, 0x7F], expect_str="否定响应(7F 85 7F)"): return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step6", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step10", "发送子功能为0x01、0x02的85服务请求")
        for sn in [0x01, 0x02]:
            if not service_85_check(node, sn, expect_data=[0x7F, 0x85, 0x11], expect_str="否定响应(7F 85 11)"): return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG6_TC10_funRequest_85_NRC7F():
    case_name = "TG6_TC10_85服务NRC7F检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送子功能为0x01、0x02的85服务请求")
        for sn in [0x01, 0x02]:
            if not service_85_check(node, sn, expect_data=None, expect_str="无响应", func_req=True): return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step6", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step10", "发送子功能为0x01、0x02的85服务请求")
        for sn in [0x01, 0x02]:
            if not service_85_check(node, sn, expect_data=None, expect_str="无响应", func_req=True): return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG6_TC11_phyRequest_85_NRC22():
    case_name = "TG6_TC11_85服务NRC22检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "遍历触发NRC22的所有条件并发送子功能SN=01、02的85服务请求")
        condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x85)
        if len(condition_list) == 0:
            TestLog("WARNING", "Step4", "未配置85服务可执行的NRC22条件，跳过该测试")
            return
        for condition in condition_list:
            if not start_nrc22_condition(condition): continue
            try:
                for sn in [0x01, 0x02]:
                    if not service_85_check(node, sn, expect_data=[0x7F, 0x85, 0x22], expect_str="否定响应(7F 85 22)"): return
            finally:
                stop_nrc22_condition(condition)

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG6_TC12_funRequest_85_NRC22():
    case_name = "TG6_TC12_85服务NRC22检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)", func_req=True): return

        TestLog("INFO", "Step2", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)", func_req=True): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "遍历触发NRC22的所有条件并发送子功能SN=01、02的85服务请求")
        condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x85)
        if len(condition_list) == 0:
            TestLog("WARNING", "Step4", "未配置85服务可执行的NRC22条件，跳过该测试")
            return
        for condition in condition_list:
            if not start_nrc22_condition(condition): continue
            try:
                for sn in [0x01, 0x02]:
                    if not service_85_check(node, sn, expect_data=[0x7F, 0x85, 0x22], expect_str="否定响应(7F 85 22)", func_req=True): return
            finally:
                stop_nrc22_condition(condition)

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return


    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG6_TC13_phyRequest_85_NRCPriorityCheck():
    case_name = "TG6_TC13_85服务NRC优先级检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "遍历触发NRC22的所有条件并发送85 01服务请求")
        condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x85)
        if len(condition_list) > 0:
            condition = condition_list[0]
            if not start_nrc22_condition(condition): return
            try:
                if not service_85_check(node, 0x01, expect_data=[0x7F, 0x85, 0x22], expect_str="否定响应(7F 85 22)"): return
            finally:
                stop_nrc22_condition(condition)
        else:
            TestLog("WARNING", "Step3", "未配置85服务可执行的NRC22条件，跳过NRC22优先级子步骤")

        TestLog("INFO", "Step4", "发送85 03服务请求")
        if not service_85_check(node, 0x03, expect_data=[0x7F, 0x85, 0x7F], expect_str="否定响应(7F 85 7F)"): return

        TestLog("INFO", "Step5", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step6", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step7", "发送85请求")
        if not service_85_check(node, None, expect_data=[0x7F, 0x85, 0x13], expect_str="否定响应(7F 85 13)"): return

        TestLog("INFO", "Step8", "发送85 03 00请求")
        if not service_85_check(node, 0x03, expect_data=[0x7F, 0x85, 0x12], expect_str="否定响应(7F 85 12)", dl=3, dl_padding=0x00): return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG6_TC14_funRequest_85_NRCPriorityCheck():
    case_name = "TG6_TC14_85服务NRC优先级检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "遍历触发NRC22的所有条件并发送85 01服务请求")
        condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x85)
        if len(condition_list) > 0:
            condition = condition_list[0]
            if not start_nrc22_condition(condition): return
            try:
                if not service_85_check(node, 0x01, expect_data=[0x7F, 0x85, 0x22], expect_str="否定响应(7F 85 22)", func_req=True): return
            finally:
                stop_nrc22_condition(condition)
        else:
            TestLog("WARNING", "Step3", "未配置85服务可执行的NRC22条件，跳过NRC22优先级子步骤")

        TestLog("INFO", "Step4", "发送85 03服务请求")
        if not service_85_check(node, 0x03, expect_data=[0x7F, 0x85, 0x7F], expect_str="否定响应(7F 85 7F)", func_req=True): return

        TestLog("INFO", "Step5", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step6", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step7", "发送85请求")
        if not service_85_check(node, None, expect_data=[0x7F, 0x85, 0x13], expect_str="否定响应(7F 85 13)", func_req=True): return

        TestLog("INFO", "Step8", "发送85 03 00请求")
        if not service_85_check(node, 0x03, expect_data=[0x7F, 0x85, 0x12], expect_str="否定响应(7F 85 12)", dl=3, dl_padding=0x00, func_req=True): return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return


    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG7_TC1_phyRequest_22_Positive():
    """
    22服务肯定响应检查(物理寻址)
    """
    case_name = "22服务肯定响应检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "遍历所有22服务支持的DID(默认会话)")
        did_list = UDSTestParams.Services22DIDSupportList_Default
        for did in did_list:
            status, _ = service_22_check(node, did, [0x62, (did>>8)&0xFF, did&0xFF], f"肯定响应(62 {(did>>8)&0xFF:02X} {did&0xFF:02X} ...)")
            if not status: return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step6", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "发送27 01请求")
        status, resp = service_27_check(node, 0x01, [0x67, 0x01], "返回种子(67 01 XX XX XX XX)")
        if not status: return
        seed = get_seed_from_27_resp(resp)

        TestLog("INFO", "Step9", "发送27 02请求")
        if not service_27_xx_check(node, 0x02, seed, [0x67, 0x02], "肯定响应，解锁成功(67 02)", AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step10", "遍历所有22服务支持的DID(扩展会话)")
        did_list = UDSTestParams.Services22DIDSupportList_Extended
        for did in did_list:
            status, _ = service_22_check(node, did, [0x62, (did>>8)&0xFF, did&0xFF], f"肯定响应(62 {(did>>8)&0xFF:02X} {did&0xFF:02X} ...)")
            if not status: return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step12", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step13", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step14", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step15", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        TestLog("INFO", "Step16", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        # tester_present_start(node)
        # time.sleep(15)
        # tester_present_stop()

        TestLog("INFO", "Step17", "发送27 11请求")
        status, resp = service_27_check(node, 0x11, [0x67, 0x11], "返回种子(67 11 XX XX XX XX)")
        if not status: return
        seed = get_seed_from_27_resp(resp)

        TestLog("INFO", "Step18", "发送27 12请求")
        if not service_27_xx_check(node, 0x12, seed, [0x67, 0x12], "肯定响应，解锁成功(67 12)", AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step19", "遍历所有22服务支持的DID(刷新会话)")
        did_list = UDSTestParams.Services22DIDSupportList_Programming
        for did in did_list:
            status, _ = service_22_check(node, did, [0x62, (did>>8)&0xFF, did&0xFF], f"肯定响应(62 {(did>>8)&0xFF:02X} {did&0xFF:02X} ...)")
            if not status: return

        TestLog("INFO", "Step20", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG7_TC2_funRequest_22_Positive():
    """
    22服务肯定响应检查(功能寻址)
    """
    case_name = "22服务肯定响应检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "遍历所有22服务支持的DID(默认会话，功能寻址)")
        did_list = UDSTestParams.Services22DIDSupportList_Default
        for did in did_list:
            status, _ = service_22_check(node, did, [0x62, (did>>8)&0xFF, did&0xFF], f"肯定响应(62 {(did>>8)&0xFF:02X} {did&0xFF:02X} ...)", func_req=True)
            if not status: return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step6", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "发送27 01请求")
        status, resp = service_27_check(node, 0x01, [0x67, 0x01], "返回种子(67 01 XX XX XX XX)")
        if not status: return
        seed = get_seed_from_27_resp(resp)

        TestLog("INFO", "Step9", "发送27 02请求")
        if not service_27_xx_check(node, 0x02, seed, [0x67, 0x02], "肯定响应，解锁成功(67 02)", AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step10", "遍历所有22服务支持的DID(扩展会话，功能寻址)")
        did_list = UDSTestParams.Services22DIDSupportList_Extended
        for did in did_list:
            status, _ = service_22_check(node, did, [0x62, (did>>8)&0xFF, did&0xFF], f"肯定响应(62 {(did>>8)&0xFF:02X} {did&0xFF:02X} ...)", func_req=True)
            if not status: return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step12", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step13", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step14", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step16", "发送27 11请求")
        status, resp = service_27_check(node, 0x11, [0x67, 0x11], "返回种子(67 11 XX XX XX XX)")
        if not status: return
        seed = get_seed_from_27_resp(resp)

        TestLog("INFO", "Step17", "发送27 12请求")
        if not service_27_xx_check(node, 0x12, seed, [0x67, 0x12], "肯定响应，解锁成功(67 12)", AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step18", "遍历所有22服务支持的DID(刷新会话，功能寻址)")
        did_list = UDSTestParams.Services22DIDSupportList_Programming
        for did in did_list:
            status, _ = service_22_check(node, did, [0x62, (did>>8)&0xFF, did&0xFF], f"肯定响应(62 {(did>>8)&0xFF:02X} {did&0xFF:02X} ...)", func_req=True)
            if not status: return

        TestLog("INFO", "Step19", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG7_TC3_phyRequest_22_MultiRead():
    """
    22服务多数据读取检查(物理寻址)
    """
    case_name = "22服务多数据读取检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        max_mul_did = P.DiagServiceInfo.MaxMulDIDNumber

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", f"以最大数目({max_mul_did})读取22服务支持的DID")
        did_list = UDSTestParams.Services22DIDSupportList_Default[:max_mul_did]
        if len(did_list) > 0:
            status, _ = service_22_check(node, did_list, [0x62], "肯定响应(62 ...)")
            if not status: return

        TestLog("INFO", "Step4", "多数据读取仅使用ReadDIDs配置项，不自动追加配置外不支持DID")

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step6", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step7", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step9", f"以最大数目({max_mul_did})读取22服务支持的DID")
        did_list = UDSTestParams.Services22DIDSupportList_Extended[:max_mul_did]
        if len(did_list) > 0:
            status, _ = service_22_check(node, did_list, [0x62], "肯定响应(62 ...)")
            if not status: return

        TestLog("INFO", "Step10", "多数据读取仅使用ReadDIDs配置项，不自动追加配置外不支持DID")

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step12", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step13", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step14", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step16", f"以最大数目({max_mul_did})读取22服务支持的DID")
        did_list = UDSTestParams.Services22DIDSupportList_Programming[:max_mul_did]
        if len(did_list) > 0:
            status, _ = service_22_check(node, did_list, [0x62], "肯定响应(62 ...)")
            if not status: return

        TestLog("INFO", "Step17", "多数据读取仅使用ReadDIDs配置项，不自动追加配置外不支持DID")

        TestLog("INFO", "Step18", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG7_TC4_funRequest_22_MultiRead():
    """
    22服务多数据读取检查(功能寻址)
    """
    case_name = "22服务多数据读取检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        max_mul_did = min(P.DiagServiceInfo.MaxMulDIDNumber, 3)

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", f"如果同时读取的最大数量大于3，设置最大数量为3 (当前: {max_mul_did})")

        TestLog("INFO", "Step4", f"以最大数目({max_mul_did})读取22服务支持的DID(功能寻址)")
        did_list = UDSTestParams.Services22DIDSupportList_Default[:max_mul_did]
        if len(did_list) > 0:
            status, _ = service_22_check(node, did_list, [0x62], "肯定响应(62 ...)", func_req=True)
            if not status: return

        TestLog("INFO", "Step5", "多数据读取仅使用ReadDIDs配置项，不自动追加配置外不支持DID(功能寻址)")

        TestLog("INFO", "Step6", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step7", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step8", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step10", f"以最大数目({max_mul_did})读取22服务支持的DID(功能寻址)")
        did_list = UDSTestParams.Services22DIDSupportList_Extended[:max_mul_did]
        if len(did_list) > 0:
            status, _ = service_22_check(node, did_list, [0x62], "肯定响应(62 ...)", func_req=True)
            if not status: return

        TestLog("INFO", "Step11", "多数据读取仅使用ReadDIDs配置项，不自动追加配置外不支持DID(功能寻址)")

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step13", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step14", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step15", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        TestLog("INFO", "Step16", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step17", f"以最大数目({max_mul_did})读取22服务支持的DID(功能寻址)")
        did_list = UDSTestParams.Services22DIDSupportList_Programming[:max_mul_did]
        if len(did_list) > 0:
            status, _ = service_22_check(node, did_list, [0x62], "肯定响应(62 ...)", func_req=True)
            if not status: return

        TestLog("INFO", "Step18", "多数据读取仅使用ReadDIDs配置项，不自动追加配置外不支持DID(功能寻址)")

        TestLog("INFO", "Step19", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG7_TC5_phyRequest_22_NRC31():
    """
    22服务NRC31检查(物理寻址)
    """
    case_name = "22服务NRC31检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "遍历所有22服务不支持的DID(默认会话)")
        unsupported_did_list = UDSTestParams.Services22DIDUnsupportedList
        for did in unsupported_did_list:
            status, _ = service_22_check(node, did, [0x7F, 0x22, 0x31], f"否定响应，NRC=0x31(7F 22 31)")
            if not status: return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step6", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "遍历所有22服务不支持的DID(扩展会话)")
        for did in unsupported_did_list:
            status, _ = service_22_check(node, did, [0x7F, 0x22, 0x31], f"否定响应，NRC=0x31(7F 22 31)")
            if not status: return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step10", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step11", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step12", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        TestLog("INFO", "Step13", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step14", "遍历所有22服务不支持的DID(刷新会话)")
        for did in unsupported_did_list:
            status, _ = service_22_check(node, did, [0x7F, 0x22, 0x31], f"否定响应，NRC=0x31(7F 22 31)")
            if not status: return

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG7_TC6_funRequest_22_NRC31():
    """
    22服务NRC31检查(功能寻址)
    """
    case_name = "22服务NRC31检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "遍历所有22服务不支持的DID(默认会话，功能寻址)")
        unsupported_did_list = UDSTestParams.Services22DIDUnsupportedList
        for did in unsupported_did_list:
            status, _ = service_22_check(node, did, None, "无响应", func_req=True, timeout=0.1)
            if not status: return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step6", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "遍历所有22服务不支持的DID(扩展会话，功能寻址)")
        for did in unsupported_did_list:
            status, _ = service_22_check(node, did, None, "无响应", func_req=True, timeout=0.1)
            if not status: return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step10", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step11", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step12", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        TestLog("INFO", "Step13", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step14", "遍历所有22服务不支持的DID(刷新会话，功能寻址)")
        for did in unsupported_did_list:
            status, _ = service_22_check(node, did, None, "无响应", func_req=True, timeout=0.1)
            if not status: return

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG7_TC7_phyRequest_22_NRC13():
    """
    22服务NRC13检查(物理寻址)
    """
    case_name = "22服务NRC13检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        invalid_dl_list = [
            (1, "DL=1, 只有SID"),
            (2, "DL=2, SID+1字节(有效位用00填充)"),
            (4, "DL=4, SID+3字节(有效位用00填充)"),
            (6, "DL=6, SID+5字节(有效位用00填充)"),
            (8, "DL=8, SID+7字节(有效位用00填充)"),
        ]

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送错误长度的22服务请求(默认会话)")
        for dl, desc in invalid_dl_list:
            TestLog("INFO", "Step3", f"发送 {desc}")
            status, _ = service_22_check(node, None, [0x7F, 0x22, 0x13], f"否定响应，NRC=0x13(7F 22 13)", dl=dl, dl_padding=0x00)
            if not status: return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step6", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        time.sleep(2)

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "发送错误长度的22服务请求(扩展会话)")
        for dl, desc in invalid_dl_list:
            TestLog("INFO", "Step8", f"发送 {desc}")
            status, _ = service_22_check(node, None, [0x7F, 0x22, 0x13], f"否定响应，NRC=0x13(7F 22 13)", dl=dl, dl_padding=0x00)
            if not status: return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step10", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step11", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step12", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        TestLog("INFO", "Step13", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step14", "发送错误长度的22服务请求(刷新会话)")
        for dl, desc in invalid_dl_list:
            TestLog("INFO", "Step14", f"发送 {desc}")
            status, _ = service_22_check(node, None, [0x7F, 0x22, 0x13], f"否定响应，NRC=0x13(7F 22 13)", dl=dl, dl_padding=0x00)
            if not status: return

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG7_TC8_funRequest_22_NRC13():
    """
    22服务NRC13检查(功能寻址)
    """
    case_name = "22服务NRC13检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        invalid_dl_list = [
            (1, "DL=1, 只有SID"),
            (2, "DL=2, SID+1字节(有效位用00填充)"),
            (4, "DL=4, SID+3字节(有效位用00填充)"),
            (6, "DL=6, SID+5字节(有效位用00填充)"),
        ]

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送错误长度的22服务请求(默认会话，功能寻址)")
        for dl, desc in invalid_dl_list:
            TestLog("INFO", "Step3", f"发送 {desc}")
            status, _ = service_22_check(node, None, [0x7F, 0x22, 0x13], f"否定响应，NRC=0x13(7F 22 13)", func_req=True, dl=dl, dl_padding=0x00)
            if not status: return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step6", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "发送错误长度的22服务请求(扩展会话，功能寻址)")
        for dl, desc in invalid_dl_list:
            TestLog("INFO", "Step8", f"发送 {desc}")
            status, _ = service_22_check(node, None, [0x7F, 0x22, 0x13], f"否定响应，NRC=0x13(7F 22 13)", func_req=True, dl=dl, dl_padding=0x00)
            if not status: return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step10", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step11", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step12", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        TestLog("INFO", "Step13", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step14", "发送错误长度的22服务请求(刷新会话，功能寻址)")
        for dl, desc in invalid_dl_list:
            TestLog("INFO", "Step14", f"发送 {desc}")
            status, _ = service_22_check(node, None, [0x7F, 0x22, 0x13], f"否定响应，NRC=0x13(7F 22 13)", func_req=True, dl=dl, dl_padding=0x00)
            if not status: return

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG7_TC9_phyRequest_22_NRC33():
    """
    22服务NRC33检查(物理寻址)
    """
    case_name = "22服务NRC33检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        security_required_did_list = UDSTestParams.Services22DIDSecurityRequiredList
        if len(security_required_did_list) == 0:
            TestLog("INFO", "Skip", "没有配置需要安全访问的DID，跳过此测试")
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "遍历所有需要安全访问解锁的DID(扩展会话)")
        for did in security_required_did_list:
            status, _ = service_22_check(node, did, [0x7F, 0x22, 0x33], f"否定响应，NRC=0x33(7F 22 33)")
            if not status: return

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step6", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step7", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step8", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step10", "遍历所有22服务支持的DID(刷新会话)")
        did_list = UDSTestParams.Services22DIDSupportList_Programming
        for did in did_list:
            status, _ = service_22_check(node, did, [0x62, (did>>8)&0xFF, did&0xFF], f"肯定响应(62 {(did>>8)&0xFF:02X} {did&0xFF:02X} ...)")
            if not status: return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step12", "遍历所有需要安全访问解锁的DID(刷新会话)")
        for did in security_required_did_list:
            status, _ = service_22_check(node, did, [0x7F, 0x22, 0x33], f"否定响应，NRC=0x33(7F 22 33)")
            if not status: return

        TestLog("INFO", "Step13", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG7_TC10_funRequest_22_NRC33():
    """
    22服务NRC33检查(功能寻址)
    """
    case_name = "22服务NRC33检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        security_required_did_list = UDSTestParams.Services22DIDSecurityRequiredList
        if len(security_required_did_list) == 0:
            TestLog("INFO", "Skip", "没有配置需要安全访问的DID，跳过此测试")
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "遍历所有需要安全访问解锁的DID(扩展会话，功能寻址)")
        for did in security_required_did_list:
            status, _ = service_22_check(node, did, [0x7F, 0x22, 0x33], f"否定响应，NRC=0x33(7F 22 33)", func_req=True)
            if not status: return

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step6", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step7", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step8", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step10", "遍历所有22服务支持的DID(刷新会话，功能寻址)")
        did_list = UDSTestParams.Services22DIDSupportList_Programming
        for did in did_list:
            status, _ = service_22_check(node, did, [0x62, (did>>8)&0xFF, did&0xFF], f"肯定响应(62 {(did>>8)&0xFF:02X} {did&0xFF:02X} ...)", func_req=True)
            if not status: return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step12", "遍历所有需要安全访问解锁的DID(刷新会话，功能寻址)")
        for did in security_required_did_list:
            status, _ = service_22_check(node, did, [0x7F, 0x22, 0x33], f"否定响应，NRC=0x33(7F 22 33)", func_req=True)
            if not status: return

        TestLog("INFO", "Step13", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG7_TC11_phyRequest_22_NRC22():
    """
    22服务NRC22检查(物理寻址)
    """
    case_name = "22服务NRC22检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        nrc22_condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x22)
        if len(nrc22_condition_list) == 0:
            TestLog("INFO", "Skip", "没有配置NRC22触发条件，跳过此测试")
            return
        first_22_did = next((did_list[0] for did_list in (
            UDSTestParams.Services22DIDSupportList_Default,
            UDSTestParams.Services22DIDSupportList_Extended,
            UDSTestParams.Services22DIDSupportList_Programming,
        ) if did_list), None)

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "遍历触发NRC0x22的所有条件并发送22请求(默认会话)")
        for condition in nrc22_condition_list:
            did = getattr(condition, 'did', None) or first_22_did
            if did is None:
                TestLog("WARNING", "Step3", "没有可用于22服务NRC22测试的DID，跳过")
                continue
            desc = getattr(condition, 'desc', None) or f'DID={did:04X}'
            if not start_nrc22_condition(condition): continue
            try:
                status, _ = service_22_check(node, did, [0x7F, 0x22, 0x22], f"否定响应，NRC=0x22(7F 22 22) - {desc}")
            finally:
                stop_nrc22_condition(condition)
            if not status: return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step6", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "遍历触发NRC0x22的所有条件并发送22请求(扩展会话)")
        for condition in nrc22_condition_list:
            did = getattr(condition, 'did', None) or first_22_did
            if did is None:
                TestLog("WARNING", "Step8", "没有可用于22服务NRC22测试的DID，跳过")
                continue
            desc = getattr(condition, 'desc', None) or f'DID={did:04X}'
            if not start_nrc22_condition(condition): continue
            try:
                status, _ = service_22_check(node, did, [0x7F, 0x22, 0x22], f"否定响应，NRC=0x22(7F 22 22) - {desc}")
            finally:
                stop_nrc22_condition(condition)
            if not status: return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step10", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step11", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step13", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        TestLog("INFO", "Step14", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step15", "遍历触发NRC0x22的所有条件并发送22请求(刷新会话)")
        for condition in nrc22_condition_list:
            did = getattr(condition, 'did', None) or first_22_did
            if did is None:
                TestLog("WARNING", "Step15", "没有可用于22服务NRC22测试的DID，跳过")
                continue
            desc = getattr(condition, 'desc', None) or f'DID={did:04X}'
            if not start_nrc22_condition(condition): continue
            try:
                status, _ = service_22_check(node, did, [0x7F, 0x22, 0x22], f"否定响应，NRC=0x22(7F 22 22) - {desc}")
            finally:
                stop_nrc22_condition(condition)
            if not status: return

        TestLog("INFO", "Step16", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG7_TC12_funRequest_22_NRC22():
    """
    22服务NRC22检查(功能寻址)
    """
    case_name = "22服务NRC22检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        nrc22_condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x22)
        if len(nrc22_condition_list) == 0:
            TestLog("INFO", "Skip", "没有配置NRC22触发条件，跳过此测试")
            return
        first_22_did = next((did_list[0] for did_list in (
            UDSTestParams.Services22DIDSupportList_Default,
            UDSTestParams.Services22DIDSupportList_Extended,
            UDSTestParams.Services22DIDSupportList_Programming,
        ) if did_list), None)

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)", func_req=True): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "遍历触发NRC0x22的所有条件并发送22请求(默认会话，功能寻址)")
        for condition in nrc22_condition_list:
            did = getattr(condition, 'did', None) or first_22_did
            if did is None:
                TestLog("WARNING", "Step3", "没有可用于22服务NRC22测试的DID，跳过")
                continue
            desc = getattr(condition, 'desc', None) or f'DID={did:04X}'
            if not start_nrc22_condition(condition): continue
            try:
                status, _ = service_22_check(node, did, [0x7F, 0x22, 0x22], f"否定响应，NRC=0x22(7F 22 22) - {desc}", func_req=True)
            finally:
                stop_nrc22_condition(condition)
            if not status: return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)", func_req=True): return

        TestLog("INFO", "Step6", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)", func_req=True): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "遍历触发NRC0x22的所有条件并发送22请求(扩展会话，功能寻址)")
        for condition in nrc22_condition_list:
            did = getattr(condition, 'did', None) or first_22_did
            if did is None:
                TestLog("WARNING", "Step8", "没有可用于22服务NRC22测试的DID，跳过")
                continue
            desc = getattr(condition, 'desc', None) or f'DID={did:04X}'
            if not start_nrc22_condition(condition): continue
            try:
                status, _ = service_22_check(node, did, [0x7F, 0x22, 0x22], f"否定响应，NRC=0x22(7F 22 22) - {desc}", func_req=True)
            finally:
                stop_nrc22_condition(condition)
            if not status: return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step10", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)", func_req=True): return

        TestLog("INFO", "Step11", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)", func_req=True): return

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step13", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=True): return

        TestLog("INFO", "Step14", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step15", "遍历触发NRC0x22的所有条件并发送22请求(刷新会话，功能寻址)")
        for condition in nrc22_condition_list:
            did = getattr(condition, 'did', None) or first_22_did
            if did is None:
                TestLog("WARNING", "Step15", "没有可用于22服务NRC22测试的DID，跳过")
                continue
            desc = getattr(condition, 'desc', None) or f'DID={did:04X}'
            if not start_nrc22_condition(condition): continue
            try:
                status, _ = service_22_check(node, did, [0x7F, 0x22, 0x22], f"否定响应，NRC=0x22(7F 22 22) - {desc}", func_req=True)
            finally:
                stop_nrc22_condition(condition)
            if not status: return

        TestLog("INFO", "Step16", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG7_TC13_phyRequest_22_NRC_Priority():
    """
    22服务NRC优先级检查(物理寻址)
    """
    case_name = "22服务NRC优先级检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        unsupported_did_list = UDSTestParams.Services22DIDUnsupportedList
        security_required_did_list = UDSTestParams.Services22DIDSecurityRequiredList
        nrc22_condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x22)
        first_22_did = next((did_list[0] for did_list in (
            UDSTestParams.Services22DIDSupportList_Default,
            UDSTestParams.Services22DIDSupportList_Extended,
            UDSTestParams.Services22DIDSupportList_Programming,
        ) if did_list), None)

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "触发NRC22条件并发送22请求")
        if len(nrc22_condition_list) > 0:
            condition = nrc22_condition_list[0]
            did = getattr(condition, 'did', None) or first_22_did
            if did is not None and start_nrc22_condition(condition):
                try:
                    status, _ = service_22_check(node, did, [0x7F, 0x22, 0x22], "否定响应，NRC=0x22(7F 22 22)")
                    if not status: return
                finally:
                    stop_nrc22_condition(condition)
        else:
            TestLog("INFO", "Step4", "没有配置NRC22触发条件，跳过此步骤")

        TestLog("INFO", "Step5", "发送22请求(DL=1，只有SID)")
        status, _ = service_22_check(node, None, [0x7F, 0x22, 0x13], "否定响应，NRC=0x13(7F 22 13)", dl=1, dl_padding=0x00)
        if not status: return

        TestLog("INFO", "Step6", "发送22 XX XX请求(不支持的DID)")
        if len(unsupported_did_list) > 0:
            did = unsupported_did_list[0]
            status, _ = service_22_check(node, did, [0x7F, 0x22, 0x31], f"否定响应，NRC=0x31(7F 22 31)")
            if not status: return
        else:
            TestLog("INFO", "Step6", "没有配置不支持的DID，跳过此步骤")

        TestLog("INFO", "Step7", "发送22 XX XX请求(需要解锁的DID)")
        if len(security_required_did_list) > 0:
            did = security_required_did_list[0]
            status, _ = service_22_check(node, did, [0x7F, 0x22, 0x33], f"否定响应，NRC=0x33(7F 22 33)")
            if not status: return
        else:
            TestLog("INFO", "Step7", "没有配置需要安全访问的DID，跳过此步骤")

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG7_TC14_funRequest_22_NRC_Priority():
    """
    22服务NRC优先级检查(功能寻址)
    """
    case_name = "22服务NRC优先级检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        unsupported_did_list = UDSTestParams.Services22DIDUnsupportedList
        security_required_did_list = UDSTestParams.Services22DIDSecurityRequiredList
        nrc22_condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x22)
        first_22_did = next((did_list[0] for did_list in (
            UDSTestParams.Services22DIDSupportList_Default,
            UDSTestParams.Services22DIDSupportList_Extended,
            UDSTestParams.Services22DIDSupportList_Programming,
        ) if did_list), None)

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "触发NRC22条件并发送22请求(功能寻址)")
        if len(nrc22_condition_list) > 0:
            condition = nrc22_condition_list[0]
            did = getattr(condition, 'did', None) or first_22_did
            if did is not None and start_nrc22_condition(condition):
                try:
                    status, _ = service_22_check(node, did, [0x7F, 0x22, 0x22], "否定响应，NRC=0x22(7F 22 22)", func_req=True)
                    if not status: return
                finally:
                    stop_nrc22_condition(condition)
        else:
            TestLog("INFO", "Step4", "没有配置NRC22触发条件，跳过此步骤")

        TestLog("INFO", "Step5", "发送22请求(DL=1，只有SID，功能寻址)")
        status, _ = service_22_check(node, None, [0x7F, 0x22, 0x13], "否定响应，NRC=0x13(7F 22 13)", func_req=True, dl=1, dl_padding=0x00)
        if not status: return

        TestLog("INFO", "Step6", "发送22 XX XX请求(不支持的DID，功能寻址)")
        if len(unsupported_did_list) > 0:
            did = unsupported_did_list[0]
            status, _ = service_22_check(node, did, [0x7F, 0x22, 0x31], f"否定响应，NRC=0x31(7F 22 31)", func_req=True)
            if not status: return
        else:
            TestLog("INFO", "Step6", "没有配置不支持的DID，跳过此步骤")

        TestLog("INFO", "Step7", "发送22 XX XX请求(需要解锁的DID，功能寻址)")
        if len(security_required_did_list) > 0:
            did = security_required_did_list[0]
            status, _ = service_22_check(node, did, [0x7F, 0x22, 0x33], f"否定响应，NRC=0x33(7F 22 33)", func_req=True)
            if not status: return
        else:
            TestLog("INFO", "Step7", "没有配置需要安全访问的DID，跳过此步骤")

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG8_TC1_phyRequest_2E_Positive():
    case_name = "2E服务肯定响应及功能检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_5, LEVEL_PRO_5_STR = 0x05, "05"  # 刷新等级
    LEVEL_PRO_6, LEVEL_PRO_6_STR = 0x06, "06"  # 刷新等级+1
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        time.sleep(1)

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", f"发送27 01请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step5", f"发送27 02请求(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x67, LEVEL_EXT_2], f"肯定响应(67 {LEVEL_EXT_2_STR})",
                                   alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step6", "令ABCD=0x0000")
        for ABCD in range(0, 0xFFFF):
            if ABCD not in UDSTestParams.Services2EDIDSupportListExtend:
                continue
            TestLog("INFO", "Step7", f"如果ABCD<0xFFFF且ABCD不为支持的DID，则ABCD+=1，直到ABCD<0xFFFF，当前DID={hex(ABCD)}")
            did_0, did_1 =  ABCD >> 8 & 0xFF, ABCD & 0xFF

            TestLog("INFO", "Step8", "如果ABCD是支持的DID，则读取其值，否则跳转至步骤29")
            status, resp = service_22_check(node, ABCD, [0x62, did_0, did_1], "肯定响应(62)")
            if not status: return

            src_data = get_info_from_22_resp(resp)

            TestLog("INFO", "Step9", "写入一个不同于读取到的数据值")
            new_data = copy.copy(src_data)
            new_data[0] = (new_data[0] + 1) % (0xFF + 1)
            if not service_2E_check(node, ABCD, bytes(new_data), [0x6E, did_0, did_1], "肯定响应(6E)"): return

            TestLog("INFO", "Step10", f"读取DID=ABCD({hex(ABCD)})的数据")
            status, resp = service_22_check(node, ABCD, [0x62, did_0, did_1], "肯定响应(62)")
            if not status: return

            data = get_info_from_22_resp(resp)
            if list(data) == list(new_data):
                TestLog("PASS", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据相同")
            else:
                TestLog("FAIL", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据不同")
                return

            TestLog("INFO", "Step11", "DUT复位(11 01)")
            if not service_11_check(node, 0x01, [0x51, 0x01], "肯定响应(51 01)"): return

            TestLog("INFO", "Step12", "复位完成后，请求进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            time.sleep(2)

            TestLog("INFO", "Step13", "进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            TestLog("INFO", "Step14", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step15", f"发送27 01请求(27 {LEVEL_EXT_STR})")
            status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
            if not status: return

            seed_list = get_seed_from_27_resp(resp)
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

            TestLog("INFO", "Step16", f"发送27 02请求(27 {LEVEL_EXT_2_STR})")
            if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x67, LEVEL_EXT_2], f"肯定响应(67 {LEVEL_EXT_2_STR})",
                                       alg_type=AlgorithmType.EXTENDED): return

            TestLog("INFO", "Step17", f"读取DID=ABCD({hex(ABCD)})的数据")
            status, resp = service_22_check(node, ABCD, [0x62, did_0, did_1], "肯定响应(62)")
            if not status: return

            data = get_info_from_22_resp(resp)
            if list(data) == list(new_data):
                TestLog("PASS", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据相同")
            else:
                TestLog("FAIL", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据不同")
                return

            TestLog("INFO", "Step18", f"断电后重新上电")
            ctx.power_ctrl.off()
            time.sleep(1)
            ctx.power_ctrl.on()
            time.sleep(1)

            TestLog("INFO", "Step19", "进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step20", "进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            time.sleep(1)

            TestLog("INFO", "Step21", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step22", f"发送27 01请求(27 {LEVEL_EXT_STR})")
            status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
            if not status: return

            seed_list = get_seed_from_27_resp(resp)
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

            TestLog("INFO", "Step23", f"发送27 02请求(27 {LEVEL_EXT_2_STR})")
            if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x67, LEVEL_EXT_2], f"肯定响应(67 {LEVEL_EXT_2_STR})",
                                       alg_type=AlgorithmType.EXTENDED): return

            TestLog("INFO", "Step24", f"读取DID=ABCD({hex(ABCD)})的数据")
            status, resp = service_22_check(node, ABCD, [0x62, did_0, did_1], "肯定响应(62)")
            if not status: return

            data = get_info_from_22_resp(resp)
            if list(data) == list(new_data):
                TestLog("PASS", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据相同")
            else:
                TestLog("FAIL", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据不同")
                return

            TestLog("INFO", "Step25", f"对DID=ABCD({hex(ABCD)})写入原值")
            if not service_2E_check(node, ABCD, bytes(src_data), [0x6E, did_0, did_1], "肯定响应(6E)"): return

            TestLog("INFO", "Step26", f"读取DID=ABCD({hex(ABCD)})的数据")
            status, resp = service_22_check(node, ABCD, [0x62, did_0, did_1], "肯定响应(62)")
            if not status: return

            data = get_info_from_22_resp(resp)
            if list(data) == list(src_data):
                TestLog("PASS", "", "期望:读取到的数据与原值相同; 实际： 读取到的数据与原值相同")
            else:
                TestLog("FAIL", "", "期望:读取到的数据与原值相同; 实际： 读取到的数据与原值不同")
                return

            TestLog("INFO", "Step27", f"ABCD+=1，跳转至步骤7")

        TestLog("INFO", "Step28", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step29", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step30", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step31", "进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        TestLog("INFO", "Step32", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step33", f"发送27 11请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step34", f"发送27 12请求(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_11, seed_list, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_12_STR})",
                                   alg_type=AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step35", "令ABCD=0x0000")
        for ABCD in range(0, 0xFFFF):
            if ABCD not in UDSTestParams.Services2EDIDSupportListProgramming:
                continue
            TestLog("INFO", "Step36", f"如果ABCD<0xFFFF且ABCD不为支持的DID，则ABCD+=1，直到ABCD<0xFFFF, 当前DID={hex(ABCD)}")
            did_0, did_1 =  ABCD >> 8 & 0xFF, ABCD & 0xFF

            TestLog("INFO", "Step37", "如果ABCD是支持的DID，则读取其值，否则结束本项测试")
            status, resp = service_22_check(node, ABCD, [0x62, did_0, did_1], "肯定响应(62)")
            if not status: return

            src_data = get_info_from_22_resp(resp)

            TestLog("INFO", "Step38", "写入一个不同于读取到的数据值")
            new_data = copy.copy(src_data)
            new_data[0] = (new_data[0] + 1) % (0xFF + 1)
            if not service_2E_check(node, ABCD, bytes(new_data), [0x6E, did_0, did_1], "肯定响应(6E)"): return

            TestLog("INFO", "Step39", f"读取DID=ABCD({hex(ABCD)})的数据")
            status, resp = service_22_check(node, ABCD, [0x62, did_0, did_1], "肯定响应(62)")
            if not status: return

            data = get_info_from_22_resp(resp)
            if list(data) == list(new_data):
                TestLog("PASS", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据相同")
            else:
                TestLog("FAIL", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据不同")
                return

            TestLog("INFO", "Step40", "DUT复位(11 01)")
            if not service_11_check(node, 0x01, [0x51, 0x01], "肯定响应(51 01)"): return

            TestLog("INFO", "Step41", "复位完成后，请求进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            time.sleep(2)

            TestLog("INFO", "Step42", "进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            TestLog("INFO", "Step43", "进入刷新会话(10 02)")
            if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

            TestLog("INFO", "Step44", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

            TestLog("INFO", "Step45", f"发送27 11请求(27 {LEVEL_PRO_11_STR})")
            status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
            if not status: return

            seed_list = get_seed_from_27_resp(resp)
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

            TestLog("INFO", "Step46", f"发送27 12请求(27 {LEVEL_PRO_12_STR})")
            if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x67, LEVEL_PRO_12], f"肯定响应(67 {LEVEL_PRO_12_STR})",
                                       alg_type=AlgorithmType.PROGRAMMING): return

            TestLog("INFO", "Step47", f"读取DID=ABCD({hex(ABCD)})的数据")
            status, resp = service_22_check(node, ABCD, [0x62, did_0, did_1], "肯定响应(62)")
            if not status: return

            data = get_info_from_22_resp(resp)
            if list(data) == list(new_data):
                TestLog("PASS", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据相同")
            else:
                TestLog("FAIL", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据不同")
                return

            TestLog("INFO", "Step48", f"断电后重新上电")
            ctx.power_ctrl.off()
            time.sleep(1)
            ctx.power_ctrl.on()
            time.sleep(1)

            TestLog("INFO", "Step49", "进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step50", "进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            TestLog("INFO", "Step51", "进入刷新会话(10 02)")
            if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

            TestLog("INFO", "Step52", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

            TestLog("INFO", "Step53", f"发送27 11请求(27 {LEVEL_PRO_11_STR})")
            status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
            if not status: return

            seed_list = get_seed_from_27_resp(resp)
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

            TestLog("INFO", "Step54", f"发送27 12请求(27 {LEVEL_PRO_12_STR})")
            if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x67, LEVEL_PRO_12], f"肯定响应(67 {LEVEL_PRO_12_STR})",
                                       alg_type=AlgorithmType.PROGRAMMING): return

            TestLog("INFO", "Step55", f"读取DID=ABCD({hex(ABCD)})的数据")
            status, resp = service_22_check(node, ABCD, [0x62, did_0, did_1], "肯定响应(62)")
            if not status: return

            data = get_info_from_22_resp(resp)
            if list(data) == list(new_data):
                TestLog("PASS", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据相同")
            else:
                TestLog("FAIL", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据不同")
                return

            TestLog("INFO", "Step56", f"对DID=ABCD({hex(ABCD)})写入原值")
            if not service_2E_check(node, ABCD, bytes(src_data), [0x6E, did_0, did_1], "肯定响应(6E)"): return

            TestLog("INFO", "Step57", f"读取DID=ABCD({hex(ABCD)})的数据")
            status, resp = service_22_check(node, ABCD, [0x62, did_0, did_1], "肯定响应(62)")
            if not status: return

            data = get_info_from_22_resp(resp)
            if list(data) == list(src_data):
                TestLog("PASS", "", "期望:读取到的数据与原值相同; 实际： 读取到的数据与原值相同")
            else:
                TestLog("FAIL", "", "期望:读取到的数据与原值相同; 实际： 读取到的数据与原值不同")
                return

            TestLog("INFO", "Step58", f"ABCD+=1，跳转至步骤36")

        TestLog("INFO", "Step59", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG8_TC2_phyRequest_2E_NRC13():
    case_name = "2E服务NRC13检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_5, LEVEL_PRO_5_STR = 0x05, "05"  # 刷新等级
    LEVEL_PRO_6, LEVEL_PRO_6_STR = 0x06, "06"  # 刷新等级+1
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", f"发送27 01请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step5", f"发送27 02请求(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x67, LEVEL_EXT_2], f"肯定响应(67 {LEVEL_EXT_2_STR})",
                                   alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step6", "发送长度较短2E服务请求")
        data_list = [None]  # [None, [0xF1], [0xF1, 0x90], [0xF0, 0xFA], [0xF0, 0xFF]]
        for did in UDSTestParams.Services2EDIDSupportListExtend:
            did_str = hex(did).removeprefix("0x")
            did_bytes = bytes.fromhex(did_str)
            if did_bytes[0] not in data_list:
                data_list.append(bytes([did_bytes[0]]))  # 添加did的第一个字节，比如0xF190的0xF1
            if did_bytes not in  data_list:
                data_list.append(did_bytes)
        for data in data_list:
            print(f"{data=}")
            if not service_2E_check(node, None, expect_data=[0x7F, 0x2E, 0x13], expect_str="否定响应(7F 2E 13)", defined_data=data): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step9", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step10", "进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step12", f"发送27 11请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step13", f"发送27 12请求(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x67, LEVEL_PRO_12], f"肯定响应(67 {LEVEL_PRO_12_STR})",
                                   alg_type=AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step14", "发送长度较短2E服务请求")
        data_list = [None]  # [None, [0xF1], [0xF1, 0x84]]
        for did in UDSTestParams.Services2EDIDSupportListProgramming:
            did_str = hex(did).removeprefix("0x")
            did_bytes = bytes.fromhex(did_str)
            if did_bytes[0] not in data_list:
                data_list.append(bytes([did_bytes[0]]))  # 添加did的第一个字节，比如0xF184的0xF1
            if did_bytes not in  data_list:
                data_list.append(did_bytes)
        
        for data in data_list:
            if not service_2E_check(node, None, expect_data=[0x7F, 0x2E, 0x13], expect_str="否定响应(7F 2E 13)", defined_data=data): return

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG8_TC3_phyRequest_2E_NRC31():
    case_name = "2E服务NRC31检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_5, LEVEL_PRO_5_STR = 0x05, "05"  # 刷新等级
    LEVEL_PRO_6, LEVEL_PRO_6_STR = 0x06, "06"  # 刷新等级+1
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1

    min_did, max_did = 0x0001, 0x0010
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        time.sleep(1)

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", f"发送27 01请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step5", f"发送27 02请求(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x67, LEVEL_EXT_2], f"肯定响应(67 {LEVEL_EXT_2_STR})",
                                   alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step6", "遍历所有2E服务不支持的DID（当前会话下）")
        # for did in range(min_did, max_did + 1):
        #     if did in UDSTestParams.Services2EDIDSupportList:
        #         continue
        #     # 不支持的did
        #     # TODO 写入的数据
        #     if not service_2E_check(node, did, bytes([]), expect_data=[0x7F, 0x2E, 0x31], expect_str="否定响应(7F 2E 31)"): return
        for i in range(0x00, 0x11):
            data = [0x00, i, 0xC3]
            if not service_2E_check(node, None, expect_data=[0x7F, 0x2E, 0x31], expect_str="否定响应(7F 2E 31)", defined_data=bytes(data)): return

        # TestLog("INFO", "Step7", "遍历所有2E服务支持的DID（当前会话下），但是写入的数据超过数据范围")
        # for did in range(min_did, max_did + 1):
        #     if did not in UDSTestParams.Services2EDIDSupportList:
        #         continue
        #     # 支持的did
        #     # TODO 写入的数据
        #     if not service_2E_check(node, did, bytes([]), expect_data=[0x7F, 0x2E, 0x31], expect_str="否定响应(7F 2E 31)"): return

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step9", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step10", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step11", "进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step13", f"发送27 11请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step14", f"发送27 12请求(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x67, LEVEL_PRO_12], f"肯定响应(67 {LEVEL_PRO_12_STR})",
                                   alg_type=AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step15", "遍历所有2E服务不支持的DID（当前会话下）")
        # for did in range(min_did, max_did + 1):
        #     if did in UDSTestParams.Services2EDIDSupportList:
        #         continue
        #     # 不支持的did
        #     # TODO 写入的数据
        #     if not service_2E_check(node, did, bytes([]), expect_data=[0x7F, 0x2E, 0x31], expect_str="否定响应(7F 2E 31)"): return
        for i in range(0x00, 0x11):
            data = [0x00, i, 0xC3]
            if not service_2E_check(node, None, expect_data=[0x7F, 0x2E, 0x31], expect_str="否定响应(7F 2E 31)", defined_data=bytes(data)): return

        # TestLog("INFO", "Step16", "遍历所有2E服务支持的DID（当前会话下），但是写入的数据超过数据范围")
        # for did in range(min_did, max_did + 1):
        #     if did not in UDSTestParams.Services2EDIDSupportList:
        #         continue
        #     # 支持的did
        #     # TODO 写入的数据
        #     if not service_2E_check(node, did, bytes([]), expect_data=[0x7F, 0x2E, 0x31], expect_str="否定响应(7F 2E 31)"): return

        TestLog("INFO", "Step17", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG8_TC4_phyRequest_2E_NRC33():
    case_name = "2E服务NRC33检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        time.sleep(1)

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "读取所有2E服务支持但需要安全解锁的DID")
        for did in UDSTestParams.Services2EDIDSupportListExtend:
            if did not in UDSTestParams.Services2EDIDNeedUnlockSupportList:
                continue
            # 支持的且需要安全解锁的did
            status, resp = service_22_check(node, did, expect_data=[0x62], expect_str="肯定响应(62)")
            if status is False:
                return
            data = get_info_from_22_resp(resp)

            TestLog("INFO", "Step5", "遍历所有2E服务支持的但需要安全解锁的DID，写入原值")
            if not service_2E_check(node, did, data, [0x7F, 0x2E, 0x33], "否定响应(7F 2E 33)"): return

        TestLog("INFO", "Step6", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step7", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step8", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step9", "进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        TestLog("INFO", "Step10", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step11", "读取所有2E服务支持但需要安全解锁的DID")
        for did in UDSTestParams.Services2EDIDSupportListProgramming:
            if did not in UDSTestParams.Services2EDIDNeedUnlockSupportList:
                continue
            # 支持的且需要安全解锁的did
            status, resp = service_22_check(node, did, expect_data=[0x62], expect_str="肯定响应(62)")
            if status is False:
                return
            data = get_info_from_22_resp(resp)

            TestLog("INFO", "Step12", "遍历所有2E服务支持的但需要安全解锁的DID，写入原值")
            if not service_2E_check(node, did, data, [0x7F, 0x2E, 0x33], "否定响应(7F 2E 33)"): return

        TestLog("INFO", "Step13", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG8_TC5_phyRequest_2E_NRC7F():
    case_name = "2E服务NRC7F检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "遍历所有2E服务在其他session支持的DID，写入值为原值")
        for did in UDSTestParams.Services2EDIDSupportListExtend + UDSTestParams.Services2EDIDSupportListProgramming:
            if did not in UDSTestParams.Services2EDIDNeedUnlockSupportList:
                continue
            # 支持的且需要安全解锁的did
            status, resp = service_22_check(node, did, expect_data=[0x62], expect_str="肯定响应(62)")
            if not status: return
            data = get_info_from_22_resp(resp)
            if not service_2E_check(node, did, data, [0x7F, 0x2E, 0x7F], "否定响应(7F 2E 7F)"): return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG8_TC6_phyRequest_2E_NRC22():
    case_name = "2E服务NRC0x22检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_5, LEVEL_PRO_5_STR = 0x05, "05"  # 刷新等级
    LEVEL_PRO_6, LEVEL_PRO_6_STR = 0x06, "06"  # 刷新等级+1
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", f"发送27 01请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step5", f"发送27 02请求(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x67, LEVEL_EXT_2], f"肯定响应(67 {LEVEL_EXT_2_STR})",
                                   alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step6", "遍历触发NRC0x22的所有条件并发送2E请求")
        nrc22_condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x2E)
        did, data = None, b""
        for candidate_did in UDSTestParams.Services2EDIDSupportListExtend:
            status, resp = service_22_check(node, candidate_did, [0x62], f"读取2E NRC22测试DID原值({candidate_did:04X})")
            if status:
                did, data = candidate_did, bytes(get_info_from_22_resp(resp))
                break
        if did is None or len(nrc22_condition_list) == 0:
            TestLog("WARNING", "Step6", "未配置2E服务DID或NRC22条件，跳过该测试")
            return
        for condition in nrc22_condition_list:
            if not start_nrc22_condition(condition): continue
            try:
                if not service_2E_check(node, did, data, [0x7F, 0x2E, 0x22], "否定响应(7F 2E 22)"): return
            finally:
                stop_nrc22_condition(condition)

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step9", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step10", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step11", "进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step13", f"发送27 11请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step14", f"发送27 12请求(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x67, LEVEL_PRO_12], f"肯定响应(67 {LEVEL_PRO_12_STR})",
                                   alg_type=AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step15", "遍历触发NRC0x22的所有条件并发送2E请求")
        did, data = None, b""
        for candidate_did in UDSTestParams.Services2EDIDSupportListProgramming:
            status, resp = service_22_check(node, candidate_did, [0x62], f"读取2E NRC22测试DID原值({candidate_did:04X})")
            if status:
                did, data = candidate_did, bytes(get_info_from_22_resp(resp))
                break
        if did is None or len(nrc22_condition_list) == 0:
            TestLog("WARNING", "Step15", "未配置2E服务DID或NRC22条件，跳过该测试")
            return
        for condition in nrc22_condition_list:
            if not start_nrc22_condition(condition): continue
            try:
                if not service_2E_check(node, did, data, [0x7F, 0x2E, 0x22], "否定响应(7F 2E 22)"): return
            finally:
                stop_nrc22_condition(condition)

        TestLog("INFO", "Step16", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG8_TC7_phyRequest_2E_NRCPriorityCheck():
    case_name = "2E服务NRC优先级检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_5, LEVEL_PRO_5_STR = 0x05, "05"  # 刷新等级
    LEVEL_PRO_6, LEVEL_PRO_6_STR = 0x06, "06"  # 刷新等级+1
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", f"发送27 01请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step5", f"发送27 02请求(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x67, LEVEL_EXT_2], f"肯定响应(67 {LEVEL_EXT_2_STR})",
                                   alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step6", "遍历触发NRC0x22的所有条件并发送2E请求(触发条件需要根据供应商要求添加)")
        nrc22_condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x2E)
        condition = nrc22_condition_list[0] if len(nrc22_condition_list) > 0 else None
        if condition is not None:
            start_nrc22_condition(condition)
        try:
            if not service_2E_check(node, None, expect_data=[0x7F, 0x2E, 0x13], expect_str="否定响应(7F 2E 13)"): return
        finally:
            if condition is not None: stop_nrc22_condition(condition)

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step9", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step10", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step11", "进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step13", f"发送27 11请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step14", f"发送27 12请求(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x67, LEVEL_PRO_12], f"肯定响应(67 {LEVEL_PRO_12_STR})",
                                   alg_type=AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step15", "遍历触发NRC0x22的所有条件并发送2E请求(触发条件需要根据供应商要求添加)")
        condition = nrc22_condition_list[0] if len(nrc22_condition_list) > 0 else None
        if condition is not None:
            start_nrc22_condition(condition)
        try:
            if not service_2E_check(node, 0x00, bytes([]), expect_data=[0x7F, 0x2E, 0x31], expect_str="否定响应(7F 2E 31)"): return
        finally:
            if condition is not None: stop_nrc22_condition(condition)

        TestLog("INFO", "Step16", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return


    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG9_TC1_phyRequest_14_Positive():
    """
    14服务肯定响应及功能检查(物理寻址)
    """
    case_name = "14服务肯定响应及功能检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        dtc_group_list = UDSTestParams.Services14DTCGroupSupportList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "使DUT接收的报文失效，等待4.5s")
        TestLog("INFO", "", "设置低电压，开启3E 80会话保持服务")
        tester_present_start(node)
        print(ctx.power_ctrl.set_voltage(8))
        time.sleep(4.5)

        # TODO 此步骤需要根据实际环境实现报文失效功能
        TestLog("INFO", "", "跳过报文失效步骤(需根据实际实际环境实现)")

        TestLog("INFO", "Step4", "发送19 02 09读DTC")
        status, resp = service_19_check(node, 0x02, [0x59, 0x02], "DUT返回DTC(59 02 ...)", DTCStatusMask=0x09)
        if not status: return

        TestLog("INFO", "Step5", "检查是否通信丢失DTC被成功存储")
        TestLog("INFO", "", "跳过DTC存储检查(需根据实际环境实现)")

        TestLog("INFO", "Step6", "使DUT接收的报文恢复，等待4.5s")
        TestLog("INFO", "", "跳过报文恢复步骤(需根据实际环境实现)")
        ctx.power_ctrl.set_voltage(rVnormal)
        time.sleep(4.5)
        tester_present_stop()

        TestLog("INFO", "Step7", "遍历所有支持的14服务请求子功能参数(物理寻址)")
        for dtc_group in dtc_group_list:
            h, m, l = (dtc_group >> 16) & 0xFF, (dtc_group >> 8) & 0xFF, dtc_group & 0xFF
            status, _ = service_14_check(node, dtc_group, [0x54], f"肯定响应(54) - DTC组: {h:02X} {m:02X} {l:02X}")
            if not status: return

        TestLog("INFO", "Step8", "检查是否通信丢失DTC被成功清除(19 02 09)")
        status, resp = service_19_check(node, 0x02, [0x59, 0x02], "相关DTC已清除(59 02 ...)", DTCStatusMask=0x09)
        if not status: return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step10", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step11", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step13", "使DUT接收的报文失效，等待4.5s")
        TestLog("INFO", "", "设置低电压，开启3E 80会话保持服务")
        tester_present_start(node)
        ctx.power_ctrl.set_voltage(8)
        time.sleep(4.5)

        TestLog("INFO", "Step14", "发送19 02 09读DTC")
        status, resp = service_19_check(node, 0x02, [0x59, 0x02], "DUT返回DTC(59 02 ...)", DTCStatusMask=0x09)
        if not status: return

        TestLog("INFO", "Step15", "检查是否通信丢失DTC被成功存储")
        TestLog("INFO", "", "跳过DTC存储检查(需根据实际环境实现)")

        TestLog("INFO", "Step16", "使DUT接收的报文恢复，等待4.5s")
        TestLog("INFO", "", "跳过报文恢复步骤(需根据实际环境实现)")
        ctx.power_ctrl.set_voltage(rVnormal)
        time.sleep(4.5)
        tester_present_stop()

        TestLog("INFO", "Step17", "遍历所有支持的14服务请求子功能参数(物理寻址)")
        for dtc_group in dtc_group_list:
            h, m, l = (dtc_group >> 16) & 0xFF, (dtc_group >> 8) & 0xFF, dtc_group & 0xFF
            status, _ = service_14_check(node, dtc_group, [0x54], f"肯定响应(54) - DTC组: {h:02X} {m:02X} {l:02X}")
            if not status: return

        TestLog("INFO", "Step18", "检查是否通信丢失DTC被成功清除(19 02 09)")
        status, resp = service_19_check(node, 0x02, [0x59, 0x02], "相关DTC已清除(59 02 ...)", DTCStatusMask=0x09)
        if not status: return

        TestLog("INFO", "Step19", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG9_TC2_funRequest_14_Positive():
    """
    14服务肯定响应及功能检查(功能寻址)
    """
    case_name = "14服务肯定响应及功能检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        dtc_group_list = UDSTestParams.Services14DTCGroupSupportList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "使DUT接收的报文失效，等待4.5s")
        TestLog("INFO", "", "设置低电压，开启3E 80会话保持服务")
        tester_present_start(node)
        print(ctx.power_ctrl.set_voltage(8))
        time.sleep(4.5)

        # TODO 此步骤需要根据实际环境实现报文失效功能
        TestLog("INFO", "", "跳过报文失效步骤(需根据实际实际环境实现)")

        TestLog("INFO", "Step4", "发送19 02 09读DTC")
        status, resp = service_19_check(node, 0x02, [0x59, 0x02], "DUT返回DTC(59 02 ...)", DTCStatusMask=0x09)
        if not status: return

        TestLog("INFO", "Step5", "检查是否通信丢失DTC被成功存储")
        TestLog("INFO", "", "跳过DTC存储检查(需根据实际环境实现)")

        TestLog("INFO", "Step6", "使DUT接收的报文恢复，等待4.5s")
        TestLog("INFO", "", "跳过报文恢复步骤(需根据实际环境实现)")
        ctx.power_ctrl.set_voltage(rVnormal)
        time.sleep(4.5)
        tester_present_stop()

        TestLog("INFO", "Step7", "遍历所有支持的14服务请求子功能参数(物理寻址)")
        for dtc_group in dtc_group_list:
            h, m, l = (dtc_group >> 16) & 0xFF, (dtc_group >> 8) & 0xFF, dtc_group & 0xFF
            status, _ = service_14_check(node, dtc_group, [0x54], f"肯定响应(54) - DTC组: {h:02X} {m:02X} {l:02X}", func_req=True)
            if not status: return

        TestLog("INFO", "Step8", "检查是否通信丢失DTC被成功清除(19 02 09)")
        status, resp = service_19_check(node, 0x02, [0x59, 0x02], "相关DTC已清除(59 02 ...)", DTCStatusMask=0x09)
        if not status: return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step10", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step11", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step13", "使DUT接收的报文失效，等待4.5s")
        TestLog("INFO", "", "设置低电压，开启3E 80会话保持服务")
        tester_present_start(node)
        ctx.power_ctrl.set_voltage(8)
        time.sleep(4.5)

        TestLog("INFO", "Step14", "发送19 02 09读DTC")
        status, resp = service_19_check(node, 0x02, [0x59, 0x02], "DUT返回DTC(59 02 ...)", DTCStatusMask=0x09)
        if not status: return

        TestLog("INFO", "Step15", "检查是否通信丢失DTC被成功存储")
        TestLog("INFO", "", "跳过DTC存储检查(需根据实际环境实现)")

        TestLog("INFO", "Step16", "使DUT接收的报文恢复，等待4.5s")
        TestLog("INFO", "", "跳过报文恢复步骤(需根据实际环境实现)")
        ctx.power_ctrl.set_voltage(rVnormal)
        time.sleep(4.5)
        tester_present_stop()

        TestLog("INFO", "Step17", "遍历所有支持的14服务请求子功能参数(物理寻址)")
        for dtc_group in dtc_group_list:
            h, m, l = (dtc_group >> 16) & 0xFF, (dtc_group >> 8) & 0xFF, dtc_group & 0xFF
            status, _ = service_14_check(node, dtc_group, [0x54], f"肯定响应(54) - DTC组: {h:02X} {m:02X} {l:02X}", func_req=True)
            if not status: return

        TestLog("INFO", "Step18", "检查是否通信丢失DTC被成功清除(19 02 09)")
        status, resp = service_19_check(node, 0x02, [0x59, 0x02], "相关DTC已清除(59 02 ...)", DTCStatusMask=0x09)
        if not status: return

        TestLog("INFO", "Step19", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG9_TC3_phyRequest_14_NRC13():
    """
    14服务NRC13检查(物理寻址)
    """
    case_name = "14服务NRC13检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送较短14服务请求(DL=3，14 FF FF)")
        status, _ = service_14_check(node, None, [0x7F, 0x14, 0x13], "否定响应，NRC=0x13(7F 14 13)",
                                     dl=3, dl_padding=0xFF)
        if not status: return

        TestLog("INFO", "Step4", "发送较长14服务请求(DL=5，14 FF FF FF FF)")
        status, _ = service_14_check(node, None, [0x7F, 0x14, 0x13], "否定响应，NRC=0x13(7F 14 13)",
                                     dl=5, dl_padding=0xFF)
        if not status: return

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step6", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step7", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step9", "发送较短14服务请求(DL=3，14 FF FF)")
        status, _ = service_14_check(node, None, [0x7F, 0x14, 0x13], "否定响应，NRC=0x13(7F 14 13)",
                                     dl=3, dl_padding=0xFF)
        if not status: return

        TestLog("INFO", "Step10", "发送较长14服务请求(DL=5，14 FF FF FF FF)")
        status, _ = service_14_check(node, None, [0x7F, 0x14, 0x13], "否定响应，NRC=0x13(7F 14 13)",
                                     dl=5, dl_padding=0xFF)
        if not status: return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG9_TC4_funRequest_14_NRC13():
    """
    14服务NRC13检查(功能寻址)
    """
    case_name = "14服务NRC13检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送较短14服务请求(DL=3，14 FF FF，功能寻址)")
        status, _ = service_14_check(node, None, [0x7F, 0x14, 0x13], "否定响应，NRC=0x13(7F 14 13)",
                                     func_req=True, dl=3, dl_padding=0xFF)
        if not status: return

        TestLog("INFO", "Step4", "发送较长14服务请求(DL=5，14 FF FF FF FF，功能寻址)")
        status, _ = service_14_check(node, None, [0x7F, 0x14, 0x13], "否定响应，NRC=0x13(7F 14 13)",
                                     func_req=True, dl=5, dl_padding=0xFF)
        if not status: return

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step6", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step7", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step9", "发送较短14服务请求(DL=3，14 FF FF，功能寻址)")
        status, _ = service_14_check(node, None, [0x7F, 0x14, 0x13], "否定响应，NRC=0x13(7F 14 13)",
                                     func_req=True, dl=3, dl_padding=0xFF)
        if not status: return

        TestLog("INFO", "Step10", "发送较长14服务请求(DL=5，14 FF FF FF FF，功能寻址)")
        status, _ = service_14_check(node, None, [0x7F, 0x14, 0x13], "否定响应，NRC=0x13(7F 14 13)",
                                     func_req=True, dl=5, dl_padding=0xFF)
        if not status: return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG9_TC5_phyRequest_14_NRC31():
    """
    14服务NRC31检查(物理寻址)
    """
    case_name = "14服务NRC31检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        unsupported_dtc_group_list = UDSTestParams.Services14DTCGroupUnsupportedList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "遍历所有不支持的诊断故障代码组(物理寻址)")
        for dtc_group in unsupported_dtc_group_list:
            h, m, l = (dtc_group >> 16) & 0xFF, (dtc_group >> 8) & 0xFF, dtc_group & 0xFF
            status, _ = service_14_check(node, dtc_group, [0x7F, 0x14, 0x31],
                                         f"否定响应，NRC=0x31(7F 14 31) - DTC组: {h:02X} {m:02X} {l:02X}")
            if not status: return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step6", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "遍历所有不支持的诊断故障代码组(物理寻址)")
        for dtc_group in unsupported_dtc_group_list:
            h, m, l = (dtc_group >> 16) & 0xFF, (dtc_group >> 8) & 0xFF, dtc_group & 0xFF
            status, _ = service_14_check(node, dtc_group, [0x7F, 0x14, 0x31],
                                         f"否定响应，NRC=0x31(7F 14 31) - DTC组: {h:02X} {m:02X} {l:02X}")
            if not status: return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG9_TC6_funRequest_14_NRC31():
    """
    14服务NRC31检查(功能寻址)
    """
    case_name = "14服务NRC31检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        unsupported_dtc_group_list = UDSTestParams.Services14DTCGroupUnsupportedList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)", func_req=True): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "遍历所有不支持的诊断故障代码组(功能寻址)")
        for dtc_group in unsupported_dtc_group_list:
            h, m, l = (dtc_group >> 16) & 0xFF, (dtc_group >> 8) & 0xFF, dtc_group & 0xFF
            status, _ = service_14_check(node, dtc_group, None,
                                         f"无响应 - DTC组: {h:02X} {m:02X} {l:02X}", func_req=True)
            if not status: return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)", func_req=True): return

        TestLog("INFO", "Step6", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)", func_req=True): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "遍历所有不支持的诊断故障代码组(功能寻址)")
        for dtc_group in unsupported_dtc_group_list:
            h, m, l = (dtc_group >> 16) & 0xFF, (dtc_group >> 8) & 0xFF, dtc_group & 0xFF
            status, _ = service_14_check(node, dtc_group, None,
                                         f"无响应 - DTC组: {h:02X} {m:02X} {l:02X}", func_req=True)
            if not status: return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG9_TC7_phyRequest_14_NRC22():
    """
    14服务NRC0x22检查(物理寻址)
    """
    case_name = "14服务NRC0x22检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        nrc22_condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x14)

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "遍历触发NRC0x22的所有条件并发送14请求(物理寻址)")
        if len(nrc22_condition_list) > 0:
            for condition in nrc22_condition_list:
                if not start_nrc22_condition(condition): continue
                try:
                    status, _ = service_14_check(node, 0xFFFFFF, [0x7F, 0x14, 0x22],
                                                 "NRC0x22的否定响应(7F 14 22)")
                finally:
                    stop_nrc22_condition(condition)
                if not status: return
        else:
            TestLog("INFO", "", "没有配置NRC22触发条件，跳过此步骤")

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step6", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "遍历触发NRC0x22的所有条件并发送14请求(物理寻址)")
        if len(nrc22_condition_list) > 0:
            for condition in nrc22_condition_list:
                if not start_nrc22_condition(condition): continue
                try:
                    status, _ = service_14_check(node, 0xFFFFFF, [0x7F, 0x14, 0x22],
                                                 "NRC0x22的否定响应(7F 14 22)")
                finally:
                    stop_nrc22_condition(condition)
                if not status: return
        else:
            TestLog("INFO", "", "没有配置NRC22触发条件，跳过此步骤")

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG9_TC8_funRequest_14_NRC22():
    """
    14服务NRC0x22检查(功能寻址)
    """
    case_name = "14服务NRC0x22检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        nrc22_condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x14)

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "遍历触发NRC0x22的所有条件并发送14请求(功能寻址)")
        if len(nrc22_condition_list) > 0:
            for condition in nrc22_condition_list:
                if not start_nrc22_condition(condition): continue
                try:
                    status, _ = service_14_check(node, 0xFFFFFF, [0x7F, 0x14, 0x22],
                                                 "NRC0x22的否定响应(7F 14 22)", func_req=True)
                finally:
                    stop_nrc22_condition(condition)
                if not status: return
        else:
            TestLog("INFO", "", "没有配置NRC22触发条件，跳过此步骤")

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step6", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "遍历触发NRC0x22的所有条件并发送14请求(功能寻址)")
        if len(nrc22_condition_list) > 0:
            for condition in nrc22_condition_list:
                if not start_nrc22_condition(condition): continue
                try:
                    status, _ = service_14_check(node, 0xFFFFFF, [0x7F, 0x14, 0x22],
                                                 "NRC0x22的否定响应(7F 14 22)", func_req=True)
                finally:
                    stop_nrc22_condition(condition)
                if not status: return
        else:
            TestLog("INFO", "", "没有配置NRC22触发条件，跳过此步骤")

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG9_TC9_phyRequest_14_NRCPriority():
    """
    14服务NRC优先级检查(物理寻址)
    """
    case_name = "14服务NRC优先级检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        nrc22_condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x14)
        unsupported_dtc_group_list = UDSTestParams.Services14DTCGroupUnsupportedList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "触发NRC0x22的条件之一并发送14 FF FF请求(长度错误)")
        condition = nrc22_condition_list[0] if len(nrc22_condition_list) > 0 else None
        if len(nrc22_condition_list) > 0:
            start_nrc22_condition(condition)
        try:
            status, _ = service_14_check(node, None, [0x7F, 0x14, 0x13],
                                         "NRC0x13的否定响应(7F 14 13) - 长度错误优先",
                                         dl=3, dl_padding=0xFF)
        finally:
            if condition is not None: stop_nrc22_condition(condition)
        if not status: return

        TestLog("INFO", "Step4", "触发NRC0x22的条件之一并发送14 LL MM NN请求(不支持的DTC组)")
        condition = nrc22_condition_list[0] if len(nrc22_condition_list) > 0 else None
        if len(nrc22_condition_list) > 0:
            start_nrc22_condition(condition)
        if len(unsupported_dtc_group_list) > 0:
            try:
                dtc_group = unsupported_dtc_group_list[0]
                status, _ = service_14_check(node, dtc_group, [0x7F, 0x14, 0x31],
                                             "NRC0x31的否定响应(7F 14 31) - 不支持的DTC组优先")
            finally:
                if condition is not None: stop_nrc22_condition(condition)
            if not status: return
        else:
            TestLog("INFO", "", "没有配置不支持的DTC组，跳过此步骤")
            if condition is not None: stop_nrc22_condition(condition)

        TestLog("INFO", "Step5", "触发NRC0x22的条件之一并发送14 FF FF FF请求")
        if len(nrc22_condition_list) > 0:
            condition = nrc22_condition_list[0]
            if not start_nrc22_condition(condition): return
            try:
                status, _ = service_14_check(node, 0xFFFFFF, [0x7F, 0x14, 0x22],
                                             "NRC0x22的否定响应(7F 14 22)")
            finally:
                stop_nrc22_condition(condition)
            if not status: return
        else:
            TestLog("INFO", "", "没有配置NRC22触发条件，跳过此步骤")

        TestLog("INFO", "Step6", "再次触发NRC22条件并发送14 FF FF FF请求")
        if len(nrc22_condition_list) > 0:
            condition = nrc22_condition_list[0]
            if not start_nrc22_condition(condition): return
            try:
                status, _ = service_14_check(node, 0xFFFFFF, [0x7F, 0x14, 0x22],
                                             "NRC0x22的否定响应(7F 14 22)")
            finally:
                stop_nrc22_condition(condition)
            if not status: return
        else:
            TestLog("INFO", "", "没有配置NRC22触发条件，跳过此步骤")

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG9_TC10_funRequest_14_NRCPriority():
    """
    14服务NRC优先级检查(功能寻址)
    """
    case_name = "14服务NRC优先级检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        nrc22_condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x14)
        unsupported_dtc_group_list = UDSTestParams.Services14DTCGroupUnsupportedList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)", func_req=True): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "触发NRC0x22的条件之一并发送14 FF FF请求(长度错误，功能寻址)")
        condition = nrc22_condition_list[0] if len(nrc22_condition_list) > 0 else None
        if len(nrc22_condition_list) > 0:
            start_nrc22_condition(condition)
        try:
            status, _ = service_14_check(node, None, [0x7F, 0x14, 0x13],
                                         "NRC0x13的否定响应(7F 14 13) - 长度错误优先",
                                         func_req=True, dl=3, dl_padding=0xFF)
        finally:
            if condition is not None: stop_nrc22_condition(condition)
        if not status: return

        TestLog("INFO", "Step4", "触发NRC0x22的条件之一并发送14 LL MM NN请求(不支持的DTC组，功能寻址)")
        condition = nrc22_condition_list[0] if len(nrc22_condition_list) > 0 else None
        if len(nrc22_condition_list) > 0:
            start_nrc22_condition(condition)
        if len(unsupported_dtc_group_list) > 0:
            try:
                dtc_group = unsupported_dtc_group_list[0]
                status, _ = service_14_check(node, dtc_group, [0x7F, 0x14, 0x31],
                                             "NRC0x31的否定响应(7F 14 31) - 不支持的DTC组优先", func_req=True)
            finally:
                if condition is not None: stop_nrc22_condition(condition)
            if not status: return
        else:
            TestLog("INFO", "", "没有配置不支持的DTC组，跳过此步骤")
            if condition is not None: stop_nrc22_condition(condition)

        TestLog("INFO", "Step5", "触发NRC0x22的条件之一并发送14 FF FF FF请求(功能寻址)")
        if len(nrc22_condition_list) > 0:
            condition = nrc22_condition_list[0]
            if not start_nrc22_condition(condition): return
            try:
                status, _ = service_14_check(node, 0xFFFFFF, [0x7F, 0x14, 0x22],
                                             "NRC0x22的否定响应(7F 14 22)", func_req=True)
            finally:
                stop_nrc22_condition(condition)
            if not status: return
        else:
            TestLog("INFO", "", "没有配置NRC22触发条件，跳过此步骤")

        TestLog("INFO", "Step6", "再次触发NRC22条件并发送14 FF FF FF请求(功能寻址)")
        if len(nrc22_condition_list) > 0:
            condition = nrc22_condition_list[0]
            if not start_nrc22_condition(condition): return
            try:
                status, _ = service_14_check(node, 0xFFFFFF, [0x7F, 0x14, 0x22],
                                             "NRC0x22的否定响应(7F 14 22)", func_req=True)
            finally:
                stop_nrc22_condition(condition)
            if not status: return
        else:
            TestLog("INFO", "", "没有配置NRC22触发条件，跳过此步骤")

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG10_TC1_phyRequest_19_Positive():
    case_name = "19服务肯定响应检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "使用19 01请求遍历所有支持的状态掩码")
        for msk in UDSTestParams.Services19MaskSupportList:
            status, resp = service_19_check(node, 0x01, [0x59, 0x01], f"肯定响应(59 01)", DTCStatusMask=msk)
            if not status: return

        TestLog("INFO", "Step4", "使用19 02请求遍历所有支持的状态掩码")
        for msk in UDSTestParams.Services19MaskSupportList:
            status, resp = service_19_check(node, 0x02, [0x59, 0x02], f"肯定响应(59 02)", DTCStatusMask=msk)
            if not status: return

        TestLog("INFO", "Step5", "使用19 04请求遍历所有支持的DTC和快照记录号")
        for dtc in UDSTestParams.Services19DTCSupportList:
            for snapshot in UDSTestParams.Services19SnapshotRecordNumberSupportList:
                defined_data = bytes([0x04, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, snapshot])
                status, resp = service_19_check(node, None, [0x59, 0x04], f"肯定响应(59 04)", defined_data=defined_data)
                if not status: return 

        TestLog("INFO", "Step6", "使用19 06请求遍历所有支持的DTC和扩展记录号")
        for dtc in UDSTestParams.Services19DTCSupportList:
            for ext in UDSTestParams.Services19ExtendRecordNumberSupportList:
                defined_data = bytes([0x06, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, ext])
                status, resp = service_19_check(node, None, [0x59, 0x06], f"肯定响应(59 06)", defined_data=defined_data)
                if not status: return

        TestLog("INFO", "Step7", "使用19 0A请求")
        status, resp = service_19_check(node, 0x0A, [0x59, 0x0A], f"肯定响应(59 0A)")
        if not status: return

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step9", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step10", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step12", "使用19 01请求遍历所有支持的状态掩码")
        for msk in UDSTestParams.Services19MaskSupportList:
            status, resp = service_19_check(node, 0x01, [0x59, 0x01], f"肯定响应(59 01)", DTCStatusMask=msk)
            if not status: return

        TestLog("INFO", "Step13", "使用19 02请求遍历所有支持的状态掩码")
        for msk in UDSTestParams.Services19MaskSupportList:
            status, resp = service_19_check(node, 0x02, [0x59, 0x02], f"肯定响应(59 02)", DTCStatusMask=msk)
            if not status: return

        TestLog("INFO", "Step14", "使用19 04请求遍历所有支持的DTC和快照记录号")
        for dtc in UDSTestParams.Services19DTCSupportList:
            for snapshot in UDSTestParams.Services19SnapshotRecordNumberSupportList:
                defined_data = bytes([0x04, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, snapshot])
                status, resp = service_19_check(node, None, [0x59, 0x04], f"肯定响应(59 04)", defined_data=defined_data)
                if not status: return

        TestLog("INFO", "Step15", "使用19 06请求遍历所有支持的DTC和扩展记录号")
        for dtc in UDSTestParams.Services19DTCSupportList:
            for ext in UDSTestParams.Services19ExtendRecordNumberSupportList:
                defined_data = bytes([0x06, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, ext])
                status, resp = service_19_check(node, None, [0x59, 0x06], f"肯定响应(59 06)", defined_data=defined_data)
                if not status: return

        TestLog("INFO", "Step16", "使用19 0A请求")
        status, resp = service_19_check(node, 0x0A, [0x59, 0x0A], f"肯定响应(59 0A)")
        if not status: return

        TestLog("INFO", "Step17", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG10_TC2_funRequest_19_Positive():
    case_name = "19服务肯定响应检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "使用19 01请求遍历所有支持的状态掩码")
        for msk in UDSTestParams.Services19MaskSupportList:
            status, resp = service_19_check(node, 0x01, [0x59, 0x01], f"肯定响应(59 01)", func_req=True, DTCStatusMask=msk)
            if not status: return

        TestLog("INFO", "Step4", "使用19 02请求遍历所有支持的状态掩码")
        for msk in UDSTestParams.Services19MaskSupportList:
            status, resp = service_19_check(node, 0x02, [0x59, 0x02], f"肯定响应(59 02)", func_req=True, DTCStatusMask=msk)
            if not status: return

        TestLog("INFO", "Step5", "使用19 04请求遍历所有支持的DTC和快照记录号")
        for dtc in UDSTestParams.Services19DTCSupportList:
            for snapshot in UDSTestParams.Services19SnapshotRecordNumberSupportList:
                defined_data = bytes([0x04, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, snapshot])
                status, resp = service_19_check(node, None, [0x59, 0x04], f"肯定响应(59 04)", defined_data=defined_data)
                if not status: return

        TestLog("INFO", "Step6", "使用19 06请求遍历所有支持的DTC和扩展记录号")
        for dtc in UDSTestParams.Services19DTCSupportList:
            for ext in UDSTestParams.Services19ExtendRecordNumberSupportList:
                defined_data = bytes([0x06, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, ext])
                status, resp = service_19_check(node, None, [0x59, 0x06], f"肯定响应(59 06)", defined_data=defined_data)
                if not status: return

        TestLog("INFO", "Step7", "使用19 0A请求")
        status, resp = service_19_check(node, 0x0A, [0x59, 0x0A], f"肯定响应(59 0A)", func_req=True)
        if not status: return

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step9", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step10", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step12", "使用19 01请求遍历所有支持的状态掩码")
        for msk in UDSTestParams.Services19MaskSupportList:
            status, resp = service_19_check(node, 0x01, [0x59, 0x01], f"肯定响应(59 01)", func_req=True, DTCStatusMask=msk)
            if not status: return

        TestLog("INFO", "Step13", "使用19 02请求遍历所有支持的状态掩码")
        for msk in UDSTestParams.Services19MaskSupportList:
            status, resp = service_19_check(node, 0x02, [0x59, 0x02], f"肯定响应(59 02)", func_req=True, DTCStatusMask=msk)
            if not status: return

        TestLog("INFO", "Step14", "使用19 04请求遍历所有支持的DTC和快照记录号")
        for dtc in UDSTestParams.Services19DTCSupportList:
            for snapshot in UDSTestParams.Services19SnapshotRecordNumberSupportList:
                defined_data = bytes([0x04, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, snapshot])
                status, resp = service_19_check(node, None, [0x59, 0x04], f"肯定响应(59 04)", defined_data=defined_data)
                if not status: return

        TestLog("INFO", "Step15", "使用19 06请求遍历所有支持的DTC和扩展记录号")
        for dtc in UDSTestParams.Services19DTCSupportList:
            for ext in UDSTestParams.Services19ExtendRecordNumberSupportList:
                defined_data = bytes([0x06, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, ext])
                status, resp = service_19_check(node, None, [0x59, 0x06], f"肯定响应(59 06)", defined_data=defined_data)
                if not status: return

        TestLog("INFO", "Step16", "使用19 0A请求")
        status, resp = service_19_check(node, 0x0A, [0x59, 0x0A], f"肯定响应(59 0A)", func_req=True)
        if not status: return

        TestLog("INFO", "Step17", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG10_TC3_phyRequest_19_NRC12():
    case_name = "19服务NRC12检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    sn_min, sn_max = UDSTestParams.MinSubID, UDSTestParams.MaxSubID
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "使用19 SN请求遍历所有不支持的子功能")
        for sn in range(sn_min, sn_max + 1):
            if sn in UDSTestParams.Services19SubfunSupportList:
                continue
            status, resp = service_19_check(node, sn, [0x7F, 0x19, 0x12], f"否定响应(7F 19 12)")
            if not status: return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step6", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "使用19 SN请求遍历所有不支持的子功能")
        for sn in range(sn_min, sn_max + 1):
            if sn in UDSTestParams.Services19SubfunSupportList:
                continue
            status, resp = service_19_check(node, sn, [0x7F, 0x19, 0x12], f"否定响应(7F 19 12)")
            if not status: return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG10_TC4_funRequest_19_NRC12():
    case_name = "19服务NRC12检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    sn_min, sn_max = UDSTestParams.MinSubID, UDSTestParams.MaxSubID
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "使用19 SN请求遍历所有不支持的子功能")
        for sn in range(sn_min, sn_max + 1):
            if sn in UDSTestParams.Services19SubfunSupportList:
                continue
            status, resp = service_19_check(node, sn, None, f"无响应", func_req=True, timeout=0.1)
            if not status: return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step6", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "使用19 SN请求遍历所有不支持的子功能")
        for sn in range(sn_min, sn_max + 1):
            if sn in UDSTestParams.Services19SubfunSupportList:
                continue
            status, resp = service_19_check(node, sn, None, f"无响应", func_req=True, timeout=0.1)
            if not status: return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG10_TC5_phyRequest_19_NRC13():
    case_name = "19服务NRC13检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送长度不正确的19 01请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        data_list = [
            [], [0x01], [0x01, msk, 0x00], [0x01, msk, 0x00, 0x00], [0x01, msk, 0x00, 0x00, 0x00], [0x01, msk, 0x00, 0x00, 0x00, 0x00]
            # [], [0x01], [0x01, 0x00, 0x00], [0x01, 0x00, 0x00, 0x00], [0x01, 0x00, 0x00, 0x00, 0x00], [0x01, 0x00, 0x00, 0x00, 0x00, 0x00]
        ]
        for data in data_list:
            status, resp = service_19_check(node, None, defined_data=data, expect_data=[0x7F, 0x19, 0x13], expect_str="否定响应(7F 19 13)")
            if not status: return

        TestLog("INFO", "Step4", "发送长度不正确的19 02请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        data_list = [
            [], [0x02], [0x02, msk, 0x00], [0x02, msk, 0x00, 0x00], [0x02, msk, 0x00, 0x00, 0x00], [0x02, msk, 0x00, 0x00, 0x00, 0x00]
            # [], [0x02], [0x02, 0x00, 0x00], [0x02, 0x00, 0x00, 0x00], [0x02, 0x00, 0x00, 0x00, 0x00], [0x02, 0x00, 0x00, 0x00, 0x00, 0x00]
        ]
        for data in data_list:
            status, resp = service_19_check(node, None, defined_data=data, expect_data=[0x7F, 0x19, 0x13], expect_str="否定响应(7F 19 13)")
            if not status: return

        TestLog("INFO", "Step5", "发送长度不正确的19 04请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        dtc = UDSTestParams.Services19DTCSupportList[0]
        number = UDSTestParams.Services19ExtendRecordNumberSupportList[0]
        dtc_h, dtc_m, dtc_l = (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF
        data_list = [
            [], [0x04], [0x04, dtc_h], [0x04, dtc_h, dtc_m], [0x04, dtc_h, dtc_m, dtc_l], [0x04, dtc_h, dtc_m, dtc_l, number, 0x00]
            # [], [0x04], [0x04, 0x00], [0x04, 0x00, 0x00], [0x04, 0x00, 0x00, 0x00], [0x04, 0x00, 0x00, 0x00, 0x00, 0x00]
        ]
        for data in data_list:
            status, resp = service_19_check(node, None, defined_data=data, expect_data=[0x7F, 0x19, 0x13], expect_str="否定响应(7F 19 13)")
            if not status: return

        TestLog("INFO", "Step6", "发送长度不正确的19 06请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        dtc = UDSTestParams.Services19DTCSupportList[0]
        number = UDSTestParams.Services19ExtendRecordNumberSupportList[0]
        dtc_h, dtc_m, dtc_l = (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF
        data_list = [
            [], [0x06], [0x06, dtc_h], [0x06, dtc_h, dtc_m], [0x06, dtc_h, dtc_m, dtc_l], [0x06, dtc_h, dtc_m, dtc_l, number, 0x00]
            # [], [0x06], [0x06, 0x00], [0x06, 0x00, 0x00], [0x06, 0x00, 0x00, 0x00], [0x06, 0x00, 0x00, 0x00, 0x00, 0x00]
        ]
        for data in data_list:
            status, resp = service_19_check(node, None, defined_data=data, expect_data=[0x7F, 0x19, 0x13], expect_str="否定响应(7F 19 13)")
            if not status: return

        TestLog("INFO", "Step7", "发送长度不正确的19 0A请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        dtc = UDSTestParams.Services19DTCSupportList[0]
        number = UDSTestParams.Services19ExtendRecordNumberSupportList[0]
        dtc_h, dtc_m, dtc_l = (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF
        data_list = [
            [], [0x0A, dtc_h], [0x0A, dtc_h, dtc_m], [0x0A, dtc_h, dtc_m, dtc_l], [0x0A, dtc_h, dtc_m, dtc_l, number, 0x00]
            # [], [0x0A, 0x00], [0x0A, 0x00, 0x00], [0x0A, 0x00, 0x00, 0x00], [0x0A, 0x00, 0x00, 0x00, 0x00], [0x0A, 0x00, 0x00, 0x00, 0x00, 0x00]
        ]
        for data in data_list:
            status, resp = service_19_check(node, None, defined_data=data, expect_data=[0x7F, 0x19, 0x13], expect_str="否定响应(7F 19 13)")
            if not status: return

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step9", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step10", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step12", "发送长度不正确的19 01请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        data_list = [
            [], [0x01], [0x01, msk, 0x00], [0x01, msk, 0x00, 0x00], [0x01, msk, 0x00, 0x00, 0x00], [0x01, msk, 0x00, 0x00, 0x00, 0x00]
            # [], [0x01], [0x01, 0x00, 0x00], [0x01, 0x00, 0x00, 0x00], [0x01, 0x00, 0x00, 0x00, 0x00], [0x01, 0x00, 0x00, 0x00, 0x00, 0x00]
        ]
        for data in data_list:
            status, resp = service_19_check(node, None, defined_data=data, expect_data=[0x7F, 0x19, 0x13], expect_str="否定响应(7F 19 13)")
            if not status: return

        TestLog("INFO", "Step13", "发送长度不正确的19 02请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        data_list = [
            [], [0x02], [0x02, msk, 0x00], [0x02, msk, 0x00, 0x00], [0x02, msk, 0x00, 0x00, 0x00], [0x02, msk, 0x00, 0x00, 0x00, 0x00]
            # [], [0x02], [0x02, 0x00, 0x00], [0x02, 0x00, 0x00, 0x00], [0x02, 0x00, 0x00, 0x00, 0x00], [0x02, 0x00, 0x00, 0x00, 0x00, 0x00]
        ]
        for data in data_list:
            status, resp = service_19_check(node, None, defined_data=data, expect_data=[0x7F, 0x19, 0x13], expect_str="否定响应(7F 19 13)")
            if not status: return

        TestLog("INFO", "Step14", "发送长度不正确的19 04请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        dtc = UDSTestParams.Services19DTCSupportList[0]
        number = UDSTestParams.Services19ExtendRecordNumberSupportList[0]
        dtc_h, dtc_m, dtc_l = (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF
        data_list = [
            [], [0x04], [0x04, dtc_h], [0x04, dtc_h, dtc_m], [0x04, dtc_h, dtc_m, dtc_l], [0x04, dtc_h, dtc_m, dtc_l, number, 0x00]
            # [], [0x04], [0x04, 0x00], [0x04, 0x00, 0x00], [0x04, 0x00, 0x00, 0x00], [0x04, 0x00, 0x00, 0x00, 0x00, 0x00]
        ]
        for data in data_list:
            status, resp = service_19_check(node, None, defined_data=data, expect_data=[0x7F, 0x19, 0x13], expect_str="否定响应(7F 19 13)")
            if not status: return

        TestLog("INFO", "Step15", "发送长度不正确的19 06请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        dtc = UDSTestParams.Services19DTCSupportList[0]
        number = UDSTestParams.Services19ExtendRecordNumberSupportList[0]
        dtc_h, dtc_m, dtc_l = (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF
        data_list = [
            [], [0x06], [0x06, dtc_h], [0x06, dtc_h, dtc_m], [0x06, dtc_h, dtc_m, dtc_l], [0x06, dtc_h, dtc_m, dtc_l, number, 0x00]
            # [], [0x06], [0x06, 0x00], [0x06, 0x00, 0x00], [0x06, 0x00, 0x00, 0x00], [0x06, 0x00, 0x00, 0x00, 0x00, 0x00]
        ]
        for data in data_list:
            status, resp = service_19_check(node, None, defined_data=data, expect_data=[0x7F, 0x19, 0x13], expect_str="否定响应(7F 19 13)")
            if not status: return

        TestLog("INFO", "Step16", "发送长度不正确的19 0A请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        dtc = UDSTestParams.Services19DTCSupportList[0]
        number = UDSTestParams.Services19ExtendRecordNumberSupportList[0]
        dtc_h, dtc_m, dtc_l = (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF
        data_list = [
            [], [0x0A, dtc_h], [0x0A, dtc_h, dtc_m], [0x0A, dtc_h, dtc_m, dtc_l], [0x0A, dtc_h, dtc_m, dtc_l, number, 0x00]
            # [], [0x0A, 0x00], [0x0A, 0x00, 0x00], [0x0A, 0x00, 0x00, 0x00], [0x0A, 0x00, 0x00, 0x00, 0x00], [0x0A, 0x00, 0x00, 0x00, 0x00, 0x00]
        ]
        for data in data_list:
            status, resp = service_19_check(node, None, defined_data=data, expect_data=[0x7F, 0x19, 0x13], expect_str="否定响应(7F 19 13)")
            if not status: return

        TestLog("INFO", "Step17", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG10_TC6_funRequest_19_NRC13():
    case_name = "19服务NRC13检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送长度不正确的19 01请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        data_list = [
            [], [0x01], [0x01, msk, 0x00], [0x01, msk, 0x00, 0x00], [0x01, msk, 0x00, 0x00, 0x00], [0x01, msk, 0x00, 0x00, 0x00, 0x00]
        ]
        for data in data_list:
            status, resp = service_19_check(node, None, defined_data=data, expect_data=[0x7F, 0x19, 0x13], expect_str="否定响应(7F 19 13)", func_req=True)
            if not status: return

        TestLog("INFO", "Step4", "发送长度不正确的19 02请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        data_list = [
            [], [0x02], [0x02, msk, 0x00], [0x02, msk, 0x00, 0x00], [0x02, msk, 0x00, 0x00, 0x00], [0x02, msk, 0x00, 0x00, 0x00, 0x00]
        ]
        for data in data_list:
            status, resp = service_19_check(node, None, defined_data=data, expect_data=[0x7F, 0x19, 0x13], expect_str="否定响应(7F 19 13)", func_req=True)
            if not status: return

        TestLog("INFO", "Step5", "发送长度不正确的19 04请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        dtc = UDSTestParams.Services19DTCSupportList[0]
        number = UDSTestParams.Services19ExtendRecordNumberSupportList[0]
        dtc_h, dtc_m, dtc_l = (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF
        data_list = [
            [], [0x04], [0x04, dtc_h], [0x04, dtc_h, dtc_m], [0x04, dtc_h, dtc_m, dtc_l], [0x04, dtc_h, dtc_m, dtc_l, number, 0x00]
        ]
        for data in data_list:
            status, resp = service_19_check(node, None, defined_data=data, expect_data=[0x7F, 0x19, 0x13], expect_str="否定响应(7F 19 13)", func_req=True)
            if not status: return

        TestLog("INFO", "Step6", "发送长度不正确的19 06请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        dtc = UDSTestParams.Services19DTCSupportList[0]
        number = UDSTestParams.Services19ExtendRecordNumberSupportList[0]
        dtc_h, dtc_m, dtc_l = (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF
        data_list = [
            [], [0x06], [0x06, dtc_h], [0x06, dtc_h, dtc_m], [0x06, dtc_h, dtc_m, dtc_l], [0x06, dtc_h, dtc_m, dtc_l, number, 0x00]
        ]
        for data in data_list:
            status, resp = service_19_check(node, None, defined_data=data, expect_data=[0x7F, 0x19, 0x13], expect_str="否定响应(7F 19 13)", func_req=True)
            if not status: return

        TestLog("INFO", "Step7", "发送长度不正确的19 0A请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        dtc = UDSTestParams.Services19DTCSupportList[0]
        number = UDSTestParams.Services19ExtendRecordNumberSupportList[0]
        dtc_h, dtc_m, dtc_l = (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF
        data_list = [
            [], [0x0A, dtc_h], [0x0A, dtc_h, dtc_m], [0x0A, dtc_h, dtc_m, dtc_l], [0x0A, dtc_h, dtc_m, dtc_l, number, 0x00]
        ]
        for data in data_list:
            status, resp = service_19_check(node, None, defined_data=data, expect_data=[0x7F, 0x19, 0x13], expect_str="否定响应(7F 19 13)", func_req=True)
            if not status: return

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step9", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step10", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step12", "发送长度不正确的19 01请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        data_list = [
            [], [0x01], [0x01, msk, 0x00], [0x01, msk, 0x00, 0x00], [0x01, msk, 0x00, 0x00, 0x00], [0x01, msk, 0x00, 0x00, 0x00, 0x00]
        ]
        for data in data_list:
            status, resp = service_19_check(node, None, defined_data=data, expect_data=[0x7F, 0x19, 0x13], expect_str="否定响应(7F 19 13)", func_req=True)
            if not status: return

        TestLog("INFO", "Step13", "发送长度不正确的19 02请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        data_list = [
            [], [0x02], [0x02, msk, 0x00], [0x02, msk, 0x00, 0x00], [0x02, msk, 0x00, 0x00, 0x00], [0x02, msk, 0x00, 0x00, 0x00, 0x00]
        ]
        for data in data_list:
            status, resp = service_19_check(node, None, defined_data=data, expect_data=[0x7F, 0x19, 0x13], expect_str="否定响应(7F 19 13)", func_req=True)
            if not status: return

        TestLog("INFO", "Step14", "发送长度不正确的19 04请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        dtc = UDSTestParams.Services19DTCSupportList[0]
        number = UDSTestParams.Services19ExtendRecordNumberSupportList[0]
        dtc_h, dtc_m, dtc_l = (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF
        data_list = [
            [], [0x04], [0x04, dtc_h], [0x04, dtc_h, dtc_m], [0x04, dtc_h, dtc_m, dtc_l], [0x04, dtc_h, dtc_m, dtc_l, number, 0x00]
        ]
        for data in data_list:
            status, resp = service_19_check(node, None, defined_data=data, expect_data=[0x7F, 0x19, 0x13], expect_str="否定响应(7F 19 13)", func_req=True)
            if not status: return

        TestLog("INFO", "Step15", "发送长度不正确的19 06请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        dtc = UDSTestParams.Services19DTCSupportList[0]
        number = UDSTestParams.Services19ExtendRecordNumberSupportList[0]
        dtc_h, dtc_m, dtc_l = (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF
        data_list = [
            [], [0x06], [0x06, dtc_h], [0x06, dtc_h, dtc_m], [0x06, dtc_h, dtc_m, dtc_l], [0x06, dtc_h, dtc_m, dtc_l, number, 0x00]
        ]
        for data in data_list:
            status, resp = service_19_check(node, None, defined_data=data, expect_data=[0x7F, 0x19, 0x13], expect_str="否定响应(7F 19 13)", func_req=True)
            if not status: return

        TestLog("INFO", "Step16", "发送长度不正确的19 0A请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        dtc = UDSTestParams.Services19DTCSupportList[0]
        number = UDSTestParams.Services19ExtendRecordNumberSupportList[0]
        dtc_h, dtc_m, dtc_l = (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF
        data_list = [
            [], [0x0A, dtc_h], [0x0A, dtc_h, dtc_m], [0x0A, dtc_h, dtc_m, dtc_l], [0x0A, dtc_h, dtc_m, dtc_l, number, 0x00]
        ]
        for data in data_list:
            status, resp = service_19_check(node, None, defined_data=data, expect_data=[0x7F, 0x19, 0x13], expect_str="否定响应(7F 19 13)", func_req=True)
            if not status: return

        TestLog("INFO", "Step17", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG10_TC7_phyRequest_19_NRC31():
    case_name = "19服务NRC31检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        dtc_not_support_list = UDSTestParams.Services19DTCUnSupportList

        TestLog("INFO", "Step3", "使用19 04请求遍历不支持的DTC")
        for dtc in dtc_not_support_list:
            for snapshot in UDSTestParams.Services19SnapshotRecordNumberSupportList:  # 0x01, 0xFF
                defined_data = bytes([0x04, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, snapshot])
                status, resp = service_19_check(node, None, [0x7F, 0x19, 0x31], f"否定响应(7F 19 31)", defined_data=defined_data)
                if not status: return

        TestLog("INFO", "Step4", "使用19 06请求遍历不支持的DTC")
        for dtc in dtc_not_support_list:
            for ext in UDSTestParams.Services19ExtendRecordNumberSupportList:  # 0x01, 0xFF
                defined_data = bytes([0x06, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, ext])
                status, resp = service_19_check(node, None, [0x7F, 0x19, 0x31], f"否定响应(7F 19 31)", defined_data=defined_data)
                if not status: return

        if not UDSTestParams.Services19DTCSupportList:
            TestLog("WARNING", case_name, "Services19DTCSupportList 为空，Step5/6/13/14 将被跳过")

        TestLog("INFO", "Step5", "使用19 04请求发送一个支持的DTC，遍历所有不等于0x00、0x01、0x02、0xFF的NUM")
        for dtc in UDSTestParams.Services19DTCSupportList[:1]:
            for snapshot in range(0x00, 0xFF):
                if snapshot in [0x00, 0x01, 0x02, 0xFF]:
                    continue
                defined_data = bytes([0x04, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, snapshot])
                status, resp = service_19_check(node, None, [0x7F, 0x19, 0x31], f"否定响应(7F 19 31)", defined_data=defined_data)
                if not status: return

        TestLog("INFO", "Step6", "使用19 06请求发送一个支持的DTC，遍历所有不等于0x01的NUM")
        for dtc in UDSTestParams.Services19DTCSupportList[:1]:
            for ext in range(0x00, 0xFF):
                if ext in [0x01]:
                    continue
                defined_data = bytes([0x06, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, ext])
                status, resp = service_19_check(node, None, [0x7F, 0x19, 0x31], f"否定响应(7F 19 31)", defined_data=defined_data)
                if not status: return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step8", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step9", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step10", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step11", "使用19 04请求遍历不支持的DTC")
        for dtc in dtc_not_support_list:
            for snapshot in UDSTestParams.Services19SnapshotRecordNumberSupportList:  # 0x01, 0xFF
                defined_data = bytes([0x04, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, snapshot])
                status, resp = service_19_check(node, None, [0x7F, 0x19, 0x31], f"否定响应(7F 19 31)", defined_data=defined_data)
                if not status: return

        TestLog("INFO", "Step12", "使用19 06请求遍历不支持的DTC")
        for dtc in dtc_not_support_list:
            for ext in UDSTestParams.Services19ExtendRecordNumberSupportList:  # 0x01, 0xFF
                defined_data = bytes([0x06, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, ext])
                status, resp = service_19_check(node, None, [0x7F, 0x19, 0x31], f"否定响应(7F 19 31)", defined_data=defined_data)
                if not status: return

        TestLog("INFO", "Step13", "使用19 04请求发送一个支持的DTC，遍历所有不等于0x00、0x01、0x02、0xFF的NUM")
        for dtc in UDSTestParams.Services19DTCSupportList[:1]:
            for snapshot in range(0x00, 0xFF):
                if snapshot in [0x00, 0x01, 0x02, 0xFF]:
                    continue
                defined_data = bytes([0x04, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, snapshot])
                status, resp = service_19_check(node, None, [0x7F, 0x19, 0x31], f"否定响应(7F 19 31)", defined_data=defined_data)
                if not status: return

        TestLog("INFO", "Step14", "使用19 06请求发送一个支持的DTC，遍历所有不等于0x01的NUM")
        for dtc in UDSTestParams.Services19DTCSupportList[:1]:
            for ext in range(0x00, 0xFF):
                if ext in [0x01]:
                    continue
                defined_data = bytes([0x06, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, ext])
                status, resp = service_19_check(node, None, [0x7F, 0x19, 0x31], f"否定响应(7F 19 31)", defined_data=defined_data)
                if not status: return

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG10_TC8_funRequest_19_NRC31():
    case_name = "19服务NRC31检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        dtc_not_support_list = UDSTestParams.Services19DTCUnSupportList

        TestLog("INFO", "Step3", "使用19 04请求遍历不支持的DTC")
        for dtc in dtc_not_support_list:
            for snapshot in UDSTestParams.Services19SnapshotRecordNumberSupportList:  # 0x01, 0xFF
                defined_data = bytes([0x04, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, snapshot])
                status, resp = service_19_check(node, None, None, f"无响应", timeout=0.1, defined_data=defined_data, func_req=True)
                if not status: return

        TestLog("INFO", "Step4", "使用19 06请求遍历不支持的DTC")
        for dtc in dtc_not_support_list:
            for ext in UDSTestParams.Services19ExtendRecordNumberSupportList:  # 0x01, 0xFF
                defined_data = bytes([0x06, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, ext])
                status, resp = service_19_check(node, None, None, f"无响应", timeout=0.1, defined_data=defined_data, func_req=True)
                if not status: return

        if not UDSTestParams.Services19DTCSupportList:
            TestLog("WARNING", case_name, "Services19DTCSupportList 为空，Step5/6/13/14 将被跳过")

        TestLog("INFO", "Step5", "使用19 04请求发送一个支持的DTC，遍历所有不等于0x00、0x01、0x02、0xFF的NUM")
        for dtc in UDSTestParams.Services19DTCSupportList[:1]:
            for snapshot in range(0x00, 0xFF):
                if snapshot in [0x00, 0x01, 0x02, 0xFF]:
                    continue
                defined_data = bytes([0x04, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, snapshot])
                status, resp = service_19_check(node, None, None, f"无响应", timeout=0.1, defined_data=defined_data, func_req=True)
                if not status: return

        TestLog("INFO", "Step6", "使用19 06请求发送一个支持的DTC，遍历所有不等于0x01的NUM")
        for dtc in UDSTestParams.Services19DTCSupportList[:1]:
            for ext in range(0x00, 0xFF):
                if ext in [0x01]:
                    continue
                defined_data = bytes([0x06, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, ext])
                status, resp = service_19_check(node, None, None, f"无响应", timeout=0.1, defined_data=defined_data, func_req=True)
                if not status: return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step8", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step9", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step10", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step11", "使用19 04请求遍历不支持的DTC")
        for dtc in dtc_not_support_list:
            for snapshot in UDSTestParams.Services19SnapshotRecordNumberSupportList:  # 0x01, 0xFF
                defined_data = bytes([0x04, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, snapshot])
                status, resp = service_19_check(node, None, None, f"无响应", timeout=0.1, defined_data=defined_data, func_req=True)
                if not status: return

        TestLog("INFO", "Step12", "使用19 06请求遍历不支持的DTC")
        for dtc in dtc_not_support_list:
            for ext in UDSTestParams.Services19ExtendRecordNumberSupportList:  # 0x01, 0xFF
                defined_data = bytes([0x06, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, ext])
                status, resp = service_19_check(node, None, None, f"无响应", timeout=0.1, defined_data=defined_data, func_req=True)
                if not status: return

        TestLog("INFO", "Step13", "使用19 04请求发送一个支持的DTC，遍历所有不等于0x00、0x01、0x02、0xFF的NUM")
        for dtc in UDSTestParams.Services19DTCSupportList[:1]:
            for snapshot in range(0x00, 0xFF):
                if snapshot in [0x00, 0x01, 0x02, 0xFF]:
                    continue
                defined_data = bytes([0x04, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, snapshot])
                status, resp = service_19_check(node, None, None, f"无响应", timeout=0.1, defined_data=defined_data, func_req=True)
                if not status: return

        TestLog("INFO", "Step14", "使用19 06请求发送一个支持的DTC，遍历所有不等于0x01的NUM")
        for dtc in UDSTestParams.Services19DTCSupportList[:1]:
            for ext in range(0x00, 0xFF):
                if ext in [0x01]:
                    continue
                defined_data = bytes([0x06, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, ext])
                status, resp = service_19_check(node, None, None, f"无响应", timeout=0.1, defined_data=defined_data, func_req=True)
                if not status: return

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG10_TC9_phyRequest_19_NRCPriorityCheck():
    case_name = "19服务NRC优先级检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "使用19请求")
        status, resp = service_19_check(node, None, [0x7F, 0x19, 0x13], f"否定响应(7F 19 13)")
        if not status: return

        TestLog("INFO", "Step4", "使用19 0B请求")
        status, resp = service_19_check(node, None, defined_data=[0x0B], expect_data=[0x7F, 0x19, 0x12], expect_str=f"否定响应(7F 19 12)")
        if not status: return

        TestLog("INFO", "Step5", "使用19 0B 00请求")
        status, resp = service_19_check(node, None, defined_data=[0x0B, 0x00], expect_data=[0x7F, 0x19, 0x12], expect_str=f"否定响应(7F 19 12)")
        if not status: return

        TestLog("INFO", "Step6", "发送19 XX XX + (length-1)字节数据请求")
        defined_data = bytes([0x04, 0x00, 0x00, 0xFF])
        status, resp = service_19_check(node, None, [0x7F, 0x19, 0x13], f"否定响应(7F 19 13)", defined_data=defined_data)
        if not status: return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG10_TC10_funRequest_19_NRCPriorityCheck():
    case_name = "19服务NRC优先级检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "使用19请求")
        status, resp = service_19_check(node, None, [0x7F, 0x19, 0x13], f"否定响应(7F 19 13)", func_req=True)
        if not status: return

        TestLog("INFO", "Step4", "使用19 0B请求(功能寻址NRC12抑制，期望无响应)")
        status, resp = service_19_check(node, None, defined_data=[0x0B], expect_data=None, expect_str="功能寻址NRC12抑制，无响应", func_req=True, timeout=0.1)
        if not status: return

        TestLog("INFO", "Step5", "使用19 0B 00请求(功能寻址NRC12抑制，期望无响应)")
        status, resp = service_19_check(node, None, defined_data=[0x0B, 0x00], expect_data=None, expect_str="功能寻址NRC12抑制，无响应", func_req=True, timeout=0.1)
        if not status: return

        TestLog("INFO", "Step6", "发送19 XX XX + (length-1)字节数据请求")
        defined_data = bytes([0x04, 0x00, 0x00, 0xFF])
        status, resp = service_19_check(node, None, defined_data=defined_data, expect_data=[0x7F, 0x19, 0x13], expect_str=f"否定响应(7F 19 13)", func_req=True)
        if not status: return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG11_TC1_phyRequest_2F_Positive():
    """
    2F服务肯定响应检查(物理寻址)
    """
    case_name = "2F服务肯定响应检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        did_list = UDSTestParams.Services2FDIDSupportList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "发送27 01请求")
        status, resp = service_27_check(node, 0x01, [0x67, 0x01], "返回种子(67 01 XX XX XX XX)")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step5", "发送27 02请求")
        if not service_27_xx_check(node, 0x02, seed_list, [0x67, 0x02], "肯定响应，解锁成功(67 02)", alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step6", "遍历所有支持的2F服务的DID")
        for did_info in did_list:
            did = did_info.get('did', 0)
            control_params = did_info.get('control_params', [])
            for sn in control_params:
                did_h, did_l = (did >> 8) & 0xFF, did & 0xFF
                status, _ = service_2F_check(node, did, sn, [0x6F, did_h, did_l],
                                             f"肯定响应(6F {did_h:02X} {did_l:02X} XX) - DID: {did:04X}, SN: {sn:02X}")
                if not status: return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG11_TC2_phyRequest_2F_ControlParam():
    """
    2F服务控制参数检查(物理寻址)
    """
    case_name = "2F服务控制参数检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        did_list_00 = UDSTestParams.Services2FControlParam00DIDList
        did_list_02 = UDSTestParams.Services2FControlParam02DIDList
        did_list_03 = UDSTestParams.Services2FControlParam03DIDList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "发送27 01请求")
        status, resp = service_27_check(node, 0x01, [0x67, 0x01], "返回种子(67 01 XX XX XX XX)")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step5", "发送27 02请求")
        if not service_27_xx_check(node, 0x02, seed_list, [0x67, 0x02], "肯定响应，解锁成功(67 02)", alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step6", "遍历所有支持控制参数00的2F服务的DID")
        for did in did_list_00:
            did_h, did_l = (did >> 8) & 0xFF, did & 0xFF
            status, _ = service_2F_check(node, did, 0x00, [0x6F, did_h, did_l],
                                         f"肯定响应(6F {did_h:02X} {did_l:02X} XX) - DID: {did:04X}, SN: 0x00")
            if not status: return

        TestLog("INFO", "Step7", "遍历所有支持控制参数02的2F服务的DID")
        for did in did_list_02:
            did_h, did_l = (did >> 8) & 0xFF, did & 0xFF
            status, _ = service_2F_check(node, did, 0x02, [0x6F, did_h, did_l],
                                         f"肯定响应(6F {did_h:02X} {did_l:02X} XX) - DID: {did:04X}, SN: 0x02")
            if not status: return

        TestLog("INFO", "Step8", "遍历所有支持控制参数03的2F服务的DID")
        for did in did_list_03:
            did_h, did_l = (did >> 8) & 0xFF, did & 0xFF
            status, _ = service_2F_check(node, did, 0x03, [0x6F, did_h, did_l],
                                         f"肯定响应(6F {did_h:02X} {did_l:02X} XX) - DID: {did:04X}, SN: 0x03")
            if not status: return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG11_TC3_phyRequest_2F_NRC7F():
    """
    2F服务NRC7F检查(物理寻址)
    """
    case_name = "2F服务NRC7F检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        did_list = UDSTestParams.Services2FDIDSupportList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送一个2F服务请求(在扩展会话下支持)")
        if len(did_list) > 0:
            did_info = did_list[0]
            did = did_info.get('did', 0)
            control_params = did_info.get('control_params', [0x00])
            sn = control_params[0] if control_params else 0x00
            status, _ = service_2F_check(node, did, sn, [0x7F, 0x2F, 0x7F], "否定响应，NRC=7F(7F 2F 7F)")
            if not status: return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step6", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step10", "发送一个2F服务请求(在扩展会话下支持)")
        if len(did_list) > 0:
            did_info = did_list[0]
            did = did_info.get('did', 0)
            control_params = did_info.get('control_params', [0x00])
            sn = control_params[0] if control_params else 0x00
            status, _ = service_2F_check(node, did, sn, [[0x7F, 0x2F, 0x7F], [0x7F, 0x2F, 0x11]],
                                         "否定响应，NRC=7F或NRC=0x11(7F 2F 7F or 7F 2F 11)")
            if not status: return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG11_TC4_phyRequest_2F_NRC13():
    """
    2F服务NRC13检查(物理寻址)
    """
    case_name = "2F服务NRC13检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        did_list = UDSTestParams.Services2FDIDSupportList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "发送27 01请求")
        status, resp = service_27_check(node, 0x01, [0x67, 0x01], "返回种子(67 01 XX XX XX XX)")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step5", "发送27 02请求")
        if not service_27_xx_check(node, 0x02, seed_list, [0x67, 0x02], "肯定响应，解锁成功(67 02)", alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step6", "发送长度较短的2F请求(2F DIDH DIDL)")
        for did_info in did_list:
            did = did_info.get('did', 0)
            status, _ = service_2F_check(node, did, None, [0x7F, 0x2F, 0x13],
                                         f"否定响应，NRC=13(7F 2F 13) - DID: {did:04X}", dl=3)
            if not status: return

        TestLog("INFO", "Step7", "发送位映射DID的2F请求(长度不正确)")
        for did_info in did_list:
            did = did_info.get('did', 0)
            status, _ = service_2F_check(node, did, 0x00, [0x7F, 0x2F, 0x13],
                                         f"否定响应，NRC=13(7F 2F 13) - DID: {did:04X}", dl=5, dl_padding=0x00)
            if not status: return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG11_TC5_phyRequest_2F_NRC31():
    """
    2F服务NRC31检查(物理寻址)
    """
    case_name = "2F服务NRC31检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        unsupported_did_list = UDSTestParams.Services2FDIDUnsupportedList
        did_list = UDSTestParams.Services2FDIDSupportList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        time.sleep(2)

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "发送27 01请求")
        status, resp = service_27_check(node, 0x01, [0x67, 0x01], "返回种子(67 01 XX XX XX XX)")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step5", "发送27 02请求")
        if not service_27_xx_check(node, 0x02, seed_list, [0x67, 0x02], "肯定响应，解锁成功(67 02)", alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step6", "遍历不支持的DID发送2F请求")
        for did in unsupported_did_list:
            for sn in [0x00, 0x02, 0x03]:
                did_h, did_l = (did >> 8) & 0xFF, did & 0xFF
                status, _ = service_2F_check(node, did, sn, [0x7F, 0x2F, 0x31], f"否定响应，NRC=31(7F 2F 31) - DID: {did:04X}, SN: {sn:02X}")
                if not status: return

        TestLog("INFO", "Step7", "遍历支持的DID发送不支持的控制参数")
        for did_info in did_list:
            did = did_info.get('did', 0)
            supported_params = did_info.get('control_params', [])
            for unsupported_sn in [0x01, 0x04, 0x05]:
                if unsupported_sn not in supported_params:
                    did_h, did_l = (did >> 8) & 0xFF, did & 0xFF
                    status, _ = service_2F_check(node, did, unsupported_sn, [0x7F, 0x2F, 0x31],
                                                 f"否定响应，NRC=31(7F 2F 31) - DID: {did:04X}, 不支持的SN: {unsupported_sn:02X}")
                    if not status: return
                    break

        TestLog("INFO", "Step8", "遍历位映射DID发送不支持的位使能控制组合")
        TestLog("INFO", "", "跳过位映射DID测试(需根据实际DID配置实现)")

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG11_TC6_phyRequest_2F_NRC33():
    """
    2F服务NRC33检查(物理寻址)
    """
    case_name = "2F服务NRC33检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        security_did_list = UDSTestParams.Services2FDIDSupportList
        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "遍历所有需要安全解锁的2F服务DID(未解锁状态)")
        for did_info in security_did_list:
            did = did_info.get('did', 0)
            print(f"did = {hex(did)}")
            control_params = did_info.get('control_params', [0x00])
            sn = control_params[0] if control_params else 0x00
            did_h, did_l = (did >> 8) & 0xFF, did & 0xFF
            status, _ = service_2F_check(node, did, sn, [0x7F, 0x2F, 0x33],
                                         f"否定响应，NRC=33(7F 2F 33) - DID: {did:04X}")
            if not status: return

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG11_TC7_phyRequest_2F_NRC22():
    """
    2F服务NRC22检查(物理寻址)
    """
    case_name = "2F服务NRC22检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        nrc22_condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x2F)
        did_list = UDSTestParams.Services2FDIDSupportList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "发送27 01请求")
        status, resp = service_27_check(node, 0x01, [0x67, 0x01], "返回种子(67 01 XX XX XX XX)")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step5", "发送27 02请求")
        if not service_27_xx_check(node, 0x02, seed_list, [0x67, 0x02], "肯定响应，解锁成功(67 02)", alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step6", "遍历触发NRC22的所有条件并发送2F请求")
        for condition in nrc22_condition_list:
            if len(did_list) > 0:
                did_info = did_list[0]
                did = did_info.get('did', 0)
                control_params = did_info.get('control_params', [0x00])
                sn = control_params[0] if control_params else 0x00
                if not start_nrc22_condition(condition): continue
                try:
                    status, _ = service_2F_check(node, did, sn, [0x7F, 0x2F, 0x22],
                                                 f"否定响应，NRC=22(7F 2F 22) - 条件: {getattr(condition, 'ConditionName', 'unknown')}")
                finally:
                    stop_nrc22_condition(condition)
                if not status: return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG11_TC8_phyRequest_2F_NRCPriority():
    """
    2F服务NRC优先级检查(物理寻址)
    """
    case_name = "2F服务NRC优先级检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        nrc22_condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x2F)
        did_list = UDSTestParams.Services2FDIDSupportList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送一个2F服务请求(在扩展会话下支持)")
        if len(did_list) > 0:
            did_info = did_list[0]
            did = did_info.get('did', 0)
            control_params = did_info.get('control_params', [0x00])
            sn = control_params[0] if control_params else 0x00
            status, _ = service_2F_check(node, did, sn, [0x7F, 0x2F, 0x7F], "否定响应，NRC=7F(7F 2F 7F)")
            if not status: return

        TestLog("INFO", "Step4", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step6", "发送27 01请求")
        status, resp = service_27_check(node, 0x01, [0x67, 0x01], "返回种子(67 01 XX XX XX XX)")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step7", "发送27 02请求")
        if not service_27_xx_check(node, 0x02, seed_list, [0x67, 0x02], "肯定响应，解锁成功(67 02)", alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step8", "触发NRC22条件并发送2F请求(NRC22条件下)")
        condition = nrc22_condition_list[0] if len(nrc22_condition_list) > 0 else None
        if condition is None:
            TestLog("WARNING", case_name, "未配置2F服务可执行的NRC22条件，跳过该测试")
            return
        if not start_nrc22_condition(condition): return
        try:
            if len(did_list) > 0:
                did_info = did_list[0]
                did = did_info.get('did', 0)
                status, _ = service_2F_check(node, did, 0x00, [0x7F, 0x2F, 0x22],
                                             "否定响应，NRC=22(7F 2F 22)")
                if not status: return

            TestLog("INFO", "Step9", "触发NRC22条件并发送2F请求(长度错误，NRC13优先)")
            status, _ = service_2F_check(node, None, None, [0x7F, 0x2F, 0x13],
                                         "否定响应，NRC=13(7F 2F 13) - 长度错误优先", dl=1)
            if not status: return

            TestLog("INFO", "Step10", "触发NRC22条件并发送2F FF FF 00 00 00请求(NRC31优先)")
            status, _ = service_2F_check(node, 0xFFFF, 0x00, [0x7F, 0x2F, 0x31],
                                         "否定响应，NRC=31(7F 2F 31) - 不支持的DID优先")
            if not status: return

            TestLog("INFO", "Step11", "触发NRC22条件并发送2F DIDH DIDL 00 00 00请求(NRC13优先)")
            if len(did_list) > 0:
                did_info = did_list[0]
                did = did_info.get('did', 0)
                status, _ = service_2F_check(node, did, 0x00, [0x7F, 0x2F, 0x13],
                                             "否定响应，NRC=13(7F 2F 13)", dl=6, dl_padding=0x00)
                if not status: return

            TestLog("INFO", "Step12", "触发NRC22条件并发送2F FF FF 00 00 00请求(NRC31优先)")
            status, _ = service_2F_check(node, 0xFFFF, 0x00, [0x7F, 0x2F, 0x31],
                                         "否定响应，NRC=31(7F 2F 31) - 不支持的DID优先")
            if not status: return

            TestLog("INFO", "Step13", "触发NRC22条件并发送需要安全解锁的2F请求(NRC33优先)")
            security_did_list = UDSTestParams.Services2FDIDSecurityRequiredList
            if len(security_did_list) > 0:
                did_info = security_did_list[0]
                did = did_info.get('did', 0)
                control_params = did_info.get('control_params', [0x00])
                sn = control_params[0] if control_params else 0x00
                status, _ = service_2F_check(node, did, sn, [0x7F, 0x2F, 0x33],
                                             "否定响应，NRC=33(7F 2F 33) - 安全访问被拒绝优先")
                if not status: return
            else:
                TestLog("INFO", "", "没有配置需要安全解锁的DID，跳过此步骤")
        finally:
            stop_nrc22_condition(condition)

        TestLog("INFO", "Step14", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG11_TC9_phyRequest_2F_ControlReturn():
    """
    2F服务控制权归还检查(物理寻址)
    """
    case_name = "2F服务控制权归还检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        did_list_03 = UDSTestParams.Services2FControlParam03DIDList

        for did in did_list_03:
            TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step4", "发送27 01请求")
            status, resp = service_27_check(node, 0x01, [0x67, 0x01], "返回种子(67 01 XX XX XX XX)")
            if not status: return

            seed_list = get_seed_from_27_resp(resp)
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

            TestLog("INFO", "Step5", "发送27 02请求")
            if not service_27_xx_check(node, 0x02, seed_list, [0x67, 0x02], "肯定响应，解锁成功(67 02)", alg_type=AlgorithmType.EXTENDED): return

            TestLog("INFO", "Step6", f"发送2F服务控制DID {did:04X}，控制参数=0x03")
            did_h, did_l = (did >> 8) & 0xFF, did & 0xFF
            status, _ = service_2F_check(node, did, 0x03, [0x6F, did_h, did_l],
                                         f"肯定响应(6F {did_h:02X} {did_l:02X} XX)")
            if not status: return

            TestLog("INFO", "Step7", "发送10 01请求进入默认会话(控制权归还ECU)")
            if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

            TestLog("INFO", "Step8", f"22服务读取DID {did:04X}，验证控制权已归还")
            status, _ = service_22_check(node, did, [0x62, did_h, did_l], f"肯定响应，DID数据为0x00(62 {did_h:02X} {did_l:02X} ...)")
            if not status: return

        for did in did_list_03:
            TestLog("INFO", "Step10", "请求进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step12", "发送27 01请求")
            status, resp = service_27_check(node, 0x01, [0x67, 0x01], "返回种子(67 01 XX XX XX XX)")
            if not status: return

            seed_list = get_seed_from_27_resp(resp)
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

            TestLog("INFO", "Step13", "发送27 02请求")
            if not service_27_xx_check(node, 0x02, seed_list, [0x67, 0x02], "肯定响应，解锁成功(67 02)", alg_type=AlgorithmType.EXTENDED): return

            TestLog("INFO", "Step14", f"发送2F服务控制DID {did:04X}，控制参数=0x03")
            did_h, did_l = (did >> 8) & 0xFF, did & 0xFF
            status, _ = service_2F_check(node, did, 0x03, [0x6F, did_h, did_l],
                                         f"肯定响应(6F {did_h:02X} {did_l:02X} XX)")
            if not status: return

            TestLog("INFO", "Step15", "发送11 01请求复位(控制权归还ECU)")
            service_11_check(node, 0x01, [0x51, 0x01], "肯定响应(51 01)")
            time.sleep(2)  # 等待ECU复位

            TestLog("INFO", "Step16", f"22服务读取DID {did:04X}，验证控制权已归还")
            status, _ = service_22_check(node, did, [0x62, did_h, did_l], f"肯定响应，DID数据为0x00(62 {did_h:02X} {did_l:02X} ...)")
            if not status: return

        for did in did_list_03:
            TestLog("INFO", "Step18", "请求进入扩展会话(10 03)")
            if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

            TestLog("INFO", "Step19", "检查当前会话状态(31 01 02 03)")
            if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

            TestLog("INFO", "Step20", "发送27 01请求")
            status, resp = service_27_check(node, 0x01, [0x67, 0x01], "返回种子(67 01 XX XX XX XX)")
            if not status: return

            seed_list = get_seed_from_27_resp(resp)
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

            TestLog("INFO", "Step21", "发送27 02请求")
            if not service_27_xx_check(node, 0x02, seed_list, [0x67, 0x02], "肯定响应，解锁成功(67 02)", alg_type=AlgorithmType.EXTENDED): return

            TestLog("INFO", "Step22", f"发送2F服务控制DID {did:04X}，控制参数=0x03")
            did_h, did_l = (did >> 8) & 0xFF, did & 0xFF
            status, _ = service_2F_check(node, did, 0x03, [0x6F, did_h, did_l],
                                         f"肯定响应(6F {did_h:02X} {did_l:02X} XX)")
            if not status: return

            TestLog("INFO", "Step23", "等待6s(S3 Server超时使控制权归ECU)")
            time.sleep(6)

            TestLog("INFO", "Step24", f"22服务读取DID {did:04X}，验证控制权已归还")
            status, _ = service_22_check(node, did, [0x62, did_h, did_l], f"肯定响应，DID数据为0x00(62 {did_h:02X} {did_l:02X} ...)")
            if not status: return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG12_TC1_phyRequest_31_Positive():
    """
    31服务肯定响应检查(物理寻址)
    """
    case_name = "31服务肯定响应检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        rid_list_extended = UDSTestParams.Services31RIDSupportList_Extended
        rid_list_programming = UDSTestParams.Services31RIDSupportList_Programming

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "发送27 01请求")
        status, resp = service_27_check(node, 0x01, [0x67, 0x01], "返回种子(67 01 XX XX XX XX)")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step5", "发送27 02请求")
        if not service_27_xx_check(node, 0x02, seed_list, [0x67, 0x02], "肯定响应，解锁成功(67 02)", alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step6", "遍历扩展会话下支持的31服务RID")
        for rid_info in rid_list_extended:
            rid = rid_info.get('rid', 0)
            sub_funcs = rid_info.get('sub_funcs', [0x01])
            record = rid_info.get('record', b'')
            rid_h, rid_l = (rid >> 8) & 0xFF, rid & 0xFF
            for sub_func in sub_funcs:
                status, _ = service_31_check(node, sub_func, rid, [0x71, sub_func, rid_h, rid_l],
                                             f"肯定响应(71 {sub_func:02X} {rid_h:02X} {rid_l:02X} XX) - RID: {rid:04X}", record=record)
                if not status: return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step9", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step10", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, [0x50, 0x02], "肯定响应(50 02)"): return

        TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step12", "发送27 11请求")
        status, resp = service_27_check(node, 0x11, [0x67, 0x11], "返回种子(67 11 XX XX XX XX)")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step13", "发送27 12请求")
        if not service_27_xx_check(node, 0x12, seed_list, [0x67, 0x12], "肯定响应，解锁成功(67 12)", alg_type=AlgorithmType.PROGRAMMING): return

        TestLog("INFO", "Step14", "遍历刷新会话下支持的31服务RID")
        for rid_info in rid_list_programming:
            rid = rid_info.get('rid', 0)
            sub_funcs = rid_info.get('sub_funcs', [0x01])
            record = rid_info.get('record', b'')
            rid_h, rid_l = (rid >> 8) & 0xFF, rid & 0xFF
            for sub_func in sub_funcs:
                status, _ = service_31_check(node, sub_func, rid, [0x71, sub_func, rid_h, rid_l],
                                             f"肯定响应(71 {sub_func:02X} {rid_h:02X} {rid_l:02X} XX) - RID: {rid:04X}", record=record)
                if not status: return

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG12_TC2_phyRequest_31_NRC12():
    """
    31服务NRC12检查(物理寻址)
    """
    case_name = "31服务NRC12检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        unsupported_subfunc_list = UDSTestParams.Services31SubFunUnsupportedList
        rid_list = UDSTestParams.Services31RIDSupportList_Extended

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "发送27 01请求")
        status, resp = service_27_check(node, 0x01, [0x67, 0x01], "返回种子(67 01 XX XX XX XX)")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step5", "发送27 02请求")
        if not service_27_xx_check(node, 0x02, seed_list, [0x67, 0x02], "肯定响应，解锁成功(67 02)", alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step6", "遍历不支持的子功能发送31请求")
        for sub_func in unsupported_subfunc_list:
            if len(rid_list) > 0:
                rid_info = rid_list[0]
                rid = rid_info.get('rid', 0)
                status, _ = service_31_check(node, sub_func, rid, [0x7F, 0x31, 0x12],
                                             f"否定响应，NRC=12(7F 31 12) - 子功能: {sub_func:02X}")
                if not status: return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG12_TC3_phyRequest_31_NRC13():
    """
    31服务NRC13检查(物理寻址)
    """
    case_name = "31服务NRC13检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        rid_list = UDSTestParams.Services31RIDSupportList_Extended

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "发送27 01请求")
        status, resp = service_27_check(node, 0x01, [0x67, 0x01], "返回种子(67 01 XX XX XX XX)")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step5", "发送27 02请求")
        if not service_27_xx_check(node, 0x02, seed_list, [0x67, 0x02], "肯定响应，解锁成功(67 02)", alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step6", "发送长度较短的31请求(31 01)")
        status, _ = service_31_check(node, None, 0, [0x7F, 0x31, 0x13],
                                     "否定响应，NRC=13(7F 31 13) - 长度较短", dl=2, dl_padding=0x01)
        if not status: return

        TestLog("INFO", "Step7", "发送长度较短的31请求(31 01 RIDH)")
        status, _ = service_31_check(node, None, 0, [0x7F, 0x31, 0x13],
                                     "否定响应，NRC=13(7F 31 13) - 长度较短", dl=3, dl_padding=0x01)
        if not status: return

        TestLog("INFO", "Step8", "遍历支持的RID发送长度不正确的31请求")
        for rid_info in rid_list:
            rid = rid_info.get('rid', 0)
            status, _ = service_31_check(node, 0x01, rid, [0x7F, 0x31, 0x13],
                                         f"否定响应，NRC=13(7F 31 13) - RID: {rid:04X}", dl=5, dl_padding=0x00)
            if not status: return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG12_TC4_phyRequest_31_NRC24():
    """
    31服务NRC24检查(物理寻址)
    """
    case_name = "31服务NRC24检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        rid_list = UDSTestParams.Services31RIDSupportList_Extended

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "发送27 01请求")
        status, resp = service_27_check(node, 0x01, [0x67, 0x01], "返回种子(67 01 XX XX XX XX)")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step5", "发送27 02请求")
        if not service_27_xx_check(node, 0x02, seed_list, [0x67, 0x02], "肯定响应，解锁成功(67 02)", alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step6", "遍历支持的RID发送31 02请求(未启动例程)")
        for rid_info in rid_list:
            rid = rid_info.get('rid', 0)
            sub_funcs = rid_info.get('sub_funcs', [0x01])
            if 0x02 in sub_funcs:
                status, _ = service_31_check(node, 0x02, rid, [0x7F, 0x31, 0x24],
                                             f"否定响应，NRC=24(7F 31 24) - RID: {rid:04X}")
                if not status: return

        TestLog("INFO", "Step7", "遍历支持的RID发送31 03请求(未启动例程)")
        for rid_info in rid_list:
            rid = rid_info.get('rid', 0)
            sub_funcs = rid_info.get('sub_funcs', [0x01])
            if 0x03 in sub_funcs:
                status, _ = service_31_check(node, 0x03, rid, [0x7F, 0x31, 0x24],
                                             f"否定响应，NRC=24(7F 31 24) - RID: {rid:04X}")
                if not status: return

        TestLog("INFO", "Step8", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG12_TC5_phyRequest_31_NRC31():
    """
    31服务NRC31检查(物理寻址)
    """
    case_name = "31服务NRC31检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        unsupported_rid_list = UDSTestParams.Services31RIDUnsupportedList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "发送27 01请求")
        status, resp = service_27_check(node, 0x01, [0x67, 0x01], "返回种子(67 01 XX XX XX XX)")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step5", "发送27 02请求")
        if not service_27_xx_check(node, 0x02, seed_list, [0x67, 0x02], "肯定响应，解锁成功(67 02)", alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step6", "遍历不支持的RID发送31请求")
        for rid in unsupported_rid_list:
            for sub_func in [0x01, 0x02, 0x03]:
                status, _ = service_31_check(node, sub_func, rid, [0x7F, 0x31, 0x31],
                                             f"否定响应，NRC=31(7F 31 31) - RID: {rid:04X}, 子功能: {sub_func:02X}")
                if not status: return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG12_TC6_phyRequest_31_NRC33():
    """
    31服务NRC33检查(物理寻址)
    """
    case_name = "31服务NRC33检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        security_rid_list = UDSTestParams.Services31RIDSupportList_Extended

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "遍历所有需要安全解锁的31服务RID(未解锁状态)")
        for rid_info in security_rid_list:
            rid = rid_info.get('rid', 0)
            sub_funcs = rid_info.get('sub_funcs', [0x01])
            sub_func = sub_funcs[0] if sub_funcs else 0x01
            status, _ = service_31_check(node, sub_func, rid, [0x7F, 0x31, 0x33],
                                         f"否定响应，NRC=33(7F 31 33) - RID: {rid:04X}")
            if not status: return

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG12_TC7_phyRequest_31_NRC7F():
    """
    31服务NRC7F检查(物理寻址)
    """
    case_name = "31服务NRC7F检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        rid_list_extended = UDSTestParams.Services31RIDSupportList_Extended

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送一个31服务请求(在扩展会话下支持)")
        if len(rid_list_extended) > 0:
            rid_info = rid_list_extended[0]
            rid = rid_info.get('rid', 0)
            sub_funcs = rid_info.get('sub_funcs', [0x01])
            sub_func = sub_funcs[0] if sub_funcs else 0x01
            status, _ = service_31_check(node, sub_func, rid, [0x7F, 0x31, 0x7F],
                                         "否定响应，NRC=7F(7F 31 7F)")
            if not status: return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG12_TC8_phyRequest_31_NRC22():
    """
    31服务NRC22检查(物理寻址)
    """
    case_name = "31服务NRC22检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        nrc22_condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x31)
        rid_list = UDSTestParams.Services31RIDSupportList_Extended

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "发送27 01请求")
        status, resp = service_27_check(node, 0x01, [0x67, 0x01], "返回种子(67 01 XX XX XX XX)")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step5", "发送27 02请求")
        if not service_27_xx_check(node, 0x02, seed_list, [0x67, 0x02], "肯定响应，解锁成功(67 02)", alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step6", "遍历触发NRC22的所有条件并发送31请求")
        for condition in nrc22_condition_list:
            if len(rid_list) > 0:
                rid_info = rid_list[0]
                rid = rid_info.get('rid', 0)
                sub_funcs = rid_info.get('sub_funcs', [0x01])
                sub_func = sub_funcs[0] if sub_funcs else 0x01
                if not start_nrc22_condition(condition): continue
                try:
                    status, _ = service_31_check(node, sub_func, rid, [0x7F, 0x31, 0x22],
                                                 f"否定响应，NRC=22(7F 31 22) - 条件: {getattr(condition, 'ConditionName', 'unknown')}")
                finally:
                    stop_nrc22_condition(condition)
                if not status: return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG12_TC9_phyRequest_31_NRCPriority():
    """
    31服务NRC优先级检查(物理寻址)
    """
    case_name = "31服务NRC优先级检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        nrc22_condition_list = UDSTestParams.get_nrc22_conditions_for_service(0x31)
        rid_list = UDSTestParams.Services31RIDSupportList_Extended
        unsupported_rid_list = UDSTestParams.Services31RIDUnsupportedList

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "发送一个31服务请求(在扩展会话下支持)")
        if len(rid_list) > 0:
            rid_info = rid_list[0]
            rid = rid_info.get('rid', 0)
            sub_funcs = rid_info.get('sub_funcs', [0x01])
            sub_func = sub_funcs[0] if sub_funcs else 0x01
            status, _ = service_31_check(node, sub_func, rid, [0x7F, 0x31, 0x7F],
                                         "否定响应，NRC=7F(7F 31 7F)")
            if not status: return

        TestLog("INFO", "Step4", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step6", "发送27 01请求")
        status, resp = service_27_check(node, 0x01, [0x67, 0x01], "返回种子(67 01 XX XX XX XX)")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step7", "发送27 02请求")
        if not service_27_xx_check(node, 0x02, seed_list, [0x67, 0x02], "肯定响应，解锁成功(67 02)", alg_type=AlgorithmType.EXTENDED): return

        TestLog("INFO", "Step8", "触发NRC22条件并发送31请求(NRC22条件下)")
        condition = nrc22_condition_list[0] if len(nrc22_condition_list) > 0 else None
        if condition is None:
            TestLog("WARNING", case_name, "未配置31服务可执行的NRC22条件，跳过该测试")
            return
        if not start_nrc22_condition(condition): return
        try:
            if len(rid_list) > 0:
                rid_info = rid_list[0]
                rid = rid_info.get('rid', 0)
                status, _ = service_31_check(node, 0x01, rid, [0x7F, 0x31, 0x22],
                                             "否定响应，NRC=22(7F 31 22)")
                if not status: return

            TestLog("INFO", "Step9", "触发NRC22条件并发送31请求(不支持的子功能，NRC12优先)")
            if len(rid_list) > 0:
                rid_info = rid_list[0]
                rid = rid_info.get('rid', 0)
                status, _ = service_31_check(node, 0x00, rid, [0x7F, 0x31, 0x12],
                                             "否定响应，NRC=12(7F 31 12) - 不支持的子功能优先")
                if not status: return

            TestLog("INFO", "Step10", "触发NRC22条件并发送31请求(长度错误，NRC13优先)")
            status, _ = service_31_check(node, None, 0, [0x7F, 0x31, 0x13],
                                         "否定响应，NRC=13(7F 31 13) - 长度错误优先", dl=2, dl_padding=0x01)
            if not status: return

            TestLog("INFO", "Step11", "触发NRC22条件并发送31请求(不支持的RID，NRC31优先)")
            if len(unsupported_rid_list) > 0:
                rid = unsupported_rid_list[0]
                status, _ = service_31_check(node, 0x01, rid, [0x7F, 0x31, 0x31],
                                             "否定响应，NRC=31(7F 31 31) - 不支持的RID优先")
                if not status: return

            TestLog("INFO", "Step12", "触发NRC22条件并发送31 02请求(未启动例程，NRC24优先)")
            if len(rid_list) > 0:
                rid_info = rid_list[0]
                rid = rid_info.get('rid', 0)
                sub_funcs = rid_info.get('sub_funcs', [0x01])
                if 0x02 in sub_funcs:
                    status, _ = service_31_check(node, 0x02, rid, [0x7F, 0x31, 0x24],
                                                 "否定响应，NRC=24(7F 31 24) - 未启动例程优先")
                    if not status: return
        finally:
            stop_nrc22_condition(condition)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG14_TC1_P2_ServerTimeTest():
    """
    P2 Server时间测试
    """
    case_name = "P2 Server时间测试"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    # 保存运行过程中的变量
    rt = RunTimeInfo()

    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rP2ServerTime = 50  # ms
        rP2EnhanceServerTime = 5000  # ms

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        time.sleep(0.005)
        rt.clear()

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return
        time.sleep(1)
        if not check_msg_time_diff_ms(rt, [0x10, 0x01], [0x50, 0x01], rP2ServerTime): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return
        time.sleep(1)
        if not check_msg_time_diff_ms(rt, [0x31, 0x01, 0x02, 0x03], [0x7F, 0x31, 0x7F], rP2ServerTime): return

        # TestLog("INFO", "Step3", "请求清除所有DTC(14 FF FF FF)")
        # status, _ = service_14_check(node, 0xFFFFFF, [0x54], f"肯定响应(54)")
        # if not status: return
        # if not check_msg_time_diff_ms(rt, [0x14, 0xFF, 0xFF, 0xFF], [0x54], rP2ServerTime): return

        TestLog("INFO", "Step4", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return
        time.sleep(1)
        if not check_msg_time_diff_ms(rt, [0x10, 0x03], [0x50, 0x03], rP2ServerTime): return

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return
        time.sleep(1)
        if not check_msg_time_diff_ms(rt, [0x31, 0x01, 0x02, 0x03], [0x71, 0x01, 0x02, 0x03], rP2ServerTime): return

        # TestLog("INFO", "Step6", "请求清除所有DTC(14 FF FF FF)")
        # status, _ = service_14_check(node, 0xFFFFFF, [0x54], f"肯定响应(54)")
        # if not status: return
        # if not check_msg_time_diff_ms(rt, [0x14, 0xFF, 0xFF, 0xFF], [0x54], rP2ServerTime): return

        TestLog("INFO", "Step7", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return
        time.sleep(1)
        if not check_msg_time_diff_ms(rt, [0x27, LEVEL_EXT], [0x67, LEVEL_EXT], rP2ServerTime): return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step8", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x67, LEVEL_EXT_2], f"肯定响应(67 {LEVEL_EXT_2_STR})", alg_type=AlgorithmType.EXTENDED): return
        time.sleep(1)
        if not check_msg_time_diff_ms(rt, [0x27, LEVEL_EXT_2], [0x67, LEVEL_EXT_2], rP2ServerTime): return

        TestLog("INFO", "Step9", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return
        time.sleep(1)
        if not check_msg_time_diff_ms(rt, [0x10, 0x02], [0x50, 0x02], rP2ServerTime): return

        TestLog("INFO", "Step10", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return
        time.sleep(1)
        if not check_msg_time_diff_ms(rt, [0x31, 0x01, 0x02, 0x03], [0x7F, 0x31, 0x31], rP2ServerTime): return


        TestLog("INFO", "Step11", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return
        time.sleep(1)
        if not check_msg_time_diff_ms(rt, [0x27, LEVEL_PRO_11], [0x67, LEVEL_PRO_11], rP2ServerTime): return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step12", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x67, LEVEL_PRO_12], f"肯定响应(67 {LEVEL_PRO_12_STR})", alg_type=AlgorithmType.EXTENDED): return
        time.sleep(1)
        if not check_msg_time_diff_ms(rt, [0x27, LEVEL_PRO_12], [0x67, LEVEL_PRO_12], rP2ServerTime): return

        TestLog("INFO", "Step13", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return
        time.sleep(1)
        if not check_msg_time_diff_ms(rt, [0x10, 0x01], [0x50, 0x01], rP2ServerTime): return

        # 停止检测响应报文的线程
        check_msg_thread_stop(rt)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        # 停止检测响应报文的线程
        check_msg_thread_stop(rt)


def test_TG14_TC2_P2E_ServerTimeTest():
    """
    P2* Server时间测试
    """
    case_name = "P2* Server时间测试"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    # 保存运行过程中的变量
    rt = RunTimeInfo()

    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rP2ServerTime = 50  # ms
        rP2EnhanceServerTime = 5000  # ms

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        time.sleep(0.005)
        rt.clear()

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return
        time.sleep(1)
        if not check_msg_time_diff_ms_with_78_flag(rt, [0x10, 0x01], [0x50, 0x01], rP2ServerTime, rP2EnhanceServerTime): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return
        time.sleep(1)
        if not check_msg_time_diff_ms_with_78_flag(rt, [0x31, 0x01, 0x02, 0x03], [0x7F, 0x31, 0x7F], rP2ServerTime, rP2EnhanceServerTime): return

        TestLog("INFO", "Step3", "请求清除所有DTC(14 FF FF FF)")
        status, _ = service_14_check(node, 0xFFFFFF, [0x54], f"肯定响应(54)")
        if not status: return
        if not check_msg_time_diff_ms_with_78_flag(rt, [0x14, 0xFF, 0xFF, 0xFF], [0x54], rP2ServerTime, rP2EnhanceServerTime): return

        TestLog("INFO", "Step4", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return
        time.sleep(1)
        if not check_msg_time_diff_ms_with_78_flag(rt, [0x10, 0x03], [0x50, 0x03], rP2ServerTime, rP2EnhanceServerTime): return

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return
        time.sleep(1)
        if not check_msg_time_diff_ms_with_78_flag(rt, [0x31, 0x01, 0x02, 0x03], [0x71, 0x01, 0x02, 0x03], rP2ServerTime, rP2EnhanceServerTime): return

        TestLog("INFO", "Step6", "请求清除所有DTC(14 FF FF FF)")
        status, _ = service_14_check(node, 0xFFFFFF, [0x54], f"肯定响应(54)")
        if not status: return
        if not check_msg_time_diff_ms_with_78_flag(rt, [0x14, 0xFF, 0xFF, 0xFF], [0x54], rP2ServerTime, rP2EnhanceServerTime): return

        TestLog("INFO", "Step7", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_STR})")
        status, resp = service_27_check(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT_STR})")
        if not status: return
        time.sleep(1)
        if not check_msg_time_diff_ms_with_78_flag(rt, [0x27, LEVEL_EXT], [0x67, LEVEL_EXT], rP2ServerTime, rP2EnhanceServerTime): return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step8", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT_2_STR})")
        if not service_27_xx_check(node, LEVEL_EXT_2, seed_list, [0x67, LEVEL_EXT_2], f"肯定响应(67 {LEVEL_EXT_2_STR})", alg_type=AlgorithmType.EXTENDED): return
        time.sleep(1)
        if not check_msg_time_diff_ms_with_78_flag(rt, [0x27, LEVEL_EXT_2], [0x67, LEVEL_EXT_2], rP2ServerTime, rP2EnhanceServerTime): return

        TestLog("INFO", "Step9", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return
        time.sleep(1)
        if not check_msg_time_diff_ms_with_78_flag(rt, [0x10, 0x02], [0x50, 0x02], rP2ServerTime, rP2EnhanceServerTime): return

        TestLog("INFO", "Step10", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return
        time.sleep(1)
        if not check_msg_time_diff_ms_with_78_flag(rt, [0x31, 0x01, 0x02, 0x03], [0x7F, 0x31, 0x31], rP2ServerTime, rP2EnhanceServerTime): return

        TestLog("INFO", "Step11", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return
        time.sleep(1)
        if not check_msg_time_diff_ms_with_78_flag(rt, [0x27, LEVEL_PRO_11], [0x67, LEVEL_PRO_11], rP2ServerTime, rP2EnhanceServerTime): return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step12", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_12_STR})")
        if not service_27_xx_check(node, LEVEL_PRO_12, seed_list, [0x67, LEVEL_PRO_12], f"肯定响应(67 {LEVEL_PRO_12_STR})", alg_type=AlgorithmType.PROGRAMMING): return
        time.sleep(1)
        if not check_msg_time_diff_ms_with_78_flag(rt, [0x27, LEVEL_PRO_12], [0x67, LEVEL_PRO_12], rP2ServerTime, rP2EnhanceServerTime): return

        TestLog("INFO", "Step13", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return
        time.sleep(1)
        if not check_msg_time_diff_ms_with_78_flag(rt, [0x10, 0x01], [0x50, 0x01], rP2ServerTime, rP2EnhanceServerTime): return

        # 停止检测响应报文的线程
        check_msg_thread_stop(rt)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        # 停止检测响应报文的线程
        check_msg_thread_stop(rt)


def test_TG14_TC3_SessionSwitchingTimeTest():
    """
    会话切换时间测试
    """
    case_name = "会话切换时间测试"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step4", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "等待4.5s")
        sl_time().sleep(int(4.5*1000))

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step6", "等待5.5s")
        sl_time().sleep(int(5.5*1000))

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step8", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step9", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step10", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step11", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step13", "等待4.5s")
        sl_time().sleep(int(4.5*1000))

        TestLog("INFO", "Step14", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step15", "等待5.5s")
        sl_time().sleep(int(5.5*1000))

        TestLog("INFO", "Step16", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG14_TC4_APPJumpToBootTimeTest():
    """
    APP跳转到Boot时间测试
    """
    case_name = "APP跳转到Boot时间测试"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rSessionTime_s = P.DiagServiceInfo.SessionTime / 1000  # ms -> s

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step4", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step5", f"等待T_wait={rSessionTime_s}s时间")
        sl_time().sleep(int(rSessionTime_s * 1000))

        TestLog("INFO", "Step6", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11_STR})")
        status, resp = service_27_check(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11], f"肯定响应(67 {LEVEL_PRO_11_STR})")
        if not status: return

        seed_list = get_seed_from_27_resp(resp)
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG14_TC5_BootJumpToAPPTimeTest():
    """
    Boot转到APP时间测试
    """
    case_name = "Boot转到APP时间测试"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rSessionTime_s = P.DiagServiceInfo.SessionTime / 1000  # ms -> s

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step4", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step5", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step6", f"等待T_wait={rSessionTime_s}s时间")
        sl_time().sleep(int(rSessionTime_s * 1000))

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG14_TC6_EnterBootModeToStopNetworkCommunicationTest():
    """
    进入Boot停止网络通信测试
    """
    case_name = "进入Boot停止网络通信测试"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rSessionTime_s = P.DiagServiceInfo.SessionTime / 1000  # ms -> s

        normal_app_id_list = UDSTestParams.AppFrameIDList  # 正常应用报文 0x01
        nm_id_list = UDSTestParams.NMFrameIDList  # 网络管理报文 0x02

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step4", "进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step4", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step5", f"等待T_wait={rSessionTime_s}s时间")
        ctx.can.clear_messages()
        sl_time().sleep(int(rSessionTime_s * 1000))

        TestLog("INFO", "Step6", "检查应用报文和网络管理报文是否正常发送")
        app_count = get_app_msg_count(normal_app_id_list)
        nm_count = get_nm_msg_count(nm_id_list)
        if app_count == 0 and nm_count == 0:
            TestLog("PASS", "", f"期望: 应用报文和网络管理报文均未发送; 实际: 应用报文发送次数={app_count}, 网络管理报文发送次数={nm_count}")
        else:
            TestLog("FAIL", "", f"期望: 应用报文和网络管理报文均未发送; 实际: 应用报文发送次数={app_count}, 网络管理报文发送次数={nm_count}")
            return

        TestLog("INFO", "Step7", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return

        TestLog("INFO", "Step8", f"等待T_wait={rSessionTime_s}s时间")
        ctx.can.clear_messages()
        sl_time().sleep(int(rSessionTime_s * 1000))
        
        TestLog("INFO", "Step9", "检查应用报文和网络管理报文是否正常发送")
        app_count = get_app_msg_count(normal_app_id_list)
        nm_count = get_nm_msg_count(nm_id_list)
        if app_count == 0 or nm_count == 0:
            TestLog("FAIL", "", f"期望: 应用报文和网络管理报文均恢复发送; 实际: 应用报文发送次数={app_count}, 网络管理报文发送次数={nm_count}")
            return
        else:
            TestLog("PASS", "", f"期望: 应用报文和网络管理报文均恢复发送; 实际: 应用报文发送次数={app_count}, 网络管理报文发送次数={nm_count}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
        
        
def test_TG13_TC1_phyRequest_NRC11_ServiceNotSupported():
    """
    不支持服务NRC11检查(物理寻址)
    """
    case_name = "不支持服务NRC11检查(物理寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        unsupported_services = UDSTestParams.ServicesUnsupportedList

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "遍历所有不支持的服务(物理寻址)，期望返回NRC=11")
        for sn in unsupported_services:
            TestLog("INFO", "", f"发送不支持的服务请求: SN={hex(sn)}")
            if not service_unsupported_check(node, sn, expect_data=[0x7F, sn, 0x11],
                                             expect_str=f"否定响应NRC=11(7F {hex(sn)} 11)"): return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step6", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "遍历所有不支持的服务(物理寻址)，期望返回NRC=11")
        for sn in unsupported_services:
            TestLog("INFO", "", f"发送不支持的服务请求: SN={hex(sn)}")
            if not service_unsupported_check(node, sn, expect_data=[0x7F, sn, 0x11],
                                             expect_str=f"否定响应NRC=11(7F {hex(sn)} 11)"): return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step10", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        TestLog("INFO", "Step11", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return

        TestLog("INFO", "Step12", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        TestLog("INFO", "Step13", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step14", "遍历所有不支持的服务(物理寻址)，期望返回NRC=11")
        for sn in unsupported_services:
            TestLog("INFO", "", f"发送不支持的服务请求: SN={hex(sn)}")
            if not service_unsupported_check(node, sn, expect_data=[0x7F, sn, 0x11],
                                             expect_str=f"否定响应NRC=11(7F {hex(sn)} 11)"): return

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG13_TC2_funRequest_NRC11_ServiceNotSupported():
    """
    不支持服务NRC11检查(功能寻址)
    """
    case_name = "不支持服务NRC11检查(功能寻址)"
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    node = get_can_node(sa, ta, fa, is_canfd=True)

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        unsupported_services = UDSTestParams.ServicesUnsupportedList

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)",
                                func_req=True): return

        TestLog("INFO", "Step2", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step3", "遍历所有不支持的服务(功能寻址)，期望无响应")
        for sn in unsupported_services:
            TestLog("INFO", "", f"发送不支持的服务请求(功能寻址): SN={hex(sn)}")
            if not service_unsupported_check(node, sn, expect_data=None,
                                             expect_str="无响应", func_req=True, timeout=0.1): return

        TestLog("INFO", "Step4", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x7F],
                                     expect_str="位于默认会话中(7F 31 7F)"): return

        TestLog("INFO", "Step5", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)",
                                func_req=True): return

        TestLog("INFO", "Step6", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)",
                                func_req=True): return

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step8", "遍历所有不支持的服务(功能寻址)，期望无响应")
        for sn in unsupported_services:
            TestLog("INFO", "", f"发送不支持的服务请求(功能寻址): SN={hex(sn)}")
            if not service_unsupported_check(node, sn, expect_data=None,
                                             expect_str="无响应", func_req=True): return

        TestLog("INFO", "Step9", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                     expect_str="位于扩展会话中(71 01 02 03 00)"): return

        TestLog("INFO", "Step10", "请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)",
                                func_req=True): return

        TestLog("INFO", "Step11", "请求进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)",
                                func_req=True): return

        TestLog("INFO", "Step12", "请求进入刷新会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)",
                                func_req=True): return

        TestLog("INFO", "Step13", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step14", "遍历所有不支持的服务(功能寻址)，期望无响应")
        for sn in unsupported_services:
            TestLog("INFO", "", f"发送不支持的服务请求(功能寻址): SN={hex(sn)}")
            if not service_unsupported_check(node, sn, expect_data=None,
                                             expect_str="无响应", func_req=True, timeout=0.1): return

        TestLog("INFO", "Step15", "检查当前会话状态(31 01 02 03)")
        if not check_current_session(node, [0x7F, 0x31, 0x31],
                                     expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def get_all_test_cases():
    """获取uds测试用例"""
    current_module = inspect.getmodule(inspect.currentframe())

    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj

    return test_cases
