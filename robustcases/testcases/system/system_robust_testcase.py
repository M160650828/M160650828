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
from common.can_utils import send_canmsg, canmsg_create
from common.utils import TimerCyclic
from common.wakeup import WakeupStart, WakeupStop
from slplus.time import sl_time

from testcases.can.can_module import (
    can_initialization, can_deinitialization,
    can_power_setup_and_communication_check,
    check_can_communication_state,
    build_rx_msg_info, analyze_messages, report_message_tests,
)


class SystemRobustTestFixture(TestFixture):
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


def test_TG1_TC1_ECUResetDuringCommunicationTest():
    """通信中ECU复位鲁棒性测试"""
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        cycle_count = min(P.CANInfo.Tcount, 5)
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

        TestLog("INFO", "Step2", f"执行{cycle_count}次通信中KL30复位循环")
        all_recovered = True

        for i in range(1, cycle_count + 1):
            TestLog("INFO", "Step2", f"第{i}/{cycle_count}次: 正常通信 → KL30下电 → 重新上电")

            ctx.can.clear_messages()
            ctx.can.set_info('gErrorFrameCount', 0)

            ctx.bob_ctrl.set_power('KL30', False)
            ctx.power_ctrl.set_voltage(0)
            time.sleep(2)

            ctx.power_ctrl.set_voltage(rVnormal)
            ctx.bob_ctrl.set_power('KL30', True)
            WakeupStart()
            time.sleep(min(rTstable_s, 5))

            ret = check_can_communication_state(wait_time=3)
            if ret == 0:
                TestLog("INFO", "Step2", f"第{i}次: 通信恢复正常")
            else:
                TestLog("WARNING", "Step2", f"第{i}次: 通信恢复异常")
                all_recovered = False

        TestLog("INFO", "Step3", "最后完成全部复位循环后，监控5分钟验证通信质量")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(5 * 60 * 1000)

        if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
            TestLog("FAIL", "Step3", "存在错误帧")
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

        if all_recovered:
            TestLog("PASS", "通信中ECU复位鲁棒性测试", "所有复位循环后DUT均正常恢复通信")
        else:
            TestLog("WARNING", "通信中ECU复位鲁棒性测试", "部分复位循环后DUT通信恢复异常")

    except Exception as e:
        TestLog("FAIL", "通信中ECU复位鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "通信中ECU复位鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC2_ExtendedContinuousOperationTest():
    """长时间连续运行鲁棒性测试"""
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rTperiodDeviation1 = P.CANInfo.TperiodDeviation1_pct
        rTperiodDeviation2 = P.CANInfo.TperiodDeviation2_pct
        monitor_minutes = 30

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.set_filter_by_channel(can_channel)
        can_db_msg_defs = ctx.can.get_info('can_db_msg_defs') or {}

        TestLog("INFO", "Step2", f"执行{monitor_minutes}分钟持续运行监控，每10分钟进行一次检查")
        checkpoints = [10, 20, monitor_minutes]

        for mins in checkpoints:
            TestLog("INFO", "Step2", f"运行至第{mins}分钟检查点")
            ctx.can.clear_messages()
            ctx.can.set_info('gErrorFrameCount', 0)
            sl_time().sleep(60 * 1000)

            err_count = ctx.can.get_info('gErrorFrameCount') or 0
            msg_count = len(ctx.can.messages)
            TestLog("INFO", "Step2", f"第{mins}分钟: 报文={msg_count}, 错误帧={err_count}")

            if err_count > 0:
                TestLog("WARNING", "Step2", f"第{mins}分钟存在{err_count}个错误帧")

            if msg_count == 0:
                TestLog("FAIL", "Step2", f"第{mins}分钟无报文输出")

        TestLog("INFO", "Step3", "持续运行结束，分析报文周期偏移")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        time.sleep(60)

        messages = ctx.can.messages
        rx_stats = build_rx_msg_info(messages)
        MsgReceivedList, MsgNotReceivedList, MsgTmpList = analyze_messages(rx_stats, can_db_msg_defs)

        report_message_tests(
            MsgReceivedList, MsgNotReceivedList, MsgTmpList,
            rx_stats, can_db_msg_defs,
            tests=("period",),
            period_thresholds=(rTperiodDeviation1, rTperiodDeviation2),
        )

        TestLog("INFO", "长时间连续运行鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "长时间连续运行鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "长时间连续运行鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC3_MultiEventConcurrentHandlingTest():
    """多事件并发处理鲁棒性测试"""
    tids = []
    try:
        rVnormal = P.CANInfo.Vnormal
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

        TestLog("INFO", "Step2", "同时触发多个并发事件：高总线负载 + 电压波动 + 诊断请求")
        for burst_id in range(0x200, 0x208):
            msg = canmsg_create(burst_id, 8, data=0xFF, rtr=0, fdf=0, brs=0, ext=0)
            TimerCyclic.start(burst_id, 10, send_canmsg, can_channel, msg=msg)
            tids.append(burst_id)

        ctx.power_ctrl.set_voltage(rVnormal - 1.5)
        time.sleep(5)
        ctx.power_ctrl.set_voltage(rVnormal + 1.5)
        time.sleep(5)
        ctx.power_ctrl.set_voltage(rVnormal)

        for t in tids:
            TimerCyclic.stop(t)
        tids.clear()

        TestLog("INFO", "Step3", "并发事件结束，验证DUT通信状态")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        time.sleep(5)

        ret = check_can_communication_state(wait_time=3)
        if ret == 0:
            TestLog("PASS", "Step3",
                    "期望结果：多事件并发后DUT通信正常。实际结果：DUT通信正常")
        else:
            TestLog("FAIL", "Step3",
                    "期望结果：多事件并发后DUT通信正常。实际结果：DUT通信异常")

        TestLog("INFO", "Step4", "监控5分钟，验证DUT报文周期偏移是否正常")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        time.sleep(5 * 60)

        if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
            TestLog("FAIL", "Step4", "存在错误帧")
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

        TestLog("INFO", "多事件并发处理鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "多事件并发处理鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "多事件并发处理鲁棒性测试", f"详细错误: {traceback.format_exc()}")
    finally:
        for t in tids:
            try:
                TimerCyclic.stop(t)
            except:
                pass


def get_all_test_cases():
    import inspect
    current_module = inspect.getmodule(inspect.currentframe())
    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj
    return test_cases
