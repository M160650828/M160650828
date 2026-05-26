import copy 
import inspect
import sys
import os
import time
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from env.config import *

from uvtest.testlog import TestLog
from .can_utils import (
    check_expected_response, start_simulation_msgs, stop_simulation_msgs, send_random_data_msg,
    check_bus_error_frames, kl30_power_cycle, voltage_step_test, dut_force_sleep,
    simulation_powermode_signal, stop_powermode_signal,
    simulation_special_message, stop_special_message
)
from common.context import ctx
from common.utils import TimerCyclic
from common.can_utils import send_canmsg, canmsg_create
from sl.sl import sl_project_start

from common.params import P

from .can_module import (
    can_power_setup_and_communication_check,
    check_can_communication_state,
    analyze_messages,
    report_message_tests,
    can_fault_injection,
    check_communication_recovery_time,
    build_rx_msg_info, report_max_cycle_not_exceed_2x, get_all_id_time, can_clear_injection,
)
from common.control import TestStart, TestEnd
from uvtest.framework import TestFixture
from .can_module import can_initialization, can_deinitialization
from common.wakeup import WakeupStart, WakeupStop
from common.voltage_control import voltage_threshold_test_with_validation
from .can_module import CanCommChecker
from slplus.busstatis import sl_busstatis
from slplus.time import sl_time
from .can_diag_utils import close_can_node


class CANTestFixture(TestFixture):
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

def test_TG1_TC5_PhyLayer_LowVoltageRangeTest():
    """
    低电压通信范围测试
    """
    try:
        # 测试参数
        rVnormal = P.CANInfo.Vnormal
        rVlowStand = P.CANInfo.VlowStand
        rVtestRange = P.CANInfo.VtestRange
        rVstep = P.CANInfo.Vstep
        rTstable_s = P.CANInfo.Tstable_s
        rTvStepDelay = P.CANInfo.TvStepDelay_s
        ctx.can.set_filter_by_channel(DEFAULT_CAN_CHANNELS[0])

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{rTstable_s}时间至通信稳定")
        # 测试环境设置
        ctx.can.clear_messages()
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "接收报文测试", "期望结果：DUT通信正常。实际结果：电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS","","期望结果：DUT通信正常。实际结果：DUT通信正常")

        TestLog("INFO","Step2",f"将{rVlowStand + rVtestRange}V作为起始电压，以{rTvStepDelay}时间为间隔，以{rVstep}V为步长，逐步降压，监控DUT通信状态，重复上述操作")
        # Step2: 验证通信步进停止的电压阈值
        stop_success, voltage_low_stop = voltage_threshold_test_with_validation(CanCommChecker(),
                                                                                test_type="stop",
                                                                                start_voltage=rVlowStand + rVtestRange,
                                                                                end_voltage=rVlowStand - rVtestRange,
                                                                                step=-rVstep,
                                                                                step_delay=rTvStepDelay,
                                                                                validation_voltage=rVlowStand,
                                                                                tolerance=0.0
                                                                                )

        if not stop_success or voltage_low_stop is None:
            return

        TestLog("INFO", "Step3",
                f"将{voltage_low_stop}作为起始电压，以{rTvStepDelay}V时间为间隔，以{rVstep}V为步长，逐步升压，监控DUT通信状态，重复上述操作")
        # Step3: 验证通信步进恢复的电压阈值
        resume_success, voltage_resume = voltage_threshold_test_with_validation(CanCommChecker(),
                                                                                test_type="resume",
                                                                                start_voltage=voltage_low_stop,
                                                                                end_voltage=rVlowStand + rVtestRange,
                                                                                step=rVstep,
                                                                                step_delay=rTvStepDelay,
                                                                                validation_voltage=rVlowStand,
                                                                                tolerance=rVstep
                                                                                )
        if not resume_success or voltage_resume is None:
            return
        TestLog("INFO", "低电压通信范围测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "低电压通信范围测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "低电压通信范围测试", f"详细错误: {traceback.format_exc()}")

def test_TG1_TC6_PhyLayer_HighVoltageRangeTest():
    """
    高电压通信范围测试
    """
    try:
        # 测试参数
        rVnormal = P.CANInfo.Vnormal
        rVhighStand = P.CANInfo.VhighStand
        rVtestRange = P.CANInfo.VtestRange
        rVstep = P.CANInfo.Vstep
        rTstable_s = P.CANInfo.Tstable_s
        rTvStepDelay = P.CANInfo.TvStepDelay_s
        ctx.can.set_filter_by_channel(DEFAULT_CAN_CHANNELS[0])
        ctx.can.clear_messages()
        # 测试环境设置
        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{rTstable_s}时间至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "接收报文测试", "期望结果：DUT通信正常。实际结果：电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        TestLog("INFO", "Step2",
                f"将{rVhighStand - rVtestRange}作为起始电压，以{rTvStepDelay}时间为间隔，以{rVstep}为步长，逐步升压，监控DUT通信状态，重复上述操作")
        # Step2: 验证通信步进停止的电压阈值
        stop_success, voltage_high_stop = voltage_threshold_test_with_validation(CanCommChecker(),
                                                                                 test_type="stop",
                                                                                 start_voltage=rVhighStand - rVtestRange,
                                                                                 end_voltage=rVhighStand + rVtestRange,
                                                                                 step=rVstep,
                                                                                 step_delay=rTvStepDelay,
                                                                                 validation_voltage=rVhighStand,
                                                                                 tolerance=0.0
                                                                                 )
        if not stop_success or voltage_high_stop is None:
            return

        TestLog("INFO", "Step3",
                f"将{voltage_high_stop}作为起始电压，以{rTvStepDelay}时间为间隔，以{rVstep}为步长，逐步降压，监控DUT通信状态，重复上述操作")

        # Step3: 验证通信步进恢复的电压阈值
        resume_success, voltage_resume = voltage_threshold_test_with_validation(CanCommChecker(),
                                                                                test_type="resume",
                                                                                start_voltage=voltage_high_stop,
                                                                                end_voltage=rVhighStand - rVtestRange,
                                                                                step=-rVstep,
                                                                                step_delay=rTvStepDelay,
                                                                                validation_voltage=rVhighStand,
                                                                                tolerance=-rVstep
                                                                                )
        if not resume_success or voltage_resume is None:
            return
        TestLog("INFO", "高电压通信范围测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "高电压通信范围测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "高电压通信范围测试", f"详细错误: {traceback.format_exc()}")

def test_TG2_TC3_CANFD_DataLinkLayer_CANMessageCompatibilityTest():
    """
    CANFD CAN报文兼容性测试
    """
    try:
        # 测试参数
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rTdefaultWait = P.CANInfo.TdefaultWait_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1


        # # Step1: 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        # 检查初始通信状态
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        ret = check_can_communication_state(rTstable)
        if ret != 0:
            TestLog("INFO", "CANFD CAN报文兼容性测试", "DUT通信不正常，测试结束")
            return

        if (ctx.can.get_info('gErrorFrameCount') or 0) == 0:
            TestLog("PASS", "", "实际: DUT通信正常，无错误帧; 期望: DUT通信正常，无错误帧")
        else:
            TestLog("FAIL", "", "实际: 存在错误帧; 期望: DUT通信正常，无错误帧")
            return

        # Step2: 以10ms周期，同时向总线发送ID为0x001和0x7FF，DLC=8，FDF=0，数据段均为0x3C的CAN报文
        TestLog("INFO", "Step2",
                f"同时发送ID为0x001和0x7FF，DLC=8，FDF=0，数据段均为0x3C的CAN报文，持续时间 {rTdefaultWait}s")

        # 创建CAN报文
        msg1 = canmsg_create(0x001, 8, data=0x3C, rtr=0, fdf=0, brs=0, ext=0)  # ID=0x001, DLC=8, FDF=0
        msg2 = canmsg_create(0x7FF, 8, data=0x3C, rtr=0, fdf=0, brs=0, ext=0)  # ID=0x7FF, DLC=8, FDF=0

        # 设置周期定时器
        TimerCyclic.start(1, 10, send_canmsg, can_channel, msg=msg1)  # 10ms周期发送msg1
        TimerCyclic.start(2, 10, send_canmsg, can_channel, msg=msg2)  # 10ms周期发送msg2

        # 检查通信
        check_can_communication_state(rTdefaultWait)

        # 停止发送报文
        TimerCyclic.stop(1)
        TimerCyclic.stop(2)

        if (ctx.can.get_info('gErrorFrameCount') or 0) == 0:
            TestLog("PASS", "", "实际: DUT通信正常，无错误帧; 期望: DUT通信正常，无错误帧")
        else:
            TestLog("FAIL", "", "实际: 存在错误帧; 期望: DUT通信正常，无错误帧")
            return

        # Step3: 以10ms周期，同时向总线发送ID为0x001和0x7FF，DLC=15，FDF=1，BRS=1，数据段均为0x3C的CAN FD报文
        TestLog("INFO", "Step3",
                f"同时发送ID为0x001和0x7FF，DLC=15，FDF=1，BRS=1，数据段均为0x3C的CAN FD报文，持续时间{rTdefaultWait}s")

        # 创建CANFD报文
        msg1 = canmsg_create(0x001, 15, data=0x3C, rtr=0, fdf=1, brs=1, ext=0)  # ID=0x001, DLC=15, FDF=1, BRS=1
        msg2 = canmsg_create(0x7FF, 15, data=0x3C, rtr=0, fdf=1, brs=1, ext=0)  # ID=0x7FF, DLC=15, FDF=1, BRS=1

        TimerCyclic.start(1, 10, send_canmsg, can_channel, msg=msg1)  # 10ms周期发送msg1
        TimerCyclic.start(2, 10, send_canmsg, can_channel, msg=msg2)  # 10ms周期发送msg2

        # 检查通信
        check_can_communication_state(rTdefaultWait)

        # 停止发送报文
        TimerCyclic.stop(1)
        TimerCyclic.stop(2)

        if (ctx.can.get_info('gErrorFrameCount') or 0) == 0:
            TestLog("PASS", "", "实际: DUT通信正常，无错误帧; 期望: DUT通信正常，无错误帧")
        else:
            TestLog("FAIL", "", "实际: 存在错误帧; 期望: DUT通信正常，无错误帧")
            return

        # Step4: 混合发送CAN和CANFD报文
        TestLog("INFO", "Step4",
                f"同时发送ID为0x001，DLC=8，FDF=0的CAN报文和ID为0x7FF，DLC=15，FDF=1，BRS=1的CAN FD报文，持续时间{rTdefaultWait}s")

        # 创建混合报文
        msg1 = canmsg_create(0x001, 8, 0x3C,0, 0, 0, 0)  # CAN报文
        msg2 = canmsg_create(0x7FF, 15, 0x3C, 0, 1, 1, 0)  # CANFD报文

        # 设置周期定时器
        TimerCyclic.start(1, 10, send_canmsg, can_channel, msg=msg1)  # 10ms周期发送msg1
        TimerCyclic.start(2, 10, send_canmsg, can_channel, msg=msg2)  # 10ms周期发送msg1


        # 检查通信
        check_can_communication_state(rTdefaultWait)

        # 停止发送报文
        TimerCyclic.stop(1)
        TimerCyclic.stop(2)

        if (ctx.can.get_info('gErrorFrameCount') or 0) == 0:
            TestLog("PASS", "", "实际: DUT通信正常，无错误帧; 期望: DUT通信正常，无错误帧")
        else:
            TestLog("FAIL", "", "实际: 存在错误帧; 期望: DUT通信正常，无错误帧")
            return

        if (ctx.can.get_info('gErrorFrameCount') or 0) == 0:
            TestLog("PASS", "", "实际: DUT通信正常，无错误帧; 期望: DUT通信正常，无错误帧")
        else:
            TestLog("FAIL", "", "实际: 存在错误帧; 期望: DUT通信正常，无错误帧")
            return

        # Step5: 以10ms周期，同时向总线发送ID为0x001和0x7FF，DLC=15，FDF=1，BRS=0，数据段均为0x3C的CAN FD报文
        TestLog("INFO", "Step5",
                f"同时发送ID为0x001和0x7FF，DLC=15，FDF=1，BRS=0，数据段均为0x3C的CAN FD报文，持续时间{rTdefaultWait}s")

        # 创建CANFD报文(BRS=0)
        msg1 = canmsg_create(0x001, 15, 0x3C, 0, 1, 0, 0)  # ID=0x001, DLC=15, FDF=1, BRS=0
        msg2 = canmsg_create(0x7FF, 15, 0x3C, 0, 1, 0, 0)  # ID=0x7FF, DLC=15, FDF=1, BRS=0

        # 设置周期定时器
        TimerCyclic.start(1, 10, send_canmsg, can_channel, msg=msg1)  # 10ms周期发送msg1
        TimerCyclic.start(2, 10, send_canmsg, can_channel, msg=msg2)  # 10ms周期发送msg2

        # 检查通信
        check_can_communication_state(rTdefaultWait)

        # 停止发送报文
        TimerCyclic.stop(1)
        TimerCyclic.stop(2)

        if (ctx.can.get_info('gErrorFrameCount') or 0) == 0:
            TestLog("PASS", "", "实际: DUT通信正常，无错误帧; 期望: DUT通信正常，无错误帧")
        else:
            TestLog("FAIL", "", "实际: 存在错误帧; 期望: DUT通信正常，无错误帧")
            return

        # Step6: 以10ms周期，同时向总线发送ID为0x001和0x7FF，DLC=8-14，FDF=1，BRS=1，数据段均为0x3C的CAN FD报文
        TestLog("INFO", "Step6", f"同时发送ID为0x001和0x7FF，DLC=8-14，FDF=1，BRS=1，数据段均为0x3C的CAN FD报文")

        for dlc in range(8, 15):  # DLC从8到14
            TestLog("INFO", "", f"发送DLC={dlc}的CANFD报文，持续时间{rTdefaultWait}s")

            # 创建CANFD报文
            msg1 = canmsg_create(0x001, dlc, 0x3C, 0, 1, 1, 0)  # ID=0x001
            msg2 = canmsg_create(0x7FF, dlc, 0x3C, 0, 1, 1, 0)  # ID=0x7FF

            # 设置周期定时器
            TimerCyclic.start(1, 10, send_canmsg, can_channel, msg=msg1)  # 10ms周期发送msg1
            TimerCyclic.start(2, 10, send_canmsg, can_channel, msg=msg2)  # 10ms周期发送msg2

            # 检查通信
            check_can_communication_state(rTdefaultWait)

            # 停止发送报文
            TimerCyclic.stop(1)
            TimerCyclic.stop(2)

            time.sleep(1)  # 间隔1秒

            if (ctx.can.get_info('gErrorFrameCount') or 0) == 0:
                TestLog("PASS", "", "实际: DUT通信正常，无错误帧; 期望: DUT通信正常，无错误帧")
            else:
                TestLog("FAIL", "", "实际: 存在错误帧; 期望: DUT通信正常，无错误帧")
                return

        TestLog("INFO", "CANFD CAN报文兼容性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "CANFD CAN报文兼容性测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "CANFD CAN报文兼容性测试", f"详细错误: {traceback.format_exc()}")
    finally:
        try:
            TimerCyclic.stop(1)
            TimerCyclic.stop(2)
        except:
            pass
        TestLog("INFO", "测试结束", "执行测试结束和去初始化")

def test_TG2_TC4_DataLinkLayer_MaximumFillBitMessageTest():
    """最大填充位报文测试"""
    try:
        # 测试参数
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable_s = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rTdefaultWait = P.CANInfo.TdefaultWait_s
        rMsgID = 0x78
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1


        # 测试环境设置
        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{rTstable_s}时间至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "", "期望结果：DUT通信正常。实际结果：电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.clear_messages()
        if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
            TestLog("FAIL", "测试结束", "实际: 存在错误帧; 期望: 无错误帧")
            return

        # Step2: 以10ms为周期，向总线发送ID为0x78,DLC=8,数据场均为0x3C的CAN报文，持续测试Tdefaultwait时间
        TestLog("INFO", "Step2", f"发送ID为{hex(rMsgID)}，DLC=8，FDF=0，数据场为0x3C的CAN报文，持续时间 {rTdefaultWait}s")
        # 创建CAN报文
        msg = canmsg_create(rMsgID, 15, data=0x3C, rtr=0, fdf=1, brs=1, ext=0)

        # 设置周期定时器
        TimerCyclic.start(1, 10, send_canmsg, can_channel, msg=msg)  # 10ms周期发送msg

        # 持续测试Tdefaultwait时间
        check_can_communication_state(rTdefaultWait)

        # 停止发送报文
        TimerCyclic.stop(1)

        TestLog("INFO", "最大填充位报文测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "最大填充位报文测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "最大填充位报文测试", f"详细错误: {traceback.format_exc()}")

def test_TG2_TC5_DataLinkLayer_ExtendFrameTest():
    """扩展帧测试"""
    try:
        # 测试参数
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable_s = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rTdefaultWait = P.CANInfo.TdefaultWait_s
        rExtendMsgID = P.CANInfo.ExtendMsgID
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1


        # 测试环境设置
        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{rTstable_s}时间至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "", "期望结果：DUT通信正常。实际结果：电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.clear_messages()
        if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
            TestLog("FAIL", "测试结束", "实际: 存在错误帧; 期望: 无错误帧")
            return

        # Step2: 以10ms为周期，向总线发送ID为扩展帧,DLC=8,数据场均为0x3C的CAN报文，持续测试Tdefaultwait时间
        TestLog("INFO", "Step2",
                f"发送ID为{rExtendMsgID},{type(rExtendMsgID)}，DLC=8，FDF=0，数据场为0x3C的CAN报文，持续时间 {rTdefaultWait}s")
        # 创建CAN报文
        msg = canmsg_create(rExtendMsgID, 8, data=0x3C, rtr=0, fdf=0, brs=0, ext=1)

        # 设置周期定时器
        TimerCyclic.start(1, 10, send_canmsg, can_channel, msg=msg)  # 10ms周期发送msg

        # 持续测试Tdefaultwait时间
        check_can_communication_state(rTdefaultWait)

        # 停止发送报文
        TimerCyclic.stop(1)

        if (ctx.can.get_info('gErrorFrameCount') or 0) == 0:
            TestLog("PASS", "", "实际: DUT通信正常，无错误帧; 期望: DUT通信正常，无错误帧")
        else:
            TestLog("FAIL", "", "实际: 存在错误帧; 期望: DUT通信正常，无错误帧")
            return

        # Step3: 以10ms为周期，以10ms为周期，向总线发送ID为ExtendmsgID，DLC=15，FDF=1，BRS=1，数据段均为0x3C的CAN FD报文，持续测试TdefaultWait时间之后停止发送
        TestLog("INFO", "Step3",
                f"发送ID为{rExtendMsgID},{type(rExtendMsgID)}，DLC=15，FDF=1，BRS=1，数据场为0x3C的CAN报文，持续时间 {rTdefaultWait}s")
        # 创建CAN报文
        msg = canmsg_create(rExtendMsgID, 15, data=0x3C, rtr=0, fdf=1, brs=1, ext=1)

        # 设置周期定时器
        TimerCyclic.start(1, 10, send_canmsg, can_channel, msg=msg)  # 10ms周期发送msg

        # 持续测试Tdefaultwait时间
        check_can_communication_state(rTdefaultWait)

        # 停止发送报文
        TimerCyclic.stop(1)

        if (ctx.can.get_info('gErrorFrameCount') or 0) == 0:
            TestLog("PASS", "", "实际: DUT通信正常，无错误帧; 期望: DUT通信正常，无错误帧")
        else:
            TestLog("FAIL", "", "实际: 存在错误帧; 期望: DUT通信正常，无错误帧")
            return

        # Step4: 以10ms为周期，同时向总线发送ID为ExtendmsgID，DLC=8，FDF=0，数据段均为0x3C的CAN报文和ID为ExtendmsgID，DLC=15，FDF=1，BRS=1，数据段均为0x3C的CAN FD报文，持续测试TdefaultWait时间之后停止发送
        TestLog("INFO", "Step4",
                f"发送ID为{rExtendMsgID},{type(rExtendMsgID)}，DLC=8，FDF=0，数据场为0x3C的CAN报文和，DLC=15，FDF=1，BRS=1，数据段均为0x3C的CAN FD报文，持续测试TdefaultWait时间之后停止发送持续时间 {rTdefaultWait}s")
        # 创建CAN报文
        msg1 = canmsg_create(rExtendMsgID, 8, data=0x3C, rtr=0, fdf=0, brs=0, ext=1)
        msg2 = canmsg_create(rExtendMsgID, 15, data=0x3C, rtr=0, fdf=1, brs=1, ext=1)

        # 设置周期定时器
        TimerCyclic.start(1, 10, send_canmsg, can_channel, msg=msg1)  # 10ms周期发送msg
        TimerCyclic.start(2, 10, send_canmsg, can_channel, msg=msg2)  # 10ms周期发送msg

        # 持续测试Tdefaultwait时间
        check_can_communication_state(rTdefaultWait)

        # 停止发送报文
        TimerCyclic.stop(1)
        TimerCyclic.stop(2)

        if (ctx.can.get_info('gErrorFrameCount') or 0) == 0:
            TestLog("PASS", "", "实际: DUT通信正常，无错误帧; 期望: DUT通信正常，无错误帧")
        else:
            TestLog("FAIL", "", "实际: 存在错误帧; 期望: DUT通信正常，无错误帧")
            return

        TestLog("INFO", "扩展帧测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "扩展帧测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "扩展帧测试", f"详细错误: {traceback.format_exc()}")

def test_TG2_TC6_DataLinkLayer_RemoteFrameTest():
    """远程帧测试"""
    try:
        # 测试参数
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable_s = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rTdefaultWait = P.CANInfo.TdefaultWait_s
        rRemoteMsgID = P.CANInfo.RemoteMsgID
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1


        # 测试环境设置
        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{rTstable_s}时间至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "", "期望结果：DUT通信正常。实际结果：电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.clear_messages()
        if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
            TestLog("FAIL", "测试结束", "实际: 存在错误帧; 期望: 无错误帧")
            return

        # Step2: 以10ms为周期，向总线发送ID为远程帧,DLC=8,数据场均为0x3C的CAN报文，持续测试Tdefaultwait时间
        TestLog("INFO", "Step2",
                f"发送ID为{hex(rRemoteMsgID)}，DLC=8，FDF=0，数据场为0x3C的CAN报文，持续时间 {rTdefaultWait}s")
        # 创建CAN报文
        msg = canmsg_create(rRemoteMsgID, 8, data=0x3C, rtr=1, fdf=0, brs=0, ext=0)

        # 设置周期定时器
        TimerCyclic.start(1, 10, send_canmsg, can_channel, msg=msg)  # 10ms周期发送msg

        # 持续测试Tdefaultwait时间
        check_can_communication_state(rTdefaultWait)

        # 停止发送报文
        TimerCyclic.stop(1)

        TestLog("INFO", "远程帧测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "远程帧测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "远程帧测试", f"详细错误: {traceback.format_exc()}")

def test_TG2_TC7_DataLinkLayer_ErrorFrameTest():
    """错误帧测试"""
    try:
        # 测试参数
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable_s = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rTdefaultWait = P.CANInfo.TdefaultWait_s
        rErrorMsgID = P.CANInfo.ErrorMsgID
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1


        # 测试环境设置
        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{rTstable_s}时间至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "", "期望结果：DUT通信正常。实际结果：电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.clear_messages()
        if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
            TestLog("FAIL", "测试结束", "实际: 存在错误帧; 期望: 无错误帧")
            return

        # Step2: 以10ms为周期，向总线发送ID为错误帧,DLC=8,数据场均为0x3C的CAN报文，持续测试Tdefaultwait时间
        TestLog("INFO", "Step2",
                f"发送ID为{hex(rErrorMsgID)}，DLC=8，FDF=0，数据场为0x3C的CAN报文，持续时间 {rTdefaultWait}s")
        # 创建CAN报文
        # TODO 发送错误帧
        msg = canmsg_create(rErrorMsgID, 8, data=0x3C, rtr=1, fdf=0, brs=0, ext=0)

        # 设置周期定时器
        TimerCyclic.start(1, 10, send_canmsg, can_channel, msg=msg)  # 10ms周期发送msg

        # 持续测试Tdefaultwait时间
        check_can_communication_state(rTdefaultWait)

        # 停止发送报文
        TimerCyclic.stop(1)

        TestLog("INFO", "错误帧测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "错误帧测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "错误帧测试", f"详细错误: {traceback.format_exc()}")

def test_TG2_TC8_DataLinkLayer_DiagnosticMessageDLCErrorTest():
    """诊断报文DLC错误测试"""
    try:
        # 测试参数
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable_s = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rTdefaultWait = P.CANInfo.TdefaultWait_s
        rDiagReqID = P.ECUInfo.DiagReqID_int  # TODO 读取参数配置表
        rDiagRespID = P.ECUInfo.DiagRespID_int  # TODO 读取参数配置表
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{rTstable_s}时间至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "", "期望结果：DUT通信正常。实际结果：电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        # Step2: 发送物理寻址诊断请求：02 10 01，DLC=7
        TestLog("INFO", "Step2", f"发送物理寻址诊断请求：02 10 01，DLC=7")
        # 创建CAN报文
        msg = canmsg_create(rDiagReqID, 7, data=[0x02, 0x10, 0x01] + [0xAA] * 5, rtr=0, fdf=0, brs=0, ext=0)
        ctx.can.clear_messages()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=7, rtr=0, fdf=0, brs=0)

        timeout = 5  # 检测5秒钟
        if check_expected_response(rDiagRespID, 1, [0x50, 0x01], timeout=timeout) is True:
            TestLog("FAIL", "", f"实际: {timeout}s内检测到正响应报文; 期望: DLC=7时无响应")
            return
        TestLog("PASS", "", f"实际: {timeout}s内未收到响应; 期望: DLC=7时无响应")


        # Step3: 发送物理寻址诊断请求：02 10 01，DLC=8
        TestLog("INFO", "Step3", f"发送物理寻址诊断请求：02 10 01，DLC=8")
        # 创建CAN报文
        msg = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, rtr=0, fdf=0, brs=0, ext=0)
        ctx.can.clear_messages()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8, rtr=0, fdf=0, brs=0)

        timeout = 5  # 检测5秒钟
        if check_expected_response(rDiagRespID, 1, [0x50, 0x01], timeout=timeout) is False:
            TestLog("FAIL", "", f"实际: {timeout}s内未收到响应; 期望: DLC=8时DUT发出正响应报文(51 01)")
            return
        TestLog("PASS", "", f"实际: {timeout}s内检测到正响应报文; 期望: DLC=8时DUT发出正响应报文(51 01)")

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "诊断报文DLC错误测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "诊断报文DLC错误测试", f"详细错误: {traceback.format_exc()}")

def test_TG2_TC12_DataLinkLayer_BusLoadRateMonitoringTest():
    """总线负载率监控测试"""
    try:
        # 测试参数
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable_s = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rTdefaultWait = P.CANInfo.TdefaultWait_s
        rErrorMsgID = P.CANInfo.ErrorMsgID
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rBusloadNormal = P.CANInfo.BusloadNormal_pct

        # 测试环境设置
        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{rTstable_s}时间至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "", "期望结果：DUT通信正常。实际结果：电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.clear_messages()
        if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
            TestLog("FAIL", "测试结束", "实际: 存在错误帧; 期望: 无错误帧")
            return

        # Step2: 持续监控5分钟，记录总线负载的最小值、最大值、平均值
        TestLog("INFO", "Step2", f"持续监控5分钟，记录总线负载的最小值、最大值、平均值")
        sl_time().sleep(5 * 60_000)

        busload = sl_busstatis().get_can_stat_by_ch(can_channel)
        # TestLog("INFO","",f"busload={busload}")
        busload_min = round(busload.get("busload", {}).get("min") * 100, 2)
        busload_max = round(busload.get("busload", {}).get("max") * 100, 2)
        busload_avg = round(busload.get("busload", {}).get("avg") * 100, 2)
        # TestLog("INFO","",f"busload_min={busload_min},busload_max={busload_max},busload_avg={busload_avg}")

        if busload_avg <= rBusloadNormal:
            TestLog("PASS", "",
                    f"实际: {busload_avg=}, {rBusloadNormal=}; 期望: {busload_avg=} < {rBusloadNormal=}")
        else:
            TestLog("FAIL", "",
                    f"实际: {busload_avg=}, {rBusloadNormal=}; 期望: {busload_avg=} < {rBusloadNormal=}")

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "总线负载率监控测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "总线负载率监控测试", f"详细错误: {traceback.format_exc()}")

def test_TG2_TC13_DataLinkLayer_BusLoadMiddleRateMonitoringTest():
    """总线中负载率监控测试"""
    tids = []
    timer_id = 1
    try:
        # 测试参数
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rBusloadNormal = P.CANInfo.BusloadMedium_pct
        # 周期偏移阈值
        rTperiodDeviation1 = P.CANInfo.TperiodDeviation1_pct  # 20ms以内周期报文偏移范围，典型值20%；
        rTperiodDeviation2 = P.CANInfo.TperiodDeviation2_pct  # 20ms以上周期报文偏移范围，典型值10%
        rTperiodDeviation3 = P.CANInfo.TperiodDeviation3_pct  # 总线中负载通信速率下，20ms以内周期报文偏移范围，典型值30%
        rTperiodDeviation4 = P.CANInfo.TperiodDeviation4_pct  # 总线中负载通信速率下，20ms以上周期报文偏移范围，典型值20%

        # 测试环境设置
        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{rTstable}时间至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", "", "期望结果：DUT通信正常。实际结果：电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.clear_messages()
        ctx.can.set_filter_by_channel(DEFAULT_CAN_CHANNELS[0])
        #不要的id
        ctx.can.add_black_id(1)
        ctx.can.add_black_id(0x7FF)
        if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
            TestLog("FAIL", "测试结束", "实际: 存在错误帧; 期望: 无错误帧")
            return
        # Step2 ：
        TestLog("INFO", "Step2",
                f"模拟发送最高优先级报文(ID=0x001)，使总线负载达到Busload_medium以上，持续监控总线5分钟， 记录在这期间DUT发送的所有报文及对应的最大周期")
        # 创建CAN报文
        msg1 = canmsg_create(0x001, 8, data=0x3C, rtr=0, fdf=1, brs=0, ext=0)
        tids = []
        start_time = time.time()
        while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) < rBusloadNormal:
            if time.time() - start_time > 2 * 60:
                busload = sl_busstatis().get_can_stat_by_ch(can_channel)
                busload_min = round(busload.get("busload", {}).get("min") * 100, 2)
                busload_cur = round(busload.get("busload", {}).get("cur") * 100, 2)
                busload_max = round(busload.get("busload", {}).get("max") * 100, 2)
                busload_avg = round(busload.get("busload", {}).get("avg") * 100, 2)
                TestLog("FAIL", "", f"期望结果：总线负载达到{rBusloadNormal}。实际结果：2min总线负载未达到{rBusloadNormal}，busload_min={busload_min},busload_max={busload_max},busload_avg={busload_avg},busload_cur={busload_cur}")
                return

            TimerCyclic.start(timer_id, 5, send_canmsg, can_channel, msg=msg1)  # 10ms周期发送msg1
            tids.append(timer_id)
            timer_id += 1
            time.sleep(5)

        busload = sl_busstatis().get_can_stat_by_ch(can_channel)
        busload_cur = round(busload.get("busload", {}).get("cur") * 100, 2)
        busload_min = round(busload.get("busload", {}).get("min") * 100, 2)
        busload_max = round(busload.get("busload", {}).get("max") * 100, 2)
        busload_avg = round(busload.get("busload", {}).get("avg") * 100, 2)
        TestLog("INFO", "", f"busload_min={busload_min},busload_max={busload_max},busload_avg={busload_avg},,busload_cur={busload_cur}")


        # 持续监控总线5分钟
        sl_time().sleep(2 * 60 * 1000)

        # 停止发送报文
        for t in tids:
            TimerCyclic.stop(t)
        tids.clear()

        TestLog("INFO", "Step3", f"停止模拟发送高优先级报文，等待10s")
        sl_time().sleep(10 * 1000)
        if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
            TestLog("FAIL"," ", "实际: 存在错误帧; 期望: 无错误帧")
            return

        messages = ctx.can.messages
        rx_stats = build_rx_msg_info(messages)
        TestLog("INFO", "Step3", f"监控完成，共接收到 {len(rx_stats)} 种不同ID的报文")

        # Step3: 分析周期偏移结果
        TestLog("INFO", "Step3", "分析报文周期偏移")
        can_db_msg_defs = ctx.can.get_info('can_db_msg_defs') or {}
        MsgReceivedList, MsgNotReceivedList, MsgTmpList = analyze_messages(
            rx_stats,
            can_db_msg_defs,
        )

        # Step4: 周期偏移比较和测试结果输出
        TestLog("INFO", "Step3", "周期偏移比较和测试结果")

        report_message_tests(
            MsgReceivedList,
            MsgNotReceivedList,
            MsgTmpList,
            rx_stats,
            can_db_msg_defs,
            tests=("period",),
            period_thresholds=(rTperiodDeviation3, rTperiodDeviation4),
        )

        TestLog("INFO", "Step4",
                f"模拟发送最低优先级报文(ID=0x7FF)，使总线负载达到Busload_medium以上，持续监控总线5分钟， 记录在这期间DUT发送的所有报文及对应的最大周期")
        msg2 = canmsg_create(0x7FF, 8, data=0x3C, rtr=0, fdf=1, brs=0, ext=0)
        start_time = time.time()
        while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) < rBusloadNormal:
            if time.time() - start_time > 2 * 60:
                busload = sl_busstatis().get_can_stat_by_ch(can_channel)
                busload_min = round(busload.get("busload", {}).get("min") * 100, 2)
                busload_cur = round(busload.get("busload", {}).get("cur") * 100, 2)
                busload_max = round(busload.get("busload", {}).get("max") * 100, 2)
                busload_avg = round(busload.get("busload", {}).get("avg") * 100, 2)
                TestLog("FAIL", "",
                        f"期望结果：总线负载达到{rBusloadNormal}。实际结果：2min总线负载未达到{rBusloadNormal}，busload_min={busload_min},busload_max={busload_max},busload_avg={busload_avg},busload_cur={busload_cur}")
                return

            TimerCyclic.start(timer_id, 5, send_canmsg, can_channel, msg=msg2)  # 10ms周期发送msg1
            tids.append(timer_id)
            timer_id += 1
            time.sleep(5)

        busload = sl_busstatis().get_can_stat_by_ch(can_channel)
        busload_min = round(busload.get("busload", {}).get("min") * 100, 2)
        busload_max = round(busload.get("busload", {}).get("max") * 100, 2)
        busload_avg = round(busload.get("busload", {}).get("avg") * 100, 2)
        TestLog("INFO", "", f"busload_min={busload_min},busload_max={busload_max},busload_avg={busload_avg},,busload_cur={busload_cur}")

        # 持续监控总线5分钟
        sl_time().sleep(5 * 60 * 1000)

        TestLog("INFO", "Step5", f"停止模拟发送高优先级报文")
        for t in tids:
            TimerCyclic.stop(t)
        tids.clear()

        if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
            TestLog("FAIL", "测试结束", "实际: 存在错误帧; 期望: 无错误帧")
            return

        messages = ctx.can.messages
        rx_stats = build_rx_msg_info(messages)
        TestLog("INFO", "Step5", f"监控完成，共接收到 {len(rx_stats)} 种不同ID的报文")

        # Step3: 分析周期偏移结果
        TestLog("INFO", "Step5", "分析报文周期偏移")
        can_db_msg_defs = ctx.can.get_info('can_db_msg_defs') or {}
        MsgReceivedList, MsgNotReceivedList, MsgTmpList = analyze_messages(
            rx_stats,
            can_db_msg_defs,
        )

        # Step4: 周期偏移比较和测试结果输出
        TestLog("INFO", "Step5", "周期偏移比较和测试结果")

        report_message_tests(
            MsgReceivedList,
            MsgNotReceivedList,
            MsgTmpList,
            rx_stats,
            can_db_msg_defs,
            tests=("period",),
            period_thresholds=(rTperiodDeviation1, rTperiodDeviation2),
        )

        TestLog("INFO", "总线中负载率监控测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "总线中负载率监控测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "总线中负载率监控测试", f"详细错误: {traceback.format_exc()}")
    finally:
        # 保险关定时器
        for t in tids:
            try:
                TimerCyclic.stop(t)
            except:
                pass

def test_TG2_TC14_DataLinkLayer_BusLoadHighRateMonitoringTest():
    """总线高负载率监控测试"""
    tids = []
    timer_id = 1
    try:
        # 测试参数
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rTdefaultWait = P.CANInfo.TdefaultWait_s
        rErrorMsgID = P.CANInfo.ErrorMsgID  # TODO 读取参数配置表
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rBusloadHigh = P.CANInfo.BusloadHigh_pct
        # 周期偏移阈值
        rTperiodDeviation1 = P.CANInfo.TperiodDeviation1_pct  # 20ms以内周期报文偏移范围，典型值20%；
        rTperiodDeviation2 = P.CANInfo.TperiodDeviation2_pct  # 20ms以上周期报文偏移范围，典型值10%
        rTperiodDeviation3 = P.CANInfo.TperiodDeviation3_pct  # 总线中负载通信速率下，20ms以内周期报文偏移范围，典型值30%
        rTperiodDeviation4 = P.CANInfo.TperiodDeviation4_pct  # 总线中负载通信速率下，20ms以上周期报文偏移范围，典型值20%

        # 测试环境设置
        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{rTstable}时间至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", "", "期望结果：DUT通信正常。实际结果：电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.clear_messages()
        ctx.can.set_filter_by_channel(DEFAULT_CAN_CHANNELS[0])
        # 不要的id
        ctx.can.add_black_id(1)
        ctx.can.add_black_id(0x7FF)

        sl_time().sleep(int(rTdefaultWait * 1000))
        if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
            TestLog("FAIL", "测试结束", "实际: 存在错误帧; 期望: 无错误帧")
            return
        # Step2
        TestLog("INFO", "Step2",
                f"模拟发送最高优先级报文(ID=0x001)，使总线负载达到Busload_high以上，持续监控总线5分钟， 记录在这期间DUT发送的所有报文及对应的最大周期")
        # 创建CANFD报文
        msg1 = canmsg_create(0x001, 8, data=0x3C, rtr=0, fdf=1, brs=0, ext=0)
        start_time = time.time()
        while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) < rBusloadHigh:
            if time.time() - start_time > 5 * 60:
                busload = sl_busstatis().get_can_stat_by_ch(can_channel)
                busload_min = round(busload.get("busload", {}).get("min") * 100, 2)
                busload_cur = round(busload.get("busload", {}).get("cur") * 100, 2)
                busload_max = round(busload.get("busload", {}).get("max") * 100, 2)
                busload_avg = round(busload.get("busload", {}).get("avg") * 100, 2)
                TestLog("FAIL", "",
                        f"期望结果：总线负载达到{rBusloadHigh}。实际结果：2min总线负载未达到{rBusloadHigh}，busload_min={busload_min},busload_max={busload_max},busload_avg={busload_avg},busload_cur={busload_cur}")
                return

            TimerCyclic.start(timer_id, 5, send_canmsg, can_channel, msg=msg1)  # 10ms周期发送msg1
            tids.append(timer_id)
            timer_id += 1
            time.sleep(5)

        busload = sl_busstatis().get_can_stat_by_ch(can_channel)
        busload_min = round(busload.get("busload", {}).get("min") * 100, 2)
        busload_cur = round(busload.get("busload", {}).get("cur") * 100, 2)
        busload_max = round(busload.get("busload", {}).get("max") * 100, 2)
        busload_avg = round(busload.get("busload", {}).get("avg") * 100, 2)
        TestLog("INFO", "", f"busload_min={busload_min},busload_max={busload_max},busload_avg={busload_avg},busload_cur={busload_cur}")

        # 持续监控总线5分钟
        sl_time().sleep(5 * 60 * 1000)

        TestLog("INFO", "Step3", f"停止模拟发送高优先级报文，等待10s")
        # 停止发送报文
        for t in tids:
            TimerCyclic.stop(t)
        tids.clear()
        time.sleep(10)

        if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
            TestLog("FAIL", "测试结束", "实际: 存在错误帧; 期望: 无错误帧")
            return
        messages = ctx.can.messages
        rx_stats = build_rx_msg_info(messages)
        TestLog("INFO", "Step3", f"监控完成，共接收到 {len(rx_stats)} 种不同ID的报文")

        TestLog("INFO", "Step3", "分析报文周期偏移")
        can_db_msg_defs = ctx.can.get_info('can_db_msg_defs') or {}
        MsgReceivedList, MsgNotReceivedList, MsgTmpList = analyze_messages(
            rx_stats,
            can_db_msg_defs,
        )

        # Step3: DUT发送的所有周期报文的最大周期均小于2倍数据库定义周期
        TestLog("INFO", "Step3", "DUT发送的所有周期报文的最大周期均小于2倍数据库定义周期")
        report_max_cycle_not_exceed_2x(
            MsgReceivedList,
            MsgNotReceivedList,
            MsgTmpList,
            rx_stats,
            can_db_msg_defs,
            include_names=False,
        )


        TestLog("INFO", "Step4",
                f"模拟发送最低优先级报文(ID=0x7FF)，使总线负载达到Busload_high以上，持续监控总线5分钟， 记录在这期间DUT发送的所有报文及对应的最大周期")

        msg2 = canmsg_create(0x7FF, 8, data=0x3C, rtr=0, fdf=1, brs=0, ext=0)
        start_time = time.time()
        while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) < rBusloadHigh:
            if time.time() - start_time > 5 * 60:
                busload = sl_busstatis().get_can_stat_by_ch(can_channel)
                busload_min = round(busload.get("busload", {}).get("min") * 100, 2)
                busload_cur = round(busload.get("busload", {}).get("cur") * 100, 2)
                busload_max = round(busload.get("busload", {}).get("max") * 100, 2)
                busload_avg = round(busload.get("busload", {}).get("avg") * 100, 2)
                TestLog("FAIL", "",
                        f"期望结果：总线负载达到{rBusloadHigh}。实际结果：2min总线负载未达到{rBusloadHigh}，busload_min={busload_min},busload_max={busload_max},busload_avg={busload_avg},busload_cur={busload_cur}")
                return

            TimerCyclic.start(timer_id, 5, send_canmsg, can_channel, msg=msg2)  # 10ms周期发送msg1
            tids.append(timer_id)
            timer_id += 1
            time.sleep(5)

        busload = sl_busstatis().get_can_stat_by_ch(can_channel)
        busload_min = round(busload.get("busload", {}).get("min") * 100, 2)
        busload_max = round(busload.get("busload", {}).get("max") * 100, 2)
        busload_avg = round(busload.get("busload", {}).get("avg") * 100, 2)
        TestLog("INFO", "", f"busload_min={busload_min},busload_max={busload_max},busload_avg={busload_avg},busload_cur={busload_cur}")

        # 持续监控总线5分钟
        sl_time().sleep(5 * 60 * 1000)

        TestLog("INFO", "Step5", f"停止模拟发送高优先级报文")
        # 停止发送报文
        for t in tids:
            TimerCyclic.stop(t)
            time.sleep(1)
        tids.clear()
        if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
            TestLog("FAIL", "测试结束", "实际: 存在错误帧; 期望: 无错误帧")
            return

        messages = ctx.can.messages
        rx_stats = build_rx_msg_info(messages)
        TestLog("INFO", "Step5", f"监控完成，共接收到 {len(rx_stats)} 种不同ID的报文")

        # Step3: 分析周期偏移结果
        TestLog("INFO", "Step5", "分析报文周期偏移")
        can_db_msg_defs = ctx.can.get_info('can_db_msg_defs') or {}
        MsgReceivedList, MsgNotReceivedList, MsgTmpList = analyze_messages(
            rx_stats,
            can_db_msg_defs,
        )

        # Step4: 周期偏移比较和测试结果输出
        TestLog("INFO", "Step5", "周期偏移比较和测试结果")

        report_message_tests(
            MsgReceivedList,
            MsgNotReceivedList,
            MsgTmpList,
            rx_stats,
            can_db_msg_defs,
            tests=("period",),
            period_thresholds=(rTperiodDeviation1, rTperiodDeviation2),
        )

        TestLog("INFO", "总线高负载率监控测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "总线高负载率监控测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "总线高负载率监控测试", f"详细错误: {traceback.format_exc()}")
    finally:
        # 保险关定时器
        for t in tids:
            try:
                TimerCyclic.stop(t)
            except:
                pass

def test_TG2_TC17_VoltageJumpRecoveryCommunicationDiagnosticStrategyTest():
    """
    电压跳变恢复后通信诊断策略测试
    """
    try:
        V_normal = P.CANInfo.Vnormal
        V_low_stand = P.CANInfo.VlowStand
        V_high_stand = P.CANInfo.VhighStand
        T_stable = P.CANInfo.Tstable_s
        T_vStepDelay = P.CANInfo.TvStepDelay_ms
        rTperiodDeviation1 = P.CANInfo.TperiodDeviation1_pct
        rTperiodDeviation2 = P.CANInfo.TperiodDeviation2_pct
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{V_normal}V，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{T_stable}s时间至通信稳定")
        ret = can_power_setup_and_communication_check(V_normal, T_stable)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败，结束测试")
            return

        if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
            TestLog("FAIL", "Step1", "期望结果：DUT通信正常，无错误帧。实际结果：存在错误帧")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常，无错误帧。实际结果：DUT通信正常，无错误帧")

        can_db_msg_defs = ctx.can.get_info('can_db_msg_defs') or {}

        TestLog("INFO", "Step2",
                f"设置DUT的供电电压到{V_low_stand}V，等待{T_vStepDelay}ms时间后，设置DUT的供电电压恢复到{V_normal}V，持续监控总线5分钟")

        ctx.can.clear_messages()
        ctx.can.set_filter_by_channel(can_channel)

        ctx.power_ctrl.set_voltage(V_low_stand)
        sl_time().sleep(T_vStepDelay)
        ctx.power_ctrl.set_voltage(V_normal)
        sl_time().sleep(5 * 60 * 1000)

        if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
            TestLog("FAIL", "Step2", "期望结果：总线无错误帧。实际结果：存在错误帧")
        else:
            TestLog("PASS", "Step2", "期望结果：总线无错误帧。实际结果：总线无错误帧")

        messages = ctx.can.messages
        rx_stats = build_rx_msg_info(messages)
        TestLog("INFO", "Step2", f"监控完成，共接收到 {len(rx_stats)} 种不同ID的报文")

        MsgReceivedList, MsgNotReceivedList, MsgTmpList = analyze_messages(rx_stats, can_db_msg_defs)

        report_message_tests(
            MsgReceivedList,
            MsgNotReceivedList,
            MsgTmpList,
            rx_stats,
            can_db_msg_defs,
            tests=("period",),
            period_thresholds=(rTperiodDeviation1, rTperiodDeviation2),
        )

        TestLog("INFO", "Step3",
                f"设置DUT的供电电压到{V_high_stand}V，等待{T_vStepDelay}ms时间后，设置DUT的供电电压恢复到{V_normal}V，持续监控总线5分钟")

        ctx.can.clear_messages()
        ctx.power_ctrl.set_voltage(V_high_stand)
        sl_time().sleep(T_vStepDelay)
        ctx.power_ctrl.set_voltage(V_normal)
        sl_time().sleep(5 * 60 * 1000)

        if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
            TestLog("FAIL", "Step3", "期望结果：总线无错误帧。实际结果：存在错误帧")
        else:
            TestLog("PASS", "Step3", "期望结果：总线无错误帧。实际结果:总线无错误帧")

        messages = ctx.can.messages
        rx_stats = build_rx_msg_info(messages)
        TestLog("INFO", "Step3", f"监控完成，共接收到 {len(rx_stats)} 种不同ID的报文")

        MsgReceivedList, MsgNotReceivedList, MsgTmpList = analyze_messages(rx_stats, can_db_msg_defs)

        report_message_tests(
            MsgReceivedList,
            MsgNotReceivedList,
            MsgTmpList,
            rx_stats,
            can_db_msg_defs,
            tests=("period",),
            period_thresholds=(rTperiodDeviation1, rTperiodDeviation2),
        )

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "电压跳变恢复后通信诊断策略测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "电压跳变恢复后通信诊断策略测试", f"详细错误: {traceback.format_exc()}")

def test_TG3_TC1_InteractionLayer_MessageIDTest():
    """
    报文ID测试
    """
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        #电源设置与通信检查
        TestLog("INFO", "Step1", f"设置DUT电源电压为{rVnormal}，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{rTstable_s}时间至通信稳定")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        # ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, 20)
        if ret != 0:
            TestLog("INFO", "报文ID测试", "结束测试")
            return

        # Step2: 持续监控总线1分钟，记录在此期间接收到的所有报文ID
        TestLog("INFO", "Step2", "持续监控总线 1min 时间，记录在此期间接收到的所有报文ID")
        ctx.can.clear_messages()
        ctx.can.set_filter_by_channel(DEFAULT_CAN_CHANNELS[0])
        ctx.can.set_info('gErrorFrameCount', 0)
        TestLog("INFO", "Step2", "等待60秒收集报文...")
        sl_time().sleep(60 * 1000)

        messages = ctx.can.messages
        rx_stats = build_rx_msg_info(messages)
        TestLog("INFO", "Step2", f"监控完成，共接收到 {len(rx_stats)} 种不同ID的报文")

        # Step3: 分析报文
        TestLog("INFO", "Step2", "分析报文")
        can_db_msg_defs = ctx.can.get_info('can_db_msg_defs') or {}
        MsgReceivedList, MsgNotReceivedList, MsgTmpList = analyze_messages(
            rx_stats,
            can_db_msg_defs,
        )

        # Step4: 输出测试结果
        TestLog("INFO", "Step2", "测试结果")
        report_message_tests(
            MsgReceivedList,
            MsgNotReceivedList,
            MsgTmpList,
            rx_stats,
            can_db_msg_defs,
            tests=("id",),
            include_names=True,
        )

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")

def test_TG3_TC2_InteractionLayer_MessageDLCTest():
    """
    报文DLC测试
    """

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{rTstable_s}时间至通信稳定")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        if ret != 0:
            TestLog("INFO", "报文DLC测试", "结束测试")
            return

        # Step2: 持续监控总线1分钟，记录在此期间接收到的所有报文ID
        TestLog("INFO", "Step2", "持续监控总线 1min 时间，记录在此期间接收到的所有报文ID及DLC")
        ctx.can.clear_messages()
        ctx.can.set_filter_by_channel(DEFAULT_CAN_CHANNELS[0])
        ctx.can.set_info('gErrorFrameCount', 0)

        TestLog("INFO", "Step2", "等待60秒收集报文...")
        time.sleep(60)

        messages = ctx.can.messages
        rx_stats = build_rx_msg_info(messages)
        TestLog("INFO", "Step2", f"监控完成，共接收到 {len(rx_stats)} 种不同ID的报文")

        # Step3: 分析报文接收结果
        TestLog("INFO", "Step3", "分析报文DLC")
        can_db_msg_defs = ctx.can.get_info('can_db_msg_defs') or {}
        MsgReceivedList, MsgNotReceivedList, MsgTmpList = analyze_messages(
            rx_stats,
            can_db_msg_defs,
        )

        # Step4: 输出测试结果
        TestLog("INFO", "Step4", "测试结果")
        report_message_tests(
            MsgReceivedList,
            MsgNotReceivedList,
            MsgTmpList,
            rx_stats,
            can_db_msg_defs,
            tests=("dlc",),
        )

        TestLog("INFO", "报文DLC测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "报文DLC测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "报文DLC测试", f"详细错误: {traceback.format_exc()}")

def test_TG3_TC3_InteractionLayer_MessagePeriodDeviationTest():
    """
    报文周期偏移测试
    """
    try:

        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        rTperiodDeviationDelay = P.CANInfo.TperiodDeviationDelay_min  # 分钟
        # 周期偏移阈值
        rTperiodDeviation1 = P.CANInfo.TperiodDeviation1_pct  # 周期<=20ms的报文偏移阈值(%)
        rTperiodDeviation2 = P.CANInfo.TperiodDeviation2_pct  # 周期>20ms的报文偏移阈值(%)
        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{rTstable_s}时间至通信稳定")
        ret = can_power_setup_and_communication_check(P.CANInfo.Vnormal, P.CANInfo.Tstable_s)
        if ret != 0:
            TestLog("INFO", "报文DLC测试", "结束测试")
            return

        # Step2: 持续监控总线指定时间，记录周期信息
        TestLog("INFO", "Step2", f"持续监控总线 {rTperiodDeviationDelay}min 时间")
        ctx.can.clear_messages()
        ctx.can.set_filter_by_channel(DEFAULT_CAN_CHANNELS[0])
        ctx.can.set_info('gErrorFrameCount', 0)

        TestLog("INFO", "Step2", f"等待{rTperiodDeviationDelay * 60}秒收集报文周期信息...")
        time.sleep(rTperiodDeviationDelay * 60)

        messages = ctx.can.messages
        rx_stats = build_rx_msg_info(messages)
        TestLog("INFO", "Step2", f"监控完成，共接收到 {len(rx_stats)} 种不同ID的报文")
        stats = get_all_id_time(messages)
        for can_id, (tmin, tmax, tavg) in stats.items():
            TestLog("INFO","",f"0x{can_id:x}: Tmin={tmin}, Tmax={tmax}, Tavg={tavg:.1f}")

        # Step3: 分析周期偏移结果
        TestLog("INFO", "Step3", "分析报文周期偏移")
        can_db_msg_defs = ctx.can.get_info('can_db_msg_defs') or {}
        MsgReceivedList, MsgNotReceivedList, MsgTmpList = analyze_messages(
            rx_stats,
            can_db_msg_defs,
        )

        # Step4: 周期偏移比较和测试结果输出
        TestLog("INFO", "Step2", "周期偏移比较和测试结果")
        report_message_tests(
            MsgReceivedList,
            MsgNotReceivedList,
            MsgTmpList,
            rx_stats,
            can_db_msg_defs,
            tests=("period",),
            period_thresholds=(rTperiodDeviation1, rTperiodDeviation2),
        )

        TestLog("INFO", "报文周期偏移测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "报文周期偏移测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "报文周期偏移测试", f"详细错误: {traceback.format_exc()}")

def test_TG3_TC4_InteractionLayer_SignalInitialTest():
    """
    信号初始值测试
    """
    from common.signal_parser import sig
    from common.db_parser import sigdb

    try:
        rTinitial = P.CANInfo.Tinitial_s
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        # Step1: KL30上电，等待DUT进入休眠状态
        TestLog("INFO", "Step1", f"设置电压{rVnormal}V，KL30上电，等待DUT休眠")
        ctx.bob_ctrl.set_power('KL30', True)
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL15', False)
        time.sleep(rTstable)

        ctx.can.clear_messages()
        time.sleep(2)
        if len(ctx.can.messages) == 0:
            TestLog("PASS", "Step1", "期望结果：总线无报文。实际结果：总线无报文")
        else:
            TestLog("WARNING", "Step1", f"总线仍有报文，DUT可能未完全休眠")

        # Step2: 持续监控总线指定时间，记录周期信息
        TestLog("INFO", "Step2", f"唤醒网络，监控总线 {rTinitial}min")
        ctx.can.clear_messages()
        sig.clear()
        WakeupStart()
        time.sleep(rTinitial * 60)

        messages = ctx.can.messages
        first_msg_by_id = {}
        for m in messages:
            msg_id = getattr(m, 'id', None)
            if msg_id is not None and msg_id not in first_msg_by_id:
                first_msg_by_id[msg_id] = m

        TestLog("INFO", "Step2", f"收到 {len(messages)} 条报文，{len(first_msg_by_id)} 个不同ID")
        sig.load_messages(list(first_msg_by_id.values()))

        TestLog("INFO", "Step3", "从数据库中选取1个信号，比较数据库中定义的信号初始值和接收到的报文信号值")
        pass_count, fail_count, warning_count, skip_count = 0, 0, 0, 0

        tx_signal_names = sigdb.ecu_tx_signal_names()
        TestLog("INFO", "信号初始值", f"ECU TX信号数量: {len(tx_signal_names)}")

        for signal_name in tx_signal_names:
            sig_def = sigdb.get_signal_def(signal_name)
            if sig_def is None:
                continue

            msg_def = sigdb.get_msg_def(sig_def.msg_id)
            if msg_def and msg_def.get('cycle', 0) == 0:
                skip_count += 1
                continue

            sig_accessor = getattr(sig, signal_name)
            init_value = sig_def.init_value
            first_value = sig_accessor[0]

            if first_value is None:
                TestLog("WARNING", "信号初始值",
                        f"{signal_name} (0x{sig_def.msg_id:X}): 未收到数据")
                warning_count += 1
            elif abs(first_value.phy - init_value) <= (abs(init_value) * 0.001 or 0.001):
                TestLog("PASS", "信号初始值", f"(0x{sig_def.msg_id:X}),{signal_name}: 实际结果={first_value.phy}, 期望结果={init_value}")
                pass_count += 1
            else:
                TestLog("FAIL", "信号初始值", f"(0x{sig_def.msg_id:X}),{signal_name}: 实际结果={first_value.phy}, 期望结果={init_value}")
                fail_count += 1

        TestLog("INFO", "Step4", f"通过:{pass_count} 失败:{fail_count} 未收到:{warning_count} 跳过(非周期):{skip_count}")
        if fail_count == 0:
            TestLog("PASS", "信号初始值测试", "所有信号初始值验证通过")
        else:
            TestLog("FAIL", "信号初始值测试", f"{fail_count}个信号初始值不符合预期")

        TestLog("INFO", "Step5", "断开唤醒源，等待DUT休眠")
        WakeupStop()
        time.sleep(rTstable)

    except Exception as e:
        TestLog("FAIL", "信号初始值测试", f"测试出错: {e}")
        TestLog("DEBUG", "信号初始值测试", f"详细错误: {traceback.format_exc()}")

def test_TG3_TC5_InteractionLayer_UnuseBitValueTest():
    """
    未使用位填充测试
    """
    from common.signal_parser import sig
    from common.db_parser import sigdb

    TAG = "未使用位填充测试"

    try:
        rTinitial = P.CANInfo.Tinitial_min
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        expected_value = getattr(P.CANInfo, 'UnuseBitValue', 0x00) or 0x00

        # Step1: KL30上电，等待DUT进入休眠状态
        TestLog("INFO", "Step1", f"设置电压{rVnormal}V，KL30上电，等待DUT休眠")
        ctx.bob_ctrl.set_power('KL30', True)
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL15', False)
        time.sleep(rTstable)

        ctx.can.clear_messages()
        time.sleep(2)
        if len(ctx.can.messages) == 0:
            TestLog("PASS", "Step1", "期望结果：总线无报文，DUT已休眠。实际结果：总线无报文，DUT已休眠")
        else:
            TestLog("WARNING", "Step1", f"总线仍有报文，DUT可能未完全休眠")

        TestLog("INFO", "Step2", f"唤醒网络，监控总线 {rTinitial}min")
        ctx.can.clear_messages()
        sig.clear()
        WakeupStart()
        time.sleep(rTinitial * 60)

        first_msg_by_id = {}
        for m in ctx.can.messages:
            if hasattr(m, 'id') and m.id not in first_msg_by_id:
                first_msg_by_id[m.id] = m
        TestLog("INFO", "Step2", f"收到 {len(ctx.can.messages)} 条报文，{len(first_msg_by_id)} 个不同ID")

        TestLog("INFO", "Step3", f"遍历 ECU TX周期报文，检查未使用位填充值(期望0x{expected_value:02X})")
        pass_cnt, fail_cnt, warn_cnt = 0, 0, 0

        for msg_id in sigdb.ecu_tx_msg_ids():
            msg_def = sigdb.get_msg_def(msg_id)
            name = msg_def.get('name', f'0x{msg_id:X}') if msg_def else f'0x{msg_id:X}'
            unused_bits = sigdb.get_unused_bits(msg_id)

            if not unused_bits:
                continue

            cycle = msg_def.get('cycle', 0) if msg_def else 0
            if cycle == 0:
                continue

            if msg_id not in first_msg_by_id:
                TestLog("WARNING", TAG, f"0x{msg_id:X}'), {name}: 未收到报文")
                warn_cnt += 1
                continue

            msg = first_msg_by_id[msg_id]
            payload_hex = getattr(msg, 'payload_hex', None) or getattr(msg, 'data', None)
            if not payload_hex:
                TestLog("WARNING", TAG, f"0x{msg_id:X}') ,{name}: 无法获取数据")
                warn_cnt += 1
                continue

            try:
                data = bytes.fromhex(payload_hex.replace(' ', ''))
            except (ValueError, AttributeError):
                TestLog("WARNING", TAG, f"{name}: 数据格式错误")
                warn_cnt += 1
                continue

            ok, bad_bits = sigdb.check_unused_bits_value(msg_id, data, expected_value)
            if ok:
                TestLog("PASS", TAG, f"期望结果：0x{msg_id:X}'), {name}: {len(unused_bits)}个未使用位填充正确，实际结果：0x{msg_id:X}'), {name}: {len(unused_bits)}个未使用位填充正确")
                pass_cnt += 1
            else:
                TestLog("FAIL", TAG, f"期望结果：0x{msg_id:X}'), {name}: {len(unused_bits)}个未使用位填充正确，实际结果：0x{msg_id:X}'), {name}: 填充错误(期望0x{expected_value:02X}), 元组里第一位是byte位，第二位是bit位：{bad_bits = }")
                fail_cnt += 1

        TestLog("INFO", "Step4", f"通过:{pass_cnt} 失败:{fail_cnt} 未收到:{warn_cnt}")
        if fail_cnt == 0:
            TestLog("PASS" if warn_cnt == 0 else "WARNING", TAG,
                    "验证通过" if warn_cnt == 0 else f"已收到报文验证通过，{warn_cnt}个未收到")
        else:
            TestLog("FAIL", TAG, f"{fail_cnt}个报文未使用位填充不符")

        TestLog("INFO", "Step5", "断开唤醒源，等待DUT休眠")
        WakeupStop()
        time.sleep(rTstable)

    except Exception as e:
        TestLog("FAIL", TAG, f"测试出错: {e}")
        import traceback
        TestLog("DEBUG", TAG, traceback.format_exc())

def test_TG3_TC6_InteractionLayer_ReceiveMessageTest():
    """
    接收报文测试
    """
    from .can_module import _load_and_parse_database
    from common.db_parser import sigdb

    active_timer_ids = []

    try:
        rTreceiveMsgDelay = P.CANInfo.TreceiveMsgDelay_min
        can_channel = DEFAULT_CAN_CHANNELS[0]
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{rTstable_s}时间至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "接收报文测试", "电源设置与通信检查失败，结束测试")
            return

        ecu_rx_msg_defs = _load_and_parse_database(msg_type='rx')
        if not ecu_rx_msg_defs:
            TestLog("WARNING", "接收报文测试", "未从数据库获取到ECU RX报文定义，跳过仿真发送")
        else:
            TestLog("INFO", "接收报文测试", f"从数据库获取到 {len(ecu_rx_msg_defs)} 个ECU RX报文定义")

        ctx.can.clear_messages()
        ctx.can.set_filter_by_channel(DEFAULT_CAN_CHANNELS[1])
        ctx.can.set_info('gErrorFrameCount', 0)
        TestLog("INFO", "Step2", f"仿真发送接收节点为DUT的所有报文，持续{rTreceiveMsgDelay}min，监控总线通信状态")

        unused_bit_value = getattr(P.CANInfo, 'UnuseBitValue', 0x00) or 0x00

        timer_id_base = 1000
        for idx, (msg_id, msg_info) in enumerate(ecu_rx_msg_defs.items()):
            try:
                msg_dlc = msg_info.get('dlc', 8)
                msg_cycle = msg_info.get('cycle', 0)
                msg_name = msg_info.get('name', f'Unknown_{msg_id:x}')
                is_canfd = msg_info.get('is_fd', False) or msg_info.get('fdf', False)
                brs = msg_info.get('brs', False)

                if msg_cycle <= 0:
                    TestLog("DEBUG", "仿真发送", f"跳过报文 0x{msg_id:x} ({msg_name})，周期为0")
                    continue

                period_ms = msg_cycle

                msg_data = sigdb.encode_msg_with_init_values(msg_id, unused_bit_value)

                msg = canmsg_create(
                    msg_id,
                    msg_dlc,
                    data=msg_data,
                    rtr=0,
                    fdf=1 if is_canfd else 0,
                    brs=1 if (is_canfd and brs) else 0,
                    ext=0
                )

                if msg is None:
                    TestLog("WARNING", "报文创建", f"创建报文 0x{msg_id:x} ({msg_name}) 失败")
                    continue

                timer_id = timer_id_base + idx
                ret = TimerCyclic.start(timer_id, period_ms, send_canmsg, can_channel, msg=msg)
                if ret:
                    active_timer_ids.append(timer_id)
                    TestLog("DEBUG", "仿真发送", f"启动报文 0x{msg_id:x} ({msg_name}) 周期发送，周期={period_ms}ms")
                else:
                    TestLog("WARNING", "仿真发送", f"启动报文 0x{msg_id:x} ({msg_name}) 定时器失败")

            except Exception as e:
                TestLog("WARNING", "仿真发送", f"处理报文 0x{msg_id:x} 时出错: {e}")

        TestLog("INFO", "仿真发送", f"已启动 {len(active_timer_ids)} 个报文的周期发送")

        time.sleep(rTreceiveMsgDelay * 60)

        error_count = ctx.can.get_info('gErrorFrameCount') or 0
        if error_count == 0:
            TestLog("PASS", "",
                    "期望结果：仿真发送DUT接收的所有报文，DUT通信正常，无错误帧。实际结果：仿真发送DUT接收的所有报文，DUT通信正常，无错误帧")
        else:
            TestLog("FAIL", "", f"实际: 存在 {error_count} 个错误帧; 期望: DUT通信正常，无错误帧")
            return

        TestLog("INFO", "Step3", "停止发送所有仿真报文")
        for timer_id in active_timer_ids:
            try:
                TimerCyclic.stop(timer_id)
            except Exception as e:
                TestLog("DEBUG", "停止定时器", f"停止定时器 {timer_id} 时出错: {e}")
        active_timer_ids.clear()
        TestLog("INFO", "接收报文测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "接收报文测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "接收报文测试", f"详细错误: {traceback.format_exc()}")
    finally:
        for timer_id in active_timer_ids:
            try:
                TimerCyclic.stop(timer_id)
            except Exception:
                pass

def test_TG3_TC7_ExpectedFrameReceiveTest():
    """
    预期帧接收测试
    """
    from .can_module import _load_and_parse_database

    active_timer_ids = []

    try:
        rTreceiveMsgDelay = P.CANInfo.TreceiveMsgDelay_min
        can_channel = DEFAULT_CAN_CHANNELS[0]
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{rTstable_s}s时间至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "预期帧接收测试", "电源设置与通信检查失败，结束测试")
            return

        all_msg_defs = _load_and_parse_database(msg_type='all')
        ecu_tx_msg_defs = _load_and_parse_database(msg_type='tx')

        other_node_msg_defs = {msg_id: msg_info for msg_id, msg_info in all_msg_defs.items()
                               if msg_id not in ecu_tx_msg_defs}

        other_node_msg_defs = {msg_id: msg_info for msg_id, msg_info in other_node_msg_defs.items()
                               if msg_info.get('cycle', 0) > 0}

        if not other_node_msg_defs:
            TestLog("WARNING", "", "未从数据库获取到除DUT以外的其他节点周期报文定义，跳过测试")
            return

        TestLog("INFO", "", f"从数据库获取到 {len(other_node_msg_defs)} 个其他节点周期报文定义")

        ctx.can.clear_messages()
        ctx.can.set_filter_by_channel(can_channel)
        ctx.can.set_info('gErrorFrameCount', 0)

        TestLog("INFO", "Step2",
                f"仿真发送除DUT本身节点以外的所有节点的报文ID，持续{rTreceiveMsgDelay}min时间，监控总线通信状态")

        timer_id_base = 2000
        active_timer_ids = start_simulation_msgs(other_node_msg_defs, timer_id_base, can_channel)
        TestLog("INFO", "", f"已启动 {len(active_timer_ids)} 个报文的周期发送")

        sl_time().sleep(rTreceiveMsgDelay * 60 * 1000)

        no_error = check_bus_error_frames("Step2")

        TestLog("INFO", "Step3", "停止发送所有仿真报文")
        stop_simulation_msgs(active_timer_ids)
        active_timer_ids.clear()

        if no_error:
            TestLog("PASS", "预期帧接收测试", "DUT接收到其所在网段的所有报文时都能够正常通信，无错误帧产生")
        else:
            TestLog("FAIL", "预期帧接收测试", "DUT接收预期报文时存在错误帧")

    except Exception as e:
        TestLog("FAIL", "预期帧接收测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "预期帧接收测试", f"详细错误: {traceback.format_exc()}")
    finally:
        for timer_id in active_timer_ids:
            try:
                TimerCyclic.stop(timer_id)
            except Exception:
                pass

def test_TG3_TC8_UnexpectedFrameReceiveTest():
    """
    非预期帧接收测试
    """
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0]
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        extend_id = P.CANInfo.ExtendMsgID
        remote_id = P.CANInfo.RemoteMsgID
        extend_and_remote_id = P.CANInfo.ExtendandRemoteMsgID

        TestLog("INFO", "SubCase1", "扩展帧测试")

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{rTstable_s}s时间至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "", "SubCase1电源设置与通信检查失败")
            return

        if not check_bus_error_frames("SubCase1-Step1"):
            return

        TestLog("INFO", "Step2", "使用CANoe模拟节点发送报文，报文类型为扩展帧，其周期为10ms，持续发送1s时间")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)

        msg_ext = canmsg_create(extend_id, 8, data=0x55, rtr=0, fdf=0, brs=0, ext=1)
        timer_id_ext = 3001
        TimerCyclic.start(timer_id_ext, 10, send_canmsg, can_channel, msg=msg_ext)
        sl_time().sleep(1000)
        TimerCyclic.stop(timer_id_ext)

        no_error_ext = check_bus_error_frames("SubCase1-Step3")

        TestLog("INFO", "SubCase2", "远程帧测试")

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{rTstable_s}s时间至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "SubCase2电源设置与通信检查失败")
            return

        if not check_bus_error_frames("SubCase2-Step1"):
            return

        TestLog("INFO", "Step2", "使用CANoe模拟节点发送报文，报文类型为远程帧，其周期为10ms，持续发送1s时间")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)

        msg_rtr = canmsg_create(remote_id, 8, data=0x00, rtr=1, fdf=0, brs=0, ext=0)
        timer_id_rtr = 3002
        TimerCyclic.start(timer_id_rtr, 10, send_canmsg, can_channel, msg=msg_rtr)
        sl_time().sleep(1000)
        TimerCyclic.stop(timer_id_rtr)

        no_error_rtr = check_bus_error_frames("SubCase2-Step3")

        TestLog("INFO", "SubCase3", "扩展远程帧测试")

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{rTstable_s}s时间至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "非预期帧接收测试", "SubCase3电源设置与通信检查失败")
            return

        if not check_bus_error_frames("SubCase3-Step1"):
            return

        TestLog("INFO", "Step2", "使用CANoe模拟节点发送报文，报文类型为扩展远程帧，其周期为10ms，持续发送1s时间")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)

        msg_ext_rtr = canmsg_create(extend_and_remote_id, 8, data=0x00, rtr=1, fdf=0, brs=0, ext=1)
        timer_id_ext_rtr = 3003
        TimerCyclic.start(timer_id_ext_rtr, 10, send_canmsg, can_channel, msg=msg_ext_rtr)
        sl_time().sleep(1000)
        TimerCyclic.stop(timer_id_ext_rtr)

        no_error_ext_rtr = check_bus_error_frames("SubCase3-Step3")

        if no_error_ext and no_error_rtr and no_error_ext_rtr:
            TestLog("PASS", "",
                    "DUT接收扩展帧、远程帧、扩展远程帧的情况下，应能保持正常通信，无错误帧产生")
        else:
            TestLog("FAIL", "",
                    f"DUT接收非预期报文时存在错误帧，扩展帧:{not no_error_ext}，远程帧:{not no_error_rtr}，扩展远程帧:{not no_error_ext_rtr}")

    except Exception as e:
        TestLog("FAIL", "非预期帧接收测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "非预期帧接收测试", f"详细错误: {traceback.format_exc()}")

def test_TG3_TC9_EventMessageSendTest():
    """
    事件型报文发送测试
    """
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0]

        can_db_msg_defs = ctx.can.get_info('can_db_msg_defs') or {}
        event_msg_defs = {msg_id: msg_info for msg_id, msg_info in can_db_msg_defs.items()
                          if msg_info.get('cycle', 0) == 0}

        if not event_msg_defs:
            TestLog("WARNING", "", "DUT无事件型报文定义，此测试项跳过")
            return

        TestLog("INFO", "", f"检测到 {len(event_msg_defs)} 个事件型报文定义")

        TestLog("INFO", "SubCase1", "基本事件触发测试")

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{rTstable_s}s时间至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "事件型报文发送测试", "电源设置与通信检查失败，结束测试")
            return

        TestLog("PASS", "Step1", "期望结果：DUT正常发送应用报文。实际结果：DUT正常发送应用报文")

        TestLog("INFO", "Step2", "TODO: 模拟事件型报文的触发条件，触发该事件型报文发送")

        ctx.can.clear_messages()
        ctx.can.set_filter_by_channel(can_channel)
        TestLog("INFO", "Step3", "检测事件型报文的ID、DLC、重复发送次数nRepetitionE及重复时间间隔tRepetitionE")

        sl_time().sleep(5000)

        messages = ctx.can.messages
        event_msg_received = {}
        for m in messages:
            if m.id in event_msg_defs:
                if m.id not in event_msg_received:
                    event_msg_received[m.id] = []
                event_msg_received[m.id].append(m)

        for msg_id, msg_list in event_msg_received.items():
            msg_info = event_msg_defs.get(msg_id, {})
            expected_dlc = msg_info.get('dlc', 8)

            actual_dlc = msg_list[0].dlc if msg_list else 0
            if actual_dlc == expected_dlc:
                TestLog("PASS", "Step3", f"事件报文 0x{msg_id:x} DLC正确: 期望={expected_dlc}, 实际={actual_dlc}")
            else:
                TestLog("FAIL", "Step3", f"事件报文 0x{msg_id:x} DLC不正确: 期望={expected_dlc}, 实际={actual_dlc}")

            if len(msg_list) > 1:
                intervals = []
                for i in range(1, len(msg_list)):
                    interval = msg_list[i].time_ms - msg_list[i-1].time_ms
                    intervals.append(interval)
                avg_interval = sum(intervals) / len(intervals)
                TestLog("INFO", "Step3",
                        f"事件报文 0x{msg_id:x} 重复发送次数={len(msg_list)}, 平均重复间隔={avg_interval:.2f}ms")
            else:
                TestLog("INFO", "Step3", f"事件报文 0x{msg_id:x} 仅收到1次，无法计算重复间隔")

        if not event_msg_received:
            TestLog("WARNING", "SubCase1", "未检测到任何事件型报文，可能需要手动触发事件条件")

        TestLog("INFO", "SubCase2", "20ms后新事件触发测试 - 验证事件报文间隔不小于20ms")
        TestLog("WARNING", "SubCase2", "TODO: 此测试需要在接收到第一条事件型报文20ms后立即触发新事件，验证DUT是否发送新事件报文并丢弃上一个事件报文")

        TestLog("INFO", "SubCase3", "20ms内新事件触发测试 - 验证新事件报文推迟到20ms之后发送")
        TestLog("WARNING", "SubCase3", "TODO: 此测试需要在接收到第一条事件型报文后20ms内立即触发新事件，验证DUT是否推迟新事件报文到20ms之后发送")


    except Exception as e:
        TestLog("FAIL", "事件型报文发送测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "事件型报文发送测试", f"详细错误: {traceback.format_exc()}")

def test_TG3_TC10_CyclicEventMessageSendTest():
    """
    周期事件型报文发送测试
    """
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0]

        can_db_msg_defs = ctx.can.get_info('can_db_msg_defs') or {}
        cyclic_event_msg_defs = {msg_id: msg_info for msg_id, msg_info in can_db_msg_defs.items()
                                  if msg_info.get('cycle', 0) > 0 and msg_info.get('is_cyclic_event', False)}

        if not cyclic_event_msg_defs:
            TestLog("WARNING", "", "DUT无周期事件型报文定义，此测试项跳过")
            return

        TestLog("INFO", "周期事件型报文发送测试", f"检测到 {len(cyclic_event_msg_defs)} 个周期事件型报文定义")

        TestLog("INFO", "SubCase1", "基本周期事件触发测试")

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{rTstable_s}s时间至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "周期事件型报文发送测试", "电源设置与通信检查失败，结束测试")
            return

        TestLog("PASS", "Step1", "期望结果：DUT正常发送应用报文。实际结果：DUT正常发送应用报文")

        TestLog("INFO", "Step2", "模拟周期事件型报文的触发条件，触发该周期事件型报文发送")
        TestLog("WARNING", "Step2", "TODO: 周期事件型报文的触发条件依赖于具体DUT实现，需要根据实际情况手动触发或通过诊断指令触发")

        ctx.can.clear_messages()
        ctx.can.set_filter_by_channel(can_channel)
        TestLog("INFO", "Step3", "检测周期事件型报文的ID、DLC、重复发送次数nRepetitionCE及重复时间间隔tRepetitionCE")

        sl_time().sleep(5000)

        messages = ctx.can.messages
        ce_msg_received = {}
        for m in messages:
            if m.id in cyclic_event_msg_defs:
                if m.id not in ce_msg_received:
                    ce_msg_received[m.id] = []
                ce_msg_received[m.id].append(m)

        for msg_id, msg_list in ce_msg_received.items():
            msg_info = cyclic_event_msg_defs.get(msg_id, {})
            expected_dlc = msg_info.get('dlc', 8)
            expected_cycle = msg_info.get('cycle', 0)

            actual_dlc = msg_list[0].dlc if msg_list else 0
            if actual_dlc == expected_dlc:
                TestLog("PASS", "Step3", f"周期事件报文 0x{msg_id:x} DLC正确: 期望={expected_dlc}, 实际={actual_dlc}")
            else:
                TestLog("FAIL", "Step3", f"周期事件报文 0x{msg_id:x} DLC不正确: 期望={expected_dlc}, 实际={actual_dlc}")

            if len(msg_list) > 1:
                intervals = []
                for i in range(1, len(msg_list)):
                    interval = msg_list[i].time_ms - msg_list[i-1].time_ms
                    intervals.append(interval)
                avg_interval = sum(intervals) / len(intervals)
                TestLog("INFO", "Step3",
                        f"周期事件报文 0x{msg_id:x} 收到 {len(msg_list)} 帧, 平均间隔={avg_interval:.2f}ms, 期望周期={expected_cycle}ms")
            else:
                TestLog("INFO", "Step3", f"周期事件报文 0x{msg_id:x} 仅收到1帧")

        if not ce_msg_received:
            TestLog("WARNING", "SubCase1", "未检测到任何周期事件型报文")

        TestLog("INFO", "SubCase2", "事件触发后的快速发送测试")
        TestLog("WARNING", "SubCase2",
                "TODO :此测试验证事件触发后，周期事件型报文以tRepetitionCE间隔快速发送nRepetitionCE次，然后恢复正常周期发送")

    except Exception as e:
        TestLog("FAIL", "周期事件型报文发送测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "周期事件型报文发送测试", f"详细错误: {traceback.format_exc()}")

def test_TG3_TC11_RealVehicleLoadStressTest():
    """
    实车负载压力测试
    """
    from .can_module import _load_and_parse_database

    active_timer_ids = []
    test_repeat_count = P.CANInfo.Tcount

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0]

        all_msg_defs = _load_and_parse_database(msg_type='all')
        ecu_tx_msg_defs = _load_and_parse_database(msg_type='tx')
        other_node_msg_defs = {msg_id: msg_info for msg_id, msg_info in all_msg_defs.items()
                               if msg_id not in ecu_tx_msg_defs and msg_info.get('cycle', 0) > 0}

        if not other_node_msg_defs:
            TestLog("WARNING", "实车负载压力测试", "未从数据库获取到除DUT以外的其他节点周期报文定义，跳过测试")
            return

        TestLog("INFO", "实车负载压力测试", f"从数据库获取到 {len(other_node_msg_defs)} 个其他节点周期报文定义")

        TestLog("INFO", "SubCase1", "实车负载情况下，查看DUT的报文周期是否存在异常")
        subcase1_fail_count = 0

        for loop in range(test_repeat_count):
            TestLog("INFO", "SubCase1", f"第 {loop + 1}/{test_repeat_count} 次循环")
            ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
            if ret != 0:
                TestLog("FAIL", "SubCase1", f"第{loop + 1}次循环：电源设置与通信检查失败")
                subcase1_fail_count += 1
                continue

            ctx.can.clear_messages()
            ctx.can.set_filter_by_channel(can_channel)
            active_timer_ids = start_simulation_msgs(other_node_msg_defs, 4000, can_channel)
            TestLog("DEBUG", "SubCase1", f"已启动 {len(active_timer_ids)} 个报文的周期发送")

            sl_time().sleep(3 * 60 * 1000)

            stop_simulation_msgs(active_timer_ids)
            active_timer_ids.clear()

            ctx.bob_ctrl.set_power('KL15', False)
            sl_time().sleep(2000)
            ctx.bob_ctrl.set_power('KL15', True)
            sl_time().sleep(2000)

        if subcase1_fail_count == 0:
            TestLog("PASS", "SubCase1", f"实车负载下DUT报文周期测试完成，{test_repeat_count}次循环全部通过")
        else:
            TestLog("FAIL", "SubCase1", f"实车负载下DUT报文周期测试，{subcase1_fail_count}/{test_repeat_count}次失败")

        TestLog("INFO", "SubCase2", "实车负载情况下，发送诊断指令，是否会影响DUT报文周期")
        subcase2_fail_count = 0

        diag_commands = [
            bytes([0x22, 0xF1, 0x89]),  # 22F189
            bytes([0x22, 0xF1, 0x80]),  # 22F180
            bytes([0x22, 0xF1, 0x8A]),  # 22F18A
            bytes([0x22, 0xF1, 0x8C]),  # 22F18C
            bytes([0x14, 0xFF, 0xFF, 0xFF]),  # 14FFFFFF
            bytes([0x19, 0x02, 0x09]),  # 190209
        ]


        from testcases.can.can_diag_utils import CANBusSim
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rDiagFuncReqID = P.TpInfo.CAN_LIN_FuncReqID_int
        diag_bus = CANBusSim()
        diag_bus.init(can_channel, rDiagReqID, rDiagRespID, rDiagFuncReqID)

        for loop in range(test_repeat_count):
            TestLog("INFO", "SubCase2", f"第 {loop + 1}/{test_repeat_count} 次循环")

            ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
            if ret != 0:
                TestLog("FAIL", "SubCase2", f"第{loop + 1}次循环：电源设置与通信检查失败")
                subcase2_fail_count += 1
                continue

            ctx.can.clear_messages()
            ctx.can.set_filter_by_channel(can_channel)
            active_timer_ids = start_simulation_msgs(other_node_msg_defs, 5000, can_channel)

            sl_time().sleep(1000)

            for cmd in diag_commands:
                try:
                    diag_bus.send(cmd)
                    sl_time().sleep(100)
                except Exception as e:
                    TestLog("DEBUG", "SubCase2", f"发送诊断指令失败: {e}")

            sl_time().sleep(3 * 60 * 1000)

            stop_simulation_msgs(active_timer_ids)
            active_timer_ids.clear()

            ctx.bob_ctrl.set_power('KL15', False)
            sl_time().sleep(2000)
            ctx.bob_ctrl.set_power('KL15', True)
            sl_time().sleep(2000)

        diag_bus.close()

        if subcase2_fail_count == 0:
            TestLog("PASS", "SubCase2", f"实车负载+诊断指令测试完成，{test_repeat_count}次循环全部通过")
        else:
            TestLog("FAIL", "SubCase2", f"实车负载+诊断指令测试，{subcase2_fail_count}/{test_repeat_count}次失败")

        if subcase1_fail_count == 0 and subcase2_fail_count == 0:
            TestLog("PASS", "实车负载压力测试", "DUT在实车负载条件下能够正常通信")
        else:
            TestLog("FAIL", "实车负载压力测试", "DUT在实车负载条件下存在异常")

    except Exception as e:
        TestLog("FAIL", "实车负载压力测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "实车负载压力测试", f"详细错误: {traceback.format_exc()}")
    finally:
        stop_simulation_msgs(active_timer_ids)

def test_TG3_TC12_RandomSignalTest():
    """
    接收报文信号随机变化测试
    """
    from .can_module import _load_and_parse_database

    active_timer_ids = []
    test_repeat_count = P.CANInfo.Tcount

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0]

        all_msg_defs = _load_and_parse_database(msg_type='all')
        ecu_tx_msg_defs = _load_and_parse_database(msg_type='tx')
        other_node_msg_defs = {msg_id: msg_info for msg_id, msg_info in all_msg_defs.items()
                               if msg_id not in ecu_tx_msg_defs and msg_info.get('cycle', 0) > 0}

        if not other_node_msg_defs:
            TestLog("WARNING", "信号随机变化测试", "未从数据库获取到除DUT以外的其他节点周期报文定义，跳过测试")
            return

        TestLog("INFO", "信号随机变化测试", f"从数据库获取到 {len(other_node_msg_defs)} 个其他节点周期报文定义，重复{test_repeat_count}次")

        fail_count = 0

        TestLog("INFO", "Step1", "设置DUT电源电压为Vnormal，上电唤醒，等待Tstable时间至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败")
            return

        for loop in range(test_repeat_count):
            TestLog("INFO", f"Loop{loop + 1}", f"第 {loop + 1}/{test_repeat_count} 次循环")

            ctx.can.clear_messages()
            ctx.can.set_filter_by_channel(can_channel)
            ctx.can.set_info('gErrorFrameCount', 0)

            TestLog("INFO", "Step2", "仿真发送除DUT外的ID，信号值随机变化，周期按照矩阵周期发送")
            timer_id_base = 6000
            for idx, (msg_id, msg_info) in enumerate(other_node_msg_defs.items()):
                try:
                    msg_dlc = msg_info.get('dlc', 8)
                    msg_cycle = msg_info.get('cycle', 0)
                    if msg_cycle <= 0:
                        continue
                    is_canfd = msg_info.get('is_fd', False) or msg_info.get('fdf', False)
                    brs = msg_info.get('brs', False)

                    timer_id = timer_id_base + idx
                    ret = TimerCyclic.start(timer_id, msg_cycle, send_random_data_msg,
                                            can_channel, msg_id, msg_dlc, is_canfd, brs)
                    if ret:
                        active_timer_ids.append(timer_id)
                except Exception:
                    pass

            TestLog("INFO", "Step3", "检测报文周期是否正常，运行3分钟")
            sl_time().sleep(3 * 60 * 1000)

            for tid in active_timer_ids:
                try:
                    TimerCyclic.stop(tid)
                except Exception:
                    pass
            active_timer_ids.clear()

            error_count = ctx.can.get_info('gErrorFrameCount') or 0
            if error_count > 0:
                TestLog("FAIL", f"Loop{loop + 1}", f"存在 {error_count} 个错误帧")
                fail_count += 1

            TestLog("INFO", "Step4", "下电5s，重新上电等待2s")
            ctx.bob_ctrl.set_power('KL15', False)
            ctx.bob_ctrl.set_power('KL30', False)
            sl_time().sleep(5000)
            ctx.bob_ctrl.set_power('KL30', True)
            ctx.bob_ctrl.set_power('KL15', True)
            sl_time().sleep(2000)

        if fail_count == 0:
            TestLog("PASS", "信号随机变化测试", f"测试完成，{test_repeat_count}次循环全部通过，DUT通信正常")
        else:
            TestLog("FAIL", "信号随机变化测试", f"测试完成，{fail_count}/{test_repeat_count}次失败")

    except Exception as e:
        TestLog("FAIL", "信号随机变化测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "信号随机变化测试", f"详细错误: {traceback.format_exc()}")
    finally:
        for tid in active_timer_ids:
            try:
                TimerCyclic.stop(tid)
            except Exception:
                pass

def test_TG4_TC1_CAN_H_L_ShortPowerTest():
    """CAN_H/L短电源测试"""
    try:

        # 从配置文件获取测试参数
        V_normal = P.CANInfo.Vnormal  # 正常电压
        T_stable = P.CANInfo.Tstable_s  # 通信稳定时间(s)

        T_faultDelay = P.CANInfo.TfaultDelay_s   # 故障保持时间(s)
        T_faultRecoveryMax = P.CANInfo.TfaultRecoveryMax_ms  # 最大恢复时间(ms)
        N_faultRepeat = P.CANInfo.NfaultRepeat # 重复测试次数

        ctrl_can_channel = P.ECUInfo.BOBControlCan
        target_can_channel = P.ECUInfo.ETS6124CanChannel
        board_addr = P.ECUInfo.ETS6124Addr_int

        test_results = []
        overall_result = True
        ctx.can.set_filter_by_channel(DEFAULT_CAN_CHANNELS[0])
        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{V_normal}，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{T_stable}时间至通信稳定")
        ret = can_power_setup_and_communication_check(V_normal, T_stable)
        if ret != 0:
            TestLog("FAIL", "接收报文测试", "电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        # for round_num in range(1, N_faultRepeat + 1):
        for round_num in range(1, 2):
            # 步骤2-3: CAN_H短路测试
            TestLog("INFO", "", f"开始第{round_num}轮CAN_H对电源短路测试")

            TestLog("INFO", "Step2", f"制造CAN_H与电源短路故障，持续{T_faultDelay}时间")
            fault_result = can_fault_injection('CAN_H_short_power', target_can_channel,
                                               T_faultDelay * 1000)
            if not fault_result:
                TestLog("FAIL", "故障注入", "CAN_H对电源短路故障注入失败")
                return

            TestLog("INFO", "Step3", "移除故障，等待1s，监控总线通信状态")
            fault_result = can_clear_injection('CAN_H_short_power', target_can_channel)
            # 检查返回值类型
            if isinstance(fault_result, tuple) and len(fault_result) == 2:
                fault_success, t1 = fault_result
            else:
                fault_success = fault_result
                t1 = None
            if not fault_success:
                TestLog("FAIL", "故障注入", "CAN_H对电源短路故障故障清除失败")
                return
            TestLog("INFO", "故障注入", "CAN_H对电源短路故障已注入并自动清除")

            # 等待1s，监控总线通信状态
            time.sleep(1.0)

            # 检查DUT通信是否正常，总线无错误帧
            ret = check_can_communication_state(T_stable)
            if ret != 0:
                TestLog("FAIL", "CAN_H短电源测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信不正常，测试结束")
                overall_result = False
                return
            TestLog("PASS", "CAN_H短电源测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信正常，总线无错误帧")

            can_h_result = True

            # 步骤4-5: 重新进行电源设置（模拟KL30断电再上电）
            TestLog("INFO", "Step4", "执行KL30下电,等待2s")
            ctx.bob_ctrl.set_power('KL30', False)
            time.sleep(2.0)

            TestLog("INFO", "Step5", f"重新将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{T_stable}时间至通信稳定")
            ret = can_power_setup_and_communication_check(V_normal, T_stable)
            if ret != 0:
                TestLog("FAIL", "通信检查", "期望结果：DUT通信正常。实际结果:KL30重新上电后DUT通信异常")
                overall_result = False
                return
            TestLog("PASS", "通信检查", "期望结果：DUT通信正常。实际结果:DUT通信正常")

            # 步骤6-8: CAN_L短路测试
            TestLog("INFO", "Stpe6", f"制造CAN_L与电源短路故障，持续{T_faultDelay}时间")

            # 使用封装好的故障注入函数
            fault_result = can_fault_injection('CAN_L_short_power', target_can_channel,
                                               T_faultDelay * 1000)
            if not fault_result:
                TestLog("FAIL", "故障注入", "CAN_L对电源短路故障注入失败")
                return

            if (ctx.can.get_info('gErrorFrameCount') or 0) == 0:
                TestLog("FAIL", "测试结束", "实际: 不存在错误帧; 期望: 总线出现错误帧")
                overall_result = False
                return
            TestLog("PASS", "测试结束", "实际: 总线出现错误帧; 期望: 总线出现错误帧")

            TestLog("INFO", "Step7", f"移除故障，记录时刻t1，等待DUT恢复通信，记录时刻t2")
            fault_result = can_clear_injection('CAN_L_short_power', target_can_channel)
            ctx.can.set_info('gErrorFrameCount', 0)
            # 检查返回值类型
            if isinstance(fault_result, tuple) and len(fault_result) == 2:
                fault_success, t1 = fault_result
            else:
                fault_success = fault_result
                t1 = None

            if not fault_success:
                TestLog("FAIL", "故障注入", "CAN_L对电源短路故障清除失败")
                return

            # 等待DUT恢复通信
            recovery_success, T_recovery = check_communication_recovery_time(t1, T_faultRecoveryMax)

            # 记录故障清除时刻t1
            TestLog("INFO", "故障清除", f"CAN_L对电源短路故障已清除，记录时刻t1: {t1}")
            if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
                TestLog("FAIL", "测试结束", "实际: 存在错误帧; 期望: DUT通信正常，总线无错误帧")
                overall_result = False
                return
            TestLog("PASS", "测试结束", "实际:  DUT通信正常，总线无错误帧; 期望:  DUT通信正常，总线无错误帧")

            if recovery_success:
                # T_recovery是t2 - t1的时间差（毫秒）
                TestLog("PASS", "通信恢复", f"DUT通信已恢复，恢复时间: {T_recovery:.2f}ms")

                # 检查恢复时间是否满足600ms及以内
                if T_recovery <= T_faultRecoveryMax:
                    TestLog("PASS", "恢复时间检查",
                            f"T_recovery({T_recovery:.2f}ms) ≤ T_faultRecoveryMax({T_faultRecoveryMax}ms)")
                    time_ok = True
                else:
                    TestLog("FAIL", "恢复时间检查",
                            f"T_recovery({T_recovery:.2f}ms) > T_faultRecoveryMax({T_faultRecoveryMax}ms)")
                    time_ok = False
                    overall_result = False
            else:
                TestLog("FAIL", "通信恢复", f"DUT在{T_faultRecoveryMax}ms内通信未恢复")
                T_recovery = T_faultRecoveryMax
                time_ok = False
                overall_result = False

            can_l_result = time_ok
            round_result = can_h_result and can_l_result

            # 记录本轮测试结果
            test_results.append({
                'round': round_num,
                'can_h_result': can_h_result,
                'can_l_result': can_l_result,
                'recovery_time': T_recovery,
                'overall_result': round_result
            })
            # 输出本轮测试结果
            TestLog("INFO", "测试轮次结果",
                    f"第{round_num}轮测试结果 - CAN_H短电源测试: {'通过' if can_h_result else '失败'}, "
                    f"CAN_L短电源测试: {'通过' if can_l_result else '失败'}, 恢复时间: {T_recovery:.2f}ms ")

            TestLog("INFO", "测试轮次", f"第{round_num}轮测试完成，本轮结果: {'通过' if round_result else '失败'}")

        # 最终评价
        if overall_result:
            TestLog("PASS", "最终结果", "CAN_H/L短电源测试用例通过")
        else:
            TestLog("FAIL", "最终结果", "CAN_H/L短电源测试用例失败")

    except Exception as e:
        TestLog("FAIL", "CAN_H/L短电源测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "CAN_H/L短电源测试", f"详细错误: {traceback.format_exc()}")

def test_TG4_TC2_CAN_H_L_ShortGNDTest():
    """CAN_H/L短地测试"""
    try:

        # 从配置文件获取测试参数
        V_normal = P.CANInfo.Vnormal  # 正常电压
        T_stable = P.CANInfo.Tstable_s  # 通信稳定时间(s)
        T_faultDelay = P.CANInfo.TfaultDelay_s   # 故障保持时间(s)
        T_faultRecoveryMax = P.CANInfo.TfaultRecoveryMax_ms  # 最大恢复时间(ms)
        N_faultRepeat = P.CANInfo.NfaultRepeat  # 重复测试次数

        ctrl_can_channel = P.ECUInfo.BOBControlCan
        target_can_channel = P.ECUInfo.ETS6124CanChannel
        board_addr = P.ECUInfo.ETS6124Addr_int

        test_results = []
        overall_result = True
        ctx.can.set_filter_by_channel(DEFAULT_CAN_CHANNELS[0])
        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{V_normal}，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{T_stable}时间至通信稳定")
        ret = can_power_setup_and_communication_check(V_normal, T_stable)
        if ret != 0:
            TestLog("FAIL", "接收报文测试", "电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        # for round_num in range(1, N_faultRepeat + 1):
        for round_num in range(1, 2):
            TestLog("INFO", "Step2", f"制造CAN_H与地短路故障，持续{T_faultDelay}时间")

            # 步骤2: CAN_H与地短路测试
            TestLog("INFO", "CAN_H对地短路测试", f"开始第{round_num}轮CAN_H对地短路测试")
            fault_result = can_fault_injection('CAN_H_short_GND', target_can_channel,
                                               T_faultDelay * 1000)
            if not fault_result:
                TestLog("FAIL", "故障注入", "CAN_H与地短路故障注入失败")
                return

            if (ctx.can.get_info('gErrorFrameCount') or 0) == 0:
                TestLog("FAIL", "Step2", "实际: 不存在错误帧; 期望: 总线出现错误帧")
                return
            TestLog("PASS", "Step2", "实际: 总线出现错误帧; 期望: 总线出现错误帧")

            TestLog("INFO", "Step3", f"移除故障，记录时刻t1，等待DUT恢复通信，记录时刻t2")
            fault_result = can_clear_injection('CAN_H_short_GND', target_can_channel)
            ctx.can.set_info('gErrorFrameCount', 0)
            # 检查返回值类型
            if isinstance(fault_result, tuple) and len(fault_result) == 2:
                fault_success, t1 = fault_result
            else:
                fault_success = fault_result
                t1 = None

            if not fault_success:
                TestLog("FAIL", "故障注入", "CAN_H与地短路故障清除失败")
                return
            TestLog("INFO", "故障清除", f"CAN_L对地短路故障已清除，记录时刻t1: {t1}")

            # 检查DUT通信是否正常，总线无错误帧
            # ret = check_can_communication_state(T_stable)
            # if ret != 0:
            #     TestLog("FAIL", "CAN_H短电源测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信不正常，测试结束")
            #     overall_result = False
            #     return
            # TestLog("PASS", "CAN_H短电源测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信正常，总线无错误帧")
            if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
                TestLog("FAIL", "CAN_H短电源测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信正常，总线存在错误帧")
                overall_result = False
                return
            TestLog("PASS", "CAN_H短电源测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信正常，总线无错误帧")

            # 步骤3: 等待DUT恢复通信，记录时刻t2
            recovery_success, T_recovery = check_communication_recovery_time(t1, T_faultRecoveryMax)
            TestLog("INFO", "Step4", f"根据步骤3，计算通信恢复时间，计算方式如下：T_recovery= t2 – t1")

            if recovery_success:
                # T_recovery是t2 - t1的时间差（毫秒）
                TestLog("PASS", "通信恢复", f"DUT通信已恢复，恢复时间: {T_recovery:.2f}ms")
                if T_recovery <= T_faultRecoveryMax:
                    TestLog("PASS", "恢复时间检查",
                            f"期望结果：Trecovery ≤ TfaultRecoveryMax。实际结果：T_recovery({T_recovery:.2f}ms) ≤ T_faultRecoveryMax({T_faultRecoveryMax}ms)")
                    time_ok = True
                else:
                    TestLog("FAIL", "恢复时间检查",
                            f"期望结果：Trecovery ≤ TfaultRecoveryMax。实际结果：T_recovery({T_recovery:.2f}ms) > T_faultRecoveryMax({T_faultRecoveryMax}ms)")
                    time_ok = False
                    overall_result = False
            else:
                TestLog("FAIL", "通信恢复", f"DUT在{T_faultRecoveryMax}ms内通信未恢复")
                T_recovery = T_faultRecoveryMax
                time_ok = False
                overall_result = False

            # 步骤4-5: 重新进行电源设置（KL30断电再上电）
            TestLog("INFO", "Step5", "将KL30断电，等待2s")
            ctx.bob_ctrl.set_power('KL30', False)
            time.sleep(2.0)

            TestLog("INFO", "Stpe6", "KL30重新上电及通信准备")
            ret = can_power_setup_and_communication_check(V_normal, T_stable)
            if ret != 0:
                TestLog("FAIL", "通信检查", "KL30重新上电后DUT通信异常")
                overall_result = False
                return
            TestLog("PASS","","期望结果：DUT通信正常。实际结果：DUT通信正常")

            # 步骤6-8: CAN_L短路测试
            TestLog("INFO", "Stpe7", f"制造CAN_L与地短路故障，持续{T_faultDelay}时间")
            fault_result = can_fault_injection('CAN_L_short_GND', target_can_channel,
                                               T_faultDelay * 1000)

            TestLog("INFO", "Step8", "移除故障，等待1s，监控总线通信状态")
            fault_result = can_clear_injection('CAN_L_short_GND', target_can_channel)
            ctx.can.set_info('gErrorFrameCount', 0)
            # 检查返回值类型
            if isinstance(fault_result, tuple) and len(fault_result) == 2:
                fault_success, t1 = fault_result
            else:
                fault_success = fault_result
                t1 = None

            if not fault_success:
                TestLog("FAIL", "故障注入", "CAN_L与地短路清除失败")
                return

            TestLog("INFO", "故障注入", "CAN_L与地短路故障已注入并自动清除")

            time.sleep(1.0)

            # 检查DUT通信是否正常，总线无错误帧
            ret = check_can_communication_state(T_stable)
            if ret != 0:
                TestLog("FAIL", "CAN_L短地测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信不正常，测试结束")
                overall_result = False
                return
            TestLog("PASS", "CAN_L短地测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信正常，总线无错误帧")
            can_l_result = True

            # 记录本轮测试结果
            can_h_result = time_ok
            round_result = can_h_result and can_l_result
            test_results.append({
                'round': round_num,
                'can_h_result': can_h_result,
                'can_l_result': can_l_result,
                'recovery_time': T_recovery,
                'overall_result': round_result
            })

            # 输出本轮测试结果
            TestLog("INFO", "测试轮次结果",
                    f"第{round_num}轮测试结果 - CAN_H短地测试: {'通过' if can_h_result else '失败'}, "
                    f"CAN_L短地测试: {'通过' if can_l_result else '失败'}, "
                    f"恢复时间: {T_recovery:.2f}ms")

            TestLog("INFO", "测试轮次", f"第{round_num}轮测试完成，本轮结果: {'通过' if round_result else '失败'}")

        # 最终评价
        if overall_result:
            TestLog("PASS", "最终结果", "CAN_H/L短地测试用例通过")
        else:
            TestLog("FAIL", "最终结果", "CAN_H/L短地测试用例失败")

    except Exception as e:
        TestLog("FAIL", "CAN_H/L短地测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "CAN_H/L短地测试", f"详细错误: {traceback.format_exc()}")

def test_TG4_TC3_CAN_H_L_ShortCircuitTest():
    """CAN_H与CAN_L短路测试"""
    try:
        # 从配置文件获取测试参数
        V_normal = P.CANInfo.Vnormal  # 正常电压
        T_stable = P.CANInfo.Tstable_s  # 通信稳定时间(s)
        T_faultDelay = P.CANInfo.TfaultDelay_s   # 故障保持时间(s)
        T_faultRecoveryMax = P.CANInfo.TfaultRecoveryMax_ms  # 最大恢复时间(ms)
        N_faultRepeat = P.CANInfo.NfaultRepeat  # 重复测试次数

        ctrl_can_channel = P.ECUInfo.BOBControlCan
        target_can_channel = P.ECUInfo.ETS6124CanChannel
        board_addr = P.ECUInfo.ETS6124Addr_int

        test_results = []
        overall_result = True
        ctx.can.set_filter_by_channel(DEFAULT_CAN_CHANNELS[0])
        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{V_normal}，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{T_stable}时间至通信稳定")
        ret = can_power_setup_and_communication_check(V_normal, T_stable)
        if ret != 0:
            TestLog("FAIL", "接收报文测试", "期望结果：DUT通信正常。实际结果：电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "", "期望结果：DUT通信正常。实际结果：DUT通信正常")
        # for round_num in range(1, N_faultRepeat + 1):
        for round_num in range(1, 2):
            TestLog("INFO", "Step2", f"制造CAN_H与CAN_L短路故障，持续{T_faultDelay}时间")

            # 步骤2: 制造CAN_H与CAN_L短路故障
            TestLog("INFO", "CAN_H/L短路测试", f"开始第{round_num}轮CAN_H/L短路测试")
            fault_result = can_fault_injection('CAN_H_L_short', target_can_channel,
                                           T_faultDelay * 1000)

            ctx.can.clear_messages()
            # print(f"{(len(ctx.can.messages))=}")
            time.sleep(20)
            # print(f"{(len(ctx.can.messages))=}")
            if(len(ctx.can.messages) >0 ):
                TestLog("FAIL","Step2", f"期望结果：总线无CAN报文 。实际结果：总线CAN报文，存在{(len(ctx.can.messages))}条报文")
                overall_result = False
                return
            TestLog("PASS", "Step2", "期望结果：总线无CAN报文 。实际结果：总线无CAN报文")

            TestLog("INFO", "Step3", f"移除故障，记录时刻t1，等待DUT恢复通信，记录时刻t2")
            fault_result = can_clear_injection('CAN_H_L_short', target_can_channel)
            ctx.can.set_info('gErrorFrameCount', 0)
            # 检查返回值类型
            if isinstance(fault_result, tuple) and len(fault_result) == 2:
                fault_success, t1 = fault_result
            else:
                fault_success = fault_result
                t1 = None

            if not fault_success:
                TestLog("FAIL", "故障注入", "CAN_H/L短路故障清除失败")
                return

            # # 检查DUT通信是否正常，总线无错误帧
            # ret = check_can_communication_state(T_stable)
            # if ret != 0:
            #     TestLog("FAIL", "CAN_H短电源测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信不正常，测试结束")
            #     overall_result = False
            #     return
            # TestLog("PASS", "CAN_H短电源测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信正常，总线无错误帧")

            if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
                TestLog("FAIL", "CAN_H短电源测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信正常，总线存在错误帧")
                overall_result = False
                return
            TestLog("PASS", "CAN_H短电源测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信正常，总线无错误帧")

            # 等待DUT恢复通信，计算恢复时间
            recovery_success, T_recovery = check_communication_recovery_time(t1, T_faultRecoveryMax)

            TestLog("INFO", "Step4", f"根据步骤3，计算通信恢复时间，计算方式如下：{T_recovery} = t2 – t1")
            if recovery_success:
                # T_recovery是t2 - t1的时间差（毫秒）
                TestLog("PASS", "通信恢复", f"DUT通信已恢复，恢复时间: {T_recovery:.2f}ms")
                if T_recovery <= T_faultRecoveryMax:
                    TestLog("PASS", "恢复时间检查",
                            f"期望结果：T_recovery({T_recovery:.2f}ms) ≤ T_faultRecoveryMax({T_faultRecoveryMax}ms)。实际结果：T_recovery({T_recovery:.2f}ms) ≤ T_faultRecoveryMax({T_faultRecoveryMax}ms)")
                    time_ok = True
                else:
                    TestLog("FAIL", "恢复时间检查",
                            f"期望结果：T_recovery({T_recovery:.2f}ms) ≤ T_faultRecoveryMax({T_faultRecoveryMax}ms)。实际结果T_recovery({T_recovery:.2f}ms) > T_faultRecoveryMax({T_faultRecoveryMax}ms)，不满足要求")

                    time_ok = False
                    overall_result = False

            else:
                TestLog("FAIL", "通信恢复", f"DUT在{T_faultRecoveryMax}ms内通信未恢复")
                T_recovery = T_faultRecoveryMax
                time_ok = False
                overall_result = False

            # 记录本轮测试结果
            test_results.append({
                'round': round_num,
                'recovery_time': T_recovery,
                'can_h/l_short_result': time_ok,
                'overall_result': time_ok
            })

            # 输出本轮测试结果
            TestLog("INFO", "测试轮次结果",
                    f"第{round_num}轮测试结果 - CAN_H/L短路测试: {'通过' if time_ok else '失败'}, "
                    f"恢复时间: {T_recovery:.2f}ms")

            TestLog("INFO", "测试轮次", f"第{round_num}轮测试完成，本轮结果: {'通过' if time_ok else '失败'}")

        # 最终评价
        if overall_result:
            TestLog("PASS", "最终结果", "CAN_H/L短路测试用例通过")
        else:
            TestLog("FAIL", "最终结果", "CAN_H/L短路测试用例失败")

    except Exception as e:
        TestLog("FAIL", "CAN_H/L短路测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "CAN_H/L短路测试", f"详细错误: {traceback.format_exc()}")

def test_TG4_TC4_CAN_H_L_OpenCircuitTest():
    """CAN_H/L断路测试"""
    try:

        # 从配置文件获取测试参数
        V_normal = P.CANInfo.Vnormal  # 正常电压
        T_stable = P.CANInfo.Tstable_s  # 通信稳定时间(s)
        T_faultDelay = P.CANInfo.TfaultDelay_s  # 故障保持时间(s)
        T_faultRecoveryMax = P.CANInfo.TfaultRecoveryMax_ms  # 最大恢复时间(ms)
        N_faultRepeat = P.CANInfo.NfaultRepeat  # 重复测试次数

        ctrl_can_channel = P.ECUInfo.BOBControlCan
        target_can_channel = P.ECUInfo.ETS6124CanChannel
        board_addr = P.ECUInfo.ETS6124Addr_int

        test_results = []
        overall_result = True
        ctx.can.set_filter_by_channel(DEFAULT_CAN_CHANNELS[0])
        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{V_normal}，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{T_stable}时间至通信稳定")
        ret = can_power_setup_and_communication_check(V_normal, T_stable)
        if ret != 0:
            TestLog("FAIL", "接收报文测试", "电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        # for round_num in range(1, N_faultRepeat + 1):
        for round_num in range(1, 1 + 1):
            TestLog("INFO", "Step2", f"制造CAN_H线断开故障，持续{T_faultDelay}时间")

            # 步骤2: 制造CAN_H线断开故障
            TestLog("INFO", "CAN_H断路测试", f"开始第{round_num}轮CAN_H断路测试")
            fault_result = can_fault_injection('CAN_H_Open', target_can_channel,
                                               T_faultDelay * 1000)
            if (ctx.can.get_info('gErrorFrameCount') or 0) == 0:
                TestLog("FAIL", "Step2", "实际: 不存在错误帧; 期望: 总线出现错误帧")
                return
            TestLog("PASS", "Step2", "实际: 总线出现错误帧; 期望: 总线出现错误帧")

            TestLog("INFO", "Step3", f"移除故障，记录时刻t1，等待DUT恢复通信，记录时刻t2")
            fault_result = can_clear_injection('CAN_H_Open', target_can_channel)
            ctx.can.set_info('gErrorFrameCount', 0)
            # 检查返回值类型
            if isinstance(fault_result, tuple) and len(fault_result) == 2:
                fault_success, t1 = fault_result
            else:
                fault_success = fault_result
                t1 = None

            if not fault_success:
                TestLog("FAIL", "故障注入", "CAN_H线断开故障清除失败")
                return

            TestLog("INFO", "故障清除", f"CAN_H线断开故障已清除，记录时刻t1: {t1}")

            # 检查DUT通信是否正常，总线无错误帧
            # ret = check_can_communication_state(T_stable)
            # if ret != 0:
            #     TestLog("FAIL", "CAN_H短电源测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信不正常，测试结束")
            #     overall_result = False
            #     return
            # TestLog("PASS", "CAN_H短电源测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信正常，总线无错误帧")
            if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
                TestLog("FAIL", "CAN_H短电源测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信正常，总线存在错误帧")
                overall_result = False
                return
            TestLog("PASS", "CAN_H短电源测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信正常，总线无错误帧")

            # 步骤3: 等待DUT恢复通信，记录时刻t2
            recovery_success, T_recovery = check_communication_recovery_time(t1, T_faultRecoveryMax)
            TestLog("INFO", "Step4", f"根据步骤3，计算通信恢复时间，计算方式如下：Trecovery= t2 – t1")
            if recovery_success:
                # T_recovery是t2 - t1的时间差（毫秒）
                TestLog("PASS", "通信恢复", f"DUT通信已恢复，恢复时间: {T_recovery:.2f}ms")
                T_h_recovery = T_recovery
                if T_recovery <= T_faultRecoveryMax:
                    TestLog("PASS", "恢复时间检查",
                            f"期望结果：T_recovery({T_recovery:.2f}ms) ≤ T_faultRecoveryMax({T_faultRecoveryMax}ms。实际结果：T_recovery({T_recovery:.2f}ms) ≤ T_faultRecoveryMax({T_faultRecoveryMax}ms")
                    can_h_result = True
                else:
                    TestLog("FAIL", "恢复时间检查",
                            f"期望结果：T_recovery({T_recovery:.2f}ms) ≤ T_faultRecoveryMax({T_faultRecoveryMax}ms。实际结果：T_recovery({T_recovery:.2f}ms) > T_faultRecoveryMax({T_faultRecoveryMax}ms)")
                    can_h_result = False
                    overall_result = False
            else:
                TestLog("FAIL", "通信恢复", f"DUT在{T_faultRecoveryMax}ms内通信未恢复")
                T_h_recovery = T_faultRecoveryMax
                can_h_result = False
                overall_result = False

            # 步骤4-5: 重新进行电源设置（KL30断电再上电）
            TestLog("INFO", "Step5", "将KL30断电，等待2s")
            ctx.bob_ctrl.set_power('KL30', False)
            time.sleep(2.0)

            TestLog("INFO", "Step6", "KL30重新上电及通信准备")
            ret = can_power_setup_and_communication_check(V_normal, T_stable)
            if ret != 0:
                TestLog("FAIL", "Step6", "期望结果：DUT通信正常。实际结果：KL30重新上电后DUT通信异常")
                overall_result = False
                return
            TestLog("PASS", "Step6", "期望结果：DUT通信正常。实际结果：DUT通信正常")
            # 步骤7: 制造CAN_L线断路故障
            TestLog("INFO", "Stpe7", f"制造CAN_L线断路故障，持续{T_faultDelay}时间")
            fault_result = can_fault_injection('CAN_L_Open', target_can_channel,
                                               T_faultDelay * 1000)

            if (ctx.can.get_info('gErrorFrameCount') or 0) == 0:
                TestLog("FAIL", "Step7", "实际: 不存在错误帧; 期望: 总线出现错误帧")
                return
            TestLog("PASS", "Step7", "实际: 总线出现错误帧; 期望: 总线出现错误帧")

            TestLog("INFO", "Step8", "移除故障，记录时刻t1，等待DUT恢复通信，记录时刻t2")
            fault_result = can_clear_injection('CAN_L_Open', target_can_channel)
            ctx.can.set_info('gErrorFrameCount', 0)
            # 检查返回值类型
            if isinstance(fault_result, tuple) and len(fault_result) == 2:
                fault_success, t1 = fault_result
            else:
                fault_success = fault_result
                t1 = None

            if not fault_success:
                TestLog("FAIL", "故障注入", "CAN_L线断路故障清除失败")
                return

            TestLog("INFO", "故障清除", f"CAN_L线断路故障已清除，记录时刻t1: {t1}")
            # 检查DUT通信是否正常，总线无错误帧
            # ret = check_can_communication_state(T_stable)
            # if ret != 0:
            #     TestLog("FAIL", "CAN_H短电源测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信不正常，测试结束")
            #     overall_result = False
            #     return
            # TestLog("PASS", "CAN_H短电源测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信正常，总线无错误帧")
            if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
                TestLog("FAIL", "CAN_H短电源测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信正常，总线存在错误帧")
                overall_result = False
                return
            TestLog("PASS", "CAN_H短电源测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信正常，总线无错误帧")

            # 等待DUT恢复通信，计算恢复时间
            recovery_success, T_recovery = check_communication_recovery_time(t1, T_faultRecoveryMax)
            TestLog("INFO","Step9", f"根据步骤8，计算通信恢复时间，计算方式如下：{T_recovery} = t2 – t1")
            if recovery_success:
                # T_recovery是t2 - t1的时间差（毫秒）
                TestLog("PASS", "通信恢复", f"DUT通信已恢复，恢复时间: {T_recovery:.2f}ms")
                T_l_recovery = T_recovery

                if T_recovery <= T_faultRecoveryMax:
                    TestLog("PASS", "恢复时间检查",
                            f"期望结果：T_recovery({T_recovery:.2f}ms) ≤ T_faultRecoveryMax({T_faultRecoveryMax}ms)。实际结果：T_recovery({T_recovery:.2f}ms) ≤ T_faultRecoveryMax({T_faultRecoveryMax}")
                    can_l_result = True
                else:
                    TestLog("FAIL", "恢复时间检查",
                            f"期望结果：T_recovery({T_recovery:.2f}ms) ≤ T_faultRecoveryMax({T_faultRecoveryMax}ms)。实际结果：T_recovery({T_recovery:.2f}ms) > T_faultRecoveryMax({T_faultRecoveryMax}ms)")
                    can_l_result = False
                    overall_result = False
            else:
                TestLog("FAIL", "通信恢复", f"DUT在{T_faultRecoveryMax}ms内通信未恢复")
                T_l_recovery = T_faultRecoveryMax
                can_l_result = False
                overall_result = False

            round_result = can_h_result and can_l_result

            # 记录本轮测试结果
            test_results.append({
                'round': round_num,
                'can_h_result': can_h_result,
                'can_l_result': can_l_result,
                'overall_result': round_result,
                'T_h_recovery': T_h_recovery,
                'T_l_recovery': T_l_recovery,

            })

            # 输出本轮测试结果
            TestLog("INFO", "测试轮次结果",
                    f"第{round_num}轮测试结果 - CAN_H断路测试: {'通过' if can_h_result else '失败'}, "
                    f"CAN_H断路测试: {'通过' if can_h_result else '失败'}, 恢复时间: {T_h_recovery:.2f}ms "
                    f"CAN_L断路测试: {'通过' if can_l_result else '失败'}, 恢复时间: {T_l_recovery:.2f}ms ")

            TestLog("INFO", "测试轮次", f"第{round_num}轮测试完成，本轮结果: {'通过' if round_result else '失败'}")

        # 最终评价
        if overall_result:
            TestLog("PASS", "最终结果", "CAN_H/L断路测试用例通过")
        else:
            TestLog("FAIL", "最终结果", "CAN_H/L断路测试用例失败")

    except Exception as e:
        TestLog("FAIL", "CAN_H/L断路测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "CAN_H/L断路测试", f"详细错误: {traceback.format_exc()}")

def test_TG4_TC5_DUT_KL30_PowerOffTest():
    """KL30断电恢复测试"""
    try:

        # 从配置文件获取测试参数
        V_normal = P.CANInfo.Vnormal  # 正常电压
        T_stable = P.CANInfo.Tstable_s  # 通信稳定时间(s)
        T_faultDelay = P.CANInfo.TfaultDelay_s  # 故障保持时间(s)
        T_faultRecoveryMax = P.CANInfo.TfaultRecoveryMax_ms  # 最大恢复时间(ms)
        N_faultRepeat = P.CANInfo.NfaultRepeat  # 重复测试次数

        test_results = []
        overall_result = True
        ctx.can.set_filter_by_channel(DEFAULT_CAN_CHANNELS[0])
        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{V_normal}，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{T_stable}时间至通信稳定")
        ret = can_power_setup_and_communication_check(V_normal, T_stable)
        if ret != 0:
            TestLog("FAIL", "接收报文测试", "电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        # for round_num in range(1, N_faultRepeat + 1):
        for round_num in range(1, 1 + 1):
            # 步骤2: DUT掉电测试
            TestLog("INFO", "DUT掉电测试", f"开始第{round_num}轮DUT掉电测试")
            TestLog("INFO", "Step2", f"将KL30断电，持续{T_faultDelay}时间")
            ctx.bob_ctrl.set_power('KL30', False)
            time.sleep(T_faultDelay)

            # 步骤3: 重新将KL30上电，记录时刻t1，等待DUT恢复通信，记录时刻t2
            TestLog("INFO", "Step3", "重新将KL30上电，记录时刻t1，等待DUT恢复通信")

            # 执行KL30上电
            ctx.bob_ctrl.set_power('KL30', True)

            # 记录KL30上电时刻t1
            t1 = time.time()
            TestLog("INFO", "KL30上电", f"KL30重新上电，记录时刻t1: {t1}")

            # 根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络
            TestLog("INFO", "唤醒DUT", "根据DUT通信唤醒方式，唤醒CAN网络")
            WakeupStart()

            # 检查DUT通信是否正常，总线无错误帧
            # ret = check_can_communication_state(T_stable)
            # if ret != 0:
            #     TestLog("FAIL", "Step3", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信不正常，测试结束")
            #     overall_result = False
            #     return
            # TestLog("PASS", "Step3", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信正常，总线无错误帧")
            if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
                TestLog("FAIL", "CAN_H短电源测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信正常，总线存在错误帧")
                overall_result = False
                return
            TestLog("PASS", "CAN_H短电源测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信正常，总线无错误帧")

            # 使用通信恢复检查函数
            TestLog("INFO", "Step4", f"根据步骤3，计算通信恢复时间，计算方式如下：Trecovery = t2 – t1")
            recovery_success, T_recovery = check_communication_recovery_time(t1, T_faultRecoveryMax)
            if recovery_success:
                # T_recovery是t2 - t1的时间差（毫秒）
                TestLog("PASS", "通信恢复", f"DUT通信已恢复，恢复时间: {T_recovery:.2f}ms")

                if T_recovery <= T_faultRecoveryMax:
                    TestLog("PASS", "恢复时间检查",
                            f"期望结果：T_recovery({T_recovery:.2f}ms) ≤ T_faultRecoveryMax({T_faultRecoveryMax}ms)。实际结果：T_recovery({T_recovery:.2f}ms) ≤ T_faultRecoveryMax({T_faultRecoveryMax}ms)")
                    recovery_time_ok = True
                else:
                    if T_recovery > T_faultRecoveryMax:
                        TestLog("FAIL", "恢复时间检查",
                                f"期望结果：T_recovery({T_recovery:.2f}ms) ≤ T_faultRecoveryMax({T_faultRecoveryMax}ms)。实际结果：T_recovery({T_recovery:.2f}ms) > T_faultRecoveryMax({T_faultRecoveryMax}ms)")
                    else:
                        TestLog("FAIL", "通信状态检查", "DUT通信状态异常")
                    recovery_time_ok = False
                    overall_result = False
            else:
                TestLog("FAIL", "通信恢复", f"DUT在{T_faultRecoveryMax}ms内通信未恢复")
                T_recovery = T_faultRecoveryMax
                recovery_time_ok = False
                overall_result = False

            round_result = recovery_time_ok

            # 记录本轮测试结果
            test_results.append({
                'round': round_num,
                'recovery_time': T_recovery,
                'recovery_time_ok': recovery_time_ok,
                'overall_result': round_result
            })

            # 输出本轮测试结果
            TestLog("INFO", "测试轮次结果",
                    f"第{round_num}轮测试结果 - 恢复时间: {T_recovery:.2f}ms, "
                    f"恢复时间检查: {'通过' if recovery_time_ok else '失败'}, ")

            TestLog("INFO", "测试轮次", f"第{round_num}轮测试完成，本轮结果: {'通过' if round_result else '失败'}")

        # 最终评价
        if overall_result:
            TestLog("PASS", "最终结果", "DUT掉电测试用例通过")
        else:
            TestLog("FAIL", "最终结果", "DUT掉电测试用例失败")

        # 输出详细测试结果统计
        successful_rounds = sum(1 for result in test_results if result['overall_result'])
        TestLog("INFO", "测试统计",
                f"总测试轮次: {N_faultRepeat}, 成功轮次: {successful_rounds}, 失败轮次: {N_faultRepeat - successful_rounds}")

    except Exception as e:
        TestLog("FAIL", "DUT掉电测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "DUT掉电测试", f"详细错误: {traceback.format_exc()}")

def test_TG4_TC6_DUT_GND_DisconnectTest():
    """DUT与GND断开恢复测试"""
    try:

        # 从配置文件获取测试参数
        V_normal = P.CANInfo.Vnormal  # 正常电压
        T_stable = P.CANInfo.Tstable_s  # 通信稳定时间(s)
        T_faultDelay = P.CANInfo.TfaultDelay_s  # 故障保持时间(s)
        T_faultRecoveryMax = P.CANInfo.TfaultRecoveryMax_ms  # 最大恢复时间(ms)
        N_faultRepeat = P.CANInfo.NfaultRepeat  # 重复测试次数
        target_ecu_channel = P.ECUInfo.ETS6124ECUChannel

        test_results = []
        overall_result = True
        ctx.can.set_filter_by_channel(DEFAULT_CAN_CHANNELS[0])
        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{V_normal}，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{T_stable}时间至通信稳定")
        ret = can_power_setup_and_communication_check(V_normal, T_stable)
        if ret != 0:
            TestLog("FAIL", "接收报文测试", "电源设置与通信检查失败，结束测试")
            return
        TestLog("PASS", "", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        # for round_num in range(1, N_faultRepeat + 1):
        for round_num in range(1, 1 + 1):
            TestLog("INFO", "DUT掉地测试", f"开始第{round_num}轮DUT掉地测试")
            # 步骤2: 将DUT与GND断开
            TestLog("INFO", "Stet2", f"将DUT与GND断开，持续{T_faultDelay}时间")
            ctx.bob_ctrl.set_power('GND', False, target_ecu_channel)
            time.sleep(T_faultDelay)
            # time.sleep(20)
            # 步骤3: 将DUT与GND重新连接，记录时刻t1，等待DUT恢复通信
            TestLog("INFO", "Step3", "将DUT与GND重新连接，记录时刻t1，等待DUT恢复通信")

            # 执行GND重新连接
            ctx.bob_ctrl.set_power('GND', True, target_ecu_channel)
            ctx.can.set_info('gErrorFrameCount', 0)
            # 记录GND重新连接时刻t1
            t1 = time.time()
            TestLog("INFO", "GND恢复", f"DUT与GND重新连接，记录时刻t1: {t1}")

            # 根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络
            TestLog("INFO", "唤醒DUT", "根据DUT通信唤醒方式，唤醒CAN网络")
            WakeupStart()

            # 检查DUT通信是否正常，总线无错误帧
            # ret = check_can_communication_state(T_stable)
            # if ret != 0:
            #     TestLog("FAIL", "Step3", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信不正常，测试结束")
            #     overall_result = False
            #     return
            # TestLog("PASS", "Step3", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信正常，总线无错误帧")
            if (ctx.can.get_info('gErrorFrameCount') or 0) > 0:
                TestLog("FAIL", "CAN_H短电源测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信正常，总线存在错误帧")
                overall_result = False
                return
            TestLog("PASS", "CAN_H短电源测试", "期望结果：DUT通信正常，总线无错误帧。实际结果：DUT通信正常，总线无错误帧")

            # 使用通信恢复检查函数
            TestLog("INFO", "Step4", "根据步骤3，计算通信恢复时间，计算方式如下：Trecovery = t2 – t1")
            recovery_success, T_recovery = check_communication_recovery_time(t1, T_faultRecoveryMax)

            if recovery_success:
                # T_recovery是t2 - t1的时间差（毫秒）
                TestLog("PASS", "", f"DUT通信已恢复，恢复时间: {T_recovery:.2f}ms")

                if T_recovery <= T_faultRecoveryMax:
                    TestLog("PASS", "",
                            f"期望结果：T_recovery({T_recovery:.2f}ms) ≤ T_faultRecoveryMax({T_faultRecoveryMax}ms)。实际结果：T_recovery({T_recovery:.2f}ms) ≤ T_faultRecoveryMax({T_faultRecoveryMax}ms)")
                    recovery_time_ok = True
                else:
                    if T_recovery > T_faultRecoveryMax:
                        TestLog("FAIL", "",
                                f"期望结果：T_recovery({T_recovery:.2f}ms) ≤ T_faultRecoveryMax({T_faultRecoveryMax}ms)。实际结果：T_recovery({T_recovery:.2f}ms) > T_faultRecoveryMax({T_faultRecoveryMax}ms)")
                    else:
                        TestLog("FAIL", "", "DUT通信状态异常")
                    recovery_time_ok = False
                    overall_result = False
            else:
                TestLog("FAIL", "", f"DUT在{T_faultRecoveryMax}ms内通信未恢复")
                T_recovery = T_faultRecoveryMax
                recovery_time_ok = False
                overall_result = False

            round_result = recovery_time_ok

            # 记录本轮测试结果
            test_results.append({
                'round': round_num,
                'recovery_time': T_recovery,
                'recovery_time_ok': recovery_time_ok,
                'overall_result': round_result
            })

            # 输出本轮测试结果
            TestLog("INFO", "",
                    f"第{round_num}轮测试结果 - 恢复时间: {T_recovery:.2f}ms, "
                    f"恢复时间检查: {'通过' if recovery_time_ok else '失败'}, ")

            TestLog("INFO", "", f"第{round_num}轮测试完成，本轮结果: {'通过' if round_result else '失败'}")

        # 最终评价
        if overall_result:
            TestLog("PASS", "", "DUT掉地测试用例通过")
        else:
            TestLog("FAIL", "", "DUT掉地测试用例失败")

        # 输出详细测试结果统计
        successful_rounds = sum(1 for result in test_results if result['overall_result'])
        TestLog("INFO", "测试统计",
                f"总测试轮次: {N_faultRepeat}, 成功轮次: {successful_rounds}, 失败轮次: {N_faultRepeat - successful_rounds}")

    except Exception as e:
        TestLog("FAIL", "DUT掉地测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "DUT掉地测试", f"详细错误: {traceback.format_exc()}")

def test_TG5_TC3_DiagnosticServiceDuringCommunication():
    """
    通信中诊断服务测试
    """
    try:
        from testcases.can.can_diag_utils import get_can_node, send_diagnostic_sequence

        V_normal = P.CANInfo.Vnormal
        T_stable = P.CANInfo.Tstable_s
        rTperiodDeviation1 = P.CANInfo.TperiodDeviation1_pct
        rTperiodDeviation2 = P.CANInfo.TperiodDeviation2_pct
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        can_db_msg_defs = ctx.can.get_info('can_db_msg_defs') or {}

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{V_normal}V，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{T_stable}s时间至通信稳定")
        ret = can_power_setup_and_communication_check(V_normal, T_stable)
        if ret != 0:
            TestLog("FAIL", "Step1", "期望结果：DUT通信正常，无错误帧。实际结果：电源设置与通信检查失败，结束测试")
            return

        ctx.can.set_filter_by_channel(can_channel)
        if not check_bus_error_frames("Step1"):
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常，无错误帧。实际结果：DUT通信正常，无错误帧")

        sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
        node = get_can_node(sa, ta, fa, is_canfd=P.TpInfo.CanFDMode)

        diag_interval_ms = 2000
        diag_repeat_count = 10

        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)

        TestLog("INFO", "Step2", "以2000ms为周期依次向DUT发送诊断服务: 1001、1003、14FFFFFF、190209、22F189、22F089")

        TestLog("INFO", "Step3", f"重复步骤2发送诊断服务{diag_repeat_count}次")
        for repeat in range(1, diag_repeat_count + 1):
            TestLog("INFO", "", f"第{repeat}/{diag_repeat_count}次发送诊断服务序列")
            send_diagnostic_sequence(node, interval_ms=diag_interval_ms)

        error_count = ctx.can.get_info('gErrorFrameCount') or 0
        if error_count > 0:
            TestLog("FAIL", "Step3", f"期望结果：总线无错误帧。实际结果：存在{error_count}个错误帧")
        else:
            TestLog("PASS", "Step3", "期望结果：总线无错误帧。实际结果：总线无错误帧")

        messages = ctx.can.messages
        rx_stats = build_rx_msg_info(messages)
        TestLog("INFO", "Step3", f"监控完成，共接收到 {len(rx_stats)} 种不同ID的报文")

        MsgReceivedList, MsgNotReceivedList, MsgTmpList = analyze_messages(rx_stats, can_db_msg_defs)

        TestLog("INFO", "Step3", f"验证周期偏移：20ms以内周期报文偏移应在{rTperiodDeviation1}%以内，20ms以上周期报文偏移应在{rTperiodDeviation2}%以内")
        report_message_tests(
            MsgReceivedList,
            MsgNotReceivedList,
            MsgTmpList,
            rx_stats,
            can_db_msg_defs,
            tests=("period",),
            period_thresholds=(rTperiodDeviation1, rTperiodDeviation2),
        )

        TestLog("PASS", "", "通信中诊断服务测试完成")

    except Exception as e:
        TestLog("FAIL", "通信中诊断服务测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "通信中诊断服务测试", f"详细错误: {traceback.format_exc()}")

def test_TG5_TC4_DiagnosticCommunicationTimeoutTest():
    """
    诊断通信超时测试
    """
    try:
        from testcases.can.can_diag_utils import service_19_check, get_can_node, get_dtc_list_from_19_resp

        V_normal = P.CANInfo.Vnormal
        T_stable = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        T_DiagStart = 2000
        nm_msg_id = P.ECUInfo.NMMsgID_int

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{V_normal}V，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{T_stable}s时间至通信稳定")

        dut_force_sleep(wait_time_s=5)

        ctx.can.clear_messages()
        ctx.can.set_filter_by_channel(can_channel)

        ctx.power_ctrl.set_voltage(V_normal)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)
        WakeupStart()


        TestLog("INFO", "Step1", f"记录DUT被唤醒后发出的第一NM报文(0x{nm_msg_id:X})时间为T1")
        T1 = None
        start_time = sl_time().timestamp()
        found_nm = False  # 标志变量
        while sl_time().timestamp() - start_time < 3000:
            messages = ctx.can.messages
            for msg in messages:
                if msg.id == nm_msg_id:
                    T1 = msg.time_ms
                    TestLog("INFO", "Step2", f"检测到第一帧NM报文，时间T1 = {T1:.2f}ms")
                    found_nm = True
                    break  # 跳出for循环
            
            if found_nm:
                break  # 跳出while循环

        if T1 is None:
            TestLog("FAIL", "Step2", f"期望结果：检测到DUT发出的NM报文。实际结果：未检测到NM报文(0x{nm_msg_id:X})，结束测试")
            return

        TestLog("INFO", "Step2", "以1ms周期时间发送诊断指令$19 02 09持续读取DTC，记录第一次成功读取到DUT支持的节点超时故障码的时间为T2")
        sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
        node = get_can_node(sa, ta, fa, is_canfd=P.TpInfo.CanFDMode)

        # 创建CAN报文
        msg = canmsg_create(P.ECUInfo.DiagReqID_int, 8, data=[0x03, 0x19, 0x02, 0x09] + [0xAA] * 4, rtr=0, fdf=0, brs=0, ext=0)

        # 设置周期定时器
        TimerCyclic.start(1, 1, send_canmsg, can_channel, msg=msg)  # 10ms周期发送msg
        
        max_wait_time_ms = 5000  # 最大等待10秒
        sl_time().sleep(max_wait_time_ms)
        # 停止发送报文
        TimerCyclic.stop(1)
        
        #获取59 02的时间戳
        messages = ctx.can.messages
        for msg in messages:
            payload = list(bytes.fromhex(msg.payload_hex))
            if msg.id == P.ECUInfo.DiagRespID_int and payload[1] == 0x59 and payload[2] == 0x02 and payload[3] == 0x09:
                T2 = msg.time_ms
                TestLog("INFO", "Step3", f"第一次成功读取到节点超时故障码，时间T2 = {T2:.2f}ms")
                break

        if T2 is None:
            TestLog("FAIL", "Step3", "期望结果：读取到节点超时故障码。实际结果：在最大等待时间内未读取到节点超时故障码")
            return

        TestLog("INFO", "Step4", f"计算诊断初始化时间T2 - T1，期望结果：T2 - T1 > T_DiagStart({T_DiagStart}ms)")

        diag_init_time = T2 - T1
        TestLog("INFO", "Step4", f"T2 - T1 = {T2:.2f} - {T1:.2f} = {diag_init_time:.2f}ms")

        if diag_init_time > T_DiagStart:
            TestLog("PASS", "Step4", f"期望结果：T2 - T1 > {T_DiagStart}ms。实际结果：{diag_init_time:.2f}ms > {T_DiagStart}ms，满足规范要求")
        else:
            TestLog("FAIL", "Step4", f"期望结果：T2 - T1 > {T_DiagStart}ms。实际结果：{diag_init_time:.2f}ms <= {T_DiagStart}ms，不满足规范要求")

        TestLog("INFO", "", "诊断通信超时测试完成")

    except Exception as e:
        TestLog("FAIL", "诊断通信超时测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "诊断通信超时测试", f"详细错误: {traceback.format_exc()}")

def test_TG5_TC5_DiagnosticLowVoltageRangeTest():
    """
    诊断低压范围测试
    """
    try:
        from testcases.can.can_diag_utils import service_19_check, get_can_node, service_14_check, get_dtc_list_from_19_resp

        V_normal = P.CANInfo.Vnormal
        V_low_stand = P.CANInfo.VlowStand 
        T_stable = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        V_diag_low_min = 8.5
        V_diag_low_max = 9.5
        V_step = 0.1  
        T_settle = 1000 

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{V_normal}V，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{T_stable}s时间至通信稳定")
        ret = can_power_setup_and_communication_check(V_normal, T_stable)
        if ret != 0:
            TestLog("FAIL", "Step1", "期望结果：DUT通信正常，无错误帧。实际结果：电源设置与通信检查失败，结束测试")
            return

        if P.CANInfo.EnableDTCMessaegID_int > 0x10:
            TestLog("INFO", "", "发送DTC使能报文（PowerMode = On）")
            simulation_powermode_signal(P.CANInfo.EnableDTCMessaegID_int, 1)

        ctx.can.set_filter_by_channel(can_channel)
        if not check_bus_error_frames("Step1"):
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常，无错误帧。实际结果：DUT通信正常，无错误帧")

        sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
        node = get_can_node(sa, ta, fa, is_canfd=P.TpInfo.CanFDMode)

        status, _ = service_14_check(node, 0xFFFFFF, [0x54], "肯定响应(54)", timeout=100)

        TestLog("INFO", "Step2",
                f"设置供电电压从{V_normal}V开始以每次{V_step}V向下递减到{V_low_stand}V，读取网络相关DTC，并记录相关电压值")

        current_voltage = V_normal
        dtc_recorded_voltages = []  

        while current_voltage >= V_low_stand:
            ctx.power_ctrl.set_voltage(current_voltage)
            sl_time().sleep(T_settle)

            status, _ = service_14_check(node, 0xFFFFFF, [0x54], "肯定响应(54)", timeout=100)
            sl_time().sleep(500)

            result_19, resp = service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02],
                                               expect_str=f"读取DTC@{current_voltage:.1f}V", DTCStatusMask=0xFF)
            if result_19:
                dtc_list = get_dtc_list_from_19_resp(resp)
                if len(dtc_list) > 0:
                    dtc_recorded_voltages.append(current_voltage)
                    TestLog("INFO", "", f"在{current_voltage:.1f}V读取到{len(dtc_list)}个网络相关DTC")
                else:
                    TestLog("INFO", "", f"在{current_voltage:.1f}V未读取到网络相关DTC")
            else:
                TestLog("INFO", "", f"在{current_voltage:.1f}V诊断服务无响应")

            current_voltage -= V_step
            current_voltage = round(current_voltage, 1)  

        ctx.power_ctrl.set_voltage(V_normal)

        TestLog("INFO", "Step2", f"期望结果：在诊断电压范围{V_diag_low_min}V - {V_diag_low_max}V内读到网络相关DTC，开启网络相关诊断功能")

        if len(dtc_recorded_voltages) > 0:
            voltages_in_range = [v for v in dtc_recorded_voltages if V_diag_low_min <= v <= V_diag_low_max]

            if len(voltages_in_range) > 0:
                TestLog("PASS", "Step2",
                        f"期望结果：在诊断电压低压范围({V_diag_low_min}V-{V_diag_low_max}V)内读到DTC。"
                        f"实际结果：在{min(voltages_in_range):.1f}V-{max(voltages_in_range):.1f}V范围内读取到网络相关DTC")
            else:
                TestLog("FAIL", "Step2",
                        f"期望结果：在诊断电压低压范围({V_diag_low_min}V-{V_diag_low_max}V)内读到DTC。"
                        f"实际结果：读取到DTC的电压值{dtc_recorded_voltages}不在规范要求范围内")
        else:
            TestLog("FAIL", "Step2",
                    f"期望结果：在诊断电压低压范围({V_diag_low_min}V-{V_diag_low_max}V)内读到DTC。"
                    f"实际结果：在整个测试过程中未读取到任何网络相关DTC")

        stop_powermode_signal()
        TestLog("INFO", "", "诊断低压范围测试完成")

    except Exception as e:
        TestLog("FAIL", "诊断低压范围测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "诊断低压范围测试", f"详细错误: {traceback.format_exc()}")
    finally:
        try:
            ctx.power_ctrl.set_voltage(P.CANInfo.Vnormal)
            stop_powermode_signal()
        except:
            pass

def test_TG5_TC6_DiagnosticHighVoltageRangeTest():
    """
    诊断高压范围测试
    """
    try:
        from testcases.can.can_diag_utils import service_19_check, get_can_node, service_14_check, get_dtc_list_from_19_resp

        V_normal = P.CANInfo.Vnormal
        V_high_stand = P.CANInfo.VhighStand  
        T_stable = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        V_diag_high_min = 15.5
        V_diag_high_max = 16.5
        V_step = 0.1  
        T_settle = 1000  

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{V_normal}V，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{T_stable}s时间至通信稳定")
        ret = can_power_setup_and_communication_check(V_normal, T_stable)
        if ret != 0:
            TestLog("FAIL", "Step1", "期望结果：DUT通信正常，无错误帧。实际结果：电源设置与通信检查失败，结束测试")
            return

        if P.CANInfo.EnableDTCMessaegID_int > 0x10:
            TestLog("INFO", "", "发送DTC使能报文（PowerMode = On）")
            simulation_powermode_signal(P.CANInfo.EnableDTCMessaegID_int, 1)

        ctx.can.set_filter_by_channel(can_channel)
        if not check_bus_error_frames("Step1"):
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常，无错误帧。实际结果：DUT通信正常，无错误帧")

        sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
        node = get_can_node(sa, ta, fa, is_canfd=P.TpInfo.CanFDMode)

        status, _ = service_14_check(node, 0xFFFFFF, [0x54], "肯定响应(54)", timeout=100)

        TestLog("INFO", "Step2",
                f"设置供电电压从{V_normal}V开始以每次{V_step}V向上递增到{V_high_stand}V，读取网络相关DTC，并记录相关电压值")

        current_voltage = V_normal
        dtc_recorded_voltages = [] 

        while current_voltage <= V_high_stand:
            ctx.power_ctrl.set_voltage(current_voltage)
            sl_time().sleep(T_settle)

            status, _ = service_14_check(node, 0xFFFFFF, [0x54], "肯定响应(54)", timeout=100)
            sl_time().sleep(500)

            result_19, resp = service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02],
                                               expect_str=f"读取DTC@{current_voltage:.1f}V", DTCStatusMask=0xFF)
            if result_19:
                dtc_list = get_dtc_list_from_19_resp(resp)
                if len(dtc_list) > 0:
                    dtc_recorded_voltages.append(current_voltage)
                    TestLog("INFO", "", f"在{current_voltage:.1f}V读取到{len(dtc_list)}个网络相关DTC")
                else:
                    TestLog("INFO", "", f"在{current_voltage:.1f}V未读取到网络相关DTC")
            else:
                TestLog("INFO", "", f"在{current_voltage:.1f}V诊断服务无响应")

            current_voltage += V_step
            current_voltage = round(current_voltage, 1)  # 避免浮点精度问题

        ctx.power_ctrl.set_voltage(V_normal)

        TestLog("INFO", "Step2", f"期望结果：在诊断电压范围{V_diag_high_min}V - {V_diag_high_max}V内读到网络相关DTC，开启网络相关诊断功能")

        if len(dtc_recorded_voltages) > 0:
            voltages_in_range = [v for v in dtc_recorded_voltages if V_diag_high_min <= v <= V_diag_high_max]

            if len(voltages_in_range) > 0:
                TestLog("PASS", "Step2",
                        f"期望结果：在诊断电压高压范围({V_diag_high_min}V-{V_diag_high_max}V)内读到DTC。"
                        f"实际结果：在{min(voltages_in_range):.1f}V-{max(voltages_in_range):.1f}V范围内读取到网络相关DTC")
            else:
                TestLog("FAIL", "Step2",
                        f"期望结果：在诊断电压高压范围({V_diag_high_min}V-{V_diag_high_max}V)内读到DTC。"
                        f"实际结果：读取到DTC的电压值{dtc_recorded_voltages}不在规范要求范围内")
        else:
            TestLog("FAIL", "Step2",
                    f"期望结果：在诊断电压高压范围({V_diag_high_min}V-{V_diag_high_max}V)内读到DTC。"
                    f"实际结果：在整个测试过程中未读取到任何网络相关DTC")

        stop_powermode_signal()
        TestLog("INFO", "", "诊断高压范围测试完成")

    except Exception as e:
        TestLog("FAIL", "诊断高压范围测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "诊断高压范围测试", f"详细错误: {traceback.format_exc()}")
    finally:
        # 确保恢复正常电压
        try:
            ctx.power_ctrl.set_voltage(P.CANInfo.Vnormal)
            stop_powermode_signal()
        except:
            pass

def test_TG5_TC7_DiagnosticLowVoltageRecoveryTimeTest():
    """
    诊断低压恢复时间测试
    """
    try:
        from testcases.can.can_diag_utils import service_19_check, get_can_node, service_14_check, get_dtc_list_from_19_resp
        import time

        V_normal = P.CANInfo.Vnormal
        V_low_stand = P.CANInfo.VlowStand  
        T_stable = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        T_DiagRecover = 500 
        V_step = 0.1  
        T_settle = 1000  

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{V_normal}V，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{T_stable}s时间至通信稳定")
        ret = can_power_setup_and_communication_check(V_normal, T_stable)
        if ret != 0:
            TestLog("FAIL", "Step1", "期望结果：DUT通信正常，无错误帧。实际结果：电源设置与通信检查失败，结束测试")
            return

        if P.CANInfo.EnableDTCMessaegID_int > 0x10:
            TestLog("INFO", "", "发送DTC使能报文（PowerMode = On）")
            simulation_powermode_signal(P.CANInfo.EnableDTCMessaegID_int, 1)

        ctx.can.set_filter_by_channel(can_channel)
        if not check_bus_error_frames("Step1"):
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常，无错误帧。实际结果：DUT通信正常，无错误帧")

        sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
        node = get_can_node(sa, ta, fa, is_canfd=P.TpInfo.CanFDMode)

        TestLog("INFO", "Step2",
                f"设置供电电压从{V_normal}V开始以每次{V_step}V向下递减到{V_low_stand}V，读取网络相关DTC，并记录相关电压值")

        current_voltage = V_normal
        V_lowoff = None  

        while current_voltage >= V_low_stand:
            ctx.power_ctrl.set_voltage(current_voltage)
            sl_time().sleep(T_settle)

            status, _ = service_14_check(node, 0xFFFFFF, [0x54], "肯定响应(54)", timeout=100)
            sl_time().sleep(500)

            result_19, resp = service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02],
                                               expect_str=f"读取DTC@{current_voltage:.1f}V", DTCStatusMask=0x09)
            if result_19:
                dtc_list = get_dtc_list_from_19_resp(resp)
                if len(dtc_list) > 0:
                    TestLog("INFO", "", f"在{current_voltage:.1f}V读取到{len(dtc_list)}个网络相关DTC")
                else:
                    V_lowoff = current_voltage
                    TestLog("INFO", "Step3", f"在{current_voltage:.1f}V未读取到网络相关DTC，记录Vlowoff = {V_lowoff:.1f}V")
                    break
            else:
                V_lowoff = current_voltage
                TestLog("INFO", "Step3", f"在{current_voltage:.1f}V诊断服务无响应，记录Vlowoff = {V_lowoff:.1f}V")
                break

            current_voltage -= V_step
            current_voltage = round(current_voltage, 1)

        if V_lowoff is None:
            TestLog("FAIL", "Step3", "在整个电压递减过程中始终能读取到网络相关DTC，无法确定Vlowoff")
            ctx.power_ctrl.set_voltage(V_normal)
            stop_powermode_signal()
            return

        V_recover = round(V_lowoff + 0.1, 1)
        TestLog("INFO", "Step4",
                f"恢复供电电压到正常诊断电压范围，设置供电电压为Vlowoff+0.1={V_recover:.1f}V，并记录此时恢复到正常诊断电压范围内电压值的时间为TRecoverStart")

        ctx.power_ctrl.set_voltage(V_recover)
        T_RecoverStart = sl_time().timestamp() * 1000
        TestLog("INFO","Step4",f"T_RecoverStart={T_RecoverStart}")

        TestLog("INFO", "Step5", "以1ms周期时间发送诊断指令$19 02 09持续读取DTC，记录第一次成功读取到DUT支持的节点超时故障码的时间为TRecoverEnd")

        T_RecoverEnd = None
        max_wait_time = 2000  
        start_time = sl_time().timestamp() * 1000

        while (sl_time().timestamp() * 1000 - start_time) < max_wait_time:
            result_19, resp = service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02],
                                               expect_str="读取DTC", DTCStatusMask=0x09)
            if result_19:
                dtc_list = get_dtc_list_from_19_resp(resp)
                if len(dtc_list) > 0:
                    T_RecoverEnd = sl_time().timestamp() * 1000
                    TestLog("INFO","",f"{T_RecoverEnd = }")
                    TestLog("INFO", "Step5", f"在{T_RecoverEnd - T_RecoverStart:.1f}ms时首次成功读取到节点超时故障码")
                    break
            sl_time().sleep(1)
            
        if T_RecoverEnd is None:
            TestLog("FAIL", "Step5", f"在{max_wait_time}ms内未能读取到节点超时故障码")
            ctx.power_ctrl.set_voltage(V_normal)
            stop_powermode_signal()
            return

        T_Recover = T_RecoverEnd - T_RecoverStart
        TestLog("INFO", "Step6", f"计算诊断低电压恢复时间TRecoverEnd - TRecoverStart = {T_Recover:.1f}ms")

        if T_Recover < T_DiagRecover:
            TestLog("PASS", "Step6",
                    f"期望结果：TRecoverEnd - TRecoverStart < T_DiagRecover({T_DiagRecover}ms)。"
                    f"实际结果：{T_Recover:.1f}ms < {T_DiagRecover}ms，满足规范要求")
        else:
            TestLog("FAIL", "Step6",
                    f"期望结果：TRecoverEnd - TRecoverStart < T_DiagRecover({T_DiagRecover}ms)。"
                    f"实际结果：{T_Recover:.1f}ms >= {T_DiagRecover}ms，不满足规范要求")

        ctx.power_ctrl.set_voltage(V_normal)
        stop_powermode_signal()
        TestLog("INFO", "", "诊断低压恢复时间测试完成")

    except Exception as e:
        TestLog("FAIL", "诊断低压恢复时间测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "诊断低压恢复时间测试", f"详细错误: {traceback.format_exc()}")
    finally:
        try:
            ctx.power_ctrl.set_voltage(P.CANInfo.Vnormal)
            stop_powermode_signal()
        except:
            pass

def test_TG5_TC8_DiagnosticHighVoltageRecoveryTimeTest():
    """
    诊断高压恢复时间测试
    """
    try:
        from testcases.can.can_diag_utils import service_19_check, get_can_node, service_14_check, get_dtc_list_from_19_resp
        import time

        V_normal = P.CANInfo.Vnormal
        V_high_stand = P.CANInfo.VhighStand  
        T_stable = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        T_DiagRecover = 500  
        V_step = 0.1 
        T_settle = 1000 

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{V_normal}V，将KL30上电，根据DUT通信唤醒方式，使用KL15上电或网络管理报文的方式唤醒CAN网络，等待{T_stable}s时间至通信稳定")
        ret = can_power_setup_and_communication_check(V_normal, T_stable)
        if ret != 0:
            TestLog("FAIL", "Step1", "期望结果：DUT通信正常，无错误帧。实际结果：电源设置与通信检查失败，结束测试")
            return

        if P.CANInfo.EnableDTCMessaegID_int > 0x10:
            TestLog("INFO", "", "发送DTC使能报文（PowerMode = On）")
            simulation_powermode_signal(P.CANInfo.EnableDTCMessaegID_int, 1)

        ctx.can.set_filter_by_channel(can_channel)
        if not check_bus_error_frames("Step1"):
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常，无错误帧。实际结果：DUT通信正常，无错误帧")

        sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
        node = get_can_node(sa, ta, fa, is_canfd=P.TpInfo.CanFDMode)

        TestLog("INFO", "Step2",
                f"设置供电电压从{V_normal}V开始以每次{V_step}V向上递增到{V_high_stand}V，读取网络相关DTC，并记录相关电压值")

        current_voltage = V_normal
        V_highoff = None 

        while current_voltage <= V_high_stand:
            ctx.power_ctrl.set_voltage(current_voltage)
            sl_time().sleep(T_settle)

            status, _ = service_14_check(node, 0xFFFFFF, [0x54], "肯定响应(54)", timeout=100)
            sl_time().sleep(500)

            result_19, resp = service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02],
                                               expect_str=f"读取DTC@{current_voltage:.1f}V", DTCStatusMask=0x09)
            if result_19:
                dtc_list = get_dtc_list_from_19_resp(resp)
                if len(dtc_list) > 0:
                    TestLog("INFO", "", f"在{current_voltage:.1f}V读取到{len(dtc_list)}个网络相关DTC")
                else:
                    V_highoff = current_voltage
                    TestLog("INFO", "Step3", f"在{current_voltage:.1f}V未读取到网络相关DTC，记录Vhighoff = {V_highoff:.1f}V")
                    break
            else:
                V_highoff = current_voltage
                TestLog("INFO", "Step3", f"在{current_voltage:.1f}V诊断服务无响应，记录Vhighoff = {V_highoff:.1f}V")
                break

            current_voltage += V_step
            current_voltage = round(current_voltage, 1)

        if V_highoff is None:
            TestLog("FAIL", "Step3", "在整个电压递增过程中始终能读取到网络相关DTC，无法确定Vhighoff")
            ctx.power_ctrl.set_voltage(V_normal)
            stop_powermode_signal()
            return

        V_recover = round(V_highoff - 0.1, 1)
        TestLog("INFO", "Step4",
                f"恢复供电电压到正常诊断电压范围，设置供电电压为Vhighoff-0.1={V_recover:.1f}V，并记录此时恢复到正常诊断电压范围内电压值的时间为TRecoverStart")

        ctx.power_ctrl.set_voltage(V_recover)
        T_RecoverStart = sl_time().timestamp * 1000 
        TestLog("INFO","",f"{T_RecoverStart = }")

        TestLog("INFO", "Step5", "以1ms周期时间发送诊断指令$19 02 09持续读取DTC，记录第一次成功读取到DUT支持的节点超时故障码的时间为TRecoverEnd")

        T_RecoverEnd = None
        max_wait_time = 2000  
        start_time = sl_time().timestamp * 1000

        while (sl_time().timestamp * 1000 - start_time) < max_wait_time:
            result_19, resp = service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02],
                                               expect_str="读取DTC", DTCStatusMask=0x09)
            if result_19:
                dtc_list = get_dtc_list_from_19_resp(resp)
                if len(dtc_list) > 0:
                    T_RecoverEnd = sl_time().timestamp * 1000
                    TestLog("INFO","",f"{T_RecoverEnd = }")
                    TestLog("INFO", "Step5", f"在{T_RecoverEnd - T_RecoverStart:.1f}ms时首次成功读取到节点超时故障码")
                    break
            sl_time().sleep(1) 

        if T_RecoverEnd is None:
            TestLog("FAIL", "Step5", f"在{max_wait_time}ms内未能读取到节点超时故障码")
            ctx.power_ctrl.set_voltage(V_normal)
            stop_powermode_signal()
            return

        T_Recover = T_RecoverEnd - T_RecoverStart
        TestLog("INFO", "Step6", f"计算诊断高电压恢复时间TRecoverEnd - TRecoverStart = {T_Recover:.1f}ms")

        if T_Recover < T_DiagRecover:
            TestLog("PASS", "Step6",
                    f"期望结果：TRecoverEnd - TRecoverStart < T_DiagRecover({T_DiagRecover}ms)。"
                    f"实际结果：{T_Recover:.1f}ms < {T_DiagRecover}ms，满足规范要求")
        else:
            TestLog("FAIL", "Step6",
                    f"期望结果：TRecoverEnd - TRecoverStart < T_DiagRecover({T_DiagRecover}ms)。"
                    f"实际结果：{T_Recover:.1f}ms >= {T_DiagRecover}ms，不满足规范要求")

        ctx.power_ctrl.set_voltage(V_normal)
        stop_powermode_signal()
        TestLog("INFO", "", "诊断高压恢复时间测试完成")

    except Exception as e:
        TestLog("FAIL", "诊断高压恢复时间测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "诊断高压恢复时间测试", f"详细错误: {traceback.format_exc()}")
    finally:
        try:
            ctx.power_ctrl.set_voltage(P.CANInfo.Vnormal)
            stop_powermode_signal()
        except:
            pass

def get_all_test_cases():
    """获取CAN测试用例"""
    current_module = inspect.getmodule(inspect.currentframe())

    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj

    return test_cases
