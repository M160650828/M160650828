import time
from typing import Tuple, Optional
from uvtest.testlog import TestLog

from slplus.time import sl_time
from env.config import DEFAULT_CAN_CHANNELS, DEFAULT_LIN_CHANNEL
from slplus.lin import sl_linmsg
from sl.sl_channel import lin_update_response, lin_output
from slplus.can import register_canmsg_handler, unregister_canmsg_handler
from slplus.lin import register_linmsg_handler, unregister_linmsg_handler
from slplus.can import sl_can
from slplus.event import TextEvents
from sl.sl_event import register_busevent_handler, unregister_busevent_handler, EventType

from common.context import ctx

from common.params import P
from copy import deepcopy

gCanTextEvent_RX, gCanTextEvent_TX = "CAN Frame is Received", "CAN Frame is Transmitted"
gNmTextEvent_RX = "NM Frame is Received"
gLinTextEvent_RX, gLinTextEvent_TX = "LIN Frame is Received", "LIN Frame is Transmitted"

nmctx = deepcopy(ctx)

def _on_can_nm(bustype, busid, msg, cookie):
    _ = bustype
    _ = cookie
    try:
        ts_ns = getattr(msg, "timestamp_ns", None)
        if ts_ns is not None:
            current_time = float(ts_ns) / 1_000_000.0  # ns -> ms
        else:
            current_time = sl_time().timestamp()

        msg_id = int(getattr(msg, "msgid", 0) or 0)
        msg_dlc = int(getattr(msg, "dlc", 8) or 8)
        is_fd = bool(getattr(msg, "is_fd", False))
        payload_bytes = getattr(msg, "payload", b"") or b""

        # try:
        #     if msg_id == int(P.ECUInfo.WakeupMsgID_int):
        #         return
        # except Exception:
        #     pass

        dir_str = "TX" if getattr(msg, "dirv", 0) == 1 else "RX"
        try:
            try:
                chan = int(P.ECUInfo.CommCANChannelNum)
            except Exception:
                try:
                    chan = int(DEFAULT_CAN_CHANNELS[0])
                except Exception:
                    chan = None
            if chan is not None and busid == chan:
                TextEvents().supply(gCanTextEvent_TX if dir_str == "TX" else gCanTextEvent_RX)
        except Exception:
            pass

        try:
            if dir_str != "TX" and msg_id == int(P.ECUInfo.NMMsgID_int):
                TextEvents().supply(gNmTextEvent_RX)
        except Exception:
            pass

        payload_hex = payload_bytes.hex().upper()
        dirv = getattr(msg, "dirv", 0)
        try:
            # 过滤掉机柜内部的通信报文
            if busid == DEFAULT_CAN_CHANNELS[1]:
                return

            ctx.can.add_message(
                id=msg_id,
                time_ms=current_time,
                dlc=msg_dlc,
                channel=busid,
                payload_hex=payload_hex,
                direction=dirv,
            )
            if msg_id == int(P.ECUInfo.NMMsgID_int):
                nmctx.can.add_message(
                    id=msg_id,
                    time_ms=current_time,
                    dlc=msg_dlc,
                    channel=busid,
                    payload_hex=payload_hex,
                    direction=dirv,
                )
        except Exception:
            pass

    except Exception:
        try:
            try:
                target_channel = int(DEFAULT_CAN_CHANNELS[0])
            except Exception:
                target_channel = None
            if target_channel is not None and busid == target_channel:
                error_count = int(ctx.can.get_info("gErrorFrameCount") or 0)
                now_ms = sl_time().timestamp()
                if error_count == 0:
                    ctx.can.set_info("firstErrorFrameTime_ms", now_ms)
                ctx.can.set_info("gErrorFrameCount", error_count + 1)
        except Exception:
            pass


def handle_can_error(error_value, bus_id, user_data):
    """
    处理CAN错误事件
    """
    try:
        errors = ("unknown", "bit", "format", "stuff", "crc", "ack", "arb")
        error_name = errors[error_value] if error_value < len(errors) else f"unknown({error_value})"

        if bus_id == DEFAULT_CAN_CHANNELS[0]:
            error_count = ctx.can.get_info('gErrorFrameCount') or 0
            if error_count == 0:
                ctx.can.set_info('firstErrorFrameTime_ms', sl_time().timestamp())
            ctx.can.set_info('gErrorFrameCount', error_count + 1)
            TestLog("DEBUG", "错误帧", f"ECU通信总线 {bus_id} 错误: {error_name}")
            if error_name == "ack":  # ACK错误单独计数
                error_count = ctx.can.get_info('gAckErrorFrameCount') or 0
                ctx.can.set_info('gAckErrorFrameCount', error_count + 1)
        else:
            TestLog("DEBUG", "错误帧", f"CAN通道 {bus_id} 错误: {error_name}")
    except Exception as e:
        TestLog("WARNING", "错误处理", f"处理CAN错误失败: {e}")

def handle_can_state(state_value, bus_id, user_data):
    """
    处理CAN总线状态变化
    """
    try:
        if 0 <= state_value <= 2:
            states = ["passive_error", "active_error", "bus_off"]
            state_name = states[state_value]
            TestLog("WARNING", "总线状态", f"总线 {bus_id} 状态: {state_name}")
    except Exception as e:
        TestLog("WARNING", "状态处理", f"处理CAN状态失败: {e}")

def _on_busevent(bustype, busid, value, cookie):
    try:
        if bustype != 2:
            return
        event_kind, value = value
        if event_kind == EventType.UG_BUS_STATE.value:
            handle_can_state(value, busid, cookie)
        elif event_kind == EventType.UG_BUS_ERROR.value:
            handle_can_error(value, busid, cookie)
    except Exception as e:
        TestLog("WARNING", "事件处理", f"处理CAN错误/状态事件失败: {e}")


def _on_lin_nm(bustype, busid, msg, cookie):
    _ = bustype
    _ = cookie
    try:
        ts_ns = getattr(msg, 'timestamp_ns', None)
        current_ms = float(ts_ns) / 1_000_000.0 if ts_ns is not None else (time.sl_time() * 1000.0)

        dir_str = "TX" if int(getattr(msg, 'dirv', 0)) == 1 else "RX"
        frame_id = int(getattr(msg, 'id', getattr(msg, 'pid', 0)) & 0x3F)

        try:
            cap_en = bool(ctx.can.get_info('lin_first_frames'))
            already = (ctx.can.get_info('lin_first_frame_time_hw_ms') is not None)
            dir_filter = ctx.can.get_info('lin_first_frame_dir')
            if cap_en and (not already) and (frame_id not in (0x3C, 0x3D)):
                if (dir_filter is None) or (str(dir_filter).upper() == dir_str):
                    ctx.can.set_info('lin_first_frame_time_hw_ms', current_ms)
                    ctx.can.set_info('lin_first_frame_id', frame_id)
        except Exception:
            pass

        try:
            is_tx = (dir_str == 'TX')
            TextEvents().supply(gLinTextEvent_TX if is_tx else gLinTextEvent_RX)
        except Exception:
            pass

    except Exception:
        try:
            ctx.can.set_info('gLinErrorFrameCount', int(ctx.can.get_info('gLinErrorFrameCount') or 0) + 1)
        except Exception:
            pass


def _load_and_parse_database(msg_type: str = 'tx'):
    from common.db_parser import DB
    from common.params import P

    if msg_type == 'all':
        result = DB.can()
        return result.messages if result.success else {}

    ecu_name = (P.ECUInfo.ECUName or '').strip()
    result = DB.can(ecu_name)
    if not result.success:
        return {}
    if msg_type == 'rx':
        return result.rx
    return result.tx


# 参数获取与处理
DEFAULT_NM_PERIOD_TOLERANCE_PCT = 5.0
DEFAULT_NM_BIT_CHECK_FRAMES = 3
DEFAULT_REPT_MSG_BIT0 = 0                # RepeatMessage 位索引
DEFAULT_ACT_WUP_BIT4 = 4                 # ActiveWakeup 位索引

def _bit(byte_val: int, bit_index: int) -> int:
    """返回byte的第 bit_index位"""
    return (int(byte_val) >> int(bit_index)) & 0x1


#初始化/去初始化
def nm_initialization():
    """NM测试初始化"""
    try:
        TestLog("INFO", "NM初始化", "开始NM相关初始化")

        # 全局上下文初始化
        ctx.can.reset_all()
        ctx.can.clear_messages()
        ctx.can.set_info("gErrorFrameCount", 0)
        ctx.can.set_info("gLinErrorFrameCount", 0)


        # LIN 相关状态
        ctx.can.set_info("lin_first_frames", False)
        ctx.can.set_info("lin_first_frame_time_hw_ms", None)
        ctx.can.set_info("lin_first_frame_dir", None)
        ctx.can.set_info("lin_first_frame_id", None)

        # 注册回调
        register_canmsg_handler(_on_can_nm, bus=0)
        register_busevent_handler(_on_busevent)
        register_linmsg_handler(_on_lin_nm, bus=0)

        # 激活 CAN 通道
        cans = DEFAULT_CAN_CHANNELS
        if not cans:
            TestLog("FAIL", "NM初始化", "CAN通道配置为空")
            return False

        activated_count = 0
        for can_ch in cans:
            try:
                sl_can(can_ch).active()
                activated_count += 1
                TestLog("INFO", "通道激活", f"成功激活CAN通道 {can_ch}")
            except Exception as e:
                TestLog("WARNING", "通道激活", f"激活CAN通道 {can_ch} 失败: {e}")

        if activated_count <= 0:
            TestLog("FAIL", "NM初始化", "未能激活任何CAN通道")
            return False

        # 解析 DBC
        try:
            sMsgInfoList = _load_and_parse_database()
            print("解析出来的数据库内容", sMsgInfoList)
            if not sMsgInfoList:
                TestLog("FAIL", "NM初始化", "DBC文件解析失败")
                return False
            ctx.can.set_info("sMsgInfoList", sMsgInfoList)
        except Exception as e:
            TestLog("FAIL", "NM初始化", f"DBC解析异常: {e}")
            return False

        TestLog("PASS", "NM初始化", f"NM初始化完成，DBC报文: {len(ctx.can.get_info('sMsgInfoList') or {})}")
        return True
    except Exception as e:
        TestLog("FAIL", "NM初始化", f"初始化失败: {e}")
        return False


def nm_deinitialization():
    """NM测试去初始化"""
    try:
        try:
            unregister_canmsg_handler(_on_can_nm)
        except Exception:
            pass
        try:
            unregister_linmsg_handler(_on_lin_nm)
        except Exception:
            pass

        try:
            cans = DEFAULT_CAN_CHANNELS
        except Exception:
            cans = []
        for can_ch in cans:
            try:
                sl_can(can_ch).deactive()
                TestLog("INFO", "通道停用", f"成功停用CAN通道 {can_ch}")
            except Exception as e:
                TestLog("WARNING", "通道停用", f"停用CAN通道 {can_ch} 失败: {e}")

        # 清理上下文
        ctx.can.reset_all()

        return True
    except Exception:
        return False


# 唤醒/休眠
def nm_start_wakeup(mode: str | None = None):
    """
    启动唤醒
    """
    try:
        if mode in (None, 'passive'):
            from common.wakeup import WakeupMsgSimulationStart
            TestLog("INFO", "唤醒", "启动被动唤醒")
            WakeupMsgSimulationStart(0x47F, 8, "CANFD", 100, b"\x00" * 8)
        if mode in (None, 'active'):
            TestLog("INFO", "唤醒", "启动主动唤醒(KL15 ON)")
            ctx.bob_ctrl.set_power('KL15', True)
    except Exception as e:
        TestLog("WARNING", "唤醒", f"启动唤醒异常: {e}")


def nm_stop_wakeup(mode: str | None = None):
    """
    停止唤醒
    """
    try:
        if mode == 'active':
            ctx.bob_ctrl.set_power('KL15', False)
        elif mode == 'passive':
            from common.wakeup import WakeupMsgSimulationStop
            WakeupMsgSimulationStop()
        else:
            try:
                from common.wakeup import WakeupMsgSimulationStop
                WakeupMsgSimulationStop()
            except Exception:
                pass
            try:
                ctx.bob_ctrl.set_power('KL15', False)
            except Exception:
                pass
        TestLog("INFO", "唤醒", "停止唤醒")
    except Exception as e:
        TestLog("WARNING", "唤醒", f"停止唤醒异常: {e}")


def lin_goto_sleep(lin_channel: int | None = None) -> bool:
    """发送linGotoSleep命令帧"""
    try:
        ch = lin_channel if lin_channel is not None else DEFAULT_LIN_CHANNEL
        msg = sl_linmsg(0x3C)
        msg.set_dlc(8)
        msg.StartResp()
        msg.UpdateResponse(bytes([0x00] + [0xFF] * 7))
        lin_update_response(ch, msg.msg)
        lin_output(ch, 0x3C)
        TestLog("INFO", "LIN操作", "发送Go-To-Sleep 0x3C帧: 00 FF FF FF FF FF FF FF")
        return True
    except Exception as e:
        TestLog("WARNING", "LIN操作", f"linGotoSleep失败: {e}")
        return False

def nm_power_on():
    """
    nm上电
    """
    try:
        v = P.NMInfo.Vnormal
        TestLog("INFO", "电源设置", f"设置电压为 {v:.2f}V 并上电")

        ctx.power_ctrl.set_voltage(v)
        ctx.power_ctrl.on()
        ctx.bob_ctrl.set_power('KL30', True)
        ctx.can.set_info('ts_KL30_ON_ms', sl_time().timestamp())
        return True
    except Exception as e:
        TestLog("WARNING", "电源设置", f"电源控制异常: {e}")
        return False


# 获取报文
def nm_wait_first_lin_msg(timeout_ms: int,
                          dir: Optional[str] = None,
                          interval: bool = False,
                          baseline_ms: Optional[float] = None,
                          max_ms: int = 60000):

    ms = max(0, int(timeout_ms))

    ctx.can.set_info('lin_first_frames', True)
    ctx.can.set_info('lin_first_frame_time_hw_ms', None)

    ctx.can.set_info('lin_first_frame_id', None)
    if dir in ("tx", "TX"):
        ctx.can.set_info('lin_first_frame_dir', "TX")
    elif dir in ("rx", "RX"):
        ctx.can.set_info('lin_first_frame_dir', "RX")
    else:
        ctx.can.set_info('lin_first_frame_dir', None)

    if dir in ("tx", "TX"):
        event_name = gLinTextEvent_TX
    elif dir in ("rx", "RX"):
        event_name = gLinTextEvent_RX
    else:
        sim_mode = ctx.can.get_info('lin_mode')
        event_name = gLinTextEvent_TX if sim_mode == "slave" else gLinTextEvent_RX

    base = float(baseline_ms) if baseline_ms is not None else sl_time().timestamp()
    ret = bool(TextEvents().wait(event_name, ms))

    if interval:
        hw_ms = ctx.can.get_info('lin_first_frame_time_hw_ms')

        interval_val = None
        try:
            if hw_ms is not None:
                e_hw = float(hw_ms) - float(base)
                if 0 <= e_hw <= float(max_ms):
                    interval_val = e_hw
        except Exception:
            pass

        if interval_val is None:
            interval_val = sl_time().timestamp() - base
        return ret, interval_val

    return ret

def nm_wait_no_nm_for(duration_ms: int, max_wait_ms: int) -> bool:
    """等待连续 duration_ms 时间没有新的 NM 报文到达"""
    deadline_ms = sl_time().timestamp() + max_wait_ms
    while sl_time().timestamp() < deadline_ms:
        base_len = len(_get_nm_frames_from_log())
        start_ms = sl_time().timestamp()
        while sl_time().timestamp() - start_ms < duration_ms:
            cur_len = len(_get_nm_frames_from_log())
            if cur_len > base_len:
                break
            sl_time().sleep(1000)
        else:
            return True
    return False


def _get_nm_frames_from_log() -> list[tuple[float, bytes]]:
    frames: list[tuple[float, bytes]] = []
    try:
        nm_id = int(P.ECUInfo.NMMsgID_int)
    except Exception:
        return frames

    start_ms = ctx.can.get_info("nm_frames_start_ms")
    try:
        messages = list(ctx.can.messages)
    except Exception:
        return frames

    for m in messages:
        try:
            mid = int(getattr(m, "id", getattr(m, "msgid", 0)) or 0)
            if mid != nm_id:
                continue
            t = float(getattr(m, "time_ms", 0.0) or 0.0)
            if start_ms is not None:
                try:
                    if t < float(start_ms):
                        continue
                except Exception:
                    pass
            payload_hex = getattr(m, "payload_hex", "") or ""
            try:
                payload_bytes = bytes.fromhex(payload_hex)
            except Exception:
                payload_bytes = b""
            frames.append((t, payload_bytes))
        except Exception:
            continue

    frames.sort(key=lambda x: x[0])
    return frames


# 校验报文
def nm_check_cycle_interval(skip_first_n: Optional[int] = None) -> bool:
    """
    NM正常周期检查
    """
    try:
        nimm_cfg = P.NMInfo.NimmediateSend
        nimm = int(nimm_cfg if skip_first_n is None else skip_first_n)
        tnorm = P.NMInfo.TnormalCycle_ms
        tol = P.NMInfo.TnormalDeviation_pct
        low = tnorm * (1 - tol / 100.0)
        high = tnorm * (1 + tol / 100.0)

        frames = _get_nm_frames_from_log()
        cnt = len(frames)
        if cnt == 0:
            TestLog("WARNING", "周期检查", "窗口内未采集到NM帧")
            return True
        if cnt <= nimm:
            TestLog("FAIL", "周期检查", f"样本不足: 总帧数={cnt} ≤ 跳过帧数={nimm}")
            return False

        errors = []
        start_i = max(1, nimm)
        for i in range(start_i, cnt):
            try:
                interval = float(frames[i][0]) - float(frames[i - 1][0])
            except Exception:
                interval = float('nan')
            ok = (interval == interval) and (low <= interval <= high)
            TestLog("PASS" if ok else "FAIL", "逐帧周期检查",
                    f"第{i+1}帧间隔={interval:.1f}ms, 允许=[{low:.1f}, {high:.1f}]ms (期望≈{tnorm:.0f}ms±{tol}%)")
            if not ok:
                errors.append((i, interval))

        if not errors:
            TestLog("PASS", "周期检查结果", f"全部满足正常周期，共检查 {cnt - start_i} 个间隔")
            return True
        else:
            bads = ", ".join([f"#{idx+1}:{ival:.1f}ms" for idx, ival in errors[:10]])
            TestLog("FAIL", "周期检查结果", f"存在不满足的间隔 {len(errors)} 个（示例: {bads}）")
            return False
    except Exception as e:
        TestLog("FAIL", "周期检查异常", f"异常: {e}")
        return False



def _nm_read_avg_current_ma(samples: int = 10, interval_ms: int = 1) -> float:
    """读取电源电流"""
    vals_ma = []
    for _ in range(max(1, samples)):
        try:
            cur_a = ctx.power_ctrl.get_current()
            if cur_a is not None:
                vals_ma.append(float(cur_a) * 1000.0)
        except Exception:
            pass
        sl_time().sleep(max(0, int(interval_ms)))
    if not vals_ma:
        return -1.0
    return sum(vals_ma) / len(vals_ma)


def nm_check_comm_stop_and_sleep_current(timeout_ms: int, quiet_ms: int = 200) -> bool:
    """
    校验通信停止后平均睡眠电流是否低于Isleep
    """
    sl_time().sleep(2000)
    ret_stop = nm_wait_no_nm_for(duration_ms=min(quiet_ms, timeout_ms), max_wait_ms=max(quiet_ms, timeout_ms))
    TestLog("PASS" if ret_stop else "FAIL", "通信停止检查", f"在{timeout_ms}ms窗口内{('检测到通信停止' if ret_stop else '未检测到通信停止')}, 静默判定窗口={min(quiet_ms, timeout_ms)}ms")

    # 电流测量
    isleep_ma = P.ECUInfo.ISleep
    avg_ma = _nm_read_avg_current_ma(samples=10, interval_ms=1)
    if avg_ma < 0:
        TestLog("FAIL", "睡眠电流测量", "电源电流读取失败")
        return False

    ret_curr = (avg_ma <= isleep_ma)
    TestLog("PASS" if ret_curr else "FAIL", "睡眠电流检查", f"平均={avg_ma:.1f} mA, 阈值(Isleep)={isleep_ma:.1f} mA")

    return ret_stop and ret_curr


def nm_wakeup_and_wait_first_msg(mode: str | None, timeout_ms: int) -> bool:
    """触发唤醒并在超时内等待“任意报文"""
    ctx.can.clear_messages()
    nm_start_wakeup(mode)

    twu = max(0, int(timeout_ms))
    ret = bool(TextEvents().wait(gCanTextEvent_RX, twu))
    TestLog("PASS" if ret else "FAIL", "唤醒后等待任意报文", f"在{twu}ms内{('收到至少1帧报文' if ret else '未收到报文')}")
    return ret



def nm_check_repeat_message_state_after_wakeup(mode: str) -> bool:
    """
    重复阶段检查
    """
    frames: list[tuple] = _get_nm_frames_from_log()
    if not frames:
        TestLog("WARNING", "重复阶段检查", "未记录到NM帧")
        return False

    if mode not in ('active', 'passive'):
        TestLog("FAIL", "重复阶段检查", f"非法模式: {mode}，仅支持 'active' 或 'passive'")
        return False

    expected_req_bit = 1 if mode == 'active' else 0

    trep = P.NMInfo.TrepeatMessage_ms
    nimm = P.NMInfo.NimmediateSend
    timm = P.NMInfo.TimmediateCycle_ms
    tnorm = P.NMInfo.TnormalCycle_ms
    dev_im = P.NMInfo.TimmediateDeviation_pct
    dev_no = P.NMInfo.TnormalDeviation_pct

    im_min = timm * (1 - dev_im / 100.0)
    im_max = timm * (1 + dev_im / 100.0)
    no_min = tnorm * (1 - dev_no / 100.0)
    no_max = tnorm * (1 + dev_no / 100.0)

    t0 = float(frames[0][0])
    period_error = False
    repeat_bit_error = False
    repeat_sts_error = False

    for i in range(1, len(frames)):
        tm_i = float(frames[i][0])
        tm_prev = float(frames[i - 1][0])
        internal_time = tm_i - t0
        if internal_time > trep:
            break
        interval = tm_i - tm_prev

        # 周期性检查
        if (mode == 'active') and (0 < i < nimm):
            ok = (im_min <= interval <= im_max)
            TestLog("PASS" if ok else "FAIL", "重复阶段-立即周期",
                    f"第{i+1}帧间隔={interval:.1f}ms, 允许=[{im_min:.1f}, {im_max:.1f}]ms (期望≈{timm}ms±{dev_im}%)")
            if not ok:
                period_error = True
        else:
            ok = (no_min <= interval <= no_max)
            TestLog("PASS" if ok else "FAIL", "重复阶段-正常周期",
                    f"第{i+1}帧间隔={interval:.1f}ms, 允许=[{no_min:.1f}, {no_max:.1f}]ms (期望≈{tnorm:.0f}ms±{dev_no}%)")
            if not ok:
                period_error = True

        # 位检查（窗口内的90%）
        if internal_time < 0.9 * trep:
            payload: bytes = frames[i][1] if len(frames[i]) > 1 else b""

            check_req_bit = P.NMInfo.RepeatMessageBit0 == 1
            req_bit_idx = P.NMInfo.ReptMsgBit0

            # RepeatMessageRequestBit（Byte1.bitX）
            bit_req = _bit(payload[1], req_bit_idx) if len(payload) > 1 else None
            if check_req_bit:
                ok_req = (bit_req == expected_req_bit)
                TestLog("PASS" if ok_req else "FAIL", "RepeatMessageRequestBit",
                        f"Byte1.bit{req_bit_idx}={bit_req}, 期望={expected_req_bit}, t={internal_time:.1f}ms")
                if not ok_req:
                    repeat_bit_error = True
            else:
                TestLog("INFO", "RepeatMessageRequestBit",
                        f"跳过检查(RepeatMessageBit0=0)，实际 Byte1.bit{req_bit_idx}={bit_req}, t={internal_time:.1f}ms")

            # RepeatMsgSts（Byte2.bit0）始终检查
            bit_sts = _bit(payload[2], 0) if len(payload) > 2 else None
            ok_sts = (bit_sts == 1)
            TestLog("PASS" if ok_sts else "FAIL", "RepeatMsgSts",
                    f"Byte2.bit0={bit_sts}, 期望=1, t={internal_time:.1f}ms")
            if not ok_sts:
                repeat_sts_error = True

    ret = (not period_error) and (not repeat_bit_error) and (not repeat_sts_error)
    TestLog("PASS" if ret else "FAIL", "重复阶段摘要",
            f"period_ok={not period_error}, reqbit_ok={not repeat_bit_error}, stsbit_ok={not repeat_sts_error}")
    return ret




def _group_msg_times_by_id(start_ms: Optional[float] = None) -> dict[int, list[float]]:
    result: dict[int, list[float]] = {}
    try:
        messages = list(ctx.can.messages)
    except Exception:
        return result
    for m in messages:
        try:
            t = float(getattr(m, "time_ms", 0.0) or 0.0)
            if start_ms is not None and t < start_ms:
                continue
            mid = int(getattr(m, "id", 0) or 0)
        except Exception:
            continue
        bucket = result.get(mid)
        if bucket is None:
            bucket = []
            result[mid] = bucket
        bucket.append(t)
    return result


def _period_stats(times: list[float]) -> tuple[float, float, int]:
    if len(times) <= 1:
        return 0.0, 0.0, 0
    max_p = 0.0
    sum_p = 0.0
    cnt = 0
    prev = times[0]
    for t in times[1:]:
        dt = t - prev
        if dt < 0:
            prev = t
            continue
        sum_p += dt
        cnt += 1
        if dt > max_p:
            max_p = dt
        prev = t
    return max_p, sum_p, cnt



def nm_check_nm_and_app_msgs(mode: str) -> bool:
    try:
        if mode not in ('active', 'passive'):
            TestLog("FAIL", "NM+应用联动", f"非法模式: {mode}，仅支持 'active' 或 'passive'")
            return False

        try:
            nm_id_int = int(P.ECUInfo.NMMsgID_int)
        except Exception:
            TestLog("FAIL", "NM+应用联动", "未配置NM报文ID (P.ECUInfo.NMMsgID_int)")
            return False

        tnm = P.NMInfo.TNMtimeout_ms
        tnorm = P.NMInfo.TnormalCycle_ms

        times_by_id = _group_msg_times_by_id()
        if not times_by_id:
            TestLog("FAIL", "NM+应用联动", "长保持窗口内未记录到任何报文")
            return False

        select_app_id = None
        max_cnt = 0
        for mid, times in times_by_id.items():
            try:
                if int(mid) == nm_id_int:
                    continue
            except Exception:
                continue
            cnt = len(times or [])
            if cnt > max_cnt:
                max_cnt = cnt
                select_app_id = mid

        if select_app_id is None:
            TestLog("FAIL", "NM+应用联动", "窗口内未接收到任何应用层报文（非NM）")
            return False

        nm_times = times_by_id.get(nm_id_int, [])
        app_times = times_by_id.get(select_app_id, [])

        try:
            end_ms = max(max(ts) for ts in times_by_id.values() if ts)
        except Exception:
            end_ms = 0.0

        nm_last_ms = nm_times[-1] if nm_times else 0.0
        app_last_ms = app_times[-1] if app_times else 0.0
        nm_internal = end_ms - nm_last_ms if nm_last_ms > 0 else float('inf')
        app_internal = end_ms - app_last_ms if app_last_ms > 0 else float('inf')

        if mode == 'passive':
            TestLog("INFO", "NM+应用联动", f"(passive) 选择应用报文: 0x{int(select_app_id):x}, AppMsgInternal={app_internal:.0f}ms")

            if app_internal <= tnm:
                app_pmax, app_sum_p, app_period_cnt = _period_stats(app_times)
                app_avg = (app_sum_p / app_period_cnt) if app_period_cnt > 0 else None
                app_avg_eff = (app_avg if (app_avg is not None and app_avg > 0) else max(1000.0, app_pmax or 0.0))

                app_ok = (app_pmax <= 2 * float(app_avg_eff))
                if app_ok:
                    TestLog("PASS", "NM+应用联动", f"期望：DUT 长保持期间发送应用报文；实际：接收到且周期正常 (App=0x{int(select_app_id):x})")
                    return True
                else:
                    TestLog("FAIL", "NM+应用联动", f"接收到 应用(0x{int(select_app_id):x})，但应用周期异常")
                    return False
            else:
                TestLog("FAIL", "NM+应用联动", f"在TNMtimeout内未收到 应用(0x{int(select_app_id):x})")
                return False

        # active
        TestLog("INFO", "NM+应用联动", f"(active) 选择应用报文: 0x{int(select_app_id):x}, NMMsgInternal={nm_internal:.0f}ms, AppMsgInternal={app_internal:.0f}ms")

        if nm_internal <= tnm and app_internal <= tnm:
            nm_pmax, _, _ = _period_stats(nm_times)
            app_pmax, app_sum_p, app_period_cnt = _period_stats(app_times)
            app_avg = (app_sum_p / app_period_cnt) if app_period_cnt > 0 else None
            app_avg_eff = (app_avg if (app_avg is not None and app_avg > 0) else max(1000.0, app_pmax or 0.0))

            nm_ok = (nm_pmax <= 2 * float(tnorm))
            app_ok = (app_pmax <= 2 * float(app_avg_eff))

            if nm_ok and app_ok:
                TestLog("PASS", "NM+应用联动", f"期望：DUT 长保持期间发送 NM 与应用报文；实际：均满足且周期无异常 (NM=0x{nm_id_int:x}, App=0x{int(select_app_id):x})")
                return True
            elif nm_ok and not app_ok:
                TestLog("FAIL", "NM+应用联动", f"收到 NM(0x{nm_id_int:x}) 与 应用(0x{int(select_app_id):x})，NM周期正常，应用周期异常")
                return False
            elif (not nm_ok) and app_ok:
                TestLog("FAIL", "NM+应用联动", f"收到 NM(0x{nm_id_int:x}) 与 应用(0x{int(select_app_id):x})，应用周期正常，NM周期异常")
                return False
            else:
                TestLog("FAIL", "NM+应用联动", f"收到 NM(0x{nm_id_int:x}) 与 应用(0x{int(select_app_id):x})，NM与应用周期均异常")
                return False

        elif nm_internal <= tnm and app_internal > tnm:
            TestLog("FAIL", "NM+应用联动", f"在TNMtimeout内仅收到 NM(0x{nm_id_int:x})，未收到应用(0x{int(select_app_id):x})")
            return False
        elif nm_internal > tnm and app_internal <= tnm:
            TestLog("FAIL", "NM+应用联动", f"在TNMtimeout内仅收到 应用(0x{int(select_app_id):x})，未收到 NM(0x{nm_id_int:x})")
            return False
        else:
            TestLog("FAIL", "NM+应用联动", f"在TNMtimeout内未收到 NM(0x{nm_id_int:x}) 与 应用(0x{int(select_app_id):x})")
            return False

    except Exception as e:
        TestLog("FAIL", "NM+应用联动", f"检查异常: {e}")
        return False



def nm_check_ready_sleep_app_msgs(window_ms: int, start_ms: Optional[float] = None) -> bool:
    """ReadySleep 应用报文校验"""
    try:
        try:
            nm_id_int = int(P.ECUInfo.NMMsgID_int)
        except Exception:
            TestLog("FAIL", "ReadySleep应用报文", "未配置NM报文ID (P.ECUInfo.NMMsgID_int)")
            return False

        times_by_id = _group_msg_times_by_id()
        if not times_by_id:
            TestLog("FAIL", "ReadySleep应用报文", "未记录到任何报文，无法判定")
            return False

        win = max(0, int(window_ms))

        last_times = []
        for times in times_by_id.values():
            if not times:
                continue
            last_times.append(times[-1])

        if start_ms is None:
            end_ms = max(last_times) if last_times else 0.0
            start = max(0.0, end_ms - win)
        else:
            start = float(start_ms)
            end_ms = start + win

        found_ids = []
        for mid, times in times_by_id.items():
            if not times:
                continue
            try:
                if int(mid) == nm_id_int:
                    continue
            except Exception:
                pass
            tlast = times[-1]
            if start < tlast <= end_ms:
                found_ids.append(mid)

        if found_ids:
            show = ", ".join([f"0x{int(m):x}" for m in found_ids[:5]])
            TestLog("PASS", "ReadySleep应用报文", f"在窗口内收到应用层报文：{show}{' 等' if len(found_ids)>5 else ''}")
            return True
        else:
            TestLog("FAIL", "ReadySleep应用报文", "在窗口内未收到任何应用层报文")
            return False
    except Exception as e:
        TestLog("FAIL", "ReadySleep应用报文", f"检查异常: {e}")
        return False







