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
from common.can_utils import send_canmsg, canmsg_create
from common.utils import TimerCyclic
from slplus.time import sl_time
from slplus.busstatis import sl_busstatis

from testcases.can.can_module import can_initialization, can_deinitialization
from testcases.tp.can_test_pre_module import can_power_setup_and_communication_check
from testcases.tp.tp_can_utils import (
    check_msg_thread_start, check_msg_thread_stop,
    RunTimeInfo, get_fc_st_min_ms, create_ff_cfs,
    check_resp_FC_ok, check_resp_FF_ok, check_first_cf,
    check_default_session, check_negative_resp, wait_stable_communcation,
    emit_can_busload_high, emit_can_busload_high_stop,
)


class TPRobustTestFixture(TestFixture):
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


def test_TG1_TC1_ConsecutiveFrameLossRecoveryTest():
    """连续帧丢失恢复鲁棒性测试"""
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout
        rP2_Client_ms = P.TpInfo.P2_Client

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，唤醒CAN网络，等待{rTstable}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        TestLog("INFO", "Step2", "发送请求报文请求多帧响应, 验证首帧接收")
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        msg_default_session = canmsg_create(rDiagReqID, 8,
                                            data=[0x02, 0x10, 0x01] + [0xAA] * 5,
                                            fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        msg = canmsg_create(rDiagReqID, 8,
                            data=[0x02, 0x19, 0x0A] + [0xAA] * 5,
                            fdf=P.TpInfo.CanFDMode)
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        sl_time().sleep(rP2_Client_ms * 2)

        ff_ok = False
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if len(payload) > 0 and payload[0] >> 4 == 0x1:
                ff_ok = True
                break

        if ff_ok:
            TestLog("PASS", "Step2", "期望结果：收到首帧(1_)。实际结果：收到首帧")
        else:
            TestLog("FAIL", "Step2", "期望结果：收到首帧(1_)。实际结果：未收到首帧")

        TestLog("INFO", "Step3",
                "发送流控帧(STmin=0), 但立即将总线负载推至100%使得连续帧无法到达")
        fc_msg = canmsg_create(rDiagReqID, 8,
                               data=[0x30, 0x00, 0x00] + [0xAA] * 5,
                               fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, fc_msg, rDiagReqID, dlc=fc_msg.dlc)

        timer_id_start, timer_id_end = emit_can_busload_high(can_channel)
        while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) < 90:
            sl_time().sleep(10)

        sl_time().sleep(rN_CrTimeout_ms * 1.5)

        TestLog("INFO", "Step4", "停止总线负载，验证DUT是否重新响应")
        emit_can_busload_high_stop(timer_id_start, timer_id_end)
        while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) > 20:
            sl_time().sleep(10)

        sl_time().sleep(3000)

        rt.clear()
        msg_retry = canmsg_create(rDiagReqID, 8,
                                   data=[0x02, 0x19, 0x0A] + [0xAA] * 5,
                                   fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_retry, rDiagReqID, dlc=msg_retry.dlc)

        sl_time().sleep(rP2_Client_ms * 3)

        ff_ok2 = False
        recv_list2 = rt.get_recv_list()
        for i in range(len(recv_list2)):
            payload = rt.get_recv_item_payload(i)
            if len(payload) > 0 and payload[0] >> 4 == 0x1:
                ff_ok2 = True
                break

        if ff_ok2:
            TestLog("PASS", "Step4",
                    "期望结果：连续帧丢失后DUT重新发送首帧。实际结果：收到新的首帧响应")
        else:
            TestLog("FAIL", "Step4",
                    "期望结果：连续帧丢失后DUT重新发送首帧。实际结果：未收到新首帧")

        check_msg_thread_stop(rt)
        TestLog("INFO", "连续帧丢失恢复鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "连续帧丢失恢复鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "连续帧丢失恢复鲁棒性测试", f"详细错误: {traceback.format_exc()}")
    finally:
        check_msg_thread_stop(rt)


def test_TG1_TC2_AbnormalSTminHandlingTest():
    """异常STmin值处理鲁棒性测试"""
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rP2_Client_ms = P.TpInfo.P2_Client

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，唤醒CAN网络，等待{rTstable}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        st_min_values = [0x00, 0x7F, 0xF1, 0xF2, 0xF3, 0xFF]
        TestLog("INFO", "Step2", f"测试不同STmin值: {[hex(v) for v in st_min_values]}")

        for st_min in st_min_values:
            check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
            sl_time().sleep(3)

            msg_default_session = canmsg_create(rDiagReqID, 8,
                                                data=[0x02, 0x10, 0x01] + [0xAA] * 5,
                                                fdf=P.TpInfo.CanFDMode)
            send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
            sl_time().sleep(rP2_Client_ms * 0.8)

            msg = canmsg_create(rDiagReqID, 8,
                                data=[0x02, 0x19, 0x0A] + [0xAA] * 5,
                                fdf=P.TpInfo.CanFDMode)
            rt.clear()
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

            sl_time().sleep(rP2_Client_ms * 2)

            ff_ok = False
            recv_list = rt.get_recv_list()
            for i in range(len(recv_list)):
                payload = rt.get_recv_item_payload(i)
                if len(payload) > 0 and payload[0] >> 4 == 0x1:
                    ff_ok = True
                    break

            if ff_ok:
                fc_msg = canmsg_create(rDiagReqID, 8,
                                       data=[0x30, 0x00, st_min] + [0xAA] * 5,
                                       fdf=P.TpInfo.CanFDMode)
                send_canmsg(can_channel, fc_msg, rDiagReqID, dlc=fc_msg.dlc)
                sl_time().sleep(5000)

                cf_received = False
                recv_list2 = rt.get_recv_list()
                for i in range(len(recv_list2)):
                    payload = rt.get_recv_item_payload(i)
                    if len(payload) > 0 and payload[0] >> 4 == 0x2:
                        cf_received = True
                        break

                if cf_received:
                    TestLog("PASS", "Step2",
                            f"STmin=0x{st_min:02X}: DUT正常发送连续帧")
                else:
                    TestLog("WARNING", "Step2",
                            f"STmin=0x{st_min:02X}: DUT未发送连续帧")

            check_msg_thread_stop(rt)
            time.sleep(1)

        TestLog("INFO", "异常STmin值处理鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "异常STmin值处理鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "异常STmin值处理鲁棒性测试", f"详细错误: {traceback.format_exc()}")
    finally:
        check_msg_thread_stop(rt)


def test_TG1_TC3_MultiFrameTransmissionInterruptionTest():
    """多帧传输中断恢复鲁棒性测试"""
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout
        rP2_Client_ms = P.TpInfo.P2_Client

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，唤醒CAN网络，等待{rTstable}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        interrupt_cycles = 3
        TestLog("INFO", "Step2", f"执行{interrupt_cycles}轮多帧传输-中断-恢复循环")

        for cycle in range(1, interrupt_cycles + 1):
            check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
            sl_time().sleep(3)

            msg_default_session = canmsg_create(rDiagReqID, 8,
                                                data=[0x02, 0x10, 0x01] + [0xAA] * 5,
                                                fdf=P.TpInfo.CanFDMode)
            send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
            sl_time().sleep(rP2_Client_ms * 0.8)

            msg = canmsg_create(rDiagReqID, 8,
                                data=[0x02, 0x19, 0x0A] + [0xAA] * 5,
                                fdf=P.TpInfo.CanFDMode)
            rt.clear()
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            sl_time().sleep(rP2_Client_ms * 2)

            ff_ok = False
            recv_list = rt.get_recv_list()
            for i in range(len(recv_list)):
                payload = rt.get_recv_item_payload(i)
                if len(payload) > 0 and payload[0] >> 4 == 0x1:
                    ff_ok = True
                    break

            if ff_ok:
                TestLog("INFO", "Step2", f"第{cycle}轮: 收到首帧, 发送流控帧STmin=0")
                fc_msg = canmsg_create(rDiagReqID, 8,
                                       data=[0x30, 0x00, 0x00] + [0xAA] * 5,
                                       fdf=P.TpInfo.CanFDMode)
                send_canmsg(can_channel, fc_msg, rDiagReqID, dlc=fc_msg.dlc)

                sl_time().sleep(2000)

                TestLog("INFO", "Step2", f"第{cycle}轮: 中断传输（发送高优先级报文淹没总线）")
                timer_id_start, timer_id_end = emit_can_busload_high(can_channel)
                while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) < 90:
                    sl_time().sleep(10)

                sl_time().sleep(rN_CrTimeout_ms * 1.5)
                emit_can_busload_high_stop(timer_id_start, timer_id_end)
            else:
                TestLog("WARNING", "Step2", f"第{cycle}轮: 未收到首帧")

            check_msg_thread_stop(rt)
            time.sleep(2)

        TestLog("INFO", "Step3", "所有中断循环结束后验证DUT可以重新正常传输多帧")
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(3)

        msg_default_session = canmsg_create(rDiagReqID, 8,
                                            data=[0x02, 0x10, 0x01] + [0xAA] * 5,
                                            fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        msg = canmsg_create(rDiagReqID, 8,
                            data=[0x02, 0x19, 0x0A] + [0xAA] * 5,
                            fdf=P.TpInfo.CanFDMode)
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
        sl_time().sleep(rP2_Client_ms * 3)

        ff_ok_final = False
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if len(payload) > 0 and payload[0] >> 4 == 0x1:
                ff_ok_final = True
                break

        if ff_ok_final:
            TestLog("PASS", "Step3",
                    f"期望结果：{interrupt_cycles}轮中断后DUT多帧传输正常。实际结果：收到首帧响应")
        else:
            TestLog("FAIL", "Step3",
                    f"期望结果：{interrupt_cycles}轮中断后DUT多帧传输正常。实际结果：未收到首帧")

        TestLog("INFO", "多帧传输中断恢复鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "多帧传输中断恢复鲁棒性测试", f"测试执行出错: {e}")
        TestLog("DEBUG", "多帧传输中断恢复鲁棒性测试", f"详细错误: {traceback.format_exc()}")
    finally:
        check_msg_thread_stop(rt)


def get_all_test_cases():
    import inspect
    current_module = inspect.getmodule(inspect.currentframe())
    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj
    return test_cases
