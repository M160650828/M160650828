import inspect
import sys
import os
import time

from env.config import *
from uvtest.testlog import TestLog
from uvtest.framework import TestFixture
from common.context import ctx
from common.control import TestStart, TestEnd
from common.params import P
from common.wakeup import WakeupStart
from common.voltage_control import voltage_threshold_test_with_validation
from .lin_module import LinCommChecker
from .lin_module import lin_initialization, lin_deinitialization
from .lin_module import (
    ActivateDut,
    stop_lin_simulation,
    monitor_lin_communication,
    verify_lin_messages,
    lin_communication_bitrate_reset,
    get_test_case_mode,
    lin_fault_injection,
    check_communication_recovery_time,
    _start_lin_simulation_for_dut,
    _setup_lin_simulation_for_dut,
    _current_dut_mode,
    send_wakeup,
)


class LINTestFixture(TestFixture):
    def group_setup(self, context=None):
        lin_initialization()

    def group_teardown(self, context=None):
        lin_deinitialization()

    def case_setup(self, context=None):
        if context:
            TestStart(context["test_name"])

    def case_teardown(self, context=None):
        stop_lin_simulation()
        TestEnd("")
        TestLog("INFO", "测试结束", "执行测试结束和去初始化")


def test_TG1_TC1_PhyLayer_Resistance_Test():
    """
    电阻测试
    """
    try:

        pass
        TestLog("FAIL", "Step1", "Not Suport")
        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "电阻测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "电阻测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC2_PhyLayer_LowVoltageRangeTest():
    """
    LIN物理层低电压范围测试
    """
    # 测试参数
    rVlowStand = P.LINInfo.VlowStand  # 标准通信最小电压标准值
    rVtestRange = P.LINInfo.VtestRange  # 测试电压测试范围
    rVstep = P.LINInfo.Vstep  # 每次测试电压步进值
    rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
    rTvStepDelay = P.LINInfo.TvStepDelay_s  # 每次测试电压设置后等待时间
    rSimulationActivate = P.LINInfo.SimulationActivate  # 仿真激活标志
    rTdefaultWait = P.LINInfo.TdefaultWait_s  # 默认等待时间
    try:
        ctx.lin.clear_messages()
        ctx.lin.set_info('gLinErrorFrameCount', 0)
        ctx.lin.set_info('gLinFrameIDCount', 0)

        ctx.lin.clear_messages()
        ctx.lin.set_info('gLinErrorFrameCount', 0)
        ctx.lin.set_info('gLinFrameIDCount', 0)

        # 激活DUT
        TestLog("INFO", "Step4", "激活DUT")
        ret = ActivateDut(rSimulationActivate, rTdefaultWait)
        if ret != 0:
            TestLog("INFO", "LIN低电压通信范围测试", "DUT激活失败，结束测试")
            TestEnd("")
            return

        # Step2: 验证通信步进停止的电压阈值
        stop_success, voltage_low_stop = voltage_threshold_test_with_validation(LinCommChecker(),
                                                                                test_type="stop",
                                                                                start_voltage=rVlowStand + rVtestRange,
                                                                                end_voltage=rVlowStand - rVtestRange,
                                                                                step=-rVstep,
                                                                                step_delay=rTvStepDelay,
                                                                                validation_voltage=rVlowStand,
                                                                                tolerance=0.0,

                                                                                )

        if not stop_success or voltage_low_stop is None:
            TestEnd("")
            return

        # Step3: 验证通信步进恢复的电压阈值
        resume_success, voltage_resume = voltage_threshold_test_with_validation(LinCommChecker(),
                                                                                test_type="resume",
                                                                                start_voltage=voltage_low_stop,
                                                                                end_voltage=rVlowStand + rVtestRange,
                                                                                step=rVstep,
                                                                                step_delay=rTvStepDelay,
                                                                                validation_voltage=rVlowStand,
                                                                                tolerance=rVstep,

                                                                                )

        TestLog("INFO", "LIN低电压通信范围测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "LIN低压通信范围测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "LIN低压通信范围测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC3_PhyLayer_HighVoltageRangeTest():
    """
    LIN物理层高电压范围测试
    """
    # 测试参数
    rVnormal = P.LINInfo.Vnormal  # 电源正常电压
    rVhighStand = P.LINInfo.VhighStand  # 标准通信最大电压标准值
    rVtestRange = P.LINInfo.VtestRange  # 测试电压测试范围
    rVstep = P.LINInfo.Vstep  # 每次测试电压步进值
    rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
    rTvStepDelay = P.LINInfo.TvStepDelay_s  # 每次测试电压设置后等待时间
    rSimulationActivate = P.LINInfo.SimulationActivate  # 仿真激活标志
    rTdefaultWait = P.LINInfo.TdefaultWait_s  # 默认等待时间
    try:
        ctx.lin.clear_messages()
        ctx.lin.set_info('gLinErrorFrameCount', 0)
        ctx.lin.set_info('gLinFrameIDCount', 0)

        # 激活DUT
        TestLog("INFO", "Step4", "激活DUT")
        ret = ActivateDut(rSimulationActivate, rTdefaultWait)
        if ret != 0:
            TestLog("INFO", "LIN高电压通信范围测试", "DUT激活失败，结束测试")
            TestEnd("")
            return

        # Step2: 验证通信步进停止的电压阈值
        stop_success, voltage_high_stop = voltage_threshold_test_with_validation(LinCommChecker(),
                                                                                 test_type="stop",
                                                                                 start_voltage=rVhighStand - rVtestRange,
                                                                                 end_voltage=rVhighStand + rVtestRange,
                                                                                 step=rVstep,
                                                                                 step_delay=rTvStepDelay,
                                                                                 validation_voltage=rVhighStand,
                                                                                 tolerance=0.0,

                                                                                 )

        if not stop_success or voltage_high_stop is None:
            TestEnd("")
            return

        # Step3: 验证通信步进恢复的电压阈值
        resume_success, voltage_resume = voltage_threshold_test_with_validation(LinCommChecker(),
                                                                                test_type="resume",
                                                                                start_voltage=voltage_high_stop,
                                                                                end_voltage=rVhighStand - rVtestRange,
                                                                                step=-rVstep,
                                                                                step_delay=rTvStepDelay,
                                                                                validation_voltage=rVhighStand,
                                                                                tolerance=-rVstep,

                                                                                )

        TestLog("INFO", "LIN高电压通信范围测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "LIN高电压通信范围测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "LIN高电压通信范围测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC4_PhyLayer_DominantVlotage_Test():
    """
    显性电压测试,需要示波器
    """
    try:
        pass
        TestLog("FAIL", "Step1", "Not Suport")
        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "显性电压测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "显性电压测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC5_PhyLayer_RecessiveVlotage_Test():
    """
    Lin隐性电压测试,需要示波器
    """
    try:
        pass
        TestLog("FAIL", "Step1", "Not Suport")
        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "Lin隐性电压测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "Lin隐性电压测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC6_PhyLayer_GndOffset_Test():
    """
    地漂电源偏移测试
    """
    try:
        pass
        TestLog("FAIL", "Step1", "Not Suport")
        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "地漂电源偏移测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "地漂电源偏移测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC7_PhyLayer_BitTime_Test():
    """
    位时间测试
    """
    try:
        pass
        TestLog("FAIL", "Step1", "Not Suport")
        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "位时间测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "位时间测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC8_PhyLayer_Slope_Test():
    """
    斜率测试
    """
    try:
        pass
        TestLog("FAIL", "Step1", "Not Suport")
        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "斜率测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "斜率测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC9_PhyLayer_DutyRatio_Test():
    """
    占空比测试
    """
    try:
        pass
        TestLog("FAIL", "Step1", "Not Suport")
        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "占空比测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "占空比测试", f"详细错误: {traceback.format_exc()}")


def test_TG1_TC10_PhyLayer_Capacitance_Test():
    """
    电容测试
    """
    try:
        pass
        TestLog("FAIL", "Step1", "Not Suport")
        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "电容测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "电容测试", f"详细错误: {traceback.format_exc()}")


def test_TG2_TC1_ComLayer_FrameID_Test():
    """
    LIN帧ID测试
    """
    # 测试参数配置
    rTdefaultWait = P.LINInfo.TdefaultWait_s  # 默认等待时间
    rSimulationActivate = P.LINInfo.SimulationActivate  # 仿真激活标志
    try:
        ctx.lin.clear_messages()
        ctx.lin.set_info('gLinErrorFrameCount', 0)
        ctx.lin.set_info('gLinFrameIDCount', 0)

        # 激活DUT
        TestLog("INFO", "Step1", "激活DUT")
        ret = ActivateDut(rSimulationActivate, rTdefaultWait)
        if ret != 0:
            TestLog("INFO", "LIN帧ID测试", "DUT激活失败，结束测试")
            TestEnd("")
            return

        # Step2: 持续监控通信
        msgs, direction = monitor_lin_communication(duration_sec=20)

        # Step3: 检查LIN帧ID是否与通信数据库定义一致
        verify_lin_messages(msgs, direction, "id", test_name="帧ID测试")

        TestLog("INFO", "LIN帧ID测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "LIN帧ID测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "LIN帧ID测试", f"详细错误: {traceback.format_exc()}")


def test_TG2_TC2_ComLayer_FrameDlc_Test():
    """
    LIN帧数据长度测试
    """
    # 测试参数配置
    rTdefaultWait = P.LINInfo.TdefaultWait_s  # 默认等待时间
    rSimulationActivate = P.LINInfo.SimulationActivate  # 仿真激活标志
    try:
        ctx.lin.clear_messages()
        ctx.lin.set_info('gLinErrorFrameCount', 0)
        ctx.lin.set_info('gLinFrameIDCount', 0)

        ctx.lin.clear_messages()
        ctx.lin.set_info('gLinErrorFrameCount', 0)
        ctx.lin.set_info('gLinFrameIDCount', 0)

        # 激活DUT
        TestLog("INFO", "Step4", "激活DUT")
        ret = ActivateDut(rSimulationActivate, rTdefaultWait)
        if ret != 0:
            TestLog("INFO", "LIN帧ID测试", "DUT激活失败，结束测试")
            TestEnd("")
            return

        # Step2: 持续监控通信
        msgs, direction = monitor_lin_communication(duration_sec=30)

        # Step3: 检查LIN帧DLC是否与通信数据库定义一致
        verify_lin_messages(msgs, direction, "dlc", test_name="帧DLC测试")

        TestLog("INFO", "LIN帧DLC测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "LIN帧DLC测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "LIN帧DLC测试", f"详细错误: {traceback.format_exc()}")


def test_TG2_TC3_ComLayer_FrameHeaderLength_Test():
    """
    Lin帧头长度测试
    """
    try:
        pass
        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "Lin帧头长度测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "Lin帧头长度测试", f"详细错误: {traceback.format_exc()}")


def test_TG2_TC4_ComLayer_FrameLength_Test():
    """
    Lin帧长度
    """
    try:
        pass
        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "Lin帧长度", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "Lin帧长度", f"详细错误: {traceback.format_exc()}")


def test_TG2_TC5_ComLayer_FrameChecksum_Test():
    """
    帧校验方式测试
    """
    # 测试参数配置
    rTdefaultWait = P.LINInfo.TdefaultWait_s  # 默认等待时间
    rSimulationActivate = P.LINInfo.SimulationActivate  # 仿真激活标志
    try:
        TestLog("INFO", "帧校验方式测试", "开始测试")
        ctx.lin.clear_messages()
        ctx.lin.set_info('gLinErrorFrameCount', 0)
        ctx.lin.set_info('gLinFrameIDCount', 0)
        TestLog("INFO", "Step1", "激活DUT")
        ret = ActivateDut(rSimulationActivate, rTdefaultWait)
        if ret != 0:
            TestLog("INFO", "帧校验方式测试", "DUT激活失败，结束测试")
            TestEnd("")
            return   
        if get_test_case_mode()=="master":
            from common.wakeup import WakeupStop
            monitor_lin_communication(2)
            WakeupStop()
            msgs, direction = monitor_lin_communication(60,False)
            verify_lin_messages(msgs, direction,"0x3c", test_name="帧校验方式测试")
            WakeupStart()
            time.sleep(2)
        else:
            from .lin_module import send_message,rcv_message,get_nand_id
            monitor_lin_communication(2)
            TestLog("INFO", "Step2", "SEND 0X3C 报文 "+ hex(get_nand_id())+"  02 10 01 ")
            send_message(0X3C,8,bytes([get_nand_id(),0X02,0X10,0X01]))
            time.sleep(0.01)
            rcv_message(0X3D)
            time.sleep(0.01)
            msgs, direction = monitor_lin_communication(2,False)
            verify_lin_messages(msgs, direction,"0x3d", test_name="帧校验方式测试")
        # 激活DUT

        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "帧校验方式测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "帧校验方式测试", f"详细错误: {traceback.format_exc()}") 


def test_TG2_TC6_ComLayer_BreakField_DominantVlotageLength_Test():
    """
    同步间隔场显性电平长度测试
    """
    try:
        pass
        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "同步间隔场显性电平长度测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "同步间隔场显性电平长度测试", f"详细错误: {traceback.format_exc()}")


def test_TG2_TC7_ComLayer_SyncField_Length_Test():
    """
    同步界定符电平长度测试
    """
    try:
        pass
        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "同步界定符电平长度测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "同步界定符电平长度测试", f"详细错误: {traceback.format_exc()}")


def test_TG2_TC8_ComLayer_SchedTableSlot_Test():
    """
    调度表时隙测试
    """
    rSimulationActivate = P.LINInfo.SimulationActivate  # 仿真激活标志
    try:
        if get_test_case_mode() == "slave":
            TestLog("FAIL", "调度表时隙测试", f"测试主节点使用,不是从节点用例")
            TestEnd("")
            return
        ret = ActivateDut(rSimulationActivate, 0)
        if ret != 0:
            TestLog("INFO", "调度表时隙测试", "DUT激活失败，结束测试")
            TestEnd("")
            return    
        msgs, direction = monitor_lin_communication(5*60,True)
        verify_lin_messages(msgs, direction,"solt_time", test_name="调度表时隙测试")
        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "调度表时隙测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "调度表时隙测试", f"详细错误: {traceback.format_exc()}")


def test_TG2_TC9_ComLayer_SchedTableSequence_Test():
    """
    调度表顺序测试
    """
    rSimulationActivate = P.LINInfo.SimulationActivate  # 仿真激活标志
    try:
        if get_test_case_mode() == "slave":
            TestLog("FAIL", "调度表顺序测试", f"测试主节点使用,不是从节点用例")
            TestEnd("")
        ret = ActivateDut(rSimulationActivate, 0)
        if ret != 0:
            TestLog("INFO", "调度表顺序测试", "DUT激活失败，结束测试")
            TestEnd("")
            return    
        msgs, direction = monitor_lin_communication(5*60,True)
        verify_lin_messages(msgs, direction,"Sequence", test_name="调度表顺序测试")
        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "调度表顺序测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "调度表顺序测试", f"详细错误: {traceback.format_exc()}")


def test_TG2_TC10_ComLayer_BaudrateCompatibility_Test():
    """
    波特率兼容测试
    """
    # 测试参数配置
    rTdefaultWait = P.LINInfo.TdefaultWait_s  # 默认等待时间
    rSimulationActivate = P.LINInfo.SimulationActivate  # 仿真激活标志
    normal = P.LINInfo.BRnominal
    deviation = P.LINInfo.BRdeviationominal
    try:
        TestLog("INFO", "波特率兼容测试", "开始测试")
        ctx.lin.clear_messages()
        ctx.lin.set_info('gLinErrorFrameCount', 0)
        ctx.lin.set_info('gLinFrameIDCount', 0)
        # 激活DUT
        TestLog("INFO", "Step1", "激活DUT")
        ret = ActivateDut(rSimulationActivate, rTdefaultWait)
        if ret != 0:
            TestLog("INFO", "波特率兼容测试", "DUT激活失败，结束测试")
            TestEnd("")
            return
        TestLog("INFO", " Step3", "设置波特率" + str(normal * 1000 + normal * deviation * 10))
        lin_communication_bitrate_reset(bitrate=(normal * 1000 + normal * deviation * 10))
        msgs, direction = monitor_lin_communication(duration_sec=5 * 60)
        verify_lin_messages(msgs, direction, "dlc", test_name="设置波特率")

        TestLog("INFO", "Step4", "设置波特率" + str(normal * 1000))
        lin_communication_bitrate_reset(bitrate=(normal * 1000))
        msgs, direction = monitor_lin_communication(duration_sec=60)
        verify_lin_messages(msgs, direction, "dlc", test_name="设置波特率")

        TestLog("INFO", "Step5", "设置波特率" + str(normal * 1000 - normal * deviation * 10))
        lin_communication_bitrate_reset(bitrate=(normal * 1000 - normal * deviation * 10))
        msgs, direction = monitor_lin_communication(duration_sec=5 * 60)
        verify_lin_messages(msgs, direction, "dlc", test_name="设置波特率")

        TestLog("INFO", "Step6", "设置波特率" + str(normal * 1000))
        lin_communication_bitrate_reset(bitrate=(normal * 1000))
        msgs, direction = monitor_lin_communication(duration_sec=60)
        verify_lin_messages(msgs, direction, "dlc", test_name="设置波特率")

        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "波特率兼容测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "波特率兼容测试", f"详细错误: {traceback.format_exc()}")


def test_TG3_TC1_NMLayer_StartUpTime_Test():
    """
    启动时间测试
    """   
    rSimulationActivate = P.LINInfo.SimulationActivate  # 仿真激活标志
    Repeat = P.LINInfo.NdefaultRepeat
    awake_ms =  P.LINInfo.Tawake_ms/1000
    try:
        if get_test_case_mode() == "master":
            from .lin_module import get_powerup_to_first_frame_time
            for i in range(Repeat):
                ret = ActivateDut(rSimulationActivate, 0,2)
                if ret != 0:
                    TestLog("INFO", "启动时间测试", "DUT激活失败，结束测试")
                    TestEnd("")
                    return  
                time.sleep(1)
                time_val = get_powerup_to_first_frame_time()
                if time_val>130:
                    TestLog("FAIL", "启动时间测试", "启动时间超时，时长"+str(time_val))
                    TestEnd("")
                    return  
        else:
            from .lin_module import get_powerup_to_first_frame_time
            for i in range(Repeat):
                ret = ActivateDut(rSimulationActivate, 1,2)
                if ret != 0:
                    TestLog("INFO", "启动时间测试", "DUT激活失败，结束测试")
                    TestEnd("")
                    return  
                time.sleep(1)
                time_val = get_powerup_to_first_frame_time()
                if time_val>awake_ms:
                    TestLog("FAIL", "启动时间测试", "启动时间超时，时长"+str(time_val))
                    TestEnd("")
                    return  
                else:
                    TestLog("PASS", "启动时间测试", "测试成功"+str(time_val)+"<"+str(awake_ms))
        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "启动时间测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "启动时间测试", f"详细错误: {traceback.format_exc()}") 


def test_TG3_TC2_NMLayer_WakeUpTime_Test():
    """
    网络唤醒测试
    """
    rTdefaultWait = P.LINInfo.TdefaultWait_s  # 默认等待时间
    rSimulationActivate = P.LINInfo.SimulationActivate  # 仿真激活标志
    try:
        if get_test_case_mode() == "master":
            pass
        else:
            pass
        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "网络唤醒测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "网络唤醒测试", f"详细错误: {traceback.format_exc()}")


def test_TG3_TC3_NMLayer_Sleep_Test():
    """
    网络休眠测试
    """
    rTdefaultWait = P.LINInfo.TdefaultWait_s  # 默认等待时间
    rSimulationActivate = P.LINInfo.SimulationActivate  # 仿真激活标志
    Isleep = P.LINInfo.SleepCurrent  # 睡眠电流
    SilentTime =  P.LINInfo.SilentTime  # 静态时间
    try:
        ctx.lin.clear_messages()
        ctx.lin.set_info('gLinErrorFrameCount', 0)
        ctx.lin.set_info('gLinFrameIDCount', 0)
        TestLog("INFO", "Step1", "激活DUT")
        ret = ActivateDut(rSimulationActivate, rTdefaultWait)
        if ret != 0:
            TestLog("INFO", "网络休眠测试", "DUT激活失败，结束测试")
            TestEnd("")
            return   
        if get_test_case_mode()=="master":
            from common.wakeup import WakeupStop
            monitor_lin_communication(2)
            WakeupStop()
            msgs, direction = monitor_lin_communication(60,False)
            verify_lin_messages(msgs, direction,"0x3c", test_name="网络休眠测试")
            WakeupStart()
            time.sleep(2)
        else:
            from .lin_module import send_message
            monitor_lin_communication(2)
            send_message(0X3C,8,bytes([0,0XFF,0XFF,0XFF,0XFF,0XFF,0XFF,0XFF]))
            time.sleep(1)
            status,I_sleep_test = ctx.power_ctrl.get_current()
            if I_sleep_test> Isleep:
                TestLog("FAIL", "网络休眠测试", f"测试执行出错:{I_sleep_test}>{Isleep}")
            else:
                TestLog("PASS", "网络休眠测试", f"睡眠后电流:{I_sleep_test}")
            send_wakeup()
            time.sleep(SilentTime)
            status,I_sleep_test = ctx.power_ctrl.get_current()
            if I_sleep_test> Isleep:
                TestLog("FAIL", "网络休眠测试", f"静态后电流:{I_sleep_test}>{Isleep}")
            else:
                TestLog("PASS", "网络休眠测试", f"静态后电流:{I_sleep_test}")
        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "网络休眠测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "网络休眠测试", f"详细错误: {traceback.format_exc()}")


def test_TG4_TC1_FauLayer_LINOpen_Test():
    """
    LIN线断开测试
    """
    try:
        # 从配置文件获取测试参数
        V_normal = P.LINInfo.Vnormal  # 正常电压
        T_defaultWait = P.LINInfo.TdefaultWait_s  # 通信稳定时间(s)
        T_faultDelay = P.LINInfo.TfaultDelay_s  # 故障保持时间(s)，典型值1min
        T_faultRecoveryMax = P.LINInfo.TfaultRecoveryMax_ms  # 故障恢复时间(s)
        N_faultRepeat = P.LINInfo.NfaultRepeat  # 测试循环次数
        SimulationActivate = P.LINInfo.SimulationActivate  # 是否需要仿真节点

        ctrl_can_channel = P.ECUInfo.BOBControlCan
        target_lin_channel = P.ECUInfo.ETS6124LinChannel

        test_results = []
        overall_result = True

        TestLog("INFO", "LIN线断开测试", "开始执行测试用例")

        for round_num in range(1, N_faultRepeat + 1):
            TestLog("INFO", "测试轮次", f"开始第{round_num}轮测试")

            # 步骤1: 使用标准电源设置与通信检查
            TestLog("INFO", "测试环境设置", f"开始设置通道{ctrl_can_channel}的测试环境")
            ret = ActivateDut(SimulationActivate, T_defaultWait)
            if ret != 0:
                TestLog("FAIL", "测试环境设置", "DUT通信配置异常，测试结束")
                return
            # 步骤2: 制造LIN线断开故障
            TestLog("INFO", "LIN断路测试", f"开始第{round_num}轮LIN断路测试")
            fault_result = lin_fault_injection('LIN_Open', target_lin_channel,
                                               T_faultDelay * 1000)

            # 检查返回值类型
            if isinstance(fault_result, tuple) and len(fault_result) == 2:
                fault_success, t1 = fault_result
            else:
                fault_success = fault_result
                t1 = None

            if not fault_success:
                TestLog("FAIL", "故障注入", "LIN线断开故障注入失败")
                return
            TestLog("INFO", "故障清除", f"CAN_H线断开故障已清除，记录时刻t1: {t1}")

            recovery_success, T_recovery = check_communication_recovery_time(t1, T_faultRecoveryMax)

            # 检查恢复时间是否满足要求
            if recovery_success:
                TestLog("PASS", "通信恢复", f"DUT通信已恢复，恢复时间: {T_recovery:.2f}ms")
                if T_recovery <= T_faultRecoveryMax:
                    TestLog("PASS", "恢复时间检查",
                            f"恢复时间({T_recovery:.2f}ms) ≤ 允许时间({T_faultRecoveryMax}ms)")
                    recovery_ok = True
                else:
                    TestLog("FAIL", "恢复时间检查",
                            f"恢复时间({T_recovery:.2f}ms) > 允许时间({T_faultRecoveryMax}ms)")
                    recovery_ok = False
                    overall_result = False
            else:
                TestLog("FAIL", "通信恢复", f"DUT在{T_faultRecoveryMax}ms内通信未恢复")
                recovery_ok = False
                overall_result = False

            # 步骤4: 控制DUT下电，等待30s
            TestLog("INFO", "DUT下电", "控制DUT下电，等待30s")
            # 停用DUT
            ctx.bob_ctrl.set_power('KL30', False)
            time.sleep(30.0)

            # 记录本轮测试结果
            round_result = fault_success and recovery_ok
            test_results.append({
                'round': round_num,
                'recovery_time': T_recovery if recovery_success else T_faultRecoveryMax,
                'round_result': round_result
            })

            TestLog("INFO", "测试轮次结果",
                    f"第{round_num}轮测试结果 - 故障状态: {'通过' if round_result else '失败'}, "
                    f"恢复状态: {'通过' if recovery_ok else '失败'}, "
                    f"恢复时间: {T_recovery if recovery_success else '超时'}ms")

        # 最终评价
        if overall_result:
            TestLog("PASS", "最终结果", "LIN线断开测试用例通过")
        else:
            TestLog("FAIL", "最终结果", "LIN线断开测试用例失败")

    except Exception as e:
        TestLog("FAIL", "LIN线断开测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "LIN线断开测试", f"详细错误: {traceback.format_exc()}")


def test_TG4_TC2_FauLayer_LINShortVbatt_Test():
    """
    LIN线与电源短路测试
    """
    try:
        # 从配置文件获取测试参数
        V_normal = P.LINInfo.Vnormal  # 正常电压
        T_defaultWait = P.LINInfo.TdefaultWait_s  # 通信稳定时间(s)
        T_faultDelay = P.LINInfo.TfaultDelay_s  # 故障保持时间(s)，典型值1min
        T_faultRecoveryMax = P.LINInfo.TfaultRecoveryMax_ms  # 故障恢复时间(s)
        N_faultRepeat = P.LINInfo.NfaultRepeat  # 测试循环次数
        SimulationActivate = P.LINInfo.SimulationActivate  # 是否需要仿真节点

        ctrl_can_channel = P.ECUInfo.BOBControlCan
        target_lin_channel = P.ECUInfo.ETS6124LinChannel

        test_results = []
        overall_result = True

        TestLog("INFO", "LIN线与电源短路测试", "开始执行测试用例")

        for round_num in range(1, N_faultRepeat + 1):
            TestLog("INFO", "测试轮次", f"开始第{round_num}轮测试")

            # 步骤1: 使用标准电源设置与通信检查
            TestLog("INFO", "测试环境设置", f"开始设置通道{ctrl_can_channel}的测试环境")
            ret = ActivateDut(SimulationActivate, T_defaultWait)
            if ret != 0:
                TestLog("FAIL", "测试环境设置", "DUT通信配置异常，测试结束")
                return
            # 步骤2: 制造LIN线与电源短路
            TestLog("INFO", "LIN线与电源短路测试", f"开始第{round_num}轮LIN断路测试")
            fault_result = lin_fault_injection('LIN_short_power', target_lin_channel,
                                               T_faultDelay * 1000)

            # 检查返回值类型
            if isinstance(fault_result, tuple) and len(fault_result) == 2:
                fault_success, t1 = fault_result
            else:
                fault_success = fault_result
                t1 = None

            if not fault_success:
                TestLog("FAIL", "故障注入", "LIN线与电源短路故障注入失败")
                return
            TestLog("INFO", "故障清除", f"LIN线与电源短路故障已清除，记录时刻t1: {t1}")

            recovery_success, T_recovery = check_communication_recovery_time(t1, T_faultRecoveryMax)

            # 检查恢复时间是否满足要求
            if recovery_success:
                TestLog("PASS", "通信恢复", f"DUT通信已恢复，恢复时间: {T_recovery:.2f}ms")
                if T_recovery <= T_faultRecoveryMax:
                    TestLog("PASS", "恢复时间检查",
                            f"恢复时间({T_recovery:.2f}ms) ≤ 允许时间({T_faultRecoveryMax}ms)")
                    recovery_ok = True
                else:
                    TestLog("FAIL", "恢复时间检查",
                            f"恢复时间({T_recovery:.2f}ms) > 允许时间({T_faultRecoveryMax}ms)")
                    recovery_ok = False
                    overall_result = False
            else:
                TestLog("FAIL", "通信恢复", f"DUT在{T_faultRecoveryMax}ms内通信未恢复")
                recovery_ok = False
                overall_result = False

            # 步骤4: 控制DUT下电，等待30s
            TestLog("INFO", "DUT下电", "控制DUT下电，等待30s")
            # 停用DUT
            ctx.bob_ctrl.set_power('KL30', False)
            time.sleep(30.0)

            # 记录本轮测试结果
            round_result = fault_success and recovery_ok
            test_results.append({
                'round': round_num,
                'recovery_time': T_recovery if recovery_success else T_faultRecoveryMax,
                'round_result': round_result
            })

            TestLog("INFO", "测试轮次结果",
                    f"第{round_num}轮测试结果 - 故障状态: {'通过' if round_result else '失败'}, "
                    f"恢复状态: {'通过' if recovery_ok else '失败'}, "
                    f"恢复时间: {T_recovery if recovery_success else '超时'}ms")

        # 最终评价
        if overall_result:
            TestLog("PASS", "最终结果", "LIN线与电源短路测试用例通过")
        else:
            TestLog("FAIL", "最终结果", "LIN线与电源短路测试用例失败")

    except Exception as e:
        TestLog("FAIL", "LIN线与电源短路测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "LIN线与电源短路测试", f"详细错误: {traceback.format_exc()}")


def test_TG4_TC3_FauLayer_LINShortGnd_Test():
    """
    LIN线与地短路测试
    """
    try:
        # 从配置文件获取测试参数
        V_normal = P.LINInfo.Vnormal  # 正常电压
        T_defaultWait = P.LINInfo.TdefaultWait_s  # 通信稳定时间(s)
        T_faultDelay = P.LINInfo.TfaultDelay_s  # 故障保持时间(s)，典型值1min
        T_faultRecoveryMax = P.LINInfo.TfaultRecoveryMax_ms  # 故障恢复时间(s)
        N_faultRepeat = P.LINInfo.NfaultRepeat  # 测试循环次数
        SimulationActivate = P.LINInfo.SimulationActivate  # 是否需要仿真节点

        ctrl_can_channel = P.ECUInfo.BOBControlCan
        target_lin_channel = P.ECUInfo.ETS6124LinChannel

        test_results = []
        overall_result = True

        TestLog("INFO", "LIN线与地短路测试", "开始执行测试用例")

        for round_num in range(1, N_faultRepeat + 1):
            TestLog("INFO", "测试轮次", f"开始第{round_num}轮测试")

            # 步骤1: 使用标准电源设置与通信检查
            TestLog("INFO", "测试环境设置", f"开始设置通道{ctrl_can_channel}的测试环境")
            ret = ActivateDut(SimulationActivate, T_defaultWait)
            if ret != 0:
                TestLog("FAIL", "测试环境设置", "DUT通信配置异常，测试结束")
                return
            # 步骤2: 制造LIN线与地短路
            TestLog("INFO", "LIN线与地短路测试", f"开始第{round_num}轮LIN断路测试")
            fault_result = lin_fault_injection('LIN_short_GND', target_lin_channel,
                                               T_faultDelay * 1000)

            # 检查返回值类型
            if isinstance(fault_result, tuple) and len(fault_result) == 2:
                fault_success, t1 = fault_result
            else:
                fault_success = fault_result
                t1 = None

            if not fault_success:
                TestLog("FAIL", "故障注入", "LIN线与地短路故障注入失败")
                return
            TestLog("INFO", "故障清除", f"LIN线与地短路故障已清除，记录时刻t1: {t1}")

            recovery_success, T_recovery = check_communication_recovery_time(t1, T_faultRecoveryMax)

            # 检查恢复时间是否满足要求
            if recovery_success:
                TestLog("PASS", "通信恢复", f"DUT通信已恢复，恢复时间: {T_recovery:.2f}ms")
                if T_recovery <= T_faultRecoveryMax:
                    TestLog("PASS", "恢复时间检查",
                            f"恢复时间({T_recovery:.2f}ms) ≤ 允许时间({T_faultRecoveryMax}ms)")
                    recovery_ok = True
                else:
                    TestLog("FAIL", "恢复时间检查",
                            f"恢复时间({T_recovery:.2f}ms) > 允许时间({T_faultRecoveryMax}ms)")
                    recovery_ok = False
                    overall_result = False
            else:
                TestLog("FAIL", "通信恢复", f"DUT在{T_faultRecoveryMax}ms内通信未恢复")
                recovery_ok = False
                overall_result = False

            # 步骤4: 控制DUT下电，等待30s
            TestLog("INFO", "DUT下电", "控制DUT下电，等待30s")
            # 停用DUT
            ctx.bob_ctrl.set_power('KL30', False)
            time.sleep(30.0)

            # 记录本轮测试结果
            round_result = fault_success and recovery_ok
            test_results.append({
                'round': round_num,
                'recovery_time': T_recovery if recovery_success else T_faultRecoveryMax,
                'round_result': round_result
            })

            TestLog("INFO", "测试轮次结果",
                    f"第{round_num}轮测试结果 - 故障状态: {'通过' if round_result else '失败'}, "
                    f"恢复状态: {'通过' if recovery_ok else '失败'}, "
                    f"恢复时间: {T_recovery if recovery_success else '超时'}ms")

        # 最终评价
        if overall_result:
            TestLog("PASS", "最终结果", "LIN线与地短路测试用例通过")
        else:
            TestLog("FAIL", "最终结果", "LIN线与地短路测试用例失败")

    except Exception as e:
        TestLog("FAIL", "LIN线与地短路测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "LIN线与地短路测试", f"详细错误: {traceback.format_exc()}")


def test_TG4_TC4_FauLayer_VbattOpen_Test():
    """
    掉电测试
    """
    try:
        # 从配置文件获取测试参数
        V_normal = P.LINInfo.Vnormal  # 正常电压
        T_defaultWait = P.LINInfo.TdefaultWait_s  # 通信稳定时间(s)
        T_faultDelay = P.LINInfo.TfaultDelay_s  # 故障保持时间(s)，典型值1min
        T_faultRecoveryMax = P.LINInfo.TfaultRecoveryMax_ms  # 故障恢复时间(s)
        N_faultRepeat = P.LINInfo.NfaultRepeat  # 测试循环次数
        SimulationActivate = P.LINInfo.SimulationActivate  # 是否需要仿真节点

        ctrl_can_channel = P.ECUInfo.BOBControlCan
        target_lin_channel = P.ECUInfo.ETS6124LinChannel
        target_ecu_channel = P.ECUInfo.ETS6124ECUChannel

        test_results = []
        overall_result = True

        TestLog("INFO", "LIN掉电测试", "开始执行测试用例")

        for round_num in range(1, N_faultRepeat + 1):
            TestLog("INFO", "测试轮次", f"开始第{round_num}轮测试")

            # 步骤1: 使用标准电源设置与通信检查
            TestLog("INFO", "测试环境设置", f"开始设置通道{ctrl_can_channel}的测试环境")
            ret = ActivateDut(SimulationActivate, T_defaultWait)
            if ret != 0:
                TestLog("FAIL", "测试环境设置", "DUT通信配置异常，测试结束")
                return
            # 步骤2: DUT掉电测试
            TestLog("INFO", "DUT掉电测试", f"开始第{round_num}轮DUT掉电测试")

            ctx.bob_ctrl.set_power('KL30', False, target_ecu_channel)
            time.sleep(1)
            ctx.lin.clear_messages()
            # 记录故障前的通信状态
            initial_msg_count = 0
            for msg in ctx.lin.messages:
                if msg.direction == 0 and msg.dlc != 0:  # RX方向
                    initial_msg_count += 1
            initial_error_count = ctx.lin.get_info('gLinErrorFrameCount') or 0
            TestLog("INFO", "通信状态监测",
                    f"故障前状态: 响应帧报文数={initial_msg_count}, 错误帧数={initial_error_count}")

            # 故障期间通信状态监测
            fault_start_time = time.time()
            duration_ms = T_faultDelay * 1000 if (T_faultDelay is not None and isinstance(T_faultDelay, (int, float)) and T_faultDelay >= 0) else 60000
            fault_end_time = fault_start_time + duration_ms / 1000.0
            check_interval = 0.1  # 每100ms检查一次
            fault_detected = False

            while time.time() < fault_end_time:
                current_time = time.time()
                elapsed_time = (current_time - fault_start_time) * 1000

                # 检查是否有新的LIN帧传输
                current_msg_count = 0
                for msg in ctx.lin.messages:
                    if msg.direction == 0 and msg.dlc != 0:  # RX方向
                        current_msg_count += 1
                current_error_count = ctx.lin.get_info('gLinErrorFrameCount') or 0

                if current_msg_count > initial_msg_count:
                    # 检测到新的LIN帧传输
                    TestLog("WARNING", "通信状态监测",
                            f"故障期间检测到LIN响应帧传输: 时间={elapsed_time:.1f}ms, 新增报文数={current_msg_count - initial_msg_count}")
                    fault_detected = True

                # 检查错误帧数量变化
                if current_error_count > initial_error_count:
                    TestLog("WARNING", "通信状态监测",
                            f"故障期间检测到错误帧: 时间={elapsed_time:.1f}ms, 错误帧数={current_error_count}")

                # 检查是否到达故障结束时间
                remaining_time = fault_end_time - current_time
                if remaining_time <= 0:
                    break

                # 等待下一次检查
                sleep_time = min(check_interval, remaining_time)
                time.sleep(sleep_time)

            # 故障期间通信状态总结
            if fault_detected:
                TestLog("FAIL", "通信状态监测",
                        f"故障期间检测到通信活动: 总线上有LIN响应帧传输产生")
            else:
                TestLog("PASS", "通信状态监测",
                        f"故障期间通信状态正常: 总线上无LIN响应帧传输产生")

            # 记录KL30上电时刻t1
            t1 = time.time()
            TestLog("INFO", "KL30上电", f"KL30重新上电，记录时刻t1: {t1}")
            # 执行KL30上电
            ctx.bob_ctrl.set_power('KL30', True, target_ecu_channel)

            TestLog("INFO", "Step1", "发送LIN唤醒信号")
            WakeupStart()

            dut_mode = _current_dut_mode()
            TestLog("INFO", "DUT模式", f"当前 DUT 模式: {dut_mode}")
            ret = _setup_lin_simulation_for_dut(dut_mode)
            if ret != 0:
                TestLog("FAIL", "DUT激活", "仿真准备失败")
                return -1
            ret = _start_lin_simulation_for_dut(dut_mode)
            if ret != 0:
                TestLog("FAIL", "DUT激活", "仿真启动失败")
                return -1
            TestLog("PASS", "DUT激活", f"按 DUT 模式({dut_mode}) 启动仿真成功")

            # 使用通信恢复检查函数
            recovery_success, T_recovery = check_communication_recovery_time(t1, T_faultRecoveryMax)

            if recovery_success:
                # T_recovery是t2 - t1的时间差（毫秒）
                TestLog("PASS", "通信恢复", f"DUT通信已恢复，恢复时间: {T_recovery:.2f}ms")

                if T_recovery <= T_faultRecoveryMax:
                    TestLog("PASS", "恢复时间检查",
                            f"T_recovery({T_recovery:.2f}ms) ≤ T_faultRecoveryMax({T_faultRecoveryMax}ms)")
                    recovery_ok = True
                else:
                    TestLog("FAIL", "恢复时间检查",
                            f"T_recovery({T_recovery:.2f}ms) > T_faultRecoveryMax({T_faultRecoveryMax}ms)")
                    recovery_ok = False
                    overall_result = False
            else:
                TestLog("FAIL", "通信恢复", f"DUT在{T_faultRecoveryMax}ms内通信未恢复")
                recovery_ok = False
                overall_result = False

            # 步骤4: 控制DUT下电，等待30s
            TestLog("INFO", "DUT下电", "控制DUT下电，等待30s")
            # 停用DUT
            ctx.bob_ctrl.set_power('KL30', False)
            time.sleep(30.0)

            # 记录本轮测试结果
            test_results.append({
                'round': round_num,
                'recovery_time': T_recovery if recovery_success else T_faultRecoveryMax,
                'recovery_ok': recovery_ok
            })

            TestLog("INFO", "测试轮次结果",
                    f"第{round_num}轮测试结果 - 故障及恢复状态: {'通过' if recovery_ok else '失败'}, "
                    f"恢复时间: {T_recovery if recovery_success else '超时'}ms")

        # 最终评价
        if overall_result:
            TestLog("PASS", "最终结果", "LIN掉电测试用例通过")
        else:
            TestLog("FAIL", "最终结果", "LIN掉电测试用例失败")

    except Exception as e:
        TestLog("FAIL", "LIN掉电测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "LIN掉电测试", f"详细错误: {traceback.format_exc()}")


def test_TG4_TC5_FauLayer_GndOpen_Test():
    """
    掉地测试
    """
    try:
        # 从配置文件获取测试参数
        V_normal = P.LINInfo.Vnormal  # 正常电压
        T_defaultWait = P.LINInfo.TdefaultWait_s  # 通信稳定时间(s)
        T_faultDelay = P.LINInfo.TfaultDelay_s  # 故障保持时间(s)，典型值1min
        T_faultRecoveryMax = P.LINInfo.TfaultRecoveryMax_ms  # 故障恢复时间(s)
        N_faultRepeat = P.LINInfo.NfaultRepeat  # 测试循环次数
        SimulationActivate = P.LINInfo.SimulationActivate  # 是否需要仿真节点

        ctrl_can_channel = P.ECUInfo.BOBControlCan
        target_lin_channel = P.ECUInfo.ETS6124LinChannel
        target_ecu_channel = P.ECUInfo.ETS6124ECUChannel

        test_results = []
        overall_result = True

        TestLog("INFO", "LIN掉地测试", "开始执行测试用例")

        for round_num in range(1, N_faultRepeat + 1):
            TestLog("INFO", "测试轮次", f"开始第{round_num}轮测试")

            # 步骤1: 使用标准电源设置与通信检查
            TestLog("INFO", "测试环境设置", f"开始设置通道{ctrl_can_channel}的测试环境")
            ret = ActivateDut(SimulationActivate, T_defaultWait)
            if ret != 0:
                TestLog("FAIL", "测试环境设置", "DUT通信配置异常，测试结束")
                return
            # 步骤2: DUT掉地测试
            TestLog("INFO", "DUT掉地测试", f"开始第{round_num}轮DUT掉电测试")
            ctx.bob_ctrl.set_power('GND', False, target_ecu_channel)

            time.sleep(1)
            ctx.lin.clear_messages()

            # 记录故障后的通信状态
            initial_msg_count = 0
            for msg in ctx.lin.messages:
                if msg.direction == 0 and msg.dlc != 0:  # RX方向
                    initial_msg_count += 1
            initial_error_count = ctx.lin.get_info('gLinErrorFrameCount') or 0
            TestLog("INFO", "通信状态监测",
                    f"故障前状态: 响应帧报文数={initial_msg_count}, 错误帧数={initial_error_count}")

            # 故障期间通信状态监测
            fault_start_time = time.time()
            duration_ms = T_faultDelay * 1000 if (T_faultDelay is not None and isinstance(T_faultDelay, (int,
                                                                                                         float)) and T_faultDelay >= 0) else 60000
            fault_end_time = fault_start_time + duration_ms / 1000.0
            check_interval = 0.1  # 每100ms检查一次
            fault_detected = False

            while time.time() < fault_end_time:
                current_time = time.time()
                elapsed_time = (current_time - fault_start_time) * 1000

                # 检查是否有新的LIN帧传输
                current_msg_count = 0
                for msg in ctx.lin.messages:
                    if msg.direction == 0 and msg.dlc != 0:  # RX方向
                        current_msg_count += 1
                current_error_count = ctx.lin.get_info('gLinErrorFrameCount') or 0

                if current_msg_count > initial_msg_count:
                    # 检测到新的LIN帧传输
                    TestLog("WARNING", "通信状态监测",
                            f"故障期间检测到LIN响应帧传输: 时间={elapsed_time:.1f}ms, 新增报文数={current_msg_count - initial_msg_count}")
                    fault_detected = True

                # 检查错误帧数量变化
                if current_error_count > initial_error_count:
                    TestLog("WARNING", "通信状态监测",
                            f"故障期间检测到错误帧: 时间={elapsed_time:.1f}ms, 错误帧数={current_error_count}")

                # 检查是否到达故障结束时间
                remaining_time = fault_end_time - current_time
                if remaining_time <= 0:
                    break

                # 等待下一次检查
                sleep_time = min(check_interval, remaining_time)
                time.sleep(sleep_time)

            # 故障期间通信状态总结
            if fault_detected:
                TestLog("FAIL", "通信状态监测",
                        f"故障期间检测到通信活动: 总线上有LIN响应帧传输产生")
            else:
                TestLog("PASS", "通信状态监测",
                        f"故障期间通信状态正常: 总线上无LIN响应帧传输产生")

            # 记录GND接入时刻t1
            t1 = time.time()
            TestLog("INFO", "GND恢复", f"GND重新接入，记录时刻t1: {t1}")
            # 执行GND接入
            ctx.bob_ctrl.set_power('GND', True, target_ecu_channel)

            TestLog("INFO", "Step1", "发送LIN唤醒信号")
            WakeupStart()

            dut_mode = _current_dut_mode()
            TestLog("INFO", "DUT模式", f"当前 DUT 模式: {dut_mode}")
            ret = _setup_lin_simulation_for_dut(dut_mode)
            if ret != 0:
                TestLog("FAIL", "DUT激活", "仿真准备失败")
                return -1
            ret = _start_lin_simulation_for_dut(dut_mode)
            if ret != 0:
                TestLog("FAIL", "DUT激活", "仿真启动失败")
                return -1
            TestLog("PASS", "DUT激活", f"按 DUT 模式({dut_mode}) 启动仿真成功")

            # 使用通信恢复检查函数
            recovery_success, T_recovery = check_communication_recovery_time(t1, T_faultRecoveryMax)

            if recovery_success:
                # T_recovery是t2 - t1的时间差（毫秒）
                TestLog("PASS", "通信恢复", f"DUT通信已恢复，恢复时间: {T_recovery:.2f}ms")

                if T_recovery <= T_faultRecoveryMax:
                    TestLog("PASS", "恢复时间检查",
                            f"T_recovery({T_recovery:.2f}ms) ≤ T_faultRecoveryMax({T_faultRecoveryMax}ms)")
                    recovery_ok = True
                else:
                    TestLog("FAIL", "恢复时间检查",
                            f"T_recovery({T_recovery:.2f}ms) > T_faultRecoveryMax({T_faultRecoveryMax}ms)")
                    recovery_ok = False
                    overall_result = False
            else:
                TestLog("FAIL", "通信恢复", f"DUT在{T_faultRecoveryMax}ms内通信未恢复")
                recovery_ok = False
                overall_result = False

            # 步骤4: 控制DUT下电，等待30s
            TestLog("INFO", "DUT下电", "控制DUT下电，等待30s")
            # 停用DUT
            ctx.bob_ctrl.set_power('KL30', False)
            time.sleep(30.0)

            # 记录本轮测试结果
            test_results.append({
                'round': round_num,
                'recovery_time': T_recovery if recovery_success else T_faultRecoveryMax,
                'recovery_ok': recovery_ok
            })

            TestLog("INFO", "测试轮次结果",
                    f"第{round_num}轮测试结果 - 故障及恢复状态: {'通过' if recovery_ok else '失败'}, "
                    f"恢复时间: {T_recovery if recovery_success else '超时'}ms")

        # 最终评价
        if overall_result:
            TestLog("PASS", "最终结果", "LIN掉地测试用例通过")
        else:
            TestLog("FAIL", "最终结果", "LIN掉地测试用例失败")

    except Exception as e:
        TestLog("FAIL", "LIN掉地测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "LIN掉地测试", f"详细错误: {traceback.format_exc()}")


def test_TG4_TC6_FauLayer_SynFieldError_Test():
    """
    同步场错误测试
    """
    try:
        pass
        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "同步场错误测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "同步场错误测试", f"详细错误: {traceback.format_exc()}")


def test_TG4_TC7_FauLayer_IDFieldCheckBitError_Test():
    """
    ID场错误测试
    """
    try:
        pass
        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "ID场错误测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "ID场错误测试", f"详细错误: {traceback.format_exc()}")


def test_TG4_TC8_FauLayer_DataFieldError_Test():
    """
    数据场错误测试
    """
    try:
        pass
        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "数据场错误测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "数据场错误测试", f"详细错误: {traceback.format_exc()}")


def test_TG4_TC9_FauLayer_IncomFrameDisturb_Test():
    """
    不完整帧干扰测试
    """
    try:
        pass
        TestEnd("")
    except Exception as e:
        TestLog("FAIL", "不完整帧干扰测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "不完整帧干扰测试", f"详细错误: {traceback.format_exc()}")




def get_all_test_cases():
    """获取LIN测试用例"""
    current_module = inspect.getmodule(inspect.currentframe())

    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj

    return test_cases
