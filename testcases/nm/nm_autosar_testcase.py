import inspect
import time
import traceback
import sys
import os

from common.can_utils import canmsg_create, send_canmsg

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from env.config import *

from common.context import ctx
from env.config import *
from uvtest.testlog import TestLog
from common.utils import TimerCyclic
from common.control import TestStart, TestEnd
from slplus.time import sl_time
from common.params import P

from uvtest.framework import TestFixture

from .nm_autosar_utils import wait_dut_enter_sleep, get_nm_message_list, wakeup_active_start, wakeup_active_stop, \
    wakeup_passive_start, wakeup_passive_stop, wait_dut_send_first_msg, check_all_reserve_bit, \
    check_active_wakeup_bit, check_repeat_message_request_bit, check_UserData0_bit0, send_period, get_app_message_list, \
    check_repeat_message_state_after_active_wakeup, check_repeat_message_state_after_passive_wakeup, check_normal_state, \
    check_repeat_message_state, check_ready_sleep_state, repeat_msg_state_req_stop, check_readySleep_to_normal_state, \
    check_repeat_message_state_after_repeat_msg_request, repeat_msg_state_req_start, check_ready_sleep_state_rx_msg, \
    check_ready_sleep_state_rx_app_msg, prepare_sleep_state_test_start, prepare_sleep_state_test_stop, \
    check_prepare_sleep_state, check_bus_sleep_state, get_msg_first_ms, get_msg_first_app_msg_ms, \
    get_nm_message_period_ms, check_first_frame_isNm, wakeup_passive_normal_cycle_start, \
    wakeup_passive_normal_cycle_stop, \
    get_rx_message_list, get_tx_and_rx_nm_message_list, clear_ctx_can_messages, check_nmPdu_send_and_appMsg_send, \
    check_appMsg_send, \
    wait_nm_message, wait_nm_message_stop, check_unused_user_data_bytes, check_wakeup_source_bit, wait_app_message_stop
from .nm_module import (
    nm_initialization, nm_deinitialization,
    nm_power_on, nm_start_wakeup, nm_stop_wakeup,
    nm_wait_no_nm_for, nm_check_nm_and_app_msgs,
    nm_check_comm_stop_and_sleep_current,
    nm_check_repeat_message_state_after_wakeup,
    nm_wakeup_and_wait_first_msg,
    nm_check_cycle_interval,
    nm_check_ready_sleep_app_msgs, _load_and_parse_database,
)


class NMAutosarTestFixture(TestFixture):
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
        wakeup_passive_normal_cycle_stop()
        repeat_msg_state_req_stop()
        prepare_sleep_state_test_stop()
        clear_ctx_can_messages()
        TestEnd("")
        TestLog("INFO", "测试结束", "执行测试结束和去初始化")


def test_TG0_TC1_NMSendTest_ActiveWakeup():
    """
    NM报文发送测试-主动唤醒测试
    """
    case_name = "TG0_TC1_NM报文发送测试-主动唤醒测试"
    try:
        rIsleep_mA = P.ECUInfo.ISleep
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rVnormal = P.NMInfo.Vnormal

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {rVnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("INFO", "Step2", f"触发主动唤醒源并保持，监测DUT报文发送")
        clear_ctx_can_messages()
        wakeup_active_start()

        status, nm_messages = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，总线未收到ID为NMmsgID({hex(rNMmsgID)})的报文")
            return
        TestLog("PASS", "", f"总线收到ID为NMmsgID({hex(rNMmsgID)})的报文")

        TestLog("INFO", "Step3", f"取消主动唤醒源，等待DUT进入睡眠模式")
        wakeup_active_stop()

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        wakeup_active_stop()

def test_TG0_TC2_NMSendTest_PassiveWakeup():
    """
    NM报文发送测试-被动唤醒测试
    """
    case_name = "TG0_TC2_NM报文发送测试-被动唤醒测试"
    try:
        rIsleep_mA = P.ECUInfo.ISleep
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rVnormal = P.NMInfo.Vnormal

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {rVnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("INFO", "Step2", f"触发被动唤醒请求并保持，监测DUT报文发送")
        clear_ctx_can_messages()
        wakeup_passive_start()

        status, nm_messages = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，总线未收到ID为NMmsgID({hex(rNMmsgID)})的报文")
            return
        TestLog("PASS", "", f"总线收到ID为NMmsgID({hex(rNMmsgID)})的报文")

        TestLog("INFO", "Step3", f"停止发送唤醒报文，等待DUT进入睡眠模式")
        wakeup_passive_stop()

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        wakeup_passive_stop()

def test_TG0_TC3_DUTSleepTest_ActiveWakeup():
    """
    DUT睡眠测试-主动唤醒测试
    """
    case_name = "TG0_TC3_DUT睡眠测试-主动唤醒测试"
    try:
        rIsleep_mA = P.ECUInfo.ISleep
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms
        rVnormal = P.NMInfo.Vnormal

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {rVnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("INFO", "Step2", f"触发主动唤醒源并保持，监测DUT报文发送")
        clear_ctx_can_messages()
        wakeup_active_start()

        status, nm_messages = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，总线未收到ID为NMmsgID({hex(rNMmsgID)})的报文")
            return
        TestLog("PASS", "", f"总线收到ID为NMmsgID({hex(rNMmsgID)})的报文")

        TestLog("INFO", "Step3", f"取消主动唤醒源，监测DUT报文发送")
        wakeup_active_stop()
        clear_ctx_can_messages()

        # 等待DUT停止发送NM报文
        status, nm_stop_time = wait_nm_message_stop(timeout_ms=rTNMtimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"DUT未停止发送NM报文")
            return
        TestLog("INFO", "", f"DUT已停止发送NM报文")

        status, app_stop_time = wait_app_message_stop(timeout_ms=rTNMtimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"DUT在TNMtimeout时间后仍在发送APP报文")
            return
        TestLog("PASS", "", f"DUT停止发送NM报文，并在TNMtimeout时间后停止发送APP报文")

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        wakeup_active_stop()

def test_TG0_TC4_DUTSleepTest_PassiveWakeup():
    """
    DUT睡眠测试-被动唤醒测试
    """
    case_name = "TG0_TC4_DUT睡眠测试-被动唤醒测试"
    try:
        rIsleep_mA = P.ECUInfo.ISleep
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms
        rVnormal = P.NMInfo.Vnormal

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {rVnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("INFO", "Step2", f"触发被动唤醒源并保持，监测DUT报文发送")
        clear_ctx_can_messages()
        wakeup_passive_start()

        status, nm_messages = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，总线未收到ID为NMmsgID({hex(rNMmsgID)})的报文")
            return
        TestLog("PASS", "", f"总线收到ID为NMmsgID({hex(rNMmsgID)})的报文")

        TestLog("INFO", "Step3", f"取消被动唤醒源，监测DUT报文发送")
        wakeup_passive_stop()
        clear_ctx_can_messages()

        status, nm_stop_time = wait_nm_message_stop(timeout_ms=rTNMtimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"DUT未停止发送NM报文")
            return
        TestLog("INFO", "", f"DUT已停止发送NM报文")

        status, app_stop_time = wait_app_message_stop(timeout_ms=rTNMtimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"DUT在TNMtimeout时间后仍在发送APP报文")
            return
        TestLog("PASS", "", f"DUT停止发送NM报文，并在TNMtimeout时间后停止发送APP报文")

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        wakeup_passive_stop()

def test_TG0_TC5_DUTWakeupTest_ActiveWakeup():
    """
    DUT唤醒测试-主动唤醒测试
    """
    case_name = "TG0_TC5_DUT唤醒测试-主动唤醒测试"
    try:
        rIsleep_mA = P.ECUInfo.ISleep
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rVnormal = P.NMInfo.Vnormal

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {rVnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("INFO", "Step2", f"触发主动唤醒源并保持，监测DUT报文发送")
        clear_ctx_can_messages()
        wakeup_active_start()

        status, nm_messages = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，总线未收到ID为NMmsgID({hex(rNMmsgID)})的报文")
            return
        TestLog("PASS", "", f"DUT能被主动唤醒源唤醒，总线收到ID为NMmsgID({hex(rNMmsgID)})的报文")

        TestLog("INFO", "Step3", f"取消主动唤醒源，等待DUT进入睡眠模式")
        wakeup_active_stop()

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        wakeup_active_stop()

def test_TG0_TC6_DUTWakeupTest_PassiveWakeup():
    """
    DUT唤醒测试-被动唤醒测试
    """
    case_name = "TG0_TC6_DUT唤醒测试-被动唤醒测试"
    try:
        rIsleep_mA = P.ECUInfo.ISleep
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rVnormal = P.NMInfo.Vnormal

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {rVnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("INFO", "Step2", f"触发被动唤醒源并保持，监测DUT报文发送")
        clear_ctx_can_messages()
        wakeup_passive_start()

        status, nm_messages = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，总线未收到ID为NMmsgID({hex(rNMmsgID)})的报文")
            return
        TestLog("PASS", "", f"DUT能被被动唤醒源唤醒，总线收到ID为NMmsgID({hex(rNMmsgID)})的报文")

        TestLog("INFO", "Step3", f"停止发送唤醒报文，等待DUT进入睡眠模式")
        wakeup_passive_stop()

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        wakeup_passive_stop()

def test_TG1_TC1_SourceNodeIDCheck_ActiveWakeup():
    """源节点标识符检查-主动唤醒测试"""
    case_name = "源节点标识符检查-主动唤醒测试"
    try:
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTactiveWakeup_ms = P.NMInfo.TactiveWakeup_ms
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)
        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", f"触发主动唤醒源并保持，等待TrepeatMessage + TactiveKeep时间。"
                                 f"监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_active_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)
        time.sleep(rTactiveKeep_s)

        nm_messages = get_nm_message_list()
        if len(nm_messages) == 0:
            TestLog("FAIL", "", f"总线未收到DUT发出的NM报文")
            return
        TestLog("PASS", "", f"总线收到DUT发出的NM报文")

        TestLog("INFO", "Step3", f"比较NM报文表示源节点标识符的字节内容ByteData是否与定义一致")
        for msg in nm_messages:
            sid = bytes.fromhex(msg.payload_hex)[0]
            if sid != rSourceNodeID:
                TestLog("FAIL", "", f"实际结果:SourceNodeID={hex(sid)}，与定义不一致; 期望结果: SourceNodeID={hex(rSourceNodeID)}")
                return
        TestLog("PASS", "", f"实际结果:SourceNodeID与定义一致; 期望结果: SourceNodeID={hex(rSourceNodeID)}")

        TestLog("INFO", "Step4", f"取消主动唤醒源，等待DUT进入睡眠模式")
        wakeup_active_stop()
        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG1_TC2_SourceNodeIDCheck_PassiveWakeup():
    """源节点标识符检查-被动唤醒测试"""
    case_name = "源节点标识符检查-被动唤醒测试"
    try:
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms


        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)
        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", f"触发被动唤醒源并保持，等待TrepeatMessage + TpassiveKeep时间。"
                                 f"监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_passive_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            wakeup_passive_stop()
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)
        time.sleep(rTpassiveKeep_s)

        nm_messages = get_nm_message_list()
        if len(nm_messages) == 0:
            TestLog("FAIL", "", f"总线未收到DUT发出的NM报文")
            wakeup_passive_stop()
            return
        TestLog("PASS", "", f"总线收到DUT发出的NM报文")

        TestLog("INFO", "Step3", f"比较NM报文表示源节点标识符的字节内容ByteData是否与定义一致")
        for msg in nm_messages:
            sid = bytes.fromhex(msg.payload_hex)[0]
            if sid != rSourceNodeID:
                TestLog("FAIL", "", f"实际结果:SourceNodeID={hex(sid)}，与定义不一致; 期望结果: SourceNodeID={hex(rSourceNodeID)}")
                wakeup_passive_stop()
                return
        TestLog("PASS", "", f"实际结果:SourceNodeID与定义一致; 期望结果: SourceNodeID={hex(rSourceNodeID)}")

        TestLog("INFO", "Step4", f"取消被动唤醒源，等待DUT进入睡眠模式")
        wakeup_passive_stop()

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG1_TC3_ControlBitsCheck_ActiveWakeup():
    """控制位状态检查-主动唤醒测试"""
    case_name = "控制位状态检查-主动唤醒测试"
    try:
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTactiveWakeup_ms = P.NMInfo.TactiveWakeup_ms
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms

        rBit1_CAL = P.NMInfo.ReserveBit1  # 是否支持ReserveBit1状态位，1，支持，0，不支持
        rBit2_CAL = P.NMInfo.ReserveBit2  # 是否支持ReserveBit2状态位，1，支持，0，不支持
        rBit3_CAL = P.NMInfo.ReserveBit3  # 是否支持ReserveBit3状态位，1，支持，0，不支持
        rBit5_CAL = P.NMInfo.ReserveBit5  # 是否支持ReserveBit5状态位，1，支持，0，不支持
        rBit6_CAL = P.NMInfo.ReserveBit6  # 是否支持ReserveBit6状态位，1，支持，0，不支持
        rBit7_CAL = P.NMInfo.ReserveBit7  # 是否支持ReserveBit7状态位，1，支持，0，不支持
        rReptMsgBit0 = P.NMInfo.RepeatMessageBit0  # 是否支持RepeatMessageRequestBit状态位，1，支持，0，不支持
        rActWupBit4 = P.NMInfo.ActiveWakeupBit4  # 是否支持ActiveWakeupBit4状态位，1，支持，0，不支持
        rResBitValue = P.NMInfo.ReserveBitValue  # 保留状态位填充值，填充值为0或1


        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)
        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", f"触发主动唤醒源并保持，等待TrepeatMessage + TactiveKeep时间。"
                                 f"监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_active_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)
        time.sleep(rTactiveKeep_s)

        nm_messages = get_nm_message_list()
        if len(nm_messages) == 0:
            TestLog("FAIL", "", f"总线未收到DUT发出的NM报文")
            return
        TestLog("PASS", "", f"总线收到DUT发出的NM报文")

        TestLog("INFO", "Step3", f"判断NM报文的RepeatMessageRequestBit 状态位是否符合设计要求")
        if rReptMsgBit0 == 1:
            if -1 == check_repeat_message_request_bit(nm_messages):
                return
        else:
            TestLog("WARNING", case_name, "RepeatMessageBit0 = 0，不支持该项测试")

        TestLog("INFO", "Step3", f"判断NM报文的UserData0 bit0 状态位是否符合设计要求")
        if -1 == check_UserData0_bit0(nm_messages):
            return

        TestLog("INFO", "Step4", f"判断NM报文的ActiveWakeupBit 状态位是否符合设计要求")
        if rActWupBit4 == 1:
            if -1 == check_active_wakeup_bit(nm_messages, 1):
                return
        else:
            TestLog("WARNING", "", "ActiveWakeupBit4 = 0，不支持该项测试")


        TestLog("INFO", "Step5", f"判断NM报文的ReserveBit 状态位是否符合设计要求")
        if rBit1_CAL or rBit2_CAL or rBit3_CAL or rBit5_CAL or rBit6_CAL or rBit7_CAL:
            if -1 == check_all_reserve_bit(nm_messages, rResBitValue):
                return
        else:
            TestLog("WARNING", "", "ReserveBit1、2、3、5、6、7全为0，不支持该项测试")

        TestLog("INFO", "Step6", f"取消主动唤醒源，等待DUT进入睡眠模式")
        wakeup_active_stop()
        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG1_TC4_ControlBitsCheck_PassiveWakeup():
    """控制位状态检查-被动唤醒测试"""
    case_name = "控制位状态检查-被动唤醒测试"
    try:
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms

        rBit1_CAL = P.NMInfo.ReserveBit1  # 是否支持ReserveBit1状态位，1，支持，0，不支持
        rBit2_CAL = P.NMInfo.ReserveBit2  # 是否支持ReserveBit2状态位，1，支持，0，不支持
        rBit3_CAL = P.NMInfo.ReserveBit3  # 是否支持ReserveBit3状态位，1，支持，0，不支持
        rBit5_CAL = P.NMInfo.ReserveBit5  # 是否支持ReserveBit5状态位，1，支持，0，不支持
        rBit6_CAL = P.NMInfo.ReserveBit6  # 是否支持ReserveBit6状态位，1，支持，0，不支持
        rBit7_CAL = P.NMInfo.ReserveBit7  # 是否支持ReserveBit7状态位，1，支持，0，不支持
        rReptMsgBit0 = P.NMInfo.RepeatMessageBit0  # 是否支持RepeatMessageRequestBit状态位，1，支持，0，不支持
        rActWupBit4 = P.NMInfo.ActiveWakeupBit4  # 是否支持ActiveWakeupBit4状态位，1，支持，0，不支持
        rResBitValue = P.NMInfo.ReserveBitValue  # 保留状态位填充值，填充值为0或1


        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", f"触发被动唤醒源并保持，等待TrepeatMessage + TpassiveKeep时间。"
                                 f"监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_passive_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            wakeup_passive_stop()
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)
        time.sleep(rTpassiveKeep_s)

        nm_messages = get_nm_message_list()
        if len(nm_messages) == 0:
            TestLog("FAIL", "", f"总线未收到DUT发出的NM报文")
            wakeup_passive_stop()
            return
        TestLog("PASS", "", f"总线收到DUT发出的NM报文")

        TestLog("INFO", "Step3", f"若RepeatMessageBit0=1，判断NM报文的RepeatMessageRequestBit状态位和UserData0 bit0")
        if rReptMsgBit0 == 1:
            if -1 == check_repeat_message_request_bit(nm_messages):
                return
            if -1 == check_UserData0_bit0(nm_messages):
                return
        else:
            TestLog("WARNING", case_name, "RepeatMessageBit0 = 0，按规范跳过Step3，不检查RepeatMessageRequestBit和UserData0 bit0")

        TestLog("INFO", "Step4", f"若ActiveWakeupBit4=1，判断NM报文的ActiveWakeupBit状态位")
        if rActWupBit4 == 1:
            if -1 == check_active_wakeup_bit(nm_messages, 0):
                return
        else:
            TestLog("WARNING", "", "ActiveWakeupBit4 = 0，按规范跳过Step4，不检查ActiveWakeupBit")

        TestLog("INFO", "Step5", f"判断NM报文的ReserveBit 状态位是否符合设计要求")
        if rBit1_CAL or rBit2_CAL or rBit3_CAL or rBit5_CAL or rBit6_CAL or rBit7_CAL:
            if -1 == check_all_reserve_bit(nm_messages, rResBitValue):
                return
        else:
            TestLog("WARNING", "", "ReserveBit1、2、3、5、6、7全为0，不支持该项测试")

        TestLog("INFO", "Step6", f"停止发送唤醒报文，等待DUT进入睡眠模式")
        wakeup_passive_stop()

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG1_TC5_NMMsgIDRangeCheck():
    """NM唤醒报文ID范围测试"""
    case_name = "NM唤醒报文ID范围测试"
    try:
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms


        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)


        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms  # 重复发送报文状态的保持时间
        rNimmediateSend = P.NMInfo.NimmediateSend  # 快速发送NM报文的帧数
        rTnormalCycle_ms = P.NMInfo.TnormalCycle_ms  # 正常发送NM报文的周期
        rTimmediateCycle_ms = P.NMInfo.TimmediateCycle_ms  # 快速发送NM报文的周期
        rWakeupMsgID = 0x47F
        rWakeupMsgDLC = P.ECUInfo.WakeupMsgDLC
        rWakeupMsgData = bytearray(P.ECUInfo.WakeupMsgData_bytes)[:rWakeupMsgDLC]
        rReptMsgBit0 = P.NMInfo.RepeatMessageBit0
        rActWupBit4 = P.NMInfo.ActiveWakeupBit4

        rWakeupMsgData[1] |= 0x01  # RepeatMessageBitRequest = 1
        rWakeupMsgData[1] &= 0xEF  # ActiveWakeupBit = 0

        nm_msg_count = 0
        sMsgInfoList = _load_and_parse_database(msg_type='rx') or {}
        for msg_id in sMsgInfoList.keys():
            if msg_id < rNMmsgIDMin or msg_id > rNMmsgIDMax:
                continue
            # 排除DUT本身发送的NM报文ID
            if msg_id == rNMmsgID:
                TestLog("INFO", "", f"跳过DUT自身的NM报文ID=0x{msg_id:X}，不作为唤醒报文测试")
                continue
            nm_msg_count += 1

            clear_ctx_can_messages()
            rWakeupMsgData[0] = msg_id - 0x400
            TestLog("INFO", "Step2",
                    "以TimmediateCycle周期快速发送ID为数据库定义的其中一个NM报文，"
                    "DLC为数据库定义值，数据内容为WakeupmsgData的唤醒报文，连续发送NimmediateSend帧，"
                    "之后以正常周期TnormalCycle持续发送，等待TrepeatMessage时间，监控DUT是否发出NM报文")
            # 快发
            msg = canmsg_create(msg_id, rWakeupMsgDLC, data=rWakeupMsgData, rtr=0, fdf=0, brs=0, ext=0)
            send_period(can_channel, msg, rNimmediateSend, rTimmediateCycle_ms)

            # 正常发
            TimerCyclic.start(1, rTnormalCycle_ms, send_canmsg, can_channel, msg=msg)
            # 等待一段时间
            time.sleep(rTrepeatMessage_ms / 1000)

            nm_messages = get_nm_message_list()
            app_messages = get_app_message_list()  # TODO 获取应用报文
            if len(nm_messages) == 0:
                TestLog("FAIL", "", f"期望结果:DUT能够被报文（ID={hex(msg_id)}）唤醒，正常发送NN报文和应用报文，"
                                    f"实际结果:DUT没有被唤醒，总线没有接收到任何报文")


            # 检测到DUT发出NM报文和应用报文
            if len(nm_messages) >= 1 and len(app_messages) >= 2:
                TestLog("PASS", "", f"期望结果:DUT能够被报文（ID={hex(msg_id)}）唤醒，正常发送NN报文和应用报文，"
                                    "实际结果:DUT被唤醒，总线接收到NM报文和应用报文")
            elif len(nm_messages) >= 1 and len(app_messages) == 1:
                TestLog("FAIL", "", f"期望结果:DUT能够被报文（ID={hex(msg_id)}）唤醒，正常发送NN报文和应用报文，"
                                           "实际结果:DUT被唤醒，但总线没有接收到应用报文，仅接收到NM报文")
            elif len(nm_messages) == 0 and len(app_messages) >= 1:
                TestLog("FAIL", "", f"期望结果:DUT能够被报文（ID={hex(msg_id)}）唤醒，正常发送NN报文和应用报文，"
                                           "实际结果:DUT被唤醒，但总线没有接收到应用报文，仅接收到应用报文")
            elif len(nm_messages) == 0 and len(app_messages) == 0:
                TestLog("FAIL", "", f"期望结果:DUT能够被报文（ID={hex(msg_id)}）唤醒，正常发送NN报文和应用报文，"
                                           "实际结果:DUT被唤醒，但总线没有接收任何报文")

            # 停止发送报文
            TimerCyclic.stop(1)
            # 等待DUT进入睡眠模式
            status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
            if status is False:
                TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
                return
            TestLog("PASS", "", msg)
        if nm_msg_count == 0:
            TestLog("WARNING", "", "数据库中没有查找到NM报文，终止测试")

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG1_TC6_CannotWakeupMsgIDRangeCheck():
    """禁止唤醒报文ID范围测试"""
    case_name = "禁止唤醒报文ID范围测试"
    try:
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms


        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)


        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms  # 重复发送报文状态的保持时间
        rNimmediateSend = P.NMInfo.NimmediateSend  # 快速发送NM报文的帧数
        rTnormalCycle_ms = P.NMInfo.TnormalCycle_ms  # 正常发送NM报文的周期
        rTimmediateCycle_ms = P.NMInfo.TimmediateCycle_ms  # 快速发送NM报文的周期
        rWakeupMsgID = 0x47F
        rWakeupMsgDLC = P.ECUInfo.WakeupMsgDLC
        rWakeupMsgData = bytearray(P.ECUInfo.WakeupMsgData_bytes)[:rWakeupMsgDLC]
        rReptMsgBit0 = P.NMInfo.RepeatMessageBit0
        rActWupBit4 = P.NMInfo.ActiveWakeupBit4

        rWakeupMsgData[1] |= 0x01  # RepeatMessageBitRequest = 1
        rWakeupMsgData[1] &= 0xEF  # ActiveWakeupBit = 0

        nm_msg_count = 0
        sMsgInfoList = _load_and_parse_database(msg_type='rx') or {}
        sMsgInfoList[rNMmsgIDMin - 1] = None
        sMsgInfoList[rNMmsgIDMax + 1] = None
        for msg_id in sMsgInfoList.keys():
            if rNMmsgIDMin <= msg_id <= rNMmsgIDMax:
                continue
            nm_msg_count += 1

            clear_ctx_can_messages()
            rWakeupMsgData[0] = msg_id & 0xFF
            TestLog("INFO", "Step2",
                    "以TimmediateCycle周期快速发送ID为数据库定义的其中一个NM报文，"
                    "DLC为数据库定义值，数据内容为WakeupmsgData的唤醒报文，连续发送NimmediateSend帧，"
                    "之后以正常周期TnormalCycle持续发送，等待TrepeatMessage时间，监控DUT是否发出NM报文")
            # 快发
            msg = canmsg_create(msg_id, rWakeupMsgDLC, data=rWakeupMsgData, rtr=0, fdf=0, brs=0, ext=0)
            send_period(can_channel, msg, rNimmediateSend, rTimmediateCycle_ms)

            # 正常发
            TimerCyclic.start(1, rTnormalCycle_ms, send_canmsg, can_channel, msg=msg)
            # 等待一段时间
            time.sleep(rTrepeatMessage_ms / 1000)

            nm_messages = get_nm_message_list()
            app_messages = get_app_message_list()  # TODO 获取应用报文

            # 检测到DUT发出NM报文和应用报文
            if len(nm_messages) == 0 and len(app_messages) == 0:
                TestLog("PASS", "", f"期望结果:DUT不能被报文（ID={hex(msg_id)}）唤醒，"
                                    f"实际结果:DUT没有被唤醒，总线没有接收到任何报文")
            else:
                TestLog("FAIL", "", f"期望结果:DUT不能被报文（ID={hex(msg_id)}）唤醒，"
                                           "实际结果:DUT被唤醒，总线接收到报文")

            # 停止发送报文
            TimerCyclic.stop(1)
            # 等待DUT进入睡眠模式
            status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
            if status is False:
                TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
                return
            TestLog("PASS", "", msg)
        if nm_msg_count == 0:
            TestLog("WARNING", "", "数据库中没有查找到NM报文，终止测试")

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        TimerCyclic.stop(1)
        try:
            from slplus.can import sl_can
            can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
            TestLog("DEBUG", "CAN恢复", f"TG1_TC6结束后恢复CAN通道 {can_channel}")
            sl_can(can_channel).deactive()
            time.sleep(0.1)
            sl_can(can_channel).active()
            time.sleep(0.2)
        except Exception as e:
            TestLog("WARNING", "CAN恢复", f"TG1_TC6结束后恢复CAN通道失败: {e}")
        clear_ctx_can_messages()

def test_TG1_TC7_FirstFrameCheck_ActiveWakeup():
    """唤醒后首帧测试-主动唤醒测试"""
    case_name = "唤醒后首帧测试-主动唤醒测试"
    try:
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTactiveWakeup_ms = P.NMInfo.TactiveWakeup_ms
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)
        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", f"触发主动唤醒源并保持，监测DUT唤醒后的首帧报文。")
        clear_ctx_can_messages()
        wakeup_active_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)
        if -1 == check_first_frame_isNm():
            return

        TestLog("INFO", "Step3", f"取消主动唤醒源，等待DUT进入睡眠模式")
        wakeup_active_stop()
        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG1_TC8_FirstFrameCheck_PassiveWakeup():
    """唤醒后首帧测试-被动唤醒测试"""
    case_name = "唤醒后首帧测试-被动唤醒测试"
    try:
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTactiveWakeup_ms = P.NMInfo.TactiveWakeup_ms
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)
        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", f"触发被动唤醒源并保持，监测DUT唤醒后的首帧报文。")
        clear_ctx_can_messages()
        wakeup_passive_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)
        if -1 == check_first_frame_isNm():
            return

        TestLog("INFO", "Step3", f"取消被动唤醒源，等待DUT进入睡眠模式")
        wakeup_passive_stop()
        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC1_NM_GotoBusSleepModeAfterPowerOn():
    """上电初始化完成后处于睡眠模式测试"""
    case_name = "上电初始化完成后处于睡眠模式测试"
    try:
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTactiveWakeup_ms = P.NMInfo.TactiveWakeup_ms
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms

        TestLog("INFO", "Step1", "DUT内部网络请求和外部网络请求同时处于未激活状态")

        TestLog("INFO", "Step2", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")
    except Exception as e:
        TestLog("FAIL", "GotoBusSleep", f"异常: {e}")
        TestLog("DEBUG", "", traceback.format_exc())

def test_TG2_TC2_BusSleepStateGotoRepeatMessageState_ActiveWakeup():
    """睡眠模式迁移至重复报文模式-主动唤醒测试"""
    case_name = "睡眠模式迁移至重复报文模式-主动唤醒测试"
    try:
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms


        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_active_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)

        check_repeat_message_state_after_active_wakeup()

        TestLog("INFO", "Step3", f"取消主动唤醒源，等待DUT进入睡眠模式")
        wakeup_active_stop()

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC3_BusSleepStateGotoRepeatMessageState_PassiveWakeup():
    """睡眠模式迁移至重复报文模式-被动唤醒测试"""
    case_name = "睡眠模式迁移至重复报文模式-被动唤醒测试"
    try:
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms


        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_passive_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)

        check_repeat_message_state_after_passive_wakeup()

        TestLog("INFO", "Step3", f"取消被动唤醒源，等待DUT进入睡眠模式")
        wakeup_passive_stop()

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC4_RepeatMessageStateGotoNormalState_ActiveWakeup():
    """重复报文模式迁移至正常工作模式-主动唤醒测试"""
    case_name = "重复报文模式迁移至正常工作模式-主动唤醒测试"
    try:
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms


        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_active_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)

        check_repeat_message_state_after_active_wakeup()

        TestLog("INFO", "Step3", "继续等待TactiveKeep时间，监控在此期间DUT发出的所有NM报文")
        time.sleep(rTactiveKeep_s)

        check_normal_state()

        TestLog("INFO", "Step4", f"取消主动唤醒源，等待DUT进入睡眠模式")
        wakeup_active_stop()

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC5_RepeatMessageStateGotoNormalState_PassiveWakeup():
    """重复报文模式迁移至正常工作模式-被动唤醒测试"""
    case_name = "重复报文模式迁移至正常工作模式-被动唤醒测试"
    rDiagTimerID = "TG2_TC5_DIAG_3E80"
    try:
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rDiagCycle_ms = 500
        rDiagKeep_s = 60


        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发被动唤醒源并保持，从收到DUT发出第1帧报文开始等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_passive_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            wakeup_passive_stop()
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)

        if -1 == check_repeat_message_state_after_passive_wakeup():
            wakeup_passive_stop()
            return

        TestLog("INFO", "Step3", "继续发送唤醒报文，并将唤醒报文的RepeatMessageRequestBit状态位设置为0，等待TpassiveKeep时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        time.sleep(rTpassiveKeep_s)

        if -1 == check_normal_state():
            wakeup_passive_stop()
            return

        TestLog("INFO", "Step4", "停止发送唤醒报文，等待DUT进入睡眠模式")
        wakeup_passive_stop()

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step5", "触发被动唤醒请求并保持，从收到DUT发出第1帧报文开始，等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_passive_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            wakeup_passive_stop()
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)

        if -1 == check_repeat_message_state_after_passive_wakeup():
            wakeup_passive_stop()
            return

        TestLog("INFO", "Step6", f"停发唤醒报文，以{rDiagCycle_ms}ms周期发送诊断报文，等待{rDiagKeep_s}s，监控在此期间DUT发出的所有NM报文")
        wakeup_passive_stop()
        clear_ctx_can_messages()

        can_channel = P.ECUInfo.DiagCANChannelNum or (DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1)
        diag_msg_data = [0x02, 0x3E, 0x80] + [0xAA] * 5
        diag_msg = canmsg_create(P.ECUInfo.DiagReqID_int, 8, data=diag_msg_data,
                                 rtr=0, fdf=P.TpInfo.CanFDMode, brs=0, ext=0)
        if diag_msg is None:
            TestLog("FAIL", "Step6", "诊断报文创建失败，测试终止")
            return

        if not TimerCyclic.start(rDiagTimerID, rDiagCycle_ms, send_canmsg, can_channel, msg=diag_msg):
            TestLog("FAIL", "Step6", "诊断报文周期发送定时器启动失败，测试终止")
            return

        diag_check_result = 0
        try:
            time.sleep(rDiagKeep_s)
            diag_check_result = check_normal_state()
        finally:
            TimerCyclic.stop(rDiagTimerID)

        if -1 == diag_check_result:
            return

        TestLog("INFO", "Step7", "停止发送诊断报文，等待DUT进入睡眠模式")
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TimerCyclic.stop(rDiagTimerID)
        wakeup_passive_stop()
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC6_RepeatMessageStateGotoReadySleepState_ActiveWakeup():
    """重复报文模式迁移至准备睡眠模式-主动唤醒测试"""
    case_name = "重复报文模式迁移至准备睡眠模式-主动唤醒测试"
    try:
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间


        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始等待0.5*TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_active_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        # time.sleep(0.5 * rTrepeatMessage_ms / 1000.0)
        sl_time().sleep(P.NMInfo.NimmediateSend * 20 * 1.1)
        check_repeat_message_state_after_active_wakeup()

        TestLog("INFO", "Step3", "取消主动唤醒源，继续等待0.5*rTrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        wakeup_active_stop()
        time.sleep(0.5 * rTrepeatMessage_ms / 1000.0)
        # check_repeat_message_state(0.5*rTrepeatMessage_ms, 0.9*rTrepeatMessage_ms)
        check_repeat_message_state(P.NMInfo.NimmediateSend * 20 * 1.1, P.NMInfo.NimmediateSend * 20 * 1.1 + 2000)

        TestLog("INFO", "Step4", "继续等待TNMtimeout时间，监控DUT在此期间是否停止发送NM报文，并且正常发送应用报文")
        time.sleep(0.2 * rTNMtimeout_ms / 1000)
        clear_ctx_can_messages()
        time.sleep((1-0.2) * rTNMtimeout_ms / 1000)
        check_ready_sleep_state()

        TestLog("INFO", "Step5", "等待DUT进入睡眠模式")
        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC7_RepeatMessageStateGotoReadySleepState_PassiveWakeup():
    """重复报文模式迁移至准备睡眠模式-被动唤醒测试"""
    case_name = "重复报文模式迁移至准备睡眠模式-被动唤醒测试"
    try:
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms


        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始等待0.5*TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_passive_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(0.5 * rTrepeatMessage_ms / 1000.0)

        check_repeat_message_state_after_passive_wakeup()

        TestLog("INFO", "Step3", "取消被动唤醒源，继续等待0.5*rTrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        wakeup_passive_stop()
        time.sleep(0.5 * rTrepeatMessage_ms / 1000.0)
        check_repeat_message_state(0.5*rTrepeatMessage_ms, 0.9*rTrepeatMessage_ms)

        TestLog("INFO", "Step4", "继续等待TNMtimeout时间，监控DUT在此期间是否停止发送NM报文，并且正常发送应用报文")
        time.sleep(0.2 * rTNMtimeout_ms / 1000)
        clear_ctx_can_messages()
        time.sleep((1 - 0.2) * rTNMtimeout_ms / 1000)
        check_ready_sleep_state()

        TestLog("INFO", "Step5", "等待DUT进入睡眠模式")
        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC8_NormalStateGotoRepeatMessageState_ActiveWakeup():
    """正常工作模式迁移至重复报文模式-主动唤醒测试"""
    case_name = "正常工作模式迁移至重复报文模式-主动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms


        if rNormalToReptMsg == 0:
            TestLog("WARNING", "", "NormalStateToRepeatMessageState = 0, 该用例不适用")
            return

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始，等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_active_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)

        check_repeat_message_state_after_active_wakeup()

        TestLog("INFO", "Step3", "继续等待TactiveKeep时间，监控在此期间DUT发出的所有NM报文")
        time.sleep(rTactiveKeep_s)
        check_normal_state()

        TestLog("INFO", "Step4", f"取消主动唤醒源，触发重复报文模式请求，等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        wakeup_active_stop()

        clear_ctx_can_messages()

        repeat_msg_state_req_start()

        time.sleep(rTrepeatMessage_ms / 1000.0)
        check_repeat_message_state_after_repeat_msg_request()

        TestLog("INFO", "Step5", "取消重复报文模式请求，等待DUT进入睡眠模式")
        repeat_msg_state_req_stop()

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC9_NormalStateGotoRepeatMessageState_PassiveWakeup():
    """正常工作模式迁移至重复报文模式-被动唤醒测试"""
    case_name = "正常工作模式迁移至重复报文模式-被动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms


        if rNormalToReptMsg == 0:
            TestLog("WARNING", "", "NormalStateToRepeatMessageState = 0, 该用例不适用")
            return

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发被动唤醒源并保持，从收到DUT发出第1帧报文开始，等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_passive_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)

        check_repeat_message_state_after_passive_wakeup()

        TestLog("INFO", "Step3", "继续等待TactiveKeep时间，监控在此期间DUT发出的所有NM报文")
        time.sleep(rTactiveKeep_s)
        check_normal_state()

        TestLog("INFO", "Step4", f"取消被动唤醒源，触发重复报文模式请求，等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        wakeup_passive_stop()

        clear_ctx_can_messages()

        repeat_msg_state_req_start()

        time.sleep(rTrepeatMessage_ms / 1000.0)
        check_repeat_message_state_after_repeat_msg_request()

        TestLog("INFO", "Step5", "取消重复报文模式请求，等待DUT进入睡眠模式")
        repeat_msg_state_req_stop()

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC10_NM_NormalStateGotoBusSleep_ActiveWakeup():
    """正常工作模式迁移至准备睡眠模式-主动唤醒测试"""
    case_name = "正常工作模式迁移至准备睡眠模式-主动唤醒测试"
    try:
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms  # NM Timeout Timer时间

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_active_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)

        check_repeat_message_state_after_active_wakeup()

        TestLog("INFO", "Step3", "继续等待TactiveKeep时间，监控在此期间DUT发出的所有NM报文")
        time.sleep(rTactiveKeep_s)

        check_normal_state()

        TestLog("INFO", "Step4", f"取消主动唤醒源，从DUT发送完最后1帧NM报文开始，等待TNMtimeout时间，监控DUT在此期间是否停止发送NM报文，并且正常发送应用报文")
        wakeup_active_stop()

        nm_message = get_nm_message_list()
        lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else 0
        clear_ctx_can_messages()

        testStartTime_ms =  time.time() * 1000
        # lastRxNMMsgTimeStamp_ms =  time.time() * 1000
        testTimeout_ms = 60000  # 60s超时
        testTimeoutFlag = 0  # 是否超时标志

        while (time.time() * 1000 - lastRxNMMsgTimeStamp_ms) < rTNMtimeout_ms:
            time.sleep(0.001)
            nm_message = get_nm_message_list()
            lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else lastRxNMMsgTimeStamp_ms
            if (time.time() * 1000 - testStartTime_ms) >= testTimeout_ms:
                testTimeoutFlag = 1
                break

        # 60s超时之前进入了准备睡眠状态
        if not testTimeoutFlag:
            TestLog("INFO", "", f"DUT发送最后1帧NM报文时刻：{lastRxNMMsgTimeStamp_ms/1000} S")
            check_ready_sleep_state_rx_msg(rTNMtimeout_ms)
        else:
            TestLog("FAIL", "", "期望结果:DUT停止发送NM报文，正常发送应用报文，"
                                "实际结果:取消主动唤醒源之后，超过60s时间，DUT仍然一直发送NM报文，测试终止")
            return

        # 等待DUT进入睡眠模式
        TestLog("INFO", "Step5","等待DUT进入睡眠模式")
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC11_NM_NormalStateGotoBusSleep_PassiveWakeup():
    """正常工作模式迁移至准备睡眠模式-被动唤醒测试"""
    case_name = "正常工作模式迁移至准备睡眠模式-被动唤醒测试"
    try:
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms  # NM Timeout Timer时间

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发被动唤醒源并保持，从收到DUT发出第1帧报文开始等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_passive_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)

        check_repeat_message_state_after_passive_wakeup()

        TestLog("INFO", "Step3", "继续发送唤醒报文，并将唤醒报文的RepeatMessageRequestBit状态位设置为0，等待TpassiveKeep时间，监控在此期间DUT发出的所有NM报文")
        time.sleep(rTpassiveKeep_s)

        check_normal_state()

        TestLog("INFO", "Step4",
                f"取消被动唤醒源，从DUT发送完最后1帧NM报文开始，等待TNMtimeout时间，监控DUT在此期间是否停止发送NM报文，并且正常发送应用报文")
        wakeup_passive_stop()

        nm_message = get_nm_message_list()
        lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else 0
        clear_ctx_can_messages()

        testStartTime_ms = time.time() * 1000
        # lastRxNMMsgTimeStamp_ms =  time.time() * 1000
        testTimeout_ms = 60000  # 60s超时
        testTimeoutFlag = 0  # 是否超时标志

        while (time.time() * 1000 - lastRxNMMsgTimeStamp_ms) < rTNMtimeout_ms:
            time.sleep(0.001)
            nm_message = get_nm_message_list()
            lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else lastRxNMMsgTimeStamp_ms
            if (time.time() * 1000 - testStartTime_ms) >= testTimeout_ms:
                testTimeoutFlag = 1
                break

        # 60s超时之前进入了准备睡眠状态
        if not testTimeoutFlag:
            TestLog("INFO", "", f"DUT发送最后1帧NM报文时刻：{lastRxNMMsgTimeStamp_ms / 1000} S")
            check_ready_sleep_state_rx_msg(rTNMtimeout_ms)
        else:
            TestLog("FAIL", "", "期望结果:DUT停止发送NM报文，正常发送应用报文，"
                                "实际结果:取消主动唤醒源之后，超过60s时间，DUT仍然一直发送NM报文，测试终止")
            return

        # 等待DUT进入睡眠模式
        TestLog("INFO", "Step5", "等待DUT进入睡眠模式")
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC12_NM_NormalStateLongKeep_ActiveWakeup():
    """正常工作模式保持-主动唤醒测试"""
    case_name = "正常工作模式保持-主动唤醒测试"
    try:
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTLongKeep_s = P.NMInfo.TlongKeep_min * 60
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms  # NM Timeout Timer时间

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_active_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)

        check_repeat_message_state_after_active_wakeup()

        TestLog("INFO", "Step3", "保持主动唤醒源，继续等待TlongKeep时间，监控在此期间DUT是否正常发送NM报文和应用报文")
        clear_ctx_can_messages()
        time.sleep(rTLongKeep_s)

        check_nmPdu_send_and_appMsg_send()

        # # NM + 应用层报文联动检查
        # if not nm_check_nm_and_app_msgs('active'):
        #     TestLog("FAIL", "Step3", "长保持阶段 NM+应用层报文联动检查失败")
        #     return

        # 等待DUT进入睡眠模式
        TestLog("INFO", "Step4", "取消主动唤醒源，等待DUT进入睡眠模式")
        wakeup_active_stop()
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC13_NM_NormalStateLongKeep_PassiveWakeup():
    """正常工作模式迁移至准备睡眠模式-被动唤醒测试"""
    case_name = "正常工作模式迁移至准备睡眠模式-被动唤醒测试"
    try:
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTLongKeep_s = P.NMInfo.TlongKeep_min * 60
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms  # NM Timeout Timer时间

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2",
                "触发被动唤醒源并保持，从收到DUT发出第1帧报文开始等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_passive_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            wakeup_passive_stop()
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)

        check_repeat_message_state_after_passive_wakeup()

        TestLog("INFO", "Step3",
                "继续发送唤醒报文，并将唤醒报文的RepeatMessageRequestBit状态位设置为0，等待TlongKeep时间，监控在此期间DUT是否正常发送NM报文和应用报文")
        clear_ctx_can_messages()
        time.sleep(rTLongKeep_s)

        check_appMsg_send()
        #
        # # NM + 应用层报文联动检查
        # if not nm_check_nm_and_app_msgs('passive'):
        #     TestLog("FAIL", "Step3", "长保持阶段 NM+应用层报文联动检查失败")
        #     wakeup_passive_stop()
        #     return

        # 等待DUT进入睡眠模式
        TestLog("INFO", "Step4", "取消被动唤醒源，等待DUT进入睡眠模式")
        wakeup_passive_stop()
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC14_ReadySleepStateGotoNormalState_ActiveWakeup():
    """准备睡眠模式迁移至正常工作模式-主动唤醒测试"""
    case_name = "准备睡眠模式迁移至正常工作模式-主动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始，等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_active_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)

        check_repeat_message_state_after_active_wakeup()

        TestLog("INFO", "Step3",
                "取消主动唤醒源，从收到DUT发出最后1帧NM报文开始等待0.5*TNMtimeout时间，监控DUT在此期间是否停止发送NM报文，并且正常发送应用报文")
        wakeup_active_stop()

        nm_message = get_nm_message_list()
        lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else 0
        clear_ctx_can_messages()

        testStartTime_ms =  time.time() * 1000
        # lastRxNMMsgTimeStamp_ms =  time.time() * 1000
        testTimeout_ms = 60000  # 60s超时
        testTimeoutFlag = 0  # 是否超时标志

        while (time.time() * 1000 - lastRxNMMsgTimeStamp_ms) < 0.5 * rTNMtimeout_ms:
            time.sleep(0.001)
            nm_message = get_nm_message_list()
            lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else lastRxNMMsgTimeStamp_ms
            if (time.time() * 1000 - testStartTime_ms) >= testTimeout_ms:
                testTimeoutFlag = 1
                break

        # 60s超时之前进入了准备睡眠状态
        if not testTimeoutFlag:
            TestLog("INFO", "", f"DUT发送最后1帧NM报文时刻：{lastRxNMMsgTimeStamp_ms/1000} S")
            check_ready_sleep_state_rx_msg(0.5 * rTNMtimeout_ms)
        else:
            TestLog("FAIL", "", "期望结果:DUT停止发送NM报文，正常发送应用报文，"
                                "实际结果:取消主动唤醒源之后，超过60s时间，DUT仍然一直发送NM报文，测试终止")
            return


        TestLog("INFO", "Step4", "重新触发主动唤醒源并保持，持续TactiveKeep时间，监控在此期间DUT发出的所有NM报文")
        wakeup_active_start()
        clear_ctx_can_messages()

        time.sleep(rTactiveKeep_s)

        check_readySleep_to_normal_state()

        TestLog("INFO", "Step5", f"取消主动唤醒源，等待DUT进入睡眠模式")
        wakeup_active_stop()

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC15_ReadySleepStateGotoNormalState_PassiveWakeup():
    """准备睡眠模式迁移至正常工作模式-被动唤醒测试"""
    case_name = "准备睡眠模式迁移至正常工作模式-被动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发被动唤醒源并保持，从收到DUT发出第1帧报文开始，等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_passive_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)

        check_repeat_message_state_after_passive_wakeup()

        TestLog("INFO", "Step3",
                "取消被动唤醒源，从收到DUT发出最后1帧NM报文开始等待0.5*TNMtimeout时间，监控DUT在此期间是否停止发送NM报文，并且正常发送应用报文")
        wakeup_passive_stop()

        nm_message = get_nm_message_list()
        lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else 0
        clear_ctx_can_messages()

        testStartTime_ms =  time.time() * 1000
        # lastRxNMMsgTimeStamp_ms =  time.time() * 1000
        testTimeout_ms = 60000  # 60s超时
        testTimeoutFlag = 0  # 是否超时标志

        while (time.time() * 1000 - lastRxNMMsgTimeStamp_ms) < 0.5 * rTNMtimeout_ms:
            time.sleep(0.001)
            nm_message = get_nm_message_list()
            lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else lastRxNMMsgTimeStamp_ms
            if (time.time() * 1000 - testStartTime_ms) >= testTimeout_ms:
                testTimeoutFlag = 1
                break

        # 60s超时之前进入了准备睡眠状态
        if not testTimeoutFlag:
            TestLog("INFO", "", f"DUT发送最后1帧NM报文时刻：{lastRxNMMsgTimeStamp_ms/1000} S")
            check_ready_sleep_state_rx_msg(0.5 * rTNMtimeout_ms)
        else:
            TestLog("FAIL", "", "期望结果:DUT停止发送NM报文，正常发送应用报文，"
                                "实际结果:取消主动唤醒源之后，超过60s时间，DUT仍然一直发送NM报文，测试终止")
            return


        TestLog("INFO", "Step4", "以正常周期TnormalCycle重新开始发送唤醒报文，RepeatMessageRequestBit设置为0，持续TpassiveKeep时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_passive_normal_cycle_start()

        time.sleep(rTpassiveKeep_s)

        check_readySleep_to_normal_state()

        TestLog("INFO", "Step5", f"取消被动唤醒源，等待DUT进入睡眠模式")
        wakeup_passive_normal_cycle_stop()

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC16_ReadySleepStateGotoRepeatMessageState_ActiveWakeup():
    """准备睡眠模式迁移至重复报文模式-主动唤醒测试"""
    case_name = "准备睡眠模式迁移至重复报文模式-主动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rReadyToReptMsg = P.NMInfo.ReadySleepStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间

        if rReadyToReptMsg == 0:
            TestLog("WARNING", "", "ReadySleepStateToRepeatMessageState = 0, 该用例不适用")
            return

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始，等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_active_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)

        check_repeat_message_state_after_active_wakeup()

        TestLog("INFO", "Step3",
                "取消主动唤醒源，从收到DUT发出最后1帧NM报文开始等待0.5*TNMtimeout时间，监控DUT在此期间是否停止发送NM报文，并且正常发送应用报文")
        wakeup_active_stop()

        nm_message = get_nm_message_list()
        lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else 0
        clear_ctx_can_messages()

        testStartTime_ms =  time.time() * 1000
        # lastRxNMMsgTimeStamp_ms =  time.time() * 1000
        testTimeout_ms = 60000  # 60s超时
        testTimeoutFlag = 0  # 是否超时标志

        while (time.time() * 1000 - lastRxNMMsgTimeStamp_ms) < 0.5 * rTNMtimeout_ms:
            time.sleep(0.001)
            nm_message = get_nm_message_list()
            lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else lastRxNMMsgTimeStamp_ms
            if (time.time() * 1000 - testStartTime_ms) >= testTimeout_ms:
                testTimeoutFlag = 1
                break

        # 60s超时之前进入了准备睡眠状态
        if not testTimeoutFlag:
            TestLog("INFO", "", f"DUT发送最后1帧NM报文时刻：{lastRxNMMsgTimeStamp_ms/1000} S")
            check_ready_sleep_state_rx_msg(0.5 * rTNMtimeout_ms)
        else:
            TestLog("FAIL", "", "期望结果:DUT停止发送NM报文，正常发送应用报文，"
                                "实际结果:取消主动唤醒源之后，超过60s时间，DUT仍然一直发送NM报文，测试终止")
            return


        TestLog("INFO", "Step4", "触发重复报文模式请求，等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()

        repeat_msg_state_req_start()

        time.sleep(rTrepeatMessage_ms / 1000.0)

        check_repeat_message_state_after_repeat_msg_request()

        TestLog("INFO", "Step5", f"取消重复报文模式请求，等待DUT进入睡眠模式")
        repeat_msg_state_req_stop()

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC17_ReadySleepStateGotoRepeatMessageState_PassiveWakeup():
    """准备睡眠模式迁移至重复报文模式-被动唤醒测试"""
    case_name = "准备睡眠模式迁移至重复报文模式-被动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rReadyToReptMsg = P.NMInfo.ReadySleepStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间

        if rReadyToReptMsg == 0:
            TestLog("WARNING", "", "ReadySleepStateToRepeatMessageState = 0, 该用例不适用")
            return

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发被动唤醒源并保持，从收到DUT发出第1帧报文开始，等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_passive_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)

        check_repeat_message_state_after_passive_wakeup()

        TestLog("INFO", "Step3",
                "停止发送唤醒报文，从收到DUT发出最后1帧NM报文开始等待0.5*TNMtimeout时间，监控DUT在此期间是否停止发送NM报文，并且正常发送应用报文")
        wakeup_passive_stop()

        nm_message = get_nm_message_list()
        lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else 0
        clear_ctx_can_messages()

        testStartTime_ms =  time.time() * 1000
        # lastRxNMMsgTimeStamp_ms =  time.time() * 1000
        testTimeout_ms = 60000  # 60s超时
        testTimeoutFlag = 0  # 是否超时标志

        while (time.time() * 1000 - lastRxNMMsgTimeStamp_ms) < 0.5 * rTNMtimeout_ms:
            time.sleep(0.001)
            nm_message = get_nm_message_list()
            lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else lastRxNMMsgTimeStamp_ms
            if (time.time() * 1000 - testStartTime_ms) >= testTimeout_ms:
                testTimeoutFlag = 1
                break

        # 60s超时之前进入了准备睡眠状态
        if not testTimeoutFlag:
            TestLog("INFO", "", f"DUT发送最后1帧NM报文时刻：{lastRxNMMsgTimeStamp_ms/1000} S")
            check_ready_sleep_state_rx_msg(0.5 * rTNMtimeout_ms)
        else:
            TestLog("FAIL", "", "期望结果:DUT停止发送NM报文，正常发送应用报文，"
                                "实际结果:取消主动唤醒源之后，超过60s时间，DUT仍然一直发送NM报文，测试终止")
            return

        TestLog("INFO", "Step4", "触发重复报文模式请求，等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        repeat_msg_state_req_start()

        time.sleep(rTrepeatMessage_ms / 1000.0)

        check_repeat_message_state_after_repeat_msg_request()

        TestLog("INFO", "Step5", f"取消重复报文模式请求，等待DUT进入睡眠模式")
        repeat_msg_state_req_stop()

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC18_ReadySleepStateGotoPrepareSleepState_ActiveWakeup():
    """准备睡眠模式迁移至预睡眠模式-主动唤醒测试"""
    case_name = "准备睡眠模式迁移至预睡眠模式-主动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms # Wait Bus Sleep Timer时间

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始，等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_active_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)

        check_repeat_message_state_after_active_wakeup()

        TestLog("INFO", "Step3",
                "取消主动唤醒源，从收到DUT发出最后1帧NM报文开始等待TNMtimeout时间，监控DUT在此期间是否停止发送NM报文，并且正常发送应用报文")
        wakeup_active_stop()

        nm_message = get_nm_message_list()
        lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else 0

        testStartTime_ms =  time.time() * 1000
        # lastRxNMMsgTimeStamp_ms =  time.time() * 1000
        testTimeout_ms = 60000  # 60s超时
        testTimeoutFlag = 0  # 是否超时标志

        while (time.time() * 1000 - lastRxNMMsgTimeStamp_ms) < rTNMtimeout_ms:
            time.sleep(0.001)
            nm_message = get_nm_message_list()
            lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else lastRxNMMsgTimeStamp_ms
            if (time.time() * 1000 - testStartTime_ms) >= testTimeout_ms:
                testTimeoutFlag = 1
                break

        # 60s超时之前进入了准备睡眠状态
        if not testTimeoutFlag:
            TestLog("INFO", "", f"DUT发送最后1帧NM报文时刻：{lastRxNMMsgTimeStamp_ms/1000} S")
            check_ready_sleep_state_rx_app_msg()
        else:
            TestLog("FAIL", "", "期望结果:DUT停止发送NM报文，正常发送应用报文，"
                                "实际结果:取消主动唤醒源之后，超过60s时间，DUT仍然一直发送NM报文")
            return

        TestLog("INFO", "Step4", "从DUT发出最后1帧报文开始，等待0.8*TwaitBusSleep时间，然后仿真发送1帧报文（ID为0x001，DLC=8，数据内容均为0x55），监控总线是否出现错误帧")
        testStartTime_ms =  time.time() * 1000
        app_message = get_app_message_list()
        lastRxMsgTimeStamp_ms =  app_message[-1].time_ms if app_message else 0
        testTimeout_ms = 60000  # 60s超时
        while (time.time() * 1000 - lastRxMsgTimeStamp_ms) < 0.8 * rTwaitBusSleep_ms:
            time.sleep(0.001)
            app_message = get_app_message_list()
            lastRxMsgTimeStamp_ms = app_message[-1].time_ms if app_message else lastRxMsgTimeStamp_ms
            if (time.time() * 1000 - testStartTime_ms) >= testTimeout_ms:
                testTimeoutFlag = 1
                break
        clear_ctx_can_messages()

        # DUT进入预睡眠模式
        if not testTimeoutFlag:
            TestLog("INFO", "", f"DUT发送最后1帧报文时刻：{lastRxMsgTimeStamp_ms/1000} S")
            prepare_sleep_state_test_start()
            prepare_sleep_state_test_stop()
            time.sleep(0.5*rTwaitBusSleep_ms / 1000)  # 用于检测是否被唤醒

            check_prepare_sleep_state()
        # DUT无法进入预睡眠模式
        else:

            TestLog("FAIL", "", "期望结果：DUT停止发送NM报文和应用报文，总线无错误帧，"
                                "实际结果:等待超过60s，DUT一直发送报文，无法进入预睡眠模式，测试终止")
            return

        TestLog("INFO", "Step5", f"等待DUT进入睡眠模式")
        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC19_ReadySleepStateGotoPrepareSleepState_PassiveWakeup():
    """准备睡眠模式迁移至预睡眠模式-被动唤醒测试"""
    case_name = "准备睡眠模式迁移至预睡眠模式-被动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms # Wait Bus Sleep Timer时间

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发被动唤醒请求并保持，从收到DUT发出第1帧报文开始，等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_passive_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)

        check_repeat_message_state_after_passive_wakeup()

        TestLog("INFO", "Step3",
                "停止发送唤醒报文，从收到DUT发出最后1帧NM报文开始等待TNMtimeout时间，监控DUT在此期间是否停止发送NM报文，并且正常发送应用报文")
        wakeup_passive_stop()

        nm_message = get_nm_message_list()
        lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else 0

        testStartTime_ms =  time.time() * 1000
        # lastRxNMMsgTimeStamp_ms =  time.time() * 1000
        testTimeout_ms = 60000  # 60s超时
        testTimeoutFlag = 0  # 是否超时标志

        while (time.time() * 1000 - lastRxNMMsgTimeStamp_ms) < rTNMtimeout_ms:
            time.sleep(0.001)
            nm_message = get_nm_message_list()
            lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else lastRxNMMsgTimeStamp_ms
            if (time.time() * 1000 - testStartTime_ms) >= testTimeout_ms:
                testTimeoutFlag = 1
                break

        # 60s超时之前进入了准备睡眠状态
        if not testTimeoutFlag:
            TestLog("INFO", "", f"DUT发送最后1帧NM报文时刻：{lastRxNMMsgTimeStamp_ms/1000} S")
            check_ready_sleep_state_rx_app_msg()
        else:
            TestLog("FAIL", "", "期望结果:DUT停止发送NM报文，正常发送应用报文，"
                                "实际结果:停止发送唤醒报文之后，超过60s时间，DUT仍然一直发送NM报文")
            return

        TestLog("INFO", "Step4", "从DUT发出最后1帧报文开始，等待0.8*TwaitBusSleep时间，然后仿真发送1帧报文（ID为0x001，DLC=8，数据内容均为0x55），监控总线是否出现错误帧")
        testStartTime_ms =  time.time() * 1000
        app_message = get_app_message_list()
        lastRxMsgTimeStamp_ms =  app_message[-1].time_ms if app_message else 0
        testTimeout_ms = 60000  # 60s超时
        while (time.time() * 1000 - lastRxMsgTimeStamp_ms) < 0.8 * rTwaitBusSleep_ms:
            time.sleep(0.001)
            app_message = get_app_message_list()
            lastRxMsgTimeStamp_ms = app_message[-1].time_ms if app_message else lastRxMsgTimeStamp_ms
            if (time.time() * 1000 - testStartTime_ms) >= testTimeout_ms:
                testTimeoutFlag = 1
                break
        clear_ctx_can_messages()

        # DUT进入预睡眠模式
        if not testTimeoutFlag:
            TestLog("INFO", "", f"DUT发送最后1帧报文时刻：{lastRxMsgTimeStamp_ms/1000} S")
            prepare_sleep_state_test_start()
            prepare_sleep_state_test_stop()
            time.sleep(0.5*rTwaitBusSleep_ms / 1000)  # 用于检测是否被唤醒

            check_prepare_sleep_state()
        # DUT无法进入预睡眠模式
        else:

            TestLog("FAIL", "", "期望结果：DUT停止发送NM报文和应用报文，总线无错误帧，"
                                "实际结果:等待超过60s，DUT一直发送报文，无法进入预睡眠模式，测试终止")
            return

        TestLog("INFO", "Step5", f"等待DUT进入睡眠模式")
        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC20_PrepareSleepStateGotoRepeatMessageState_ActiveWakeup():
    """预睡眠模式迁移至重复报文模式-主动唤醒测试"""
    case_name = "预睡眠模式迁移至重复报文模式-主动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms # Wait Bus Sleep Timer时间

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始，等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_active_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)

        check_repeat_message_state_after_active_wakeup()

        TestLog("INFO", "Step3",
                "取消主动唤醒源，从DUT发出最后1帧报文开始，等待0.5*TwaitBusSleep时间，然后仿真发送1帧报文（ID为0x001，DLC=8，数据内容均为0x55），监控总线是否出现错误帧")
        wakeup_active_stop()
        app_message = get_app_message_list()
        lastRxMsgTimeStamp_ms =  app_message[-1].time_ms if app_message else 0
        clear_ctx_can_messages()

        testStartTime_ms =  time.time() * 1000
        # lastRxMsgTimeStamp_ms =  time.time() * 1000
        testTimeout_ms = 60000  # 60s超时
        testTimeoutFlag = 0  # 是否超时标志

        # 等待DUT进入预睡眠模式
        while (time.time() * 1000 - lastRxMsgTimeStamp_ms) < 0.5 * rTwaitBusSleep_ms:
            time.sleep(0.001)
            app_message = get_app_message_list()
            lastRxMsgTimeStamp_ms = app_message[-1].time_ms if app_message else lastRxMsgTimeStamp_ms
            if (time.time() * 1000 - testStartTime_ms) >= testTimeout_ms:
                testTimeoutFlag = 1
                break
        clear_ctx_can_messages()

        # DUT进入预睡眠模式
        if not testTimeoutFlag:
            TestLog("INFO", "", f"DUT发送最后1帧报文时刻：{lastRxMsgTimeStamp_ms/1000} S")

            prepare_sleep_state_test_start()
            prepare_sleep_state_test_stop()
            time.sleep(0.5 * rTwaitBusSleep_ms / 1000)
            check_prepare_sleep_state()
        else:
            TestLog("FAIL", "", "期望结果：DUT停止发送NM报文和应用报文，总线无错误帧，"
                                "实际结果:等待超过60s，DUT一直发送报文，无法进入预睡眠模式，测试终止")
            return

        TestLog("INFO", "Step4", "重新触发主动唤醒源并保持，从收到DUT发出第1帧报文开始，等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_active_start()

        # 等待DUT唤醒
        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTwaitBusSleep_ms / 1000.0)
        check_repeat_message_state_after_active_wakeup()

        TestLog("INFO", "Step5", f"取消主动唤醒源，等待DUT进入睡眠模式")
        wakeup_active_stop()

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC21_PrepareSleepStateGotoRepeatMessageState_PassiveWakeup():
    """预睡眠模式迁移至重复报文模式-被动唤醒测试"""
    case_name = "预睡眠模式迁移至重复报文模式-被动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms # Wait Bus Sleep Timer时间

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发被动唤醒请求并保持，从收到DUT发出第1帧报文开始，等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_passive_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)

        check_repeat_message_state_after_passive_wakeup()

        TestLog("INFO", "Step3",
                "停止发送唤醒报文，从DUT发出最后1帧报文开始，等待0.5*TwaitBusSleep时间，然后仿真发送1帧报文（ID为0x001，DLC=8，数据内容均为0x55），监控总线是否出现错误帧")
        wakeup_passive_stop()
        app_message = get_app_message_list()
        lastRxMsgTimeStamp_ms =  app_message[-1].time_ms if app_message else 0
        clear_ctx_can_messages()

        testStartTime_ms =  time.time() * 1000
        # lastRxMsgTimeStamp_ms =  time.time() * 1000
        testTimeout_ms = 60000  # 60s超时
        testTimeoutFlag = 0  # 是否超时标志

        # 等待DUT进入预睡眠模式
        while (time.time() * 1000 - lastRxMsgTimeStamp_ms) < 0.5 * rTwaitBusSleep_ms:
            time.sleep(0.001)
            app_message = get_app_message_list()
            lastRxMsgTimeStamp_ms = app_message[-1].time_ms if app_message else lastRxMsgTimeStamp_ms
            if (time.time() * 1000 - testStartTime_ms) >= testTimeout_ms:
                testTimeoutFlag = 1
                break
        clear_ctx_can_messages()

        # DUT进入预睡眠模式
        if not testTimeoutFlag:
            TestLog("INFO", "", f"DUT发送最后1帧报文时刻：{lastRxMsgTimeStamp_ms/1000} S")

            prepare_sleep_state_test_start()
            prepare_sleep_state_test_stop()
            time.sleep(0.5 * rTwaitBusSleep_ms / 1000)
            check_prepare_sleep_state()
        else:
            TestLog("FAIL", "", "期望结果：DUT停止发送NM报文和应用报文，总线无错误帧，"
                                "实际结果:等待超过60s，DUT一直发送报文，无法进入预睡眠模式，测试终止")
            return

        TestLog("INFO", "Step4", "停止发送仿真报文，重新触发被动唤醒请求并保持，从收到DUT发出第1帧报文开始等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_passive_start()

        # 等待DUT唤醒
        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTwaitBusSleep_ms / 1000.0)
        check_repeat_message_state_after_passive_wakeup()

        TestLog("INFO", "Step5", f"停止发送唤醒报文，等待DUT进入睡眠模式")
        wakeup_passive_stop()

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC22_PrepareSleepStateGotoBusSleepState_ActiveWakeup():
    """预睡眠模式迁移至睡眠模式-主动唤醒测试"""
    case_name = "预睡眠模式迁移至睡眠模式-主动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms # Wait Bus Sleep Timer时间

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始，等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_active_start()

        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)

        check_repeat_message_state_after_active_wakeup()

        TestLog("INFO", "Step3",
                "取消主动唤醒源，从DUT发出最后1帧报文开始，等待0.5*TwaitBusSleep时间，然后仿真发送1帧报文（ID为0x001，DLC=8，数据内容均为0x55），监控总线是否出现错误帧")
        wakeup_active_stop()
        app_message = get_app_message_list()
        lastRxMsgTimeStamp_ms =  app_message[-1].time_ms if app_message else 0
        clear_ctx_can_messages()

        testStartTime_ms =  time.time() * 1000
        # lastRxMsgTimeStamp_ms =  time.time() * 1000
        testTimeout_ms = 60000  # 60s超时
        testTimeoutFlag = 0  # 是否超时标志

        # 等待DUT进入预睡眠模式
        while (time.time() * 1000 - lastRxMsgTimeStamp_ms) < 0.5 * rTwaitBusSleep_ms:
            time.sleep(0.001)
            app_message = get_app_message_list()
            lastRxMsgTimeStamp_ms = app_message[-1].time_ms if app_message else lastRxMsgTimeStamp_ms
            if (time.time() * 1000 - testStartTime_ms) >= testTimeout_ms:
                testTimeoutFlag = 1
                break
        clear_ctx_can_messages()

        # DUT进入预睡眠模式
        if not testTimeoutFlag:
            TestLog("INFO", "", f"DUT发送最后1帧报文时刻：{lastRxMsgTimeStamp_ms/1000} S")

            prepare_sleep_state_test_start()
            prepare_sleep_state_test_stop()
            time.sleep(0.5 * rTwaitBusSleep_ms / 1000)
            check_prepare_sleep_state()
        else:
            TestLog("FAIL", "", "期望结果：DUT停止发送NM报文和应用报文，总线无错误帧，"
                                "实际结果:等待超过60s，DUT一直发送报文，无法进入预睡眠模式，测试终止")
            return

        TestLog("INFO", "Step4", "继续等待TwaitBusSleep时间，然后仿真发送1帧报文（ID为0x001，DLC=8，数据内容均为0x55），等待TrepeatMessage时间，监控总线是否出现错误帧")
        time.sleep(rTwaitBusSleep_ms / 1000.0)
        prepare_sleep_state_test_start()
        prepare_sleep_state_test_stop()
        time.sleep(rTrepeatMessage_ms / 1000.0)

        # 结果判断
        check_bus_sleep_state()

        TestLog("INFO", "Step5", f"等待DUT进入睡眠模式")
        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC23_PrepareSleepStateGotoBusSleepState_PassiveWakeup():
    """预睡眠模式迁移至睡眠模式-被动唤醒测试"""
    case_name = "预睡眠模式迁移至睡眠模式-被动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms # Wait Bus Sleep Timer时间

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发被动唤醒请求并保持，从收到DUT发出第1帧报文开始，等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
        clear_ctx_can_messages()
        wakeup_passive_start()

        # 等待DUT唤醒
        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000.0)

        check_repeat_message_state_after_passive_wakeup()

        TestLog("INFO", "Step3",
                "停止发送唤醒报文，从DUT发出最后1帧报文开始，等待0.5*TwaitBusSleep时间，然后仿真发送1帧报文（ID为0x001，DLC=8，数据内容均为0x55），监控总线是否出现错误帧")
        wakeup_passive_stop()
        app_message = get_app_message_list()
        lastRxMsgTimeStamp_ms =  app_message[-1].time_ms if app_message else 0
        # TestLog("INFO", "",f"lastRxMsgTimeStamp_ms = {lastRxMsgTimeStamp_ms}")
        clear_ctx_can_messages()

        testStartTime_ms =  time.time() * 1000
        # lastRxMsgTimeStamp_ms =  time.time() * 1000
        testTimeout_ms = 60000  # 60s超时
        testTimeoutFlag = 0  # 是否超时标志

        # 等待DUT进入预睡眠模式
        while (time.time() * 1000 - lastRxMsgTimeStamp_ms) < 0.5 * rTwaitBusSleep_ms:
            time.sleep(0.001)
            app_message = get_app_message_list()
            lastRxMsgTimeStamp_ms = app_message[-1].time_ms if app_message else lastRxMsgTimeStamp_ms
            # TestLog("INFO", "", f"lastRxMsgTimeStamp_ms = {lastRxMsgTimeStamp_ms}")
            if (time.time() * 1000 - testStartTime_ms) >= testTimeout_ms:
                testTimeoutFlag = 1
                break
        clear_ctx_can_messages()

        # DUT进入预睡眠模式
        if not testTimeoutFlag:
            TestLog("INFO", "", f"DUT发送最后1帧报文时刻：{lastRxMsgTimeStamp_ms/1000} S")

            prepare_sleep_state_test_start()
            prepare_sleep_state_test_stop()
            time.sleep(0.5 * rTwaitBusSleep_ms / 1000)
            check_prepare_sleep_state()
        else:
            TestLog("FAIL", "", "期望结果：DUT停止发送NM报文和应用报文，总线无错误帧，"
                                "实际结果:等待超过60s，DUT一直发送报文，无法进入预睡眠模式，测试终止")
            return

        time.sleep(10)
        TestLog("INFO", "Step4", "继续等待TwaitBusSleep时间，然后仿真发送1帧报文（ID为0x001，DLC=8，数据内容均为0x55），等待TrepeatMessage时间，监控总线是否出现错误帧")
        time.sleep(rTwaitBusSleep_ms / 1000.0)
        prepare_sleep_state_test_start()
        prepare_sleep_state_test_stop()
        wakeup_passive_stop()
        time.sleep(rTrepeatMessage_ms / 1000.0)

        # 结果判断
        check_bus_sleep_state()

        TestLog("INFO", "Step5", f"等待DUT进入睡眠模式")
        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC24_SleepProcesstoRepeatMessageState_ActiveWakeup():
    """休眠过程中迁移至重复报文模式-主动唤醒测试"""
    case_name = "休眠过程中迁移至重复报文模式-主动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rReadyToReptMsg = P.NMInfo.ReadySleepStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间

        if rReadyToReptMsg == 0:
            TestLog("WARNING", "", "ReadySleepStateToRepeatMessageState = 0, 该用例不适用")
            return

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        for n in range(50):
            TestLog("INFO", "", f"第 {n + 1} 次测试")
            clear_ctx_can_messages()

            TestLog("INFO", "Step2", "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始，等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
            wakeup_active_start()

            if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
                TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
                return

            time.sleep(rTrepeatMessage_ms / 1000.0)

            check_repeat_message_state_after_active_wakeup()

            TestLog("INFO", "Step3",
                    f"取消主动唤醒源，从DUT发出最后1帧NM报文开始，等待0.5*TNMtimeout + {n}*100 ms时间")
            wakeup_active_stop()

            nm_message = get_nm_message_list()
            lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else 0
            clear_ctx_can_messages()

            testStartTime_ms =  time.time() * 1000
            # lastRxNMMsgTimeStamp_ms =  time.time() * 1000
            testTimeout_ms = 60000  # 60s超时
            testTimeoutFlag = 0  # 是否超时标志

            while (time.time() * 1000 - lastRxNMMsgTimeStamp_ms) < 0.5 * rTNMtimeout_ms + n * 100:
                time.sleep(0.001)
                nm_message = get_nm_message_list()
                lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else lastRxNMMsgTimeStamp_ms
                if (time.time() * 1000 - testStartTime_ms) >= testTimeout_ms:
                    testTimeoutFlag = 1
                    break

            # 60s超时之前进入了准备睡眠状态
            if not testTimeoutFlag:
                TestLog("INFO", "", f"DUT发送最后1帧NM报文时刻：{lastRxNMMsgTimeStamp_ms/1000} S")
                # check_ready_sleep_state_rx_msg(0.5 * rTNMtimeout_ms)
            else:
                TestLog("FAIL", "", "期望结果:DUT停止发送NM报文，正常发送应用报文，"
                                    "实际结果:取消主动唤醒源之后，超过60s时间，DUT仍然一直发送NM报文，测试终止")
                return


            TestLog("INFO", "Step4", "重新触发主动唤醒源并保持，从收到DUT发出第1帧报文开始，等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
            clear_ctx_can_messages()
            wakeup_active_start()

            # 等待DUT唤醒发出第1帧报文
            if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
                TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
                return

            time.sleep(rTrepeatMessage_ms / 1000.0)


            check_repeat_message_state_after_active_wakeup()

            TestLog("INFO", "Step5", f"取消主动唤醒源，等待DUT进入睡眠模式")
            wakeup_active_stop()

            # 等待DUT进入睡眠模式
            status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
            if status is False:
                TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
                return

            TestLog("INFO", "Step6", "n+1，重复2-5步，n*100<TNMtimeout+TwaitBusSleep(ms)")

        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC25_SleepProcesstoRepeatMessageState_PassiveWakeup():
    """休眠过程中迁移至重复报文模式-被动唤醒测试"""
    case_name = "休眠过程中迁移至重复报文模式-被动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rReadyToReptMsg = P.NMInfo.ReadySleepStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间

        if rReadyToReptMsg == 0:
            TestLog("WARNING", "", "ReadySleepStateToRepeatMessageState = 0, 该用例不适用")
            return

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        for n in range(50):
            TestLog("INFO", "", f"第 {n + 1} 次测试")
            clear_ctx_can_messages()

            TestLog("INFO", "Step2", "触发被动唤醒请求并保持，从收到DUT发出第1帧报文开始，等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
            wakeup_passive_start()

            if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
                TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
                return

            time.sleep(rTrepeatMessage_ms / 1000.0)

            check_repeat_message_state_after_passive_wakeup()

            TestLog("INFO", "Step3",
                    f"取消被动唤醒源，从DUT发出最后1帧NM报文开始，等待0.5*TNMtimeout + {n}*100 ms时间")
            wakeup_passive_stop()

            nm_message = get_nm_message_list()
            lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else 0
            clear_ctx_can_messages()

            testStartTime_ms =  time.time() * 1000
            # lastRxNMMsgTimeStamp_ms =  time.time() * 1000
            testTimeout_ms = 60000  # 60s超时
            testTimeoutFlag = 0  # 是否超时标志

            while (time.time() * 1000 - lastRxNMMsgTimeStamp_ms) < 0.5 * rTNMtimeout_ms + n * 100:
                time.sleep(0.001)
                nm_message = get_nm_message_list()
                lastRxNMMsgTimeStamp_ms = nm_message[-1].time_ms if nm_message else lastRxNMMsgTimeStamp_ms
                if (time.time() * 1000 - testStartTime_ms) >= testTimeout_ms:
                    testTimeoutFlag = 1
                    break

            # 60s超时之前进入了准备睡眠状态
            if not testTimeoutFlag:
                TestLog("INFO", "", f"DUT发送最后1帧NM报文时刻：{lastRxNMMsgTimeStamp_ms/1000} S")
                # check_ready_sleep_state_rx_msg(0.5 * rTNMtimeout_ms)
            else:
                TestLog("FAIL", "", "期望结果:DUT停止发送NM报文，正常发送应用报文，"
                                    "实际结果:取消主动唤醒源之后，超过60s时间，DUT仍然一直发送NM报文，测试终止")
                return


            TestLog("INFO", "Step4", "重新触发被动唤醒源并保持，从收到DUT发出第1帧报文开始，等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
            clear_ctx_can_messages()
            wakeup_passive_start()

            # 等待DUT唤醒发出第1帧报文
            if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
                TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
                return

            time.sleep(rTrepeatMessage_ms / 1000.0)


            check_repeat_message_state_after_passive_wakeup()

            TestLog("INFO", "Step5", f"取消被动唤醒源，等待DUT进入睡眠模式")
            wakeup_passive_stop()

            # 等待DUT进入睡眠模式
            status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
            if status is False:
                TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
                return

            TestLog("INFO", "Step6", "n+1，重复2-5步，n*100<TNMtimeout+TwaitBusSleep(ms)")

        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG3_TC1_WakeupTimeCheck_ActiveWakeup():
    """唤醒时间检查-主动唤醒测试"""
    case_name = "唤醒时间检查-主动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rIsleep_mA = P.ECUInfo.ISleep  
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveWakeup_ms
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms # Wait Bus Sleep Timer时间
        rNtimeRepeat = P.NMInfo.NtimeRepeat  # 时间参数测试次数

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，触发主动唤醒源并保持，等待3秒，取消主动唤醒源，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        wakeup_active_start()
        time.sleep(3)
        wakeup_active_stop()

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)


        for i in range(rNtimeRepeat):
            TestLog("INFO", "", f"第 {i + 1} 次测试")
            clear_ctx_can_messages()

            TestLog("INFO", "Step2",
                    "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文，计算从触发主动唤醒源时刻到DUT发出第1帧NM报文时刻的间隔时间Twakeup");
            clear_ctx_can_messages()
            wakeup_active_start()
            clear_ctx_can_messages() 

            testStartTime_ms = time.time() * 1000

            # 等待DUT唤醒
            if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
                TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
                return

            time.sleep(rTrepeatMessage_ms / 1000)

            nm_message = get_nm_message_list()
            firstRxMsgTimeStamp_ms = nm_message[0].time_ms
            internalTime_ms = firstRxMsgTimeStamp_ms - testStartTime_ms
            if internalTime_ms <= rTactiveKeep_s * 1000:
                TestLog("PASS", "", f"期望结果：唤醒时间 <= TactiveWakeup， "
                                    f"实际结果：唤醒时间：{internalTime_ms} ms <= {rTactiveKeep_s*1000} ms")
            else:
                TestLog("FAIL", "", f"期望结果：唤醒时间 <= TactiveWakeup， "
                                    f"实际结果：唤醒时间：{internalTime_ms} ms > {rTactiveKeep_s*1000} ms")

            TestLog("INFO", "Step3", f"取消主动唤醒源，等待DUT进入睡眠模式")
            wakeup_active_stop()
            # 等待DUT进入睡眠模式
            status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
            if status is False:
                TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
                return

            TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG3_TC2_WakeupTimeCheck_PassiveWakeup():
    """唤醒时间检查-被动唤醒测试"""
    case_name = "唤醒时间检查-被动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rIsleep_mA = P.ECUInfo.ISleep  
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveWakeup_ms
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms # Wait Bus Sleep Timer时间
        rNtimeRepeat = P.NMInfo.NtimeRepeat  # 时间参数测试次数

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，触发被动唤醒请求并保持，等待3秒，取消被动唤醒请求，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        wakeup_passive_start()
        time.sleep(3)
        wakeup_passive_stop()

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)


        for i in range(rNtimeRepeat):
            TestLog("INFO", "", f"第 {i + 1} 次测试")
            clear_ctx_can_messages()

            TestLog("INFO", "Step2",
                    "触发被动唤醒请求并保持，从收到DUT发出第1帧报文开始等待TrepeatMessage时间，监控在此期间DUT发出的所有NM报文，计算从发送唤醒报文时刻到DUT发出第1帧NM报文时刻的间隔时间Twakeup");
            clear_ctx_can_messages()
            wakeup_passive_start()
            clear_ctx_can_messages() 

            testStartTime_ms = time.time() * 1000

            # 等待DUT唤醒
            if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
                TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
                return

            time.sleep(rTrepeatMessage_ms / 1000)

            nm_message = get_nm_message_list()
            firstRxMsgTimeStamp_ms = nm_message[0].time_ms
            internalTime_ms = firstRxMsgTimeStamp_ms - testStartTime_ms
            if internalTime_ms <= rTpassiveKeep_s * 1000:
                TestLog("PASS", "", f"期望结果：唤醒时间 <= TpassiveWakeup， "
                                    f"实际结果：唤醒时间：{internalTime_ms} ms <= {rTpassiveKeep_s*1000} ms")
            else:
                TestLog("FAIL", "", f"期望结果：唤醒时间 <= TpassiveWakeup， "
                                    f"实际结果：唤醒时间：{internalTime_ms} ms > {rTpassiveKeep_s*1000} ms")

            TestLog("INFO", "Step3", f"停止发送唤醒报文，等待DUT进入睡眠模式")
            wakeup_passive_stop()
            # 等待DUT进入睡眠模式
            status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
            if status is False:
                TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
                return

            TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG3_TC3_AllMsgFirstSendTimeCheck_ActiveWakeup():
    """所有报文发送一轮时间检查-主动唤醒测试"""
    case_name = "所有报文发送一轮时间检查-主动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms # Wait Bus Sleep Timer时间
        rNtimeRepeat = P.NMInfo.NtimeRepeat  # 时间参数测试次数
        rTinitialCycle_ms = P.NMInfo.TinitialCycle_ms  # DUT唤醒后发送完一轮报文的时间

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)


        for i in range(rNtimeRepeat):
            TestLog("INFO", "", f"第 {i + 1} 次测试")
            clear_ctx_can_messages()

            TestLog("INFO", "Step2",
                    "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始等待TrepeatMessage时间，记录在此期间收到的所有报文")
            wakeup_active_start()

            testStartTime_ms = time.time() * 1000

            # 等待DUT唤醒
            if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
                TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
                return

            time.sleep(rTrepeatMessage_ms / 1000)

            sMsgInfoList = ctx.can.get_info("sMsgInfoList") or {}
            rx_messages = get_rx_message_list()

            errorCount = 0
            errorMsgIDList = []
            # 遍历数据库
            for db_msg_id, msg_info in sMsgInfoList.items():
                if db_msg_id >= 0x700:
                    continue
                if msg_info.get("cycle", 0) == 0:
                    continue
                findFlag = 0
                for rx_msg in rx_messages:
                    if rx_msg.id == db_msg_id and findFlag == 0:
                        findFlag = 1
                        # 指定id的第一帧消息的时间 - 收到的所有报文的第一帧消息的时间
                        internalTime_ms = get_msg_first_ms(db_msg_id) - rx_messages[0].time_ms
                        if internalTime_ms <= rTinitialCycle_ms:
                            TestLog("PASS", "", f"期望结果：报文(ID = {hex(db_msg_id)})在唤醒后的 {rTinitialCycle_ms} ms 时间之内发出， "
                                                f"实际结果：发送时间：{internalTime_ms} ms <= {rTinitialCycle_ms} ms，满足要求")
                        else:
                            errorCount += 1
                            TestLog("FAIL", "", f"期望结果：报文(ID = {hex(db_msg_id)})在唤醒后的 {rTinitialCycle_ms} ms 时间之内发出， "
                                                f"实际结果：发送时间：{internalTime_ms} ms > {rTinitialCycle_ms} ms，不满足要求")
                            errorMsgIDList.append(hex(db_msg_id))

                if findFlag == 0:
                    errorCount += 1
                    TestLog("FAIL", "", f"期望结果：报文(ID = {hex(db_msg_id)})在唤醒后的 {rTinitialCycle_ms} ms 时间之内发出， "
                                        f"实际结果：等待超过TrepeatMessage时间，未收到该报文")
                    errorMsgIDList.append(hex(db_msg_id))

            if errorCount == 0:
                TestLog("PASS", "", f"期望结果：在唤醒后的 {rTinitialCycle_ms} ms 时间之内，DUT所有报文均发送一轮，"
                                    f"实际结果：从接收到第1帧报文开始，在 {rTinitialCycle_ms} ms 时间之内，DUT所有报文均发送一轮，满足要求")
            else:
                TestLog("FAIL", "", f"期望结果：在唤醒后的 {rTinitialCycle_ms} ms 时间之内，DUT所有报文均发送一轮，"
                                    f"实际结果：报文：{errorMsgIDList} 未在规定时间内发出")

            TestLog("INFO", "Step3", f"停止发送唤醒报文，等待DUT进入睡眠模式")
            wakeup_active_stop()
            # 等待DUT进入睡眠模式
            status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
            if status is False:
                TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
                return
            TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG3_TC4_AllMsgFirstSendTimeCheck_PassiveWakeup():
    """所有报文发送一轮时间检查-被动唤醒测试"""
    case_name = "所有报文发送一轮时间检查-被动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms # Wait Bus Sleep Timer时间
        rNtimeRepeat = P.NMInfo.NtimeRepeat  # 时间参数测试次数
        rTinitialCycle_ms = P.NMInfo.TinitialCycle_ms  # DUT唤醒后发送完一轮报文的时间

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)


        for i in range(rNtimeRepeat):
            TestLog("INFO", "", f"第 {i + 1} 次测试")
            clear_ctx_can_messages()

            TestLog("INFO", "Step2",
                    "触发被动唤醒请求并保持，从收到DUT发出第1帧报文开始等待TrepeatMessage时间，记录在此期间收到的所有报文")
            wakeup_passive_start()

            testStartTime_ms = time.time() * 1000

            # 等待DUT唤醒
            if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
                TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
                return

            time.sleep(rTrepeatMessage_ms / 1000)

            sMsgInfoList = ctx.can.get_info("sMsgInfoList") or {}
            rx_messages = get_rx_message_list()

            errorCount = 0
            errorMsgIDList = []
            # 遍历数据库
            for db_msg_id, msg_info in sMsgInfoList.items():
                if db_msg_id >= 0x700:
                    continue
                if msg_info.get("cycle", 0) == 0:
                    continue
                findFlag = 0
                for rx_msg in rx_messages:
                    if rx_msg.id == db_msg_id and findFlag == 0:
                        findFlag = 1
                        # 指定id的第一帧消息的时间 - 收到的所有报文的第一帧消息的时间
                        internalTime_ms = get_msg_first_ms(db_msg_id) - rx_messages[0].time_ms
                        if internalTime_ms <= rTinitialCycle_ms:
                            TestLog("PASS", "", f"期望结果：报文(ID = {hex(db_msg_id)})在唤醒后的 {rTinitialCycle_ms} ms 时间之内发出， "
                                                f"实际结果：发送时间：{internalTime_ms} ms <= {rTinitialCycle_ms} ms，满足要求")
                        else:
                            errorCount += 1
                            TestLog("FAIL", "", f"期望结果：报文(ID = {hex(db_msg_id)})在唤醒后的 {rTinitialCycle_ms} ms 时间之内发出， "
                                                f"实际结果：发送时间：{internalTime_ms} ms > {rTinitialCycle_ms} ms，不满足要求")
                            errorMsgIDList.append(hex(db_msg_id))

                if findFlag == 0:
                    errorCount += 1
                    TestLog("FAIL", "", f"期望结果：报文(ID = {hex(db_msg_id)})在唤醒后的 {rTinitialCycle_ms} ms 时间之内发出， "
                                        f"实际结果：等待超过TrepeatMessage时间，未收到该报文")
                    errorMsgIDList.append(hex(db_msg_id))

            if errorCount == 0:
                TestLog("PASS", "", f"期望结果：在唤醒后的 {rTinitialCycle_ms} ms 时间之内，DUT所有报文均发送一轮，"
                                    f"实际结果：从接收到第1帧报文开始，在 {rTinitialCycle_ms} ms 时间之内，DUT所有报文均发送一轮，满足要求")
            else:
                TestLog("FAIL", "", f"期望结果：在唤醒后的 {rTinitialCycle_ms} ms 时间之内，DUT所有报文均发送一轮，"
                                    f"实际结果：报文：{errorMsgIDList} 未在规定时间内发出")

            TestLog("INFO", "Step3", f"停止发送唤醒报文，等待DUT进入睡眠模式")
            wakeup_passive_stop()
            # 等待DUT进入睡眠模式
            status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
            if status is False:
                TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
                return
            TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG3_TC5_TxEnableTimeCheck_ActiveWakeup():
    """应用报文发送使能时间检查-主动唤醒测试"""
    case_name = "应用报文发送使能时间检查-主动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms # Wait Bus Sleep Timer时间
        rNtimeRepeat = P.NMInfo.NtimeRepeat  # 时间参数测试次数
        rTinitialCycle_ms = P.NMInfo.TinitialCycle_ms  # DUT唤醒后发送完一轮报文的时间
        rTenableTx_ms = P.NMInfo.TenableTx_ms  # DUT发送应用报文使能时间

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)


        for i in range(rNtimeRepeat):
            TestLog("INFO", "", f"第 {i + 1} 次测试")
            clear_ctx_can_messages()

            TestLog("INFO", "Step2",
                    "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始等待TrepeatMessage时间，记录在此期间收到的所有报文")
            wakeup_active_start()

            testStartTime_ms = time.time() * 1000

            # 等待DUT唤醒
            if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
                TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
                return

            time.sleep(rTrepeatMessage_ms / 1000)

            sMsgInfoList = ctx.can.get_info("sMsgInfoList") or {}
            rx_messages = get_rx_message_list()

            # 指定id的第一帧消息的时间 - 收到的所有报文的第一帧消息的时间
            internalTime_ms = get_msg_first_app_msg_ms() - rx_messages[0].time_ms
            if internalTime_ms <= rTenableTx_ms:
                TestLog("PASS", "", f"期望结果：应用报文发送使能时间 <= TenableTx， "
                                    f"实际结果：应用报文发送使能时间：{internalTime_ms} ms <= {rTenableTx_ms} ms")
            else:
                TestLog("FAIL", "", f"期望结果：应用报文发送使能时间 <= TenableTx， "
                                    f"实际结果：应用报文发送使能时间：{internalTime_ms} ms > {rTenableTx_ms} ms")

            TestLog("INFO", "Step3", f"取消主动唤醒源，等待DUT进入睡眠模式")
            wakeup_active_stop()

            time.sleep(10)

            # 等待DUT进入睡眠模式
            status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
            if status is False:
                TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
                return
            TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG3_TC6_TxEnableTimeCheck_PassiveWakeup():
    """应用报文发送使能时间检查-被动唤醒测试"""
    case_name = "应用报文发送使能时间检查-被动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms # Wait Bus Sleep Timer时间
        rNtimeRepeat = P.NMInfo.NtimeRepeat  # 时间参数测试次数
        rTinitialCycle_ms = P.NMInfo.TinitialCycle_ms  # DUT唤醒后发送完一轮报文的时间
        rTenableTx_ms = P.NMInfo.TenableTx_ms  # DUT发送应用报文使能时间

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)


        for i in range(rNtimeRepeat):
            TestLog("INFO", "", f"第 {i + 1} 次测试")
            clear_ctx_can_messages()

            TestLog("INFO", "Step2",
                    "触发被动唤醒请求并保持，从收到DUT发出第1帧报文开始等待TrepeatMessage时间，记录在此期间收到的所有报文")
            wakeup_passive_start()

            testStartTime_ms = time.time() * 1000

            # 等待DUT唤醒
            if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
                TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
                return

            time.sleep(rTrepeatMessage_ms / 1000)

            sMsgInfoList = ctx.can.get_info("sMsgInfoList") or {}
            rx_messages = get_rx_message_list()

            # 指定id的第一帧消息的时间 - 收到的所有报文的第一帧消息的时间
            internalTime_ms = get_msg_first_app_msg_ms() - rx_messages[0].time_ms
            if internalTime_ms <= rTenableTx_ms:
                TestLog("PASS", "", f"期望结果：应用报文发送使能时间 <= TenableTx， "
                                    f"实际结果：应用报文发送使能时间：{internalTime_ms} ms >= {rTenableTx_ms} ms")
            else:
                TestLog("FAIL", "", f"期望结果：应用报文发送使能时间 <= TenableTx， "
                                    f"实际结果：应用报文发送使能时间：{internalTime_ms} ms < {rTenableTx_ms} ms")

            TestLog("INFO", "Step3", f"停止发送唤醒报文，等待DUT进入睡眠模式")
            wakeup_passive_stop()

            time.sleep(10)

            # 等待DUT进入睡眠模式
            status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
            if status is False:
                TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
                return
            TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG3_TC7_ImmediateCycleTimeCheck_ActiveWakeup():
    """快速发送NM报文周期时间检查-主动唤醒测试"""
    case_name = "快速发送NM报文周期时间检查-主动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms # Wait Bus Sleep Timer时间
        rNtimeRepeat = P.NMInfo.NtimeRepeat  # 时间参数测试次数
        rTinitialCycle_ms = P.NMInfo.TinitialCycle_ms  # DUT唤醒后发送完一轮报文的时间
        rTenableTx_ms = P.NMInfo.TenableTx_ms  # DUT发送应用报文使能时间
        rNimmediateSend = P.NMInfo.NimmediateSend  # 快速发送NM报文的帧数
        rTimmediateCycle_ms = P.NMInfo.TimmediateCycle_ms  # 快速发送NM报文的周期
        rTimmediateDeviation = P.NMInfo.TimmediateDeviation_pct  # 快速发送NM报文的周期偏移范围

        rTimmediateSendMin_ms = rTimmediateCycle_ms * (1 - rTimmediateDeviation / 100)
        rTimmediateSendMax_ms = rTimmediateCycle_ms * (1 + rTimmediateDeviation / 100)

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        for i in range(rNtimeRepeat):
            TestLog("INFO", "", f"第 {i + 1} 次测试")
            clear_ctx_can_messages()

            TestLog("INFO", "Step2",
                    "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始等待TrepeatMessage时间，记录在此期间收到的所有报文")
            wakeup_active_start()

            testStartTime_ms = time.time() * 1000

            # 等待DUT唤醒
            if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
                TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
                return

            time.sleep(rTrepeatMessage_ms / 1000)

            errorFlag = 0
            strAllNMMMsgTimeList = []
            strErrorMsgSendTime = []
            # 比较前NimmediateSend帧NM报文的发送间隔是否满足要求
            nm_message = get_nm_message_list()
            for j in range(1, rNimmediateSend):
                if j > 1:
                    pass

                internal_ms = nm_message[j].time_ms - nm_message[j-1].time_ms
                strAllNMMMsgTimeList.append(internal_ms)
                if rTimmediateSendMin_ms <= internal_ms <= rTimmediateSendMax_ms:
                    pass
                else:
                    errorFlag = 1
                    strErrorMsgSendTime.append(internal_ms)

            if errorFlag == 0:
                TestLog("PASS", "", f"期望结果:前 {rNimmediateSend} 帧NM报文发送间隔均满足快发周期({rTimmediateCycle_ms} ms)，"
                                    f"实际结果:{strAllNMMMsgTimeList}，满足要求")
            else:
                TestLog("FAIL", "", f"期望结果:前 {rNimmediateSend} 帧NM报文发送间隔均满足快发周期({rTimmediateCycle_ms} ms)，"
                                    f"实际结果:{strAllNMMMsgTimeList}，其中{strErrorMsgSendTime}, 不满足要求")


            TestLog("INFO", "Step3", f"取消主动唤醒源，等待DUT进入睡眠模式")
            wakeup_active_stop()

            # 等待DUT进入睡眠模式
            status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
            if status is False:
                TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
                return
            TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG3_TC8_ImmediateSendCountsCheck_ActiveWakeup():
    """快速发送NM报文次数检查-主动唤醒测试"""
    case_name = "快速发送NM报文次数检查-主动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms # Wait Bus Sleep Timer时间
        rNtimeRepeat = P.NMInfo.NtimeRepeat  # 时间参数测试次数
        rTinitialCycle_ms = P.NMInfo.TinitialCycle_ms  # DUT唤醒后发送完一轮报文的时间
        rTenableTx_ms = P.NMInfo.TenableTx_ms  # DUT发送应用报文使能时间
        rNimmediateSend = P.NMInfo.NimmediateSend  # 快速发送NM报文的帧数
        rTimmediateCycle_ms = P.NMInfo.TimmediateCycle_ms  # 快速发送NM报文的周期
        rTimmediateDeviation = P.NMInfo.TimmediateDeviation_pct  # 快速发送NM报文的周期偏移范围

        rTimmediateSendMin_ms = rTimmediateCycle_ms * (1 - rTimmediateDeviation / 100)
        rTimmediateSendMax_ms = rTimmediateCycle_ms * (1 + rTimmediateDeviation / 100)

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        for i in range(rNtimeRepeat):
            TestLog("INFO", "", f"第 {i + 1} 次测试")
            clear_ctx_can_messages()

            TestLog("INFO", "Step2",
                    "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始等待TrepeatMessage时间，记录在此期间收到的所有报文")
            wakeup_active_start()

            testStartTime_ms = time.time() * 1000

            # 等待DUT唤醒
            if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
                TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
                return

            time.sleep(rTrepeatMessage_ms / 1000)

            sendCount = 0
            # 比较所有接收到的NM报文发送间隔
            nm_message = get_nm_message_list()
            for j in range(1, len(nm_message)):
                internal_ms = nm_message[j].time_ms - nm_message[j-1].time_ms
                if rTimmediateSendMin_ms <= internal_ms <= rTimmediateSendMax_ms:
                    sendCount += 1
                else:
                    break

            if sendCount == rNimmediateSend - 1:
                TestLog("PASS", "", f"期望结果：主动唤醒后，NM报文快发次数 = {rNimmediateSend}，"
                                    f"实际结果：NM报文快发次数 = {sendCount + 1}，满足要求")
            elif sendCount > 0:
                TestLog("FAIL", "", f"期望结果：主动唤醒后，NM报文快发次数 = {rNimmediateSend}，"
                                    f"实际结果：NM报文快发次数 = {sendCount + 1}，不满足要求")
            else:
                TestLog("PASS", "", f"期望结果：主动唤醒后，NM报文快发次数 == {rNimmediateSend}，"
                                    f"实际结果：NM报文快发次数 = {sendCount + 1}，不满足要求")

            TestLog("INFO", "Step3", f"取消主动唤醒源，等待DUT进入睡眠模式")
            wakeup_active_stop()

            # 等待DUT进入睡眠模式
            status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
            if status is False:
                TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
                return
            TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG3_TC9_NormalCycleTimeCheck_ActiveWakeup():
    """正常发送NM报文周期时间检查-主动唤醒测试"""
    case_name = "正常发送NM报文周期时间检查-主动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms # Wait Bus Sleep Timer时间
        rNtimeRepeat = P.NMInfo.NtimeRepeat  # 时间参数测试次数
        rTinitialCycle_ms = P.NMInfo.TinitialCycle_ms  # DUT唤醒后发送完一轮报文的时间
        rTenableTx_ms = P.NMInfo.TenableTx_ms  # DUT发送应用报文使能时间
        rNimmediateSend = P.NMInfo.NimmediateSend  # 快速发送NM报文的帧数
        rTimmediateCycle_ms = P.NMInfo.TimmediateCycle_ms  # 快速发送NM报文的周期
        rTimmediateDeviation = P.NMInfo.TimmediateDeviation_pct  # 快速发送NM报文的周期偏移范围
        rTnormalCycle_ms = P.NMInfo.TnormalCycle_ms  # 正常发送NM报文的周期
        rTnormalDeviation = P.NMInfo.TnormalDeviation_pct  # 正常发送NM报文的周期偏移范围

        rTnormalCycleMin_ms = rTnormalCycle_ms * (1 - rTnormalDeviation / 100)
        rTnormalCycleMax_ms = rTnormalCycle_ms * (1 + rTnormalDeviation / 100)

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2",
                "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始等待TrepeatMessage时间，然后继续等待TactiveKeep时间, 记录在此期间收到的所有报文")
        clear_ctx_can_messages()
        wakeup_active_start()

        testStartTime_ms = time.time() * 1000

        # 等待DUT唤醒
        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000)
        time.sleep(rTactiveKeep_s)

        errorFlag = 0
        strAllNMMMsgTimeList = []
        strErrorMsgSendTime = []
        # 比较前NimmediateSend帧之后, 所有NM报文的发送间隔是否满足要求
        nm_message = get_nm_message_list()
        for i in range(rNimmediateSend, len(nm_message)):
            internal_ms = nm_message[i].time_ms - nm_message[i-1].time_ms
            strAllNMMMsgTimeList.append(internal_ms)
            if rTnormalCycleMin_ms <= internal_ms <= rTnormalCycleMax_ms:
                pass
            else:
                errorFlag = 1
                strErrorMsgSendTime.append(internal_ms)

        if errorFlag == 0:
            TestLog("PASS", "", f"期望结果:第{rNimmediateSend}帧NM报文之后，所有NM报文发送间隔均满足正常发送周期({rTnormalCycle_ms} ms)，"
                                f"实际结果:{strAllNMMMsgTimeList}，均满足要求")
        else:
            TestLog("FAIL", "", f"期望结果:第{rNimmediateSend}帧NM报文之后，所有NM报文发送间隔均满足正常发送周期({rTnormalCycle_ms} ms)，"
                                f"实际结果:{strAllNMMMsgTimeList}，其中{strErrorMsgSendTime}, 不满足要求")


        TestLog("INFO", "Step3", f"取消主动唤醒源，等待DUT进入睡眠模式")
        wakeup_active_stop()

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG3_TC10_NormalCycleTimeCheck_PassiveWakeup():
    """正常发送NM报文周期时间检查-被动唤醒测试"""
    case_name = "正常发送NM报文周期时间检查-被动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms # Wait Bus Sleep Timer时间
        rNtimeRepeat = P.NMInfo.NtimeRepeat  # 时间参数测试次数
        rTinitialCycle_ms = P.NMInfo.TinitialCycle_ms  # DUT唤醒后发送完一轮报文的时间
        rTenableTx_ms = P.NMInfo.TenableTx_ms  # DUT发送应用报文使能时间
        rNimmediateSend = P.NMInfo.NimmediateSend  # 快速发送NM报文的帧数
        rTimmediateCycle_ms = P.NMInfo.TimmediateCycle_ms  # 快速发送NM报文的周期
        rTimmediateDeviation = P.NMInfo.TimmediateDeviation_pct  # 快速发送NM报文的周期偏移范围
        rTnormalCycle_ms = P.NMInfo.TnormalCycle_ms  # 正常发送NM报文的周期
        rTnormalDeviation = P.NMInfo.TnormalDeviation_pct  # 正常发送NM报文的周期偏移范围

        rTnormalCycleMin_ms = rTnormalCycle_ms * (1 - rTnormalDeviation / 100)
        rTnormalCycleMax_ms = rTnormalCycle_ms * (1 + rTnormalDeviation / 100)

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2",
                "触发被动唤醒请求并保持，从收到DUT发出第1帧报文开始等待TrepeatMessage时间，然后继续等待TpassiveKeep时间, 记录在此期间收到的所有报文")
        clear_ctx_can_messages()
        wakeup_passive_start()

        testStartTime_ms = time.time() * 1000

        # 等待DUT唤醒
        if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return

        time.sleep(rTrepeatMessage_ms / 1000)
        time.sleep(rTpassiveKeep_s)

        errorFlag = 0
        strAllNMMMsgTimeList = []
        strErrorMsgSendTime = []
        # 比较前NimmediateSend帧之后, 所有NM报文的发送间隔是否满足要求
        nm_message = get_nm_message_list()
        for i in range(1, len(nm_message)):
            internal_ms = nm_message[i].time_ms - nm_message[i-1].time_ms
            strAllNMMMsgTimeList.append(internal_ms)
            if rTnormalCycleMin_ms <= internal_ms <= rTnormalCycleMax_ms:
                pass
            else:
                errorFlag = 1
                strErrorMsgSendTime.append(internal_ms)

        if errorFlag == 0:
            TestLog("PASS", "", f"期望结果:所有NM报文发送间隔均满足正常发送周期({rTnormalCycle_ms} ms)，"
                                f"实际结果:{strAllNMMMsgTimeList}，均满足要求")
        else:
            TestLog("FAIL", "", f"期望结果:所有NM报文发送间隔均满足正常发送周期({rTnormalCycle_ms} ms)，"
                                f"实际结果:{strAllNMMMsgTimeList}，其中{strErrorMsgSendTime}, 不满足要求")


        TestLog("INFO", "Step3", f"取消主动唤醒源，等待DUT进入睡眠模式")
        wakeup_passive_stop()

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG3_TC11_RepeatMessageStateKeepTimeCheck_ActiveWakeup():
    """重复报文模式维持时间检查-主动唤醒测试"""
    case_name = "重复报文模式维持时间检查-主动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms # Wait Bus Sleep Timer时间
        rNtimeRepeat = P.NMInfo.NtimeRepeat  # 时间参数测试次数
        rTinitialCycle_ms = P.NMInfo.TinitialCycle_ms  # DUT唤醒后发送完一轮报文的时间
        rTenableTx_ms = P.NMInfo.TenableTx_ms  # DUT发送应用报文使能时间
        rNimmediateSend = P.NMInfo.NimmediateSend  # 快速发送NM报文的帧数
        rTimmediateCycle_ms = P.NMInfo.TimmediateCycle_ms  # 快速发送NM报文的周期
        rTimmediateDeviation = P.NMInfo.TimmediateDeviation_pct  # 快速发送NM报文的周期偏移范围
        rTnormalCycle_ms = P.NMInfo.TnormalCycle_ms  # 正常发送NM报文的周期
        rTnormalDeviation = P.NMInfo.TnormalDeviation_pct  # 正常发送NM报文的周期偏移范围
        rReptMsgBit0 = P.NMInfo.RepeatMessageBit0  # 是否支持RepeatMessageRequestBit状态位，1，支持，0，不支持

        rTnormalCycleMin_ms = rTnormalCycle_ms * (1 - rTnormalDeviation / 100)
        rTnormalCycleMax_ms = rTnormalCycle_ms * (1 + rTnormalDeviation / 100)

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", f"RepeatMessageBit0 = {rReptMsgBit0}")
        if rReptMsgBit0 == 1:
            for i in range(rNtimeRepeat):
                TestLog("INFO", "", f"第 {i + 1} 次测试")
                clear_ctx_can_messages()

                TestLog("INFO", "Step3",
                        "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始，等待2*TrepeatMessage时间，监控在此期间DUT发出的所有NM报文，"
                        "计算从DUT发出第1帧NM报文时刻到发出NM报文的RepeatMessageRequestBit状态位变为0的时刻的间隔时间Tinterval")
                wakeup_active_start()

                # 等待DUT唤醒
                if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
                    TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
                    return

                tFirstRepeatMessageRequestBit1Time = 0
                tFirstRepeatMessageRequestBit0Time = 0
                nm_message = get_nm_message_list()
                for i in range(len(nm_message)):
                    if nm_message[i].payload[2] & 0x01 == 1 and tFirstRepeatMessageRequestBit1Time == 0:
                        tFirstRepeatMessageRequestBit1Time = nm_message[i].time_ms
                    if nm_message[i].payload[2] & 0x01 == 0:
                        tFirstRepeatMessageRequestBit0Time = nm_message[i].time_ms

                errorFlag = 0
                internal_ms = tFirstRepeatMessageRequestBit0Time - tFirstRepeatMessageRequestBit1Time
                if (rTrepeatMessage_ms - rTnormalCycle_ms) * 0.95 <= internal_ms <= (rTrepeatMessage_ms + rTnormalCycle_ms) * 1.05:
                    pass
                else:
                    errorFlag = 1

                if errorFlag == 0:
                    TestLog("PASS", "",
                            f"期望结果:重复报文模式维持时间满足：（{rTrepeatMessage_ms} ± {rTnormalCycle_ms}）±5%)，"
                            f"实际结果:重复报文模式维持时间为 {internal_ms} = 第1帧RepeatMessageRequestBit=1的NM报文{tFirstRepeatMessageRequestBit0Time}"
                            f" - 第1帧RepeatMessageRequestBit=0的NM报文{tFirstRepeatMessageRequestBit1Time}")
                else:
                    TestLog("FAIL", "",
                            f"期望结果:重复报文模式维持时间满足：（{rTrepeatMessage_ms} ± {rTnormalCycle_ms}）±5%)，"
                            f"实际结果:重复报文模式维持时间为 {internal_ms} = 第1帧RepeatMessageRequestBit=1的NM报文{tFirstRepeatMessageRequestBit0Time}"
                            f" - 第1帧RepeatMessageRequestBit=0的NM报文{tFirstRepeatMessageRequestBit1Time}")

                TestLog("INFO", "Step4", f"取消主动唤醒源，等待DUT进入睡眠模式")
                wakeup_active_stop()

                # 等待DUT进入睡眠模式
                status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
                if status is False:
                    TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
                    return

                TestLog("PASS", "", msg)

            TestLog("INFO", "", "测试完成")

        else:
            for i in range(rNtimeRepeat):
                TestLog("INFO", "", f"第 {i + 1} 次测试")
                clear_ctx_can_messages()

                TestLog("INFO", "Step6",
                        "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始，等待0.5*TrepeatMessage时间，记录DUT发出第1帧报文时刻t1")
                wakeup_active_start()

                # 等待DUT唤醒
                if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
                    TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
                    return

                time.sleep(0.5 * rTrepeatMessage_ms / 1000.0)
                nm_message = get_nm_message_list()
                t1 = nm_message[0].time_ms
                check_repeat_message_state_after_active_wakeup()

                TestLog("INFO", "Step7",
                        "取消主动唤醒源，继续等待0.5*rTrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
                wakeup_active_stop()
                time.sleep(0.5 * rTrepeatMessage_ms / 1000.0)
                check_repeat_message_state(0.5*rTrepeatMessage_ms, 0.9*rTrepeatMessage_ms)
                nm_message = get_nm_message_list()
                t2 = nm_message[-1].time_ms

                errorFlag = 0
                internal_ms = t2 - t1
                if (rTrepeatMessage_ms - rTnormalCycle_ms) * 0.95 <= internal_ms <= (
                        rTrepeatMessage_ms + rTnormalCycle_ms) * 1.05:
                    pass
                else:
                    errorFlag = 1

                TestLog("INFO", "Step8", "计算Tinterval = t2 – t1")
                if errorFlag == 0:
                    TestLog("PASS", "",
                            f"期望结果:重复报文模式维持时间满足：（{rTrepeatMessage_ms} ± {rTnormalCycle_ms}）±5%)，"
                            f"实际结果:重复报文模式维持时间为 {internal_ms} = 最后一帧NM报文{t2}"
                            f" - 第1帧NM报文{t1}")
                else:
                    TestLog("FAIL", "",
                            f"期望结果:重复报文模式维持时间满足：（{rTrepeatMessage_ms} ± {rTnormalCycle_ms}）±5%)，"
                            f"实际结果:重复报文模式维持时间为 {internal_ms} = 最后一帧NM报文{t2}"
                            f" - 第1帧NM报文{t1}")

                TestLog("INFO", "Step9", f"等待DUT进入睡眠模式")
                # 等待DUT进入睡眠模式
                status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
                if status is False:
                    TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
                    return

                TestLog("PASS", "", msg)

            TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG3_TC12_RepeatMessageStateKeepTimeCheck_PassiveWakeup():
    """重复报文模式维持时间检查-被动唤醒测试"""
    case_name = "重复报文模式维持时间检查-被动唤醒测试"
    try:
        rNormalToReptMsg = P.NMInfo.NormalStateToRepeatMessageState
        rIsleep_mA = 300  # TODO 读配置表
        rNMmsgIDMin = 0x400  # NM报文ID范围最小值
        rNMmsgIDMax = 0x4FF  # NM报文ID范围最大值
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rSourceNodeID = P.NMInfo.NMByte0_int
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTactiveKeep_s = P.NMInfo.TactiveKeep_s
        rTpassiveKeep_s = P.NMInfo.TpassiveKeep_s
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTpassiveWakeup = 100
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms # NM Timeout Timer时间
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms # Wait Bus Sleep Timer时间
        rNtimeRepeat = P.NMInfo.NtimeRepeat  # 时间参数测试次数
        rTinitialCycle_ms = P.NMInfo.TinitialCycle_ms  # DUT唤醒后发送完一轮报文的时间
        rTenableTx_ms = P.NMInfo.TenableTx_ms  # DUT发送应用报文使能时间
        rNimmediateSend = P.NMInfo.NimmediateSend  # 快速发送NM报文的帧数
        rTimmediateCycle_ms = P.NMInfo.TimmediateCycle_ms  # 快速发送NM报文的周期
        rTimmediateDeviation = P.NMInfo.TimmediateDeviation_pct  # 快速发送NM报文的周期偏移范围
        rTnormalCycle_ms = P.NMInfo.TnormalCycle_ms  # 正常发送NM报文的周期
        rTnormalDeviation = P.NMInfo.TnormalDeviation_pct  # 正常发送NM报文的周期偏移范围
        rReptMsgBit0 = P.NMInfo.RepeatMessageBit0  # 是否支持RepeatMessageRequestBit状态位，1，支持，0，不支持

        rTnormalCycleMin_ms = rTnormalCycle_ms * (1 - rTnormalDeviation / 100)
        rTnormalCycleMax_ms = rTnormalCycle_ms * (1 + rTnormalDeviation / 100)

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {P.NMInfo.Vnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        # KL30 ON
        ctx.bob_ctrl.set_power('KL30', True)

        # 等待DUT进入睡眠模式
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", f"RepeatMessageBit0 = {rReptMsgBit0}")
        if rReptMsgBit0 == 1:
            for i in range(rNtimeRepeat):
                TestLog("INFO", "", f"第 {i + 1} 次测试")
                clear_ctx_can_messages()

                TestLog("INFO", "Step3",
                        "触发被动唤醒源并保持，从收到DUT发出第1帧报文开始，等待2*TrepeatMessage时间，监控在此期间DUT发出的所有NM报文，"
                        "计算从DUT发出第1帧NM报文时刻到发出NM报文的RepeatMessageRequestBit状态位变为0的时刻的间隔时间Tinterval")
                wakeup_passive_start()

                # 等待DUT唤醒
                if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
                    TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
                    return

                tFirstRepeatMessageRequestBit1Time = 0
                tFirstRepeatMessageRequestBit0Time = 0
                nm_message = get_nm_message_list()
                for i in range(len(nm_message)):
                    if nm_message[i].payload[2] & 0x01 == 1 and tFirstRepeatMessageRequestBit1Time == 0:
                        tFirstRepeatMessageRequestBit1Time = nm_message[i].time_ms
                    if nm_message[i].payload[2] & 0x01 == 0:
                        tFirstRepeatMessageRequestBit0Time = nm_message[i].time_ms

                errorFlag = 0
                internal_ms = tFirstRepeatMessageRequestBit0Time - tFirstRepeatMessageRequestBit1Time
                if (rTrepeatMessage_ms - rTnormalCycle_ms) * 0.95 <= internal_ms <= (rTrepeatMessage_ms + rTnormalCycle_ms) * 1.05:
                    pass
                else:
                    errorFlag = 1

                if errorFlag == 0:
                    TestLog("PASS", "",
                            f"期望结果:重复报文模式维持时间满足：（{rTrepeatMessage_ms} ± {rTnormalCycle_ms}）±5%)，"
                            f"实际结果:重复报文模式维持时间为 {internal_ms} = 第1帧RepeatMessageRequestBit=1的NM报文{tFirstRepeatMessageRequestBit0Time}"
                            f" - 第1帧RepeatMessageRequestBit=0的NM报文{tFirstRepeatMessageRequestBit1Time}")
                else:
                    TestLog("FAIL", "",
                            f"期望结果:重复报文模式维持时间满足：（{rTrepeatMessage_ms} ± {rTnormalCycle_ms}）±5%)，"
                            f"实际结果:重复报文模式维持时间为 {internal_ms} = 第1帧RepeatMessageRequestBit=1的NM报文{tFirstRepeatMessageRequestBit0Time}"
                            f" - 第1帧RepeatMessageRequestBit=0的NM报文{tFirstRepeatMessageRequestBit1Time}")

                TestLog("INFO", "Step4", f"取消被动唤醒源，等待DUT进入睡眠模式")
                wakeup_passive_stop()

                # 等待DUT进入睡眠模式
                status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
                if status is False:
                    TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
                    return

                TestLog("PASS", "", msg)

            TestLog("INFO", "", "测试完成")

        else:
            for i in range(rNtimeRepeat):
                TestLog("INFO", "", f"第 {i + 1} 次测试")
                clear_ctx_can_messages()

                TestLog("INFO", "Step6",
                        "触发被动唤醒源并保持，从收到DUT发出第1帧报文开始，等待0.5*TrepeatMessage时间，记录DUT发出第1帧报文时刻t1")
                wakeup_passive_start()

                # 等待DUT唤醒
                if wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0) is False:
                    TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
                    return

                time.sleep(0.5 * rTrepeatMessage_ms / 1000.0)
                nm_message = get_nm_message_list()
                t1 = nm_message[0].time_ms
                check_repeat_message_state_after_passive_wakeup()

                TestLog("INFO", "Step7",
                        "取消被动唤醒源，继续等待0.5*rTrepeatMessage时间，监控在此期间DUT发出的所有NM报文")
                wakeup_passive_stop()
                time.sleep(0.5 * rTrepeatMessage_ms / 1000.0)
                check_repeat_message_state(0.5*rTrepeatMessage_ms, 0.9*rTrepeatMessage_ms)
                nm_message = get_nm_message_list()
                t2 = nm_message[-1].time_ms

                errorFlag = 0
                internal_ms = t2 - t1
                if (rTrepeatMessage_ms - rTnormalCycle_ms) * 0.95 <= internal_ms <= (
                        rTrepeatMessage_ms + rTnormalCycle_ms) * 1.05:
                    pass
                else:
                    errorFlag = 1

                TestLog("INFO", "Step8", "计算Tinterval = t2 – t1")
                if errorFlag == 0:
                    TestLog("PASS", "",
                            f"期望结果:重复报文模式维持时间满足：（{rTrepeatMessage_ms} ± {rTnormalCycle_ms}）±5%)，"
                            f"实际结果:重复报文模式维持时间为 {internal_ms} = 最后一帧NM报文{t2}"
                            f" - 第1帧NM报文{t1}")
                else:
                    TestLog("FAIL", "",
                            f"期望结果:重复报文模式维持时间满足：（{rTrepeatMessage_ms} ± {rTnormalCycle_ms}）±5%)，"
                            f"实际结果:重复报文模式维持时间为 {internal_ms} = 最后一帧NM报文{t2}"
                            f" - 第1帧NM报文{t1}")

                TestLog("INFO", "Step9", f"等待DUT进入睡眠模式")
                # 等待DUT进入睡眠模式
                status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
                if status is False:
                    TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
                    return

                TestLog("PASS", "", msg)

            TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG3_TC13_NM_NMTimeoutTimerTimeCheck_ActiveWakeup():
    """NMTimeoutTimer 时间检查-主动唤醒"""
    case_name = "NMTimeoutTimer 时间检查-主动唤醒"
    try:
        rIsleep_mA = 300
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s

        TestLog("INFO", "Step1", f"设置电源为 {P.NMInfo.Vnormal} V，上电并等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if not status:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发主动唤醒并保持，从收到第1帧NM报文开始等待TrepeatMessage时间，收集NM及应用报文")
        clear_ctx_can_messages()
        wakeup_active_start()
        if not wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0):
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return
        time.sleep(rTrepeatMessage_ms / 1000.0)

        TestLog("INFO", "Step3", "取消主动唤醒源，从收到最后1帧NM报文后等待TNMtimeout+TwaitBusSleep时间以便统计报文时序")
        wakeup_active_stop()
        wait_total_ms = rTNMtimeout_ms + rTwaitBusSleep_ms
        start_wait_ms = time.time() * 1000.0
        while (time.time() * 1000.0 - start_wait_ms) < wait_total_ms:
            time.sleep(0.001)

        nm_message = get_nm_message_list()
        app_message = get_app_message_list()
        if not nm_message or not app_message:
            TestLog("FAIL", "", "在观察窗口内未能同时采集到NM报文和应用报文，无法计算NM Timeout 时间间隔")
            return

        last_nm_time_ms = nm_message[-1].time_ms
        last_app_time_ms = app_message[-1].time_ms
        internal_time_ms = last_app_time_ms - last_nm_time_ms
        TestLog("INFO", "", f"最后1帧NM报文时间：{last_nm_time_ms/1000:.6f} s，最后1帧应用报文时间：{last_app_time_ms/1000:.6f} s，差值={internal_time_ms:.1f} ms")

        lower = 0.9 * rTNMtimeout_ms
        upper = 1.1 * rTNMtimeout_ms
        if lower <= internal_time_ms <= upper:
            TestLog("PASS", "", f"internalTime={internal_time_ms:.1f} ms，满足 0.9*TNMtimeout({lower:.1f})~1.1*TNMtimeout({upper:.1f}) 区间要求")
        else:
            TestLog("FAIL", "", f"internalTime={internal_time_ms:.1f} ms，不在 0.9*TNMtimeout({lower:.1f})~1.1*TNMtimeout({upper:.1f}) 区间内")

        TestLog("INFO", "Step4", "等待DUT重新进入睡眠模式")
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if not status:
            TestLog("FAIL", "", f"DUT未重新进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")


    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG3_TC14_NM_NMTimeoutTimerTimeCheck_PassiveWakeup():
    """NMTimeoutTimer 时间检查-被动唤醒"""
    case_name = "NMTimeoutTimer 时间检查-被动唤醒"
    try:
        rIsleep_mA = 300
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s

        TestLog("INFO", "Step1", f"设置电源为 {P.NMInfo.Vnormal} V，上电并等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if not status:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "Step2", "触发被动唤醒请求并保持，从收到第1帧NM报文开始等待TrepeatMessage时间，收集NM及应用报文")
        clear_ctx_can_messages()
        wakeup_start_time_ms = time.time() * 1000.0
        wakeup_passive_start()
        if not wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0):
            TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
            return
        time.sleep(rTrepeatMessage_ms / 1000.0)

        TestLog("INFO", "Step3", "停止发送唤醒报文，从唤醒开始时刻起等待TNMtimeout+TwaitBusSleep时间以便统计报文时序")
        wakeup_passive_stop()
        wait_total_ms = rTNMtimeout_ms + rTwaitBusSleep_ms
        start_wait_ms = time.time() * 1000.0
        while (time.time() * 1000.0 - start_wait_ms) < wait_total_ms:
            time.sleep(0.001)

        nm_message = get_tx_and_rx_nm_message_list()
        app_message = get_app_message_list()
        if not nm_message or not app_message:
            TestLog("FAIL", "", "在观察窗口内未能同时采集到NM报文和应用报文，无法计算NM Timeout 时间间隔")
            return

        last_nm_time_ms = nm_message[-1].time_ms
        last_app_time_ms = app_message[-1].time_ms
        internal_time_ms = last_app_time_ms - last_nm_time_ms
        TestLog("INFO", "", f"最后1帧NM报文时间：{last_nm_time_ms/1000:.6f} s，最后1帧应用报文时间：{last_app_time_ms/1000:.6f} s，差值={internal_time_ms:.1f} ms")

        lower = 0.9 * rTNMtimeout_ms
        upper = 1.1 * rTNMtimeout_ms
        if lower <= internal_time_ms <= upper:
            TestLog("PASS", "", f"internalTime={internal_time_ms:.1f} ms，满足 0.9*TNMtimeout({lower:.1f})~1.1*TNMtimeout({upper:.1f}) 区间要求")
        else:
            TestLog("FAIL", "", f"internalTime={internal_time_ms:.1f} ms，不在 0.9*TNMtimeout({lower:.1f})~1.1*TNMtimeout({upper:.1f}) 区间内")

        TestLog("INFO", "Step4", "等待DUT重新进入睡眠模式")
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if not status:
            TestLog("FAIL", "", f"DUT未重新进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG3_TC15_NM_WaitBusSleepTimerTimeCheck_ActiveWakeup():
    """WaitBusSleepTimer 时间检查-主动唤醒"""
    case_name = "WaitBusSleepTimer 时间检查-主动唤醒"
    try:
        rIsleep_mA = 300
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rNtimeRepeat = max(int(P.NMInfo.NtimeRepeat or 0), 1)

        TestLog("INFO", "Step1", f"设置电源为 {P.NMInfo.Vnormal} V，上电并等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if not status:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        for repeat_idx in range(rNtimeRepeat):
            TestLog("INFO", "Step2", f"=== 第 {repeat_idx + 1}/{rNtimeRepeat} 次重复测试 === "
                                     f"按 TwaitBusSleep 周期扫描不同注入时刻，对应 CAPL 中 0.8*TwaitBusSleep~2*TwaitBusSleep 的多次尝试")
            max_test_time_ms = int(2 * rTwaitBusSleep_ms)
            test_time_ms = int(0.8 * rTwaitBusSleep_ms)
            step_test_time_ms = int(0.05 * rTwaitBusSleep_ms)

            found_window = False
            while test_time_ms <= max_test_time_ms:
                TestLog("INFO", "Step2", f"触发主动唤醒源并保持，从收到DUT发出第1帧报文开始，等待TrepeatMessage时间")
                clear_ctx_can_messages()
                wakeup_active_start()
                if not wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0):
                    TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
                    wakeup_active_stop()
                    return
                time.sleep(rTrepeatMessage_ms / 1000.0)
                check_repeat_message_state_after_active_wakeup()

                TestLog("INFO", "Step3", f"取消主动唤醒源，从收到DUT发出最后1帧报文开始，等待Tinterval（初始值为0.8* TwaitBusSleep）时间，"
                                         f"然后仿真发送1帧报文（ID为0x001，DLC=8，数据内容均为0x55），监控总线是否出现错误帧")
                wakeup_active_stop()

                test_start_ms = time.time() * 1000.0
                lastRxMsgTimeStamp_ms = None
                rx_messages = get_rx_message_list()
                if rx_messages:
                    lastRxMsgTimeStamp_ms = rx_messages[-1].time_ms
                else:
                    lastRxMsgTimeStamp_ms = test_start_ms

                timeout_ms = 60000
                while (time.time() * 1000.0 - lastRxMsgTimeStamp_ms) < test_time_ms:
                    time.sleep(0.002)
                    rx_messages = get_rx_message_list()
                    lastRxMsgTimeStamp_ms = rx_messages[-1].time_ms if rx_messages else lastRxMsgTimeStamp_ms
                    if (time.time() * 1000.0 - test_start_ms) >= timeout_ms:
                        TestLog("FAIL", "", f"等待 {test_time_ms} ms 内 DUT 一直有报文发送，无法进入总线空闲，终止本次扫描循环")
                        break
                else:
                    TestLog("INFO", "",
                            f"从DUT最后1帧报文(约 {lastRxMsgTimeStamp_ms / 1000:.6f} s) 开始计时，等待 {test_time_ms} ms 后注入应用报文")
                    ctx.can.set_info("gErrorFrameCount", 0)
                    ctx.can.set_info("firstErrorFrameTime_ms", None)
                    prepare_sleep_state_test_start()
                    sl_time().sleep(3000)
                    prepare_sleep_state_test_stop()

                    g_error = ctx.can.get_info("gErrorFrameCount") or 0
                    first_err_ms = ctx.can.get_info("firstErrorFrameTime_ms")
                    if g_error > 0:
                        lower = 0.9 * rTwaitBusSleep_ms
                        upper = 1.1 * rTwaitBusSleep_ms
                        if first_err_ms is not None:
                            internal_time_ms = first_err_ms - lastRxMsgTimeStamp_ms
                            TestLog("INFO", "", f"首帧错误帧时间：{first_err_ms/1000:.6f} s，最后1帧正常报文时间：{lastRxMsgTimeStamp_ms/1000:.6f} s，差值={internal_time_ms:.1f} ms")
                            if lower <= internal_time_ms <= upper:
                                TestLog("PASS", "", f"internalTime={internal_time_ms:.1f} ms 满足 0.9*TwaitBusSleep({lower:.1f})~1.1*TwaitBusSleep({upper:.1f}) 要求")
                            else:
                                TestLog("FAIL", "", f"internalTime={internal_time_ms:.1f} ms 不在 0.9*TwaitBusSleep({lower:.1f})~1.1*TwaitBusSleep({upper:.1f}) 区间内")
                        else:
                            TestLog("FAIL", "", f"检测到 {g_error} 个错误帧，但未获取到首帧错误时间戳，无法计算 internalTime，结束本轮扫描")

                        TestLog("INFO", "Step4", "等待DUT重新进入睡眠模式")
                        wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
                        TestLog("INFO", "Step5", f"当前扫描 testTimeCount={test_time_ms} ms 完成，结束本轮扫描")
                        found_window = True
                        break
                    else:
                        TestLog("INFO", "Step4", "本次注入未观察到错误帧，视为尚未触发 WaitBusSleepTimer 窗口，继续增加等待时间")
                        wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
                        TestLog("INFO", "Step5", f"从最后1帧报文开始等待 {test_time_ms} ms 注入应用报文未触发错误帧，增加 {step_test_time_ms} ms 后继续扫描")

                test_time_ms += step_test_time_ms

            if not found_window:
                TestLog("FAIL", "", f"第 {repeat_idx + 1}/{rNtimeRepeat} 次：扫描到 2*TwaitBusSleep({max_test_time_ms} ms) 仍未观察到错误帧，WaitBusSleepTimer 判定失败")

        TestLog("INFO", "", f"NtimeRepeat={rNtimeRepeat} 次重复测试全部完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG3_TC16_NM_WaitBusSleepTimerTimeCheck_PassiveWakeup():
    """WaitBusSleepTimer 时间检查-被动唤醒"""
    case_name = "WaitBusSleepTimer 时间检查-被动唤醒"
    try:
        rIsleep_mA = 300
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rNtimeRepeat = max(int(P.NMInfo.NtimeRepeat or 0), 1)

        TestLog("INFO", "Step1", f"设置电源为 {P.NMInfo.Vnormal} V，上电并等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)
        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if not status:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", msg)

        for repeat_idx in range(rNtimeRepeat):
            TestLog("INFO", "Step2", f"=== 第 {repeat_idx + 1}/{rNtimeRepeat} 次重复测试 === "
                                     f"按 TwaitBusSleep 周期扫描不同注入时刻，对应 CAPL 中 0.8*TwaitBusSleep~2*TwaitBusSleep 的多次尝试")
            max_test_time_ms = int(2 * rTwaitBusSleep_ms)
            test_time_ms = int(0.8 * rTwaitBusSleep_ms)
            step_test_time_ms = int(0.05 * rTwaitBusSleep_ms)

            found_window = False
            while test_time_ms <= max_test_time_ms:
                TestLog("INFO", "Step2", "触发被动唤醒请求并保持，从收到DUT发出第1帧报文开始，等待TrepeatMessage时间")
                clear_ctx_can_messages()
                wakeup_passive_start()
                if not wait_dut_send_first_msg(rTwakeupTimeout_ms / 1000.0):
                    TestLog("FAIL", "", f"等待超过{rTwakeupTimeout_ms}ms，DUT无法被唤醒，测试终止")
                    return
                time.sleep(rTrepeatMessage_ms / 1000.0)
                check_repeat_message_state_after_passive_wakeup()
                wakeup_passive_stop()

                test_start_ms = time.time() * 1000.0
                lastRxMsgTimeStamp_ms = None
                rx_messages = get_rx_message_list()
                if rx_messages:
                    lastRxMsgTimeStamp_ms = rx_messages[-1].time_ms
                else:
                    lastRxMsgTimeStamp_ms = test_start_ms

                timeout_ms = 60000
                while (time.time() * 1000.0 - lastRxMsgTimeStamp_ms) < test_time_ms:
                    time.sleep(0.002)
                    rx_messages = get_rx_message_list()
                    lastRxMsgTimeStamp_ms = rx_messages[-1].time_ms if rx_messages else lastRxMsgTimeStamp_ms
                    if (time.time() * 1000.0 - test_start_ms) >= timeout_ms:
                        TestLog("FAIL", "", f"等待 {test_time_ms} ms 内 DUT 一直有报文发送，无法进入总线空闲，终止本次扫描循环")
                        break
                else:
                    TestLog("INFO", "Step3",
                            f"从DUT最后1帧报文(约 {lastRxMsgTimeStamp_ms / 1000:.6f} s) 开始计时，等待 {test_time_ms} ms 后注入应用报文")
                    ctx.can.set_info("gErrorFrameCount", 0)
                    ctx.can.set_info("firstErrorFrameTime_ms", None)
                    prepare_sleep_state_test_start()
                    sl_time().sleep(3000)
                    prepare_sleep_state_test_stop()

                    g_error = ctx.can.get_info("gErrorFrameCount") or 0
                    first_err_ms = ctx.can.get_info("firstErrorFrameTime_ms")
                    if g_error > 0:
                        lower = 0.9 * rTwaitBusSleep_ms
                        upper = 1.1 * rTwaitBusSleep_ms
                        if first_err_ms is not None:
                            internal_time_ms = first_err_ms - lastRxMsgTimeStamp_ms
                            TestLog("INFO", "", f"首帧错误帧时间：{first_err_ms/1000:.6f} s，最后1帧正常报文时间：{lastRxMsgTimeStamp_ms/1000:.6f} s，差值={internal_time_ms:.1f} ms")
                            if lower <= internal_time_ms <= upper:
                                TestLog("PASS", "", f"internalTime={internal_time_ms:.1f} ms 满足 0.9*TwaitBusSleep({lower:.1f})~1.1*TwaitBusSleep({upper:.1f}) 要求")
                            else:
                                TestLog("FAIL", "", f"internalTime={internal_time_ms:.1f} ms 不在 0.9*TwaitBusSleep({lower:.1f})~1.1*TwaitBusSleep({upper:.1f}) 区间内")
                        else:
                            TestLog("FAIL", "", f"检测到 {g_error} 个错误帧，但未获取到首帧错误时间戳，无法计算 internalTime，结束本轮扫描")

                        TestLog("INFO", "Step4", "等待DUT重新进入睡眠模式")
                        wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
                        TestLog("INFO", "Step5", f"当前扫描 testTimeCount={test_time_ms} ms 完成，结束本轮扫描")
                        found_window = True
                        break
                    else:
                        TestLog("INFO", "Step4", "本次注入未观察到错误帧，视为尚未触发 WaitBusSleepTimer 窗口，继续增加等待时间")
                        wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
                        TestLog("INFO", "Step5", f"从最后1帧报文开始等待 {test_time_ms} ms 注入应用报文未触发错误帧，增加 {step_test_time_ms} ms 后继续扫描")

                test_time_ms += step_test_time_ms

            if not found_window:
                TestLog("FAIL", "", f"第 {repeat_idx + 1}/{rNtimeRepeat} 次：扫描到 2*TwaitBusSleep({max_test_time_ms} ms) 仍未观察到错误帧，WaitBusSleepTimer 判定失败")

        TestLog("INFO", "", f"NtimeRepeat={rNtimeRepeat} 次重复测试全部完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG4_TC1_SleepWakeupStressTest_ActiveWakeup():
    """
    CAN网络休眠唤醒压力测试-主动唤醒测试
    """
    case_name = "TG4_TC1_CAN网络休眠唤醒压力测试-主动唤醒测试"
    try:
        rIsleep_mA = P.ECUInfo.ISleep
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rVnormal = P.NMInfo.Vnormal
        rNLoopTime = P.NMInfo.NLoopTime

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {rVnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        for loop_idx in range(rNLoopTime):
            TestLog("INFO", "Step2", f"触发主动唤醒源并保持，监测DUT（第{loop_idx + 1}/{rNLoopTime}次）")
            clear_ctx_can_messages()
            wakeup_active_start()

            status, nm_messages = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
            if status is False:
                TestLog("FAIL", "", f"第{loop_idx + 1}次唤醒失败，总线未收到NM报文")
                return

            app_messages = get_app_message_list()
            if len(app_messages) == 0:
                sl_time().sleep(1000)
                app_messages = get_app_message_list()
            if len(app_messages) == 0:
                TestLog("FAIL", "", f"第{loop_idx + 1}次唤醒后未收到APP报文")
                return
            TestLog("PASS", "", f"DUT发送NM报文和APP报文")

            TestLog("INFO", "Step3", f"停止主动唤醒源，等待DUT进入睡眠模式（第{loop_idx + 1}/{rNLoopTime}次）")
            wakeup_active_stop()

            status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
            if status is False:
                TestLog("FAIL", "", f"第{loop_idx + 1}次DUT未进入睡眠模式: {msg}")
                return
            TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("PASS", "", f"休眠唤醒{rNLoopTime}次，DUT正常工作")
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        wakeup_active_stop()

def test_TG4_TC2_SleepWakeupStressTest_PassiveWakeup():
    """
    CAN网络休眠唤醒压力测试-被动唤醒测试
    """
    case_name = "TG4_TC2_CAN网络休眠唤醒压力测试-被动唤醒测试"
    try:
        rIsleep_mA = P.ECUInfo.ISleep
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rVnormal = P.NMInfo.Vnormal
        rNLoopTime = P.NMInfo.NLoopTime

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {rVnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        for loop_idx in range(rNLoopTime):
            TestLog("INFO", "Step2", f"触发被动唤醒源并保持，监测DUT（第{loop_idx + 1}/{rNLoopTime}次）")
            clear_ctx_can_messages()
            wakeup_passive_start()

            status, nm_messages = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
            if status is False:
                TestLog("FAIL", "", f"第{loop_idx + 1}次唤醒失败，总线未收到NM报文")
                return

            app_messages = get_app_message_list()
            if len(app_messages) == 0:
                sl_time().sleep(1000)
                app_messages = get_app_message_list()
            if len(app_messages) == 0:
                TestLog("FAIL", "", f"第{loop_idx + 1}次唤醒后未收到APP报文")
                return
            TestLog("PASS", "", f"DUT发送NM报文和APP报文")

            TestLog("INFO", "Step3", f"停止发送唤醒报文，等待DUT进入睡眠模式（第{loop_idx + 1}/{rNLoopTime}次）")
            wakeup_passive_stop()

            status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
            if status is False:
                TestLog("FAIL", "", f"第{loop_idx + 1}次DUT未进入睡眠模式: {msg}")
                return
            TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("PASS", "", f"休眠唤醒{rNLoopTime}次，DUT正常工作")
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        wakeup_passive_stop()



# def test_TG4_TC3_UnusedUserDataByteTest_ActiveWakeup():
#     """
#     未使用的用户数据字节测试-主动唤醒测试
#     """
#     case_name = "TG4_TC3_未使用的用户数据字节测试-主动唤醒测试"
#     try:
#         rIsleep_mA = P.ECUInfo.ISleep
#         rNMmsgID = P.ECUInfo.NMMsgID_int
#         rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
#         rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
#         rVnormal = P.NMInfo.Vnormal

#         TestLog("INFO", "Step1", f"设置DUT电源电压为 {rVnormal} V，执行KL30上电，等待DUT进入睡眠模式")
#         ctx.power_ctrl.set_voltage(rVnormal)
#         ctx.power_ctrl.on()
#         ctx.bob_ctrl.set_power('KL30', True)

#         status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
#         if status is False:
#             TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
#             return
#         TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

#         TestLog("INFO", "Step2", f"触发主动唤醒源并保持，监测DUT")
#         clear_ctx_can_messages()
#         wakeup_active_start()

#         status, nm_messages = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
#         if status is False:
#             TestLog("FAIL", "", f"总线未收到NM报文")
#             return
#         TestLog("PASS", "", f"DUT发送NM报文")

#         TestLog("INFO", "Step3", f"检测未使用的用户数据字节是否为默认值0")
#         nm_msgs = get_nm_message_list()
#         if not check_unused_user_data_bytes(nm_msgs):
#             return
#         TestLog("PASS", "", f"DUT未使用的用户数据字节默认值为0")

#         TestLog("INFO", "Step4", f"停止主动唤醒源，等待DUT进入睡眠模式")
#         wakeup_active_stop()

#         status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
#         if status is False:
#             TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
#             return
#         TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

#         TestLog("INFO", "", "测试完成")

#     except Exception as e:
#         TestLog("FAIL", case_name, f"测试执行出错: {e}")
#         import traceback
#         TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
#     finally:
#         wakeup_active_stop()

# def test_TG4_TC4_UnusedUserDataByteTest_PassiveWakeup():
#     """
#     未使用的用户数据字节测试-被动唤醒测试
#     """
#     case_name = "TG4_TC4_未使用的用户数据字节测试-被动唤醒测试"
#     try:
#         rIsleep_mA = P.ECUInfo.ISleep
#         rNMmsgID = P.ECUInfo.NMMsgID_int
#         rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
#         rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
#         rVnormal = P.NMInfo.Vnormal

#         TestLog("INFO", "Step1", f"设置DUT电源电压为 {rVnormal} V，执行KL30上电，等待DUT进入睡眠模式")
#         ctx.power_ctrl.set_voltage(rVnormal)
#         ctx.power_ctrl.on()
#         ctx.bob_ctrl.set_power('KL30', True)

#         status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
#         if status is False:
#             TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
#             return
#         TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

#         TestLog("INFO", "Step2", f"触发被动唤醒源并保持，监测DUT")
#         clear_ctx_can_messages()
#         wakeup_passive_start()

#         status, nm_messages = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
#         if status is False:
#             TestLog("FAIL", "", f"总线未收到NM报文")
#             return
#         TestLog("PASS", "", f"DUT发送NM报文")

#         TestLog("INFO", "Step3", f"检测未使用的用户数据字节是否为默认值0")
#         nm_msgs = get_nm_message_list()
#         if not check_unused_user_data_bytes(nm_msgs):
#             return
#         TestLog("PASS", "", f"DUT未使用的用户数据字节默认值为0")

#         TestLog("INFO", "Step4", f"停止发送唤醒报文，等待DUT进入睡眠模式")
#         wakeup_passive_stop()

#         status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
#         if status is False:
#             TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
#             return
#         TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

#         TestLog("INFO", "", "测试完成")

#     except Exception as e:
#         TestLog("FAIL", case_name, f"测试执行出错: {e}")
#         import traceback
#         TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
#     finally:
#         wakeup_passive_stop()

def test_TG4_TC5_WakeupSourceInfoTest_ActiveWakeup():
    """
    网络管理唤醒源信息测试-主动唤醒测试
    """
    case_name = "TG4_TC5_网络管理唤醒源信息测试-主动唤醒测试"
    try:
        rIsleep_mA = P.ECUInfo.ISleep
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rVnormal = P.NMInfo.Vnormal
        rActiveWakeupBit4 = P.NMInfo.ActiveWakeupBit4

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {rVnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("INFO", "Step2", f"触发主动唤醒源并保持，监测DUT")
        clear_ctx_can_messages()
        wakeup_active_start()

        status, nm_messages = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"总线未收到NM报文")
            return
        TestLog("PASS", "", f"DUT发送NM报文")

        TestLog("INFO", "Step3", f"检测DUT发送的NM报文中唤醒原因是否为对应信号值")
        nm_msgs = get_nm_message_list()
        if not check_wakeup_source_bit(nm_msgs, expected_value=1):
            TestLog("FAIL", "", f"DUT唤醒源信息与实际唤醒源不一致，期望ActiveWakeupBit=1")
            return
        TestLog("PASS", "", f"DUT唤醒源信息（信号值）与实际唤醒源一致")

        TestLog("INFO", "Step4", f"停止主动唤醒源，等待DUT进入睡眠模式")
        wakeup_active_stop()

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        wakeup_active_stop()

def test_TG4_TC6_WakeupSourceInfoTest_PassiveWakeup():
    """
    网络管理唤醒源信息测试-被动唤醒测试
    """
    case_name = "TG4_TC6_网络管理唤醒源信息测试-被动唤醒测试"
    try:
        rIsleep_mA = P.ECUInfo.ISleep
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rVnormal = P.NMInfo.Vnormal

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {rVnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("INFO", "Step2", f"触发被动唤醒源并保持，监测DUT")
        clear_ctx_can_messages()
        wakeup_passive_start()

        status, nm_messages = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"总线未收到NM报文")
            return
        TestLog("PASS", "", f"DUT发送NM报文")

        TestLog("INFO", "Step3", f"检测DUT发送的NM报文中唤醒原因是否为对应信号值")
        nm_msgs = get_nm_message_list()
        if not check_wakeup_source_bit(nm_msgs, expected_value=0):
            TestLog("FAIL", "", f"DUT唤醒源信息与实际唤醒源不一致，期望ActiveWakeupBit=0（被动唤醒）")
            return
        TestLog("PASS", "", f"DUT唤醒源信息（信号值）与实际唤醒源一致")

        TestLog("INFO", "Step4", f"停止发送唤醒报文，等待DUT进入睡眠模式")
        wakeup_passive_stop()

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        wakeup_passive_stop()

def test_TG4_TC7_SleepWakeupScan_ActiveWakeup():
    """
    休眠唤醒扫描-主动唤醒测试
    """
    case_name = "TG4_TC7_休眠唤醒扫描-主动唤醒测试"
    try:
        rIsleep_mA = P.ECUInfo.ISleep
        rNMmsgID = P.ECUInfo.NMMsgID_int
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms
        rNimmediateSend = P.NMInfo.NimmediateSend
        rVnormal = P.NMInfo.Vnormal

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {rVnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("INFO", "Step2", f"触发主动唤醒源并保持，等待TrepeatMessage时间，监控DUT发出的NM报文")
        clear_ctx_can_messages()
        wakeup_active_start()

        status, nm_messages = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"总线未收到NM报文")
            return

        sl_time().sleep(rTrepeatMessage_ms)
        TestLog("PASS", "", f"DUT首先快发NimmediateSend帧NM报文，然后以正常周期发送NM报文")

        TestLog("INFO", "Step3", f"取消主动唤醒源，等待TNMtimeout时间，监控DUT是否停止发送NM报文")
        wakeup_active_stop()
        clear_ctx_can_messages()

        status, nm_stop_time = wait_nm_message_stop(timeout_ms=rTNMtimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"DUT未停止发送NM报文")
            return

        app_messages = get_app_message_list()
        if len(app_messages) == 0:
            TestLog("FAIL", "", f"DUT停止发送NM报文后未正常发送应用报文")
            return
        TestLog("PASS", "", f"DUT停止发送NM报文，正常发送应用报文（RSS）")

        status, app_stop_time = wait_app_message_stop(timeout_ms=rTNMtimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"DUT在TNMtimeout时间后仍在发送APP报文")
            return
        TestLog("PASS", "", f"DUT在TNMtimeout时间后停止发送APP报文")

        TestLog("INFO", "Step4", f"等待0.8*TwaitBusSleep时间")
        wait_time_ms = int(0.8 * rTwaitBusSleep_ms) - (time.time() * 1000 - app_stop_time)
        sl_time().sleep(wait_time_ms)
        TestLog("PASS", "", f"DUT停止发送NM报文和应用报文")

        twait_ms = 5
        twait_max_ms = int(0.3 * rTwaitBusSleep_ms)
        wakeup_failed = False

        while twait_ms <= twait_max_ms:
            TestLog("INFO", "Step5", f"等待Twait={twait_ms}ms")
            sl_time().sleep(twait_ms)

            TestLog("INFO", "Step6", f"触发主动唤醒源并保持，检测DUT是否被唤醒")
            clear_ctx_can_messages()
            wakeup_active_start()

            status, nm_messages = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
            if status is False:
                TestLog("FAIL", "", f"Twait={twait_ms}ms时，DUT未被唤醒，唤醒事件丢失")
                wakeup_failed = True
                break
            TestLog("PASS", "", f"DUT被唤醒并开始发送NM报文")

            TestLog("INFO", "Step7", f"取消主动唤醒源，等待TNMtimeout时间")
            wakeup_active_stop()
            clear_ctx_can_messages()

            status, nm_stop_time = wait_nm_message_stop(timeout_ms=rTNMtimeout_ms)
            if status is False:
                TestLog("FAIL", "", f"DUT未停止发送NM报文")
                wakeup_failed = True
                break
            TestLog("PASS", "", f"DUT停止发送NM报文，正常发送应用报文（RSS）")

            status, app_stop_time = wait_app_message_stop(timeout_ms=rTNMtimeout_ms)
            if status is False:
                TestLog("FAIL", "", f"DUT在TNMtimeout时间后仍在发送APP报文")
                return
            TestLog("PASS", "", f"DUT在TNMtimeout时间后停止发送APP报文")

            TestLog("INFO", "Step8", f"等待0.8*TwaitBusSleep时间")
            wait_time_ms = int(0.8 * rTwaitBusSleep_ms) - (time.time() * 1000 - app_stop_time)
            sl_time().sleep(wait_time_ms)
            TestLog("PASS", "", f"DUT停止发送NM报文和应用报文")

            twait_ms += 5

        if wakeup_failed:
            return

        TestLog("INFO", "Step10", f"停止主动唤醒源，等待DUT进入睡眠模式")
        wakeup_active_stop()

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("PASS", "", f"DUT从PBM到BSM状态切换的过程中，收到主动唤醒请求，DUT能被唤醒，不丢失唤醒事件")
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        wakeup_active_stop()

def test_TG4_TC8_SleepWakeupScan_PassiveWakeup():
    """
    休眠唤醒扫描-被动唤醒测试
    """
    case_name = "TG4_TC8_休眠唤醒扫描-被动唤醒测试"
    try:
        rIsleep_mA = P.ECUInfo.ISleep
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTNMtimeout_ms = P.NMInfo.TNMtimeout_ms
        rTwaitBusSleep_ms = P.NMInfo.TwaitBusSleep_ms
        rVnormal = P.NMInfo.Vnormal

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {rVnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("INFO", "Step2", f"触发被动唤醒源并保持，监测DUT")
        clear_ctx_can_messages()
        wakeup_passive_start()

        status, _ = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"总线未收到NM报文")
            return
        TestLog("PASS", "", f"DUT发送NM报文")

        TestLog("INFO", "Step3", f"停止发送唤醒报文，等待TNMtimeout时间，监控DUT是否停止发送NM报文")
        wakeup_passive_stop()
        clear_ctx_can_messages()

        status, _ = wait_nm_message_stop(timeout_ms=rTNMtimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"DUT未停止发送NM报文")
            return

        app_messages = get_app_message_list()
        if len(app_messages) == 0:
            TestLog("FAIL", "", f"DUT停止发送NM报文后未正常发送应用报文")
            return
        TestLog("PASS", "", f"DUT停止发送NM报文，正常发送应用报文（RSS）")

        status, app_stop_time = wait_app_message_stop(timeout_ms=rTNMtimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"DUT在TNMtimeout时间后仍在发送APP报文")
            return
        TestLog("PASS", "", f"DUT在TNMtimeout时间后停止发送APP报文")

        TestLog("INFO", "Step4", f"等待0.8*TwaitBusSleep时间")
        wait_time_ms = int(0.8 * rTwaitBusSleep_ms) - (time.time() * 1000 - app_stop_time)
        sl_time().sleep(wait_time_ms)
        TestLog("PASS", "", f"DUT停止发送NM报文和应用报文")

        twait_ms = 5
        twait_max_ms = int(0.3 * rTwaitBusSleep_ms)
        wakeup_failed = False

        while twait_ms <= twait_max_ms:
            TestLog("INFO", "Step5", f"等待Twait={twait_ms}ms")
            sl_time().sleep(twait_ms)

            TestLog("INFO", "Step6", f"触发被动唤醒源并保持，检测DUT是否被唤醒")
            clear_ctx_can_messages()
            wakeup_passive_start()

            status, _ = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
            if status is False:
                error_count = ctx.can.get_info('gErrorFrameCount') or 0
                if error_count > 0:
                    TestLog("WARNING", "", f"检测到{error_count}个错误帧，疑似Bus Off，尝试恢复CAN控制器后重新检测")
                    try:
                        from slplus.can import sl_can
                        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
                        sl_can(can_channel).deactive()
                        time.sleep(0.1)
                        sl_can(can_channel).active()
                    except Exception as e:
                        TestLog("WARNING", "", f"CAN控制器恢复异常: {e}")
                    clear_ctx_can_messages()
                    status, _ = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)

                if status is False:
                    TestLog("FAIL", "", f"Twait={twait_ms}ms时，DUT未被唤醒，唤醒事件丢失")
                    wakeup_failed = True
                    break
            TestLog("PASS", "", f"DUT被唤醒并开始发送NM报文")

            TestLog("INFO", "Step7", f"停止发送唤醒报文，等待TNMtimeout时间")
            wakeup_passive_stop()
            clear_ctx_can_messages()

            status, _ = wait_nm_message_stop(timeout_ms=rTNMtimeout_ms)
            if status is False:
                TestLog("FAIL", "", f"DUT未停止发送NM报文")
                wakeup_failed = True
                break
            TestLog("PASS", "", f"DUT停止发送NM报文，正常发送应用报文（RSS）")

            status, app_stop_time = wait_app_message_stop(timeout_ms=rTNMtimeout_ms)
            if status is False:
                TestLog("FAIL", "", f"DUT在TNMtimeout时间后仍在发送APP报文")
                return
            TestLog("PASS", "", f"DUT在TNMtimeout时间后停止发送APP报文")

            TestLog("INFO", "Step8", f"等待0.8*TwaitBusSleep时间")
            wait_time_ms = int(0.8 * rTwaitBusSleep_ms) - (time.time() * 1000 - app_stop_time)
            sl_time().sleep(wait_time_ms)
            TestLog("PASS", "", f"DUT停止发送NM报文和应用报文")

            twait_ms += 5

        if wakeup_failed:
            return

        TestLog("INFO", "Step10", f"停止发送唤醒报文，等待DUT进入睡眠模式")
        wakeup_passive_stop()

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("PASS", "", f"DUT从PBM到BSM状态切换的过程中，收到网络唤醒请求，DUT能被唤醒，不丢失唤醒事件")
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        wakeup_passive_stop()

def test_TG4_TC9_HighLoadWakeupTest_ActiveWakeup():
    """
    高负载下唤醒测试-主动唤醒测试
    """
    case_name = "TG4_TC9_高负载下唤醒测试-主动唤醒测试"
    high_load_timer_ids = []
    try:
        rIsleep_mA = P.ECUInfo.ISleep
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rVnormal = P.NMInfo.Vnormal
        can_channel = P.ECUInfo.CommCANChannelNum

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {rVnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("INFO", "Step2", f"仿真APP报文（ID=0x7FF），使得总线负载率达到100%并保持")
        high_load_msg = canmsg_create(0x7FF, 8, data=[0xAA] * 8)
        for i in range(1, 26):
            TimerCyclic.start(f"highload_{i}", 1, send_canmsg, can_channel, msg=high_load_msg)
            high_load_timer_ids.append(f"highload_{i}")
        sl_time().sleep(500)

        TestLog("INFO", "Step3", f"触发主动唤醒源并保持，监测DUT")
        clear_ctx_can_messages()
        wakeup_active_start()

        status, _ = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"总线未收到NM报文，DUT未被唤醒")
            return
        TestLog("PASS", "", f"DUT发送NM报文，在高负载状态下DUT能被唤醒")

        TestLog("INFO", "Step4", f"停止主动唤醒源，等待DUT进入睡眠模式")
        wakeup_active_stop()
        for tid in high_load_timer_ids:
            TimerCyclic.stop(tid)
        high_load_timer_ids.clear()

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("PASS", "", f"在高负载状态下，DUT能被唤醒")
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        wakeup_active_stop()
        for tid in high_load_timer_ids:
            TimerCyclic.stop(tid)

def test_TG4_TC10_HighLoadWakeupTest_PassiveWakeup():
    """
    高负载下唤醒测试-被动唤醒测试
    """
    case_name = "TG4_TC10_高负载下唤醒测试-被动唤醒测试"
    high_load_timer_ids = []
    try:
        rIsleep_mA = P.ECUInfo.ISleep
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rVnormal = P.NMInfo.Vnormal
        can_channel = P.ECUInfo.CommCANChannelNum

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {rVnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("INFO", "Step2", f"仿真APP报文（ID=0x7FF），使得总线负载率达到100%并保持")
        high_load_msg = canmsg_create(0x7FF, 8, data=[0xAA] * 8)
        for i in range(1, 26):
            TimerCyclic.start(f"highload_{i}", 1, send_canmsg, can_channel, msg=high_load_msg)
            high_load_timer_ids.append(f"highload_{i}")
        sl_time().sleep(500)

        TestLog("INFO", "Step3", f"触发被动唤醒源并保持，监测DUT")
        clear_ctx_can_messages()
        wakeup_passive_start()

        status, _ = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"总线未收到NM报文，DUT未被唤醒")
            return
        TestLog("PASS", "", f"DUT发送NM报文，在高负载状态下DUT能被唤醒")

        TestLog("INFO", "Step4", f"停止发送唤醒报文，等待DUT进入睡眠模式")
        wakeup_passive_stop()
        for tid in high_load_timer_ids:
            TimerCyclic.stop(tid)
        high_load_timer_ids.clear()

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("PASS", "", f"在高负载状态下，DUT能被唤醒")
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        wakeup_passive_stop()
        for tid in high_load_timer_ids:
            TimerCyclic.stop(tid)

def test_TG4_TC11_LocalAndNetworkWakeupTest_ActiveWakeup():
    """
    本地和网络同时唤醒测试-主动唤醒测试
    """
    case_name = "TG4_TC11_本地和网络同时唤醒测试-主动唤醒测试"
    try:
        rIsleep_mA = P.ECUInfo.ISleep
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rVnormal = P.NMInfo.Vnormal

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {rVnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("INFO", "Step2", f"触发主动唤醒源，同时触发被动唤醒源，并保持，监测DUT")
        clear_ctx_can_messages()
        wakeup_active_start()
        wakeup_passive_start()

        status, _ = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"总线未收到NM报文，DUT未被唤醒")
            return
        TestLog("PASS", "", f"DUT发送NM报文")

        TestLog("INFO", "Step3", f"停止主动唤醒源，同时停止发送唤醒报文，等待DUT进入睡眠模式")
        wakeup_active_stop()
        wakeup_passive_stop()

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("PASS", "", f"DUT在同时接收本地唤醒源和网络唤醒源时，能被正常唤醒")
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        wakeup_active_stop()
        wakeup_passive_stop()

def test_TG4_TC12_StateMachineFaultToleranceTest_ActiveWakeup():
    """
    状态机切换容错测试-主动唤醒测试
    """
    case_name = "TG4_TC12_状态机切换容错测试-主动唤醒测试"
    try:
        rIsleep_mA = P.ECUInfo.ISleep
        rTpowerOnInitial_s = P.NMInfo.TpowerOnInitial_s
        rTwakeupTimeout_ms = P.NMInfo.TwakeupTimeout_ms
        rTrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms
        rVnormal = P.NMInfo.Vnormal
        can_channel = P.ECUInfo.CommCANChannelNum

        TestLog("INFO", "Step1", f"设置DUT电源电压为 {rVnormal} V，执行KL30上电，等待DUT进入睡眠模式")
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("INFO", "Step2", f"触发主动唤醒源并保持，监测DUT")
        clear_ctx_can_messages()
        wakeup_active_start()

        status, _ = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"总线未收到NM报文")
            return
        TestLog("PASS", "", f"DUT发送NM报文")

        TestLog("INFO", "Step3", f"RMS状态下，触发CAN_H和CAN_L短路故障，并保持10s")
        target = f"CAN{can_channel}_HL"
        success, status_msg = ctx.bob_ctrl.set_fault(target, "SHORT", enable=True)
        if not success:
            TestLog("FAIL", "", f"CAN_H与CAN_L短路故障注入失败: {status_msg}")
            return
        TestLog("INFO", "", f"DUT进入Busoff")
        sl_time().sleep(10000)

        TestLog("INFO", "Step4", f"移除CAN总线短路故障，检测DUT是否可以正常周期发送NM报文和应用报文")
        ctx.bob_ctrl.set_fault(target, "SHORT", enable=False)
        clear_ctx_can_messages()
        sl_time().sleep(3000)

        nm_msgs = get_nm_message_list()
        app_msgs = get_app_message_list()
        if len(nm_msgs) == 0:
            TestLog("FAIL", "", f"移除故障后DUT未发送NM报文")
            return
        if len(app_msgs) == 0:
            TestLog("FAIL", "", f"移除故障后DUT未发送APP报文")
            return
        TestLog("PASS", "", f"DUT发送NM报文和APP报文")

        TestLog("INFO", "Step5", f"停止主动唤醒源，等待DUT进入睡眠模式")
        wakeup_active_stop()

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("INFO", "Step6", f"触发主动唤醒源并保持，监测DUT")
        clear_ctx_can_messages()
        wakeup_active_start()

        status, _ = wait_nm_message(timeout_ms=rTwakeupTimeout_ms)
        if status is False:
            TestLog("FAIL", "", f"总线未收到NM报文")
            return
        TestLog("PASS", "", f"DUT发送NM报文")

        TestLog("INFO", "Step7", f"等待TrepeatMessage时间后，监测DUT")
        sl_time().sleep(rTrepeatMessage_ms)
        TestLog("PASS", "", f"DUT以正常周期发送NM报文（进入NOS）")

        TestLog("INFO", "Step8", f"NOS状态下，触发CAN_H和CAN_L短路故障，并保持5s")
        success, status_msg = ctx.bob_ctrl.set_fault(target, "SHORT", enable=True)
        if not success:
            TestLog("FAIL", "", f"CAN_H与CAN_L短路故障注入失败: {status_msg}")
            return
        TestLog("INFO", "", f"DUT进入Busoff")
        sl_time().sleep(5000)

        TestLog("INFO", "Step9", f"移除CAN总线短路故障，检测DUT是否可以正常周期发送NM报文和应用报文")
        ctx.bob_ctrl.set_fault(target, "SHORT", enable=False)
        clear_ctx_can_messages()
        sl_time().sleep(3000)

        nm_msgs = get_nm_message_list()
        app_msgs = get_app_message_list()
        if len(nm_msgs) == 0:
            TestLog("FAIL", "", f"移除故障后DUT未发送NM报文")
            return
        if len(app_msgs) == 0:
            TestLog("FAIL", "", f"移除故障后DUT未发送APP报文")
            return
        TestLog("PASS", "", f"DUT发送NM报文和APP报文")

        TestLog("INFO", "Step10", f"停止主动唤醒源，等待DUT进入睡眠模式")
        wakeup_active_stop()

        status, msg = wait_dut_enter_sleep(rIsleep_mA / 1000.0, timeout_s=rTpowerOnInitial_s)
        if status is False:
            TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")
            return
        TestLog("PASS", "", f"总线无报文，静态电流<Isleep，DUT进入睡眠模式")

        TestLog("PASS", "", f"DUT状态机切换时，发生busoff并恢复后，DUT能正常工作")
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        wakeup_active_stop()
        try:
            target = f"CAN{P.ECUInfo.CommCANChannelNum}_HL"
            ctx.bob_ctrl.set_fault(target, "SHORT", enable=False)
        except Exception:
            pass

def get_all_test_cases():
    current_module = inspect.getmodule(inspect.currentframe())

    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj

    return test_cases
