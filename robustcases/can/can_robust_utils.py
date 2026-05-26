import time
import traceback
from common.context import ctx
from common.params import P
from common.can_utils import send_canmsg, canmsg_create
from common.utils import TimerCyclic
from uvtest.testlog import TestLog
from slplus.time import sl_time
from env.config import DEFAULT_CAN_CHANNELS


def inject_bus_off_and_wait_recovery(can_channel, timeout_s=30):
    """通过发送高优先级报文制造总线过载，触发BusOff并等待恢复"""
    msg = canmsg_create(0x001, 8, data=0x00, rtr=0, fdf=0, brs=0, ext=0)
    timer_ids = []
    tid = 1

    TestLog("INFO", "BusOff注入", "通过大量高优先级报文制造总线冲突")
    start_time = time.time()
    while (ctx.can.get_info('gBusOffCount') or 0) == 0:
        if time.time() - start_time > timeout_s:
            TestLog("WARNING", "BusOff注入", "未能在规定时间内触发BusOff")
            break
        TimerCyclic.start(tid, 2, send_canmsg, can_channel, msg=msg)
        timer_ids.append(tid)
        tid += 1
        sl_time().sleep(500)

    for t in timer_ids:
        TimerCyclic.stop(t)

    busoff_count = ctx.can.get_info('gBusOffCount') or 0
    if busoff_count > 0:
        TestLog("INFO", "BusOff注入", f"成功触发BusOff, 次数={busoff_count}")

    TestLog("INFO", "BusOff恢复", "等待ECU从BusOff状态自动恢复")
    ctx.can.clear_messages()
    sl_time().sleep(5 * 1000)

    recovery = check_can_communication_state(wait_time=3)
    if recovery == 0:
        TestLog("PASS", "BusOff恢复", "ECU已从BusOff状态恢复，通信正常")
    else:
        TestLog("FAIL", "BusOff恢复", "ECU未能从BusOff状态恢复")

    return recovery == 0


def inject_error_frames_and_check(can_channel, target_id, duration_s=30):
    """持续发送错误帧并检查DUT通信恢复能力"""
    msg = canmsg_create(target_id, 8, data=0xFF, rtr=0, fdf=0, brs=0, ext=0)
    err_count_before = ctx.can.get_info('gErrorFrameCount') or 0

    TestLog("INFO", "错误帧注入", f"以2ms周期向总线发送ID=0x{target_id:X}的冲突报文, 持续{duration_s}s")
    TimerCyclic.start(99, 2, send_canmsg, can_channel, msg=msg)
    sl_time().sleep(duration_s * 1000)
    TimerCyclic.stop(99)

    err_count_after = ctx.can.get_info('gErrorFrameCount') or 0
    new_errors = err_count_after - err_count_before

    ctx.can.clear_messages()
    sl_time().sleep(3 * 1000)

    comm_ok = check_can_communication_state(wait_time=3) == 0
    msg_count = len(ctx.can.messages)

    return new_errors, comm_ok, msg_count


def cycle_can_fault_and_check(fault_type, can_channel, cycles=3):
    """循环注入并清除CAN总线故障，检查每次恢复情况"""
    results = []
    for i in range(1, cycles + 1):
        TestLog("INFO", f"故障注入({fault_type})", f"第{i}/{cycles}轮 - 注入故障")
        ctx.can.clear_messages()

        ok = can_fault_injection(fault_type, can_channel, duration_ms=5000)
        if not ok:
            TestLog("FAIL", f"故障注入({fault_type})", f"第{i}轮故障注入失败")
            results.append(False)
            continue

        TestLog("INFO", f"故障注入({fault_type})", f"第{i}/{cycles}轮 - 清除故障并等待恢复")
        cleared, t1 = can_clear_injection(fault_type, can_channel)
        if not cleared:
            TestLog("FAIL", f"故障注入({fault_type})", f"第{i}轮故障清除失败")
            results.append(False)
            continue

        recovered, recovery_ms = check_communication_recovery_time(t1, timeout_ms=5000)
        if recovered:
            TestLog("PASS", f"故障注入({fault_type})",
                    f"第{i}轮 - 故障恢复成功, 恢复时间={recovery_ms:.1f}ms")
        else:
            TestLog("FAIL", f"故障注入({fault_type})",
                    f"第{i}轮 - 故障恢复失败, 超时5000ms")

        results.append(recovered)
        time.sleep(3)

    return results
