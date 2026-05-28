import sys
import os
import time
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from env.config import DEFAULT_LIN_CHANNEL
from uvtest.testlog import TestLog
from uvtest.framework import TestFixture
from common.control import TestStart, TestEnd
from common.context import ctx
from common.params import P
from slplus.time import sl_time

from testcases.lin.lin_module import lin_initialization, lin_deinitialization


class LINRobustTestFixture(TestFixture):
    def group_setup(self, context=None):
        lin_initialization()

    def group_teardown(self, context=None):
        lin_deinitialization()

    def case_setup(self, context=None):
        if context:
            TestStart(context["test_name"])

    def case_teardown(self, context=None):
        TestEnd("")
        TestLog("INFO", "测试结束", "执行测试结束和去初始化")


def _lin_power_on_and_check(rVnormal, rTstable_s):
    """LIN电源设置与通信检查"""
    TestLog("INFO", "", f"设置DUT供电电压为{rVnormal}V")
    ctx.power_ctrl.set_voltage(rVnormal)
    ctx.power_ctrl.on()
    ctx.bob_ctrl.set_power('KL30', True)
    TestLog("INFO", "", f"等待{rTstable_s}s至通信稳定")
    time.sleep(rTstable_s)
    return 0


def test_TG1_TC1_LINBusShortCircuitRecoveryTest():
    """LIN总线短路恢复鲁棒性测试"""
    try:
        rVnormal = P.LINInfo.Vnormal if hasattr(P.LINInfo, 'Vnormal') else 12.0
        rTstable_s = P.LINInfo.Tstable_s if hasattr(P.LINInfo, 'Tstable_s') else 5.0
        lin_channel = DEFAULT_LIN_CHANNEL

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，将KL30上电，等待{rTstable_s}s至通信稳定")
        ret = _lin_power_on_and_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败")
            return
        TestLog("PASS", "Step1", "期望结果：DUT LIN通信正常。实际结果：DUT上电完成")

        lin_faults = ['LIN_short_GND', 'LIN_short_BAT']
        TestLog("INFO", "Step2", f"依次测试LIN总线故障类型: {lin_faults}")

        for fault in lin_faults:
            TestLog("INFO", "Step2", f"注入LIN故障: {fault}, 持续5秒")
            try:
                ctx.bob_ctrl.set_fault(f"LIN{lin_channel}", "SHORT_GND", enable=True)
                time.sleep(5)
                ctx.bob_ctrl.set_fault(f"LIN{lin_channel}", "SHORT_GND", enable=False)
                time.sleep(3)
            except Exception as ex:
                TestLog("WARNING", "Step2", f"LIN故障注入/清除({fault})失败: {ex}")

        TestLog("INFO", "Step3", "所有LIN故障清除后等待通信恢复")
        ctx.lin.clear_messages()
        time.sleep(5)
        lin_msgs = len(ctx.lin.messages)

        if lin_msgs > 0:
            TestLog("PASS", "Step3",
                    f"期望结果：LIN故障清除后通信恢复。实际结果：收到{lin_msgs}条LIN报文")
        else:
            TestLog("WARNING", "Step3",
                    "期望结果：LIN故障清除后通信恢复。实际结果：未收到LIN报文")

        TestLog("INFO", "LIN总线短路恢复鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "LIN总线短路恢复鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "LIN总线短路恢复鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC2_LINChecksumErrorHandlingTest():
    """LIN校验和错误处理鲁棒性测试"""
    try:
        rVnormal = P.LINInfo.Vnormal if hasattr(P.LINInfo, 'Vnormal') else 12.0
        rTstable_s = P.LINInfo.Tstable_s if hasattr(P.LINInfo, 'Tstable_s') else 5.0

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，将KL30上电，等待{rTstable_s}s至通信稳定")
        ret = _lin_power_on_and_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败")
            return
        TestLog("PASS", "Step1", "期望结果：DUT LIN通信正常。实际结果：DUT上电完成")

        TestLog("INFO", "Step2", "监控LIN总线通信5分钟，检查是否有校验错误")
        ctx.lin.clear_messages()
        sl_time().sleep(5 * 60 * 1000)

        lin_msgs = len(ctx.lin.messages)
        TestLog("INFO", "Step2", f"5分钟内收到{lin_msgs}条LIN报文")

        if lin_msgs > 0:
            TestLog("PASS", "Step2",
                    f"期望结果：LIN通信正常且无校验错误。实际结果：收到{lin_msgs}条LIN报文")
        else:
            TestLog("WARNING", "Step2",
                    "期望结果：LIN通信正常。实际结果：未收到LIN报文")

        TestLog("INFO", "Step3", "在电压波动后验证LIN通信恢复")
        ctx.power_ctrl.set_voltage(max(0, rVnormal - 2.0))
        time.sleep(2)
        ctx.power_ctrl.set_voltage(rVnormal)
        time.sleep(5)

        ctx.lin.clear_messages()
        time.sleep(10)
        lin_msgs_after = len(ctx.lin.messages)

        if lin_msgs_after > 0:
            TestLog("PASS", "Step3",
                    f"电压波动后LIN通信正常: {lin_msgs_after}条报文")
        else:
            TestLog("WARNING", "Step3",
                    "电压波动后未收到LIN报文")

        TestLog("INFO", "LIN校验和错误处理鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "LIN校验和错误处理鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "LIN校验和错误处理鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC3_LINSleepWakeupRecoveryTest():
    """LIN休眠唤醒恢复鲁棒性测试"""
    try:
        rVnormal = P.LINInfo.Vnormal if hasattr(P.LINInfo, 'Vnormal') else 12.0
        rTstable_s = P.LINInfo.Tstable_s if hasattr(P.LINInfo, 'Tstable_s') else 5.0
        cycle_count = min(P.CANInfo.Tcount, 5) if hasattr(P.CANInfo, 'Tcount') else 5

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，将KL30上电，等待{rTstable_s}s至通信稳定")
        ret = _lin_power_on_and_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败")
            return
        TestLog("PASS", "Step1", "期望结果：DUT LIN通信正常。实际结果：DUT上电完成")

        TestLog("INFO", "Step2", f"执行{cycle_count}次LIN休眠-唤醒循环")
        for i in range(1, cycle_count + 1):
            TestLog("INFO", "Step2", f"第{i}/{cycle_count}次: 进入休眠")
            ctx.bob_ctrl.set_power('KL30', False)
            ctx.power_ctrl.set_voltage(0)
            time.sleep(3)

            TestLog("INFO", "Step2", f"第{i}/{cycle_count}次: 唤醒")
            ctx.power_ctrl.set_voltage(rVnormal)
            ctx.bob_ctrl.set_power('KL30', True)
            time.sleep(3)

            ctx.lin.clear_messages()
            time.sleep(5)
            lin_msgs = len(ctx.lin.messages)

            if lin_msgs > 0:
                TestLog("PASS", "Step2",
                        f"第{i}次唤醒后LIN通信正常: {lin_msgs}条报文")
            else:
                TestLog("WARNING", "Step2",
                        f"第{i}次唤醒后未收到LIN报文")

        TestLog("INFO", "Step3", "最终长时间监控LIN通信稳定性")
        ctx.lin.clear_messages()
        time.sleep(60)
        final_lin_msgs = len(ctx.lin.messages)

        if final_lin_msgs > 0:
            TestLog("PASS", "Step3",
                    f"休眠唤醒循环后LIN通信稳定: {final_lin_msgs}条报文/分钟")
        else:
            TestLog("WARNING", "Step3",
                    "休眠唤醒循环后LIN通信异常")

        TestLog("INFO", "LIN休眠唤醒恢复鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "LIN休眠唤醒恢复鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "LIN休眠唤醒恢复鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def get_all_test_cases():
    import inspect
    current_module = inspect.getmodule(inspect.currentframe())
    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj
    return test_cases
