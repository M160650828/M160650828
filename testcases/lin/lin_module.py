import json
import time
from uvtest.testlog import TestLog
from uvtest.syslog import output_log
from common.context import ctx
from common.params import P

from env.config import DEFAULT_LIN_CHANNEL, DEFAULT_CAN_CHANNELS
from slplus.event import TextEvents
from slplus.can import sl_can, sl_canmsg
from slplus.time import sl_time
from slplus.lin import sl_lin, sl_linconfig, sl_linmsg

'''
variable
'''
gLinTextEvent_RX = "LIN Frame is Received"
gLinTextEvent_TX = "LIN Frame is Transmitted"

__first_rcv_ok_frame = None
__power_start_time = 0
__0x3c_frame = None
__0x3d_frame = None
__rcv_all_frame = []

__sch_tbls = []
__all_nodes = []
__all_frames = {}

__lin_ch_handel = None
__lin_sch_handle = None
_lin_slave_frame_info = {}
'''
事件处理
'''


def handle_lin_message(msg, bus_id):
    global __first_rcv_ok_frame, __0x3c_frame, __0x3d_frame, __rcv_all_frame
    """
	LIN 报文回调处理
    """
    try:
        pid = int(getattr(msg, "pid", 0) or 0)
        frame_id = int(getattr(msg, "id", (pid & 0x3F)) or 0)
        frame_dlc = int(getattr(msg, "dlc", 0) or 0)
        data_bytes = list(getattr(msg, "data", b""))
        err_type = int(getattr(msg, "err_type", 0) or 0)
        checksum = int(getattr(msg, "checksum", 0) or 0)
        direction = int(getattr(msg, "dirv", 0) or 0)  # 0=RX,1=TX
        ts_ns = int(getattr(msg, "timestamp_ns", 0) or 0)
        current_time_ms = float(ts_ns) / 1_000_000.0 if ts_ns else (time.time() * 1000.0)
        if err_type != 0:
            err_count = ctx.lin.get_info('gLinErrorFrameCount')
            if err_count == None:
                err_count = 0
            err_count += 1
            ctx.lin.set_info('gLinErrorFrameCount', err_count)
        try:
            event_name = gLinTextEvent_TX if direction == 1 else gLinTextEvent_RX
            TextEvents().supply(event_name)
        except Exception:
            pass
        __rcv_all_frame.append((frame_id, current_time_ms))
        frame_id = int(frame_id)
        if frame_id in (0x3C, 0x3D):
            if frame_id == 0x3C and err_type == 0:
                __0x3c_frame = msg
            if frame_id == 0x3d and err_type == 0:
                __0x3d_frame = msg
            return
        if __first_rcv_ok_frame == None:
            if _current_dut_mode() == "master":
                __first_rcv_ok_frame = {}
                __first_rcv_ok_frame["now_time"] = time.time()
                __first_rcv_ok_frame["msg"] = msg
            else:
                if err_type == 0 and direction == 0:
                    __first_rcv_ok_frame = {}
                    __first_rcv_ok_frame["now_time"] = time.time()
                    __first_rcv_ok_frame["msg"] = msg
        try:
            payload_hex = "".join(f"{b:02X}" for b in data_bytes) if frame_dlc > 0 else ""
            ctx.lin.add_message(
                id=frame_id,
                time_ms=current_time_ms,
                dlc=frame_dlc,
                channel=bus_id,
                payload_hex=payload_hex,
                direction=direction,
            )
        except Exception:
            pass

        try:
            unique_ids = {m.id for m in ctx.lin.messages}
            ctx.lin.set_info("gLinFrameIDCount", len(unique_ids))
        except Exception:
            pass

        try:
            payload_display = " ".join(f"{b:02X}" for b in data_bytes) if frame_dlc > 0 else "无数据"
            action = "发送" if direction == 1 else "接收"
            count = sum(1 for m in ctx.lin.messages if m.id == frame_id)
            # print(
            #     f"{action}LIN报文 - 通道: {bus_id}, PID=0x{pid:02x}(ID=0x{frame_id:02x}), "
            #     f"DLC: {frame_dlc}, 数据长度: {frame_dlc}, 数据: [{payload_display}], 计数: {count}"
            # )
        except Exception:
            pass

    except Exception as e:
        print(f"LIN消息处理错误: {e}")


class lin_ch(sl_lin):
    def __init__(self, ch):
        self.ch = ch
        super().__init__(ch)
        self.__callback=[]
        self.active_status = True

    def add_call_back(self, call):
        self.__callback.append(call)
    
    def del_call_back(self, call):
        self.__callback.remove(call)

    def _on_message(self, p_msg):
        # frame_msg = {
        #     "id":p_msg.id,
        #     "time": p_msg.timestamp_ns,
        #     "dirv": p_msg.dirv,
        #     "dlc": p_msg.dlc,
        #     "err_type": p_msg.err_type,
        #     "checksum": p_msg.checksum,
        #     "data": p_msg.data,
        # }
        # print(frame_msg)
        if self.active_status == False:
            return
        for call in self.__callback:
            call(p_msg)
        handle_lin_message(p_msg, self.ch)



def handle_can_message(msg_frame_ptr, bus_id):
    o = msg_frame_ptr
    msg_id = int(getattr(o, 'msgid', 0) or 0)
    dlc = getattr(o, 'dlc', 8)
    payload = getattr(o, 'payload', b'') or b''
    dirv = getattr(o, 'dirv', None)
    action = "接收" if (dirv is None or dirv == 0) else ("发送" if dirv == 1 else "未知")
    msg_type = "CANFD" if getattr(o, 'is_fd', False) else "CAN"
    disp = ' '.join(f"{b:02X}" for b in payload) if payload else "无数据"
    sRx = ctx.can.get_info('sRxMsgInfoList') or {}
    cnt = sRx.get(msg_id, {}).get('count', 0)
    print(
        f"{action}{msg_type}报文 - 通道: {bus_id}, ID: 0x{msg_id:x}, DLC: {dlc}, 数据长度: {len(payload)}, 数据: [{disp}]" + (
            f", 计数: {cnt}" if cnt else ""))


def create_lin_ch(ch=None):
    global __lin_ch_handel
    if __lin_ch_handel == None:
        if ch == None:
            ch = DEFAULT_LIN_CHANNEL
        __lin_ch_handel = lin_ch(ch)
    __lin_ch_handel.active_status =True
    return __lin_ch_handel


def __release_lin():
    global __lin_ch_handel
    if __lin_ch_handel != None:
        __lin_ch_handel.active_status =False


def create_lin_sch(ch=None):
    global __lin_sch_handle
    from slplus.linsch import sl_linsch, sl_linsch_node
    if __lin_sch_handle == None:
        if ch == None:
            ch = DEFAULT_LIN_CHANNEL
        __lin_sch_handle = sl_linsch(ch)
    return __lin_sch_handle


'''
总线仿真
'''


def ActivateDut(rSimulationActivate=1, rTstable=20, power_off: float = None):
    global __first_rcv_ok_frame, __0x3c_frame, __0x3d_frame, __rcv_all_frame, __power_start_time, _lin_slave_frame_info
    """
    激活DUT
    1) 设置DUT供电电压
    2) WakeupStart
    3) 按 DUT 模式执行仿真流程
       - DUT 为 slave: 仿真 master + 剩余 slave节点
       - DUT 为 master: 仿真所有 slave
    4) check_lin_communication_state
    """
    from common.wakeup import WakeupStart

    rVnormal = P.LINInfo.Vnormal  # 正常工作电压
    try:
        ctx.lin.set_info('lin_simulation_activate', int(rSimulationActivate))
    except Exception:
        pass
    try:
        TestLog("INFO", "LIN测试设置", "开始LIN测试设置和通道设置")
        ctx.lin.set_info('gLinErrorFrameCount', 0)
        if power_off != None:
            ctx.power_ctrl.off()
            ctx.bob_ctrl.set_power('KL30', False)
            time.sleep(power_off)
        __first_rcv_ok_frame = None
        __0x3c_frame = None
        __0x3d_frame = None
        __rcv_all_frame = []

        # Step3: 根据 DUT节点准备并启动仿真
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

        # Step1: 设置DUT供电电压
        TestLog("INFO", "Step1", f"设置DUT供电电压为 {rVnormal:.2f}V")
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.power_ctrl.on()
        sch = create_lin_sch()
        lin_ch = create_lin_ch()
        lin_ch.send_wakeup()
        if dut_mode == "slave":
            sch.stop()
        time.sleep(1)
        ctx.bob_ctrl.set_power('KL30', True)
        ctx.bob_ctrl.set_power('KL15', True)
        TestLog("INFO", "Step2", "执行KL30上电")
        # # Step2: WakeupStart
        # try:
        #     from common.wakeup import WakeupStart
        #     TestLog("INFO", "Step1", "发送LIN唤醒信号")
        #     WakeupStart()
        # except Exception as e:
        #     TestLog("WARNING", "唤醒", f"WakeupStart 执行异常: {e}")
        __power_start_time = time.time()
        # Step4: 等待通信稳定并检查通信状态
        if rTstable != 0:
            TestLog("INFO", "Step3", f"等待 {rTstable}s 以检查LIN通信状态,LDF:{len(_lin_slave_frame_info)}")
            print(len(_lin_slave_frame_info), _lin_slave_frame_info)
            if dut_mode == "slave" and len(_lin_slave_frame_info) > 0:
                count = rTstable / 0.01
                id = _lin_slave_frame_info[-1]["id"]
                lin_msg = sl_linmsg(id)
                lin_msg.set_dlc(_lin_slave_frame_info[-1]["dlc"])
                lin_msg.StopResp()
                lin_ch.update_response(lin_msg)
                while count > 0:
                    lin_ch.output(id)
                    time.sleep(0.01)
                    count -= 1
                sch.start()
            else:
                time.sleep(rTstable)
            ret = check_lin_communication_state(rTstable,False)
            if ret != 0:
                TestLog("FAIL", "LIN通信检查", "LIN通信状态检查失败")
                return -1

        TestLog("PASS", "DUT激活", f"按 DUT 模式({dut_mode}) 启动仿真成功，通信正常")
        return 0

    except Exception as e:
        TestLog("FAIL", "DUT激活", f"DUT激活失败: {e}")
        import traceback
        TestLog("DEBUG", "DUT激活", f"详细错误: {traceback.format_exc()}")
        return -1


def _setup_lin_simulation_for_dut(dut_mode, lin_channel=None):
    """
    配置仿真节点信息：
    - DUT 为 slave: 激活 master + 其余 slave（排除 DUT 本身）
    - DUT 为 master: 仅激活所有 slave
    """
    try:
        sch = create_lin_sch()
        # 设置节点激活
        try:
            ecu_name = str(P.ECUInfo.ECUName or '').strip()
        except Exception:
            ecu_name = ''
        current_ecu_name = ctx.lin.get_info('current_ecu_name')
        if current_ecu_name is None:
            current_ecu_name = ecu_name
        from slplus.linsch import sl_linsch, sl_linsch_node
        nodes = sch.nodes()
        for node in nodes:
            try:
                attr = node.attr()
                name = attr.get("name", "")
                is_master = bool(attr.get("is_master"))
                if dut_mode == "slave":
                    # 仿真 master + 其余 slave（排除 DUT）
                    active = is_master or ((not is_master) and (name != current_ecu_name))
                else:
                    # DUT 为 master -> 仿真所有 slave
                    active = (not is_master)
                node.set_active(active)
            except Exception:
                pass

        ctx.lin.set_info('lin_schedule', sch)
        ctx.lin.set_info('lin_schedule_channel', lin_channel)
        TestLog("DEBUG", "", f"已完成调度表与节点激活设置 - DUT: {dut_mode}")
        return 0
    except Exception as e:
        TestLog("FAIL", "LIN仿真准备", f"异常: {e}")
        import traceback
        TestLog("DEBUG", "LIN仿真准备", f"详细错误: {traceback.format_exc()}")
        return -1


def _start_lin_simulation_for_dut(dut_mode, lin_channel=None):
    """
    启动调度表仿真
    """
    try:
        from env.config import DEFAULT_LIN_CHANNEL
        sch = create_lin_sch()
        if dut_mode == "slave":
            normal_idxs = ctx.lin.get_info('NormalSchedTableIndex') or []
            print("normal_idxs:", normal_idxs, ctx.lin.get_info('NormalSchedTableIndex'))
            idx = (normal_idxs[0] if len(normal_idxs) > 0 else 0)
            try:
                sch.switch_scheduletable(idx)
                TestLog("DEBUG", "", f"切换到正常调度表索引 {idx}")
            except Exception as e:
                TestLog("WARNING", "调度表切换", f"切换失败，继续默认表: {e}")

        lin_ch = create_lin_ch()
        lin_ch.active()
        try:
            sch.start()
        except Exception:
            pass

        TestLog("PASS", "", f"LIN仿真启动完成 - DUT: {dut_mode}")
        return 0
    except Exception as e:
        TestLog("FAIL", "LIN仿真启动", f"异常: {e}")
        import traceback
        TestLog("DEBUG", "LIN仿真启动", f"详细错误: {traceback.format_exc()}")
        return -1


def stop_lin_simulation():
    """
    停止当前LIN仿真：
    - 停止已创建的调度表
    - 停止工程
    """
    sch = create_lin_sch()
    sch.stop()
    lin_ch = create_lin_ch()
    lin_ch.deactive()
    TestLog("INFO", "LIN仿真停止", "已请求停止LIN调度与工程")
    time.sleep(0.1)


'''
过程控制
'''


def _current_dut_mode() -> str:
    """返回 DUT 的 LIN 模式: 'master' 或 'slave'
    SIMULATION_ACTIVATE: 0=仿真主(测试端主/DUT从), 1=仿真从(测试端从/DUT主)
    """
    try:
        val = ctx.lin.get_info('lin_simulation_activate')
        if val is None:
            val = P.LINInfo.SimulationActivate
        sim_act = int(val)
        return "slave" if sim_act == 0 else "master"
    except Exception:
        return "slave"


def _load_and_parse_ldf():
    global __all_nodes, _lin_slave_frame_info,__all_frames,__sch_tbls
    from common.db_parser import DB

    result = DB.lin()
    if not result.success:
        return {}
    _lin_slave_frame_info = []
    ecu_name = str(P.ECUInfo.ECUName or '').strip()
    ctx.lin.set_info('current_ecu_name', ecu_name)
    for key, msg in result.messages.items():
        if [ecu_name] == msg["publishers"]:
            msg["id"] = key
            _lin_slave_frame_info.append(msg)
    for key, ctx_key in [
        ('network_name', 'ldf_network_name'),
        ('master_name', 'ldf_master_name'),
        ('slave_names', 'ldf_slave_names'),
        ('schedule_indexes', 'ldf_schedule_indexes'),
        ('schedule_tables', 'lin_schedule_tables'),
        ('normal_indexes', 'NormalSchedTableIndex'),
    ]:
        if key in result.extra:
            ctx.lin.set_info(ctx_key, result.extra[key])
    __all_nodes = result.extra.get('nodes', [])
    __all_frames = {}
    for fid, info in result.messages.items():
        frame_name = info.get('name', '')
        pub = info.get('publishers', [])
        sigs = info.get('signals', [])
        if frame_name:
            __all_frames[frame_name] = {'id': fid, 'type': 'Unconditional','publishers':pub,'signals':sigs}
    __sch_tbls = result.extra.get('schedule_tables',[])
    for sch_tabl in __sch_tbls:
        for slot in sch_tabl.get('slots', []):
            slot_name = slot.get('name', '')
            if slot_name in __all_frames:
                slot['id'] = __all_frames[slot_name]['id']
                slot['type'] = __all_frames[slot_name]['type']
            else:
                slot['id'] = 255
                slot['type'] = 'Sporadic'
    network_name = result.extra.get('network_name', '')
    if network_name:
        sch = create_lin_sch()
        sch.bind_db(network_name)
        tables  = sch.scheduletables()
        for tabl in tables:
            slots = tabl.timeslots()
            for slot in slots:
                attr = slot.get_attr()
                if  attr["name"]  in __all_frames.keys():
                    __all_frames[attr["name"]]["msg"] = slot.get_bind_msg()[0]
    return result.messages



def set_msg_rcv(msgid:int):
    global __all_frames
    for key,msg in __all_frames.items():
        if msgid ==  msg["id"]:
            if "msg" in msg.keys():
               msg["msg"].StopResp()


def set_msg_send(msgid:int):
    global __all_frames
    for key,msg in __all_frames.items():
        if msgid ==  msg["id"]:
            if "msg" in msg.keys():
               msg["msg"].StartResp()
 

def set_invalid_data(msgid:int,data:bytes=b""):
    global __all_frames
    for key,msg in __all_frames.items():
        if msgid ==  msg["id"]:
            if len(data)<8:
                data = data + bytes([0])*8-len(data)
            data_val = int.from_bytes(data,"little")
            for sig in msg["signals"]:
                sig["val"]  = ((data_val>>sig["start_bit"]) &   ((1<<(sig["bit_length"]))-1))
            if "msg" in msg.keys():
               msg["msg"].UpdateResponse(data)


def set_sig_data(sigs:dict):
    global __all_frames
    for key,msg in __all_frames.items():
        msg_changed_flg = False
        data_val =0
        for sig in msg["signals"]:
            if sig["name"] in sigs.keys():
               sig["val"]  = (sigs[sig["name"]] &   ((1<<(sig["bit_length"]))-1))
               msg_changed_flg = True
            if "val" in sig.keys():
               data_val =  data_val|(sig["val"] << sig["start_bit"])
        if msg_changed_flg==True:
            msg["msg"].UpdateResponse(int.to_bytes(data_val,8,"little"))

def get_sig_data(sig_name:str):
    global __all_frames
    for key,msg in __all_frames.items():
        for sig in msg["signals"]:
            if sig["name"] ==sig_name:
                if "val" in sig.keys():
                    return sig["val"]
    return 0

def lin_communication_bitrate_reset(lin_channel=None, bitrate=19200):
    try:
        from env.config import DEFAULT_LIN_CHANNEL
        stop_lin_simulation()
        lin_ch = create_lin_ch()
        cfg = lin_ch.config
        cfg.set_bitrate(int(bitrate))
        cfg.ch_apply_config()
        if (_current_dut_mode() == "slave"):
            ActivateDut(0, 1)
        else:
            ActivateDut(1, 1)
    except Exception as e:
        TestLog("FAIL", "LIN波特率设置", f"LIN波特率设置失败: {e}")
        import traceback
        TestLog("DEBUG", "LIN波特率设置", f"详细错误: {traceback.format_exc()}")
        return -1


def lin_communication_setup(lin_channel=None):
    """
    LIN通信设置
    """
    try:
        mode = ctx.lin.get_info('lin_mode')
        TestLog("INFO", "LIN通信设置", f"开始LIN通信设置 - 模式: {mode}")

        # 1. 设置LIN通道模式
        TestLog("INFO", "Step1", f"设置LIN通道 {lin_channel} 为 {mode} 模式")
        lin_ch = create_lin_ch()
        config = lin_ch.config
        if mode == "master":
            config.set_master(True)
            config.set_resistor(True)
            TestLog("INFO", "通道配置", f"LIN通道 {lin_channel} 配置为主节点模式")
        elif mode == "slave":
            config.set_master(False)
            config.set_resistor(False)
            TestLog("INFO", "通道配置", f"LIN通道 {lin_channel} 配置为从节点模式")
        else:
            TestLog("FAIL", "LIN通信设置", f"不支持的模式: {mode}，支持的模式: master, slave")
            return -1

        # 2. 应用配置
        TestLog("INFO", "Step3", f"应用LIN通道 {lin_channel} 配置")
        ret = config.ch_apply_config()
        if ret != 0:
            TestLog("FAIL", "LIN通道配置", "LIN通道配置失败")
            return -1

        TestLog("INFO", "LIN通信设置",
                f"LIN通信设置完成 - 模式: {mode}, 通道: {lin_channel}, LDF帧: {len(ctx.lin.get_info('sLdfMsgInfoList') or {})}")
        return 0

    except Exception as e:
        TestLog("FAIL", "LIN通信设置", f"LIN通信设置失败: {e}")
        import traceback
        TestLog("DEBUG", "LIN通信设置", f"详细错误: {traceback.format_exc()}")
        return -1


def monitor_lin_communication(duration_sec=20, clear: bool = True):
    global __rcv_all_frame
    sim_mode = ctx.lin.get_info("lin_mode")
    direction = "TX" if sim_mode == "slave" else "RX"

    TestLog("INFO", "监控通信", f"记录{direction}方向的 LIN 帧ID")

    try:
        if clear == True:
            ctx.lin.clear_messages()
            __rcv_all_frame = []
    except Exception:
        pass

    TestLog("INFO", "监控通信", f"等待{duration_sec}秒收集LIN帧...")
    time.sleep(duration_sec)

    msgs = {}
    try:
        for m in ctx.lin.messages:
            fid = int(m.id)
            try:
                payload_hex = m.payload_hex or ""
                data_bytes = [int(payload_hex[i: i + 2], 16) for i in
                              range(0, len(payload_hex), 2)] if payload_hex else []
            except Exception:
                data_bytes = []

            record = {
                "pid": fid,
                "id": fid,
                "dlc": int(m.dlc),
                "err_type": 0,
                "checksum": 0,
                "data": data_bytes,
                "time": float(m.time_ms),
                "channel": int(m.channel),
                "direction": direction,
            }
            msgs.setdefault(fid, []).append(record)
    except Exception:
        pass

    TestLog("INFO", "监控通信", f"监控完成，共记录了 {len(msgs)} 种不同ID的LIN帧({direction})")
    return msgs, direction


def get_nand_id(name: str = None):
    global __all_nodes
    if name == None:
        name = ctx.lin.get_info('current_ecu_name')
    for node in __all_nodes:
        if node["name"] == name:
            return node["nandid"]
    return 0


def get_other_nand_id(name: str = None):
    global __all_nodes
    if name == None:
        name = ctx.lin.get_info('current_ecu_name')
    other_nand = {}
    for node in __all_nodes:
        if node["name"] != name:
            if "nandid" in node.keys():
                other_nand[node["name"]] = node["nandid"]
    return other_nand


def get_powerup_to_first_frame_time():
    global __first_rcv_ok_frame, __power_start_time
    if __first_rcv_ok_frame == None:
        return (time.time() - __power_start_time)
    return (__first_rcv_ok_frame["now_time"] - __power_start_time)


def send_message(msgid: int, dlc: int = 8, data: bytes = bytes([]), stop_sch: bool = True):
    from env.config import DEFAULT_LIN_CHANNEL
    if stop_sch:
        sch = create_lin_sch()
        sch.stop()
        time.sleep(0.01)
    lin_msg = sl_linmsg(msgid)
    lin_msg.set_dlc(dlc)
    lin_msg.StartResp()
    lin_msg.UpdateResponse(data)
    lin_ch = create_lin_ch()
    lin_ch.update_response(lin_msg)
    lin_ch.output(msgid)


def rcv_message(msgid: int, stop_sch: bool = True):
    if stop_sch:
        sch = create_lin_sch()
        sch.stop()
    lin_msg = sl_linmsg(msgid)
    lin_msg.StopResp()
    lin_ch = create_lin_ch()
    lin_ch.update_response(lin_msg)
    lin_ch.output(msgid)


def send_wakeup():
    lin_ch = create_lin_ch()
    lin_ch.send_wakeup()


class LinCommChecker:
    def set_and_check(self, voltage: float, delay: float = 1.0):
        global _lin_slave_frame_info
        status, msg = ctx.power_ctrl.set_voltage(voltage)
        if status is False:
            TestLog("FAIL", "LIN通信状态检查", f"设置电压失败: {msg}")
            return False, False, False



        if _current_dut_mode() == "slave" and len(_lin_slave_frame_info) > 0:
            sch = create_lin_sch()
            lin_ch = create_lin_ch()
            sch.stop()  
            time.sleep(0.1)
            try:
                ctx.lin.clear_messages()
                ctx.lin.set_info('gLinErrorFrameCount', 0)
                ctx.lin.set_info('gLinFrameIDCount', 0)
            except Exception:
                pass
            id = _lin_slave_frame_info[-1]["id"]
            lin_msg = sl_linmsg(id)
            lin_msg.set_dlc(_lin_slave_frame_info[-1]["dlc"])
            lin_msg.StopResp()
            lin_ch.update_response(lin_msg)
            begin_time = time.time()
            while True:
                lin_ch.output(id)
                time.sleep(0.01)
                if (time.time() - begin_time) > delay:
                    break
            sch.start()
        else:
            try:
                ctx.lin.clear_messages()
                ctx.lin.set_info('gLinErrorFrameCount', 0)
                ctx.lin.set_info('gLinFrameIDCount', 0)
            except Exception:
                pass
            if delay and delay > 0:
                sl_time().sleep(int(delay * 1000))

        try:
            msg_count = len(ctx.lin.messages)
            frame_cnt = int(ctx.lin.get_info('gLinFrameIDCount') or 0)
            has_comm = (msg_count > 0) or (frame_cnt > 0)
        except Exception:
            has_comm = False

        return True, has_comm, False


def check_lin_communication_state(wait_time,clear:bool =True):
    """检查LIN通信状态"""
    TestLog("INFO", "LIN通信状态检查", f"等待 {wait_time}s 检查LIN通信状态")

    ctx.lin.set_info('gLinErrorFrameCount', 0)

    try:
        if clear ==True:
            ctx.lin.clear_messages()
    except Exception:
        pass
    
    sim_mode = ctx.lin.get_info('lin_mode')
    event_name = gLinTextEvent_TX if sim_mode == "slave" else gLinTextEvent_RX
    event_detected = bool(TextEvents().wait(event_name, int(wait_time * 1000)))

    try:
        total_msgs = len(ctx.lin.messages)
        unique_ids = {m.id for m in ctx.lin.messages}
        frame_cnt = len(unique_ids)
        ctx.lin.set_info('gLinFrameIDCount', frame_cnt)
    except Exception:
        total_msgs = 0
        frame_cnt = 0

    TestLog("INFO", "LIN通信状态", f"消息总数={total_msgs}, 不同ID数量={frame_cnt}, event_detected={event_detected}")

    err_cnt = ctx.lin.get_info('gLinErrorFrameCount') or 0

    if (frame_cnt > 0 or event_detected) and err_cnt == 0:
        TestLog("PASS", "LIN通信状态检查", "LIN通信正常，总线上有帧的传输，且无错误帧")
        return 0
    elif (frame_cnt > 0 or event_detected) and err_cnt > 0:
        TestLog("WARNING", "LIN通信状态检查", "LIN通信正常，总线上有帧的传输，但有错误帧")
        return 0
    elif frame_cnt == 0 and err_cnt > 0:
        TestLog("FAIL", "LIN通信状态检查", "LIN通信不正常，总线上无帧的传输，有错误帧")
        return -1
    else:  # frame_cnt == 0 and err_cnt == 0 and not event_detected
        TestLog("FAIL", "LIN通信状态检查", "LIN通信未恢复")
        return -1


def verify_lin_messages(msgs, direction, check_type, test_name="LIN帧检查"):
    global __0x3c_frame, __0x3d_frame, __rcv_all_frame, __sch_tbls
    """LIN帧校验"""
    step_label = "通信检查"
    ldf = ctx.lin.get_info('sLdfMsgInfoList') or {}

    try:
        dut_mode = _current_dut_mode()
    except Exception:
        dut_mode = "slave"

    try:
        ecu_name = str(P.ECUInfo.ECUName or "").strip()
    except Exception:
        ecu_name = ""
    if check_type not in ("id", "dlc", "Sequence", "solt_time", "0x3c", "0x3d"):
        TestLog("WARNING", step_label, f"未知校验类型: {check_type}，默认执行ID校验")
        check_type = "id"

    if check_type == "Sequence":
        normal_idxs = ctx.lin.get_info('NormalSchedTableIndex') or []
        idx = (normal_idxs[0] if len(normal_idxs) > 0 else 0)
        start_index = 0
        passed = True
        for (id, time_ms) in __rcv_all_frame:
            if id != __sch_tbls[idx]["slots"][start_index]["id"]:
                passed = False
                break
            start_index += 1
            if start_index >= len(__sch_tbls[idx]["slots"]):
                start_index = 0
        TestLog("PASS" if passed else "FAIL", test_name, "测试通过" if passed else "测试失败")
        return passed
    elif check_type == "solt_time":
        normal_idxs = ctx.lin.get_info('NormalSchedTableIndex') or []
        idx = (normal_idxs[0] if len(normal_idxs) > 0 else 0)
        start_index = 0
        passed = True
        rTperiodDeviation = P.LINInfo.TperiodDeviation  # 仿真激活标志
        if len(__rcv_all_frame) < 2:
            TestLog("FAIL", test_name, "测试通过" if passed else "测试失败")
            return
        for index in range(len(__rcv_all_frame) - 1):
            (id1, time_ms1) = __rcv_all_frame[index]
            (id2, time_ms2) = __rcv_all_frame[index + 1]
            time_ms = time_ms2 - time_ms1

            war_min_delay = __sch_tbls[idx]["slots"][start_index]["delay"] * (1 - rTperiodDeviation / 100)
            war_max_delay = __sch_tbls[idx]["slots"][start_index]["delay"] * (1 + rTperiodDeviation / 100)

            min_delay = __sch_tbls[idx]["slots"][start_index]["delay"] * (1 - (rTperiodDeviation*2) / 100)
            max_delay = __sch_tbls[idx]["slots"][start_index]["delay"] * (1 + (rTperiodDeviation*2) / 100)

            if max_delay <= time_ms or time_ms <= min_delay:
                passed = False
                TestLog("FAIL", test_name, f"测试失败 {index} - ID 0x{id1:x} 延迟时间 {time_ms:.3f}ms 不在期望范围内 [{min_delay:.3f}ms, {max_delay:.3f}ms]")
            else:
                if war_max_delay <= time_ms or time_ms <= war_min_delay:
                   TestLog("WARNING", test_name, f"测试警告 {index} - ID 0x{id1:x} 延迟时间 {time_ms:.3f}ms 不在期望范围内 [{war_min_delay:.3f}ms, {war_max_delay:.3f}ms]")
            start_index += 1
            if start_index >= len(__sch_tbls[idx]["slots"]):
                start_index = 0
        TestLog("PASS" if passed else "FAIL", test_name, "测试通过" if passed else "测试失败")
        return passed
    elif check_type == "0x3c":
        if __0x3c_frame != None:
            passed = True
        else:
            passed = False
        TestLog("PASS" if passed else "FAIL", test_name, "0X3C CRC 测试通过" if passed else "测试失败")
        return passed
    elif check_type == "0x3d":
        if __0x3d_frame != None:
            passed = True
        else:
            passed = False
        TestLog("PASS" if passed else "FAIL", test_name, "0X3D CRC 测试通过" if passed else "测试失败")
        return passed
    if not msgs:
        TestLog("FAIL", test_name, f"测试失败 - 未记录到任何{direction}方向的LIN帧")
        return False

    passed = True

    for frame_id in msgs.keys():
        if frame_id not in ldf:
            TestLog(
                "FAIL",
                "",
                f"期望结果：{direction} 的LIN报文ID应与通信数据库一致，测试结果：ID 0x{frame_id:x} 未出现在对应LDF文件中",
            )
            passed = False

    if not ecu_name:
        TestLog(
            "WARNING",
            step_label,
            "未配置 P.ECUInfo.ECUName，跳过 Publisher 过滤和ID/DLC校验，仅报告未知ID",
        )
        TestLog("PASS" if passed else "FAIL", test_name, "测试通过" if passed else "测试失败")
        return passed

    def _match_target(fid, info):
        if not isinstance(info, dict):
            return False
        if fid in (0x3C, 0x3D):  # 诊断帧不参与 ID/DLC 校验
            return False
        node = str(info.get("nodeName", "")).strip()
        if not node:
            return False
        if dut_mode == "slave":
            return node == ecu_name
        else:
            return node != ecu_name

    target_ids = {fid for fid, info in ldf.items() if _match_target(fid, info)}

    if dut_mode == "slave":
        obj_desc = f"Publisher 为被测 ECU ({ecu_name}) 的LIN帧"
        role_desc = f"Publisher 为 {ecu_name}"
    else:
        obj_desc = f"其它节点(Publisher≠{ecu_name}) 的LIN帧"
        role_desc = f"其它节点(Publisher≠{ecu_name})"

    if check_type == "id":
        TestLog("INFO", step_label, f"检查 {obj_desc} ID 是否与通信数据库定义一致")
    else:
        TestLog("INFO", step_label, f"检查 {obj_desc} DLC 是否与通信数据库定义一致")

    if not target_ids:
        if dut_mode == "slave":
            TestLog(
                "FAIL",
                step_label,
                f"LDF 中未找到 Publisher 为 {ecu_name} 的帧定义，无法执行针对被测ECU的ID/DLC校验",
            )
        else:
            TestLog(
                "FAIL",
                step_label,
                f"LDF 中未找到其它节点(Publisher≠{ecu_name}) 的帧定义，无法执行 master 场景的ID/DLC校验",
            )
        TestLog("PASS" if passed else "FAIL", test_name, "测试通过" if passed else "测试失败")
        return passed

    for fid in sorted(target_ids):
        records = msgs.get(fid, [])
        if not records:
            TestLog(
                "FAIL",
                "",
                f"期望结果：总线{direction}方向应能观测到 {role_desc} 的帧 ID 0x{fid:x}，测试结果：未观测到该帧",
            )
            passed = False
            continue

        if check_type == "id":
            last_dlc = records[-1].get("dlc", 0)
            if last_dlc != 0:
                TestLog(
                    "PASS",
                    "",
                    f"观测到 {role_desc} 的LIN报文 ID 0x{fid:x}，与LDF定义一致",
                )
            else:
                TestLog(
                    "FAIL",
                    "",
                    f"观测到 {role_desc} 的LIN报文 ID 0x{fid:x},无回复",
                )
                passed = False
        else:
            expected_dlc = ldf.get(fid, {}).get("dlc", 0)
            last_dlc = records[-1].get("dlc", 0)
            if last_dlc == expected_dlc:
                TestLog(
                    "PASS",
                    "",
                    f"期望结果：{role_desc} 的LIN报文DLC与通信数据库配置一致，测试结果：ID 0x{fid:x} DLC={last_dlc} 与数据库定义一致",
                )
            else:
                TestLog(
                    "FAIL",
                    "",
                    f"期望结果：{role_desc} 的LIN报文DLC与通信数据库配置一致，测试结果：ID 0x{fid:x} DLC={last_dlc} 与数据库定义DLC={expected_dlc}不一致",
                )
                passed = False

    TestLog("PASS" if passed else "FAIL", test_name, "测试通过" if passed else "测试失败")
    return passed


def get_test_case_mode():
    return _current_dut_mode()


'''
模块初始化
'''


def lin_initialization(session_dir=None):
    """
    LIN测试初始化函数
    """
    try:
        TestLog("INFO", "LIN初始化", "开始LIN协议相关初始化")
        ctx.lin.reset_all()
        # 1. 设置LIN通信模式
        try:
            dut_mode = _current_dut_mode()
            sim_mode = "master" if dut_mode == "slave" else "slave"
            ctx.lin.set_info('lin_mode', sim_mode)
            TestLog("INFO", "Step4", f"配置LIN通信为 {sim_mode} 模式")
            ret = lin_communication_setup()
            if ret != 0:
                TestLog("FAIL", "LIN初始化", "LIN通信设置失败")
                return True
        except Exception as e:
            TestLog("WARNING", "LIN初始化", f"LIN通信设置阶段异常: {e}")

        TestLog("INFO", "Step2", "初始化LIN测试环境")
        ctx.lin.set_info('gLinErrorFrameCount', 0)
        ctx.lin.set_info('gLinFrameIDCount', 0)
        ctx.lin.set_info('active_lin_channels', [])

        # 2. 解析LDF数据库
        TestLog("INFO", "Step3", "解析LDF数据库获取帧定义")
        sLdfMsgInfoList = _load_and_parse_ldf()
        if not sLdfMsgInfoList:
            TestLog("WARNING", "LDF解析", "LDF文件解析失败或无帧定义")
            sLdfMsgInfoList = {}

        ctx.lin.set_info('sLdfMsgInfoList', sLdfMsgInfoList)
        TestLog("INFO", "LDF数据存储", f"已将 {len(sLdfMsgInfoList)} 个帧定义存储到全局上下文")

        try:
            ctx.can.set_info('active_can_channels', [])
            cans = DEFAULT_CAN_CHANNELS
            if not cans:
                TestLog("WARNING", "CAN通道", "CAN通道配置为空，跳过激活")
            else:
                ok = 0
                for can_ch in cans:
                    try:
                        rte = sl_can(can_ch).active()
                        print("can active ", rte)
                        active_can_channels = ctx.can.get_info('active_can_channels')
                        if active_can_channels is None:
                            active_can_channels = []
                            ctx.can.set_info('active_can_channels', active_can_channels)
                        active_can_channels.append(can_ch)
                        ok += 1
                        TestLog("INFO", "通道激活", f"成功激活CAN通道 {can_ch}")
                    except Exception as e:
                        TestLog("WARNING", "通道激活", f"激活CAN通道 {can_ch} 失败: {e}")
                if ok <= 0:
                    TestLog("WARNING", "CAN通道", "未能激活任何CAN通道")
        except Exception as e:
            TestLog("WARNING", "CAN通道", f"CAN通道激活流程异常: {e}")

        TestLog("INFO", "LIN测试初始化", "基础初始化完成")
        return True

    except Exception as e:
        TestLog("FAIL", "LIN测试初始化", f"初始化失败: {e}")
        import traceback
        TestLog("DEBUG", "LIN测试初始化", f"详细错误: {traceback.format_exc()}")
        return False


def lin_deinitialization():
    """
    LIN测试去初始化函数
    """
    TestLog("INFO", "LIN测试去初始化", "开始LIN测试去初始化...")
    __release_lin()
    try:
        try:

            TestLog("INFO", "回调注销", "已取消注册 LIN 适配层回调 _on_msg_lin")
        except Exception as e:
            TestLog("WARNING", "回调注销", f"取消注册LIN回调失败: {e}")
        try:
            for can_ch in (ctx.can.get_info('active_can_channels') or []):
                try:
                    sl_can(can_ch).deactive()
                    TestLog("INFO", "通道停用", f"成功停用CAN通道 {can_ch}")
                except Exception as e:
                    TestLog("WARNING", "通道停用", f"停用CAN通道 {can_ch} 失败: {e}")
        except Exception:
            pass

        # 2. 清理所有上下文数据
        TestLog("INFO", "Step2", "清理LIN和CAN上下文数据")
        ctx.lin.reset_all()
        ctx.can.reset_all()

        TestLog("INFO", "LIN测试去初始化", "去初始化完成")
        return True

    except Exception as e:
        TestLog("FAIL", "LIN测试去初始化", f"去初始化失败: {e}")
        import traceback
        TestLog("DEBUG", "LIN测试去初始化", f"详细错误: {traceback.format_exc()}")
        return False


# ========== 故障注入和通信检查功能 ==========
def lin_fault_injection(fault_type, target_lin_channel, duration_ms=60000):
    """模拟LIN总线故障注入"""
    try:
        FAULT_MAP = {
            'LIN_short_power': ('SHORT_KL30', "LIN对电源短路"),
            'LIN_short_GND': ('SHORT_GND', "LIN对地短路"),
            'LIN_Open': ('OPEN', "LIN断开"),
        }

        fault_info = FAULT_MAP.get(fault_type)
        if fault_info is None:
            TestLog("FAIL", "故障注入", f"未知故障类型: {fault_type}")
            return False

        kind, fault_desc = fault_info
        target = f"LIN{target_lin_channel}"

        TestLog("INFO", "故障注入", f"开始注入{fault_desc}，目标={target}，持续时间={duration_ms}ms")

        # 注入故障
        success, status = ctx.bob_ctrl.set_fault(target, kind, enable=True)
        if not success:
            TestLog("FAIL", "故障注入", f"{fault_desc}注入失败: {status}")
            return False

        TestLog("INFO", "故障注入", f"{fault_desc}注入成功，等待{duration_ms}ms")

        # 记录故障后的通信状态
        initial_msg_count = 0
        for msg in ctx.lin.messages:
            if msg.direction == 0 and msg.dlc != 0:  # RX方向
                initial_msg_count += 1
        initial_error_count = ctx.lin.get_info('gLinErrorFrameCount') or 0
        TestLog("INFO", "通信状态监测", f"故障前状态: 响应帧报文数={initial_msg_count}, 错误帧数={initial_error_count}")

        # 故障期间通信状态监测
        fault_start_time = time.time()
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

        # 清除故障
        t1 = time.time()
        success, status = ctx.bob_ctrl.set_fault(target, kind, enable=False)
        if not success:
            TestLog("FAIL", "故障注入", f"{fault_desc}清除失败: {status}")
        else:
            TestLog("INFO", "故障注入", f"{fault_desc}已清除")
            sl_lin(target_lin_channel).deactive()
            sl_lin(target_lin_channel).active()
        return True, t1

    except Exception as e:
        TestLog("ERROR", "故障注入", f"故障注入异常: {e}")
        return False


def check_communication_recovery_time(start_time_t1, timeout_ms=2000):
    """故障恢复后规定时间内检查通信恢复时间"""
    error_count_before = ctx.lin.get_info('gLinErrorFrameCount') or 0
    msg_count_before = len(ctx.lin.messages)

    TestLog("INFO", "通信恢复检查", f"开始监控通信恢复，超时时间{timeout_ms}ms")

    while (time.time() - start_time_t1) * 1000 < timeout_ms:
        # 检查是否有新的CAN报文接收
        current_msg_count = len(ctx.lin.messages)
        current_error_count = ctx.lin.get_info('gLinErrorFrameCount') or 0

        if current_msg_count > msg_count_before and current_error_count <= error_count_before:
            recovery_time = (time.time() - start_time_t1) * 1000
            TestLog("INFO", "通信恢复", f"通信已恢复，恢复时间: {recovery_time:.2f}ms")
            return True, recovery_time

        time.sleep(0.001)

    TestLog("WARNING", "通信恢复", f"在{timeout_ms}ms内通信未恢复")
    return False, timeout_ms
