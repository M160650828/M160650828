import inspect
import math
import random
import sys
import os
import threading

import traceback

from numpy.ma.core import count
from slplus.busstatis import sl_busstatis
from env.config import *
from common.context import ctx
from slplus.time import sl_time
from uvtest.testlog import TestLog
from common.control import TestStart, TestEnd
from uvtest.framework import TestFixture

from .can_test_pre_module import can_power_setup_and_communication_check
from common.can_utils import send_canmsg, canmsg_create
from .tp_can_utils import (
    check_msg_thread_start,
    RunTimeInfo,
    check_msg_thread_stop,
    emit_can_busload_high,
    emit_can_busload_high_stop,
    get_fc_st_min_ms, create_ff_cfs, check_resp_FC_ok, check_resp_FF_ok, check_first_cf,check_default_session,check_negative_resp,wait_stable_communcation
)
from ..can.can_module import can_initialization, can_deinitialization


workdir_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(workdir_path)

class CANTPTestFixture(TestFixture):
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


def test_TG1_TC1_TimeoutCheck_N_AS():
    """N_As超时值检查"""
    case_name = "N_As超时值检查"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_AsTimeout_ms = P.TpInfo.N_AsTimeout  # N_As最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        # 优先构造流控帧报文
        msg_30 = canmsg_create(rDiagReqID, 8, data=[0x30] + [0x00] * 2 + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)

        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应。"
                                 "在请求之后，立即发送使总线负载达到100%的高优先级帧。"
                                 "这些高优先级帧不是ECU配置为接收的诊断帧或应用信号帧。")

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        msg = canmsg_create(rDiagReqID, 8, data=[0x02, 0x19, 0x0A] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        # 发送高优先级can报文
        timer_id_start, timer_id_end = emit_can_busload_high(can_channel)
        while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) < 90:
            sl_time().sleep(10)
        # TestLog("INFO", "等待10s", "确保总线负载达到100%")
        # sl_time().sleep(10000)
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        TestLog("INFO", "Step2", f"等待允许的最大{rN_AsTimeout_ms}超时(+10%)")
        sl_time().sleep(rN_AsTimeout_ms * 1.1)

        # 发送的请求报文时间
        send_timestamp = 0
        send_list = rt.get_send_list()
        for i in range(len(send_list)):
            payload = rt.get_send_item_payload(i)
            if payload[:3] == [0x02, 0x19, 0x0A]:
                send_timestamp = rt.get_send_item_timestamp(i)
                break

        # ECU发送的首帧和连续帧的时间
        ff_timestamp = None
        fc_timestamp = None
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 0x1:
                ff_timestamp = rt.get_recv_item_timestamp(i)
            elif payload[0] == 0x21:
                fc_timestamp = rt.get_recv_item_timestamp(i)

        TestLog("INFO", "Step3", "停止发送高优先级帧")
        emit_can_busload_high_stop(timer_id_start, timer_id_end)
        while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) > 20:
            sl_time().sleep(10)
        if ff_timestamp is not None:
            if ff_timestamp - send_timestamp > rN_AsTimeout_ms * 1.1:
                TestLog("FAIL", "期望结果：无响应或DUT发送FF，若DUT无响应跳转至步骤5", f"实际结果：收到DUT发送FF的时间超时, "
                                           f"请求报文发送时间点={send_timestamp}ms,"
                                           f"首帧报文发送时间点={ff_timestamp}ms,"
                                           f"差值={ff_timestamp - send_timestamp}ms")
            else:
                TestLog("PASS", "期望结果：无响应或DUT发送FF，若DUT无响应跳转至步骤5", "实际结果：收到DUT发送FF(1_)")
                TestLog("INFO", "Step4", "发送流控帧，其中STmin=0")
                send_canmsg(can_channel, msg_30, rDiagReqID, dlc=msg_30.dlc)

                sl_time().sleep(rN_CrTimeout_ms * 1.1)

                fc_timestamp = None
                recv_list = rt.get_recv_list()
                for i in range(len(recv_list)):
                    payload = rt.get_recv_item_payload(i)
                    if payload[0] == 0x21:
                        fc_timestamp = rt.get_recv_item_timestamp(i)

                if fc_timestamp is not None:
                    TestLog("FAIL", "期望结果：在N_Cr超时前未收到后续CF", "实际结果：收到连续帧的第1帧")
                else:
                    TestLog("PASS", "期望结果：在N_Cr超时前未收到后续CF", "实际结果：未收到连续帧的第1帧")
        else:
            TestLog("INFO", "期望结果：无响应或DUT发送FF，若DUT无响应跳转至步骤5", "实际结果：未收到DUT发送FF(1_)，跳过步骤4的发送流控帧，继续步骤5")

        check_msg_thread_stop(rt)

        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        TestLog("INFO", "Step5", "发送请求报文，请求多帧响应。")
        msg = canmsg_create(rDiagReqID, 8, data=[0x02, 0x19, 0x0A] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        sl_time().sleep(rN_AsTimeout_ms * 1.1)

        # ECU发送的首帧的时间
        ff_timestamp = None
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 0x1:
                ff_timestamp = rt.get_recv_item_timestamp(i)

        if ff_timestamp is None:
            TestLog("FAIL", "期望结果：DUT发送首帧 DUT sends FF", "实际结果：未收到首帧(1_)")
        else:
            TestLog("PASS", "期望结果：DUT发送首帧 DUT sends FF", "实际结果：DUT发送首帧1_")
            TestLog("INFO", "Step6", "发送流控帧，其中STmin=0。在发送流控帧后立即将总线负载提到100%")
            send_canmsg(can_channel, msg_30, rDiagReqID, dlc=msg_30.dlc)
            timer_id_start, timer_id_end = emit_can_busload_high(can_channel)
            while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) < 90:
                sl_time().sleep(10)
            # TestLog("INFO", "等待10s", "确保总线负载达到100%")
            # sl_time().sleep(10000)
            TestLog("INFO", "Step7", f"等待允许的最大{rN_AsTimeout_ms}超时(+10%)")
            sl_time().sleep(rN_AsTimeout_ms * 1.1)

            # 发送的流控帧的时间戳
            fc_timestamp = 0
            send_list = rt.get_send_list()
            for i in range(len(send_list)):
                payload = rt.get_send_item_payload(i)
                if payload[0] == 0x30:
                    fc_timestamp = rt.get_send_item_timestamp(i)
                    break

            # 收到的连续帧的时间戳
            cf_timestamp = None
            recv_list = rt.get_recv_list()
            for i in range(len(recv_list)):
                payload = rt.get_recv_item_payload(i)
                if payload[0] == 0x21:
                    cf_timestamp = rt.get_recv_item_timestamp(i)
                    break

            if cf_timestamp is not None:
                if cf_timestamp - fc_timestamp > rN_AsTimeout_ms * 1.1:
                    TestLog("FAIL", "期望结果：无响应或DUT发送CF第一帧，若无响应跳转至步骤10", f"实际结果：收到DUT发送第一帧CF的时间超时, "
                                               f"流控报文发送时间点={fc_timestamp}ms,"
                                               f"续帧报文发送时间点={cf_timestamp}ms,"
                                               f"差值={cf_timestamp - fc_timestamp}ms")
                else:
                    TestLog("PASS", "期望结果：无响应或DUT发送CF第一帧，若无响应跳转至步骤10", "实际结果：收到连续帧的第1帧")
            else:
                TestLog("INFO", "期望结果：无响应或DUT发送CF第一帧，若无响应跳转至步骤10", "实际结果：未收到连续帧的第1帧")
        check_msg_thread_stop(rt)

        TestLog("INFO", "Step9", "停止发送高优先级帧")
        emit_can_busload_high_stop(timer_id_start, timer_id_end)
        while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) > 20:
            sl_time().sleep(10)

        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        TestLog("INFO", "Step10", "发送请求报文，请求多帧响应。")
        msg = canmsg_create(rDiagReqID, 8, data=[0x02, 0x19, 0x0A] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        sl_time().sleep(rN_AsTimeout_ms * 1.1)

        ff_timestamp = None
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 0x1:
                ff_timestamp = rt.get_recv_item_timestamp(i)
                break

        if ff_timestamp is None:
            TestLog("FAIL", "期望结果：DUT发送首帧 DUT sends FF", "实际结果：未收到首帧(1_)")
        else:
            TestLog("PASS", "期望结果：DUT发送首帧 DUT sends FF", "实际结果：DUT发送首帧1_")

            TestLog("INFO", "Step11", "发送流控帧，其中STmin=0，在接收到DUT返回的连续帧第一帧之后立即发送使总线负载提到100％")
            rt.clear()
            send_canmsg(can_channel, msg_30, rDiagReqID, dlc=msg_30.dlc)

            timer_id_start, timer_id_end = 0, 0
            sl_time().sleep(rN_CrTimeout_ms * 1.1)
            status = False
            recv_list = rt.get_recv_list()
            for i in range(len(recv_list)):
                payload = rt.get_recv_item_payload(i)
                if payload[0] == 0x21:
                    status = True
                    break
            if status is True:
                TestLog("PASS", "期望结果：收到连续帧的第1帧", "实际结果：收到连续帧的第1帧")
                timer_id_start, timer_id_end = emit_can_busload_high(can_channel)
                while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) < 90:
                    sl_time().sleep(10)
                # TestLog("INFO", "等待10s", "确保总线负载达到100%")
                # sl_time().sleep(10000)
            else:
                TestLog("FAIL", "期望结果：收到连续帧的第1帧", "未收到连续帧的第1帧")

            sl_time().sleep(rN_AsTimeout_ms * 1.1)
            TestLog("INFO", "Step12", "停止发送高优先级帧")
            emit_can_busload_high_stop(timer_id_start, timer_id_end)
            while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) > 20:
                sl_time().sleep(10)
            # 收到的连续帧的时间戳
            cf_timestamp1 = 0
            cf_timestamp2 = 0
            recv_list = rt.get_recv_list()
            for i in range(len(recv_list)):
                payload = rt.get_recv_item_payload(i)
                if payload[0] == 0x21:
                    cf_timestamp1 = rt.get_recv_item_timestamp(i)
                if payload[0] == 0x22:
                    cf_timestamp2 = rt.get_recv_item_timestamp(i)
            if cf_timestamp2 > 0:
                if cf_timestamp2 - cf_timestamp1 > rN_AsTimeout_ms * 1.1:
                    TestLog("FAIL", "期望结果：无响应或DUT发送CF下一帧", f"实际结果：收到DUT发送第一帧CF的时间超时, "
                                               f"续帧1报文发送时间点={cf_timestamp1}ms,"
                                               f"续帧2报文发送时间点={cf_timestamp2}ms,"
                                               f"差值={cf_timestamp2 - cf_timestamp1}ms")
                else:
                    TestLog("PASS", "期望结果：无响应或DUT发送CF下一帧", "实际结果：收到连续帧的第2帧")
            else:
                TestLog("INFO", "", "未收到连续帧的第2帧")

        check_msg_thread_stop(rt)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC2_TimeoutCheck_N_Ar():
    """N_Ar超时值检查"""
    case_name = "N_Ar超时值检查"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_AsTimeout_ms = P.TpInfo.N_AsTimeout  # N_As最大时间
        rN_ArTimeout_ms = P.TpInfo.N_ArTimeout  # N_Ar最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        if P.TpInfo.CanFDMode == 0:
            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x0D  # 总长度
        else:
            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x7D  # 总长度

        status, msg_first = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        TestLog("INFO", "Step1", "发送多帧请求报文请求响应。"
                                 "在请求之后立即发送使总线负载达到100%的高优先级帧。")
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        timer_id_start, timer_id_end = emit_can_busload_high(can_channel)
        while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) < 90:
            sl_time().sleep(10)
        rt.clear()
        send_canmsg(can_channel, msg_first[0], rDiagReqID, dlc=msg_first[0].dlc)

        TestLog("INFO", "Step2", "等待允许的最大N_As超时(+10%)")

        sl_time().sleep(rN_ArTimeout_ms * 1.1)

        # 发送的首帧报文时间
        send_timestamp = 0
        send_list = rt.get_send_list()
        for i in range(len(send_list)):
            payload = rt.get_send_item_payload(i)
            if P.TpInfo.CanFDMode == 0:
                if payload[:4] == [0x10, 0x0D, 0x22, 0x01]:
                    send_timestamp = rt.get_send_item_timestamp(i)
                    break
            else:
                if payload[:4] == [0x10, 0x7D, 0x22, 0x01]:
                    send_timestamp = rt.get_send_item_timestamp(i)
                    break

        # 收到的流控帧的时间戳
        fc_timestamp = 0
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0]>>4 == 0x3:
                fc_timestamp = rt.get_recv_item_timestamp(i)
                break
        TestLog("INFO", "", f"{send_timestamp=}, {fc_timestamp=}")

        TestLog("INFO", "Step3", "停止发送高优先级帧")
        emit_can_busload_high_stop(timer_id_start, timer_id_end)
        while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) > 20:
            sl_time().sleep(10)

        if fc_timestamp > 0:
            if fc_timestamp - send_timestamp > rN_AsTimeout_ms * 1.1:
                TestLog("FAIL", case_name, f"收到DUT发送FC的时间超时, "
                                           f"请求首帧报文发送时间点={send_timestamp}ms,"
                                           f"流控帧报文发送时间点={fc_timestamp}ms,"
                                           f"差值={fc_timestamp - send_timestamp}ms")
            else:
                TestLog("PASS", case_name, "收到DUT发送FC")
        else:
            TestLog("FAIL", case_name, "未收到DUT发送FC")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step4", "发送后续请求")
        for msg in msg_first[1:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        check_msg_thread_stop(rt)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC3_TimeoutCheck_N_Cr():
    """N_Cr超时值检查"""
    case_name = "N_Cr超时值检查"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        msg_first = canmsg_create(rDiagReqID, 8, data=[0x02, 0x19, 0x0A] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_30 = canmsg_create(rDiagReqID, 8, data=[0x30] + [0xAA] * 7, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg_first, rDiagReqID, dlc=msg_first.dlc)

        sl_time().sleep(rN_BsTimeout_ms)

        # 收到的首帧的时间戳
        ff_timestamp = 0
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 0x1:
                ff_timestamp = rt.get_recv_item_timestamp(i)
                break
        if ff_timestamp > 0:
            TestLog("PASS", "", f"期望结果：在N_Br={rN_BsTimeout_ms}ms超时时间内收到FF。实际结果：在N_Br={rN_BsTimeout_ms}ms超时时间内收到FF")
        else:
            TestLog("FAIL", "", f"期望结果：在N_Br={rN_BsTimeout_ms}ms超时时间内收到FF。实际结果：在N_Br={rN_BsTimeout_ms}ms超时时间内未收到FF")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step2", "发送FC")
        send_canmsg(can_channel, msg_30, rDiagReqID, dlc=msg_30.dlc)
        check_msg_thread_stop(rt)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC4_TimeoutCheck_N_CsN_As():
    """N_Cs+N_As超时值检查"""
    case_name = "N_Cs+N_As超时值检查"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        msg_first = canmsg_create(rDiagReqID, 8, data=[0x02, 0x19, 0x0A] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_30 = canmsg_create(rDiagReqID, 8, data=[0x30] + [0x00, 0x00] + [0xAA] * 7, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg_first, rDiagReqID, dlc=msg_first.dlc)

        sl_time().sleep(rN_BsTimeout_ms)

        # 收到的首帧的时间戳
        ff_timestamp = 0
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 0x1:
                ff_timestamp = rt.get_recv_item_timestamp(i)
                break
        if ff_timestamp > 0:
            TestLog("PASS", "", f"期望结果：收到FF。实际结果：收到FF")
        else:
            TestLog("FAIL", "", f"期望结果：收到FF。实际结果：未收到FF")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step2", "发送FC")
        send_canmsg(can_channel, msg_30, rDiagReqID, dlc=msg_30.dlc)
        check_msg_thread_stop(rt)

        # 发送的流控帧的时间戳
        fc_timestamp = 0
        send_list = rt.get_send_list()
        for i in range(len(send_list)):
            payload = rt.get_send_item_payload(i)
            if payload[0]>>4 == 0x3:
                fc_timestamp = rt.get_send_item_timestamp(i)
                break

        # 收到的首帧的时间戳
        cf_timestamp = 0
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] == 0x21:
                cf_timestamp = rt.get_recv_item_timestamp(i)
                break

        # TODo 检查N_Cs+N_As是否符合性能要求

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC5_TimeoutCheck_N_BrN_Ar():
    """N_Br+N_Ar超时值检查"""
    case_name = "N_Br+N_Ar超时值检查"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        if P.TpInfo.CanFDMode == 0:
            n_max = 8
            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x0D  # 总长度
        else:
            n_max = 15
            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x7D  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=1,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", "发送多帧请求报文请求响应")
        rt.clear()
        for msg in msg_list:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            sl_time().sleep(1)

        sl_time().sleep(rN_BsTimeout_ms)

        # 收到的流控帧的时间戳
        fc_timestamp = 0
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0]>>4 == 0x3:
                fc_timestamp = rt.get_recv_item_timestamp(i)
                break
        if fc_timestamp > 0:
            TestLog("PASS", "", f"期望结果：收到流控帧(FC)。实际结果：收到FC")
        else:
            TestLog("FAIL", "", f"期望结果：收到流控帧(FC)。实际结果：未收到FC")
            check_msg_thread_stop(rt)
            return

        # TODo 检查N_Br+N_Ar是否符合性能要求

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC6_AbortTransmission():
    """停止发送后续部分连续帧"""
    case_name = "停止发送后续部分连续帧"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        if P.TpInfo.CanFDMode == 0:
            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x22  # 总长度
        else:
            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x13A  # 总长度


        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()
        
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.5)
    

        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        TestLog("INFO", "Step1", "发送多帧请求报文请求响应")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)


        # 收到的流控帧的时间戳
        payload_30 = None
        start_time = sl_time().timestamp()
        # 从接收报文列表中获取流控帧  -s
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)
        if payload_30 is not None:
            TestLog("PASS", "", f"期望结果：收到流控帧(FC)。实际结果：收到FC")
        else:
            TestLog("FAIL", "", f"期望结果：收到流控帧(FC)。实际结果：未收到FC")
            check_msg_thread_stop(rt)
            return

        stmin_ms = get_fc_st_min_ms(payload_30)

        TestLog("INFO", "Step2", "发送后续连续帧，不发送最后一帧")
        rt.clear()
        for msg in msg_list[1:-1]:
            sl_time().sleep(stmin_ms)
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            
        # sl_time().sleep(rN_CrTimeout_ms * 1.1)
        sl_time().sleep(rN_CrTimeout_ms * 1.3)
        # 在该状态下，应该没有任何报文
        if len(rt.get_recv_list()) != 0:
            TestLog("FAIL", "", f"收到ECU的响应报文")
        else:
            TestLog("PASS", "", f"ECU无响应报文")

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC7_NoCF():
    """不发送所有连续帧"""
    case_name = "不发送所有连续帧"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        if P.TpInfo.CanFDMode == 0:

            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x122  # 总长度
        else:

            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x13A  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()
        
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.5)

        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        TestLog("INFO", "Step1", "发送多帧请求报文请求响应")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        start_time = sl_time().timestamp()
        # 从接收报文列表中获取流控帧  -s
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)
        if payload_30 is not None:
            TestLog("PASS", "", f"期望结果：收到流控帧(FC)。实际结果：收到FC")
        else:
            TestLog("FAIL", "", f"期望结果：收到流控帧(FC)。实际结果：未收到FC")
            check_msg_thread_stop(rt)
            return

        stmin_ms = get_fc_st_min_ms(payload_30)

        TestLog("INFO", "Step2", "不发送连续帧")
        rt.clear()
        sl_time().sleep(rN_CrTimeout_ms * 1.3)

        # 在该状态下，应该没有帧
        if len(rt.get_recv_list()) != 0:
            TestLog("FAIL", "", f"期望结果：收到ECU的响应报文。实际结果：收到ECU的响应报文")
        else:
            TestLog("PASS", "", f"期望结果：收到ECU的响应报文。实际结果：ECU无响应报文")

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC8_DropCF():
    """连续帧丢失"""
    case_name = "连续帧丢失"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        if P.TpInfo.CanFDMode == 0:

            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x1C  # 总长度
        else:

            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0xFC  # 总长度


        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", "发送多帧请求报文请求响应")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)

        sl_time().sleep(rN_BsTimeout_ms)
        # 收到的流控帧的时间戳
        recv_list = rt.get_recv_list()
        payload_30 = None
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0]>>4 == 0x3:
                payload_30 = payload
                break
        if payload_30 is not None:
            TestLog("PASS", "", f"期望结果：收到流控帧(FC)。实际结果：收到FC")
        else:
            TestLog("FAIL", "", f"期望结果：收到流控帧(FC)。实际结果：未收到FC")
            check_msg_thread_stop(rt)
            return

        stmin_ms = get_fc_st_min_ms(payload_30)
        TestLog("INFO", "Step2", "发送连续帧，其中第三帧丢失")
        for msg in msg_list[1:3] + msg_list[4:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            sl_time().sleep(stmin_ms)

        sl_time().sleep(rP2_Client_ms)
        # 在该状态下，应该只有1帧流控帧
        if len(rt.get_recv_list()) != 1:
            TestLog("FAIL", "", f"收到ECU的响应报文")
        else:
            TestLog("PASS", "", f"ECU无响应报文")

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC9_DoubleCF():
    """重复发送连续帧"""
    case_name = "重复发送连续帧"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        if P.TpInfo.CanFDMode == 0:

            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x1C  # 总长度
        else:

            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0xFC  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)

        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        TestLog("INFO", "Step1", "发送多帧请求报文请求响应")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        start_time = sl_time().timestamp()
        # 收到的流控帧的时间戳
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)

        if payload_30 is not None:
            TestLog("PASS", "", f"期望结果：收到流控帧(FC)。实际结果：收到FC")
        else:
            TestLog("FAIL", "", f"期望结果：收到流控帧(FC)。实际结果：未收到FC")
            check_msg_thread_stop(rt)
            return

        stmin_ms = get_fc_st_min_ms(payload_30)

        TestLog("INFO", "Step2", "将第一个连续帧发送两次")
        rt.clear()
        for msg in [msg_list[1]] + msg_list[1:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            sl_time().sleep(stmin_ms)
        # 在该状态下，应该只有1帧流控帧
        sl_time().sleep(rP2_Client_ms * 1.3)
        if len(rt.get_recv_list()) == 0:
            TestLog("PASS", "", f"期望结果：收到ECU的响应报文。实际结果：无ECU响应报文")
        else:
            status, retult = check_negative_resp(rt)
            if status is False:
                TestLog("WARNING", "", f"期望结果：收到ECU的响应报文。实际结果：ECU响应报文,{retult}")
            else:
                TestLog("FAIL", "", f"期望结果：收到ECU的响应报文。实际结果：收到ECU的响应报文")

        TestLog("INFO", "Step3", "发送多帧请求报文请求响应")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        start_time = sl_time().timestamp()

        # 收到的流控帧的时间戳
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)
        if payload_30 is not None:
            TestLog("PASS", "", f"期望结果：收到流控帧(FC)。实际结果：收到FC")
        else:
            TestLog("FAIL", "", f"期望结果：收到流控帧(FC)。实际结果：未收到FC")
            check_msg_thread_stop(rt)
            return

        stmin_ms = get_fc_st_min_ms(payload_30)

        TestLog("INFO", "Step4", "将最后一个连续帧发送两次")
        # for msg in msg_list[1:]+[msg_list[-1]]:
        #     send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
        #     sl_time().sleep(stmin_ms)
        cf_list = msg_list[1:]                 # 连续帧切片
        for i, msg in enumerate(cf_list):
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            if i == len(cf_list) - 1:          # 真正的最后一帧
                send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            else:
                sl_time().sleep(stmin_ms)

        sl_time().sleep(rP2_Client_ms * 1.3)

        # 在该状态下，应该有1帧流控帧和1帧负响应报文
        if len(rt.get_recv_list()) >= 2 and rt.get_recv_item_payload(1)[:3] == [0x03, 0x7F, 0x22]:
            TestLog("PASS", "", f"期望结果：收到ECU的响应报文。实际结果：收到ECU的响应报文")
        else:
            TestLog("FAIL", "", f"期望结果：收到ECU的响应报文。实际结果：ECU无响应报文,报文数量为{len(rt.get_recv_list())}")
        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC10_DelayCF():
    """延迟发送连续帧"""
    case_name = "延迟发送连续帧"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_AsTimeout_ms = P.TpInfo.N_AsTimeout  # N_As最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        if P.TpInfo.CanFDMode == 0:

            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x01C  # 总长度
        else:

            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0xFC  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        # Step1 ：发送多帧请求报文请求响应
        TestLog("INFO", "Step1", "发送多帧请求报文请求响应")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        start_time = sl_time().timestamp()

        # 收到的流控帧的时间戳
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)
        if payload_30 is not None:
            TestLog("PASS", "", f"期望结果：收到流控帧(FC)。实际结果：收到FC")
        else:
            TestLog("FAIL", "", f"期望结果：收到流控帧(FC)。实际结果：未收到FC")
            check_msg_thread_stop(rt)
            return

        # Step2：等待超时时间110%
        TestLog("INFO", "Step2", f"等待超时(超时时间110%N_Cr={rN_CrTimeout_ms * 1.1}ms)")
        rt.clear()
        sl_time().sleep(rN_CrTimeout_ms * 1.1)

        stmin_ms = get_fc_st_min_ms(payload_30)

        # Step3 ： 发送连续帧
        TestLog("INFO", "Step3", "发送连续帧")
        for msg in msg_list[1:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            sl_time().sleep(stmin_ms)

        sl_time().sleep(rP2_Client_ms)

        # 此时应只有没有帧
        if len(rt.get_recv_list()) == 0:
            TestLog("PASS", "", "期望结果：DUT在P2超时前未响应。实际结果：DUT在P2超时前未响应")
        else:
            status, retult = check_negative_resp(rt)
            if status is False:
                TestLog("WARNING", "", f"期望结果：收到ECU的响应报文。实际结果：ECU响应报文,{retult}")
            else:
                TestLog("FAIL", "",
                    f"期望结果：DUT在P2超时前未响应。实际结果：DUT在P2超时前响应: {[[hex(i) for i in item['payload']] for item in rt.get_recv_list()]}")

        TestLog("INFO", "Step4", "发送多帧请求报文请求响应")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        start_time = sl_time().timestamp()
        # 收到的流控帧的时间戳
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)
        if payload_30 is not None:
            TestLog("PASS", "", f"期望结果：收到流控帧(FC)。实际结果：收到FC")
        else:
            TestLog("FAIL", "", f"期望结果：收到流控帧(FC)。实际结果：未收到FC")
            check_msg_thread_stop(rt)
            return

        stmin_ms = get_fc_st_min_ms(payload_30)

        TestLog("INFO", "Step5", "发送CF第一帧")
        send_canmsg(can_channel, msg_list[1], rDiagReqID, dlc=msg_list[1].dlc)

        TestLog("INFO", "Step6", f"等待超时(超时时间110%N_Cr={rN_CrTimeout_ms * 1.1}ms)")

        sl_time().sleep(rN_CrTimeout_ms * 1.1)

        TestLog("INFO", "Step7", "发送剩下的连续帧")
        for msg in msg_list[2:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            sl_time().sleep(stmin_ms)
        sl_time().sleep(rP2_Client_ms)

        # 此时应只有1帧流控帧
        if len(rt.get_recv_list()) == 1:
            TestLog("PASS", "Step7", "期望结果：DUT在P2超时前未响应。实际结果：DUT在P2超时前未响应")
        else:
            status, retult = check_negative_resp(rt)
            if status is False:
                TestLog("WARNING", "", f"期望结果：收到ECU的响应报文。实际结果：ECU响应报文,{retult}")
            else:
                TestLog("FAIL", "Step7",
                    f"期望结果：DUT在P2超时前未响应。实际结果：DUT在P2超时前响应: {[[hex(i) for i in item['payload']] for item in rt.get_recv_list()]}")

        TestLog("INFO", "Step8", "发送多帧请求报文请求响应")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)

        start_time = sl_time().timestamp()
        # 收到的流控帧的时间戳
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)
        if payload_30 is not None:
            TestLog("PASS", "", f"期望结果：收到流控帧(FC)。实际结果：收到FC")
        else:
            TestLog("FAIL", "", f"期望结果：收到流控帧(FC)。实际结果：未收到FC")
            check_msg_thread_stop(rt)
            return

        stmin_ms = get_fc_st_min_ms(payload_30)

        TestLog("INFO", "Step9", f"等待超时(超时时间N_Cr-5ms={rN_CrTimeout_ms - 5}ms)")
        # sl_time().sleep(rN_CrTimeout_ms - 50)

        TestLog("INFO", "Step10", "发送连续帧")
        for msg in msg_list[1:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            sl_time().sleep(stmin_ms)
        sl_time().sleep(rP2_Client_ms)

        # 在该状态下，应该有1帧流控帧和1帧负响应报文
        if len(rt.get_recv_list()) >= 2 and rt.get_recv_item_payload(1)[:3] == [0x03, 0x7F, 0x22]:
            TestLog("PASS", "",
                    f"期望结果：DUT在P2超时前未响应。实际结果：DUT在P2超时前响应:{[[hex(i) for i in item['payload']] for item in rt.get_recv_list()]}")
        else:
            TestLog("FAIL", "", f"期望结果：DUT在P2超时前未响应。实际结果：DUT在P2超时前未响应")

        TestLog("INFO", "Step11", "发送多帧请求报文请求响应")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)

        start_time = sl_time().timestamp()
        # 收到的流控帧的时间戳
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)
        if payload_30 is not None:
            TestLog("PASS", "", f"期望结果：收到流控帧(FC)。实际结果：收到FC")
        else:
            TestLog("FAIL", "", f"期望结果：收到流控帧(FC)。实际结果：未收到FC")
            check_msg_thread_stop(rt)
            return

        stmin_ms = get_fc_st_min_ms(payload_30)

        TestLog("INFO", "Step12", "发送CF第一帧")
        send_canmsg(can_channel, msg_list[1], rDiagReqID, dlc=msg_list[1].dlc)

        TestLog("INFO", "Step13", f"等待超时(超时时间N_Cr-5={rN_CrTimeout_ms - 5}ms)")
        # sl_time().sleep(rN_CrTimeout_ms - 10)

        TestLog("INFO", "Step14", "发送剩下的连续帧")
        for msg in msg_list[2:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            sl_time().sleep(stmin_ms)
        sl_time().sleep(rP2_Client_ms)

        # 在该状态下，应该有1帧流控帧和1帧负响应报文
        if len(rt.get_recv_list()) >= 2 and rt.get_recv_item_payload(1)[:3] == [0x03, 0x7F, 0x22]:
            TestLog("PASS", "",
                    f"期望结果：DUT在P2超时前未响应。实际结果：DUT在P2超时前响应: {[[hex(i) for i in item['payload']] for item in rt.get_recv_list()]}")
        else:
            TestLog("FAIL", "", f"期望结果：DUT在P2超时前未响应。实际结果：DUT在P2超时前未响应,报文数量为{len(rt.get_recv_list())}")

        check_msg_thread_stop(rt)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC11_NoFC():
    """无流控帧"""
    case_name = "无流控帧"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        msg_first = canmsg_create(rDiagReqID, 8, data=[0x02, 0x19, 0x0A] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_30 = canmsg_create(rDiagReqID, 8, data=[0x30] + [0xAA] * 7, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        send_canmsg(can_channel, msg_first, rDiagReqID, dlc=msg_first.dlc)

        TestLog("INFO", "Step2", "不发送流控帧")
        sl_time().sleep(rN_BsTimeout_ms + rN_CrTimeout_ms)

        # 此时应只有1帧首帧
        if len(rt.get_recv_list()) == 1:
            TestLog("PASS", "", "期望结果：DUT在P2超时前未响应。实际结果：DUT在P2超时前未响应")
        else:
            TestLog("FAIL", "",
                    f"期望结果：DUT在P2超时前未响应。实际结果：DUT在P2超时前响应: {[[hex(i) for i in item['payload']] for item in rt.get_recv_list()]}")
        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC12_DelayFC():
    """延迟发送流控帧"""
    case_name = "延迟发送流控帧"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        msg_first = canmsg_create(rDiagReqID, 8, data=[0x02, 0x19, 0x0A] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_30 = canmsg_create(rDiagReqID, 8, data=[0x30] + [0x00] * 2 + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg_first, rDiagReqID, dlc=msg_first.dlc)
        # 从接收报文列表中获取所有的首帧FF  -s
        payload_10 = None
        payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
        if payload_10 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return
        
        TestLog("INFO", "Step2", "等待超时(超时时间110%*N_Bsms)")

        # sl_time().sleep(165)

        TestLog("INFO", "Step3", "发送流控帧")
        rt.clear()
        sl_time().sleep(rN_CrTimeout_ms * 1.1)
        send_canmsg(can_channel, msg_30, rDiagReqID, dlc=msg_30.dlc)

        sl_time().sleep(rN_CrTimeout_ms)

        # 此时应只有0帧报文
        if len(rt.get_recv_list()) ==0:
            TestLog("PASS", "", f"期望结果：DUT在P2超时前未响应。实际结果：DUT在{1.1 * rN_CrTimeout_ms}超时前未响应")
        else:
            TestLog("FAIL", "",
                    f"期望结果：DUT在P2超时前未响应。实际结果：DUT在{1.1 * rN_CrTimeout_ms}超时前响应: {[[hex(i) for i in item['payload']] for item in rt.get_recv_list()]}")

        TestLog("INFO", "Step4", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg_first, rDiagReqID, dlc=msg_first.dlc)
        # 从接收报文列表中获取所有的首帧FF  -s
        payload_10 = None
        payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
        if payload_10 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step5", f"等待超时(超时时间{0.9 * rN_CrTimeout_ms})")

        # sl_time().sleep(rN_CrTimeout_ms * 0.8)

        TestLog("INFO", "Step6", "发送流控帧")
        send_canmsg(can_channel, msg_30, rDiagReqID, dlc=msg_30.dlc)

        sl_time().sleep(rN_CrTimeout_ms)

        recv_list = rt.get_recv_list()
        status = False
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] == 0x21:
                status = True
                break

        if status is True:
            TestLog("PASS", "",
                    f"期望结果：DUT在P2超时前响应。实际结果：DUT在{1.1 * rN_CrTimeout_ms}超时前响应")
        else:
            TestLog("FAIL", "", f"期望结果：DUT在P2超时前响应。实际结果：DUT在{1.1 * rN_CrTimeout_ms}超时前未响应")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC13_RepeatFC():
    """重复发送流控帧"""
    case_name = "重复发送流控帧"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        msg_first = canmsg_create(rDiagReqID, 8, data=[0x02, 0x19, 0x0A] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_30_1 = canmsg_create(rDiagReqID, 8, data=[0x30, 0x00, 0x28] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_30_2 = canmsg_create(rDiagReqID, 8, data=[0x30, 0x00, 0x00] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg_first, rDiagReqID, dlc=msg_first.dlc)

        # 从接收报文列表中获取所有的首帧FF  -s
        payload_10 = None
        payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
        if payload_10 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step2", "发送流控帧(STmin=0x28[40ms])")
        rt.clear()
        send_canmsg(can_channel, msg_30_1, rDiagReqID, dlc=msg_30_1.dlc)

        TestLog("INFO", "Step3", "再次发送流控帧(STmin=0x00[0ms])")
        rt.clear()
        send_canmsg(can_channel, msg_30_2, rDiagReqID, dlc=msg_30_2.dlc)

        sl_time().sleep(rN_CrTimeout_ms * 1.1)

        # 从首帧中获取DL
        dl = ((payload_10[0] & 0x0F) << 8) | payload_10[1]
        expect_cf_counter = math.ceil((dl - (P.TpInfo.MaxCanFDDataLength - 2)) / (P.TpInfo.MaxCanFDDataLength - 1))  # 根据DL计算出正常的连续帧的数量

        sl_time().sleep(expect_cf_counter * rN_CrTimeout_ms)
        # 从接收报文列表中获取所有的连续帧CF  -s
        cf_tm_list = []
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            timestamp = rt.get_recv_item_timestamp(i)
            if payload[0] >> 4 == 2:
                cf_tm_list.append(timestamp)

        cf_tm_diff = []
        for i in range(len(cf_tm_list) - 1):
            cf_tm_diff.append(cf_tm_list[i + 1] - cf_tm_list[i])
        if min(cf_tm_diff) < 0x28:
            TestLog("FAIL", "",
                    f"期望结果：接收到响应，且连续帧之间的间隔均大于等于0x28(40ms)。实际结果：收到的连续帧之间的时间间隔存在小于0x28(40ms)，CF帧时间戳={cf_tm_list}，时间间隔={cf_tm_diff}")
            check_msg_thread_stop(rt)
            return
        else:
            TestLog("PASS", "",
                    f"期望结果：接收到响应，且连续帧之间的间隔均大于等于0x28(40ms)。实际结果：接收到响应，且连续帧之间的间隔均大于等于0x28(40ms)，CF帧时间戳={cf_tm_list}，时间间隔={cf_tm_diff}")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC14_STminTiming():
    """STmin时间测试"""
    case_name = "STmin时间测试"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_ArTimeout_ms = P.TpInfo.N_ArTimeout  # N_Ar最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        msg_first = canmsg_create(rDiagReqID, 8, data=[0x02, 0x19, 0x0A] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)

        stmin_list = [1, 10, 20, 30, 40, 50, 60]
        TestLog("INFO", "", f"循环测试{stmin_list=}")
        for stmin_ms in stmin_list:
            TestLog("INFO", "", f"===使用STmin={stmin_ms}ms进行测试===")
            msg_30 = canmsg_create(rDiagReqID, 8, data=[0x30, 0x00, stmin_ms] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)

            # 开启线程，用于检测响应报文
            check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
            sl_time().sleep(5)
            TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
            rt.clear()
            send_canmsg(can_channel, msg_first, rDiagReqID, dlc=msg_first.dlc)

            # 从接收报文列表中获取首帧FF  -s
            payload_10 = None
            payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
            if payload_10 is not None:
                TestLog("PASS", "", "期望结果：收到流控帧(FF)。实际结果：收到首帧(FF)")
            else:
                TestLog("FAIL", "", "期望结果：收到流控帧(FF)。实际结果：超时未收到首帧(FF)")
                check_msg_thread_stop(rt)
                continue

            TestLog("INFO", "Step2", f"发送流控帧(STmin={stmin_ms}ms)")
            rt.clear()
            send_canmsg(can_channel, msg_30, rDiagReqID, dlc=msg_30.dlc)

            # 从首帧中获取DL
            dl = ((payload_10[0] & 0x0F) << 8) | payload_10[1]
            expect_cf_counter = math.ceil((dl - (P.TpInfo.MaxCanFDDataLength - 2)) / (P.TpInfo.MaxCanFDDataLength - 1))  # 根据DL计算出正常的连续帧的数量

            sl_time().sleep(expect_cf_counter * rN_CrTimeout_ms)

            # 从接收报文列表中获取所有的连续帧CF  -s
            cf_tm_list = []
            cf_list = []
            recv_list = rt.get_recv_list()
            for i in range(len(recv_list)):
                payload = rt.get_recv_item_payload(i)
                timestamp = rt.get_recv_item_timestamp(i)
                if payload[0] >> 4 == 2:
                    cf_tm_list.append(timestamp)
                    cf_list.append(payload)
            # 从接收报文列表中获取所有的连续帧CF  -e

            if len(cf_tm_list) != expect_cf_counter:
                TestLog("FAIL", "", f"期望收到{expect_cf_counter}帧连续帧,"
                                    f"实际收到{len(cf_tm_list)}帧连续帧={cf_list}")
                check_msg_thread_stop(rt)
                continue

            cf_tm_diff = []
            for i in range(len(cf_tm_list) - 1):
                cf_tm_diff.append(cf_tm_list[i + 1] - cf_tm_list[i])
            if min(cf_tm_diff) < stmin_ms:
                TestLog("FAIL", "",
                        f"期望结果：接收到响应，且连续帧之间的间隔均大于等于{stmin_ms}ms。实际结果：收到的连续帧之间的时间间隔存在小于{stmin_ms}ms，CF帧时间戳={cf_tm_list}，时间间隔={cf_tm_diff}")
                check_msg_thread_stop(rt)
                continue
            else:
                TestLog("PASS", "",
                        f"期望结果：接收到响应，且连续帧之间的间隔均大于等于{stmin_ms}ms。实际结果：接收到响应，且连续帧之间的间隔均大于等于{stmin_ms}ms，CF帧时间戳={cf_tm_list}，时间间隔={cf_tm_diff}")

            check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC15_CheckValidSTmin():
    """确认DUT的STmin参数有效"""
    case_name = "确认DUT的STmin参数有效"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        if P.TpInfo.CanFDMode == 0:

            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x1C  # 总长度
        else:

            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0xFC  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        TestLog("INFO", "Step1", "发送多帧请求报文请求响应")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)

        sl_time().sleep(rN_BsTimeout_ms)

        # 从接收报文列表中获取流控帧FC  -s
        payload_30 = None
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0]>>4 == 0x3:
                payload_30 = payload
                break
        # 从接收报文列表中获取流控帧FC  -e

        if payload_30 is not None:
            TestLog("PASS", "", f"期望结果：收到流控帧(FC)。实际结果：收到FC")
        else:
            TestLog("FAIL", "", f"期望结果：收到流控帧(FC)。实际结果：未收到FC")
            check_msg_thread_stop(rt)
            return

        stmin_byte = payload_30[2]

        if 0x00 <= stmin_byte <= 0x7F or 0xF1 <= stmin_byte <= 0xF9:
            TestLog("PASS", "", f"期望结果：STmin is valid={hex(stmin_byte)}。实际结果：STmin is valid={hex(stmin_byte)}")
        else:
            TestLog("FAIL", "", f"期望结果：STmin is valid={hex(stmin_byte)}。实际结果：STmin is invalid={hex(stmin_byte)}")

        check_msg_thread_stop(rt)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC16_CheckSFDatalength():
    """检查SF报文长度"""
    case_name = "检查SF报文长度"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        msg = canmsg_create(rDiagReqID, 8, data=[0x03, 0x22, 0xF0, 0xF1] + [0xAA] * 4, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        TestLog("INFO", "Step1", "发送请求报文请求单帧响应")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        sl_time().sleep(rN_BsTimeout_ms)

        response_list = rt.get_recv_list()
        if len(response_list) == 0:
            TestLog("FAIL", "", f"期望结果：收到ECU响应报文。实际结果：未收到响应报文")
            check_msg_thread_stop(rt)
            return

        response_data = rt.get_recv_item_payload(0)
        pci_type = (response_data[0] & 0xF0) >> 4
        pci_low = response_data[0] & 0x0F
        if pci_type != 0:
            TestLog("FAIL", "", f"期望结果：收到SF帧。实际结果：PCI类型={pci_type}，非SF帧，数据={[hex(i) for i in response_data]}")
            check_msg_thread_stop(rt)
            return
        if pci_low != 0:
            sf_len = pci_low
            max_len = 7
        else:
            sf_len = response_data[1]
            max_len = P.TpInfo.MaxCanFDDataLength - 2
        if 0 < sf_len <= max_len:
            TestLog("PASS", "", f"期望结果：the length of SF is valid={sf_len}。实际结果：the length of SF is valid={sf_len}")
        else:
            TestLog("FAIL", "", f"期望结果：the length of SF is valid={sf_len}。实际结果：the length of SF is invalid={sf_len}")
            check_msg_thread_stop(rt)
            return

        check_msg_thread_stop(rt)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC17_CheckFFDatalength():
    """检查FF报文长度"""
    case_name = "检查FF报文长度"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        msg = canmsg_create(rDiagReqID, 8, data=[0x02, 0x19, 0x0A] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        # sl_time().sleep(rN_BsTimeout_ms)

        # 从接收报文列表中获取首帧FF  -s
        payload_10 = None
        payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
        if payload_10 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return 

        ff_len = (payload_10[0] & 0xF) << 8 | payload_10[1]
        if P.TpInfo.CanFDMode:
            if 62 < ff_len <= 0xFFF:
                TestLog("PASS", "",f"实际结果：the length of FF is valid={hex(ff_len)}，期望结果：the length of FF is valid={hex(ff_len)}")
            else:
                TestLog("FAIL", "",f"实际结果：the length of FF is valid={hex(ff_len)}，期望结果：the length of FF is invalid={hex(ff_len)}")
        else:
            if 7 < ff_len <= 0xFFF:
                TestLog("PASS", "",f"实际结果：the length of FF is valid={hex(ff_len)}，期望结果：the length of FF is valid={hex(ff_len)}")
            else:
                TestLog("FAIL", "",f"实际结果：the length of FF is valid={hex(ff_len)}，期望结果：the length of FF is invalid={hex(ff_len)}")

        check_msg_thread_stop(rt)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC18_ResponseInterruptedbySF():
    """响应被非预期单帧报文干扰"""
    case_name = "响应被非预期单帧报文干扰"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_ArTimeout_ms = P.TpInfo.N_ArTimeout  # N_Ar最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        msg = canmsg_create(rDiagReqID, 8, data=[0x02, 0x19, 0x0A] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_30_1 = canmsg_create(rDiagReqID, 8, data=[0x30, 0x00, 0x14] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_ff = canmsg_create(rDiagReqID, 8, data=[0x03, 0x22, 0xF0, 0xF1] + [0xAA] * 4, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        sl_time().sleep(rN_ArTimeout_ms)

        # 从接收报文列表中获取首帧FF  -s
        payload_10 = None
        payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
        if payload_10 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return 


        TestLog("INFO", "Step2", "发送流控帧")
        send_canmsg(can_channel, msg_30_1, rDiagReqID, dlc=msg_30_1.dlc)

        TestLog("INFO", "Step3", "发送单帧")
        send_canmsg(can_channel, msg_ff, rDiagReqID, dlc=msg_ff.dlc)

        # 从首帧中获取DL
        dl = ((payload_10[0] & 0x0F) << 8) | payload_10[1]
        expect_cf_counter = math.ceil((dl - (P.TpInfo.MaxCanFDDataLength - 2)) / (P.TpInfo.MaxCanFDDataLength - 1))  # 根据DL计算出正常的连续帧的数量

        sl_time().sleep(expect_cf_counter * rN_CrTimeout_ms)

        # 从接收报文列表中获取连续帧CF 和 正响应报文  -s
        positive_response = False
        cf_list = []
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 2:
                cf_list.append(payload)
            if 0x62 in payload and 0xf0 in payload and 0xf1 in payload:
                positive_response = True
        # 从接收报文列表中获取连续帧CF 和 正响应报文  -s

        if expect_cf_counter != len(cf_list):
            TestLog("FAIL", "", f"未收到完整的连续帧，期望收到{expect_cf_counter}帧，实际收到{len(cf_list)}帧")
            check_msg_thread_stop(rt)
            return
        else:
            flag = True
            for i in range(len(cf_list) - 1):
                diff = cf_list[i + 1][0] - cf_list[i][0]
                if cf_list[i][0] == 0x2F and cf_list[i + 1][0] != 0x20:
                    flag = False
                    break
                elif diff != 1 and cf_list[i][0] != 0x2F:
                    flag = False
                    break

            if flag is False:
                TestLog("FAIL", "", f"期望结果：收到完整的连续帧，收到{expect_cf_counter}帧。实际结果：收到的连续帧SN不连续，{cf_list=}")
                check_msg_thread_stop(rt)
                return
            else:
                TestLog("PASS", "", f"期望结果：收到完整的连续帧，收到{expect_cf_counter}帧。实际结果：收到{len(cf_list)}帧")

        if positive_response is True:
            TestLog("WARNING", "", f"收到了单帧的响应报文")
        else:
            TestLog("WARNING", "", f"未收到单帧的响应报文")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC19_ResponseInterruptedbyFF():
    """响应被非预期首帧报文干扰"""
    case_name = "响应被非预期首帧报文干扰"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_ArTimeout_ms = P.TpInfo.N_ArTimeout  # N_Ar最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout
        if P.TpInfo.CanFDMode == 0:

            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x1C  # 总长度
        else:

            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0xFC  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)

        msg = canmsg_create(rDiagReqID, 8, data=[0x02, 0x19, 0x0A] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_30_1 = canmsg_create(rDiagReqID, 8, data=[0x30, 0x00, 0x14] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
        # 从接收报文列表中获取首帧FF  -s
        payload_10 = None
        payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
        if payload_10 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step2", "发送流控帧")
        send_canmsg(can_channel, msg_30_1, rDiagReqID, dlc=msg_30_1.dlc)

        # 从首帧中获取DL
        dl = ((payload_10[0] & 0x0F) << 8) | payload_10[1]
        expect_cf_counter = math.ceil((dl - (P.TpInfo.MaxCanFDDataLength - 2)) / (P.TpInfo.MaxCanFDDataLength - 1))  # 根据DL计算出正常的连续帧的数量
        sl_time().sleep(22)

        TestLog("INFO", "Step3", "发送首帧")
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        sl_time().sleep(rN_CrTimeout_ms * (expect_cf_counter-1))

        # 从接收报文列表中获取所有的连续帧CF 和 流控帧FC  -s
        fc_counter = 0
        cf_list = []
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 2:
                cf_list.append(payload)
            if payload[0] >> 4 == 3:
                fc_counter += 1
        # 从接收报文列表中获取所有的连续帧CF 和 流控帧FC  -e

        if expect_cf_counter != len(cf_list):
            TestLog("FAIL", "", f"未收到完整的连续帧，期望收到{expect_cf_counter}帧，实际收到{len(cf_list)}帧")
            check_msg_thread_stop(rt)
            return
        else:
            flag = True
            for i in range(len(cf_list) - 1):
                diff = cf_list[i + 1][0] - cf_list[i][0]
                if cf_list[i][0] == 0x2F and cf_list[i + 1][0] != 0x20:
                    flag = False
                    break
                elif diff != 1 and cf_list[i][0] != 0x2F:
                    flag = False
                    break
            if flag is False:
                TestLog("FAIL", "", f"期望结果：收到完整的连续帧，收到{expect_cf_counter}帧。实际结果：收到的连续帧SN不连续，{cf_list=}")
                check_msg_thread_stop(rt)
                return
            else:
                TestLog("PASS", "", f"期望结果：收到完整的连续帧，收到{expect_cf_counter}帧。实际结果：收到{len(cf_list)}帧")

        if fc_counter > 0:
            TestLog("WARNING", "", f"实际结果：收到了首帧的响应报文")
        else:
            TestLog("WARNING", "", f"实际结果：未收到首帧的响应报文")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC20_ResponseInterruptedbyCF():
    """响应被非预期连续帧报文干扰"""
    case_name = "响应被非预期连续帧报文干扰"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_ArTimeout_ms = P.TpInfo.N_ArTimeout  # N_Ar最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout
        if P.TpInfo.CanFDMode == 0:

            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x0D  # 总长度
        else:

            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x7D  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        msg = canmsg_create(rDiagReqID, 8, data=[0x02, 0x19, 0x0A] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_30_1 = canmsg_create(rDiagReqID, 8, data=[0x30, 0x00, 0x14] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        sl_time().sleep(rN_ArTimeout_ms)

        # 从接收报文列表中获取首帧FF  -s
        payload_10 = None
        payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
        if payload_10 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step2", "发送流控帧")
        send_canmsg(can_channel, msg_30_1, rDiagReqID, dlc=msg_30_1.dlc)

        # 从首帧中获取DL
        dl = ((payload_10[0] & 0x0F) << 8) | payload_10[1]
        expect_cf_counter = math.ceil((dl - (P.TpInfo.MaxCanFDDataLength - 2)) / (P.TpInfo.MaxCanFDDataLength - 1))  # 根据DL计算出正常的连续帧的数量
        sl_time().sleep(22)

        TestLog("INFO", "Step3", "发送连续帧")
        for msg in msg_list[1:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        
        sl_time().sleep(expect_cf_counter * rN_CrTimeout_ms)

        # 从接收报文列表中获取所有的连续帧CF  -s
        cf_list = []
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 2:
                cf_list.append(payload)
        # 从接收报文列表中获取所有的连续帧CF  -e

        TestLog("INFO", case_name, f"cf_list={[[hex(i) for i in item] for item in cf_list]}")

        if expect_cf_counter != len(cf_list):
            TestLog("FAIL", "", f"未收到完整的连续帧，期望收到{expect_cf_counter}帧，实际收到{len(cf_list)}帧")
            check_msg_thread_stop(rt)
            return
        else:
            flag = True
            for i in range(len(cf_list) - 1):
                diff = cf_list[i + 1][0] - cf_list[i][0]
                if cf_list[i][0] == 0x2F and cf_list[i + 1][0] != 0x20:
                    flag = False
                    break
                elif diff != 1 and cf_list[i][0] != 0x2F:
                    flag = False
                    break
            if flag is False:
                TestLog("FAIL", "", f"期望结果：收到完整的连续帧，收到{expect_cf_counter}帧。实际结果：收到的连续帧SN不连续，{cf_list=}")
                check_msg_thread_stop(rt)
                return
            else:
                TestLog("PASS", "", f"期望结果：收到完整的连续帧，收到{expect_cf_counter}帧。实际结果：收到{len(cf_list)}帧")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")
    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC21_ResponseInterruptedbyFC():
    """响应被非预期流控帧报文干扰"""
    case_name = "响应被非预期流控帧报文干扰"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_ArTimeout_ms = P.TpInfo.N_ArTimeout  # N_Ar最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        msg = canmsg_create(rDiagReqID, 8, data=[0x02, 0x19, 0x0A] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_30_1 = canmsg_create(rDiagReqID, 8, data=[0x30, 0x00, 0x14] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_32 = canmsg_create(rDiagReqID, 8, data=[0x32, 0x00, 0x14] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        sl_time().sleep(rN_ArTimeout_ms)

        # 从接收报文列表中获取首帧FF  -s
        payload_0x10 = None
        payload_0x10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
        if payload_0x10 is not None:
            TestLog("PASS", "", "期望结果：收到首帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到首帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step2", "发送流控帧")
        rt.clear()
        send_canmsg(can_channel, msg_30_1, rDiagReqID, dlc=msg_30_1.dlc)
        start_time = sl_time().timestamp()
        payload_first_cf = check_first_cf(rN_CrTimeout_ms, start_time, rt)
        if payload_first_cf is not None:
            TestLog("PASS", "", "期望结果：连续帧第一帧响应.实际结果：连续帧第一帧响应")
        else:
            TestLog("FAIL", "", "期望结果：连续帧第一帧响应.实际结果：超时未收到连续帧第一帧响应")
            check_msg_thread_stop(rt)
            return

        # 从首帧中获取DL
        dl = ((payload_0x10[0] & 0x0F) << 8) | payload_0x10[1]
        expect_cf_counter = math.ceil((dl - (P.TpInfo.MaxCanFDDataLength - 2)) / (P.TpInfo.MaxCanFDDataLength - 1))  # 根据DL计算出正常的连续帧的数量

        TestLog("INFO", "Step3", "发送流控帧")
        send_canmsg(can_channel, msg_32, rDiagReqID, dlc=msg_32.dlc)

        sl_time().sleep(expect_cf_counter * rN_CrTimeout_ms)

        # 从接收报文列表中获取所有的连续帧CF  -s
        cf_list = []
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 2:
                cf_list.append(payload)
        # 从接收报文列表中获取所有的连续帧CF  -e

        TestLog("INFO", case_name, f"cf_list={[[hex(i) for i in item] for item in cf_list]}")

        if expect_cf_counter != len(cf_list):
            TestLog("FAIL", "", f"未收到完整的连续帧，期望收到{expect_cf_counter}帧，实际收到{len(cf_list)}帧")
            check_msg_thread_stop(rt)
            return
        else:
            flag = True
            for i in range(len(cf_list) - 1):
                diff = cf_list[i + 1][0] - cf_list[i][0]
                if cf_list[i][0] == 0x2F and cf_list[i + 1][0] != 0x20:
                    flag = False
                    break
                elif diff != 1 and cf_list[i][0] != 0x2F:
                    flag = False
                    break
            if flag is False:
                TestLog("FAIL", "", f"期望结果：收到完整的连续帧，收到{expect_cf_counter}帧。实际结果：收到的连续帧SN不连续，{cf_list=}")
                check_msg_thread_stop(rt)
                return
            else:
                TestLog("PASS", "", f"期望结果：收到完整的连续帧，收到{expect_cf_counter}帧。实际结果：收到{len(cf_list)}帧")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC22_ResponseInterruptedbyUnknownFrame():
    """响应被非预期未知报文干扰"""
    case_name = "响应被非预期未知报文干扰"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        msg = canmsg_create(rDiagReqID, 8, data=[0x02, 0x19, 0x0A] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_30_1 = canmsg_create(rDiagReqID, 8, data=[0x30, 0x00, 0x14] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_unknown = canmsg_create(rDiagReqID, 8, data=[0x40, 0x01, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
        # 从接收报文列表中获取首帧FF  -s
        payload_0x10 = None
        payload_0x10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
        if payload_0x10 is not None:
            TestLog("PASS", "", "期望结果：收到首帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到首帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step2", "发送流控帧")
        rt.clear()
        send_canmsg(can_channel, msg_30_1, rDiagReqID, dlc=msg_30_1.dlc)
        start_time = sl_time().timestamp()
        payload_first_cf = check_first_cf(rN_CrTimeout_ms, start_time, rt)

        if payload_first_cf is not None:
            TestLog("PASS", "", "期望结果：连续帧第一帧响应.实际结果：连续帧第一帧响应")
        else:
            TestLog("FAIL", "", "期望结果：连续帧第一帧响应.实际结果：超时未收到连续帧第一帧响应")
            check_msg_thread_stop(rt)
            return

        # 从首帧中获取DL
        dl = ((payload_0x10[0] & 0x0F) << 8) | payload_0x10[1]
        expect_cf_counter = math.ceil((dl - (P.TpInfo.MaxCanFDDataLength - 2)) / (P.TpInfo.MaxCanFDDataLength - 1))  # 根据DL计算出正常的连续帧的数量

        TestLog("INFO", "Step3", "发送未定义的报文")
        send_canmsg(can_channel, msg_unknown, rDiagReqID, dlc=msg_unknown.dlc)

        sl_time().sleep(expect_cf_counter * rN_CrTimeout_ms)

        # 从接收报文列表中获取所有的连续帧CF  -s
        cf_list = []
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 2:
                cf_list.append(payload)
        # 从接收报文列表中获取所有的连续帧CF  -e

        TestLog("INFO", "", f"cf_list={[[hex(i) for i in item] for item in cf_list]}")

        if expect_cf_counter != len(cf_list):
            TestLog("FAIL", "", f"未收到完整的连续帧，期望收到{expect_cf_counter}帧，实际收到{len(cf_list)}帧")
            check_msg_thread_stop(rt)
            return
        else:
            flag = True
            for i in range(len(cf_list) - 1):
                diff = cf_list[i + 1][0] - cf_list[i][0]
                if cf_list[i][0] == 0x2F and cf_list[i + 1][0] != 0x20:
                    flag = False
                    break
                elif diff != 1 and cf_list[i][0] != 0x2F:
                    flag = False
                    break
            if flag is False:
                TestLog("FAIL", "", f"期望结果：收到完整的连续帧，收到{expect_cf_counter}帧。实际结果：收到的连续帧SN不连续，{cf_list=}")
                check_msg_thread_stop(rt)
                return
            else:
                TestLog("PASS", "", f"期望结果：收到完整的连续帧，收到{expect_cf_counter}帧。实际结果：收到{len(cf_list)}帧")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC23_RequestInterruptedbySF():
    """请求被单帧报文干扰"""
    case_name = "请求被单帧报文干扰"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_ArTimeout_ms = P.TpInfo.N_ArTimeout  # N_Ar最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        if P.TpInfo.CanFDMode == 0:
            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x1C  # 总长度
        else:
            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0xFC  # 总长度


        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)


        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)
        msg_sf = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLengthToDLC, data=[0x03, 0x22, 0xF0, 0xF1] + [0xAA] * 4, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        TestLog("INFO", "Step1", "发送多帧请求报文，请求响应报文")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        start_time = sl_time().timestamp()
        # 从接收报文列表中获取流控帧FC  -s
        payload_0x30 = check_resp_FC_ok(rN_CrTimeout_ms, start_time, rt)

        if payload_0x30 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FC)。实际结果：收到流控帧(FC)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FC)。实际结果：超时未收到流控帧(FC)")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step2", "发送单帧")
        rt.clear()
        send_canmsg(can_channel, msg_sf, rDiagReqID, dlc=msg_sf.dlc)

        sl_time().sleep(rN_CrTimeout_ms * 1.1)

        # 从接收报文列表中获取所有的单帧的响应帧  -s
        sf_response = None
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if 0x62 in payload and 0xF0 in payload and 0xF1 in payload:
                sf_response = payload
        # 从接收报文列表中获取所有的单帧的响应帧  -e

        if sf_response is None:
            TestLog("FAIL", "", f"期望结果：收到单帧的响应报文。实际结果：未收到单帧的响应报文")
            check_msg_thread_stop(rt)
            return
        else:
            TestLog("PASS", "", f"期望结果：收到单帧的响应报文。实际结果：收到单帧的响应报文")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC24_RequestInterruptedbyFF():
    """请求被首帧报文干扰"""
    case_name = "请求被首帧报文干扰"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        if P.TpInfo.CanFDMode == 0:
            sid = 0x33 # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x1C  # 总长度
        else:
            sid = 0x33 # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0xFC  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        status, msg_list = create_ff_cfs(rDiagReqID, 0x34, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.9)

        TestLog("INFO", "Step1", "发送多帧请求报文，请求响应报文")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        start_time = sl_time().timestamp()

        # 从接收报文列表中获取流控帧FC  -s
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)

        if payload_30 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FC)。实际结果：收到流控帧(FC)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FC)。实际结果：超时未收到流控帧(FC)")
            check_msg_thread_stop(rt)
            return
        stmin_ms = get_fc_st_min_ms(payload_30)

        TestLog("INFO", "Step2", "发送首帧")
        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        start_time = sl_time().timestamp()
        # 从接收报文列表中获取流控帧FC  -s
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)

        if payload_30 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FC)。实际结果：收到流控帧(FC)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FC)。实际结果：超时未收到流控帧(FC)")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step3", "发送连续帧")
        rt.clear()
        for msg in msg_list[1:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            sl_time().sleep(stmin_ms)

        sl_time().sleep(rP2_Client_ms)

        # 从接收报文列表中获取所有的单帧的响应帧  -s
        sf_response = None
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if 0x7F in payload and 0x33 in payload:
                sf_response = payload
        # 从接收报文列表中获取所有的单帧的响应帧  -e

        if sf_response is None:
            TestLog("FAIL", "", f"期望结果：收到诊断请求的响应。实际结果：未收到诊断请求的响应")
            check_msg_thread_stop(rt)
            return
        else:
            TestLog("PASS", "", f"期望结果：收到诊断请求的响应。实际结果：收到诊断请求的响应")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC25_RequestInterruptedbyFC():
    """请求被流控帧报文干扰"""
    case_name = "请求被流控帧报文干扰"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        if P.TpInfo.CanFDMode == 0:
            sid = 0x33  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x1C  # 总长度
        else:
            sid = 0x33  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0xFC  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        msg_30_1 = canmsg_create(rDiagReqID, 8, data=[0x30, 0x00, 0x00] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)

        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", "发送多帧请求报文，请求响应报文")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        start_time = sl_time().timestamp()
        # 从接收报文列表中获取流控帧FC  -s
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)

        if payload_30 is not None:
            TestLog("PASS", "", f"期望结果：收到流控帧(FC)。实际结果：收到流控帧(FC)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FC)。实际结果：超时未收到流控帧(FC)")
            check_msg_thread_stop(rt)
            return
        stmin_ms = get_fc_st_min_ms(payload_30)
        TestLog("INFO", "", f"stmin_ms = {stmin_ms}")

        TestLog("INFO", "Step2", "发送流控帧")
        send_canmsg(can_channel, msg_30_1, rDiagReqID, dlc=msg_30_1.dlc)

        TestLog("INFO", "Step3", "发送连续帧")
        for msg in msg_list[1:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            sl_time().sleep(stmin_ms)

        sl_time().sleep(rP2_Client_ms)

        # 从接收报文列表中获取所有的单帧的响应帧  -s
        sf_response = None
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if 0x7F in payload and 0x33 in payload:
                sf_response = payload
        # 从接收报文列表中获取所有的单帧的响应帧  -e

        if sf_response is None:
            TestLog("FAIL", "", f"期望结果：收到诊断请求的响应。实际结果：未收到诊断请求的响应")
            check_msg_thread_stop(rt)
            return
        else:
            TestLog("PASS", "", f"期望结果：收到诊断请求的响应。实际结果：收到诊断请求的响应")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC26_RequestInterruptedbyUnknown():
    """请求被未知报文干扰"""
    case_name = "请求被未知报文干扰"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        if P.TpInfo.CanFDMode == 0:
            sid = 0x33  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x1C  # 总长度
        else:
            sid = 0x33  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0xFC  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)

        msg_unknown = canmsg_create(rDiagReqID, 8, data=[0x40, 0x01, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)

        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", "发送多帧请求报文，请求响应报文")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        start_time = sl_time().timestamp()

        # 从接收报文列表中获取流控帧FC  -s
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)
        if payload_30 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FC)。实际结果：收到流控帧(FC)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FC)。实际结果：超时未收到流控帧(FC)")
            check_msg_thread_stop(rt)
            return
        stmin_ms = get_fc_st_min_ms(payload_30)

        TestLog("INFO", "Step2", "发送未知报文")
        send_canmsg(can_channel, msg_unknown, rDiagReqID, dlc=msg_unknown.dlc)

        TestLog("INFO", "Step3", "发送连续帧")
        for msg in msg_list[1:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            sl_time().sleep(stmin_ms)
        sl_time().sleep(rP2_Client_ms)

        # 从接收报文列表中获取所有的单帧的响应帧  -s
        sf_response = None
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if 0x7F in payload and 0x33 in payload:
                sf_response = payload
        # 从接收报文列表中获取所有的单帧的响应帧  -e

        if sf_response is None:
            TestLog("FAIL", "", f"期望结果：收到诊断请求的响应。实际结果：未收到诊断请求的响应")
            check_msg_thread_stop(rt)
            return
        else:
            TestLog("PASS", "", f"期望结果：收到诊断请求的响应。实际结果：收到诊断请求的响应")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC27_OverflowFC():
    """流控制状态为Overflow"""
    case_name = "流控制状态为Overflow"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        msg = canmsg_create(rDiagReqID, 8, data=[0x02, 0x19, 0x0A] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)

        msg_30 = canmsg_create(rDiagReqID, 8, data=[0x32, 0x00, 0x14] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        # 从接收报文列表中获取首帧FF  -s
        payload_10 = None
        payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
        TestLog("info", "", f"payload_10 = {payload_10}")
        if payload_10 is not None:
            TestLog("PASS", "", "期望结果：收到首帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到首帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step2", "发送流控状态为Overflow的流控帧")
        send_canmsg(can_channel, msg_30, rDiagReqID, dlc=msg_30.dlc)
        sl_time().sleep(rN_CrTimeout_ms)

        # 从接收报文列表中获取所有的连续帧CF  -s
        cf_list = []
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 2:
                cf_list.append(payload)
        # 从接收报文列表中获取所有的连续帧CF  -e

        if len(cf_list) > 0:
            TestLog("FAIL", "", f"期望: ECU无响应，实际: 收到了ECU发送的连续帧")
            check_msg_thread_stop(rt)
            return
        else:
            TestLog("PASS", "", f"期望: ECU无响应，实际: 未收到ECU发送的连续帧")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC28_BlockSize():
    """BlockSize测试"""
    case_name = "BlockSize测试"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        msg = canmsg_create(rDiagReqID, 8, data=[0x02, 0x19, 0x0A] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_30_01 = canmsg_create(rDiagReqID, 8, data=[0x30, 0x01, 0x00] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_31_01 = canmsg_create(rDiagReqID, 8, data=[0x31, 0x01, 0x00] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        # 从接收报文列表中获取首帧FF  -s
        payload_10 = None
        payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
        if payload_10 is not None:
            TestLog("PASS", "", "期望结果：收到首帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到首帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step2", "发送BS=1的流控帧")
        rt.clear()
        send_canmsg(can_channel, msg_30_01, rDiagReqID, dlc=msg_30_01.dlc)
        start_time = sl_time().timestamp()
        payload_first_cf = check_first_cf(rN_CrTimeout_ms, start_time, rt)
        cf_list = []
        if payload_first_cf is not None:
            cf_list.append(payload_first_cf)
            TestLog("PASS", "", "期望结果：连续帧第一帧响应.实际结果：连续帧第一帧响应")
        else:
            TestLog("FAIL", "", "期望结果：连续帧第一帧响应.实际结果：超时未收到连续帧第一帧响应")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step3", "发送流控制状态为Wait，BS=1的流控帧")
        send_canmsg(can_channel, msg_31_01, rDiagReqID, dlc=msg_31_01.dlc)
        sl_time().sleep(rN_CrTimeout_ms - 5)
        # 从接收报文列表中获取所有的连续帧CF  -s
        cf_list = []
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 2:
                cf_list.append(payload)
        # 此状态存在连续帧第一帧响应
        if len(cf_list) == 1 and cf_list[0][0] == 0x21:
            TestLog("PASS", "Step3", f"期望: 在{rN_CrTimeout_ms - 5}ms超时前无响应，实际: 未收到响应")
        else:
            TestLog("FAIL", "Step3", f"期望: 在{rN_CrTimeout_ms - 5}超时前无响应，实际: 非期望响应={cf_list}")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step4", "发送流控制状态为Wait，BS=1的流控帧")
        send_canmsg(can_channel, msg_31_01, rDiagReqID, dlc=msg_31_01.dlc)
        sl_time().sleep(rN_CrTimeout_ms - 5)

        # 从接收报文列表中获取所有的连续帧CF  -s
        cf_list = []
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 2:
                cf_list.append(payload)
        # 从接收报文列表中获取所有的连续帧CF  -e
        print(f"{ len(cf_list)= },{cf_list[0][0] = }")
        if len(cf_list) == 1 and cf_list[0][0] == 0x21:
            TestLog("PASS", "Step4", f"期望: 在{rN_CrTimeout_ms - 5}超时前无响应，实际: 未收到响应")
        else:
            TestLog("FAIL", "Step4", f"期望: 在{rN_CrTimeout_ms - 5}超时前无响应，实际: 非期望响应={cf_list}")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step5", "发送BS=1的流控帧")
        send_canmsg(can_channel, msg_30_01, rDiagReqID, dlc=msg_30_01.dlc)
        sl_time().sleep(rN_CrTimeout_ms)

        # 从接收报文列表中获取所有的连续帧CF  -s
        cf_list = []
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 2:
                cf_list.append(payload)
        # 从接收报文列表中获取所有的连续帧CF  -e
        TestLog("INFO", "", f"len(cf_list) = {len(cf_list)}")
        if not (len(cf_list) == 2 and cf_list[0][0] == 0x21 and cf_list[1][0] == 0x22):
            TestLog("FAIL", "", f"期望: 收到连续帧第二帧响应，实际: 非期望响应={cf_list}")
            check_msg_thread_stop(rt)
            return
        else:
            TestLog("PASS", "", f"期望: 收到连续帧第二帧响应，实际: 收到连续帧第二帧响应")

        TestLog("INFO", "Step6", "初始化变量aa=2")
        aa = 2
        while True:
            if aa > 0xFF:  # DL最大是-0xFF
                break
            TestLog("INFO", "Step7", "发送请求报文，请求多帧响应报文")
            # # 进入默认会话
            # msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5,
            #                                     fdf=P.TpInfo.CanFDMode)
            # send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
            # sl_time().sleep(rP2_Client_ms * 0.8)
            rt.clear()
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

            # 从接收报文列表中获取首帧FF  -s
            payload_10 = None
            payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
            if payload_10 is not None:
                TestLog("PASS", "", "期望结果：收到首帧(FF)。实际结果：收到首帧(FF)")
            else:
                TestLog("FAIL", "", "期望结果：收到首帧(FF)。实际结果：超时未收到首帧(FF)")
                check_msg_thread_stop(rt)
                return

            ff_dl = ((payload_10[0] & 0x0F) << 8) | payload_10[1]

            TestLog("INFO", "Step8", f"发送BS={aa}的流控帧")

            msg_30_01 = canmsg_create(rDiagReqID, 8, data=[0x30, aa, 0x00] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
            rt.clear()
            send_canmsg(can_channel, msg_30_01, rDiagReqID, dlc=msg_30_01.dlc)
            sl_time().sleep(rN_CrTimeout_ms * aa)

            # 从接收报文列表中获取所有的连续帧CF  -s
            cf_list = []
            recv_list = rt.get_recv_list()
            for i in range(len(recv_list)):
                payload = rt.get_recv_item_payload(i)
                if payload[0] >> 4 == 2:
                    cf_list.append(payload)
            # 从接收报文列表中获取所有的连续帧CF  -e

            if not (len(cf_list) == aa):
                TestLog("FAIL", "", f"期望: 收到连续帧{aa}帧响应，实际: 非期望响应={cf_list}")
                check_msg_thread_stop(rt)
                return
            else:
                TestLog("PASS", "", f"期望: 收到连续帧{aa}帧响应，实际: 收到连续帧{aa}帧响应")

            TestLog("INFO", "", f"len_cf_list = {len(cf_list)}")

            # sn_status = 1
            # for i in range(aa):
            #     expect = 0x21 + (i % 16)  # 0x21…0x2F 循环
            #     if i % 16 == 15:  # 每第 16 帧（0x2F 后）下一帧应是 0x20
            #         expect = 0x20
            #     sn_status &= (cf_list[i][0] == expect)

            # if not (len(cf_list) == aa and sn_status):
            #     TestLog("FAIL", "", f"期望: 收到连续帧{aa}帧响应，实际: 非期望响应={cf_list}")
            #     check_msg_thread_stop(rt)
            #     return
            # else:
            #     TestLog("PASS", "", f"期望: 收到连续帧{aa}帧响应，实际: 收到连续帧{aa}帧响应")

            TestLog("INFO", "Step9", f"令aa=aa+1, 若aa<=(FF_DL-6)/7+2，则跳到步骤7")
            # aa *= 2
            aa = aa +1
            if aa <= math.ceil((ff_dl - (P.TpInfo.MaxCanFDDataLength -2 )) / (P.TpInfo.MaxCanFDDataLength -1)):
                continue
            else:
                break

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC29_InvalidOverflowFC():
    """无效流控制状态"""
    case_name = "无效流控制状态"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        msg = canmsg_create(rDiagReqID, 8, data=[0x02, 0x19, 0x0A] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)

        msg_30 = canmsg_create(rDiagReqID, 8, data=[0x33, 0x00, 0x00] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)

        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
        # 从接收报文列表中获取首帧FF  -s
        payload_10 = None
        payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
        if payload_10 is not None:
            TestLog("PASS", "", "期望结果：收到首帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到首帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        N = 3
        TestLog("INFO", "Step2", f"发送流控状态为N={N}(!=0, 1, 2)的流控帧")
        send_canmsg(can_channel, msg_30, rDiagReqID, dlc=msg_30.dlc)
        sl_time().sleep(rN_CrTimeout_ms)

        # 从接收报文列表中获取所有的连续帧CF  -s
        cf_list = []
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 2:
                cf_list.append(payload)
        # 从接收报文列表中获取所有的连续帧CF  -e

        if len(cf_list) > 0:
            TestLog("FAIL", "", f"期望结果: ECU无响应，实际结果: 收到了ECU发送的连续帧")
            check_msg_thread_stop(rt)
            return
        else:
            TestLog("PASS", "", f"期望结果: ECU无响应，实际结果: 未收到ECU发送的连续帧")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC30_FlowStatusWait():
    """流控状态WAIT测试"""
    case_name = "流控状态WAIT测试"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rP2_Client_ms = P.TpInfo.P2_Client
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # step1: 发送SF请求(0x19 0x0A - 读取DTC)，期望收到FF响应
        sf_data = [0x02, 0x19, 0x0A] + [0xAA] * 5
        msg = canmsg_create(rDiagReqID, 8, data=sf_data, fdf=P.TpInfo.CanFDMode)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", "发送SF请求(19 0A)，期望收到FF响应")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

        # 等待P2_Client超时时间，检查是否收到FF
        payload_10 = None
        payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
        if payload_10 is not None:
            TestLog("PASS", "", "期望结果：收到首帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到首帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        # step2: 发送FC帧(FS=WAIT, 0x31)，期望DUT等待不发送CF
        fc_wait_data = [0x31, 0x00, 0x00] + [0xAA] * 5
        msg = canmsg_create(rDiagReqID, 8, data=fc_wait_data, fdf=P.TpInfo.CanFDMode)

        TestLog("INFO", "Step2", "发送FC帧(FS=WAIT)，期望DUT等待")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

        # 等待N_Cr超时时间，检查是否有响应（应该无响应）
        sl_time().sleep(rN_CrTimeout_ms)

        recv_list = rt.get_recv_list()
        if len(recv_list) == 0:
            TestLog("PASS", "Step2", "期望结果：DUT正确未发送CF。实际结果：DUT正确未发送CF")
        else:
            TestLog("FAIL", "Step2", f"期望结果：DUT正确未发送CF。实际结果：DUT发送CF "
                                     f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

        # step3: 等待额外时间
        TestLog("INFO","Step3",f"等待{rN_BsTimeout_ms * 1.1 - rN_CrTimeout_ms}ms")
        wait_time = (rN_BsTimeout_ms * 1.1 - rN_CrTimeout_ms)
        if wait_time > 0:
            sl_time().sleep(wait_time)

        # step4: 发送FC帧(FS=CTS, 0x30)，然后发送SF请求验证通信恢复
        fc_cts_data = [0x30, 0x00, 0x00] + [0xAA] * 5
        msg = canmsg_create(rDiagReqID, 8, data=fc_cts_data, fdf=P.TpInfo.CanFDMode)

        TestLog("INFO", "Step4", "发送FC帧(FS=CTS)")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

        sl_time().sleep(1)  # 等待1ms

        # 发送会话控制请求验证通信
        sf_session_data = [0x02, 0x10, 0x01] + [0xAA] * 5
        msg = canmsg_create(rDiagReqID, 8, data=sf_session_data, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

        default_session = None
        default_session = check_default_session(rP2_Client_ms,rt)
        if default_session is not None:
            TestLog("PASS", "Step1", "期望结果：收到会话控制响应50 01。期望结果：收到会话控制响应50 01")
        else:
            TestLog("FAIL", "Step1", "期望结果：收到会话控制响应50 01。期望结果：未收到会话控制响应")
            all_passed = False

        # step5: 发送请求报文，请求多帧响应报文
        TestLog("INFO", "Step5", "发送多帧请求(19 0A)，期望收到FF响应")
        sf_data_msg = canmsg_create(rDiagReqID, 8, data=[0x02, 0x19, 0x0A] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        rt.clear()
        send_canmsg(can_channel, sf_data_msg, rDiagReqID, dlc=8)
        payload_10 = None
        payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
        TestLog("INFO", "", f"payload_10 = {payload_10}")
        if payload_10 is not None:
            TestLog("PASS", "", "期望结果：收到首帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到首帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        # step6: 发送FC帧，期望DUT无响应
        fc_data = [0x31, 0x00, 0x14] + [0xAA] * 5
        msg = canmsg_create(rDiagReqID, 8, data=fc_data, fdf=P.TpInfo.CanFDMode)

        TestLog("INFO", "Step6", "发送FC帧(FS=WAIT)，期望DUT等待")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

        # 等待N_Cr超时时间，检查是否有响应（应该无响应）
        sl_time().sleep(rN_BsTimeout_ms - 5)

        recv_list = rt.get_recv_list()
        if len(recv_list) == 0:
            TestLog("PASS", "Step6", f"期望结果:在{rN_BsTimeout_ms - 5}前无响应。实际结果:在{rN_BsTimeout_ms - 5}前无响应。")
        else:
            TestLog("FAIL", "Step6", f"期望结果:在{rN_BsTimeout_ms - 5}前无响应。实际结果:在{rN_BsTimeout_ms - 5}前收到响应 "
                                     f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

        # Step7： 发送流控制状态为0的流控帧
        fc_wait_data = [0x30, 0x00, 0x00] + [0xAA] * 5
        msg = canmsg_create(rDiagReqID, 8, data=fc_wait_data, fdf=P.TpInfo.CanFDMode)

        TestLog("INFO", "Step7", "发送FC帧(FS=WAIT)，期望DUT接收到连续帧响应")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

        # 等待N_Cr超时时间，检查是否有响应（应该无响应）
        sl_time().sleep(rN_CrTimeout_ms)

        recv_list = rt.get_recv_list()
        if len(recv_list) > 0:
            TestLog("PASS", "Step7", "DUT正确等待，DUT接收到连续帧响应")
        else:
            TestLog("FAIL", "Step7", "DUT未接收到连续帧响应")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC31_IncorrectFCDLC():
    """流控帧CANDLC不正确测试"""
    case_name = "流控帧CANDLC不正确测试"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        rP2Timeout_ms = P.TpInfo.P2Timeout
        rN_CrTimeout_ms = getattr(P.TpInfo, "CanTp_Cr_ms", 150)
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        all_passed = True
        for dlc in range(1, 8):
            # step2: 发送SF请求(0x19 0x0A)，期望收到FF响应
            sf_data = [0x02, 0x19, 0x0A] + [0xAA] * 5
            msg = canmsg_create(rDiagReqID, 8, data=sf_data, fdf=P.TpInfo.CanFDMode)

            TestLog("INFO", f"Step1-DLC{dlc}", "发送SF请求(19 0A)，期望收到FF响应")
            rt.clear()
            send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

            # 等待P2_Client超时时间，检查是否收到FF
            payload_10 = None
            payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
            if payload_10 is not None:
                TestLog("PASS", "", "期望结果：收到首帧(FF)。实际结果：收到首帧(FF)")
            else:
                TestLog("FAIL", "", "期望结果：收到首帧(FF)。实际结果：超时未收到首帧(FF)")
                continue

            # step3: 发送FC帧但DLC不正确
            fc_data = [0x30, 0x00, 0x00] + [0xAA] * 5
            msg = canmsg_create(rDiagReqID, dlc=dlc, data=fc_data, fdf=P.TpInfo.CanFDMode)

            TestLog("INFO", f"Step3-DLC{dlc}", f"发送FC帧，CAN DLC={dlc}（不正确）")
            rt.clear()
            send_canmsg(can_channel, msg, rDiagReqID, dlc=dlc)

            # 等待N_Cr超时时间，检查是否有CF响应（应该无响应）
            sl_time().sleep(rN_CrTimeout_ms * 1.1)

            recv_list = rt.get_recv_list()
            if len(recv_list) != 0:
                all_passed = False
                TestLog("FAIL", "", f"DLC={dlc}: 期望结果：DUT在{rN_CrTimeout_ms * 1.1}ms超时前无响应.实际结果：DUT在{rN_CrTimeout_ms * 1.1}ms超时前响应 "
                                           f"{[[hex(i) for i in item['payload']] for item in recv_list]}")
            else:
                TestLog("PASS", "",
                        f"DLC={dlc}: 期望结果：DUT在{rN_CrTimeout_ms * 1.1}ms超时前无响应.实际结果：DUT在{rN_CrTimeout_ms * 1.1}ms超时前无响应 "
                        f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

            # step4: 发送会话控制请求重置状态
            sf_session_data = [0x02, 0x10, 0x01] + [0xAA] * 5
            msg = canmsg_create(rDiagReqID, 8, data=sf_session_data, fdf=P.TpInfo.CanFDMode)
            send_canmsg(can_channel, msg, rDiagReqID, dlc=8)
            default_session= None
            default_session = check_default_session(rP2_Client_ms,rt)
            if default_session is not None:
                TestLog("PASS", "Step3", "期望结果：收到会话控制响应50 01。期望结果：收到会话控制响应50 01")
            else:
                TestLog("FAIL", "Step3", "期望结果：收到会话控制响应50 01。期望结果：未收到会话控制响应")
                all_passed = False

        if all_passed:
            TestLog("PASS", "", "DUT正确地忽略了所有CAN DLC不正确的FC帧")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC32_FunctionalFC():
    """功能寻址流控帧"""
    case_name = "功能寻址流控帧"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rDiagFuncID = P.ECUInfo.DiagFuncID_int
        rP2_Client_ms = P.TpInfo.P2_Client
        rN_CrTimeout_ms = getattr(P.TpInfo, "CanTp_Cr_ms", 150)

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}, FuncID={hex(rDiagFuncID)}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # step1: 发送SF请求(0x19 0x0A)，期望收到FF响应
        sf_data = [0x02, 0x19, 0x0A] + [0xAA] * 5
        msg = canmsg_create(rDiagReqID, 8, data=sf_data, fdf=P.TpInfo.CanFDMode)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", "发送SF请求(19 0A)，期望收到FF响应")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

        # 等待P2_Client超时时间，检查是否收到FF
        payload_10 = None
        payload_10 = check_resp_FF_ok(rN_CrTimeout_ms, rt)
        if payload_10 is not None:
            TestLog("PASS", "", "期望结果：收到首帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到首帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        # step2: 使用功能寻址ID发送FC帧
        fc_data = [0x30, 0x00, 0x00] + [0xAA] * 5
        msg = canmsg_create(rDiagFuncID, 8, data=fc_data, fdf=P.TpInfo.CanFDMode)

        TestLog("INFO", "Step2", f"使用功能寻址ID(0x{rDiagFuncID:X})发送FC帧")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagFuncID, dlc=8)

        # 等待N_Cr超时时间，检查是否有CF响应（应该无响应，因为FC使用了功能寻址）
        sl_time().sleep(rN_CrTimeout_ms)

        recv_list = rt.get_recv_list()
        if len(recv_list) == 0:
            TestLog("PASS", "", f"期望结果：DUT在{rN_CrTimeout_ms}超时前无响应。实际结果：DUT在{rN_CrTimeout_ms}超时前无响应。")
        else:
            TestLog("FAIL", "", f"期望结果：DUT在{rN_CrTimeout_ms}超时前无响应。实际结果：DUT收到功能寻址的FC帧响应 "
                                       f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC33_IncorrectSFDL():
    """SF帧数据长度不正确测试"""
    case_name = "SF帧数据长度不正确测试"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rN_CrTimeout_ms = getattr(P.TpInfo, "CanTp_Cr_ms", 150)
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        all_passed = True
        if P.TpInfo.CanFDMode:
            for dlc in range(9, 16):
                for n in range(9, 0x38):
                    sf_data_1 = [0x00, n, 0x22, 0xF1, 0x8C] + [0xAA] * 3
                    msg = canmsg_create(rDiagReqID, dlc=dlc, data=sf_data_1, fdf=P.TpInfo.CanFDMode)

                    TestLog("INFO", "Step2", f"发送SF帧，DL={dlc}（无效值）")
                    rt.clear()
                    send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

                    # 等待N_Cr超时时间
                    sl_time().sleep(rN_CrTimeout_ms * 1.1)

                    # 检查DUT是否有响应（应忽略无效DL的SF）
                    recv_list = rt.get_recv_list()
                    if len(recv_list) != 0:
                        all_passed = False
                        TestLog("FAIL", "", f"DL={n}: 期望结果：DUT不应响应，实际结果：DUT不应响应，但收到: "
                                            f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

            if all_passed:
                TestLog("PASS", "", "DUT正确地忽略了所有DL值无效的SF帧")
        else:
            for n in range(8, 0x10):
                sf_data_1 = [n, 0x22, 0xF1, 0x8C] + (n-4) * [0xAA]
                msg = canmsg_create(rDiagReqID, dlc=8, data=sf_data_1, fdf=P.TpInfo.CanFDMode)

                TestLog("INFO", "Step2", f"发送SF帧，DL={8}（无效值）")
                rt.clear()
                send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

                # 等待N_Cr超时时间
                sl_time().sleep(rN_CrTimeout_ms * 1.1)

                # 检查DUT是否有响应（应忽略无效DL的SF）
                recv_list = rt.get_recv_list()
                if len(recv_list) != 0:
                    all_passed = False
                    TestLog("FAIL", "", f"DL={n}: 期望结果：DUT不应响应，实际结果：DUT不应响应，但收到: "
                                        f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

            if all_passed:
                TestLog("PASS", "", "DUT正确地忽略了所有DL值无效的SF帧")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC34_IncorrectCANDLCSF():
    """DLC不正确单帧"""
    case_name = "DLC不正确单帧"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rN_CrTimeout_ms = getattr(P.TpInfo, "CanTp_Cr_ms", 150)
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        # step2: 发送SF帧，SF_DL=3，但CAN DLC从1到7（都小于所需的4字节：PCI+3字节数据）
        # 对于SF_DL=3，需要的最小DLC是4（1字节PCI + 3字节数据）
        all_passed = True
        for dlc in range(1, 8):
            sf_data = [0x03, 0x22, 0xF1, 0x8C] + [0xAA] * 4
            msg = canmsg_create(rDiagReqID, dlc=dlc, data=sf_data, fdf=P.TpInfo.CanFDMode)

            TestLog("INFO", "Step2", f"发送SF帧(SF_DL=3)，CAN DLC={dlc}")
            rt.clear()
            send_canmsg(can_channel, msg, rDiagReqID, dlc=dlc)

            # 等待N_Cr超时时间

            sl_time().sleep(rN_CrTimeout_ms * 1.1)

            # 检查DUT是否有响应（DLC不正确时应忽略）
            recv_list = rt.get_recv_list()
            if len(recv_list) != 0:
                all_passed = False
                TestLog("FAIL", "", f"DLC={dlc}: 期望结果：DUT在{rN_CrTimeout_ms}超时前无响应。实际结果：DUT在{rN_CrTimeout_ms}超时前响应:  "
                                           f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

        if all_passed:
            TestLog("PASS", "", "DUT正确地忽略了所有CAN DLC不正确的SF帧")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC35_IncorrectFFDL():
    """不正确的FF数据长度"""
    case_name = "不正确的FF数据长度"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rN_BsTimeout_ms = getattr(P.TpInfo, "CanTp_Bs_ms", 150)
        # 获取DLC传输设置，默认为8
        # rDLC_Trans = getattr(P.TpInfo, "Cantp_dlc", 8)
        rDLC_Trans = P.TpInfo.MaxCanFDDataLength
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}, DLC_Trans={rDLC_Trans}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        # step2: 发送FF帧，DL值从1到(DLC_Trans-2)
        # 对于DLC=8，FF帧需要DL>=7才有意义（因为SF最多容纳7字节数据）
        all_passed = True
        for n in range(1, rDLC_Trans - 1):
            ff_data = [0x10, n, 0x22, 0xF1, 0x86] + [i - 4 for i in range(5, rDLC_Trans)]
            msg = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLengthToDLC, data=ff_data, fdf=P.TpInfo.CanFDMode)

            TestLog("INFO", "Step2", f"发送FF帧，DL={n}（不正确的值）")
            rt.clear()
            send_canmsg(can_channel, msg, rDiagReqID, dlc=rDLC_Trans)

            # 等待N_Bs超时时间

            sl_time().sleep(rN_BsTimeout_ms * 1.1)
            # 额外等待以确保稳定
            # sl_time().sleep(2000)

            # 检查DUT是否有响应（应忽略DL不正确的FF帧）
            recv_list = rt.get_recv_list()
            if len(recv_list) != 0:
                all_passed = False
                TestLog("FAIL", "", f"DL={n}: 期望结果：DUT在{rN_BsTimeout_ms * 1.1}ms超时前无响应。实际结果：DUT在{rN_BsTimeout_ms * 1.1}ms超时前响应 "
                                           f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

        if all_passed:
            TestLog("PASS", "", "DUT正确地忽略了所有DL值不正确的FF帧")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC36_IncorrectCANDLCFF():
    """DLC不正确首帧"""
    case_name = "DLC不正确首帧"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rN_BsTimeout_ms = getattr(P.TpInfo, "CanTp_Bs_ms", 150)
        # 获取DLC传输设置，默认为8
        rDLC_Trans = getattr(P.TpInfo, "Cantp_dlc", 8)
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        # 根据DLC_Trans确定最大测试范围
        if P.TpInfo.MaxCanFDDataLength == 64:
            n_max = 15
        else:
            n_max = 8

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}, DLC_Trans={rDLC_Trans}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        # step2: 发送FF帧(DL=7)，但CAN DLC从1到(n_max-1)（都小于所需值）
        all_passed = True
        for dlc in range(1, 8):
            ff_data = [0x10, 0x1C, 0x22] + [i - 2 for i in range(3, 8)]
            msg_1 = canmsg_create(rDiagReqID, dlc=dlc, data=ff_data, fdf=P.TpInfo.CanFDMode)

            TestLog("INFO", "Step2", f"发送FF帧(DL=7)，CAN DLC={dlc}")
            rt.clear()
            send_canmsg(can_channel, msg_1, rDiagReqID, dlc=dlc)

            # 等待N_Bs超时时间

            sl_time().sleep(rN_BsTimeout_ms * 1.1)
            # 额外等待以确保稳定
            # sl_time().sleep(2000)

            # 检查DUT是否有响应（DLC不正确时应忽略）
            recv_list = rt.get_recv_list()
            if len(recv_list) != 0:
                all_passed = False
                TestLog("FAIL", "", f"DLC={dlc}: 期望结果：DUT在{rN_BsTimeout_ms * 1.1}ms超时前无响应。实际结果：DUT在{rN_BsTimeout_ms * 1.1}ms超时前响应"
                                            f"{[[hex(i) for i in item['payload']] for item in recv_list]}")


        if all_passed:
            TestLog("PASS", "", "DUT正确地忽略了所有CAN DLC不正确的FF帧")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC37_IncorrectCANDLCCF():
    """DLC不正确连续帧"""
    case_name = "DLC不正确连续帧"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rP2_Client_ms = 150
        rN_CrTimeout_ms = getattr(P.TpInfo, "CanTp_Cr_ms", 150)
        # 获取DLC传输设置，默认为8
        rDLC_Trans = getattr(P.TpInfo, "Cantp_dlc", 8)
        if P.TpInfo.CanFDMode == 0:
            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x0D  # 总长度
        else:
            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x7D  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        all_passed = True
        if P.TpInfo.CanFDMode == 0:
            for dlc in range(1, P.TpInfo.MaxCanFDDataLengthToDLC):
                # step2: 发送FF帧，期望收到FC响应
                TestLog("INFO", "Step2", f"发送FF帧")
                rt.clear()
                status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                            dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)
                send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=P.TpInfo.MaxCanFDDataLengthToDLC)

                # 等待P2_Client超时时间，检查是否收到FC
                sl_time().sleep(rP2_Client_ms)

                recv_list = rt.get_recv_list()
                fc_received = False
                for item in recv_list:
                    payload = item.get("payload", [])
                    if payload and (payload[0] & 0xF0) == 0x30:
                        fc_received = True
                        break

                if not fc_received:
                    TestLog("FAIL", f"Step2-DLC{dlc}", "期望结果：收到流控帧(FC)。实际结果：未收到流控帧(FC)")
                    continue

                # step3: 发送CF帧，但CAN DLC不正确
                status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                            dlc=dlc, brs=P.TpInfo.CanFDMode)
                TestLog("INFO", "Step3", f"发送CF帧，CAN DLC={dlc}（不正确）")
                rt.clear()
                for msg in msg_list[1:]:
                    send_canmsg(can_channel, msg, rDiagReqID, dlc=dlc)

                # 等待N_Cr超时时间
                sl_time().sleep(rN_CrTimeout_ms * 1.1)

                # 检查DUT是否有响应（DLC不正确时应忽略CF帧）
                recv_list = rt.get_recv_list()
                if len(recv_list) != 0:
                    all_passed = False
                    TestLog("FAIL", "", f"CF DLC={dlc}: 期望结果：DUT在{rN_CrTimeout_ms * 1.1}ms超时前无响应。实际结果：DUT在{rN_CrTimeout_ms * 1.1}ms超时前响应"
                                            f"{[[hex(i) for i in item['payload']] for item in recv_list]}")
        if P.TpInfo.CanFDMode == 1:
            for dlc in range(9, P.TpInfo.MaxCanFDDataLengthToDLC):
                # step2: 发送FF帧，期望收到FC响应
                TestLog("INFO", "Step2", f"发送FF帧")
                rt.clear()
                status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                            dlc=dlc, brs=P.TpInfo.CanFDMode)
                send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=dlc)

                # 等待P2_Client超时时间，检查是否收到FC
                sl_time().sleep(rP2_Client_ms)

                recv_list = rt.get_recv_list()
                fc_received = False
                for item in recv_list:
                    payload = item.get("payload", [])
                    if payload and (payload[0] & 0xF0) == 0x30:
                        fc_received = True
                        break

                if not fc_received:
                    TestLog("FAIL", f"Step2-DLC{dlc}", "期望结果：收到流控帧(FC)。实际结果：未收到流控帧(FC)")
                    continue

                # step3: 发送CF帧，但CAN DLC不正确
                TestLog("INFO", "Step3", f"发送CF帧，CAN DLC={dlc}（不正确）")
                rt.clear()
                for msg in [msg_list[1]]:
                    send_canmsg(can_channel, msg, rDiagReqID, dlc=dlc)

                # 等待N_Cr超时时间
                sl_time().sleep(rN_CrTimeout_ms * 1.1)

                # 检查DUT是否有响应（DLC不正确时应忽略CF帧）
                recv_list = rt.get_recv_list()
                if len(recv_list) != 0:
                    all_passed = False
                    TestLog("FAIL", "", f"CF DLC={dlc}: 期望结果：DUT在{rN_CrTimeout_ms * 1.1}ms超时前无响应。实际结果：DUT在{rN_CrTimeout_ms * 1.1}ms超时前响应"
                                            f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

        if all_passed:
            TestLog("PASS", "", "DUT正确地忽略了所有CAN DLC不正确的CF帧")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC38_UnknownFrame():
    """未知帧类型测试"""
    case_name = "未知帧类型测试"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rP2_Client_ms = P.TpInfo.P2_Client  # P2_Client超时时间

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        # step1: 发送未知帧类型（PCI=0x40，未定义的帧类型）
        # PCI的高4位为帧类型：0=SF, 1=FF, 2=CF, 3=FC，4及以上为未知类型
        unknown_frame_data = [0x40, 0x10, 0x01] + [0xAA] * 5
        msg = canmsg_create(rDiagReqID, 8, data=unknown_frame_data, fdf=P.TpInfo.CanFDMode)

        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", "发送未知帧类型（PCI=0x40）")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        # 等待P2_Client超时时间
        sl_time().sleep(rP2_Client_ms * 1.1)

        # 检查DUT是否有响应
        recv_list = rt.get_recv_list()
        if len(recv_list) == 0:
            TestLog("PASS", "", "期望结果：DUT正确地忽略了未知帧类型，无响应。期望结果：DUT正确地忽略了未知帧类型，无响应")
        else:
            TestLog("FAIL", "", f"期望结果：DUT正确地忽略了未知帧类型，无响应。期望结果：DUT收到了响应: "
                                       f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC39_FunctionalFF():
    """功能寻址首帧测试"""
    case_name = "功能寻址首帧测试"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rDiagFuncID = P.ECUInfo.DiagFuncID_int  # 功能寻址ID
        rN_BsTimeout_ms = getattr(P.TpInfo, "CanTp_Bs_ms", 150)
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        if P.TpInfo.CanFDMode == 0:

            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x1C  # 总长度
        else:

            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0xFC  # 总长度


        TestLog("-->", "", f"{rVnormal=}, {rTstable=}, FuncID={hex(rDiagFuncID)}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        # step1: 使用功能寻址ID发送首帧(FF)
        # 首帧格式: [PCI_H, PCI_L, SID, ...]，PCI = 0x10 | (DL >> 8)

        check_msg_thread_start(rt, rDiagFuncID, rDiagRespID)
        sl_time().sleep(5)
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", f"使用功能寻址ID(0x{rDiagFuncID:X})发送首帧(FF)")
        rt.clear()
        status, msg_list = create_ff_cfs(rDiagFuncID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_list[0], rDiagFuncID, dlc=msg_list[0].dlc)

        # 等待N_Bs超时时间
        sl_time().sleep(rN_BsTimeout_ms * 1.1)

        # 检查DUT是否有响应（功能寻址的FF应被忽略，不应有流控帧响应）
        recv_list = rt.get_recv_list()
        if len(recv_list) == 0:
            TestLog("PASS", "", "期望结果：DUT正确地忽略了功能寻址的首帧，无响应。期望结果：DUT正确地忽略了功能寻址的首帧，无响应")
        else:
            TestLog("FAIL", "", f"期望结果：DUT正确地忽略了功能寻址的首帧，无响应。期望结果：DUT对功能寻址的首帧响应"
                                       f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC40_SingleFF():
    """单独首帧测试"""
    case_name = "单独首帧测试"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rN_BsTimeout_ms = getattr(P.TpInfo, "CanTp_Bs_ms", 150)
        rP2Timeout_ms = P.TpInfo.P2Timeout  # P2超时时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        if P.TpInfo.CanFDMode == 0:

            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x1C  # 总长度
        else:

            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0xFC  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()


        # step1: 发送首帧(FF)
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", "发送首帧(FF)，期望DUT响应流控帧(FC)")
        rt.clear()
        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)

        # 等待N_Bs超时时间，检查是否收到流控帧
        sl_time().sleep(rN_BsTimeout_ms)

        # 检查是否收到流控帧(FC)
        fc_received = False
        recv_list = rt.get_recv_list()
        for item in recv_list:
            payload = item.get("payload", [])
            if payload and (payload[0] & 0xF0) == 0x30:  # FC帧的PCI高4位为3
                fc_received = True
                TestLog("PASS", "Step1", f"期望结果：收到流控帧(FC)。实际结果：收到流控帧(FC): {[hex(b) for b in payload]}")
                break

        if not fc_received:
            TestLog("FAIL", "Step1", "期望结果：收到流控帧(FC)。实际结果：未收到流控帧(FC)")
            check_msg_thread_stop(rt)
            return

        # step2: 不发送连续帧，等待并检查DUT是否有其他响应
        TestLog("INFO", "Step2", "不发送连续帧，等待P2超时")
        sl_time().sleep(1)  # 等待1ms
        rt.clear()  # 清除之前的接收记录

        # 等待P2超时时间
        sl_time().sleep(rP2Timeout_ms)

        # 检查DUT是否有额外响应（不应有）
        recv_list = rt.get_recv_list()
        if len(recv_list) == 0:
            TestLog("PASS", "", f"期望结果：DUT在{rP2Timeout_ms}ms超时前无响应。实际结果：DUT在{rP2Timeout_ms}ms超时前无响应")
        else:
            TestLog("FAIL", "", f"期望结果：DUT在{rP2Timeout_ms}ms超时前无响应。实际结果：DUT在{rP2Timeout_ms}ms超时前无响应"
                                       f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC41_UnexpectedCF():
    """意外连续帧测试"""
    case_name = "意外连续帧测试"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rP2Timeout_ms = P.TpInfo.P2Timeout  # P2超时时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        # step1: 直接发送连续帧(CF)，不先发送首帧
        # 连续帧格式: [PCI, data...]，PCI = 0x20 + SN（SN为0-15的随机值）
        sn = random.randint(0, 0x0F)  # 序列号0-15
        cf_data = [0x2E + sn] + [i + 5 for i in range(1, P.TpInfo.MaxCanFDDataLength)]
        msg = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLengthToDLC, data=cf_data, fdf=P.TpInfo.CanFDMode)

        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", f"直接发送意外的连续帧(CF)，SN={sn}")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        # 等待P2超时时间
        sl_time().sleep(rP2Timeout_ms * 1.1)

        # 检查DUT是否有响应（应忽略意外的CF）
        recv_list = rt.get_recv_list()
        if len(recv_list) == 0:
            TestLog("PASS", "", f"期望结果：DUT在{rP2Timeout_ms}ms超时前无响应。实际结果：DUT在{rP2Timeout_ms}ms超时前无响应")
        else:
            TestLog("FAIL", "", f"期望结果：DUT在{rP2Timeout_ms}ms超时前无响应。实际结果：DUT在{rP2Timeout_ms}ms超时前响应 "
                                       f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC42_UnexpectedFC():
    """意外流控帧测试"""
    case_name = "意外流控帧测试"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rN_CrTimeout_ms = getattr(P.TpInfo, "CanTp_Cr_ms", 150)
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        # step1: 直接发送流控帧(FC)，不先发送首帧
        # 流控帧格式: [PCI, BS, STmin, padding...]，PCI = 0x30 + FS（FS为流状态0-2）
        fs = random.randint(0, 2)  # 流状态: 0=CTS, 1=WAIT, 2=OVFLW
        fc_data = [0x32 + fs, 0x00, 0x00] + [0xAA] * 5
        msg = canmsg_create(rDiagReqID, 8, data=fc_data, fdf=P.TpInfo.CanFDMode)

        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", f"直接发送意外的流控帧(FC)，FS={fs}")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        # 等待N_Cr超时时间
        sl_time().sleep(rN_CrTimeout_ms * 1.1)

        # 检查DUT是否有响应（应忽略意外的FC）
        recv_list = rt.get_recv_list()
        if len(recv_list) == 0:
            TestLog("PASS", "", f"期望结果：DUT在{rN_CrTimeout_ms}ms超时前无响应。实际结果：DUT在{rN_CrTimeout_ms}ms超时前无响应")
        else:
            TestLog("FAIL", "", f"期望结果：DUT在{rN_CrTimeout_ms}ms超时前无响应。实际结果：DUT在{rN_CrTimeout_ms}ms超时前响应"
                                       f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC43_Service3E():
    """3E服务"""
    case_name = "3E服务"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rDiagFuncID = P.ECUInfo.DiagFuncID_int
        rP2_Client_ms = P.TpInfo.P2_Client
        rP2Timeout_ms = getattr(P.TpInfo, "CanTp_P2_ms", 150)
        rSTmin_ms = getattr(P.TpInfo, "CanTp_STmin_ms", 10)
        if P.TpInfo.CanFDMode == 0:
            rDLC_Trans = 8
            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x0E  # 总长度
            did_data_len_1 = 0x0D
            did_data_len_2 = 0x1C
        else:
            rDLC_Trans = 15
            sid = 0x22  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x7E  # 总长度
            did_data_len_1 = 0x7D
            did_data_len_2 = 0xFC

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        all_passed = True

        # Step1: 发送会话控制请求(10 01)
        sf_session_data = [0x02, 0x10, 0x01] + [0xAA] * 5
        msg = canmsg_create(rDiagReqID, 8, data=sf_session_data, fdf=P.TpInfo.CanFDMode)

        TestLog("INFO", "Step1", "发送会话控制请求(10 01)")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

        sl_time().sleep(rP2Timeout_ms)

        recv_list = rt.get_recv_list()
        if len(recv_list) > 0:
            TestLog("PASS", "Step1", "期望结果：收到会话控制响应50 01。期望结果：收到会话控制响应50 01")
        else:
            TestLog("FAIL", "Step1", "期望结果：收到会话控制响应50 01。期望结果：未收到会话控制响应")
            all_passed = False

        # Step2: 发送FF帧(DL=0x0E)，期望收到FC
        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)

        TestLog("INFO", "Step2", f"发送FF帧")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        start_time = sl_time().timestamp()
        payload_30 = check_resp_FC_ok(rP2_Client_ms, start_time, rt)
        TestLog("INFO", "", f"payload_30 = {payload_30}")
        if payload_30 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FC)。实际结果：收到流控帧(FC)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FC)。实际结果：超时未收到流控帧(FC)")
            check_msg_thread_stop(rt)
            return

        # sl_time().sleep(rP2Timeout_ms)
        #
        # recv_list = rt.get_recv_list()
        # fc_received = False
        # for item in recv_list:
        #     payload = item.get("payload", [])
        #     if payload and (payload[0] & 0xF0) == 0x30:
        #         fc_received = True
        #         break
        #
        # if fc_received:
        #     TestLog("PASS", "Step2", "收到FC流控帧")
        # else:
        #     TestLog("FAIL", "Step2", "未收到FC流控帧")
        #     all_passed = False

        # Step3: 发送CF(0x21) + 3E 80(功能寻址)

        TestLog("INFO", "Step3", "发送CF(0x21)后紧接着发送3E 80(功能寻址)")
        rt.clear()
        send_canmsg(can_channel, msg_list[1], rDiagReqID, dlc=msg_list[1].dlc)
        tp_3e_data = [0x02, 0x3E, 0x80] + [0xAA] * 5
        msg_3e = canmsg_create(rDiagFuncID, 8, data= tp_3e_data, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_3e, rDiagFuncID, dlc=msg_3e.dlc)
        print(f"{sl_time().timestamp() = }")
        

        # Step4: 发送CF(0x22)，期望无响应

        TestLog("INFO", "Step4", "发送CF(0x22)，期望无响应")
        rt.clear()
        send_canmsg(can_channel, msg_list[2], rDiagReqID, dlc=msg_list[2].dlc)
        sl_time().sleep(rP2Timeout_ms)

        recv_list = rt.get_recv_list()
        if len(recv_list) == 0:
            TestLog("PASS", "Step4", f"期望结果：DUT在{rP2Timeout_ms}ms超时前无响应.期望结果：DUT在{rP2Timeout_ms}ms超时前无响应")
        else:
            TestLog("FAIL", "Step4", f"D期望结果：DUT在{rP2Timeout_ms}ms超时前无响应.期望结果：DUT在{rP2Timeout_ms}ms超时前响应 "
                                     f"{[[hex(i) for i in item['payload']] for item in recv_list]}")
            all_passed = False

        # Step5: 进入扩展会话(10 03)
        sf_ext_session_data = [0x02, 0x10, 0x03] + [0xAA] * 5
        msg = canmsg_create(rDiagReqID, 8, data=sf_ext_session_data, fdf=P.TpInfo.CanFDMode)

        TestLog("INFO", "Step5", "进入扩展会话(10 03)")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

        sl_time().sleep(rP2Timeout_ms)

        recv_list = rt.get_recv_list()
        extend_session = False
        for item in recv_list:
            payload = item.get("payload", [])
            if payload[1] == 0x50 and payload[2] == 0x03:
                extend_session = True
                break

        if extend_session is True:
            TestLog("PASS", "Step1", "期望结果：收到会话控制响应50 03。期望结果：收到会话控制响应50 03")
        else:
            TestLog("FAIL", "Step1", "期望结果：收到会话控制响应50 03。期望结果：未收到会话控制响应")
            all_passed = False

        # Step6: 发送FF帧，期望收到FC
        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len_2, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)

        TestLog("INFO", "Step6", f"发送FF帧)")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)

        sl_time().sleep(rP2Timeout_ms)

        recv_list = rt.get_recv_list()
        fc_received = False
        for item in recv_list:
            payload = item.get("payload", [])
            if payload and payload[0] == 0x30:
                fc_received = True
                break

        if fc_received:
            TestLog("PASS", "Step6", "期望结果：收到流控帧(FC)。实际结果：收到FC流控帧")
        else:
            TestLog("FAIL", "Step6", "期望结果：收到流控帧(FC)。实际结果：未收到FC流控帧")
            all_passed = False

        # Step7: 循环发送CF + 3E 80，期望最终收到NRC=0x13
        TestLog("INFO", "Step7", "发送多个CF，每个CF后插入3E 80(功能寻址)")
        for msg in msg_list[1:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            send_canmsg(can_channel, msg_3e, rDiagFuncID, dlc=msg_3e.dlc)

        # rt.clear()
        #
        # if rDLC_Trans == 8:
        #     # CAN 2.0: 发送4个CF (0x21-0x22)
        #     for j in range(1, 5):
        #         cf_data = [0x20 + j] + [i + 5 for i in range(1, 8)]
        #         msg_cf = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLength, data=cf_data, fdf=P.TpInfo.CanFDMode)
        #         send_canmsg(can_channel, msg_cf, rDiagReqID, dlc=8)
        #
        #         msg_3e = canmsg_create(rDiagFuncID, 8, data=tp_3e_data, fdf=P.TpInfo.CanFDMode)
        #         send_canmsg(can_channel, msg_3e, rDiagFuncID, dlc=8)
        #
        #         if j != 4:
        #             sl_time().sleep(rSTmin_ms)
        #             # 最后一个CF
        # else:
        #     # CAN FD: 发送3个CF + 最后一个短CF
        #     for j in range(1, 4):
        #         cf_data = [0x20 + j] + [i + 0x3E for i in range(1, 64)]
        #         msg_cf = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLengthToDLC, data=cf_data, fdf=P.TpInfo.CanFDMode)
        #         send_canmsg(can_channel, msg_cf, rDiagReqID, dlc=rDLC_Trans)
        #
        #         msg_3e = canmsg_create(rDiagFuncID, 8, data=tp_3e_data, fdf=P.TpInfo.CanFDMode)
        #         send_canmsg(can_channel, msg_3e, rDiagFuncID, dlc=8)
        #         sl_time().sleep(rSTmin_ms)
        #
        #     # 最后一个CF
        #     cf_last_data = [0x24, 0xFB] + [0xAA] * 6
        #     msg_cf = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLengthToDLC, data=cf_last_data, fdf=P.TpInfo.CanFDMode)
        #     send_canmsg(can_channel, msg_cf, rDiagReqID, dlc=8)
        #
        #     msg_3e = canmsg_create(rDiagFuncID, 8, data=tp_3e_data, fdf=P.TpInfo.CanFDMode)
        #     send_canmsg(can_channel, msg_3e, rDiagFuncID, dlc=8)

        sl_time().sleep(rP2_Client_ms)

        # 检查是否收到NRC=0x13
        recv_list = rt.get_recv_list()
        nrc13_received = False
        for item in recv_list:
            payload = item.get("payload", [])
            if payload and len(payload) >= 4:
                if payload[1] == 0x7F and payload[2] == 0x22 and payload[3] == 0x13:
                    nrc13_received = True
                    break

        if nrc13_received:
            TestLog("PASS", "Step7", "期望结果：收到NRC=0x13(incorrectMessageLengthOrInvalidFormat)。实际结果：收到NRC=0x13(incorrectMessageLengthOrInvalidFormat)")
        else:
            TestLog("FAIL", "Step7", "期望结果：收到NRC=0x13(incorrectMessageLengthOrInvalidFormat)。实际结果：未收到预期的NRC=0x13")
            all_passed = False

        # Step8: 先发3E 80，再发SF(0x01 0x22)
        TestLog("INFO", "Step8", "先发送3E 80(功能寻址)，再发送SF(0x01 0x22)")
        rt.clear()

        msg_3e = canmsg_create(rDiagFuncID, 8, data=tp_3e_data, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_3e, rDiagFuncID, dlc=8)

        sf_22_data = [0x01, 0x22] + [i - 2 for i in range(2, 8)]
        msg_sf = canmsg_create(rDiagReqID, 8, data=sf_22_data, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_sf, rDiagReqID, dlc=8)

        sl_time().sleep(rP2_Client_ms)

        recv_list = rt.get_recv_list()
        nrc13_received = False
        for item in recv_list:
            payload = item.get("payload", [])
            if payload and len(payload) >= 4:
                if payload[1] == 0x7F and payload[2] == 0x22 and payload[3] == 0x13:
                    nrc13_received = True
                    break

        if nrc13_received:
            TestLog("PASS", "Step8", "期望结果：收到NRC=0x13.实际结果：收到NRC=0x13")
        else:
            TestLog("FAIL", "Step8", "期望结果：收到NRC=0x13.实际结果：未收到预期的NRC=0x13")
            all_passed = False

        # Step9: 先发SF(0x01 0x22)，再发3E 80
        TestLog("INFO", "Step9", "先发送SF(0x01 0x22)，再发送3E 80(功能寻址)")
        rt.clear()

        msg_sf = canmsg_create(rDiagReqID, 8, data=sf_22_data, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_sf, rDiagReqID, dlc=8)

        msg_3e = canmsg_create(rDiagFuncID, 8, data=tp_3e_data, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_3e, rDiagFuncID, dlc=8)

        sl_time().sleep(rP2_Client_ms)

        recv_list = rt.get_recv_list()
        nrc13_received = False
        for item in recv_list:
            payload = item.get("payload", [])
            if payload and len(payload) >= 4:
                if payload[1] == 0x7F and payload[2] == 0x22 and payload[3] == 0x13:
                    nrc13_received = True
                    break

        if nrc13_received:
            TestLog("PASS", "Step9", "期望结果：收到NRC=0x13.实际结果：收到NRC=0x13")
        else:
            TestLog("FAIL", "Step9", "期望结果：收到NRC=0x13.实际结果：未收到预期的NRC=0x13")
            all_passed = False

        # Step10: 发送FF(0x19多帧) + 3E 80，期望收到FC

        status, msg_list = create_ff_cfs(rDiagReqID, 0x19, did, did_data_len_1, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)


        TestLog("INFO", "Step10", "发送FF(0x19多帧) + 3E 80(功能寻址)")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)

        msg_3e = canmsg_create(rDiagFuncID, 8, data=tp_3e_data, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_3e, rDiagFuncID, dlc=8)

        start_time = sl_time().timestamp()
        payload_30 = check_resp_FC_ok(rP2_Client_ms, start_time, rt)
        TestLog("INFO", "", f"payload_30 = {payload_30}")
        if payload_30 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FC)。实际结果：收到流控帧(FC)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FC)。实际结果：超时未收到流控帧(FC)")
            all_passed = False
            check_msg_thread_stop(rt)
            return

        # if fc_received:
        #     TestLog("PASS", "Step10", "期望结果：收到流控帧(FC)。实际结果：收到FC流控帧")
        # else:
        #     TestLog("FAIL", "Step10", "期望结果：收到流控帧(FC)。实际结果：未收到FC流控帧")
        #     all_passed = False

        # Step11: 发送CF(0x21)，期望收到NRC=0x13
        for msg in msg_list[1:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        sl_time().sleep(rP2_Client_ms)

        recv_list = rt.get_recv_list()
        nrc13_received = False
        for item in recv_list:
            payload = item.get("payload", [])
            if payload and len(payload) >= 4:
                if payload[1] == 0x7F and payload[2] == 0x19 and payload[3] == 0x13:
                    nrc13_received = True
                    break

        if nrc13_received:
            TestLog("PASS", "Step11", "期望结果：收到NRC=0x13.实际结果：收到0x19的NRC=0x13")
        else:
            TestLog("FAIL", "Step11", "期望结果：收到NRC=0x13.实际结果：未收到预期的0x19的NRC=0x13")
            all_passed = False

        if all_passed:
            TestLog("PASS", "", "所有步骤测试通过")
        else:
            TestLog("FAIL", "", "部分步骤测试失败")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC44_Framepadding():
    """报文填充"""
    case_name = "报文填充"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rP2_Client_ms = P.TpInfo.P2_Client
        rN_CrTimeout_ms = getattr(P.TpInfo, "CanTp_Cr_ms", 150)
        pad_byte = getattr(P.TpInfo, "Can_Padding_Byte", 0xAA) & 0xFF
        rDLC_Trans = getattr(P.TpInfo, "Cantp_dlc", 8)
        rDLC_Receive = getattr(P.TpInfo, "Cantp_dlc_receive", 8)
        if P.TpInfo.CanFDMode == 0:

            sid = 0x33 # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x0D  # 总长度
        else:

            sid = 0x33  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x7D  # 总长度

        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}, pad_byte=0x{pad_byte:02X}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        all_passed = True

        # Step1: 发送FF帧(SID=0x33)，期望收到FC，检查填充字节
        TestLog("INFO", "Step1", f"发送FF帧(SID=0x33，期望收到FC")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)

        sl_time().sleep(rP2_Client_ms)

        recv_list = rt.get_recv_list()
        fc_received = False
        fc_padding_ok = True
        for item in recv_list:
            payload = item.get("payload", [])
            if payload and (payload[0] & 0xF0) == 0x30:
                fc_received = True
                # 检查FC帧的填充字节(从byte3开始)
                if len(payload) >= 8:
                    for i in range(3, 8):
                        if payload[i] != pad_byte:
                            fc_padding_ok = False
                            break
                break

        if fc_received:
            if fc_padding_ok:
                TestLog("PASS", "Step1", f"期望结果：收到流控帧(FC)。实际结果：收到FC，填充字节正确(0x{pad_byte:02X})")
            else:
                TestLog("FAIL", "Step1", f"期望结果：收到流控帧(FC)。实际结果：FC填充字节不正确，应为0x{pad_byte:02X}")
                all_passed = False
        else:
            TestLog("FAIL", "Step1", "期望结果：收到流控帧(FC)。实际结果：未收到FC流控帧")
            all_passed = False

        # Step2: 发送CF(0x21)，期望收到NRC=0x11，检查填充字节
        TestLog("INFO", "Step2", "发送CF(0x21)，期望收到NRC=0x11(serviceNotSupported)")
        rt.clear()
        for msg in msg_list[1:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=rDLC_Trans)

        sl_time().sleep(rP2_Client_ms)

        recv_list = rt.get_recv_list()
        nrc11_received = False
        nrc_padding_ok = True
        for item in recv_list:
            payload = item.get("payload", [])
            if payload and len(payload) >= 4:
                if payload[1] == 0x7F and payload[2] == 0x33 and payload[3] == 0x11:
                    nrc11_received = True
                    # 检查NRC响应的填充字节(从byte4开始)
                    if len(payload) >= 8:
                        for i in range(4, 8):
                            if payload[i] != pad_byte:
                                nrc_padding_ok = False
                                break
                    break

        if nrc11_received:
            if nrc_padding_ok:
                TestLog("PASS", "Step2", f"期望结果：收到NRC=0x11.实际结果：收到NRC=0x11，填充字节正确(0x{pad_byte:02X})")
            else:
                TestLog("FAIL", "Step2", f"期望结果：收到NRC=0x11.实际结果：NRC响应填充字节不正确，应为0x{pad_byte:02X}")
                all_passed = False
        else:
            TestLog("FAIL", "Step2", "期望结果：收到NRC=0x11.实际结果：未收到预期的NRC=0x11")
            all_passed = False

        # Step3: 发送SF请求(0x19 0x0A)读取DTC，期望收到FF
        sf_data = [0x02, 0x19, 0x0A] + [0xAA] * 5
        msg = canmsg_create(rDiagReqID, 8, data=sf_data, fdf=P.TpInfo.CanFDMode)

        TestLog("INFO", "Step3", "发送SF请求(19 0A)读取DTC，期望收到FF")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

        sl_time().sleep(rP2_Client_ms)

        recv_list = rt.get_recv_list()
        ff_payload = None
        ff_payload = check_resp_FF_ok(rN_CrTimeout_ms, rt)
        if ff_payload is not None:
            TestLog("PASS", "", "期望结果：收到首帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到首帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return
        
        total_len = ((ff_payload[0] & 0x0F) << 8) + ff_payload[1]
        TestLog("INFO", "Step3", f"收到FF，总长度={total_len}")

        # Step4: 发送FC，接收所有CF，检查最后一帧的填充字节
        fc_data = [0x30] + [0x00] * 2 + [0xAA] * 5
        msg = canmsg_create(rDiagReqID, 8, data=fc_data, fdf=P.TpInfo.CanFDMode)

        TestLog("INFO", "Step4", "发送FC，接收所有CF并检查填充字节")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

        # 等待足够时间接收所有CF
        sl_time().sleep(rP2_Client_ms * 3)

        recv_list = rt.get_recv_list()
        cf_payloads = []
        for item in recv_list:
            payload = item.get("payload", [])
            if payload and (payload[0] & 0xF0) == 0x20:
                cf_payloads.append(payload)

        if not cf_payloads:
            TestLog("FAIL", "Step4", "期望结果：DUT发送连续帧检查报文填充及DLC是否符合要求(最后一帧使用AA填充).实际结果：未收到任何CF")
            all_passed = False
        else:
            # 计算最后一帧真实数据长度
            remaining = total_len - (P.TpInfo.MaxCanFDDataLength -2) - (len(cf_payloads) - 1) * (P.TpInfo.MaxCanFDDataLength - 1)

            for idx, cf in enumerate(cf_payloads, 1):
                data_bytes = cf[1:]          # 去掉 PCI
                is_last    = (idx == len(cf_payloads))
                if is_last:
                    # 2. 最后一帧填充
                    pad_cnt = (P.TpInfo.MaxCanFDDataLength - 1) - remaining
                    padding = data_bytes[-pad_cnt:] if pad_cnt else b''
                    if padding and any(b != 0xAA for b in padding):
                        TestLog("FAIL", "Step4",
                                f"最后一帧填充错误：最后{pad_cnt}字节应全为0xAA，实际{[hex(b) for b in padding]}")
                        all_passed = False
                    else:
                        TestLog("PASS", "Step4",
                                f"最后一帧填充正确（最后{pad_cnt}字节为0xAA）")
                        
        # messages = ctx.can.messages
        # for m in messages:
        #     if m.id == P.ECUInfo.DiagRespID_int and m.dlc != P.TpInfo.MaxCanFDDataLengthToDLC :
        #         print(f"{m.id = },{P.ECUInfo.DiagRespID_int = },{m.dlc = },{P.TpInfo.MaxCanFDDataLengthToDLC = }")
        #         all_passed = False
            
        
        if all_passed:
            TestLog("PASS", "", "TODO DLC判断所有 CF 的 DLC 与填充检查通过")
        else:
            TestLog("FAIL", "", "TODO DLC判断部分 CF 的 DLC 或填充检查失败")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG1_TC45_WrongPhyAddressID():
    """错误的物理寻址ID测试"""
    case_name = "错误的物理寻址ID测试"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rP2_Client_ms = P.TpInfo.P2_Client
        rN_BsTimeout_ms = getattr(P.TpInfo, "CanTp_Bs_ms", 150)

        rWrongPhyReqID = rDiagReqID + 1

        TestLog("INFO", "", f"{rVnormal=}, {rTstable=}, 正确物理寻址ID=0x{rDiagReqID:X}, 错误物理寻址ID=0x{rWrongPhyReqID:X}")

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        check_msg_thread_start(rt, rWrongPhyReqID, rDiagRespID)
        sl_time().sleep(5)

        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", f"使用错误的物理寻址ID(0x{rWrongPhyReqID:X})发送请求报文(02 19 0A)，期望无响应")
        sf_data = [0x02, 0x19, 0x0A] + [0xAA] * 5
        msg = canmsg_create(rWrongPhyReqID, 8, data=sf_data, fdf=P.TpInfo.CanFDMode)

        rt.clear()
        send_canmsg(can_channel, msg, rWrongPhyReqID, dlc=8)

        sl_time().sleep(rN_BsTimeout_ms + rP2_Client_ms)

        recv_list = rt.get_recv_list()
        if len(recv_list) == 0:
            TestLog("PASS", "Step1", "期望结果：无响应。实际结果：DUT正确忽略了错误物理寻址ID的请求，无响应")
        else:
            TestLog("FAIL", "Step1", f"期望结果：无响应。实际结果：DUT不应对错误物理寻址ID的请求响应，但收到了响应: "
                                     f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC1_TimeoutCheck_N_AS():
    """N_As超时值检查"""
    case_name = "N_As超时值检查"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_AsTimeout_ms = P.TpInfo.N_AsTimeout  # N_As最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        read_DID = P.TpInfo.DID
        read_DID = list(divmod(read_DID, 256))


        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        # 优先构造流控帧报文
        msg_30 = canmsg_create(rDiagReqID, 8, data=[0x30] + [0x00] * 2 + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)

        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应。"
                                 "在请求之后，立即发送使总线负载达到100%的高优先级帧。"
                                 "这些高优先级帧不是ECU配置为接收的诊断帧或应用信号帧。")

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8,data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8,data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8,data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8,data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        msg = canmsg_create(rDiagReqID, 8, data=[0x03, 0x22] + read_DID + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        # 发送高优先级can报文
        timer_id_start, timer_id_end = emit_can_busload_high(can_channel)
        while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) < 90:
            sl_time().sleep(10)
        # TestLog("INFO", "等待10s", "确保总线负载达到100%")
        # sl_time().sleep(10000)
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        TestLog("INFO", "Step2", f"等待允许的最大{rN_AsTimeout_ms}超时(+10%)")
        sl_time().sleep((rN_AsTimeout_ms * 1.1))

        # 发送的请求报文时间
        send_timestamp = 0
        send_list = rt.get_send_list()
        for i in range(len(send_list)):
            payload = rt.get_send_item_payload(i)
            if payload[:3] == [0x02, 0x19, 0x0A]:
                send_timestamp = rt.get_send_item_timestamp(i)
                break

        # ECU发送的首帧和连续帧的时间
        ff_timestamp = None
        fc_timestamp = None
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] == 0x10:
                ff_timestamp = rt.get_recv_item_timestamp(i)
            if payload[0] == 0x21:
                fc_timestamp = rt.get_recv_item_timestamp(i)

        # TestLog("INFO", "", f"{send_timestamp=}, {ff_timestamp=}")

        TestLog("INFO", "Step3", "停止发送高优先级帧")
        emit_can_busload_high_stop(timer_id_start, timer_id_end)
        while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) > 20:
            sl_time().sleep(10)
        if ff_timestamp is not None:
            if ff_timestamp - send_timestamp > rN_AsTimeout_ms * 1.1:
                TestLog("FAIL", "期望结果：无响应或DUT发送FF，若DUT无响应跳转至步骤5", f"实际结果：收到DUT发送FF的时间超时, "
                                           f"请求报文发送时间点={send_timestamp}ms,"
                                           f"首帧报文发送时间点={ff_timestamp}ms,"
                                           f"差值={ff_timestamp - send_timestamp}ms")
            else:
                TestLog("PASS", "期望结果：无响应或DUT发送FF，若DUT无响应跳转至步骤5", "实际结果：收到DUT发送FF(1_)")
                TestLog("INFO", "Step4", "发送流控帧，其中STmin=0")
                send_canmsg(can_channel, msg_30, rDiagReqID, dlc=msg_30.dlc)

                sl_time().sleep((rN_CrTimeout_ms * 1.1))

                fc_timestamp = None
                recv_list = rt.get_recv_list()
                for i in range(len(recv_list)):
                    payload = rt.get_recv_item_payload(i)
                    if payload[0] == 0x21:
                        fc_timestamp = rt.get_recv_item_timestamp(i)

                if fc_timestamp is not None:
                    TestLog("FAIL", "期望结果：在N_Cr超时前未收到后续CF", "实际结果：收到连续帧的第1帧")
                else:
                    TestLog("PASS", "期望结果：在N_Cr超时前未收到后续CF", "实际结果：未收到连续帧的第1帧")
        else:
            TestLog("INFO", "期望结果：无响应或DUT发送FF，若DUT无响应跳转至步骤5", "实际结果：未收到DUT发送FF(1_)，跳过步骤4的发送流控帧，继续步骤5")

        check_msg_thread_stop(rt)

        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        TestLog("INFO", "Step5", "发送请求报文，请求多帧响应。")
        msg = canmsg_create(rDiagReqID, 8, data=[0x03, 0x22] + read_DID + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        sl_time().sleep((rN_AsTimeout_ms * 1.1))

        # ECU发送的首帧的时间
        ff_timestamp = None
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] == 0x10:
                ff_timestamp = rt.get_recv_item_timestamp(i)

        if ff_timestamp is None:
            TestLog("FAIL", "期望结果：DUT发送首帧 DUT sends FF", "实际结果：未收到首帧(1_)")
        else:
            TestLog("PASS", "期望结果：DUT发送首帧 DUT sends FF", "实际结果：DUT发送首帧1_")
            TestLog("INFO", "Step6", "发送流控帧，其中STmin=0。在发送流控帧后立即将总线负载提到100%")
            send_canmsg(can_channel, msg_30, rDiagReqID, dlc=msg_30.dlc)
            timer_id_start, timer_id_end = emit_can_busload_high(can_channel)
            while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) < 90:
                sl_time().sleep(10)
            # TestLog("INFO", "等待10s", "确保总线负载达到100%")
            # sl_time().sleep(10000)
            TestLog("INFO", "Step7", f"等待允许的最大{rN_AsTimeout_ms}超时(+10%)")
            sl_time().sleep((rN_AsTimeout_ms * 1.1))

            # 发送的流控帧的时间戳
            fc_timestamp = 0
            send_list = rt.get_send_list()
            for i in range(len(send_list)):
                payload = rt.get_send_item_payload(i)
                if payload[0] == 0x30:
                    fc_timestamp = rt.get_send_item_timestamp(i)
                    break

            # 收到的连续帧的时间戳
            cf_timestamp = None
            recv_list = rt.get_recv_list()
            for i in range(len(recv_list)):
                payload = rt.get_recv_item_payload(i)
                if payload[0] == 0x21:
                    cf_timestamp = rt.get_recv_item_timestamp(i)
                    break

            if cf_timestamp is not None:
                if cf_timestamp - fc_timestamp > rN_AsTimeout_ms * 1.1:
                    TestLog("FAIL", "期望结果：无响应或DUT发送CF第一帧，若无响应跳转至步骤10", f"实际结果：收到DUT发送第一帧CF的时间超时, "
                                               f"流控报文发送时间点={fc_timestamp}ms,"
                                               f"续帧报文发送时间点={cf_timestamp}ms,"
                                               f"差值={cf_timestamp - fc_timestamp}ms")
                else:
                    TestLog("PASS", "期望结果：无响应或DUT发送CF第一帧，若无响应跳转至步骤10", "实际结果：收到连续帧的第1帧")
            else:
                TestLog("INFO", "期望结果：无响应或DUT发送CF第一帧，若无响应跳转至步骤10", "实际结果：未收到连续帧的第1帧")
        check_msg_thread_stop(rt)

        TestLog("INFO", "Step9", "停止发送高优先级帧")
        emit_can_busload_high_stop(timer_id_start, timer_id_end)
        while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) > 20:
            sl_time().sleep(10)

        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        TestLog("INFO", "Step10", "发送请求报文，请求多帧响应。")
        msg = canmsg_create(rDiagReqID, 8, data=[0x03, 0x22] + read_DID + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        sl_time().sleep((rN_AsTimeout_ms * 1.1))

        ff_timestamp = None
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] == 0x10:
                ff_timestamp = rt.get_recv_item_timestamp(i)
                break

        if ff_timestamp is None:
            TestLog("FAIL", "期望结果：DUT发送首帧 DUT sends FF", "实际结果：未收到首帧(1_)")
        else:
            TestLog("PASS", "期望结果：DUT发送首帧 DUT sends FF", "实际结果：DUT发送首帧1_")

            TestLog("INFO", "Step11", "发送流控帧，其中STmin=0，在接收到DUT返回的连续帧第一帧之后立即发送使总线负载提到100％")
            rt.clear()
            send_canmsg(can_channel, msg_30, rDiagReqID, dlc=msg_30.dlc)

            timer_id_start, timer_id_end = 0, 0
            sl_time().sleep((rN_CrTimeout_ms * 1.1))
            status = False
            recv_list = rt.get_recv_list()
            for i in range(len(recv_list)):
                payload = rt.get_recv_item_payload(i)
                if payload[0] == 0x21:
                    status = True
                    break
            if status is True:
                TestLog("PASS", "期望结果：收到连续帧的第1帧", "实际结果：收到连续帧的第1帧")
                timer_id_start, timer_id_end = emit_can_busload_high(can_channel)
                while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) < 90:
                    sl_time().sleep(10)
                # TestLog("INFO", "等待10s", "确保总线负载达到100%")
                # sl_time().sleep(10000)
            else:
                TestLog("FAIL", "期望结果：收到连续帧的第1帧", "未收到连续帧的第1帧")

            sl_time().sleep((rN_AsTimeout_ms * 1.1))
            TestLog("INFO", "Step12", "停止发送高优先级帧")
            emit_can_busload_high_stop(timer_id_start, timer_id_end)
            while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) > 20:
                sl_time().sleep(10)
            # 收到的连续帧的时间戳
            cf_timestamp1 = 0
            cf_timestamp2 = 0
            recv_list = rt.get_recv_list()
            for i in range(len(recv_list)):
                payload = rt.get_recv_item_payload(i)
                if payload[0] == 0x21:
                    cf_timestamp1 = rt.get_recv_item_timestamp(i)
                if payload[0] == 0x22:
                    cf_timestamp2 = rt.get_recv_item_timestamp(i)
            if cf_timestamp2 > 0:
                if cf_timestamp2 - cf_timestamp1 > rN_AsTimeout_ms * 1.1:
                    TestLog("FAIL", "期望结果：无响应或DUT发送CF下一帧", f"实际结果：收到DUT发送第一帧CF的时间超时, "
                                               f"续帧1报文发送时间点={cf_timestamp1}ms,"
                                               f"续帧2报文发送时间点={cf_timestamp2}ms,"
                                               f"差值={cf_timestamp2 - cf_timestamp1}ms")
                else:
                    TestLog("PASS", "期望结果：无响应或DUT发送CF下一帧", "实际结果：收到连续帧的第2帧")
            else:
                TestLog("INFO", "", "未收到连续帧的第2帧")

        check_msg_thread_stop(rt)

        TestLog("INFO", case_name, "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC2_TimeoutCheck_N_Ar():
    """N_Ar超时值检查"""
    case_name = "N_Ar超时值检查"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_AsTimeout_ms = P.TpInfo.N_AsTimeout  # N_As最大时间
        rN_ArTimeout_ms = P.TpInfo.N_ArTimeout  # N_Ar最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        msg_first = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLength, data=[0x10, 0x0D, 0x22, 0x01, 0x02, 0x03, 0x04, 0x05],
                                  fdf=P.TpInfo.CanFDMode)
        msg_cf1 = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLength, data=[0x21, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0xAA],
                                fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        TestLog("INFO", "Step1", "发送多帧请求报文请求响应。"
                                 "在请求之后立即发送使总线负载达到100%的高优先级帧。")
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        timer_id_start, timer_id_end = emit_can_busload_high(can_channel)
        while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) < 90:
            sl_time().sleep(10)
        rt.clear()
        send_canmsg(can_channel, msg_first, rDiagReqID, dlc=msg_first.dlc)

        TestLog("INFO", "Step2", "等待允许的最大N_As超时(+10%)")

        sl_time().sleep((rN_ArTimeout_ms * 1.1))

        # 发送的首帧报文时间
        send_timestamp = 0
        send_list = rt.get_send_list()
        for i in range(len(send_list)):
            payload = rt.get_send_item_payload(i)
            if payload[:4] == [0x10, 0x0D, 0x22, 0x01]:
                send_timestamp = rt.get_send_item_timestamp(i)
                break

        # 收到的流控帧的时间戳
        fc_timestamp = 0
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] == 0x30:
                fc_timestamp = rt.get_recv_item_timestamp(i)
                break
        TestLog("INFO", "", f"{send_timestamp=}, {fc_timestamp=}")

        TestLog("INFO", "Step3", "停止发送高优先级帧")
        emit_can_busload_high_stop(timer_id_start, timer_id_end)
        while round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2) > 20:
            sl_time().sleep(10)

        if fc_timestamp > 0:
            if fc_timestamp - send_timestamp > rN_AsTimeout_ms * 1.1:
                TestLog("FAIL", case_name, f"收到DUT发送FC的时间超时, "
                                           f"请求首帧报文发送时间点={send_timestamp}ms,"
                                           f"流控帧报文发送时间点={fc_timestamp}ms,"
                                           f"差值={fc_timestamp - send_timestamp}ms")
            else:
                TestLog("PASS", case_name, "收到DUT发送FC")
        else:
            TestLog("PASS", case_name, "未收到DUT发送FC")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step4", "发送后续请求")
        send_canmsg(can_channel, msg_cf1, rDiagReqID, dlc=msg_cf1.dlc)
        check_msg_thread_stop(rt)

        TestLog("INFO", case_name, "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC3_TimeoutCheck_N_Cr():
    """N_Cr超时值检查"""
    case_name = "N_Cr超时值检查"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        read_DID = P.TpInfo.DID
        read_DID = list(divmod(read_DID, 256))

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        msg_first = canmsg_create(rDiagReqID, 8, data=[0x03, 0x22] + read_DID + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_30 = canmsg_create(rDiagReqID, 8, data=[0x30] + [0x00] * 7, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)
        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg_first, rDiagReqID, dlc=msg_first.dlc)

        sl_time().sleep(rN_BsTimeout_ms)

        # 收到的首帧的时间戳
        ff_timestamp = 0
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] == 0x10:
                ff_timestamp = rt.get_recv_item_timestamp(i)
                break
        if ff_timestamp > 0:
            TestLog("PASS", case_name, f"在N_Br={rN_BsTimeout_ms}ms超时时间内收到FF")
        else:
            TestLog("FAIL", case_name, f"在N_Br={rN_BsTimeout_ms}ms超时时间内未收到FF")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step2", "发送FC")
        send_canmsg(can_channel, msg_30, rDiagReqID, dlc=msg_30.dlc)
        check_msg_thread_stop(rt)

        TestLog("INFO", case_name, "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC4_TimeoutCheck_N_CsN_As():
    """N_Cs+N_As超时值检查"""
    case_name = "N_Cs+N_As超时值检查"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        read_DID = P.TpInfo.DID
        read_DID = list(divmod(read_DID, 256))

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()
        msg_first = canmsg_create(rDiagReqID, 8, data=[0x03, 0x22] + read_DID + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_30 = canmsg_create(rDiagReqID, 8, data=[0x30] + [0x00, 0x00] + [0xAA] * 7, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg_first, rDiagReqID, dlc=msg_first.dlc)

        sl_time().sleep(rN_BsTimeout_ms)

        # 收到的首帧的时间戳
        ff_timestamp = 0
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] == 0x10:
                ff_timestamp = rt.get_recv_item_timestamp(i)
                break
        if ff_timestamp > 0:
            TestLog("PASS", case_name, f"收到FF")
        else:
            TestLog("FAIL", case_name, f"未收到FF")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step2", "发送FC")
        send_canmsg(can_channel, msg_30, rDiagReqID, dlc=msg_30.dlc)
        check_msg_thread_stop(rt)

        # 发送的流控帧的时间戳
        fc_timestamp = 0
        send_list = rt.get_send_list()
        for i in range(len(send_list)):
            payload = rt.get_send_item_payload(i)
            if payload[0] == 0x30:
                fc_timestamp = rt.get_send_item_timestamp(i)
                break

        # 收到的首帧的时间戳
        cf_timestamp = 0
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] == 0x21:
                cf_timestamp = rt.get_recv_item_timestamp(i)
                break

        # TODo 检查N_Cs+N_As是否符合性能要求

        TestLog("INFO", case_name, "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC5_TimeoutCheck_N_BrN_Ar():
    """N_Br+N_Ar超时值检查"""
    case_name = "N_Br+N_Ar超时值检查"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        msg_first = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLength, data=[0x10, 0x0D, 0x22, 0x01, 0x02, 0x03, 0x04, 0x05],
                                  fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        # 进入默认会话
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", "发送多帧请求报文请求响应")
        rt.clear()
        send_canmsg(can_channel, msg_first, rDiagReqID, dlc=msg_first.dlc)

        sl_time().sleep(rN_BsTimeout_ms)

        # 收到的流控帧的时间戳
        fc_timestamp = 0
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] == 0x30:
                fc_timestamp = rt.get_recv_item_timestamp(i)
                break
        if fc_timestamp > 0:
            TestLog("PASS", case_name, f"收到FC")
        else:
            TestLog("FAIL", case_name, f"未收到FC")
            check_msg_thread_stop(rt)
            return

        # TODo 检查N_Br+N_Ar是否符合性能要求

        TestLog("INFO", case_name, "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC6_AbortTransmission():
    """停止发送后续部分连续帧"""
    case_name = "停止发送后续部分连续帧"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        sid = 0x22  # 服务id
        did = [0x01, 0x02]  # did
        if P.TpInfo.CanFDMode:
            did_data_len = 0x13A  # 总长度
        else:
            did_data_len = 0x22  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)
        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len,fdf=P.TpInfo.CanFDMode,dlc=P.TpInfo.MaxCanFDDataLengthToDLC)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        TestLog("INFO", "Step1", "发送多帧请求报文请求响应")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)

        sl_time().sleep(rN_BsTimeout_ms)
        # 收到的流控帧的时间戳
        recv_list = rt.get_recv_list()
        payload_30 = None
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0]>>4 == 3:
                payload_30 = payload
                break
        if payload_30 is not None:
            hex_str = bytes(rt.get_recv_item_payload(i - 1)).hex().upper()
            TestLog("PASS", case_name, f"期望结果：收到流控帧(FC)。实际结果：收到FC")
        else:
            TestLog("FAIL", case_name, f"期望结果：收到流控帧(FC)。实际结果：未收到FC")
            check_msg_thread_stop(rt)
            return

        stmin_ms = get_fc_st_min_ms(payload_30)

        TestLog("INFO", "Step2", "发送后续连续帧，不发送最后一帧")
        for msg in msg_list[1:4]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            sl_time().sleep(stmin_ms)

        # 在该状态下，应该只有1帧流控帧
        if len(rt.get_recv_list()) != 1:
            TestLog("FAIL", "", f"期望结果：ECU无响应报文。实际结果：收到ECU的响应报文")
        else:
            TestLog("PASS", "", f"期望结果：ECU无响应报文。实际结果：ECU无响应报文")

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC7_NoCF():
    """不发送所有连续帧"""
    case_name = "不发送所有连续帧"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        sid = 0x22  # 服务id
        did = [0x01, 0x02]  # did
        if P.TpInfo.CanFDMode:
            did_data_len = 0x13A  # 总长度
        else:
            did_data_len = 0x22  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,dlc=P.TpInfo.MaxCanFDDataLengthToDLC)

        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        TestLog("INFO", "Step1", "发送多帧请求报文请求响应")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        start_time = sl_time().timestamp()
        # 从接收报文列表中获取流控帧  -s
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)

        if payload_30 is not None:
            TestLog("PASS", "", f"期望结果：收到流控帧(FC)。实际结果：收到FC")
        else:
            TestLog("FAIL", "", f"期望结果：收到流控帧(FC)。实际结果：未收到FC")
            check_msg_thread_stop(rt)
            return

        stmin_ms = get_fc_st_min_ms(payload_30)

        TestLog("INFO", "Step2", "不发送连续帧")
        sl_time().sleep(stmin_ms)

        # 在该状态下，应该只有1帧流控帧
        if len(rt.get_recv_list()) != 1:
            TestLog("FAIL", "", f"期望结果：ECU无响应报文。实际结果：收到ECU的响应报文")
        else:
            TestLog("PASS", "", f"期望结果：ECU无响应报文。实际结果：ECU无响应报文")

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC8_DropCF():
    """连续帧丢失"""
    case_name = "连续帧丢失"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        sid = 0x22  # 服务id
        did = [0x01, 0x02]  # did
        if P.TpInfo.CanFDMode:
            did_data_len = 0xFC  # 总长度
        else:
            did_data_len = 0x1C  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode, dlc=P.TpInfo.MaxCanFDDataLengthToDLC)

        TestLog("INFO", "Step1", "发送多帧请求报文请求响应")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)

        sl_time().sleep(rN_BsTimeout_ms)
        # 收到的流控帧的时间戳
        recv_list = rt.get_recv_list()
        payload_30 = None
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] == 0x30:
                payload_30 = payload
                break
        if payload_30 is not None:
            TestLog("PASS", "", f"期望结果：收到流控帧(FC)，实际结果：收到FC")
        else:
            TestLog("FAIL", "", f"期望结果：收到流控帧(FC)，实际结果：未收到FC")
            check_msg_thread_stop(rt)
            return

        stmin_ms = get_fc_st_min_ms(payload_30)

        rt.clear()
        TestLog("INFO", "Step2", "发送连续帧，其中第三帧丢失")
        for msg in msg_list[1:3] + msg_list[4:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            sl_time().sleep(stmin_ms)
        sl_time().sleep(10)

        # 预先将 payload 转换为易读的十六进制格式
        recv_list = rt.get_recv_list()
        if len(recv_list) > 0:
            # 获取第一条报文并格式化为 "00 11 22..."
            raw_payload = rt.get_recv_item_payload(0)
            hex_payload = " ".join([f"{b:02X}" for b in raw_payload]) if raw_payload else "Empty Payload"

            TestLog("WARNING", "",f"期望结果：ECU无响应报文；"f"实际结果：收到 {len(recv_list)} 条响应报文，第一条为: {hex_payload}")
        else:
            TestLog("PASS", "","期望结果：ECU无响应报文；""实际结果：ECU无响应报文")

        TestLog("INFO", case_name, "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()

def test_TG2_TC9_DoubleCF():
    """重复发送连续帧"""
    case_name = "重复发送连续帧"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        sid = 0x22  # 服务id
        did = [0x01, 0x02]  # did
        if P.TpInfo.CanFDMode:
            did_data_len = 0xFC  # 总长度
        else:
            did_data_len = 0x1C  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC)

        TestLog("INFO", "Step1", "发送多帧请求报文请求响应")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        start_time = sl_time().timestamp()
        # 收到的流控帧的时间戳
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)

        if payload_30 is not None:
            TestLog("PASS", case_name, f"期望结果：收到FC。实际结果：收到FC")
        else:
            TestLog("FAIL", case_name, f"期望结果：收到FC。实际结果：未收到FC")
            check_msg_thread_stop(rt)
            return

        stmin_ms = get_fc_st_min_ms(payload_30)
        rt.clear()
        TestLog("INFO", "Step2", "将第一个连续帧发送两次")
        for msg in [msg_list[1]] + msg_list[1:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            sl_time().sleep(stmin_ms)

        sl_time().sleep(10)
        # 预先将 payload 转换为易读的十六进制格式
        recv_list = rt.get_recv_list()
        if len(recv_list) > 0:
            # 获取第一条报文并格式化为 "00 11 22..."
            raw_payload = rt.get_recv_item_payload(0)
            hex_payload = " ".join([f"{b:02X}" for b in raw_payload]) if raw_payload else "Empty Payload"

            TestLog("WARNING", "",f"期望结果：ECU无响应报文；"f"实际结果：收到 {len(recv_list)} 条响应报文，第一条为: {hex_payload}")
        else:
            TestLog("PASS", "","期望结果：ECU无响应报文；""实际结果：ECU无响应报文")

        rt.clear()
        TestLog("INFO", "Step3", "发送多帧请求报文请求响应")
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        start_time = sl_time().timestamp()

        # 收到的流控帧的时间戳
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)
        if payload_30 is not None:
            TestLog("PASS", "", f"期望结果：收到FC。实际结果：收到FC")
        else:
            TestLog("FAIL", "", f"期望结果：收到FC。实际结果：未收到FC")
            check_msg_thread_stop(rt)
            return

        stmin_ms = get_fc_st_min_ms(payload_30)
        rt.clear()
        TestLog("INFO", "Step4", "将最后一个连续帧发送两次")
        # for msg in msg_list[1:]+[msg_list[-1]]:
        #     send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
        #     sl_time().sleep(stmin_ms)
        for i, msg in enumerate(msg_list[1:], start=1):
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            if i != len(msg_list) - 1:
                sl_time().sleep(stmin_ms)
            else:
                sl_time().sleep(5)
                send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        sl_time().sleep(10)
        # 预先将 payload 转换为易读的十六进制格式
        recv_list = rt.get_recv_list()
        if len(rt.get_recv_list()) > 0 and rt.get_recv_item_payload(0)[:3] == [0x03, 0x7F, 0x22]:
            # 获取第一条报文并格式化为 "00 11 22..."
            raw_payload = rt.get_recv_item_payload(0)
            hex_payload = " ".join([f"{b:02X}" for b in raw_payload]) if raw_payload else "Empty Payload"

            TestLog("PASS", "",f"期望结果：ECU收到否定响应报文；"f"实际结果：收到 {len(recv_list)} 条响应报文，第一条为: {hex_payload}")
        elif len(rt.get_recv_list()) <= 0:
            TestLog("FAIL", "", "期望结果：ECU收到否定响应报文；""实际结果：ECU无响应报文")
        else:
            TestLog("FAIL", "",f"期望结果：ECU收到否定响应报文；"f"实际结果：收到 {len(recv_list)} 条响应报文，第一条为: {hex_payload}")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC10_DelayCF():
    """延迟发送连续帧"""
    case_name = "延迟发送连续帧"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_AsTimeout_ms = P.TpInfo.N_AsTimeout  # N_As最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        sid = 0x22  # 服务id
        did = [0x01, 0x02]  # did
        if P.TpInfo.CanFDMode:
            did_data_len = 0xFC  # 总长度
        else:
            did_data_len = 0x1C  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,dlc=P.TpInfo.MaxCanFDDataLengthToDLC)

        # Step1 ：发送多帧请求报文请求响应
        TestLog("INFO", "Step1", "发送多帧请求报文请求响应")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        start_time = sl_time().timestamp()

        # 收到的流控帧的时间戳
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)
        if payload_30 is not None:
            TestLog("PASS", case_name, f"期望结果：收到FC。实际结果：收到FC")
        else:
            TestLog("FAIL", case_name, f"期望结果：收到FC。实际结果：未收到FC")
            check_msg_thread_stop(rt)
            return

        # Step2：等待超时时间110%
        TestLog("INFO", "Step2", f"等待超时(超时时间110%N_Cr={rN_CrTimeout_ms * 1.1}ms)")

        sl_time().sleep(rN_CrTimeout_ms * 1.1)
        stmin_ms = get_fc_st_min_ms(payload_30)

        rt.clear()
        # Step3 ： 发送连续帧
        TestLog("INFO", "Step3", "发送连续帧")
        for msg in msg_list[1:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            sl_time().sleep(stmin_ms)
        sl_time().sleep(rP2_Client_ms)

        # 此时应只有1帧流控帧
        if len(rt.get_recv_list()) == 0:
            TestLog("PASS", case_name, "期望结果：DUT在P2超时前未响应。实际结果：DUT在P2超时前未响应")
        else:
            TestLog("FAIL", case_name,
                    f"期望结果：DUT在P2超时前未响应。实际结果：DUT在P2超时前响应: {[[hex(i) for i in item['payload']] for item in rt.get_recv_list()]}")

        TestLog("INFO", "Step4", "发送多帧请求报文请求响应")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        start_time = sl_time().timestamp()
        # 收到的流控帧的时间戳
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)
        if payload_30 is not None:
            TestLog("PASS", "", f"期望结果：收到FC。实际结果：收到FC")
        else:
            TestLog("FAIL", "", f"期望结果：收到FC。实际结果：未收到FC")
            check_msg_thread_stop(rt)
            return

        stmin_ms = get_fc_st_min_ms(payload_30)
        rt.clear()
        TestLog("INFO", "Step5", "发送CF第一帧")
        send_canmsg(can_channel, msg_list[1], rDiagReqID, dlc=msg_list[1].dlc)

        TestLog("INFO", "Step6", f"等待超时(超时时间110%N_Cr={rN_CrTimeout_ms * 1.1}ms)")

        sl_time().sleep((rN_CrTimeout_ms * 1.1))

        TestLog("INFO", "Step7", "发送剩下的连续帧")
        for msg in msg_list[2:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            sl_time().sleep(stmin_ms)
        sl_time().sleep(rP2_Client_ms)

        # 此时应只有1帧流控帧
        if len(rt.get_recv_list()) == 0:
            TestLog("PASS", "", "期望结果：DUT在P2超时前未响应。实际结果：DUT在P2超时前未响应")
        else:
            TestLog("FAIL", "",
                    f"期望结果：DUT在P2超时前未响应。实际结果：DUT在P2超时前响应: {[[hex(i) for i in item['payload']] for item in rt.get_recv_list()]}")

        TestLog("INFO", "Step8", "发送多帧请求报文请求响应")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)

        start_time = sl_time().timestamp()
        # 收到的流控帧的时间戳
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)
        if payload_30 is not None:
            TestLog("PASS", "", f"期望结果：收到FC。实际结果：收到FC")
        else:
            TestLog("FAIL", "", f"期望结果：收到FC。实际结果：未收到FC")
            check_msg_thread_stop(rt)
            return

        stmin_ms = get_fc_st_min_ms(payload_30)

        TestLog("INFO", "Step9", f"等待超时(超时时间N_Cr-5ms={rN_CrTimeout_ms - 10}ms)")
        sl_time().sleep(rN_CrTimeout_ms - 10)
        rt.clear()
        TestLog("INFO", "Step10", "发送连续帧")
        for msg in msg_list[1:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            sl_time().sleep(stmin_ms)
        sl_time().sleep(rP2_Client_ms)

        # 在该状态下，应该有帧负响应报文
        if len(rt.get_recv_list()) == 1 and rt.get_recv_item_payload(0)[:3] == [0x03, 0x7F, 0x22]:
            TestLog("PASS", "",
                    f"期望结果：DUT在P2超时前响应。实际结果:DUT在P2超时前响应。{[[hex(i) for i in item['payload']] for item in rt.get_recv_list()]}")
        else:
            TestLog("FAIL", "", f"期望结果：DUT在P2超时前响应。实际结果:DUT在P2超时前未响应")

        TestLog("INFO", "Step11", "发送多帧请求报文请求响应")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)

        start_time = sl_time().timestamp()
        # 收到的流控帧的时间戳
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)
        if payload_30 is not None:
            TestLog("PASS", "", f"期望结果：收到FC。实际结果：收到FC")
        else:
            TestLog("FAIL", "", f"期望结果：收到FC。实际结果：未收到FC")
            check_msg_thread_stop(rt)
            return

        stmin_ms = get_fc_st_min_ms(payload_30)
        rt.clear()
        TestLog("INFO", "Step12", "发送CF第一帧")
        send_canmsg(can_channel, msg_list[1], rDiagReqID, dlc=msg_list[1].dlc)

        TestLog("INFO", "Step13", f"等待超时(超时时间N_Cr-5={rN_CrTimeout_ms - 10}ms)")
        sl_time().sleep(rN_CrTimeout_ms - 10)

        TestLog("INFO", "Step14", "发送剩下的连续帧")
        for msg in msg_list[2:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            sl_time().sleep(stmin_ms)
        sl_time().sleep(rP2_Client_ms)

        # 在该状态下，应该1帧负响应报文
        if len(rt.get_recv_list()) == 1 and rt.get_recv_item_payload(0)[:3] == [0x03, 0x7F, 0x22]:
            TestLog("PASS", "",
                    f"期望结果：DUT在P2超时前响应。实际结果: DUT在P2超时前响应{[[hex(i) for i in item['payload']] for item in rt.get_recv_list()]}")
        else:
            TestLog("FAIL", "", f"期望结果：DUT在P2超时前响应。实际结果:DUT在P2超时前未响应,报文数量为{len(rt.get_recv_list())}")

        check_msg_thread_stop(rt)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC11_NoFC():
    """无流控帧"""
    case_name = "无流控帧"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_AsTimeout_ms = P.TpInfo.N_AsTimeout  # N_As最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        read_DID = P.TpInfo.DID
        read_DID = list(divmod(read_DID, 256))
        sid = 0x22  # 服务id
        did = [0x01, 0x02]  # did
        if P.TpInfo.CanFDMode:
            did_data_len = 0xFC  # 总长度
        else:
            did_data_len = 0x1C  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)
        msg_first = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLengthToDLC, data=[0x03, sid] + read_DID + [0xAA] * (P.TpInfo.MaxCanFDDataLength-4), fdf=P.TpInfo.CanFDMode)
        # msg_first = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10,0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)

        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        send_canmsg(can_channel, msg_first, rDiagReqID, dlc=msg_first.dlc)

        payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
        TestLog("INFO", "", f"payload_10 = {payload_10}")
        if payload_10 is not None:
            TestLog("PASS", "", "期望结果：收到首帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到首帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step2", "不发送流控帧")
        sl_time().sleep(rN_BsTimeout_ms + rN_CrTimeout_ms)
        sl_time().sleep(1000)
        # 此时应只有1帧首帧
        if len(rt.get_recv_list()) == 1:
            TestLog("PASS", "", f"期望结果：DUT在{rN_BsTimeout_ms + rN_CrTimeout_ms}超时前未响应。实际结果：DUT在{rN_BsTimeout_ms + rN_CrTimeout_ms}超时前未响应。")
        else:
            TestLog("FAIL", "",
                    f"期望结果：DUT在{rN_BsTimeout_ms + rN_CrTimeout_ms}超时前未响应。DUT在P2超时前响应: {[[hex(i) for i in item['payload']] for item in rt.get_recv_list()]}")
        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC12_DelayFC():
    """延迟发送流控帧"""
    case_name = "延迟发送流控帧"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        read_DID = P.TpInfo.DID
        read_DID = list(divmod(read_DID, 256))
        sid = 0x22

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)
        msg_first = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLengthToDLC, data=[0x03, sid] + read_DID + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        #TODO 规范要求发送XX
        msg_30 = canmsg_create(rDiagReqID, 8, data=[0x30] + [0x00] * 2 + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        msg_default_session = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLengthToDLC, data=[0x02, 0x10, 0x01] + [0xAA] * (P.TpInfo.MaxCanFDDataLength - 3), fdf=P.TpInfo.CanFDMode,brs=1)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # msg_default_session = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLength,
        #                                     data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode,brs = 1)
        # send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        # sl_time().sleep(rP2_Client_ms * 0.8)
        # msg_default_session = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLength,
        #                                     data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode,brs = 1)
        # send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        # sl_time().sleep(rP2_Client_ms * 0.8)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg_first, rDiagReqID, dlc=msg_first.dlc)

        payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
        if payload_10 is not None:
            TestLog("PASS", "", "期望结果:收到首帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果:收到首帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step2", f"等待超时(超时时间{rN_BsTimeout_ms * 1.1 = } ms)（N_BsTimeout = {rN_BsTimeout_ms}）")

        sl_time().sleep(rN_BsTimeout_ms * 1.1)

        TestLog("INFO", "Step3", "发送流控帧")
        rt.clear()
        send_canmsg(can_channel, msg_30, rDiagReqID, dlc=msg_30.dlc)

        sl_time().sleep(rN_CrTimeout_ms)

        # 此时应只有1帧首帧
        if len(rt.get_recv_list()) == 0:
            TestLog("PASS", "", "期望结果：DUT在110%*N_Cr超时前未响应。实际结果：DUT在110%*N_Cr超时前未响应")
        else:
            TestLog("FAIL", "",
                    f"期望结果：DUT在110%*N_Cr超时前未响应。实际结果：DUT在110%*N_Cr超时前响应: {[[hex(i) for i in item['payload']] for item in rt.get_recv_list()]}")

        TestLog("INFO", "Step4", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg_first, rDiagReqID, dlc=msg_first.dlc)
        payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
        if payload_10 is not None:
            TestLog("PASS", "", "期望结果:收到首帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果:收到首帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step5", f"等待超时(超时时间{rN_BsTimeout_ms * 0.9 = } ms)（N_BsTimeout = {rN_BsTimeout_ms}）")

        sl_time().sleep(rN_CrTimeout_ms * 0.9)

        TestLog("INFO", "Step6", "发送流控帧")
        rt.clear()
        send_canmsg(can_channel, msg_30, rDiagReqID, dlc=msg_30.dlc)

        sl_time().sleep(rN_CrTimeout_ms)

        recv_list = rt.get_recv_list()
        status = False
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] == 0x21:
                status = True
                break

        if status is True:
            TestLog("PASS", "",
                    f"期望结果：DUT在{1.1 * rN_CrTimeout_ms=}超时前收到响应。实际结果: DUT在{1.1 * rN_CrTimeout_ms=}超时前收到响应{[[hex(i) for i in item['payload']] for item in rt.get_recv_list()]}")
        else:
            TestLog("FAIL", "", f"期望结果：DUT在{1.1 * rN_CrTimeout_ms=}超时前收到响应。实际结果: DUT在110%*N_Cr超时前未响应")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC13_RepeatFC():
    """重复发送流控帧"""
    case_name = "重复发送流控帧"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        read_DID = P.TpInfo.DID
        read_DID = list(divmod(read_DID, 256))
        sid = 0x22

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()
        msg_first = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLengthToDLC, data=[0x03,sid] + read_DID + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_30_1 = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLengthToDLC, data=[0x30, 0x00, 0x28] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_30_2 = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLengthToDLC, data=[0x30, 0x00, 0x00] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,
                                            fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg_first, rDiagReqID, dlc=msg_first.dlc)
        # 从接收报文列表中获取所有的首帧FF  -s
        payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
        if payload_10 is not None:
            TestLog("PASS", "", "期望结果：收到首帧(FF)。实际结果：收到首帧(FF)。")
        else:
            TestLog("FAIL", "", "期望结果：收到首帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step2", "发送流控帧(STmin=0x28[40ms])")
        rt.clear()
        send_canmsg(can_channel, msg_30_1, rDiagReqID, dlc=msg_30_1.dlc)

        TestLog("INFO", "Step3", "再次发送流控帧(STmin=0x00[0ms])")
        rt.clear()
        send_canmsg(can_channel, msg_30_2, rDiagReqID, dlc=msg_30_2.dlc)

        sl_time().sleep(1000)

        # 从首帧中获取DL
        dl = ((payload_10[0] & 0x0F) << 4) | payload_10[1]
        expect_cf_counter = math.ceil((dl - 6) / 7)  # 根据DL计算出正常的连续帧的数量

        # 从接收报文列表中获取所有的连续帧CF  -s
        cf_tm_list = []
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            timestamp = rt.get_recv_item_timestamp(i)
            if payload[0] >> 4 == 2:
                cf_tm_list.append(timestamp)

        cf_tm_diff = []
        for i in range(len(cf_tm_list) - 1):
            cf_tm_diff.append(cf_tm_list[i + 1] - cf_tm_list[i])
        if min(cf_tm_diff) < 0x28:
            TestLog("FAIL", "",
                    f"期望结果：收到的所有连续帧之间的时间间隔均大于等于0x28(40ms)，实际结果：收到的连续帧之间的时间间隔存在小于0x28(40ms)，CF帧时间戳={cf_tm_list}，时间间隔={cf_tm_diff}")
            check_msg_thread_stop(rt)
            return
        else:
            TestLog("PASS", "",
                    f"期望结果：收到的连续帧之间的时间间隔均大于等于0x28(40ms)，实际结果：接收到响应，且连续帧之间的间隔均大于等于0x28(40ms)，CF帧时间戳={cf_tm_list}，时间间隔={cf_tm_diff}")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC14_STminTiming():
    """STmin时间测试"""
    case_name = "STmin时间测试"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_ArTimeout_ms = P.TpInfo.N_ArTimeout  # N_Ar最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        read_DID = P.TpInfo.DID
        read_DID = list(divmod(read_DID, 256))
        sid = 0x22

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()
        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        msg_first = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLengthToDLC, data=[0x03, sid] + read_DID + [0xAA] * (P.TpInfo.MaxCanFDDataLength - 4), fdf=P.TpInfo.CanFDMode)

        stmin_list = [1, 10, 20, 30, 40, 50, 60]
        TestLog("INFO", "", f"循环测试{stmin_list=}")
        for stmin_ms in stmin_list:
            TestLog("INFO", "", f"===使用STmin={stmin_ms}ms进行测试===")
            msg_30 = canmsg_create(rDiagReqID, 8, data=[0x30, 0x00, stmin_ms] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)

            # 开启线程，用于检测响应报文
            check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
            sl_time().sleep(5)
            TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
            rt.clear()
            send_canmsg(can_channel, msg_first, rDiagReqID, dlc=msg_first.dlc)

            # 从接收报文列表中获取首帧FF  -s
            payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
            if payload_10 is not None:
                TestLog("PASS", "", "期望结果：收到首帧(FF)。实际结果：收到首帧(FF)。")
            else:
                TestLog("FAIL", "", "期望结果：收到首帧(FF)。实际结果：超时未收到首帧(FF)")
                check_msg_thread_stop(rt)
                continue

            TestLog("INFO", "Step2", f"发送流控帧(STmin={stmin_ms}ms)")
            rt.clear()
            send_canmsg(can_channel, msg_30, rDiagReqID, dlc=msg_30.dlc)

            # 从首帧中获取DL
            dl = ((payload_10[0] & 0x0F) << 8) | payload_10[1]
            expect_cf_counter = math.ceil(
                (dl - (P.TpInfo.MaxCanFDDataLength - 2)) / (P.TpInfo.MaxCanFDDataLength - 1))  # 根据DL计算出正常的连续帧的数量


            sl_time().sleep((rN_CrTimeout_ms) * expect_cf_counter)

            # 从接收报文列表中获取所有的连续帧CF  -s
            cf_tm_list = []
            cf_list = []
            recv_list = rt.get_recv_list()
            for i in range(len(recv_list)):
                payload = rt.get_recv_item_payload(i)
                timestamp = rt.get_recv_item_timestamp(i)
                if payload[0] >> 4 == 2:
                    cf_tm_list.append(timestamp)
                    cf_list.append(payload)
            # 从接收报文列表中获取所有的连续帧CF  -e

            if len(cf_tm_list) != expect_cf_counter:
                TestLog("FAIL", "", f"期望结果：收到{expect_cf_counter}帧连续帧,实际结果：收到{len(cf_tm_list)}帧连续帧={cf_list}")
                check_msg_thread_stop(rt)
                continue

            cf_tm_diff = []
            for i in range(len(cf_tm_list) - 1):
                cf_tm_diff.append(cf_tm_list[i + 1] - cf_tm_list[i])
            if min(cf_tm_diff) < stmin_ms:
                TestLog("FAIL", "",
                        f"期望结果：接收到响应，且连续帧之间的间隔均大于等于{stmin_ms}ms。实际结果：收到的连续帧之间的时间间隔存在小于{stmin_ms}ms，CF帧时间戳={cf_tm_list}，时间间隔={cf_tm_diff}")
                check_msg_thread_stop(rt)
                continue
            else:
                TestLog("PASS", "",
                        f"期望结果：接收到响应，且连续帧之间的间隔均大于等于{stmin_ms}ms。实际结果：接收到响应，且连续帧之间的间隔均大于等于{stmin_ms}msCF帧时间戳={cf_tm_list}，时间间隔={cf_tm_diff}")

            check_msg_thread_stop(rt)
        TestLog("INFO", case_name, "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC15_CheckValidSTmin():
    """确认DUT的STmin参数有效"""
    case_name = "确认DUT的STmin参数有效"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        sid = 0x22  # 服务id
        did = [0x01, 0x02]  # did
        if P.TpInfo.CanFDMode:
            did_data_len = 0xFC  # 总长度
        else:
            did_data_len = 0x1C  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()
        #进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,dlc=P.TpInfo.MaxCanFDDataLengthToDLC)
        TestLog("INFO", "Step1", "发送多帧请求报文请求响应")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)

        sl_time().sleep(rN_BsTimeout_ms)

        # 从接收报文列表中获取流控帧FC  -s
        payload_30 = None
        recv_list = rt.get_recv_list()
        # TestLog("INFO","",f"{(len(recv_list))=}")
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] ==0x30:
                payload_30 = payload
                break
        # 从接收报文列表中获取流控帧FC  -e

        if payload_30 is not None:
            TestLog("PASS", "", f"期望结果：收到FC。实际结果：收到FC。")
        else:
            TestLog("FAIL", "", f"期望结果：收到FC。实际结果：未收到FC")
            check_msg_thread_stop(rt)
            return

        stmin_byte = payload_30[2]

        if 0x00 <= stmin_byte <= 0x7F or 0xF1 <= stmin_byte <= 0xF9:
            TestLog("PASS", "", f"期望结果：STmin is valid={hex(stmin_byte)}。实际结果：STmin is valid={hex(stmin_byte)}")
        else:
            TestLog("FAIL", "", f"期望结果：STmin is valid={hex(stmin_byte)}。实际结果：STmin is invalid={hex(stmin_byte)}")

        check_msg_thread_stop(rt)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC16_CheckSFDatalength():
    """检查SF报文长度"""
    case_name = "检查SF报文长度"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()
        #进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        msg = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLengthToDLC, data=[0x03, 0x22, 0xF0, 0xF1] + [0xAA] * (P.TpInfo.MaxCanFDDataLength - 4), fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)
        TestLog("INFO", "Step1", "发送请求报文请求单帧响应")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        sl_time().sleep(rP2_Client_ms * 0.8)

        response_list = rt.get_recv_list()
        # TestLog("INFO","",f"{(len(response_list))=}")
        if len(response_list) == 0:
            TestLog("FAIL", "", f"期望结果：收到SF报文。实际结果：未收到SF报文")
            check_msg_thread_stop(rt)
            return
        TestLog("PASS", "", f"期望结果：收到SF报文。实际结果：收到SF报文")
        response_data = rt.get_recv_item_payload(0)
        pci_type = (response_data[0] & 0xF0) >> 4
        pci_low = response_data[0] & 0x0F
        if pci_type != 0:
            TestLog("FAIL", "", f"期望结果：收到SF帧；实际结果：PCI类型={pci_type}，非SF帧，数据={[hex(i) for i in response_data]}")
            check_msg_thread_stop(rt)
            return
        if pci_low != 0:
            sf_len = pci_low
            max_len = 7
        else:
            sf_len = response_data[1]
            max_len = P.TpInfo.MaxCanFDDataLength - 2
        if 0 < sf_len <= max_len:
            TestLog("PASS", "", f"期望结果：the length of SF is valid={sf_len}；实际结果：the length of SF is valid={sf_len}")
        else:
            TestLog("FAIL", "", f"期望结果：the length of SF is valid={sf_len}；实际结果：the length of SF is invalid={sf_len}")

        check_msg_thread_stop(rt)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC17_CheckFFDatalength():
    """检查FF报文长度"""
    case_name = "检查FF报文长度"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        read_DID = P.TpInfo.DID
        read_DID = list(divmod(read_DID, 256))
        sid = 0x22

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()
        #进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        msg = canmsg_create(rDiagReqID, 8, data=[0x03, sid] + read_DID +[0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        sl_time().sleep(rP2_Client_ms * 0.8)

        # 从接收报文列表中获取首帧FF  -s
        payload_10 = None
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] == 0x10:
                payload_10 = payload
                break
        # 从接收报文列表中获取首帧FF  -e

        if payload_10 is not None:
            TestLog("PASS", "", "期望结果：收到首帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到首帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        ff_len = (payload_10[0] & 0xF) << 8 | payload_10[1]
        if P.TpInfo.CanFDMode:
            if 62 < ff_len <= 0xFFF:
                TestLog("PASS", "",f"实际结果：the length of FF is valid={hex(ff_len)}，期望结果：the length of FF is valid={hex(ff_len)}")
            else:
                TestLog("FAIL", "",f"实际结果：the length of FF is valid={hex(ff_len)}，期望结果：the length of FF is invalid={hex(ff_len)}")
        else:
            if 7 < ff_len <= 0xFFF:
                TestLog("PASS", "",f"实际结果：the length of FF is valid={hex(ff_len)}，期望结果：the length of FF is valid={hex(ff_len)}")
            else:
                TestLog("FAIL", "",f"实际结果：the length of FF is valid={hex(ff_len)}，期望结果：the length of FF is invalid={hex(ff_len)}")

        check_msg_thread_stop(rt)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC18_ResponseInterruptedbySF():
    """响应被非预期单帧报文干扰"""
    case_name = "响应被非预期单帧报文干扰"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_ArTimeout_ms = P.TpInfo.N_ArTimeout  # N_Ar最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        read_DID = P.TpInfo.DID
        read_DID = list(divmod(read_DID, 256))
        sid = 0x22

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        msg = canmsg_create(rDiagReqID, 8, data=[0x03, sid] +read_DID + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_30_1 = canmsg_create(rDiagReqID, 8, data=[0x30, 0x00, 0x14] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_ff = canmsg_create(rDiagReqID, 8, data=[0x03, 0x22, 0xF0, 0xF1] + [0xAA] * 4, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        sl_time().sleep(rN_ArTimeout_ms)

        # 从接收报文列表中获取首帧FF  -s
        payload_10 = None
        recv_list = rt.get_recv_list()
        TestLog("INFO","",f"{(len(recv_list))=}")
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] == 0x10:
                payload_10 = payload
                break
        # 从接收报文列表中获取首帧FF  -e

        if payload_10 is not None:
            TestLog("PASS", "", "期望结果：收到首帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到首帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step2", "发送流控帧")
        send_canmsg(can_channel, msg_30_1, rDiagReqID, dlc=msg_30_1.dlc)

        TestLog("INFO", "Step3", "发送单帧")
        send_canmsg(can_channel, msg_ff, rDiagReqID, dlc=msg_ff.dlc)

        # 从首帧中获取DL
        dl = (payload_10[0] & 0xF) << 8 | payload_10[1]
        expect_cf_counter = math.ceil((dl - 6) / 7)  # 根据DL计算出正常的连续帧的数量

        sl_time().sleep(expect_cf_counter * rN_CrTimeout_ms)

        # 从接收报文列表中获取连续帧CF 和 正响应报文  -s
        positive_response = False
        cf_list = []
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 2:
                cf_list.append(payload)
            if 0x62 in payload and 0xf0 in payload and 0xf1 in payload:
                positive_response = True
        # 从接收报文列表中获取连续帧CF 和 正响应报文  -s

        if expect_cf_counter != len(cf_list):
            TestLog("FAIL", "", f"未收到完整的连续帧，期望收到{expect_cf_counter}帧，实际收到{len(cf_list)}帧")
            check_msg_thread_stop(rt)
            return
        else:
            flag = True
            for i in range(len(cf_list) - 1):
                diff = cf_list[i + 1][0] - cf_list[i][0]
                if cf_list[i][0] == 0x2F and cf_list[i + 1][0] != 0x20:
                    flag = False
                    break
                elif diff != 1 and cf_list[i][0] != 0x2F:
                    flag = False
                    break

            if flag is False:
                TestLog("FAIL", "", f"期望结果：收到完整的连续帧，实际结果：收到的连续帧SN不连续，{cf_list=}")
                check_msg_thread_stop(rt)
                return
            else:
                TestLog("PASS", "", f"期望结果：收到完整的连续帧，期望收到{expect_cf_counter}帧，实际收到{len(cf_list)}帧")

        if positive_response is True:
            TestLog("FAIL", "", f"期望结果：未收到单帧的响应报文。实际结果：收到了单帧的响应报文")
        else:
            TestLog("PASS", "", f"期望结果：未收到单帧的响应报文。实际结果：未收到单帧的响应报文")

        check_msg_thread_stop(rt)
        TestLog("INFO", case_name, "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC19_ResponseInterruptedbyFF():
    """响应被非预期首帧报文干扰"""
    case_name = "响应被非预期首帧报文干扰"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_ArTimeout_ms = P.TpInfo.N_ArTimeout  # N_Ar最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        read_DID = P.TpInfo.DID
        read_DID = list(divmod(read_DID, 256))
        sid = 0x22  # 服务id
        did = [0x01, 0x02]  # did
        if P.TpInfo.CanFDMode:
            did_data_len = 0xFC  # 总长度
        else:
            did_data_len = 0x1C  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        msg = canmsg_create(rDiagReqID, 8, data=[0x03,sid] + read_DID + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,dlc=P.TpInfo.MaxCanFDDataLengthToDLC)
        msg_30_1 = canmsg_create(rDiagReqID, 8, data=[0x30, 0x00, 0x14] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,
                                            fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        sl_time().sleep(rN_ArTimeout_ms)

        # 从接收报文列表中获取首帧FF  -s
        payload_0x10 = None
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] == 0x10:
                payload_0x10 = payload
                break
        # 从接收报文列表中获取首帧FF  -e

        if payload_0x10 is not None:
            TestLog("PASS", "", "期望结果：收到首帧(FF)。实际结果：收到首帧(FF)。")
        else:
            TestLog("FAIL", "", "期望结果：收到首帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step2", "发送流控帧")
        send_canmsg(can_channel, msg_30_1, rDiagReqID, dlc=msg_30_1.dlc)

        # 从首帧中获取DL
        dl = (payload_0x10[0] & 0xF) << 8 | payload_0x10[1]
        expect_cf_counter = math.ceil((dl - 6) / 7)  # 根据DL计算出正常的连续帧的数量

        TestLog("INFO", "Step3", "发送首帧")
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)

        sl_time().sleep(expect_cf_counter * rN_CrTimeout_ms)

        # 从接收报文列表中获取所有的连续帧CF 和 流控帧FC  -s
        fc_counter = 0
        cf_list = []
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 2:
                cf_list.append(payload)
            if payload[0] >> 4 == 3:
                fc_counter += 1
        # 从接收报文列表中获取所有的连续帧CF 和 流控帧FC  -e

        if expect_cf_counter != len(cf_list):
            TestLog("FAIL", "", f"未收到完整的连续帧，期望收到{expect_cf_counter}帧，实际收到{len(cf_list)}帧")
            check_msg_thread_stop(rt)
            return
        else:
            flag = True
            for i in range(len(cf_list) - 1):
                diff = cf_list[i + 1][0] - cf_list[i][0]
                if cf_list[i][0] == 0x2F and cf_list[i + 1][0] != 0x20:
                    flag = False
                    break
                elif diff != 1 and cf_list[i][0] != 0x2F:
                    flag = False
                    break
            if flag is False:
                TestLog("FAIL", "", f"期望结果：收到完整的连续帧。实际结果：收到的连续帧SN不连续，{cf_list=}")
                check_msg_thread_stop(rt)
                return
            else:
                TestLog("PASS", "", f"收到完整的连续帧，期望收到{expect_cf_counter}帧，实际收到{len(cf_list)}帧")

        if fc_counter > 0:
            TestLog("FAIL", "", f"期望结果：未收到首帧的响应报文。实际结果：收到了首帧的响应报文")
        else:
            TestLog("PASS", "", f"期望结果：未收到首帧的响应报文。实际结果：未收到首帧的响应报文。")

        check_msg_thread_stop(rt)
        TestLog("INFO", case_name, "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC20_ResponseInterruptedbyCF():
    """响应被非预期连续帧报文干扰"""
    case_name = "响应被非预期连续帧报文干扰"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_ArTimeout_ms = P.TpInfo.N_ArTimeout  # N_Ar最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        read_DID = P.TpInfo.DID
        read_DID = list(divmod(read_DID, 256))
        sid = 0x22  # 服务id
        did = [0x01, 0x02]  # did
        if P.TpInfo.CanFDMode:
            did_data_len = 0xFC  # 总长度
        else:
            did_data_len = 0x1C  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        msg = canmsg_create(rDiagReqID, 8, data=[0x03, sid] + read_DID + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_30_1 = canmsg_create(rDiagReqID, 8, data=[0x30, 0x00, 0x14] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,dlc=P.TpInfo.MaxCanFDDataLengthToDLC)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        sl_time().sleep(rN_ArTimeout_ms)

        # 从接收报文列表中获取首帧FF  -s
        payload_0x10 = None
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] == 0x10:
                payload_0x10 = payload
                # length = payload[0]<<8 | payload[1]
                break
        # 从接收报文列表中获取首帧FF  -e
        # TestLog("INFO","",f"length={length}")
        if payload_0x10 is not None:
            TestLog("PASS", "", "期望结果：收到首帧(FF)。实际结果：收到首帧(FF)。")
        else:
            TestLog("FAIL", "", "期望结果：收到首帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step2", "发送流控帧")
        send_canmsg(can_channel, msg_30_1, rDiagReqID, dlc=msg_30_1.dlc)

        # 从首帧中获取DL
        dl = (payload_0x10[0] & 0xF) << 8 | payload_0x10[1]
        expect_cf_counter = math.ceil((dl - 6) / 7)  # 根据DL计算出正常的连续帧的数量

        TestLog("INFO", "Step3", "发送连续帧")
        send_canmsg(can_channel, msg_list[1], rDiagReqID, dlc=msg_list[1].dlc)

        sl_time().sleep(expect_cf_counter * rN_CrTimeout_ms)

        # 从接收报文列表中获取所有的连续帧CF  -s
        cf_list = []
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 2:
                cf_list.append(payload)
        # 从接收报文列表中获取所有的连续帧CF  -e

        TestLog("INFO", case_name, f"cf_list={[[hex(i) for i in item] for item in cf_list]}")

        if expect_cf_counter != len(cf_list):
            TestLog("FAIL", "", f"未收到完整的连续帧，期望收到{expect_cf_counter}帧，实际收到{len(cf_list)}帧")
            check_msg_thread_stop(rt)
            return
        else:
            flag = True
            for i in range(len(cf_list) - 1):
                diff = cf_list[i + 1][0] - cf_list[i][0]
                if cf_list[i][0] == 0x2F and cf_list[i + 1][0] != 0x20:
                    flag = False
                    break
                elif diff != 1 and cf_list[i][0] != 0x2F:
                    flag = False
                    break
            if flag is False:
                TestLog("FAIL", "", f"期望结果：收到完整的连续帧。实际结果：收到的连续帧SN不连续，{cf_list=}")
                check_msg_thread_stop(rt)
                return
            else:
                TestLog("PASS", "", f"收到完整的连续帧，期望收到{expect_cf_counter}帧，实际收到{len(cf_list)}帧")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")
    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC21_ResponseInterruptedbyFC():
    """响应被非预期流控帧报文干扰"""
    case_name = "响应被非预期流控帧报文干扰"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_ArTimeout_ms = P.TpInfo.N_ArTimeout  # N_Ar最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        read_DID = P.TpInfo.DID
        read_DID = list(divmod(read_DID, 256))
        sid = 0x22  # 服务id

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        msg = canmsg_create(rDiagReqID, 8, data=[0x03, sid] + read_DID+ [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_30_1 = canmsg_create(rDiagReqID, 8, data=[0x30, 0x00, 0x14] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_32 = canmsg_create(rDiagReqID, 8, data=[0x32, 0x00, 0x14] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        sl_time().sleep(rN_ArTimeout_ms)

        # 从接收报文列表中获取首帧FF  -s
        payload_10 = None
        recv_list = rt.get_recv_list()
        TestLog("INFO", "", f"{(len(recv_list))=}")
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] == 0x10:
                payload_10 = payload
                break
        # 从接收报文列表中获取首帧FF  -e

        if payload_10 is not None:
            TestLog("PASS", "", "期望结果：收到首帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到首帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step2", "发送流控帧")
        rt.clear()
        send_canmsg(can_channel, msg_30_1, rDiagReqID, dlc=msg_30_1.dlc)
        start_time = sl_time().timestamp()
        payload_first_cf = check_first_cf(rN_CrTimeout_ms, start_time, rt)

        if payload_first_cf is not None:
            TestLog("PASS", "", "期望结果：连续帧第一帧响应。实际结果：连续帧第一帧响应")
        else:
            TestLog("FAIL", "", "期望结果：连续帧第一帧响应。实际结果：超时未收到连续帧第一帧响应")
            check_msg_thread_stop(rt)
            return

        # 从首帧中获取DL
        dl = (payload_10[0] & 0xF) << 8 | payload_10[1]
        expect_cf_counter = math.ceil((dl - 6) / 7)  # 根据DL计算出正常的连续帧的数量

        TestLog("INFO", "Step3", "发送流控帧")
        send_canmsg(can_channel, msg_32, rDiagReqID, dlc=msg_32.dlc)

        sl_time().sleep(expect_cf_counter * rN_CrTimeout_ms)

        # 从接收报文列表中获取所有的连续帧CF  -s
        cf_list = []
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 2:
                cf_list.append(payload)
        # 从接收报文列表中获取所有的连续帧CF  -e

        TestLog("INFO", case_name, f"cf_list={[[hex(i) for i in item] for item in cf_list]}")

        if expect_cf_counter != len(cf_list):
            TestLog("FAIL", "", f"未收到完整的连续帧，期望收到{expect_cf_counter}帧，实际收到{len(cf_list)}帧")
            check_msg_thread_stop(rt)
            return
        else:
            flag = True
            for i in range(len(cf_list) - 1):
                diff = cf_list[i + 1][0] - cf_list[i][0]
                if cf_list[i][0] == 0x2F and cf_list[i + 1][0] != 0x20:
                    flag = False
                    break
                elif diff != 1 and cf_list[i][0] != 0x2F:
                    flag = False
                    break
            if flag is False:
                TestLog("FAIL", "", f"期望结果：收到完整的连续帧。实际结果：收到的连续帧SN不连续，{cf_list=}")
                check_msg_thread_stop(rt)
                return
            else:
                TestLog("PASS", "", f"收到完整的连续帧，期望收到{expect_cf_counter}帧，实际收到{len(cf_list)}帧")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC22_ResponseInterruptedbyUnknownFrame():
    """响应被非预期未知报文干扰"""
    case_name = "响应被非预期未知报文干扰"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_ArTimeout_ms = P.TpInfo.N_ArTimeout  # N_Ar最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        read_DID = P.TpInfo.DID
        read_DID = list(divmod(read_DID, 256))
        sid = 0x22

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        msg = canmsg_create(rDiagReqID, 8, data=[0x03,sid] + read_DID + [0xAA] * 5, fdf=P.TpInfo.CanFDMode,brs=P.TpInfo.CanFDMode)
        msg_30_1 = canmsg_create(rDiagReqID, 8, data=[0x30, 0x00, 0x14] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode,brs=P.TpInfo.CanFDMode)
        msg_unknown = canmsg_create(rDiagReqID, 8, data=[0x40, 0x01, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode,brs=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        sl_time().sleep(rN_ArTimeout_ms)

        # 从接收报文列表中获取首帧FF  -s
        payload_0x10 = None
        recv_list = rt.get_recv_list()
        TestLog("INFO", "", f"{(len(recv_list))=}")
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] == 0x10:
                payload_0x10 = payload
                break
        # 从接收报文列表中获取首帧FF  -e

        if payload_0x10 is not None:
            TestLog("PASS", "", "期望结果：收到首帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到首帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step2", "发送流控帧")
        rt.clear()
        send_canmsg(can_channel, msg_30_1, rDiagReqID, dlc=msg_30_1.dlc)
        start_time = sl_time().timestamp()
        payload_first_cf = check_first_cf(rN_CrTimeout_ms, start_time, rt)

        if payload_first_cf is not None:
            TestLog("PASS", "", "期望结果：连续帧第一帧响应。实际结果：连续帧第一帧响应")
        else:
            TestLog("FAIL", "", "期望结果：连续帧第一帧响应。实际结果：超时未收到连续帧第一帧响应")
            check_msg_thread_stop(rt)
            return

        # 从首帧中获取DL
        dl = (payload_0x10[0] & 0xF) << 8 | payload_0x10[1]
        expect_cf_counter = math.ceil((dl - 6) / 7)  # 根据DL计算出正常的连续帧的数量

        TestLog("INFO", "Step3", "发送未定义的报文")
        send_canmsg(can_channel, msg_unknown, rDiagReqID, dlc=msg_unknown.dlc)

        sl_time().sleep(expect_cf_counter * rN_CrTimeout_ms)

        # 从接收报文列表中获取所有的连续帧CF  -s
        cf_list = []
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 2:
                cf_list.append(payload)
        # 从接收报文列表中获取所有的连续帧CF  -e

        TestLog("INFO", case_name, f"cf_list={[[hex(i) for i in item] for item in cf_list]}")

        if expect_cf_counter != len(cf_list):
            TestLog("FAIL", "", f"未收到完整的连续帧，期望收到{expect_cf_counter}帧，实际收到{len(cf_list)}帧")
            check_msg_thread_stop(rt)
            return
        else:
            flag = True
            for i in range(len(cf_list) - 1):
                diff = cf_list[i + 1][0] - cf_list[i][0]
                if cf_list[i][0] == 0x2F and cf_list[i + 1][0] != 0x20:
                    flag = False
                    break
                elif diff != 1 and cf_list[i][0] != 0x2F:
                    flag = False
                    break
            if flag is False:
                TestLog("FAIL", "", f"期望结果：收到完整的连续帧。实际结果：收到的连续帧SN不连续，{cf_list=}")
                check_msg_thread_stop(rt)
                return
            else:
                TestLog("PASS", "", f"收到完整的连续帧，期望收到{expect_cf_counter}帧，实际收到{len(cf_list)}帧")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC23_RequestInterruptedbySF():
    """请求被单帧报文干扰"""
    case_name = "请求被单帧报文干扰"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_ArTimeout_ms = P.TpInfo.N_ArTimeout  # N_Ar最大时间
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        sid = 0x22  # 服务id
        did = [0x01, 0x02]  # did
        if P.TpInfo.CanFDMode:
            did_data_len = 0xFC  # 总长度
        else:
            did_data_len = 0x1C  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,dlc=P.TpInfo.MaxCanFDDataLengthToDLC)
        msg_sf = canmsg_create(rDiagReqID, 8, data=[0x03, 0x22, 0xF0, 0xF1] + [0xAA] * 4, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,
                                            fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", "发送多帧请求报文，请求响应报文")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        start_time = sl_time().timestamp()
        # 从接收报文列表中获取流控帧FC  -s
        payload_0x30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)

        if payload_0x30 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FC)。实际结果：收到流控帧(FC)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FC)。实际结果：超时未收到流控帧(FC)")
            check_msg_thread_stop(rt)
            return

        stmin_ms = get_fc_st_min_ms(payload_0x30)
        count = 0
        # Step2 ： 发送连续帧第一帧后发送单帧
        TestLog("INFO", "Step2", "发送连续帧第一帧后发送单帧")
        for msg in msg_list[1:]:
            count+=1
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            if count == 1:
                rt.clear()
                send_canmsg(can_channel, msg_sf, rDiagReqID, dlc=msg_sf.dlc)
            sl_time().sleep(stmin_ms)

        sl_time().sleep(rP2_Client_ms * 0.8)

        # 从接收报文列表中获取所有的单帧的响应帧  -s
        sf_response = None
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if 0x62 in payload and 0xF0 in payload and 0xF1 in payload:
                sf_response = payload
        # 从接收报文列表中获取所有的单帧的响应帧  -e

        if sf_response is None:
            TestLog("FAIL", "", f"期望结果：收到单帧的响应报文。实际结果：未收到单帧的响应报文")
            check_msg_thread_stop(rt)
            return
        else:
            TestLog("PASS", "", f"期望结果：收到单帧的响应报文。实际结果：收到单帧的响应报文")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC24_RequestInterruptedbyFF():
    """请求被首帧报文干扰"""
    case_name = "请求被首帧报文干扰"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        sid = 0x34  # 服务id
        did = [0x01, 0x02]  # did
        if P.TpInfo.CanFDMode:
            did_data_len = 0xFC  # 总长度
        else:
            did_data_len = 0x1C  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,dlc=P.TpInfo.MaxCanFDDataLengthToDLC)

        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", "发送多帧请求报文，请求响应报文")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        start_time = sl_time().timestamp()

        # 从接收报文列表中获取流控帧FC  -s
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)

        if payload_30 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FC)。实际结果：收到流控帧(FC)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FC)。实际结果：超时未收到流控帧(FC)")
            check_msg_thread_stop(rt)
            return
        stmin_ms = get_fc_st_min_ms(payload_30)

        TestLog("INFO", "Step2", "发送首帧")
        rt.clear()
        sid = 0x33  # 服务id
        status, msg_list1 = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,dlc=P.TpInfo.MaxCanFDDataLengthToDLC)
        send_canmsg(can_channel, msg_list1[0], rDiagReqID, dlc=msg_list1[0].dlc)
        start_time = sl_time().timestamp()
        # 从接收报文列表中获取流控帧FC  -s
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)

        if payload_30 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FC)。实际结果收到流控帧(FC)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FC)。实际结果超时未收到流控帧(FC)")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step3", "发送连续帧")
        rt.clear()
        for msg in msg_list1[1:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            sl_time().sleep(stmin_ms)

        sl_time().sleep(rP2_Client_ms)

        # 从接收报文列表中获取所有的单帧的响应帧  -s
        sf_response = None
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if 0x7F in payload and 0x33 in payload:
                sf_response = payload
        # 从接收报文列表中获取所有的单帧的响应帧  -e

        if sf_response is None:
            TestLog("FAIL", "", f"期望结果：收到诊断请求的响应。实际结果：未收到诊断请求的响应")
            check_msg_thread_stop(rt)
            return
        else:
            TestLog("PASS", "", f"期望结果：收到诊断请求的响应。实际结果：收到诊断请求的响应")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC25_RequestInterruptedbyFC():
    """请求被流控帧报文干扰"""
    case_name = "请求被流控帧报文干扰"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        sid = 0x33  # 服务id
        did = [0x01, 0x02]  # did
        if P.TpInfo.CanFDMode:
            did_data_len = 0xFC  # 总长度
        else:
            did_data_len = 0x1C  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,dlc=P.TpInfo.MaxCanFDDataLengthToDLC)

        #TODO规范写的是XX
        msg_30_1 = canmsg_create(rDiagReqID, 8, data=[0x30, 0x00, 0x00] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)

        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", "发送多帧请求报文，请求响应报文")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        start_time = sl_time().timestamp()
        # 从接收报文列表中获取流控帧FC  -s
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)

        if payload_30 is not None:
            TestLog("PASS", "", f"期望结果：收到流控帧(FC)。实际结果：收到流控帧(FC)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FC)。实际结果：超时未收到流控帧(FC)")
            check_msg_thread_stop(rt)
            return
        stmin_ms = get_fc_st_min_ms(payload_30)
        TestLog("INFO", "", f"stmin_ms = {stmin_ms}")

        TestLog("INFO", "Step2", "发送流控帧")
        send_canmsg(can_channel, msg_30_1, rDiagReqID, dlc=msg_30_1.dlc)

        TestLog("INFO", "Step3", "发送连续帧")
        for msg in msg_list[1:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            sl_time().sleep(stmin_ms)

        sl_time().sleep(rP2_Client_ms)

        # 从接收报文列表中获取所有的单帧的响应帧  -s
        sf_response = None
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if 0x7F in payload and 0x33 in payload:
                sf_response = payload
        # 从接收报文列表中获取所有的单帧的响应帧  -e

        if sf_response is None:
            TestLog("FAIL", "", f"期望结果：收到诊断请求的响应。实际结果：未收到诊断请求的响应")
            check_msg_thread_stop(rt)
            return
        else:
            TestLog("PASS", "", f"期望结果：收到诊断请求的响应。实际结果：收到诊断请求的响应")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC26_RequestInterruptedbyUnknown():
    """请求被未知报文干扰"""
    case_name = "请求被未知报文干扰"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        sid = 0x33  # 服务id
        did = [0x01, 0x02]  # did
        if P.TpInfo.CanFDMode:
            did_data_len = 0xFC  # 总长度
        else:
            did_data_len = 0x1C  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,dlc=P.TpInfo.MaxCanFDDataLengthToDLC)

        msg_unknown = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLength, data=[0x40, 0x01, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)

        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", "发送多帧请求报文，请求响应报文")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        start_time = sl_time().timestamp()

        # 从接收报文列表中获取流控帧FC  -s
        payload_30 = check_resp_FC_ok(rN_BsTimeout_ms, start_time, rt)
        if payload_30 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FC)。实际结果:收到流控帧(FC)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FC)。实际结果:超时未收到流控帧(FC)")
            check_msg_thread_stop(rt)
            return
        stmin_ms = get_fc_st_min_ms(payload_30)

        TestLog("INFO", "Step2", "发送未知报文")
        send_canmsg(can_channel, msg_unknown, rDiagReqID, dlc=msg_unknown.dlc)

        TestLog("INFO", "Step3", "发送连续帧")
        for msg in msg_list[1:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
            sl_time().sleep(stmin_ms)
        sl_time().sleep(rP2_Client_ms)

        # 从接收报文列表中获取所有的单帧的响应帧  -s
        sf_response = None
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if 0x7F in payload and 0x33 in payload:
                sf_response = payload
        # 从接收报文列表中获取所有的单帧的响应帧  -e

        if sf_response is None:
            TestLog("FAIL", "", f"期望结果：收到诊断请求的响应。实际结果：未收到诊断请求的响应")
            check_msg_thread_stop(rt)
            return
        else:
            TestLog("PASS", "", f"期望结果：收到诊断请求的响应。实际结果：收到诊断请求的响应")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC27_OverflowFC():
    """流控制状态为Overflow"""
    case_name = "流控制状态为Overflow"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        read_DID = P.TpInfo.DID
        sid = 0x22
        read_DID = list(divmod(read_DID, 256))

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        msg = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLength, data=[0x03, sid] +read_DID + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)

        msg_30 = canmsg_create(rDiagReqID, 8, data=[0x32, 0x00, 0x14] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        # 从接收报文列表中获取首帧FF  -s
        payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
        hex_payload = " ".join([f"{b:02X}" for b in payload_10])
        TestLog("info", "", f"payload_10 = [{hex_payload}]")
        if payload_10 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FC)。实际结果:收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FC)。实际结果:超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step2", "发送流控状态为Overflow的流控帧")
        send_canmsg(can_channel, msg_30, rDiagReqID, dlc=msg_30.dlc)
        sl_time().sleep(rN_CrTimeout_ms)

        # 从接收报文列表中获取所有的连续帧CF  -s
        cf_list = []
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 2:
                cf_list.append(payload)
        # 从接收报文列表中获取所有的连续帧CF  -e

        if len(cf_list) > 0:
            TestLog("FAIL", "", f"期望: ECU无响应，实际: 收到了ECU发送的连续帧")
            check_msg_thread_stop(rt)
            return
        else:
            TestLog("PASS", "", f"期望: ECU无响应，实际: 未收到ECU发送的连续帧")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC28_BlockSize():
    """BlockSize测试"""
    case_name = "BlockSize测试"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client
        read_DID = P.TpInfo.DID
        read_DID = list(divmod(read_DID, 256))
        sid = 0x22

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        msg = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLength, data=[0x03, sid] +read_DID + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_30_01 = canmsg_create(rDiagReqID, 8, data=[0x30, 0x01, 0x00] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        msg_31_01 = canmsg_create(rDiagReqID, 8, data=[0x31, 0x01, 0x00] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        # start_time = sl_time().timestamp()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        # 从接收报文列表中获取首帧FF  -s
        payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
        if payload_10 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FC)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FC)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step2", "发送BS=1的流控帧")
        rt.clear()
        send_canmsg(can_channel, msg_30_01, rDiagReqID, dlc=msg_30_01.dlc)
        start_time = sl_time().timestamp()
        payload_first_cf = check_first_cf(rN_CrTimeout_ms, start_time, rt)
        cf_list = []
        if payload_first_cf is not None:
            cf_list.append(payload_first_cf)
            TestLog("PASS", "", "期望结果：连续帧第一帧响应。实际结果：连续帧第一帧响应")
        else:
            TestLog("FAIL", "", "期望结果：连续帧第一帧响应。实际结果：超时未收到连续帧第一帧响应")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step3", "发送流控制状态为Wait，BS=1的流控帧")
        send_canmsg(can_channel, msg_31_01, rDiagReqID, dlc=msg_31_01.dlc)
        sl_time().sleep(10)

        # 从接收报文列表中获取所有的连续帧CF  -s
        cf_list = []
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 2:
                cf_list.append(payload)
        # 此状态存在连续帧第一帧响应
        if len(cf_list) == 1 and cf_list[0][0] == 0x21:
            TestLog("PASS", "", f"期望: 在N_CrTimeout_ms超时前无响应，实际: 未收到响应")
        else:
            TestLog("FAIL", "", f"期望: 在N_CrTimeout_ms超时前无响应，实际: 非期望响应={cf_list}")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step4", "发送流控制状态为Wait，BS=1的流控帧")
        send_canmsg(can_channel, msg_31_01, rDiagReqID, dlc=msg_31_01.dlc)
        sl_time().sleep(10)

        # 从接收报文列表中获取所有的连续帧CF  -s
        cf_list = []
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 2:
                cf_list.append(payload)
        # 从接收报文列表中获取所有的连续帧CF  -e

        if len(cf_list) == 1 and cf_list[0][0] == 0x21:
            TestLog("PASS", "", f"期望: 在N_CrTimeout_ms超时前无响应，实际: 未收到响应")
        else:
            TestLog("FAIL", "", f"期望: 在N_CrTimeout_ms超时前无响应，实际: 非期望响应={cf_list}")
            check_msg_thread_stop(rt)
            return

        TestLog("INFO", "Step5", "发送BS=1的流控帧")
        send_canmsg(can_channel, msg_30_01, rDiagReqID, dlc=msg_30_01.dlc)
        sl_time().sleep(10)

        # 从接收报文列表中获取所有的连续帧CF  -s
        cf_list = []
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 2:
                cf_list.append(payload)
        # 从接收报文列表中获取所有的连续帧CF  -e
        TestLog("INFO", "", f"len(cf_list) = {len(cf_list)}")
        if not (len(cf_list) == 2 and cf_list[0][0] == 0x21 and cf_list[1][0] == 0x22):
            TestLog("FAIL", "", f"期望: 收到连续帧第二帧响应，实际: 非期望响应={cf_list}")
            check_msg_thread_stop(rt)
            return
        else:
            TestLog("PASS", "", f"期望: 收到连续帧第二帧响应，实际: 收到连续帧第二帧响应")

        sl_time().sleep(rP2_Client_ms)
        TestLog("INFO", "Step6", "使BS==2")
        BS = 2
        while True:
            if BS > 0xFF:  # DL最大是-0xFF
                break
            TestLog("INFO", "Step7", "发送请求报文，请求多帧响应报文")
            rt.clear()
            send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

            sl_time().sleep(rP2_Client_ms)

            # 从接收报文列表中获取首帧FF  -s
            payload_10 = None
            recv_list = rt.get_recv_list()
            for i in range(len(recv_list)):
                payload = rt.get_recv_item_payload(i)
                if payload[0] == 0x10:
                    payload_10 = payload
                    break
            # 从接收报文列表中获取首帧FF  -e
            # TestLog("INFO", "", f"payload_10 = {payload_10}")
            if payload_10 is not None:
                TestLog("PASS", "", "期望结果：收到流控帧(FF)。实际结果：收到首帧(FF)")
            else:
                TestLog("FAIL", "", "期望结果：收到流控帧(FF)。实际结果：超时未收到首帧(FF)")
                check_msg_thread_stop(rt)
                return

            ff_dl = ((payload_10[0] & 0x0F) << 8) | payload_10[1]

            TestLog("INFO", "Step8", f"发送BS={BS}的流控帧")

            msg_30_01 = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLength, data=[0x30, BS, 0x00] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
            send_canmsg(can_channel, msg_30_01, rDiagReqID, dlc=msg_30_01.dlc)
            sl_time().sleep(rN_CrTimeout_ms*0.5)

            # 从接收报文列表中获取所有的连续帧CF  -s
            cf_list = []
            recv_list = rt.get_recv_list()
            for i in range(len(recv_list)):
                payload = rt.get_recv_item_payload(i)
                if payload[0] >> 4 == 2:
                    cf_list.append(payload)
            # 从接收报文列表中获取所有的连续帧CF  -e

            if not (len(cf_list) == BS):
                TestLog("FAIL", "", f"期望: 收到连续帧{BS}帧响应，实际: 非期望响应={cf_list}")
                check_msg_thread_stop(rt)
                return
            else:
                TestLog("PASS", "", f"期望: 收到连续帧{BS}帧响应，实际: 收到连续帧{BS}帧响应")

            TestLog("INFO", "", f"len_cf_list = {len(cf_list)}")

            # sn_status = 1
            # for i in range(BS):
            #     expect = 0x21 + (i % 16)  # 0x21…0x2F 循环
            #     if i % 16 == 15:  # 每第 16 帧（0x2F 后）下一帧应是 0x20
            #         expect = 0x20
            #     sn_status &= (cf_list[i][0] == expect)
            #
            # if not (len(cf_list) == BS and sn_status):
            #     TestLog("FAIL", "", f"期望: 收到连续帧{BS}帧响应，实际: 非期望响应={cf_list}")
            #     check_msg_thread_stop(rt)
            #     return
            # else:
            #     TestLog("PASS", "", f"期望: 收到连续帧{BS}帧响应，实际: 收到连续帧{BS}帧响应")

            TestLog("INFO", "Step9", f"令BS=BS+1, 若BS<=(FF_DL-6)/7+2，则跳到步骤7")
            BS *= 2
            if BS <= math.ceil((ff_dl - 6) / 7):
                continue
            else:
                break
            sl_time().sleep(rP2_Client_ms)
        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC29_InvalidOverflowFC():
    """无效流控制状态"""
    case_name = "无效流控制状态"

    # 保存运行过程中的变量
    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        rDiagReqID = P.ECUInfo.DiagReqID_int  # CanTpPhyReqID
        rDiagRespID = P.ECUInfo.DiagRespID_int  # CanTpPhyReqID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout  # N_Cr最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        read_DID = P.TpInfo.DID
        read_DID = list(divmod(read_DID, 256))
        sid = 0x22

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        msg = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLength, data=[0x03, sid] +read_DID + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)

        msg_30 = canmsg_create(rDiagReqID, 8, data=[0x33, 0x00, 0x00] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)

        # 开启线程，用于检测响应报文
        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", "发送请求报文，请求多帧响应报文")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
        # 从接收报文列表中获取首帧FF  -s
        payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
        if payload_10 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        N = 3
        TestLog("INFO", "Step2", f"发送流控状态为N={N}(!=0, 1, 2)的流控帧")
        send_canmsg(can_channel, msg_30, rDiagReqID, dlc=msg_30.dlc)
        sl_time().sleep(rN_CrTimeout_ms)

        # 从接收报文列表中获取所有的连续帧CF  -s
        cf_list = []
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] >> 4 == 2:
                cf_list.append(payload)
        # 从接收报文列表中获取所有的连续帧CF  -e

        if len(cf_list) > 0:
            TestLog("FAIL", "", f"期望: ECU无响应，实际: 收到了ECU发送的连续帧")
            check_msg_thread_stop(rt)
            return
        else:
            TestLog("PASS", "", f"期望: ECU无响应，实际: 未收到ECU发送的连续帧")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()

def test_TG2_TC30_FlowStatusWait():
    """流控状态WAIT测试"""
    case_name = "流控状态WAIT测试"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rP2_Client_ms = P.TpInfo.P2_Client
        rN_CrTimeout_ms = P.TpInfo.N_CrTimeout
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout
        read_DID = P.TpInfo.DID
        read_DID = list(divmod(read_DID, 256))
        sid = 0x22

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        msg = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLength, data=[0x03, sid] + read_DID + [0xAA] * 5,fdf=P.TpInfo.CanFDMode)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", "发送单帧请求，期望收到FF响应")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

        # 等待P2_Client超时时间，检查是否收到FF
        sl_time().sleep(rP2_Client_ms)

        recv_list = rt.get_recv_list()
        ff_received = False
        for item in recv_list:
            payload = item.get("payload", [])
            if payload and (payload[0] & 0xF0) == 0x10:  # FF帧
                ff_received = True
                TestLog("PASS", "", f"期望结果：收到流控帧(FF)。实际结果：收到FF响应: {[hex(b) for b in payload]}")
                break

        if not ff_received:
            TestLog("FAIL", "Step1", "期望结果：收到流控帧(FF)。实际结果：未收到FF响应，测试无法继续")
            check_msg_thread_stop(rt)
            return

        # step2: 发送FC帧(FS=WAIT, 0x31)，期望DUT等待不发送CF
        fc_wait_data = [0x31, 0x00, 0x00] + [0xAA] * 5
        msg = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLength, data=fc_wait_data, fdf=P.TpInfo.CanFDMode)

        TestLog("INFO", "Step2", "发送FC帧(FS=WAIT)，期望DUT等待")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

        # 等待N_Cr超时时间，检查是否有响应（应该无响应）
        sl_time().sleep(rN_CrTimeout_ms)

        recv_list = rt.get_recv_list()
        if len(recv_list) == 0:
            TestLog("PASS", "", "期望结果：ECU未响应。实际结果：ECU未响应")
        else:
            TestLog("FAIL", "", f"期望结果：ECU未响应。实际结果：DUT不应发送CF，但收到: "f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

        # step3: 等待额外时间
        TestLog("INFO","",f"等待超时(等待时间{1.1 * rN_CrTimeout_ms}ms)")
        wait_time = (1.1 * rN_CrTimeout_ms) / 1000.0
        if wait_time > 0:
            sl_time().sleep((wait_time))

        # step4: 发送FC帧(FS=CTS, 0x30)，然后发送SF请求验证通信恢复
        fc_cts_data = [0x30, 0x00, 0x00] + [0xAA] * 5
        msg = canmsg_create(rDiagReqID, 8, data=fc_cts_data, fdf=P.TpInfo.CanFDMode)

        TestLog("INFO", "Step4", "发送FC帧(FS=CTS)")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

        sl_time().sleep(1)  # 等待1ms

        # 发送会话控制请求验证通信
        TestLog("INFO", "Step4", "10 02单帧诊断请求")
        sf_session_data = [0x02, 0x10, 0x02] + [0xAA] * 5
        msg = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLength, data=sf_session_data, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

        sl_time().sleep(rP2_Client_ms)

        recv_list = rt.get_recv_list()
        if len(recv_list) > 0:
            TestLog("PASS", "", "期望结果：DUT正常回复响应，实际结果：DUT正常回复响应")
        else:
            TestLog("FAIL", "", "期望结果：DDUT正常回复响应，实际结果：DUT未回复响应")

        # step5: 发送请求报文，请求多帧响应报文
        TestLog("INFO", "Step5", "发送单帧请求，期望收到FF响应")
        ff_data_msg = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLength, data=[0x03, sid] + read_DID + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        rt.clear()
        send_canmsg(can_channel, ff_data_msg, rDiagReqID, dlc=8)
        start_time = sl_time().timestamp()
        payload_10 = check_resp_FF_ok(rN_BsTimeout_ms, rt)
        TestLog("INFO", "", f"payload_10 = {payload_10}")
        if payload_10 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FF)。实际结果：收到首帧(FF)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FF)。实际结果：超时未收到首帧(FF)")
            check_msg_thread_stop(rt)
            return

        # step6: 发送FC帧，期望DUT无响应
        fc_data = [0x31, 0x00, 0x14] + [0xAA] * 5
        msg = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLength, data=fc_data, fdf=P.TpInfo.CanFDMode)

        TestLog("INFO", "Step6", "发送FC帧(FS=WAIT)，期望DUT等待")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

        # 等待N_Cr超时时间，检查是否有响应（应该无响应）
        sl_time().sleep(rN_CrTimeout_ms * 0.5)

        recv_list = rt.get_recv_list()
        if len(recv_list) == 0:
            TestLog("PASS", "Step6", "期望结果：DUT正确等待，未发送CF。实际结果：DUT正确等待，未发送CF")
        else:
            TestLog("FAIL", "Step6", f"期望结果：DUT正确等待，未发送CF。实际结果：DUT不应发送CF，但收到: "f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

        # Step7： 发送流控制状态为0的流控帧
        fc_wait_data = [0x30, 0x00, 0x00] + [0xAA] * 5
        msg = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLength, data=fc_wait_data, fdf=P.TpInfo.CanFDMode)

        TestLog("INFO", "Step7", "发送FC帧(FS=WAIT)，期望DUT接收到连续帧响应")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

        # 等待N_Cr超时时间，检查是否有响应（应该接收到连续帧响应）
        sl_time().sleep(rN_CrTimeout_ms)

        recv_list = rt.get_recv_list()
        if len(recv_list) > 0:
            TestLog("PASS", "Step7", "期望结果：DUT正确等待，DUT接收到连续帧响应。实际结果：DUT正确等待，DUT接收到连续帧响应")
        else:
            TestLog("FAIL", "Step7", "期望结果：DUT正确等待，DUT接收到连续帧响应。实际结果：DUT未接收到连续帧响应")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()

def test_TG2_TC31_IncorrectFCDLC():
    """流控帧CANDLC不正确测试"""
    case_name = "流控帧CANDLC不正确测试"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        rP2Timeout_ms = P.TpInfo.P2Timeout
        rN_CrTimeout_ms = getattr(P.TpInfo, "CanTp_Cr_ms", 150)
        read_DID = P.TpInfo.DID
        read_DID = list(divmod(read_DID, 256))
        sid = 0x22

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        all_passed = True
        for dlc in range(1, 8):
            # step2: 发送SF请求(0x19 0x0A)，期望收到FF响应
            sf_data = [0x03,sid] + read_DID + [0xAA] * 5
            msg = canmsg_create(rDiagReqID, 8, data=sf_data, fdf=P.TpInfo.CanFDMode)

            TestLog("INFO", f"Step1-DLC{dlc}", "发送单帧请求，期望收到FF响应")
            rt.clear()
            send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

            # 等待P2_Client超时时间
            sl_time().sleep(rP2_Client_ms)

            recv_list = rt.get_recv_list()
            ff_received = False
            for item in recv_list:
                payload = item.get("payload", [])
                if payload and (payload[0] & 0xF0) == 0x10:
                    ff_received = True
                    break

            if not ff_received:
                TestLog("FAIL", f"Step1-DLC{dlc}", "期望结果：收到FF响应。实际结果：未收到FF响应")
                continue

            # step3: 发送FC帧但DLC不正确
            fc_data = [0x30, 0x00, 0x00] + [0xAA] * 5
            msg = canmsg_create(rDiagReqID, dlc=dlc, data=fc_data, fdf=P.TpInfo.CanFDMode)

            TestLog("INFO", f"Step3-DLC{dlc}", f"发送FC帧，CAN DLC={dlc}（不正确）")
            rt.clear()
            send_canmsg(can_channel, msg, rDiagReqID, dlc=dlc)

            # 等待N_Cr超时时间，检查是否有CF响应（应该无响应）
            sl_time().sleep((rN_CrTimeout_ms * 1.1))

            recv_list = rt.get_recv_list()
            if len(recv_list) != 0:
                all_passed = False
                TestLog("FAIL", "", f"DLC={dlc}: 期望结果：DUT不应发送CF。实际结果：DUT不应发送CF，但收到: "f"{[[hex(i) for i in item['payload']] for item in recv_list]}")
            TestLog("PASS","", f"期望结果：{1.1 * rN_CrTimeout_ms}ms内无响应。实际结果：{1.1 * rN_CrTimeout_ms}ms内无响应。")
            # step4: 发送会话控制请求重置状态
            sf_session_data = [0x02, 0x10, 0x02] + [0xAA] * 5
            msg = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLength, data=sf_session_data, fdf=P.TpInfo.CanFDMode)
            send_canmsg(can_channel, msg, rDiagReqID, dlc=8)
            sl_time().sleep(rP2Timeout_ms)

            for i in range(len(recv_list)):
                payload = rt.get_recv_item_payload(i)
                if 0x50 in payload and 0x02 in payload:
                    TestLog("PASS", "", f"期望结果：{1.1 * rN_CrTimeout_ms}ms内,ECU响应50 02。实际结果：期望结果：{1.1 * rN_CrTimeout_ms}ms内,ECU响应50 02")
                else:
                    TestLog("FAIL", "",f"期望结果：{1.1 * rN_CrTimeout_ms}ms内,ECU响应50 02。实际结果：期望结果：{1.1 * rN_CrTimeout_ms}ms内,ECU未响应50 02")

            sl_time().sleep(1000)  # 额外等待

        if all_passed:
            TestLog("PASS", "", "DUT正确地忽略了所有CAN DLC不正确的FC帧")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC32_FunctionalFC():
    """功能寻址流控帧"""
    case_name = "功能寻址流控帧"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rDiagFuncID = P.ECUInfo.DiagFuncID_int
        rP2_Client_ms = P.TpInfo.P2_Client
        rN_CrTimeout_ms = getattr(P.TpInfo, "CanTp_Cr_ms", 150)
        read_DID = P.TpInfo.DID
        read_DID = list(divmod(read_DID, 256))
        sid = 0x22

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}, FuncID={hex(rDiagFuncID)}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # step1: 发送SF请求(0x19 0x0A)，期望收到FF响应
        sf_data = [0x03, sid] + read_DID + [0xAA] * 5
        msg = canmsg_create(rDiagReqID, 8, data=sf_data, fdf=P.TpInfo.CanFDMode)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", "发送单帧请求，期望收到FF响应")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

        # 等待P2_Client超时时间
        sl_time().sleep(rP2_Client_ms)

        recv_list = rt.get_recv_list()
        ff_received = False
        for item in recv_list:
            payload = item.get("payload", [])
            if payload and (payload[0] & 0xF0) == 0x10:
                ff_received = True
                TestLog("PASS", "Step1", f"期望结果：收到流控帧(FF)。实际结果：收到FF响应: {[hex(b) for b in payload]}")
                break

        if not ff_received:
            TestLog("FAIL", "Step1", "期望结果：收到流控帧(FF)。实际结果：未收到FF响应，测试无法继续")
            check_msg_thread_stop(rt)
            return

        # step2: 使用功能寻址ID发送FC帧
        fc_data = [0x30, 0x00, 0x00] + [0xAA] * 5
        msg = canmsg_create(rDiagFuncID, 8, data=fc_data, fdf=P.TpInfo.CanFDMode)

        TestLog("INFO", "Step2", f"使用功能寻址ID(0x{rDiagFuncID:X})发送FC帧")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagFuncID, dlc=8)

        # 等待N_Cr超时时间，检查是否有CF响应（应该无响应，因为FC使用了功能寻址）
        sl_time().sleep(rN_CrTimeout_ms)

        recv_list = rt.get_recv_list()
        if len(recv_list) == 0:
            TestLog("PASS", "", "期望结果：DUT正确地忽略了功能寻址的FC帧，未发送CF。实际结果：DUT正确地忽略了功能寻址的FC帧，未发送CF")
        else:
            TestLog("FAIL", "", f"期望结果：DUT正确地忽略了功能寻址的FC帧，未发送CF。实际结果：DUT不应对功能寻址的FC帧响应，但收到: "f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

        check_msg_thread_stop(rt)

        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC33_IncorrectSFDL():
    """SF帧数据长度不正确测试"""
    case_name = "SF帧数据长度不正确测试"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rN_CrTimeout_ms = getattr(P.TpInfo, "CanTp_Cr_ms", 150)
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        all_passed = True
        if P.TpInfo.CanFDMode:
            for dlc in range(9, 16):
                for n in range(9, 0x38):
                    sf_data_1 = [0x00, n, 0x22, 0xF1, 0x8C] + [0xAA] * 3
                    msg = canmsg_create(rDiagReqID, dlc=dlc, data=sf_data_1, fdf=P.TpInfo.CanFDMode)
                    TestLog("INFO", "Step2", f"发送SF帧，DL={dlc}（无效值）")
                    rt.clear()
                    send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
                    # 等待rP2_Client_ms超时时间
                    sl_time().sleep(rP2_Client_ms)
                    # 检查DUT是否有响应（应忽略无效DL的SF）
                    recv_list = rt.get_recv_list()
                    if len(recv_list) != 0:
                        all_passed = False
                        TestLog("FAIL", "", f"DL={n}: 期望结果：DUT不应响应，实际结果：DUT不应响应，但收到: "f"{[[hex(i) for i in item['payload']] for item in recv_list]}")
            if all_passed:
                TestLog("PASS", "", "DUT正确地忽略了所有DL值无效的SF帧")
        else:
            for n in range(8, 0x10):
                sf_data_1 = [n, 0x22, 0xF1, 0x8C] + [0xAA] * 4
                msg = canmsg_create(rDiagReqID, dlc=8, data=sf_data_1, fdf=P.TpInfo.CanFDMode)
                TestLog("INFO", "Step2", f"发送SF帧，DL=8（无效值）")
                rt.clear()
                send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)
                # 等待rP2_Client_ms超时时间
                sl_time().sleep(rP2_Client_ms)
                # 检查DUT是否有响应（应忽略无效DL的SF）
                recv_list = rt.get_recv_list()
                if len(recv_list) != 0:
                    all_passed = False
                    TestLog("FAIL", "", f"DL={n}: 期望结果：DUT不应响应，实际结果：DUT不应响应，但收到: "f"{[[hex(i) for i in item['payload']] for item in recv_list]}")
            if all_passed:
                TestLog("PASS", "", "DUT正确地忽略了所有DL值无效的SF帧")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC34_IncorrectCANDLCSF():
    """DLC不正确单帧"""
    case_name = "DLC不正确单帧"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rN_CrTimeout_ms = getattr(P.TpInfo, "CanTp_Cr_ms", 150)
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        # step2: 发送SF帧，SF_DL=3，但CAN DLC从1到7（都小于所需的4字节：PCI+3字节数据）
        # 对于SF_DL=3，需要的最小DLC是4（1字节PCI + 3字节数据）
        all_passed = True
        if P.TpInfo.CanFDMode:
            for dlc in range(1, 8):
                sf_data = [0x00, 0x03, 0x22, 0xF1, 0x84] + [0xAA] * 3
                msg = canmsg_create(rDiagReqID, dlc=dlc, data=sf_data, fdf=P.TpInfo.CanFDMode)
                TestLog("INFO", "Step2", f"发送SF帧(SF_DL=3)，CAN DLC={dlc}")
                rt.clear()
                send_canmsg(can_channel, msg, rDiagReqID, dlc=dlc)
                # 等待rP2_Client_ms超时时间
                sl_time().sleep(rP2_Client_ms)
                # 检查DUT是否有响应（DLC不正确时应忽略）
                recv_list = rt.get_recv_list()
                if len(recv_list) != 0:
                    all_passed = False
                    TestLog("FAIL", "",f"DLC={dlc}: 期望结果：DUT不应响应。实际结果：DUT不应响应，但收到: "f"{[[hex(i) for i in item['payload']] for item in recv_list]}")
                # 额外等待以确保稳定
                sl_time().sleep(1000)
            if all_passed:
                TestLog("PASS", "", "DUT正确地忽略了所有CAN DLC不正确的SF帧")
        else:
            for dlc in range(1, 8):
                sf_data = [0x03, 0x22, 0xF1, 0x84] + [0xAA] * 4
                msg = canmsg_create(rDiagReqID, dlc=dlc, data=sf_data, fdf=P.TpInfo.CanFDMode)
                TestLog("INFO", "Step2", f"发送SF帧(SF_DL=3)，CANFD DLC={dlc}")
                rt.clear()
                send_canmsg(can_channel, msg, rDiagReqID, dlc=dlc)
                # 等待rP2_Client_ms超时时间
                sl_time().sleep(rP2_Client_ms)
                # 检查DUT是否有响应（DLC不正确时应忽略）
                recv_list = rt.get_recv_list()
                if len(recv_list) != 0:
                    all_passed = False
                    TestLog("FAIL", "",
                            f"DLC={dlc}: 期望结果：DUT不应响应。实际结果：DUT不应响应，但收到: "f"{[[hex(i) for i in item['payload']] for item in recv_list]}")
                # 额外等待以确保稳定
                sl_time().sleep(1000)
            if all_passed:
                TestLog("PASS", "", "DUT正确地忽略了所有CAN DLC不正确的SF帧")


        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC35_IncorrectFFDL():
    """不正确的FF数据长度"""
    case_name = "不正确的FF数据长度"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rN_BsTimeout_ms = getattr(P.TpInfo, "CanTp_Bs_ms", 150)
        # 获取DLC传输设置，默认为8
        rDLC_Trans = P.TpInfo.MaxCanFDDataLength
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}, DLC_Trans={rDLC_Trans}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        # step2: 发送FF帧，DL值从1到(DLC_Trans-2)
        # 对于DLC=8，FF帧需要DL>=7才有意义（因为SF最多容纳7字节数据）
        all_passed = True
        for n in range(1, rDLC_Trans - 1):
            ff_data = [0x10, n, 0x22] + [i - 4 for i in range(5, rDLC_Trans - 1)]
            msg = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLength, data=ff_data, fdf=P.TpInfo.CanFDMode)

            TestLog("INFO", "Step2", f"发送FF帧，DL={n}（不正确的值）")
            rt.clear()
            send_canmsg(can_channel, msg, rDiagReqID, dlc=rDLC_Trans)

            # 等待rP2_Client_ms超时时间
            sl_time().sleep(rP2_Client_ms)
            # 检查DUT是否有响应（应忽略DL不正确的FF帧）
            recv_list = rt.get_recv_list()
            if len(recv_list) != 0:
                all_passed = False
                TestLog("FAIL", "", f"DL={n}: 期望结果：DUT不应响应。实际结果：DUT不应响应，但收到: "f"{[[hex(i) for i in item['payload']] for item in recv_list]}")
        # 额外等待以确保稳定
        sl_time().sleep(1000)
        if all_passed:
            TestLog("PASS", "", "DUT正确地忽略了所有DL值不正确的FF帧")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC36_IncorrectCANDLCFF():
    """DLC不正确首帧"""
    case_name = "DLC不正确首帧"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rN_BsTimeout_ms = getattr(P.TpInfo, "CanTp_Bs_ms", 150)
        # 获取DLC传输设置，默认为8
        rDLC_Trans = P.TpInfo.MaxCanFDDataLength
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔
        read_DID = P.TpInfo.DID
        read_DID = list(divmod(read_DID, 256))
        sid = 0x22  # 服务id
        did = [0x01, 0x02]  # did
        if P.TpInfo.CanFDMode:
            did_data_len = 0xFC  # 总长度
        else:
            did_data_len = 0x1C  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        # 根据DLC_Trans确定最大测试范围
        if rDLC_Trans == 64:
            n_max = 15
        else:
            n_max = 8


        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        # step2: 发送FF帧(DL=7)，但CAN DLC从1到(n_max-1)（都小于所需值）
        all_passed = True
        for dlc in range(1, n_max):
            TestLog("INFO", "Step2", f"发送FF帧，CAN DLC={dlc}")
            rt.clear()
            status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,dlc=dlc)
            send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=dlc)
            # 等待rP2_Client_ms超时时间
            sl_time().sleep(rP2_Client_ms)
            # 检查DUT是否有响应（DLC不正确时应忽略）
            recv_list = rt.get_recv_list()
            if len(recv_list) != 0:
                all_passed = False
                TestLog("FAIL", "", f"DLC={dlc}: 期望结果：DUT不应响应。实际结果：DUT不应响应，但收到:"f"{[[hex(i) for i in item['payload']] for item in recv_list]}")
        # 额外等待以确保稳定
        sl_time().sleep(1000)
        if all_passed:
            TestLog("PASS", "", "DUT正确地忽略了所有CAN DLC不正确的FF帧")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC37_IncorrectCANDLCCF():
    """DLC不正确连续帧"""
    case_name = "DLC不正确连续帧"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        # 获取DLC传输设置，默认为8
        rDLC_Trans = getattr(P.TpInfo, "Cantp_dlc", 8)
        sid = 0x22  # 服务id
        did = [0x01, 0x02]  # did
        if P.TpInfo.CanFDMode:
            did_data_len = 0x7D  # 总长度
        else:
            did_data_len = 0x0D  # 总长度

        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,dlc=P.TpInfo.MaxCanFDDataLengthToDLC)

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}, DLC_Trans={rDLC_Trans}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        all_passed = True
        for dlc in range(1, 8):
            TestLog("INFO", "Step2", f"发送FF帧()")
            rt.clear()
            send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=rDLC_Trans)

            # 等待rN_BsTimeout_ms超时时间，检查是否收到FC
            sl_time().sleep(rN_BsTimeout_ms*0.5)

            recv_list = rt.get_recv_list()
            fc_received = False
            for item in recv_list:
                payload = item.get("payload", [])
                if payload and (payload[0] & 0xF0) == 0x30:
                    fc_received = True
                    break

            if not fc_received:
                TestLog("FAIL", f"Step2", "未收到流控帧(FC)")
                continue

            # step3: 发送CF帧，但CAN DLC不正确
            cf_data = [0x21] + [i + 5 for i in range(1, 8)]
            msg = canmsg_create(rDiagReqID, dlc=dlc, data=cf_data, fdf=P.TpInfo.CanFDMode)

            TestLog("INFO", "Step3", f"发送CF帧，CAN DLC={dlc}（不正确）")
            rt.clear()
            send_canmsg(can_channel, msg, rDiagReqID, dlc=dlc)

            # 等待rP2_Client_ms超时时间
            sl_time().sleep(rP2_Client_ms)

            # 检查DUT是否有响应（DLC不正确时应忽略CF帧）
            recv_list = rt.get_recv_list()

            for i in range(len(recv_list)):
                payload = rt.get_recv_item_payload(i)
                if payload[1] == 0x7F:
                    all_passed = False
                    TestLog("WARNING", "",f"CF DLC={dlc}: 期望结果：DUT不响应或者回复否定响应。实际结果：DUT回复否定响应，收到: "f"{[[hex(i) for i in item['payload']] for item in recv_list]}")
                else:
                    all_passed = False
                    TestLog("FAIL", "",f"CF DLC={dlc}: 期望结果：DUT不响应或者回复否定响应。实际结果：DUT回复否定响应，收到: "f"{[[hex(i) for i in item['payload']] for item in recv_list]}")
        # 额外等待以确保稳定
        sl_time().sleep(1000)
        if all_passed:
            TestLog("PASS", "", "DUT正确地忽略了所有CAN DLC不正确的CF帧")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC38_UnknownFrame():
    """未知帧类型测试"""
    case_name = "未知帧类型测试"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        # step1: 发送未知帧类型（PCI=0x40，未定义的帧类型）
        # PCI的高4位为帧类型：0=SF, 1=FF, 2=CF, 3=FC，4及以上为未知类型
        unknown_frame_data = [0x40, 0x10, 0x01] + [0xAA] * 5
        msg = canmsg_create(rDiagReqID, 8, data=unknown_frame_data, fdf=P.TpInfo.CanFDMode)

        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", "发送未知帧类型（PCI=0x40）")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        # 等待P2_Client超时时间
        sl_time().sleep((rP2_Client_ms))

        # 检查DUT是否有响应
        recv_list = rt.get_recv_list()
        if len(recv_list) == 0:
            TestLog("PASS", "", "期望结果：DUT正确地忽略了未知帧类型，无响应；实际结果：DUT正确地忽略了未知帧类型，无响应")
        else:
            TestLog("FAIL", "", f"期望结果：DUT正确地忽略了未知帧类型，无响应；实际结果：DUT不应对未知帧类型响应，但收到了响应: "f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC39_FunctionalFF():
    """功能寻址首帧测试"""
    case_name = "功能寻址首帧测试"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rDiagFuncID = P.ECUInfo.DiagFuncID_int  # 功能寻址ID
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        sid = 0x22  # 服务id
        did = [0x01, 0x02]  # did
        if P.TpInfo.CanFDMode:
            did_data_len = 0xFC  # 总长度
        else:
            did_data_len = 0x1C  # 总长度

        status, msg_list = create_ff_cfs(rDiagFuncID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,dlc=P.TpInfo.MaxCanFDDataLengthToDLC)

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}, FuncID={hex(rDiagFuncID)}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        check_msg_thread_start(rt, rDiagFuncID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", f"使用功能寻址ID(0x{rDiagFuncID:X})发送首帧(FF)")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagFuncID, dlc=msg_list[0].dlc)

        # 等待N_Bs超时时间
        sl_time().sleep(rN_BsTimeout_ms * 1.1)

        # 检查DUT是否有响应（功能寻址的FF应被忽略，不应有流控帧响应）
        recv_list = rt.get_recv_list()
        if len(recv_list) == 0:
            TestLog("PASS", "", "期望结果：DUT正确地忽略了功能寻址的首帧，无响应。实际结果：DUT正确地忽略了功能寻址的首帧，无响应")
        else:
            TestLog("FAIL", "", f"期望结果：DUT正确地忽略了功能寻址的首帧，无响应。实际结果：DUT不应对功能寻址的首帧响应，但收到了响应: "f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC40_SingleFF():
    """单独首帧测试"""
    case_name = "单独首帧测试"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rN_BsTimeout_ms = P.TpInfo.N_BsTimeout  # N_Bs最大时间
        rP2Timeout_ms = P.TpInfo.P2Timeout  # P2超时时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        sid = 0x22  # 服务id
        did = [0x01, 0x02]  # did
        if P.TpInfo.CanFDMode:
            did_data_len = 0xFC  # 总长度
        else:
            did_data_len = 0x1C  # 总长度

        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,dlc=P.TpInfo.MaxCanFDDataLengthToDLC)

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}, rDiagReqID={hex(rDiagReqID)}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", "发送首帧(FF)，期望DUT响应流控帧(FC)")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)

        # 等待N_Bs超时时间，检查是否收到流控帧
        sl_time().sleep(rN_BsTimeout_ms)

        # 检查是否收到流控帧(FC)
        fc_received = False
        recv_list = rt.get_recv_list()
        for item in recv_list:
            payload = item.get("payload", [])
            if payload and (payload[0] & 0xF0) == 0x30:  # FC帧的PCI高4位为3
                fc_received = True
                TestLog("PASS", "Step1", f"期望结果：收到流控帧(FC)。实际结果：收到流控帧(FC): {[hex(b) for b in payload]}")
                break

        if not fc_received:
            TestLog("FAIL", "Step1", "期望结果：收到流控帧(FC)。实际结果：未收到流控帧(FC)")
            check_msg_thread_stop(rt)
            return

        # step2: 不发送连续帧，等待并检查DUT是否有其他响应
        TestLog("INFO", "Step2", "不发送连续帧，等待P2超时")
        rt.clear()  # 清除之前的接收记录

        # 等待P2超时时间
        sl_time().sleep(rP2_Client_ms)

        # 检查DUT是否有额外响应（不应有）
        recv_list = rt.get_recv_list()
        if len(recv_list) == 0:
            TestLog("PASS", "", "期望结果：DUT在不发送CF的情况下正确地超时，无额外响应。实际结果：DUT在不发送CF的情况下正确地超时，无额外响应")
        else:
            TestLog("FAIL", "", f"期望结果：DUT在不发送CF的情况下正确地超时，无额外响应。实际结果：DUT不应有额外响应，但收到了: "f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC41_UnexpectedCF():
    """意外连续帧测试"""
    case_name = "意外连续帧测试"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rP2Timeout_ms = P.TpInfo.P2Timeout  # P2超时时间
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        # step1: 直接发送连续帧(CF)，不先发送首帧
        # 连续帧格式: [PCI, data...]，PCI = 0x20 + SN（SN为0-15的随机值）
        sn = random.randint(0, 0x0F)  # 序列号0-15
        cf_data = [0x20 + sn] + [i + 5 for i in range(1, 8)]
        msg = canmsg_create(rDiagReqID, 8, data=cf_data, fdf=P.TpInfo.CanFDMode)

        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", f"直接发送意外的连续帧(CF)，SN={sn}")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        # 等待P2超时时间
        sl_time().sleep(rP2_Client_ms)

        # 检查DUT是否有响应（应忽略意外的CF）
        recv_list = rt.get_recv_list()
        if len(recv_list) == 0:
            TestLog("PASS", "", "DUT正确地忽略了意外的连续帧，无响应")
        else:
            TestLog("FAIL", "", f"DUT不应对意外的连续帧响应，但收到了响应: "f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC42_UnexpectedFC():
    """意外流控帧测试"""
    case_name = "意外流控帧测试"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rN_CrTimeout_ms = getattr(P.TpInfo, "CanTp_Cr_ms", 150)
        rP2_Client_ms = P.TpInfo.P2_Client  # Tester成功发送诊断报文请求之后等待ECU回复诊断响应的时间间隔

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        # step1: 直接发送流控帧(FC)，不先发送首帧
        # 流控帧格式: [PCI, BS, STmin, padding...]，PCI = 0x30 + FS（FS为流状态0-2）
        fs = random.randint(0, 2)  # 流状态: 0=CTS, 1=WAIT, 2=OVFLW
        fc_data = [0x30 + fs, 0x00, 0x00] + [0xAA] * 5
        msg = canmsg_create(rDiagReqID, 8, data=fc_data, fdf=P.TpInfo.CanFDMode)

        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", f"直接发送意外的流控帧(FC)，FS={fs}")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=msg.dlc)

        # 等待N_Cr超时时间
        sl_time().sleep(rP2_Client_ms)

        # 检查DUT是否有响应（应忽略意外的FC）
        recv_list = rt.get_recv_list()
        if len(recv_list) == 0:
            TestLog("PASS", "", "期望结果：DUT正确地忽略了意外的流控帧，无响应。实际结果：DUT正确地忽略了意外的流控帧，无响应")
        else:
            TestLog("FAIL", "", f"期望结果：DUT正确地忽略了意外的流控帧，无响应。实际结果：DUT不应对意外的流控帧响应，但收到了响应: "f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC43_Service3E():
    """3E服务"""
    case_name = "3E服务"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rDiagFuncID = P.ECUInfo.DiagFuncID_int
        rP2_Client_ms = P.TpInfo.P2_Client
        rP2Timeout_ms = P.TpInfo.P2Timeout
        rSTmin_ms = P.TpInfo.STmin_Service
        rDLC_Trans = P.TpInfo.MaxCanFDDataLength

        if rDLC_Trans == 64:
            sid=0x22
            did= [0x01, 0x02]
            did_data_len = 0x7E
            did_data_len_1 = 0xFC
            did_data_len_2 = 0x7D  # CAN FD多帧总长度
        else:
            sid=0x22
            did= [0x01, 0x02]
            did_data_len = 0x0E
            did_data_len_1 = 0x1C
            did_data_len_2 = 0x0D  # 标准CAN多帧总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}, DLC_Trans={rDLC_Trans}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)

        all_passed = True

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        # Step1: 发送FF帧(DL=0x0E)，期望收到FC

        TestLog("INFO", "Step1", f"发送FF帧")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        start_time = sl_time().timestamp()
        payload_30 = check_resp_FC_ok(rP2_Client_ms, start_time, rt)
        # TestLog("INFO", "", f"payload_30 = {payload_30}")
        if payload_30 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FC)。实际结果：收到流控帧(FC)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FC)。实际结果：超时未收到流控帧(FC)")
            check_msg_thread_stop(rt)
            return

        # Step2: 发送CF(0x21) + 3E 80(功能寻址)

        tp_3e_data = [0x02, 0x3E, 0x80] + [0xAA] * 5
        msg_3e = canmsg_create(rDiagFuncID, 8, data=tp_3e_data, fdf=P.TpInfo.CanFDMode)

        TestLog("INFO", "Step2", "发送CF(0x21)后紧接着发送3E 80(功能寻址)")
        rt.clear()

        send_canmsg(can_channel, msg_list[1], rDiagReqID, dlc=msg_list[1].dlc)
        send_canmsg(can_channel, msg_3e, rDiagFuncID, dlc=8)

        sl_time().sleep(rSTmin_ms)

        # Step3: 发送CF(0x22)，期望无响应
        TestLog("INFO", "Step3", "发送CF(0x22)，期望无响应")
        send_canmsg(can_channel, msg_list[2], rDiagReqID, dlc=8)
        sl_time().sleep(rP2_Client_ms)
        recv_list = rt.get_recv_list()
        if len(recv_list) == 0:
            TestLog("PASS", "Step4", f"期望结果：DUT在{rP2Timeout_ms}ms超时前无响应.期望结果：DUT在{rP2Timeout_ms}ms超时前无响应")
        else:
            TestLog("FAIL", "Step4", f"D期望结果：DUT在{rP2Timeout_ms}ms超时前无响应.期望结果：DUT在{rP2Timeout_ms}ms超时前响应 "
                                     f"{[[hex(i) for i in item['payload']] for item in recv_list]}")
            all_passed = False


        # Step4:发送首帧，同时发送功能寻址
        TestLog("INFO", "Step4", "发送后续连续帧同时发送功能寻址的3E 80请求")
        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len_1, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)
        start_time = sl_time().timestamp()
        payload_30 = None
        payload_30 = check_resp_FC_ok(rP2_Client_ms, start_time, rt)
        # TestLog("INFO", "", f"payload_30 = {payload_30}")
        if payload_30 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FC)。实际结果：收到流控帧(FC)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FC)。实际结果：超时未收到流控帧(FC)")
            check_msg_thread_stop(rt)
            return
        
        #Step5:发送后续连续帧同时发送功能寻址的3E 80 + (0x21 0x22)
        for msg in msg_list[1:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=8)
            send_canmsg(can_channel, msg_3e, rDiagFuncID, dlc=8)

        sl_time().sleep(rP2_Client_ms)
        recv_list = rt.get_recv_list()
        fc_received = False
        for item in recv_list:
            payload = item.get("payload", [])
            print(f"{payload = }")
            if payload[1] == 0x7F and payload[2]== 0x22 and payload[3]== 0x13:
                fc_received = True
                break

        if fc_received:
            TestLog("PASS", "Step5", "期望结果：DUT发送响应。实际结果：DUT发送响应")
        else:
            TestLog("FAIL", "Step5", "期望结果：DUT发送响应。实际结果：DUT未发送响应")
            all_passed = False

        # Step6: 发送FF帧，期望收到FC
        ff_data = [0x01, 0x22, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05]
        msg = canmsg_create(rDiagReqID, 8, data=ff_data, fdf=P.TpInfo.CanFDMode)

        TestLog("INFO", "Step6", f"发送FF帧")
        rt.clear()
        send_canmsg(can_channel, msg_3e, rDiagFuncID, dlc=8)
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8)
        
        sl_time().sleep(rP2_Client_ms)

        recv_list = rt.get_recv_list()
        fc_received = False
        for item in recv_list:
            payload = item.get("payload", [])
            if payload[1] == 0x7F and payload[2]== 0x22 and payload[3]== 0x13:
                fc_received = True
                break

        if fc_received:
            TestLog("PASS", "Step6", "期望结果：DUT发送响应。实际结果：DUT发送响应")
        else:
            TestLog("FAIL", "Step6", "期望结果：DUT发送响应。实际结果：DUT未发送响应")
            all_passed = False

        # Step7: 循环发送CF + 3E 80，期望最终收到NRC=0x13
        TestLog("INFO", "Step7", "发送多个CF，每个CF后插入3E 80(功能寻址)")
        rt.clear()
        ff_data = [0x01, 0x22, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05]
        msg = canmsg_create(rDiagReqID, 8, data=ff_data, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8)
        send_canmsg(can_channel, msg_3e, rDiagFuncID, dlc=8)

        sl_time().sleep(rP2_Client_ms)

        recv_list = rt.get_recv_list()
        fc_received = False
        for item in recv_list:
            payload = item.get("payload", [])
            if payload[1] == 0x7F and payload[2]== 0x22 and payload[3]== 0x13:
                fc_received = True
                break

        if fc_received:
            TestLog("PASS", "Step6", "期望结果：DUT发送响应。实际结果：DUT发送响应")
        else:
            TestLog("FAIL", "Step6", "期望结果：DUT发送响应。实际结果：DUT未发送响应")
            all_passed = False
        
        # Step8: 先发3E 80，再发SF(0x01 0x22)
        TestLog("INFO", "Step8", "先发送3E 80(功能寻址)，再发送SF(0x01 0x22)")
        rt.clear()

        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len_2, fdf=P.TpInfo.CanFDMode,
                                         dlc=P.TpInfo.MaxCanFDDataLengthToDLC, brs=P.TpInfo.CanFDMode)

        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=8)

        msg_3e = canmsg_create(rDiagFuncID, 8, data=tp_3e_data, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_3e, rDiagFuncID, dlc=8)

        start_time = sl_time().timestamp()
        payload_30 = None
        payload_30 = check_resp_FC_ok(rP2_Client_ms, start_time, rt)
        if payload_30 is not None:
            TestLog("PASS", "", "期望结果：收到流控帧(FC)。实际结果：收到流控帧(FC)")
        else:
            TestLog("FAIL", "", "期望结果：收到流控帧(FC)。实际结果：超时未收到流控帧(FC)")
            check_msg_thread_stop(rt)
            return      
        
        # Step9: 先发SF(0x01 0x22)，再发3E 80
        TestLog("INFO", "Step9", "先发送SF(0x01 0x22)，再发送3E 80(功能寻址)")
        rt.clear()
        for msg in msg_list[1:]:
            send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

        sl_time().sleep(rP2_Client_ms)

        recv_list = rt.get_recv_list()
        nrc13_received = False
        for item in recv_list:
            payload = item.get("payload", [])
            if payload and len(payload) >= 4:
                if payload[1] == 0x7F and payload[2]== 0x22 and payload[3]== 0x13:
                    nrc13_received = True
                    break

        if nrc13_received:
            TestLog("PASS", "Step9", "期望结果：收到NRC=0x13(incorrectMessageLengthOrInvalidFormat)。实际结果：收到NRC=0x13")
        else:
            TestLog("FAIL", "Step9", "期望结果：收到NRC=0x13(incorrectMessageLengthOrInvalidFormat)。实际结果：未收到预期的NRC=0x13")
            all_passed = False

        if all_passed:
            TestLog("PASS", "", "所有步骤测试通过")
        else:
            TestLog("FAIL", "", "部分步骤测试失败")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC44_Framepadding():
    """报文填充"""
    case_name = "报文填充"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rP2_Client_ms = P.TpInfo.P2_Client
        rN_CrTimeout_ms = getattr(P.TpInfo, "CanTp_Cr_ms", 150)
        pad_byte = getattr(P.TpInfo, "Can_Padding_Byte", 0xAA) & 0xFF
        rDLC_Trans = getattr(P.TpInfo, "Cantp_dlc", 8)
        rDLC_Receive = getattr(P.TpInfo, "Cantp_dlc_receive", 8)
        read_DID = P.TpInfo.DID
        read_DID = list(divmod(read_DID, 256))
        if P.TpInfo.CanFDMode == 0:
            sid = 0x33  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x0D  # 总长度
        else:
            sid = 0x33  # 服务id
            did = [0x01, 0x02]  # did
            did_data_len = 0x7D  # 总长度

        TestLog("-->", "", f"{rVnormal=}, {rTstable=}, pad_byte=0x{pad_byte:02X}")
        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        status, msg_list = create_ff_cfs(rDiagReqID, sid, did, did_data_len, fdf=P.TpInfo.CanFDMode,dlc=P.TpInfo.MaxCanFDDataLengthToDLC)

        check_msg_thread_start(rt, rDiagReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        all_passed = True

        # Step1: 发送FF帧(SID=0x33)，期望收到FC，检查填充字节
        TestLog("INFO", "Step1", f"发送FF帧(SID=0x33，期望收到FC")
        rt.clear()
        send_canmsg(can_channel, msg_list[0], rDiagReqID, dlc=msg_list[0].dlc)

        sl_time().sleep(rP2_Client_ms)

        recv_list = rt.get_recv_list()
        fc_received = False
        fc_padding_ok = True
        for item in recv_list:
            payload = item.get("payload", [])
            if payload and (payload[0] & 0xF0) == 0x30:
                fc_received = True
                # 检查FC帧的填充字节(从byte3开始)
                if len(payload) >= 8:
                    for i in range(3, 8):
                        if payload[i] != pad_byte:
                            fc_padding_ok = False
                            break
                break

        if fc_received:
            if fc_padding_ok:
                TestLog("PASS", "Step1", f"期望结果：收到流控帧(FC)。实际结果：收到FC，填充字节正确(0x{pad_byte:02X})")
            else:
                TestLog("FAIL", "Step1", f"期望结果：收到流控帧(FC)。实际结果：FC填充字节不正确，应为0x{pad_byte:02X}")
                all_passed = False
        else:
            TestLog("FAIL", "Step1", "期望结果：收到流控帧(FC)。实际结果：未收到FC流控帧")
            all_passed = False

        # Step2: 发送CF(0x21)，期望收到NRC=0x11，检查填充字节

        TestLog("INFO", "Step2", "发送CF(0x21)，期望收到NRC=0x11(serviceNotSupported)")
        rt.clear()
        send_canmsg(can_channel, msg_list[1], rDiagReqID, dlc=msg_list[1].dlc)

        sl_time().sleep(rP2_Client_ms)

        recv_list = rt.get_recv_list()
        nrc11_received = False
        nrc_padding_ok = True
        for item in recv_list:
            payload = item.get("payload", [])
            if payload and len(payload) >= 4:
                if payload[1] == 0x7F and payload[2] == 0x33 and payload[3] == 0x11:
                    nrc11_received = True
                    # 检查NRC响应的填充字节(从byte4开始)
                    if len(payload) >= 8:
                        for i in range(4, 8):
                            if payload[i] != pad_byte:
                                nrc_padding_ok = False
                                break
                    break

        if nrc11_received:
            if nrc_padding_ok:
                TestLog("PASS", "Step2", f"期望结果:收到NRC=0x11，填充字节正确(0x{pad_byte:02X})。实际结果:收到NRC=0x11，填充字节正确(0x{pad_byte:02X})")
            else:
                TestLog("FAIL", "Step2", f"期望结果:收到NRC=0x11，填充字节正确(0x{pad_byte:02X})。实际结果:NRC响应填充字节不正确，应为0x{pad_byte:02X}")
                all_passed = False
        else:
            TestLog("FAIL", "Step2", "期望结果:收到NRC=0x11，填充字节正确(0x{pad_byte:02X})。实际结果:未收到预期的NRC=0x11")
            all_passed = False

        # Step3: 发送SF请求(0x19 0x0A)读取DTC，期望收到FF
        sf_data = [0x03, 0x22] + read_DID +[0x00] * 5
        msg = canmsg_create(rDiagReqID, 8, data=sf_data, fdf=P.TpInfo.CanFDMode)

        TestLog("INFO", "Step3", "发送SF请求(19 0A)读取DTC，期望收到FF")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

        ff_payload = None
        ff_payload = check_resp_FF_ok(rP2_Client_ms,rt)
        if ff_payload is None:
            TestLog("FAIL", "Step3", "期望结果：收到流控帧(FF)。实际结果：未收到FF首帧，测试无法继续")
            check_msg_thread_stop(rt)
            return

        total_len = ((ff_payload[0] & 0x0F) << 8) + ff_payload[1]
        TestLog("INFO", "Step3", f"收到FF，总长度={total_len}")

        # Step4: 发送FC，接收所有CF，检查最后一帧的填充字节
        #TODO规范要求为XX
        fc_data = [0x30] + [0x00] * 7
        msg = canmsg_create(rDiagReqID, P.TpInfo.MaxCanFDDataLength, data=fc_data, fdf=P.TpInfo.CanFDMode)

        TestLog("INFO", "Step4", "发送FC，接收所有CF并检查填充字节")
        rt.clear()
        send_canmsg(can_channel, msg, rDiagReqID, dlc=8)

        # 等待足够时间接收所有CF
        sl_time().sleep(rP2_Client_ms * 3)

        recv_list = rt.get_recv_list()
        cf_payloads = []
        for item in recv_list:
            payload = item.get("payload", [])
            if payload and (payload[0] & 0xF0) == 0x20:
                cf_payloads.append(payload)

        if not cf_payloads:
            TestLog("FAIL", "Step4", "期望结果：收到流控帧(CF)。实际结果：未收到任何CF")
            all_passed = False
        else:
            remaining = total_len - (len(ff_payload) - 2)

            # 检查每个CF的填充
            for idx, cf in enumerate(cf_payloads, start=1):
                cf_data_len = len(cf) - 1  # CF中数据字节数(去掉PCI)

                if remaining >= cf_data_len:
                    remaining -= cf_data_len
                else:
                    start_unused = 1 + remaining
                    if start_unused < len(cf):
                        unused_bytes = cf[start_unused:]
                        all_padded = all(b == pad_byte for b in unused_bytes)

                        if all_padded:
                            TestLog("PASS", "Step4",
                                    f"第{idx}帧CF填充正确(0x{pad_byte:02X})")
                        else:
                            TestLog("FAIL", "Step4",
                                    f"第{idx}帧CF填充错误: {[hex(b) for b in unused_bytes]}")
                            all_passed = False
                    remaining = 0

        if all_passed:
            TestLog("PASS", "", "所有帧填充字节检查通过")
        else:
            TestLog("FAIL", "", "部分帧填充字节检查失败")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def test_TG2_TC45_WrongPhyAddressID():
    """错误的物理寻址ID测试"""
    case_name = "错误的物理寻址ID测试"

    rt = RunTimeInfo()
    try:
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        rDiagReqID = P.ECUInfo.DiagReqID_int
        rDiagRespID = P.ECUInfo.DiagRespID_int
        rP2_Client_ms = P.TpInfo.P2_Client
        rN_BsTimeout_ms = getattr(P.TpInfo, "CanTp_Bs_ms", 150)
        rWrongPhyReqID = rDiagReqID + 1

        TestLog("INFO", "", f"{rVnormal=}, {rTstable=}, 正确物理寻址ID=0x{rDiagReqID:X}, 错误物理寻址ID=0x{rWrongPhyReqID:X}")

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        wait_stable_communcation()

        check_msg_thread_start(rt, rWrongPhyReqID, rDiagRespID)
        sl_time().sleep(5)

        # 进入默认会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x01] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入扩展会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x03] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 检查预编程前置条件
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x04, 0x31, 0x01, 0x02, 0x03] + [0xAA] * 3,fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(rP2_Client_ms * 0.8)
        # 进入编程会话
        msg_default_session = canmsg_create(rDiagReqID, 8, data=[0x02, 0x10, 0x02] + [0xAA] * 5, fdf=P.TpInfo.CanFDMode)
        send_canmsg(can_channel, msg_default_session, rDiagReqID, dlc=msg_default_session.dlc)
        sl_time().sleep(1000)

        TestLog("INFO", "Step1", f"使用错误的物理寻址ID(0x{rWrongPhyReqID:X})发送请求报文(02 19 0A)，期望无响应")
        sf_data = [0x02, 0x19, 0x0A] + [0xAA] * 5
        msg = canmsg_create(rWrongPhyReqID, 8, data=sf_data, fdf=P.TpInfo.CanFDMode)

        rt.clear()
        send_canmsg(can_channel, msg, rWrongPhyReqID, dlc=8)

        sl_time().sleep(rN_BsTimeout_ms + rP2_Client_ms)

        recv_list = rt.get_recv_list()
        if len(recv_list) == 0:
            TestLog("PASS", "Step1", "期望结果：无响应。实际结果：DUT正确忽略了错误物理寻址ID的请求，无响应")
        else:
            TestLog("FAIL", "Step1", f"期望结果：无响应。实际结果：DUT不应对错误物理寻址ID的请求响应，但收到了响应: "
                                     f"{[[hex(i) for i in item['payload']] for item in recv_list]}")

        check_msg_thread_stop(rt)
        TestLog("INFO", "", "测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        rt.stop_run()


def get_all_test_cases():
    """获取tp测试用例"""
    current_module = inspect.getmodule(inspect.currentframe())

    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj

    return test_cases