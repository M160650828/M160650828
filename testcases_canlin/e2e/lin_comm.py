import time
from uvtest.testlog import TestLog
from common.context import ctx
from common.params import P

from env.config import DEFAULT_LIN_CHANNEL, DEFAULT_CAN_CHANNELS
from slplus.event import TextEvents
from slplus.can import sl_can
from slplus.lin import sl_lin, sl_linconfig, sl_linmsg

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
__lin_slave_frame_info = {}


def handle_lin_message(msg, bus_id):
    global __first_rcv_ok_frame, __0x3c_frame, __0x3d_frame, __rcv_all_frame
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
        if __first_rcv_ok_frame is None:
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
            print(
                f"{action}LIN报文 - 通道: {bus_id}, PID=0x{pid:02x}(ID=0x{frame_id:02x}), "
                f"DLC: {frame_dlc}, 数据长度: {frame_dlc}, 数据: [{payload_display}], 计数: {count}"
            )
        except Exception:
            pass

    except Exception as e:
        print(f"LIN消息处理错误: {e}")


class lin_ch(sl_lin):
    def __init__(self, ch):
        self.ch = ch
        super().__init__(ch)

    def _on_message(self, p_msg):
        handle_lin_message(p_msg, self.ch)


def create_lin_ch(ch=None):
    global __lin_ch_handel
    if __lin_ch_handel is None:
        if ch is None:
            ch = DEFAULT_LIN_CHANNEL
        __lin_ch_handel = lin_ch(ch)
    return __lin_ch_handel


def __release_lin():
    global __lin_ch_handel
    del __lin_ch_handel
    __lin_ch_handel = None


def create_lin_sch(ch=None):
    global __lin_sch_handle
    from slplus.linsch import sl_linsch, sl_linsch_node
    if __lin_sch_handle is None:
        if ch is None:
            ch = DEFAULT_LIN_CHANNEL
        __lin_sch_handle = sl_linsch(ch)
    return __lin_sch_handle


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
    global __all_nodes, __lin_slave_frame_info
    from common.db_parser import DB

    result = DB.lin()
    if not result.success:
        return {}
    __lin_slave_frame_info = []
    ecu_name = str(P.ECUInfo.ECUName or '').strip()
    ctx.lin.set_info('current_ecu_name', ecu_name)
    for key, msg in result.messages.items():
        if [ecu_name] == msg["publishers"]:
            msg["id"] = key
            __lin_slave_frame_info.append(msg)
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
    network_name = result.extra.get('network_name', '')
    if network_name:
        sch = create_lin_sch()
        sch.bind_db(network_name)
    return result.messages


def lin_communication_setup(lin_channel=None):
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

        lin_ch_obj = create_lin_ch()
        lin_ch_obj.active()
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
    lin_ch_obj = create_lin_ch()
    lin_ch_obj.deactive()
    TestLog("INFO", "LIN仿真停止", "已请求停止LIN调度与工程")
    time.sleep(0.1)


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


def ActivateDut(rSimulationActivate=1, rTstable=20, power_off: float = None):
    """
    激活DUT
    1) 设置DUT供电电压
    2) WakeupStart
    3) 按 DUT 模式执行仿真流程
       - DUT 为 slave: 仿真 master + 剩余 slave节点
       - DUT 为 master: 仿真所有 slave
    4) check_lin_communication_state
    """
    global __first_rcv_ok_frame, __0x3c_frame, __0x3d_frame, __rcv_all_frame, __power_start_time, __lin_slave_frame_info
    from common.wakeup import WakeupStart

    rVnormal = P.LINInfo.Vnormal  # 正常工作电压
    try:
        ctx.lin.set_info('lin_simulation_activate', int(rSimulationActivate))
    except Exception:
        pass
    try:
        TestLog("INFO", "LIN测试设置", "开始LIN测试设置和通道设置")

        if power_off is not None:
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
        lin_ch_obj = create_lin_ch()
        if dut_mode == "slave":
            sch.stop()

        ctx.bob_ctrl.set_power('KL30', True)
        ctx.bob_ctrl.set_power('KL15', True)
        TestLog("INFO", "Step2", "执行KL30上电")
        __power_start_time = time.time()

        # Step4: 等待通信稳定并检查通信状态
        if rTstable != 0:
            TestLog("INFO", "Step3", f"等待 {rTstable}s 以检查LIN通信状态")
            print(len(__lin_slave_frame_info), __lin_slave_frame_info)
            if dut_mode == "slave" and len(__lin_slave_frame_info) > 0:
                count = rTstable / 0.01
                id = __lin_slave_frame_info[-1]["id"]
                lin_msg = sl_linmsg(id)
                lin_msg.set_dlc(__lin_slave_frame_info[-1]["dlc"])
                lin_msg.StopResp()
                lin_ch_obj.update_response(lin_msg)
                while count > 0:
                    lin_ch_obj.output(id)
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


def lin_initialization(session_dir=None):
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
    TestLog("INFO", "LIN测试去初始化", "开始LIN测试去初始化...")
    try:
        __release_lin()
    except Exception:
        pass
    try:
        stop_lin_simulation()
    except Exception:
        pass
    TestLog("INFO", "LIN测试去初始化", "LIN测试去初始化完成")