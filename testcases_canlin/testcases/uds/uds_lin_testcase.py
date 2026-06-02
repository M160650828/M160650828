import inspect
import sys
import os
import time
import traceback
from env.config import *

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uvtest.testlog import TestLog
from common.control import TestStart, TestEnd
from common.params import P
from .lintp_module import lin_mormal_tp_init, lin_tp_end, lin_can_init, lin_can_deinit
from .uds_lin_utils import (UDSTestParams, get_lin_node, lin_node_power_setup_and_communication_check, \
    test_phyRequest_10_Positive, \
    test_phyRequest_10_NRC12, test_phyRequest_10_NRC13, test_phyRequest_10_NRC22, \
    test_phyRequest_10_NRC7E, test_phyRequest_10_PowerOnOff, test_phyRequest_10_HardReset, \
    test_phyRequest_10_NRC_Priority, test_phyRequest_11_Positive, test_phyRequest_11_NRC12, \
    test_phyRequest_11_NRC13, test_phyRequest_11_NRC22, test_phyRequest_11_NRC7F, \
    test_phyRequest_11_NRC_Priority, test_phyRequest_28_Positive, test_phyRequest_28_ExitFunction, \
    test_phyRequest_28_NRC13, test_phyRequest_28_NRC7F, test_phyRequest_28_NRC22, \
    test_phyRequest_28_Function_Check, test_phyRequest_28_NRC31, test_phyRequest_28_NRC_Priority, \
    test_phyRequest_85_Positive, test_phyRequest_28_NRC12, test_phyRequest_85_NRC12, \
    test_phyRequest_85_FunctionCheck, test_phyRequest_85_NRC13, test_phyRequest_85_NRC7F, \
    test_phyRequest_85_NRC22, test_phyRequest_85_NRCPriority, test_phyRequest_14_Positive, \
    test_phyRequest_14_NRC13, test_phyRequest_14_NRC31, test_phyRequest_14_NRC22, \
    test_phyRequest_14_NRC_Priority, test_phyRequest_19_Positive, test_phyRequest_19_NRC12, \
    test_phyRequest_19_NRC13, test_phyRequest_19_NRC31, test_phyRequest_19_NRCPriorityCheck, \
    test_phyRequest_2F_Positive, test_Session_SwitchingTimeTest, test_AppToBoot_TimeTest, \
    test_BootToApp_TimeTest, test_EnterBoot_StopCommunicationTest, test_P2Server_TimingTest, \
    test_phyRequest_27_Positive, test_phyRequest_27_AlgorithmCheck, \
    test_phyRequest_27_SwitchSessionDelay_LockCheck, test_phyRequest_27_NRC12, test_phyRequest_27_NRC13, \
    test_phyRequest_27_NRC24, test_phyRequest_27_NRC7E_7F, test_phyRequest_27_NRC22, \
    test_phyRequest_27_SessionChangeCheck, test_phyRequest_27_ResetCheck, test_phyRequest_27_PowerOnOff, \
    test_phyRequest_27_ResetDelay_LockCheck, test_phyRequest_27_PowerOnDelay_LockCheck, \
    test_phyRequest_27_SwitchSessionDelay_IndependenceCheck,test_phyRequest_27_NRCPriorityCheck, \
    test_phyRequest_3E_Positive, test_phyRequest_3E_NRC12, test_phyRequest_3E_NRC13, \
    test_phyRequest_3E_NRCPriority, test_phyRequest_22_Positive, test_phyRequest_22_MultiRead, \
    test_phyRequest_22_NRC31, test_phyRequest_22_NRC13, test_phyRequest_22_NRC33, test_phyRequest_22_NRC22, \
    test_phyRequest_22_NRCPriority, test_phyRequest_2E_Positive, test_phyRequest_2E_NRC13, test_phyRequest_2E_NRC31, \
    test_phyRequest_2E_NRC33, test_phyRequest_2E_NRC7F, test_phyRequest_2E_NRC22, test_phyRequest_2E_NRCPriorityCheck, \
    test_phyRequest_2F_ControlParam, test_phyRequest_2F_NRC7F, test_phyRequest_2F_NRC13, test_phyRequest_2F_NRC31, \
    test_phyRequest_2F_NRC33, test_phyRequest_2F_NRC22, test_phyRequest_2F_NRCPriority, \
    test_phyRequest_2F_ControlReturn, \
    test_phyRequest_31_Positive, test_phyRequest_31_NRC12, test_phyRequest_31_NRC13, test_phyRequest_31_NRC24, \
    test_phyRequest_31_NRC31, test_phyRequest_31_NRC33, test_phyRequest_31_NRC7F, test_phyRequest_31_NRC22, \
    test_phyRequest_31_NRCPriority,test_phyRequest_NRC11)

from uvtest.framework import TestFixture


class UDSLINTestFixture(TestFixture):
    def group_setup(self, context=None):
        lin_can_init()

    def group_teardown(self, context=None):
        lin_can_deinit()

    def case_setup(self, context=None):
        if context:
            TestStart(context["test_name"])

    def case_teardown(self, context=None):
        TestEnd("")
        TestLog("INFO", "测试结束", "执行测试结束和去初始化")


def test_TG1_TC1_phyRequest_10_Positive():
    """[TG1_TC1] 10服务肯定响应与功能检查(物理寻址)"""
    case_name = "[TG1_TC1] 10服务肯定响应与功能检查(物理寻址)"

    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源和通信检查
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
        test_phyRequest_10_Positive(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC2_phyRequest_10_NRC12():
    """[TG1_TC2] 10服务NRC12检查(物理寻址)"""
    case_name = "[TG1_TC2] 10服务NRC12检查(物理寻址)"

    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_10_NRC12(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC3_phyRequest_10_NRC13():
    """[TG1_TC3] 10服务NRC13检查(物理寻址)"""
    case_name = "[TG1_TC3] 10服务NRC13检查(物理寻址)"

    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_10_NRC13(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC4_phyRequest_10_NRC22():
    """[TG1_TC4] 10服务NRC22检查(物理寻址)"""
    case_name = "[TG1_TC4] 10服务NRC22检查(物理寻址)"

    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_10_NRC22(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC5_phyRequest_10_NRC7E():
    """[TG1_TC5] 10服务NRC7E检查(物理寻址)"""
    case_name = "[TG1_TC5] 10服务NRC7E检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_10_NRC7E(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC6_phyRequest_10_PowerOnOff():
    """[TG1_TC6] 10服务重新上电检查(物理寻址)"""
    case_name = "[TG1_TC6] 10服务重新上电检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_10_PowerOnOff(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC7_phyRequest_10_HardReset():
    """[TG1_TC7] 10服务硬复位检查(物理寻址)"""
    case_name = "[TG1_TC7] 10服务硬复位检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_10_HardReset(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC8_phyRequest_10_NRCPriorityCheck():
    """[TG1_TC8] 10服务NRC优先级检查(物理寻址)"""
    case_name = "[TG1_TC8] 10服务NRC优先级检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return
        test_phyRequest_10_NRC_Priority(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC1_phyRequest_11_Positive():
    """[TG2_TC1] 11服务肯定响应与功能检查(物理寻址)"""
    case_name = "[TG2_TC1] 11服务肯定响应与功能检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_11_Positive(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC2_phyRequest_11_NRC12():
    """[TG2_TC2] 11服务NRC12检查(物理寻址)"""
    case_name = "[TG2_TC2] 11服务NRC12检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_11_NRC12(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC3_phyRequest_11_NRC13():
    """[TG2_TC3] 11服务NRC13检查(物理寻址)"""
    case_name = "[TG2_TC3] 11服务NRC13检查(物理寻址)"

    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_11_NRC13(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC4_phyRequest_11_NRC22():
    """[TG2_TC4] 11服务NRC22检查(物理寻址)"""
    case_name = "[TG2_TC4] 11服务NRC22检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_11_NRC22(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC5_phyRequest_11_NRC7F():
    """[TG2_TC5] 11服务NRC7F检查(物理寻址)"""
    case_name = "[TG2_TC5] 11服务NRC7F检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_11_NRC7F(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC6_phyRequest_11_NRCPriorityCheck():
    """[TG2_TC6] 11服务NRC优先级检查(物理寻址)"""
    case_name = "[TG2_TC6] 11服务NRC优先级检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_11_NRC_Priority(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC1_phyRequest_27_Positive():
    """[TG3_TC1] 27服务肯定响应与功能检查(物理寻址)"""
    case_name = "[TG3_TC1] 27服务肯定响应与功能检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_27_Positive(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC2_phyRequest_27_AlgorithmCheck():
    """[TG3_TC2] 27服务算法检查(物理寻址)"""
    case_name = "[TG3_TC2] 27服务算法检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_27_AlgorithmCheck(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC3_phyRequest_27_SwitchSessionDelay_LockCheck():
    """[TG3_TC3] 27服务切换会话延时机制与锁定检查(物理寻址)"""
    case_name = "[TG3_TC3] 27服务切换会话延时机制与锁定检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_27_SwitchSessionDelay_LockCheck(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC4_phyRequest_27_NRC12():
    """[TG3_TC4] 27服务NRC12检查(物理寻址)"""
    case_name = "[TG3_TC4] 27服务NRC12检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_27_NRC12(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC5_phyRequest_27_NRC13():
    """[TG3_TC5] 27服务NRC12检查(物理寻址)"""
    case_name = "[TG3_TC5] 27服务NRC12检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_27_NRC13(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC6_phyRequest_27_NRC24():
    """[TG3_TC6] 27服务NRC24检查(物理寻址)"""
    case_name = "[TG3_TC6] 27服务NRC24检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_27_NRC24(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC7_phyRequest_27_NRC7E_7F():
    """[TG3_TC7] 27服务NRC7E、NRC7F检查(物理寻址)"""
    case_name = "[TG3_TC7] 27服务NRC7E、NRC7F检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_27_NRC7E_7F(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC8_phyRequest_27_NRC22():
    """[TG3_TC8] 27服务NRC22检查(物理寻址)"""
    case_name = "[TG3_TC8] 27服务NRC22检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_27_NRC22(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC9_phyRequest_27_SessionChangeCheck():
    """[TG3_TC9] 27服务会话切换检查(物理寻址)"""
    case_name = "[TG3_TC9] 27服务会话切换检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_27_SessionChangeCheck(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC10_phyRequest_27_ResetCheck():
    """[TG3_TC10] 27服务复位检查(物理寻址)"""
    case_name = "[TG3_TC10] 27服务复位检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_27_ResetCheck(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC11_phyRequest_27_PowerOnOff():
    """[TG3_TC11] 27服务重新上电检查(物理寻址)"""
    case_name = "[TG3_TC11] 27服务重新上电检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_27_PowerOnOff(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC12_phyRequest_27_ResetDelay_LockCheck():
    """[TG3_TC12] 27复位延时机制与锁定检查(物理寻址)"""
    case_name = "[TG3_TC12] 27复位延时机制与锁定检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_27_ResetDelay_LockCheck(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC13_phyRequest_27_PowerOnDelay_LockCheck():
    """[TG3_TC13] 27服务重新上电延时机制和锁定检查(物理寻址)"""
    case_name = "[TG3_TC13] 27服务重新上电延时机制和锁定检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_27_PowerOnDelay_LockCheck(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC14_phyRequest_27_SwitchSessionDelay_IndependenceCheck():
    """[TG3_TC14] 27服务切换会话延时机制独立性检查(物理寻址)"""
    case_name = "[TG3_TC14] 27服务切换会话延时机制独立性检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_27_SwitchSessionDelay_IndependenceCheck(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC15_phyRequest_27_NRCPriorityCheck():
    """[TG3_TC15] 27服务NRC优先级检查(物理寻址)"""
    case_name = "[TG3_TC15] 27服务NRC优先级检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_27_NRCPriorityCheck(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC1_phyRequest_28_Positive():
    """[TG4_TC1] 28服务肯定响应检查(物理寻址)"""
    case_name = "[TG4_TC1] 28服务肯定响应检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_28_Positive(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC2_phyRequest_28_ExitFunction():
    """[TG4_TC2] 28服务退出功能检查(物理寻址)"""
    case_name = "[TG4_TC2] 28服务退出功能检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_28_ExitFunction(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC3_phyRequest_28_NRC12():
    """[TG4_TC3] 28服务NRC12检查(物理寻址)"""
    case_name = "[TG4_TC3] 28服务NRC12检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_28_NRC12(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC4_phyRequest_28_NRC13():
    """[TG4_TC4] 28服务NRC13检查(物理寻址)"""
    case_name = "[TG4_TC4] 28服务NRC13检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_28_NRC13(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC5_phyRequest_28_NRC7F():
    """[TG4_TC5] 28服务NRC7F检查(物理寻址)"""
    case_name = "[TG4_TC5] 28服务NRC7F检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_28_NRC7F(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC6_phyRequest_28_NRC22():
    """[TG4_TC6] 28服务NRC22检查(物理寻址)"""
    case_name = "[TG4_TC6] 28服务NRC22检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_28_NRC22(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC7_phyRequest_28_Function_Check():
    """[TG4_TC7] 28服务功能检查(物理寻址)"""
    case_name = "[TG4_TC7] 28服务功能检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_28_Function_Check(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC8_phyRequest_28_NRC31():
    """[TG4_TC8] 28服务NRC31检查(物理寻址)"""
    case_name = "[TG4_TC8] 28服务NRC31检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_28_NRC31(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC9_phyRequest_28_NRCPriorityCheck():
    """[TG4_TC9] 28服务NRC优先级检查(物理寻址)"""
    case_name = "[TG4_TC9] 28服务NRC优先级检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_28_NRC_Priority(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG5_TC1_phyRequest_3E_Positive():
    """[TG5_TC1] 3E服务肯定响应与功能检查(物理寻址)"""
    case_name = "[TG5_TC1] 3E服务肯定响应与功能检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_3E_Positive(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG5_TC2_phyRequest_3E_NRC12():
    """[TG5_TC2] 3E服务NRC12检查(物理寻址)"""
    case_name = "[TG5_TC2] 3E服务NRC12检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_3E_NRC12(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG5_TC3_phyRequest_3E_NRC13():
    """[TG5_TC3] 3E服务NRC13检查(物理寻址)"""
    case_name = "[TG5_TC3] 3E服务NRC13检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_3E_NRC13(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG5_TC4_phyRequest_3E_NRCPriority():
    """[TG5_TC4] 3E服务NRC优先级检查(物理寻址)"""
    case_name = "[TG5_TC4] 3E服务NRC优先级检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_3E_NRCPriority(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG6_TC1_phyRequest_85_Positive():
    """[TG6_TC1] 85服务肯定响应检查(物理寻址)"""
    case_name = "[TG6_TC1] 85服务肯定响应检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_85_Positive(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG6_TC2_phyRequest_85_FunctionCheck():
    """[TG6_TC2] 85服务功能检查(物理寻址)"""
    case_name = "[TG6_TC2] 85服务功能检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_85_FunctionCheck(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG6_TC3_phyRequest_85_NRC12():
    """[TG6_TC3] 85服务NRC12检查(物理寻址)"""
    case_name = "[TG6_TC3] 85服务NRC12检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_85_NRC12(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG6_TC4_phyRequest_85_NRC13():
    """[TG6_TC4] 85服务NRC13检查(物理寻址)"""
    case_name = "[TG6_TC4] 85服务NRC13检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_85_NRC13(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG6_TC5_phyRequest_85_NRC7F():
    """[TG6_TC5] 85服务NRC7F检查(物理寻址)"""
    case_name = "[TG6_TC5] 85服务NRC7F检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_85_NRC7F(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG6_TC6_phyRequest_85_NRC22():
    """[TG6_TC6] 85服务NRC22检查(物理寻址)"""
    case_name = "[TG6_TC6] 85服务NRC22检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_85_NRC22(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG6_TC7_phyRequest_85_NRC_Priority():
    """[TG6_TC7] 85服务NRC优先级检查(物理寻址)"""
    case_name = "[TG6_TC7] 85服务NRC优先级检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_85_NRCPriority(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG7_TC1_phyRequest_22_Positive():
    """[TG7_TC1] 22服务肯定响应检查(物理寻址)"""
    case_name = "[TG7_TC1] 22服务肯定响应检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_22_Positive(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG7_TC2_phyRequest_22_MultiRead():
    """[TG7_TC2] 22服务多数据读取检查(物理寻址)"""
    case_name = "[TG7_TC2] 22服务多数据读取检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_22_MultiRead(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG7_TC3_phyRequest_22_NRC31():
    """[TG7_TC3] 22服务NRC31检查(物理寻址)"""
    case_name = "[TG7_TC3] 22服务NRC31检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_22_NRC31(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG7_TC4_phyRequest_22_NRC13():
    """[TG7_TC4] 22服务NRC13检查(物理寻址)"""
    case_name = "[TG7_TC4] 22服务NRC13检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_22_NRC13(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG7_TC5_phyRequest_22_NRC33():
    """[TG7_TC5] 22服务NRC33检查(物理寻址)"""
    case_name = "[TG7_TC5] 22服务NRC33检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_22_NRC33(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG7_TC6_phyRequest_22_NRC22():
    """[TG7_TC6] 22服务NRC22检查(物理寻址)"""
    case_name = "[TG7_TC6] 22服务NRC22检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_22_NRC22(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG7_TC7_phyRequest_22_NRCPriority():
    """[TG7_TC7] 22服务NRC优先级检查(物理寻址)"""
    case_name = "[TG7_TC7] 22服务NRC优先级检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_22_NRCPriority(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG8_TC1_phyRequest_2E_Positive():
    """[TG8_TC1] 2E服务肯定响应及功能检查(物理寻址)"""
    case_name = "[TG8_TC1] 2E服务肯定响应及功能检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_2E_Positive(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG8_TC2_phyRequest_2E_NRC13():
    """[TG8_TC2] 2E服务NRC13检查(物理寻址)"""
    case_name = "[TG8_TC2] 2E服务NRC13检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_2E_NRC13(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG8_TC3_phyRequest_2E_NRC31():
    """[TG8_TC3] 2E服务NRC31检查(物理寻址)"""
    case_name = "[TG8_TC3] 2E服务NRC31检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_2E_NRC31(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG8_TC4_phyRequest_2E_NRC33():
    """[TG8_TC4] 2E服务NRC33检查(物理寻址)"""
    case_name = "[TG8_TC4] 2E服务NRC33检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_2E_NRC33(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG8_TC5_phyRequest_2E_NRC7F():
    """[TG8_TC5] 2E服务NRC7F检查(物理寻址)"""
    case_name = "[TG8_TC5] 2E服务NRC7F检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_2E_NRC7F(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG8_TC6_phyRequest_2E_NRC22():
    """[TG8_TC6] 2E服务NRC0x22检查(物理寻址)"""
    case_name = "[TG8_TC6] 2E服务NRC0x22检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_2E_NRC22(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG8_TC7_phyRequest_2E_NRCPriorityCheck():
    """[TG8_TC1] 2E服务NRC优先级检查(物理寻址)"""
    case_name = "[TG8_TC1] 2E服务NRC优先级检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_2E_NRCPriorityCheck(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG9_TC1_phyRequest_14_Positive():
    """[TG9_TC1] 14服务肯定响应及功能检查(物理寻址)"""
    case_name = "[TG9_TC1] 14服务肯定响应及功能检查(物理寻址)"
    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_14_Positive(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG9_TC2_phyRequest_14_NRC13():
    """[TG9_TC2] 14服务NRC13检查(物理寻址)"""
    case_name = "[TG9_TC2] 14服务NRC13检查(物理寻址)"

    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_14_NRC13(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG9_TC3_phyRequest_14_NRC31():
    """[TG9_TC3] 14服务NRC31检查(物理寻址)"""
    case_name = "[TG9_TC3] 14服务NRC31检查(物理寻址)"

    try:
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_14_NRC31(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG9_TC4_phyRequest_14_NRC22():
    """[TG9_TC4] 14服务NRC22检查(物理寻址)"""
    case_name = "[TG9_TC4] 14服务NRC22检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        # 调用测试函数
        test_phyRequest_14_NRC22(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG9_TC5_phyRequest_14_NRC_Priority():
    """
    [TG9_TC5] 14服务NRC优先级检查(物理寻址)
    """
    case_name = "[TG9_TC5] 14服务NRC优先级检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_14_NRC_Priority(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG10_TC1_phyRequest_19_Positive():
    """
    [TG10_TC1] 19服务肯定响应检查(物理寻址)
    """
    case_name = "[TG10_TC1] 19服务肯定响应检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_19_Positive(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG10_TC2_phyRequest_19_NRC12():
    """
    [TG10_TC2] 19服务NRC12检查(物理寻址)
    """
    case_name = "[TG10_TC2] 19服务NRC12检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_19_NRC12(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG10_TC3_phyRequest_19_NRC13():
    """
    [TG10_TC3] 19服务NRC13检查(物理寻址)
    """
    case_name = "[TG10_TC3] 19服务NRC13检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_19_NRC13(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG10_TC4_phyRequest_19_NRC31():
    """
    [TG10_TC4] 19服务NRC31检查(物理寻址)
    """
    case_name = "[TG10_TC4] 19服务NRC31检查(物理寻址)",
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_19_NRC31(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG10_TC5_phyRequest_19_NRCPriorityCheck():
    """
    [TG10_TC5] 19服务NRC优先级检查(物理寻址)
    """
    case_name = "[TG10_TC5] 19服务NRC优先级检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_19_NRCPriorityCheck(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG11_TC1_phyRequest_2F_Positive():
    """
    [TG11_TC1] 2F服务肯定响应检查(物理寻址)
    """
    case_name = "[TG11_TC1] 2F服务肯定响应检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_2F_Positive(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG11_TC2_phyRequest_2F_ControlParam():
    """
    [TG11_TC2] 2F服务控制参数检查(物理寻址)
    """
    case_name = "[TG11_TC2] 2F服务控制参数检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_2F_ControlParam(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG11_TC3_phyRequest_2F_NRC7F():
    """
    [TG11_TC3] 2F服务NRC7F检查(物理寻址)
    """
    case_name = "[TG11_TC3] 2F服务NRC7F检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_2F_NRC7F(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG11_TC4_phyRequest_2F_NRC13():
    """
    [TG11_TC4] 2F服务NRC13检查(物理寻址)
    """
    case_name = "[TG11_TC4] 2F服务NRC13检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_2F_NRC13(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG11_TC5_phyRequest_2F_NRC31():
    """
    [TG11_TC5] 2F服务NRC31检查(物理寻址)
    """
    case_name = "[TG11_TC5] 2F服务NRC31检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_2F_NRC31(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG11_TC6_phyRequest_2F_NRC33():
    """
    [TG11_TC6] 2F服务NRC33检查(物理寻址)
    """
    case_name = "[TG11_TC6] 2F服务NRC33检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_2F_NRC33(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG11_TC7_phyRequest_2F_NRC22():
    """
    [TG11_TC7] 2F服务NRC22检查(物理寻址)
    """
    case_name = "[TG11_TC7] 2F服务NRC22检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_2F_NRC22(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG11_TC8_phyRequest_2F_NRCPriority():
    """
    [TG11_TC8] 2F服务NRC优先级检查(物理寻址)
    """
    case_name = "[TG11_TC8] 2F服务NRC优先级检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_2F_NRCPriority(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG11_TC9_phyRequest_2F_ControlReturn():
    """
    [TG11_TC9] 2F服务控制权归还检查(物理寻址)
    """
    case_name = "[TG11_TC9] 2F服务控制权归还检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_2F_ControlReturn(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG12_TC1_phyRequest_31_Positive():
    """
    [TG12_TC1] 31服务肯定响应检查(物理寻址)
    """
    case_name = "[TG12_TC1] 31服务肯定响应检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_31_Positive(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG12_TC2_phyRequest_31_NRC12():
    """
    [TG12_TC2] 31服务NRC12检查(物理寻址)
    """
    case_name = "[TG12_TC2] 31服务NRC12检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_31_NRC12(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG12_TC3_phyRequest_31_NRC13():
    """
    [TG12_TC3] 31服务NRC13检查(物理寻址)
    """
    case_name = "[TG12_TC3] 31服务NRC13检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_31_NRC13(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG12_TC4_phyRequest_31_NRC24():
    """
    [TG12_TC4] 31服务NRC24检查(物理寻址)
    """
    case_name = "[TG12_TC4] 31服务NRC24检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_31_NRC24(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG12_TC5_phyRequest_31_NRC31():
    """
    [TG12_TC5] 31服务NRC31检查(物理寻址)
    """
    case_name = "[TG12_TC5] 31服务NRC31检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_31_NRC31(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG12_TC6_phyRequest_31_NRC33():
    """
    [TG12_TC6] 31服务NRC33检查(物理寻址)
    """
    case_name = "[TG12_TC6] 31服务NRC33检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_31_NRC33(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG12_TC7_phyRequest_31_NRC7F():
    """
    [TG12_TC7] 31服务NRC7F检查(物理寻址)
    """
    case_name = "[TG12_TC7] 31服务NRC7F检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_31_NRC7F(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG12_TC8_phyRequest_31_NRC22():
    """
    [TG12_TC8] 31服务NRC22检查(物理寻址)
    """
    case_name = "[TG12_TC8] 31服务NRC22检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_31_NRC22(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG12_TC9_phyRequest_31_NRCPriority():
    """
    [TG12_TC9] 31服务NRC22检查(物理寻址)
    """
    case_name = "[TG12_TC9] 31服务NRC22检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_31_NRCPriority(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG13_TC1_phyRequest_NRC11():
    """
    [TG13_TC1] 不支持服务NRC11检查(物理寻址)
    """
    case_name = "[TG13_TC1] 不支持服务NRC11检查(物理寻址)"
    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源设置与通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_phyRequest_NRC11(node, case_name, func_flg=False)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")



def test_TG14_TC1_P2ServerTimingTest():
    """[TG14_TC1] P2 Server时间测试"""
    case_name = "[TG14_TC1] P2 Server时间测试"

    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源和通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_P2Server_TimingTest(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG14_TC2_P2ServerTimingTest():
    """[TG14_TC2] P2*Server时间测试"""
    case_name = "[TG14_TC2] P2*Server时间测试"

    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源和通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_P2Server_TimingTest(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG14_TC3_SessionSwitchingTimeTest():
    """[TG14_TC3] 会话切换时间测试"""
    case_name = "[TG14_TC3] 会话切换时间测试"

    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源和通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_Session_SwitchingTimeTest(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG14_TC4_AppToBootTimeTest():
    """[TG14_TC4] APP跳转到Boot时间测试"""
    case_name = "[TG14_TC4] APP跳转到Boot时间测试"

    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源和通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_AppToBoot_TimeTest(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG14_TC5_BootToAppTimeTest():
    """[TG14_TC5] Boot跳转到APP时间测试"""
    case_name = "[TG14_TC5] Boot跳转到APP时间测试"

    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源和通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_BootToApp_TimeTest(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG14_TC6_EnterBootStopCommunicationTest():
    """[TG14_TC6] 进入Boot停止网络通信测试"""
    case_name = "[TG14_TC6] 进入Boot停止网络通信测试"

    try:
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源和通信检查
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        test_EnterBoot_StopCommunicationTest(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def get_all_test_cases():
    """获取uds测试用例"""
    current_module = inspect.getmodule(inspect.currentframe())

    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj

    return test_cases
