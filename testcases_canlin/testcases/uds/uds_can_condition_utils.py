import time

from uvtest.testlog import TestLog

from common.can_utils import canmsg_create, send_canmsg
from common.utils import TimerCyclic
from env.config import DEFAULT_CAN_CHANNELS


__all__ = ("start_nrc22_condition", "stop_nrc22_condition", "stop_all_nrc22_conditions")
_ACTIVE_CONDITIONS = {}
_DLC_LENGTH = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8,
               9: 12, 10: 16, 11: 20, 12: 24, 13: 32, 14: 48, 15: 64}

def _value(condition, name, default=None):
    value = condition.get(name, default) if isinstance(condition, dict) else getattr(condition, name, default)
    return default if value is None else value

def _raw(condition, name):
    raw = condition if isinstance(condition, dict) else getattr(condition, "raw", {})
    return raw.get(name) if isinstance(raw, dict) else None

def _timer_id(condition):
    return f"uds_nrc22_{_value(condition, 'ConditionName', 'NRC22')}_{_value(condition, 'MessageID', 0):03X}"

def _runnable(condition):
    return _value(condition, "MessageID", 0) > 0 and _value(condition, "MessageDLC", 0) > 0 \
        and _value(condition, "SignalLength", 0) > 0

def _signal_value(condition, active):
    raw = _raw(condition, "TriggerRawValue" if active else "NormalRawValue")
    if raw is None and active:
        raw = _raw(condition, "SignalValue")
    if raw is not None:
        return raw
    physical = _value(condition, "TriggerPhysicalValue" if active else "NormalPhysicalValue", 0.0)
    coefficient = _value(condition, "VehicleSpeedCoefficientValue", 1.0) or 1.0
    return int(round(physical / coefficient))

def _write_signal(data, start, length, value, big_endian=False):
    if length <= 0:
        return
    byte_index, bit_index = divmod(start, 8)
    for offset in range(length):
        if not big_endian:
            byte_index, bit_index = divmod(start + offset, 8)
        if byte_index < len(data):
            mask = 1 << bit_index
            data[byte_index] = data[byte_index] | mask if value & (1 << offset) else data[byte_index] & ~mask
        if big_endian:
            bit_index -= 1
            if bit_index < 0:
                byte_index, bit_index = byte_index + 1, 7

def _message(condition, active):
    dlc = _value(condition, "MessageDLC", 8)
    is_fd = str(_value(condition, "MessageType", "CAN")).upper() in ("CANFD", "FD", "1", "TRUE")
    big = str(_value(condition, "MessageDatabaseType", 1)).lower() in ("0", "big", "big_endian", "motorola", "msb")
    data = bytearray(_DLC_LENGTH.get(dlc, 8) if is_fd else min(max(dlc, 0), 8))
    _write_signal(data, _value(condition, "SignalValidBitStartBit", 0), _value(condition, "SignalValidBitLength", 0), 1, big)
    _write_signal(data, _value(condition, "SignalStartBit", 0), _value(condition, "SignalLength", 0), _signal_value(condition, active), big)
    if _value(condition, "MessageE2EFlag", 0):
        TestLog("WARNING", "NRC22条件", f"{_value(condition, 'ConditionName', 'unknown')} 配置了E2EFlag，当前仅发送原始信号，暂未计算E2E")
    return canmsg_create(_value(condition, "MessageID", 0), dlc, data=bytes(data), fdf=int(is_fd), brs=int(is_fd), ext=0)

def start_nrc22_condition(condition, settle_s=2.0):
    if not _runnable(condition):
        TestLog("WARNING", "NRC22条件", f"{_value(condition, 'ConditionName', 'unknown')} 条件报文配置不完整，跳过条件触发")
        return False
    msg = _message(condition, active=True)
    channel = _value(condition, "MessageChannel", 0) or int(DEFAULT_CAN_CHANNELS[0])
    period = _value(condition, "MessagePeriod", 100)
    timer_id = _timer_id(condition)
    ok = TimerCyclic.start(timer_id, period, send_canmsg, channel, msg=msg)
    if ok:
        _ACTIVE_CONDITIONS[timer_id] = condition
        TestLog("INFO", "NRC22条件", f"已触发 {_value(condition, 'ConditionName', 'unknown')}，MsgID=0x{msg.id:X}, 周期={period}ms")
        time.sleep(settle_s)
    return ok

def stop_nrc22_condition(condition, settle_s=0.2):
    timer_id = _timer_id(condition)
    ok = TimerCyclic.stop(timer_id)
    _ACTIVE_CONDITIONS.pop(timer_id, None)
    if _runnable(condition):
        send_canmsg(_value(condition, "MessageChannel", 0) or int(DEFAULT_CAN_CHANNELS[0]), msg=_message(condition, active=False))
        time.sleep(settle_s)
    TestLog("INFO", "NRC22条件", f"已清理 {_value(condition, 'ConditionName', 'unknown')}")
    return ok

def stop_all_nrc22_conditions():
    for _, condition in list(_ACTIVE_CONDITIONS.items()):
        stop_nrc22_condition(condition, settle_s=0.0)