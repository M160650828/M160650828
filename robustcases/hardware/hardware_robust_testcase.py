import sys
import os
import time
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from env.config import DEFAULT_CAN_CHANNELS, CAN_TERMINATION
from uvtest.testlog import TestLog
from uvtest.framework import TestFixture
from common.control import TestStart, TestEnd
from common.context import ctx
from common.params import P
from common.wakeup import WakeupStart, WakeupStop
from slplus.time import sl_time

from testcases.can.can_module import (
    can_initialization, can_deinitialization,
    can_power_setup_and_communication_check,
    check_can_communication_state,
    build_rx_msg_info, analyze_messages, report_message_tests,
)


class HardwareRobustTestFixture(TestFixture):
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


def test_TG1_TC1_RapidPowerCycleRecoveryTest():
    """多次快速上下电恢复鲁棒性测试"""
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        cycle_count = max(P.CANInfo.Tcount, 20)
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        TestLog("INFO", "Step1",
                f"执行{cycle_count}次快速KL30上下电循环（间隔100ms）")
        for i in range(1, cycle_count + 1):
            ctx.power_ctrl.set_voltage(rVnormal)
            ctx.bob_ctrl.set_power('KL30', True)
            time.sleep(0.05)
            ctx.bob_ctrl.set_power('KL30', False)
            ctx.power_ctrl.set_voltage(0)
            time.sleep(0.05)
            if i % 10 == 0:
                TestLog("INFO", "Step1", f"已完成 {i}/{cycle_count} 次循环")

        TestLog("INFO", "Step2",
                f"快速上下电完成后正常上电, 设置{rVnormal}V, 唤醒DUT, 等待{rTstable_s}s通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step2", f"{cycle_count}次快速上下电后DUT通信检查失败")
            return
        TestLog("PASS", "Step2",
                f"期望结果：{cycle_count}次快速上下电后DUT正常通信。实际结果：DUT通信正常")

        ctx.can.set_filter_by_channel(can_channel)

        TestLog("INFO", "Step3", "监控5分钟验证通信质量和报文周期")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(5 * 60 * 1000)

        if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
            TestLog("FAIL", "Step3", "通信中存在错误帧")
            return

        rTperiodDeviation1 = P.CANInfo.TperiodDeviation1_pct
        rTperiodDeviation2 = P.CANInfo.TperiodDeviation2_pct
        can_db_msg_defs = ctx.can.get_info('can_db_msg_defs') or {}

        messages = ctx.can.messages
        rx_stats = build_rx_msg_info(messages)
        MsgReceivedList, MsgNotReceivedList, MsgTmpList = analyze_messages(rx_stats, can_db_msg_defs)

        report_message_tests(
            MsgReceivedList, MsgNotReceivedList, MsgTmpList,
            rx_stats, can_db_msg_defs,
            tests=("period",),
            period_thresholds=(rTperiodDeviation1, rTperiodDeviation2),
        )

        TestLog("INFO", "多次快速上下电恢复鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "多次快速上下电恢复鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "多次快速上下电恢复鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC2_ExtremeVoltageBoundaryTest():
    """极限电压边界鲁棒性测试"""
    try:
        rVnormal = P.CANInfo.Vnormal
        rVlowStand = P.CANInfo.VlowStand
        rVhighStand = P.CANInfo.VhighStand
        rTstable_s = P.CANInfo.Tstable_s
        rTvStepDelay = P.CANInfo.TvStepDelay_ms
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，将KL30上电，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.set_filter_by_channel(can_channel)
        test_points = [
            (rVlowStand - 1.0, "低于最低工作电压1V"),
            (rVlowStand, "最低工作电压边界"),
            (rVhighStand, "最高工作电压边界"),
            (rVhighStand + 1.0, "高于最高工作电压1V"),
        ]

        for voltage, desc in test_points:
            TestLog("INFO", "Step2", f"设置电压到{voltage}V ({desc}), 保持{rTvStepDelay}ms")
            ctx.can.clear_messages()
            ctx.can.set_info('gErrorFrameCount', 0)
            ctx.power_ctrl.set_voltage(max(0, voltage))
            sl_time().sleep(rTvStepDelay)

            err_count = ctx.can.get_info('gErrorFrameCount') or 0
            msg_count = len(ctx.can.messages)
            TestLog("INFO", "Step2",
                    f"{desc}: 电压={voltage}V, 报文={msg_count}, 错误帧={err_count}")

            ctx.power_ctrl.set_voltage(rVnormal)
            sl_time().sleep(int(rTvStepDelay / 2))

            ret = check_can_communication_state(wait_time=2)
            if ret == 0:
                TestLog("PASS", "Step2", f"{desc}({voltage}V): 恢复{rVnormal}V后通信正常")
            else:
                TestLog("FAIL", "Step2", f"{desc}({voltage}V): 恢复{rVnormal}V后通信异常")

        TestLog("INFO", "Step3", "测试完成后验证DUT在正常电压下的通信质量")
        ctx.power_ctrl.set_voltage(rVnormal)
        time.sleep(2)
        ret = check_can_communication_state(wait_time=5)
        if ret == 0:
            TestLog("PASS", "Step3", "所有极限电压测试后DUT在正常电压下通信正常")
        else:
            TestLog("FAIL", "Step3", "极限电压测试后DUT通信异常")

        TestLog("INFO", "极限电压边界鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "极限电压边界鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "极限电压边界鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC3_PersistentOperationStabilityTest():
    """持续运行稳定性鲁棒性测试"""
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        monitor_duration_min = 15

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，将KL30上电，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.set_filter_by_channel(can_channel)
        checkpoints = [
            (1, "1分钟"), (5, "5分钟"), (10, "10分钟"), (monitor_duration_min, f"{monitor_duration_min}分钟")
        ]

        start_time = time.time()
        for mins, label in checkpoints:
            target_time = start_time + mins * 60
            wait_s = max(0, target_time - time.time())
            if wait_s > 0:
                time.sleep(wait_s)

            ctx.can.clear_messages()
            ctx.can.set_info('gErrorFrameCount', 0)
            time.sleep(10)

            err_count = ctx.can.get_info('gErrorFrameCount') or 0
            msg_count = len(ctx.can.messages)
            TestLog("INFO", checkpoints, f"持续运行{label}: 10s内收到{msg_count}条报文, 错误帧={err_count}")

            if msg_count == 0:
                TestLog("FAIL", f"第{label}检查点", "DUT无报文发送")
            elif err_count > 0:
                TestLog("WARNING", f"第{label}检查点", f"存在{err_count}个错误帧")
            else:
                TestLog("PASS", f"第{label}检查点", f"通信正常: {msg_count}条报文, 0个错误帧")

        rTperiodDeviation1 = P.CANInfo.TperiodDeviation1_pct
        rTperiodDeviation2 = P.CANInfo.TperiodDeviation2_pct
        can_db_msg_defs = ctx.can.get_info('can_db_msg_defs') or {}

        messages = ctx.can.messages
        rx_stats = build_rx_msg_info(messages)
        MsgReceivedList, MsgNotReceivedList, MsgTmpList = analyze_messages(rx_stats, can_db_msg_defs)

        TestLog("INFO", "最终检查", "分析长期运行后的报文周期偏移")
        report_message_tests(
            MsgReceivedList, MsgNotReceivedList, MsgTmpList,
            rx_stats, can_db_msg_defs,
            tests=("period",),
            period_thresholds=(rTperiodDeviation1, rTperiodDeviation2),
        )

        TestLog("INFO", "持续运行稳定性鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "持续运行稳定性鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "持续运行稳定性鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def get_all_test_cases():
    import inspect
    current_module = inspect.getmodule(inspect.currentframe())
    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj
    return test_cases
