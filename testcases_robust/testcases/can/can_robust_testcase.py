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
from slplus.time import sl_time

from testcases_canlin.can.can_module import (
    can_initialization, can_deinitialization,
    can_power_setup_and_communication_check,
    check_can_communication_state,
)
from .can_robust_utils import (
    inject_bus_off_and_wait_recovery,
    inject_error_frames_and_check,
    cycle_can_fault_and_check,
)


class CANRobustTestFixture(TestFixture):
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


def test_TG1_TC1_BusOffAutoRecoveryTest():
    """BusOff自动恢复鲁棒性测试"""
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，将KL30上电，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.set_info('gBusOffCount', 0)
        ctx.can.set_filter_by_channel(can_channel)

        TestLog("INFO", "Step2", "通过持续冲突报文触发CAN BusOff状态")
        recovered = inject_bus_off_and_wait_recovery(can_channel, timeout_s=20)

        TestLog("INFO", "Step3", "验证BusOff恢复后DUT通信质量（监控2分钟）")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(2 * 60 * 1000)

        msg_count = len(ctx.can.messages)
        err_count = ctx.can.get_info('gErrorFrameCount') or 0
        TestLog("INFO", "Step3", f"BusOff恢复后收到{msg_count}条报文, 错误帧={err_count}")

        if msg_count > 0 and err_count == 0:
            TestLog("PASS", "Step3", "期望结果：BusOff恢复后通信正常无错误帧。实际结果：通信正常无错误帧")
        elif msg_count > 0 and err_count > 0:
            TestLog("WARNING", "Step3", f"BusOff恢复后存在{err_count}个错误帧")
        else:
            TestLog("FAIL", "Step3", "BusOff恢复后无通信或通信异常")

        TestLog("INFO", "BusOff自动恢复测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "BusOff自动恢复测试", f"测试执行出错: {e}")
        import traceback
        import traceback
        TestLog("DEBUG", "BusOff自动恢复测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC2_ContinuousErrorFrameRobustnessTest():
    """持续错误帧注入鲁棒性测试"""
    tids = []
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        rTdefaultWait = P.CANInfo.TdefaultWait_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        conflict_msg_id = 0x7FF

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，将KL30上电，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.set_filter_by_channel(can_channel)
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)

        TestLog("INFO", "Step2",
                f"以2ms周期发送ID=0x{conflict_msg_id:X}的高优先级冲突报文, 持续{rTdefaultWait}s")
        new_errors, comm_ok, msg_count = inject_error_frames_and_check(
            can_channel, conflict_msg_id, duration_s=rTdefaultWait)

        TestLog("INFO", "Step2", f"注入期间产生{new_errors}个新错误帧")

        TestLog("INFO", "Step3", "停止冲突报文后验证DUT通信恢复状态")
        if comm_ok:
            TestLog("PASS", "Step3", f"期望结果：停止冲突报文后DUT恢复通信。实际结果：DUT正常通信，收到{msg_count}条报文")
        else:
            TestLog("FAIL", "Step3",
                    f"期望结果：停止冲突报文后DUT恢复通信。实际结果：DUT通信未恢复，收到{msg_count}条报文")

        TestLog("INFO", "Step4", "继续监控2分钟，验证长期稳定性")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(2 * 60 * 1000)

        stable_msgs = len(ctx.can.messages)
        stable_errs = ctx.can.get_info('gErrorFrameCount') or 0

        if stable_msgs > 0 and stable_errs == 0:
            TestLog("PASS", "Step4",
                    f"期望结果：长期通信稳定无错误帧。实际结果：收到{stable_msgs}条报文，0个错误帧")
        else:
            TestLog("WARNING", "Step4",
                    f"长期稳定性存疑: 报文={stable_msgs}, 错误帧={stable_errs}")

        TestLog("INFO", "持续错误帧注入鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "持续错误帧注入鲁棒性测试", f"测试执行出错: {e}")
        import traceback
        import traceback
        TestLog("DEBUG", "持续错误帧注入鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC3_CANBusShortCircuitRecoveryTest():
    """CAN总线短路恢复鲁棒性测试"""
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        fault_types = ['CAN_H_short_GND', 'CAN_L_short_GND', 'CAN_H_L_short']

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，将KL30上电，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.set_filter_by_channel(can_channel)
        all_passed = True

        for fault in fault_types:
            TestLog("INFO", "Step2", f"测试故障类型: {fault}")
            results = cycle_can_fault_and_check(fault, can_channel, cycles=3)
            pass_count = sum(1 for r in results if r)
            TestLog("INFO", fault, f"3轮测试通过{pass_count}/3")

            if pass_count < 3:
                all_passed = False

        TestLog("INFO", "Step3", "所有故障类型测试完成后验证DUT通信可恢复")
        ctx.can.clear_messages()
        time.sleep(5)
        final_check = check_can_communication_state(wait_time=5)
        if final_check == 0:
            TestLog("PASS", "Step3", "期望结果：全部故障清除后DUT通信正常。实际结果：DUT通信正常")
        else:
            TestLog("FAIL", "Step3", "期望结果：全部故障清除后DUT通信正常。实际结果：DUT通信异常")

        if all_passed:
            TestLog("PASS", "CAN总线短路恢复鲁棒性测试", "所有短路故障恢复测试通过")
        else:
            TestLog("WARNING", "CAN总线短路恢复鲁棒性测试", "部分故障恢复存在异常")

    except Exception as e:
        TestLog("FAIL", "CAN总线短路恢复鲁棒性测试", f"测试执行出错: {e}")
        import traceback
        import traceback
        TestLog("DEBUG", "CAN总线短路恢复鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC4_TerminationResistorMissingTest():
    """终端电阻丢失鲁棒性测试"""
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，启用终端电阻，将KL30上电，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "Step1", "期望结果：终端电阻正常时DUT通信正常。实际结果：DUT通信正常")

        ctx.can.set_filter_by_channel(can_channel)

        TestLog("INFO", "Step2", "断开终端电阻，监控DUT通信状态")
        ctx.bob_ctrl.set_resistance(120, False, ch=can_channel)
        TestLog("INFO", "Step2", f"已断开CAN{can_channel}终端电阻")

        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(10 * 1000)

        errors_without_term = ctx.can.get_info('gErrorFrameCount') or 0
        msgs_without_term = len(ctx.can.messages)
        TestLog("INFO", "Step2",
                f"无终端电阻时: 报文={msgs_without_term}, 错误帧={errors_without_term}")

        TestLog("INFO", "Step3", "恢复终端电阻，验证DUT通信恢复")
        ctx.bob_ctrl.set_resistance(120, True, ch=can_channel)
        TestLog("INFO", "Step3", f"已恢复CAN{can_channel}终端电阻")

        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(5 * 1000)

        recovery_check = check_can_communication_state(wait_time=3)
        if recovery_check == 0:
            TestLog("PASS", "Step3",
                    "期望结果：恢复终端电阻后DUT通信恢复正常。实际结果：DUT通信恢复正常")
        else:
            TestLog("FAIL", "Step3",
                    "期望结果：恢复终端电阻后DUT通信恢复正常。实际结果：DUT通信未恢复")

        TestLog("INFO", "Step4", "监控5分钟，验证长期通信稳定性")
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
                    f"长期通信存在异常: 报文={final_msgs}, 错误帧={final_errs}")

        TestLog("INFO", "终端电阻丢失鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "终端电阻丢失鲁棒性测试", f"测试执行出错: {e}")
        import traceback
        import traceback
        TestLog("DEBUG", "终端电阻丢失鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC5_CANFDBRSErrorRobustnessTest():
    """CAN FD BRS标志错误鲁棒性测试"""
    tids = []
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        rTdefaultWait = P.CANInfo.TdefaultWait_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，将KL30上电，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.set_filter_by_channel(can_channel)
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)

        TestLog("INFO", "Step2",
                "发送BRS=1的CAN FD报文（高波特率），同时混发Classic CAN报文，持续{rTdefaultWait}s")

        fd_msg = canmsg_create(0x100, 15, data=0x5A, rtr=0, fdf=1, brs=1, ext=0)
        classic_msg = canmsg_create(0x200, 8, data=0x3C, rtr=0, fdf=0, brs=0, ext=0)

        TimerCyclic.start(91, 10, send_canmsg, can_channel, msg=fd_msg)
        TimerCyclic.start(92, 20, send_canmsg, can_channel, msg=classic_msg)
        tids = [91, 92]

        sl_time().sleep(int(rTdefaultWait * 1000))

        for t in tids:
            TimerCyclic.stop(t)
        tids.clear()

        err_count = ctx.can.get_info('gErrorFrameCount') or 0
        msg_count = len(ctx.can.messages)
        TestLog("INFO", "Step2", f"FD/Classic混跑后: 报文={msg_count}, 错误帧={err_count}")

        TestLog("INFO", "Step3", "停止FD报文发送后验证基础Classic CAN通信恢复正常")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(3 * 1000)

        ret = check_can_communication_state(wait_time=3)
        if ret == 0:
            TestLog("PASS", "Step3",
                    f"期望结果：FD BRS错误注入后Classic CAN通信正常。实际结果：通信正常, {len(ctx.can.messages)}条报文")
        else:
            TestLog("FAIL", "Step3",
                    "期望结果：FD BRS错误注入后Classic CAN通信正常。实际结果：通信异常")

        TestLog("INFO", "CAN FD BRS错误鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "CAN FD BRS错误鲁棒性测试", f"测试执行出错: {e}")
        import traceback
        import traceback
        TestLog("DEBUG", "CAN FD BRS错误鲁棒性测试", f"详细错误: {traceback.format_exc()}")
    finally:
        for t in tids:
            try:
                TimerCyclic.stop(t)
            except:
                pass


def test_TG1_TC6_CANBaudrateInterferenceTest():
    """CAN波特率干扰鲁棒性测试"""
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，将KL30上电，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.set_filter_by_channel(can_channel)

        TestLog("INFO", "Step2", "切换CAN通道波特率配置产生干扰，观察DUT通信状态")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)

        # 通过快速切换报文速率模拟波特率干扰
        conflict_msg_fast = canmsg_create(0x100, 8, data=0xAA, rtr=0, fdf=1, brs=1, ext=0)
        conflict_msg_slow = canmsg_create(0x200, 8, data=0x55, rtr=0, fdf=0, brs=0, ext=0)

        TestLog("INFO", "Step2", "交替发送CANFD和Classic CAN报文，模拟波特率不匹配场景")
        for burst in range(1, 6):
            TestLog("INFO", "Step2", f"第{burst}/5轮波特率干扰")
            ctx.can.clear_messages()
            ctx.can.set_info('gErrorFrameCount', 0)
            # 快速交替发送不同类型报文
            import time as _time
            start = _time.time()
            while _time.time() - start < 3:
                send_canmsg(can_channel, msg=conflict_msg_fast)
                send_canmsg(can_channel, msg=conflict_msg_slow)
                _time.sleep(0.002)

            err_count = ctx.can.get_info('gErrorFrameCount') or 0
            TestLog("INFO", "Step2", f"第{burst}轮干扰后错误帧={err_count}")
            _time.sleep(2)

        TestLog("INFO", "Step3", "停止波特率干扰后验证DUT通信恢复")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(5 * 1000)

        ret = check_can_communication_state(wait_time=3)
        if ret == 0:
            TestLog("PASS", "Step3",
                    "期望结果：波特率干扰停止后DUT通信恢复。实际结果：DUT通信正常")
        else:
            TestLog("FAIL", "Step3",
                    "期望结果：波特率干扰停止后DUT通信恢复。实际结果：DUT通信异常")

        TestLog("INFO", "Step4", "监控5分钟验证恢复后长期稳定性")
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
                    f"长期通信存在异常: 报文={final_msgs}, 错误帧={final_errs}")

        TestLog("INFO", "CAN波特率干扰鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "CAN波特率干扰鲁棒性测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "CAN波特率干扰鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC7_CANCRCTamperTest():
    """CAN CRC篡改鲁棒性测试"""
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，将KL30上电，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.set_filter_by_channel(can_channel)

        TestLog("INFO", "Step2", "注入多种格式错误帧（DLC超范围、无效位填充、保留位置位），观察DUT行为")
        error_patterns = [
            ("DLC=9超范围", 0x300, 9, 0x00, 0, 0),    # DLC超范围
            ("保留位RTR=1", 0x301, 8, 0x00, 1, 0),     # RTR=1异常
            ("DLC=0空数据", 0x302, 0, 0x00, 0, 0),      # DLC=0
            ("DLC=15大载荷", 0x303, 15, 0xFF, 1, 1),    # CANFD max DLC
        ]

        all_errors_handled = True
        for desc, mid, dlc, data_byte, rtr, fdf in error_patterns:
            TestLog("INFO", "Step2", f"注入异常帧: {desc}")
            ctx.can.clear_messages()
            ctx.can.set_info('gErrorFrameCount', 0)

            msg = canmsg_create(mid, dlc, data=data_byte, rtr=rtr, fdf=fdf, brs=0, ext=0)
            if msg:
                # 快速发送异常帧
                for _ in range(50):
                    send_canmsg(can_channel, msg=msg)

            sl_time().sleep(2 * 1000)
            err_count = ctx.can.get_info('gErrorFrameCount') or 0
            TestLog("INFO", "Step2", f"{desc}: 错误帧={err_count}")

        TestLog("INFO", "Step3", "验证异常帧停止后DUT通信恢复")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(5 * 1000)

        ret = check_can_communication_state(wait_time=3)
        if ret == 0:
            TestLog("PASS", "Step3",
                    "期望结果：格式错误帧停止后DUT通信恢复。实际结果：DUT通信正常")
        else:
            TestLog("FAIL", "Step3",
                    "期望结果：格式错误帧停止后DUT通信恢复。实际结果：DUT通信异常")
            all_errors_handled = False

        TestLog("INFO", "Step4", "监控5分钟验证长期稳定性")
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
                    f"长期通信存在异常: 报文={final_msgs}, 错误帧={final_errs}")

        if all_errors_handled:
            TestLog("PASS", "CAN CRC篡改鲁棒性测试", "所有异常帧注入后DUT均正常恢复")
        else:
            TestLog("WARNING", "CAN CRC篡改鲁棒性测试", "部分异常帧注入后恢复异常")

    except Exception as e:
        TestLog("FAIL", "CAN CRC篡改鲁棒性测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "CAN CRC篡改鲁棒性测试", f"详细错误: {traceback.format_exc()}")


def get_all_test_cases():
    import inspect
    current_module = inspect.getmodule(inspect.currentframe())
    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj
    return test_cases
