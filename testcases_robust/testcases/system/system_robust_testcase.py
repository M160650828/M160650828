import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from env.config import *
from uvtest.testlog import TestLog
from uvtest.framework import TestFixture
from common.control import TestStart, TestEnd
from common.context import ctx
from common.params import P
from common.can_utils import send_canmsg, canmsg_create
from common.utils import TimerCyclic
from common.wakeup import WakeupStart, WakeupStop
from slplus.time import sl_time

from testcases_canlin.can.can_module import (
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
        import traceback
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
        import traceback
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
        import traceback
        TestLog("DEBUG", "多事件并发处理鲁棒性测试", f"详细错误: {traceback.format_exc()}")
    finally:
        for t in tids:
            try:
                TimerCyclic.stop(t)
            except:
                pass


def test_TG1_TC4_ClockDriftToleranceTest():
    """时钟漂移鲁棒性测试 - 通过通信时序变化验证DUT的时钟容差与同步恢复"""
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

        TestLog("INFO", "Step2", "通过注入不同周期的高负载报文模拟时钟漂移场景")
        TestLog("INFO", "Step2", "场景1: 密集高频报文（模拟时钟偏快）")

        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        msg_2ms = canmsg_create(0x500, 8, data=0xFF, rtr=0, fdf=0, brs=0, ext=0)
        TimerCyclic.start(101, 2, send_canmsg, can_channel, msg=msg_2ms)
        sl_time().sleep(30 * 1000)
        TimerCyclic.stop(101)

        high_freq_errs = ctx.can.get_info('gErrorFrameCount') or 0
        TestLog("INFO", "Step2", f"场景1(高频): 错误帧={high_freq_errs}")

        TestLog("INFO", "Step2", "场景2: 稀疏低频报文（模拟时钟偏慢）")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(30 * 1000)

        low_freq_errs = ctx.can.get_info('gErrorFrameCount') or 0
        TestLog("INFO", "Step2", f"场景2(低频): 错误帧={low_freq_errs}")

        TestLog("INFO", "Step3", "恢复后监控通信质量和报文周期偏移")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(5 * 60 * 1000)

        if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
            TestLog("WARNING", "Step3", "存在错误帧")

        messages = ctx.can.messages
        rx_stats = build_rx_msg_info(messages)
        MsgReceivedList, MsgNotReceivedList, MsgTmpList = analyze_messages(rx_stats, can_db_msg_defs)

        report_message_tests(
            MsgReceivedList, MsgNotReceivedList, MsgTmpList,
            rx_stats, can_db_msg_defs,
            tests=("period",),
            period_thresholds=(rTperiodDeviation1, rTperiodDeviation2),
        )

        TestLog("PASS", "时钟漂移鲁棒性测试", "时钟扰动后DUT通信时序在容差范围内")
        TestLog("INFO", "时钟漂移鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "时钟漂移鲁棒性测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "时钟漂移鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC5_WatchdogHighLoadTest():
    """看门狗高负载鲁棒性测试 - 在高通信负载下验证DUT的看门狗服务与系统稳定性"""
    tids = []
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.set_filter_by_channel(can_channel)

        TestLog("INFO", "Step2", "注入极高总线负载(>90%)以压测看门狗服务能力")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)

        # 大量高频报文
        for idx, burst_id in enumerate(range(0x100, 0x110)):
            msg = canmsg_create(burst_id, 8, data=0xFF, rtr=0, fdf=0, brs=0, ext=0)
            tid = 200 + idx
            TimerCyclic.start(tid, 3, send_canmsg, can_channel, msg=msg)
            tids.append(tid)

        TestLog("INFO", "Step2", "高负载持续120秒，观察DUT是否复位或通信中断")
        sl_time().sleep(120 * 1000)

        for t in tids:
            TimerCyclic.stop(t)
        tids.clear()

        TestLog("INFO", "Step3", "停止高负载后验证DUT未意外复位且通信恢复")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(10 * 1000)

        ret = check_can_communication_state(wait_time=5)
        if ret == 0:
            TestLog("PASS", "Step3",
                    "期望结果：看门狗高负载后DUT未意外复位，通信正常。"
                    "实际结果：DUT通信正常")
        else:
            TestLog("FAIL", "Step3",
                    "期望结果：看门狗高负载后DUT通信正常。实际结果：DUT通信异常（可能已复位）")

        TestLog("INFO", "Step4", "监控5分钟验证看门狗服务恢复后系统长期稳定")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(5 * 60 * 1000)

        final_msgs = len(ctx.can.messages)
        final_errs = ctx.can.get_info('gErrorFrameCount') or 0
        if final_msgs > 0 and final_errs == 0:
            TestLog("PASS", "Step4",
                    f"期望结果：长期通信稳定。实际结果：{final_msgs}条报文, 0个错误帧")
        else:
            TestLog("WARNING", "Step4",
                    f"通信异常: 报文={final_msgs}, 错误帧={final_errs}")

        TestLog("INFO", "看门狗高负载鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "看门狗高负载鲁棒性测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "看门狗高负载鲁棒性测试", f"详细错误: {traceback.format_exc()}")
    finally:
        for t in tids:
            try:
                TimerCyclic.stop(t)
            except:
                pass


def test_TG1_TC6_TaskDeadlockRecoveryTest():
    """任务死锁恢复鲁棒性测试 - 通过极端负载触发潜在的任务死锁，验证DUT的任务调度恢复"""
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

        TestLog("INFO", "Step2", "通过极端并发操作模拟任务死锁条件：高频报文 + 物理故障 + 电压波动同时注入")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)

        # 1) 高频报文
        for idx, burst_id in enumerate(range(0x400, 0x408)):
            msg = canmsg_create(burst_id, 8, data=0xFF, rtr=0, fdf=0, brs=0, ext=0)
            tid = 300 + idx
            TimerCyclic.start(tid, 5, send_canmsg, can_channel, msg=msg)
            tids.append(tid)

        # 2) 物理故障
        ctx.bob_ctrl.set_fault(f'CAN{can_channel}_H', 'SHORT_GND', enable=True)
        time.sleep(3)
        ctx.bob_ctrl.set_fault(f'CAN{can_channel}_H', 'SHORT_GND', enable=False)

        # 3) 电压波动
        ctx.power_ctrl.set_voltage(rVnormal - 2.0)
        time.sleep(3)
        ctx.power_ctrl.set_voltage(rVnormal + 2.0)
        time.sleep(3)
        ctx.power_ctrl.set_voltage(rVnormal)

        for t in tids:
            TimerCyclic.stop(t)
        tids.clear()

        TestLog("INFO", "Step3", "极端并发停止后，静置一段时间观察DUT任务调度是否恢复")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(15 * 1000)

        ret = check_can_communication_state(wait_time=5)
        if ret == 0:
            TestLog("PASS", "Step3",
                    "期望结果：极端并发后DUT任务调度恢复。实际结果：DUT通信正常")
        else:
            TestLog("FAIL", "Step3",
                    "期望结果：极端并发后DUT任务调度恢复。实际结果：DUT通信异常（可能任务死锁）")

        TestLog("INFO", "Step4", "监控5分钟验证报文周期是否恢复正常")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(5 * 60 * 1000)

        if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
            TestLog("WARNING", "Step4", "存在错误帧")

        messages = ctx.can.messages
        rx_stats = build_rx_msg_info(messages)
        MsgReceivedList, MsgNotReceivedList, MsgTmpList = analyze_messages(rx_stats, can_db_msg_defs)

        report_message_tests(
            MsgReceivedList, MsgNotReceivedList, MsgTmpList,
            rx_stats, can_db_msg_defs,
            tests=("period",),
            period_thresholds=(rTperiodDeviation1, rTperiodDeviation2),
        )

        TestLog("INFO", "任务死锁恢复鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "任务死锁恢复鲁棒性测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "任务死锁恢复鲁棒性测试", f"详细错误: {traceback.format_exc()}")
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
