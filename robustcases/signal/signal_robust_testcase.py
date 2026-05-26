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
from common.can_utils import send_canmsg, canmsg_create
from common.utils import TimerCyclic
from common.signal_parser import sig
from common.db_parser import sigdb
from slplus.time import sl_time

from testcases.can.can_module import (
    can_initialization, can_deinitialization,
    can_power_setup_and_communication_check,
    check_can_communication_state,
)


class SignalRobustTestFixture(TestFixture):
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


def test_TG1_TC1_SignalTimeoutDetectionTest():
    """信号超时检测鲁棒性测试"""
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        rTinitial = P.CANInfo.Tinitial_min
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.set_filter_by_channel(can_channel)

        TestLog("INFO", "Step2", f"监控总线{rTinitial}分钟，建立初始信号数据基线")
        ctx.can.clear_messages()
        sig.clear()
        sl_time().sleep(int(rTinitial * 60 * 1000))

        TestLog("INFO", "Step2", f"收到{len(ctx.can.messages)}条报文")
        sig.load_messages(list(ctx.can.messages))

        tx_signal_names = sigdb.ecu_tx_signal_names()
        TestLog("INFO", "Step2", f"ECU TX信号数量: {len(tx_signal_names)}")

        pass_count, fail_count, warn_count = 0, 0, 0
        checked_count = 0

        for signal_name in tx_signal_names:
            sig_accessor = getattr(sig, signal_name)
            sig_def = sigdb.get_signal_def(signal_name)
            if sig_def is None:
                continue

            msg_def = sigdb.get_msg_def(sig_def.msg_id)
            if msg_def is None:
                continue

            cycle_ms = msg_def.get('cycle', 0)
            if cycle_ms <= 0:
                continue

            checked_count += 1

            timestamps = sig_accessor.timestamps if hasattr(sig_accessor, 'timestamps') else []
            if len(timestamps) < 2:
                warn_count += 1
                continue

            max_gap_ms = 0
            for i in range(1, len(timestamps)):
                gap = timestamps[i] - timestamps[i - 1]
                if gap > max_gap_ms:
                    max_gap_ms = gap

            max_allowed_ms = cycle_ms * 3

            if max_gap_ms <= max_allowed_ms:
                pass_count += 1
            else:
                TestLog("FAIL", "信号超时",
                        f"(0x{sig_def.msg_id:X}),{signal_name}: "
                        f"最大间隔={max_gap_ms:.0f}ms > 允许={max_allowed_ms}ms (Cycle={cycle_ms}ms)")
                fail_count += 1

        TestLog("INFO", "Step3",
                f"信号超时检测完成: 通过={pass_count}, 失败={fail_count}, 数据不足={warn_count}, 检查={checked_count}")

        if fail_count == 0:
            TestLog("PASS", "信号超时检测鲁棒性测试",
                    f"所有{checked_count}个周期信号更新间隔正常 (阈值=3倍cycle)")
        else:
            TestLog("FAIL", "信号超时检测鲁棒性测试",
                    f"{fail_count}个信号超时 / {checked_count}个周期信号")

    except Exception as e:
        TestLog("FAIL", "信号超时检测鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "信号超时检测鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC2_SignalValueOutOfRangeTest():
    """信号值超范围鲁棒性测试"""
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        rTinitial = P.CANInfo.Tinitial_min
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.set_filter_by_channel(can_channel)

        TestLog("INFO", "Step2", f"监控总线{rTinitial}分钟，收集信号数据")
        ctx.can.clear_messages()
        sig.clear()
        sl_time().sleep(int(rTinitial * 60 * 1000))

        sig.load_messages(list(ctx.can.messages))
        TestLog("INFO", "Step2", f"收集{len(ctx.can.messages)}条报文进行信号值分析")

        tx_signal_names = sigdb.ecu_tx_signal_names()
        pass_count, fail_count, warn_count = 0, 0, 0

        for signal_name in tx_signal_names:
            sig_def = sigdb.get_signal_def(signal_name)
            if sig_def is None:
                continue

            sig_accessor = getattr(sig, signal_name)

            factor = getattr(sig_def, 'factor', 1.0) or 1.0
            offset = getattr(sig_def, 'offset', 0.0) or 0.0
            phy_min = getattr(sig_def, 'phy_min', None)
            phy_max = getattr(sig_def, 'phy_max', None)

            if phy_min is None and phy_max is None:
                continue

            raw_values = sig_accessor.raw if hasattr(sig_accessor, 'raw') else []
            if not raw_values:
                warn_count += 1
                continue

            out_of_range = False
            for raw in raw_values:
                if raw is None:
                    continue
                phy = raw * factor + offset
                if phy_min is not None and phy < phy_min:
                    out_of_range = True
                    TestLog("FAIL", "信号超范围",
                            f"(0x{sig_def.msg_id:X}),{signal_name}: "
                            f"phy={phy:.3f} < 最小值={phy_min}")
                    break
                if phy_max is not None and phy > phy_max:
                    out_of_range = True
                    TestLog("FAIL", "信号超范围",
                            f"(0x{sig_def.msg_id:X}),{signal_name}: "
                            f"phy={phy:.3f} > 最大值={phy_max}")
                    break

            if out_of_range:
                fail_count += 1
            else:
                pass_count += 1

        TestLog("INFO", "Step3",
                f"信号值范围校验完成: 通过={pass_count}, 失败={fail_count}, 无数据={warn_count}")

        if fail_count == 0:
            TestLog("PASS", "信号值超范围鲁棒性测试",
                    f"所有信号值均在数据库定义的物理范围内")
        else:
            TestLog("FAIL", "信号值超范围鲁棒性测试",
                    f"{fail_count}个信号值超出物理范围")

    except Exception as e:
        TestLog("FAIL", "信号值超范围鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "信号值超范围鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC3_StaleSignalDataTest():
    """信号数据停滞（Stale Data）鲁棒性测试"""
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        monitor_duration_min = 5

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.set_filter_by_channel(can_channel)
        sig.clear()

        TestLog("INFO", "Step2",
                f"监控{monitor_duration_min}分钟，检测信号值是否正常更新（非停滞）")
        start_time = time.time()
        while time.time() - start_time < monitor_duration_min * 60:
            sl_time().sleep(30 * 1000)
            elapsed = (time.time() - start_time) / 60
            TestLog("INFO", "Step2", f"已监控{elapsed:.1f}分钟...")

        sig.load_messages(list(ctx.can.messages))
        TestLog("INFO", "Step2", f"总计收到{len(ctx.can.messages)}条报文")

        tx_signal_names = sigdb.ecu_tx_signal_names()
        pass_count, fail_count, warn_count = 0, 0, 0

        for signal_name in tx_signal_names:
            sig_def = sigdb.get_signal_def(signal_name)
            if sig_def is None:
                continue

            msg_def = sigdb.get_msg_def(sig_def.msg_id)
            if msg_def is None:
                continue

            cycle_ms = msg_def.get('cycle', 0)
            if cycle_ms == 0:
                continue

            sig_accessor = getattr(sig, signal_name)
            values = sig_accessor.phy if hasattr(sig_accessor, 'phy') else []

            if len(values) < 2:
                warn_count += 1
                continue

            unique_count = len(set(round(v, 2) for v in values if v is not None))
            total_count = len(values)

            if unique_count <= 1 and total_count > 10:
                TestLog("FAIL", "信号停滞",
                        f"(0x{sig_def.msg_id:X}),{signal_name}: "
                        f"{total_count}个采样点只有{unique_count}个唯一值——信号可能停滞")
                fail_count += 1
            else:
                pass_count += 1

        TestLog("INFO", "Step3",
                f"信号停滞检测完成: 通过={pass_count}, 疑似停滞={fail_count}, 数据不足={warn_count}")

        if fail_count == 0:
            TestLog("PASS", "信号停滞检测鲁棒性测试",
                    "所有周期信号正常更新，无停滞现象")
        else:
            TestLog("WARNING", "信号停滞检测鲁棒性测试",
                    f"{fail_count}个信号可能停滞，需人工确认")

    except Exception as e:
        TestLog("FAIL", "信号停滞检测鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "信号停滞检测鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def get_all_test_cases():
    import inspect
    current_module = inspect.getmodule(inspect.currentframe())
    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj
    return test_cases
