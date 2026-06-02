import inspect
import sys
import os
import time
import traceback
from env.config import *

from . import lintp_module

workdir_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(workdir_path)

from uvtest.testlog import TestLog
# from ..lin.lin_module import *
from common.control import TestStart, TestEnd
from uvtest.framework import TestFixture
from .lintp_module import (lin_mormal_tp_init, lin_tp_end, lintp_send_req, lintp_rcv_response,
                           lin_can_init, lin_can_deinit
,  lintp_rcv_request, lintp_send_responese, get_all_tp_rcv_frame_time,
get_all_tp_send_frame_time,lintp_send_req_by_message,lintp_rcv_res_by_message,lin_module_cantp_send_req,lin_ch_by_message)


class LINTPTestFixture(TestFixture):
    def group_setup(self, context=None):
        lin_can_init()

    def group_teardown(self, context=None):
        lin_can_deinit()

    def case_setup(self, context=None):
        if context:
            TestStart(context["test_name"])

    def case_teardown(self, context=None):
        _uds_deinit("")
        TestEnd("")
        TestLog("INFO", "测试结束", "执行测试结束和去初始化")


def uds_deinit():
    pass


_uds_init = lin_mormal_tp_init
_uds_deinit = lin_tp_end


def test_SlaveNode_TPMultiFrameTiming():
    """
    TG1_TC1 从节点传输层时间参数测试（多帧）
    """
    case_name = "从节点传输层时间参数测试（多帧）"
    TestLog("INFO", case_name, "开始测试")

    try:
        if not lin_mormal_tp_init(case_name, False):
            TestLog("FAIL", case_name, "LINTP初始化失败")
            TestEnd(case_name)
            _uds_deinit()
            return
        TestLog("INFO", case_name, "发送0x22 F1 89请求，触发DUT多帧响应")
        send_val = bytes([0x22, 0xF1, 0x89])
        if lintp_send_req(send_val) == 0:
            TestLog("FAIL", case_name, "发送读DID请求失败")
            TestEnd(case_name)
            _uds_deinit()
            return
        response = lintp_rcv_response()
        if response is None:
            TestLog("FAIL", case_name, "未收到DUT响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        _, data = response
        if len(data) <= 6:
            TestLog("FAIL", case_name, "未捕获到期望的多帧帧响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        all_time = get_all_tp_rcv_frame_time()
        limit_ms = lintp_module.default_lin_tp_n_cr * 0.9

        delta_ms = all_time[1] - all_time[0]
        if delta_ms > limit_ms:
            TestLog("FAIL", case_name, f"ΔT={delta_ms:.3f}ms >{limit_ms} (0.9*N_Cr) 无法满足要求")
            TestEnd(case_name)
            _uds_deinit()
            return
        else:
            TestLog("PASS", case_name, f"ΔT={delta_ms:.3f}ms <{limit_ms} (0.9*N_Cr) 满足要求")
            TestEnd(case_name)
            _uds_deinit()
            return
    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
        TestEnd(case_name)
        _uds_deinit()
        return


def test_SlaveNode_TPSingleFrameTiming():
    """TG1_TC2 从节点传输层时间参数测试（单帧）"""
    case_name = "从节点传输层时间参数测试（单帧）"
    TestLog("INFO", case_name, "开始测试")
    try:
        if not lin_mormal_tp_init(case_name, False):
            TestLog("FAIL", case_name, "LINTP初始化失败")
            TestEnd(case_name)
            _uds_deinit()
            return

        # 优先从配置文件读取 N_Cr
        try:
            n_cr_ms = P.TpInfo.N_CrTimeout
        except Exception:
            n_cr_ms = lintp_module.default_lin_tp_n_cr

        test_data = bytes([0x22] + list(range(1, 16)))  # 0x22 0x01 ... 0x0F

        # Step4/5: CF 发送间隔 T1 < 0.9*N_Cr
        t1_normal_s = (n_cr_ms * 0.1) / 1000.0
        TestLog("INFO", case_name,
                f"发送0x22 01 02 ...0f请求，触发DUT响应,间隔{t1_normal_s * 1000:.0f}ms(<0.9*N_Cr={n_cr_ms * 0.9:.0f}ms)")
        lintp_send_req_by_message(test_data, t1_normal_s)
        TestLog("INFO", case_name, "接收响应")
        response = lintp_rcv_res_by_message(0.05, timeout=5)
        if len(response) == 0:
            TestLog("FAIL", case_name, "未收到DUT响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        TestLog("PASS", case_name, "DUT响应 " + hex(int.from_bytes(bytes(response))))

        # Step6: CF 发送间隔 T1 > 0.9*N_Cr
        t1_timeout_s = n_cr_ms / 1000.0
        TestLog("INFO", case_name,
                f"发送0x22 01 02 ...0f请求，触发DUT响应,间隔{t1_timeout_s * 1000:.0f}ms(>0.9*N_Cr={n_cr_ms * 0.9:.0f}ms)")
        lintp_send_req_by_message(test_data, t1_timeout_s)
        TestLog("INFO", case_name, "接收响应")
        response = lintp_rcv_res_by_message(0.05, timeout=5)
        if len(response) == 0:
            TestLog("PASS", case_name, "DUT未响应，满足要求")
        elif len(response) >= 3 and bytes(response[0:2]) == bytes([0x7F, 0x22]):
            TestLog("PASS", case_name, "DUT返回负响应，满足要求 " + hex(int.from_bytes(bytes(response))))
        else:
            TestLog("FAIL", case_name, "收到DUT响应 " + hex(int.from_bytes(bytes(response))))
            TestEnd(case_name)
            _uds_deinit()
            return
        TestLog("PASS", case_name, f"测试通过")
        TestEnd(case_name)
        _uds_deinit()
        return
    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
        TestEnd(case_name)
        _uds_deinit()
        return


def test_SlaveAppTimeTest():
    """[TG1_TC3] 从节点应用层层时间参数测试"""
    step = 1
    try:
        case_name = "从节点应用层层时间参数测试"
        TestLog("INFO", case_name, "开始测试")
        if not lin_mormal_tp_init(case_name, False):
            TestLog("FAIL", case_name, "LINTP初始化失败")
            TestEnd(case_name)
            _uds_deinit()
            return
        TestLog("INFO", case_name, "发送0x10, 0X03请求，触发DUT响应")
        send_val = bytes([0x10, 0X03])
        lintp_rcv_request()  # 清除接收的缓存
        if lintp_send_req(send_val) == 0:
            TestLog("FAIL", case_name, "发送读DID请求失败")
            TestEnd(case_name)
            _uds_deinit()
            return
        response = lintp_rcv_response()
        if response is None:
            TestLog("FAIL", case_name, "未收到DUT响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        _, data = response
        if len(data) < 2:
            TestLog("FAIL", case_name, f"响应异常{data.hex()}")
            TestEnd(case_name)
            _uds_deinit()
            return
        if data[0:2] != bytes([0X50, 0X03]):
            TestLog("FAIL", case_name, "未捕获到期望的多帧帧响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        send_time = get_all_tp_send_frame_time()
        rcv_time = get_all_tp_rcv_frame_time()
        if len(send_time) < 1:
            TestLog("FAIL", case_name, "未捕获到发送时间")
            TestEnd(case_name)
            _uds_deinit()
            return
        if len(rcv_time) < 1:
            TestLog("FAIL", case_name, "未捕获到接收时间")
            TestEnd(case_name)
            _uds_deinit()
            return
        d_time = rcv_time[0] - send_time[0]
        if d_time < 0.5:
            TestLog("PASS", case_name, f"测试成功")
            TestEnd(case_name)
            _uds_deinit()
            return
        else:
            TestLog("FAIL", case_name, f"测试失败,时间不在范围内，{rcv_time[0]} - {send_time[0]} = {d_time}")
            TestEnd(case_name)
            _uds_deinit()
            return
    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")

        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
        TestEnd(case_name)
        _uds_deinit()
        return


def test_SlaveNode_TPReceive():
    """[TG1_TC4] 从节点多帧传输_接收"""
    try:
        case_name = "从节点多帧传输接收测试"
        TestLog("INFO", "从节点多帧传输接收测试", "开始测试")
        if lin_mormal_tp_init("从节点多帧传输接收测试", False) == False:
            TestLog("FAIL", "从节点多帧传输接收测试", "LINTP测试失败")
            _uds_deinit("")
            TestEnd("")
            return
        TestLog("INFO", "Step4", "从节点多帧传输测试，开始接收多帧")
        send_val = bytes(
            [0X22, 0X01, 0X02, 0X03, 0X04, 0X05, 0X06, 0X07, 0X08, 0X09, 0X0A, 0X0B, 0X0C, 0X0D, 0X0E, 0X0F])
        add_msg = bytes([0X7E, 0X02, 0X3E, 0X80, 0XFF, 0XFF, 0XFF, 0XFF])
        lintp_send_req_by_message(send_val, 0.01, add_msg=add_msg)
        response = lintp_rcv_res_by_message(0.05, timeout=5)
        if len(response) == 0:
            TestLog("FAIL", case_name, "未收到DUT响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        TestLog("INFO", "从节点多帧传输接收测试结束", "测试成功")
    except Exception as e:
        TestLog("FAIL", "从节点多帧传输接收测试", f"测试执行出错: {e}")

        TestLog("DEBUG", "从节点多帧传输接收测试", f"详细错误: {traceback.format_exc()}")


def test_SlaveNode_TPSend():
    """[TG1_TC5] 从节点多帧传输_发送"""
    try:
        TestLog("INFO", "从节点多帧传输发送测试", "开始测试")
        # 配置LIN通信为从节点模式

        if lin_mormal_tp_init("从节点多帧传输发送测试", True) == False:
            TestLog("FAIL", "从节点多帧传输发送测试", "LINTP测试失败")
            _uds_deinit("")
            TestEnd("")
            return
        lintp_rcv_request()
        send_val = bytes([0X22, 0XF1, 0X89])
        if lintp_send_req(send_val) == 0:
            TestLog("FAIL", "从节点多帧传输发送测试结束", "测试失败，发送请求异常")
            _uds_deinit("")
            TestEnd("从节点多帧传输发送测试")
            return

        rcv_val = lintp_rcv_response()
        if rcv_val == None:
            TestLog("FAIL", "从节点多帧传输发送测试结束", "测试失败，多帧发送插入功能寻址，未收到物理寻址节点回复")
            TestEnd("")
            return
        nandid, data = rcv_val
        if data[0] != (send_val[0] + 0X40) and data[0, 2] != bytes([0X7F, 0X22]):
            TestLog("FAIL", "从节点多帧传输发送测试", "测试失败，")
            _uds_deinit("")
            TestEnd("")
            return
        TestLog("PASS", "从节点多帧传输发送测试", "测试成功")
    except Exception as e:
        TestLog("FAIL", "从节点多帧传输发送测试", f"测试执行出错: {e}")

        TestLog("DEBUG", "从节点多帧传输发送测试", f"详细错误: {traceback.format_exc()}")


def test_SessionSwitch_Response():
    """[TG1_TC6] 重启及会话模式响应测试(APP)"""
    case_name = "重启及会话模式响应测试(APP)"
    TestLog("INFO", case_name, "开始测试")
    try:
        if not lin_mormal_tp_init(case_name, False):
            TestLog("FAIL", case_name, "LINTP初始化失败")
            TestEnd(case_name)
            _uds_deinit()
            return
        TestLog("INFO", case_name, "发送0X10,0X03请求，触发DUT多帧响应")
        test_data1 = bytes([0X10, 0X03])
        lintp_send_req_by_message(test_data1, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response = lintp_rcv_res_by_message(0.05, timeout=3)
        if len(response) == 0 or bytes(response[0:2]) != bytes([0X50, 0X03]):
            TestLog("FAIL", case_name, "未收到DUT[0X10,0X03]响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        TestLog("INFO", case_name, "发送0X31,0X01,0X02,0X03请求，触发RoutineControl")
        test_data31 = bytes([0X31, 0X01, 0X02, 0X03])
        lintp_send_req_by_message(test_data31, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response = lintp_rcv_res_by_message(0.05, timeout=3)
        if len(response) == 0 or bytes(response[0:2]) != bytes([0X71, 0X01]):
            TestLog("FAIL", case_name, "未收到DUT[0X31,0X01,0X02,0X03]期望响应0x71 0x01")
            TestEnd(case_name)
            _uds_deinit()
            return
        TestLog("INFO", case_name, "发送0X10,0X02请求，触发DUT多帧响应")
        test_data2 = bytes([0X10, 0X02])
        lintp_send_req_by_message(test_data2, 0)
        TestLog("INFO", case_name, "等待450ms")
        time.sleep(0.45)
        TestLog("INFO", case_name, "接收响应")
        response = lintp_rcv_res_by_message(0.05, timeout=3)
        if len(response) == 0:
            TestLog("FAIL", case_name, "未收到DUT[0X10,0X02]响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        if bytes(response[0:2]) != bytes([0X50, 0X02]):
            TestLog("FAIL", case_name, "未收到DUT[0X10,0X02]期望响应0x50 0x02")
            TestEnd(case_name)
            _uds_deinit()
            return

        TestLog("INFO", case_name, "发送0X10,0X01请求，触发DUT多帧响应")
        test_data1 = bytes([0X10, 0X01])
        lintp_send_req_by_message(test_data1, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response = lintp_rcv_res_by_message(0.05, timeout=3)
        if len(response) == 0:
            TestLog("FAIL", case_name, "未收到DUT[0X10,0X03]响应")
            TestEnd(case_name)
            _uds_deinit()
            return

        TestLog("INFO", case_name, "发送0X31,0X01,0X02,0X03请求，触发RoutineControl")
        test_data31 = bytes([0X31, 0X01, 0X02, 0X03])
        lintp_send_req_by_message(test_data31, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response = lintp_rcv_res_by_message(0.05, timeout=3)
        if len(response) == 0:
            TestLog("FAIL", case_name, "未收到DUT[0X31,0X01,0X02,0X03]期望响应")
            TestEnd(case_name)
            _uds_deinit()
            return        



        TestLog("INFO", case_name, "发送0X10,0X03请求，触发DUT多帧响应")
        test_data1 = bytes([0X10, 0X03])
        lintp_send_req_by_message(test_data1, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response = lintp_rcv_res_by_message(0.05, timeout=3)
        if len(response) == 0:
            TestLog("FAIL", case_name, "未收到DUT[0X10,0X03]响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        TestLog("INFO", case_name, "发送0X31,0X01,0X02,0X03请求，触发RoutineControl")
        test_data31 = bytes([0X31, 0X01, 0X02, 0X03])
        lintp_send_req_by_message(test_data31, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response = lintp_rcv_res_by_message(0.05, timeout=3)
        if len(response) == 0 or bytes(response[0:2]) != bytes([0X71, 0X01]):
            TestLog("FAIL", case_name, "未收到DUT[0X31,0X01,0X02,0X03]期望响应0x71 0x01")
            TestEnd(case_name)
            _uds_deinit()
            return
        

        TestLog("INFO", case_name, "发送0X10,0X02请求，触发DUT多帧响应")
        test_data2 = bytes([0X10, 0X02])
        lintp_send_req_by_message(test_data2, 0)
        TestLog("INFO", case_name, "等待550ms")
        time.sleep(0.55)
        TestLog("INFO", case_name, "接收响应")
        response = lintp_rcv_res_by_message(0.05, timeout=3)
        if len(response) == 0:
            TestLog("PASS", case_name, "未收到DUT[0X10,0X02]响应")
        else:
            TestLog("FAIL", case_name, "收到DUT[0X10,0X02]期望响应0x50 0x02")
            TestEnd(case_name)
            _uds_deinit()
            return



        TestLog("INFO", case_name, "发送0X10,0X01请求，触发DUT多帧响应")
        test_data1 = bytes([0X10, 0X01])
        lintp_send_req_by_message(test_data1, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response = lintp_rcv_res_by_message(0.05, timeout=3)
        if len(response) == 0:
            TestLog("FAIL", case_name, "未收到DUT[0X10,0X03]响应")
            TestEnd(case_name)
            _uds_deinit()
            return

        TestLog("INFO", case_name, "发送0X31,0X01,0X02,0X03请求，触发RoutineControl")
        test_data31 = bytes([0X31, 0X01, 0X02, 0X03])
        lintp_send_req_by_message(test_data31, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response = lintp_rcv_res_by_message(0.05, timeout=3)
        if len(response) == 0:
            TestLog("FAIL", case_name, "未收到DUT[0X31,0X01,0X02,0X03]期望响应")
            TestEnd(case_name)
            _uds_deinit()
            return        



        TestLog("INFO", case_name, "发送0X10,0X03请求，触发DUT多帧响应")
        test_data1 = bytes([0X10, 0X03])
        lintp_send_req_by_message(test_data1, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response = lintp_rcv_res_by_message(0.05, timeout=3)
        if len(response) == 0:
            TestLog("FAIL", case_name, "未收到DUT[0X10,0X03]响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        TestLog("INFO", case_name, "发送0X31,0X01,0X02,0X03请求，触发RoutineControl")
        test_data31 = bytes([0X31, 0X01, 0X02, 0X03])
        lintp_send_req_by_message(test_data31, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response = lintp_rcv_res_by_message(0.05, timeout=3)
        if len(response) == 0 or bytes(response[0:2]) != bytes([0X71, 0X01]):
            TestLog("FAIL", case_name, "未收到DUT[0X31,0X01,0X02,0X03]期望响应0x71 0x01")
            TestEnd(case_name)
            _uds_deinit()
            return
        
        TestLog("INFO", case_name, "发送0X11,0X01请求，触发DUT多帧响应")
        test_data2 = bytes([0X11, 0X01])
        lintp_send_req_by_message(test_data2, 0)
        TestLog("INFO", case_name, "等待450ms")
        time.sleep(0.45)
        TestLog("INFO", case_name, "接收响应")
        response = lintp_rcv_res_by_message(0.05, timeout=3)
        if len(response) != 0:
            TestLog("PASS", case_name, "收到DUT[0X11,0X01]正响应")
            TestEnd(case_name)
            _uds_deinit()
            return



        TestLog("INFO", case_name, "发送0X10,0X03请求，触发DUT多帧响应")
        test_data1 = bytes([0X10, 0X03])
        lintp_send_req_by_message(test_data1, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response = lintp_rcv_res_by_message(0.05, timeout=3)
        if len(response) == 0:
            TestLog("FAIL", case_name, "未收到DUT[0X10,0X03]响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        TestLog("INFO", case_name, "发送0X31,0X01,0X02,0X03请求，触发RoutineControl")
        test_data31 = bytes([0X31, 0X01, 0X02, 0X03])
        lintp_send_req_by_message(test_data31, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response = lintp_rcv_res_by_message(0.05, timeout=3)
        if len(response) == 0 or bytes(response[0:2]) != bytes([0X71, 0X01]):
            TestLog("FAIL", case_name, "未收到DUT[0X31,0X01,0X02,0X03]期望响应0x71 0x01")
            TestEnd(case_name)
            _uds_deinit()
            return


        TestLog("INFO", case_name, "发送0X11,0X01请求，触发DUT多帧响应")
        test_data2 = bytes([0X11, 0X01])
        lintp_send_req_by_message(test_data2, 0)
        TestLog("INFO", case_name, "等待550ms")
        time.sleep(0.55)
        TestLog("INFO", case_name, "接收响应")
        response = lintp_rcv_res_by_message(0.05, timeout=3)
        if len(response) == 0:
            TestLog("PASS", case_name, "DUT未响应[0X11,0X01]，满足要求")
        elif len(response) >= 3 and bytes(response[0:2]) == bytes([0x7F, 0x11]):
            TestLog("PASS", case_name, "DUT返回负响应，满足要求 " + hex(int.from_bytes(bytes(response))))
        else:
            TestLog("FAIL", case_name, "收到DUT[0X11,0X01]正响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        TestLog("PASS", case_name, f"测试通过")
        TestEnd(case_name)
        _uds_deinit()
        return
    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
        TestEnd(case_name)
        _uds_deinit()
        return


def test_SlaveDLC():
    """[TG1_TC7] 从节点报文长度测试(APP)"""
    case_name = "从节点报文长度测试(APP)"
    TestLog("INFO", case_name, "开始测试")
    try:
        if not lin_mormal_tp_init(case_name, False):
            TestLog("FAIL", case_name, "LINTP初始化失败")
            TestEnd(case_name)
            _uds_deinit()
            return
        TestLog("INFO", case_name, "发送0X10,0X03请求，触发DUT响应")
        test_data1 = bytes([0X10, 0X03])
        lintp_send_req_by_message(test_data1, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response, frames = lintp_rcv_res_by_message(0.05, timeout=5, frame_check_type=True)
        if len(response) == 0:
            TestLog("FAIL", case_name, "未收到DUT[0X10,0X03]响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        for frame in frames:
            if frame.dlc != 8:
                TestLog("FAIL", case_name, "dut 的 dlc!=8")
                TestEnd(case_name)
                _uds_deinit()
                return

        TestLog("INFO", case_name, "发送22 F1 89请求，触发DUT响应")
        test_data2 = bytes([0X22, 0XF1, 0X89])
        lintp_send_req_by_message(test_data2, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response, frames = lintp_rcv_res_by_message(0.05, timeout=5, frame_check_type=True)
        if len(response) == 0:
            TestLog("FAIL", case_name, "未收到DUT响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        for frame in frames:
            if frame.dlc != 8:
                TestLog("FAIL", case_name, "dut 的 dlc!=8")
                TestEnd(case_name)
                _uds_deinit()
                return

        TestLog("INFO", case_name, "发送31 01 02 03 请求，触发DUT响应")
        test_data2 = bytes([0X31, 0X01, 0X02, 0X03])
        lintp_send_req_by_message(test_data2, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response, frames = lintp_rcv_res_by_message(0.05, timeout=5, frame_check_type=True)
        if len(response) == 0:
            TestLog("FAIL", case_name, "未收到DUT响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        for frame in frames:
            if frame.dlc != 8:
                TestLog("FAIL", case_name, "dut 的 dlc!=8")
                TestEnd(case_name)
                _uds_deinit()
                return

        TestLog("INFO", case_name, "发送10 02请求，触发DUT响应")
        test_data2 = bytes([0X10, 0X02])
        lintp_send_req_by_message(test_data2, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response, frames = lintp_rcv_res_by_message(0.05, timeout=5, frame_check_type=True)
        if len(response) == 0:
            TestLog("FAIL", case_name, "未收到DUT响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        for frame in frames:
            if frame.dlc != 8:
                TestLog("FAIL", case_name, "dut 的 dlc!=8")
                TestEnd(case_name)
                _uds_deinit()
                return

        TestLog("INFO", case_name, "发送22 F1 80请求，触发DUT响应")
        test_data2 = bytes([0X22, 0XF1, 0X80])
        lintp_send_req_by_message(test_data2, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response, frames = lintp_rcv_res_by_message(0.05, timeout=5, frame_check_type=True)
        if len(response) == 0:
            TestLog("FAIL", case_name, "未收到DUT响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        for frame in frames:
            if frame.dlc != 8:
                TestLog("FAIL", case_name, "dut 的 dlc!=8")
                TestEnd(case_name)
                _uds_deinit()
                return

        TestLog("PASS", case_name, f"测试通过")
        TestEnd(case_name)
        _uds_deinit()
        return
    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
        TestEnd(case_name)
        _uds_deinit()
        return


def test_SlavePadding():
    """[TG1_TC8] 从节点报文填充字节测试(APP)"""
    case_name = "从节点报文填充字节测试(APP)"
    TestLog("INFO", case_name, "开始测试")
    try:
        if not lin_mormal_tp_init(case_name, False):
            TestLog("FAIL", case_name, "LINTP初始化失败")
            TestEnd(case_name)
            _uds_deinit()
            return
        TestLog("INFO", case_name, "发送0X10,0X03请求，触发DUT响应")
        test_data1 = bytes([0X10, 0X03])
        lintp_send_req_by_message(test_data1, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response, frames = lintp_rcv_res_by_message(0.05, timeout=5, frame_check_type=True)
        if len(response) == 0:
            TestLog("FAIL", case_name, "未收到DUT[0X10,0X03]响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        for frame in frames:
            if frame.dlc != 8:
                TestLog("FAIL", case_name, "dut 的 dlc!=8")
                TestEnd(case_name)
                _uds_deinit()
                return
        if len(response) <= 6:
            last_frame_padding_len = 6 - len(response)
        else:
            last_frame_padding_len = (len(response) - 5) % 6
        if last_frame_padding_len > 0:
            if bytes(frames[-1].data[8 - last_frame_padding_len:]) != bytes(([0XFF] * last_frame_padding_len)):
                TestLog("FAIL", case_name,
                        "报文填充不是0XFF " + hex(int.from_bytes(bytes(frames[-1].data[8 - last_frame_padding_len:]))))
                TestEnd(case_name)
                _uds_deinit()
                return

        TestLog("INFO", case_name, "发送22 F1 89请求，触发DUT响应")
        test_data2 = bytes([0X22, 0XF1, 0X89])
        lintp_send_req_by_message(test_data2, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response, frames = lintp_rcv_res_by_message(0.05, timeout=5, frame_check_type=True)
        if len(response) == 0:
            TestLog("FAIL", case_name, "未收到DUT响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        for frame in frames:
            if frame.dlc != 8:
                TestLog("FAIL", case_name, "dut 的 dlc!=8")
                TestEnd(case_name)
                _uds_deinit()
                return
        if len(response) <= 6:
            last_frame_padding_len = 6 - len(response)
        else:
            last_frame_padding_len = (len(response) - 5) % 6
        if last_frame_padding_len > 0:
            if bytes(frames[-1].data[8 - last_frame_padding_len:]) != bytes(([0XFF] * last_frame_padding_len)):
                TestLog("FAIL", case_name,
                        "报文填充不是0XFF " + hex(int.from_bytes(bytes(frames[-1].data[8 - last_frame_padding_len:]))))
                TestEnd(case_name)
                _uds_deinit()
                return

        TestLog("INFO", case_name, "发送31 01 02 03 请求，触发DUT响应")
        test_data2 = bytes([0X31, 0X01, 0X02, 0X03])
        lintp_send_req_by_message(test_data2, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response, frames = lintp_rcv_res_by_message(0.05, timeout=5, frame_check_type=True)
        if len(response) == 0:
            TestLog("FAIL", case_name, "未收到DUT响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        for frame in frames:
            if frame.dlc != 8:
                TestLog("FAIL", case_name, "dut 的 dlc!=8")
                TestEnd(case_name)
                _uds_deinit()
                return
        if len(response) <= 6:
            last_frame_padding_len = 6 - len(response)
        else:
            last_frame_padding_len = (len(response) - 5) % 6
        if last_frame_padding_len > 0:
            if bytes(frames[-1].data[8 - last_frame_padding_len:]) != bytes(([0XFF] * last_frame_padding_len)):
                TestLog("FAIL", case_name,
                        "报文填充不是0XFF " + hex(int.from_bytes(bytes(frames[-1].data[8 - last_frame_padding_len:]))))
                TestEnd(case_name)
                _uds_deinit()
                return

        TestLog("INFO", case_name, "发送10 02请求，触发DUT响应")
        test_data2 = bytes([0X10, 0X02])
        lintp_send_req_by_message(test_data2, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response, frames = lintp_rcv_res_by_message(0.05, timeout=5, frame_check_type=True)
        if len(response) == 0:
            TestLog("FAIL", case_name, "未收到DUT响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        for frame in frames:
            if frame.dlc != 8:
                TestLog("FAIL", case_name, "dut 的 dlc!=8")
                TestEnd(case_name)
                _uds_deinit()
                return
        if len(response) <= 6:
            last_frame_padding_len = 6 - len(response)
        else:
            last_frame_padding_len = (len(response) - 5) % 6
        if last_frame_padding_len > 0:
            if bytes(frames[-1].data[8 - last_frame_padding_len:]) != bytes(([0XFF] * last_frame_padding_len)):
                TestLog("FAIL", case_name,
                        "报文填充不是0XFF " + hex(int.from_bytes(bytes(frames[-1].data[8 - last_frame_padding_len:]))))
                TestEnd(case_name)
                _uds_deinit()
                return

        TestLog("INFO", case_name, "发送22 F1 80请求，触发DUT响应")
        test_data2 = bytes([0X22, 0XF1, 0X80])
        lintp_send_req_by_message(test_data2, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response, frames = lintp_rcv_res_by_message(0.05, timeout=5, frame_check_type=True)
        if len(response) == 0:
            TestLog("FAIL", case_name, "未收到DUT响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        for frame in frames:
            if frame.dlc != 8:
                TestLog("FAIL", case_name, "dut 的 dlc!=8")
                TestEnd(case_name)
                _uds_deinit()
                return
        if len(response) <= 6:
            last_frame_padding_len = 6 - len(response)
        else:
            last_frame_padding_len = (len(response) - 5) % 6
        if last_frame_padding_len > 0:
            if bytes(frames[-1].data[8 - last_frame_padding_len:]) != bytes(([0XFF] * last_frame_padding_len)):
                TestLog("FAIL", case_name,
                        "报文填充不是0XFF " + hex(int.from_bytes(bytes(frames[-1].data[8 - last_frame_padding_len:]))))
                TestEnd(case_name)
                _uds_deinit()
                return

        TestLog("PASS", case_name, f"测试通过")
        TestEnd(case_name)
        _uds_deinit()
        return
    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
        TestEnd(case_name)
        _uds_deinit()
        return


def test_SlaveNandID():
    """[TG1_TC9] 从节点NAD遍历测试"""
    case_name = "从节点NAD遍历测试"
    TestLog("INFO", case_name, "开始测试")
    try:
        if not lin_mormal_tp_init(case_name, False):
            TestLog("FAIL", case_name, "LINTP初始化失败")
            TestEnd(case_name)
            _uds_deinit()
            return
        TestLog("INFO", case_name, "发送0X10,0X03请求，触发DUT响应")
        test_data1 = bytes([0X10, 0X03])
        lintp_send_req_by_message(test_data1, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response = lintp_rcv_res_by_message(0.05, timeout=5)
        if len(response) == 0:
            TestLog("FAIL", case_name, "未收到DUT[0X10,0X03]响应")
            TestEnd(case_name)
            _uds_deinit()
            return
            # Step3-4: 使用DUT的NAD发送0x10 0x01，期望DUT正常回复单帧响应
        TestLog("INFO", case_name, "发送0X10,0X01请求(DUT NAD)，触发DUT响应")
        test_data1 = bytes([0X10, 0X01])
        lintp_send_req_by_message(test_data1, 0.01)
        TestLog("INFO", case_name, "接收响应")
        response = lintp_rcv_res_by_message(0.05, timeout=5)
        if len(response) == 0:
            TestLog("FAIL", case_name, "未收到DUT[0X10,0X01]响应")
            TestEnd(case_name)
            _uds_deinit()
            return
        if bytes(response[0:2]) != bytes([0X50, 0X01]):
            TestLog("FAIL", case_name, "未收到DUT[0X10,0X01]期望响应0x50 0x01")
            TestEnd(case_name)
            _uds_deinit()
            return
        from ..tp.lin_test_pre_module import get_other_nand_id
        other_ecu = get_other_nand_id()
        for key, id in other_ecu.items():
            TestLog("INFO", case_name, f"发送0X10,0X01请求(NAD=0x{id:02X})，触发DUT响应")
            test_data1 = bytes([0X10, 0X01])
            lintp_send_req_by_message(test_data1, 0.01, nadid=id)
            TestLog("INFO", case_name, "接收响应")
            response = lintp_rcv_res_by_message(0.05, timeout=5)
            if len(response) == 0:
                TestLog("PASS", case_name, f"NAD=0x{id:02X} 未响应，满足要求")
            elif len(response) >= 3 and bytes(response[0:2]) == bytes([0x7F, 0x10]):
                TestLog("PASS", case_name, f"NAD=0x{id:02X} 返回负响应，满足要求")
            else:
                TestLog("FAIL", case_name, f"NAD=0x{id:02X} 收到DUT正响应")
                TestEnd(case_name)
                _uds_deinit()
                return
        TestLog("PASS", case_name, f"测试通过")
        TestEnd(case_name)
        _uds_deinit()
        return
    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
        TestEnd(case_name)
        _uds_deinit()
        return


def test_MasterNode_TPSend():
    """[TG2_TC1] 主节点多帧传输_发送"""
    try:
        if lin_mormal_tp_init("主节点多帧传输发送测试", True) == False:
            TestLog("FAIL", "主节点多帧传输发送测试", "LINTP测试失败")
            _uds_deinit("")
            TestEnd("")
            return
            # 通过CAN 设置ECU发送多帧LINTP报文
        TestLog("INFO", "Step4", "接收物理地址报文")
        print("########################主机准备发送多包，等待时间10S,或者添加设置接口")
        val = lintp_rcv_request(timeout=10000, func_tp_send=2)
        if val == None:
            TestLog("INFO", "主节点多帧传输发送测试", "未收到主节点数据，确认连接")
        else:
            nadid, data = val
            if nadid != 0X7E:
                TestLog("INFO", "Step5", "未接收到功能寻址单帧")
                _uds_deinit("")
                TestEnd("")
                return
        val = lintp_rcv_request(timeout=1000)
        if val == None:
            TestLog("INFO", "主节点多帧传输发送测试", "未收到主节点数据，确认连接")
            _uds_deinit("")
            TestEnd("")
            return
        else:
            TestLog("INFO", "Step5", "接收到物理寻址")
            nadid, data = val
            if nadid != 0X7E:
                TestLog("INFO", "主节点多帧传输发送测试", "测试成功")
                _uds_deinit("")
                TestEnd("")
                return
            else:
                TestLog("INFO", "主节点多帧传输发送测试", "测试失败")
                _uds_deinit("")
                TestEnd("")
                return
        TestLog("INFO", "主节点多帧传输发送测试", "测试成功")
    except Exception as e:
        TestLog("FAIL", "从节点多帧传输接收测试", f"测试执行出错: {e}")

        TestLog("DEBUG", "从节点多帧传输接收测试", f"详细错误: {traceback.format_exc()}")


def test_MasterNode_TPReceive():
    """[TG2_TC2] 主节点多帧传输_接收"""
    try:
        if lin_mormal_tp_init("主节点多帧传输接收测试", True) == False:
            TestLog("FAIL", "主节点多帧传输接收测试", "LINTP测试失败")
            _uds_deinit("")
            TestEnd("")
            return
        TestLog("INFO", "Step4", "接收物理地址报文")

        # can_to_lin(bytes([0XF1,0X89]))
        print("########################主机准备发送单包，等待时间10S")
        val = lintp_rcv_request(timeout=10000, func_tp_send=1)
        if val == None:
            TestLog("INFO", "主节点多帧传输接收测试", "未收到主节点数据，确认连接")
        else:
            nadid, data = val
            TestLog("INFO", "Step5", "接收到did请求寻址单帧")
            # 需要确认发送数据
            send_data = [1] * (11 + 3)
            send_data[0] = data[0] + 0x40
            send_data[1] = data[1]
            send_data[2] = data[2]
            val = lintp_send_responese(send_data, rcv_0x7e_flg=True)
            if val == 1:
                TestLog("INFO", "主节点多帧传输接收测试", "测试成功")
                _uds_deinit("")
                TestEnd("")
                return
            else:
                TestLog("INFO", "主节点多帧传输接收测试", "测试失败")
                _uds_deinit("")
                TestEnd("")
                return

    except Exception as e:
        TestLog("FAIL", "从节点多帧传输接收测试", f"测试执行出错: {e}")

        TestLog("DEBUG", "从节点多帧传输接收测试", f"详细错误: {traceback.format_exc()}")


def test_Diagnostic_model_Control():
    """[TG2_TC3] 诊断模式切换测试"""
    case_name = "诊断模式切换测试"
    TestLog("INFO", case_name, "开始测试")
    try:
        if not lin_mormal_tp_init(case_name, False):
            TestLog("FAIL", case_name, "LINTP初始化失败")
            TestEnd(case_name)
            _uds_deinit()
            return
        TestLog("INFO", case_name, "进入扩展会话")
        test_data1 = bytes([0X10, 0X03])
        lin_module_cantp_send_req(test_data1)
        time.sleep(0.5)
        TestLog("INFO", case_name, "禁止主节点通讯")
        test_data1 = bytes([0X28, 0X03, 0X01])
        lin_module_cantp_send_req(test_data1)
        time.sleep(0.3)
        TestLog("INFO", case_name, "检查是否还有报文")
        msgs = lin_ch_by_message(timeout=1)
        if len(msgs) > 0:
            TestLog("FAIL", case_name, "收到报文数量" + str(len(msgs)))
        else:
            TestLog("PASS", case_name, "未收到报文数量")

        def send_once_func(flg: list):
            if send_once_flg[0] == 0:
                TestLog("INFO", case_name, "进入默认会话")
                test_data1 = bytes([0X10, 0X01])
                lin_module_cantp_send_req(test_data1)
                send_once_flg[0] += 1

        send_once_flg = [0]
        msgs = lin_ch_by_message(timeout=1, func_in_rcv_time=send_once_func, args=send_once_flg)
        TestLog("INFO", case_name, "检查0X3C 和 0X3D 的间隔")
        t_0x3c = 0
        t_0x3d = 0
        for (id, time_val, msg) in msgs:
            if id == 0X3C:
                t_0x3c = time_val
            if id == 0X3D and msg.err_type == 0:
                t_0x3d = time_val
        t_d = t_0x3d - t_0x3c
        if t_d > 0.011 or t_d < 0.009:
            TestLog("FAIL", case_name, f"{t_0x3d} - {t_0x3c}")
        else:
            TestLog("PASS", case_name, f"{t_0x3d}  {t_0x3c}")

        TestLog("INFO", case_name, "恢复主节点通讯")
        test_data1 = bytes([0X28, 0X00, 0X01])
        lin_module_cantp_send_req(test_data1)
        time.sleep(0.3)
        TestLog("INFO", case_name, "检查主节点有报文")
        msgs = lin_ch_by_message(timeout=1)
        if len(msgs) == 0:
            TestLog("FAIL", case_name, "未收到报文" + str(len(msgs)))
        else:
            TestLog("PASS", case_name, "收到报文数量" + str(len(msgs)))

        send_once_flg = [0]
        msgs = lin_ch_by_message(timeout=1, func_in_rcv_time=send_once_func, args=send_once_flg)
        TestLog("INFO", case_name, "检查0X3C 和 0X3D 的间隔")
        t_0x3c = 0
        t_0x3d = 0
        for (id, time_val, msg) in msgs:
            if id == 0X3C:
                t_0x3c = time_val
            if id == 0X3D and msg.err_type == 0:
                t_0x3d = time_val
        t_d = t_0x3d - t_0x3c
        if t_d < 11:
            TestLog("FAIL", case_name, f"{t_0x3d} - {t_0x3c}")
        else:
            TestLog("PASS", case_name, f"{t_0x3d}  {t_0x3c}")

        TestLog("PASS", case_name, f"测试通过")
        TestEnd(case_name)
        _uds_deinit()
        return
    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
        TestEnd(case_name)
        _uds_deinit()
        return


def get_all_test_cases():
    """获取tp测试用例"""
    current_module = inspect.getmodule(inspect.currentframe())

    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj

    return test_cases
