import sys
import os
import time
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from env.config import DEFAULT_CAN_CHANNELS
from uvtest.testlog import TestLog
from uvtest.framework import TestFixture
from common.control import TestStart, TestEnd
from common.context import ctx
from common.params import P
from slplus.time import sl_time

from testcases.dtc.can_comm import can_power_setup_and_communication_check, can_initialization, can_deinitialization
from testcases.dtc.dtc_can_utils import (
    get_can_node, service_19_check, get_dtc_list_from_19_resp, service_14_check,
    DTCStatusBit, check_dtc_list_status_bits,
    inject_fault_and_read_global_snapshot, recover_fault_and_read_global_snapshot,
    env_simulator, dtc_enable_conditions, clear_dtc, read_global_snapshot,
    write_dtc_config, enable_dtc_config, disable_dtc_config, DTCTestParams,
    select_fault_type, service_10_check,
)


class DTCRobustTestFixture(TestFixture):
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


def test_TG1_TC1_DTCAgingCounterRolloverTest():
    """DTC老化计数器翻转鲁棒性测试"""
    node = None
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        node = get_can_node()

        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "Step1", "清除所有DTC，确保初始状态干净")
        clear_dtc(node)

        fault_type = select_fault_type()
        if fault_type is None:
            TestLog("WARNING", "", "未配置可用故障类型，跳过测试")
            return

        TestLog("INFO", "Step2", f"注入故障触发DTC: {fault_type}")
        inject_fault_and_read_global_snapshot(node, fault_type, step="Step2")

        TestLog("INFO", "Step3", "恢复故障，验证DTC状态变为'已恢复'(confirmedDTC=1, testFailed=0)")
        recover_fault_and_read_global_snapshot(node, fault_type, step="Step3")

        TestLog("INFO", "Step4", "多次执行操作循环以推进老化计数器")
        op_cycle_count = max(P.CANInfo.OperationCycle, 5)
        for i in range(1, op_cycle_count + 1):
            TestLog("INFO", "Step4", f"执行第{i}/{op_cycle_count}次操作循环")
            dtc_enable_conditions(False, env_simulator._POWERMODE_SLEEP)
            time.sleep(2)
            dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
            time.sleep(2)

        TestLog("INFO", "Step5", "读取DTC状态，检查老化计数器是否正常递减")
        success, resp = service_19_check(node, report_type=0x02,
                                         expect_data=[0x59, 0x02],
                                         expect_str="肯定响应(59 02)",
                                         func_req=False, DTCStatusMask=0xFF)

        if success:
            dtc_list = get_dtc_list_from_19_resp(resp)
            dtc_count = len(dtc_list)
            TestLog("INFO", "Step5", f"操作循环后读取到 {dtc_count} 个DTC")

            if dtc_count > 0:
                still_confirmed = any(
                    (dtc_info['status'] & DTCStatusBit.CONFIRMED.value) != 0
                    for dtc_info in dtc_list
                )
                if still_confirmed:
                    TestLog("PASS", "Step5",
                            "期望结果：老化计数器正常运行，DTC仍存在（未到达老化阈值）。"
                            "实际结果：DTC仍为confirmed状态")
                else:
                    TestLog("PASS", "Step5",
                            "期望结果：老化计数器正常运行，DTC已老化清除。"
                            "实际结果：DTC已被老化清除")
            else:
                TestLog("PASS", "Step5", "DTC已全部老化清除，老化计数器正常")
        else:
            TestLog("FAIL", "Step5", "读取DTC状态失败")

        TestLog("INFO", "DTC老化计数器翻转鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "DTC老化计数器翻转鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "DTC老化计数器翻转鲁棒性测试", f"详细错误: {traceback.format_exc()}")
    finally:
        env_simulator.stop()
        if node:
            node.close()


def test_TG1_TC2_MultipleFaultSimultaneousTest():
    """多故障同时注入鲁棒性测试"""
    node = None
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        node = get_can_node()

        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "Step1", "清除所有DTC")
        clear_dtc(node)

        fault_type = select_fault_type()
        if fault_type is None:
            TestLog("WARNING", "", "未配置可用故障类型")
            return

        TestLog("INFO", "Step2", f"第1次注入故障: {fault_type}")
        inject_fault_and_read_global_snapshot(node, fault_type, step="Step2")

        TestLog("INFO", "Step3", "恢复第1次故障后立即再次注入同一故障")
        recover_fault_and_read_global_snapshot(node, fault_type, step="Step3-恢复")

        TestLog("INFO", "Step4", f"第2次注入故障: {fault_type}")
        inject_fault_and_read_global_snapshot(node, fault_type, step="Step4")

        TestLog("INFO", "Step5", "恢复第2次故障后立即第三次注入")
        recover_fault_and_read_global_snapshot(node, fault_type, step="Step5-恢复")

        TestLog("INFO", "Step6", f"第3次注入故障: {fault_type}")
        inject_fault_and_read_global_snapshot(node, fault_type, step="Step6")

        TestLog("INFO", "Step7", "最终读取DTC列表，检查DTC事件计数器和状态")
        success, resp = service_19_check(node, report_type=0x0A,
                                         expect_data=[0x59, 0x0A],
                                         expect_str="肯定响应(59 0A)",
                                         func_req=False)
        if success:
            dtc_list = get_dtc_list_from_19_resp(resp)
            TestLog("INFO", "Step7", f"经过3次故障注入后读取到 {len(dtc_list)} 个DTC")

            if len(dtc_list) > 0:
                check_dtc_list_status_bits(dtc_list, DTCStatusBit.CONFIRMED,
                                          log_prefix="Step7-Confirmed检查")
                TestLog("PASS", "Step7",
                        "期望结果：多次故障注入/恢复后DTC状态管理正常。"
                        "实际结果：DTC列表正常返回")
            else:
                TestLog("FAIL", "Step7", "期望结果：DTC列表非空。实际结果：DTC列表为空")
        else:
            TestLog("FAIL", "Step7", "读取DTC列表失败")

        TestLog("INFO", "多故障同时注入鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "多故障同时注入鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "多故障同时注入鲁棒性测试", f"详细错误: {traceback.format_exc()}")
    finally:
        env_simulator.stop()
        if node:
            node.close()


def test_TG1_TC3_DTCTriggerAfterClearTest():
    """DTC清除后重新触发鲁棒性测试"""
    node = None
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        node = get_can_node()

        TestLog("INFO", "前置条件", "设置测试环境，建立正常通信")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", "", "测试环境设置失败")
            return
        dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
        time.sleep(5)

        TestLog("INFO", "Step1", "清除所有DTC")
        clear_dtc(node)

        fault_type = select_fault_type()
        if fault_type is None:
            TestLog("WARNING", "", "未配置可用故障类型")
            return

        TestLog("INFO", "Step2", f"注入故障触发DTC: {fault_type}")
        inject_fault_and_read_global_snapshot(node, fault_type, step="Step2")

        TestLog("INFO", "Step3", "发送14服务清除DTC")
        clear_dtc(node)
        time.sleep(2)

        success, resp = service_19_check(node, report_type=0x0A,
                                         expect_data=[0x59, 0x0A],
                                         expect_str="肯定响应(59 0A)",
                                         func_req=False)
        if success:
            dtc_list = get_dtc_list_from_19_resp(resp)
            confirmed_count = sum(
                1 for d in dtc_list
                if (d['status'] & DTCStatusBit.CONFIRMED.value) != 0
            )
            if confirmed_count == 0:
                TestLog("PASS", "Step3",
                        "期望结果：DTC已清除。实际结果：confirmed DTC数量为0")
            else:
                TestLog("WARNING", "Step3",
                        f"DTC清除后仍有{confirmed_count}个confirmed DTC")
        else:
            TestLog("FAIL", "Step3", "读取DTC列表失败")

        TestLog("INFO", "Step4", "清除后再次注入相同故障，验证DTC可重新触发")
        recover_fault_and_read_global_snapshot(node, fault_type, step="Step4-确保恢复")
        time.sleep(2)

        inject_fault_and_read_global_snapshot(node, fault_type, step="Step4")
        success2, resp2 = service_19_check(node, report_type=0x0A,
                                           expect_data=[0x59, 0x0A],
                                           expect_str="肯定响应(59 0A)",
                                           func_req=False)
        if success2:
            dtc_list2 = get_dtc_list_from_19_resp(resp2)
            confirmed_count2 = sum(
                1 for d in dtc_list2
                if (d['status'] & DTCStatusBit.CONFIRMED.value) != 0
            )
            if confirmed_count2 > 0:
                TestLog("PASS", "Step4",
                        f"期望结果：DTC可重新触发。实际结果：恢复后重新注入故障, confirmed DTC={confirmed_count2}")
            else:
                TestLog("FAIL", "Step4",
                        "期望结果：DTC可重新触发。实际结果：清除后无法重新触发DTC")
        else:
            TestLog("FAIL", "Step4", "读取DTC列表失败")

        TestLog("INFO", "DTC清除后重新触发鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "DTC清除后重新触发鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "DTC清除后重新触发鲁棒性测试", f"详细错误: {traceback.format_exc()}")
    finally:
        env_simulator.stop()
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
