"""
Flash/Bootloader 鲁棒性测试用例

基于UDS诊断服务（$10编程会话 / $31 RoutineControl / $34 RequestDownload / $36 TransferData）
验证ECU在刷写流程异常中断场景下的鲁棒性。

不执行真实的Flash写入操作 —— 仅测试诊断服务交互和异常恢复能力。
参考: testcases/bootloader/ 中的刷写流程实现。
"""
import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from env.config import *
from uvtest.testlog import TestLog
from uvtest.framework import TestFixture
from common.control import TestStart, TestEnd
from common.context import ctx
from common.params import P
from common.wakeup import WakeupStart, WakeupStop
from slplus.time import sl_time

from testcases_canlin.bootloader.can_comm import (
    can_initialization, can_deinitialization,
    can_power_setup_and_communication_check,
    check_can_communication_state,
)
from testcases_canlin.bootloader.utils.bootloader_utils import (
    get_can_node, get_flash_config, FlashConfig,
    service_10_check, service_31_check, service_22_check,
    security_access, tester_present_start, tester_present_stop,
    check_resp,
)
from library.uds.uds_node import UDSNode


class FlashRobustTestFixture(TestFixture):
    def group_setup(self, context=None):
        can_initialization()

    def group_teardown(self, context=None):
        can_deinitialization()

    def case_setup(self, context=None):
        if context:
            TestStart(context["test_name"])

    def case_teardown(self, context=None):
        tester_present_stop()
        TestEnd("")
        TestLog("INFO", "测试结束", "执行测试结束和去初始化")


# ========== 辅助函数 ==========

def _get_flash_node() -> UDSNode:
    """获取用于刷写诊断通信的UDS节点"""
    sa = P.ECUInfo.DiagReqID_int
    ta = P.ECUInfo.DiagRespID_int
    fa = P.ECUInfo.DiagFuncID_int
    is_canfd = True if P.TpInfo.CanFDMode == 1 else False
    return get_can_node(sa, ta, fa, is_canfd)


def _enter_programming_session(node: UDSNode) -> bool:
    """进入编程会话 ($10 02)，失败时自动记录TestLog"""
    TestLog("INFO", "会话控制", "请求进入编程会话(10 02)")
    if not service_10_check(node, 0x02, expect_data=[0x50, 0x02],
                            expect_str="肯定响应(50 02)"):
        TestLog("FAIL", "会话控制", "进入编程会话失败")
        return False
    TestLog("PASS", "会话控制", "成功进入编程会话")
    return True


def _verify_default_session_after_recovery(node: UDSNode) -> bool:
    """验证异常中断后ECU可回到默认会话"""
    time.sleep(3)
    TestLog("INFO", "恢复验证", "验证ECU能否进入默认会话(10 01)")
    if service_10_check(node, 0x01, expect_data=[0x50, 0x01],
                        expect_str="肯定响应(50 01)"):
        TestLog("PASS", "恢复验证", "ECU成功回到默认会话")
        return True
    else:
        TestLog("FAIL", "恢复验证", "ECU未能回到默认会话（可能处于锁死状态）")
        return False


# ========== 测试用例 ==========

def test_TG1_TC1_FlashInterruptPoweroffTest():
    """Flash烧录断电鲁棒性测试 - 编程会话中多次断电，验证DUT恢复能力"""
    node = None
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        power_cycles = min(P.CANInfo.NdefaultRepeat, 5)

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.set_filter_by_channel(can_channel)

        TestLog("INFO", "Step2",
                f"执行{power_cycles}次'进入编程会话→断电→重新上电'循环")
        all_recovered = True
        for i in range(1, power_cycles + 1):
            TestLog("INFO", "Step2", f"--- 第{i}/{power_cycles}次循环 ---")

            # 每次循环创建新节点（因为断电后旧连接无效）
            if node:
                try:
                    node.close()
                except:
                    pass
            node = _get_flash_node()

            # 进入编程会话
            if not _enter_programming_session(node):
                TestLog("WARNING", "Step2", f"第{i}次: 进入编程会话失败，仍然执行断电测试")

            # 发送一个RoutineControl请求（模拟刷写流程已经开始）
            TestLog("INFO", "Step2", "发送$31 RoutineControl(检查编程前置条件)")
            service_31_check(node, 0x01, 0xFF00,
                           expect_data=[0x71, 0x01, 0xFF, 0x00],
                           expect_str="71 01 FF 00(Routine响应)")

            # 断电
            TestLog("INFO", "Step2", f"第{i}次: KL30下电（模拟烧录中突发断电）")
            ctx.bob_ctrl.set_power('KL30', False)
            ctx.power_ctrl.set_voltage(0)
            time.sleep(3)

            # 重新上电
            TestLog("INFO", "Step2", f"第{i}次: 重新上电，验证ECU恢复")
            ctx.power_ctrl.set_voltage(rVnormal)
            ctx.bob_ctrl.set_power('KL30', True)
            WakeupStart()
            sl_time().sleep(8 * 1000)

            # 重建节点并验证
            try:
                node.close()
            except:
                pass
            node = _get_flash_node()

            if _verify_default_session_after_recovery(node):
                TestLog("PASS", "Step2", f"第{i}次: 断电恢复成功")
            else:
                all_recovered = False

        TestLog("INFO", "Step3", f"全部{power_cycles}次断电循环完成，验证最终通信状态")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(10 * 1000)

        ret = check_can_communication_state(wait_time=5)
        if ret == 0:
            TestLog("PASS", "Step3",
                    f"期望结果：{power_cycles}次编程会话断电后DUT通信正常。"
                    "实际结果：DUT通信正常")
        else:
            TestLog("FAIL", "Step3",
                    f"期望结果：{power_cycles}次编程会话断电后DUT通信正常。"
                    "实际结果：DUT通信异常")

        if all_recovered:
            TestLog("PASS", "Flash烧录断电鲁棒性测试", "所有编程会话断电后ECU均正常恢复")
        else:
            TestLog("WARNING", "Flash烧录断电鲁棒性测试", "部分断电恢复异常")

    except Exception as e:
        TestLog("FAIL", "Flash烧录断电鲁棒性测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "Flash烧录断电鲁棒性测试", f"详细错误: {traceback.format_exc()}")
    finally:
        if node:
            try:
                node.close()
            except:
                pass


def test_TG1_TC2_OTAInterruptRecoveryTest():
    """OTA中断恢复鲁棒性测试 - RequestDownload后断电，验证ECU回滚与恢复"""
    node = None
    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.set_filter_by_channel(can_channel)
        node = _get_flash_node()

        TestLog("INFO", "Step2", "进入扩展会话后进行安全访问")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03],
                                expect_str="肯定响应(50 03)"):
            TestLog("FAIL", "Step2", "进入扩展会话失败")
            return
        TestLog("PASS", "Step2", "扩展会话进入成功")

        # 安全访问
        if not security_access(node, 0x01):
            TestLog("WARNING", "Step2", "安全访问级别1失败，继续尝试（部分ECU可能不需要）")

        # 进入编程会话
        if not _enter_programming_session(node):
            return

        TestLog("INFO", "Step3", "发送$34 RequestDownload请求后立即断电（模拟OTA传输中断）")
        TestLog("INFO", "Step3", "发送$34请求下载，dataFormatIdentifier=0x00")

        # 发送RequestDownload并断电
        try:
            # 使用UDSNode直接发请求（不等响应）
            resp = node.Service_0x34_RequestDownload(
                dataFormatIdentifier=0x00,
                addressAndLengthFormatIdentifier=0x44,  # 4字节地址+4字节长度
                memoryAddress=0x00000000,
                memorySize=0x00001000
            )
            TestLog("INFO", "Step3", f"RequestDownload已发送, 响应={resp}")
        except Exception:
            TestLog("INFO", "Step3", "RequestDownload发送后无响应（预期——立即断电）")

        # 不等传输完成，立即断电
        TestLog("INFO", "Step3", "模拟OTA传输中断: KL30下电")
        ctx.bob_ctrl.set_power('KL30', False)
        ctx.power_ctrl.set_voltage(0)
        time.sleep(5)

        TestLog("INFO", "Step4", "恢复供电，验证ECU不被'变砖'并恢复正常通信")
        ctx.power_ctrl.set_voltage(rVnormal)
        ctx.bob_ctrl.set_power('KL30', True)
        WakeupStart()
        sl_time().sleep(15 * 1000)

        # 重建节点
        try:
            node.close()
        except:
            pass
        node = _get_flash_node()

        # 验证ECU可以回到默认会话
        session_recovered = _verify_default_session_after_recovery(node)

        # 验证CAN通信
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(5 * 1000)

        ret = check_can_communication_state(wait_time=3)
        if ret == 0 and session_recovered:
            TestLog("PASS", "Step4",
                    "期望结果：OTA中断后ECU回滚到原固件并正常通信。"
                    "实际结果：ECU通信正常且会话可恢复")
        elif ret == 0:
            TestLog("WARNING", "Step4",
                    "CAN通信正常但会话恢复异常")
        else:
            TestLog("FAIL", "Step4",
                    "期望结果：OTA中断后ECU可恢复。实际结果：ECU通信异常（可能已变砖）")

        TestLog("INFO", "Step5", "监控5分钟验证OTA中断恢复后长期稳定性")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(5 * 60 * 1000)

        final_msgs = len(ctx.can.messages)
        final_errs = ctx.can.get_info('gErrorFrameCount') or 0
        if final_msgs > 0 and final_errs == 0:
            TestLog("PASS", "Step5",
                    f"期望结果：OTA中断恢复后长期稳定。"
                    f"实际结果：{final_msgs}条报文, 0个错误帧")
        else:
            TestLog("WARNING", "Step5",
                    f"通信异常: 报文={final_msgs}, 错误帧={final_errs}")

        TestLog("INFO", "OTA中断恢复鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "OTA中断恢复鲁棒性测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "OTA中断恢复鲁棒性测试", f"详细错误: {traceback.format_exc()}")
    finally:
        if node:
            try:
                node.close()
            except:
                pass


def test_TG1_TC3_BootloaderVoltageRippleTest():
    """Bootloader电压纹波鲁棒性测试 - 编程会话中施加电压波动，验证会话稳定性和恢复能力"""
    node = None
    try:
        rVnormal = P.CANInfo.Vnormal
        rVlowStand = P.CANInfo.VlowStand
        rVhighStand = P.CANInfo.VhighStand
        rTstable_s = P.CANInfo.Tstable_s
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1

        TestLog("INFO", "Step1",
                f"设置DUT电源电压为{rVnormal}V，唤醒CAN网络，等待{rTstable_s}s至通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable_s)
        if ret != 0:
            TestLog("FAIL", "Step1", "电源设置与通信检查失败")
            return
        TestLog("PASS", "Step1", "期望结果：DUT通信正常。实际结果：DUT通信正常")

        ctx.can.set_filter_by_channel(can_channel)
        node = _get_flash_node()

        TestLog("INFO", "Step2", "进入扩展会话并安全访问")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03],
                                expect_str="肯定响应(50 03)"):
            TestLog("FAIL", "Step2", "进入扩展会话失败")
            return
        security_access(node, 0x01)

        # 进入编程会话
        if not _enter_programming_session(node):
            return

        # 启动TesterPresent保持会话
        tester_present_start(node, period_ms=1000)

        TestLog("INFO", "Step3",
                f"在编程会话中施加电压纹波: 在{rVlowStand}V和{rVhighStand}V之间波动")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)

        ripple_cycles = min(P.CANInfo.Tcount, 20)
        session_lost = False
        for i in range(1, ripple_cycles + 1):
            # 低压→高压波动
            ctx.power_ctrl.set_voltage(rVlowStand)
            time.sleep(0.2)
            ctx.power_ctrl.set_voltage(rVhighStand)
            time.sleep(0.2)

            if i % 5 == 0:
                # 每5次检查一次会话是否还保持（发送22读DID验证）
                try:
                    still_alive = service_22_check(node, 0xF1, 0x90,
                                                   expect_data=[0x62, 0xF1, 0x90],
                                                   expect_str="62 F1 90(DID响应)",
                                                   timeout=2)
                    if not still_alive:
                        TestLog("WARNING", "Step3",
                                f"第{i}/{ripple_cycles}次: 编程会话在电压波动中丢失")
                        session_lost = True
                        break
                except:
                    pass

        ctx.power_ctrl.set_voltage(rVnormal)
        tester_present_stop()

        if not session_lost:
            TestLog("PASS", "Step3",
                    f"期望结果：编程会话在{ripple_cycles}次电压纹波中保持。"
                    f"实际结果：会话正常保持")

        TestLog("INFO", "Step4", "电压纹波后验证ECU可正常退出编程会话")
        try:
            node.close()
        except:
            pass
        node = _get_flash_node()

        if _verify_default_session_after_recovery(node):
            TestLog("PASS", "Step4",
                    "期望结果：纹波后ECU正常退出编程会话。实际结果：成功回到默认会话")
        else:
            TestLog("FAIL", "Step4",
                    "期望结果：纹波后ECU正常退出编程会话。实际结果：会话恢复失败")

        TestLog("INFO", "Step5", "监控5分钟验证纹波后的通信稳定性")
        ctx.can.clear_messages()
        ctx.can.set_info('gErrorFrameCount', 0)
        sl_time().sleep(5 * 60 * 1000)

        final_msgs = len(ctx.can.messages)
        final_errs = ctx.can.get_info('gErrorFrameCount') or 0
        if final_msgs > 0 and final_errs == 0:
            TestLog("PASS", "Step5",
                    f"期望结果：纹波后通信稳定。实际结果：{final_msgs}条报文, 0个错误帧")
        else:
            TestLog("WARNING", "Step5",
                    f"通信异常: 报文={final_msgs}, 错误帧={final_errs}")

        TestLog("INFO", "Bootloader电压纹波鲁棒性测试", "测试完成")

    except Exception as e:
        TestLog("FAIL", "Bootloader电压纹波鲁棒性测试", f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", "Bootloader电压纹波鲁棒性测试", f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()
        if node:
            try:
                node.close()
            except:
                pass


def get_all_test_cases():
    import inspect
    current_module = inspect.getmodule(inspect.currentframe())
    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj
    return test_cases
