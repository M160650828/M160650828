import traceback
import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import traceback
from env.config import *

from uvtest.testlog import TestLog
from common.control import TestStart, TestEnd
from common.params import P
from tp.lintp_module import lin_mormal_tp_init, lin_tp_end, lin_can_init, lin_can_deinit
from .dtc_lin_utils import get_lin_node, lin_node_power_setup_and_communication_check, test_ReadSupported_DTCList_TC1, \
    test_DTCStatusAvailabilityMask_TC2, test_DTCStatusAvailabilityMaskList_TC3, test_DTCFaultGeneration_TC4, \
    test_DTCFaultRecovery_TC5, test_DTCAgingMechanism_TC6, test_ParentChildHighDTCScenario_TC7, \
    test_ParentChildLowDTCScenario_TC8, test_ParentChildDTCScenario_TC9, test_FaultWarningCheck_TC10, \
    test_FaultWarningCheck_TC11, test_FaultWarningCheck_TC12, test_FaultWarningCheck_TC13, \
    test_GlobalSnapshotDataCheck_TC14, test_GlobalSnapshotDataCheck_TC15, test_GlobalSnapshotDataCheck_TC16, \
    test_GlobalSnapshotDataCheck_TC17, test_GlobalSnapshotDataCheck_TC18, test_GlobalSnapshotDataCheck_TC19, \
    test_GlobalSnapshotDataCheck_TC20, test_GlobalSnapshotDataCheck_TC21, test_LocalSnapshotDataCheck_TC22, \
    test_LocalSnapshotDataCheck_TC23, test_DTCTriggerCheck_TC24, test_DTCTriggerCheck_TC25, test_DTCTriggerCheck_TC26, \
    test_QuietModeCheck_TC27, test_EngineCrank_TC28, test_DTCConfigurationCheck_TC29, test_DTCConfigurationCheck_TC30, \
    test_MaxDTCEntriesCheck_TC31, test_NonVolatileMemoryStorageCheck_TC32, test_DTCOverflowMechanismCheck_TC33


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


def test_TG1_TC1_ReadSupportedDTCList():
    """[TG1_TC1] LIN诊断故障代码列表读取检查"""
    case_name = "[TG1_TC1] LIN诊断故障代码列表读取检查"

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

        test_ReadSupported_DTCList_TC1(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC2_DTCStatusAvailabilityMask():
    """[TG1_TC2] 诊断故障代码状态掩码检查"""
    case_name = "[TG1_TC2] 诊断故障代码状态掩码检查"

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

        test_DTCStatusAvailabilityMask_TC2(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC3_DTCStatusMaskFiltering():
    """[TG1_TC3] 诊断故障代码状态掩码检查"""
    case_name = "[TG1_TC3] 诊断故障代码状态掩码检查"

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

        test_DTCStatusAvailabilityMaskList_TC3(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC4_DTCFaultGeneration():
    """[TG1_TC4] 诊断故障代码产生和恢复条件检查"""
    case_name = "[TG1_TC4] 诊断故障代码产生和恢复条件检查"

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

        test_DTCFaultGeneration_TC4(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC5_DTCFaultRecovery():
    """[TG1_TC5] 诊断故障代码产生和恢复条件检查"""
    case_name = "[TG1_TC5] 诊断故障代码产生和恢复条件检查"

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

        test_DTCFaultRecovery_TC5(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC6_DTCAgingMechanism():
    """[TG1_TC6] 诊断故障代码老化机制检查"""
    case_name = "[TG1_TC6] 诊断故障代码老化机制检查"

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

        test_DTCAgingMechanism_TC6(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC7_ParentChildHighDTCScenario():
    """[TG1_TC7] 父子高压故障场景检查"""
    case_name = "[TG1_TC7] 父子高压故障场景检查"

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

        test_ParentChildHighDTCScenario_TC7(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC8_ParentChildLowDTCScenario():
    """[TG1_TC8] 父子低压故障场景检查"""
    case_name = "[TG1_TC8] 父子低压故障场景检查"

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

        test_ParentChildLowDTCScenario_TC8(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC9_ParentChildDTCScenario():
    """[TG1_TC9] 父子其它故障场景检查"""
    case_name = "[TG1_TC9] 父子其它故障场景检查"

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

        test_ParentChildDTCScenario_TC9(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC10_FaultWarningCheck():
    """[TG1_TC10] 故障警示检查（故障警示相关信号）"""
    case_name = "[TG1_TC10] 故障警示检查"

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

        test_FaultWarningCheck_TC10(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC11_FaultWarningCheck():
    """[TG1_TC11] 故障警示检查（故障现象消除即灭灯）"""
    case_name = "[TG1_TC11] 故障警示检查"

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

        test_FaultWarningCheck_TC11(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC12_FaultWarningCheck():
    """[TG1_TC12] 故障警示检查（操作循环结束时灭灯）"""
    case_name = "[TG1_TC12] 故障警示检查"

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

        test_FaultWarningCheck_TC12(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC13_FaultWarningCheck():
    """[TG1_TC11] 故障警示检查（连续三操作循环无故障才灭灯）"""
    case_name = "[TG1_TC13] 故障警示检查"

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

        test_FaultWarningCheck_TC13(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC14_GlobalSnapshotDataCheck():
    """[TG1_TC14] 全局快照数据检查（故障产生时读取快照）"""
    case_name = "[TG1_TC14] 全局快照数据检查"

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

        test_GlobalSnapshotDataCheck_TC14(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC15_GlobalSnapshotDataCheck():
    """[TG1_TC15] 全局快照数据检查（故障恢复后检查快照不变性）"""
    case_name = "[TG1_TC15] 全局快照数据检查"

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

        test_GlobalSnapshotDataCheck_TC15(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC16_GlobalSnapshotDataCheck():
    """[TG1_TC16] 全局快照数据检查（数据变更后检查快照不变性）"""
    case_name = "[TG1_TC16] 全局快照数据检查"

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

        test_GlobalSnapshotDataCheck_TC16(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC17_GlobalSnapshotDataCheck():
    """[TG1_TC17] 全局快照数据检查（检查快照数据全为FF）"""
    case_name = "[TG1_TC17] 全局快照数据检查"

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

        test_GlobalSnapshotDataCheck_TC17(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC18_GlobalSnapshotDataCheck():
    """[TG1_TC18] 全局快照数据检查（检查最近有效值）"""
    case_name = "[TG1_TC18] 全局快照数据检查"

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

        test_GlobalSnapshotDataCheck_TC18(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC19_GlobalSnapshotDataCheck():
    """[TG1_TC19] 全局快照数据检查（检查系统数据与真实状态一致）"""
    case_name = "[TG1_TC19] 全局快照数据检查"

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

        test_GlobalSnapshotDataCheck_TC19(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC20_GlobalSnapshotDataCheck():
    """[TG1_TC20] 全局快照数据检查（故障恢复后改变数据并检查最新快照）"""
    case_name = "[TG1_TC20] 全局快照数据检查"

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

        test_GlobalSnapshotDataCheck_TC20(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC21_GlobalSnapshotDataCheck():
    """[TG1_TC21] 全局快照数据检查（再次故障恢复后改变数据并检查最新快照）"""
    case_name = "[TG1_TC21] 全局快照数据检查"

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

        test_GlobalSnapshotDataCheck_TC21(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC22_LocalSnapshotDataCheck():
    """[TG1_TC22] 局部快照数据检查（故障条件下检查局部快照数据与实际状态一致）"""
    case_name = "[TG1_TC22] 局部快照数据检查"

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

        test_LocalSnapshotDataCheck_TC22(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC23_LocalSnapshotDataCheck():
    """[TG1_TC23] 局部快照数据检查（故障恢复后检查局部快照数据保持不变）"""
    case_name = "[TG1_TC23] 局部快照数据检查"

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

        test_LocalSnapshotDataCheck_TC23(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC24_DTCTriggerCheck():
    """[TG1_TC24] 单个诊断故障代码触发检查"""
    case_name = "[TG1_TC24] 单个诊断故障代码触发检查"

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

        test_DTCTriggerCheck_TC24(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC25_DTCTriggerCheck():
    """[TG1_TC25] 单个诊断故障代码触发检查"""
    case_name = "[TG1_TC25] 单个诊断故障代码触发检查"

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

        test_DTCTriggerCheck_TC25(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC26_DTCTriggerCheck():
    """[TG1_TC26] 多个诊断故障代码触发检查"""
    case_name = "[TG1_TC26] 多个诊断故障代码触发检查"

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

        test_DTCTriggerCheck_TC26(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC27_QuietModeCheck():
    """[TG1_TC27] 安静模式检查"""
    case_name = "[TG1_TC27] 安静模式检查"

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

        test_QuietModeCheck_TC27(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC28_EngineCrank():
    """[TG1_TC28] 发动机起动场景检查"""
    case_name = "[TG1_TC28] 发动机起动场景检查"

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

        test_EngineCrank_TC28(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC29_DTCConfigurationCheck():
    """[TG1_TC29] 诊断故障代码配置检查"""
    case_name = "[TG1_TC29] 诊断故障代码配置检查"

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

        test_DTCConfigurationCheck_TC29(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC30_DTCConfigurationCheck():
    """[TG1_TC30] 诊断故障代码配置检查"""
    case_name = "[TG1_TC30] 诊断故障代码配置检查"

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

        test_DTCConfigurationCheck_TC30(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC31_MaxDTCEntriesCheck():
    """[TG1_TC31] 最大诊断故障代码条目数检查"""
    case_name = "[TG1_TC31] 最大诊断故障代码条目数检查"

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

        test_MaxDTCEntriesCheck_TC31(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC32_NonVolatileMemoryStorageCheck():
    """[TG1_TC32] 非易失存储器存储检查"""
    case_name = "[TG1_TC32] 非易失存储器存储检查"

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

        test_NonVolatileMemoryStorageCheck_TC32(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC33_DTCOverflowMechanismCheck():
    """[TG1_TC33] 诊断故障代码溢出机制检查"""
    case_name = "[TG1_TC33] 诊断故障代码溢出机制检查"

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

        test_DTCOverflowMechanismCheck_TC33(node, case_name)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")