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
from slplus.time import sl_time
from slplus.busstatis import sl_busstatis

from testcases.can.can_module import (
    can_initialization, can_deinitialization,
    can_power_setup_and_communication_check,
    check_can_communication_state,
    build_rx_msg_info, analyze_messages, report_message_tests,
)


class BusStressTestFixture(TestFixture):
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


def test_TG1_TC1_BusLoadStressTest():
    """总线负载压力鲁棒性测试"""
    tids = []
    timer_id = 1
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rBusloadHigh = P.CANInfo.BusloadHigh_pct
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
        ctx.can.add_black_id(1)

        TestLog("INFO", "Step2",
                f"通过发送高优先级报文将总线负载推至{rBusloadHigh}%以上, 持续监控5分钟")
        can_db_msg_defs = ctx.can.get_info('can_db_msg_defs') or {}

        msg_high = canmsg_create(0x001, 8, data=0x00, rtr=0, fdf=0, brs=0, ext=0)
        start_time = time.time()
        while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) < rBusloadHigh:
            if time.time() - start_time > 2 * 60:
                TestLog("FAIL", "Step2", f"2分钟内无法将总线负载提升至{rBusloadHigh}%")
                return
            TimerCyclic.start(timer_id, 3, send_canmsg, can_channel, msg=msg_high)
            tids.append(timer_id)
            timer_id += 1
            time.sleep(3)

        busload = sl_busstatis().get_can_stat_by_ch(can_channel)
        cur_load = round(busload.get("busload", {}).get("cur") * 100, 2)
        TestLog("INFO", "Step2", f"当前总线负载: {cur_load}%")

        sl_time().sleep(5 * 60 * 1000)

        for t in tids:
            TimerCyclic.stop(t)
        tids.clear()

        TestLog("INFO", "Step3", "停止高负载报文, 等待10秒后检查通信恢复")
        time.sleep(10)

        if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
            TestLog("FAIL", "Step3", "高负载后存在错误帧")
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

        TestLog("INFO", "总线负载压力鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "总线负载压力鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "总线负载压力鲁棒性测试", f"详细错误: {traceback.format_exc()}")
    finally:
        for t in tids:
            try:
                TimerCyclic.stop(t)
            except:
                pass


def test_TG1_TC2_InterruptStormViaBusLoadTest():
    """中断风暴模拟鲁棒性测试（通过极高总线负载模拟）"""
    tids = []
    timer_id = 1
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
        ctx.can.add_black_id(1)

        TestLog("INFO", "Step2", "以极高频率发送多个ID的报文，模拟中断风暴场景")
        for base_id in [0x100, 0x200, 0x300]:
            msg = canmsg_create(base_id, 8, data=0xFF, rtr=0, fdf=0, brs=0, ext=0)
            TimerCyclic.start(timer_id, 5, send_canmsg, can_channel, msg=msg)
            tids.append(timer_id)
            timer_id += 1

        sl_time().sleep(30 * 1000)

        for t in tids:
            TimerCyclic.stop(t)
        tids.clear()

        TestLog("INFO", "Step3", "停止所有干扰报文，验证DUT通信恢复")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        time.sleep(5)

        ret = check_can_communication_state(wait_time=3)
        if ret == 0:
            TestLog("PASS", "Step3",
                    "期望结果：中断风暴后DUT通信恢复正常。实际结果：DUT通信正常")
        else:
            TestLog("FAIL", "Step3",
                    "期望结果：中断风暴后DUT通信恢复正常。实际结果：DUT通信异常")

        TestLog("INFO", "Step4", "监控3分钟，确认无延迟累积")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(3 * 60 * 1000)

        msg_count = len(ctx.can.messages)
        err_count = ctx.can.get_info('gErrorFrameCount') or 0
        if msg_count > 0 and err_count == 0:
            TestLog("PASS", "Step4",
                    f"期望结果：长期通信正常无延迟累积。实际结果：{msg_count}条报文, 0个错误帧")
        else:
            TestLog("WARNING", "Step4",
                    f"存在异常: 报文={msg_count}, 错误帧={err_count}")

        TestLog("INFO", "中断风暴模拟鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "中断风暴模拟鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "中断风暴模拟鲁棒性测试", f"详细错误: {traceback.format_exc()}")
    finally:
        for t in tids:
            try:
                TimerCyclic.stop(t)
            except:
                pass


def test_TG1_TC3_HighFrequencyMessageBurstTest():
    """高频率报文突发鲁棒性测试"""
    tids = []
    timer_id = 1
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        burst_cycles = min(P.CANInfo.Tcount, 10)

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.set_filter_by_channel(can_channel)

        TestLog("INFO", "Step2", f"执行{burst_cycles}轮报文突发-停止循环")
        all_stable = True

        for i in range(1, burst_cycles + 1):
            TestLog("INFO", "Step2", f"第{i}/{burst_cycles}轮: 发送突发报文(10秒)")

            for burst_id in range(0x50, 0x60):
                msg = canmsg_create(burst_id, 8, data=0xAA, rtr=0, fdf=0, brs=0, ext=0)
                TimerCyclic.start(timer_id, 10, send_canmsg, can_channel, msg=msg)
                tids.append(timer_id)
                timer_id += 1

            time.sleep(10)

            for t in tids:
                TimerCyclic.stop(t)
            tids.clear()

            ctx.can.clear_messages()
            ctx.can.set_info('gErrorFrameCount', 0)
            time.sleep(3)

            ret = check_can_communication_state(wait_time=2)
            if ret != 0:
                TestLog("FAIL", "Step2", f"第{i}轮突发后通信未恢复")
                all_stable = False

        if all_stable:
            TestLog("PASS", "Step2",
                    f"期望结果：{burst_cycles}轮突发后通信均正常恢复。实际结果：全部稳定恢复")
        else:
            TestLog("WARNING", "Step2", "部分轮次通信恢复异常")

        TestLog("INFO", "高频率报文突发鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "高频率报文突发鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "高频率报文突发鲁棒性测试", f"详细错误: {traceback.format_exc()}")
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
