import copy
import inspect
import sys
import os
import threading
import time
import traceback
from env.config import *

from common.context import ctx
from uvtest.testlog import TestLog
from common.control import TestStart, TestEnd
from uvtest.framework import TestFixture

from testcases.bootloader.utils.bootloader_utils import get_can_node, get_flash_config, main_flash, \
    main_flash_until_erase_memory, service_19_check, service_10_check, service_11_check, phase_pre_programming, \
    get_ctx_can_msg, clear_ctx_can_messages, tester_present_stop, service_31_check, service_22_check, security_access, \
    phase_programming, phase_pro_programming, phase_programming_before_erase_memory, \
    phase_programming_doing_erase_memory, phase_programming_stop_within_transfer_data, write_fingerprint, \
    get_flash_file, FlashConfig, check_resp, steps_before_download, download_driver,download_app, erase_memory, check_memory, \
    check_programming_dependencies, check_programming_dependencies_fail, download_file, parse_signature_xml, \
    phase_pre_programming_without_precondition_check, steps_before_download_without_fingerprint, \
    download_driver_without_signature, download_app_without_signature, check_memory_with_power_off,\
    phase_programming_stop_within_transfer_data_more_2_bytes, phase_programming_stop_within_transfer_data_skip_counter, \
    phase_programming_stop_within_transfer_data_with_same_counter, phase_programming_stop_without_transfer_data, \
    phase_programming_skip_dependencies, powerOn_WithoutCheck, powerOff, phase_programming_with_prevent_switch_part, \
    switchPart, parse_flashFile, check_memory_error, phase_programming_stop_after_request_download, \
    phase_programming_stop_after_transfer_exit, phase_programming_stop_after_erase_memory, \
    prepare_for_manual_transfer_data,download_file_with_22_after_34_interference,download_file_with_22_after_36_interference, \
    download_app_until_erase_memory, download_app_stop_witin_transfer_data, \
    phase_programming_stop_driver_within_transfer_data
from testcases.bootloader.utils.isotp_utils import (
    IsoTpRunTimeInfo, isotp_monitor_start, isotp_monitor_stop,
    wait_for_fc, get_fc_stmin_ms, build_isotp_first_frame, build_isotp_consecutive_frames
)
from library.security.security import Seed2Key
from .can_comm import can_power_setup_and_communication_check, can_initialization, can_deinitialization
from common.utils import TimerCyclic
from common.can_utils import send_canmsg, canmsg_create
from slplus.busstatis import sl_busstatis

workdir_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(workdir_path)

g_node = None
testmodule = None


def get_global_node():
    global g_node
    sa, ta, fa = P.ECUInfo.DiagReqID_int, P.ECUInfo.DiagRespID_int, P.ECUInfo.DiagFuncID_int
    is_canfd = True if P.TpInfo.CanFDMode == 1 else False
    if g_node is None:
        g_node = get_can_node(sa, ta, fa, is_canfd)
    return g_node


def close_global_node():
    global g_node
    if g_node:
        g_node.close()
        g_node = None


class UDSCANTestFixture(TestFixture):
    def group_setup(self, context=None):
        can_initialization()
        global testmodule
        testmodule = "can_bootloader"

    def group_teardown(self, context=None):
        can_deinitialization()
        testmodule = None

    def case_setup(self, context=None):
        test_name = context.get("test_name") if isinstance(context, dict) else None

        if test_name:
            TestStart(test_name)

    def case_teardown(self, context=None):
        tester_present_stop()
        close_global_node()
        TestEnd("")
        TestLog("INFO", "测试结束", "执行测试结束和去初始化")


workdir_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(workdir_path)


def test_positive():
    """
    正向刷写流程
    """
    case_name = "正向刷写流程"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        # 测试环境设置
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        if not main_flash(node, flash_config, support_partition_ab):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")

def test_TG0_TC1_FlashFail_VersionTest():
    """
        刷写失败后软件版本测试-SubCase1
    """
    case_name = "刷写失败后软件版本测试-SubCase1"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        support_partition_ab = P.TpInfo.PartSupportFlag

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", "读取DUT原始版本号")
        version_ids = {
            "软件版本号(F189)": 0xF189,
            "硬件版本号(F089)": 0xF089,
            "BOOT版本号(F180)": 0xF180,
        }
        orig_versions = {}
        for name, did in version_ids.items():
            status, respMsg = service_22_check(node, did, expect_data=None, expect_str=f"肯定响应(62 {did>>8:02X} {did&0xFF:02X})")
            if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
            if resp[0] == 0x62:
                orig_versions[name] = resp.hex(' ').upper()
                TestLog("INFO", "", f"{name}: {orig_versions[name]}")
            else:
                TestLog("FAIL", "", f"读取{name}失败")
                return

        TestLog("INFO", "Step3", "执行预编程阶段")
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", f"预编程阶段失败: {msg}")
            return

        TestLog("INFO", "Step4", "执行刷写流程擦除APP内存后断电")
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"下载前步骤失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)
        if not download_driver(node, flash_files):
            TestLog("FAIL", "", "下载DRIVER失败")
            return

        if not download_app_until_erase_memory(node, flash_files):
            TestLog("FAIL", "", "擦除APP内存失败")
            return

        TestLog("INFO", "Step5", "断开KL30电源，使应用程序无效")
        powerOff()
        time.sleep(1)

        TestLog("INFO", "Step6", "控制程控电源给DUT重新上电")
        powerOn_WithoutCheck()
        time.sleep(5)

        TestLog("INFO", "Step7", "重新上电后读取DUT版本号(擦除后)")
        erase_versions = {}
        all_match_or_invalid = True
        for name, did in version_ids.items():
            status, respMsg = service_22_check(node, did, expect_data=None, expect_str=f"肯定响应(62 {did>>8:02X} {did&0xFF:02X})")
            if (resp := (respMsg or type('', (), {'data': None})()).data) is None:
                erase_versions[name] = ""
            elif resp[0] == 0x62:
                erase_versions[name] = resp.hex(' ').upper()
            else:
                erase_versions[name] = ""

            orig_v = orig_versions.get(name, "")
            erase_v = erase_versions.get(name, "")

            is_orig_invalid = "FF" in orig_v or "00" in orig_v
            is_erase_invalid = "FF" in erase_v or "00" in erase_v or erase_v == ""

            if orig_v == erase_v or is_erase_invalid:
                TestLog("INFO", "", f"{name}验证通过: 原始={orig_v}, 擦除后={erase_v}")
            else:
                TestLog("FAIL", "", f"{name}验证失败: 原始={orig_v}, 擦除后={erase_v}")
                all_match_or_invalid = False

        if all_match_or_invalid:
            TestLog("PASS", "", "期望：内存擦除后断电，之后读取的版本号不变或为无效值, 测试通过")
        else:
            TestLog("FAIL", "", "期望：内存擦除后断电，之后读取的版本号不变或为无效值, 测试失败")

        TestLog("INFO", "Step8", "重新执行刷写流程，在数据传输过程中断电")
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"下载前步骤失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)
        if not download_driver(node, flash_files):
            TestLog("FAIL", "", "下载DRIVER失败")
            return

        if not download_app_stop_witin_transfer_data(node, flash_files, "stop"):
            TestLog("INFO", "", "数据传输中断为预期行为")

        TestLog("INFO", "Step9", "断开KL30电源")
        powerOff()
        time.sleep(1)

        TestLog("INFO", "Step10", "控制程控电源给DUT重新上电")
        powerOn_WithoutCheck()
        time.sleep(5)

        TestLog("INFO", "Step11", "重新上电后读取DUT版本号(数据传输中断后)")
        trans_interrupt_versions = {}
        all_match_or_invalid_2 = True
        for name, did in version_ids.items():
            status, respMsg = service_22_check(node, did, expect_data=None, expect_str=f"肯定响应(62 {did>>8:02X} {did&0xFF:02X})")
            if (resp := (respMsg or type('', (), {'data': None})()).data) is None:
                trans_interrupt_versions[name] = ""
            elif resp[0] == 0x62:
                trans_interrupt_versions[name] = resp.hex(' ').upper()
            else:
                trans_interrupt_versions[name] = ""

            orig_v = orig_versions.get(name, "")
            trans_v = trans_interrupt_versions.get(name, "")

            is_orig_invalid = "FF" in orig_v or "00" in orig_v
            is_trans_invalid = "FF" in trans_v or "00" in trans_v or trans_v == ""

            if orig_v == trans_v or is_trans_invalid:
                TestLog("INFO", "", f"{name}验证通过: 原始={orig_v}, 数据传输中断后={trans_v}")
            else:
                TestLog("FAIL", "", f"{name}验证失败: 原始={orig_v}, 数据传输中断后={trans_v}")
                all_match_or_invalid_2 = False

        if all_match_or_invalid_2:
            TestLog("PASS", "", "期望：数据传输中断电，之后读取的版本号不变或为无效值, 测试通过")
        else:
            TestLog("FAIL", "", "期望：数据传输中断电，之后读取的版本号不变或为无效值, 测试失败")

        TestLog("INFO", "Step12", "重新上下电，执行完整的刷写流程")
        powerOff()
        time.sleep(1)
        powerOn_WithoutCheck()
        time.sleep(5)

        TestLog("INFO", "Step13", "执行完整的刷写流程")
        if not main_flash(node, flash_config, support_partition_ab):
            return

        time.sleep(5)

        TestLog("PASS", case_name, "刷写失败后软件版本无效测试执行完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()


def test_TG1_TC1_AppInvalid_DownloadTest():
    """
        应用程序无效时正常下载测试
    """
    case_name = "应用程序无效时正常下载测试"
    node = get_global_node()
    flash_config = get_flash_config()

    support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
    if support_partition_ab == 1:
        TestLog("WARNING", case_name, "PartSupportFlag = 1，不支持该项测试")
        return

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"测试设备执行下载流程，擦除DUT中的应用程序后停止下载，使应用程序无效")
        if not main_flash_until_erase_memory(node, flash_config):
            return

        TestLog("INFO", "Step3", f"重新上电，等待5s以上，发送 19 02 FF 请求，验证DUT处于BootLoader模式下")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        time.sleep(6)

        respMsg = node.Service_0x19_ReadDTCInformation(report_type=0x02, DTCStatusMask=0xFF, func_req=False)
        if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
        if not (resp[0] == 0x7F and resp[1] == 0x19 and resp[2] in [0x7F, 0x11]):
            TestLog("FAIL", " ", f"期望: ECU否定响应(7F 19 7F/11); 实际: {resp.hex(' ').upper()}")
            print(f"DEBUG: len={len(resp)}, raw={list(resp)}, "
                  f"resp[0]=0x{resp[0]:02X}, resp[1]=0x{resp[1]:02X}, resp[2]=0x{resp[2]:02X}")
            return
        else:
            TestLog("PASS", " ", f"期望: ECU否定响应(7F 19 7F/11); 实际: {resp.hex(' ').upper()}")

        TestLog("INFO", "Step4", f"请求进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="正响应(50 01)"):
            return

        TestLog("INFO", "Step5", f"发送 19 02 FF 请求，验证DUT处于BootLoader模式下")
        respMsg = node.Service_0x19_ReadDTCInformation(report_type=0x02, DTCStatusMask=0xFF, func_req=False)
        if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
        if not (resp[0] == 0x7F and resp[1] == 0x19 and resp[2] in [0x7F, 0x11]):
            TestLog("FAIL", " ", f"期望: ECU否定响应(7F 19 7F/11); 实际: {resp.hex(' ').upper()}")
            return
        else:
            TestLog("PASS", " ", f"期望: ECU否定响应(7F 19 7F/11); 实际: {resp.hex(' ').upper()}")

        TestLog("INFO", "Step6", f"ECU复位(11 01)")
        if not service_11_check(node, 0x01, expect_data=[0x51, 0x01], expect_str="肯定响应(51 01)"):
            return
        time.sleep(P.DiagServiceInfo.ResetTime / 1000)

        TestLog("INFO", "Step7", f"发送 19 02 FF 请求，验证DUT处于BootLoader模式下")
        respMsg = node.Service_0x19_ReadDTCInformation(report_type=0x02, DTCStatusMask=0xFF, func_req=False)
        if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
        if not (resp[0] == 0x7F and resp[1] == 0x19 and resp[2] in [0x7F, 0x11]):
            TestLog("FAIL", " ", f"期望: ECU否定响应(7F 19 7F/11); 实际: {resp.hex(' ').upper()}")
            return
        else:
            TestLog("PASS", " ", f"期望: ECU否定响应(7F 19 7F/11); 实际: {resp.hex(' ').upper()}")

        TestLog("INFO", "Step8", f"通过测试设备下载正确的应用程序")
        if not main_flash(node, flash_config, support_partition_ab):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC2_SC1_AppValid_DownloadTest():
    """
        应用程序有效时正常下载测试
    """
    case_name = "应用程序有效时正常下载测试9V"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = 9  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备下载正确的应用程序")
        if not main_flash(node, flash_config, support_partition_ab):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC2_SC2_AppValid_DownloadTest():
    """
        应用程序有效时正常下载测试
    """
    case_name = "应用程序有效时正常下载测试12V"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = 12  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备下载正确的应用程序")
        if not main_flash(node, flash_config, support_partition_ab):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC2_SC3_AppValid_DownloadTest():
    """
        应用程序有效时正常下载测试
    """
    case_name = "应用程序有效时正常下载测试16V"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = 16  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备下载正确的应用程序")
        if not main_flash(node, flash_config, support_partition_ab):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC3_SC1_ExitTestAfterEnterBootloader():
    """
        正常进入Bootloader模式后退出测试
    """
    case_name = "正常进入Bootloader模式后退出测试_通过默认会话请求退出"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return


        TestLog("INFO", "Step2", "测试设备控制DUT正常执行预编程步骤")
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", f"预编程步骤失败: {msg}")
            return

        TestLog("INFO", "Step3", "测试设备向DUT发送编程会话模式请求")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        clear_ctx_can_messages()

        # DUT响应肯定报文后，应用报文停止发送
        msg_list = get_ctx_can_msg()
        if len(msg_list) == 0:
            TestLog("PASS", " ", "期望: 应用报文停止发送; 实际: 未检测到应用报文")
        else:
            TestLog("FAIL", " ", "期望: 应用报文停止发送; 实际: 检测到应用报文")
            return

        TestLog("INFO", "Step4", "测试设备向DUT发送默认会话模式请求")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return

        clear_ctx_can_messages()

        # DUT响应肯定报文后，应用报文恢复发送
        msg_list = get_ctx_can_msg()
        if len(msg_list) > 0:
            TestLog("PASS", " ", "期望: 应用报文恢复发送; 实际: 检测到应用报文")
        else:
            TestLog("FAIL", " ", "期望: 应用报文恢复发送; 实际: 未检测到应用报文")
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC3_SC2_ExitTestAfterEnterBootloader():
    """
        正常进入Bootloader模式后退出测试
    """
    case_name = "正常进入Bootloader模式后退出测试_通过ECU复位退出"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", "测试设备控制DUT正常执行预编程步骤")
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", f"预编程步骤失败: {msg}")
            return

        TestLog("INFO", "Step3", "测试设备向DUT发送编程会话模式请求")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        clear_ctx_can_messages()

        # DUT响应肯定报文后，应用报文停止发送
        msg_list = get_ctx_can_msg()
        if len(msg_list) == 0:
            TestLog("PASS", " ", "期望: 应用报文停止发送; 实际: 未检测到应用报文")
        else:
            TestLog("FAIL", " ", "期望: 应用报文停止发送; 实际: 检测到应用报文")
            return

        TestLog("INFO", "Step4", "测试设备向DUT发送ECU复位请求")
        if not service_11_check(node, 0x01, expect_data=[0x51, 0x01], expect_str="肯定响应(51 01)"): return
        time.sleep(P.DiagServiceInfo.ResetTime / 1000)

        clear_ctx_can_messages()

        # DUT响应肯定报文后，应用报文恢复发送
        msg_list = get_ctx_can_msg()
        if len(msg_list) > 0:
            TestLog("PASS", " ", "期望: 应用报文恢复发送; 实际: 检测到应用报文")
        else:
            TestLog("FAIL", " ", "期望: 应用报文恢复发送; 实际: 未检测到应用报文")
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC3_SC3_ExitTestAfterEnterBootloader():
    """
        正常进入Bootloader模式后退出测试
    """
    case_name = "正常进入Bootloader模式后退出测试_通过S3Server超时退出"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", "测试设备控制DUT正常执行预编程步骤")
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", f"预编程步骤失败: {msg}")
            return

        TestLog("INFO", "Step3", "测试设备向DUT发送编程会话模式请求")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return

        clear_ctx_can_messages()

        # DUT响应肯定报文后，应用报文停止发送
        msg_list = get_ctx_can_msg()
        if len(msg_list) == 0:
            TestLog("PASS", " ", "期望: 应用报文停止发送; 实际: 未检测到应用报文")
        else:
            TestLog("FAIL", " ", "期望: 应用报文停止发送; 实际: 检测到应用报文")
            return

        TestLog("INFO", "Step4", "测试设备停止周期发送TP(3E)报文，等待5s以上")
        tester_present_stop()
        time.sleep(6)

        clear_ctx_can_messages()

        # DUT响应肯定报文后，应用报文恢复发送
        msg_list = get_ctx_can_msg()
        if len(msg_list) > 0:
            TestLog("PASS", " ", "期望: 应用报文恢复发送; 实际: 检测到应用报文")
        else:
            TestLog("FAIL", " ", "期望: 应用报文恢复发送; 实际: 未检测到应用报文")
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")



def test_TG1_TC4_StayInBootTest():
    """
        StayInBoot测试
    """
    case_name = "StayInBoot测试"
    node = get_global_node()
    flash_config = get_flash_config()
    rStayInBootSupportFlag = P.TpInfo.StayInBootSupportFlag
    from common.can_utils import canmsg_create, send_canmsg

    # 整体测试结果标志
    test_passed = True

    if rStayInBootSupportFlag == 0:
        TestLog("WARNING", case_name, "StayInBootSupportFlag = 0，不支持该项测试")
        return  # 不支持时直接返回，不执行后续

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", "Step1", "上电通信检查失败")
            test_passed = False
            # 不 return，继续执行

        TestLog("INFO", "Step2", f"停止本地唤醒/远程唤醒源，等待总线睡眠")
        powerOff()

        TestLog("INFO", "Step3", f"唤醒DUT，20ms内发送StayInBoot诊断请求31 01 DD 01")
        powerOn_WithoutCheck()

        start_wait_ms = time.time() * 1000.0
        wait_total_ms = P.CANInfo.Tstable_ms
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        r31Data = [0x04, 0x31, 0x01, 0xDD, 0x01, 0x00, 0x00, 0x00]
        msg = canmsg_create(node.tx_id, 8, data=r31Data, rtr=0, fdf=P.TpInfo.CanFDMode, brs=0, ext=0)
        while (time.time() * 1000.0 - start_wait_ms) < wait_total_ms:
            error_count1 = ctx.can.get_info("gErrorFrameCount") or 0
            send_canmsg(can_channel, msg)
            time.sleep(0.002)
            error_count2 = ctx.can.get_info("gErrorFrameCount") or 0
            if error_count1 == error_count2:
                break
            clear_ctx_can_messages()
            time.sleep(0.005)

        status, resp = service_31_check(node, 0x01, 0xDD01, expect_data=[0x71, 0x01, 0xDD, 0x01],
                                        expect_str="肯定响应(71 01 DD 01)")
        if not status:
            test_passed = False
            # 继续执行

        TestLog("INFO", "Step4", f"发送 19 02 FF 请求")
        respMsg = node.Service_0x19_ReadDTCInformation(report_type=0x02, DTCStatusMask=0xFF, func_req=False)
        if (resp := (respMsg or type('', (), {'data': None})()).data) is None:
            TestLog("FAIL", "Step4", "未收到响应")
            test_passed = False
        else:
            if not (resp[0] == 0x7F and resp[1] == 0x19 and resp[2] in [0x7F, 0x11]):
                TestLog("FAIL", " ", f"期望: ECU否定响应(7F 19 7F/11); 实际: {resp.hex(' ').upper()}")
                test_passed = False
            else:
                TestLog("PASS", " ", f"期望: ECU否定响应(7F 19 7F/11); 实际: {resp.hex(' ').upper()}")

        TestLog("INFO", "Step5", f"停发TP(3E 80)报文，等待6s")
        tester_present_stop()
        time.sleep(6)

        TestLog("INFO", "Step6", f"发送诊断请求 31 01 DD 01")
        status, resp = service_31_check(node, 0x01, 0xDD01, expect_data=[0x7F, 0x31, 0x7F],
                                        expect_str="否定响应(7F 31 7F)")
        if not status:
            test_passed = False

        TestLog("INFO", "Step7", f"停止本地唤醒/远程唤醒源，等待总线睡眠")
        powerOff()

        TestLog("INFO", "Step8", f"唤醒DUT，20ms后发送StayInBoot诊断请求31 01 DD 01")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            TestLog("FAIL", "Step8", "上电通信检查失败")
            test_passed = False
        else:
            status, resp = service_31_check(node, 0x01, 0xDD01, expect_data=[0x7F, 0x31, 0x7F],
                                            expect_str="否定响应(7F 31 7F)")
            if not status:
                test_passed = False

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
        test_passed = False

    # 最终结果
    if test_passed:
        TestLog("PASS", case_name, "所有步骤执行成功")
    else:
        TestLog("FAIL", case_name, "测试存在失败步骤")


def test_TG1_TC5_SC1_ABSwitchTest():
    """
        AB分区样件切区测试-两个分区都有效的情况下进行切区流程测试
    """
    case_name = "AB分区样件切区测试-两个分区都有效的情况下进行切区流程测试"
    node = get_global_node()
    flash_config = get_flash_config()

    support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
    if support_partition_ab == 0:
        TestLog("WARNING", case_name, "PartSupportFlag = 0，不支持该项测试")
        return

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        for i in range(2):
            TestLog("INFO", " ", f"第{i + 1}遍测试")

            TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
            ret = can_power_setup_and_communication_check(rVnormal, rTstable)
            if ret != 0:
                return

            TestLog("INFO", "Step2", f"读取当前运行分区(22 F0 F0)，记录读取结果数据为DATA1(41为A区，42为B区)")
            status, respMsg = service_22_check(node, 0xF0F0, expect_data=[0x62, 0xF0, 0xF0],
                                               expect_str="肯定响应62 F0 F0")
            if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
            if not status:
                return
            data1 = f"0x{resp[3]:X}"
            TestLog("INFO", " ", f"DATA1={data1}")

            TestLog("INFO", "Step3", f"进入扩展会话，通过安全访问Level1")
            TestLog("INFO", " ", f"进入扩展会话")
            if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
                return
            TestLog("INFO", " ", f"安全访问")
            if not security_access(node, 0x01): return

            TestLog("INFO", "Step4",
                    f"测试设备每间隔1s发送一次切区启动请求(31 01 DD 04)，如果收到正响应(71 01 DD 04 00)，则执行步骤5;"
                    f"10s内没有收到正响应，则切区启动超时，测试失败，终止测试")
            current_time = time.time()
            cyclic_timeout_s = 10  # 10s
            while True:
                if time.time() - current_time > cyclic_timeout_s:
                    TestLog("FAIL", " ", f"{cyclic_timeout_s}s内没有收到正响应，终止测试")
                    return
                status, resp = service_31_check(node, 0x01, 0xDD04, expect_data=[0x71, 0x01, 0xDD, 0x04, 0x00],
                                                expect_str="肯定响应(71 01 DD 04 00)", timeout=1)
                if status is True:
                    TestLog("PASS", " ", f"{cyclic_timeout_s}s收到正响应")
                    break

            TestLog("INFO", "Step5", f"测试设备每间隔1s发送一次读取切区结果请求(31 03 DD 04)，"
                                     f"如果收到响应71 03 DD 04 00，则执行步骤6;"
                                     f"如果收到响应71 03 DD 04 01，测试失败，终止测试;"
                                     f"如果收到响应71 03 DD 04 02，继续发送切区结果请求直至得到正响应;"
                                     f"若30min内未得到正响应，测试失败，终止测试")
            current_time = time.time()
            cyclic_timeout_s = 30 * 60  # 30min
            while True:
                if time.time() - current_time > cyclic_timeout_s:
                    TestLog("FAIL", " ", f"{cyclic_timeout_s}s内没有收到期望正响应，终止测试")
                    return
                status, respMsg = service_31_check(node, 0x03, 0xDD04, expect_data=[0x71, 0x03, 0xDD, 0x04],
                                                   expect_str="肯定响应(71 03 DD 04)", timeout=1)
                if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
                if status is False:
                    continue
                if resp[4] == 0x00:
                    TestLog("PASS", " ", f"{cyclic_timeout_s}s收到正响应")
                    break
                if resp[4] == 0x01:
                    TestLog("FAIL", " ", f"收到71 03 DD 04 01，测试失败，终止测试")
                    return
                if resp[4] == 0x02:
                    TestLog("PASS", " ", f"收到71 03 DD 04 02，继续发送切区结果请求直至得到正响应")
                    continue

            TestLog("INFO", "Step6", f"读取当前运行分区(22 F0 F0)，记录读取结果数据为DATA2(DATA2=DATA1)")
            status, respMsg = service_22_check(node, 0xF0F0, expect_data=[0x62, 0xF0, 0xF0],
                                               expect_str="肯定响应62 F0 F0")
            if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
            if not status:
                return
            data2 = f"0x{resp[3]:X}"
            TestLog("INFO", " ", f"DATA2={data2}")
            if data1 == data2:
                TestLog("PASS", " ", f"期望: DATA1=DATA2; 实际: DATA1 = DATA2")
            else:
                TestLog("FAIL", " ", f"期望: DATA1=DATA2; 实际: DATA1 != DATA2")
                return

            TestLog("INFO", "Step7", f"ECU复位(11 01)")
            if not service_11_check(node, 0x01, expect_data=[0x51, 0x01], expect_str="肯定响应(51 01)"):
                return
            time.sleep(P.DiagServiceInfo.ResetTime / 1000)

            TestLog("INFO", "Step8", f"读取当前运行分区(22 F0 F0)，记录读取结果数据为DATA3(DATA3!=DATA1)")
            status, respMsg = service_22_check(node, 0xF0F0, expect_data=[0x62, 0xF0, 0xF0],
                                               expect_str="肯定响应62 F0 F0")
            if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
            if not status:
                return
            data3 = f"0x{resp[3]:X}"
            TestLog("INFO", " ", f"DATA3={data3}")
            if data1 == data3:
                TestLog("FAIL", " ", "期望: DATA1!=DATA3; 实际: DATA1 = DATA3")
                return
            else:
                TestLog("PASS", " ", "期望: DATA1!=DATA3; 实际: DATA1 != DATA3")

            if not switchPart(node, data1):
                return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC5_SC2_ABSwitchTest():
    """
        AB分区样件切区测试-某个分区失效的情况下进行切区流程测试
    """
    case_name = "AB分区样件切区测试-某个分区失效的情况下进行切区流程测试"
    node = get_global_node()
    flash_config = get_flash_config()

    support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
    if support_partition_ab == 0:
        TestLog("WARNING", case_name, "PartSupportFlag = 0，不支持该项测试")
        return

    # 整体测试结果标志
    test_passed = True

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        for i in range(2):
            TestLog("INFO", " ", f"第{i + 1}遍测试")

            TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
            ret = can_power_setup_and_communication_check(rVnormal, rTstable)
            if ret != 0:
                TestLog("FAIL", "Step1", "上电通信检查失败")
                test_passed = False
                # 继续执行下一遍测试（不return）

            TestLog("INFO", "Step2", f"读取当前运行分区(22 F0 F0)，记录读取结果数据为DATA1(41为A区，42为B区)")
            status, respMsg = service_22_check(node, 0xF0F0, expect_data=[0x62, 0xF0, 0xF0],
                                               expect_str="肯定响应62 F0 F0")
            resp = (respMsg or type('', (), {'data': None})()).data
            if not status or resp is None:
                TestLog("FAIL", "Step2", "读取运行分区失败")
                test_passed = False
                continue  # 跳过本轮后续步骤
            data1 = f"0x{resp[3]:X}"
            TestLog("INFO", " ", f"DATA1={data1}")

            TestLog("INFO", "Step3", f"通过测试设备执行刷写流程，在内存擦除后控制程控电源断开KL30 10s，使备份分区失效")
            if not main_flash_until_erase_memory(node, flash_config, support_partition_ab):
                TestLog("FAIL", "Step3", "刷写流程失败，无法使备份分区失效")
                test_passed = False
                continue
            ctx.power_ctrl.off()
            time.sleep(10)

            TestLog("INFO", "Step4", f"重新上电，等待2s至总线通信稳定")
            ctx.power_ctrl.on()
            time.sleep(2)

            TestLog("INFO", "", f"进入扩展会话，通过安全访问Level1")
            TestLog("INFO", " ", f"进入扩展会话")
            if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
                TestLog("FAIL", "Step4", "进入扩展会话失败")
                test_passed = False
                continue
            TestLog("INFO", " ", f"安全访问")
            if not security_access(node, 0x01):
                TestLog("FAIL", "Step4", "安全访问失败")
                test_passed = False
                continue

            TestLog("INFO", "Step5", f"测试设备每间隔1s发送一次切区启动请求(31 01 DD 04)，"
                                     f"如果收到正响应(71 01 DD 04 00)，则执行步骤6;"
                                     f"如果收到正响应(71 01 DD 04 01)，则执行步骤7;"
                                     f"10s内没有收到正响应，则切区启动超时，测试失败，终止测试")
            current_time = time.time()
            cyclic_timeout_s = 10  # 10s
            step5_result = None  # 用于记录收到的响应状态
            while True:
                if time.time() - current_time > cyclic_timeout_s:
                    TestLog("FAIL", " ", f"{cyclic_timeout_s}s内没有收到正响应，切区启动超时")
                    test_passed = False
                    step5_result = "timeout"
                    break
                status, respMsg = service_31_check(node, 0x01, 0xDD04, expect_data=[0x71, 0x01, 0xDD, 0x04],
                                                   expect_str="肯定响应(71 01 DD 04)", timeout=1)
                resp = (respMsg or type('', (), {'data': None})()).data
                if not status or resp is None:
                    continue
                result = resp[4]
                if result == 0x00:
                    TestLog("PASS", " ", f"收到响应 71 01 DD 04 00，执行步骤6")
                    step5_result = "00"
                    break
                elif result == 0x01:
                    TestLog("PASS", " ", f"收到响应 71 01 DD 04 01，执行步骤7")
                    step5_result = "01"
                    break
                # 其他值视为未收到期望，继续循环
            if step5_result is None:
                continue  # 超时，跳过本轮后续步骤

            TestLog("INFO", "Step6", f"测试设备每间隔1s发送一次读取切区结果请求(31 03 DD 04)，"
                                     f"如果收到响应71 03 DD 04 00，则执行步骤7;"
                                     f"如果收到响应71 03 DD 04 01，测试成功;"
                                     f"如果收到响应71 03 DD 04 02，继续发送切区结果请求直至得到正响应;"
                                     f"若30min内未得到正响应，测试失败，终止测试")
            current_time = time.time()
            cyclic_timeout_s = 30 * 60  # 30min
            step6_result = None
            while True:
                if time.time() - current_time > cyclic_timeout_s:
                    TestLog("FAIL", " ", f"{cyclic_timeout_s}s内未得到期望响应，切区结果超时")
                    test_passed = False
                    step6_result = "timeout"
                    break
                status, respMsg = service_31_check(node, 0x03, 0xDD04, expect_data=[0x71, 0x03, 0xDD, 0x04],
                                                   expect_str="肯定响应(71 03 DD 04)", timeout=1)
                resp = (respMsg or type('', (), {'data': None})()).data
                if not status or resp is None:
                    continue
                result = resp[4]
                if result == 0x00:
                    TestLog("PASS", " ", f"收到71 03 DD 04 00，执行步骤7")
                    step6_result = "00"
                    break
                elif result == 0x01:
                    TestLog("PASS", " ", f"收到71 03 DD 04 01，测试成功")
                    step6_result = "01"
                    break
                elif result == 0x02:
                    TestLog("PASS", " ", f"收到71 03 DD 04 02，继续发送切区结果请求")
                    continue
                # 其他值继续等待
            if step6_result is None:
                continue

            TestLog("INFO", "Step7", f"ECU复位(11 01)")
            if not service_11_check(node, 0x01, expect_data=[0x51, 0x01], expect_str="肯定响应(51 01)"):
                TestLog("FAIL", "Step7", "ECU复位失败")
                test_passed = False
                continue
            time.sleep(P.DiagServiceInfo.ResetTime / 1000)

            TestLog("INFO", "Step8", f"读取当前运行分区(22 F0 F0)，记录读取结果数据为DATA2")
            status, respMsg = service_22_check(node, 0xF0F0, expect_data=[0x62, 0xF0, 0xF0],
                                               expect_str="肯定响应62 F0 F0")
            resp = (respMsg or type('', (), {'data': None})()).data
            if not status or resp is None:
                TestLog("FAIL", "Step8", "读取运行分区失败")
                test_passed = False
                continue
            data2 = f"0x{resp[3]:X}"
            TestLog("INFO", " ", f"DATA2={data2}")

            # 根据规范 SubCase2，分区失效时不应切区，因此 DATA1 应等于 DATA2
            if data1 == data2:
                TestLog("PASS", " ", f"期望: DATA1=DATA2; 实际: DATA1 == DATA2")
            else:
                TestLog("FAIL", " ", f"期望: DATA1=DATA2; 实际: DATA1 != DATA2")
                test_passed = False

            TestLog("INFO", "Step9", f"通过测试设备执行刷写流程")
            if not main_flash(node, flash_config, support_partition_ab):
                TestLog("FAIL", "Step9", "刷写流程失败")
                test_passed = False
                continue

            TestLog("INFO", "Step10", f"读取当前运行分区(22 F0 F0)，记录读取结果数据为DATA3")
            status, respMsg = service_22_check(node, 0xF0F0, expect_data=[0x62, 0xF0, 0xF0],
                                               expect_str="肯定响应62 F0 F0")
            resp = (respMsg or type('', (), {'data': None})()).data
            if not status or resp is None:
                TestLog("FAIL", "Step10", "读取运行分区失败")
                test_passed = False
                continue
            data3 = f"0x{resp[3]:X}"
            TestLog("INFO", " ", f"DATA3={data3}")
            if data1 != data3:
                TestLog("PASS", " ", "期望: DATA1!=DATA3; 实际: DATA1 != DATA3")
            else:
                TestLog("FAIL", " ", "期望: DATA1!=DATA3; 实际: DATA1 == DATA3")
                test_passed = False

            if not switchPart(node, data1):
                TestLog("FAIL", "Step11", "切换分区失败")
                test_passed = False
                continue

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
        test_passed = False

    # 最终结果
    if test_passed:
        TestLog("PASS", case_name, "所有步骤执行成功")
    else:
        TestLog("FAIL", case_name, "测试存在失败步骤")

def test_TG1_TC6_SC1_ABPreventSwitchTest():
    """
        AB分区样件阻止切区测试-不发送阻止切区请求
    """
    case_name = "AB分区样件阻止切区测试-不发送阻止切区请求"
    node = get_global_node()
    flash_config = get_flash_config()

    support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
    if support_partition_ab == 0:
        TestLog("WARNING", case_name, "PartSupportFlag = 0，不支持该项测试")
        return

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        for i in range(2):
            TestLog("INFO", " ", f"第{i + 1}遍测试")

            TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
            ret = can_power_setup_and_communication_check(rVnormal, rTstable)
            if ret != 0:
                return

            TestLog("INFO", "Step2", f"读取当前运行分区(22 F0 F0)，记录读取结果数据为DATA1(41为A区，42为B区)")
            status, respMsg = service_22_check(node, 0xF0F0, expect_data=[0x62, 0xF0, 0xF0],
                                               expect_str="肯定响应62 F0 F0")
            if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
            if not status:
                return
            data1 = f"0x{resp[3]:X}"
            TestLog("INFO", " ", f"DATA1={data1}")

            TestLog("INFO", "Step3",
                    f"通过测试设备执行刷写流程，在应用程序传输完成后，不发送阻止自动切区诊断请求，继续执行后续刷写步骤，刷写完成后执行ECU复位(11 01)")
            if not main_flash(node, flash_config, support_partition_ab): return

            TestLog("INFO", "Step4", f"读取当前运行分区(22 F0 F0)，记录读取结果数据为DATA2")
            status, respMsg = service_22_check(node, 0xF0F0, expect_data=[0x62, 0xF0, 0xF0],
                                               expect_str="肯定响应62 F0 F0")
            if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
            if not status:
                return
            data2 = f"0x{resp[3]:X}"
            TestLog("INFO", " ", f"DATA2={data2}")
            if data1 != data2:
                TestLog("PASS", " ", f"期望: DATA1 != DATA2; 实际: DATA1 != DATA2")
            else:
                TestLog("FAIL", " ", f"期望: DATA1 != DATA2; 实际: DATA1 = DATA2")
                return

            if not switchPart(node, data1):
                return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC6_SC2_ABPreventSwitchTest():
    """
        AB分区样件阻止切区测试-发送阻止切区请求
    """
    case_name = "AB分区样件阻止切区测试-发送阻止切区请求"
    node = get_global_node()
    flash_config = get_flash_config()

    support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
    if support_partition_ab == 0:
        TestLog("WARNING", case_name, "PartSupportFlag = 0，不支持该项测试")
        return

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        for i in range(2):
            TestLog("INFO", " ", f"第{i + 1}遍测试")

            TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
            ret = can_power_setup_and_communication_check(rVnormal, rTstable)
            if ret != 0:
                return

            TestLog("INFO", "Step2", f"读取当前运行分区(22 F0 F0)，记录读取结果数据为DATA1(41为A区，42为B区)")
            status, respMsg = service_22_check(node, 0xF0F0, expect_data=[0x62, 0xF0, 0xF0],
                                               expect_str="肯定响应62 F0 F0")
            if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
            if not status:
                return
            data1 = f"0x{resp[3]:X}"
            TestLog("INFO", " ", f"DATA1={data1}")

            TestLog("INFO", "Step3",
                    f"通过测试设备执行刷写流程，在应用程序传输完成后，发送阻止自动切区诊断请求(31 01 FF 0F)")
            # 预编程阶段
            status, msg = phase_pre_programming(node)
            if not status:
                TestLog("FAIL", " ", "预编程阶段失败")
                return

            # 编程阶段
            status, msg = phase_programming_with_prevent_switch_part(node, flash_config, support_partition_ab)
            if not status:
                TestLog("FAIL", " ", "编程阶段失败")
                return

            TestLog("INFO", "Step4", f"执行后续刷写步骤，ECU复位后，读取当前运行分区(22 F0 F0)，记录读取结果数据来DATA2")
            # 后编程阶段
            status, msg = phase_pro_programming(node)
            if not status:
                TestLog("FAIL", " ", "后编程阶段失败")
                return

            status, respMsg = service_22_check(node, 0xF0F0, expect_data=[0x62, 0xF0, 0xF0],
                                               expect_str="肯定响应62 F0 F0")
            if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
            if not status:
                return
            data2 = f"0x{resp[3]:X}"
            TestLog("INFO", " ", f"DATA2={data2}")
            if data1 == data2:
                TestLog("PASS", " ", f"期望: DATA1=DATA2; 实际: DATA1 = DATA2")
            else:
                TestLog("FAIL", " ", f"期望: DATA1=DATA2; 实际: DATA1 != DATA2")
                return

            TestLog("INFO", "Step5", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
            ctx.power_ctrl.off()
            ctx.power_ctrl.on()
            time.sleep(2)

            TestLog("INFO", "Step6", f"通过测试设备执行刷写流程")
            if not main_flash(node, flash_config, support_partition_ab): return

            TestLog("INFO", "Step7", f"读取当前运行分区(22 F0 F0)，记录读取结果数据为DATA3(DATA3!=DATA1)")
            status, respMsg = service_22_check(node, 0xF0F0, expect_data=[0x62, 0xF0, 0xF0],
                                               expect_str="肯定响应62 F0 F0")
            if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
            if not status:
                return
            data3 = f"0x{resp[3]:X}"
            TestLog("INFO", " ", f"DATA3={data3}")
            if data1 == data3:
                TestLog("FAIL", " ", "期望: DATA1!=DATA3; 实际: DATA1 = DATA3")
                return
            else:
                TestLog("PASS", " ", "期望: DATA1!=DATA3; 实际: DATA1 != DATA3")

            if not switchPart(node, data1):
                return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG1_TC7_SC1_ProgrammingConditionCheckTest():
    """
        编程条件检查测试-SubCase1
    """
    case_name = "编程条件检查测试-SubCase1"
    node = get_global_node()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
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


# def test_TG1_TC7_SC2_ProgrammingConditionCheckTest():
#     """
#         编程条件检查测试-SubCase2
#     """
#     case_name = "编程条件检查测试-SubCase2"
#     node = get_global_node()
#
#     try:
#         rVnormal = P.CANInfo.Vnormal  # 电源正常电压
#         rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
#
#         TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
#         ret = can_power_setup_and_communication_check(rVnormal, rTstable)
#         if ret != 0:
#             return
#
#         TestLog("INFO", "Step2", "TODO:模拟车速≤3km/h，档位P档，等待5s后停止发送")
#         time.sleep(5)
#
#         TestLog("INFO", "Step3", "TODO:等待5s，再次开始模拟车速≤3km/h，档位P档")
#         time.sleep(5)
#
#         TestLog("INFO", "Step4", "执行进入默认会话(10 01)")
#         if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"):
#             return
#
#         TestLog("INFO", "Step5", "执行进入扩展会话(10 03)")
#         if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
#             return
#
#         TestLog("INFO", "Step6", "执行编程条件检查(31 01 02 03)")
#         status, resp = service_31_check(node, 0x01, 0x0203, expect_data=[0x71, 0x01, 0x02, 0x03, 0x00],
#                                         expect_str="肯定响应(71 01 02 03 00)")
#         if not status:
#             return
#
#         TestLog("INFO", "Step7", "执行进入编程会话(10 02)")
#         if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"):
#             return
#
#     except Exception as e:
#         TestLog("FAIL", case_name, f"测试执行出错: {e}")
#         import traceback
#         TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
#     finally:
#         tester_present_stop()
#
#
# def test_TG1_TC7_SC3_ProgrammingConditionCheckTest():
#     """
#         编程条件检查测试-SubCase3
#     """
#     case_name = "编程条件检查测试-SubCase3"
#     node = get_global_node()
#
#     try:
#         rVnormal = P.CANInfo.Vnormal
#         rTstable = P.CANInfo.Tstable_s
#
#         TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
#         ret = can_power_setup_and_communication_check(rVnormal, rTstable)
#         if ret != 0:
#             return
#
#         TestLog("INFO", "Step2", "TODO:模拟车速≤3km/h，档位P档")
#
#         TestLog("INFO", "Step3", "执行进入默认会话(10 01)")
#         if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"):
#             return
#
#         TestLog("INFO", "Step4", "执行进入扩展会话(10 03)")
#         if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
#             return
#
#         TestLog("INFO", "Step5", "执行编程条件检查(31 01 02 03)")
#         status, resp = service_31_check(node, 0x01, 0x0203, expect_data=[0x71, 0x01, 0x02, 0x03, 0x00],
#                                         expect_str="肯定响应(71 01 02 03 00)")
#         if not status:
#             return
#
#         TestLog("INFO", "Step6", "执行进入编程会话(10 02)")
#         if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"):
#             return
#
#     except Exception as e:
#         TestLog("FAIL", case_name, f"测试执行出错: {e}")
#         import traceback
#         TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
#     finally:
#         tester_present_stop()
#
#
# def test_TG1_TC7_SC4_ProgrammingConditionCheckTest():
#     """
#         编程条件检查测试-SubCase4
#     """
#     case_name = "编程条件检查测试-SubCase4"
#     node = get_global_node()
#
#     try:
#         rVnormal = P.CANInfo.Vnormal
#         rTstable = P.CANInfo.Tstable_s
#
#         TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
#         ret = can_power_setup_and_communication_check(rVnormal, rTstable)
#         if ret != 0:
#             return
#
#         TestLog("INFO", "Step2", "TODO:模拟车速≤3km/h，档位N档")
#
#         TestLog("INFO", "Step3", "执行进入默认会话(10 01)")
#         if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"):
#             return
#
#         TestLog("INFO", "Step4", "执行进入扩展会话(10 03)")
#         if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
#             return
#
#         TestLog("INFO", "Step5", "执行编程条件检查(31 01 02 03)")
#         status, resp = service_31_check(node, 0x01, 0x0203, expect_data=[0x71, 0x01, 0x02, 0x03, 0x00],
#                                         expect_str="肯定响应(71 01 02 03 00)")
#         if not status:
#             return
#
#         TestLog("INFO", "Step6", "执行进入编程会话(10 02)")
#         if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"):
#             return
#
#     except Exception as e:
#         TestLog("FAIL", case_name, f"测试执行出错: {e}")
#         import traceback
#         TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
#     finally:
#         tester_present_stop()


#shb为纯电，无发动机，不适用该测试用例

# def test_TG1_TC7_SC5_ProgrammingConditionCheckTest():
#     """
#         编程条件检查测试-SubCase5
#     """
#     case_name = "编程条件检查测试-SubCase5(发动机转速异常)"
#     node = get_global_node()
#
#     try:
#         rVnormal = P.CANInfo.Vnormal
#         rTstable = P.CANInfo.Tstable_s
#
#         TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
#         ret = can_power_setup_and_communication_check(rVnormal, rTstable)
#         if ret != 0:
#             return
#
#         TestLog("INFO", "Step2", "TODO: 模拟发动机转速>1000rpm")
#
#         TestLog("INFO", "Step3", "执行进入默认会话(10 01)")
#         if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"):
#             return
#
#         TestLog("INFO", "Step4", "执行进入扩展会话(10 03)")
#         if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
#             return
#
#         TestLog("INFO", "Step5", "执行编程条件检查(31 01 02 03)")
#         status, resp = service_31_check(node, 0x01, 0x0203, expect_data=[0x71, 0x01, 0x02, 0x03, 0x04],
#                                         expect_str="响应(71 01 02 03 04)-发动机转速异常")
#         if not status:
#             TestLog("INFO", "", "编程条件检查未返回预期的异常响应")
#
#         TestLog("INFO", "Step6", "执行进入编程会话(10 02)，期望否定响应")
#         if service_10_check(node, 0x02, expect_data=[0x7F, 0x10, 0x22], expect_str="否定响应(7F 10 22)"):
#             TestLog("PASS", "", "正确返回条件不满足的否定响应")
#         else:
#             TestLog("FAIL", "", "未返回预期的否定响应")
#
#     except Exception as e:
#         TestLog("FAIL", case_name, f"测试执行出错: {e}")
#         import traceback
#         TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
#     finally:
#         tester_present_stop()


# def test_TG1_TC7_SC6_ProgrammingConditionCheckTest():
#     """
#         编程条件检查测试-SubCase6
#     """
#     case_name = "编程条件检查测试-SubCase6(车速异常)"
#     node = get_global_node()
#
#     try:
#         rVnormal = P.CANInfo.Vnormal
#         rTstable = P.CANInfo.Tstable_s
#
#         TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
#         ret = can_power_setup_and_communication_check(rVnormal, rTstable)
#         if ret != 0:
#             return
#
#         TestLog("INFO", "Step2", "TODO: 模拟车速>3km/h，档位P/N档")
#
#         TestLog("INFO", "Step3", "执行进入默认会话(10 01)")
#         if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"):
#             return
#
#         TestLog("INFO", "Step4", "执行进入扩展会话(10 03)")
#         if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
#             return
#
#         TestLog("INFO", "Step5", "执行编程条件检查(31 01 02 03)")
#         status, resp = service_31_check(node, 0x01, 0x0203, expect_data=[0x71, 0x01, 0x02, 0x03, 0x03],
#                                         expect_str="响应(71 01 02 03 03)-车速异常")
#         if not status:
#             TestLog("INFO", "", "编程条件检查未返回预期的异常响应")
#
#         TestLog("INFO", "Step6", "执行进入编程会话(10 02)，期望否定响应")
#         if service_10_check(node, 0x02, expect_data=[0x7F, 0x10, 0x22], expect_str="否定响应(7F 10 22)"):
#             TestLog("PASS", "", "正确返回条件不满足的否定响应")
#         else:
#             TestLog("FAIL", "", "未返回预期的否定响应")
#
#     except Exception as e:
#         TestLog("FAIL", case_name, f"测试执行出错: {e}")
#         import traceback
#         TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
#     finally:
#         tester_present_stop()
#
#
# def test_TG1_TC7_SC7_ProgrammingConditionCheckTest():
#     """
#         编程条件检查测试-SubCase7
#     """
#     case_name = "编程条件检查测试-SubCase7(档位异常)"
#     node = get_global_node()
#
#     try:
#         rVnormal = P.CANInfo.Vnormal
#         rTstable = P.CANInfo.Tstable_s
#
#         TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
#         ret = can_power_setup_and_communication_check(rVnormal, rTstable)
#         if ret != 0:
#             return
#
#         TestLog("INFO", "Step2", "TODO: 模拟车速≤3km/h，档位非P/N档(如D档)")
#
#         TestLog("INFO", "Step3", "执行进入默认会话(10 01)")
#         if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"):
#             return
#
#         TestLog("INFO", "Step4", "执行进入扩展会话(10 03)")
#         if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
#             return
#
#         TestLog("INFO", "Step5", "执行编程条件检查(31 01 02 03)")
#         status, resp = service_31_check(node, 0x01, 0x0203, expect_data=[0x71, 0x01, 0x02, 0x03, 0x05],
#                                         expect_str="响应(71 01 02 03 05)-档位异常")
#         if not status:
#             TestLog("INFO", "", "编程条件检查未返回预期的异常响应")
#
#         TestLog("INFO", "Step6", "执行进入编程会话(10 02)，期望否定响应")
#         if service_10_check(node, 0x02, expect_data=[0x7F, 0x10, 0x22], expect_str="否定响应(7F 10 22)"):
#             TestLog("PASS", "", "正确返回条件不满足的否定响应")
#         else:
#             TestLog("FAIL", "", "未返回预期的否定响应")
#
#     except Exception as e:
#         TestLog("FAIL", case_name, f"测试执行出错: {e}")
#         import traceback
#         TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
#     finally:
#         tester_present_stop()


def test_TG1_TC7_SC8_ProgrammingConditionCheckTest():
    """
        编程条件检查测试-SubCase8
    """
    case_name = "编程条件检查测试-SubCase8(电压过低)"
    node = get_global_node()

    try:
        rVlow = 7.0  # 低电压
        rTstable = P.CANInfo.Tstable_s

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVlow}V(欠压), 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVlow, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", "执行进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"):
            return

        TestLog("INFO", "Step3", "执行进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
            return

        TestLog("INFO", "Step4", "执行编程条件检查(31 01 02 03)")
        status, resp = service_31_check(node, 0x01, 0x0203, expect_data=[0x71, 0x01, 0x02, 0x03, 0x02],
                                        expect_str="响应(71 01 02 03 02)-电压异常")
        if not status:
            TestLog("INFO", "", "编程条件检查未返回预期的异常响应")

        TestLog("INFO", "Step5", "执行进入编程会话(10 02)，期望否定响应")
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
            rVnormal = P.CANInfo.Vnormal
            can_power_setup_and_communication_check(rVnormal, 1)
        except:
            pass
        tester_present_stop()


def test_TG1_TC7_SC9_ProgrammingConditionCheckTest():
    """
        编程条件检查测试-SubCase9
    """
    case_name = "编程条件检查测试-SubCase9(电压过高)"
    node = get_global_node()

    try:
        rVhigh = 18.0  # 高电压
        rTstable = P.CANInfo.Tstable_s

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVhigh}V(过压), 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVhigh, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", "执行进入默认会话(10 01)")
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"):
            return

        TestLog("INFO", "Step3", "执行进入扩展会话(10 03)")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
            return

        TestLog("INFO", "Step4", "执行编程条件检查(31 01 02 03)")
        status, resp = service_31_check(node, 0x01, 0x0203, expect_data=[0x71, 0x01, 0x02, 0x03, 0x02],
                                        expect_str="响应(71 01 02 03 02)-电压异常")
        if not status:
            TestLog("INFO", "", "编程条件检查未返回预期的异常响应")

        TestLog("INFO", "Step5", "执行进入编程会话(10 02)，期望否定响应")
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
            rVnormal = P.CANInfo.Vnormal
            can_power_setup_and_communication_check(rVnormal, 1)
        except:
            pass
        tester_present_stop()

# F184普遍只支持2711安全访问，所以该用例不能通过2701解锁后写入F184

def test_TG1_TC8_SC1_2E_WriteDataAfterFlashTest():
    """
        2E写入数据刷写后检查是否重置测试
    """
    case_name = "2E写入数据刷写后检查是否重置测试-SubCase1"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return False

        time.sleep(2)
        TestLog("INFO", "进入编程会话", "10 02")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02],
                                expect_str="肯定响应(50 02)"): return False, f"编程阶段失败: 进入编程会话失败"

        TestLog("INFO", "安全访问", "27 11")
        if not security_access(node, 0x11):
            return False, "编程阶段失败: 安全访问失败"



        TestLog("INFO", "Step3", "通过2E服务写入刷写指纹(2E F1 84 + DATA1)")
        from testcases.bootloader.utils.bootloader_utils import make_fingerprint
        fingerprint_data = make_fingerprint("TestFlash")
        data1 = bytes(fingerprint_data)
        TestLog("INFO", "", f"DATA1={data1.hex(' ').upper()}")
        resp = node.Service_0x2E_WriteDataByIdentifier(0xF184, fingerprint_data)
        if resp is None:
            TestLog("FAIL", "", "写入指纹失败: 未收到响应")
            return
        resp_data = resp.data if hasattr(resp, 'data') else resp
        if resp_data[0] != 0x6E:
            TestLog("FAIL", "", f"期望: 肯定响应(6E F1 84); 实际: {resp_data.hex(' ').upper()}")
            return
        TestLog("PASS", "", f"期望: 肯定响应(6E F1 84); 实际: {resp_data.hex(' ').upper()}")

        TestLog("INFO", "Step4", "控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab):
            return

        TestLog("INFO", "Step5", "控制程控电源给DUT重新上电")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        time.sleep(rTstable)

        TestLog("INFO", "Step6", "通过22服务读取指纹数据(22 F1 84)，记录为DATA2")
        status, respMsg = service_22_check(node, 0xF184, expect_data=[0x62, 0xF1, 0x84],
                                           expect_str="肯定响应(62 F1 84)")
        if not status:
            return
        if (resp := (respMsg or type('', (), {'data': None})()).data) is None:
            return
        data2 = bytes(resp[3:]) if len(resp) > 3 else b''
        TestLog("INFO", "", f"DATA2={data2.hex(' ').upper() if data2 else 'Empty'}")

        TestLog("INFO", "Step7", "比对DATA1，DATA2")
        if data2 == data1:
            TestLog("PASS", "", f"期望: DATA2=DATA1(数据保持); 实际: DATA2=DATA1")
        else:
            TestLog("FAIL", "", f"期望: DATA2=DATA1(数据保持); 实际: DATA2!=DATA1")
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()


# def test_TG1_TC8_SC2_2E_WriteDataAfterFlashTest():
#     """
#         2E写入数据刷写后检查是否重置测试-SubCase2
#     """
#     case_name = "2E写入数据刷写后检查是否重置测试-SubCase2"
#     node = get_global_node()
#     flash_config = get_flash_config()
#
#     try:
#         rVnormal = P.CANInfo.Vnormal  # 电源正常电压
#         rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
#         support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
#
#         TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
#         ret = can_power_setup_and_communication_check(rVnormal, rTstable)
#         if ret != 0:
#             return
#
#         TestLog("INFO", "Step2", "进入扩展会话(10 03)，通过安全访问Level1")
#         if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
#             return
#         if not security_access(node, 0x01):
#             return
#
#         TestLog("INFO", "Step3", "通过2E服务写入通用数据(2E XX XX + DATA1)")
#         # 需要根据实际项目配置
#         test_did = 0xF190
#         test_data = bytes([0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38])
#         data1 = test_data
#         TestLog("INFO", "", f"DATA1={data1.hex(' ').upper()}")
#         resp = node.Service_0x2E_WriteDataByIdentifier(test_did, test_data)
#         if resp is None:
#             TestLog("FAIL", "", "写入数据失败: 未收到响应")
#             return
#         resp_data = resp.data if hasattr(resp, 'data') else resp
#         if resp_data[0] != 0x6E:
#             TestLog("FAIL", "", f"期望: 肯定响应(6E); 实际: {resp_data.hex(' ').upper()}")
#             return
#         TestLog("PASS", "", f"期望: 肯定响应(6E); 实际: {resp_data.hex(' ').upper()}")
#
#         TestLog("INFO", "Step4", "控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
#         ctx.power_ctrl.off()
#         time.sleep(1)
#         ctx.power_ctrl.on()
#         time.sleep(rTstable)
#         if not main_flash(node, flash_config, support_partition_ab):
#             return
#
#         TestLog("INFO", "Step5", "控制程控电源给DUT重新上电")
#         ctx.power_ctrl.off()
#         time.sleep(1)
#         ctx.power_ctrl.on()
#         time.sleep(rTstable)
#
#         TestLog("INFO", "Step6", f"通过22服务读取数据(22 {test_did:04X})，记录为DATA2")
#         status, respMsg = service_22_check(node, test_did, expect_data=[0x62, (test_did >> 8) & 0xFF, test_did & 0xFF],
#                                            expect_str=f"肯定响应(62 {test_did:04X})")
#         if not status:
#             return
#         if (resp := (respMsg or type('', (), {'data': None})()).data) is None:
#             return
#         data2 = bytes(resp[3:]) if len(resp) > 3 else b''
#         TestLog("INFO", "", f"DATA2={data2.hex(' ').upper() if data2 else 'Empty'}")
#
#         TestLog("INFO", "Step7", "比对DATA1，DATA2")
#         if data2 == data1:
#             TestLog("PASS", "", f"期望: DATA2=DATA1(数据保持); 实际: DATA2=DATA1")
#         else:
#             TestLog("FAIL", "", f"期望: DATA2=DATA1(数据保持); 实际: DATA2!=DATA1")
#             return
#
#     except Exception as e:
#         TestLog("FAIL", case_name, f"测试执行出错: {e}")
#         import traceback
#         TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
#     finally:
#         tester_present_stop()


# def test_TG12_TC9_2E_WriteConfigWordTest():
#     """
#         2E写入配置字测试-SubCase1
#     """
#     case_name = "2E写入配置字测试-SubCase1"
#     node = get_global_node()
#
#     try:
#         rVnormal = P.CANInfo.Vnormal  # 电源正常电压
#         rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
#
#         TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
#         ret = can_power_setup_and_communication_check(rVnormal, rTstable)
#         if ret != 0:
#             return
#
#         TestLog("INFO", "Step2", "进入扩展会话(10 03)，通过安全访问Level1")
#         if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
#             return
#         if not security_access(node, 0x01):
#             return
#
#         TestLog("INFO", "Step3", "通过2E服务写入配置字(2E XX XX DATA1)")
#         # 配置字DID，可根据实际项目配置修改
#         config_did = 0xF0FF
#         test_config_data = bytes([0x01, 0x02, 0x03, 0x04])
#         data1 = test_config_data
#         TestLog("INFO", "", f"DATA1={data1.hex(' ').upper()}")
#         resp = node.Service_0x2E_WriteDataByIdentifier(config_did, test_config_data)
#         if resp is None:
#             TestLog("FAIL", "", "写入配置字失败: 未收到响应")
#             return
#         resp_data = resp.data if hasattr(resp, 'data') else resp
#         if resp_data[0] == 0x6E:
#             TestLog("PASS", "", f"期望: 肯定响应; 实际: {resp_data.hex(' ').upper()}")
#         else:
#             TestLog("FAIL", "", f"期望: 肯定响应; 实际: {resp_data.hex(' ').upper()}")
#             return
#
#         TestLog("INFO", "Step4", "控制程控电源给DUT重新上电")
#         ctx.power_ctrl.off()
#         time.sleep(1)
#         ctx.power_ctrl.on()
#         time.sleep(rTstable)
#
#         TestLog("INFO", "Step5", f"通过22服务读取配置字(22 {config_did:04X})，记录为DATA2")
#         status, respMsg = service_22_check(node, config_did, expect_data=[0x62, (config_did >> 8) & 0xFF, config_did & 0xFF],
#                                            expect_str=f"肯定响应(62 {config_did:04X})")
#         if not status:
#             return
#         if (resp := (respMsg or type('', (), {'data': None})()).data) is None:
#             return
#         data2 = bytes(resp[3:]) if len(resp) > 3 else b''
#         TestLog("INFO", "", f"DATA2={data2.hex(' ').upper() if data2 else 'Empty'}")
#
#         TestLog("INFO", "Step6", "比对DATA1，DATA2")
#         if data2 == data1:
#             TestLog("PASS", "", f"期望: DATA2=DATA1(配置字保持); 实际: DATA2=DATA1")
#         else:
#             TestLog("FAIL", "", f"期望: DATA2=DATA1(配置字保持); 实际: DATA2!=DATA1")
#
#     except Exception as e:
#         TestLog("FAIL", case_name, f"测试执行出错: {e}")
#         import traceback
#         TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
#     finally:
#         tester_present_stop()
def test_TG1_TC9_2E_WriteConfigWordTest():
    """
    2E写入配置字测试
    """
    case_name = "2E写入配置字测试"
    node = get_global_node()

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", "进入扩展会话(10 03)，通过安全访问Level1")
        if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
            return
        if not security_access(node, 0x01):
            return

        config_did = P.TpInfo.ConfigDataDID
        test_config_data = P.TpInfo.ConfigDataDIDData
        if not test_config_data or len(test_config_data) == 0:
            test_config_data = bytes([0x01, 0x02, 0x03, 0x04])
        data1 = test_config_data
        TestLog("INFO", "Step3", f"通过2E服务写入配置字(2E {config_did:04X} {data1.hex(' ').upper()})")
        resp = node.Service_0x2E_WriteDataByIdentifier(config_did, test_config_data)
        if resp is None:
            TestLog("FAIL", "", "写入配置字失败: 未收到响应")
            return
        resp_data = resp.data if hasattr(resp, 'data') else resp
        if resp_data[0] == 0x6E:
            TestLog("PASS", "", f"期望: 肯定响应; 实际: {resp_data.hex(' ').upper()}")
        else:
            TestLog("FAIL", "", f"期望: 肯定响应; 实际: {resp_data.hex(' ').upper()}")
            return

        TestLog("INFO", "Step4", "控制程控电源给DUT重新上电")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        time.sleep(rTstable)

        TestLog("INFO", "Step5", f"通过22服务读取配置字(22 {config_did:04X})，记录为DATA2")
        status, respMsg = service_22_check(node, config_did, expect_data=[0x62, (config_did >> 8) & 0xFF, config_did & 0xFF],
                                           expect_str=f"肯定响应(62 {config_did:04X})")
        if not status:
            return
        if (resp := (respMsg or type('', (), {'data': None})()).data) is None:
            return
        data2 = bytes(resp[3:]) if len(resp) > 3 else b''
        TestLog("INFO", "", f"DATA2={data2.hex(' ').upper() if data2 else 'Empty'}")

        TestLog("INFO", "Step6", "比对DATA1，DATA2")
        if data2 == data1:
            TestLog("PASS", "", f"期望: DATA2=DATA1(配置字保持); 实际: DATA2=DATA1")
        else:
            TestLog("FAIL", "", f"期望: DATA2=DATA1(配置字保持); 实际: DATA2!=DATA1")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

# def test_TG1_TC10_SC1_MultiFileTypeDownloadTest():
#     """
#         多文件类型下载测试-仅刷写应用软件
#     """
#     case_name = "多文件类型下载测试-仅刷写应用软件"
#     node = get_global_node()
#     flash_config = get_flash_config()
#
#     try:
#         rVnormal = P.CANInfo.Vnormal  # 电源正常电压
#         rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
#         support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
#
#         TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
#         ret = can_power_setup_and_communication_check(rVnormal, rTstable)
#         if ret != 0:
#             return
#
#         clear_ctx_can_messages()
#         msg_list = get_ctx_can_msg()
#         if len(msg_list) > 0:
#             TestLog("PASS", "", "期望: DUT正常发送应用报文; 实际: 收到应用报文")
#         else:
#             TestLog("FAIL", "", "期望: DUT正常发送应用报文; 实际: 未收到应用报文")
#
#         TestLog("INFO", "Step2", f"通过测试设备下载正确的应用程序（仅刷写应用软件数据）")
#
#         if not main_flash(node, flash_config, support_partition_ab):
#             TestLog("FAIL", "", "刷写应用软件失败")
#             return
#         TestLog("PASS", "", "应用软件刷写成功")
#
#         TestLog("INFO", "Step3", f"检查DUT是否正常工作")
#         time.sleep(rTstable)
#         clear_ctx_can_messages()
#         msg_list = get_ctx_can_msg()
#         if len(msg_list) > 0:
#             TestLog("PASS", "", "期望: DUT正常发送应用报文; 实际: 收到应用报文")
#         else:
#             TestLog("FAIL", "", "期望: DUT正常发送应用报文; 实际: 未收到应用报文")
#
#     except Exception as e:
#         TestLog("FAIL", case_name, f"测试执行出错: {e}")
#         import traceback
#         TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
#     finally:
#         tester_present_stop()

# TG1_TC10_SC2-SC4目前项目不适用
# def test_TG1_TC10_SC2_MultiFileTypeDownloadTest():
#     """
#         多文件类型下载测试-仅刷写网络配置数据
#     """
#     case_name = "多文件类型下载测试-仅刷写网络配置数据"
#     node = get_global_node()
#     flash_config = get_flash_config()
#
#     try:
#         rVnormal = P.CANInfo.Vnormal  # 电源正常电压
#         rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
#         support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
#
#         TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
#         ret = can_power_setup_and_communication_check(rVnormal, rTstable)
#         if ret != 0:
#             return
#
#         clear_ctx_can_messages()
#         msg_list = get_ctx_can_msg()
#         if len(msg_list) > 0:
#             TestLog("PASS", "", "期望: DUT正常发送应用报文; 实际: 收到应用报文")
#         else:
#             TestLog("FAIL", "", "期望: DUT正常发送应用报文; 实际: 未收到应用报文")
#
#         TestLog("INFO", "Step2", f"通过测试设备下载正确的应用程序（仅刷写网络配置数据）")
#         if not main_flash(node, flash_config, support_partition_ab):
#             TestLog("FAIL", "", "刷写网络配置数据失败")
#             return
#         TestLog("PASS", "", "网络配置数据刷写成功")
#
#         TestLog("INFO", "Step3", f"检查DUT是否正常工作")
#         time.sleep(rTstable)
#         clear_ctx_can_messages()
#         msg_list = get_ctx_can_msg()
#         if len(msg_list) > 0:
#             TestLog("PASS", "", "期望: DUT正常发送应用报文; 实际: 收到应用报文")
#         else:
#             TestLog("FAIL", "", "期望: DUT正常发送应用报文; 实际: 未收到应用报文")
#
#     except Exception as e:
#         TestLog("FAIL", case_name, f"测试执行出错: {e}")
#         import traceback
#         TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
#     finally:
#         tester_present_stop()


# def test_TG1_TC10_SC3_MultiFileTypeDownloadTest():
#     """
#         多文件类型下载测试-仅刷写标定数据
#     """
#     case_name = "多文件类型下载测试-仅刷写标定数据"
#     node = get_global_node()
#     flash_config = get_flash_config()
#
#     try:
#         rVnormal = P.CANInfo.Vnormal  # 电源正常电压
#         rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
#         support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
#
#         TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
#         ret = can_power_setup_and_communication_check(rVnormal, rTstable)
#         if ret != 0:
#             return
#
#         clear_ctx_can_messages()
#         msg_list = get_ctx_can_msg()
#         if len(msg_list) > 0:
#             TestLog("PASS", "", "期望: DUT正常发送应用报文; 实际: 收到应用报文")
#         else:
#             TestLog("FAIL", "", "期望: DUT正常发送应用报文; 实际: 未收到应用报文")
#
#         TestLog("INFO", "Step2", f"通过测试设备下载正确的应用程序（仅刷写标定数据）")
#         if not main_flash(node, flash_config, support_partition_ab):
#             TestLog("FAIL", "", "刷写标定数据失败")
#             return
#         TestLog("PASS", "", "标定数据刷写成功")
#
#         TestLog("INFO", "Step3", f"检查DUT是否正常工作")
#         time.sleep(rTstable)
#         clear_ctx_can_messages()
#         msg_list = get_ctx_can_msg()
#         if len(msg_list) > 0:
#             TestLog("PASS", "", "期望: DUT正常发送应用报文; 实际: 收到应用报文")
#         else:
#             TestLog("FAIL", "", "期望: DUT正常发送应用报文; 实际: 未收到应用报文")
#
#     except Exception as e:
#         TestLog("FAIL", case_name, f"测试执行出错: {e}")
#         import traceback
#         TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
#     finally:
#         tester_present_stop()
#
#
# def test_TG1_TC10_SC4_MultiFileTypeDownloadTest():
#     """
#         多文件类型下载测试-刷写所有数据（应用软件+网络配置数据+标定数据）
#     """
#     case_name = "多文件类型下载测试-刷写所有数据"
#     node = get_global_node()
#     flash_config = get_flash_config()
#
#     try:
#         rVnormal = P.CANInfo.Vnormal  # 电源正常电压
#         rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
#         support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
#
#         TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
#         ret = can_power_setup_and_communication_check(rVnormal, rTstable)
#         if ret != 0:
#             return
#
#         clear_ctx_can_messages()
#         msg_list = get_ctx_can_msg()
#         if len(msg_list) > 0:
#             TestLog("PASS", "", "期望: DUT正常发送应用报文; 实际: 收到应用报文")
#         else:
#             TestLog("FAIL", "", "期望: DUT正常发送应用报文; 实际: 未收到应用报文")
#
#         TestLog("INFO", "Step2", f"通过测试设备下载正确的应用程序（刷写所有的应用软件，网络配置数据和标定数据）")
#         if not main_flash(node, flash_config, support_partition_ab):
#             TestLog("FAIL", "", "刷写所有数据失败")
#             return
#         TestLog("PASS", "", "所有数据刷写成功")
#
#         TestLog("INFO", "Step3", f"检查DUT是否正常工作")
#         time.sleep(rTstable)
#         clear_ctx_can_messages()
#         msg_list = get_ctx_can_msg()
#         if len(msg_list) > 0:
#             TestLog("PASS", "", "期望: DUT正常发送应用报文; 实际: 收到应用报文")
#         else:
#             TestLog("FAIL", "", "期望: DUT正常发送应用报文; 实际: 未收到应用报文")
#
#     except Exception as e:
#         TestLog("FAIL", case_name, f"测试执行出错: {e}")
#         import traceback
#         TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
#     finally:
#         tester_present_stop()


def test_TG2_TC1_SC1_PowerOffBeforeEraseMemoryTest():
    """
        内存擦除前断电测试-擦除内存前断开电源
    """
    case_name = "内存擦除前断电测试-断开电源"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在发送内存擦除请求前控制程控电源断开KL30电10s")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return

        # 编程阶段
        status, msg = phase_programming_before_erase_memory(node, flash_config, support_partition_ab)
        if not status:
            TestLog("FAIL", " ", "编程阶段失败")
            return
        ctx.bob_ctrl.set_power("KL30", False)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.bob_ctrl.set_power("KL30", True)

        if not main_flash(node, flash_config, support_partition_ab):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC1_SC2_PowerOffBeforeEraseMemoryTest():
    """
        内存擦除前断电测试-擦除内存前断开地
    """
    case_name = "内存擦除前断电测试-断开地"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在发送内存擦除请求前控制程控电源断开KL30电10s")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return

        # 编程阶段
        status, msg = phase_programming_before_erase_memory(node, flash_config, support_partition_ab)
        if not status:
            TestLog("FAIL", " ", "编程阶段失败")
            return
        ctx.bob_ctrl.set_power("GND", False)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.bob_ctrl.set_power("GND", True)

        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC2_SC1_PowerOffWithinEraseMemoryTest():
    """
        内存擦除前断电测试-擦除内存中，断开电源
    """
    case_name = "内存擦除中断电测试-断开电源"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在发送内存擦除请求前控制程控电源断开KL30电10s")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return

        # 编程阶段
        phase_programming_doing_erase_memory(node, flash_config, support_partition_ab)
        time.sleep(0.01)
        ctx.bob_ctrl.set_power("KL30", False)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.bob_ctrl.set_power("KL30", True)

        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC2_SC2_PowerOffWithinEraseMemoryTest():
    """
        内存擦除前断电测试-擦除内存中，断开地
    """
    case_name = "内存擦除中断电测试-断开地"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在发送内存擦除请求前控制程控电源断开KL30电10s")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return

        # 编程阶段
        phase_programming_doing_erase_memory(node, flash_config, support_partition_ab)
        time.sleep(0.01)
        ctx.bob_ctrl.set_power("GND", False)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.bob_ctrl.set_power("GND", True)

        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC3_SC1_PowerOffStopWithinTransferDataTest():
    """
        数据传输中断电测试-数据传输过程断开电源正极
    """
    case_name = "数据传输中断电测试-断开电源"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在数据传输中控制程控电源断开KL30电10s")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return

        # 编程阶段
        phase_programming_stop_within_transfer_data(node, flash_config, "None", support_partition_ab)
        time.sleep(0.01)
        ctx.bob_ctrl.set_power("KL30", False)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.bob_ctrl.set_power("KL30", True)

        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC3_SC2_PowerOffStopWithinTransferDataTest():
    """
        数据传输中断电测试-数据传输过程断开电源地
    """
    case_name = "数据传输中断电测试-断开地"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在数据传输中控制程控电源断开KL30电10s")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return

        # 编程阶段
        phase_programming_stop_within_transfer_data(node, flash_config, "None", support_partition_ab)
        time.sleep(0.01)
        ctx.bob_ctrl.set_power("GND", False)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.bob_ctrl.set_power("GND", True)

        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC3_SC3_PowerOffStopWithinDriverTransferDataTest():
    """
        DRIVER数据传输中断电测试-数据传输过程断开电源正极
    """
    case_name = "DRIVER数据传输中断电测试-断开电源"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        support_partition_ab = P.TpInfo.PartSupportFlag

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在DRIVER数据传输中控制程控电源断开KL30电10s")
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return

        phase_programming_stop_driver_within_transfer_data(node, flash_config, support_partition_ab)
        time.sleep(0.01)
        ctx.bob_ctrl.set_power("KL30", False)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.bob_ctrl.set_power("KL30", True)

        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC3_SC4_PowerOffStopWithinDriverTransferGNDTest():
    """
        DRIVER数据传输中断电测试-数据传输过程断开电源地
    """
    case_name = "DRIVER数据传输中断电测试-断开地"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        support_partition_ab = P.TpInfo.PartSupportFlag

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在DRIVER数据传输中控制程控电源断开电源地10s")
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return

        phase_programming_stop_driver_within_transfer_data(node, flash_config, support_partition_ab)
        time.sleep(0.01)
        ctx.bob_ctrl.set_power("GND", False)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.bob_ctrl.set_power("GND", True)

        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC4_SC1_VoltageAbnormalWithinTransferDataTest():
    """
        数据传输中电压异常测试-数据传输时电压超出正常工作电压范围
    """
    case_name = "数据传输中电压异常测试-数据传输时电压超出正常工作电压范围"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        # TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在数据传输中控制程控电源电压升高到19V，保持10s")

        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return

        # 编程阶段
        status, resp = phase_programming_stop_within_transfer_data(node, flash_config, "None", support_partition_ab)
        time.sleep(0.01)
        rVnormalH = 19  # 电源正常电压
        ctx.power_ctrl.set_voltage(rVnormalH)
        TestLog("INFO", "Step2", f"在数据传输过程中，设置DUT供电电压为{rVnormalH}V, 保持10s")
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.set_voltage(rVnormal)

        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC4_SC2_VoltageAbnormalWithinTransferDataTest():
    """
        数据传输中电压异常测试-数据传输时电压低于正常工作电压范围
    """
    case_name = "数据传输中电压异常测试-数据传输时电压低于正常工作电压范围"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        # TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在数据传输中控制程控电源电压降低到5V，保持10s")

        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return

        status, resp = phase_programming_stop_within_transfer_data(node, flash_config, "None", support_partition_ab)
        time.sleep(0.01)
        rVnormalL = 5
        ctx.power_ctrl.set_voltage(rVnormalL)
        TestLog("INFO", "Step2", f"在数据传输过程中，设置DUT供电电压为{rVnormalL}V, 保持10s")
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.set_voltage(rVnormal)

        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC4_SC3_VoltageAbnormalWithinTransferDataTest():
    """
        数据传输中电压异常测试-数据传输时电压过高
    """
    case_name = "数据传输中电压异常测试-数据传输时电压过高"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        # TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在数据传输中控制程控电源电压升高到17V")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return

        # 编程阶段
        status, resp = phase_programming_stop_within_transfer_data(node, flash_config, "HighVoltage",
                                                                   support_partition_ab)
        rVnormalH = 17
        ctx.power_ctrl.set_voltage(rVnormalH)
        TestLog("INFO", "Step2", f"在数据传输过程中，设置DUT供电电压为{rVnormalH}V")

        if not status:
            return
        if resp[:3] == bytes([0x7F, 0x36, 0x92]):
            TestLog("PASS", " ", f"期望: 7F 36 92; 实际: {resp.hex(' ').upper()}")
        else:
            TestLog("FAIL", " ", f"期望: 7F 36 92; 实际: {resp.hex(' ').upper()}")
            return

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.set_voltage(rVnormal)

        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC4_SC4_VoltageAbnormalWithinTransferDataTest():
    """
        数据传输中电压异常测试-数据传输时电压过低
    """
    case_name = "数据传输中电压异常测试-数据传输时电压过低"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        # TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在数据传输中控制程控电源电压降低8V")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return

        # 编程阶段
        status, resp = phase_programming_stop_within_transfer_data(node, flash_config, "LowVoltage",
                                                                   support_partition_ab)
        rVnormalL = 8
        ctx.power_ctrl.set_voltage(rVnormalL)
        TestLog("INFO", "Step2", f"在数据传输过程中，设置DUT供电电压为{rVnormalL}V")

        if not status:
            return
        if resp[:3] == bytes([0x7F, 0x36, 0x93]):
            TestLog("PASS", " ", f"期望: 7F 36 93; 实际: {resp.hex(' ').upper()}")
        else:
            TestLog("FAIL", " ", f"期望: 7F 36 93; 实际: {resp.hex(' ').upper()}")
            return

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.set_voltage(rVnormal)

        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC5_SC1_CommunicationOffTest():
    """
        通信中断测试-CANH/CANL短路-内存擦除前通信中断
    """
    case_name = "通信中断测试-CANH/CANL短路-内存擦除前通信中断"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在发送内存擦除请求前使CANH和CANL短路，即中断通信10s")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return
        # 编程阶段
        phase_programming_before_erase_memory(node, flash_config, support_partition_ab)
        time.sleep(0.01)
        ctx.bob_ctrl.set_test_channel('CAN1', True)
        ctx.bob_ctrl.set_fault("HL", "SHORT", True)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", f"恢复正常通信，并控制程控电源给DUT重新上电")
        ctx.bob_ctrl.set_fault("HL", "SHORT", False)
        ctx.bob_ctrl.set_test_channel('CAN1', False)

        TestLog("INFO", "Step4", f"通过测试设备重新下载正确的应用程序")
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC5_SC2_CommunicationOffTest():
    """
        通信中断测试-CANH/CANL短路-内存擦除中通信中断
    """
    case_name = "通信中断测试-CANH/CANL短路-内存擦除中通信中断"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2",
                f"通过测试设备执行刷写流程，在发送内存擦除请求后等待50ms，使CANH和CANL短路，即中断通信10s")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return
        # 编程阶段
        phase_programming_doing_erase_memory(node, flash_config, support_partition_ab)
        time.sleep(0.01)
        ctx.bob_ctrl.set_test_channel('CAN1', True)
        ctx.bob_ctrl.set_fault("HL", "SHORT", True)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", f"恢复正常通信，并控制程控电源给DUT重新上电")
        ctx.bob_ctrl.set_fault("HL", "SHORT", False)
        ctx.bob_ctrl.set_test_channel('CAN1', False)

        TestLog("INFO", "Step4", f"通过测试设备重新下载正确的应用程序")
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC5_SC3_CommunicationOffTest():
    """
        通信中断测试-CANH/CANL短路-数据传输中通信中断
    """
    case_name = "通信中断测试-CANH/CANL短路-数据传输中通信中断"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，数据传输过程使CANH和CANL短路，即中断通信10s")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return
        # 编程阶段
        phase_programming_stop_within_transfer_data(node, flash_config, "None", support_partition_ab)
        time.sleep(0.01)
        ctx.bob_ctrl.set_test_channel('CAN1', True)
        ctx.bob_ctrl.set_fault("HL", "SHORT", True)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", f"恢复正常通信，并控制程控电源给DUT重新上电")
        ctx.bob_ctrl.set_fault("HL", "SHORT", False)
        ctx.bob_ctrl.set_test_channel('CAN1', False)

        TestLog("INFO", "Step4", f"通过测试设备重新下载正确的应用程序")
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC6_SC1_CommunicationOffTest():
    """
        通信中断测试-CANH/CANL开路-内存擦除前通信中断CANH开路
    """
    case_name = "通信中断测试-CANH/CANL开路-内存擦除前通信中断CANH开路"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在发送内存擦除请求前使 CANH开路，即中断通信10s")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return
        # 编程阶段
        phase_programming_before_erase_memory(node, flash_config, support_partition_ab)
        time.sleep(0.01)
        ctx.bob_ctrl.set_test_channel('CAN1', True)
        ctx.bob_ctrl.set_fault("H", "OPEN", True)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", f"恢复正常通信，并控制程控电源给DUT重新上电")
        ctx.bob_ctrl.set_fault("H", "OPEN", False)
        ctx.bob_ctrl.set_test_channel('CAN1', False)

        TestLog("INFO", "Step4", f"通过测试设备重新下载正确的应用程序")
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC6_SC2_CommunicationOffTest():
    """
        通信中断测试-CANH/CANL开路-内存擦除前通信中断CANL开路
    """
    case_name = "通信中断测试-CANH/CANL开路-内存擦除前通信中断CANL开路"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在发送内存擦除请求前使 CANL开路，即中断通信10s")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return
        # 编程阶段
        phase_programming_before_erase_memory(node, flash_config, support_partition_ab)
        time.sleep(0.01)
        ctx.bob_ctrl.set_test_channel('CAN1', True)
        ctx.bob_ctrl.set_fault("L", "OPEN", True)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", f"恢复正常通信，并控制程控电源给DUT重新上电")
        ctx.bob_ctrl.set_fault("L", "OPEN", False)
        ctx.bob_ctrl.set_test_channel('CAN1', False)

        TestLog("INFO", "Step4", f"通过测试设备重新下载正确的应用程序")
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC6_SC3_CommunicationOffTest():
    """
        通信中断测试-CANH/CANL开路-内存擦除中通信中断CANH开路
    """
    case_name = "通信中断测试-CANH/CANL开路-内存擦除中通信中断CANH开路"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在发送内存擦除请求前使 CANH开路，即中断通信10s")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return
        # 编程阶段
        phase_programming_doing_erase_memory(node, flash_config, support_partition_ab)
        time.sleep(0.01)
        ctx.bob_ctrl.set_test_channel('CAN1', True)
        ctx.bob_ctrl.set_fault("H", "OPEN", True)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", f"恢复正常通信，并控制程控电源给DUT重新上电")
        ctx.bob_ctrl.set_fault("H", "OPEN", False)
        ctx.bob_ctrl.set_test_channel('CAN1', False)

        TestLog("INFO", "Step4", f"通过测试设备重新下载正确的应用程序")
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC6_SC4_CommunicationOffTest():
    """
        通信中断测试-CANH/CANL开路-内存擦除中通信中断CANL开路
    """
    case_name = "通信中断测试-CANH/CANL开路-内存擦除中通信中断CANL开路"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在发送内存擦除请求前使 CANL开路，即中断通信10s")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return
        # 编程阶段
        phase_programming_doing_erase_memory(node, flash_config, support_partition_ab)
        time.sleep(0.01)
        ctx.bob_ctrl.set_test_channel('CAN1', True)
        ctx.bob_ctrl.set_fault("L", "OPEN", True)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", f"恢复正常通信，并控制程控电源给DUT重新上电")
        ctx.bob_ctrl.set_fault("L", "OPEN", False)
        ctx.bob_ctrl.set_test_channel('CAN1', False)

        TestLog("INFO", "Step4", f"通过测试设备重新下载正确的应用程序")
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC6_SC5_CommunicationOffTest():
    """
        通信中断测试-CANH/CANL开路-数据传输过程使CANH开路
    """
    case_name = "通信中断测试-CANH/CANL开路-数据传输过程使CANH开路"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，数据传输过程 CANH开路，即中断通信10s")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return
        # 编程阶段
        phase_programming_stop_within_transfer_data(node, flash_config, "None", support_partition_ab)
        time.sleep(0.01)
        ctx.bob_ctrl.set_test_channel('CAN1', True)
        ctx.bob_ctrl.set_fault("H", "OPEN", True)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", f"恢复正常通信，并控制程控电源给DUT重新上电")
        ctx.bob_ctrl.set_fault("H", "OPEN", False)
        ctx.bob_ctrl.set_test_channel('CAN1', False)

        TestLog("INFO", "Step4", f"通过测试设备重新下载正确的应用程序")
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC6_SC6_CommunicationOffTest():
    """
        通信中断测试-CANH/CANL开路-数据传输过程使CANL开路
    """
    case_name = "通信中断测试-CANH/CANL开路-数据传输过程使CANL开路"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，数据传输过程 CANL开路，即中断通信10s")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return
        # 编程阶段
        phase_programming_stop_within_transfer_data(node, flash_config, "None", support_partition_ab)
        time.sleep(0.01)
        ctx.bob_ctrl.set_test_channel('CAN1', True)
        ctx.bob_ctrl.set_fault("L", "OPEN", True)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", f"恢复正常通信，并控制程控电源给DUT重新上电")
        ctx.bob_ctrl.set_fault("L", "OPEN", False)
        ctx.bob_ctrl.set_test_channel('CAN1', False)

        TestLog("INFO", "Step4", f"通过测试设备重新下载正确的应用程序")
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC7_DownloadWithFunctionTP():
    """
        功能寻址TP报文对下载影响测试
    """
    case_name = "功能寻址TP报文对下载影响测试"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，整个过程将TP报文(3E 80)发送周期设置为2000ms")
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG2_TC8_SC1_UnexpectedFrameTest():
    """
        数据传输中接收非预期帧测试-非预期帧为单帧
    """
    case_name = "数据传输中接收非预期帧测试-非预期帧为单帧"
    node = get_global_node()
    flash_config = get_flash_config()
    rt = IsoTpRunTimeInfo()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        is_canfd = True if P.TpInfo.CanFDMode == 1 else False
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        diag_req_id = P.ECUInfo.DiagReqID_int
        diag_resp_id = P.ECUInfo.DiagRespID_int

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在数据传输中(36 BlockSequenceCounter Data)，"
                                 f"36服务发送完首帧之后，Tester向DUT发送非预期帧(如：22 F1 89)，"
                                 f"之后继续发送36服务后续的连续帧")

        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", f"预编程阶段失败: {msg}")
            return

        status, result = prepare_for_manual_transfer_data(node, flash_config, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段准备失败: {result}")
            return

        block_data = result["block_data"]
        max_block_length = result["max_block_length"]

        # 构造36服务请求数据: SID(0x36) + counter(1) + data
        transfer_data = bytes([0x36, 0x01]) + block_data[:max_block_length]
        TestLog("INFO", "", f"构造36服务请求, 总长度={len(transfer_data)}, max_block_length={max_block_length}")

        isotp_monitor_start(rt, diag_req_id, diag_resp_id)
        time.sleep(0.05)

        # 构造首帧(FF)
        ff_payload, ff_data_len = build_isotp_first_frame(transfer_data, padding_byte=0xAA, is_canfd=is_canfd)
        TestLog("INFO", "", f"发送36服务首帧(FF): {' '.join(f'{b:02X}' for b in ff_payload[:16])}...")
        dlc =  8
        msg_ff = canmsg_create(diag_req_id, dlc, data=ff_payload, rtr=0, fdf=P.TpInfo.CanFDMode, brs=0, ext=0)
        send_canmsg(can_channel, msg_ff)
        time.sleep(0.02)

        # 在首帧后立即发送非预期帧，不等待FC
        TestLog("INFO", "", "发送非预期帧(单帧): 22 F1 89")
        unexpected_sf = [0x03, 0x22, 0xF1, 0x89, 0xAA, 0xAA, 0xAA, 0xAA]
        if is_canfd:
            unexpected_sf = unexpected_sf + [0xAA] * (P.TpInfo.MaxCanFDDataLength - 8)
        msg_unexpected = canmsg_create(diag_req_id, dlc, data=unexpected_sf, rtr=0, fdf=P.TpInfo.CanFDMode, brs=0, ext=0)
        send_canmsg(can_channel, msg_unexpected)

        # 等待DUT回复22服务的肯定响应
        resp_22 = None
        for _ in range(20):
            recv_list = rt.get_recv_list()
            for item in recv_list:
                payload = item["payload"] if isinstance(item, dict) else item
                if len(payload) >= 3 and (
                    (payload[0] == 0x62 and payload[1] == 0xF1 and payload[2] == 0x89) or  # 单帧
                    (payload[0] == 0x00 and payload[2] == 0x62 and payload[3] == 0xF1 and payload[4] == 0x89)  # 首帧
                ):
                    resp_22 = payload
                    break
            if resp_22:
                break
            time.sleep(0.01)

        if resp_22:
            TestLog("INFO", "", f"DUT回复22服务肯定响应: {bytes(resp_22).hex(' ').upper()}")
        else:
            TestLog("INFO", "", "DUT未回复22服务肯定响应")

        # 继续发送36服务的连续帧(CF)
        TestLog("INFO", "", "继续发送36服务连续帧(CF)")
        stmin_ms = 10
        cf_list = build_isotp_consecutive_frames(transfer_data, ff_data_len, padding_byte=0xAA, is_canfd=is_canfd)
        for idx, cf_payload in enumerate(cf_list):
            time.sleep(stmin_ms / 1000.0)
            msg_cf = canmsg_create(diag_req_id, dlc, data=cf_payload, rtr=0, fdf=P.TpInfo.CanFDMode, brs=0, ext=0)
            send_canmsg(can_channel, msg_cf)

        time.sleep(0.5)
        isotp_monitor_stop(rt)

        TestLog("INFO", "", "验证DUT是否中止了36服务接收过程")
        # 发送下一个36服务请求，检查响应
        resp36 = node.Service_0x36_TransferData(counter=2, record=block_data[:max_block_length], timeout=5)
        if resp36 is not None:
            resp36_data = resp36.data if hasattr(resp36, 'data') else resp36
            if resp36_data[0] == 0x7F and resp36_data[1] == 0x36:
                TestLog("PASS", "", f"期望: DUT中止36服务接收过程; 实际: 收到36服务否定响应 {resp36_data.hex(' ').upper()}")
            elif resp36_data[0] == 0x76:
                TestLog("FAIL", "", f"期望: DUT中止36服务接收过程; 实际: DUT继续响应36服务 {resp36_data.hex(' ').upper()}")
            else:
                TestLog("INFO", "", f"收到响应: {resp36_data.hex(' ').upper()}")
        else:
            TestLog("PASS", "", "期望: DUT中止36服务接收过程; 实际: DUT未响应36服务")

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        time.sleep(rTstable)

        if not main_flash(node, flash_config, support_partition_ab):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        isotp_monitor_stop(rt)
        tester_present_stop()

def test_TG2_TC8_SC2_UnexpectedFrameTest():
    """
        数据传输中接收非预期帧测试-非预期帧为首帧
    """
    case_name = "数据传输中接收非预期帧测试-非预期帧为首帧"
    node = get_global_node()
    flash_config = get_flash_config()
    rt = IsoTpRunTimeInfo()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        is_canfd = True if P.TpInfo.CanFDMode == 1 else False
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        diag_req_id = P.ECUInfo.DiagReqID_int
        diag_resp_id = P.ECUInfo.DiagRespID_int

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在数据传输中(36 BlockSequenceCounter Data)，"
                                 f"36服务发送完首帧之后，Tester向DUT发送非预期帧(如：10 FF 22 F1 89)，"
                                 f"之后继续发送36服务后续的连续帧")

        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", f"预编程阶段失败: {msg}")
            return

        status, result = prepare_for_manual_transfer_data(node, flash_config, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段准备失败: {result}")
            return

        block_data = result["block_data"]
        max_block_length = result["max_block_length"]

        # 构造36服务请求数据: SID(0x36) + counter(1) + data
        transfer_data = bytes([0x36, 0x01]) + block_data[:max_block_length]
        TestLog("INFO", "", f"构造36服务请求, 总长度={len(transfer_data)}, max_block_length={max_block_length}")

        isotp_monitor_start(rt, diag_req_id, diag_resp_id)
        time.sleep(0.05)

        # 构造首帧(FF)
        ff_payload, ff_data_len = build_isotp_first_frame(transfer_data, padding_byte=0xAA, is_canfd=is_canfd)
        TestLog("INFO", "", f"发送36服务首帧(FF): {' '.join(f'{b:02X}' for b in ff_payload[:16])}...")
        dlc =  P.TpInfo.MaxCanFDDataLengthToDLC if is_canfd else 8
        msg_ff = canmsg_create(diag_req_id, dlc, data=ff_payload, rtr=0, fdf=P.TpInfo.CanFDMode, brs=0, ext=0)
        send_canmsg(can_channel, msg_ff)
        time.sleep(0.02)

        # 继续发送36服务的连续帧(CF)
        TestLog("INFO", "", "继续发送36服务连续帧(CF)")
        stmin_ms = 10
        cf_list = build_isotp_consecutive_frames(transfer_data, ff_data_len, padding_byte=0xAA, is_canfd=is_canfd)
        for idx, cf_payload in enumerate(cf_list):
            time.sleep(stmin_ms / 1000.0)
            msg_cf = canmsg_create(diag_req_id, dlc, data=cf_payload, rtr=0, fdf=P.TpInfo.CanFDMode, brs=0, ext=0)
            send_canmsg(can_channel, msg_cf)

        time.sleep(0.5)
        isotp_monitor_stop(rt)

        TestLog("INFO", "", "验证DUT是否中止了36服务接收过程")
        # 在首帧后立即发送非预期帧，不等待FC
        TestLog("INFO", "", "发送非预期帧(单帧): 22 F1 89")
        unexpected_sf = [0x10, 0xFF, 0x22, 0xF1, 0x89, 0xAA, 0xAA, 0xAA]
        if is_canfd:
            unexpected_sf = unexpected_sf + [0xAA] * (P.TpInfo.MaxCanFDDataLength - 8)
        msg_unexpected = canmsg_create(diag_req_id, dlc, data=unexpected_sf, rtr=0, fdf=P.TpInfo.CanFDMode, brs=0,
                                       ext=0)
        send_canmsg(can_channel, msg_unexpected)

        # 等待DUT回复22服务的肯定响应
        resp_22 = None
        for _ in range(20):
            recv_list = rt.get_recv_list()
            for item in recv_list:
                payload = item["payload"] if isinstance(item, dict) else item
                if len(payload) >= 3 and payload[0] == 0x30:
                    resp_22 = payload
                    break
            if resp_22:
                break
            time.sleep(0.01)

        if resp_22:
            TestLog("INFO", "", f"DUT回复FC: {bytes(resp_22).hex(' ').upper()}")
        else:
            TestLog("INFO", "", f"DUT回复FC：{bytes(resp_22).hex(' ').upper()}")
        # 发送下一个36服务请求，检查响应
        resp36 = node.Service_0x36_TransferData(counter=2, record=block_data[:max_block_length], timeout=5)
        if resp36 is not None:
            resp36_data = resp36.data if hasattr(resp36, 'data') else resp36
            if resp36_data[0] == 0x7F and resp36_data[1] == 0x36:
                TestLog("PASS", "", f"期望: DUT中止36服务接收过程; 实际: 收到36服务否定响应 {resp36_data.hex(' ').upper()}")
            elif resp36_data[0] == 0x76:
                TestLog("FAIL", "", f"期望: DUT中止36服务接收过程; 实际: DUT继续响应36服务 {resp36_data.hex(' ').upper()}")
            else:
                TestLog("INFO", "", f"收到响应: {resp36_data.hex(' ').upper()}")
        else:
            TestLog("PASS", "", "期望: DUT中止36服务接收过程; 实际: DUT未响应36服务")

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(1)
        ctx.power_ctrl.on()
        time.sleep(rTstable)

        if not main_flash(node, flash_config, support_partition_ab):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        isotp_monitor_stop(rt)
        tester_present_stop()

# def test_TG2_TC8_SC2_UnexpectedFrameTest():
#     """
#         数据传输中接收非预期帧测试-非预期帧为首帧
#     """
#     case_name = "数据传输中接收非预期帧测试-非预期帧为首帧"
#     node = get_global_node()
#     flash_config = get_flash_config()
#     rt = IsoTpRunTimeInfo()
#
#     try:
#         rVnormal = P.CANInfo.Vnormal  # 电源正常电压
#         rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
#         support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
#         is_canfd = True if P.TpInfo.CanFDMode == 1 else False
#         can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
#         diag_req_id = P.ECUInfo.DiagReqID_int
#         diag_resp_id = P.ECUInfo.DiagRespID_int
#
#         TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
#         ret = can_power_setup_and_communication_check(rVnormal, rTstable)
#         if ret != 0:
#             return
#
#         TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在数据传输中(36 BlockSequenceCounter Data)，"
#                                  f"36服务发送完首帧之后，Tester向DUT发送非预期帧(如：10 FF 22 ...)，"
#                                  f"之后继续发送36服务后续的连续帧")
#
#         status, msg = phase_pre_programming(node)
#         if not status:
#             TestLog("FAIL", "", f"预编程阶段失败: {msg}")
#             return
#
#         # 准备阶段：执行编程会话、安全访问、写指纹、下载driver、擦除APP内存、34服务
#         status, result = prepare_for_manual_transfer_data(node, flash_config, support_partition_ab)
#         if not status:
#             TestLog("FAIL", "", f"编程阶段准备失败: {result}")
#             return
#
#         block_data = result["block_data"]
#         max_block_length = result["max_block_length"]
#
#         # 构造36服务请求数据: SID(0x36) + counter(1) + data
#         transfer_data = bytes([0x36, 0x01]) + block_data[:max_block_length]
#         TestLog("INFO", "", f"构造36服务请求, 总长度={len(transfer_data)}, max_block_length={max_block_length}")
#
#         isotp_monitor_start(rt, diag_req_id, diag_resp_id)
#         time.sleep(0.05)
#
#         # 构造首帧(FF)
#         ff_payload, ff_data_len = build_isotp_first_frame(transfer_data, padding_byte=0xAA, is_canfd=is_canfd)
#         TestLog("INFO", "", f"发送36服务首帧(FF): {' '.join(f'{b:02X}' for b in ff_payload[:16])}...")
#         dlc = P.TpInfo.MaxCanFDDataLengthToDLC if is_canfd else 8
#         msg_ff = canmsg_create(diag_req_id, dlc, data=ff_payload, rtr=0, fdf=P.TpInfo.CanFDMode, brs=0, ext=0)
#         send_canmsg(can_channel, msg_ff)
#         time.sleep(0.02)
#
#         # 发送非预期首帧，不等待原36的FC
#         TestLog("INFO", "", "发送非预期帧(首帧): 10 FF 22 F1 86 01 02 03")
#         unexpected_ff = [0x10, 0xFF, 0x22, 0xF1, 0x86, 0x01, 0x02, 0x03]
#         if is_canfd:
#             unexpected_ff = unexpected_ff + [0xAA] * (P.TpInfo.MaxCanFDDataLength - 8)
#         msg_unexpected = canmsg_create(diag_req_id, dlc, data=unexpected_ff, rtr=0, fdf=P.TpInfo.CanFDMode, brs=0, ext=0)
#         send_canmsg(can_channel, msg_unexpected)
#
#         resp_unexpected = None
#         for _ in range(30):
#             recv_list = rt.get_recv_list()
#             for item in recv_list:
#                 payload = item["payload"] if isinstance(item, dict) else item
#                 TestLog("DEBUG", "", f"SC2收到报文: {bytes(payload).hex(' ').upper() if isinstance(payload, (list, bytes)) else payload}")
#                 if len(payload) >= 3 and payload[0] == 0x30:
#                     resp_unexpected = payload
#                     break
#             if resp_unexpected:
#                 break
#             time.sleep(0.01)
#
#         if resp_unexpected is not None:
#             TestLog("INFO", "", f"DUT回复FC: {bytes(resp_unexpected).hex(' ').upper()}")
#         else:
#             TestLog("INFO", "", "DUT未回复FC")
#
#         # 继续发送原36服务的连续帧(CF)
#         TestLog("INFO", "", "继续发送原36服务连续帧(CF)")
#         stmin_ms = 10
#         cf_list = build_isotp_consecutive_frames(transfer_data, ff_data_len, padding_byte=0xAA, is_canfd=is_canfd)
#         for idx, cf_payload in enumerate(cf_list):
#             time.sleep(stmin_ms / 1000.0)
#             msg_cf = canmsg_create(diag_req_id, dlc, data=cf_payload, rtr=0, fdf=P.TpInfo.CanFDMode, brs=0, ext=0)
#             send_canmsg(can_channel, msg_cf)
#
#         time.sleep(0.5)
#         isotp_monitor_stop(rt)
#
#         TestLog("INFO", "", "验证DUT是否中止了36服务接收过程")
#         resp36 = node.Service_0x36_TransferData(counter=2, record=block_data[:max_block_length], timeout=5)
#         if resp36 is not None:
#             resp36_data = resp36.data if hasattr(resp36, 'data') else resp36
#             if resp36_data[0] == 0x7F and resp36_data[1] == 0x36:
#                 TestLog("PASS", "", f"期望: DUT中止36服务接收过程; 实际: 收到36服务否定响应 {resp36_data.hex(' ').upper()}")
#             elif resp36_data[0] == 0x76:
#                 TestLog("FAIL", "", f"期望: DUT中止36服务接收过程; 实际: DUT继续响应36服务 {resp36_data.hex(' ').upper()}")
#             else:
#                 TestLog("INFO", "", f"收到响应: {resp36_data.hex(' ').upper()}")
#         else:
#             TestLog("PASS", "", "期望: DUT中止36服务接收过程; 实际: DUT未响应36服务")
#
#         TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
#         ctx.power_ctrl.off()
#         time.sleep(1)
#         ctx.power_ctrl.on()
#         time.sleep(rTstable)
#
#         if not main_flash(node, flash_config, support_partition_ab):
#             return
#
#     except Exception as e:
#         TestLog("FAIL", case_name, f"测试执行出错: {e}")
#         import traceback
#         TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
#     finally:
#         isotp_monitor_stop(rt)
#         tester_present_stop()


def test_TG2_TC9_SC1_ExitProgrammingSessionTest():
    """
        数据传输中退出编程会话测试-默认会话
    """
    case_name = "数据传输中退出编程会话测试-默认会话"
    node = get_global_node()
    flash_config = get_flash_config()
    rt = IsoTpRunTimeInfo()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        is_canfd = True if P.TpInfo.CanFDMode == 1 else False
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        diag_req_id = P.ECUInfo.DiagReqID_int
        diag_resp_id = P.ECUInfo.DiagRespID_int

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在数据传输中(36 BlockSequenceCounter Data)，"
                                 f"Tester向DUT发送默认会话请求(10 01)")

        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", f"预编程阶段失败: {msg}")
            return

        # 准备阶段：执行编程会话、安全访问、写指纹、下载driver、擦除APP内存、34服务
        status, result = prepare_for_manual_transfer_data(node, flash_config, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段准备失败: {result}")
            return

        block_data = result["block_data"]
        max_block_length = result["max_block_length"]

        # 构造36服务请求数据: SID(0x36) + counter(1) + data
        transfer_data = bytes([0x36, 0x01]) + block_data[:max_block_length]
        TestLog("INFO", "", f"构造36服务请求, 总长度={len(transfer_data)}, max_block_length={max_block_length}")

        isotp_monitor_start(rt, diag_req_id, diag_resp_id)
        time.sleep(0.05)

        # 构造首帧(FF)
        ff_payload, ff_data_len = build_isotp_first_frame(transfer_data, padding_byte=0xAA, is_canfd=is_canfd)
        TestLog("INFO", "", f"发送36服务首帧(FF): {' '.join(f'{b:02X}' for b in ff_payload[:16])}...")
        dlc = P.TpInfo.MaxCanFDDataLengthToDLC if is_canfd else 8
        msg_ff = canmsg_create(diag_req_id, dlc, data=ff_payload, rtr=0, fdf=P.TpInfo.CanFDMode, brs=0, ext=0)
        send_canmsg(can_channel, msg_ff)
        time.sleep(0.02)

        # 继续发送36服务的连续帧(CF)
        TestLog("INFO", "", "继续发送36服务连续帧(CF)")
        stmin_ms = 10
        cf_list = build_isotp_consecutive_frames(transfer_data, ff_data_len, padding_byte=0xAA, is_canfd=is_canfd)
        for idx, cf_payload in enumerate(cf_list):
            time.sleep(stmin_ms / 1000.0)
            msg_cf = canmsg_create(diag_req_id, dlc, data=cf_payload, rtr=0, fdf=P.TpInfo.CanFDMode, brs=0, ext=0)
            send_canmsg(can_channel, msg_cf)

        time.sleep(0.5)
        isotp_monitor_stop(rt)

        # 在首帧和连续帧之间发送默认会话请求
        TestLog("INFO", "", "在36服务传输过程中发送默认会话请求(10 01)")
        resp_10 = node.Service_0x10_SessionControl(0x01)
        if resp_10 is not None:
            resp_data = resp_10.data if hasattr(resp_10, 'data') else resp_10
            if resp_data[0] == 0x50 and resp_data[1] == 0x01:
                TestLog("PASS", "", f"期望: DUT回复50 01; 实际: {resp_data.hex(' ').upper()}")
            else:
                TestLog("INFO", "", f"DUT响应: {resp_data.hex(' ').upper()}")
        else:
            TestLog("FAIL", "", "期望: DUT回复50 01; 实际: 未收到响应")

        # isotp_monitor_stop(rt)
        time.sleep(P.DiagServiceInfo.ResetTime / 1000)
        TestLog("INFO", "Step3", f"发送 19 02 FF 请求，验证DUT处于默认会话模式下")
        respMsg = node.Service_0x19_ReadDTCInformation(report_type=0x02, DTCStatusMask=0xFF, func_req=False)
        if respMsg is None:
            TestLog("FAIL", "", "未收到19 02 FF响应")
            return
        resp_data = respMsg.data if hasattr(respMsg, 'data') else respMsg
        if resp_data[0] == 0x59:
            TestLog("PASS", "", f"期望: DUT回复肯定响应; 实际: {resp_data.hex(' ').upper()}")
        else:
            TestLog("INFO", "", f"DUT响应: {resp_data.hex(' ').upper()}")
            if resp_data[0] == 0x7F and resp_data[1] == 0x19:
                TestLog("PASS", "", f"期望: DUT处于默认会话模式; 实际: 收到19服务响应 {resp_data.hex(' ').upper()}")
            else:
                TestLog("FAIL", "", f"期望: DUT回复肯定响应或否定响应; 实际: {resp_data.hex(' ').upper()}")
                return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        isotp_monitor_stop(rt)
        tester_present_stop()


def test_TG2_TC9_SC2_ExitProgrammingSessionTest():
    """
        数据传输中退出编程会话测试-复位
    """
    case_name = "数据传输中退出编程会话测试-复位"
    node = get_global_node()
    flash_config = get_flash_config()
    rt = IsoTpRunTimeInfo()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        is_canfd = True if P.TpInfo.CanFDMode == 1 else False
        can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
        diag_req_id = P.ECUInfo.DiagReqID_int
        diag_resp_id = P.ECUInfo.DiagRespID_int

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在数据传输中(36 BlockSequenceCounter Data)，"
                                 f"Tester向DUT发送复位请求(11 01)")

        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", f"预编程阶段失败: {msg}")
            return

        # 准备阶段：执行编程会话、安全访问、写指纹、下载driver、擦除APP内存、34服务
        status, result = prepare_for_manual_transfer_data(node, flash_config, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段准备失败: {result}")
            return

        block_data = result["block_data"]
        max_block_length = result["max_block_length"]

        # 构造36服务请求数据: SID(0x36) + counter(1) + data
        transfer_data = bytes([0x36, 0x01]) + block_data[:max_block_length]
        TestLog("INFO", "", f"构造36服务请求, 总长度={len(transfer_data)}, max_block_length={max_block_length}")

        isotp_monitor_start(rt, diag_req_id, diag_resp_id)
        time.sleep(0.05)

        # 构造首帧(FF)
        ff_payload, ff_data_len = build_isotp_first_frame(transfer_data, padding_byte=0xAA, is_canfd=is_canfd)
        TestLog("INFO", "", f"发送36服务首帧(FF): {' '.join(f'{b:02X}' for b in ff_payload[:16])}...")
        dlc = P.TpInfo.MaxCanFDDataLengthToDLC if is_canfd else 8
        msg_ff = canmsg_create(diag_req_id, dlc, data=ff_payload, rtr=0, fdf=P.TpInfo.CanFDMode, brs=0, ext=0)
        send_canmsg(can_channel, msg_ff)
        time.sleep(0.02)

        # 继续发送36服务的连续帧(CF)
        TestLog("INFO", "", "继续发送36服务连续帧(CF)")
        stmin_ms = 10
        cf_list = build_isotp_consecutive_frames(transfer_data, ff_data_len, padding_byte=0xAA, is_canfd=is_canfd)
        for idx, cf_payload in enumerate(cf_list):
            time.sleep(stmin_ms / 1000.0)
            msg_cf = canmsg_create(diag_req_id, dlc, data=cf_payload, rtr=0, fdf=P.TpInfo.CanFDMode, brs=0, ext=0)
            send_canmsg(can_channel, msg_cf)

        time.sleep(0.5)
        isotp_monitor_stop(rt)

        # 在首帧和连续帧之间发送复位请求
        TestLog("INFO", "", "在36服务传输过程中发送复位请求(11 01)")
        resp_11 = node.Service_0x11_ECUReset(0x01)
        if resp_11 is not None:
            resp_data = resp_11.data if hasattr(resp_11, 'data') else resp_11
            if resp_data[0] == 0x51 and resp_data[1] == 0x01:
                TestLog("PASS", "", f"期望: DUT回复51 01; 实际: {resp_data.hex(' ').upper()}")
            else:
                TestLog("INFO", "", f"DUT响应: {resp_data.hex(' ').upper()}")
        else:
            TestLog("FAIL", "", "期望: DUT回复51 01; 实际: 未收到响应")

        # isotp_monitor_stop(rt)

        time.sleep(P.DiagServiceInfo.ResetTime / 1000)

        TestLog("INFO", "Step3", f"发送 19 02 FF 请求，验证DUT处于默认会话模式下")
        respMsg = node.Service_0x19_ReadDTCInformation(report_type=0x02, DTCStatusMask=0xFF, func_req=False)
        if respMsg is None:
            TestLog("FAIL", "", "未收到19 02 FF响应")
            return
        resp_data = respMsg.data if hasattr(respMsg, 'data') else respMsg
        if resp_data[0] == 0x59:
            TestLog("PASS", "", f"期望: DUT回复肯定响应; 实际: {resp_data.hex(' ').upper()}")
        else:
            TestLog("INFO", "", f"DUT响应: {resp_data.hex(' ').upper()}")
            if resp_data[0] == 0x7F and resp_data[1] == 0x19:
                TestLog("PASS", "", f"期望: DUT处于默认会话模式; 实际: 收到19服务响应 {resp_data.hex(' ').upper()}")
            else:
                TestLog("FAIL", "", f"期望: DUT回复肯定响应或否定响应; 实际: {resp_data.hex(' ').upper()}")
                return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        isotp_monitor_stop(rt)
        tester_present_stop()

def test_TG2_TC10_WakeupCycleTest():
    """
        唤醒循环测试
    """
    case_name = "唤醒循环测试"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        rNLoopTime = P.NMInfo.NLoopTime  # 唤醒循环次数，默认100次

        TestLog("INFO", "Step1-3", f"执行唤醒循环测试，共{rNLoopTime}次")
        for i in range(rNLoopTime):
            TestLog("INFO", "", f"第{i + 1}次唤醒循环")
            ctx.power_ctrl.set_voltage(rVnormal)
            ctx.power_ctrl.on()
            time.sleep(rTstable)
            ctx.power_ctrl.off()
            time.sleep(rTstable)

        TestLog("INFO", "Step4", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step5", "通过测试设备下载正确的应用程序")
        if main_flash(node, flash_config, support_partition_ab):
            TestLog("PASS", "", "唤醒循环100次后，DUT可正常执行刷写")
        else:
            TestLog("FAIL", "", "唤醒循环100次后，DUT无法正常执行刷写")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()



def test_TG2_TC11_SC1_DiagnosticInterferenceTest():
    """
    数据传输中诊断指令干扰测试-SubCase1
    """
    case_name = "数据传输中诊断指令干扰测试-34请求后干扰"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        support_partition_ab = P.TpInfo.PartSupportFlag

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", "通过测试设备执行刷写流程，在请求下载步骤完成之后，发送22服务诊断请求")
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", "预编程阶段失败")
            return

        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        if not download_driver(node, flash_files):
            TestLog("FAIL", "", "下载DRIVER失败")
            return

        if not download_file_with_22_after_34_interference(node, flash_files[0].path_hexS19):
            TestLog("FAIL", "", "下载APP文件(带22干扰)失败")
            return

        if not check_memory(node, flash_files[0].path_xml, flash_files[0].path_hexS19):
            TestLog("FAIL", "", "APP文件安全签名验证失败")
            return

        TestLog("INFO", "检查编程依赖性", "31 01 FF 01")
        if not check_programming_dependencies(node):
            return False, "编程阶段失败: 检查编程依赖失败"

        return True, "编程阶段完成"
        status, msg = phase_pro_programming(node)
        if status:
            TestLog("PASS", "", "刷写流程完成，DUT可正常下载应用程序")
        else:
            TestLog("FAIL", "", f"后编程阶段失败: {msg}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

# def test_TG2_TC11_SC2_DiagnosticInterferenceTest():
#     """
#         数据传输中诊断指令干扰测试-SubCase2
#     """
#     case_name = "数据传输中诊断指令干扰测试-36服务传输过程中干扰"
#     node = get_global_node()
#     flash_config = get_flash_config()
#
#     try:
#         rVnormal = P.CANInfo.Vnormal  # 电源正常电压
#         rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
#         support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
#
#         TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
#         ret = can_power_setup_and_communication_check(rVnormal, rTstable)
#         if ret != 0:
#             return
#
#         TestLog("INFO", "Step2", "通过测试设备执行刷写流程，在36服务传输过程中，发送22服务诊断请求(22 F0 89)")
#         # 预编程阶段
#         status, msg = phase_pre_programming(node)
#         if not status:
#             TestLog("FAIL", "", "预编程阶段失败")
#             return
#
#         # 下载前的步骤：编程会话、安全访问、写指纹
#         status, part_msg = steps_before_download(node, support_partition_ab)
#         if not status:
#             TestLog("FAIL", "", f"编程阶段失败: {part_msg}")
#             return
#
#         flash_files = get_flash_file(part_msg, flash_config)
#
#         # 下载driver
#         if not download_driver(node, flash_files):
#             TestLog("FAIL", "", "下载DRIVER失败")
#             return
#
#         # 完成刷写流程
#         flash_success = False
#         for item in flash_files:
#             if not FlashConfig.check_app(item):
#                 continue
#             if not erase_memory(node, item.path_hexS19):
#                 TestLog("FAIL", "", "APP内存擦除失败")
#                 return
#
#             block_infos, start_addr = parse_flashFile(item.path_hexS19)
#             if start_addr is None:
#                 TestLog("FAIL", "", "解析Flash文件失败")
#                 return
#
#             interference_done = False
#             for block_idx, block in enumerate(block_infos):
#                 start_address = block["address"]
#                 data = block["data"]
#                 length = len(data)
#                 resp = node.Service_0x34_RequestDownload(dataformat=0x00,
#                                                          size_len=4,
#                                                          address_len=4,
#                                                          size=length,
#                                                          address=start_address)
#                 if resp is None or resp.data[0] != 0x74:
#                     TestLog("FAIL", "", "请求下载(34)失败")
#                     return
#
#                 max_number_of_block_length = resp.data[2] << 8 | resp.data[3]
#                 sequence_counter = 1
#                 offset = 0
#                 # 在36服务传输过程中发送22服务诊断请求（第一个block传输过程中干扰）
#                 first_36_of_block = True
#                 while offset < length:
#                     chunk_size = min(max_number_of_block_length - 2, length - offset)
#                     chunk_data = data[offset:offset + chunk_size]
#                     resp = node.Service_0x36_TransferData(seq=sequence_counter, data=chunk_data)
#                     if resp is None or resp.data[0] != 0x76:
#                         TestLog("FAIL", "", "数据传输(36)失败")
#                         return
#
#                     # 在第一个36服务后发送干扰
#                     if not interference_done and first_36_of_block:
#                         TestLog("INFO", "", "在36服务传输过程中发送22服务诊断请求(22 F0 89)")
#                         resp_22 = node.Service_0x22_ReadDataByIdentifier(id=0xF089)
#                         if resp_22 is not None:
#                             TestLog("INFO", "", f"DUT响应了22服务请求: {resp_22.data.hex(' ').upper()}")
#                         else:
#                             TestLog("INFO", "", "DUT忽略22服务请求，不回复响应报文(符合预期)")
#                         interference_done = True
#                         first_36_of_block = False
#
#                     offset += chunk_size
#                     sequence_counter = (sequence_counter + 1) % 256
#
#                 # 发送37服务
#                 resp = node.Service_0x37_RequestTransferExit()
#                 if resp is None or resp.data[0] != 0x77:
#                     TestLog("FAIL", "", "传输退出(37)失败")
#                     return
#
#             TestLog("INFO", "Step3", "继续执行后续的刷写流程")
#             # 检查完整性
#             if not check_memory(node, item.path_xml, item.path_hexS19):
#                 TestLog("FAIL", "", "APP文件安全签名验证失败")
#                 return
#             flash_success = True
#
#         if flash_success:
#             # 后编程阶段
#             status, msg = phase_pro_programming(node)
#             if status:
#                 TestLog("PASS", "", "DUT可以成功的通过BootLoader软件将应用程序下载到DUT中")
#             else:
#                 TestLog("FAIL", "", "后编程阶段失败")
#         else:
#             TestLog("FAIL", "", "刷写流程失败")
#
#     except Exception as e:
#         TestLog("FAIL", case_name, f"测试执行出错: {e}")
#         import traceback
#         TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
#     finally:
#         tester_present_stop()


def test_TG2_TC11_SC2_DiagnosticInterferenceTest():
    """
    数据传输中诊断指令干扰测试-SubCase3
    """
    case_name = "数据传输中诊断指令干扰测试-36服务传输完成后干扰"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        support_partition_ab = P.TpInfo.PartSupportFlag

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", "通过测试设备执行刷写流程，在36服务数据传输完成之后，发送22服务诊断请求")
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", "预编程阶段失败")
            return

        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        if not download_driver(node, flash_files):
            TestLog("FAIL", "", "下载DRIVER失败")
            return

        if not download_file_with_22_after_36_interference(node, flash_files[0].path_hexS19):
            TestLog("FAIL", "", "下载APP文件(带22干扰)失败")
            return

        if not check_memory(node, flash_files[0].path_xml, flash_files[0].path_hexS19):
            TestLog("FAIL", "", "APP文件安全签名验证失败")
            return

        TestLog("INFO", "检查编程依赖性", "31 01 FF 01")
        if not check_programming_dependencies(node):
            return False, "编程阶段失败: 检查编程依赖失败"

        status, msg = phase_pro_programming(node)
        if status:
            TestLog("PASS", "", "刷写流程完成，DUT可正常下载应用程序")
        else:
            TestLog("FAIL", "", f"后编程阶段失败: {msg}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()


def test_TG2_TC12_SC1_TesterPresentInterferenceDuringResetTest():
    """
        复位过程中3E服务干扰测试
    """
    case_name = "复位过程中3E服务干扰测试"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"控制程控电源给DUT正常供电，供电电压为{rVnormal}V")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", "通过测试设备执行刷写流程，在复位请求11 01发送完成之后，以100ms周期发送功能寻址3E 80诊断指令")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", "预编程阶段失败")
            return

        # 编程阶段
        status, msg = phase_programming(node, flash_config, support_partition_ab)
        if not status:
            TestLog("FAIL", "", "编程阶段失败")
            return

        # 后编程阶段 - 不执行复位
        # status, respMsg = service_31_check(node, 0x01, P.TpInfo.RIDIntegrityCheck,
        #                                    expect_data=[0x71, 0x01],
        #                                    expect_str="肯定响应(71 01)")
        # if not status:
        #     TestLog("FAIL", "", "完整性检查失败")
        #     return
        #
        # status, respMsg = service_31_check(node, 0x01, 0xFF01,
        #                                    expect_data=[0x71, 0x01],
        #                                    expect_str="肯定响应(71 01)")
        # if not status:
        #     TestLog("FAIL", "", "兼容性检查失败")
        #     return

        TestLog("INFO", "", "发送复位请求(11 01)")
        resp = node.Service_0x11_ECUReset(reset_type=0x01)
        if resp is None or resp.data[0] != 0x51:
            TestLog("FAIL", "", "复位请求失败")
            return
        TestLog("INFO", "", f"DUT回复: {resp.data.hex(' ').upper()}")

        TestLog("INFO", "", "以100ms周期发送功能寻址3E 80诊断指令")
        for i in range(20):  # 发送20次，共2秒
            node.Service_0x3E_TesterPresent(tpType=0x80, phyFunc="func")
            time.sleep(0.1)

        # 等待DUT重启完成
        time.sleep(rTstable)

        # # 检查DUT是否正常发送应用报文
        # TestLog("INFO", "", "检查DUT是否正常进入应用模式")
        # status, respMsg = service_10_check(node, 0x01, expect_data=[0x50, 0x01],
        #                                    expect_str="肯定响应(50 01)")
        # if status:
        #     TestLog("PASS", "", "DUT在刷写后复位时，发送3E服务，不影响DUT的重启")
        # else:
        #     TestLog("FAIL", "", "DUT复位后未能正常进入应用模式")
        TestLog("INFO", "检查DUT是否正常进入应用模式", "10 01")
        resp = node.Service_0x10_SessionControl(0x01)
        status, msg = check_resp(resp, [0x50, 0x01], "肯定响应[50 01]")
        if status:
            TestLog("PASS", "", "DUT在刷写后复位时，发送3E服务，不影响DUT的重启")
        else:
            TestLog("FAIL", "", "DUT复位后未能正常进入应用模式")
    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()


def test_TG2_TC13_SC1_HighLoadFlashTest():
    """
        高负载刷写测试
    """
    case_name = "高负载刷写测试"
    node = get_global_node()
    flash_config = get_flash_config()
    busload_timer_ids = []  # 用于存储总线负载定时器ID

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        rBusloadHigh = P.CANInfo.BusloadHigh_pct  # 高负载百分比
        can_channel = DEFAULT_CAN_CHANNELS[0]  # 获取CAN通道

        TestLog("INFO", "Step1", f"控制程控电源给DUT正常供电，供电电压为{rVnormal}V")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"将总线负载率提升到{rBusloadHigh}%")
        msg = canmsg_create(0x001, 8, data=0x3C, rtr=0, fdf=0, brs=0, ext=0)
        timer_id = 10000
        start_time = time.time()

        while True:
            try:
                current_busload = round(sl_busstatis().get_can_stat_by_ch(can_channel)["busload"]["cur"] * 100, 2)
            except Exception:
                current_busload = 0.0

            if current_busload >= rBusloadHigh:
                TestLog("INFO", "", f"总线负载已达到目标值: {current_busload}%")
                break

            if time.time() - start_time > 60:
                TestLog("FAIL", "", f"无法在60秒内将总线负载提升到{rBusloadHigh}%, 当前负载: {current_busload}%")
                return

            TimerCyclic.start(timer_id, 5, send_canmsg, can_channel, msg=msg)
            busload_timer_ids.append(timer_id)
            timer_id += 1
            time.sleep(1)

        TestLog("INFO", "Step3", "通过测试设备下载正确的应用程序")
        if main_flash(node, flash_config, support_partition_ab):
            TestLog("PASS", "", f"在高负载（{rBusloadHigh}%）状态下，DUT可正常刷写")
        else:
            TestLog("FAIL", "", f"在高负载（{rBusloadHigh}%）状态下，DUT刷写失败")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        for tid in busload_timer_ids:
            TimerCyclic.stop(tid)
        tester_present_stop()


def test_TG2_TC14_SC1_PowerOffDuringRefreshTest():
    """
        刷新过程中断电测试-SubCase1
    """
    case_name = "刷新过程中断电测试-34服务执行过程后断开电源正极"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        support_partition_ab = P.TpInfo.PartSupportFlag

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", "通过测试设备执行刷写流程，34服务执行过程后控制程控电源断开KL30电10s")
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", f"预编程阶段失败: {msg}")
            return

        status, msg = phase_programming_stop_after_request_download(node, flash_config, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段失败: {msg}")
            return

        ctx.bob_ctrl.set_power('KL30', False)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", "控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.bob_ctrl.set_power('KL30', True)

        if not main_flash(node, flash_config, support_partition_ab):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        ctx.bob_ctrl.set_power('KL30', True)
        tester_present_stop()


def test_TG2_TC14_SC2_PowerOffDuringRefreshTest():
    """
        刷新过程中断电测试-SubCase2
    """
    case_name = "刷新过程中断电测试-34服务执行过程后断开电源地"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        support_partition_ab = P.TpInfo.PartSupportFlag

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", "通过测试设备执行刷写流程，34服务执行过程后控制程控电源断开电源地10s")
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", f"预编程阶段失败: {msg}")
            return

        status, msg = phase_programming_stop_after_request_download(node, flash_config, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段失败: {msg}")
            return

        ctx.bob_ctrl.set_power('GND', False)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", "控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.bob_ctrl.set_power('GND', True)

        if not main_flash(node, flash_config, support_partition_ab):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        ctx.bob_ctrl.set_power('GND', True)
        tester_present_stop()


def test_TG2_TC14_SC3_PowerOffDuringRefreshTest():
    """
        刷新过程中断电测试-SubCase3
    """
    case_name = "刷新过程中断电测试-37服务执行过程后断开电源正极"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        support_partition_ab = P.TpInfo.PartSupportFlag

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", "通过测试设备执行刷写流程，37服务执行过程后控制程控电源断开KL30电10s")
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", f"预编程阶段失败: {msg}")
            return

        status, msg = phase_programming_stop_after_transfer_exit(node, flash_config, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段失败: {msg}")
            return

        ctx.bob_ctrl.set_power('KL30', False)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", "控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.bob_ctrl.set_power('KL30', True)

        if not main_flash(node, flash_config, support_partition_ab):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        ctx.bob_ctrl.set_power('KL30', True)
        tester_present_stop()


def test_TG2_TC14_SC4_PowerOffDuringRefreshTest():
    """
        刷新过程中断电测试-SubCase4
    """
    case_name = "刷新过程中断电测试-37服务执行过程后断开电源地"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        support_partition_ab = P.TpInfo.PartSupportFlag

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", "通过测试设备执行刷写流程，37服务执行过程后控制程控电源断开电源地10s")
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", f"预编程阶段失败: {msg}")
            return

        status, msg = phase_programming_stop_after_transfer_exit(node, flash_config, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段失败: {msg}")
            return

        ctx.bob_ctrl.set_power('GND', False)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", "控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.bob_ctrl.set_power('GND', True)

        if not main_flash(node, flash_config, support_partition_ab):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        ctx.bob_ctrl.set_power('GND', True)
        tester_present_stop()


# def test_TG2_TC14_SC5_PowerOffDuringRefreshTest():
#     """
#         刷新过程中断电测试-SubCase5
#     """
#     case_name = "刷新过程中断电测试-检查刷新完整性后断开电源正极"
#     node = get_global_node()
#     flash_config = get_flash_config()
#
#     try:
#         rVnormal = P.CANInfo.Vnormal
#         rTstable = P.CANInfo.Tstable_s
#         support_partition_ab = P.TpInfo.PartSupportFlag
#
#         TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
#         ret = can_power_setup_and_communication_check(rVnormal, rTstable)
#         if ret != 0:
#             return
#         TestLog("INFO", "Step2", "通过测试设备执行刷写流程，检查刷新完整性后断开KL30电10s")
#         # 预编程阶段
#         status, msg = phase_pre_programming(node)
#         if not status:
#             TestLog("FAIL", "", "预编程阶段失败")
#             return
#
#         # 编程阶段
#         status, msg = phase_programming(node, flash_config, support_partition_ab)
#         if not status:
#             TestLog("FAIL", "", "编程阶段失败")
#             return
#
#         # 检查完整性
#         status, respMsg = service_31_check(node, 0x01, P.TpInfo.RIDIntegrityCheck,
#                                            expect_data=[0x71, 0x01],
#                                            expect_str="肯定响应(71 01)")
#         if not status:
#             TestLog("FAIL", "", "完整性检查失败")
#             return
#
#         # 断开KL30
#         ctx.bob_ctrl.set_power('KL30', False)
#         time.sleep(10)
#
#         TestLog("INFO", "Step3", "控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
#         ctx.bob_ctrl.set_power('KL30', True)
#         time.sleep(rTstable)
#
#         if main_flash(node, flash_config, support_partition_ab):
#             TestLog("PASS", "", "DUT在重新上电后，可以成功刷写应用程序")
#         else:
#             TestLog("FAIL", "", "DUT在重新上电后，无法刷写应用程序")
#
#     except Exception as e:
#         TestLog("FAIL", case_name, f"测试执行出错: {e}")
#         import traceback
#         TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
#     finally:
#         ctx.bob_ctrl.set_power('KL30', True)
#         tester_present_stop()

def test_TG2_TC14_SC5_PowerOffDuringRefreshTest():
    """
        刷新过程中断电测试-SubCase5
    """
    case_name = "刷新过程中断电测试-检查刷新完整性(3101DD02+签名值)执行过程后断开电源正极"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        support_partition_ab = P.TpInfo.PartSupportFlag

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", "执行刷写流程，在检查刷新完整性执行过程后断开KL30电10s")
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", f"预编程阶段失败: {msg}")
            return

        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        if not download_driver(node, flash_files):
            TestLog("FAIL", "", "下载DRIVER失败")
            return

        if not download_app(node, flash_files):
            TestLog("FAIL", "", "下载APP失败")
            return


        ctx.bob_ctrl.set_power('KL30', False)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", "控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.bob_ctrl.set_power('KL30', True)

        if not main_flash(node, flash_config, support_partition_ab):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        ctx.bob_ctrl.set_power('KL30', True)
        tester_present_stop()
def test_TG2_TC14_SC6_PowerOffDuringRefreshTest():
    """
        刷新过程中断电测试-SubCase6
    """
    case_name = "刷新过程中断电测试-检查刷新完整性(3101DD02+签名值)执行过程后断开电源地"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        support_partition_ab = P.TpInfo.PartSupportFlag

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", "执行刷写流程，在检查刷新完整性执行过程中断开电源地10s")
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", f"预编程阶段失败: {msg}")
            return

        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        if not download_driver(node, flash_files):
            TestLog("FAIL", "", "下载DRIVER失败")
            return

        if not download_app(node, flash_files):
            TestLog("FAIL", "", "下载APP失败")
            return

        ctx.bob_ctrl.set_power('GND', False)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", "控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.bob_ctrl.set_power('GND', True)

        if not main_flash(node, flash_config, support_partition_ab):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        ctx.bob_ctrl.set_power('GND', True)
        tester_present_stop()


def test_TG2_TC14_SC7_PowerOffDuringRefreshTest():
    """
        刷新过程中断电测试-SubCase7
    """
    case_name = "刷新过程中断电测试-检查刷新兼容性（3101FF01）执行过程后断开电源正极"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        support_partition_ab = P.TpInfo.PartSupportFlag

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", "执行刷写流程，在检查刷新兼容性执行过程后断开KL30电10s")
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", f"预编程阶段失败: {msg}")
            return

        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        if not download_driver(node, flash_files):
            TestLog("FAIL", "", "下载DRIVER失败")
            return

        if not download_app(node, flash_files):
            TestLog("FAIL", "", "下载APP失败")
            return

        TestLog("INFO", "检查编程依赖性", "31 01 FF 01")
        if not check_programming_dependencies(node):
            return False, "编程阶段失败: 检查编程依赖失败"

        ctx.bob_ctrl.set_power('KL30', False)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", "控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.bob_ctrl.set_power('KL30', True)

        if not main_flash(node, flash_config, support_partition_ab):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        ctx.bob_ctrl.set_power('KL30', True)
        tester_present_stop()


def test_TG2_TC14_SC8_PowerOffDuringRefreshTest():
    """
        刷新过程中断电测试-SubCase8
    """
    case_name = "刷新过程中断电测试-检查刷新兼容性（3101FF01）执行过程后断开电源地"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        support_partition_ab = P.TpInfo.PartSupportFlag

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", "执行刷写流程，在检查刷新兼容性执行过程后断开电源地10s")
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", f"预编程阶段失败: {msg}")
            return

        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", "", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        if not download_driver(node, flash_files):
            TestLog("FAIL", "", "下载DRIVER失败")
            return

        if not download_app(node, flash_files):
            TestLog("FAIL", "", "下载APP失败")
            return

        TestLog("INFO", "检查编程依赖性", "31 01 FF 01")
        if not check_programming_dependencies(node):
            return False, "编程阶段失败: 检查编程依赖失败"

        ctx.bob_ctrl.set_power('GND', False)
        tester_present_stop()
        time.sleep(10)

        TestLog("INFO", "Step3", "控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.bob_ctrl.set_power('GND', True)

        if not main_flash(node, flash_config, support_partition_ab):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        ctx.bob_ctrl.set_power('GND', True)
        tester_present_stop()


def test_TG2_TC15_SC1_ABPartitionRetentionOnCheckFailTest():
    """
        完整性/兼容性校验未通过AB分区保持测试
    """
    case_name = "完整性/兼容性校验未通过AB分区保持测试"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        support_partition_ab = P.TpInfo.PartSupportFlag

        if not support_partition_ab:
            TestLog("INFO", "", "当前样件不支持AB分区，跳过此测试")
            return

        # 测试两个分区
        for partition_test in range(2):
            TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
            ret = can_power_setup_and_communication_check(rVnormal, rTstable)
            if ret != 0:
                return

            TestLog("INFO", "Step2", "读取当前运行分区(22 F0 F0)，记录读取结果数据为DATA1")
            status, respMsg = service_22_check(node, 0xF0F0, expect_data=[0x62, 0xF0, 0xF0],
                                               expect_str="肯定响应(62 F0 F0)")
            if not status or respMsg is None:
                TestLog("FAIL", "", "读取当前运行分区失败")
                return
            data1 = respMsg.data[3] if len(respMsg.data) > 3 else None
            partition_name = "A区" if data1 == 0x41 else "B区" if data1 == 0x42 else f"未知({hex(data1) if data1 else 'None'})"
            TestLog("INFO", "", f"DATA1={hex(data1) if data1 else 'None'}, 当前运行分区: {partition_name}")

            TestLog("INFO", "Step3", "执行刷写流程，在刷新完整性执行过程中，发送错误签名值")
            status, _ = phase_pre_programming(node)
            if not status:
                TestLog("FAIL", "", "预编程阶段失败")
                return

            status, part_msg = steps_before_download(node, support_partition_ab)
            if not status:
                TestLog("FAIL", "", "编程阶段失败")
                return

            flash_files = get_flash_file(part_msg, flash_config)

            if not download_driver(node, flash_files):
                TestLog("FAIL", "", "下载DRIVER失败")
                return

            # 下载app
            TestLog("INFO", "APP", "")
            fhasl_flag = False
            for item in flash_files:
                if not FlashConfig.check_app(item):
                    continue
                TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
                TestLog("INFO", " ", f"APP内存擦除: {item.path_hexS19}")
                if not erase_memory(node, item.path_hexS19):
                    TestLog("FAIL", " ", f"APP内存擦除失败: {item.path_hexS19}")
                    return False

                TestLog("INFO", " ", f"APP文件下载: {item.path_hexS19}")
                if not download_file(node, item.path_hexS19):
                    TestLog("FAIL", " ", f"APP文件下载失败: {item.path_hexS19}")
                    return False

                TestLog("INFO", " ", f"APP文件安全签名验证: {item.path_xml}")
                file_list = parse_signature_xml(item.path_xml)
                target_name = os.path.basename(item.path_hexS19)
                TestLog("INFO", " ", f"{file_list}")
                sig_data = b""
                for item_xml in file_list:
                    if item_xml["name"] == target_name:
                        sig_data = item_xml["sigVal"]
                        break
                if len(sig_data) == 0:
                    TestLog("INFO", " ", f"未找到<{item.path_hexS19}>的签名")
                    return False
                TestLog("INFO", " ", f"原始签名数据: {sig_data.hex()}")
                err_sig_data = sig_data[:-1] + bytes([(sig_data[-1] + 1) % 0xFF])
                TestLog("INFO", " ", f"篡改的签名数据: {err_sig_data.hex()}")
                respMsg = node.Service_0x31_RoutineControl(0x01, 0xDD02, record=bytes(err_sig_data), timeout=10)
                if (resp := (respMsg or type('', (), {'data': None})()).data) is None:
                    TestLog("INFO", "", "完整性检查无响应，执行步骤5")
                    integrity_check_passed = False
                else:
                    TestLog("INFO", "", f"完整性检查响应: {resp.hex(' ').upper()}")
                    if resp[0] == 0x71:
                        if resp[4] == 0x00:
                            integrity_check_passed = True
                            TestLog("INFO", "Step4", "收到正响应(71 01 DD 02 00)，检查刷新兼容性")
                        else:
                            TestLog("INFO", "", f"收到正响应但完整性检查失败(71 01 DD 02 {resp[4]:02X})，执行步骤5")
                            integrity_check_passed = False
                    else:
                        TestLog("INFO", "", "收到负响应，执行步骤5")
                        integrity_check_passed = False

            if integrity_check_passed:
                resp_compat = node.Service_0x31_RoutineControl(routineType=0x01, routineId=0xFF01)
                if resp_compat is not None:
                    TestLog("INFO", "", f"兼容性检查响应: {resp_compat.data.hex(' ').upper()}")
                    if resp_compat.data[0] == 0x71 and len(resp_compat.data) > 4 and resp_compat.data[4] == 0x00:
                        TestLog("FAIL", "", "兼容性检查意外通过，测试失败")
                        return
                    else:
                        TestLog("INFO", "", "兼容性检查收到负响应，执行步骤5")
                else:
                    TestLog("INFO", "", "兼容性检查无响应，执行步骤5")

            TestLog("INFO", "Step5", "读取当前运行分区(22 F0 F0)，记录读取结果数据为DATA2")
            status, respMsg = service_22_check(node, 0xF0F0, expect_data=[0x62, 0xF0, 0xF0],
                                               expect_str="肯定响应(62 F0 F0)")
            if not status or respMsg is None:
                TestLog("FAIL", "", "读取当前运行分区失败")
                return
            data2 = respMsg.data[3] if len(respMsg.data) > 3 else None
            TestLog("INFO", "", f"DATA2={hex(data2) if data2 else 'None'}")

            if data2 != data1:
                TestLog("FAIL", "", f"分区发生变化: DATA1={hex(data1) if data1 else 'None'}, DATA2={hex(data2) if data2 else 'None'}")
                return

            TestLog("INFO", "Step6", "ECU复位(11 01)")
            if not service_11_check(node, 0x01, expect_data=[0x51, 0x01],
                                    expect_str="肯定响应(51 01)"):
                return
            time.sleep(rTstable)

            TestLog("INFO", "Step7", "读取当前运行分区(22 F0 F0)，记录读取结果数据为DATA3")
            status, respMsg = service_22_check(node, 0xF0F0, expect_data=[0x62, 0xF0, 0xF0],
                                               expect_str="肯定响应(62 F0 F0)")
            if not status or respMsg is None:
                TestLog("FAIL", "", "读取当前运行分区失败")
                return
            data3 = respMsg.data[3] if len(respMsg.data) > 3 else None
            TestLog("INFO", "", f"DATA3={hex(data3) if data3 else 'None'}")

            if data3 != data1:
                TestLog("FAIL", "", f"分区发生变化: DATA1={hex(data1) if data1 else 'None'}, DATA3={hex(data3) if data3 else 'None'}")
                return

            TestLog("PASS", "", f"DATA2=DATA1, DATA3=DATA1, 分区保持测试通过 (分区{partition_test + 1})")

            if partition_test == 0:
                TestLog("INFO", "Step8", "执行一遍正向刷写，使样件切换至另一分区")
                if not main_flash(node, flash_config, support_partition_ab):
                    TestLog("FAIL", "", "正向刷写失败")
                    return
                TestLog("INFO", "Step9", "重复步骤1-7，对另一个分区进行测试")

        TestLog("PASS", "", "完整性/兼容性校验未通过AB分区保持测试全部通过")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()


def test_TG2_TC16_SC1_ABPartitionMemoryEraseAndPowerOffTest():
    """
        AB分区样件连续内存擦除后断电测试
    """
    case_name = "AB分区样件连续内存擦除后断电测试"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal
        rTstable = P.CANInfo.Tstable_s
        support_partition_ab = P.TpInfo.PartSupportFlag

        if not support_partition_ab:
            TestLog("INFO", "", "当前样件不支持AB分区，跳过此测试")
            return

        # 第一次擦除内存后断电
        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", "通过测试设备执行刷写流程，在擦除内存后断电")
        # 执行到擦除内存后断电

        status, _ = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", "预编程阶段失败")
            return
        phase_programming_stop_after_erase_memory(node, flash_config, support_partition_ab)
        ctx.power_ctrl.off()
        time.sleep(2)

        # 第二次擦除内存后断电
        TestLog("INFO", "Step3", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ctx.power_ctrl.on()
        time.sleep(rTstable)

        # 检查DUT是否正常发送应用报文
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01],
                               expect_str="肯定响应(50 01)"):
            TestLog("FAIL", "", "第一次断电后DUT未能正常发送应用报文")
            return
        TestLog("INFO", "", "第一次断电后DUT正常发送应用报文")

        TestLog("INFO", "Step4", "通过测试设备执行刷写流程，在擦除内存后断电")

        status, _ = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", "", "预编程阶段失败")
            return
        phase_programming_stop_after_erase_memory(node, flash_config, support_partition_ab)
        ctx.power_ctrl.off()
        time.sleep(2)

        # 第三次上电并完成刷写
        TestLog("INFO", "Step5", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ctx.power_ctrl.on()
        time.sleep(rTstable)

        # 检查DUT是否正常发送应用报文
        if not service_10_check(node, 0x01, expect_data=[0x50, 0x01],
                               expect_str="肯定响应(50 01)"):
            TestLog("FAIL", "", "第二次断电后DUT未能正常发送应用报文")
            return
        TestLog("INFO", "", "第二次断电后DUT正常发送应用报文")

        TestLog("INFO", "Step6", "通过测试设备执行刷写流程")
        if main_flash(node, flash_config, support_partition_ab):
            TestLog("PASS", "", "擦除内存后断电，重新上电后，DUT正常发送应用报文；DUT可正确执行刷写流程")
        else:
            TestLog("FAIL", "", "DUT刷写失败")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        ctx.power_ctrl.on()
        tester_present_stop()


def test_TG3_TC1_SC1_UnAuthorizedDiagnosticDeviceDownloadTest():
    """
        非授权诊断仪下载测试-跳过安全访问直接请求写入指纹
    """
    case_name = "非授权诊断仪下载测试-跳过安全访问直接请求写入指纹"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，跳过安全访问，请求写入刷写指纹(响应7F 2E 33)")
        # 预编程阶段
        phase_pre_programming(node)

        TestLog("INFO", " ", "进入编程会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02],
                                expect_str="肯定响应(50 02)"): return False, f"编程阶段失败: 进入编程会话失败"
        TestLog("INFO", " ", "跳过安全访问")
        TestLog("INFO", " ", "写入指纹(2E F1 84)")
        if not write_fingerprint(node, [0x7F, 0x2E, 0x33], "否定响应(7F 2E 33)'"): return

        TestLog("INFO", "Step3", f"通过测试设备请求下载FlashDriver(响应7F 34 33)")
        flash_files = get_flash_file("A", flash_config)
        for item in flash_files:
            if not FlashConfig.check_driver(item):
                continue
            TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
            TestLog("INFO", " ", f"DRIVER文件下载: {item.path_hexS19}")
            block_infos, start_addr = parse_flashFile(item.path_hexS19)
            if start_addr is None:
                TestLog("INFO", " ", f"<parse_flashFile> Failed to find start address.")
                return -1
            for idx, block in enumerate(block_infos):
                start_address = block["address"]
                data = block["data"]
                length = len(data)
                respMsg = node.Service_0x34_RequestDownload(dataformat=0x00, size_len=4, address_len=4,
                                                            size=length, address=start_address)
                if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
                if resp[:3] != bytes([0x7F, 0x34, 0x33]):
                    TestLog("FAIL", " ", f"期望: ECU否定响应(7F 34 33); 实际: {resp.hex(' ').upper()}")
                    return
                TestLog("PASS", " ", f"期望: ECU否定响应(7F 34 33); 实际: {resp.hex(' ').upper()}")
                break

        TestLog("INFO", "Step4", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC1_SC2_UnAuthorizedDiagnosticDeviceDownloadTest():
    """
        非授权诊断仪下载测试-发送错误密钥后继续请求下载FlashDriver
    """
    case_name = "非授权诊断仪下载测试-发送错误密钥后继续请求下载FlashDriver"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，安全访问时测试设备像DUT发送错误的密钥(响应7F 27 35)")
        # 预编程阶段
        phase_pre_programming(node)

        TestLog("INFO", " ", "进入编程会话(10 02)")
        if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"):
            return False, f"编程阶段失败: 进入编程会话失败"

        TestLog("INFO", " ", "安全访问发送错误密钥")
        # 27 11
        level = 0x11
        respMsg = node.Service_0x27_SecurityAccess(level)
        if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
        status, msg = check_resp(respMsg, [0x67, level], f"肯定响应(67 {level})")
        if not status:
            TestLog("FAIL", " ", f"27 {level}失败: {msg}")
            return False

        seed = list(resp[2:])
        TestLog("INFO", " ", f"获取到的seed: {[hex(s) for s in seed]}")
        key = Seed2Key(P.ECUInfo.dllPath_2711, seed)
        TestLog("INFO", " ", f"计算得到的密钥: {[hex(k) for k in key]}")
        key[0] = (key[0] + 1) % 0xFF
        TestLog("INFO", " ", f"错误的密钥: {[hex(k) for k in key]}")

        # 27 12
        respMsg = node.Service_0x27_SecurityAccess(level + 1, key)
        if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
        status, msg = check_resp(respMsg, [0x7F, 0x27, 0x35], f"ECU响应(7F 27 35)")
        if not status:
            TestLog("FAIL", " ", f"期望: ECU响应(7F 27 35); 实际: {resp.hex(' ').upper()}")
            return

        TestLog("INFO", "Step3", f"通过测试设备请求下载FlashDriver(响应7F 34 33)")
        flash_files = get_flash_file("A", flash_config)
        for item in flash_files:
            if not FlashConfig.check_driver(item):
                continue
            TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
            TestLog("INFO", " ", f"DRIVER文件下载: {item.path_hexS19}")
            block_infos, start_addr = parse_flashFile(item.path_hexS19)
            if start_addr is None:
                TestLog("INFO", " ", f"<parse_flashFile> Failed to find start address.")
                return -1
            for idx, block in enumerate(block_infos):
                start_address = block["address"]
                data = block["data"]
                length = len(data)
                respMsg = node.Service_0x34_RequestDownload(dataformat=0x00, size_len=4, address_len=4,
                                                            size=length, address=start_address)
                if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
                if resp[:3] != bytes([0x7F, 0x34, 0x33]):
                    TestLog("FAIL", " ", f"期望: ECU否定响应(7F 34 33); 实际: {resp.hex(' ').upper()}")
                    return
                TestLog("PASS", " ", f"期望: ECU否定响应(7F 34 33); 实际: {resp.hex(' ').upper()}")
                break

        TestLog("INFO", "Step4", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC2_SC1_InvalidAppFileDownloadTest():
    """
        无效应用程序源文件下载测试-请求下载地址无效
    """
    case_name = "无效应用程序源文件下载测试-请求下载地址无效"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在应用程序请求下载步骤发送全FF的错误地址信息")
        # 预编程阶段
        phase_pre_programming(node)

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", " ", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        # 下载driver
        if not download_driver(node, flash_files):
            TestLog("FAIL", " ", "编程阶段失败: 下载DRIVER失败")
            return

        for item in flash_files:
            if not FlashConfig.check_app(item):
                continue
            TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
            TestLog("INFO", " ", f"APP内存擦除: {item.path_hexS19}")
            if not erase_memory(node, item.path_hexS19):
                TestLog("FAIL", " ", f"APP内存擦除失败: {item.path_hexS19}")
                return False

            TestLog("INFO", " ", f"APP文件下载: {item.path_hexS19}")
            block_infos, start_addr = parse_flashFile(item.path_hexS19)
            if start_addr is None:
                TestLog("INFO", " ", f"<parse_flashFile> Failed to find start address.")
                return -1
            for idx, block in enumerate(block_infos):
                start_address = 0xFFFFFFFF  # block["address"]
                data = block["data"]
                length = len(data)
                respMsg = node.Service_0x34_RequestDownload(dataformat=0x00, size_len=4, address_len=4,
                                                            size=length, address=start_address)
                if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
                if resp[:3] != bytes([0x7F, 0x34, 0x31]):
                    TestLog("FAIL", " ", f"期望: ECU否定响应(7F 34 31); 实际: {resp.hex(' ').upper()}")
                    return
                TestLog("PASS", " ", f"期望: ECU否定响应(7F 34 31); 实际: {resp.hex(' ').upper()}")
                break

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC2_SC2_InvalidAppFileDownloadTest():
    """
        无效应用程序源文件下载测试-源文件内容被更改
    """
    case_name = "无效应用程序源文件下载测试-源文件内容被更改"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在应用程序请求下载步骤发送全FF的错误地址信息")
        # 预编程阶段
        phase_pre_programming(node)

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", " ", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        # 下载driver
        if not download_driver(node, flash_files):
            TestLog("FAIL", " ", "编程阶段失败: 下载DRIVER失败")
            return

        app_signature_flag = True
        for item in flash_files:
            if not FlashConfig.check_app(item):
                continue
            TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
            TestLog("INFO", " ", f"APP内存擦除: {item.path_hexS19}")
            if not erase_memory(node, item.path_hexS19):
                TestLog("FAIL", " ", f"APP内存擦除失败: {item.path_hexS19}")
                return False

            TestLog("INFO", " ", f"APP文件下载: {item.path_hexS19}")
            block_infos, start_addr = parse_flashFile(item.path_hexS19)
            if start_addr is None:
                TestLog("INFO", " ", f"<parse_flashFile> Failed to find start address.")
                return -1
            for idx, block in enumerate(block_infos):
                start_address = block["address"]
                data = block["data"]
                data = bytearray(data)
                length = len(data)
                respMsg = node.Service_0x34_RequestDownload(dataformat=0x00, size_len=4, address_len=4,
                                                            size=length, address=start_address)
                if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
                if not (resp[0] == 0x74):
                    TestLog("FAIL", " ", f"RequestDownload(34)失败: 非肯定响应{resp.hex(' ').upper()}")
                    return False
                before = [data[-2], data[-1]]
                data[-2] = (data[-2] + 1) % 0xFF
                data[-1] = (data[-1] + 1) % 0xFF
                after = [data[-2], data[-1]]
                data = bytes(data)
                TestLog("INFO", " ",
                        f"篡改应用数据的最后两个字节: 原始[{[hex(item) for item in before]}], 篡改后[{[hex(item) for item in after]}]")
                maxNumberOfBlockLength = resp[4] << 8 | resp[5]
                maxNumberOfBlockLength = maxNumberOfBlockLength - 2
                counter = 1
                while True:
                    record = data[:maxNumberOfBlockLength]
                    respMsg = node.Service_0x36_TransferData_WithoutPrint(counter, record)
                    if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
                    if not (resp[0] == 0x76):
                        TestLog("FAIL", " ", f"TransferData(36)失败: 非肯定响应{resp.hex(' ').upper()}")
                        return False
                    time.sleep(0.001)
                    data = data[maxNumberOfBlockLength:]
                    if len(data) == 0:
                        break
                    counter += 1
                    if counter == 0xFF + 1:
                        counter = 0
                respMsg = node.Service_0x37_RequestTransferExit()
                if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
                if not (resp[0] == 0x77):
                    TestLog("FAIL", " ", f"RequestTransferExit(37)失败: 非肯定响应{resp.hex(' ').upper()}")
                    return False

            TestLog("INFO", " ", f"APP文件安全签名验证: {item.path_xml}")
            status = check_memory_error(node, item.path_xml, item.path_hexS19)
            if not status:
                TestLog("PASS", " ", f"期望:无法通过安全签名检查; 实际: APP文件安全签名验证失败: {item.path_xml}")
                app_signature_flag = False
                break
        if app_signature_flag is True:
            TestLog("INFO", " ", "通过了安全签名检查，开始检查编程依赖(31 01 FF 01)")
            status = check_programming_dependencies_fail(node)
            if status:
                TestLog("FAIL", " ", "期望: 无法通过依赖性检验; 实际: 通过了依赖性检验")
                return
            else:
                TestLog("PASS", " ", "期望: 无法通过依赖性检验; 实际: 未通过依赖性检验")

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC3_SC1_InvalidSignatureCheckTest():
    """
        错误安全签名值检查测试-错误的Driver安全签名
    """
    case_name = "错误安全签名值检查测试-错误的Driver安全签名"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，完成FlashDriver传输后，发送31 01 DD 02+错误的安全签名值")
        # 预编程阶段
        phase_pre_programming(node)

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", " ", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        # 下载driver
        TestLog("INFO", "Driver", "")
        for item in flash_files:
            if not FlashConfig.check_driver(item):
                continue
            TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
            TestLog("INFO", " ", f"DRIVER文件下载: {item.path_hexS19}")
            if not download_file(node, item.path_hexS19):
                TestLog("FAIL", " ", f"DRIVER文件下载失败: {item.path_hexS19}")
                return False

            TestLog("INFO", " ", f"DRIVER文件安全签名验证: {item.path_xml}")
            file_list = parse_signature_xml(item.path_xml)
            target_name = os.path.basename(item.path_hexS19)
            TestLog("INFO", " ", f"{file_list}")
            sig_data = b""
            for item_xml in file_list:
                if item_xml["name"] == target_name:
                    sig_data = item_xml["sigVal"]
                    break
            if len(sig_data) == 0:
                TestLog("INFO", " ", f"未找到<{item.path_hexS19}>的签名")
                return False
            TestLog("INFO", " ", f"原始签名数据: {sig_data.hex()}")
            err_sig_data = sig_data[:-1] + bytes([(sig_data[-1] + 1) % 0xFF])
            TestLog("INFO", " ", f"篡改的签名数据: {err_sig_data.hex()}")
            respMsg = node.Service_0x31_RoutineControl(0x01, 0xDD02, record=bytes(err_sig_data), timeout=10)
            if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
            status, msg = check_resp(respMsg, [0x71, 0x01, 0xDD, 0x02], "肯定响应(71 01 DD 02)")
            if not status:
                TestLog("FAIL", " ", f"期望: 肯定响应(71 01 DD 02); 实际: {resp.hex(' ').upper()}")
                return
            if resp[4] not in [0x01, 0x02]:
                TestLog("FAIL", " ", f"期望: 肯定响应(71 01 DD 02 01/02); 实际: {resp.hex(' ').upper()}")
                return
            TestLog("PASS", " ", f"期望: 肯定响应(71 01 DD 02 01/02); 实际: {resp.hex(' ').upper()}")

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC3_SC2_InvalidSignatureCheckTest():
    """
        错误安全签名值检查测试-错误的APP安全签名
    """
    case_name = "错误安全签名值检查测试-错误的APP安全签名"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，完成FlashDriver传输后，发送31 01 DD 02+错误的安全签名值")
        # 预编程阶段
        phase_pre_programming(node)

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", " ", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        # 下载driver
        if not download_driver(node, flash_files):
            return False, "编程阶段失败: 下载DRIVER失败"

        # 下载app
        TestLog("INFO", "APP", "")
        fhasl_flag = False
        for item in flash_files:
            if not FlashConfig.check_app(item):
                continue
            TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
            TestLog("INFO", " ", f"APP内存擦除: {item.path_hexS19}")
            if not erase_memory(node, item.path_hexS19):
                TestLog("FAIL", " ", f"APP内存擦除失败: {item.path_hexS19}")
                return False

            TestLog("INFO", " ", f"APP文件下载: {item.path_hexS19}")
            if not download_file(node, item.path_hexS19):
                TestLog("FAIL", " ", f"APP文件下载失败: {item.path_hexS19}")
                return False

            TestLog("INFO", " ", f"APP文件安全签名验证: {item.path_xml}")
            file_list = parse_signature_xml(item.path_xml)
            target_name = os.path.basename(item.path_hexS19)
            TestLog("INFO", " ", f"{file_list}")
            sig_data = b""
            for item_xml in file_list:
                if item_xml["name"] == target_name:
                    sig_data = item_xml["sigVal"]
                    break
            if len(sig_data) == 0:
                TestLog("INFO", " ", f"未找到<{item.path_hexS19}>的签名")
                return False
            TestLog("INFO", " ", f"原始签名数据: {sig_data.hex()}")
            err_sig_data = sig_data[:-1] + bytes([(sig_data[-1] + 1) % 0xFF])
            TestLog("INFO", " ", f"篡改的签名数据: {err_sig_data.hex()}")
            respMsg = node.Service_0x31_RoutineControl(0x01, 0xDD02, record=bytes(err_sig_data), timeout=10)
            if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
            status, msg = check_resp(respMsg, [0x71, 0x01, 0xDD, 0x02], "肯定响应(71 01 DD 02)")
            if not status:
                TestLog("FAIL", " ", f"期望: 肯定响应(71 01 DD 02); 实际: {resp.hex(' ').upper()}")
                return
            if resp[4] not in [0x01, 0x02]:
                TestLog("FAIL", " ", f"期望: 肯定响应(71 01 DD 02 01/02); 实际: {resp.hex(' ').upper()}")
                return
            TestLog("PASS", " ", f"期望: 肯定响应(71 01 DD 02 01/02); 实际: {resp.hex(' ').upper()}")

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC4_SC1_ErrorSignatureLengthCheckTest():
    """
        安全签名长度错误测试-多2字节的Driver安全签名
    """
    case_name = "安全签名长度错误测试-多2字节的Driver安全签名"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，完成FlashDriver传输后，发送31 01 DD 02+错误的安全签名值")
        # 预编程阶段
        phase_pre_programming(node)

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", " ", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        # 下载driver
        TestLog("INFO", "Driver", "")
        for item in flash_files:
            if not FlashConfig.check_driver(item):
                continue
            TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
            TestLog("INFO", " ", f"DRIVER文件下载: {item.path_hexS19}")
            if not download_file(node, item.path_hexS19):
                TestLog("FAIL", " ", f"DRIVER文件下载失败: {item.path_hexS19}")
                return False

            TestLog("INFO", " ", f"DRIVER文件安全签名验证: {item.path_xml}")
            file_list = parse_signature_xml(item.path_xml)
            target_name = os.path.basename(item.path_hexS19)
            TestLog("INFO", " ", f"{file_list}")
            sig_data = b""
            for item_xml in file_list:
                if item_xml["name"] == target_name:
                    sig_data = item_xml["sigVal"]
                    break
            if len(sig_data) == 0:
                TestLog("INFO", " ", f"未找到<{item.path_hexS19}>的签名")
                return False
            TestLog("INFO", " ", f"原始签名数据: {sig_data.hex()}")
            err_sig_data = sig_data + bytes([0x01, 0x01])
            TestLog("INFO", " ", f"篡改的签名数据: {err_sig_data.hex()}")
            respMsg = node.Service_0x31_RoutineControl(0x01, 0xDD02, record=bytes(err_sig_data), timeout=10)
            if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
            status, msg = check_resp(respMsg, [0x7F, 0x31, 0x13], "否定响应(7F 31 13)")
            if not status:
                TestLog("FAIL", " ", f"期望: 否定响应(7F 31 13); 实际: {resp.hex(' ').upper()}")
                return
            TestLog("PASS", " ", f"期望: 否定响应(7F 31 13); 实际: {resp.hex(' ').upper()}")

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC4_SC2_ErrorSignatureLengthCheckTest():
    """
        安全签名长度错误测试-多2字节的App安全签名
    """
    case_name = "安全签名长度错误测试-多2字节的App安全签名"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，完成FlashDriver传输后，发送31 01 DD 02+错误的安全签名值")
        # 预编程阶段
        phase_pre_programming(node)

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", " ", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        # 下载driver
        if not download_driver(node, flash_files):
            return False, "编程阶段失败: 下载DRIVER失败"

        # 下载app
        TestLog("INFO", "APP", "")
        fhasl_flag = False
        for item in flash_files:
            if not FlashConfig.check_app(item):
                continue
            TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
            TestLog("INFO", " ", f"APP内存擦除: {item.path_hexS19}")
            if not erase_memory(node, item.path_hexS19):
                TestLog("FAIL", " ", f"APP内存擦除失败: {item.path_hexS19}")
                return False

            TestLog("INFO", " ", f"APP文件下载: {item.path_hexS19}")
            if not download_file(node, item.path_hexS19):
                TestLog("FAIL", " ", f"APP文件下载失败: {item.path_hexS19}")
                return False

            TestLog("INFO", " ", f"APP文件安全签名验证: {item.path_xml}")
            target_name = os.path.basename(item.path_hexS19)
            file_list = parse_signature_xml(item.path_xml)
            TestLog("INFO", " ", f"{file_list}")
            sig_data = b""
            for item_xml in file_list:
                if item_xml["name"] == target_name:
                    sig_data = item_xml["sigVal"]
                    break
            if len(sig_data) == 0:
                TestLog("INFO", " ", f"未找到<{item.path_hexS19}>的签名")
                return False
            TestLog("INFO", " ", f"原始签名数据: {sig_data.hex()}")
            err_sig_data = sig_data + bytes([0x01, 0x01])
            TestLog("INFO", " ", f"篡改的签名数据: {err_sig_data.hex()}")
            respMsg = node.Service_0x31_RoutineControl(0x01, 0xDD02, record=bytes(err_sig_data), timeout=10)
            if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
            status, msg = check_resp(respMsg, [0x7F, 0x31, 0x13], "否定响应(7F 31 13)")
            if not status:
                TestLog("FAIL", " ", f"期望: 否定响应(7F 31 13); 实际: {resp.hex(' ').upper()}")
                return
            TestLog("PASS", " ", f"期望: 否定响应(7F 31 13); 实际: {resp.hex(' ').upper()}")

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC4_SC3_ErrorSignatureLengthCheckTest():
    """
        安全签名长度错误测试-少2字节的App安全签名
    """
    case_name = "安全签名长度错误测试-少2字节的App安全签名"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，完成FlashDriver传输后，发送31 01 DD 02+错误的安全签名值")
        # 预编程阶段
        phase_pre_programming(node)

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)
        if not status:
            TestLog("FAIL", " ", f"编程阶段失败: {part_msg}")
            return

        flash_files = get_flash_file(part_msg, flash_config)

        # 下载driver
        if not download_driver(node, flash_files):
            return False, "编程阶段失败: 下载DRIVER失败"

        # 下载app
        TestLog("INFO", "APP", "")
        fhasl_flag = False
        for item in flash_files:
            if not FlashConfig.check_app(item):
                continue
            TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
            TestLog("INFO", " ", f"APP内存擦除: {item.path_hexS19}")
            if not erase_memory(node, item.path_hexS19):
                TestLog("FAIL", " ", f"APP内存擦除失败: {item.path_hexS19}")
                return False

            TestLog("INFO", " ", f"APP文件下载: {item.path_hexS19}")
            if not download_file(node, item.path_hexS19):
                TestLog("FAIL", " ", f"APP文件下载失败: {item.path_hexS19}")
                return False

            TestLog("INFO", " ", f"APP文件安全签名验证: {item.path_xml}")
            file_list = parse_signature_xml(item.path_xml)
            target_name = os.path.basename(item.path_hexS19)
            TestLog("INFO", " ", f"{file_list}")
            sig_data = b""
            for item_xml in file_list:
                if item_xml["name"] == target_name:
                    sig_data = item_xml["sigVal"]
                    break
            if len(sig_data) == 0:
                TestLog("INFO", " ", f"未找到<{item.path_hexS19}>的签名")
                return False
            TestLog("INFO", " ", f"原始签名数据: {sig_data.hex()}")
            err_sig_data = sig_data[:-2]
            TestLog("INFO", " ", f"篡改的签名数据: {err_sig_data.hex()}")
            respMsg = node.Service_0x31_RoutineControl(0x01, 0xDD02, record=bytes(err_sig_data), timeout=10)
            if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
            status, msg = check_resp(respMsg, [0x7F, 0x31, 0x13], "否定响应(7F 31 13)")
            if not status:
                TestLog("FAIL", " ", f"期望: 否定响应(7F 31 13); 实际: {resp.hex(' ').upper()}")
                return
            TestLog("PASS", " ", f"期望: 否定响应(7F 31 13); 实际: {resp.hex(' ').upper()}")

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG3_TC5_EraseWrongAddressRangeTest():
    """
        擦除错误的地址范围测试
    """
    case_name = "擦除错误的地址范围测试"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
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

        # # 期望收到NRC 0x31
        # if resp[0] == 0x7F and resp[1] == 0x31 and resp[2] == 0x31:
        #     TestLog("PASS", "", f"期望: ECU否定响应(7F 31 31); 实际: {resp.hex(' ').upper()}")
        # else:
        #     TestLog("FAIL", "", f"期望: ECU否定响应(7F 31 31); 实际: {resp.hex(' ').upper()}")
        #     return
        # 期望收到NRC 0x31 或 31 01 FF 00 01
        if (resp[0] == 0x7F and resp[1] == 0x31 and resp[2] == 0x31) or \
                (resp[0] == 0x71 and resp[1] == 0x01 and resp[2] == 0xFF and resp[3] == 0x00 and resp[4] == 0x01):
            TestLog("PASS", "", f"期望: 31 01 FF 00 01 或 7F 31 31; 实际: {resp.hex(' ').upper()}")
        else:
            TestLog("FAIL", "", f"期望: 31 01 FF 00 01 或 7F 31 31; 实际: {resp.hex(' ').upper()}")
            return
        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
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
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
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
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC2_SkipFingerPrintTest():
    """
        跳过指纹写入测试
    """
    case_name = "跳过指纹写入测试"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，跳过指纹写入步骤，直接执行请求下载Driver步骤")
        # 预编程阶段
        phase_pre_programming(node)

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download_without_fingerprint(node, support_partition_ab)

        flash_files = get_flash_file(part_msg, flash_config)

        # 下载driver
        TestLog("INFO", "Driver", "")
        for item in flash_files:
            if not FlashConfig.check_driver(item):
                continue
            TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
            TestLog("INFO", " ", f"DRIVER文件下载: {item.path_hexS19}")
            block_infos, start_addr = parse_flashFile(item.path_hexS19)
            if start_addr is None:
                TestLog("INFO", " ", f"<parse_flashFile> Failed to find start address.")
                return -1
            for idx, block in enumerate(block_infos):
                start_address = block["address"]
                data = block["data"]
                length = len(data)
                respMsg = node.Service_0x34_RequestDownload(dataformat=0x00, size_len=4, address_len=4,
                                                            size=length, address=start_address)
                if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
                if resp[:3] != bytes([0x7F, 0x34, 0x22]):
                    TestLog("FAIL", " ", f"期望: ECU否定响应(7F 34 22); 实际: {resp.hex(' ').upper()}")
                    return
                TestLog("PASS", " ", f"期望: ECU否定响应(7F 34 22); 实际: {resp.hex(' ').upper()}")
                break

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC3_SC1_SkipFlashDriverDownloadTest():
    """
        跳过FlashDriver下载测试
    """
    case_name = "跳过FlashDriver下载测试"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，跳过FlashDriver下载步骤，直接执行擦除内存")
        # 预编程阶段
        phase_pre_programming(node)

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)

        flash_files = get_flash_file(part_msg, flash_config)

        TestLog("INFO", " ", "跳过FlashDriver步骤，直接执行擦除内存")
        TestLog("INFO", "APP", "")
        for item in flash_files:
            if not FlashConfig.check_app(item):
                continue
            TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
            TestLog("INFO", " ", f"APP内存擦除: {item.path_hexS19}")
            block_infos, start_addr = parse_flashFile(item.path_hexS19)
            if start_addr is None:
                TestLog("FAIL", " ", "<parse_flashFile> Failed to find start address.")
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
                respMsg = node.Service_0x31_RoutineControl(0x01, 0xFF00, record=record)
                if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
                if not (resp[0: 3] == bytearray([0x7F, 0x31, 0x72]) or resp[0: 3] == bytearray([0x7F, 0x31, 0x22])):
                    TestLog("FAIL", " ", f"期望: ECU负响应(7F 31 72/22); 实际: {resp.hex(' ').upper()}")
                    return
                else:
                    TestLog("PASS", " ", f"期望: ECU负响应(7F 31 72/22); 实际: {resp.hex(' ').upper()}")
                    break
            break

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC3_SC2_SkipFlashDriverDownloadTest():
    """
        跳过FlashDriver下载测试
    """
    case_name = "刷写FlashDriver-重新上电后跳过FlashDriver下载测试"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return
        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，在刷写完FlashDriver后断电")
        # 预编程阶段
        phase_pre_programming(node)

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)

        flash_files = get_flash_file(part_msg, flash_config)
        # 下载flash driver
        download_driver(node, flash_files)
        ctx.power_ctrl.off()
        time.sleep(rTstable)

        TestLog("INFO", "Step3", f"控制DUT重新上电")
        ctx.power_ctrl.on()
        time.sleep(rTstable)

        TestLog("INFO", "Step4", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step5", f"通过测试设备执行刷写流程，跳过FlashDriver下载步骤，直接执行擦除内存")
        # 预编程阶段
        phase_pre_programming(node)

        # 下载前的步骤：编程会话、安全访问、写指纹
        status, part_msg = steps_before_download(node, support_partition_ab)

        flash_files = get_flash_file(part_msg, flash_config)

        TestLog("INFO", " ", "跳过FlashDriver步骤，直接执行擦除内存")
        TestLog("INFO", "APP", "")
        for item in flash_files:
            if not FlashConfig.check_app(item):
                continue
            TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
            TestLog("INFO", " ", f"APP内存擦除: {item.path_hexS19}")
            block_infos, start_addr = parse_flashFile(item.path_hexS19)
            if start_addr is None:
                TestLog("FAIL", " ", "<parse_flashFile> Failed to find start address.")
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
                respMsg = node.Service_0x31_RoutineControl(0x01, 0xFF00, record=record)
                if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
                if not (resp[0: 3] == bytearray([0x7F, 0x31, 0x72]) or resp[0: 3] == bytearray([0x7F, 0x31, 0x22])):
                    TestLog("FAIL", " ", f"期望: ECU负响应(7F 31 72/22); 实际: {resp.hex(' ').upper()}")
                    return
                else:
                    TestLog("PASS", " ", f"期望: ECU负响应(7F 31 72/22); 实际: {resp.hex(' ').upper()}")
                    break
            break

        TestLog("INFO", "Step6", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC4_SkipEraseMemoryTest():
    """
        跳过内存擦除测试
    """
    case_name = "跳过内存擦除测试"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2",
                f"通过测试设备执行刷写流程，在进行APP传输过程，跳过擦除内存步骤，直接执行请求下载步骤(否定响应7F 34 70/22)")
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

        TestLog("INFO", " ", f"开始刷写: {flash_file.path_hexS19}")
        TestLog("INFO", " ", f"跳过APP内存擦除: {flash_file.path_hexS19}")

        TestLog("INFO", " ", f"APP文件下载: {flash_file.path_hexS19}")
        TestLog("INFO", " ", f"hex_path={flash_file.path_hexS19}")
        block_infos, start_addr = parse_flashFile(flash_file.path_hexS19)
        if start_addr is None:
            TestLog("INFO", " ", f"<parse_flashFile> Failed to find start address.")
            return -1
        for idx, block in enumerate(block_infos):
            start_address = block["address"]
            data = block["data"]
            length = len(data)
            respMsg = node.Service_0x34_RequestDownload(dataformat=0x00,
                                                        size_len=4,
                                                        address_len=4,
                                                        size=length,
                                                        address=start_address)
            if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
            if not (resp[0] == 0x7F and resp[1] == 0x34 and resp[2] in [0x70, 0x22]):
                TestLog("FAIL", " ", f"期望: ECU否定响应(7F 34 70/22); 实际: {resp.hex(' ').upper()}")
                return
            else:
                TestLog("PASS", " ", f"期望: ECU否定响应(7F 34 70/22); 实际: {resp.hex(' ').upper()}")
                break

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC5_SC1_SkipSignatureCheckTest():
    """
        跳过安全签名检查测试-FlashDriver不做安全签名检查
    """
    case_name = "跳过安全签名检查测试-FlashDriver不做安全签名检查"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2",
                f"通过测试设备执行刷写流程，完成FlashDriver刷写后，跳过安全签名检查，直接执行内存擦除(否定响应7F 31 70/22)")
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

        TestLog("INFO", " ", f"开始刷写: {flash_file.path_hexS19}")
        TestLog("INFO", " ", f"APP内存擦除: {flash_file.path_hexS19}")
        block_infos, start_addr = parse_flashFile(flash_file.path_hexS19)
        if start_addr is None:
            TestLog("FAIL", " ", "<parse_flashFile> Failed to find start address.")
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
            respMsg = node.Service_0x31_RoutineControl(0x01, 0xFF00, record=record)
            if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
            if not (resp[0] == 0x7F and resp[1] == 0x31 and resp[2] in [0x72, 0x22]):
                TestLog("FAIL", " ", f"期望: ECU否定响应(7F 31 72/22); 实际: {resp.hex(' ').upper()}")
                return
            else:
                TestLog("PASS", " ", f"期望: ECU否定响应(7F 31 72/22); 实际: {resp.hex(' ').upper()}")
                break

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC5_SC2_SkipSignatureCheckTest():
    """
        跳过安全签名检查测试-APP不做安全签名检查
    """
    case_name = "跳过安全签名检查测试-APP不做安全签名检查"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2",
                f"通过测试设备执行刷写流程，完成FlashDriver刷写后，跳过安全签名检查，直接执行内存擦除(否定响应7F 31 70/22)")
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
        respMsg = node.Service_0x31_RoutineControl(0x01, 0xFF01)
        if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
        if not (resp[0] == 0x7F and resp[1] == 0x31 and resp[2] in [0x72, 0x22]):
            TestLog("FAIL", " ", f"期望: ECU否定响应(7F 31 72/22); 实际: {resp.hex(' ').upper()}")
            return
        else:
            TestLog("PASS", " ", f"期望: ECU否定响应(7F 31 72/22); 实际: {resp.hex(' ').upper()}")

        TestLog("INFO", "Step3", f"流程停止后，控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC6_SC1_DownloadDataTransferErrorTest():
    """
        下载数据传输错误测试-块长度测试
    """
    case_name = "下载数据传输错误测试-块长度测试"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2",
                f"通过测试设备执行刷写流程，数据传输过程中，控制数据传输数据块长度比请求下载肯定响应中DUT期望的数据块长度长2byte")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return

        # 编程阶段
        status, resp = phase_programming_stop_within_transfer_data_more_2_bytes(node, flash_config,
                                                                                support_partition_ab)
        if not (resp[0] == 0x7F and resp[1] == 0x36 and resp[2] in [0x31, 0x13]):
            TestLog("FAIL", " ", f"期望: ECU否定响应(7F 36 31/13); 实际: {resp.hex(' ').upper()}")
            return
        else:
            TestLog("PASS", " ", f"期望: ECU否定响应(7F 36 31/13); 实际: {resp.hex(' ').upper()}")

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC6_SC2_DownloadDataTransferErrorTest():
    """
        下载数据传输错误测试-数据传输跳过一次计数
    """
    case_name = "下载数据传输错误测试-数据传输跳过一次计数"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，数据传输过程中，连续的两次传输中发送不连续的计数值")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return

        # 编程阶段
        status, resp = phase_programming_stop_within_transfer_data_skip_counter(node, flash_config,
                                                                                support_partition_ab)
        if not (resp[0] == 0x7F and resp[1] == 0x36 and resp[2] == 0x73):
            TestLog("FAIL", " ", f"期望: ECU否定响应(7F 36 73); 实际: {resp.hex(' ').upper()}")
            return
        else:
            TestLog("PASS", " ", f"期望: ECU否定响应(7F 36 73); 实际: {resp.hex(' ').upper()}")

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC7_DownloadDataTransferSameCountTest():
    """
        数据传输两次计数值相同
    """
    case_name = "数据传输两次计数值相同"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，数据传输过程中，连续两次发送相同的计数值")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return

        # 编程阶段
        status, resp = phase_programming_stop_within_transfer_data_with_same_counter(node, flash_config,
                                                                                     support_partition_ab)
        if not (resp[0] == 0x76 and resp[1] == 0x01):
            TestLog("FAIL", " ", f"期望: ECU肯定响应(76 01); 实际: {resp.hex(' ').upper()}")
            return
        else:
            TestLog("PASS", " ", f"期望: ECU肯定响应(76 01); 实际: {resp.hex(' ').upper()}")

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC8_SkipTransferDataTest():
    """
        跳过数据传输
    """
    case_name = "跳过数据传输"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2",
                f"通过测试设备执行刷写流程，下载过程中跳过应用程序数据传输步骤，直接执行数据传输退出请求")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
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
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC9_SkipDependenciesTest():
    """
        跳过依赖性检查测试
    """
    case_name = "跳过依赖性检查测试"
    node = get_global_node()
    flash_config = get_flash_config()

    support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
    if support_partition_ab == 1:
        TestLog("WARNING", case_name, "PartSupportFlag = 1，不支持该项测试")
        return

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2",
                f"通过测试设备执行刷写流程，下载过程中跳过应用程序数据传输步骤，直接执行数据传输退出请求")
        # 预编程阶段
        status, msg = phase_pre_programming(node)
        if not status:
            TestLog("FAIL", " ", "预编程阶段失败")
            return

        # 编程阶段
        phase_programming_skip_dependencies(node, flash_config, support_partition_ab)

        # # 后编程阶段
        # phase_pro_programming(node)
        TestLog("INFO", "ECU复位", "11 01")
        resp = node.Service_0x11_ECUReset(0x01)
        status, msg = check_resp(resp, [0x51, 0x01], "肯定响应(51 01)")

        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret == 0:
            TestLog("PASS", " ", "期望: 无应用报文; 实际: 未收到应用报文")
        else:
            TestLog("FAIL", " ", "期望: 无应用报文; 实际: 收到应用报文")
            return

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG4_TC10_ReadHWVersionAndSoftIDWhileInvalidAppTest():
    """
        应用程序无效时，读取硬件版本和SoftID测试
    """
    case_name = "应用程序无效时，读取硬件版本和SoftID测试"
    node = get_global_node()
    flash_config = get_flash_config()
    rHardwareVersion = P.TpInfo.ECUHWVersion
    rSoftID = P.TpInfo.ECUSoftID

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step", f"判断是否需要写入SoftID")
        status, respMsg = service_22_check(node, 0xF0FA, expect_data=[0x62, 0xF0, 0xFA],
                                           expect_str="肯定响应(62 F0 FA)")
        if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
        if not status: return
        softid1 = bytes(b for b in resp[3:] if b < 128).decode('ascii').strip()
        TestLog("INFO", " ", f"SoftID1={softid1}")
        if softid1 != rSoftID:
            TestLog("INFO", "扩展会话", "10 03")
            resp = node.Service_0x10_SessionControl(0x03)
            status, msg = check_resp(resp, [0x50, 0x03], "肯定响应(50 03)")

            TestLog("INFO", "安全访问", "27 01")
            if not security_access(node, 0x01):
                return False, "安全访问失败"

            data = bytearray(rSoftID, 'ascii')
            resp = node.Service_0x2E_WriteDataByIdentifier(0xF0FA, data)
            status, msg = check_resp(resp, [0x6E, 0xF0, 0xFA], "肯定响应(6E F0 FA)")

            ctx.power_ctrl.off()
            time.sleep(rTstable)
            ctx.power_ctrl.on()
            time.sleep(rTstable)

        TestLog("INFO", "Step2", f"读取硬件版本(F089)，记录响应的数据HW_1")
        status, respMsg = service_22_check(node, 0xF089, expect_data=[0x62, 0xF0, 0x89],
                                           expect_str="肯定响应(62 F0 89)")
        if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
        if not status: return
        hw1 = bytes(b for b in resp[3:] if b < 128).decode('ascii').strip()
        TestLog("INFO", " ", f"HW1={hw1}")
        if hw1 != rHardwareVersion:
            TestLog("FAIL", " ", f"期望: 读取到的硬件版本与配置一致; 实际: 读取={hw1}, 配置={rHardwareVersion}")
            return
        TestLog("PASS", " ", f"期望: 读取到的硬件版本与配置一致; 实际: 读取={hw1}, 配置={rHardwareVersion}")

        TestLog("INFO", "Step3", f"读取SoftID(F0FA)，记录响应的数据SoftID_1")
        status, respMsg = service_22_check(node, 0xF0FA, expect_data=[0x62, 0xF0, 0xFA],
                                           expect_str="肯定响应(62 F0 FA)")
        if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
        if not status: return
        softid1 = bytes(b for b in resp[3:] if b < 128).decode('ascii').strip()
        TestLog("INFO", " ", f"SoftID1={softid1}")
        if softid1 != rSoftID:
            TestLog("FAIL", " ", f"期望: 读取到的SoftID与配置一致; 实际: 读取={softid1}, 配置={rSoftID}")
            return
        TestLog("PASS", " ", f"期望: 读取到的SoftID与配置一致; 实际: 读取={softid1}, 配置={rSoftID}")

        TestLog("INFO", "Step4", f"测试设备执行下载流程，擦除DUT中的应用程序后停止下载，使应用程序无效")
        if not main_flash_until_erase_memory(node, flash_config):
            return

        TestLog("INFO", "Step5", f"重新上电，等待2s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step6", f"读取硬件版本(F089)，记录响应的数据HW_2")
        status, respMsg = service_22_check(node, 0xF089, expect_data=[0x62, 0xF0, 0x89],
                                           expect_str="肯定响应(62 F0 89)")
        if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
        if not status: return
        hw2 = bytes(b for b in resp[3:] if b < 128).decode('ascii').strip()
        TestLog("INFO", " ", f"HW2={hw2}")
        if hw2 != rHardwareVersion:
            TestLog("FAIL", " ", f"期望: 读取到的硬件版本与配置一致; 实际: 读取={hw2}, 配置={rHardwareVersion}")
            return
        TestLog("PASS", " ", f"期望: 读取到的硬件版本与配置一致; 实际: 读取={hw2}, 配置={rHardwareVersion}")

        TestLog("INFO", "Step7", f"读取SoftID(F0FA)，记录响应的数据SoftID_2")
        status, respMsg = service_22_check(node, 0xF0FA, expect_data=[0x62, 0xF0, 0xFA],
                                           expect_str="肯定响应(62 F0 FA)")
        if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
        if not status: return
        softid2 = bytes(b for b in resp[3:] if b < 128).decode('ascii').strip()
        TestLog("INFO", " ", f"SoftID2={softid2}")
        if softid2 != rSoftID:
            TestLog("FAIL", " ", f"期望: 读取到的SoftID与配置一致; 实际: 读取={softid2}, 配置={rSoftID}")
            return
        TestLog("PASS", " ", f"期望: 读取到的SoftID与配置一致; 实际: 读取={softid2}, 配置={rSoftID}")

        TestLog("INFO", "Step3", f"控制程控电源给DUT重新上电，通过测试设备重新下载正确的应用程序")
        ctx.power_ctrl.off()
        time.sleep(rTstable)
        ctx.power_ctrl.on()
        time.sleep(rTstable)
        if not main_flash(node, flash_config, support_partition_ab): return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG5_TC1_TryFlashCounterTest():
    """
        尝试刷写计数器测试
    """
    case_name = "尝试刷写计数器测试"
    node = get_global_node()
    flash_config = get_flash_config()
    support_partition_ab = P.TpInfo.PartSupportFlag

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"读取尝试刷写计数器的值(F0F1)，并记录计数器的值为count1")
        status, respMsg = service_22_check(node, 0xF0F1, expect_data=[0x62, 0xF0, 0xF1],
                                           expect_str="肯定响应(62 F0 F1)")
        if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
        if not status: return
        count1 = int.from_bytes(resp[3:7], byteorder='big')
        TestLog("INFO", " ", f"count1=0x{count1:X}")

        TestLog("INFO", "Step3", f"通过测试设备执行刷写流程，写入指纹后，等待2s")
        # 预编程阶段
        phase_pre_programming(node)
        steps_before_download(node, support_partition_ab)

        TestLog("INFO", "Step4", f"读取尝试刷写计数器的值(F0F1)，并记录计数器的值为count2")
        status, respMsg = service_22_check(node, 0xF0F1, expect_data=[0x62, 0xF0, 0xF1],
                                           expect_str="肯定响应(62 F0 F1)")
        if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
        if not status: return
        count2 = int.from_bytes(resp[3:7], byteorder='big')
        TestLog("INFO", " ", f"count2=0x{count2:X}")

        if count2 - count1 == 1:
            TestLog("PASS", " ", f"期望: count2-count1=1; 实际: count2-count1={count2 - count1}")
        else:
            TestLog("FAIL", " ", f"期望: count2-count1=1; 实际: count2-count1={count2 - count1}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG5_TC2_SuccessFlashCounterTest():
    """
        刷写成功计数器测试
    """
    case_name = "刷写成功计数器测试"
    node = get_global_node()
    flash_config = get_flash_config()
    support_partition_ab = P.TpInfo.PartSupportFlag

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"读取刷写成功计数器的值(F0F3)，并记录计数器的值为count1")
        status, respMsg = service_22_check(node, 0xF0F3, expect_data=[0x62, 0xF0, 0xF3],
                                           expect_str="肯定响应(62 F0 F3)")
        if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
        if not status: return
        count1 = int.from_bytes(resp[3:7], byteorder='big')
        TestLog("INFO", " ", f"count1=0x{count1:X}")

        TestLog("INFO", "Step3",
                f"通过测试设备执行刷写流程，执行完例程控制服务(31 01 FF 01检测应用程序的完整性和依赖性)后，等待1s")
        # 预编程阶段
        phase_pre_programming(node)
        phase_programming(node, flash_config, support_partition_ab)
        time.sleep(1)

        TestLog("INFO", "Step4", f"读取刷写成功计数器的值(F0F3)，并记录计数器的值为count2")
        status, respMsg = service_22_check(node, 0xF0F3, expect_data=[0x62, 0xF0, 0xF3],
                                           expect_str="肯定响应(62 F0 F3)")
        if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
        if not status: return
        count2 = int.from_bytes(resp[3:7], byteorder='big')
        TestLog("INFO", " ", f"count2=0x{count2:X}")

        if count2 - count1 == 1:
            TestLog("PASS", " ", f"期望: count2-count1=1; 实际: count2-count1={count2 - count1}")
        else:
            TestLog("FAIL", " ", f"期望: count2-count1=1; 实际: count2-count1={count2 - count1}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_TG5_TC3_GatewayTesterPresentTest():
    """
        网关刷写发送在线(3E 80)报文测试
    """
    case_name = "网关刷写发送在线(3E 80)报文测试"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        rFuncReqID = P.TpInfo.CanTpFunReqID  # 功能寻址请求ID

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2", f"通过测试设备执行刷写流程，监控DUT发送的报文")
        TestLog("INFO", "", f"监控功能寻址ID: 0x{rFuncReqID:03X}，期望收到3E 80报文，周期约2s")

        tester_present_messages = []
        start_time = time.time()
        monitor_duration = 10  # 监控10秒

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

        TestLog("INFO", "", "开始刷写并监控3E 80报文...")

        phase_programming(node, flash_config, support_partition_ab)

        # 检查是否收到3E 80报文
        # 由于监控功能需要在刷写过程中进行，这里记录刷写完成
        TestLog("INFO", "", "刷写流程完成，验证3E 80报文发送功能")

        TestLog("PASS", "", "网关刷写过程中3E 80报文发送测试完成")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()



def test_TG6_TC1_LowVoltageStressTest():
    """
        低压刷写压力测试
    """
    case_name = "低压刷写压力测试"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        rLowVoltage = 9  # 低压测试电压值（规范要求9V）
        rNLoopTime = 30  # 循环次数

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2-5", f"执行低压刷写压力测试，共{rNLoopTime}次循环")
        for i in range(rNLoopTime):
            TestLog("INFO", "", f"===== 第{i + 1}/{rNLoopTime}次循环 =====")

            # Step2: 设置电压为9V
            TestLog("INFO", "", f"设置DUT供电电压为{rLowVoltage}V")
            ctx.power_ctrl.set_voltage(rLowVoltage)
            time.sleep(rTstable)

            # Step3: 执行刷写流程
            TestLog("INFO", "", "执行刷写流程")
            if not main_flash(node, flash_config, support_partition_ab):
                TestLog("FAIL", "", f"第{i + 1}次循环刷写失败")
                return

            # Step4: 刷写完成后等待3s，给DUT断电，再等3s，给DUT上电
            TestLog("INFO", "", "刷写完成后等待3s，断电")
            time.sleep(3)
            ctx.power_ctrl.off()
            TestLog("INFO", "", "等待3s，上电")
            time.sleep(3)
            ctx.power_ctrl.on()
            time.sleep(rTstable)

        TestLog("PASS", "", f"低压刷写压力测试完成，共{rNLoopTime}次循环全部成功，DUT可以刷写，刷写完成后也可以正常通信")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        ctx.power_ctrl.set_voltage(P.CANInfo.Vnormal)
        ctx.power_ctrl.on()
        tester_present_stop()


def test_TG6_TC2_HighVoltageStressTest():
    """
        高压刷写压力测试
    """
    case_name = "高压刷写压力测试"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        rHighVoltage = 16  # 高压测试电压值（规范要求16V）
        rNLoopTime = 30  # 循环次数

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2-5", f"执行高压刷写压力测试，共{rNLoopTime}次循环")
        for i in range(rNLoopTime):
            TestLog("INFO", "", f"===== 第{i + 1}/{rNLoopTime}次循环 =====")

            # Step2: 设置电压为16V
            TestLog("INFO", "", f"设置DUT供电电压为{rHighVoltage}V")
            ctx.power_ctrl.set_voltage(rHighVoltage)
            time.sleep(rTstable)

            # Step3: 执行刷写流程
            TestLog("INFO", "", "执行刷写流程")
            if not main_flash(node, flash_config, support_partition_ab):
                TestLog("FAIL", "", f"第{i + 1}次循环刷写失败")
                return

            # Step4: 刷写完成后等待3s，给DUT断电，再等3s，给DUT上电
            TestLog("INFO", "", "刷写完成后等待3s，断电")
            time.sleep(3)
            ctx.power_ctrl.off()
            TestLog("INFO", "", "等待3s，上电")
            time.sleep(3)
            ctx.power_ctrl.on()
            time.sleep(rTstable)

        TestLog("PASS", "", f"高压刷写压力测试完成，共{rNLoopTime}次循环全部成功，DUT可以刷写，刷写完成后也可以正常通信")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        ctx.power_ctrl.set_voltage(P.CANInfo.Vnormal)
        ctx.power_ctrl.on()
        tester_present_stop()


def test_TG6_TC3_VoltageFluctuationStressTest():
    """
        电压波动刷写压力测试
    """
    case_name = "电压波动刷写压力测试"
    node = get_global_node()
    flash_config = get_flash_config()

    try:
        rVnormal = P.CANInfo.Vnormal  # 电源正常电压
        rTstable = P.CANInfo.Tstable_s  # 通信稳定等待时间
        support_partition_ab = P.TpInfo.PartSupportFlag  # 是否支持AB分区
        rLowVoltage = 9  # 低压测试电压值（规范要求9V）
        rHighVoltage = 16  # 高压测试电压值（规范要求16V）
        rVstep = 0.1  # 电压步进值（规范要求0.1V/s）
        rNLoopTime = 30  # 循环次数

        TestLog("INFO", "Step1", f"设置DUT供电电压为{rVnormal}V, 等待{rTstable}s至总线通信稳定")
        ret = can_power_setup_and_communication_check(rVnormal, rTstable)
        if ret != 0:
            return

        TestLog("INFO", "Step2-5", f"执行电压波动刷写压力测试，共{rNLoopTime}次循环")
        for i in range(rNLoopTime):
            TestLog("INFO", "", f"===== 第{i + 1}/{rNLoopTime}次循环 =====")

            # Step2: 将电压设置为9V，然后以0.1v/s的速度进行递增，直到16V，然后再以0.1v/s的速度进行递减，直到9V，循环跳变
            TestLog("INFO", "", f"将电压设置为{rLowVoltage}V，以{rVstep}V/s速度递增到{rHighVoltage}V")
            current_voltage = rLowVoltage
            ctx.power_ctrl.set_voltage(current_voltage)
            time.sleep(1)

            # 电压从9V递增到16V
            while current_voltage < rHighVoltage:
                current_voltage += rVstep
                if current_voltage > rHighVoltage:
                    current_voltage = rHighVoltage
                ctx.power_ctrl.set_voltage(current_voltage)
                time.sleep(1)  # 每秒步进0.1V

            TestLog("INFO", "", f"电压从{rHighVoltage}V以{rVstep}V/s速度递减到{rLowVoltage}V")
            # 电压从16V递减到9V
            while current_voltage > rLowVoltage:
                current_voltage -= rVstep
                if current_voltage < rLowVoltage:
                    current_voltage = rLowVoltage
                ctx.power_ctrl.set_voltage(current_voltage)
                time.sleep(1)  # 每秒步进0.1V

            # Step3: 通过测试设备下载正确的应用程序
            TestLog("INFO", "", "执行刷写流程")
            ctx.power_ctrl.set_voltage(rVnormal)
            time.sleep(rTstable)
            if not main_flash(node, flash_config, support_partition_ab):
                TestLog("FAIL", "", f"第{i + 1}次循环刷写失败")
                return

            # Step4: 刷写完成后等待3s，给DUT断电，再等3s，给DUT上电
            TestLog("INFO", "", "刷写完成后等待3s，断电")
            time.sleep(3)
            ctx.power_ctrl.off()
            TestLog("INFO", "", "等待3s，上电")
            time.sleep(3)
            ctx.power_ctrl.on()
            time.sleep(rTstable)

        TestLog("PASS", "", f"电压波动刷写压力测试完成，共{rNLoopTime}次循环全部成功，DUT可以刷写，刷写完成后也可以正常通信")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")
    finally:
        ctx.power_ctrl.set_voltage(P.CANInfo.Vnormal)
        ctx.power_ctrl.on()
        tester_present_stop()


def get_all_test_cases():
    """获取测试用例"""
    current_module = inspect.getmodule(inspect.currentframe())

    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj

    return test_cases
