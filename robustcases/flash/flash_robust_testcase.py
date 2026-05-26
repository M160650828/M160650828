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
)


class FlashRobustTestFixture(TestFixture):
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


def test_TG1_TC1_VoltageDipDuringOperationTest():
    """运行中电压跌落鲁棒性测试"""
    try:
        rVnormal = P.CANInfo.Vnormal
        rVlowStand = P.CANInfo.VlowStand
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

        TestLog("INFO", "Step2",
                f"多次执行电压跌落测试: 从{rVnormal}V降至{rVlowStand}V, 保持{rTvStepDelay}ms, 恢复{rVnormal}V")
        dip_cycles = min(P.CANInfo.Tcount, 5)
        all_recovered = True

        for i in range(1, dip_cycles + 1):
            TestLog("INFO", "Step2", f"第{i}/{dip_cycles}次电压跌落")

            ctx.can.clear_messages()
            ctx.can.set_info('gErrorFrameCount', 0)

            ctx.power_ctrl.set_voltage(rVlowStand)
            sl_time().sleep(rTvStepDelay)

            ctx.power_ctrl.set_voltage(rVnormal)
            sl_time().sleep(3 * 1000)

            err_count = ctx.can.get_info('gErrorFrameCount') or 0
            msg_count = len(ctx.can.messages)

            ret = check_can_communication_state(wait_time=2)
            if ret == 0:
                TestLog("PASS", "Step2",
                        f"第{i}次: 电压恢复后通信正常 (报文={msg_count}, 错误帧={err_count})")
            else:
                TestLog("FAIL", "Step2",
                        f"第{i}次: 电压恢复后通信异常 (报文={msg_count}, 错误帧={err_count})")
                all_recovered = False

        TestLog("INFO", "Step3", "最后一次电压跌落后监控5分钟以验证长期稳定性")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(5 * 60 * 1000)

        final_msgs = len(ctx.can.messages)
        final_errs = ctx.can.get_info('gErrorFrameCount') or 0

        if final_msgs > 0 and final_errs == 0:
            TestLog("PASS", "Step3",
                    f"期望结果：长期通信稳定。实际结果：{final_msgs}条报文, 0个错误帧")
        else:
            TestLog("WARNING", "Step3",
                    f"长期通信有异常: 报文={final_msgs}, 错误帧={final_errs}")

        if all_recovered:
            TestLog("PASS", "运行中电压跌落鲁棒性测试", "所有电压跌落后DUT均恢复正常通信")
        else:
            TestLog("WARNING", "运行中电压跌落鲁棒性测试", "部分电压跌落后DUT通信恢复异常")

    except Exception as e:
        TestLog("FAIL", "运行中电压跌落鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "运行中电压跌落鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC2_RepeatedKL30PowerCycleTest():
    """反复KL30上下电后通信恢复鲁棒性测试"""
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        cycle_count = min(P.CANInfo.Tcount, 10)

        TestLog("INFO", "Step1",
                f"执行{cycle_count}次KL30快速上下电循环测试")
        for i in range(1, cycle_count + 1):
            TestLog("INFO", "Step1", f"第{i}/{cycle_count}次KL30上下电")
            ctx.power_ctrl.set_voltage(rVnormal)
            ctx.bob_ctrl.set_power('KL30', True)
            time.sleep(1)
            ctx.bob_ctrl.set_power('KL30', False)
            ctx.power_ctrl.set_voltage(0)
            time.sleep(0.5)

        TestLog("INFO", "Step2",
                f"执行完{cycle_count}次上下电后, 设置正常电压{rVnormal}V, 唤醒DUT, 验证通信恢复")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step2", "反复上下电后DUT通信检查失败")
            return
        TestLog("PASS", "Step2",
                f"期望结果：{cycle_count}次KL30上下电后DUT仍能正常通信。"
                f"实际结果：DUT通信正常")

        TestLog("INFO", "Step3", "监控3分钟，检查通信稳定性")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(3 * 60 * 1000)

        err_count = ctx.can.get_info('gErrorFrameCount') or 0
        msg_count = len(ctx.can.messages)

        if msg_count > 0 and err_count == 0:
            TestLog("PASS", "Step3",
                    f"期望结果：通信稳定无错误帧。实际结果：{msg_count}条报文, 0个错误帧")
        else:
            TestLog("WARNING", "Step3",
                    f"通信存在问题: 报文={msg_count}, 错误帧={err_count}")

        TestLog("INFO", "反复KL30上下电鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "反复KL30上下电鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "反复KL30上下电鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def get_all_test_cases():
    import inspect
    current_module = inspect.getmodule(inspect.currentframe())
    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj
    return test_cases
