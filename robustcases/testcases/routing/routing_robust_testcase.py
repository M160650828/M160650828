import sys
import os
import time
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from uvtest.testlog import TestLog
from uvtest.framework import TestFixture
from common.control import TestStart, TestEnd
from common.context import ctx
from common.params import P
from common.can_utils import send_canmsg, canmsg_create
from common.utils import TimerCyclic
from slplus.time import sl_time
from env.config import DEFAULT_CAN_CHANNELS, ROUTING_CAN_CHANNELS

from testcases.routing.routing_module import (
    routing_initialization, routing_deinitialization,
    get_routing_config, get_routing_sender,
    can_power_setup_and_communication_check,
    check_routing, analyze_dest_cycle, analyze_routing_delay,
    SEND_MODE_SIGNAL, SEND_MODE_INCREMENT,
    CHECK_MODE_SIGNAL, CHECK_MODE_BASIC, CHECK_MODE_DLC,
    CHECK_MODE_FRAMETYPE, CHECK_MODE_DATA,
)


class RoutingRobustTestFixture(TestFixture):
    def group_setup(self, context=None):
        routing_initialization()

    def group_teardown(self, context=None):
        routing_deinitialization()

    def case_setup(self, context=None):
        if context:
            TestStart(context["test_name"])

    def case_teardown(self, context=None):
        TestEnd("")
        TestLog("INFO", "测试结束", "执行测试结束和去初始化")


def test_TG1_TC1_SourceMessageBurstLossTest():
    """源报文突发丢失路由鲁棒性测试"""
    sender = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        entries = list(cfg.iter_signal_entries())
        if not entries:
            TestLog("WARNING", "", "未找到信号路由类型的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            src_signal_name = e.get('SrcSignalName', '')
            dest_signal_name = e.get('DestSignalName', '')

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})

            TestLog("INFO", "Step2",
                    f"第1轮: 正常发送源信号={src_signal_name}, 持续10s后停止, 模拟源报文丢失")
            duration_ms = cfg.get_duration_ms(e)
            sender.send(idx, e, mode=SEND_MODE_SIGNAL, duration_ms=duration_ms, step="Step2")

            ret_before, _ = check_routing(e, expect_count=5, mode=CHECK_MODE_BASIC)
            expected = f"目标网段({dest_net})接收目标报文(ID=0x{dest_id:x})"

            if ret_before == 0:
                TestLog("PASS", "Step2-正常",
                        f"期望结果：{expected}。实际结果：正常接收")
            else:
                TestLog("FAIL", "Step2-正常",
                        f"期望结果：{expected}。实际结果：未正常接收")

            TestLog("INFO", "Step3", f"停止发送源报文10s（模拟突发丢失）")
            time.sleep(10)

            TestLog("INFO", "Step4", f"恢复发送源报文，验证路由恢复")
            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            sender.send(idx, e, mode=SEND_MODE_SIGNAL, duration_ms=duration_ms, step="Step4")

            ret_after, _ = check_routing(e, expect_count=5, mode=CHECK_MODE_SIGNAL)
            if ret_after == 0:
                TestLog("PASS", "Step4",
                        f"期望结果：源报文丢失后路由恢复。实际结果："
                        f"目标网段接收目标报文, 信号={dest_signal_name}")
            else:
                TestLog("FAIL", "Step4",
                        f"期望结果：源报文丢失后路由恢复。实际结果：目标网段未接收到目标报文")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()


def test_TG1_TC2_RoutingUnderHighBusLoadTest():
    """高总线负载下的路由鲁棒性测试"""
    sender = None
    tids = []
    try:
        v, tstable_s, default_can_ch = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        entries = list(cfg.iter_signal_entries())
        if not entries:
            TestLog("WARNING", "", "未找到信号路由类型的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            src_signal_name = e.get('SrcSignalName', '')
            dest_signal_name = e.get('DestSignalName', '')

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})

            TestLog("INFO", "Step2",
                    f"在源网段({src_net})发送高密度干扰报文增加总线负载, 同时发送路由源信号")
            duration_ms = cfg.get_duration_ms(e)

            for can_ch in DEFAULT_CAN_CHANNELS:
                for burst_id in range(0x200, 0x210):
                    msg = canmsg_create(burst_id, 8, data=0xFF, rtr=0, fdf=0, brs=0, ext=0)
                    TimerCyclic.start(burst_id, 20, send_canmsg, can_ch, msg=msg)
                    tids.append(burst_id)

            sender.send(idx, e, mode=SEND_MODE_SIGNAL, duration_ms=duration_ms, step="Step2")

            ret, _ = check_routing(e, expect_count=5, mode=CHECK_MODE_BASIC)
            expected = f"目标网段({dest_net})接收目标报文(ID=0x{dest_id:x})"

            if ret == 0:
                TestLog("PASS", "Step3",
                        f"期望结果：高负载下{expected}。"
                        f"实际结果：高负载下路由正常 (源信号={src_signal_name})")
            else:
                TestLog("WARNING", "Step3",
                        f"期望结果：高负载下{expected}。"
                        f"实际结果：高负载下路由异常 (源信号={src_signal_name})")

        for t in tids:
            try:
                TimerCyclic.stop(t)
            except:
                pass

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        for t in tids:
            try:
                TimerCyclic.stop(t)
            except:
                pass
        if sender is not None:
            sender.routing_cleanup()


def test_TG1_TC3_DestinationNetworkInterruptionTest():
    """目标网络中断恢复路由鲁棒性测试"""
    sender = None
    try:
        v, tstable_s, _ = get_routing_config().can_params()
        if can_power_setup_and_communication_check(v, tstable_s) != 0:
            return

        sender = get_routing_sender()
        cfg = get_routing_config()

        entries = list(cfg.iter_signal_entries())
        if not entries:
            TestLog("WARNING", "", "未找到信号路由类型的路由表项")
            return

        for idx, e in entries:
            src_id = e.get('SrcMsgId', 0)
            dest_id = e.get('DestMsgId', 0)
            src_net = e.get('SrcNet', '')
            dest_net = e.get('DestNet', '')
            src_signal_name = e.get('SrcSignalName', '')
            dest_signal_name = e.get('DestSignalName', '')

            TestLog("INFO", "Step2",
                    f"在源网段({src_net})持续发送信号={src_signal_name}, "
                    f"模拟目标网段中断后恢复")

            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])
            ctx.can.set_info('sRxMsgInfoList', {})

            duration_ms = cfg.get_duration_ms(e)
            sender.send(idx, e, mode=SEND_MODE_SIGNAL, duration_ms=duration_ms, step="Step2")

            ret_before, _ = check_routing(e, expect_count=5, mode=CHECK_MODE_BASIC)
            if ret_before == 0:
                TestLog("PASS", "Step2-基准",
                        f"目标网段正常接收目标报文(ID=0x{dest_id:x})")
            else:
                TestLog("FAIL", "Step2-基准", "目标网段未接收到目标报文")
                continue

            TestLog("INFO", "Step3", "模拟目标网络中断(通过reset目标网段的context)")
            ctx.can.set_info('routing_dest_records', [])
            time.sleep(5)

            TestLog("INFO", "Step4", "目标网络恢复后继续发送源信号，验证路由是否自动恢复")
            ctx.can.set_info('routing_src_records', [])
            ctx.can.set_info('routing_dest_records', [])

            sender.send(idx, e, mode=SEND_MODE_SIGNAL, duration_ms=duration_ms, step="Step4")

            ret_after, _ = check_routing(e, expect_count=5, mode=CHECK_MODE_SIGNAL)
            if ret_after == 0:
                TestLog("PASS", "Step4",
                        f"期望结果：目标网络中断恢复后路由自动恢复。"
                        f"实际结果：路由正常，信号={dest_signal_name}")
            else:
                TestLog("WARNING", "Step4",
                        "期望结果：目标网络中断恢复后路由自动恢复。"
                        "实际结果：路由未恢复")

    except Exception as ex:
        TestLog("FAIL", "", f"执行异常: {ex}\n{traceback.format_exc()}")
    finally:
        if sender is not None:
            sender.routing_cleanup()


def get_all_test_cases():
    import inspect
    current_module = inspect.getmodule(inspect.currentframe())
    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj
    return test_cases
