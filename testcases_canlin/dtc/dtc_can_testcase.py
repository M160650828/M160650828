import sys
import os
import time
import traceback

from pandas.core.arrays.categorical import contains

from env.config import *
from uvtest.testlog import TestLog
from common.control import TestStart, TestEnd
from uvtest.framework import TestFixture

from common.params import P
from .dtc_can_utils import (
    DTCTestParams,
    get_can_node,
    service_19_check,
    service_14_check,
    get_dtc_list_from_19_resp,
    compare_dtc_list,
    GlobalSnapshotData,
    GlobalSnapshotStore,
    DTCStatusBit,
    get_bit,
    check_dtc_list_status_bits,
    FaultSimulator,
    OperationCycle,
    inject_fault_and_read_global_snapshot,
    recover_fault_and_read_global_snapshot,
    env_simulator,
    snapshot_store,
    sim_message_ctrl,
    write_dtc_config,
    enable_dtc_config,
    disable_dtc_config,
    service_10_check,
    read_global_snapshot, read_dtc_and_global_snapshot, find_DTC_by_status_mask, read_extend_data, tc13,
    select_fault_type, tc14, tc16, tc17, tc18,
    tc19, tc20, tc21, service_11_check, check_resp, tester_present_start, tester_present_stop, dtc_enable_conditions,
    service_22_check, inject_all_fault, tc15, sim_engine_rpm_msg, check_and_recovery_env_simulator, clear_dtc,
    operation_after_low_voltage, hard_reset,
)

from .can_comm import can_power_setup_and_communication_check, can_initialization, can_deinitialization
# from .e2e_module import (
#     e2e_initialization, e2e_deinitialization,
#     verify_can_crc, verify_can_counter, verify_can_busoff_counter,
#     verify_lin_crc_and_counter, verify_can_crc_receive,verify_can_counter_receive,Counter_Miss_Error,Counter_Repeated_Error,Counter_Unorder_Error
# )
from common.context import ctx

workdir_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(workdir_path)

class DTCCANTestFixture(TestFixture):
    def group_setup(self, context=None):
        can_initialization()

    def group_teardown(self, context=None):
        can_deinitialization()

    def case_setup(self, context=None):
        if context:
            TestStart(context["test_name"])

    def case_teardown(self, context=None):
        TestEnd("")
        TestLog("INFO", "测试结束", "执行测试结束和去初始化")


def test_TG1_TC1_ReadSupportedDTCList():
    """
    诊断故障代码列表读取检查
    """
    case_name = "诊断故障代码列表读取检查(19 0A)"

    node = get_can_node()

    try:
        rVnormal = P.CANInfo.Vnormal      # 电源正常电压
        rTstable = P.CANInfo.Tstable_s    # 通信稳定等待时间

        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "Step1", "发送 19 0A 请求读取电控单元支持的诊断故障代码清单(PHY Tx: 02 19 0A)")

        success, resp = service_19_check(
            node,
            report_type=0x0A,
            expect_data=[0x59, 0x0A],  # 期望肯定响应 59 0A
            expect_str="肯定响应(59 0A)",
            func_req=False
        )

        if not success:
            TestLog("FAIL", "", "未收到肯定响应")
            return

        dtc_list = get_dtc_list_from_19_resp(resp)
        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"
            TestLog("INFO", "", f"  DTC: {dtc_str}, 状态: {status:02X}")

        if DTCTestParams.ExpectedDTCList:
            if compare_dtc_list(dtc_list, DTCTestParams.ExpectedDTCList):
                TestLog("PASS", "", f"期望结果：读取到 {len(dtc_list)} 个 DTC，与 FMS 定义完全一致"
                                           f"实际结果：读取到 {len(dtc_list)} 个 DTC，与 FMS 定义完全一致")
            else:
                TestLog("FAIL", "", f"期望结果：读取到 {len(dtc_list)} 个 DTC，与 FMS 定义完全一致"
                                           "实际结果：读取的 DTC 列表与 FMS 定义不一致")
        else:
            TestLog("PASS", "", f"成功读取到 {len(dtc_list)} 个支持的 DTC（需手动验证与 FMS 定义是否一致）")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        env_simulator.stop()
        if node:
            node.close()



def test_TG1_TC2_DTCStatusAvailabilityMask():
    """DTCStatusAvailabilityMask检查(19 02)"""
    case_name = "诊断故障代码状态掩码检查"

    node = get_can_node()

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "Step1", "发送 19 02 08 请求读取DTC信息(PHY Tx: 03 19 02 08)")

        success, resp = service_19_check(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0x08
        )

        if not success:
            TestLog("FAIL", "", "未收到肯定响应")
            return

        resp_data = list(resp.data) if hasattr(resp, 'data') else list(resp)
        if len(resp_data) < 3:
            TestLog("FAIL", "", f"响应数据长度不足: {[hex(b) for b in resp_data]}")
            return

        dtc_status_availability_mask = resp_data[2]
        TestLog("INFO", "", f"DTCStatusAvailabilityMask = 0x{dtc_status_availability_mask:02X}")

        if dtc_status_availability_mask == DTCTestParams.ExpectedDTCStatusAvailabilityMask:
            TestLog("PASS", "", f"期望结果：DTCStatusAvailabilityMask与配置的参数DTCStatusAvlMask 0x{DTCTestParams.ExpectedDTCStatusAvailabilityMask:02X}一致，"
                                       f"实际结果：DTCStatusAvailabilityMask = 0x{dtc_status_availability_mask:02X}，符合预期")
        else:
            TestLog("FAIL", "", f"期望结果：DTCStatusAvailabilityMask与配置的参数DTCStatusAvlMask 0x{DTCTestParams.ExpectedDTCStatusAvailabilityMask:02X}一致，"
                                       f"实际结果：DTCStatusAvailabilityMask = 0x{dtc_status_availability_mask:02X}，不符合预期")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        env_simulator.stop()
        if node:
            node.close()


def test_TG1_TC3_DTCStatusMaskFiltering():
    """诊断故障代码状态掩码检查"""
    case_name = "诊断故障代码状态掩码检查"

    node = get_can_node()

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        status_masks = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80]
        all_passed = True

        for mask in status_masks:
            TestLog("INFO", f"Step(mask=0x{mask:02X})", f"发送 19 02 {mask:02X} 请求(PHY Tx: 03 19 02 {mask:02X} 00 00 00 00)")

            success, resp = service_19_check(
                node,
                report_type=0x02,
                expect_data=[0x59, 0x02],
                expect_str=f"肯定响应(59 02)",
                func_req=False,
                DTCStatusMask=mask
            )

            if not success:
                TestLog("FAIL", "", f"掩码 0x{mask:02X}: 未收到肯定响应")
                all_passed = False
                continue

            dtc_list = get_dtc_list_from_19_resp(resp)

            if len(dtc_list) == 0:
                TestLog("INFO", "", f"掩码 0x{mask:02X}: 未读取到匹配的 DTC")
                continue

            for dtc_info in dtc_list:
                dtc = dtc_info['dtc']
                status = dtc_info['status']
                dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"

                if (status & mask) == mask:
                    TestLog("PASS", "", f"DTC {dtc_str}: status=0x{status:02X}, (status & 0x{mask:02X})=0x{mask:02X}")
                else:
                    TestLog("FAIL", "", f"DTC {dtc_str}: status=0x{status:02X}, (status & 0x{mask:02X})=0x{status & mask:02X} ≠ 0x{mask:02X}")
                    all_passed = False

        if all_passed:
            TestLog("PASS", "", "所有状态掩码过滤检查通过")
        else:
            TestLog("FAIL", "", "部分状态掩码过滤检查未通过")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        env_simulator.stop()
        if node:
            node.close()



def test_TG1_TC4_DTCStatusMask2C():
    """诊断故障代码状态掩码检查"""
    case_name = "诊断故障代码状态掩码检查"

    node = get_can_node()

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "Step1", "发送 19 02 2C 请求读取DTC信息(PHY Tx: 03 19 02 2C)")

        success, resp = service_19_check(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0x2C
        )

        if not success:
            TestLog("FAIL", "", "未收到肯定响应")
            return

        dtc_list = get_dtc_list_from_19_resp(resp)
        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        if len(dtc_list) == 0:
            TestLog("INFO", case_name, "未读取到匹配掩码 2C 的 DTC（可能没有符合条件的故障码）")
            return

        all_passed = True
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"

            if (status & 0x2C) != 0:
                TestLog("INFO", "", f"DTC {dtc_str}: status=0x{status:02X}, (status & 0x2C)=0x{status & 0x2C:02X} != 0")
            else:
                TestLog("INFO", "", f"DTC {dtc_str}: status=0x{status:02X}, (status & 0x2C)=0x00")
                all_passed = False

        if all_passed:
            TestLog("PASS", "", "所有读取到的 DTC 状态信息至少有一位与 2C 掩码位一致")
        else:
            TestLog("FAIL", "", "存在 DTC 状态信息与 2C 掩码位不一致")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        env_simulator.stop()
        if node:
            node.close()


def test_TG1_TC5_DTCStatusMaskFF():
    """诊断故障代码状态掩码检查"""
    case_name = "诊断故障代码状态掩码检查"

    node = get_can_node()

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "Step1", "发送 19 02 FF 请求读取DTC信息(PHY Tx: 03 19 02 FF)")

        success, resp = service_19_check(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0xFF
        )

        if not success:
            TestLog("FAIL", "", "未收到肯定响应")
            return

        dtc_list = get_dtc_list_from_19_resp(resp)
        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        if len(dtc_list) == 0:
            TestLog("INFO", case_name, "未读取到任何 DTC（可能没有故障码）")
            return

        all_passed = True
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"

            if status != 0:
                TestLog("INFO", "", f"DTC {dtc_str}: statusOfDTC=0x{status:02X} != 0")
            else:
                TestLog("INFO", "", f"DTC {dtc_str}: statusOfDTC=0x00")
                all_passed = False

        if all_passed:
            TestLog("PASS", "", "所有读取到的 DTC 状态信息至少有一位为1")
        else:
            TestLog("FAIL", "", "存在 DTC 状态信息为 0x00")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        env_simulator.stop()
        if node:
            node.close()


def test_TG1_TC6_SC1_DTCTestFailedBit():
    """
    DTC测试失败位(bit0)检查
    """
    import time
    case_name = "诊断故障代码产生和恢复条件检查"

    node = get_can_node()
    sim = FaultSimulator()
    # injected_faults = []

    try:
        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "Step1", "使用0x14服务清除所有DTC")
        clear_dtc(node)
        time.sleep(1)

        TestLog("INFO", "Step2", "模拟产生节点丢失故障")
        #节点丢失故障
        for item in P.ExtendedDTCInfo.lost_communication.valid_items:
            injected_faults = []

            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x","")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{item.PassTime} ms")
            sim.lost_comm_fault(True, item.MonitorMessageID)
            injected_faults.append(('lost', item))

            wait_time_s = (item.LostTime or 5000) / 1000
            TestLog("INFO", "Step3", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            TestLog("INFO", "Step4", "发送 19 02 FF 请求读取DTC信息")
            success, resp = service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02],
                                             expect_str="肯定响应(59 02)", func_req=False, DTCStatusMask=0xFF)
            if not success:
                TestLog("FAIL", "", "未收到肯定响应")
                return

            dtc_list = get_dtc_list_from_19_resp(resp)
            TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")
            if len(dtc_list) == 0:
                TestLog("FAIL", "", "未读取到任何 DTC，故障注入可能未生效")

            result = False
            for dtc_info in dtc_list:
                dtc = dtc_info['dtc']
                status = dtc_info['status']
                dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"
                if dtc_str == dtc_select:
                    TestLog("INFO", "", f"读取到故障码 {dtc_select}")
                    if (status & 0x01) != 0:
                        TestLog("PASS", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为1, "
                                            f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为1")
                    else:
                        TestLog("FAIL", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为1, "
                                            f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为0")
                    result = True
            if not result:
                TestLog("FAIL", "", f"期望结果：读取到故障码 {dtc_select}, "
                                    f"实际结果：没有读取到故障码 {dtc_select}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        env_simulator.stop()
        sim.stop_all_timer()
        if node:
            node.close()

def test_TG1_TC6_SC2_DTCTestFailedBit():
    """
    DTC测试失败位(bit0)检查
    """
    import time
    case_name = "诊断故障代码产生和恢复条件检查"

    node = get_can_node()
    sim = FaultSimulator()
    # injected_faults = []

    try:
        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "Step1", "使用0x14服务清除所有DTC")
        clear_dtc(node)
        time.sleep(1)

        TestLog("INFO", "Step2", "无效数据故障")
        #节点丢失故障
        for item in P.ExtendedDTCInfo.invalid_data.valid_items:
            injected_faults = []
            if item.Type != "InvalidData":
                continue

            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x","")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{item.PassTime} ms")
            sim.invalid_data_fault(True, item.MonitorMessageID,
                                        dlc=item.MonitorMessageDLC, cycle_ms=item.MonitorMessagePeriod or 100,
                                        data = item.InvalidPayload, is_canfd=item.FDF,
                                        is_e2e = item.IsContainE2E, data_id = item.DataID)
            injected_faults.append(('invalid', item))

            wait_time_s = (item.LostTime or 5000) / 1000
            TestLog("INFO", "Step3", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            TestLog("INFO", "Step4", "发送 19 02 FF 请求读取DTC信息")
            success, resp = service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02],
                                             expect_str="肯定响应(59 02)", func_req=False, DTCStatusMask=0xFF)
            if not success:
                TestLog("FAIL", "", "未收到肯定响应")
                return

            dtc_list = get_dtc_list_from_19_resp(resp)
            TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")
            if len(dtc_list) == 0:
                TestLog("FAIL", "", "未读取到任何 DTC，故障注入可能未生效")

            result = False
            for dtc_info in dtc_list:
                dtc = dtc_info['dtc']
                status = dtc_info['status']
                dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"
                if dtc_str == dtc_select:
                    TestLog("INFO", "", f"读取到故障码 {dtc_select}")
                    if (status & 0x01) != 0:
                        TestLog("PASS", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为1, "
                                            f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为1")
                    else:
                        TestLog("FAIL", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为1, "
                                            f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为0")
                    result = True
            if not result:
                TestLog("FAIL", "", f"期望结果：读取到故障码 {dtc_select}, "
                                    f"实际结果：没有读取到故障码 {dtc_select}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        env_simulator.stop()
        sim.stop_all_timer()
        if node:
            node.close()


def test_TG1_TC6_SC3_DTCTestFailedBit():
    """
    DTC测试失败位(bit0)检查
    """
    import time
    case_name = "诊断故障代码产生和恢复条件检查"

    node = get_can_node()
    sim = FaultSimulator()
    # injected_faults = []

    try:
        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "Step1", "使用0x14服务清除所有DTC")
        clear_dtc(node)
        time.sleep(1)

        TestLog("INFO", "Step2", "通信校验错误故障")
        #节点丢失故障
        for item in P.ExtendedDTCInfo.invalid_data.valid_items:
            injected_faults = []
            if "E2E" not in item.Type.upper():
                continue

            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x","")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{item.PassTime} ms")
            sim.crc_e2e_fault(True, item.MonitorMessageID, item.Type,
                                        dlc=item.MonitorMessageDLC, cycle_ms=item.MonitorMessagePeriod or 100,
                                        data = item.ValidPayload, is_canfd=item.FDF,
                                        is_e2e = item.IsContainE2E, data_id = item.DataID)
            injected_faults.append(('e2e', item))

            wait_time_s = (item.LostTime or 5000) / 1000
            TestLog("INFO", "Step3", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            TestLog("INFO", "Step4", "发送 19 02 FF 请求读取DTC信息")
            success, resp = service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02],
                                             expect_str="肯定响应(59 02)", func_req=False, DTCStatusMask=0xFF)
            if not success:
                TestLog("FAIL", "", "未收到肯定响应")
                return

            dtc_list = get_dtc_list_from_19_resp(resp)
            TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")
            if len(dtc_list) == 0:
                TestLog("FAIL", "", "未读取到任何 DTC，故障注入可能未生效")

            result = False
            for dtc_info in dtc_list:
                dtc = dtc_info['dtc']
                status = dtc_info['status']
                dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"
                if dtc_str == dtc_select:
                    TestLog("INFO", "", f"读取到故障码 {dtc_select}")
                    if (status & 0x01) != 0:
                        TestLog("PASS", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为1, "
                                            f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为1")
                    else:
                        TestLog("FAIL", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为1, "
                                            f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为0")
                    result = True
            if not result:
                TestLog("FAIL", "", f"期望结果：读取到故障码 {dtc_select}, "
                                    f"实际结果：没有读取到故障码 {dtc_select}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        env_simulator.stop()
        sim.stop_all_timer()
        if node:
            node.close()

def test_TG1_TC7_SC1_DTCFaultRecoveryBit0Bit3():
    """
    诊断故障代码产生和恢复条件检查
    """
    import time
    case_name = "诊断故障代码产生和恢复条件检查"

    node = get_can_node()
    sim = FaultSimulator()
    # injected_faults = []

    try:
        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "Step1", "使用0x14服务清除所有DTC")
        clear_dtc(node)
        time.sleep(1)

        TestLog("INFO", "Step2", "模拟产生节点丢失故障")
        #节点丢失故障
        for item in P.ExtendedDTCInfo.lost_communication.valid_items:
            injected_faults = []

            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x","")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{item.PassTime} ms")
            sim.lost_comm_fault(True, item.MonitorMessageID)
            injected_faults.append(('lost', item))

            wait_time_s = (item.LostTime or 5000) / 1000
            TestLog("INFO", "Step3", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            TestLog("INFO", "Step4", "发送 19 02 FF 请求读取DTC信息")
            success, resp = service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02],
                                             expect_str="肯定响应(59 02)", func_req=False, DTCStatusMask=0xFF)
            if not success:
                TestLog("FAIL", "", "未收到肯定响应")
                return

            dtc_list = get_dtc_list_from_19_resp(resp)
            TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")
            if len(dtc_list) == 0:
                TestLog("FAIL", "", "未读取到任何 DTC，故障注入可能未生效")

            result = False
            for dtc_info in dtc_list:
                dtc = dtc_info['dtc']
                status = dtc_info['status']
                dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"
                if dtc_str == dtc_select:
                    TestLog("INFO", "", f"读取到故障码 {dtc_select}")
                    if (status & 0x01) != 0:
                        TestLog("PASS", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为1, "
                                            f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为1")
                    else:
                        TestLog("FAIL", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为1, "
                                            f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为0")
                    result = True
            if not result:
                TestLog("FAIL", "", f"期望结果：读取到故障码 {dtc_select}, "
                                    f"实际结果：没有读取到故障码 {dtc_select}")

            TestLog("INFO", "Step5", f"恢复故障DTC(0x{dtc_select})，等待故障恢复时间: {wait_time_s:.1f}s")
            check_and_recovery_env_simulator(item.MonitorMessageID)
            sim.lost_comm_fault(False, item.MonitorMessageID, dlc=item.MonitorMessageDLC,
                                cycle_ms=item.MonitorMessagePeriod or 100, is_canfd=item.FDF)
            wait_time_s = (item.PassTime or 1000) / 1000
            time.sleep(wait_time_s)

            TestLog("INFO", "Step6", "发送 19 02 FF 请求读取DTC信息")
            success, resp = service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02],
                                             expect_str="肯定响应(59 02)", func_req=False, DTCStatusMask=0xFF)
            if not success:
                TestLog("FAIL", "", "未收到肯定响应")
                return

            dtc_list = get_dtc_list_from_19_resp(resp)
            TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")
            if len(dtc_list) == 0:
                TestLog("FAIL", "", "未读取到任何 DTC，故障注入可能未生效")

            result = False
            for dtc_info in dtc_list:
                dtc = dtc_info['dtc']
                status = dtc_info['status']
                dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"
                if dtc_str == dtc_select:
                    TestLog("INFO", "", f"读取到故障码 {dtc_select}")
                    if (status & 0x01) == 0 and (status & 0x08) != 0:
                        TestLog("PASS", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为0，bit3置为1, "
                                            f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为0，bit3置为1")
                    else:
                        TestLog("FAIL", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为0，bit3置为1, "
                                            f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为{status & 0x01}，bit3置为{(status >> 3) & 1}")
                    result = True
            if not result:
                TestLog("FAIL", "", f"期望结果：读取到故障码 {dtc_select}, "
                                    f"实际结果：没有读取到故障码 {dtc_select}")


    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        env_simulator.stop()
        sim.stop_all_timer()
        if node:
            node.close()

def test_TG1_TC7_SC2_DTCFaultRecoveryBit0Bit3():
    """
    诊断故障代码产生和恢复条件检查
    """
    import time
    case_name = "诊断故障代码产生和恢复条件检查"

    node = get_can_node()
    sim = FaultSimulator()
    # injected_faults = []

    try:
        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "Step1", "使用0x14服务清除所有DTC")
        clear_dtc(node)
        time.sleep(1)

        TestLog("INFO", "Step2", "无效数据故障")
        for item in P.ExtendedDTCInfo.invalid_data.valid_items:
            injected_faults = []
            if item.Type != "InvalidData":
                continue

            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x","")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{item.PassTime} ms")
            sim.invalid_data_fault(True, item.MonitorMessageID,
                                        dlc=item.MonitorMessageDLC, cycle_ms=item.MonitorMessagePeriod or 100,
                                        data = item.InvalidPayload, is_canfd=item.FDF,
                                        is_e2e = item.IsContainE2E, data_id = item.DataID)
            injected_faults.append(('invalid', item))

            wait_time_s = (item.LostTime or 5000) / 1000
            TestLog("INFO", "Step3", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            TestLog("INFO", "Step4", "发送 19 02 FF 请求读取DTC信息")
            success, resp = service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02],
                                             expect_str="肯定响应(59 02)", func_req=False, DTCStatusMask=0xFF)
            if not success:
                TestLog("FAIL", "", "未收到肯定响应")
                return

            dtc_list = get_dtc_list_from_19_resp(resp)
            TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")
            if len(dtc_list) == 0:
                TestLog("FAIL", "", "未读取到任何 DTC，故障注入可能未生效")

            result = False
            for dtc_info in dtc_list:
                dtc = dtc_info['dtc']
                status = dtc_info['status']
                dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"
                if dtc_str == dtc_select:
                    TestLog("INFO", "", f"读取到故障码 {dtc_select}")
                    if (status & 0x01) != 0:
                        TestLog("PASS", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为1, "
                                            f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为1")
                    else:
                        TestLog("FAIL", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为1, "
                                            f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为0")
                    result = True
            if not result:
                TestLog("FAIL", "", f"期望结果：读取到故障码 {dtc_select}, "
                                    f"实际结果：没有读取到故障码 {dtc_select}")

            TestLog("INFO", "Step5", f"恢复故障DTC(0x{dtc_select})，等待故障恢复时间: {wait_time_s:.1f}s")
            check_and_recovery_env_simulator(item.MonitorMessageID)
            sim.invalid_data_fault(False, item.MonitorMessageID,
                                   dlc=item.MonitorMessageDLC, cycle_ms=item.MonitorMessagePeriod or 100,
                                   data=item.ValidPayload, is_canfd=item.FDF,
                                   is_e2e=item.IsContainE2E, data_id=item.DataID)
            wait_time_s = (item.PassTime or 1000) / 1000
            time.sleep(wait_time_s)

            TestLog("INFO", "Step6", "发送 19 02 FF 请求读取DTC信息")
            success, resp = service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02],
                                             expect_str="肯定响应(59 02)", func_req=False, DTCStatusMask=0xFF)
            if not success:
                TestLog("FAIL", "", "未收到肯定响应")
                return

            dtc_list = get_dtc_list_from_19_resp(resp)
            TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")
            if len(dtc_list) == 0:
                TestLog("FAIL", "", "未读取到任何 DTC，故障注入可能未生效")

            result = False
            for dtc_info in dtc_list:
                dtc = dtc_info['dtc']
                status = dtc_info['status']
                dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"
                if dtc_str == dtc_select:
                    TestLog("INFO", "", f"读取到故障码 {dtc_select}")
                    if (status & 0x01) == 0 and (status & 0x08) != 0:
                        TestLog("PASS", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为0，bit3置为1, "
                                            f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为0，bit3置为1")
                    else:
                        TestLog("FAIL", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为0，bit3置为1, "
                                            f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为{status & 0x01}，bit3置为{(status >> 3) & 1}")
                    result = True
            if not result:
                TestLog("FAIL", "", f"期望结果：读取到故障码 {dtc_select}, "
                                    f"实际结果：没有读取到故障码 {dtc_select}")


    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        env_simulator.stop()
        sim.stop_all_timer()
        if node:
            node.close()

def test_TG1_TC7_SC3_DTCFaultRecoveryBit0Bit3():
    """
    诊断故障代码产生和恢复条件检查
    """
    import time
    case_name = "诊断故障代码产生和恢复条件检查"

    node = get_can_node()
    sim = FaultSimulator()
    # injected_faults = []

    try:
        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "Step1", "使用0x14服务清除所有DTC")
        clear_dtc(node)
        time.sleep(1)

        TestLog("INFO", "Step2", "通信校验错误故障")
        for item in P.ExtendedDTCInfo.invalid_data.valid_items:
            injected_faults = []
            if "E2E" not in item.Type.upper():
                continue

            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x","")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{item.PassTime} ms")
            sim.crc_e2e_fault(True, item.MonitorMessageID, item.Type,
                                        dlc=item.MonitorMessageDLC, cycle_ms=item.MonitorMessagePeriod or 100,
                                        data = item.ValidPayload, is_canfd=item.FDF,
                                        is_e2e = item.IsContainE2E, data_id = item.DataID)
            injected_faults.append(('e2e', item))

            wait_time_s = (item.LostTime or 5000) / 1000
            TestLog("INFO", "Step3", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            TestLog("INFO", "Step4", "发送 19 02 FF 请求读取DTC信息")
            success, resp = service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02],
                                             expect_str="肯定响应(59 02)", func_req=False, DTCStatusMask=0xFF)
            if not success:
                TestLog("FAIL", "", "未收到肯定响应")
                return

            dtc_list = get_dtc_list_from_19_resp(resp)
            TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")
            if len(dtc_list) == 0:
                TestLog("FAIL", "", "未读取到任何 DTC，故障注入可能未生效")

            result = False
            for dtc_info in dtc_list:
                dtc = dtc_info['dtc']
                status = dtc_info['status']
                dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"
                if dtc_str == dtc_select:
                    TestLog("INFO", "", f"读取到故障码 {dtc_select}")
                    if (status & 0x01) != 0:
                        TestLog("PASS", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为1, "
                                            f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为1")
                    else:
                        TestLog("FAIL", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为1, "
                                            f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为0")
                    result = True
            if not result:
                TestLog("FAIL", "", f"期望结果：读取到故障码 {dtc_select}, "
                                    f"实际结果：没有读取到故障码 {dtc_select}")

            TestLog("INFO", "Step5", f"恢复故障DTC(0x{dtc_select})，等待故障恢复时间: {wait_time_s:.1f}s")
            check_and_recovery_env_simulator(item.MonitorMessageID)
            sim.crc_e2e_fault(False, item.MonitorMessageID, item.Type,
                              dlc=item.MonitorMessageDLC, cycle_ms=item.MonitorMessagePeriod or 100,
                              data=item.ValidPayload, is_canfd=item.FDF,
                              is_e2e=item.IsContainE2E, data_id=item.DataID)
            wait_time_s = (item.PassTime or 1000) / 1000
            time.sleep(wait_time_s)

            TestLog("INFO", "Step6", "发送 19 02 FF 请求读取DTC信息")
            success, resp = service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02],
                                             expect_str="肯定响应(59 02)", func_req=False, DTCStatusMask=0xFF)
            if not success:
                TestLog("FAIL", "", "未收到肯定响应")
                return

            dtc_list = get_dtc_list_from_19_resp(resp)
            TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")
            if len(dtc_list) == 0:
                TestLog("FAIL", "", "未读取到任何 DTC，故障注入可能未生效")

            result = False
            for dtc_info in dtc_list:
                dtc = dtc_info['dtc']
                status = dtc_info['status']
                dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"
                if dtc_str == dtc_select:
                    TestLog("INFO", "", f"读取到故障码 {dtc_select}")
                    if (status & 0x01) == 0 and (status & 0x08) != 0:
                        TestLog("PASS", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为0，bit3置为1, "
                                            f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为0，bit3置为1")
                    else:
                        TestLog("FAIL", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为0，bit3置为1, "
                                            f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为{status & 0x01}，bit3置为{(status >> 3) & 1}")
                    result = True
            if not result:
                TestLog("FAIL", "", f"期望结果：读取到故障码 {dtc_select}, "
                                    f"实际结果：没有读取到故障码 {dtc_select}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        env_simulator.stop()
        sim.stop_all_timer()
        if node:
            node.close()


def test_TG1_TC8_TC10_SC1_GlobalSnapshotDataCheck_Busoff():
    """
    全局快照数据检查
    """
    import time
    case_name = "全局快照数据检查"

    node = get_can_node()
    sim = FaultSimulator()
    EXPECTED_VOLTAGE = 13.5
    EXPECTED_SPEED = 90.0
    EXPECTED_ODOMETER = 100

    try:
        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "", "使用0x14服务清除所有DTC")
        clear_dtc(node)
        time.sleep(1)

        env_simulator.start(
            voltage=EXPECTED_VOLTAGE,
            speed=EXPECTED_SPEED,
            odometer=EXPECTED_ODOMETER,
            year=2025, month=8, day=8,
            hour=8, minute=8, second=8
        )
        TestLog("INFO", "",
                f"发送模拟信号: 电压={EXPECTED_VOLTAGE}V, 车速={EXPECTED_SPEED}km/h, 里程={EXPECTED_ODOMETER}km, 时间=2025-08-08 08:08:08")
        time.sleep(2)

        for item in P.ExtendedDTCInfo.bus_off.valid_items:
            injected_faults = []

            wait_time_s = 10
            TestLog("INFO", "TC8", "")
            TestLog("INFO", "Step1", "模拟产生故障_Busoff")
            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x","")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{wait_time_s} ms")

            sim.busoff_fault(True)
            injected_faults.append(('lost', item))

            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            sim.busoff_fault(False)
            time.sleep(wait_time_s)

            success, first_snapshot = read_dtc_and_global_snapshot(node, dtc_select)
            if not success or first_snapshot is None:
                return

            TestLog("INFO", "", "验证快照数据与仿真信号一致")
            snapshot_store.compare_to_expect(first_snapshot, EXPECTED_VOLTAGE, EXPECTED_SPEED, EXPECTED_ODOMETER, "2025-08-08 08:08:08")

            TestLog("INFO", "TC10", "")
            TestLog("INFO", "Step1", "改变ECU获取的全局快照数据的数值 (电压、里程、电源模式、时间等)，模拟产生故障")
            env_simulator.start(
                voltage=14.5,  # 改变电压值 (从 13.5V 改为 14.5V)
                speed=120.0,  # 改变车速值
                odometer=200,  # 改变里程值 (从 100km 改为 200km)
                year=2024, month=6, day=6,
                hour=6, minute=6, second=6
            )
            TestLog("INFO", "", "发送模拟信号: 电压=14.5V, 里程=200km， 车速=120km/h, 时间=2024-06-06 06:06:06")
            time.sleep(2)

            wait_time_s = 10
            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{wait_time_s} ms")
            sim.busoff_fault(True)
            injected_faults.append(('lost', item))

            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            sim.busoff_fault(False)
            time.sleep(wait_time_s)

            success, third_snapshot = read_dtc_and_global_snapshot(node, dtc_select)
            if not success or third_snapshot is None:
                return

            TestLog("INFO", "", "比对首次快照与恢复后重新制造故障后的快照")
            snapshot_store.save("first_snapshot", first_snapshot)
            is_match = snapshot_store.compare("first_snapshot", third_snapshot)

            if is_match:
                TestLog("PASS", "", f"期望结果：重新制造故障后全局快照保持不变，DTC: 0x{dtc_select}"
                                    f"实际结果：重新制造故障后全局快照保持不变，DTC: 0x{dtc_select}")
            else:
                TestLog("FAIL", "", f"期望结果：重新制造故障后全局快照保持不变，DTC: 0x{dtc_select}"
                                    f"实际结果：重新制造故障后全局快照保持发生变化，DTC: 0x{dtc_select}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        sim.stop_all_timer()
        env_simulator.stop()
        if node:
            node.close()

def test_TG1_TC8_TC10_SC2_GlobalSnapshotDataCheck_LowVoltage():
    """
    全局快照数据检查
    """
    import time
    case_name = "全局快照数据检查"

    node = get_can_node()
    sim = FaultSimulator()
    EXPECTED_VOLTAGE = 13.5
    EXPECTED_SPEED = 90.0
    EXPECTED_ODOMETER = 100

    try:
        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "", "使用0x14服务清除所有DTC")
        clear_dtc(node)
        time.sleep(1)

        env_simulator.start(
            voltage=EXPECTED_VOLTAGE,
            speed=EXPECTED_SPEED,
            odometer=EXPECTED_ODOMETER,
            year=2025, month=8, day=8,
            hour=8, minute=8, second=8
        )
        TestLog("INFO", "",
                f"发送模拟信号: 电压={EXPECTED_VOLTAGE}V, 车速={EXPECTED_SPEED}km/h, 里程={EXPECTED_ODOMETER}km, 时间=2025-08-08 08:08:08")
        time.sleep(2)

        for item in P.ExtendedDTCInfo.voltage.valid_items:
            if "低压" not in item.Notes:
                continue

            injected_faults = []

            wait_time_s = 10
            TestLog("INFO", "TC8", "")
            TestLog("INFO", "Step1", "模拟产生故障_低压")
            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x","")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{wait_time_s} ms")
            ctx.power_ctrl.set_voltage(P.TpInfo.LowVoltage)
            operation_after_low_voltage()
            EXPECTED_VOLTAGE = P.TpInfo.LowVoltage

            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            success, first_snapshot = read_dtc_and_global_snapshot(node, dtc_select)
            if not success or first_snapshot is None:
                return

            TestLog("INFO", "", "验证快照数据与仿真信号一致")
            snapshot_store.compare_to_expect(first_snapshot, EXPECTED_VOLTAGE, EXPECTED_SPEED, EXPECTED_ODOMETER, "2025-08-08 08:08:08")

            TestLog("INFO", "TC9", "")
            TestLog("INFO", "Step1", f"恢复故障DTC(0x{dtc_select})，等待故障恢复时间: {wait_time_s:.1f}s")
            ctx.power_ctrl.set_voltage(P.CANInfo.Vnormal)
            time.sleep(wait_time_s)

            success, second_snapshot = read_dtc_and_global_snapshot(node, dtc_select)
            if not success or second_snapshot is None:
                return

            TestLog("INFO", "", "比对首次快照与恢复后快照")
            snapshot_store.save("first_snapshot", first_snapshot)
            is_match = snapshot_store.compare("first_snapshot", second_snapshot)

            if is_match:
                TestLog("PASS", "", f"期望结果：故障恢复后全局快照保持不变，DTC: 0x{dtc_select}"
                                    f"实际结果：故障恢复后全局快照保持不变，DTC: 0x{dtc_select}")
            else:
                TestLog("FAIL", "", f"期望结果：故障恢复后全局快照保持不变，DTC: 0x{dtc_select}"
                                    f"实际结果：故障恢复后全局快照保持发生变化，DTC: 0x{dtc_select}")

            TestLog("INFO", "TC10", "")
            TestLog("INFO", "Step1", "改变ECU获取的全局快照数据的数值 (电压、里程、电源模式、时间等)，模拟产生故障")
            env_simulator.start(
                voltage=14.5,  # 改变电压值 (从 13.5V 改为 14.5V)
                speed=120.0,  # 改变车速值
                odometer=200,  # 改变里程值 (从 100km 改为 200km)
                year=2024, month=6, day=6,
                hour=6, minute=6, second=6
            )
            TestLog("INFO", "", "发送模拟信号: 电压=14.5V, 里程=200km， 车速=120km/h, 时间=2024-06-06 06:06:06")
            time.sleep(2)

            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{wait_time_s} ms")
            ctx.power_ctrl.set_voltage(P.TpInfo.LowVoltage)
            operation_after_low_voltage()

            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            success, third_snapshot = read_dtc_and_global_snapshot(node, dtc_select)
            if not success or third_snapshot is None:
                return

            TestLog("INFO", "", "比对首次快照与恢复后重新制造故障后的快照")
            snapshot_store.save("first_snapshot", first_snapshot)
            is_match = snapshot_store.compare("first_snapshot", third_snapshot)

            if is_match:
                TestLog("PASS", "", f"期望结果：重新制造故障后全局快照保持不变，DTC: 0x{dtc_select}"
                                    f"实际结果：重新制造故障后全局快照保持不变，DTC: 0x{dtc_select}")
            else:
                TestLog("FAIL", "", f"期望结果：重新制造故障后全局快照保持不变，DTC: 0x{dtc_select}"
                                    f"实际结果：重新制造故障后全局快照保持发生变化，DTC: 0x{dtc_select}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        sim.stop_all_timer()
        env_simulator.stop()
        if node:
            node.close()

def test_TG1_TC8_TC10_SC3_GlobalSnapshotDataCheck_Lost():
    """
    全局快照数据检查
    """
    import time
    case_name = "全局快照数据检查"

    node = get_can_node()
    sim = FaultSimulator()
    EXPECTED_VOLTAGE = 13.5
    EXPECTED_SPEED = 90.0
    EXPECTED_ODOMETER = 100
    try:
        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "", "使用0x14服务清除所有DTC")
        clear_dtc(node)
        time.sleep(1)

        env_simulator.start(
            voltage=EXPECTED_VOLTAGE,
            speed=EXPECTED_SPEED,
            odometer=EXPECTED_ODOMETER,
            year=2025, month=8, day=8,
            hour=8, minute=8, second=8
        )
        TestLog("INFO", "",
                f"发送模拟信号: 电压={EXPECTED_VOLTAGE}V, 车速={EXPECTED_SPEED}km/h, 里程={EXPECTED_ODOMETER}km, 时间=2025-08-08 08:08:08")
        time.sleep(2)

        for item in P.ExtendedDTCInfo.lost_communication.valid_items:
            injected_faults = []

            TestLog("INFO", "TC8", "")
            TestLog("INFO", "Step1", "模拟产生故障_丢失通讯")
            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{item.PassTime} ms")
            sim.lost_comm_fault(True, item.MonitorMessageID)
            injected_faults.append(('lost', item))

            wait_time_s = (item.LostTime or 5000) / 1000
            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            success, first_snapshot = read_dtc_and_global_snapshot(node, dtc_select)
            if not success or first_snapshot is None:
                return

            TestLog("INFO", "", "验证快照数据与仿真信号一致")
            snapshot_store.compare_to_expect(first_snapshot, EXPECTED_VOLTAGE, EXPECTED_SPEED, EXPECTED_ODOMETER, "2025-08-08 08:08:08")

            TestLog("INFO", "TC9", "")
            check_and_recovery_env_simulator(item.MonitorMessageID)
            TestLog("INFO", "Step1", f"恢复故障DTC(0x{dtc_select})，等待故障恢复时间: {wait_time_s:.1f}s")
            sim.lost_comm_fault(False, item.MonitorMessageID, dlc=item.MonitorMessageDLC,
                                cycle_ms=item.MonitorMessagePeriod or 100, is_canfd=item.FDF)
            wait_time_s = (item.PassTime or 1000) / 1000
            time.sleep(wait_time_s)

            success, second_snapshot = read_dtc_and_global_snapshot(node, dtc_select)
            if not success or second_snapshot is None:
                return

            TestLog("INFO", "", "比对首次快照与恢复后快照")
            snapshot_store.save("first_snapshot", first_snapshot)
            is_match = snapshot_store.compare("first_snapshot", second_snapshot)

            if is_match:
                TestLog("PASS", "", f"期望结果：故障恢复后全局快照保持不变，DTC: 0x{dtc_select}"
                                    f"实际结果：故障恢复后全局快照保持不变，DTC: 0x{dtc_select}")
            else:
                TestLog("FAIL", "", f"期望结果：故障恢复后全局快照保持不变，DTC: 0x{dtc_select}"
                                    f"实际结果：故障恢复后全局快照保持发生变化，DTC: 0x{dtc_select}")

            TestLog("INFO", "TC10", "")
            TestLog("INFO", "Step1", "改变ECU获取的全局快照数据的数值 (电压、里程、电源模式、时间等)，模拟产生故障")
            env_simulator.start(
                voltage=14.5,  # 改变电压值 (从 13.5V 改为 14.5V)
                speed=120.0,  # 改变车速值
                odometer=200,  # 改变里程值 (从 100km 改为 200km)
                year=2024, month=6, day=6,
                hour=6, minute=6, second=6
            )
            TestLog("INFO", "", "发送模拟信号: 电压=14.5V, 里程=200km， 车速=120km/h, 时间=2024-06-06 06:06:06")
            time.sleep(2)

            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{item.PassTime} ms")
            sim.lost_comm_fault(True, item.MonitorMessageID)
            injected_faults.append(('lost', item))

            wait_time_s = (item.LostTime or 5000) / 1000
            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            success, third_snapshot = read_dtc_and_global_snapshot(node, dtc_select)
            if not success or third_snapshot is None:
                return

            TestLog("INFO", "", "比对首次快照与恢复后重新制造故障后的快照")
            snapshot_store.save("first_snapshot", first_snapshot)
            is_match = snapshot_store.compare("first_snapshot", third_snapshot)

            if is_match:
                TestLog("PASS", "", f"期望结果：重新制造故障后全局快照保持不变，DTC: 0x{dtc_select}"
                                    f"实际结果：重新制造故障后全局快照保持不变，DTC: 0x{dtc_select}")
            else:
                TestLog("FAIL", "", f"期望结果：重新制造故障后全局快照保持不变，DTC: 0x{dtc_select}"
                                    f"实际结果：重新制造故障后全局快照保持发生变化，DTC: 0x{dtc_select}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        sim.stop_all_timer()
        env_simulator.stop()
        if node:
            node.close()


def test_TG1_TC11_TC12_SC1_GlobalSnapshotDataCheck_Busoff():
    """
    全局快照数据检查
    """
    import time
    case_name = "全局快照数据检查"

    node = get_can_node()
    sim = FaultSimulator()
    EXPECTED_VOLTAGE = 13.5
    EXPECTED_SPEED = 90.0
    EXPECTED_ODOMETER = 100

    try:
        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        for item in P.ExtendedDTCInfo.bus_off.valid_items:
            injected_faults = []

            TestLog("INFO", "TC11", "")
            TestLog("INFO", "Step1", "模拟停发全局快照数据的数值（电压、里程信号、电源模式、时间等）")
            env_simulator.stop()

            wait_time_s = 10
            TestLog("INFO", "Step2", "模拟产生故障_Busoff")
            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x","")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{wait_time_s} ms")
            sim.busoff_fault(True)
            injected_faults.append(('lost', item))

            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            sim.busoff_fault(False)
            time.sleep(wait_time_s)

            success, snapshot = read_dtc_and_global_snapshot(node, dtc_select)
            if not success or snapshot is None:
                return

            if snapshot is not None:
                is_default = True
                # if snapshot.voltage not in [0, 0xFF, 0xFFFF, 0xFFFFFF]:
                #     TestLog("INFO", "", f"电压值 {snapshot.voltage}V 非默认值")
                #     is_default = False
                if snapshot.odometer not in [0, 0xFF, 0xFFFF, 0xFFFFFF]:
                    TestLog("INFO", "", f"里程值 {snapshot.odometer}km 非默认值")
                    is_default = False
                if snapshot.speed not in [0, 0xFF, 0xFFFF, 0xFFFFFF]:
                    TestLog("INFO", "", f"车速值 {snapshot.speed}km/h 非默认值")
                    is_default = False
                if snapshot.year not in [0, 0xFF] or snapshot.month not in [0, 0xFF] or snapshot.day not in [0, 0xFF]\
                        or snapshot.hour not in [0, 0xFF] or snapshot.minute not in [0, 0xFF] or snapshot.second not in [0, 0xFF]:
                    TestLog("INFO", "", f"时间 {snapshot.year:04d}-{snapshot.month:02d}-{snapshot.day:02d} "
                                        f" {snapshot.hour:02d}:{snapshot.minute:02d}:{snapshot.second:02d} 非默认值")
                    is_default = False

                if is_default:
                    TestLog("PASS", "", f"期望：快照数据为默认值0x00, 或0xFF，实际：快照数据为默认值0x00, 或0xFF，DTC: {dtc_select}")
                else:
                    TestLog("FAIL", "", f"期望：快照数据为默认值0x00, 或0xFF，实际：快照数据非默认值，DTC: {dtc_select}")
            else:
                TestLog("INFO", "", "快照数据解析失败，可能为空或默认值")

            TestLog("INFO", "TC12", "")
            TestLog("INFO", "Step1", "使用0x14服务清除所有DTC")
            clear_dtc(node)
            time.sleep(1)

            TestLog("INFO", "Step1", "模拟发送全局快照数据的数值（电压、里程信号、电源模式、时间等），模拟产生故障")
            env_simulator.start(
                voltage=EXPECTED_VOLTAGE,
                speed=EXPECTED_SPEED,
                odometer=EXPECTED_ODOMETER,
                year=2025, month=8, day=8,
                hour=8, minute=8, second=8
            )
            TestLog("INFO", "",
                    f"发送模拟信号: 电压={EXPECTED_VOLTAGE}V, 车速={EXPECTED_SPEED}km/h, 里程={EXPECTED_ODOMETER}km, 时间=2025-08-08 08:08:08")
            time.sleep(2)

            wait_time_s = 10
            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{wait_time_s} ms")
            sim.busoff_fault(True)
            injected_faults.append(('lost', item))

            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            sim.busoff_fault(False)
            time.sleep(wait_time_s)

            success, snapshot = read_dtc_and_global_snapshot(node, dtc_select)
            if not success or snapshot is None:
                return

            TestLog("INFO", "", "验证快照数据与仿真信号一致")
            snapshot_store.compare_to_expect(snapshot, EXPECTED_VOLTAGE, EXPECTED_SPEED, EXPECTED_ODOMETER, "2025-08-08 08:08:08")

            TestLog("INFO", "Step5", "模拟发送全局快照数据的信号无效的数值，模拟产生故障")
            env_simulator.start(
                voltage=13.5,
                speed=100.0,
                odometer=100,
                year=2025, month=8, day=8,
                hour=8, minute=61, second=61
            )
            TestLog("INFO", "", "发送模拟信号: 电压=13.5V, 车速=100km/h, 里程=100km, 时间=2025-08-08 08:61:61")
            time.sleep(2)

            wait_time_s = 10
            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{wait_time_s} ms")
            sim.busoff_fault(True)
            injected_faults.append(('lost', item))

            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            sim.busoff_fault(False)
            time.sleep(wait_time_s)

            success, snapshot = read_dtc_and_global_snapshot(node, dtc_select)
            if not success or snapshot is None:
                return

            TestLog("INFO", "", "验证快照中保存的是信号变为无效之前的最后一个有效值")
            snapshot_store.compare_to_expect(snapshot, EXPECTED_VOLTAGE, EXPECTED_SPEED, EXPECTED_ODOMETER, "2025-08-08 08:08:08")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        sim.stop_all_timer()
        env_simulator.stop()
        if node:
            node.close()

def test_TG1_TC11_TC12_SC2_GlobalSnapshotDataCheck_LowVoltage():
    """
    全局快照数据检查
    """
    import time
    case_name = "全局快照数据检查"

    node = get_can_node()
    sim = FaultSimulator()
    EXPECTED_VOLTAGE = 13.5
    EXPECTED_SPEED = 90.0
    EXPECTED_ODOMETER = 100
    is_canfd = P.ProjectInfo.ECUType == 2

    try:
        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        for item in P.ExtendedDTCInfo.voltage.valid_items:
            if "低压" not in item.Notes:
                continue

            TestLog("INFO", "TC11", "")
            TestLog("INFO", "Step1", "模拟停发全局快照数据的数值（电压、里程信号、电源模式、时间等）")
            env_simulator.stop()

            wait_time_s = 10
            TestLog("INFO", "Step2", "模拟产生故障_低压")
            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{wait_time_s} ms")
            ctx.power_ctrl.set_voltage(P.TpInfo.LowVoltage)
            operation_after_low_voltage()

            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            success, snapshot = read_dtc_and_global_snapshot(node, dtc_select)
            if not success or snapshot is None:
                return

            if snapshot is not None:
                is_default = True
                # if snapshot.voltage not in [0, 0xFF, 0xFFFF, 0xFFFFFF]:
                #     TestLog("INFO", "", f"电压值 {snapshot.voltage}V 非默认值")
                #     is_default = False
                if snapshot.odometer not in [0, 0xFF, 0xFFFF, 0xFFFFFF]:
                    TestLog("INFO", "", f"里程值 {snapshot.odometer}km 非默认值")
                    is_default = False
                if snapshot.speed not in [0, 0xFF, 0xFFFF, 0xFFFFFF]:
                    TestLog("INFO", "", f"车速值 {snapshot.speed}km/h 非默认值")
                    is_default = False
                if snapshot.year not in [0, 0xFF] or snapshot.month not in [0, 0xFF] or snapshot.day not in [0, 0xFF]\
                        or snapshot.hour not in [0, 0xFF] or snapshot.minute not in [0, 0xFF] or snapshot.second not in [0, 0xFF]:
                    TestLog("INFO", "", f"时间 {snapshot.year:04d}-{snapshot.month:02d}-{snapshot.day:02d} "
                                        f" {snapshot.hour:02d}:{snapshot.minute:02d}:{snapshot.second:02d} 非默认值")
                    is_default = False

                if is_default:
                    TestLog("PASS", "",
                            f"期望：快照数据为默认值0x00, 或0xFF，实际：快照数据为默认值0x00, 或0xFF，DTC: {dtc_select}")
                else:
                    TestLog("FAIL", "",
                            f"期望：快照数据为默认值0x00, 或0xFF，实际：快照数据非默认值，DTC: {dtc_select}")
            else:
                TestLog("INFO", "", "快照数据解析失败，可能为空或默认值")

            TestLog("INFO", "TC12", "")
            ctx.power_ctrl.set_voltage(P.CANInfo.Vnormal)
            time.sleep(wait_time_s)
            TestLog("INFO", "Step1", "使用0x14服务清除所有DTC")
            clear_dtc(node)
            time.sleep(1)

            TestLog("INFO", "Step2", "模拟发送全局快照数据的数值（电压、里程信号、电源模式、时间等），模拟产生故障")
            env_simulator.start(
                voltage=EXPECTED_VOLTAGE,
                speed=EXPECTED_SPEED,
                odometer=EXPECTED_ODOMETER,
                year=2025, month=8, day=8,
                hour=8, minute=8, second=8
            )
            TestLog("INFO", "",
                    f"发送模拟信号: 电压={EXPECTED_VOLTAGE}V, 车速={EXPECTED_SPEED}km/h, 里程={EXPECTED_ODOMETER}km, 时间=2025-08-08 08:08:08")
            time.sleep(2)

            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{wait_time_s} ms")
            ctx.power_ctrl.set_voltage(P.TpInfo.LowVoltage)
            operation_after_low_voltage()
            EXPECTED_VOLTAGE = P.TpInfo.LowVoltage

            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            success, snapshot = read_dtc_and_global_snapshot(node, dtc_select)
            if not success or snapshot is None:
                return

            TestLog("INFO", "", "验证快照数据与仿真信号一致")
            snapshot_store.compare_to_expect(snapshot, EXPECTED_VOLTAGE, EXPECTED_SPEED, EXPECTED_ODOMETER, "2025-08-08 08:08:08")

            TestLog("INFO", "Step5", "模拟发送全局快照数据的信号无效的数值，模拟产生故障")
            env_simulator.start(
                voltage=13.5,
                speed=100.0,
                odometer=100,
                year=2025, month=8, day=8,
                hour=8, minute=61, second=61
            )
            TestLog("INFO", "", "发送模拟信号: 电压=13.5V, 车速=100km/h, 里程=100km, 时间=2025-08-08 08:61:61")

            TestLog("INFO", "", "模拟发送无效的powermode信号")
            msgs = env_simulator._build_powermode_msg(P.CANInfo.PowerModeMsgID, env_simulator._POWERMODE_OFF, is_canfd)
            env_simulator._send_can_messages(msgs)
            time.sleep(2)
            TestLog("INFO", "", "恢复电源状态为RUN")
            msgs = env_simulator._build_powermode_msg(P.CANInfo.PowerModeMsgID, env_simulator._POWERMODE_RUN, is_canfd)
            env_simulator._send_can_messages(msgs)
            time.sleep(2)

            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{wait_time_s} ms")
            ctx.power_ctrl.set_voltage(P.TpInfo.LowVoltage)
            operation_after_low_voltage()

            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            success, snapshot = read_dtc_and_global_snapshot(node, dtc_select)
            if not success or snapshot is None:
                return

            TestLog("INFO", "", "验证快照中保存的是信号变为无效之前的最后一个有效值")
            snapshot_store.compare_to_expect(snapshot, EXPECTED_VOLTAGE, EXPECTED_SPEED, EXPECTED_ODOMETER, "2025-08-08 08:08:08")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        sim.stop_all_timer()
        env_simulator.stop()
        if node:
            node.close()

def test_TG1_TC11_TC12_SC3_GlobalSnapshotDataCheck_Lost():
    """
    全局快照数据检查
    """
    import time
    case_name = "全局快照数据检查"

    node = get_can_node()
    sim = FaultSimulator()
    EXPECTED_VOLTAGE = 13.5
    EXPECTED_SPEED = 90.0
    EXPECTED_ODOMETER = 100

    try:
        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        for item in P.ExtendedDTCInfo.lost_communication.valid_items:
            injected_faults = []

            TestLog("INFO", "TC11", "")
            TestLog("INFO", "Step1", "模拟停发全局快照数据的数值（电压、里程信号、电源模式、时间等）")
            env_simulator.stop()

            TestLog("INFO", "Step2", "模拟产生故障_丢失通讯")
            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
            TestLog("INFO", "", f"目标报文0x{item.MonitorMessageID:X}已随全局快照数据源停发，丢失通信故障已模拟")
            # sim.lost_comm_fault(True, item.MonitorMessageID)
            injected_faults.append(('lost', item))

            wait_time_s = (item.LostTime or 5000) / 1000
            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            success, snapshot = read_dtc_and_global_snapshot(node, dtc_select)
            if not success or snapshot is None:
                return

            if snapshot is not None:
                is_default = True
                # if snapshot.voltage not in [0, 0xFF, 0xFFFF, 0xFFFFFF]:
                #     TestLog("INFO", "", f"电压值 {snapshot.voltage}V 非默认值")
                #     is_default = False
                if snapshot.odometer not in [0, 0xFF, 0xFFFF, 0xFFFFFF]:
                    TestLog("INFO", "", f"里程值 {snapshot.odometer}km 非默认值")
                    is_default = False
                if snapshot.speed not in [0, 0xFF, 0xFFFF, 0xFFFFFF]:
                    TestLog("INFO", "", f"车速值 {snapshot.speed}km/h 非默认值")
                    is_default = False
                if snapshot.year not in [0, 0xFF] or snapshot.month not in [0, 0xFF] or snapshot.day not in [0, 0xFF]\
                        or snapshot.hour not in [0, 0xFF] or snapshot.minute not in [0, 0xFF] or snapshot.second not in [0, 0xFF]:
                    TestLog("INFO", "", f"时间 {snapshot.year:04d}-{snapshot.month:02d}-{snapshot.day:02d} "
                                        f" {snapshot.hour:02d}:{snapshot.minute:02d}:{snapshot.second:02d} 非默认值")
                    is_default = False

                if is_default:
                    TestLog("PASS", "",
                            f"期望：快照数据为默认值0x00, 或0xFF，实际：快照数据为默认值0x00, 或0xFF，DTC: {dtc_select}")
                else:
                    TestLog("FAIL", "",
                            f"期望：快照数据为默认值0x00, 或0xFF，实际：快照数据非默认值，DTC: {dtc_select}")
            else:
                TestLog("INFO", "", "快照数据解析失败，可能为空或默认值")

            TestLog("INFO", "TC12", "")
            sim.lost_comm_fault(False, item.MonitorMessageID, dlc=item.MonitorMessageDLC,
                                cycle_ms=item.MonitorMessagePeriod or 100, is_canfd=item.FDF)
            wait_time_s = (item.PassTime or 1000) / 1000
            time.sleep(wait_time_s)
            TestLog("INFO", "Step1", "使用0x14服务清除所有DTC")
            clear_dtc(node)
            time.sleep(1)

            TestLog("INFO", "Step2", "模拟发送全局快照数据的数值（电压、里程信号、电源模式、时间等），模拟产生故障")
            env_simulator.start(
                voltage=EXPECTED_VOLTAGE,
                speed=EXPECTED_SPEED,
                odometer=EXPECTED_ODOMETER,
                year=2025, month=8, day=8,
                hour=8, minute=8, second=8
            )
            TestLog("INFO", "", f"发送模拟信号: 电压={EXPECTED_VOLTAGE}V, 车速={EXPECTED_SPEED}km/h, 里程={EXPECTED_ODOMETER}km, 时间=2025-08-08 08:08:08")
            time.sleep(2)

            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{item.PassTime} ms")
            sim.lost_comm_fault(True, item.MonitorMessageID)
            injected_faults.append(('lost', item))

            wait_time_s = (item.LostTime or 5000) / 1000
            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            success, snapshot = read_dtc_and_global_snapshot(node, dtc_select)
            if not success or snapshot is None:
                return

            TestLog("INFO", "", "验证快照数据与仿真信号一致")
            snapshot_store.compare_to_expect(snapshot, EXPECTED_VOLTAGE, EXPECTED_SPEED, EXPECTED_ODOMETER, "2025-08-08 08:08:08")

            TestLog("INFO", "Step5", "模拟发送全局快照数据的信号无效的数值，模拟产生故障")
            env_simulator.start(
                voltage=13.5,
                speed=100.0,
                odometer=100,
                year=2025, month=8, day=8,
                hour=8, minute=61, second=61
            )
            TestLog("INFO", "", "发送模拟信号: 电压=13.5V, 车速=100km/h, 里程=100km, 时间=2025-08-08 08:61:61")
            time.sleep(2)

            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{item.LostTime} ms")
            sim.lost_comm_fault(True, item.MonitorMessageID)
            injected_faults.append(('lost', item))

            wait_time_s = (item.LostTime or 5000) / 1000
            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            success, snapshot = read_dtc_and_global_snapshot(node, dtc_select)
            if not success or snapshot is None:
                return

            TestLog("INFO", "", "验证快照中保存的是信号变为无效之前的最后一个有效值")
            snapshot_store.compare_to_expect(snapshot, EXPECTED_VOLTAGE, EXPECTED_SPEED, EXPECTED_ODOMETER, "2025-08-08 08:08:08")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        sim.stop_all_timer()
        env_simulator.stop()
        if node:
            node.close()


def test_TG1_TC13_TC21_ExtendDataCheck():
    """
    诊断故障代码老化机制检查
    """
    import time
    case_name = "诊断故障代码老化机制检查"

    node = get_can_node()
    sim = FaultSimulator()

    try:
        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "", "选择进行测试的DTC")
        fault_type, dtc_select = select_fault_type(node, sim)
        if dtc_select is None:
            TestLog("WARNING", "", "没有合适的故障码进行测试，请检查配置")
            return

        tc13(node, sim, fault_type)
        tc14(node, sim, fault_type, dtc_select)
        tc16(node, sim, fault_type)
        tc17(node, sim, fault_type, dtc_select)
        tc18(node, fault_type, dtc_select)
        tc19(node, fault_type, dtc_select)
        tc20(node, fault_type, dtc_select)
        tc21(node, fault_type, dtc_select)


    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        sim.stop_all_timer()
        env_simulator.stop()
        if node:
            node.close()


def test_TG1_TC13_and_TC15_ExtendDataCheck():
    """
    诊断故障代码老化机制检查
    """
    import time
    case_name = "诊断故障代码老化机制检查"

    node = get_can_node()
    sim = FaultSimulator()

    try:
        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "", "选择进行测试的DTC")
        fault_type, dtc_select = select_fault_type(node, sim)
        if dtc_select is None:
            TestLog("WARNING", "", "没有合适的故障码进行测试，请检查配置")
            return

        tc13(node, sim, fault_type)
        tc15(node, sim, fault_type, dtc_select)

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        sim.stop_all_timer()
        env_simulator.stop()
        if node:
            node.close()

def test_TG1_TC22_OtherParentDTCCheck():
    """
    父子故障场景检查
    """
    import time
    case_name = "父子故障场景检查"

    node = get_can_node()
    sim = FaultSimulator()
    injected_faults = []

    try:
        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "Step1", "使用0x14服务清除所有DTC")
        clear_dtc(node)
        time.sleep(1)

        TestLog("INFO", "Step1", "模拟产生其它父诊断故障代码（除过压、欠压和BusOff）")
        # TODO 父故障？
        dtc_select = "112233"
        TestLog("INFO", "Step2", "发送 19 02 FF 请求读取DTC信息")
        success, status = find_DTC_by_status_mask(node, 0xFF, dtc_select)
        if not success:
            TestLog("FAIL", "", "未查询到测试的DTC")
            return

        TestLog("INFO", "Step2", "模拟产生子故障")
        TestLog("INFO", "", "模拟产生节点丢失故障")
        # 节点丢失故障
        for item in P.ExtendedDTCInfo.lost_communication.valid_items:
            injected_faults = []

            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC相关的报文并等待{item.PassTime} ms")
            sim.lost_comm_fault(True, item.MonitorMessageID)
            injected_faults.append(('lost', item))

            wait_time_s = (item.LostTime or 5000) / 1000
            TestLog("INFO", "Step3", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            TestLog("INFO", "Step4", "发送 19 02 FF 请求读取DTC信息")
            success, resp = service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02],
                                             expect_str="肯定响应(59 02)", func_req=False, DTCStatusMask=0xFF)
            if not success:
                TestLog("FAIL", "", "未收到肯定响应")
                return

            dtc_list = get_dtc_list_from_19_resp(resp)
            TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

            result = False
            for dtc_info in dtc_list:
                dtc = dtc_info['dtc']
                status = dtc_info['status']
                dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"
                if dtc_str == dtc_select:
                    TestLog("INFO", "", f"读取到故障码 {dtc_select}")
                    if (status & 0x01) == 0:
                        TestLog("PASS", "", f"期望结果：未读出当前子诊断故障码, "
                                            f"实际结果：未读出当前子诊断故障码")
                    else:
                        TestLog("FAIL", "", f"期望结果：未读出当前子诊断故障码, "
                                            f"实际结果：读出当前子诊断故障码")
                    result = True
            if not result:
                TestLog("PASS", "", f"期望结果：未读出当前子诊断故障码 {dtc_select}, "
                                    f"实际结果：未读出当前子诊断故障码 {dtc_select}")
            break

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        TestLog("INFO", "清理", "恢复所有注入的故障")
        sim.recover_dtc_faults(injected_faults)
        env_simulator.stop()
        if node:
            node.close()


def test_TG1_TC23_QuietModeDTCCheck():
    """
    安静模式DTC记录检查
    """
    import time
    case_name = "安静模式检查"

    node = get_can_node()
    sim = FaultSimulator()
    injected_faults = []

    try:
        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "Step1", "发送 10 02 进入编程会话（安静模式）")
        TestLog("INFO", "", "期望响应: 06 50 02 00 32 01 F4 00")

        TestLog("INFO", "扩展会话", "10 03")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
            return
        tester_present_start(node)

        TestLog("INFO", "检查编程条件", "31 01 02 03")
        resp = node.Service_0x31_RoutineControl(0x01, 0x0203)
        status, msg = check_resp(resp, [0x71, 0x01, 0x02, 0x03, 0x00], "肯定响应(71 01 02 03 00)")
        if not status: return False, f"预编程阶段失败: {msg}"

        TestLog("INFO", "", "使用0x14服务清除所有DTC")
        clear_dtc(node)
        time.sleep(1)

        TestLog("INFO", "编程会话", "10 02")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"):
            return

        dtc_select = ""
        TestLog("INFO", "Step2", "模拟目标诊断故障代码_低压")
        for item in P.ExtendedDTCInfo.voltage.valid_items:
            if "低压" not in item.Notes:
                continue

            wait_time_s = 10
            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{wait_time_s} ms")
            ctx.power_ctrl.set_voltage(P.TpInfo.LowVoltage)
            operation_after_low_voltage()

            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            TestLog("INFO", "Step3", "取消模拟诊断故障代码_低压")
            TestLog("INFO", "", f"恢复故障DTC(0x{dtc_select})，等待故障恢复时间: {wait_time_s:.1f}s")
            ctx.power_ctrl.set_voltage(P.CANInfo.Vnormal)
            time.sleep(wait_time_s)
            break

        tester_present_stop()
        TestLog("INFO", "Step4", "发送 11 01 复位ECU")
        hard_reset(node)
        time.sleep(5)

        TestLog("INFO", "Step5", "发送 19 02 FF 请求读取所有DTC")
        success, resp = service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02],
                                         expect_str="肯定响应(59 02)", func_req=False, DTCStatusMask=0xFF)
        if not success:
            TestLog("FAIL", "", "未收到肯定响应")
            return

        dtc_list = get_dtc_list_from_19_resp(resp)
        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        result = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"
            if dtc_str == dtc_select:
                TestLog("FAIL", "", f"期望结果：未读出低压诊断故障码 {dtc_select}, "
                                    f"实际结果：读出低压诊断故障码 {dtc_select}")
                result = True
        if not result:
            TestLog("PASS", "", f"期望结果：未读出低压诊断故障码 {dtc_select}, "
                                f"实际结果：未读出低压诊断故障码 {dtc_select}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        TestLog("INFO", "清理", "恢复所有注入的故障")
        sim.recover_dtc_faults(injected_faults)
        env_simulator.stop()
        if node:
            node.close()


def test_TG1_TC24_CrankUndervoltageDTCCheck():
    """
    发动机起动场景检查
    """
    import time
    case_name = "发动机起动场景检查"
    node = get_can_node()
    sim = FaultSimulator()
    injected_faults = []

    try:
        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "", "使用0x14服务清除所有DTC")
        clear_dtc(node)
        time.sleep(1)

        TestLog("INFO", "Step1", "模拟接收发送机发送Crank信号")
        sim_engine_rpm_msg(True)
        dtc_enable_conditions(True, env_simulator._POWERMODE_CRANK)
        time.sleep(2)

        TestLog("INFO", "Step2", "模拟目标诊断故障代码_低压")
        for item in P.ExtendedDTCInfo.voltage.valid_items:
            if "低压" not in item.Notes:
                continue

            wait_time_s = 10
            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{wait_time_s} ms")
            ctx.power_ctrl.set_voltage(P.TpInfo.LowVoltage)
            operation_after_low_voltage()

            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            TestLog("INFO", "Step3", "发送 19 02 FF 请求读取所有DTC")
            success, resp = service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02],
                                             expect_str="肯定响应(59 02)", func_req=False, DTCStatusMask=0xFF)
            if not success:
                TestLog("FAIL", "", "未收到肯定响应")
                return

            dtc_list = get_dtc_list_from_19_resp(resp)
            TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

            result = False
            for dtc_info in dtc_list:
                dtc = dtc_info['dtc']
                status = dtc_info['status']
                dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"
                if dtc_str == dtc_select:
                    TestLog("FAIL", "", f"期望结果：未读出低压诊断故障码 {dtc_select}, "
                                        f"实际结果：读出低压诊断故障码 {dtc_select}")
                    result = True
            if not result:
                TestLog("PASS", "", f"期望结果：未读出低压诊断故障码 {dtc_select}, "
                                    f"实际结果：未读出低压诊断故障码 {dtc_select}")
            break

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        TestLog("INFO", "清理", "恢复所有注入的故障")
        env_simulator.stop()
        if node:
            node.close()

def test_TG1_TC25_DTCConfigDisableCheck():
    """
    DTC配置禁用检查
    """
    import time
    case_name = "DTC配置禁用检查"

    node = get_can_node()
    sim = FaultSimulator()
    injected_faults = []

    try:
        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "Step1", "将诊断故障代码配置标识符对应位设置为0")

        TestLog("INFO", "扩展会话", "10 03")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
            return
        tester_present_start(node)

        TestLog("INFO", "关闭DTC", "85 02")
        resp = node.Service_0x85_ControlDTCSetting(0x02, func_req=True)
        status, msg = check_resp(resp, [0xC5, 0x02], "肯定响应(C5 02)")
        if not status:
            return

        TestLog("INFO", "", "使用0x14服务清除所有DTC")
        clear_dtc(node)
        time.sleep(1)

        TestLog("INFO", "Step2", f"发送 22 01 00 读取DTC配置")
        service_22_check(node, 0x0100, expect_data=[0x62, 0x01, 0x00], expect_str="肯定响应62 01 00")

        TestLog("INFO", "Step3", "模拟目标诊断故障代码_低压")
        for item in P.ExtendedDTCInfo.voltage.valid_items:
            if "低压" not in item.Notes:
                continue

            wait_time_s = 10
            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{wait_time_s} ms")
            ctx.power_ctrl.set_voltage(P.TpInfo.LowVoltage)
            operation_after_low_voltage()

            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            TestLog("INFO", "Step4", "发送 19 02 FF 请求读取所有DTC")
            success, resp = service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02],
                                             expect_str="肯定响应(59 02)", func_req=False, DTCStatusMask=0xFF)
            if not success:
                TestLog("FAIL", "", "未收到肯定响应")
                return

            dtc_list = get_dtc_list_from_19_resp(resp)
            TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

            result = False
            for dtc_info in dtc_list:
                dtc = dtc_info['dtc']
                status = dtc_info['status']
                dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"
                if dtc_str == dtc_select:
                    TestLog("FAIL", "", f"期望结果：未读出低压诊断故障码 {dtc_select}, "
                                        f"实际结果：读出低压诊断故障码 {dtc_select}")
                    result = True
            if not result:
                TestLog("PASS", "", f"期望结果：未读出低压诊断故障码 {dtc_select}, "
                                    f"实际结果：未读出低压诊断故障码 {dtc_select}")
            break


    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        TestLog("INFO", "清理", "恢复所有注入的故障")
        sim.recover_dtc_faults(injected_faults)
        env_simulator.stop()
        tester_present_stop()
        if node:
            node.close()


def test_TG1_TC26_DTCConfigDisableCheck():
    """
    DTC配置启用检查
    """
    import time
    case_name = "DTC配置启用检查"

    node = get_can_node()
    sim = FaultSimulator()
    injected_faults = []

    try:
        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "Step1", "将诊断故障代码配置标识符对应位设置为1")

        TestLog("INFO", "扩展会话", "10 03")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
            return
        tester_present_start(node)

        TestLog("INFO", "关闭DTC", "85 01")
        resp = node.Service_0x85_ControlDTCSetting(0x01, func_req=True)
        status, msg = check_resp(resp, [0xC5, 0x01], "肯定响应(C5 01)")
        if not status:
            return

        TestLog("INFO", "", "使用0x14服务清除所有DTC")
        clear_dtc(node)
        time.sleep(1)

        TestLog("INFO", "Step2", f"发送 22 01 00 读取DTC配置")
        service_22_check(node, 0x0100, expect_data=[0x62, 0x01, 0x00], expect_str="肯定响应62 01 00")

        TestLog("INFO", "Step3", "模拟目标诊断故障代码_低压")
        for item in P.ExtendedDTCInfo.voltage.valid_items:
            if "低压" not in item.Notes:
                continue

            wait_time_s = 10
            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{wait_time_s} ms")
            ctx.power_ctrl.set_voltage(P.TpInfo.LowVoltage)
            operation_after_low_voltage()

            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            TestLog("INFO", "Step4", "发送 19 02 FF 请求读取所有DTC")
            success, resp = service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02],
                                             expect_str="肯定响应(59 02)", func_req=False, DTCStatusMask=0xFF)
            if not success:
                TestLog("FAIL", "", "未收到肯定响应")
                return

            dtc_list = get_dtc_list_from_19_resp(resp)
            TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")
            if len(dtc_list) == 0:
                TestLog("FAIL", "", "未读取到任何 DTC，故障注入可能未生效")

            result = False
            for dtc_info in dtc_list:
                dtc = dtc_info['dtc']
                status = dtc_info['status']
                dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"
                if dtc_str == dtc_select:
                    TestLog("INFO", "", f"读取到故障码 {dtc_select}")
                    if (status & 0x01) != 0:
                        TestLog("PASS", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为1, "
                                            f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为1")
                    else:
                        TestLog("FAIL", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为1, "
                                            f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为0")
                    result = True
            if not result:
                TestLog("FAIL", "", f"期望结果：读取到故障码 {dtc_select}, "
                                    f"实际结果：没有读取到故障码 {dtc_select}")
            break


    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        TestLog("INFO", "清理", "恢复所有注入的故障")
        sim.recover_dtc_faults(injected_faults)
        env_simulator.stop()
        tester_present_stop()
        if node:
            node.close()

def test_TG1_TC27_TC29_MaxDTCNumberCheck():
    """
    最大诊断故障代码条目数检查
    """
    import time
    case_name = "最大诊断故障代码条目数检查"

    node = get_can_node()
    sim = FaultSimulator()
    injected_faults = []

    try:
        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "TC27", "")
        TestLog("INFO", "Step1", "逐个模拟产生N个目标诊断故障代码的失效条件")
        simulated_dtc = inject_all_fault(node, sim)

        TestLog("INFO", "Step3", "发送 19 04/06 请求读取故障码的快照数据和扩展数据")
        for dtc_select in simulated_dtc:
            TestLog("INFO", "", "")
            success, snapshot = read_global_snapshot(node, dtc_select)
            if not success or snapshot is None:
                TestLog("FAIL", "", "未获取到快照数据")

            success, occurrence_counter, pending_counter, aged_counter, ageing_counter = read_extend_data(node, dtc_select)
            if not success:
                TestLog("FAIL", "", "未获取到扩展数据")

        TestLog("INFO", "TC28", "")
        time.sleep(5)
        TestLog("INFO", "Step1", "发送 11 01 复位ECU")
        hard_reset(node)
        time.sleep(5)

        TestLog("INFO", "Step2", "发送 19 02 09 请求读取DTC信息")
        success, resp = service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02],
                                         expect_str="肯定响应(59 02)", func_req=False, DTCStatusMask=0x09)
        if not success:
            TestLog("FAIL", "", "未收到肯定响应")
            return

        dtc_list = get_dtc_list_from_19_resp(resp)
        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")
        if len(dtc_list) == 0:
            TestLog("FAIL", "", "未读取到任何 DTC")
            return

        if len(dtc_list) >= len(simulated_dtc):
            TestLog("PASS", "",
                    f"期望结果：复位后读取的DTC总数>=复位前制造的DTC数量<br>"
                    f"实际结果：复位后读取的DTC总数>=复位前制造的DTC数量，前={len(simulated_dtc)}， 后={len(dtc_list)}")
        else:
            TestLog("FAIL", "",
                    f"期望结果：复位后读取的DTC总数>=复位前制造的DTC数量<br>"
                    f"实际结果：复位后读取的DTC总数<复位前制造的DTC数量，前={len(simulated_dtc)}， 后={len(dtc_list)}")


        TestLog("INFO", "Step3", "发送 19 04/06 请求读取故障码的快照数据和扩展数据")
        for dtc_info in dtc_list:
            TestLog("INFO", "", "")
            dtc = dtc_info['dtc']
            dtc_select = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"
            success, snapshot = read_global_snapshot(node, dtc_select)
            if not success or snapshot is None:
                TestLog("FAIL", "", "未获取到快照数据")

            success, occurrence_counter, pending_counter, aged_counter, ageing_counter = read_extend_data(node, dtc_select)
            if not success:
                TestLog("FAIL", "", "未获取到扩展数据")

        TestLog("INFO", "TC29", "")
        dtc =  dtc_list[0]['dtc']
        # lowest_priority_dtc = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"
        lowest_priority_dtc = simulated_dtc[0]
        current_dtc_count = len(dtc_list)

        dtc_list = get_dtc_list_from_19_resp(resp)
        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")
        if len(dtc_list) == 0:
            TestLog("FAIL", "", "未读取到任何 DTC")
            return

        TestLog("INFO", "Step1", f"模拟第{current_dtc_count+1}个故障码优先级较高的故障码(CRC校验错误，优先级最高)")
        e2e_fault_count = 0
        new_high_priority_dtc = None
        for item in P.ExtendedDTCInfo.invalid_data.valid_items:
            if "E2E" not in item.Type.upper():
                continue

            e2e_fault_count = e2e_fault_count + 1
            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC相关的报文并等待{item.PassTime} ms")
            sim.crc_e2e_fault(True, item.MonitorMessageID, item.Type,
                              dlc=item.MonitorMessageDLC, cycle_ms=item.MonitorMessagePeriod or 100,
                              data=item.ValidPayload, is_canfd=item.FDF,
                              is_e2e=item.IsContainE2E, data_id=item.DataID)

            wait_time_s = (item.LostTime or 5000) / 1000
            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            TestLog("INFO", "", "发送 19 02 09 请求读取DTC信息")
            success, status = find_DTC_by_status_mask(node, 0x09, dtc_select)
            if not success:
                TestLog("FAIL", "", "未查询到测试的DTC")
                continue
            else:
                new_high_priority_dtc = dtc_select
                break

        if e2e_fault_count == 0 or new_high_priority_dtc is None:
            TestLog("FAIL", "", "没有可用的CRC错误DTC，无法模拟第N+1个故障")
            return


        TestLog("INFO", "Step2", "发送 19 02 09 请求读取DTC信息")
        success, resp = service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02],
                                         expect_str="肯定响应(59 02)", func_req=False, DTCStatusMask=0x09)
        if not success:
            TestLog("FAIL", "", "未收到肯定响应")
            return

        dtc_list = get_dtc_list_from_19_resp(resp)
        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")
        if len(dtc_list) == 0:
            TestLog("FAIL", "", "未读取到任何 DTC")
            return
        dtc_count_after_over_flow = len(dtc_list)

        if dtc_count_after_over_flow == current_dtc_count:
            TestLog("PASS", "",
                    f"期望结果：模拟故障码优先级较高的故障码前后，DTC总数不变，前={current_dtc_count}， 后={current_dtc_count}，符合溢出机制<br>"
                    f"实际结果：模拟故障码优先级较高的故障码前后，DTC总数不变，前={current_dtc_count}， 后={dtc_count_after_over_flow}，符合溢出机制")
        else:
            TestLog("FAIL", "",
                    f"期望结果：模拟故障码优先级较高的故障码前后，DTC总数不变，前={current_dtc_count}， 后={current_dtc_count}，符合溢出机制<br>"
                    f"实际结果：模拟故障码优先级较高的故障码前后，DTC总数变化，前={current_dtc_count}， 后={dtc_count_after_over_flow}，不符合溢出机制")

        result_lowest = False
        result_highest = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"
            if dtc_str == lowest_priority_dtc:
                result_lowest = True
            if dtc_str == new_high_priority_dtc:
                result_highest = True
        if result_lowest == False and result_highest == True:
            TestLog("PASS", "",
                    f"期望结果：最低优先级故障码被最高优先级故障码替换，查询到最高优先级故障码0x{new_high_priority_dtc}，未查询到最低优先级故障码0x{lowest_priority_dtc}<br>"
                    f"实际结果：最低优先级故障码被最高优先级故障码替换，查询到最高优先级故障码0x{new_high_priority_dtc}，未查询到最低优先级故障码0x{lowest_priority_dtc}")
        else:
            TestLog("FAIL", "",
                    f"期望结果：最低优先级故障码被最高优先级故障码替换，查询到最高优先级故障码0x{new_high_priority_dtc}，未查询到最低优先级故障码0x{lowest_priority_dtc}<br>"
                    f"实际结果：最低优先级故障码被最高优先级故障码替换，{"未"if result_highest != True else ""}查询到最高优先级故障码0x{new_high_priority_dtc}，"
                    f"{"未"if result_lowest != True else ""}查询到最低优先级故障码0x{lowest_priority_dtc}")

        success, snapshot = read_global_snapshot(node, new_high_priority_dtc)
        if not success or snapshot is None:
            TestLog("FAIL", "", "未获取到快照数据")

        success, occurrence_counter, pending_counter, aged_counter, ageing_counter = read_extend_data(node, new_high_priority_dtc)
        if not success:
            TestLog("FAIL", "", "未获取到扩展数据")


    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

    finally:
        TestLog("INFO", "清理", "恢复所有注入的故障")
        sim.recover_dtc_faults(injected_faults)
        sim.stop_all_timer()
        env_simulator.stop()
        tester_present_stop()
        if node:
            node.close()
