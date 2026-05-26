import copy
import inspect
import sys
import os
import threading
import time
import traceback
from env.config import *
workdir_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(workdir_path)
from common.context import ctx
from uvtest.testlog import TestLog
from common.control import TestStart, TestEnd
from uvtest.framework import TestFixture
from common.params import P
from testcases.bootloader.utils.bootloader_lin_utils import get_flash_config, main_flash, \
    main_flash_until_erase_memory, service_19_check, service_10_check, service_11_check, phase_pre_programming, \
    tester_present_stop, service_31_check, service_22_check, security_access, \
    phase_programming, phase_pro_programming, phase_programming_before_erase_memory, \
    phase_programming_doing_erase_memory, phase_programming_stop_within_transfer_data, write_fingerprint, \
    get_flash_file, FlashConfig, check_resp, steps_before_download, download_driver, erase_memory, check_memory, \
    check_programming_dependencies, download_file, parse_signature_xml, \
    phase_pre_programming_without_precondition_check, steps_before_download_without_fingerprint, \
    download_driver_without_signature, download_app_without_signature, \
    phase_programming_stop_within_transfer_data_more_2_bytes, phase_programming_stop_within_transfer_data_skip_counter, \
    phase_programming_stop_within_transfer_data_with_same_counter, phase_programming_stop_without_transfer_data, \
    phase_programming_skip_dependencies, lin_restart_delay, parse_flashFile, phase_pro_programming_with_3E_during_reset, \
    get_lin_node, get_max_nummber_of_blocklength_from_0x74
from .utils.hex_parser import parse_hex
from library.security.security import Seed2Key
from tp.lintp_module import lin_can_init, lin_can_deinit
from testcases.uds.lin_test_pre_module import monitor_lin_communication, create_lin_sch
from .lin_comm import lin_node_power_setup_and_communication_check

class UDSLINTestFixture(TestFixture):
    def group_setup(self, context=None):
        lin_can_init()

    def group_teardown(self, context=None):
        lin_can_deinit()

    def case_setup(self, context=None):
        test_name = context.get("test_name") if isinstance(context, dict) else None

        if test_name:
            TestStart(test_name)

    def case_teardown(self, context=None):
        TestEnd("")
        TestLog("INFO", "测试结束", "执行测试结束和去初始化")


def test_TG1_TC1_AppInvalid_DownloadTest():
    """
        应用程序无效时正常下载测试
    """
    case_name = "应用程序无效时正常下载测试"
    flash_config = get_flash_config()
    try:
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        # 获取LIN节点
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 电源和通信检查
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        TestLog("INFO", "Step2", f"测试设备执行下载流程，擦除DUT中的应用程序后停止下载，使应用程序无效")
        if not main_flash_until_erase_memory(node, flash_config):
            return

        TestLog("INFO", "Step3", f"重新上电，等待5s以上，发送 31 01 02 03 请求，验证DUT处于BootLoader模式下")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        lin_restart_delay(5)
        
        resp = node.Service_0x31_RoutineControl(0x01, 0x0203)
        if resp is None:
            TestLog("FAIL", "", "未收到响应")
        elif resp.data[0] == 0x7F and resp.data[1] == 0x31 and resp.data[2] == 0x31:
            TestLog("PASS", "", f"期望: 否定响应(7F 31 31); 实际: {resp.data.hex(' ').upper()}")
        else:
            TestLog("FAIL", "", f"期望: 否定响应(7F 31 31); 实际: {resp.data.hex(' ').upper()}")

        TestLog("INFO", "Step4", f"请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="正响应(50 01)"):
            return

        TestLog("INFO", "Step5", "发送 31 01 02 03 请求，验证DUT处于BootLoader模式下")
        resp = node.Service_0x31_RoutineControl(0x01, 0x0203)
        if resp is None:
            TestLog("FAIL", "", "未收到响应")
        elif resp.data[0] == 0x7F and resp.data[1] == 0x31 and resp.data[2] == 0x31:
            TestLog("PASS", "", f"期望: 否定响应(7F 31 31); 实际: {resp.data.hex(' ').upper()}")
        else:
            TestLog("FAIL", "", f"期望: 否定响应(7F 31 31); 实际: {resp.data.hex(' ').upper()}")

        TestLog("INFO", "Step6", f"ECU复位(11 01)")
        if not service_11_check(node, 0x01, expect_data=[0x51, 0x01], expect_str="肯定响应(51 01)"):
            return

        TestLog("INFO", "Step7", f"发送 31 01 02 03 请求，验证DUT处于BootLoader模式下")
        resp = node.Service_0x31_RoutineControl(0x01, 0x0203)
        if resp is None:
            TestLog("FAIL", "", "未收到响应")
        elif resp.data[0] == 0x7F and resp.data[1] == 0x31 and resp.data[2] == 0x31:
            TestLog("PASS", "", f"期望: 否定响应(7F 31 31); 实际: {resp.data.hex(' ').upper()}")
        else:
            TestLog("FAIL", "", f"期望: 否定响应(7F 31 31); 实际: {resp.data.hex(' ').upper()}")

        TestLog("INFO", "Step8", f"通过测试设备下载正确的应用程序")
        if not main_flash(node, flash_config, support_partition_ab):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG1_TC2_SC1_AppValid_DownloadTest():
    """
        应用程序有效时正常下载测试
    """
    case_name = "应用程序有效时正常下载测试(SC1)"
    flash_config = get_flash_config()
    try:
        rVnormal = 9  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return


        TestLog("INFO", "Step2", f"通过测试设备下载正确的应用程序")
        if not main_flash(node, flash_config, support_partition_ab):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG1_TC2_SC2_AppValid_DownloadTest():
    """
        应用程序有效时正常下载测试
    """
    case_name = "应用程序有效时正常下载测试(SC2)"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return


        TestLog("INFO", "Step2", f"通过测试设备下载正确的应用程序")
        if not main_flash(node, flash_config, support_partition_ab):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG1_TC2_SC3_AppValid_DownloadTest():
    """
        应用程序有效时正常下载测试
    """
    case_name = "应用程序有效时正常下载测试(SC3)"
    flash_config = get_flash_config()
    try:
        rVnormal = 16  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return


        TestLog("INFO", "Step2", f"通过测试设备下载正确的应用程序")
        if not main_flash(node, flash_config, support_partition_ab):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG1_TC3_SC1_ExitTestAfterEnterBootloader():
    """
        正常进入Bootloader模式后退出测试
    """
    case_name = "正常进入Bootloader模式后退出测试(SC1-通过默认会话请求退出)"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        TestLog("INFO", "Step2", "通过测试设备下载正确的应用程序")
        if not main_flash(node, flash_config, support_partition_ab):
            return

        TestLog("INFO", "Step3", "测试设备控制DUT正常执行预编程步骤")
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", f"预编程步骤失败: {msg}")
            return

        TestLog("INFO", "Step4", "测试设备向DUT发送编程会话模式请求")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        # DUT 响应肯定报文后应用报文停止发送检查
        rT_wait = P.LINInfo.TdefaultWait_s
        sch = create_lin_sch()
        sch.start()
        msgs, direction = monitor_lin_communication(rT_wait)
        sch.stop()
        TestLog("INFO", "Step5", "检查应用报文是否停止发送")
        if len(msgs) >= 0:
            for id, all_v in msgs.items():
                if all_v[0]["direction"] == "Rx":
                    for msg in all_v:
                        if msg["dlc"] != 0:
                            TestLog("FAIL", case_name, "应用报文未停止发送，期望在进入编程会话后停止网络通信")
                            return
        TestLog("PASS", "Step5", "应用报文停止发送，符合预期")

        TestLog("INFO", "Step6", "测试设备向DUT发送默认会话模式请求")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        # DUT 响应肯定报文后应用报文恢复发送检查
        sch.start()
        msgs, direction = monitor_lin_communication(rT_wait)
        sch.stop()
        TestLog("INFO", "Step7", "检查应用报文是否恢复发送")
        if len(msgs) >= 0:
            for id, all_v in msgs.items():
                if all_v[0]["direction"] == "Rx":
                    for msg in all_v:
                        if msg["dlc"] == 0:
                            TestLog("FAIL", case_name, "应用报文未恢复发送，期望在返回默认会话后恢复网络通信")
                            return
        TestLog("PASS", "Step7", "应用报文恢复发送，符合预期")
        TestLog("PASS", case_name, "进入Bootloader后退出测试完成，网络通信正常停止和恢复")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG1_TC3_SC2_ExitTestAfterEnterBootloader():
    """
        正常进入Bootloader模式后退出测试
    """
    case_name = "正常进入Bootloader模式后退出测试(SC2-通过ECU复位退出)"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        TestLog("INFO", "Step2", "通过测试设备下载正确的应用程序")
        if not main_flash(node, flash_config, support_partition_ab):
            return

        TestLog("INFO", "Step3", "测试设备控制DUT正常执行预编程步骤")
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", f"预编程步骤失败: {msg}")
            return

        TestLog("INFO", "Step4", "测试设备向DUT发送编程会话模式请求")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        # DUT 响应肯定报文后应用报文停止发送检查
        rT_wait = P.LINInfo.TdefaultWait_s
        sch = create_lin_sch()
        sch.start()
        msgs, direction = monitor_lin_communication(rT_wait)
        sch.stop()
        TestLog("INFO", "Step4", "检查应用报文是否停止发送")
        if len(msgs) >= 0:
            for id, all_v in msgs.items():
                if all_v[0]["direction"] == "Rx":
                    for msg in all_v:
                        if msg["dlc"] != 0:
                            TestLog("FAIL", case_name, "应用报文未停止发送，期望在进入编程会话后停止网络通信")
                            return
        TestLog("PASS", "Step4", "应用报文停止发送，符合预期")

        TestLog("INFO", "Step5", "测试设备向DUT发送ECU复位请求")
        if not service_11_check(node, 0x01, expect_data=[0x51, 0x01], expect_str="肯定响应(51 01)"): return


        # DUT 响应肯定报文后应用报文恢复发送检查
        sch.start()
        msgs, direction = monitor_lin_communication(rT_wait)
        sch.stop()
        TestLog("INFO", "Step5", "检查应用报文是否恢复发送")
        if len(msgs) >= 0:
            for id, all_v in msgs.items():
                if all_v[0]["direction"] == "Rx":
                    for msg in all_v:
                        if msg["dlc"] == 0:
                            TestLog("FAIL", case_name, "应用报文未恢复发送，期望在返回默认会话后恢复网络通信")
                            return
        TestLog("PASS", "Step5", "应用报文恢复发送，符合预期")
        TestLog("PASS", case_name, "进入Bootloader后退出测试完成，网络通信正常停止和恢复")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG1_TC3_SC3_ExitTestAfterEnterBootloader():
    """
        正常进入Bootloader模式后退出测试
    """
    case_name = "正常进入Bootloader模式后退出测试(SC3-通过S3Server超时退出)"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        TestLog("INFO", "Step2", "通过测试设备下载正确的应用程序")
        if not main_flash(node, flash_config, support_partition_ab):
            return

        TestLog("INFO", "Step3", "测试设备控制DUT正常执行预编程步骤")
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", f"预编程步骤失败: {msg}")
            return

        TestLog("INFO", "Step4", "测试设备向DUT发送编程会话模式请求")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

       # DUT 响应肯定报文后应用报文停止发送检查
        rT_wait = P.LINInfo.TdefaultWait_s
        sch = create_lin_sch()
        sch.start()
        msgs, direction = monitor_lin_communication(rT_wait)
        sch.stop()
        TestLog("INFO", "Step4", "检查应用报文是否停止发送")
        if len(msgs) >= 0:
            for id, all_v in msgs.items():
                if all_v[0]["direction"] == "Rx":
                    for msg in all_v:
                        if msg["dlc"] != 0:
                            TestLog("FAIL", case_name, "应用报文未停止发送，期望在进入编程会话后停止网络通信")
                            return
        TestLog("PASS", "Step4", "应用报文停止发送，符合预期")


        TestLog("INFO", "Step5", "测试设备停止周期发送TP(3E)报文，等待5s以上")
        tester_present_stop()
        sch.start()
        time.sleep(6)
        msgs, direction = monitor_lin_communication(rT_wait)
        sch.stop()
        TestLog("INFO", "Step5", "检查应用报文是否恢复发送")
        if len(msgs) >= 0:
            for id, all_v in msgs.items():
                if all_v[0]["direction"] == "Rx":
                    for msg in all_v:
                        if msg["dlc"] == 0:
                            TestLog("FAIL", case_name, "应用报文未恢复发送，期望在返回默认会话后恢复网络通信")
                            return
        TestLog("PASS", "Step5", "应用报文恢复发送，符合预期")
        TestLog("PASS", case_name, "进入Bootloader后退出测试完成，网络通信正常停止和恢复")
    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG1_TC4_StayInBootTest():
    """
        StayInBoot测试
    """
    case_name = "StayInBoot测试"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        if P.TpInfo.StayInBootSupportFlag==False:
            TestLog("FAIL", case_name, "不支持StayInBoot测试")
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return
        
        TestLog("INFO", "Step2", f"停止本地唤醒/远程唤醒源，等待总线睡眠")
        time.sleep(5)

        TestLog("INFO", "Step3", f"唤醒DUT，20ms内发送StayInBoot诊断请求31 01 DD 01")
        lin_restart_delay(0.01)
        status, resp = service_31_check(node, 0x01, 0xDD01, expect_data=[0x71, 0x01, 0xDD, 0x01], expect_str="肯定响应(71 01 DD 01)")
        if not status: return

        TestLog("INFO", "Step4", f"发送 31 01 02 03 请求，验证DUT处于BootLoader模式下")
        resp = node.Service_0x31_RoutineControl(0x01, 0x0203)
        if resp is None:
            TestLog("FAIL", "", "未收到响应")
        elif resp.data[0] == 0x7F and resp.data[1] == 0x31 and resp.data[2] == 0x31:
            TestLog("PASS", "", f"期望: 否定响应(7F 31 31); 实际: {resp.data.hex(' ').upper()}")
        else:
            TestLog("FAIL", "", f"期望: 否定响应(7F 31 31); 实际: {resp.data.hex(' ').upper()}")

        TestLog("INFO", "Step6", f"发送诊断请求 31 01 DD 01")
        status, resp = service_31_check(node, 0x01, 0xDD01, expect_data=[0x7F, 0x31, 0x7F], expect_str="否定响应(7F 31 7F)")
        if not status: return

        TestLog("INFO", "Step7", f"停止本地唤醒/远程唤醒源，等待总线睡眠")
        time.sleep(5)

        TestLog("INFO", "Step8", f"唤醒DUT，20ms内发送StayInBoot诊断请求31 01 DD 01")
        lin_restart_delay(0.02)
        status, resp = service_31_check(node, 0x01, 0xDD01, expect_data=[0x7F, 0x31, 0x7F], expect_str="否定响应(7F 31 7F)")
        if not status: return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

# TODO: 用力更新，注销
# def test_TG1_TC5_SC1_multiple_file_types_app():
#     """
#         多文件类型下载测试
#     """
#     case_name = "多文件类型下载测试 应用软件"
#     flash_config = get_flash_config("APP")
#     try:
#         rVnormal = P.LINInfo.Vnormal  # 电源正常电压
#         rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
#         support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
#         node = get_lin_node()
#         if node is None:
#             TestLog("FAIL", case_name, "获取LIN节点失败")
#             return
#         ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
#         if ret != 0:
#             TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
#             return
#
#         TestLog("INFO", "Step2", f"应用软件 下载")
#         if not main_flash(node, flash_config, support_partition_ab):
#             return
#
#         TestLog("INFO", "Step3", f"检查DUT是否正常工作")
#         rT_wait = P.LINInfo.TdefaultWait_s
#         sch = create_lin_sch()
#         sch.start()
#         msgs, direction = monitor_lin_communication(rT_wait)
#         sch.stop()
#         if len(msgs) >= 0:
#             for id, all_v in msgs.items():
#                 if all_v[0]["direction"] == "Rx":
#                     for msg in all_v:
#                         if msg["dlc"] == 0:
#                             TestLog("FAIL", case_name, "DUT未正常工作")
#                             return
#         TestLog("PASS", "Step3", "DUT 正常发送应用报文")
#
#     except Exception as e:
#         TestLog("FAIL", case_name, f"测试执行出错: {e}")
#         import traceback
#         TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
#     finally:
#         tester_present_stop()
#
# def test_TG1_TC5_SC2_multiple_file_types_cfg():
#     """
#         多文件类型下载测试
#     """
#     case_name = "多文件类型下载测试 网络配置数据"
#     flash_config = get_flash_config("Config")
#     try:
#         rVnormal = P.LINInfo.Vnormal  # 电源正常电压
#         rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
#         support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
#         node = get_lin_node()
#         if node is None:
#             TestLog("FAIL", case_name, "获取LIN节点失败")
#             return
#         ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
#         if ret != 0:
#             TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
#             return
#
#         TestLog("INFO", "Step2", f"网络配置数据 下载")
#         if not main_flash(node, flash_config, support_partition_ab):
#             return
#
#         TestLog("INFO", "Step3", f"检查DUT是否正常工作")
#         rT_wait = P.LINInfo.TdefaultWait_s
#         sch = create_lin_sch()
#         sch.start()
#         msgs, direction = monitor_lin_communication(rT_wait)
#         sch.stop()
#         if len(msgs) >= 0:
#             for id, all_v in msgs.items():
#                 if all_v[0]["direction"] == "Rx":
#                     for msg in all_v:
#                         if msg["dlc"] == 0:
#                             TestLog("FAIL", case_name, "DUT未正常工作")
#                             return
#         TestLog("PASS", "Step3", "DUT 正常发送应用报文")
#
#     except Exception as e:
#         TestLog("FAIL", case_name, f"测试执行出错: {e}")
#         import traceback
#         TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
#     finally:
#         tester_present_stop()
#
# def test_TG1_TC5_SC3_multiple_file_types_cal():
#     """
#         多文件类型下载测试
#     """
#     case_name = "多文件类型下载测试 标定数据"
#     flash_config = get_flash_config("CAL")
#     try:
#         rVnormal = P.LINInfo.Vnormal  # 电源正常电压
#         rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
#         support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
#         node = get_lin_node()
#         if node is None:
#             TestLog("FAIL", case_name, "获取LIN节点失败")
#             return
#         ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
#         if ret != 0:
#             TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
#             return
#         TestLog("INFO", "Step2", f"标定数据下载 下载")
#         if not main_flash(node, flash_config, support_partition_ab):
#             return
#
#         TestLog("INFO", "Step3", f"检查DUT是否正常工作")
#         rT_wait = P.LINInfo.TdefaultWait_s
#         sch = create_lin_sch()
#         sch.start()
#         msgs, direction = monitor_lin_communication(rT_wait)
#         sch.stop()
#         if len(msgs) >= 0:
#             for id, all_v in msgs.items():
#                 if all_v[0]["direction"] == "Rx":
#                     for msg in all_v:
#                         if msg["dlc"] == 0:
#                             TestLog("FAIL", case_name, "DUT未正常工作")
#                             return
#         TestLog("PASS", "Step3", "DUT 正常发送应用报文")
#
#     except Exception as e:
#         TestLog("FAIL", case_name, f"测试执行出错: {e}")
#         import traceback
#         TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
#     finally:
#         tester_present_stop()
#
# def test_TG1_TC5_SC4_multiple_file_types_app_cfg_cal():
#     """
#         多文件类型下载测试
#     """
#     case_name = "多文件类型下载测试 应用软件+网络配置数据+标定数据"
#     flash_config = get_flash_config()
#     try:
#         rVnormal = P.LINInfo.Vnormal  # 电源正常电压
#         rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
#         support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
#         node = get_lin_node()
#         if node is None:
#             TestLog("FAIL", case_name, "获取LIN节点失败")
#             return
#         ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
#         if ret != 0:
#             TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
#             return
#
#         TestLog("INFO", "Step2", f"应用软件+网络配置数据+标定数据下载")
#         if not main_flash(node, flash_config, support_partition_ab):
#             return
#
#         TestLog("INFO", "Step3", f"检查DUT是否正常工作")
#         rT_wait = P.LINInfo.TdefaultWait_s
#         sch = create_lin_sch()
#         sch.start()
#         msgs, direction = monitor_lin_communication(rT_wait)
#         sch.stop()
#         if len(msgs) >= 0:
#             for id, all_v in msgs.items():
#                 if all_v[0]["direction"] == "Rx":
#                     for msg in all_v:
#                         if msg["dlc"] == 0:
#                             TestLog("FAIL", case_name, "DUT未正常工作")
#                             return
#         TestLog("PASS", "Step3", "DUT 正常发送应用报文")
#
#     except Exception as e:
#         TestLog("FAIL", case_name, f"测试执行出错: {e}")
#         import traceback
#         TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
#     finally:
#         tester_present_stop()

def test_TG1_TC5_SC1_ProgrammingConditionCheckTest():
    """
        编程条件检查测试-SubCase1
    """
    case_name = "编程条件检查测试-SubCase1"

    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return
        

        TestLog("INFO", "Step2", "执行进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"):
            return

        TestLog("INFO", "Step3", "执行进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
            return

        TestLog("INFO", "Step4", "执行编程条件检查(31 01 02 03)")
        status, resp = service_31_check(node, 0x01, 0x0203, expect_data=[0x71, 0x01, 0x02, 0x03, 0x00],
                                        expect_str="肯定响应(71 01 02 03 00)")
        if not status:
            return

        TestLog("INFO", "Step5", "执行进入编程会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG1_TC5_SC2_ProgrammingConditionCheckTest():
    """
        编程条件检查测试-SubCase2
    """
    case_name = "编程条件检查测试-SubCase2"

    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        sig_info1 = P.sig_info.get_by_type("Speed_Smaller_3km")
        sig_info2 = P.sig_info.get_by_type("Gear_P")
        if len(sig_info1)==0 or len(sig_info2):
            TestLog("FAIL", "Step1", "模拟车速≤3km/h，档位P档,不支持")
            return
        sig_info = sig_info1 + sig_info2
        sig_val ={}
        for sig in sig_info:
            sig_val[sig.sig] = sig.val
            if (sig.sig==None) or (sig.val==None):
                TestLog("FAIL", "Step1", "模拟车速≤3km/h，档位P档,不支持")
                return

        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        TestLog("INFO", "Step2", "TODO:模拟车速≤3km/h，档位P档，等待5s后停止发送")
        from tp.lin_test_pre_module import set_sig_data
        set_sig_data(sig_val)
        lin_restart_delay(1,True)        
        lin_restart_delay(5)

        TestLog("INFO", "Step3", "TODO:等待5s，再次开始模拟车速≤3km/h，档位P档")
        lin_restart_delay(5,True)

        TestLog("INFO", "Step4", "执行进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"):
            return

        TestLog("INFO", "Step5", "执行进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
            return

        TestLog("INFO", "Step6", "执行编程条件检查(31 01 02 03)")
        status, resp = service_31_check(node, 0x01, 0x0203, expect_data=[0x71, 0x01, 0x02, 0x03, 0x00],
                                        expect_str="肯定响应(71 01 02 03 00)")
        if not status:
            return

        TestLog("INFO", "Step7", "执行进入编程会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG1_TC5_SC3_ProgrammingConditionCheckTest():
    """
        编程条件检查测试-SubCase3
    """
    case_name = "编程条件检查测试-SubCase3"

    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        sig_info1 = P.sig_info.get_by_type("Speed_Smaller_3km")
        sig_info2 = P.sig_info.get_by_type("Gear_N")
        if len(sig_info1)==0 or len(sig_info2):
            TestLog("FAIL", "Step1", "模拟车速≤3km/h，档位N档,不支持")
            return
        sig_info = sig_info1 + sig_info2
        sig_val ={}
        for sig in sig_info:
            sig_val[sig.sig] = sig.val
            if (sig.sig==None) or (sig.val==None):
                TestLog("FAIL", "Step1", "模拟车速≤3km/h，档位N档,不支持")
                return


        TestLog("INFO", "Step2", "TODO:模拟车速≤3km/h，档位N档")
        from tp.lin_test_pre_module import set_sig_data
        set_sig_data(sig_val)
        lin_restart_delay(1,True)        

        TestLog("INFO", "Step3", "执行进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"):
            return

        TestLog("INFO", "Step4", "执行进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
            return

        TestLog("INFO", "Step5", "执行编程条件检查(31 01 02 03)")
        status, resp = service_31_check(node, 0x01, 0x0203, expect_data=[0x71, 0x01, 0x02, 0x03, 0x00],
                                        expect_str="肯定响应(71 01 02 03 00)")
        if not status:
            return

        TestLog("INFO", "Step6", "执行进入编程会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG1_TC5_SC4_ProgrammingConditionCheckTest():
    """
        编程条件检查测试-SubCase4
    """
    case_name = "编程条件检查测试-SubCase4(发动机转速异常)"

    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return
        
        sig_info1 = P.sig_info.get_by_type("Motor_Larger_1000rmp")
        if len(sig_info1)==0 :
            TestLog("FAIL", "Step1", "模拟发送机转速>1000rpm,不支持")
            return
        sig_info = sig_info1
        sig_val ={}
        for sig in sig_info:
            sig_val[sig.sig] = sig.val
            if (sig.sig==None) or (sig.val==None):
                TestLog("FAIL", "Step1", "模拟发送机转速>1000rpm,不支持")
                return

        TestLog("INFO", "Step2", "TODO:模拟发送机转速>1000rpm")
        from tp.lin_test_pre_module import set_sig_data
        set_sig_data(sig_val)
        lin_restart_delay(1,True)   

        TestLog("INFO", "Step3", "执行进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"):
            return

        TestLog("INFO", "Step4", "执行进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
            return

        TestLog("INFO", "Step5", "执行编程条件检查(31 01 02 03)")
        status, resp = service_31_check(node, 0x01, 0x0203, expect_data=[0x71, 0x01, 0x02, 0x03, 0x00],
                                        expect_str="肯定响应(71 01 02 03 00)")
        if not status:
            return

        TestLog("INFO", "Step6", "执行进入编程会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG1_TC5_SC5_ProgrammingConditionCheckTest():
    """
        编程条件检查测试-SubCase5
    """
    case_name = "编程条件检查测试-SubCase5(车速异常)"
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return
        sig_info1 = P.sig_info.get_by_type("Speed_Larger_3km")
        sig_info2 = P.sig_info.get_by_type("Gear_N")
        if len(sig_info1)==0 or len(sig_info2):
            TestLog("FAIL", "Step1", "模拟车速>3km/h，档位N档,不支持")
            return
        sig_info = sig_info1 + sig_info2
        sig_val ={}
        for sig in sig_info:
            sig_val[sig.sig] = sig.val
            if (sig.sig==None) or (sig.val==None):
                TestLog("FAIL", "Step1", "模拟车速>3km/h，档位N档,不支持")
                return

        TestLog("INFO", "Step2", "TODO: 模拟车速>3km/h，档位P/N档")
        from tp.lin_test_pre_module import set_sig_data
        set_sig_data(sig_val)
        lin_restart_delay(1,True)   

        TestLog("INFO", "Step3", "执行进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"):
            return

        TestLog("INFO", "Step4", "执行进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
            return

        TestLog("INFO", "Step5", "执行编程条件检查(31 01 02 03)")
        status, resp = service_31_check(node, 0x01, 0x0203, expect_data=[0x71, 0x01, 0x02, 0x03, 0x03],
                                        expect_str="响应(71 01 02 03 03)-车速异常")
        if not status:
            TestLog("INFO", "", "编程条件检查未返回预期的异常响应")

        TestLog("INFO", "Step6", "执行进入编程会话(10 02)，期望否定响应")
        if service_10_check(node, 0x02, expect_data=[0x7F, 0x10, 0x22], expect_str="否定响应(7F 10 22)"):
            TestLog("PASS", "", "正确返回条件不满足的否定响应")
        else:
            TestLog("FAIL", "", "未返回预期的否定响应")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG1_TC5_SC6_ProgrammingConditionCheckTest():
    """
        编程条件检查测试-SubCase6
    """
    case_name = "编程条件检查测试-SubCase6(档位异常)"

    try:
        rVnormal = P.LINInfo.Vnormal
        rTstable = P.LINInfo.TdefaultWait_s
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return
        
        sig_info1 = P.sig_info.get_by_type("Speed_Smaller_3km")
        sig_info2 = P.sig_info.get_by_type("Gear_D")
        if len(sig_info1)==0 or len(sig_info2):
            TestLog("FAIL", "Step1", "模拟车速≤3km/h，档位D档,不支持")
            return
        sig_info = sig_info1 + sig_info2
        sig_val ={}
        for sig in sig_info:
            sig_val[sig.sig] = sig.val
            if (sig.sig==None) or (sig.val==None):
                TestLog("FAIL", "Step1", "模拟车速≤3km/h，档位D档,不支持")
                return        

        TestLog("INFO", "Step2", "TODO: 模拟车速≤3km/h，档位非P/N档(如D档)")
        from tp.lin_test_pre_module import set_sig_data
        set_sig_data(sig_val)
        lin_restart_delay(1,True)   
        
        TestLog("INFO", "Step3", "执行进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"):
            return

        TestLog("INFO", "Step4", "执行进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
            return

        TestLog("INFO", "Step5", "执行编程条件检查(31 01 02 03)")
        status, resp = service_31_check(node, 0x01, 0x0203, expect_data=[0x71, 0x01, 0x02, 0x03, 0x05],
                                        expect_str="响应(71 01 02 03 05)-档位异常")
        if not status:
            TestLog("INFO", "", "编程条件检查未返回预期的异常响应")

        TestLog("INFO", "Step6", "执行进入编程会话(10 02)，期望否定响应")
        if service_10_check(node, 0x02, expect_data=[0x7F, 0x10, 0x22], expect_str="否定响应(7F 10 22)"):
            TestLog("PASS", "", "正确返回条件不满足的否定响应")
        else:
            TestLog("FAIL", "", "未返回预期的否定响应")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG1_TC5_SC7_ProgrammingConditionCheckTest():
    """
        编程条件检查测试-SubCase7
    """
    case_name = "编程条件检查测试-SubCase7(电压过低)"


    try:
        rVlow = 7.0  # 低电压
        rTstable = P.LINInfo.TdefaultWait_s
        rVnormal = 12
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        TestLog("INFO", "Step1", f"设置DUT供电电压为12V, 等待{rTstable}s至总线通信稳定")
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return
        
        ctx.power_ctrl.set_voltage(rVlow)
        TestLog("INFO", "Step2", f"设置DUT供电电压为{rVlow}V(欠压)")

        TestLog("INFO", "Step3", "执行进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"):
            return

        TestLog("INFO", "Step4", "执行进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
            return

        TestLog("INFO", "Step5", "执行编程条件检查(31 01 02 03)")
        status, resp = service_31_check(node, 0x01, 0x0203, expect_data=[0x71, 0x01, 0x02, 0x03, 0x02],
                                        expect_str="响应(71 01 02 03 02)-电压异常")
        if not status:
            TestLog("INFO", "", "编程条件检查未返回预期的异常响应")

        TestLog("INFO", "Step6", "执行进入编程会话(10 02)，期望否定响应")
        if service_10_check(node, 0x02, expect_data=[0x7F, 0x10, 0x22], expect_str="否定响应(7F 10 22)"):
            TestLog("PASS", "", "正确返回条件不满足的否定响应")
        else:
            TestLog("FAIL", "", "未返回预期的否定响应")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        try:
            ctx.power_ctrl.set_voltage(rVnormal)
        except:
            pass
        tester_present_stop()

def test_TG1_TC5_SC8_ProgrammingConditionCheckTest():
    """
        编程条件检查测试-SubCase8
    """
    case_name = "编程条件检查测试-SubCase8(电压过高)"


    try:
        rHight = 18.0  # 高电压
        rTstable = P.LINInfo.TdefaultWait_s
        rVnormal = 12
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        TestLog("INFO", "Step1", f"设置DUT供电电压为12V, 等待{rTstable}s至总线通信稳定")
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return
        
        ctx.power_ctrl.set_voltage(rHight)
        TestLog("INFO", "Step2", f"设置DUT供电电压为{rHight}V(过压)")

        TestLog("INFO", "Step3", "执行进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"):
            return

        TestLog("INFO", "Step4", "执行进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
            return

        TestLog("INFO", "Step5", "执行编程条件检查(31 01 02 03)")
        status, resp = service_31_check(node, 0x01, 0x0203, expect_data=[0x71, 0x01, 0x02, 0x03, 0x02],
                                        expect_str="响应(71 01 02 03 02)-电压异常")
        if not status:
            TestLog("INFO", "", "编程条件检查未返回预期的异常响应")

        TestLog("INFO", "Step6", "执行进入编程会话(10 02)，期望否定响应")
        if service_10_check(node, 0x02, expect_data=[0x7F, 0x10, 0x22], expect_str="否定响应(7F 10 22)"):
            TestLog("PASS", "", "正确返回条件不满足的否定响应")
        else:
            TestLog("FAIL", "", "未返回预期的否定响应")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        # 恢复正常电压
        try:
            ctx.power_ctrl.set_voltage(rVnormal)
        except:
            pass
        tester_present_stop()

def test_TG1_TC6_2E_WriteDataAfterFlashTest():
    """
        应用软件下载不改变配置数据测试
    """
    case_name = "应用软件下载不改变配置数据测试"
    flash_config = get_flash_config()

    did_list = [
        (0xF190, "VIN码"),
        (0xF187, "零件号"),
        (0xF18A, "供应商代码"),
        (0xF089, "硬件版本号"),
        (0xF180, "FBL版本号"),
    ]

    def read_multiple_dids(node, did_list):
        """读取多个DID并返回数据字典，读取失败的DID记录为None并继续读取下一个"""
        data_dict = {}
        fail_count = 0
        for did, name in did_list:
            did_high = (did >> 8) & 0xFF
            did_low = did & 0xFF
            status, respMsg = service_22_check(node, did, expect_data=[0x62, did_high, did_low],
                                               expect_str=f"肯定响应(62 {did_high:02X} {did_low:02X})")
            if not status:
                TestLog("FAIL", "", f"读取{name}({hex(did)})失败")
                data_dict[did] = None
                fail_count += 1
                continue
            if respMsg is None or not hasattr(respMsg, 'data') or respMsg.data is None:
                TestLog("FAIL", "", f"读取{name}({hex(did)})未收到有效响应")
                data_dict[did] = None
                fail_count += 1
                continue
            resp = respMsg.data
            data_dict[did] = bytes(resp[3:]) if len(resp) > 3 else b''
            TestLog("INFO", "", f"{name}({hex(did)})={data_dict[did].hex(' ').upper() if data_dict[did] else 'Empty'}")

        if fail_count > 0:
            TestLog("WARN", "", f"共有{fail_count}个DID读取失败")
        return data_dict

    try:
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        rVnormal = P.LINInfo.Vnormal
        rTstable = P.LINInfo.TdefaultWait_s
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        TestLog("INFO", "Step1", "设置DUT供电电压为12V，等待2s至总线通信稳定")
        TestLog("PASS", "", "DUT正常发送应用报文")

        TestLog("INFO", "Step2", "读取VIN码(F190)、零件号(F187)、供应商代码(F18A)、硬件版本号(F089)、FBL版本号(F180)，记为DATA1")
        data1 = read_multiple_dids(node, did_list)
        if data1 is None:
            return

        TestLog("INFO", "Step3", "通过测试设备重新下载正确的应用程序")
        if not main_flash(node, flash_config, support_partition_ab):
            return

        TestLog("INFO", "Step4", "控制程控电源给DUT重新上电")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        lin_restart_delay(rTstable)

        TestLog("INFO", "Step5", "读取VIN码(F190)、零件号(F187)、供应商代码(F18A)、硬件版本号(F089)、FBL版本号(F180)，记为DATA2，与DATA1比对")
        data2 = read_multiple_dids(node, did_list)
        if data2 is None:
            return

        # 比对DATA1和DATA2，记录结果但继续执行后续步骤
        step5_all_match = True
        for did, name in did_list:
            if data1[did] is None or data2[did] is None:
                TestLog("FAIL", "", f"{name}({hex(did)}): 数据读取失败，无法比对")
                step5_all_match = False
            elif data1[did] == data2[did]:
                TestLog("PASS", "", f"{name}({hex(did)}): DATA2=DATA1(数据保持)")
            else:
                TestLog("FAIL", "", f"{name}({hex(did)}): DATA2!=DATA1(数据不一致)")
                step5_all_match = False

        TestLog("INFO", "Step6", "读取指纹(22 F1 84)，记为DATA3")
        status, respMsg = service_22_check(node, 0xF184, expect_data=[0x62, 0xF1, 0x84],
                                           expect_str="肯定响应(62 F1 84)")
        if not status:
            return
        if respMsg is None or not hasattr(respMsg, 'data') or respMsg.data is None:
            TestLog("FAIL", "", "未收到有效响应")
            return
        resp = respMsg.data
        data3 = bytes(resp[3:]) if len(resp) > 3 else b''
        TestLog("INFO", "", f"DATA3={data3.hex(' ').upper() if data3 else 'Empty'}")

        TestLog("INFO", "Step7", "进入扩展会话(10 03)，通过安全访问，写入指纹DATA4")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
            return
        if not security_access(node, 0x01):
            return

        from testcases.bootloader.utils.bootloader_lin_utils import make_fingerprint
        fingerprint_data = make_fingerprint("TestFlash")
        data4 = bytes(fingerprint_data)
        TestLog("INFO", "", f"DATA4={data4.hex(' ').upper()}")
        resp = node.Service_0x2E_WriteDataByIdentifier(0xF184, fingerprint_data)
        if resp is None:
            TestLog("FAIL", "", "写入指纹失败: 未收到响应")
            return
        resp_data = resp.data if hasattr(resp, 'data') else resp
        if resp_data[0] != 0x6E:
            TestLog("FAIL", "", f"期望: 肯定响应(6E F1 84); 实际: {resp_data.hex(' ').upper()}")
            return
        TestLog("PASS", "", f"期望: 肯定响应(6E F1 84); 实际: {resp_data.hex(' ').upper()}")

        TestLog("INFO", "Step8", "通过测试设备重新下载正确的应用程序")
        if not main_flash(node, flash_config, support_partition_ab):
            return

        TestLog("INFO", "", "控制程控电源给DUT重新上电")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        lin_restart_delay(rTstable)

        TestLog("INFO", "Step9", "读取指纹(22 F1 84)，记为DATA5，与DATA4比对")
        status, respMsg = service_22_check(node, 0xF184, expect_data=[0x62, 0xF1, 0x84],
                                           expect_str="肯定响应(62 F1 84)")
        if not status:
            return
        if respMsg is None or not hasattr(respMsg, 'data') or respMsg.data is None:
            TestLog("FAIL", "", "未收到有效响应")
            return
        resp = respMsg.data
        data5 = bytes(resp[3:]) if len(resp) > 3 else b''
        TestLog("INFO", "", f"DATA5={data5.hex(' ').upper() if data5 else 'Empty'}")

        if data5 == data4:
            TestLog("PASS", "", f"期望: DATA5=DATA4(数据保持); 实际: DATA5=DATA4")
        else:
            TestLog("FAIL", "", f"期望: DATA5=DATA4(数据保持); 实际: DATA5!=DATA4")
            return

        TestLog("INFO", "Step10", "进入扩展会话(10 03)，通过安全访问，将DATA3重新写入DUT")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
            return
        if not security_access(node, 0x01):
            return

        resp = node.Service_0x2E_WriteDataByIdentifier(0xF184, data3)
        if resp is None:
            TestLog("FAIL", "", "写入指纹失败: 未收到响应")
            return
        resp_data = resp.data if hasattr(resp, 'data') else resp
        if resp_data[0] != 0x6E:
            TestLog("FAIL", "", f"期望: 肯定响应(6E F1 84); 实际: {resp_data.hex(' ').upper()}")
            return
        TestLog("PASS", "", f"期望: 肯定响应(6E F1 84); 实际: {resp_data.hex(' ').upper()}")

        # 汇总判断测试结果
        if not step5_all_match:
            TestLog("FAIL", "", "Step5比对失败: 刷写后配置数据发生变化")
        else:
            TestLog("PASS", case_name, "测试通过: 刷写后配置数据保持一致，2E服务写入功能正常")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG2_TC1_SC1_PowerOffBeforeEraseMemoryTest():
    """
        内存擦除中断电测试-擦除内存中断开电源
    """
    case_name = "内存擦除前断电测试-擦除内存中断开电源"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return
        
        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在测试设备发出擦除内存请求（31 01 FF 00+data）后等待 50ms，控制程控电源断开 KL30电 10s")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", "预编程阶段失败")
            return

        # 编程阶段 - 发送擦除内存请求(31 01 FF 00)后停止
        status, msg = phase_programming_doing_erase_memory(node, flash_config, support_partition_ab)
        if not status:
            TestLog("FAIL", "", "编程阶段失败")
            return

        # 等待50ms后断电
        time.sleep(0.05)
        ctx.bob_ctrl.set_power("KL30", False)
        lin_restart_delay(10)

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.bob_ctrl.set_power("KL30", True)
        lin_restart_delay(10)
        
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG2_TC2_SC1_PowerOffWithinEraseMemoryTest():
    """
        通信中断测试 LIN与KL30 短路
    """
    case_name = "通信中断测试 LIN与KL30 短路"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return
        
        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在发送内存擦除请求前控制程控电源LIN短路KL30电10s")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", "预编程阶段失败")
            return

        # 编程阶段
        phase_programming_stop_within_transfer_data(node, flash_config, support_partition_ab)
        time.sleep(1)
        TestLog("INFO", "", f"设置LIN短路KL30")
        ctx.bob_ctrl.set_fault("LIN1","SHORT_KL30", True)
        lin_restart_delay(10)

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.bob_ctrl.set_fault("LIN1","SHORT_KL30", False)
        lin_restart_delay(10)

        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG2_TC3_SC1_PowerOffStopWithinTransferDataTest():
    """
        通信中断测试 LIN与地短路
    """
    case_name = "数据传输中断电测试-数据传输过程断开电源正极"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在数据传输中控制程控电电源LIN短路GND电10s")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", "预编程阶段失败")
            return

        # 编程阶段
        phase_programming_stop_within_transfer_data(node, flash_config, support_partition_ab)
        time.sleep(1)
        ctx.bob_ctrl.set_fault("LIN1","SHORT_GND", True)
        lin_restart_delay(10)

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.bob_ctrl.set_fault("LIN1","SHORT_GND", False)
        lin_restart_delay(10)

        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG2_TC4_SC1_LinOpenWithinTransferDataTest():
    """
        通信中断测试 LIN断路
    """
    case_name = "通信中断测试 LIN断路"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在数据传输中控制程控电源断开LIN线")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", "预编程阶段失败")
            return

        # 编程阶段
        phase_programming_stop_within_transfer_data(node, flash_config, support_partition_ab)
        time.sleep(1)
        ctx.bob_ctrl.set_fault("LIN1","OPEN", True)
        lin_restart_delay(10)

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.bob_ctrl.set_fault("LIN1","OPEN", False)
        lin_restart_delay(10)

        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG2_TC5_SC1_PowerOffStopWithinTransferDataTest():
    """
        数据传输中断电测试-数据传输过程断开电源正极
    """
    case_name = "数据传输中断电测试-断开电源"
    flash_config = get_flash_config()

    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return
        
        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在数据传输中控制程控电源断开KL30电10s")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return

        # 编程阶段
        phase_programming_stop_within_transfer_data(node, flash_config, support_partition_ab)
        time.sleep(1)
        ctx.bob_ctrl.set_power("KL30", False)
        tester_present_stop()
        lin_restart_delay(10)

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.bob_ctrl.set_power("KL30", True)
        lin_restart_delay(10)

        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG2_TC5_SC2_PowerOffStopWithinTransferDataTest():
    """
        数据传输中断电测试-数据传输过程断开电源地
    """
    case_name = "数据传输中断电测试-断开地"
    flash_config = get_flash_config()

    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在数据传输中控制程控电源断开电源地10s")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return

        # 编程阶段
        phase_programming_stop_within_transfer_data(node, flash_config, support_partition_ab)
        time.sleep(1)
        ctx.bob_ctrl.set_power("GND", False)
        tester_present_stop()
        lin_restart_delay(10)

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.bob_ctrl.set_power("GND", True)
        lin_restart_delay(10)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG2_TC6_SC1_DiagnosticInterferenceTest():
    """
        数据传输中诊断指令干扰测试-SubCase1
    """
    case_name = "数据传输中诊断指令干扰测试-34请求后干扰"
    flash_config = get_flash_config()

    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return


        TestLog("INFO", "Step2", "通过测试设备执行刷写流程，在请求下载步骤完成之后，发送22服务诊断请求(22 F0 89)")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", "预编程阶段失败")
            return

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        # 下载driver
        if not download_driver(node, flash_files):
            TestLog("FAIL", "", "下载DRIVER失败")
            return

        # 完成刷写流程
        flash_success = False
        first_34_done = False  # 移到外层循环之前，确保只干扰一次
        for item in flash_files:
            if not FlashConfig.check_app(item):
                continue
            if not erase_memory(node, item.path_hexS19):
                TestLog("FAIL", "", "APP内存擦除失败")
                return

            block_infos, start_addr = parse_flashFile(item.path_hexS19)
            if start_addr is None:
                TestLog("FAIL", "", "解析Flash文件失败")
                return

            for block in block_infos:
                start_address = block["address"]
                data = block["data"]
                length = len(data)
                resp = node.Service_0x34_RequestDownload(dataformat=0x00,
                                                         size_len=4,
                                                         address_len=4,
                                                         size=length,
                                                         address=start_address)
                if resp is None or resp.data[0] != 0x74:
                    TestLog("FAIL", "", "请求下载(34)失败")
                    return

                # 在第一个34请求后发送22服务诊断请求
                if not first_34_done:
                    TestLog("INFO", "", "在34请求后发送22服务诊断请求(22 F0 89)")
                    resp_22 = node.Service_0x22_ReadDataByIdentifier(id=0xF089)
                    if resp_22 is not None:
                        TestLog("INFO", "", f"DUT响应了22服务请求: {resp_22.data.hex(' ').upper()}")
                    else:
                        TestLog("INFO", "", "DUT忽略22服务请求，不回复响应报文(符合预期)")
                    first_34_done = True

                    # 干扰后重新发送34请求，恢复传输流程
                    TestLog("INFO", "", "干扰后重新发送34请求")
                    resp = node.Service_0x34_RequestDownload(dataformat=0x00,
                                                             size_len=4,
                                                             address_len=4,
                                                             size=length,
                                                             address=start_address)
                    if resp is None or resp.data[0] != 0x74:
                        TestLog("FAIL", "", "干扰后重新请求下载(34)失败")
                        return

                TestLog("INFO", "Step3", "继续执行后续的刷写流程")
                # 继续执行36数据传输（在34请求之后，手动完成36和37）
                max_block_length = resp.data[2] << 8 | resp.data[3]
                max_block_length = max_block_length - 2
                counter = 1
                while len(data) > 0:
                    chunk = data[:max_block_length]
                    resp_36 = node.Service_0x36_TransferData_WithoutPrint(counter, chunk, timeout=10)
                    if resp_36 is None or resp_36.data[0] != 0x76:
                        TestLog("FAIL", "", "数据传输(36)失败")
                        return
                    data = data[max_block_length:]
                    counter = (counter + 1) % 256

                # 发送37服务
                resp_37 = node.Service_0x37_RequestTransferExit()
                if resp_37 is None or resp_37.data[0] != 0x77:
                    TestLog("FAIL", "", "传输退出(37)失败")
                    return

            if not check_memory(node, item.path_xml, item.path_hexS19):
                TestLog("FAIL", "", "APP文件安全签名验证失败")
                return
            flash_success = True

        if flash_success:
            # 后编程阶段
            status, msg = phase_pro_programming(node)
            if status:
                TestLog("PASS", "", "DUT可以成功的通过BootLoader软件将应用程序下载到DUT中")
            else:
                TestLog("FAIL", "", "后编程阶段失败")
        else:
            TestLog("FAIL", "", "刷写流程失败")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG2_TC6_SC2_DiagnosticInterferenceTest():
    """
        数据传输中诊断指令干扰测试-SubCase2
    """
    case_name = "数据传输中诊断指令干扰测试-36服务传输过程中干扰"
    flash_config = get_flash_config()

    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return


        TestLog("INFO", "Step2", "通过测试设备执行刷写流程，在36服务传输过程中，发送22服务诊断请求(22 F0 89)")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", "预编程阶段失败")
            return

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        # 下载driver
        if not download_driver(node, flash_files):
            TestLog("FAIL", "", "下载DRIVER失败")
            return

        # 完成刷写流程
        flash_success = False
        for item in flash_files:
            if not FlashConfig.check_app(item):
                continue
            if not erase_memory(node, item.path_hexS19):
                TestLog("FAIL", "", "APP内存擦除失败")
                return

            block_infos, start_addr = parse_flashFile(item.path_hexS19)
            if start_addr is None:
                TestLog("FAIL", "", "解析Flash文件失败")
                return

            interference_done = False
            for block_idx, block in enumerate(block_infos):
                start_address = block["address"]
                data = block["data"]
                length = len(data)
                resp = node.Service_0x34_RequestDownload(dataformat=0x00,
                                                         size_len=4,
                                                         address_len=4,
                                                         size=length,
                                                         address=start_address)
                if resp is None or resp.data[0] != 0x74:
                    TestLog("FAIL", "", "请求下载(34)失败")
                    return

                # 从lengthFormatIdentifier的高4位获取maxNumberOfBlockLength的字节数
                n = resp.data[1] >> 4
                max_number_of_block_length = 0
                for i in range(n):
                    max_number_of_block_length = max_number_of_block_length | (resp.data[2 + i] << (8 * (n - i - 1)))
                sequence_counter = 1
                offset = 0
                # 在36服务传输过程中发送22服务诊断请求（第一个block传输过程中干扰）
                first_36_of_block = True
                while offset < length:
                    chunk_size = min(max_number_of_block_length - 2, length - offset)
                    chunk_data = data[offset:offset + chunk_size]
                    resp = node.Service_0x36_TransferData(counter=sequence_counter, record=chunk_data)
                    if resp is None or resp.data[0] != 0x76:
                        TestLog("FAIL", "", "数据传输(36)失败")
                        return

                    # 在第一个36服务后发送干扰
                    if not interference_done and first_36_of_block:
                        TestLog("INFO", "", "在36服务传输过程中发送22服务诊断请求(22 F0 89)")
                        resp_22 = node.Service_0x22_ReadDataByIdentifier(id=0xF089)
                        if resp_22 is not None:
                            TestLog("INFO", "", f"DUT响应了22服务请求: {resp_22.data.hex(' ').upper()}")
                        else:
                            TestLog("INFO", "", "DUT忽略22服务请求，不回复响应报文(符合预期)")
                        interference_done = True
                        first_36_of_block = False

                    offset += chunk_size
                    sequence_counter = (sequence_counter + 1) % 256

                # 发送37服务
                resp = node.Service_0x37_RequestTransferExit()
                if resp is None or resp.data[0] != 0x77:
                    TestLog("FAIL", "", "传输退出(37)失败")
                    return

            TestLog("INFO", "Step3", "继续执行后续的刷写流程")
            # 检查完整性
            if not check_memory(node, item.path_xml, item.path_hexS19):
                TestLog("FAIL", "", "APP文件安全签名验证失败")
                return
            flash_success = True

        if flash_success:
            # 后编程阶段
            status, msg = phase_pro_programming(node)
            if status:
                TestLog("PASS", "", "DUT可以成功的通过BootLoader软件将应用程序下载到DUT中")
            else:
                TestLog("FAIL", "", "后编程阶段失败")
        else:
            TestLog("FAIL", "", "刷写流程失败")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG2_TC6_SC3_DiagnosticInterferenceTest():
    """
        数据传输中诊断指令干扰测试-SubCase3
    """
    case_name = "数据传输中诊断指令干扰测试-36服务传输完成后干扰"
    flash_config = get_flash_config()

    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        TestLog("INFO", "Step2", "通过测试设备执行刷写流程，在36服务数据传输完成之后，发送22服务诊断请求(22 F0 89)")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", "预编程阶段失败")
            return

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        # 下载driver
        if not download_driver(node, flash_files):
            TestLog("FAIL", "", "下载DRIVER失败")
            return

        # 下载APP（包含擦除、传输）
        flash_success = False
        for item in flash_files:
            if not FlashConfig.check_app(item):
                continue
            if not erase_memory(node, item.path_hexS19):
                TestLog("FAIL", "", "APP内存擦除失败")
                return
            if not download_file(node, item.path_hexS19):
                TestLog("FAIL", "", "APP文件下载失败")
                return

            # 在36服务传输完成后（37服务后）发送22服务诊断请求
            TestLog("INFO", "", "在36服务传输完成后发送22服务诊断请求(22 F0 89)")
            resp_22 = node.Service_0x22_ReadDataByIdentifier(id=0xF089)
            if resp_22 is not None:
                TestLog("INFO", "", f"DUT响应了22服务请求: {resp_22.data.hex(' ').upper()}")
            else:
                TestLog("INFO", "", "DUT忽略22服务请求，不回复响应报文(符合预期)")

            TestLog("INFO", "Step3", "继续执行后续的刷写流程")
            if not check_memory(node, item.path_xml, item.path_hexS19):
                TestLog("FAIL", "", "APP文件安全签名验证失败")
                return
            flash_success = True

        if flash_success:
            # 后编程阶段
            status, msg = phase_pro_programming(node)
            if status:
                TestLog("PASS", "", "DUT可以成功的通过BootLoader软件将应用程序下载到DUT中")
            else:
                TestLog("FAIL", "", "后编程阶段失败")
        else:
            TestLog("FAIL", "", "刷写流程失败")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG2_TC7_SC1_VoltageAbnormalWithinTransferDataTest():
    """
        数据传输中电压异常测试-数据传输时电压过高
    """
    case_name = "数据传输中电压异常测试-数据传输时电压过高"
    flash_config = get_flash_config()

    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在数据传输中控制程控电源电压升高到17V")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return

        phase_programming_stop_within_transfer_data(node, flash_config, "HighVoltage",
                                                    support_partition_ab)
        TestLog("PASS", " ", "高压持续10秒完成")
        tester_present_stop()

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.set_voltage(rVnormal)
        lin_restart_delay(10)

        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG2_TC7_SC2_VoltageAbnormalWithinTransferDataTest():
    """
        数据传输中电压异常测试-数据传输时电压过低
    """
    case_name = "数据传输中电压异常测试-数据传输时电压过低"
    flash_config = get_flash_config()

    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在数据传输中控制程控电源电压降到7V")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return

        phase_programming_stop_within_transfer_data(node, flash_config, "LowVoltage",
                                                    support_partition_ab)
        TestLog("PASS", " ", "低压持续10秒完成")
        tester_present_stop()

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.set_voltage(rVnormal)
        lin_restart_delay(10)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG2_TC8_3EWithinReset():
    """
        复位过程中3E服务干扰测试
    """
    case_name = "复位过程中3E服务干扰测试"
    flash_config = get_flash_config()

    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return

        # 步骤1: 控制程控电源给DUT正常供电，供电电压为12V
        TestLog("INFO", "Step1", "控制程控电源给DUT正常供电，供电电压为12V")
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return
        TestLog("PASS", "Step1", "DUT正常发送应用报文")

        # 步骤2: 执行刷写流程，在复位过程中以100ms周期发送3E 80
        TestLog("INFO", "Step2", "通过测试设备执行刷写流程，在复位请求11 01发送完成之后，以100ms周期发送功能寻址3E 80诊断指令")
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return False

        # 编程阶段
        status, msg = phase_programming(node, flash_config, support_partition_ab)
        if not status:
            TestLog("FAIL", " ", "编程阶段失败")
            return False
        
        # 后编程阶段 - 复位过程中发送3E 80干扰
        status, msg = phase_pro_programming_with_3E_during_reset(node)
        if not status:
            TestLog("FAIL", " ", "后编程阶段失败")
            return False
        return True
    
    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG2_TC9_3EWithinDownload():
    """
        功能寻址 TP 报文对下载影响测
    """
    case_name = "功能寻址 TP 报文对下载影响测"
    flash_config = get_flash_config()

    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG3_TC1_SC1_UnAuthorizedDiagnosticDeviceDownloadTest():
    """
        非授权诊断仪下载测试-跳过安全访问直接请求写入指纹
    """
    case_name = "非授权诊断仪下载测试-跳过安全访问直接请求写入指纹"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return


        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，跳过安全访问，请求写入刷写指纹(响应7F 2E 33)")
        # 预编程阶段
        phase_pre_programming(node)

        TestLog("INFO", "", "进入编程会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return False, f"编程阶段失败: 进入编程会话失败"
        TestLog("INFO", "", "跳过安全访问")
        TestLog("INFO", "", "写入指纹(2E F1 84)")
        if not write_fingerprint(node, [0x7F, 0x2E, 0x33], "否定响应(7F 2E 33)'"): return

        TestLog("INFO", "Step3", f"通过测试设备请求下载FlashDriver(响应7F 34 33)")
        flash_files = get_flash_file("A", flash_config)
        for item in flash_files:
            if not FlashConfig.check_driver(item):
                continue
            TestLog("INFO", "", f"开始刷写: {item.path_hexS19}")
            TestLog("INFO", "", f"DRIVER文件下载: {item.path_hexS19}")
            block_infos, start_addr = parse_hex(item.path_hexS19)
            if start_addr is None:
                TestLog("INFO", "", f"<parse_hex> Failed to find start address.")
                return -1
            for idx, block in enumerate(block_infos):
                start_address = block["address"]
                data = bytearray(block["data"])
                length = len(data)
                resp = node.Service_0x34_RequestDownload(dataformat=0x00, size_len=4, address_len=4,
                                                         size=length, address=start_address)
                if resp.data[:3] != bytes([0x7F, 0x34, 0x33]):
                    TestLog("FAIL", "", f"期望: ECU否定响应(7F 34 33); 实际: {resp.data.hex(' ').upper()}")
                    return
                TestLog("PASS", "", f"期望: ECU否定响应(7F 34 33); 实际: {resp.data.hex(' ').upper()}")
                break

        TestLog("INFO", "Step4", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        ctx.power_ctrl.on()
        lin_restart_delay(10)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG3_TC1_SC2_UnAuthorizedDiagnosticDeviceDownloadTest():
    """
        非授权诊断仪下载测试-发送错误密钥后继续请求下载FlashDriver
    """
    case_name = "非授权诊断仪下载测试-发送错误密钥后继续请求下载FlashDriver"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return


        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，安全访问时测试设备向DUT发送错误的密钥(响应7F 27 35)")
        # 预编程阶段
        phase_pre_programming(node)

        TestLog("INFO", "", "进入编程会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return False, f"编程阶段失败: 进入编程会话失败"

        TestLog("INFO", "", "安全访问发送错误密钥")
        # 27 11
        level = 0x11
        respMsg = node.Service_0x27_SecurityAccess(level)
        if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
        status, msg = check_resp(respMsg, [0x67, level], f"肯定响应(67 {level:02X})")
        if not status:
            TestLog("FAIL", "", f"27 {level:02X}失败: {msg}")
            return False

        seed = list(resp[2:])
        TestLog("INFO", "", f"获取到的seed: {[hex(s) for s in seed]}")
        key = Seed2Key(P.ECUInfo.dllPath_2711, seed)
        TestLog("INFO", "", f"计算得到的密钥: {[hex(k) for k in key]}")
        key[0] = (key[0] + 1) % 0xFF
        TestLog("INFO", "", f"错误的密钥: {[hex(k) for k in key]}")

        # 27 12
        respMsg = node.Service_0x27_SecurityAccess(level + 1, key)
        if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
        status, msg = check_resp(respMsg, [0x7F, 0x27, 0x35], f"ECU响应(7F 27 35)")
        if not status:
            TestLog("FAIL", "", f"期望: ECU响应(7F 27 35); 实际: {resp.hex(' ').upper()}")
            return

        TestLog("INFO", "Step3", f"通过测试设备请求下载FlashDriver(响应7F 34 33)")
        flash_files = get_flash_file("A", flash_config)
        for item in flash_files:
            if not FlashConfig.check_driver(item):
                continue
            TestLog("INFO", "", f"开始刷写: {item.path_hexS19}")
            TestLog("INFO", "", f"DRIVER文件下载: {item.path_hexS19}")
            block_infos, start_addr = parse_hex(item.path_hexS19)
            if start_addr is None:
                TestLog("INFO", "", f"<parse_hex> Failed to find start address.")
                return -1
            for idx, block in enumerate(block_infos):
                start_address = block["address"]
                data = bytearray(block["data"])
                length = len(data)
                resp = node.Service_0x34_RequestDownload(dataformat=0x00, size_len=4, address_len=4,
                                                         size=length, address=start_address)
                if resp.data[:3] != bytes([0x7F, 0x34, 0x33]):
                    TestLog("FAIL", "", f"期望: ECU否定响应(7F 34 33); 实际: {resp.data.hex(' ').upper()}")
                    return
                TestLog("PASS", "", f"期望: ECU否定响应(7F 34 33); 实际: {resp.data.hex(' ').upper()}")
                break

        TestLog("INFO", "Step4", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        ctx.power_ctrl.on()
        lin_restart_delay(10)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG3_TC2_SC1_InvalidAppFileDownloadTest():
    """
        无效应用程序源文件下载测试-请求下载地址无效
    """
    case_name = "无效应用程序源文件下载测试-请求下载地址无效"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在应用程序请求下载步骤发送全FF的错误地址信息")
        # 预编程阶段
        phase_pre_programming(node)

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        # 下载driver
        if not download_driver(node, flash_files):
            TestLog("FAIL", "", "编程阶段失败: 下载DRIVER失败")
            return

        for item in flash_files:
            if not FlashConfig.check_app(item):
                continue
            TestLog("INFO", "", f"开始刷写: {item.path_hexS19}")
            TestLog("INFO", "", f"APP内存擦除: {item.path_hexS19}")
            if not erase_memory(node, item.path_hexS19):
                TestLog("FAIL", "", f"APP内存擦除失败: {item.path_hexS19}")
                return False

            TestLog("INFO", "", f"APP文件下载: {item.path_hexS19}")
            block_infos, start_addr = parse_hex(item.path_hexS19)
            if start_addr is None:
                TestLog("INFO", "", f"<parse_hex> Failed to find start address.")
                return -1
            for idx, block in enumerate(block_infos):
                start_address = 0xFFFFFFFF  # block["address"]
                data = bytearray(block["data"])
                length = len(data)
                resp = node.Service_0x34_RequestDownload(dataformat=0x00, size_len=4, address_len=4,
                                                         size=length, address=start_address)
                if resp.data[:3] != bytes([0x7F, 0x34, 0x31]):
                    TestLog("FAIL", "", f"期望: ECU否定响应(7F 34 31); 实际: {resp.data.hex(' ').upper()}")
                    return
                TestLog("PASS", "", f"期望: ECU否定响应(7F 34 31); 实际: {resp.data.hex(' ').upper()}")
                break

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        ctx.power_ctrl.on()
        lin_restart_delay(10)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG3_TC2_SC2_InvalidAppFileDownloadTest():
    """
        无效应用程序源文件下载测试-源文件内容被更改
    """
    case_name = "无效应用程序源文件下载测试-源文件内容被更改"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return


        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在应用程序请求下载步骤发送全FF的错误地址信息")
        # 预编程阶段
        phase_pre_programming(node)

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        # 下载driver
        if not download_driver(node, flash_files):
            TestLog("FAIL", "", "编程阶段失败: 下载DRIVER失败")
            return

        app_signature_flag = True
        for item in flash_files:
            if not FlashConfig.check_app(item):
                continue
            TestLog("INFO", "", f"开始刷写: {item.path_hexS19}")
            TestLog("INFO", "", f"APP内存擦除: {item.path_hexS19}")
            if not erase_memory(node, item.path_hexS19):
                TestLog("FAIL", "", f"APP内存擦除失败: {item.path_hexS19}")
                return False

            TestLog("INFO", "", f"APP文件下载: {item.path_hexS19}")
            block_infos, start_addr = parse_hex(item.path_hexS19)
            if start_addr is None:
                TestLog("INFO", "", f"<parse_hex> Failed to find start address.")
                return -1
            for idx, block in enumerate(block_infos):
                start_address = block["address"]
                data = bytearray(block["data"])
                length = len(data)
                resp = node.Service_0x34_RequestDownload(dataformat=0x00, size_len=4, address_len=4,
                                                         size=length, address=start_address)
                if not (resp.data[0] == 0x74):
                    TestLog("FAIL", "", f"RequestDownload(34)失败: 非肯定响应{resp.data}")
                    return False
                before = [data[-2], data[-1]]
                data[-2] = (data[-2] + 1) % 0xFF
                data[-1] = (data[-1] + 1) % 0xFF
                after = [data[-2], data[-1]]
                TestLog("INFO", "", f"篡改应用数据的最后两个字节: 原始[{[hex(item) for item in before]}], 篡改后[{[hex(item) for item in after]}]")
                maxNumberOfBlockLength = get_max_nummber_of_blocklength_from_0x74(resp)
                maxNumberOfBlockLength = maxNumberOfBlockLength - 2
                counter = 1
                while True:
                    record = data[:maxNumberOfBlockLength]
                    resp = node.Service_0x36_TransferData(counter, record)
                    if resp is None or resp.data is None:
                        TestLog("FAIL", "", f"TransferData(36)失败: 未收到响应")
                        return False
                    if not (resp.data[0] == 0x76):
                        TestLog("FAIL", "", f"TransferData(36)失败: 非肯定响应{resp.data.hex(' ').upper()}")
                        return False
                    time.sleep(0.001)
                    data = data[maxNumberOfBlockLength:]
                    if len(data) == 0:
                        break
                    counter += 1
                    if counter == 0xFF + 1:
                        counter = 0
                resp = node.Service_0x37_RequestTransferExit()
                if resp is None or resp.data is None:
                    TestLog("FAIL", "", f"RequestTransferExit(37)失败: 未收到响应")
                    return False
                if not (resp.data[0] == 0x77):
                    TestLog("FAIL", "", f"RequestTransferExit(37)失败: 非肯定响应{resp.data.hex(' ').upper()}")
                    return False

            TestLog("INFO", "", f"APP文件安全签名验证: {item.path_xml}")
            status = check_memory(node, item.path_xml, item.path_hexS19)
            if not status:
                TestLog("PASS", "", f"期望:无法通过安全签名检查; 实际: APP文件安全签名验证失败: {item.path_xml}")
                app_signature_flag = False
                break
        if app_signature_flag is True:
            TestLog("INFO", "", "通过了安全签名检查，开始检查编程依赖(31 01 FF 01)")
            status = check_programming_dependencies(node)
            if status:
                TestLog("FAIL", "", "期望: 无法通过依赖性检验; 实际: 通过了依赖性检验")
                return
            else:
                TestLog("PASS", "", "期望: 无法通过依赖性检验; 实际: 未通过依赖性检验")

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        ctx.power_ctrl.on()
        lin_restart_delay(10)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG3_TC3_SC1_InvalidSignatureCheckTest():
    """
        错误安全签名值检查测试-错误的Driver安全签名
    """
    case_name = "错误安全签名值检查测试-错误的Driver安全签名"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return
        

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，完成FlashDriver传输后，发送31 01 DD 02+错误的安全签名值")
        # 预编程阶段
        phase_pre_programming(node)

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        # 下载driver
        for item in flash_files:
            if not FlashConfig.check_driver(item):
                continue
            TestLog("INFO", "", f"开始刷写: {item.path_hexS19}")
            TestLog("INFO", "", f"DRIVER文件下载: {item.path_hexS19}")
            if not download_file(node, item.path_hexS19):
                TestLog("FAIL", "", f"DRIVER文件下载失败: {item.path_hexS19}")
                return False

            TestLog("INFO", "", f"DRIVER文件安全签名验证: {item.path_xml}")
            file_list = parse_signature_xml(item.path_xml)
            TestLog("INFO", "", f"{file_list}")
            sig_data = b""
            target_name = os.path.basename(item.path_hexS19)
            for sig_item in file_list:
                if sig_item["name"] == target_name:
                    sig_data = sig_item["sigVal"]
                    break
            if len(sig_data) == 0:
                TestLog("INFO", "", f"未找到<{target_name}>的签名")
                return False
            TestLog("INFO", "", f"原始签名数据: {sig_data.hex()}")
            err_sig_data = sig_data[:-1] + bytes([(sig_data[-1] + 1)%0xFF])
            TestLog("INFO", "", f"篡改的签名数据: {err_sig_data.hex()}")
            resp = node.Service_0x31_RoutineControl(0x01, 0xDD02, record=bytes(err_sig_data), timeout=10)
            status, msg = check_resp(resp, [0x71, 0x01, 0xDD, 0x02], "肯定响应(71 01 DD 02)")
            if not status:
                TestLog("FAIL", "", f"期望: 肯定响应(71 01 DD 02); 实际: {resp.data.hex(' ').upper()}")
                return
            if resp.data[4] not in [0x01, 0x02]:
                TestLog("FAIL", "", f"期望: 肯定响应(71 01 DD 02 01/02); 实际: {resp.data.hex(' ').upper()}")
                return
            TestLog("PASS", "", f"期望: 肯定响应(71 01 DD 02 01/02); 实际: {resp.data.hex(' ').upper()}")

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        ctx.power_ctrl.on()
        lin_restart_delay(10)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG3_TC3_SC2_InvalidSignatureCheckTest():
    """
        错误安全签名值检查测试-错误的APP安全签名
    """
    case_name = "错误安全签名值检查测试-错误的APP安全签名"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return
        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，完成FlashDriver传输后，发送31 01 DD 02+错误的安全签名值")
        # 预编程阶段
        phase_pre_programming(node)

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        # 下载driver
        if not download_driver(node, flash_files):
            return False, "编程阶段失败: 下载DRIVER失败"

        # 下载app
        fhasl_flag = False
        for item in flash_files:
            if not FlashConfig.check_app(item):
                continue
            TestLog("INFO", "", f"开始刷写: {item.path_hexS19}")
            TestLog("INFO", "", f"APP内存擦除: {item.path_hexS19}")
            if not erase_memory(node, item.path_hexS19):
                TestLog("FAIL", "", f"APP内存擦除失败: {item.path_hexS19}")
                return False

            TestLog("INFO", "", f"APP文件下载: {item.path_hexS19}")
            if not download_file(node, item.path_hexS19):
                TestLog("FAIL", "", f"APP文件下载失败: {item.path_hexS19}")
                return False

            TestLog("INFO", "", f"APP文件安全签名验证: {item.path_xml}")
            file_list = parse_signature_xml(item.path_xml)
            TestLog("INFO", "", f"{file_list}")
            sig_data = b""
            target_name = os.path.basename(item.path_hexS19)
            for sig_item in file_list:
                if sig_item["name"] == target_name:
                    sig_data = sig_item["sigVal"]
                    break
            if len(sig_data) == 0:
                TestLog("INFO", "", f"未找到<{target_name}>的签名")
                return False
            TestLog("INFO", "", f"原始签名数据: {sig_data.hex()}")
            err_sig_data = sig_data[:-1] + bytes([(sig_data[-1] + 1)%0xFF])
            TestLog("INFO", "", f"篡改的签名数据: {err_sig_data.hex()}")
            resp = node.Service_0x31_RoutineControl(0x01, 0xDD02, record=bytes(err_sig_data), timeout=10)
            status, msg = check_resp(resp, [0x71, 0x01, 0xDD, 0x02], "肯定响应(71 01 DD 02)")
            if not status:
                TestLog("FAIL", "", f"期望: 肯定响应(71 01 DD 02); 实际: {resp.data.hex(' ').upper()}")
                return
            if resp.data[4] not in [0x01, 0x02]:
                TestLog("FAIL", "", f"期望: 肯定响应(71 01 DD 02 01/02); 实际: {resp.data.hex(' ').upper()}")
                return
            TestLog("PASS", "", f"期望: 肯定响应(71 01 DD 02 01/02); 实际: {resp.data.hex(' ').upper()}")

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        ctx.power_ctrl.on()
        lin_restart_delay(10)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG3_TC4_SC1_ErrorSignatureLengthCheckTest():
    """
        安全签名长度错误测试-多2字节的Driver安全签名
    """
    case_name = "安全签名长度错误测试-多2字节的Driver安全签名"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return
        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，完成FlashDriver传输后，发送31 01 DD 02+错误的安全签名值")
        # 预编程阶段
        phase_pre_programming(node)

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        # 下载driver
        for item in flash_files:
            if not FlashConfig.check_driver(item):
                continue
            TestLog("INFO", "", f"开始刷写: {item.path_hexS19}")
            TestLog("INFO", "", f"DRIVER文件下载: {item.path_hexS19}")
            if not download_file(node, item.path_hexS19):
                TestLog("FAIL", "", f"DRIVER文件下载失败: {item.path_hexS19}")
                return False

            TestLog("INFO", "", f"DRIVER文件安全签名验证: {item.path_xml}")
            file_list = parse_signature_xml(item.path_xml)
            TestLog("INFO", "", f"{file_list}")
            sig_data = b""
            target_name = os.path.basename(item.path_hexS19)
            for sig_item in file_list:
                if sig_item["name"] == target_name:
                    sig_data = sig_item["sigVal"]
                    break
            if len(sig_data) == 0:
                TestLog("INFO", "", f"未找到<{target_name}>的签名")
                return False
            TestLog("INFO", "", f"原始签名数据: {sig_data.hex()}")
            err_sig_data = sig_data + bytes([0x01, 0x01])
            TestLog("INFO", "", f"篡改的签名数据: {err_sig_data.hex()}")
            resp = node.Service_0x31_RoutineControl(0x01, 0xDD02, record=bytes(err_sig_data), timeout=10)
            status, msg = check_resp(resp, [0x7F, 0x31, 0x13], "否定响应(7F 31 13)")
            if not status:
                TestLog("FAIL", "", f"期望: 否定响应(7F 31 13); 实际: {resp.data.hex(' ').upper()}")
                return
            TestLog("PASS", "", f"期望: 否定响应(7F 31 13); 实际: {resp.data.hex(' ').upper()}")

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        lin_restart_delay(10)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG3_TC4_SC2_ErrorSignatureLengthCheckTest():
    """
        安全签名长度错误测试-多2字节的App安全签名
    """
    case_name = "安全签名长度错误测试-多2字节的App安全签名"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return
        

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，完成FlashDriver传输后，发送31 01 DD 02+错误的安全签名值")
        # 预编程阶段
        phase_pre_programming(node)

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        # 下载driver
        if not download_driver(node, flash_files):
            return False, "编程阶段失败: 下载DRIVER失败"

        # 下载app
        fhasl_flag = False
        for item in flash_files:
            if not FlashConfig.check_app(item):
                continue
            TestLog("INFO", "", f"开始刷写: {item.path_hexS19}")
            TestLog("INFO", "", f"APP内存擦除: {item.path_hexS19}")
            if not erase_memory(node, item.path_hexS19):
                TestLog("FAIL", "", f"APP内存擦除失败: {item.path_hexS19}")
                return False

            TestLog("INFO", "", f"APP文件下载: {item.path_hexS19}")
            if not download_file(node, item.path_hexS19):
                TestLog("FAIL", "", f"APP文件下载失败: {item.path_hexS19}")
                return False

            TestLog("INFO", "", f"APP文件安全签名验证: {item.path_xml}")
            file_list = parse_signature_xml(item.path_xml)
            TestLog("INFO", "", f"{file_list}")
            sig_data = b""
            target_name = os.path.basename(item.path_hexS19)
            for sig_item in file_list:
                if sig_item["name"] == target_name:
                    sig_data = sig_item["sigVal"]
                    break
            if len(sig_data) == 0:
                TestLog("INFO", "", f"未找到<{target_name}>的签名")
                return False
            TestLog("INFO", "", f"原始签名数据: {sig_data.hex()}")
            err_sig_data = sig_data + bytes([0x01, 0x01])
            TestLog("INFO", "", f"篡改的签名数据: {err_sig_data.hex()}")
            resp = node.Service_0x31_RoutineControl(0x01, 0xDD02, record=bytes(err_sig_data), timeout=10)
            status, msg = check_resp(resp, [0x7F, 0x31, 0x13], "否定响应(7F 31 13)")
            if not status:
                TestLog("FAIL", "", f"期望: 否定响应(7F 31 13); 实际: {resp.data.hex(' ').upper()}")
                return
            TestLog("PASS", "", f"期望: 否定响应(7F 31 13); 实际: {resp.data.hex(' ').upper()}")

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        lin_restart_delay(10)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG3_TC4_SC3_ErrorSignatureLengthCheckTest():
    """
        安全签名长度错误测试-少2字节的App安全签名
    """
    case_name = "安全签名长度错误测试-少2字节的App安全签名"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return
        
        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，完成FlashDriver传输后，发送31 01 DD 02+错误的安全签名值")
        # 预编程阶段
        phase_pre_programming(node)

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        # 下载driver
        if not download_driver(node, flash_files):
            return False, "编程阶段失败: 下载DRIVER失败"

        # 下载app
        fhasl_flag = False
        for item in flash_files:
            if not FlashConfig.check_app(item):
                continue
            TestLog("INFO", "", f"开始刷写: {item.path_hexS19}")
            TestLog("INFO", "", f"APP内存擦除: {item.path_hexS19}")
            if not erase_memory(node, item.path_hexS19):
                TestLog("FAIL", "", f"APP内存擦除失败: {item.path_hexS19}")
                return False

            TestLog("INFO", "", f"APP文件下载: {item.path_hexS19}")
            if not download_file(node, item.path_hexS19):
                TestLog("FAIL", "", f"APP文件下载失败: {item.path_hexS19}")
                return False

            TestLog("INFO", "", f"APP文件安全签名验证: {item.path_xml}")
            file_list = parse_signature_xml(item.path_xml)
            TestLog("INFO", "", f"{file_list}")
            sig_data = b""
            target_name = os.path.basename(item.path_hexS19)
            for sig_item in file_list:
                if sig_item["name"] == target_name:
                    sig_data = sig_item["sigVal"]
                    break
            if len(sig_data) == 0:
                TestLog("INFO", "", f"未找到<{target_name}>的签名")
                return False
            TestLog("INFO", "", f"原始签名数据: {sig_data.hex()}")
            err_sig_data = sig_data[:-2]
            TestLog("INFO", "", f"篡改的签名数据: {err_sig_data.hex()}")
            resp = node.Service_0x31_RoutineControl(0x01, 0xDD02, record=bytes(err_sig_data), timeout=10)
            status, msg = check_resp(resp, [0x7F, 0x31, 0x13], "否定响应(7F 31 13)")
            if not status:
                TestLog("FAIL", "", f"期望: 否定响应(7F 31 13); 实际: {resp.data.hex(' ').upper()}")
                return
            TestLog("PASS", "", f"期望: 否定响应(7F 31 13); 实际: {resp.data.hex(' ').upper()}")

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        lin_restart_delay(10)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()
        
def test_TG3_TC5_ErrorEraceRangeofAddreess():
    """
       擦除错误的地址范围测试
    """
    case_name = "擦除错误的地址范围测试"
    flash_config = get_flash_config()

    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return
        

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，完成Flashdriver传输后，在擦除内存步骤发送错误的擦除地址范围")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", f"预编程阶段失败: {msg}")
            return

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        # 下载driver
        if not download_driver(node, flash_files):
            TestLog("FAIL", "", "编程阶段失败: 下载DRIVER失败")
            return

        # 构造错误的擦除内存请求：31 01 FF 00 44 + 引导加载程序起始地址 + 引导加载程序大小
        TestLog("INFO", "", "发送错误的擦除地址范围（引导加载程序地址）")
        wrong_start_address = 0x00000000
        wrong_size = 0x00010000
        record = b''
        record += bytearray([0x44])
        for i in range(4):
            record += bytearray([(wrong_start_address >> (8 * (3 - i))) & 0xFF])
        for i in range(4):
            record += bytearray([(wrong_size >> (8 * (3 - i))) & 0xFF])

        respMsg = node.Service_0x31_RoutineControl(0x01, 0xFF00, record=record)
        if respMsg is None:
            TestLog("FAIL", "", "未收到响应")
            return
        resp = respMsg.data
        if resp is None:
            TestLog("FAIL", "", "响应数据为空")
            return

        # 期望收到NRC 0x31
        if resp[0] == 0x7F and resp[1] == 0x31 and resp[2] == 0x31:
            TestLog("PASS", "", f"期望: ECU否定响应(7F 31 31); 实际: {resp.hex(' ').upper()}")
        else:
            TestLog("FAIL", "", f"期望: ECU否定响应(7F 31 31); 实际: {resp.hex(' ').upper()}")
            return

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()

        lin_restart_delay(rTstable)


        if not main_flash(node, flash_config, support_partition_ab):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG4_TC1_SkipPreconditionCheckTest():
    """
        跳过编程预条件检查测试
    """
    case_name = "跳过编程预条件检查测试"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，跳过编程与条件检查，直接请求进入编程会话")
        # 预编程阶段
        phase_pre_programming_without_precondition_check(node)
        if not service_10_check(node, 0x02, expect_data=[0x7F, 0x10, 0x22], expect_str="否定响应(7F 10 22)"):
            return

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        lin_restart_delay(10)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG4_TC2_SC1_SkipFlashDriverDownloadTest():
    """
        跳过FlashDriver下载测试
    """
    case_name = "跳过FlashDriver下载测试"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return
        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，跳过FlashDriver下载步骤，直接执行擦除内存")
        # 预编程阶段
        phase_pre_programming(node)

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)

        flash_files = get_flash_file(part_msg, flash_config)

        TestLog("INFO", "", "跳过FlashDriver步骤，直接执行擦除内存")
        for item in flash_files:
            if not FlashConfig.check_app(item):
                continue
            TestLog("INFO", "", f"开始刷写: {item.path_hexS19}")
            TestLog("INFO", "", f"APP内存擦除: {item.path_hexS19}")
            block_infos, start_addr = parse_hex(item.path_hexS19)
            if start_addr is None:
                TestLog("FAIL", "", "<parse_hex> Failed to find start address.")
                return False
            for idx, block in enumerate(block_infos):
                start_address = block["address"]
                length = len(block["data"])
                record = b''
                record += bytearray([0x44])
                for i in range(4):
                    record += bytearray([(start_address >> (8 * (3 - i))) & 0xFF])
                for i in range(4):
                    record += bytearray([(length >> (8 * (3 - i))) & 0xFF])
                resp = node.Service_0x31_RoutineControl(0x01, 0xFF00, record=record)
                if resp is None or resp.data is None:
                    TestLog("FAIL", "", f"期望: ECU负响应(7F 31 72/22); 实际: 未收到响应")
                    return
                if not (resp.data[0: 3] == bytearray([0x7F, 0x31, 0x72]) or resp.data[0: 3] == bytearray([0x7F, 0x31, 0x22])):
                    TestLog("FAIL", "", f"期望: ECU负响应(7F 31 72/22); 实际: {resp.data.hex(' ').upper()}")
                    return
                else:
                    TestLog("PASS", "", f"期望: ECU负响应(7F 31 72/22); 实际: {resp.data.hex(' ').upper()}")
                    break
            break

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        lin_restart_delay(10)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG4_TC3_SkipEraseMemoryTest():
    """
        跳过内存擦除测试
    """
    case_name = "跳过内存擦除测试"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return
        
        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在进行APP传输过程，跳过擦除内存步骤，直接执行请求下载步骤(否定响应7F 34 70/22)")
        # 预编程阶段
        phase_pre_programming(node)

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            return False, part_msg

        flash_files = get_flash_file(part_msg, flash_config)

        # 下载driver
        if not download_driver(node, flash_files):
            return False, "编程阶段失败: 下载DRIVER失败"

        flash_file = None
        for item in flash_files:
            if FlashConfig.check_app(item):
                flash_file = item
                break

        TestLog("INFO", "", f"开始刷写: {flash_file.path_hexS19}")
        TestLog("INFO", "", f"跳过APP内存擦除: {flash_file.path_hexS19}")

        TestLog("INFO", "", f"APP文件下载: {flash_file.path_hexS19}")
        TestLog("INFO", "", f"hex_path={flash_file.path_hexS19}")
        block_infos, start_addr = parse_hex(flash_file.path_hexS19)
        if start_addr is None:
            TestLog("INFO", "", f"<parse_hex> Failed to find start address.")
            return -1
        for idx, block in enumerate(block_infos):
            start_address = block["address"]
            data = bytearray(block["data"])
            length = len(data)
            resp = node.Service_0x34_RequestDownload(dataformat=0x00,
                                                     size_len=4,
                                                     address_len=4,
                                                     size=length,
                                                     address=start_address)
            if resp is None or resp.data is None:
                TestLog("FAIL", "", f"期望: ECU否定响应(7F 34 70/22); 实际: 未收到响应")
                return
            if not (resp.data[0] == 0x7F and resp.data[1] == 0x34 and resp.data[2] in [0x70, 0x22]):
                TestLog("FAIL", "", f"期望: ECU否定响应(7F 34 70/22); 实际: {resp.data.hex(' ').upper()}")
                return
            else:
                TestLog("PASS", "", f"期望: ECU否定响应(7F 34 70/22); 实际: {resp.data.hex(' ').upper()}")
                break

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        ctx.power_ctrl.on()
        lin_restart_delay(10)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG4_TC4_SC1_SkipSignatureCheckTest():
    """
        跳过安全签名检查测试-FlashDriver不做安全签名检查
    """
    case_name = "跳过安全签名检查测试-FlashDriver不做安全签名检查"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，完成FlashDriver刷写后，跳过安全签名检查，直接执行内存擦除(否定响应7F 31 70/22)")
        # 预编程阶段
        phase_pre_programming(node)

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            return False, part_msg

        flash_files = get_flash_file(part_msg, flash_config)

        # 下载driver，
        download_driver_without_signature(node, flash_files)

        flash_file = None
        for item in flash_files:
            if FlashConfig.check_app(item):
                flash_file = item
                break

        TestLog("INFO", "", f"开始刷写: {flash_file.path_hexS19}")
        TestLog("INFO", "", f"APP内存擦除: {flash_file.path_hexS19}")
        block_infos, start_addr = parse_hex(flash_file.path_hexS19)
        if start_addr is None:
            TestLog("FAIL", "", "<parse_hex> Failed to find start address.")
            return False
        for idx, block in enumerate(block_infos):
            start_address = block["address"]
            length = len(block["data"])
            record = b''
            record += bytearray([0x44])
            for i in range(4):
                record += bytearray([(start_address >> (8 * (3 - i))) & 0xFF])
            for i in range(4):
                record += bytearray([(length >> (8 * (3 - i))) & 0xFF])
            resp = node.Service_0x31_RoutineControl(0x01, 0xFF00, record=record)
            if resp is None or resp.data is None:
                TestLog("FAIL", "", f"期望: ECU否定响应(7F 31 72/22); 实际: 未收到响应")
                return
            if not (resp.data[0] == 0x7F and resp.data[1] == 0x31 and resp.data[2] in [0x72, 0x22]):
                TestLog("FAIL", "", f"期望: ECU否定响应(7F 31 72/22); 实际: {resp.data.hex(' ').upper()}")
                return
            else:
                TestLog("PASS", "", f"期望: ECU否定响应(7F 31 72/22); 实际: {resp.data.hex(' ').upper()}")
                break

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        ctx.power_ctrl.on()
        lin_restart_delay(10)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG4_TC4_SC2_SkipSignatureCheckTest():
    """
        跳过安全签名检查测试-APP不做安全签名检查
    """
    case_name = "跳过安全签名检查测试-APP不做安全签名检查"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return
        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，完成FlashDriver刷写后，跳过安全签名检查，直接执行内存擦除(否定响应7F 31 70/22)")
        # 预编程阶段
        phase_pre_programming(node)

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            return False, part_msg

        flash_files = get_flash_file(part_msg, flash_config)

        # 下载driver，
        download_driver(node, flash_files)

        # 下载app，不做安全签名检查
        download_app_without_signature(node, flash_files)

        # 执行兼容性检查
        resp = node.Service_0x31_RoutineControl(0x01, 0xFF01)
        if not (resp.data[0] == 0x7F and resp.data[1] == 0x31 and resp.data[2] in [0x72, 0x22]):
            TestLog("FAIL", "", f"期望: ECU否定响应(7F 31 72/22); 实际: {resp.data.hex(' ').upper()}")
            return
        else:
            TestLog("PASS", "", f"期望: ECU否定响应(7F 31 72/22); 实际: {resp.data.hex(' ').upper()}")

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        ctx.power_ctrl.on()
        lin_restart_delay(10)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG4_TC5_SC1_DownloadDataTransferErrorTest():
    """
        下载数据传输错误测试-块长度测试
    """
    case_name = "下载数据传输错误测试-块长度测试"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，数据传输过程中，控制数据传输数据块长度比请求下载肯定响应中DUT期望的数据块长度长2byte")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", "预编程阶段失败")
            return

        # 编程阶段
        status, resp = phase_programming_stop_within_transfer_data_more_2_bytes(node, flash_config, support_partition_ab)
        if resp is None:
            TestLog("FAIL", "", f"期望: ECU否定响应(7F 36 31/13); 实际: 未收到有效响应")
            return
        if not (resp[0] == 0x7F and resp[1] == 0x36 and resp[2] in [0x31, 0x13]):
            TestLog("FAIL", "", f"期望: ECU否定响应(7F 36 31/13); 实际: {resp.hex(' ').upper()}")
            return
        else:
            TestLog("PASS", "", f"期望: ECU否定响应(7F 36 31/13); 实际: {resp.hex(' ').upper()}")

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        ctx.power_ctrl.on()
        lin_restart_delay(10)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG4_TC6_SkipTransferDataTest():
    """
        跳过数据传输
    """
    case_name = "跳过数据传输"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        TestLog("INFO", "Step2",
                f"通过测试设备执行刷写流程，下载过程中跳过应用程序数据传输步骤，直接执行数据传输退出请求")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", "预编程阶段失败")
            return

        # 编程阶段
        status, resp = phase_programming_stop_without_transfer_data(node, flash_config, support_partition_ab)
        if not (resp[0] == 0x7F and resp[1] == 0x37 and resp[2] == 0x24):
            TestLog("FAIL", " ", f"期望: ECU否定响应(7F 37 24); 实际: {resp.hex(' ').upper()}")
            return
        else:
            TestLog("PASS", " ", f"期望: ECU否定响应(7F 37 24); 实际: {resp.hex(' ').upper()}")

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        ctx.power_ctrl.on()
        lin_restart_delay(10)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG4_TC7_SkipDependenciesTest():
    """
        跳过依赖性检查测试
    """
    case_name = "跳过依赖性检查测试"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return


        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，跳过依赖性检查，直接执行 ECU复位")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", "预编程阶段失败")
            return

        # 编程阶段
        phase_programming_skip_dependencies(node, flash_config, support_partition_ab)

        # 后编程阶段
        #phase_pro_programming(node)
        TestLog("INFO", "ECU复位", "11 01")
        resp = node.Service_0x11_ECUReset(0x01)
        status, msg = check_resp(resp, [0x51, 0x01], "肯定响应(51 01)")

        rT_wait = P.LINInfo.TdefaultWait_s
        sch = create_lin_sch()
        sch.start()
        msgs, direction = monitor_lin_communication(rT_wait)
        sch.stop()
        TestLog("INFO", "Step2", "检查是否无应用报文发送")
        if len(msgs) >= 0:
            for id, all_v in msgs.items():
                if all_v[0]["direction"] == "Rx":
                    for msg in all_v:
                        if msg["dlc"] != 0:
                            TestLog("FAIL", case_name, "应用报文未停止发送，期望无应用报文发送")
                            return
        TestLog("PASS", "Step2", "无应用报文发送，符合预期")


        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        ctx.power_ctrl.on()
        lin_restart_delay(10)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG5_TC1_TryFlashCounterTest():
    """
        尝试刷写计数器测试
    """
    case_name = "尝试刷写计数器测试"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return


        TestLog("INFO", "Step2", f"读取尝试刷写计数器的值(F0F1)，并记录计数器的值为count1")
        status, resp = service_22_check(node, 0xF0F1, expect_data=[0x62, 0xF0, 0xF1], expect_str="肯定响应(62 F0 F1)")
        if not status: return
        count1 = int.from_bytes(resp.data[3:], byteorder='big')
        TestLog("INFO", "", f"count1={count1}")

        TestLog("INFO", "Step3", f"通过测试设备执行刷写流程，写入指纹后，等待2s")
        # 预编程阶段
        phase_pre_programming(node)
        steps_before_download(node, support_partition_ab)

        TestLog("INFO", "Step4", f"读取尝试刷写计数器的值(F0F1)，并记录计数器的值为count2")
        status, resp = service_22_check(node, 0xF0F1, expect_data=[0x62, 0xF0, 0xF1], expect_str="肯定响应(62 F0 F1)")
        if not status: return
        count2 = int.from_bytes(resp.data[3:], byteorder='big')
        TestLog("INFO", "", f"count2={count2}")

        if count2 - count1 == 1:
            TestLog("PASS", "", f"期望: count2-count1=1; 实际: count2-count1={count2-count1}")
        else:
            TestLog("FAIL", "", f"期望: count2-count1=1; 实际: count2-count1={count2 - count1}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_TG5_TC2_SuccessFlashCounterTest():
    """
        刷写成功计数器测试
    """
    case_name = "刷写成功计数器测试"
    flash_config = get_flash_config()
    try:
        rVnormal = P.LINInfo.Vnormal  # 电源正常电压
        rTstable = P.LINInfo.TdefaultWait_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        node = get_lin_node()
        if node is None:
            TestLog("FAIL", case_name, "获取LIN节点失败")
            return
        ret = lin_node_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", case_name, "LIN电源设置或通信检查失败")
            return

        TestLog("INFO", "Step2", f"读取刷写成功计数器的值(F0F3)，并记录计数器的值为count1")
        status, resp = service_22_check(node, 0xF0F3, expect_data=[0x62, 0xF0, 0xF3], expect_str="肯定响应(62 F0 F3)")
        if not status: return
        count1 = int.from_bytes(resp.data[3:], byteorder='big')
        TestLog("INFO", "", f"count1={count1}")

        TestLog("INFO", "Step3", f"通过测试设备执行刷写流程，执行完例程控制服务(31 01 FF 01检测应用程序的完整性和依赖性)后，等待1s")
        # 预编程阶段
        phase_pre_programming(node)
        phase_programming(node, flash_config, support_partition_ab)
        time.sleep(1)

        TestLog("INFO", "Step4", f"读取刷写成功计数器的值(F0F3)，并记录计数器的值为count2")
        status, resp = service_22_check(node, 0xF0F3, expect_data=[0x62, 0xF0, 0xF3], expect_str="肯定响应(62 F0 F3)")
        if not status: return
        count2 = int.from_bytes(resp.data[3:], byteorder='big')
        TestLog("INFO", "", f"count2={count2}")

        if count2 - count1 == 1:
            TestLog("PASS", "", f"期望: count2-count1=1; 实际: count2-count1={count2-count1}")
        else:
            TestLog("FAIL", "", f"期望: count2-count1=1; 实际: count2-count1={count2 - count1}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def get_all_test_cases():
    """获取测试用例"""
    current_module = inspect.getmodule(inspect.currentframe())

    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj

    return test_cases
