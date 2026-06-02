"""
MCU/MPU 鲁棒性测试用例

通过CAN总线层面的间接观测来验证ECU内部MCU/MPU行为。
这些用例不直接访问ECU内核，而是通过通信状态变化推断内核健康度。

TODO: 某些测试需要ECU支持特定的诊断服务（如内核状态读取）才能完全验证。
当前实现侧重于通过外部可观测的CAN行为来判断。
"""
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


class MCUMPURobustTestFixture(TestFixture):
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


# ========== 测试用例 ==========

def test_TG1_TC1_IPCStressRecoveryTest():
    """IPC压力恢复鲁棒性测试 - 通过极高总线负载模拟多核IPC通信压力，验证DUT核间通信恢复能力"""
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

        TestLog("INFO", "Step2", "注入极高频率的多ID报文（模拟多核IPC通信压力）")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)

        # 大量不同ID的高频报文模拟跨核通信
        for idx, burst_id in enumerate(range(0x500, 0x510)):
            msg = canmsg_create(burst_id, 8, data=0xA5, rtr=0, fdf=0, brs=0, ext=0)
            tid = 400 + idx
            TimerCyclic.start(tid, 2, send_canmsg, can_channel, msg=msg)
            tids.append(tid)

        TestLog("INFO", "Step2", "IPC压力持续60秒")
        sl_time().sleep(60 * 1000)

        for t in tids:
            TimerCyclic.stop(t)
        tids.clear()

        TestLog("INFO", "Step3", "停止IPC压力后验证核间通信恢复（通过CAN通信状态间接判断）")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(10 * 1000)

        ret = check_can_communication_state(wait_time=5)
        if ret == 0:
            TestLog("PASS", "Step3",
                    "期望结果：IPC压力后DUT通信恢复。实际结果：DUT通信正常")
        else:
            TestLog("FAIL", "Step3",
                    "期望结果：IPC压力后DUT通信恢复。实际结果：DUT通信异常（可能核间通信故障）")

        TestLog("INFO", "Step4", "监控5分钟验证报文周期偏移")
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

        TestLog("INFO", "IPC压力恢复鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "IPC压力恢复鲁棒性测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "IPC压力恢复鲁棒性测试", f"详细错误: {traceback.format_exc()}")
    finally:
        for t in tids:
            try:
                TimerCyclic.stop(t)
            except:
                pass


def test_TG1_TC2_AsymmetricCoreFaultTest():
    """非对称核心故障鲁棒性测试 - 模拟单核心异常，验证DUT多核故障隔离与恢复"""
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

        TestLog("INFO", "Step2", "模拟单核心过载故障：只对特定ID范围报文产生冲突")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)

        # 只对特定ID范围注入冲突，模拟单核心处理异常
        for burst_id in range(0x100, 0x108):
            msg = canmsg_create(burst_id, 8, data=0xFF, rtr=0, fdf=0, brs=0, ext=0)
            tid = 500 + burst_id
            TimerCyclic.start(tid, 3, send_canmsg, can_channel, msg=msg)
            tids.append(tid)

        sl_time().sleep(30 * 1000)

        for t in tids:
            TimerCyclic.stop(t)
        tids.clear()

        TestLog("INFO", "Step3", "验证其他核心(未被压测的ID范围)的通信是否保持正常")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(10 * 1000)

        ret = check_can_communication_state(wait_time=5)
        if ret == 0:
            TestLog("PASS", "Step3",
                    "期望结果：非对称核心故障后DUT整体通信正常（故障核心已隔离）。"
                    "实际结果：DUT通信正常")
        else:
            TestLog("FAIL", "Step3",
                    "期望结果：非对称核心故障后通信正常。"
                    "实际结果：DUT通信异常（故障可能传播到其他核心）")

        TestLog("INFO", "Step4", "监控5分钟验证长期运行不出现级联故障")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(5 * 60 * 1000)

        final_msgs = len(ctx.can.messages)
        final_errs = ctx.can.get_info('gErrorFrameCount') or 0
        if final_msgs > 0 and final_errs == 0:
            TestLog("PASS", "Step4",
                    f"期望结果：无级联故障。实际结果：{final_msgs}条报文, 0个错误帧")
        else:
            TestLog("WARNING", "Step4",
                    f"可能存在级联故障: 报文={final_msgs}, 错误帧={final_errs}")

        TestLog("INFO", "非对称核心故障鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "非对称核心故障鲁棒性测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "非对称核心故障鲁棒性测试", f"详细错误: {traceback.format_exc()}")
    finally:
        for t in tids:
            try:
                TimerCyclic.stop(t)
            except:
                pass


def test_TG1_TC3_BootSequencingStressTest():
    """启动时序压力鲁棒性测试 - 在各种异常启动时序下验证DUT启动可靠性与时序容差"""
    try:
        rVnormal = P.CANInfo.Vnormal
        rVlowStand = P.CANInfo.VlowStand
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，将KL30上电，等待{rTstable_s}s至通信稳定（基准）")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.set_filter_by_channel(can_channel)

        TestLog("INFO", "Step2", "测试多种异常启动时序")
        timing_scenarios = [
            ("KL30先上电，电压缓慢爬升", lambda: [
                ctx.bob_ctrl.set_power('KL30', True),
                time.sleep(0.1),
                ctx.power_ctrl.set_voltage(rVnormal),
                WakeupStart(),
            ]),
            ("电压先到位，KL30延迟上电", lambda: [
                ctx.power_ctrl.set_voltage(rVnormal),
                time.sleep(2),
                ctx.bob_ctrl.set_power('KL30', True),
                WakeupStart(),
            ]),
            ("低电压下KL30上电，然后升压", lambda: [
                ctx.power_ctrl.set_voltage(rVlowStand),
                ctx.bob_ctrl.set_power('KL30', True),
                time.sleep(1),
                ctx.power_ctrl.set_voltage(rVnormal),
                WakeupStart(),
            ]),
        ]

        all_passed = True
        for desc, sequencer in timing_scenarios:
            # 先断电
            ctx.bob_ctrl.set_power('KL30', False)
            ctx.bob_ctrl.set_power('KL15', False)
            ctx.power_ctrl.set_voltage(0)
            time.sleep(3)

            TestLog("INFO", "Step2", f"测试启动时序: {desc}")
            sequencer()
            sl_time().sleep(int(rTstable_s * 1000))

            ret = check_can_communication_state(wait_time=3)
            if ret == 0:
                TestLog("PASS", "Step2", f"{desc}: DUT正常启动并通信")
            else:
                TestLog("FAIL", "Step2", f"{desc}: DUT启动或通信异常")
                all_passed = False

        TestLog("INFO", "Step3", "所有异常启动时序测试后回到正常启动")
        ctx.bob_ctrl.set_power('KL30', False)
        ctx.power_ctrl.set_voltage(0)
        time.sleep(3)
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret == 0:
            TestLog("PASS", "Step3",
                    "期望结果：异常时序测试后正常启动仍可靠。实际结果：DUT通信正常")
        else:
            TestLog("FAIL", "Step3", "期望结果：正常启动仍可靠。实际结果：DUT通信异常")
            all_passed = False

        if all_passed:
            TestLog("PASS", "启动时序压力鲁棒性测试", "所有启动时序测试通过")
        else:
            TestLog("WARNING", "启动时序压力鲁棒性测试", "部分启动时序测试未通过")

    except Exception as e:
        TestLog("FAIL", "启动时序压力鲁棒性测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "启动时序压力鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC4_InterruptStormToleranceTest():
    """中断风暴容忍鲁棒性测试 - 大量并发报文事件，验证DUT中断处理与调度保护"""
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

        TestLog("INFO", "Step2", "注入大量不同ID和DLC的报文模拟中断风暴")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)

        # 大量不同形态的报文触发不同中断处理路径
        for idx, burst_id in enumerate(range(0x600, 0x620)):
            dlc = 1 + (idx % 8)  # 不同DLC
            data = (idx & 0xFF)
            ext = 1 if idx % 3 == 0 else 0  # 部分扩展帧
            msg = canmsg_create(burst_id, dlc, data=data, rtr=0, fdf=0, brs=0, ext=ext)
            if msg:
                tid = 600 + idx
                TimerCyclic.start(tid, 10, send_canmsg, can_channel, msg=msg)
                tids.append(tid)

        TestLog("INFO", "Step2", "中断风暴持续120秒")
        sl_time().sleep(120 * 1000)

        for t in tids:
            TimerCyclic.stop(t)
        tids.clear()

        TestLog("INFO", "Step3", "停止中断风暴后验证DUT中断调度恢复（通信恢复）")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(10 * 1000)

        ret = check_can_communication_state(wait_time=5)
        if ret == 0:
            TestLog("PASS", "Step3",
                    "期望结果：中断风暴后DUT调度恢复。实际结果：DUT通信正常")
        else:
            TestLog("FAIL", "Step3",
                    "期望结果：中断风暴后DUT调度恢复。实际结果：DUT通信异常（可能中断系统崩溃）")

        TestLog("INFO", "Step4", "监控5分钟验证中断风暴后长期稳定性")
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

        TestLog("INFO", "中断风暴容忍鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "中断风暴容忍鲁棒性测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "中断风暴容忍鲁棒性测试", f"详细错误: {traceback.format_exc()}")
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
