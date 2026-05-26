import inspect
import time
import traceback

from env.config import *
from uvtest.testlog import TestLog
from common.context import ctx
from common.utils import TimerCyclic
from common.can_utils import canmsg_create, send_canmsg
from common.control import TestStart, TestEnd
from slplus.time import sl_time
from common.context import ctx

from common.params import P

from uvtest.framework import TestFixture
from .nm_module import (
    nm_initialization, nm_deinitialization,
    gCanTextEvent_RX,
)
from slplus.event import TextEvents
from copy import deepcopy

def clear_ack_error_count():
    """
    清除ACK错误帧计数
    """
    try:
        ctx.can.set_info('gAckErrorFrameCount', 0)
    except:
        pass

def get_ack_error_count():
    """
    获取ACK错误帧计数
    """
    error_count = ctx.can.get_info('gAckErrorFrameCount') or 0
    return error_count

def get_first_msg():
    for msg in ctx.can.messages:
        if msg.id in [0x100, 0x101]:  # 0x100和0x101是板卡内部的通信报文id
            continue
        return msg
    return None

def check_period_msg():
    """
    检查周期报文
    """
    from collections import defaultdict
    msg_dict = defaultdict(list)
    for msg in ctx.can.messages:
        msg_dict[msg.id].append(msg.time_ms)
    
    for msg_id, time_list in msg_dict.items():
        time_list.sort()
        intervals = [t2 - t1 for t1, t2 in zip(time_list[:-1], time_list[1:])]
        if len(intervals) < 2:
            continue
        avg_interval = sum(intervals) / len(intervals)
        deviations = [abs(interval - avg_interval) for interval in intervals]
        max_deviation = max(deviations)
        if max_deviation > 0.1 * avg_interval:
            TestLog("FAIL", "周期报文检查", f"报文ID 0x{msg_id:X} 存在较大周期偏差，平均周期 {avg_interval:.2f} ms，最大偏差 {max_deviation:.2f} ms")
            return False
        else:
            TestLog("PASS", "周期报文检查", f"报文ID 0x{msg_id:X} 周期稳定，平均周期 {avg_interval:.2f} ms，最大偏差 {max_deviation:.2f} ms")
            return True
    TestLog("FAIL", "周期报文检查", f"未检测到周期报文")
    return False

def get_each_period_msg_first_msg_time():
    """
    获取每个周期报文的第一帧报文的时间
    """
    from collections import defaultdict
    msg_dict = defaultdict(list)
    for msg in ctx.can.messages:
        msg_dict[msg.id].append(msg.time_ms)
    
    each_msg_first_time = {}
    for msg_id, time_list in msg_dict.items():
        time_list.sort()
        intervals = [t2 - t1 for t1, t2 in zip(time_list[:-1], time_list[1:])]
        if len(intervals) < 2:
            continue
        avg_interval = sum(intervals) / len(intervals)
        deviations = [abs(interval - avg_interval) for interval in intervals]
        max_deviation = max(deviations)
        if max_deviation <= 0.1 * avg_interval:
            if msg_id not in each_msg_first_time:
                each_msg_first_time[msg_id] = time_list[0]
    return each_msg_first_time

def get_last_msg_timestamp(msg_list=None):
    msg = ctx.can.messages[-1] if msg_list is None else msg_list[-1]
    return msg.time_ms


class NMIndirectTestFixture(TestFixture):
    def group_setup(self, context=None):
        nm_initialization()

    def group_teardown(self, context=None):
        nm_deinitialization()

    def case_setup(self, context=None):
        if context:
            TestStart(context["test_name"])

    def case_teardown(self, context=None):
        TestEnd("")
        TestLog("INFO", "测试结束", "执行测试结束和去初始化")

def test_TG0_TC1_NM_WakeUpBehaviorTest():
    """
    WakeUpBehaviorTest
    """
    try:
        if P.NMInfo.WakeUpHardWireType == 0:
            TestLog("WARNING", "", "该ECU不支持除KL30外的其他硬线唤醒，条件不满足，测试退出")
            return

        TestLog("INFO", "Step1", f"设置DUT供电电压为{P.NMInfo.Vnormal}v，KL30 和 唤醒硬线 OFF，DUT处于非工作状态")
        ctx.power_ctrl.on()
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)  # 设置电压
        ctx.bob_ctrl.set_power('KL30', False)         # KL30 OFF
        ctx.bob_ctrl.set_power('KL15', False)         # KL15 OFF（唤醒硬线OFF）

        sl_time().sleep(1000) # 等待电源稳定

        ctx.can.clear_messages()

        sl_time().sleep(3000) # 等待通信稳定

        if len(ctx.can.messages) > 0:
            TestLog("FAIL", "", "期望: 总线无报文, 实际: 检测到报文")
            return
        TestLog("PASS", "", "期望: 总线无报文, 实际: 未检测到报文")

        TestLog("INFO", "Step2", "仿真发送报文0x333,周期10ms")
        app_msg = canmsg_create(0x333, 8, data=[0x00] * 8)
        timer_id = "SimAppTimer"
        ch = DEFAULT_CAN_CHANNELS[0]
        TimerCyclic.start(timer_id, 10, send_canmsg, ch, msg=app_msg)

        TestLog("INFO", "Step3", "KL30 ON")
        ctx.bob_ctrl.set_power('KL30', True)

        sl_time().sleep(3000) # 等待通信稳定

        clear_ack_error_count()  # 清除ACK错误计数器

        TestLog("INFO", "", "等待3s，监控ECU是否给出ACK应答")
        sl_time().sleep(3000) # 等待通信稳定

        # 获取错误帧，ECU无法给出ACK应答
        if get_ack_error_count() == 0:
            TestLog("FAIL", "", "期望: ECU无法给出ACK应答(出现ACK应答错误帧), 实际: 未检测到ACK错误帧")
            return
        TestLog("PASS", "", "期望: ECU无法给出ACK应答(出现ACK应答错误帧), 实际: 检测到ACK错误帧")

        TestLog("INFO", "Step4", "接通唤醒硬线(KL15 ON)")
        ctx.bob_ctrl.set_power('KL15', True)
        
        sl_time().sleep(3000) # 等待通信稳定

        clear_ack_error_count()  # 清除ACK错误计数器
        ctx.can.clear_messages()  # 清除报文计数器

        TestLog("INFO", "", "等待3s，监控ECU是否给出ACK应答，是否发出应用报文")  # 检测收到的第一帧报文
        sl_time().sleep(3000) # 等待通信稳定

        # ECU给出ACK应答（无ACK错误帧），且发出应用报文
        c1 = get_ack_error_count() == 0
        c2 = len(ctx.can.messages) > 0

        result_log = ("" if c1 is True else "未") + "检测到ACK应答,且" + ("" if c2 is True else "未") + "检测到应用报文"
        if not (c1 and c2):
            TestLog("FAIL", "", f"期望: ECU给出ACK应答并发出应用报文, 实际: {result_log}")
            return
        TestLog("PASS", "", f"期望: ECU给出ACK应答并发出应用报文, 实际: {result_log}")

    except Exception as e:
        TestLog("FAIL", "WakeUpBehaviorTest", f"异常: {e}")
        TestLog("DEBUG", "", traceback.format_exc())
    finally:
        # 清理
        try:
            if 'timer_id' in locals() and timer_id:
                TimerCyclic.stop(timer_id)
        except Exception:
            pass
        try:
            ctx.bob_ctrl.set_power('KL30', False)
            ctx.bob_ctrl.set_power('KL15', False)
        except Exception:
            pass


def test_TG1_TC1_NM_tCANAck():
    """
    WakeUpBehaviorTest
    """
    try:

        # if P.NMInfo.WakeUpHardWireType == 0:
        #     TestLog("WARNING", "", "该ECU不支持除KL30外的其他硬线唤醒，条件不满足，测试退出")
        #     return
        T_CANAck_ms = 150  # ms

        TestLog("INFO", "Step1", f"设置DUT供电电压为{P.NMInfo.Vnormal}v，KL30 和 唤醒硬线 OFF，DUT处于非工作状态")
        ctx.power_ctrl.on()
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)  # 设置电压
        ctx.bob_ctrl.set_power('KL30', False)         # KL30 OFF
        ctx.bob_ctrl.set_power('KL15', False)         # KL15 OFF（唤醒硬线OFF）

        sl_time().sleep(1000) # 等待电源稳定

        # 期望: 总线无报文
        ctx.can.clear_messages()
        sl_time().sleep(2000)
        if len(ctx.can.messages) > 0:
            TestLog("FAIL", "", "期望: 总线无报文, 实际: 检测到报文")
            return
        TestLog("PASS", "", "期望: 总线无报文, 实际: 未检测到报文")

        # 期望: 静态电流<Isleep
        isleep_ma = P.ECUInfo.ISleep
        if isleep_ma > 0:
            sum_current_a = []
            for _ in range(10):
                try:
                    status, cur_a = ctx.power_ctrl.get_current()
                    if status is True and cur_a is not None:
                        sum_current_a.append(float(cur_a))
                except Exception:
                    pass
                sl_time().sleep(1)
            if not sum_current_a:
                TestLog("FAIL", "", "电源电流读取失败")
                return
            avg_ma = sum(sum_current_a) / len(sum_current_a) * 1000.0
            if avg_ma <= isleep_ma:
                TestLog("PASS", "", f"期望: 静态电流<Isleep({isleep_ma:.1f}mA), 实际: 平均电流={avg_ma:.2f}mA")
            else:
                TestLog("FAIL", "", f"期望: 静态电流<Isleep({isleep_ma:.1f}mA), 实际: 平均电流={avg_ma:.2f}mA")
                return
        else:
            TestLog("INFO", "", "Isleep未配置(=0)，跳过静态电流检查")

        TestLog("INFO", "Step2", "仿真发送报文0x333,周期10ms")
        simu_id = 0x333
        app_msg = canmsg_create(simu_id, 8, data=[0x00] * 8)
        timer_id = "SimAppTimer"
        ch = DEFAULT_CAN_CHANNELS[0]
        TimerCyclic.start(timer_id, 10, send_canmsg, ch, msg=app_msg)

        if P.NMInfo.WakeUpHardWireType == 0:
            TestLog("INFO", "Step3", "KL30 ON，记录此时间T1，记录DUT给出ACK应答时间T2")
            ctx.can.clear_messages()
            ctx.bob_ctrl.set_power('KL30', True)
            t1 = sl_time().timestamp() * 1000.0
        else:
            TestLog("INFO", "Step4", "KL30 ON")
            ctx.bob_ctrl.set_power('KL30', True)
            sl_time().sleep(1000)  # 等待DUT电源稳定
            TestLog("INFO", "Step5", "接通唤醒硬线,记录此时时间T1,记录DUT给出ACK应答时间T2")
            ctx.can.clear_messages()
            ctx.bob_ctrl.set_power('KL15', True)
            t1 = sl_time().timestamp() * 1000.0

        sl_time().sleep(1000)  # 等待1s

        # 检查总线上第一帧仿真报文的时间
        t2 = None
        for msg in ctx.can.messages:
            if msg.id == simu_id and msg.time_ms >= t1:
                t2 = msg.time_ms
                break
        if t2 is None:
            TestLog("FAIL", "", "未检测到DUT给出的ACK应答报文")
            return

        TestLog("INFO", "", f"{t1=}")
        TestLog("INFO", "", f"{t2=}")

        diff = t2 - t1
        if diff <= T_CANAck_ms:
            TestLog("PASS", "", f"期望: ACK应答时间<={T_CANAck_ms}ms, 实际: ACK应答时间={diff}ms")
        else:
            TestLog("FAIL", "", f"期望: ACK应答时间<={T_CANAck_ms}ms, 实际: ACK应答时间={diff}ms")
            return

    except Exception as e:
        TestLog("FAIL", "WakeUpBehaviorTest", f"异常: {e}")
        TestLog("DEBUG", "", traceback.format_exc())
    finally:
        # 清理
        try:
            TimerCyclic.stop(timer_id)
        except Exception:
            pass
        try:
            ctx.bob_ctrl.set_power('KL30', False)
            ctx.bob_ctrl.set_power('KL15', False)
        except Exception:
            pass


def test_TG1_TC2_NM_tCANinit():
    """
    tCANinit 
    """
    try:
        T_CANInit_ms = 200

        TestLog("INFO", "Step1", f"设置DUT供电电压为{P.NMInfo.Vnormal}v，KL30 和 唤醒硬线 OFF，DUT处于非工作状态")
        ctx.power_ctrl.on()
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)  # 设置电压
        ctx.bob_ctrl.set_power('KL30', False)         # KL30 OFF
        ctx.bob_ctrl.set_power('KL15', False)         # KL15 OFF（唤醒硬线OFF）

        sl_time().sleep(1000) # 等待电源稳定
        ctx.can.clear_messages()

        TestLog("INFO", "Step2", "KL30 ON，记录此时间T1，记录DUT给出ACK应答时间T2")
        if P.NMInfo.WakeUpHardWireType == 0:
            ctx.bob_ctrl.set_power('KL30', True)
        else:
            TestLog("INFO","Step3", "接通唤醒硬线,记录此时时间T1,记录DUT给出ACK应答时间T2")
            ctx.bob_ctrl.set_power('KL30', True)
            ctx.bob_ctrl.set_power('KL15', True)
        t1 = sl_time().timestamp() * 1000.0

        sl_time().sleep(1000)  # 等待100ms
        if len(ctx.can.messages) == 0:
            TestLog("FAIL", "", "总线上未检测到报文")
            return

        # 检查总线上第一帧报文的时间
        msg = ctx.can.messages[0]
        t2 = msg.time_ms

        TestLog("INFO", "", f"{t1=}")
        TestLog("INFO", "", f"{t2=}")

        diff = t2 - t1
        if diff <= T_CANInit_ms:
            TestLog("PASS", "", f"期望: 唤醒时间<={T_CANInit_ms}ms, 实际: 唤醒时间={diff}ms")
        else:
            TestLog("FAIL", "", f"期望: 唤醒时间<={T_CANInit_ms}ms, 实际: 唤醒时间={diff}ms")
            return

    except Exception as e:
        TestLog("FAIL", "tCANinit", f"异常: {e}")
        TestLog("DEBUG", "", traceback.format_exc())
    finally:
        try:
            ctx.bob_ctrl.set_power('KL30', False)
            ctx.bob_ctrl.set_power('KL15', False)
        except Exception:
            pass


def test_TG1_TC3_NM_tMsgStart():
    """tMsgStart """
    try:
        TinitialCycle_ms = P.NMInfo.TinitialCycle_ms  # DUT唤醒后发送完一轮报文的时间
        TrepeatMessage_ms = P.NMInfo.TrepeatMessage_ms  # 重复发送报文状态的保持时间

        TestLog("INFO", "Step1", f"设置DUT供电电压为{P.NMInfo.Vnormal}v，KL30 和 唤醒硬线 OFF，DUT处于非工作状态")
        ctx.power_ctrl.on()
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)  # 设置电压
        ctx.bob_ctrl.set_power('KL30', False)         # KL30 OFF
        ctx.bob_ctrl.set_power('KL15', False)         # KL15 OFF（唤醒硬线OFF）
        sl_time().sleep(1000) # 等待电源稳定

        ctx.can.clear_messages()

        TestLog("INFO","Step2", "触发主动唤醒源并保持，从收到DUT发出第1帧报文开始等待TrepeatMessage时间，记录在此期间收到的所有报文")
        if P.NMInfo.WakeUpHardWireType == 0:
            ctx.bob_ctrl.set_power('KL30', True)
        else:
            ctx.bob_ctrl.set_power('KL30', True)
            ctx.bob_ctrl.set_power('KL15', True)

        sl_time().sleep(TrepeatMessage_ms)  # 等待100ms

        if len(ctx.can.messages) == 0:
            TestLog("FAIL", "", f"{TrepeatMessage_ms}ms内未检测到报文")
            return

        first_rx_msg_timestamp = ctx.can.messages[0].time_ms

        # 将收到的每个ID的所有报文的时间戳，各自整合到列表中{0x123: [t1, t2, ...], 0x456: [t1, t2, ...]}  -s
        recved_msg_dict = {}
        for msg in ctx.can.messages:
            k = msg.id
            if k not in recved_msg_dict:
                recved_msg_dict[k] = []
            recved_msg_dict[k].append(msg.time_ms)
        # 将收到的每个ID的所有报文的时间戳，各自整合到列表中{0x123: [t1, t2, ...], 0x456: [t1, t2, ...]}  -e

        # {0x123: {'dlc': 13, 'cycle': 20, 'name': 'EMS_State_1'}}
        sMsg = ctx.can.get_info('sMsgInfoList') or {}
        no_recved_id = []
        for dbc_msg_id, msg_info_dict in sMsg.items():
            if msg_info_dict.get("cycle", 0) == 0:  # 去掉dbc中非周期报文
                continue
            if dbc_msg_id not in recved_msg_dict:
                no_recved_id.append(dbc_msg_id)  # 收集ECU未发出来的DBC中的ID
                TestLog("FAIL", "", f"期望结果：报文({hex(dbc_msg_id)})在唤醒后的{TinitialCycle_ms}ms 时间之内发出，"
                                    f"实际结果：未检测到该报文")
            else:
                first_msg_timestamp = min(recved_msg_dict[dbc_msg_id])
                diff = first_msg_timestamp - first_rx_msg_timestamp
                if diff <= TinitialCycle_ms:
                    TestLog("PASS", "", f"期望结果：报文({hex(dbc_msg_id)})在唤醒后的{TinitialCycle_ms}ms 时间之内发出，"
                                        f"实际结果：发送时间：{diff} ms <= {TinitialCycle_ms} ms，满足要求")
                else:
                    TestLog("FAIL", "", f"期望结果：报文({hex(dbc_msg_id)})在唤醒后的{TinitialCycle_ms}ms 时间之内发出，"
                                        f"实际结果：发送时间：{diff} ms > {TinitialCycle_ms} ms，满足要求")

        if len(no_recved_id) == 0:
            TestLog("PASS", "", f"期望结果：在唤醒后的{TinitialCycle_ms}ms 时间之内，DUT所有报文均发送一轮，"
                                f"实际结果：从接收到第1帧报文开始，在{TinitialCycle_ms}ms 时间之内，DUT所有报文均发送一轮，满足要求")
        else:
            str_id_list = str([hex(i) for i in no_recved_id])
            TestLog("FAIL", "", f"期望结果：在唤醒后的{TinitialCycle_ms}ms 时间之内，DUT所有报文均发送一轮，"
                                f"实际结果：报文：{str_id_list}未在规定时间内发出")

    except Exception as e:
        TestLog("FAIL", "tMsgStart", f"异常: {e}")
        TestLog("DEBUG", "", traceback.format_exc())
    finally:
        try:
            ctx.bob_ctrl.set_power('KL30', False)
            ctx.bob_ctrl.set_power('KL15', False)
        except Exception:
            pass


def test_TG2_TC1_NM_tShutDown():
    """
    tShutDown
    """
    try:
        T_ShutDown_ms = 200

        TestLog("INFO", "Step1", f"设置DUT供电电压为{P.NMInfo.Vnormal}v，KL30 和 唤醒硬线 OFF，DUT处于非工作状态")
        ctx.power_ctrl.on()
        ctx.power_ctrl.set_voltage(P.NMInfo.Vnormal)  # 设置电压
        ctx.bob_ctrl.set_power('KL30', False)         # KL30 OFF
        ctx.bob_ctrl.set_power('KL15', False)         # KL15 OFF（唤醒硬线OFF）
        sl_time().sleep(1000) # 等待电源稳定

        if P.NMInfo.WakeUpHardWireType == 0:
            TestLog("INFO","Step2", "KL30 On, DUT正常发送周期报文")
            ctx.bob_ctrl.set_power('KL30', True)
        else:
            TestLog("INFO","Step2", "KL30 On")
            TestLog("INFO","Step3", "接通唤醒硬线, DUT正常发送周期报文")
            ctx.bob_ctrl.set_power('KL30', True)
            ctx.bob_ctrl.set_power('KL15', True)

        ctx.can.clear_messages()

        sl_time().sleep(3000) # 等待通信稳定

        if len(ctx.can.messages) > 0:
            TestLog("PASS", "", "期望: DUT被唤醒, 实际: 检测到报文")
        else:
            TestLog("FAIL", "", "期望: DUT被唤醒, 实际: 未检测到报文")
            return

        if P.NMInfo.WakeUpHardWireType == 0:
            TestLog("INFO","Step3", "KL30 OFF,记录此时时间为T1,记录DUT发出最后一帧报文时间为T2")
            ctx.bob_ctrl.set_power('KL30', False)
        else:
            TestLog("INFO","Step4", "唤醒硬线 OFF,记录此时时间为T1,记录DUT发出最后一帧报文时间为T2")
            ctx.bob_ctrl.set_power('KL15', False)
        t1 = sl_time().timestamp()

        sl_time().sleep(2000) # 等待通信稳定

        t2 = get_last_msg_timestamp() / 1000.0  # 记录最后一帧报文的时间

        TestLog("INFO", "", f"{t1=}")
        TestLog("INFO", "", f"{t2=}")
        diff = t2 - t1
        if diff <= T_ShutDown_ms:
            TestLog("PASS", "", f"期望: ShutDown ≤ {T_ShutDown_ms}ms, 实际: tShutDown={diff}ms")
        else:
            TestLog("FAIL", "", f"期望: ShutDown ≤ {T_ShutDown_ms}ms, 实际: tShutDown={diff}ms")
            return

    except Exception as e:
        TestLog("FAIL", "tShutDown", f"异常: {e}")
        TestLog("DEBUG", "", traceback.format_exc())


def get_all_test_cases():
    current_module = inspect.getmodule(inspect.currentframe())

    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj

    return test_cases

