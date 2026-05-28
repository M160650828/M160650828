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
from slplus.time import sl_time

from testcases.nm.nm_module import (
    nm_initialization, nm_deinitialization,
    nm_power_on, nm_start_wakeup, nm_stop_wakeup,
    nm_wakeup_and_wait_first_msg,
    nm_check_comm_stop_and_sleep_current,
    nm_check_nm_and_app_msgs,
)
from testcases.nm.nm_autosar_utils import (
    wait_dut_enter_sleep, get_nm_message_list, wakeup_active_start, wakeup_active_stop,
    wakeup_passive_start, wakeup_passive_stop, wait_dut_send_first_msg,
    check_repeat_message_state_after_active_wakeup, check_normal_state,
    check_ready_sleep_state, check_repeat_message_state,
    repeat_msg_state_req_stop, check_bus_sleep_state,
    get_msg_first_ms, clear_ctx_can_messages,
    wait_nm_message, wait_nm_message_stop, check_active_wakeup_bit,
    prepare_sleep_state_test_start, prepare_sleep_state_test_stop,
)


class NMRobustTestFixture(TestFixture):
    def group_setup(self, context=None):
        nm_initialization()

    def group_teardown(self, context=None):
        nm_deinitialization()

    def case_setup(self, context=None):
        if context:
            TestStart(context["test_name"])

    def case_teardown(self, context=None):
        wakeup_active_stop()
        wakeup_passive_stop()
        repeat_msg_state_req_stop()
        prepare_sleep_state_test_stop()
        clear_ctx_can_messages()
        TestEnd("")
        TestLog("INFO", "测试结束", "执行测试结束和去初始化")


def test_TG1_TC1_RepeatedSleepWakeupCyclingTest():
    """重复休眠唤醒循环鲁棒性测试"""
    try:
        rIsleep_mA = P.ECUInfo.ISleep
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rVnormal = P.NMInfo.Vnormal
        cycle_count = max(P.CANInfo.Tcount, 10)

        TestLog("INFO", "Step1", f"设置DUT电源电压为{rVnormal}V，执行KL30上电, 等待DUT进入睡眠")
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "Step1", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "Step1", "DUT已进入睡眠模式")

        TestLog("INFO", "Step2", f"执行{cycle_count}次主动唤醒-睡眠循环")
        passed_cycles = 0

        for i in range(1, cycle_count + 1):
            TestLog("INFO", "Step2", f"第{i}/{cycle_count}次: 触发主动唤醒")
            clear_ctx_can_messages()
            wakeup_active_start()

            status, nm_messages = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
            if status:
                TestLog("INFO", "Step2", f"第{i}次: 收到NM报文, NM唤醒成功")
            else:
                TestLog("WARNING", "Step2", f"第{i}次: 未收到NM报文")

            TestLog("INFO", "Step2", f"第{i}/{cycle_count}次: 停止唤醒, 等待DUT重新进入睡眠")
            wakeup_active_stop()

            status2, msg2 = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
            if status2:
                TestLog("INFO", "Step2", f"第{i}次: DUT重新进入睡眠")
                passed_cycles += 1
            else:
                TestLog("WARNING", "Step2", f"第{i}次: DUT未在预期时间内进入睡眠: {msg2}")

        TestLog("INFO", "Step3", f"循环测试结果: {passed_cycles}/{cycle_count}次成功")
        if passed_cycles == cycle_count:
            TestLog("PASS", "Step3",
                    f"期望结果：{cycle_count}次循环全部成功。实际结果：全部{passed_cycles}次循环DUT正常睡眠唤醒")
        elif passed_cycles >= cycle_count * 0.8:
            TestLog("WARNING", "Step3",
                    f"期望结果：{cycle_count}次循环。实际结果：{passed_cycles}/{cycle_count}次成功")
        else:
            TestLog("FAIL", "Step3",
                    f"期望结果：{cycle_count}次循环。实际结果：仅{passed_cycles}/{cycle_count}次成功")

        TestLog("INFO", "重复休眠唤醒循环鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "重复休眠唤醒循环鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "重复休眠唤醒循环鲁棒性测试", f"详细错误: {traceback.format_exc()}")
    finally:
        wakeup_active_stop()


def test_TG1_TC2_NMMessageLossRecoveryTest():
    """NM报文丢失恢复鲁棒性测试"""
    try:
        rIsleep_mA = P.ECUInfo.ISleep
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rVnormal = P.NMInfo.Vnormal

        TestLog("INFO", "Step1", f"设置DUT电源电压为{rVnormal}V，执行KL30上电, 等待DUT进入睡眠")
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "Step1", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "Step1", "DUT已进入睡眠模式")

        TestLog("INFO", "Step2", "被动唤醒DUT并验证NM通信建立")
        clear_ctx_can_messages()
        wakeup_passive_start()

        status, nm_messages = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
        if status is False:
            TestLog("FAIL", "Step2", "被动唤醒后未收到NM报文")
            wakeup_passive_stop()
            return
        TestLog("PASS", "Step2", "被动唤醒后成功收到NM报文")

        TestLog("INFO", "Step3", "短暂停止被动唤醒(模拟NM报文丢失), 再恢复唤醒")
        wakeup_passive_stop()
        time.sleep(2)
        clear_ctx_can_messages()
        wakeup_passive_start()

        status2, nm_messages2 = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
        if status2:
            TestLog("PASS", "Step3",
                    "期望结果：NM恢复后DUT正常通信。实际结果：收到NM报文，通信恢复")
        else:
            TestLog("FAIL", "Step3",
                    "期望结果：NM恢复后DUT正常通信。实际结果：未收到NM报文")

        TestLog("INFO", "Step4", "等待DUT重新进入睡眠")
        wakeup_passive_stop()

        status3, msg3 = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status3:
            TestLog("PASS", "Step4", "DUT重新进入睡眠模式")
        else:
            TestLog("WARNING", "Step4", f"DUT可能未进入睡眠: {msg3}")

        TestLog("INFO", "NM报文丢失恢复鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "NM报文丢失恢复鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "NM报文丢失恢复鲁棒性测试", f"详细错误: {traceback.format_exc()}")
    finally:
        wakeup_passive_stop()


def test_TG1_TC3_AbnormalWakeupSourceTest():
    """异常唤醒源鲁棒性测试"""
    try:
        rIsleep_mA = P.ECUInfo.ISleep
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rVnormal = P.NMInfo.Vnormal

        TestLog("INFO", "Step1", f"设置DUT电源电压为{rVnormal}V，执行KL30上电, 等待DUT进入睡眠")
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "Step1", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "Step1", "DUT已进入睡眠模式")

        TestLog("INFO", "Step2", "使用KL15上电方式唤醒DUT（不同于NM唤醒的异常唤醒源）")
        clear_ctx_can_messages()
        ctx.bob_ctrl.set_power('KL15', True)
        time.sleep(5)

        nm_msgs = [m for m in ctx.can.messages if hasattr(m, 'id') and m.id == rNMmsgID]
        if len(nm_msgs) > 0:
            TestLog("PASS", "Step2",
                    f"期望结果：KL15上电后DUT发送NM报文。实际结果：收到{len(nm_msgs)}条NM报文")
        else:
            TestLog("WARNING", "Step2",
                    "期望结果：KL15上电后DUT发送NM报文。实际结果：未收到NM报文")

        TestLog("INFO", "Step3", "关闭KL15，等待DUT重新进入睡眠")
        ctx.bob_ctrl.set_power('KL15', False)

        status2, msg2 = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status2:
            TestLog("PASS", "Step3", "关闭异常唤醒源后DUT正常进入睡眠")
        else:
            TestLog("WARNING", "Step3", f"关闭异常唤醒源后DUT可能未进入睡眠: {msg2}")

        TestLog("INFO", "Step4", "恢复使用正常NM唤醒方式验证功能正常")
        clear_ctx_can_messages()
        wakeup_passive_start()

        from testcases.nm.nm_autosar_utils import wait_nm_message
        status3, nm_messages3 = wait_nm_message(timeout_ms=P.NMInfo.TwakeupTimeout_ms)
        if status3:
            TestLog("PASS", "Step4",
                    "期望结果：异常唤醒后正常NM唤醒方式仍有效。实际结果：NM唤醒成功")
        else:
            TestLog("FAIL", "Step4",
                    "期望结果：异常唤醒后正常NM唤醒方式仍有效。实际结果：NM唤醒失败")

        TestLog("INFO", "异常唤醒源鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "异常唤醒源鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "异常唤醒源鲁棒性测试", f"详细错误: {traceback.format_exc()}")
    finally:
        wakeup_passive_stop()


def get_all_test_cases():
    import inspect
    current_module = inspect.getmodule(inspect.currentframe())
    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj
    return test_cases
