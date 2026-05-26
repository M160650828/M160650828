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
from common.wakeup import WakeupStart, WakeupStop
from slplus.time import sl_time

from testcases.can.can_module import (
    can_initialization, can_deinitialization,
    can_power_setup_and_communication_check,
    check_can_communication_state,
    build_rx_msg_info, analyze_messages, report_message_tests,
)


class PowerRobustTestFixture(TestFixture):
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


def test_TG1_TC1_MicroBrownoutSustainedTest():
    """微欠压持续运行鲁棒性测试"""
    try:
        rVnormal = P.CANInfo.Vnormal
        rVlowStand = P.CANInfo.VlowStand
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rTperiodDeviation1 = P.CANInfo.TperiodDeviation1_pct
        rTperiodDeviation2 = P.CANInfo.TperiodDeviation2_pct

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.set_filter_by_channel(can_channel)
        can_db_msg_defs = ctx.can.get_info('can_db_msg_defs') or {}

        brownout_voltage = rVlowStand * 0.95
        TestLog("INFO", "Step2",
                f"将电压降至{brownout_voltage:.2f}V（低于最低工作电压5%），持续运行3分钟")

        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)

        ctx.power_ctrl.set_voltage(brownout_voltage)
        sl_time().sleep(3 * 60 * 1000)

        err_count = ctx.can.get_info('gErrorFrameCount') or 0
        msg_count = len(ctx.can.messages)
        TestLog("INFO", "Step2",
                f"微欠压({brownout_voltage:.2f}V)下: 报文={msg_count}, 错误帧={err_count}")

        TestLog("INFO", "Step3", f"恢复电压到{rVnormal}V，验证通信恢复")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        ctx.power_ctrl.set_voltage(rVnormal)
        sl_time().sleep(10 * 1000)

        ret = check_can_communication_state(wait_time=3)
        if ret == 0:
            TestLog("PASS", "Step3",
                    "期望结果：恢复正常电压后通信恢复。实际结果：DUT通信正常")
        else:
            TestLog("FAIL", "Step3",
                    "期望结果：恢复正常电压后通信恢复。实际结果：DUT通信异常")

        TestLog("INFO", "Step4", "监控5分钟验证恢复后通信质量")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(5 * 60 * 1000)

        if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
            TestLog("WARNING", "Step4", "恢复后存在错误帧")
            return

        messages = ctx.can.messages
        rx_stats = build_rx_msg_info(messages)
        MsgReceivedList, MsgNotReceivedList, MsgTmpList = analyze_messages(rx_stats, can_db_msg_defs)

        report_message_tests(
            MsgReceivedList, MsgNotReceivedList, MsgTmpList,
            rx_stats, can_db_msg_defs,
            tests=("period",),
            period_thresholds=(rTperiodDeviation1, rTperiodDeviation2),
        )

        TestLog("INFO", "微欠压持续运行鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "微欠压持续运行鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "微欠压持续运行鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC2_RapidVoltageFluctuationTest():
    """电压快速波动鲁棒性测试"""
    try:
        rVnormal = P.CANInfo.Vnormal
        rVlowStand = P.CANInfo.VlowStand
        rVhighStand = P.CANInfo.VhighStand
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        cycle_count = min(P.CANInfo.Tcount, 20)

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.set_filter_by_channel(can_channel)

        TestLog("INFO", "Step2",
                f"在{rVlowStand}V和{rVhighStand}V之间快速波动{cycle_count}次 (每500ms变化一次)")

        for i in range(1, cycle_count + 1):
            ctx.power_ctrl.set_voltage(rVlowStand)
            sl_time().sleep(500)
            ctx.power_ctrl.set_voltage(rVhighStand)
            sl_time().sleep(500)

        TestLog("INFO", "Step3", f"波动结束后恢复到{rVnormal}V，验证通信状态")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        ctx.power_ctrl.set_voltage(rVnormal)
        sl_time().sleep(5 * 1000)

        ret = check_can_communication_state(wait_time=3)
        if ret == 0:
            TestLog("PASS", "Step3",
                    "期望结果：电压波动后通信恢复正常。实际结果：DUT通信正常")
        else:
            TestLog("FAIL", "Step3",
                    "期望结果：电压波动后通信恢复正常。实际结果：DUT通信异常")

        TestLog("INFO", "Step4", "监控5分钟验证长期稳定性")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(5 * 60 * 1000)

        msg_count = len(ctx.can.messages)
        err_count = ctx.can.get_info('gErrorFrameCount') or 0
        if msg_count > 0 and err_count == 0:
            TestLog("PASS", "Step4",
                    f"期望结果：长期通信稳定。实际结果：{msg_count}条报文, 0个错误帧")
        else:
            TestLog("WARNING", "Step4",
                    f"存在异常: 报文={msg_count}, 错误帧={err_count}")

        TestLog("INFO", "电压快速波动鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "电压快速波动鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "电压快速波动鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC3_ColdStartSlowVoltageRampTest():
    """冷启动缓慢电压爬升鲁棒性测试"""
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        TestLog("INFO", "Step1", "确保DUT完全断电2分钟（冷启动条件）")
        ctx.bob_ctrl.set_power('KL30', False)
        ctx.bob_ctrl.set_power('KL15', False)
        ctx.power_ctrl.set_voltage(0)
        sl_time().sleep(2 * 60 * 1000)

        TestLog("INFO", "Step2", f"以0.2V/s的速率从0V缓慢爬升到{rVnormal}V")
        voltage = 0.0
        step = 0.2
        while voltage < rVnormal:
            voltage = min(voltage + step, rVnormal)
            ctx.power_ctrl.set_voltage(voltage)
            time.sleep(1)

        TestLog("INFO", "Step3", f"电压达到{rVnormal}V后KL30上电，等待DUT启动")
        ctx.bob_ctrl.set_power('KL30', True)
        sl_time().sleep(int(rTstable_s * 1000))

        TestLog("INFO", "Step4", "唤醒CAN网络并检查通信")
        WakeupStart()
        sl_time().sleep(3 * 1000)

        ret = check_can_communication_state(wait_time=3)
        if ret == 0:
            TestLog("PASS", "Step4",
                    "期望结果：缓慢爬升后DUT正常启动通信。实际结果：DUT通信正常")
        else:
            TestLog("FAIL", "Step4",
                    "期望结果：缓慢爬升后DUT正常启动通信。实际结果：DUT通信异常")

        TestLog("INFO", "Step5", "监控5分钟验证冷启动后长期通信稳定性")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(5 * 60 * 1000)

        msg_count = len(ctx.can.messages)
        err_count = ctx.can.get_info('gErrorFrameCount') or 0
        if msg_count > 0 and err_count == 0:
            TestLog("PASS", "Step5",
                    f"期望结果：冷启动后通信稳定。实际结果：{msg_count}条报文, 0个错误帧")
        else:
            TestLog("WARNING", "Step5",
                    f"存在异常: 报文={msg_count}, 错误帧={err_count}")

        TestLog("INFO", "冷启动缓慢电压爬升鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "冷启动缓慢电压爬升鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "冷启动缓慢电压爬升鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def get_all_test_cases():
    import inspect
    current_module = inspect.getmodule(inspect.currentframe())
    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj
    return test_cases
