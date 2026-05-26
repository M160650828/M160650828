import time

from common.context import ctx
from slplus.can import register_canmsg_handler, unregister_canmsg_handler
from slplus.can import sl_can, sl_canmsg
from env.config import DEFAULT_CAN_CHANNELS
from uvtest.testlog import TestLog
from slplus.event import TextEvents

from common.params import P

gCanTextEvent_RX = "CAN Frame is Received"
gCanTextEvent_TX = "CAN Frame is Transmitted"

def active_test_can_channels(status:bool = True, purpose="cantp"):
    """
    CAN通道配置函数
    """
    action_str = ""
    if status is True:
        action_str = "active"
    else:
        action_str = "deactive"

    try:
        # 获取CAN通道配置
        cans = DEFAULT_CAN_CHANNELS
        if not cans:
            TestLog("FAIL", "CAN通道设置", "none can channels selected by user")
            return False

        max_channels = min(len(cans), len(DEFAULT_CAN_CHANNELS))
        TestLog("INFO", action_str, action_str+f"所有DEFAULT_CAN_CHANNELS通道")

        if status:
            register_canmsg_handler(_on_canmsg)
        else:
            unregister_canmsg_handler(_on_canmsg)

        activated_count = 0

        for i in range(max_channels):
            can_ch = cans[i]
            try:
                print("[DEBUG]" + action_str + f"{can_ch}")
                if status:
                    sl_can(can_ch).active()
                else:
                    sl_can(can_ch).deactive()
                print(f"[DEBUG] CAN通道 {can_ch} " + action_str +"成功")

                activated_count += 1
                TestLog("INFO", "通道" + action_str, "成功" + action_str +f"CAN通道 {can_ch}")

            except Exception as e:
                TestLog("WARNING", "通道" + action_str, action_str+ f" CAN通道 {can_ch} 失败: {e}")
                import traceback
                print(f"[DEBUG] 通道激活异常详情: {traceback.format_exc()}")

        if activated_count > 0:
            TestLog("PASS", "CAN通道设置", "成功" + action_str + f"{activated_count}个CAN通道用于{purpose}")
            return True
        else:
            TestLog("FAIL", "CAN通道设置", "未能" + action_str + f"任何CAN通道用于{purpose}")
            return False

    except Exception as e:
        TestLog("FAIL", "CAN通道设置", f"CAN通道设置失败: {e}")
        import traceback
        TestLog("DEBUG", "CAN通道设置", f"详细错误: {traceback.format_exc()}")
        return False


def can_power_setup_and_communication_check(normal_voltage=None, stable_time=None):
    """
    CAN电源设置与通信检查
    包括：电源设置、KL30上电、唤醒启动、CAN通信状态检查
    """
    from common.wakeup import WakeupStart

    try:
        if normal_voltage is None:
            normal_voltage = P.CANInfo.Vnormal
        if stable_time is None:
            stable_time = P.CANInfo.Tstable_s
        TestLog("INFO", "CAN测试设置", "开始CAN测试设置和通信检查")

        # Step1: 设置DUT供电电压
        TestLog("INFO", "Step1", f"设置DUT供电电压为 {normal_voltage:.2f}V")
        ctx.power_ctrl.set_voltage(normal_voltage)
        ctx.power_ctrl.on()
        from env.config import CAN_TERMINATION
        for can_ch, enable_term in CAN_TERMINATION.items():            
            if enable_term:
                ctx.bob_ctrl.set_resistance(True, ch=can_ch)
                TestLog("INFO", "ETS6124", f"CAN{can_ch} 终端电阻已启用")

        # Step2: 执行KL30上电
        TestLog("INFO", "Step2", "执行KL30上电")
        ctx.bob_ctrl.set_power('KL30', True)
        ctx.bob_ctrl.set_power('KL15', True)

        # Step3: 根据DUT通信唤醒方式启动唤醒
        TestLog("INFO", "Step3", "根据DUT通信唤醒方式，启动ECU唤醒")
        WakeupStart()

        # Step5: 等待通信稳定并检查通信状态
        TestLog("INFO", "Step5", f"等待 {stable_time}s 至CAN通信稳定")
        ret = check_can_communication_state(stable_time)

        if ret != 0:
            TestLog("FAIL", "CAN通信检查", "CAN通信状态检查失败")
            return -1

        TestLog("PASS", "CAN测试设置", "CAN测试设置和通信检查完成")

        payload=(b"\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02")
        canfd_msg = sl_canmsg(id=0x222,is_fd=True,dlc=9,payload=payload)
        TestLog("INFO", "CAN测试设置", "发送报文")
        #sl_can(DEFAULT_CAN_CHANNELS[0]).send_canmsg(canfd_msg)
        TestLog("INFO", "CAN测试设置", "发送结束")
        return 0

    except Exception as e:
        TestLog("FAIL", "CAN测试设置", f"CAN测试设置失败: {e}")
        import traceback
        TestLog("DEBUG", "CAN测试设置", f"详细错误: {traceback.format_exc()}")
        return -1


'''
事件处理
'''
def _on_canmsg(bustype, busid, msg, cookie):
    """CAN 总线报文回调"""
    if bustype != 2:
        return

    obj = msg
    try:
        msg_id = int(getattr(obj, 'msgid', 0) or 0)
        dlc = int(getattr(obj, 'dlc', 8) or 8)
        payload = getattr(obj, 'payload', b'') or b''
        dirv = getattr(obj, 'dirv', 0) or 0
        dir_str = 'TX' if dirv == 1 else 'RX'

        try:
            payload_hex_debug = ''.join(f"{b:02X}" for b in payload) if payload else ""
            print(
                f"[CANTP] 收到CAN报文: 通道={busid}, 方向={dir_str}, "
                f"ID=0x{msg_id:X}, DLC={dlc}, 数据=[{payload_hex_debug}]"
            )
        except Exception:
            pass

        try:
            event_name = gCanTextEvent_TX if (dir_str == "TX") else gCanTextEvent_RX
            TextEvents().supply(event_name)
        except Exception:
            pass

        try:
            wakeup_msg_id = int(ctx.can.get_info('wakeup_msg_id') or 0)
            if wakeup_msg_id and msg_id == wakeup_msg_id:
                return
        except Exception:
            pass

        try:
            payload_hex = ''.join(f"{b:02X}" for b in payload) if payload else ""
            now_ms = time.time() * 1000
            ctx.can.add_message(id=msg_id, time_ms=now_ms, dlc=dlc, channel=busid, payload_hex=payload_hex, direction=dirv)
        except Exception:
            pass
    except Exception:
        pass


def _tp_build_rx_msg_info(messages):
    stats = {}
    for m in messages:
        msg_id = m.id
        info = stats.get(msg_id)
        if info is None:
            info = {
                "count": 0,
                "dlc": m.dlc,
                "channel": m.channel,
                "msgId": msg_id,
                "time": m.time_ms,
                "periodSum": 0.0,
                "lastPayload": "",
            }
            stats[msg_id] = info
        else:
            prev_time = info["time"]
            period = m.time_ms - prev_time
            info["periodSum"] += period
            info["time"] = m.time_ms
        info["count"] += 1
        info["lastPayload"] = m.payload_hex
    return stats




def check_can_communication_state(wait_time=5):
    TestLog("INFO", "CAN通信状态检查", f"等待 {wait_time}s 检查通信状态")
    from slplus.time import sl_time
    try:
        ctx.can.clear_messages()
    except Exception:
        pass

    try:
        ms = max(0, int(wait_time * 1000))
        event_detected = bool(TextEvents().wait(gCanTextEvent_RX, ms))
    except Exception:
        sl_time().sleep(int(wait_time * 1000))
        event_detected = False

    try:
        rx_stats = _tp_build_rx_msg_info(ctx.can.messages)
    except Exception:
        rx_stats = {}

    frame_cnt = len(rx_stats)
    ctx.can.set_info("gECUMsgIDCount", frame_cnt)
    err_cnt = ctx.can.get_info("gErrorFrameCount") or 0

    TestLog(
        "INFO",
        "CAN通信状态",
        f"gECUMsgIDCount = {frame_cnt}, event_detected = {event_detected}, gErrorFrameCount = {err_cnt}",
    )

    if (frame_cnt > 0 or event_detected) and err_cnt == 0:
        TestLog("PASS", "CAN通信状态检查", "DUT通信正常，总线上有报文的传输，且无错误帧")
        return 0
    if (frame_cnt > 0 or event_detected) and err_cnt > 0:
        TestLog("WARNING", "CAN通信状态检查", "DUT通信正常，总线上有报文的传输，但有错误帧")
        return 0
    if frame_cnt == 0 and err_cnt > 0:
        TestLog("FAIL", "CAN通信状态检查", "DUT通信不正常，总线上无报文的传输，有错误帧")
        return -1

    TestLog("FAIL", "CAN通信状态检查", "DUT通信未恢复")
    return -1


