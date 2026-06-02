from  common.lintp import (LINTpInitial,LINTpDeinit,SendDiagRequestLINTP,ReceiveDiagResponseLINTP,ReceiveDiagRequestLINTP,SendDiagResponseLINTP)
from env.config import DEFAULT_LIN_CHANNEL,DEFAULT_CAN_CHANNELS
from uvtest.testlog import TestLog
from common.context import ctx
from slplus.lin import sl_lin, sl_linmsg, frame_mode_enum
from .lin_test_pre_module import lin_initialization,ActivateDut,lin_deinitialization,stop_lin_simulation,get_nand_id
import os
import sys
workdir_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(workdir_path)
from slplus.lintp import sl_lintp
from slplus.linsch import sl_linsch
import threading
import time
default_lin_Simulation_nand = 1
default_lin_request_nand = 1 
default_lin_tp_n_cr  =1000
__default_CanTpFunReqID =0X7DF
__default_CanTpReqID =0X7E0

_test_rcv_0x7e_flg = 0
__lin_uds_s =None

__all_tp_rcvmsg_time =[]
__all_tp_sendmsg_time =[]
__send_func_req =False
def __lintp_notify(tp:sl_lintp,nandid,ev,user):
    global __default_CanTpFunReqID,__all_tp_rcvmsg_time,__send_func_req,__all_tp_sendmsg_time
    try:
        ch= user
        if tp.nandid() == 0:
            if nandid!=0X7E:
                if ev["type"] == 1:
                    TestLog("INFO", "收到单帧", "")
                    __all_tp_rcvmsg_time.append((time.time(),ev["type"]))
                if ev["type"] == 2:#接收多帧时发送功能寻址
                    __all_tp_rcvmsg_time.append((time.time(),ev["type"]))
                    if __send_func_req==True:
                        txBufData = [0X3E,0x80]#need add udsframe
                        TestLog("INFO", "收到首帧", "发送功能寻址")
                        SendDiagRequestLINTP(ch,0X7E,bytes(txBufData),1000)
                if ev["type"] == 3:
                    __all_tp_rcvmsg_time.append((time.time(),ev["type"]))
                    TestLog("INFO", "收到连续帧", "")
                if ev["type"] == 4:
                    TestLog("INFO", "发送单帧", "")
                    __all_tp_sendmsg_time.append((time.time(),ev["type"]))
                if ev["type"] == 5:#发送多帧时发送功能寻址
                    TestLog("INFO", "发送首帧", "发送功能寻址")
                    __all_tp_sendmsg_time.append((time.time(),ev["type"]))
                    if __send_func_req==True:
                        txBufData = [0X3E,0x80]#need add udsframe
                        SendDiagRequestLINTP(ch,0X7E,bytes(txBufData),1000)
                if ev["type"] == 6:
                    TestLog("INFO", "发送连续帧", "")
                    __all_tp_sendmsg_time.append((time.time(),ev["type"]))
        else:
            if nandid!=0X7E:  
              if ev["type"] == 2:#接收多帧时发送功能寻址
                    # txBufData = [0X3E,0x80]#need add udsframe
                    payload = bytes([0X02,0X3E,0x80])
                    can_ = sl_can(1)
                    canfd_msg = sl_canmsg(id=__default_CanTpFunReqID, is_fd=True, dlc=8, payload=payload)
                    TestLog("INFO", "CANTP", "单发送报文")
                    can_.send_canmsg(canfd_msg)
                #   SendCAN3ERequest(0x7df,sECUSettings[gECUIndex].DiagCANChannelNum,sECUSettings[gECUIndex].WakeupMsgType)
                    pass 
              if ev["type"] == 4:#发送多帧时发送功能寻址
                #   txBufData = [0X3E,0x80]#need add udsframe
                    payload = bytes([0X02,0X3E,0x80])
                    can_ = sl_can(1)
                    canfd_msg = sl_canmsg(id=__default_CanTpFunReqID, is_fd=True, dlc=8, payload=payload)
                    TestLog("INFO", "CANTP", "单发送报文")
                    can_.send_canmsg(canfd_msg)
                #   SendCAN3ERequest(0x7df,sECUSettings[gECUIndex].DiagCANChannelNum,sECUSettings[gECUIndex].WakeupMsgType)
                #   pass

    except Exception as e:
        print(f"LIN消息处理错误: {e}")

def _lintp_rcv_task(ch = None):
    global _test_rcv_0x7e_flg
    if ch == None:
        ch = DEFAULT_LIN_CHANNEL
    while _test_rcv_0x7e_flg == 0:
        val  = ReceiveDiagRequestLINTP(ch,1000)
        if val !=None:
            nandid,data = val
            if nandid  == 0X7E:
                _test_rcv_0x7e_flg = 1
            break

def lintp_send_responese(data,rcv_0x7e_flg,nandid = None,ch = None,timeout=1):
   global _test_rcv_0x7e_flg
   if ch == None:
        ch = DEFAULT_LIN_CHANNEL
   if nandid == None:
       nandid = default_lin_request_nand
   if rcv_0x7e_flg ==True :
     rcv_th =  threading.Thread(target=_lintp_rcv_task)
     _test_rcv_0x7e_flg = 0
     rcv_th.start()
   val = SendDiagResponseLINTP(ch,nandid,data,timeout*1000)
   if rcv_0x7e_flg ==True :
     if val == 1 and _test_rcv_0x7e_flg ==1:
         val = 1
     else:
        val = 0 
     _test_rcv_0x7e_flg = 1
     rcv_th.join()
   return val

def lintp_rcv_response(ch=None,Timeout=5):
    if ch == None:
        ch = DEFAULT_LIN_CHANNEL
    return ReceiveDiagResponseLINTP(ch,Timeout*1000)


from slplus.can import sl_can, sl_canmsg


def lin_module_cantp_send_req(data:bytes):
    global __default_CanTpReqID
    time.sleep(0.1)
    def __tpmsg_to_pdu_msg(data:bytes):
        mesgs = []
        data =  list(data)
        if len(data)> 7:
            msg = [(0X10+ (len(data)>>8)),len(data) &0XFF]
            msg = msg + data[0:6]
            data = data[6:]
            mesgs.append(msg)
            id = 1
            while len(data)> 0:
                if len(data) >=7:
                    msg = [(0X20+ id)]
                    msg = msg + data[0:7]
                    data = data[7:]
                    mesgs.append(msg)
                else:
                    msg = [(0X20+ id)]
                    msg = msg + data +[0XFF]*(7-len(data))
                    data = []
                    mesgs.append(msg)
                id += 1
                if id>=16:
                    id = 0
        else:
            msg = [len(data)] + data + (7-len(data))*[0XFF]
            mesgs.append(bytes(msg))
        return mesgs  
    msgs = __tpmsg_to_pdu_msg(data) 
    can_ = sl_can(DEFAULT_CAN_CHANNELS[0])
    for msg in msgs:   
        can_msg = sl_canmsg(id=__default_CanTpReqID, is_fd=False, dlc=8, payload=bytes(msg))
        can_.send_canmsg(can_msg)
        time.sleep(0.01)
  

def __lintp_send_req(func_tp_send):
    global __default_CanTpReqID
    time.sleep(0.1)
    if func_tp_send ==1:
        payload = bytes([0X03,0X22,0XF1,0X89,0xFF,0xFF,0xFF,0xFF])
        can_ = sl_can(DEFAULT_CAN_CHANNELS[0])
        canfd_msg = sl_canmsg(id=__default_CanTpReqID, is_fd=False, dlc=8, payload=payload)
        TestLog("INFO", "CANTP", "单发送报文")
        can_.send_canmsg(canfd_msg)
    else:
        payload = bytes([0x10,0x10,0x22,0x01,0x02,0x03,0x04,0x05])
        can_ = sl_can(DEFAULT_CAN_CHANNELS[0])
        canfd_msg = sl_canmsg(id=__default_CanTpReqID, is_fd=False, dlc=8, payload=payload)
        TestLog("INFO", "CANTP", "首帧发送报文")
        can_.send_canmsg(canfd_msg)
        time.sleep(0.01)
        payload = bytes([0x21,0x06,0x07,0x08,0x09,0x0A,0x0B,0x0C])
        canfd_msg = sl_canmsg(id=__default_CanTpReqID, is_fd=False, dlc=8, payload=payload)
        TestLog("INFO", "CAN测试设置", "连续帧1发送报文")
        can_.send_canmsg(canfd_msg)
        time.sleep(0.01)
        payload = bytes([0x22,0x0D,0x0E,0x0F,0xFF,0xFF,0xFF,0xFF])
        canfd_msg = sl_canmsg(id=__default_CanTpReqID, is_fd=False, dlc=8, payload=payload)
        TestLog("INFO", "CAN测试设置", "连续帧2发送报文")
        can_.send_canmsg(canfd_msg)

def lintp_rcv_request(ch=None,timeout=1000,func_tp_send=0):
    if ch == None:
        ch = DEFAULT_LIN_CHANNEL
    if func_tp_send!=0:
        send_th =  threading.Thread(target=__lintp_send_req,args=[func_tp_send])
        send_th.start()
    val =  ReceiveDiagRequestLINTP(ch,timeout)
    if func_tp_send!=0:
        send_th.join()
    return val

def lintp_send_req(msg:bytes,lin_channel=None,nadid=None,func_flg = False,timeout=1000):
    global __all_tp_rcvmsg_time,__all_tp_sendmsg_time,default_lin_request_nand
    if func_flg ==True:
        nadid = 0X7E
    else:
        if nadid == None:
            nadid = default_lin_request_nand
    if lin_channel == None:
        lin_channel = DEFAULT_LIN_CHANNEL
    __all_tp_rcvmsg_time = []
    __all_tp_sendmsg_time= []
    return SendDiagRequestLINTP(lin_channel,nadid,msg,timeout)

def lin_tp_initialization(channel=None,sim_nadid = None,net_work =None,test_slave_flg=True,funcrequest_in_phyresponse_flg=False):
    """
    LINTP测试初始化函数
    """
    global __send_func_req
    try:
        TestLog("DEBUG", "", "开始LINTP协议相关初始化")
        if sim_nadid == None:
            sim_nadid = default_lin_Simulation_nand
        if channel==None:
            channel = DEFAULT_LIN_CHANNEL
        if net_work is None:
            net_work = ctx.lin.get_info('ldf_network_name')
        if test_slave_flg is True:
            ctx.lin.set_info('lin_mode', "master")
        else:
            ctx.lin.set_info('lin_mode', "slave")
        LINTpInitial(channel,test_slave_flg,sim_nadid,__lintp_notify,channel)
           
        __send_func_req= funcrequest_in_phyresponse_flg
        return 1

    except Exception as e:
        TestLog("FAIL", "LINTP测试初始化函数", f"初始化失败: {e}")
        import traceback
        TestLog("DEBUG", "LINTP测试初始化函数", f"详细错误: {traceback.format_exc()}")
        return 0
    

def get_all_tp_rcv_frame_time():
    global __all_tp_rcvmsg_time
    time_all = []
    for msg_time,msgtype  in __all_tp_rcvmsg_time:
        time_all.append(msg_time)
    return    time_all


def get_all_tp_send_frame_time():
    global __all_tp_sendmsg_time
    time_all = []
    for msg_time,msgtype  in __all_tp_sendmsg_time:
        time_all.append(msg_time)
    return     time_all

def get_all_tp_rcv_frame_t_time():
    global __all_tp_rcvmsg_time
    return __all_tp_rcvmsg_time

def get_all_tp_send_frame_t_time():
    global __all_tp_sendmsg_time
    return __all_tp_sendmsg_time


def lin_mormal_tp_init(test_name:str="",func_req_in_phy:bool =False):
    from common.params import P
    sim_act = P.LINInfo.SimulationActivate
    ctx.lin.set_info('lin_schedule_channel', DEFAULT_LIN_CHANNEL)
    ret = 0

    if sim_act==1:
        lin_tp_initialization(test_slave_flg=False,funcrequest_in_phyresponse_flg=__send_func_req)
    else:
        lin_tp_initialization(funcrequest_in_phyresponse_flg=__send_func_req) 
    TestLog("INFO", "Step1", "激活DUT")
    from .lin_test_pre_module import get_test_case_mode
    if (get_test_case_mode() == "slave"):
       ret =  ActivateDut(0, 5)
    else:
       ret =   ActivateDut(1, 5)
    if ret != 0:
        TestLog("FAIL", test_name, "DUT激活失败，结束测试")
        return False
    sch = sl_linsch(DEFAULT_LIN_CHANNEL)
    sch.stop()
    return True


def lin_tp_end(test_name:str=""):
     LINTpDeinit(DEFAULT_LIN_CHANNEL)    
     stop_lin_simulation()
    #  lin_deinitialization()
    #  cantp_test_case_end()
     global __lin_uds_s
     __lin_uds_s = None
     time.sleep(2)

def lintp_sys_global_val_set():
    global __default_CanTpFunReqID,__default_CanTpReqID ,default_lin_Simulation_nand ,default_lin_request_nand
    from common.params import P
    __default_CanTpReqID = P.TpInfo.CAN_LIN_PhyReqID_int
    __default_CanTpFunReqID = P.TpInfo.CAN_LIN_FuncReqID_int

    from env.config import Model, LDF_FILES
    indices = list(LDF_FILES.keys())
    databases = [Model.ldf(idx) for idx in indices if Model.ldf(idx) is not None]
    ldfs_dict = {}
    for db in databases:
        if isinstance(db, dict):
            name = db.get("name")
            if name:
                ldfs_dict[name] = db
        if not databases:
            TestLog("FAIL", "LDF加载解析", "未能解析数据库（LDFs 为空）")
            return {}
    default_lin_request_nand = get_nand_id()
    default_lin_Simulation_nand = get_nand_id()

def lin_can_init():
    global default_lin_request_nand,default_lin_Simulation_nand
    lintp_sys_global_val_set()
    lin_initialization()
    default_lin_request_nand = get_nand_id()
    default_lin_Simulation_nand = get_nand_id()

def lin_can_deinit():
    lin_deinitialization()


"""
TP 以单帧的方式收发测试一些异常时间参数

"""

def __tpmsg_to_lin_msg(data:bytes,nadid:int=None):
    mesgs = []
    data =  list(data)
    if len(data)> 6:
        msg = [nadid,(0X10+ (len(data)>>8)),len(data) &0XFF]
        msg = msg + data[0:5]
        data = data[5:]
        mesgs.append(msg)
        id = 1
        while len(data)> 0:
            if len(data) >=6:
                msg = [nadid,(0X20+ id)]
                msg = msg + data[0:6]
                data = data[6:]
                mesgs.append(msg)
            else:
                msg = [nadid,(0X20+ id)]
                msg = msg + data +[0XFF]*(6-len(data))
                data = []
                mesgs.append(msg)
            id += 1
            if id>=16:
                id = 0
    else:
        msg = [nadid,len(data)] + data+([0XFF]*(6-len(data)))
        mesgs.append(bytes(msg))
    return mesgs

def lintp_send_req_by_message(data:bytes,delay_0x3c:float,lin_channel=None,nadid=None):
    global default_lin_request_nand
    if lin_channel==None:
        lin_channel = DEFAULT_LIN_CHANNEL
    if nadid == None:
        nadid = default_lin_request_nand
    msgs = __tpmsg_to_lin_msg(data,nadid)
    lin_ch = sl_lin(lin_channel)
    for msg in msgs:
        lin_msg = sl_linmsg(0X3C)
        lin_msg.set_dlc(8)
        lin_msg.StartResp()   
        lin_msg.UpdateResponse(msg)
        lin_ch.update_response(lin_msg)
        lin_ch.output(0X3C)
        if delay_0x3c:
         time.sleep(delay_0x3c)
    del lin_ch
           
def lintp_rcv_res_by_message(delay_0x3d:float,lin_channel=None,timeout=3,frame_check_type=False):
    rcv_res_msg = []
    all_frames = []
    from .lin_test_pre_module import create_lin_ch
    res_len = 0
    def __on_msg( p_msg):
        nonlocal  res_len,all_frames,rcv_res_msg
        if (p_msg.id &0X3F) == 0X3d:  
            if p_msg.err_type == 0:
                if (p_msg.data[1] &0XF0) == 0:
                    res_len = p_msg.data[1]
                    rcv_res_msg = list(p_msg.data)[2:2+res_len]
                elif (p_msg.data[1] &0XF0) == 0X10:
                    res_len = (p_msg.data[1]  & 0X0F <<8) + p_msg.data[2]
                    rcv_res_msg = list(p_msg.data)[3:]
                elif (p_msg.data[1] &0XF0) == 0X20:
                    if res_len >=6:
                        res_len -=6
                        rcv_res_msg = rcv_res_msg + list(p_msg.data)[2:]
                    else:
                        rcv_res_msg = rcv_res_msg + list(p_msg.data)[2:res_len+ 2]
                        res_len = 0
                all_frames.append(p_msg)
            elif p_msg.err_type != 2:
                all_frames.append(p_msg)
    lin_ch_usr = create_lin_ch()
    lin_ch_usr.add_call_back(__on_msg)
    begin_time = time.time()
    lin_msg = sl_linmsg(0X3D)
    lin_msg.set_dlc(8)
    lin_msg.StopResp()   
    lin_ch_usr.update_response(lin_msg)
    while True:
        lin_ch_usr.output(0X3D)
        time.sleep(delay_0x3d)
        if (time.time() - begin_time)>timeout:
            break
    lin_ch_usr.del_call_back(__on_msg)
    if frame_check_type==True:
        return (rcv_res_msg,all_frames)
    return rcv_res_msg


def lin_ch_by_message(lin_channel=None,timeout=3,func_in_rcv_time=None,args=()):
    from .lin_test_pre_module import create_lin_ch
    all_msg = []
    def __on_msg(self, p_msg):
        nonlocal  all_msg
        msg= (p_msg.id &0X3F ,time.time(),p_msg)
        all_msg.append(msg)

    lin_ch_usr = create_lin_ch()
    lin_ch_usr.add_call_back(__on_msg)
    begin_time = time.time()
    while True:
        if (time.time() - begin_time)>timeout:
            break
        if func_in_rcv_time!=None:
            func_in_rcv_time(args)
        time.sleep(0.01)
    lin_ch_usr.del_call_back(__on_msg)
    return all_msg