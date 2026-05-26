import time
from env.config import DEFAULT_CAN_CHANNELS
from uvtest.testlog import TestLog
from common.utils import TimerCyclic
from common.can_utils import send_canmsg
from common.params import P
from common.context import ctx


def WakeupStart():
    """启动唤醒"""
    power_mode = P.ECUInfo.PowerMode
    ecu_type = P.ProjectInfo.ECUType
    use_msg = (power_mode != 0) and (ecu_type < 4)

    if use_msg:
        TestLog("DEBUG", "DUT控制", "使用网络报文唤醒")
        try:
            # 启动唤醒报文模拟
            WakeupMsgSimulationStart(
                msg_id=P.ECUInfo.WakeupMsgID_int,
                msg_dlc=P.ECUInfo.WakeupMsgDLC,
                msg_type=P.ECUInfo.WakeupMsgType,
                cycle_time=P.ECUInfo.WakeupMsgPeriod_ms,
                data=P.ECUInfo.WakeupMsgData_bytes,
            )

            TestLog("INFO", "", f"开始按周期发送唤醒报文：ID=0x{P.ECUInfo.WakeupMsgID_int:X}, 周期={P.ECUInfo.WakeupMsgPeriod_ms}ms")
            return 0
        except Exception as e:
            TestLog("WARNING", "", f"启动失败: {e}")
            return 0
    else:
        TestLog("INFO", "", "使用KL15硬线唤醒")
        ctx.bob_ctrl.set_power('KL15', True)
        return 0

def WakeupStop():
    """停止唤醒"""
    power_mode = P.ECUInfo.PowerMode
    ecu_type = P.ProjectInfo.ECUType
    use_msg = (power_mode != 0) and (ecu_type < 4)

    TestLog("DEBUG", "", "停止唤醒")
    if use_msg:
        return True if WakeupMsgSimulationStop() else False
    else:
        return ctx.bob_ctrl.set_power('KL15', False)


def WakeupMsgSimulationStart(msg_id, msg_dlc, msg_type, cycle_time, data, can_channel: int | None = None, timer_id: str | None = None):
    """
    唤醒消息
    """
    from common.can_utils import canmsg_create
    try:
        msg_id = int(msg_id)
        msg_dlc = int(msg_dlc)
        cycle_time = int(cycle_time)

        TestLog("DEBUG", "", f"开始唤醒消息模拟 - ID: 0x{msg_id:x}, DLC: {msg_dlc}, 类型: {msg_type}, 周期: {cycle_time}ms")

        is_canfd = (str(msg_type).upper() == "CANFD")

        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("WakeupMsgSimulationStart data must be bytes/bytearray")
        data_bytes = bytes(data)[:msg_dlc]
        if len(data_bytes) < msg_dlc:
            data_bytes += bytes(msg_dlc - len(data_bytes))

        TestLog("DEBUG", "唤醒消息模拟", f"数据内容: {data_bytes.hex().upper()}")

        msg = canmsg_create(
            msg_id,
            msg_dlc,
            data=data_bytes,
            rtr=0,
            fdf=1 if is_canfd else 0,
            brs=1 if is_canfd else 0,
            ext=0
        )

        if msg is None:
            TestLog("FAIL", "", "创建唤醒消息失败")
            return False


        ch = DEFAULT_CAN_CHANNELS[0] if can_channel is None else int(can_channel)

        # 发送一次
        send_canmsg(ch, msg=msg)
        TestLog("DEBUG", "唤醒消息模拟", "立即发送唤醒消息")

        # 设置周期性定时器
        tid = timer_id or "wakeup_timer"
        ret = TimerCyclic.start(tid, cycle_time, send_canmsg, ch, msg=msg)
        TestLog("DEBUG", "", f"设置周期性定时器，周期: {cycle_time}ms")
        if not ret:
            TestLog("FAIL", "", "启动定时器失败")
            return False

        TestLog("PASS", "", "唤醒消息模拟启动成功")
        return True

    except Exception as e:
        TestLog("FAIL", "", f"启动唤醒消息模拟失败: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
        return False


def WakeupMsgSimulationStop(timer_id: str | None = None):
    """
    停止唤醒消息模拟
    """
    try:
        TestLog("INFO", "", "停止唤醒消息模拟")

        tid = timer_id or "wakeup_timer"
        result = TimerCyclic.stop(tid)

        if result:
            TestLog("PASS", "", "唤醒消息模拟停止成功")
            return True
        else:
            TestLog("DEBUG", "", "未发现活动定时器，跳过")
            return True

    except Exception as e:
        TestLog("FAIL", "", f"停止唤醒消息模拟失败: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
        return False

