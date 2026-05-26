import time
from typing import Callable
from .utils import TestLog
from slplus.timer import sl_timer
# from sl.sl_lintp import (lin_tp_node_get_info,lin_tp_node_add_on_receive,lin_tp_node_add_send_over
# ,lin_tp_node_add_notify,lin_creat_tp,lin_tp_bind_db,lin_tp_set_sch_diagnistic_if
# ,lin_tp_get_node,lin_tp_node_set_active,lin_tp_send_response,lin_tp_send_request)
# from sl.sl_linsch import lin_creat_sch,lin_sch_get_diagnostic_if
from slplus.linsch import sl_linsch
from slplus.lintp import sl_lintp,sl_lin_ch_sch,sl_lintp_bus
from slplus.lin import sl_lin
import threading
_tp_handel ={}
_tp_notify_call = {}
_tp_notify_call_para = {}
_tp_master_rcv={}
_tp_master_send_overmsg={}
_tp_0X3C_tx_ready={}
_tp_0X3C_tx_ready_time={}
def _master_on_notify(e:dict,usr):  
    global _tp_master_send_overmsg,_tp_master_rcv,_tp_notify_call,_tp_notify_call_para
    tp,ch =usr
    # print(e)
    if e["type"] =="rx":
        # TestLog("INFO","LINTP","Rcv Response NAD:%d len:%d"%(e["nandid"],len(e["para"]["data"])))
        _tp_master_rcv[ch]= (tp,e["nandid"],e["para"]["data"])
    if e["type"] =="tx":
        # TestLog("INFO","LINTP","Send Requset NAD:%d len:%d"%(e["nandid"],len(e["para"]["data"])))
        _tp_master_send_overmsg[(ch,e["nandid"])]= (tp,e["nandid"],e["para"]["data"])
    if e["type"] =="notify":
        if e["para"]["type"]==7:
                _tp_0X3C_tx_ready_time[ch]=time.time()
                _tp_0X3C_tx_ready[ch] = True
        elif _tp_notify_call[ch]!=None:
            _tp_notify_call[ch](tp,e["nandid"],e["para"],_tp_notify_call_para[ch])
    return 0
_tp_slave_rcv={}
_tp_slave_send_overmsg={}
def _slave_on_notify(e:dict,usr):  
    global _tp_slave_send_overmsg,_tp_slave_rcv,_tp_notify_call,_tp_notify_call_para
    tp,ch =usr
    print(e)
    if e["type"] =="rx":
        TestLog("INFO","LINTP","Rcv Requset NAD:%d len:%d"%(e["nandid"],len(e["para"]["data"])))
        _tp_slave_rcv[ch]= (tp,e["nandid"],e["para"]["data"])
    if e["type"] =="tx":
        TestLog("INFO","LINTP","Send Response NAD:%d len:%d"%(e["nandid"],len(e["para"]["data"])))
        _tp_slave_send_overmsg[ch]= (tp,e["nandid"],e["para"]["data"])
    if e["type"] =="notify":
        if _tp_notify_call[ch]!=None:
            _tp_notify_call[ch](tp,e["nandid"],e["para"],_tp_notify_call_para[ch])
    return 0

class _channel_sch_tbl(sl_lin_ch_sch):
    def __init__(self,ch,delay_0x3c,delay_0x3d):
        self.__0x3c_send = False
        self.__0x3d_send = False
        self.__running = True
        self.__delay_0x3c =delay_0x3c
        self.__delay_0x3d =delay_0x3d
        self.__ch = sl_lin(ch)
        self._ch_v=ch
        self.last_3d_time = time.time()
        self.last_3c_time = time.time()
        # self.tsak = threading.Thread(target=self.__thread_run)
        # self.tsak.start()
        def timer_callback(_timer_handle, _user_data):
            if self.__0x3c_send== True:
                if (time.time()-self.last_3c_time) >self.__delay_0x3c:
                    if _tp_0X3C_tx_ready[self._ch_v]==True:
                        ts = _tp_0X3C_tx_ready_time[self._ch_v]
                        _tp_0X3C_tx_ready[self._ch_v] = False
                        self.__ch.output(0X3C)
                        self.last_3c_time = time.time()
                        if(time.time()-ts)>(self.__delay_0x3c *3):
                            TestLog("DEBUG","LINTP",f"发送超时：{time.time()-ts}")
            elif self.__0x3d_send== True:
                if (time.time()-self.last_3d_time) >self.__delay_0x3d:
                    self.__ch.output(0X3D)
                    self.last_3d_time = time.time()

        self.timer = sl_timer(5, timer_callback)
        self.timer.start_timer()
    def __del__(self):
        self.__running = False
    def start_0x3c(self):
        # print("0x3c")
        self.__0x3c_send = True
    def start_0x3d(self):
        # print("0x3d")
        self.__0x3d_send = True
    def stop(self):
        # print("stop")
        self.__0x3c_send = False
        self.__0x3d_send = False
    def __thread_run(self):
        while  self.__running :
            if self.__0x3c_send== True:
                if _tp_0X3C_tx_ready[self._ch_v]==True:
                    ts = _tp_0X3C_tx_ready_time[self._ch_v]
                    _tp_0X3C_tx_ready[self._ch_v] = False
                    self.__ch.output(0X3C)
                    if(time.time()-ts)>(self.__delay_0x3c *3):
                        TestLog("DEBUG","LINTP",f"发送超时：{time.time()-ts}")
                    
                time.sleep(self.__delay_0x3c)
            elif self.__0x3d_send== True:
                self.__ch.output(0X3D)
                time.sleep(self.__delay_0x3d)
            else:
                time.sleep(0.01)


# * @brief: LINTP初始化
# * @param  ch：通道号
# * @param net_work: ldfname
# * @param simulatin_node:测试主节点时仿真的从节点的nandid

def LINTpInitial(ch,is_test_slave,simulatin_node:int,notify_call_back:Callable[[object,int ,dict,any],None]=None,call_back_usr_para = None,req_slot=10,resp_slot=50):
    global _tp_handel,_tp_notify_call,_tp_notify_call_para
    try:
        TestLog("DEBUG","",f"LINTP 创建通道: {ch}")
        tp_config = {
            "stmin":50,
            "as":1000,
            "cr":1000,
            "p2_min":50
        }
        bus = sl_lintp_bus(ch)
        user_sch = _channel_sch_tbl(ch,req_slot/1000,resp_slot/1000)   
        bus.init_channel_schtbl(user_sch)
        _tp_notify_call[ch] = notify_call_back
        _tp_notify_call_para[ch] = call_back_usr_para
        _tp_0X3C_tx_ready[ch] = False
        _tp_0X3C_tx_ready_time[ch]=time.time()
        if ch in _tp_handel.keys():
            if _tp_handel[ch] != None:
                if is_test_slave == False:
                    _tp_handel[ch].active(_slave_on_notify,(_tp_handel[ch],ch))
                else:
                    _tp_handel[ch].active(_master_on_notify,(_tp_handel[ch],ch))
                return
        if is_test_slave == False:
            _tp_handel[ch] = sl_lintp(ch,simulatin_node)
            _tp_handel[ch].apply_config(tp_config)
            _tp_handel[ch].active(_slave_on_notify,(_tp_handel[ch],ch))
        else:
            _tp_handel[ch] = sl_lintp(ch,0)
            _tp_handel[ch].apply_config(tp_config)
            _tp_handel[ch].active(_master_on_notify,(_tp_handel[ch],ch))
        
    except Exception as e:
        TestLog("FAIL","LINTP",f"LINTP初始化错误: {e}")

# * @brief: LINTP关闭
# * @param  ch：通道号
def LINTpDeinit(ch):
    global _tp_handel,_tp_notify_call,_tp_notify_call_para
    try:
        # _tp_handel[ch] = None
        _tp_handel[ch].deactive()
        _tp_notify_call[ch] = None
        _tp_notify_call_para[ch] = None
    except Exception as e:
        TestLog("FAIL","LINTP",f"LINTP关闭错误: {e}")
    
# * @brief: LINTP发送诊断请求
# * @param  ch：通道号
# * @param NAD: 从节点地址  FunRequest = 0X7E
# * @param txBufData: 发送的数据内容
# * @param timeoutValue: 超时时间 (ms 单位)
# * @return: 1成功， 0失败

def SendDiagRequestLINTP(ch,NAD, txBufData, timeoutValue):
    global _tp_master_send_overmsg, _tp_handel
    try:
        timeoutValue = timeoutValue//10
        txBufData  = bytes(txBufData)
        tp = _tp_handel[ch]
        begin_time = time.time()
        if (ch,NAD) in _tp_master_send_overmsg.keys():
            _tp_master_send_overmsg.pop((ch,NAD))
        while True:
            res = tp.send(NAD,txBufData)
            if res==0:
                break
            else:
                time.sleep(0.1)
                if (time.time() - begin_time) > 1:
                    break
            
        if res!=0:
             TestLog("FAIL","",f"LINTP {ch}.{NAD} 发送请求失败:无法发送")
             return 0
        if NAD== 0X7E and len(txBufData)<6:
            TestLog("DEBUG","LINTP 0X7E",f"LINTP {ch}.{NAD} 发送请求成功")
            return 1
        time_count = 0
        while True:
            time.sleep(0.01)
            time_count = time_count +1
            if (ch,NAD) in _tp_master_send_overmsg.keys():
                node,nandid,sendover_data = _tp_master_send_overmsg[(ch,NAD)]
                _tp_master_send_overmsg.pop((ch,NAD))
                if nandid == NAD:
                    if txBufData == sendover_data:
                        TestLog("DEBUG","",f"LINTP {ch}.{NAD} 发送请求成功")
                        return 1
                    else:
                        TestLog("FAIL","",f"LINTP {ch}.{NAD} 发送请求失败:数据异常")
                        return 0
            if time_count>=timeoutValue:  
                break
    except Exception as e:
        TestLog("FAIL","",f"LINTP {ch}.{NAD} 发送请求失败: {e}")
        return 0
    TestLog("FAIL","",f"LINTP {ch}.{NAD} 发送请求失败:发送超时")
    return 0

# * @brief: LINTP诊断回复接收
# * @param  ch：通道号
# * @param  timeoutValue: (ms 单位)超时时间
# * @return: (nandid,data)成功， None失败
def ReceiveDiagResponseLINTP(ch, timeoutValue):
    global _tp_master_rcv
    time_count = 0
    timeoutValue = timeoutValue//10
    try:
        while True:
            time.sleep(0.01)
            time_count = time_count +1
            if ch in _tp_master_rcv.keys():
                node,nandid,data = _tp_master_rcv[ch]
                _tp_master_rcv.pop(ch)
                # TestLog("INFO","LINTP","LINTP %d.%d 接收Response  %x 成功"%(ch,nandid,data[0]))
                return (nandid,data)
            if time_count>=timeoutValue:  
                break
    except Exception as e:
        TestLog("DEBUG","",f"LINTP {ch} 接收Response: {e}")
        return None
    TestLog("DEBUG","",f"LINTP {ch} 接收Response 超时")
    return None

# * @brief: LINTP诊断请求接收
# * @param  ch：通道号
# * @param  timeoutValue: 超时时间 (ms 单位)
# * @return: (nandid,data)成功， None失败
def ReceiveDiagRequestLINTP(ch, timeoutValue):
    global _tp_slave_rcv
    time_count = 0
    timeoutValue = timeoutValue//10
    try:
        while True:
            time.sleep(0.01)
            time_count = time_count +1
            if ch in _tp_slave_rcv.keys():
                node,nandid,data = _tp_slave_rcv[ch]
                _tp_slave_rcv.pop(ch)
                TestLog("DEBUG","LINTP","LINTP %d.%d 接收Request :%x 成功"%(ch,nandid,data[0]))
                return (nandid,data)
            if time_count>=timeoutValue:  
                break
    except Exception as e:
        TestLog("INFO","LINTP",f"LINTP {ch} 接收Request: {e}")
        return None
    TestLog("INFO","LINTP",f"LINTP {ch} 接收Request 超时")
    return None

# * @brief: LINTP发送诊断回复
# * @param  ch：通道号
# * @param NAD: 从节点地址 
# * @param txBufData: 发送的数据内容
# * @param timeoutValue: 超时时间 (ms 单位)
# * @return: 1成功， 0失败

def SendDiagResponseLINTP(ch,NAD, txBufData, timeoutValue):
    global _tp_slave_send_overmsg, _tp_handel
    try:
        timeoutValue = timeoutValue//10
        txBufData  = bytes(txBufData)
        tp = _tp_handel[ch]
        res = tp.send(NAD,txBufData)
        if res!=0:
            TestLog("FAIL","LINTP",f"LINTP {ch}.{NAD} 发送回复失败:无法发送")
            return 0
        if NAD== 0X7E:
            return 1
        time_count = 0
        while True:
            time.sleep(0.01)
            time_count = time_count +1
            if ch in _tp_slave_send_overmsg.keys():
                node,nandid,sendover_data = _tp_slave_send_overmsg[ch]
                _tp_slave_send_overmsg.pop(ch)
                if txBufData == sendover_data and NAD == nandid:
                    TestLog("DEBUG","LINTP",f"LINTP {ch}.{NAD} 发送回复成功")
                    return 1
                else:
                    if nandid!=0X7E:
                        TestLog("FAIL","LINTP",f"LINTP {ch}.{NAD} 发送回复失败:数据异常")
                        return 0
            if time_count>=timeoutValue:  
                break
    except Exception as e:
        TestLog("FAIL","LINTP",f"LINTP {ch}.{NAD} 发送回复失败: {e}")
        return 0
    TestLog("FAIL","LINTP",f"LINTP {ch}.{NAD} 发送回复失败:发送超时")
    return 0
   