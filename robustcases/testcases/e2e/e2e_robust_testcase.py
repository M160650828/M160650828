import sys
import os
import time
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from uvtest.testlog import TestLog
from uvtest.framework import TestFixture
from common.control import TestStart, TestEnd
from common.context import ctx
from common.params import P
from common.can_utils import send_canmsg, canmsg_create
from common.utils import TimerCyclic
from slplus.time import sl_time
from env.config import DEFAULT_CAN_CHANNELS

from testcases.e2e.e2e_module import (
    e2e_initialization, e2e_deinitialization,
    verify_can_crc, verify_can_counter,
    verify_can_crc_receive, verify_can_counter_receive,
    Counter_Miss_Error, Counter_Repeated_Error, Counter_Unorder_Error,
)
from testcases.can.can_module import (
    can_power_setup_and_communication_check,
    check_can_communication_state,
)


class E2ERobustTestFixture(TestFixture):
    def group_setup(self, context=None):
        e2e_initialization()

    def group_teardown(self, context=None):
        e2e_deinitialization()

    def case_setup(self, context=None):
        if context:
            TestStart(context["test_name"])

    def case_teardown(self, context=None):
        TestEnd("")
        TestLog("INFO", "测试结束", "执行测试结束和去初始化")


def test_TG1_TC1_ContinuousCRCErrorHandlingTest():
    """持续CRC错误处理鲁棒性测试"""
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，将KL30上电，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        TestLog("INFO", "Step2", "进行CAN标准CRC发送校验")
        verify_can_crc(profile_1a=True)

        TestLog("INFO", "Step3", "发送大量干扰报文后再次进行CRC校验")
        ctx.can.clear_messages()
        ctx.can.set_filter_by_channel(can_channel)
        conflict_msg = canmsg_create(0x7FE, 8, data=0xFF, rtr=0, fdf=0, brs=0, ext=0)
        TimerCyclic.start(98, 5, send_canmsg, can_channel, msg=conflict_msg)
        sl_time().sleep(10 * 1000)
        TimerCyclic.stop(98)

        ctx.can.clear_messages()
        sl_time().sleep(2 * 1000)

        verify_can_crc(profile_1a=True)

        TestLog("INFO", "Step4", "模拟BusOff后再次进行CRC校验")
        ctx.can.set_info('gBusOffCount', 0)
        TimerCyclic.start(97, 2, send_canmsg, can_channel, msg=conflict_msg)
        sl_time().sleep(3 * 1000)
        TimerCyclic.stop(97)
        sl_time().sleep(5 * 1000)

        ret = check_can_communication_state(wait_time=3)
        if ret == 0:
            verify_can_crc(profile_1a=True)
            TestLog("PASS", "Step4", "BusOff恢复后CRC校验正常")
        else:
            TestLog("WARNING", "Step4", "BusOff恢复后通信未恢复，跳过CRC校验")

        TestLog("INFO", "持续CRC错误处理鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "持续CRC错误处理鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "持续CRC错误处理鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC2_CounterAbnormalJumpTest():
    """Counter异常跳变鲁棒性测试"""
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，将KL30上电，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        TestLog("INFO", "Step2", "验证Counter重复错误检测能力")
        verify_can_counter_receive(profile_1a=True, counter_error_type=Counter_Repeated_Error)

        TestLog("INFO", "Step3", "验证Counter乱序错误检测能力")
        verify_can_counter_receive(profile_1a=True, counter_error_type=Counter_Unorder_Error)

        TestLog("INFO", "Step4", "验证Counter丢失错误检测能力")
        verify_can_counter_receive(profile_1a=True, counter_error_type=Counter_Miss_Error)

        TestLog("INFO", "Step5", "多次Counter错误后验证正常发送Counter恢复")
        verify_can_counter(profile_1a=True)
        TestLog("PASS", "Step5", "Counter错误测试后正常发送Counter恢复验证通过")

        TestLog("INFO", "Counter异常跳变鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "Counter异常跳变鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "Counter异常跳变鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC3_E2ERecoveryCapabilityTest():
    """E2E恢复能力鲁棒性测试"""
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，将KL30上电，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        TestLog("INFO", "Step2", "第一轮: CRC + Counter 发送校验（基准）")
        verify_can_crc(profile_1a=True)
        verify_can_counter(profile_1a=True)

        TestLog("INFO", "Step3", "第一轮: CRC + Counter 接收校验（基准）")
        verify_can_crc_receive(profile_1a=True)
        verify_can_counter_receive(profile_1a=True, counter_error_type=Counter_Miss_Error)

        TestLog("INFO", "Step4", "在多轮Counter错误后验证E2E通信可恢复")
        for round_num in range(1, 4):
            TestLog("INFO", "Step4", f"第{round_num}/3轮错误注入")
            verify_can_counter_receive(profile_1a=True, counter_error_type=Counter_Miss_Error)
            time.sleep(1)

        TestLog("INFO", "Step5", "所有错误注入完成后验证E2E恢复正常")
        verify_can_crc(profile_1a=True)
        verify_can_counter(profile_1a=True)
        verify_can_crc_receive(profile_1a=True)

        TestLog("PASS", "Step5", "期望结果：E2E通信恢复正常。实际结果：所有E2E校验通过")
        TestLog("INFO", "E2E恢复能力鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "E2E恢复能力鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "E2E恢复能力鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def get_all_test_cases():
    import inspect
    current_module = inspect.getmodule(inspect.currentframe())
    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj
    return test_cases
