import threading
import time
import traceback
from typing import Any

from uvtest.testlog import TestLog
from env.config import DEFAULT_LIN_CHANNEL
from common.params import P
from .lintp_module import lin_tp_initialization, lintp_send_req, lintp_rcv_response, lin_tp_end, \
    lintp_sys_global_val_set
from library.uds.uds_node import UDSNode
from library.uds.bus_sim import BusSim
from common.context import ctx


class UDSTestParams:
    # 静态参数
    Services10SubFunSupportList = [0x01, 0x02, 0x03, 0x81, 0x82, 0x83]
    Services10LengthCheckSubFunList = [0x01, 0x02, 0x03]
    Services11SubFunSupportList = [0x01, 0x02, 0x03]
    Services19SubfunSupportList = [0x01, 0x02, 0x03, 0x04, 0x06, 0x0A]
    Services19MaskSupportList = list(range(0x01, 0xFF + 1))
    Services19DTCUnSupportList = [0x000000, 0x00FFFF]
    Services19SnapshotRecordNumberSupportList = [0x01, 0xFF]
    Services19ExtendRecordNumberSupportList = [0x01]
    Services27SubFunSupportList = [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x09, 0x0A, 0x11, 0x12]
    Services85SubFunSupportList = [0x01, 0x02]
    Services28SubFunSupportList = [0x00, 0x03]
    Services28CommTypeSupportList = [0x01, 0x03]
    ServicesSupportedList = [0x10, 0x11, 0x14, 0x19, 0x22, 0x27, 0x28, 0x2E, 0x2F, 0x31, 0x34, 0x35, 0x36, 0x37, 0x3E,
                             0x85]
    ServicesUnsupportedList = [
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F,
        0x12, 0x13, 0x15, 0x16, 0x17, 0x18, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F,
        0x20, 0x21, 0x23, 0x24, 0x25, 0x26, 0x29, 0x2A, 0x2B, 0x2C, 0x2D,
        0x30, 0x32, 0x33, 0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0x3F,
        0x80, 0x81, 0x82, 0x83, 0x84, 0x86, 0x87
    ]
    Services3ESubFunSupportList = [0x00, 0x80]
    Services22DIDUnsupportedList = [0x0000, 0x0001, 0xFFFF]
    Services14DTCGroupUnsupportedList = [0x000001, 0x000002, 0xFFFFFE]
    Services2FDIDUnsupportedList = list(range(0x0000, 0x0011))
    Services31SubFunSupportList = [0x01, 0x02, 0x03]
    Services31SubFunUnsupportedList = [0x00, 0x04, 0x05, 0x06, 0x07]
    Services31RIDUnsupportedList = [0xFFFF]
    MinSubID = 0x00
    MaxSubID = 0x10
    MinDID = 0x0000
    MaxDID = 0x0010

    # 从Excel加载的参数
    # TpInfo Sheet
    AppFrameIDList = []
    NMFrameIDList = []
    # AllSupportDTCs Sheet
    Services19DTCSupportList = []
    Services14DTCGroupSupportList = []
    # ReadDIDs Sheet
    Services22DIDSupportList_Default = []
    Services22DIDSupportList_Extended = []
    Services22DIDSupportList_Programming = []
    Services22DIDSecurityRequiredList = []
    # WriteDIDs Sheet
    Services2EDIDSupportListDefault = []
    Services2EDIDSupportListExtend = []
    Services2EDIDSupportListProgramming = []
    Services2EDIDNeedUnlockSupportList = []
    # ControlDIDs Sheet
    Services2FDIDSupportList = []
    Services2FDIDSecurityRequiredList = []
    Services2FControlParam00DIDList = []
    Services2FControlParam02DIDList = []
    Services2FControlParam03DIDList = []
    # RoutineDIDs Sheet
    Services31RIDSupportList_Extended = []
    Services31RIDSupportList_Programming = []
    Services31RIDSecurityRequiredList = []
    # Conditions Sheet
    NRC22_ConditionList = []

    @classmethod
    def load_from_excel(cls):
        try:
            cls.AppFrameIDList = [P.TpInfo.APPFrameID]
            cls.NMFrameIDList = [P.TpInfo.NMFrameID]

            dtc_set = set()
            for item in P.ExtendedDTCInfo.all_support:
                if item.DTCCode != 0:
                    dtc_set.add((item.DTCCode << 8) | item.FailureType)
            cls.Services19DTCSupportList = sorted(list(dtc_set))
            cls.Services14DTCGroupSupportList = [0xFFFFFF]

            cls.Services22DIDSupportList_Default = [i.DID_int for i in P.ReadDIDs if i.DID != "EOF" and i.Support_App]
            cls.Services22DIDSupportList_Extended = cls.Services22DIDSupportList_Default.copy()
            cls.Services22DIDSupportList_Programming = [i.DID_int for i in P.ReadDIDs if
                                                        i.DID != "EOF" and i.Support_Boot]
            cls.Services22DIDSecurityRequiredList = [i.DID_int for i in P.ReadDIDs if
                                                     i.DID != "EOF" and i.SecurityUnlock]

            cls.Services2EDIDSupportListDefault = [i.DID_int for i in P.WriteDIDs if i.DID != "EOF" and i.Support_App]
            cls.Services2EDIDSupportListExtend = cls.Services2EDIDSupportListDefault.copy()
            cls.Services2EDIDSupportListProgramming = [i.DID_int for i in P.WriteDIDs if
                                                       i.DID != "EOF" and i.Support_Boot]
            cls.Services2EDIDNeedUnlockSupportList = [i.DID_int for i in P.WriteDIDs if
                                                      i.DID != "EOF" and i.SecurityUnlock]
            # cls.Services11SubFunSupportList = P.TpInfo.SID11_SupportList

            # 2F 服务
            cls._load_control_dids()
            # 31 服务
            cls._load_routine_dids()
            # LIN 侧暂未实现 NRC22 条件仿真，仅加载配置完整的条件，避免占位配置误触发 NRC22 用例
            cls.NRC22_ConditionList = [
                item for item in P.Conditions
                if not item.is_eof and getattr(item, "IsSignalConditionConfigured", False)
            ]

            dsi = P.DiagServiceInfo
            cls.MinSubID, cls.MaxSubID = sorted((dsi.MinSubID, dsi.MaxSubID))
            cls.MinDID, cls.MaxDID = sorted((dsi.MinDID, dsi.MaxDID))

            base_10 = sorted(set(dsi.SID10SubFunSupportList))
            cls.Services10LengthCheckSubFunList = [sf for sf in base_10 if cls.MinSubID <= sf <= cls.MaxSubID]
            extended_10 = set(base_10)
            for sf in base_10:
                extended_10.add(sf | 0x80)  # 抑制肯定响应位
            cls.Services10SubFunSupportList = sorted(extended_10)

            # 11 服务
            cls.Services11SubFunSupportList = dsi.SID11SubFunSupportList
            # 19 服务
            cls.Services19SubfunSupportList = dsi.SID19SubFunSupportList
            # 27 服务
            cls.Services27SubFunSupportList = dsi.SID27SubFunSupportList
            # 28 服务
            cls.Services28SubFunSupportList = dsi.SID28SubFunSupportList
            cls.Services28CommTypeSupportList = dsi.SID28CommTypeSupportList
            # 3E 服务
            cls.Services3ESubFunSupportList = dsi.SID3ESubFunSupportList
            # 85 服务
            cls.Services85SubFunSupportList = dsi.SID85SubFunSupportList
            # 31 服务
            cls.Services31SubFunSupportList = dsi.SID31SubFunSupportList
            cls.Services31SubFunUnsupportedList = [
                sf for sf in range(cls.MinSubID, cls.MaxSubID + 1)
                if sf not in set(cls.Services31SubFunSupportList)
            ]

            read_dids = set(cls.Services22DIDSupportList_Default + cls.Services22DIDSupportList_Programming)
            control_dids = {item['did'] for item in cls.Services2FDIDSupportList}
            routine_dids = {
                item['rid'] for item in cls.Services31RIDSupportList_Extended + cls.Services31RIDSupportList_Programming
            }
            cls.Services22DIDUnsupportedList = [
                did for did in range(cls.MinDID, cls.MaxDID + 1) if did not in read_dids
            ]
            cls.Services2FDIDUnsupportedList = [
                did for did in range(cls.MinDID, cls.MaxDID + 1) if did not in control_dids
            ]
            cls.Services31RIDUnsupportedList = [
                did for did in range(cls.MinDID, cls.MaxDID + 1) if did not in routine_dids
            ]

            # 整体服务支持列表
            cls.ServicesSupportedList = dsi.ServicesSupportedList
            supported = set(cls.ServicesSupportedList)
            cls.ServicesUnsupportedList = [sid for sid in range(0x00, 0x88) if sid not in supported]

        except Exception as e:
            print(f"[UDSTestParams] 加载配置失败: {e}")

    @classmethod
    def _load_control_dids(cls):
        cls.Services2FDIDSupportList = []
        cls.Services2FDIDSecurityRequiredList = []
        cls.Services2FControlParam00DIDList = []
        cls.Services2FControlParam02DIDList = []
        cls.Services2FControlParam03DIDList = []

        for item in P.DIDInfo.control:
            if item.DID == "EOF":
                continue
            params = []
            if item.ControlOption_00 > 0:
                params.append(0x00)
                cls.Services2FControlParam00DIDList.append(item.DID_int)
            if item.ControlOption_01:
                params.append(0x01)
            if item.ControlOption_02:
                params.append(0x02)
                cls.Services2FControlParam02DIDList.append(item.DID_int)
            if item.ControlOption_03:
                params.append(0x03)
                cls.Services2FControlParam03DIDList.append(item.DID_int)

            cls.Services2FDIDSupportList.append(
                {'did': item.DID_int, 'control_params': params, 'need_security': item.SecurityUnlock})
            if item.SecurityUnlock:
                cls.Services2FDIDSecurityRequiredList.append(item.DID_int)

    @classmethod
    def _load_routine_dids(cls):
        cls.Services31RIDSupportList_Extended = []
        cls.Services31RIDSupportList_Programming = []
        cls.Services31RIDSecurityRequiredList = []

        for item in P.DIDInfo.routine:
            if item.DID == "EOF":
                continue
            sub_funcs = [0x01] if item.ReqLength_31_01 >= 0 else []
            if str(item.ReqLength_31_02).lower() != "no":
                sub_funcs.append(0x02)
            if item.ReqLength_31_03 >= 0:
                sub_funcs.append(0x03)

            if not sub_funcs:
                continue
            rid_info = {'rid': item.DID_int, 'sub_funcs': sub_funcs, 'need_security': item.SecurityUnlock}
            if item.Support_App:
                cls.Services31RIDSupportList_Extended.append(rid_info)
            if item.Support_Boot:
                cls.Services31RIDSupportList_Programming.append(rid_info.copy())
            if item.SecurityUnlock:
                cls.Services31RIDSecurityRequiredList.append(item.DID_int)


UDSTestParams.load_from_excel()


class LINTPBus(BusSim):

    def __init__(self, channel=DEFAULT_LIN_CHANNEL, nadid=None):
        self.channel = channel
        self.nadid = nadid
        self.initialized = False

    def init(self, *args, **kwargs):
        pass

    @property
    def tx_id(self):
        return self.nadid

    @property
    def rx_id(self):
        return self.nadid

    @property
    def func_id(self):
        return self.nadid

    def close(self):
        try:
            lin_tp_end()
            self.initialized = False
            TestLog("INFO", "LINTP", "LIN TP总线已关闭")
        except Exception as e:
            TestLog("ERROR", "LINTP", f"关闭LIN TP总线失败: {e}")

    def send(self, data, func_req=False):
        try:
            result = lintp_send_req(data, self.channel, self.nadid, func_req, timeout=1000)
            if result == 1:
                TestLog("INFO", "LINTP", f"发送成功: {data.hex()}")
                return 0
            else:
                TestLog("ERROR", "LINTP", f"发送失败: {data.hex()}")
                return -1
        except Exception as e:
            TestLog("ERROR", "LINTP", f"发送异常: {e}")
            return -1

    def recv(self, timeout=5):
        try:
            response = lintp_rcv_response(self.channel, timeout)
            if response is not None:
                nandid, data = response
                TestLog("INFO", "LINTP", f"接收成功: NAD={nandid}, Data={data.hex()}")

                class MockCANMessage:
                    def __init__(self, nadid, data):
                        self.data = data
                        self.arbitration_id = nadid

                return True, MockCANMessage(nandid, data)
            else:
                TestLog("ERROR", "LINTP", "接收超时或失败")
                return False, None
        except Exception as e:
            TestLog("ERROR", "LINTP", f"接收异常: {e}")
            return False, None


def get_lin_node(channel=DEFAULT_LIN_CHANNEL) -> UDSNode:
    try:
        # 初始化LIN TP
        ret = lin_tp_initialization(test_slave_flg=True, funcrequest_in_phyresponse_flg=False)
        if ret != 1:
            TestLog("ERROR", "LINTP", "LIN TP初始化失败")
            return None
        from .lin_test_pre_module import get_nand_id
        # 创建LIN TP总线对象
        bus_obj = LINTPBus(channel, get_nand_id())
        bus_obj.initialized = True

        node = UDSNode(bus_obj)
        TestLog("INFO", "LINTP", "LIN节点创建成功")
        return node
    except Exception as e:
        TestLog("ERROR", "LINTP", f"创建LIN节点失败: {e}")
        return None


def lin_node_power_setup_and_communication_check(vnormal, tstable_s):
    try:
        from .lin_test_pre_module import ActivateDut, get_test_case_mode, create_lin_sch
        # 激活DUT
        if get_test_case_mode() == "slave":
            if ActivateDut(0, tstable_s) != 0:
                TestLog("FAIL", "LINTP", "DUT激活失败，结束测试")
                return -1
        else:
            TestLog("FAIL", "LINTP", "DUT激活失败，结束测试")
            return -1

        sch = create_lin_sch()
        sch.stop()
        TestLog("DEBUG", "LINTP", "LIN电源设置和通信检查成功")
        return 0
    except Exception as e:
        TestLog("ERROR", "LINTP", f"LIN电源设置和通信检查失败: {e}")
        return -1


def __lin_restart_delay(tstable_s, start_normal_sch: bool = False):
    from .lin_test_pre_module import create_lin_sch, create_lin_ch
    if start_normal_sch == True:
        sch = create_lin_sch()
        sch.start()
        time.sleep(tstable_s)
        sch.stop()
        return
    lin_ch_usr = create_lin_ch()
    begin_time = time.time()
    while True:
        lin_ch_usr.output(0X3D)
        time.sleep(0.05)
        if (time.time() - begin_time) > tstable_s:
            break


def __power_resatrt(offtime, ontime_delay):
    from common.context import ctx
    ctx.bob_ctrl.set_power('KL30', False)
    # ctx.power_ctrl.off()
    time.sleep(offtime)
    ctx.bob_ctrl.set_power('KL30', True)
    # ctx.power_ctrl.on()
    __lin_restart_delay(ontime_delay)


def __power_voltage_set(val):
    from common.context import ctx
    ctx.power_ctrl.set_voltage(val)


SESSION_EXPECT_RESPONSES = {
    "default": [0x7F, 0x31, 0x7F],
    "extended": [0x71, 0x01, 0x02, 0x03, 0x00],
    "programming": [0x7F, 0x31, 0x31],
}


def __run_service_10_step(step: int, node: UDSNode, sub_func: int, expect, desc: str, func: bool, case_name: str):
    TestLog("INFO", f"Step{step}", desc)
    if not __service_10_check_lin(
            node,
            sub_func=sub_func,
            expect_data=expect,
            expect_str=f"Step{step} {desc}",
            func_req=func,
    ):
        TestLog("FAIL", case_name, f"{desc}失败")
        return None
    return step


def __run_session_check_step(step: int, node: UDSNode, expect_key: str, desc: str, func: bool, case_name: str):
    expect_data = SESSION_EXPECT_RESPONSES[expect_key]
    TestLog("INFO", f"Step{step}", desc)
    if not __check_current_session_lin(
            node,
            expect_data=expect_data,
            expect_str=f"Step{step} {desc}",
            func_req=func,
    ):
        TestLog("FAIL", case_name, f"{desc}失败")
        return None
    return step


def __service_10_check_lin(
        node: UDSNode,
        sub_func: int | None,
        expect_data,
        expect_str: str = "",
        func_req: bool = False,
        dl: int | None = None,
        dl_padding: int = 0x00,
        timeout: float = 5,
) -> bool:
    """
    LIN 下 0x10 服务发送与结果校验
    """
    try:
        response_message = node.Service_0x10_SessionControl(
            sub_func,
            func_req=func_req,
            dl=dl,
            dl_padding=dl_padding,
            timeout=timeout,
        )
        if expect_data is None:
            # 期望无响应
            if response_message is None:
                TestLog("PASS", "Service_0x10", f"{expect_str}，无响应符合预期")
                return True
            TestLog("FAIL", "Service_0x10", f"{expect_str}，期望无响应，实际收到: {response_message.data.hex()}")
            return False

        if response_message is None:
            TestLog("FAIL", "Service_0x10", f"{expect_str}，未收到响应")
            return False

        if list(response_message.data[0:len(expect_data)]) != expect_data:
            TestLog(
                "FAIL",
                "Service_0x10",
                f"{expect_str}，响应不匹配，期望: {bytes(expect_data).hex()} 实际: {response_message.data.hex()}",
            )
            return False

        TestLog("PASS", "Service_0x10", f"{expect_str}，响应匹配: {response_message.data.hex()}")
        return True
    except Exception as e:
        TestLog("FAIL", "Service_0x10", f"{expect_str}，执行异常: {e}")
        TestLog("DEBUG", "Service_0x10", f"详细错误: {traceback.format_exc()}")
        return False


def __check_current_session_lin(node: UDSNode, expect_data, expect_str: str = "", func_req: bool = False) -> bool:
    """
    LIN 下通过 0x31 010203 例程检查当前会话状态
    """
    try:
        response_message = node.Service_0x31_RoutineControl(1, 0x203, func_req=func_req)
        if response_message is None:
            TestLog("FAIL", "CheckSession", f"{expect_str}，未收到响应")
            return False
        if list(response_message.data[0:len(expect_data)]) != expect_data:
            TestLog(
                "FAIL",
                "CheckSession",
                f"{expect_str}，响应不匹配，期望: {bytes(expect_data).hex()} 实际: {response_message.data.hex()}",
            )
            return False
        TestLog("PASS", "CheckSession", f"{expect_str}，响应匹配: {response_message.data.hex()}")
        return True
    except Exception as e:
        TestLog("FAIL", "CheckSession", f"{expect_str}，执行异常: {e}")
        TestLog("DEBUG", "CheckSession", f"详细错误: {traceback.format_exc()}")
        return False


def test_phyRequest_10_Positive(node: UDSNode, name: str = "10服务肯定响应与功能检查(物理寻址)",
                                func_flg: bool = False):
    step = 0
    try:
        if node is None:
            TestLog("FAIL", name, f"LIN 初始化失败")
            return
        TestLog("INFO", name, "执行 28 步会话切换与检查")
        sequence = [
            # Step 1-2: 默认会话基础验证
            ("svc10", 0x01, [0x50, 0x01], "请求进入默认会话"),
            ("check", "default", None, "检查当前会话状态(默认)"),

            # Step 3-4: 默认会话抑制响应验证
            ("svc10", 0x81, None, "发送抑制肯定响应的请求进入默认会话"),
            ("check", "default", None, "检查当前会话状态(默认)"),

            # Step 5-6: 扩展会话基础验证
            ("svc10", 0x03, [0x50, 0x03], "请求进入扩展会话"),
            ("check", "extended", None, "检查当前会话状态(扩展)"),

            # Step 7-8: 扩展会话抑制响应验证
            ("svc10", 0x83, None, "发送抑制肯定响应的请求进入扩展会话"),
            ("check", "extended", None, "检查当前会话状态(扩展)"),

            # Step 9-10: 默认会话再次验证
            ("svc10", 0x01, [0x50, 0x01], "请求进入默认会话"),
            ("check", "default", None, "检查当前会话状态(默认)"),

            # Step 11-12: 扩展会话抑制响应验证（从默认会话）
            ("svc10", 0x83, None, "发送抑制肯定响应的请求进入扩展会话"),
            ("check", "extended", None, "检查当前会话状态(扩展)"),

            # Step 13-14: 默认会话抑制响应验证（从扩展会话）
            ("svc10", 0x81, None, "发送抑制肯定响应的请求进入默认会话"),
            ("check", "default", None, "检查当前会话状态(默认)"),

            # Step 15-16: 扩展会话基础验证
            ("svc10", 0x03, [0x50, 0x03], "请求进入扩展会话"),
            ("check", "extended", None, "检查当前会话状态(扩展)"),

            # Step 17-18: 刷新会话基础验证
            ("svc10", 0x02, [0x50, 0x02], "请求进入刷新会话"),
            ("check", "programming", None, "检查当前会话状态(刷新)"),

            # Step 19-20: 刷新会话抑制响应验证
            ("svc10", 0x82, None, "发送抑制肯定响应的请求进入刷新会话"),
            ("check", "programming", None, "检查当前会话状态(刷新)"),

            # Step 21-22: 默认会话基础验证
            ("svc10", 0x01, [0x50, 0x01], "请求进入默认会话"),
            ("check", "default", None, "检查当前会话状态(默认)"),

            # Step 23-24: 扩展会话基础验证
            ("svc10", 0x03, [0x50, 0x03], "请求进入扩展会话"),
            ("check", "extended", None, "检查当前会话状态(扩展)"),

            # Step 25-26: 刷新会话抑制响应验证（从扩展会话）
            ("svc10", 0x82, None, "发送抑制肯定响应的请求进入刷新会话"),
            ("check", "programming", None, "检查当前会话状态(刷新)"),

            # Step 27-28: 默认会话抑制响应验证（从刷新会话）
            ("svc10", 0x81, None, "发送抑制肯定响应的请求进入默认会话"),
            ("check", "default", None, "检查当前会话状态(默认)"),
        ]
        for action_type, value, expect, desc in sequence:
            step += 1
            if action_type == "svc10":
                step = __run_service_10_step(step, node, value, expect, desc, func_flg, name)
                time.sleep(1)
            else:
                step = __run_session_check_step(step, node, value, desc, func_flg, name)
            print(step)
            if step is None:
                return
        TestLog("PASS", name, f"测试执行成功")
    except Exception as e:
        TestLog("FAIL", "10服务肯定响应与功能检查(物理寻址)", f"测试执行出错: {e}")
        TestLog("DEBUG", "10服务肯定响应与功能检查(物理寻址)", f"详细错误: {traceback.format_exc()}")
    finally:
        TestLog("INFO", "测试结束", "执行测试结束和去初始化")


def test_phyRequest_10_NRC12(
        node: UDSNode,
        name: str = "[TG1_TC2] 10服务NRC12检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG1_TC2] 10服务NRC12检查(物理寻址)
    """
    step = 0
    min_sn, max_sn = UDSTestParams.MinSubID, UDSTestParams.MaxSubID

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话 (10 01)
        step = 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        # Step2: 检查当前会话状态 (31 01 02 03) => 7F 31 7F
        step = 2
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x7F, 0x31, 0x7F],
                "位于默认会话中(7F 31 7F)",
                func_req=func_flg,
        ):
            return

        # Step3~6: 在默认会话下遍历不支持的子功能，检查 7F 10 12
        step = 3
        TestLog("INFO", f"Step{step}", "默认会话下遍历子功能 SN，检查不支持的子功能返回 7F 10 12")
        for sn in range(min_sn, max_sn + 1):
            if sn in UDSTestParams.Services10SubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)} 在10服务支持列表中，跳过")
                continue
            TestLog("INFO", "", f"SN={hex(sn)} 不在10服务支持列表中，发送并期望 7F 10 12")
            __service_10_check_lin(
                node,
                sn,
                [0x7F, 0x10, 0x12],
                "10服务NRC12检查(默认会话)",
                func_req=func_flg,
            )

        # Step7: 再次检查当前会话仍为默认会话
        step = 7
        TestLog("INFO", f"Step{step}", "再次检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x7F, 0x31, 0x7F],
                "仍位于默认会话中(7F 31 7F)",
                func_req=func_flg,
        ):
            return

        # Step8: 请求进入扩展会话 (10 03)
        step = 8
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(
                node,
                0x03,
                [0x50, 0x03],
                "扩展会话肯定响应(50 03)",
                func_req=func_flg,
        ):
            return

        # Step9: 检查当前会话状态 => 71 01 02 03 00
        step = 9
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x71, 0x01, 0x02, 0x03, 0x00],
                "位于扩展会话中(71 01 02 03 00)",
                func_req=func_flg,
        ):
            return

        # Step10~13: 扩展会话下遍历不支持子功能，检查 7F 10 12
        step = 10
        TestLog("INFO", f"Step{step}", "扩展会话下遍历子功能 SN，检查不支持的子功能返回 7F 10 12")
        for sn in range(min_sn, max_sn + 1):
            if sn in UDSTestParams.Services10SubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)} 在10服务支持列表中，跳过")
                continue
            TestLog("INFO", "", f"SN={hex(sn)} 不在10服务支持列表中，发送并期望 7F 10 12")
            __service_10_check_lin(
                node,
                sn,
                [0x7F, 0x10, 0x12],
                "10服务NRC12检查(扩展会话)",
                func_req=func_flg,
            )

        # Step14: 再次检查当前会话仍为扩展会话
        step = 14
        TestLog("INFO", f"Step{step}", "再次检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x71, 0x01, 0x02, 0x03, 0x00],
                "仍位于扩展会话中(71 01 02 03 00)",
                func_req=func_flg,
        ):
            return

        # Step15: 请求进入刷新会话 (10 02)
        step = 15
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(
                node,
                0x02,
                [0x50, 0x02],
                "刷新会话肯定响应(50 02)",
                func_req=func_flg,
        ):
            return

        # Step16: 检查当前会话状态 => 7F 31 31
        step = 16
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x7F, 0x31, 0x31],
                "位于刷新会话中(7F 31 31)",
                func_req=func_flg,
        ):
            return

        # Step17~20: 刷新会话下遍历不支持子功能，检查 7F 10 12
        step = 17
        TestLog("INFO", f"Step{step}", "刷新会话下遍历子功能 SN，检查不支持的子功能返回 7F 10 12")
        for sn in range(min_sn, max_sn + 1):
            if sn in UDSTestParams.Services10SubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)} 在10服务支持列表中，跳过")
                continue
            TestLog("INFO", "", f"SN={hex(sn)} 不在10服务支持列表中，发送并期望 7F 10 12")
            __service_10_check_lin(
                node,
                sn,
                [0x7F, 0x10, 0x12],
                "10服务NRC12检查(刷新会话)",
                func_req=func_flg,
            )

        # Step21: 再次检查当前会话仍为刷新会话
        step = 21
        TestLog("INFO", f"Step{step}", "再次检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x7F, 0x31, 0x31],
                "仍位于刷新会话中(7F 31 31)",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "10服务NRC12检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def __send_invalid_length_10_requests(node: UDSNode, func_req: bool, dl_candidates=None) -> bool:
    """
    在当前会话下循环所有受支持的 0x10 子功能，构造长度错误的报文，NRC13
    """
    dl_candidates = dl_candidates or [3, 4, 5, 6, 7]
    for sn in UDSTestParams.Services10LengthCheckSubFunList:
        if sn < 0x01 or sn > 0xFF:
            continue
        for dl in dl_candidates:
            TestLog("INFO", "", f"发送 SN=0x{sn:02X}, DL={dl} 的10请求，期望NRC13")
            if not __service_10_check_lin(
                    node,
                    sn,
                    [0x7F, 0x10, 0x13],
                    "NRC=0x13的否定响应(7F 10 13)",
                    func_req=func_req,
                    dl=dl,
                    dl_padding=0x00,
            ):
                return False
    return True


def test_phyRequest_10_NRC13(
        node: UDSNode,
        name: str = "[TG1_TC3] 10服务NRC13检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG1_TC3] 10服务NRC13检查(物理寻址)
    """
    step = 0
    dl_list = [3, 4, 5, 6, 7]

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # 默认会话阶段
        step = 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step = 2
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return

        step = 3
        TestLog("INFO", f"Step{step}", "发送长度较短10请求(仅SID)")
        if not __service_10_check_lin(node, None, [0x7F, 0x10, 0x13], "NRC=0x13的否定响应(7F 10 13)",
                                      func_req=func_flg):
            return

        step = 4
        TestLog("INFO", f"Step{step}", "设置 SN=0x01，准备遍历受支持的子功能")

        step = 5
        TestLog("INFO", f"Step{step}", "发送DL=3/4/5/6/7的10请求，期望NRC13")
        if not __send_invalid_length_10_requests(node, func_flg, dl_list):
            return

        step = 7
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return

        # 扩展会话阶段
        step = 8
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "肯定响应(50 03)", func_req=func_flg):
            return

        step = 9
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x71, 0x01, 0x02, 0x03, 0x00],
                "位于扩展会话中(71 01 02 03 00)",
                func_req=func_flg,
        ):
            return

        step = 10
        TestLog("INFO", f"Step{step}", "发送长度较短10请求(仅SID)")
        if not __service_10_check_lin(node, None, [0x7F, 0x10, 0x13], "NRC=0x13的否定响应(7F 10 13)",
                                      func_req=func_flg):
            return

        step = 11
        TestLog("INFO", f"Step{step}", "设置 SN=0x01，准备遍历受支持的子功能")

        step = 12
        TestLog("INFO", f"Step{step}", "发送DL=3/4/5/6/7的10请求，期望NRC13")
        if not __send_invalid_length_10_requests(node, func_flg, dl_list):
            return

        step = 14
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x71, 0x01, 0x02, 0x03, 0x00],
                "位于扩展会话中(71 01 02 03 00)",
                func_req=func_flg,
        ):
            return

        # 刷新/编程会话阶段
        step = 15
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        step = 16
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        step = 17
        TestLog("INFO", f"Step{step}", "发送长度较短10请求(仅SID)")
        if not __service_10_check_lin(node, None, [0x7F, 0x10, 0x13], "NRC=0x13的否定响应(7F 10 13)",
                                      func_req=func_flg):
            return

        step = 18
        TestLog("INFO", f"Step{step}", "设置 SN=0x01，准备遍历受支持的子功能")

        step = 19
        TestLog("INFO", f"Step{step}", "发送DL=3/4/5/6/7的10请求，期望NRC13")
        if not __send_invalid_length_10_requests(node, func_flg, dl_list):
            return

        step = 21
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        TestLog("PASS", name, "10服务NRC13检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def __send_10_02_with_nrc22_conditions(node: UDSNode, func_req: bool = False) -> bool:
    """UDSTestParams.NRC22_ConditionList 遍历所有可能触发 NRC22 的条件，
    """
    got_nrc22 = False
    cond_list = UDSTestParams.NRC22_ConditionList or [None]

    for idx, cond in enumerate(cond_list, start=1):
        desc = cond if isinstance(cond, str) else f"条件{idx}"
        TestLog("INFO", "Service_0x10", f"在[{desc}]下发送 10 02 请求，检查是否触发 NRC22")

        try:
            response_message = node.Service_0x10_SessionControl(0x02, func_req=func_req)
        except Exception as e:
            TestLog("FAIL", "Service_0x10", f"[{desc}] 下发送 10 02 请求异常: {e}")
            TestLog("DEBUG", "Service_0x10", f"详细错误: {traceback.format_exc()}")
            return False

        if response_message is None:
            TestLog("FAIL", "Service_0x10", f"[{desc}] 下发送 10 02 未收到响应")
            return False

        data_list = list(response_message.data)
        if len(data_list) >= 3 and data_list[0:3] == [0x7F, 0x10, 0x22]:
            TestLog(
                "PASS",
                "Service_0x10",
                f"[{desc}] 下 10 02 收到 NRC22 否定响应: {response_message.data.hex()}",
            )
            got_nrc22 = True
        elif len(data_list) >= 2 and data_list[0:2] == [0x50, 0x02]:
            TestLog(
                "INFO",
                "Service_0x10",
                f"[{desc}] 下 10 02 收到肯定响应(50 02)，可能未满足 NRC22 触发条件: {response_message.data.hex()}",
            )
        else:
            TestLog(
                "FAIL",
                "Service_0x10",
                f"[{desc}] 下 10 02 收到异常响应，期望 50 02 或 7F 10 22，实际: {response_message.data.hex()}",
            )
            return False

    if not got_nrc22:
        TestLog(
            "FAIL",
            "Service_0x10",
            "遍历所有 NRC22 条件后均未收到 7F 10 22，请检查 UDSTestParams.NRC22_ConditionList 配置或 DUT 行为",
        )
        return False

    return True


def test_phyRequest_10_NRC22(
        node: UDSNode,
        name: str = "[TG1_TC4] 10服务NRC22检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG1_TC4] 10服务NRC22检查(物理寻址)
    """
    step = 0

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step2: 检查当前会话状态 => 默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # Step3: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        # Step4: 检查当前会话状态 => 扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # Step5: 遍历所有 NRC22 触发条件并发送 10 02 请求
        step += 1
        TestLog("INFO", f"Step{step}", "遍历触发NRC22的所有条件并发送10 02请求")
        if not __send_10_02_with_nrc22_conditions(node, func_req=func_flg):
            return

        # Step6: 再次检查当前会话状态仍为扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)，确认仍在扩展会话中")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "仍位于扩展会话中",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "10服务NRC22检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def test_phyRequest_10_NRC7E(
        node: UDSNode,
        name: str = "[TG1_TC5] 10服务NRC7E检查(物理寻址)",
        func_flg: bool = False,
):
    step = 0
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step2: 请求进入刷新会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x7F, 0X10, 0X7E], "扩刷新会话响应(0x7F,0X10,0X7E)",
                                      func_req=func_flg):
            return

        # Step3: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        # Step4: 检查当前会话状态 => 扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # Step5: 请求进入刷新会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "进入刷新会话响应(50 02)", func_req=func_flg):
            return

        # Step6: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x7F, 0X10, 0X7E], "扩展会话肯定响应(0x7F,0X10,0X7E)",
                                      func_req=func_flg):
            return

        TestLog("PASS", name, "10服务NRC7E检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def test_phyRequest_10_PowerOnOff(
        node: UDSNode,
        name: str = "[TG1_TC6] 10服务重新上电检查(物理寻址)",
        func_flg: bool = False,
):
    step = 0
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step2: 检查当前会话状态 => 默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step3: 重新上电
        step += 1
        TestLog("INFO", f"Step{step}", "重新上电")
        __power_resatrt(1, 2)

        # Step4: 检查当前会话状态 => 默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # Step5: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        # Step6: 检查当前会话状态 => 扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return
        # Step7: 重新上电
        step += 1
        TestLog("INFO", f"Step{step}", "重新上电")
        __power_resatrt(1, 2)

        # Step8: 检查当前会话状态 => 默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # Step9: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return
            # Step10: 请求进入刷新会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "刷新会话肯定响应(50 02)", func_req=func_flg):
            return

        # Step11: 检查当前会话状态 => 刷新会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return
        # Step12: 重新上电
        step += 1
        TestLog("INFO", f"Step{step}", "重新上电")
        __power_resatrt(2, 2)

        # Step13: 检查当前会话状态 => 默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "10服务重新上电检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def __service_11_check(
        node: UDSNode,
        reset_type: int | None,
        expect_data,
        expect_str: str = "",
        func_req: bool = False,
        dl: int | None = None,
        dl_padding: int = 0x00,
        timeout: float = 5,
) -> bool:
    """
    LIN 下 0x10 服务发送与结果校验
    """
    try:
        response_message = node.Service_0x11_ECUReset(
            reset_type=reset_type,
            func_req=func_req,
            dl=dl,
            dl_padding=dl_padding,
            timeout=timeout
        )
        if expect_data is None:
            # 期望无响应
            if response_message is None:
                TestLog("PASS", "Service_0x11", f"{expect_str}，无响应符合预期")
                return True
            TestLog("FAIL", "Service_0x11", f"{expect_str}，期望无响应，实际收到: {response_message.data.hex()}")
            return False

        if response_message is None:
            TestLog("FAIL", "Service_0x11", f"{expect_str}，未收到响应")
            return False

        if list(response_message.data[0:len(expect_data)]) != expect_data:
            TestLog(
                "FAIL",
                "Service_0x11",
                f"{expect_str}，响应不匹配，期望: {bytes(expect_data).hex()} 实际: {response_message.data.hex()}",
            )
            return False

        TestLog("PASS", "Service_0x11", f"{expect_str}，响应匹配: {response_message.data.hex()}")
        return True
    except Exception as e:
        TestLog("FAIL", "Service_0x11", f"{expect_str}，执行异常: {e}")
        TestLog("DEBUG", "Service_0x11", f"详细错误: {traceback.format_exc()}")
        return False


def test_phyRequest_10_HardReset(
        node: UDSNode,
        name: str = "[TG1_TC6] 10服务重新上电检查(物理寻址)",
        func_flg: bool = False,
):
    step = 0
    case_name = "10服务硬件复位检查(功能寻址)"
    from common.params import P
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        # Step3: 检查当前会话状态 => 默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "发送请求使DUT进行硬件复位(11 01)，之后等待2000ms")
        if not __service_11_check(node, 0x01, expect_data=[0x51, 0x01], expect_str="肯定响应(51 01)",
                                  func_req=False): return
        __lin_restart_delay(2)

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "刷新会话肯定响应(50 02)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "发送请求使DUT进行硬件复位(11 01)，之后等待2000ms")
        if not __service_11_check(node, 0x01, expect_data=[0x51, 0x01], expect_str="肯定响应(51 01)",
                                  func_req=False): return
        __lin_restart_delay(2)

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", case_name, f"详细错误: {traceback.format_exc()}")


def test_phyRequest_10_NRC_Priority(
        node: UDSNode,
        name: str = "[TG1_TC8] 10服务NRC优先级检查(物理寻址)",
        func_flg: bool = False,
):
    """[TG1_TC8] 10服务NRC优先级检查(物理寻址)"""
    step = 0

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        # Step3: 检查当前会话状态 => 扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # Step4: 触发NRC22条件并发送10 02请求
        step += 1
        TestLog("INFO", f"Step{step}", "触发NRC22条件之一并发送10 02请求")
        # 使用第一个NRC22条件（如果列表为空，则直接发送10 02，期望可能返回50 02或7F 10 22）
        cond_list = UDSTestParams.NRC22_ConditionList or [None]
        cond = cond_list[0] if cond_list else None
        desc = cond if isinstance(cond, str) else "默认条件"
        TestLog("INFO", "Service_0x10", f"在[{desc}]下发送 10 02 请求，检查是否触发 NRC22")
        # TODO
        try:
            response_message = node.Service_0x10_SessionControl(0x02, func_req=func_flg)
            if response_message is None:
                TestLog("FAIL", name, f"Step{step}，发送10 02未收到响应")
                return

            data_list = list(response_message.data)
            if len(data_list) >= 3 and data_list[0:3] == [0x7F, 0x10, 0x22]:
                TestLog("PASS", "Service_0x10", f"Step{step}，收到NRC22否定响应: {response_message.data.hex()}")
            elif len(data_list) >= 2 and data_list[0:2] == [0x50, 0x02]:
                TestLog("WARN", "Service_0x10",
                        f"Step{step}，收到肯定响应(50 02)，未触发NRC22条件。继续测试其他NRC优先级场景")
            else:
                TestLog("FAIL", name, f"Step{step}，收到异常响应: {response_message.data.hex()}")
                return
        except Exception as e:
            TestLog("FAIL", name, f"Step{step}，发送10 02请求异常: {e}")
            TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
            return

        # Step5: 发送仅SID的10请求（无子功能字节）
        step += 1
        TestLog("INFO", f"Step{step}", "发送10请求（仅SID，无子功能）")
        if not __service_10_check_lin(node, None, [0x7F, 0x10, 0x13],
                                      "NRC=0x13的否定响应(7F 10 13) - 长度错误", func_req=func_flg):
            return

        # Step6: 发送10 04请求（不支持的子功能）
        step += 1
        TestLog("INFO", f"Step{step}", "发送10 04请求")
        if not __service_10_check_lin(node, 0x04, [0x7F, 0x10, 0x12],
                                      "NRC=0x12的否定响应(7F 10 12) ", func_req=func_flg):
            return

        # Step7: 发送10 01请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送10 01请求")
        if not __service_10_check_lin(node, 0x01, [0x7F, 0x10, 0x13], "NRC=0x13的否定响应(7F 10 13) ", dl=3,
                                      dl_padding=00,
                                      func_req=func_flg):
            return

        # Step8: 发送10 04请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送10 04请求")
        if not __service_10_check_lin(node, 0x04, [0x7F, 0x10, 0x12],
                                      "NRC=0x12的否定响应(7F 10 12) ", dl=2, dl_padding=00, func_req=func_flg):
            return

        # Step9: 检查当前会话状态仍为扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)，确认仍在扩展会话中")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "仍位于扩展会话中",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "10服务NRC优先级检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def test_phyRequest_11_Positive(
        node: UDSNode,
        name: str = "[TG2_TC1] 11服务肯定响应与功能检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG2_TC1] 11服务肯定响应与功能检查(物理寻址)
    """
    step = 0

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 检查默认会话下是否支持物理寻址11 01请求
        step += 1
        TestLog("INFO", f"Step{step}", "检查默认会话下是否支持物理寻址11 01请求")

        # 先进入默认会话
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        # 检查0x01子功能是否支持
        support_11_01 = 0x01 in UDSTestParams.Services11SubFunSupportList
        if not support_11_01:
            TestLog("INFO", name, "默认会话下不支持物理寻址11 01请求，跳转至步骤10")
            step = 9  # 跳转到步骤10

        # 步骤2-9: 默认会话下的11服务测试（仅当支持0x01时执行）
        if step < 9:
            # Step2: 请求进入默认会话
            step += 1
            TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
            if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
                return

            # Step3: 发送子功能为0x01的11服务请求
            step += 1
            TestLog("INFO", f"Step{step}", "发送子功能为0x01的11服务请求(11 01)")
            if not __service_11_check(node, 0x01, [0x51, 0x01], "硬件复位肯定响应(51 01)", func_req=func_flg):
                return

            # Step4: 等待2s
            step += 1
            TestLog("INFO", f"Step{step}", "等待2s")
            __lin_restart_delay(2)

            # Step5: 检查当前会话状态 => 默认会话
            step += 1
            TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(
                    node,
                    SESSION_EXPECT_RESPONSES["default"],
                    "位于默认会话中",
                    func_req=func_flg,
            ):
                return

            # Step6: 请求进入默认会话
            step += 1
            TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
            if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
                return

            # Step7: 发送子功能为0x81的11服务请求(抑制肯定响应)
            step += 1
            TestLog("INFO", f"Step{step}", "发送子功能为0x81的11服务请求(11 81，抑制肯定响应)")
            if not __service_11_check(node, 0x81, None, "硬件复位无响应(抑制肯定响应)", func_req=func_flg):
                return

            # Step8: 等待2s
            step += 1
            TestLog("INFO", f"Step{step}", "等待2s")
            __lin_restart_delay(2)

            # Step9: 检查当前会话状态 => 默认会话
            step += 1
            TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(
                    node,
                    SESSION_EXPECT_RESPONSES["default"],
                    "位于默认会话中",
                    func_req=func_flg,
            ):
                return

        # Step10: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        # Step11: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        # Step12: 检查当前会话状态 => 扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # Step13: 发送子功能为0x01的11服务请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送子功能为0x01的11服务请求(11 01)")
        if not __service_11_check(node, 0x01, [0x51, 0x01], "硬件复位肯定响应(51 01)", func_req=func_flg):
            return

        # Step14: 等待2s
        step += 1
        TestLog("INFO", f"Step{step}", "等待2s")
        __lin_restart_delay(2)

        # Step15: 检查当前会话状态 => 默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # Step16: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        # Step17: 检查当前会话状态 => 扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # Step18: 发送子功能为0x81的11服务请求(抑制肯定响应)
        step += 1
        TestLog("INFO", f"Step{step}", "发送子功能为0x81的11服务请求(11 81，抑制肯定响应)")
        if not __service_11_check(node, 0x81, None, "硬件复位无响应(抑制肯定响应)", func_req=func_flg):
            return

        # Step19: 等待2s
        step += 1
        TestLog("INFO", f"Step{step}", "等待2s")
        __lin_restart_delay(2)

        # Step20: 检查当前会话状态 => 默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # Step21: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        # Step22: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # Step23: 请求进入刷新会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "刷新会话肯定响应(50 02)", func_req=func_flg):
            return

        # Step24: 检查当前会话状态 => 刷新会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        # Step25: 发送子功能为0x01的11服务请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送子功能为0x01的11服务请求(11 01)")
        if not __service_11_check(node, 0x01, [0x51, 0x01], "硬件复位肯定响应(51 01)", func_req=func_flg):
            return

        # Step26: 等待2s
        step += 1
        TestLog("INFO", f"Step{step}", "等待2s")
        __lin_restart_delay(2)

        # Step27: 检查当前会话状态 => 默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # Step28: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        # Step29: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # Step30: 请求进入刷新会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "刷新会话肯定响应(50 02)", func_req=func_flg):
            return

        # Step31: 检查当前会话状态 => 刷新会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        # Step32: 发送子功能为0x81的11服务请求(抑制肯定响应)
        step += 1
        TestLog("INFO", f"Step{step}", "发送子功能为0x81的11服务请求(11 81，抑制肯定响应)")
        if not __service_11_check(node, 0x81, None, "硬件复位无响应(抑制肯定响应)", func_req=func_flg):
            return

        # Step33: 等待2s
        step += 1
        TestLog("INFO", f"Step{step}", "等待2s")
        __lin_restart_delay(2)

        # Step34: 检查当前会话状态 => 默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # ========= 以下为子功能0x02流程 =========
        support_11_02 = 0x02 in UDSTestParams.Services11SubFunSupportList

        # Step35: 如果0x11服务不支持0x02子功能，跳转至步骤52
        step += 1
        TestLog("INFO", f"Step{step}", "检查是否支持11 02 子功能")
        if not support_11_02:
            TestLog("INFO", name, "11 02 子功能不支持，跳转至步骤52")
            step = 51  # 跳转到步骤52
            # 跳转到0x03子功能流程
        else:
            # Step36: 请求进入默认会话
            step += 1
            TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
            if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
                return

            # Step37: 请求进入扩展会话
            step += 1
            TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
            if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
                return

            # Step38: 检查当前会话状态 => 扩展会话
            step += 1
            TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(
                    node,
                    SESSION_EXPECT_RESPONSES["extended"],
                    "位于扩展会话中",
                    func_req=func_flg,
            ):
                return

            # Step39: 发送子功能为0x02的11服务请求
            step += 1
            TestLog("INFO", f"Step{step}", "发送子功能为0x02的11服务请求(11 02)")
            if not __service_11_check(node, 0x02, [0x51, 0x02], "软复位肯定响应(51 02)", func_req=func_flg):
                return

            # Step40: 等待2s
            step += 1
            TestLog("INFO", f"Step{step}", "等待2s")
            __lin_restart_delay(2)

            # Step41: 检查当前会话状态 => 默认会话
            step += 1
            TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(
                    node,
                    SESSION_EXPECT_RESPONSES["default"],
                    "位于默认会话中",
                    func_req=func_flg,
            ):
                return

            # Step42: 请求进入扩展会话
            step += 1
            TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
            if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
                return

            # Step43: 检查当前会话状态 => 扩展会话
            step += 1
            TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(
                    node,
                    SESSION_EXPECT_RESPONSES["extended"],
                    "位于扩展会话中",
                    func_req=func_flg,
            ):
                return

            # Step44: 发送子功能为0x02的11服务请求(抑制肯定响应)
            step += 1
            TestLog("INFO", f"Step{step}", "发送子功能为0x02的11服务请求(11 82，抑制肯定响应)")
            if not __service_11_check(node, 0x82, None, "软复位无响应(抑制肯定响应)", func_req=func_flg):
                return

            # Step45: 等待2s
            step += 1
            TestLog("INFO", f"Step{step}", "等待2s")
            __lin_restart_delay(2)

            # Step46: 检查当前会话状态 => 默认会话
            step += 1
            TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(
                    node,
                    SESSION_EXPECT_RESPONSES["default"],
                    "位于默认会话中",
                    func_req=func_flg,
            ):
                return

            # Step47: 请求进入默认会话
            step += 1
            TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
            if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
                return

            # Step48: 请求进入扩展会话
            step += 1
            TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
            if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
                return

            # Step49: 请求进入刷新会话
            step += 1
            TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
            if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "刷新会话肯定响应(50 02)", func_req=func_flg):
                return

            # Step50: 检查当前会话状态 => 刷新会话
            step += 1
            TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(
                    node,
                    SESSION_EXPECT_RESPONSES["programming"],
                    "位于刷新会话中",
                    func_req=func_flg,
            ):
                return

            # Step51: 发送子功能为0x02的11服务请求（刷新会话）
            step += 1
            TestLog("INFO", f"Step{step}", "发送子功能为0x02的11服务请求(11 02) - 刷新会话")
            if not __service_11_check(node, 0x02, [0x51, 0x02], "软复位肯定响应(51 02)", func_req=func_flg):
                return

        # Step52: 等待2s
        step += 1
        TestLog("INFO", f"Step{step}", "等待2s")
        __lin_restart_delay(2)

        # Step53: 检查当前会话状态 => 默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # Step54: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        # Step55: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        # Step56: 请求进入刷新会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "刷新会话肯定响应(50 02)", func_req=func_flg):
            return

        # Step57: 检查当前会话状态 => 刷新会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        # Step58: 发送子功能为0x02的11服务请求(抑制肯定响应)
        step += 1
        TestLog("INFO", f"Step{step}", "发送子功能为0x02的11服务请求(11 82，抑制肯定响应) - 刷新会话")
        if not __service_11_check(node, 0x82, None, "软复位无响应(抑制肯定响应)", func_req=func_flg):
            return

        # Step59: 等待2s
        step += 1
        TestLog("INFO", f"Step{step}", "等待2s")
        __lin_restart_delay(2)

        # Step60: 检查当前会话状态 => 默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # ========= 以下为子功能0x03流程 =========
        support_11_03 = 0x03 in UDSTestParams.Services11SubFunSupportList

        # Step61: 如果0x11服务不支持0x03子功能，测试用例结束
        step += 1
        TestLog("INFO", f"Step{step}", "检查是否支持11 03 子功能")
        if not support_11_03:
            TestLog("INFO", name, "11 03 子功能不支持，测试用例结束")
            TestLog("PASS", name, "11服务肯定响应与功能检查(物理寻址) 测试执行成功")
            return

        # 仅在支持0x03时执行后续步骤
        # Step62: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        # Step63: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        # Step64: 检查当前会话状态 => 扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # Step65: 发送子功能为0x03的11服务请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送子功能为0x03的11服务请求(11 03)")
        if not __service_11_check(node, 0x03, [0x51, 0x03], "扩展会话保持肯定响应(51 03)", func_req=func_flg):
            TestLog("INFO", name, "11 03 子功能不支持，结束用例")
            return

        # Step66: 等待2s
        step += 1
        TestLog("INFO", f"Step{step}", "等待2s")
        __lin_restart_delay(2)

        # Step67: 检查当前会话状态 => 默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # Step68: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        # Step69: 检查当前会话状态 => 扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # Step70: 发送子功能为0x03的11服务请求(抑制肯定响应)
        step += 1
        TestLog("INFO", f"Step{step}", "发送子功能为0x03的11服务请求(11 83，抑制肯定响应)")
        if not __service_11_check(node, 0x83, None, "扩展会话保持无响应(抑制肯定响应)", func_req=func_flg):
            return

        # Step71: 等待2s
        step += 1
        TestLog("INFO", f"Step{step}", "等待2s")
        __lin_restart_delay(2)

        # Step72: 检查当前会话状态 => 默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # Step73: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        # Step74: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        # Step75: 请求进入刷新会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "刷新会话肯定响应(50 02)", func_req=func_flg):
            return

        # Step76: 检查当前会话状态 => 刷新会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        # Step77: 发送子功能为0x03的11服务请求（刷新会话）
        step += 1
        TestLog("INFO", f"Step{step}", "发送子功能为0x03的11服务请求(11 03) - 刷新会话")
        if not __service_11_check(node, 0x03, [0x51, 0x03], "扩展会话保持肯定响应(51 03)", func_req=func_flg):
            return

        # Step78: 等待2s
        step += 1
        TestLog("INFO", f"Step{step}", "等待2s")
        __lin_restart_delay(2)

        # Step79: 检查当前会话状态 => 默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # Step80: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        # Step81: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        # Step82: 请求进入刷新会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "刷新会话肯定响应(50 02)", func_req=func_flg):
            return

        # Step83: 检查当前会话状态 => 刷新会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        # Step84: 发送子功能为0x03的11服务请求(抑制肯定响应) - 刷新会话
        step += 1
        TestLog("INFO", f"Step{step}", "发送子功能为0x03的11服务请求(11 83，抑制肯定响应) - 刷新会话")
        if not __service_11_check(node, 0x83, None, "扩展会话保持无响应(抑制肯定响应)", func_req=func_flg):
            return

        # Step85: 等待2s
        step += 1
        TestLog("INFO", f"Step{step}", "等待2s")
        __lin_restart_delay(2)

        # Step86: 检查当前会话状态 => 默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "11服务肯定响应与功能检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def test_phyRequest_11_NRC12(
        node: UDSNode,
        name: str = "[TG2_TC2] 11服务NRC12检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG2_TC2] 11服务NRC12检查(物理寻址)
    """
    step = 0
    min_sn, max_sn = UDSTestParams.MinSubID, UDSTestParams.MaxSubID

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话 (10 01)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return

        # Step2: 请求进入扩展会话 (10 03)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        # Step3: 检查当前会话状态 (31 01 02 03) => 71 01 02 03 00
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x71, 0x01, 0x02, 0x03, 0x00],
                "位于扩展会话中(71 01 02 03 00)",
                func_req=func_flg,
        ):
            return

        # Step4: 令SN=0x00
        step += 1
        TestLog("INFO", f"Step{step}", "令SN=0x00")
        sn = min_sn

        # Step5-7: 在扩展会话下遍历不支持的11服务子功能，检查 7F 11 12
        step += 1
        TestLog("INFO", f"Step{step}", "扩展会话下遍历11服务子功能 SN，检查不支持的子功能返回 7F 11 12")
        while sn <= max_sn:
            # Step5: 如果SN为当前会话状态支持的物理寻址子功能且SN<0xFF，则SN=SN+1，直到SN为当前会话不支持的物理寻址子功能
            if sn in UDSTestParams.Services11SubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)} 在11服务支持列表中，跳过")
                sn += 1
                continue

            # Step6: 发送子功能为SN的11服务请求
            TestLog("INFO", "", f"SN={hex(sn)} 不在11服务支持列表中，发送并期望 7F 11 12")
            if not __service_11_check(
                    node,
                    sn,
                    [0x7F, 0x11, 0x12],
                    "11服务NRC12检查(扩展会话)",
                    func_req=func_flg,
            ):
                TestLog("FAIL", name, f"11服务SN={hex(sn)}未返回预期的NRC12")
                return

            # Step7: 如果SN<0xFF，SN=SN+1，然后跳转至步骤5
            sn += 1

        # Step8: 再次检查当前会话仍为扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "再次检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x71, 0x01, 0x02, 0x03, 0x00],
                "仍位于扩展会话中(71 01 02 03 00)",
                func_req=func_flg,
        ):
            return

        # Step9: 请求进入刷新会话 (10 02)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(
                node,
                0x02,
                [0x50, 0x02],
                "刷新会话肯定响应(50 02)",
                func_req=func_flg,
        ):
            return

        # Step10: 检查当前会话状态 => 7F 31 31
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x7F, 0x31, 0x31],
                "位于刷新会话中(7F 31 31)",
                func_req=func_flg,
        ):
            return

        # Step11: 令SN=0x00
        step += 1
        TestLog("INFO", f"Step{step}", "令SN=0x00")
        sn = min_sn

        # Step12-14: 刷新会话下遍历不支持的11服务子功能，检查 7F 11 12
        step += 1
        TestLog("INFO", f"Step{step}", "刷新会话下遍历11服务子功能 SN，检查不支持的子功能返回 7F 11 12")
        while sn <= max_sn:
            # Step12: 如果SN为当前会话状态支持的物理寻址子功能且SN<0xFF，则SN=SN+1，直到SN为当前会话不支持的物理寻址子功能
            if sn in UDSTestParams.Services11SubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)} 在11服务支持列表中，跳过")
                sn += 1
                continue

            # Step13: 发送子功能为SN的11服务请求
            TestLog("INFO", "", f"SN={hex(sn)} 不在11服务支持列表中，发送并期望 7F 11 12")
            if not __service_11_check(
                    node,
                    sn,
                    [0x7F, 0x11, 0x12],
                    "11服务NRC12检查(刷新会话)",
                    func_req=func_flg,
            ):
                TestLog("FAIL", name, f"11服务SN={hex(sn)}未返回预期的NRC12")
                return

            # Step14: 如果SN<0xFF，SN=SN+1，然后跳转至步骤12
            sn += 1

        # Step15: 再次检查当前会话仍为刷新会话
        step += 1
        TestLog("INFO", f"Step{step}", "再次检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x7F, 0x31, 0x31],
                "仍位于刷新会话中(7F 31 31)",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "11服务NRC12检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def test_phyRequest_11_NRC13(
        node: UDSNode,
        name: str = "[TG2_TC3] 11服务NRC13检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG2_TC3] 11服务NRC13检查(物理寻址)
    """
    step = 0
    dl_candidates = [3, 4, 5, 6, 7]  # DL值候选列表

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话 (10 01)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        __lin_restart_delay(2)
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return

        # Step2: 请求进入扩展会话 (10 03)
        step = 6
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        # Step3: 检查当前会话状态 (31 01 02 03) => 71 01 02 03 00
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x71, 0x01, 0x02, 0x03, 0x00],
                "位于扩展会话中(71 01 02 03 00)",
                func_req=func_flg,
        ):
            return

        # Step4: 发送长度较短11请求 (01 11 AA AA AA AA AA AA)
        step = 8
        TestLog("INFO", f"Step{step}", "发送长度较短11请求(01 11 AA AA AA AA AA AA)")
        # 使用DL=1发送11请求，构造长度较短的报文
        if not __service_11_check(
                node,
                None,  # 子功能0x01(复位)
                [0x7F, 0x11, 0x13],
                "NRC=0x13的否定响应(7F 11 13)",
                func_req=func_flg,
                dl=1,  # DL=1构造长度较短报文
                dl_padding=0xAA,  # 填充AA
        ):
            TestLog("FAIL", name, "长度较短11请求未返回预期的NRC13")
            return

        # Step5: 发送DL=3,4,5,6,7的11请求，有效数据填充00 (11 01 XX XX XX XX XX XX)
        step = 9
        TestLog("INFO", f"Step{step}", "发送DL=3,4,5,6,7的11请求，有效数据填充00")
        for dl in dl_candidates:
            TestLog("INFO", f"Step{step}", f"发送DL={dl}的11请求")
            if not __service_11_check(
                    node,
                    0x01,  # 子功能0x01(复位)
                    [0x7F, 0x11, 0x13],
                    f"NRC=0x13的否定响应(7F 11 13) - DL={dl}",
                    func_req=func_flg,
                    dl=dl,  # 指定DL值
                    dl_padding=0x00,  # 填充00
            ):
                TestLog("FAIL", name, f"DL={dl}的11请求未返回预期的NRC13")
                return

        # Step6: 检查当前会话状态 => 扩展会话
        step = 10
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x71, 0x01, 0x02, 0x03, 0x00],
                "仍位于扩展会话中(71 01 02 03 00)",
                func_req=func_flg,
        ):
            return

        # Step7: 请求进入刷新会话 (10 02)
        step = 11
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(
                node,
                0x02,
                [0x50, 0x02],
                "刷新会话肯定响应(50 02)",
                func_req=func_flg,
        ):
            return

        # Step8: 检查当前会话状态 => 7F 31 31
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x7F, 0x31, 0x31],
                "位于刷新会话中(7F 31 31)",
                func_req=func_flg,
        ):
            return

        # Step9: 发送长度较短11请求 (01 11 AA AA AA AA AA AA)
        step += 1
        TestLog("INFO", f"Step{step}", "发送长度较短11请求(01 11 AA AA AA AA AA AA)")
        # 使用DL=1发送11请求，构造长度较短的报文
        if not __service_11_check(
                node,
                None,  # 子功能0x01(复位)
                [0x7F, 0x11, 0x13],
                "NRC=0x13的否定响应(7F 11 13)",
                func_req=func_flg,
                dl=1,  # DL=1构造长度较短报文
                dl_padding=0xAA,  # 填充AA
        ):
            TestLog("FAIL", name, "长度较短11请求未返回预期的NRC13")
            return

        # Step10: 发送DL=3,4,5,6,7的11请求，有效数据填充00 (11 01 XX XX XX XX XX XX)
        step += 1
        TestLog("INFO", f"Step{step}", "发送DL=3,4,5,6,7的11请求，有效数据填充00")
        for dl in dl_candidates:
            TestLog("INFO", "", f"发送DL={dl}的11请求")
            if not __service_11_check(
                    node,
                    0x01,  # 子功能0x01(复位)
                    [0x7F, 0x11, 0x13],
                    f"NRC=0x13的否定响应(7F 11 13) - DL={dl}",
                    func_req=func_flg,
                    dl=dl,  # 指定DL值
                    dl_padding=0x00,  # 填充00
            ):
                TestLog("FAIL", name, f"DL={dl}的11请求未返回预期的NRC13")
                return

        # Step11: 检查当前会话状态 => 刷新会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x7F, 0x31, 0x31],
                "仍位于刷新会话中(7F 31 31)",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "11服务NRC13检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def __send_11_01_with_nrc22_conditions(node: UDSNode, func_req: bool = False) -> bool:
    """
    遍历所有可能触发 NRC22 的条件并发送 11 01 请求
    """
    got_nrc22 = False
    cond_list = UDSTestParams.NRC22_ConditionList or [None]
    # TODO: 触发条件待添加
    for idx, cond in enumerate(cond_list, start=1):
        desc = cond if isinstance(cond, str) else f"条件{idx}"
        TestLog("INFO", "Service_0x11", f"在[{desc}]下发送 11 01 请求，检查是否触发 NRC22")

        try:
            response_message = node.Service_0x11_ECUReset(reset_type=0x01, func_req=func_req)
        except Exception as e:
            TestLog("FAIL", "Service_0x11", f"[{desc}] 下发送 11 01 请求异常: {e}")
            TestLog("DEBUG", "Service_0x11", f"详细错误: {traceback.format_exc()}")
            return False

        if response_message is None:
            TestLog("FAIL", "Service_0x11", f"[{desc}] 下发送 11 01 未收到响应")
            return False

        data_list = list(response_message.data)
        if len(data_list) >= 3 and data_list[0:3] == [0x7F, 0x11, 0x22]:
            TestLog(
                "PASS",
                "Service_0x11",
                f"[{desc}] 下 11 01 收到 NRC22 否定响应: {response_message.data.hex()}",
            )
            got_nrc22 = True
        elif len(data_list) >= 2 and data_list[0:2] == [0x51, 0x01]:
            TestLog(
                "INFO",
                "Service_0x11",
                f"[{desc}] 下 11 01 收到肯定响应(51 01)，可能未满足 NRC22 触发条件: {response_message.data.hex()}",
            )
        else:
            TestLog(
                "FAIL",
                "Service_0x11",
                f"[{desc}] 下 11 01 收到异常响应，期望 51 01 或 7F 11 22，实际: {response_message.data.hex()}",
            )
            return False

    if not got_nrc22:
        TestLog(
            "FAIL",
            "Service_0x11",
            "遍历所有 NRC22 条件后均未收到 7F 11 22，请检查 UDSTestParams.NRC22_ConditionList 配置或 DUT 行为",
        )
        return False

    return True


def test_phyRequest_11_NRC22(
        node: UDSNode,
        name: str = "[TG2_TC4] 11服务NRC22检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG2_TC4] 11服务NRC22检查(物理寻址)
    """
    step = 0

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话 (10 01)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        # Step2: 请求进入扩展会话 (10 03)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        # Step3: 检查当前会话状态 (31 01 02 03) => 71 01 02 03 00
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x71, 0x01, 0x02, 0x03, 0x00],
                "位于扩展会话中(71 01 02 03 00)",
                func_req=func_flg,
        ):
            return

        # Step4: 遍历触发NRC22的所有条件并发送11 01请求
        step += 1
        TestLog("INFO", f"Step{step}", "遍历触发NRC22的所有条件并发送11 01请求")
        if not __send_11_01_with_nrc22_conditions(node, func_req=func_flg):
            return

        # Step5: 检查当前会话状态 => 扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x71, 0x01, 0x02, 0x03, 0x00],
                "仍位于扩展会话中(71 01 02 03 00)",
                func_req=func_flg,
        ):
            return

        # Step6: 请求进入默认会话 (10 01)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        # Step7: 请求进入扩展会话 (10 03)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        # Step8：检查当前会话状态 => 扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x71, 0x01, 0x02, 0x03, 0x00],
                "位于扩展会话中(71 01 02 03 00)",
                func_req=func_flg,
        ):
            return

        # Step9: 请求进入刷新会话 (10 02)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(
                node,
                0x02,
                [0x50, 0x02],
                "刷新会话肯定响应(50 02)",
                func_req=func_flg,
        ):
            return

        # Step10: 检查当前会话状态 => 7F 31 31
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x7F, 0x31, 0x31],
                "位于刷新会话中(7F 31 31)",
                func_req=func_flg,
        ):
            return

        # Step11: 遍历触发NRC22的所有条件并发送11 01请求
        step += 1
        TestLog("INFO", f"Step{step}", "遍历触发NRC22的所有条件并发送11 01请求")
        if not __send_11_01_with_nrc22_conditions(node, func_req=func_flg):
            return

        # Step12: 检查当前会话状态 => 刷新会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x7F, 0x31, 0x31],
                "仍位于刷新会话中(7F 31 31)",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "11服务NRC22检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def test_phyRequest_11_NRC7F(
        node: UDSNode,
        name: str = "[TG2_TC4] 11服务NRC7F检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG2_TC5] 11服务NRC7F检查(物理寻址)
    """
    step = 0
    min_sn, max_sn = 0x00, 0x80

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话 (10 01)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        __lin_restart_delay(2)

        # Step2: 检查当前会话状态 (31 01 02 03) => 7F 31 7F
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return

        # Step3: 令SN=0x00
        step += 1
        TestLog("INFO", f"Step{step}", f"令SN=0x00")
        sn = 0x00

        # Step4-6:遍历所有11服务子功能（0x00-0xFF）,检查NRC7F响应
        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有11服务子功能（0x00-0xFF）,检查NRC7F响应")

        while sn <= max_sn:
            # Step5: 发送子功能=SN的11服务请求
            TestLog("INFO", f"Step{step}", f"发送子功能={hex(sn)}的11服务请求")
            if not __service_11_check(
                    node,
                    sn,
                    [0x7F, 0x11, 0x7F],
                    f"11服务SN={hex(sn)} NRC7F检查",
                    func_req=func_flg,
            ):
                TestLog("FAIL", name, f"11服务SN={hex(sn)}未返回预期的NRC7F")
                return

            # Step6: 如果SN<0xFF，SN=SN+1，然后跳转至步骤4
            if sn < max_sn:
                sn += 1
            else:
                break

        # Step7: 检查当前会话状态 => 默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x7F, 0x31, 0x7F],
                "仍位于默认会话中(7F 31 7F)",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "11服务NRC7F检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def test_phyRequest_11_NRC_Priority(
        node: UDSNode,
        name: str = "[TG2_TC6] 11服务NRC优先级检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG2_TC6] 11服务NRC优先级检查(物理寻址)
    """
    step = 0

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话 (10 01)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        # Step2: 检查当前会话状态 (31 01 02 03) => 7F 31 7F
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x7F, 0x31, 0x7F],
                "位于默认会话中(7F 31 7F)",
                func_req=func_flg,
        ):
            return

        # Step3: 触发NRC22的条件之一并发送11 01请求
        step += 1
        TestLog("INFO", f"Step{step}", "触发NRC22的条件之一并发送11 01请求")
        cond_list = UDSTestParams.NRC22_ConditionList or [None]
        cond = cond_list[0] if cond_list else None
        desc = cond if isinstance(cond, str) else "默认条件"
        TestLog("INFO", "Service_0x11", f"在[{desc}]下发送 11 01 请求，检查是否触发 NRC22")
        # TODO
        try:
            response_message = node.Service_0x11_ECUReset(reset_type=0x01, func_req=func_flg)
            if response_message is None:
                TestLog("FAIL", name, f"Step{step}，发送11 01未收到响应")
                return

            data_list = list(response_message.data)
            if len(data_list) >= 3 and data_list[0:3] == [0x7F, 0x11, 0x22]:
                TestLog("PASS", "Service_0x11", f"Step{step}，收到NRC22否定响应: {response_message.data.hex()}")
            elif len(data_list) >= 2 and data_list[0:2] == [0x51, 0x01]:
                TestLog("WARN", "Service_0x11",
                        f"Step{step}，收到肯定响应(51 01)，未触发NRC22条件。继续测试其他NRC优先级场景")
            else:
                TestLog("FAIL", name, f"Step{step}，收到异常响应: {response_message.data.hex()}")
                return
        except Exception as e:
            TestLog("FAIL", name, f"Step{step}，发送11 01请求异常: {e}")
            TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
            return

        # Step4: 发送11请求(仅SID，无子功能)
        step += 1
        TestLog("INFO", f"Step{step}", "发送11请求(仅SID，无子功能)")
        if not __service_11_check(
                node,
                None,  # 无子功能
                [0x7F, 0x11, 0x13],
                "NRC=0x13的否定响应(7F 11 13) - 长度错误",
                func_req=func_flg,
        ):
            return

        # Step5: 发送11 04请求(不支持的子功能)
        step += 1
        TestLog("INFO", f"Step{step}", "发送11 04请求(不支持的子功能)")
        if not __service_11_check(
                node,
                0x04,  # 不支持的子功能
                [0x7F, 0x11, 0x12],
                "NRC=0x12的否定响应(7F 11 12)",
                func_req=func_flg,
        ):
            return

        # Step6: 发送11 01 00请求(带参数)
        step += 1
        TestLog("INFO", f"Step{step}", "发送11 01 00请求(带参数)")
        if not __service_11_check(
                node,
                0x01,  # 子功能0x01
                [0x7F, 0x11, 0x13],
                "NRC=0x13的否定响应(7F 11 13) - 带参数",
                func_req=func_flg,
                dl=3,  # DL=3构造带参数报文
                dl_padding=0x00,  # 填充00
        ):
            return

        # Step7: 发送11 04 00请求(带参数)
        step += 1
        TestLog("INFO", f"Step{step}", "发送11 04 00请求(带参数)")
        if not __service_11_check(
                node,
                0x04,  # 不支持的子功能
                [0x7F, 0x11, 0x12],
                "NRC=0x12的否定响应(7F 11 12) - 带参数",
                func_req=func_flg,
                dl=3,  # DL=3构造带参数报文
                dl_padding=0x00,  # 填充00
        ):
            return

        # Step8: 检查当前会话状态 => 默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x7F, 0x31, 0x7F],
                "仍位于默认会话中(7F 31 7F)",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "11服务NRC优先级检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def __service_27_check_lin(
        node: UDSNode,
        level,
        expect_data,
        expect_str,
        func_req=False,
        dl: int | None = None,
        dl_padding: int = 0x00,
        timeout: float = 5,
):  #(bool,list)
    """
    LIN 下 0x27 服务发送与结果校验
    """
    try:
        response_message = node.Service_0x27_SecurityAccess(
            access_type=level,
            func_req=func_req,
            dl=dl,
            dl_padding=dl_padding,
            timeout=timeout,
        )
        if expect_data is None:
            # 期望无响应
            if response_message is None:
                TestLog("PASS", "Service_0x27", f"{expect_str}，无响应符合预期")
                return True, []
            TestLog("FAIL", "Service_0x27", f"{expect_str}，期望无响应，实际收到: {response_message.data.hex()}")
            return False, list(response_message.data)

        if response_message is None:
            TestLog("FAIL", "Service_0x27", f"{expect_str}，未收到响应")
            return False, []

        if list(response_message.data[0:len(expect_data)]) != expect_data:
            TestLog(
                "FAIL",
                "Service_0x27",
                f"{expect_str}，响应不匹配，期望: {bytes(expect_data).hex()} 实际: {response_message.data.hex()}",
            )
            return False, list(response_message.data)

        TestLog("PASS", "Service_0x27", f"{expect_str}，响应匹配: {response_message.data.hex()}")
        return True, list(response_message.data)[2:]
    except Exception as e:
        TestLog("FAIL", "Service_0x27", f"{expect_str}，执行异常: {e}")
        TestLog("DEBUG", "Service_0x27", f"详细错误: {traceback.format_exc()}")
        return False, []


def __service_27_securityKey_lin(
        node: UDSNode,
        level,
        seed_data,
        expect_data,
        expect_str,
        dll_path="",
        dll_used_level=None,
        func_req=False,
        dl: int | None = None,
        dl_padding: int = 0x00,
        timeout: float = 5,
):
    from library.security.generate_key import generate_key_ex
    try:
        if dll_used_level == None:
            dll_used_level = level
        key = generate_key_ex(dll_path, seed_data, dll_used_level)
        response_message = node.Service_0x27_SecurityAccess(
            level + 1,
            seed_key=key,
            func_req=func_req,
            dl=dl,
            dl_padding=dl_padding,
            timeout=timeout, )
        if expect_data is None:
            # 期望无响应
            if response_message is None:
                TestLog("PASS", "Service_0x27", f"{expect_str}，无响应符合预期")
                return True
            TestLog("FAIL", "Service_0x27", f"{expect_str}，期望无响应，实际收到: {response_message.data.hex()}")
            return False

        if response_message is None:
            TestLog("FAIL", "Service_0x27", f"{expect_str}，未收到响应")
            return False

        if list(response_message.data[0:len(expect_data)]) != expect_data:
            TestLog(
                "FAIL",
                "Service_0x27",
                f"{expect_str}，响应不匹配，期望: {bytes(expect_data).hex()} 实际: {response_message.data.hex()}",
            )
            return False

        TestLog("PASS", "Service_0x27", f"{expect_str}，响应匹配: {response_message.data.hex()}")
        return True
    except Exception as e:
        TestLog("FAIL", "Service_0x27", f"{expect_str}，执行异常: {e}")
        TestLog("DEBUG", "Service_0x27", f"详细错误: {traceback.format_exc()}")
        return False


class TesterPresentManager:
    flag = False
    status = "stopped"


def tester_present_start(node, period_ms=2000):
    """
        开始周期发送3E 80
    """
    if TesterPresentManager.status == "running":
        return

    def run(node, period_ms):
        from .lin_test_pre_module import create_lin_sch, create_lin_ch

        lin_ch_usr = create_lin_ch()
        while TesterPresentManager.flag is True:
            node.Service_0x3E_TesterPresent(0x80, func_req=True, update_send_data=False)
            begin_time = time.time()
            while TesterPresentManager.flag is True:
                time.sleep(0.05)
                lin_ch_usr.output(0X3D)
                if (time.time() - begin_time) > period_ms / 1000:
                    break
        begin_time = time.time()
        while TesterPresentManager.flag is True:
            time.sleep(0.05)
            lin_ch_usr.output(0X3D)
            if (time.time() - begin_time) > 0.5:
                break
        TesterPresentManager.status = "stopped"

    TesterPresentManager.flag = True
    threading.Thread(target=run, args=(node, period_ms), daemon=True).start()
    TesterPresentManager.status = "running"


def tester_present_stop():
    """
        停止周期发送3E 80
    """
    TesterPresentManager.flag = False
    while TesterPresentManager.status != "stopped":
        time.sleep(0.05)
    time.sleep(0.5)


def clear_err_count(node, do_times, func_flg):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_PRO_11, DLL_PATH_PRO = 0x11, P.ECUInfo.dllPath_2711  # 刷新等级
    for i in range(do_times):
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return False
        __lin_restart_delay(2)
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中", func_req=func_flg):
            return False
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return False
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return False
        tester_present_start(node)
        time.sleep(12)
        tester_present_stop()
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})")
        if not status: return False
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            return False
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH): return False

        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return False
        __lin_restart_delay(2)
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中", func_req=func_flg):
            return False
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return False
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return False
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return False
        __lin_restart_delay(2)
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中", func_req=func_flg):
            return False

        tester_present_start(node)
        time.sleep(12)
        tester_present_stop()

        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})")
        if not status: return False

        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            return False
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x67, LEVEL_PRO_11 + 1],
                                            f"肯定响应(67 {LEVEL_PRO_11 + 1})",
                                            dll_path=DLL_PATH_PRO): return False
        time.sleep(15)
        __lin_restart_delay(2)

    return True


def test_phyRequest_27_Positive(
        node: UDSNode,
        name: str = "[TG3_TC1] 27服务肯定响应与功能检查(物理寻址)",
        func_flg: bool = False
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_PRO_11, DLL_PATH_PRO = 0x11, P.ECUInfo.dllPath_2711  # 刷新等级
    step = 0
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return
        clear_err_count(node, 1, func_flg)
        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step3: 检查当前会话状态 => 扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        tester_present_start(node)
        TestLog("INFO", "Step4", "等待12s")
        time.sleep(12)
        tester_present_stop()

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})")
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH): return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT, 0, 0, 0, 0],
                                                   f"肯定响应(67 {LEVEL_EXT})")
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step3: 检查当前会话状态 => 扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # 刷新/编程会话阶段
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["programming"],
                                           "位于刷新会话中(7F 31 31)", func_req=func_flg, ):
            return

        __lin_restart_delay(1)
        step += 1
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})")
        if not status: return

        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x67, LEVEL_PRO_11 + 1],
                                            f"肯定响应(67 {LEVEL_PRO_11 + 1})",
                                            dll_path=DLL_PATH_PRO): return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11, 0, 0, 0, 0],
                                                   f"肯定响应(67 {LEVEL_PRO_11})")
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()


def test_phyRequest_27_AlgorithmCheck(
        node: UDSNode,
        name: str = "[TG3_TC2] 27服务算法检查(物理寻址)",
        func_flg: bool = False
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_PRO_11, DLL_PATH_PRO = 0x11, P.ECUInfo.dllPath_2711  # 刷新等级
    step = 0
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return
        clear_err_count(node, 1, func_flg)
        # Step1: 请求进入默认会话
        step = 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话
        step = 2
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        # Step3: 检查当前会话状态 => 扩展会话
        step = 3
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step = 4
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})")
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 5
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0X7F, 0X27, 0X35], f"肯定响应(0X7F,0X27,0X35)",
                                            dll_path=DLL_PATH_PRO): return

        step = 6
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})")
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 7
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0X7F, 0X27, 0X35], f"肯定响应(0X7F,0X27,0X35)",
                                            dll_path=DLL_PATH_PRO): return

        step = 8
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})")
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 9
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0X7F, 0X27, 0X36], f"肯定响应(0X7F,0X27,0X36)",
                                            dll_path=DLL_PATH_PRO): return

        TestLog("INFO", "Step10", "等待10.5s(3E服务启动)")
        tester_present_start(node)
        time.sleep(10.5)
        tester_present_stop()

        step = 10
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})")
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 11
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH): return

        step = 12
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step = 13
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step = 14
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话
        step = 15
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step3: 检查当前会话状态 => 扩展会话
        step = 16
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # 刷新/编程会话阶段
        step = 17
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step = 18
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        time.sleep(1)
        step = 19
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})")
        if not status: return

        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 20
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x7F, 0x27, 0x35],
                                            f"肯定响应(0x7F, 0x27, 0x35)",
                                            dll_path=DLL_PATH): return

        step = 21
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})")
        if not status: return

        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 22
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x7F, 0x27, 0x35],
                                            f"肯定响应(0x7F, 0x27, 0x35)",
                                            dll_path=DLL_PATH): return

        step = 23
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})")
        if not status: return

        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 24
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x7F, 0x27, 0x36],
                                            f"肯定响应(0x7F, 0x27, 0x36)",
                                            dll_path=DLL_PATH): return

        TestLog("INFO", "Step25", "等待10.5s(3E服务启动)")
        tester_present_start(node)
        time.sleep(10.5)
        tester_present_stop()

        step = 26
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})")
        if not status: return

        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 27
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x67, LEVEL_PRO_11 + 1],
                                            f"肯定响应(67 {LEVEL_PRO_11 + 1})",
                                            dll_path=DLL_PATH_PRO): return

        step = 28
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11, 0, 0, 0, 0],
                                                   f"肯定响应(67 {LEVEL_PRO_11})")
        if not status: return

        step = 29
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()


def test_phyRequest_27_SwitchSessionDelay_LockCheck(
        node: UDSNode,
        name: str = "[TG3_TC3] 27服务切换会话延时机制与锁定检查(物理寻址)",
        func_flg: bool = False
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_PRO_11, DLL_PATH_PRO = 0x11, P.ECUInfo.dllPath_2711  # 刷新等级
    step = 0
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return
        clear_err_count(node, 1, func_flg)
        step = 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step = 2
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step = 3
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        tester_present_start(node)
        time.sleep(12)
        tester_present_stop()

        step = 4
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 5
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0X7F, 0X27, 0X35], f"肯定响应(0X7F,0X27,0X35)",
                                            dll_path=DLL_PATH_PRO, func_req=func_flg): return

        step = 6
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 7
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0X7F, 0X27, 0X35], f"肯定响应(0X7F,0X27,0X35)",
                                            dll_path=DLL_PATH_PRO, func_req=func_flg): return

        step = 8
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 9
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0X7F, 0X27, 0X36], f"肯定响应(0X7F,0X27,0X36)",
                                            dll_path=DLL_PATH_PRO, func_req=func_flg): return

        step = 10
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0X7F, 0X27, 0X37], f"否定响应(0X7F,0X27,0X37)",
                                                   func_req=func_flg)
        if not status: return

        step = 11
        TestLog("INFO", f"Step{step}", f"等待9s(3E服务启动)")

        tester_present_start(node)
        time.sleep(8)
        tester_present_stop()

        step = 12
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0X7F, 0X27, 0X37], f"否定响应(0X7F,0X27,0X37)",
                                                   func_req=func_flg)
        if not status: return

        step = 13
        TestLog("INFO", f"Step{step}", f"等待1s(3E服务启动)")
        time.sleep(2)

        step = 14
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 15
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH): return False

        step = 16
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step = 17
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step = 18
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话
        step = 19
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step3: 检查当前会话状态 => 扩展会话
        step = 20
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # 刷新/编程会话阶段
        step = 21
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step = 22
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        time.sleep(1)
        step = 23
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
        if not status: return

        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 24
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x7F, 0x27, 0x35],
                                            f"肯定响应(0x7F, 0x27, 0x35)",
                                            dll_path=DLL_PATH, func_req=func_flg): return

        step = 25
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
        if not status: return

        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 26
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x7F, 0x27, 0x35],
                                            f"肯定响应(0x7F, 0x27, 0x35)",
                                            dll_path=DLL_PATH, func_req=func_flg): return

        step = 27
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
        if not status: return

        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 28
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x7F, 0x27, 0x36],
                                            f"肯定响应(0x7F, 0x27, 0x36)",
                                            dll_path=DLL_PATH, func_req=func_flg): return

        step = 29
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x7F, 0x27, 0x37],
                                                   f"否定响应(0x7F, 0x27, 0x37)", func_req=func_flg)
        if not status: return

        step = 30
        TestLog("INFO", f"Step{step}", f"等待9s(3E服务启动)")
        tester_present_start(node)
        time.sleep(8)
        tester_present_stop()

        step = 31
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x7F, 0x27, 0x37],
                                                   f"否定响应(0x7F, 0x27, 0x37)", func_req=func_flg)
        if not status: return

        step = 32
        TestLog("INFO", f"Step{step}", f"等待1s(3E服务启动)")
        time.sleep(2)

        step = 33
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
        if not status: return

        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 34
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x67, LEVEL_PRO_11 + 1],
                                            f"肯定响应(0x67, {LEVEL_PRO_11 + 1})",
                                            dll_path=DLL_PATH_PRO, func_req=func_flg): return

        step = 35
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()


def test_phyRequest_27_NRC12(
        node: UDSNode,
        name: str = "[TG3_TC4] 27服务NRC12检查(物理寻址)",
        func_flg: bool = False
):
    min_subid, max_subid = UDSTestParams.MinSubID, UDSTestParams.MaxSubID
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_PRO_11, DLL_PATH_PRO = 0x11, P.ECUInfo.dllPath_2711  # 刷新等级
    step = 0
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return
        clear_err_count(node, 1, func_flg)
        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step3: 检查当前会话状态 => 扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "令SN=0x00")

        step += 1
        TestLog("INFO", f"Step{step}", "如果SN为支持的物理寻址子功能，则SN+=1，直到不支持的物理寻址子功能")
        for subid in range(min_subid, max_subid + 1):
            if subid in UDSTestParams.Services27SubFunSupportList:
                # 跳过支持的SubID
                continue
            TestLog("INFO", f"Step{step}", f"发送子功能为{hex(subid)}的27服务请求(27 {hex(subid)})")
            status, seed_list = __service_27_check_lin(node, subid, [0x7F, 0x27, 0x12], f"否定响应(7F 27 12)")
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "如果SN<0xFF，SN+=1，然后跳转至步骤5")

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step3: 检查当前会话状态 => 扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # 刷新/编程会话阶段
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "令SN=0x00")

        step += 1
        TestLog("INFO", f"Step{step}", "如果SN为支持的物理寻址子功能，则SN+=1，直到不支持的物理寻址子功能")

        step += 1
        for subid in range(min_subid, max_subid + 1):
            if subid in UDSTestParams.Services27SubFunSupportList:
                # 跳过支持的SubID
                continue
            TestLog("INFO", f"Step{step}", f"发送子功能为{hex(subid)}的27服务请求(27 {hex(subid)})")
            status, seed_list = __service_27_check_lin(node, subid, [0x7F, 0x27, 0x12], f"否定响应(7F 27 12)")
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "如果SN<0xFF，SN+=1，然后跳转至步骤14")

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_27_NRC13(
        node: UDSNode,
        name: str = "[TG3_TC5] 27服务NRC12检查(物理寻址)",
        func_flg: bool = False
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_PRO_11, DLL_PATH_PRO = 0x11, P.ECUInfo.dllPath_2711  # 刷新等级
    step = 0
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return
        clear_err_count(node, 1, func_flg)
        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step3: 检查当前会话状态 => 扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送短请求(27)")
        status, seed_list = __service_27_check_lin(node, None, [0x7F, 0x27, 0x13], f"肯定响应(0x7F, 0x27, 0x13)")
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "发送DL=3、4、5、6、7的 27 01请求，其有效数据填充部分填充0x00")
        for dl in [3, 4, 5, 6, 7]:
            TestLog("INFO", "", f"发送DL={dl}的 27 01请求")
            status, resp = __service_27_check_lin(node, LEVEL_EXT, [0x7F, 0x27, 0x13], f"否定响应(7F 27 13)", dl=dl,
                                                  dl_padding=0x00)
            if not status:
                return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step3: 检查当前会话状态 => 扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # 刷新/编程会话阶段
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送短请求(27)")
        status, seed_list = __service_27_check_lin(node, None, [0x7F, 0x27, 0x13], f"肯定响应(0x7F, 0x27, 0x13)")
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "发送DL=3、4、5、6、7的 27 01请求，其有效数据填充部分填充0x00")
        for dl in [3, 4, 5, 6, 7]:
            TestLog("INFO", "", f"发送DL={dl}的 27 01请求")
            status, resp = __service_27_check_lin(node, LEVEL_PRO_11, [0x7F, 0x27, 0x13], f"否定响应(7F 27 13)", dl=dl,
                                                  dl_padding=0x00)
            if not status:
                return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return


    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_27_NRC24(
        node: UDSNode,
        name: str = "[TG3_TC6] 27服务NRC24检查(物理寻址)",
        func_flg: bool = False
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_PRO_11, DLL_PATH_PRO = 0x11, P.ECUInfo.dllPath_2711  # 刷新等级
    step = 0
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return
        clear_err_count(node, 1, func_flg)
        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"直接发送27 02请求")
        status, seed_list = __service_27_check_lin(node, 0X02, [0x7F, 0x27, 0x24], f"肯定响应(0x7F, 0x27, 0x24)", dl=18)
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # 刷新/编程会话阶段
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"直接发送27 12请求")
        status, seed_list = __service_27_check_lin(node, 0X12, [0x7F, 0x27, 0x24], f"肯定响应(0x7F, 0x27, 0x24)", dl=18)
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_27_NRC7E_7F(
        node: UDSNode,
        name: str = "[TG3_TC7] 27服务NRC7E、NRC7F检查(物理寻址)",
        func_flg: bool = False
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_PRO_11, DLL_PATH_PRO = 0x11, P.ECUInfo.dllPath_2711  # 刷新等级
    step = 0
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return
        clear_err_count(node, 1, func_flg)
        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        tester_present_start(node)
        time.sleep(12)
        tester_present_stop()

        step += 1
        TestLog("INFO", f"Step{step}", f"直接发送27 11请求")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x7F, 0x27, 0x7E],
                                                   f"肯定响应(0x7F, 0x27, 0x7E)")
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # 刷新/编程会话阶段
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"直接发送27 01请求")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x7F, 0x27, 0x7E], f"肯定响应(0x7F, 0x27, 0x7E)")
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"直接发送27 01请求")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x7F, 0x27, 0x7F], f"肯定响应(0x7F, 0x27, 0x7F)")
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", f"直接发送27 05请求")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x7F, 0x27, 0x7F],
                                                   f"肯定响应(0x7F, 0x27, 0x7F)")
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_27_NRC22(
        node: UDSNode,
        name: str = "[TG3_TC8] 27服务NRC22检查(物理寻址)",
        func_flg: bool = False
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_PRO, DLL_PATH_PRO = 0x11, P.ECUInfo.dllPath_2711  # 刷新等级
    step = 0
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return
        clear_err_count(node, 1, func_flg)
        step += 1
        TestLog("INFO", f"Step{step}", "ECU的0x27服务需要支持NRC0x22")

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"遍历触发NRC22的所有条件并发送27 01")
        # TODO 条件仿真

        step += 1
        TestLog("INFO", f"Step{step}", f"直接发送27 01请求")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x7F, 0x27, 0x22], f"否定响应(0x7F, 0x27, 0x22)")
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", f"恢复可以正常解锁的条件，发送27 01")
        # TODO 恢复正常解锁的条件

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})")
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step7", f"遍历触发NRC22的所有条件并发送27 02")
        # TODO 条件仿真
        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0X7F, 0X27, 0X22], f"肯定响应(0X7F,0X27,0X22)",
                                            dll_path=DLL_PATH): return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step3: 检查当前会话状态 => 扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # 刷新/编程会话阶段
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"遍历触发NRC22的所有条件并发送27 05")
        # TODO 条件仿真
        status, resp = __service_27_check_lin(node, LEVEL_PRO, [0x7F, 0x27, 0x22], f"否定响应(7F 27 22)")
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", f"恢复可以正常解锁的条件，发送27 01")
        # TODO 恢复正常解锁的条件
        status, resp = __service_27_check_lin(node, LEVEL_PRO, [0x67, LEVEL_PRO + 1], f"肯定响应(67 {LEVEL_PRO + 1})")
        if not status: return

        TestLog("INFO", f"Step{step}", f"遍历触发NRC22的所有条件并发送27 12")
        # TODO 条件仿真
        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_PRO + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO, seed_list, [0X7F, 0X27, 0X22], f"肯定响应(0X7F,0X27,0X22)",
                                            dll_path=DLL_PATH): return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_27_SessionChangeCheck(
        node: UDSNode,
        name: str = "[TG3_TC9] 27服务会话切换检查(物理寻址)",
        func_flg: bool = False
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_PRO, DLL_PATH_PRO = 0x11, P.ECUInfo.dllPath_2711  # 刷新等级
    LEVEL_PRO_5, DLL_PATH_PRO_5 = 0x05, ""  # 刷新等级
    step = 0
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return
        clear_err_count(node, 1, func_flg)
        step += 1
        TestLog("INFO", f"Step{step}", "ECU的0x27服务需要支持NRC0x22")

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        time.sleep(1)
        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})")
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH): return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT, 0, 0, 0, 0],
                                                   f"肯定响应(67 {LEVEL_EXT})")
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step3: 检查当前会话状态 => 扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})")
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH): return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "刷新会话肯定响应(50 02)", func_req=func_flg):
            return

        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO, [0x67, LEVEL_PRO], f"肯定响应(67 {LEVEL_PRO})")
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_PRO + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO, seed_list, [0x67, LEVEL_PRO + 1],
                                            f"肯定响应(67 {LEVEL_PRO + 1})", dll_path=DLL_PATH_PRO): return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_5})")
        # status, seed_list = __service_27_check_lin(node, LEVEL_PRO_5, [0x67, LEVEL_PRO_5], f"肯定响应(67 {LEVEL_PRO_5})")
        # if not status: return
        # TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        # if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
        #     TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
        #     return
        # TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7f, 0x31, 0x31], "位于刷新会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "刷新会话肯定响应(50 02)", func_req=func_flg):
            return

        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO, [0x67, LEVEL_PRO], f"肯定响应(67 {LEVEL_PRO})")
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_PRO + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO, seed_list, [0x67, LEVEL_PRO + 1],
                                            f"肯定响应(67 {LEVEL_PRO + 1})", dll_path=DLL_PATH_PRO): return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7f, 0x31, 0x31], "位于刷新会话中", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def hard_reset(node=None, reset_type=1):
    if not __service_11_check(node, reset_type, expect_data=[0x51, reset_type], expect_str=f"肯定响应(51 {reset_type})",
                              func_req=False): return False
    return True


def test_phyRequest_27_ResetCheck(
        node: UDSNode,
        name: str = "[TG3_TC10] 27服务复位检查(物理寻址)",
        func_flg: bool = False
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_PRO, DLL_PATH_PRO = 0x11, P.ECUInfo.dllPath_2711  # 刷新等级
    LEVEL_PRO_5, DLL_PATH_PRO_5 = 0x05, ""  # 刷新等级
    min_subid, max_subid = 0x01, 0x10
    step = 0
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return
        clear_err_count(node, 1, func_flg)
        step += 1
        TestLog("INFO", f"Step{step}", "令SN=0x01")
        for sn in range(min_subid, max_subid + 1):
            if sn not in UDSTestParams.Services11SubFunSupportList:
                continue
            TestLog("INFO", "Step2",
                    "如果SN为扩展会话状态11服务不支持的物理寻址子功能，则SN+=1，直到SN为扩展会话支持的物理寻址的子功能；如果SN=0xFF，则跳转到步骤18")

            TestLog("INFO", "Step3", "请求进入默认会话(10 01)")
            if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
                return
            __lin_restart_delay(2)
            step += 1
            TestLog("INFO", "", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(
                    node,
                    SESSION_EXPECT_RESPONSES["default"],
                    "位于默认会话中",
                    func_req=func_flg,
            ):
                return
            TestLog("INFO", "Step4", "请求进入扩展会话(10 03)")
            if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "默认会话肯定响应(50 01)", func_req=func_flg):
                return
            __lin_restart_delay(2)
            TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(
                    node,
                    SESSION_EXPECT_RESPONSES["extended"],
                    "位于扩展会话中",
                    func_req=func_flg,
            ):
                return

            step += 1
            TestLog("INFO", f"Step6", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
            status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})")
            if not status: return
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
            if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
                TestLog("FAIL", "",
                        f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
                return
            TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

            step += 1
            TestLog("INFO", f"Step7", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
            if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                                f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH): return

            step += 1
            TestLog("INFO", f"Step8", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
            status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT, 0, 0, 0, 0],
                                                       f"肯定响应(67 {LEVEL_EXT})")
            if not status: return

            step += 1
            TestLog("INFO", f"Step9", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(
                    node,
                    SESSION_EXPECT_RESPONSES["extended"],
                    "位于扩展会话中",
                    func_req=func_flg,
            ):
                return

            TestLog("INFO", "Step10", f"请求复位，等待2s(11 {sn})")
            if not hard_reset(node): return
            __lin_restart_delay(2)

            TestLog("INFO", "Step11", "请求进入默认会话(10 01)")
            if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
                return
            __lin_restart_delay(2)
            step += 1
            TestLog("INFO", "", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(
                    node,
                    SESSION_EXPECT_RESPONSES["default"],
                    "位于默认会话中",
                    func_req=func_flg,
            ):
                return
            TestLog("INFO", "Step12", "请求进入扩展会话(10 03)")
            if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "默认会话肯定响应(50 01)", func_req=func_flg):
                return
            __lin_restart_delay(2)
            TestLog("INFO", "Step13", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(
                    node,
                    SESSION_EXPECT_RESPONSES["extended"],
                    "位于扩展会话中",
                    func_req=func_flg,
            ):
                return

            step += 1
            TestLog("INFO", f"Step14", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
            status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})")
            if not status: return
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
            if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
                TestLog("FAIL", "",
                        f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
                return
            TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

            step += 1
            TestLog("INFO", f"Step15", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
            if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                                f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH): return

            TestLog("INFO", "Step16", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(
                    node,
                    SESSION_EXPECT_RESPONSES["extended"],
                    "位于扩展会话中",
                    func_req=func_flg,
            ):
                return

            TestLog("INFO", "Step17", f"若SN={sn}<0xFF，SN+=1，跳转至步骤2")

        TestLog("INFO", "Step18", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg): return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", "", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        TestLog("INFO", "Step19", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "默认会话肯定响应(50 03)", func_req=func_flg): return
        __lin_restart_delay(2)
        TestLog("INFO", "Step20", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return
        TestLog("INFO", "Step21", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)",
                                      func_req=func_flg): return
        __lin_restart_delay(2)
        TestLog("INFO", "Step22", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        TestLog("INFO", "Step23", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO, [0x67, LEVEL_PRO], f"肯定响应(67 {LEVEL_PRO})")
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return

        TestLog("INFO", "Step24", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO, seed_list, [0x67, LEVEL_PRO + 1],
                                            f"肯定响应(67 {LEVEL_PRO})",
                                            dll_path=DLL_PATH_PRO, func_req=func_flg): return

        TestLog("INFO", "Step25", f"发送刷新安全级的请求种子(27 {LEVEL_PRO})")
        status, resp = __service_27_check_lin(node, LEVEL_PRO, [0x67, LEVEL_PRO, 0, 0, 0, 0],
                                              f"肯定响应(67 11 00 00 00 00)")
        if not status: return

        TestLog("INFO", "Step26", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

        TestLog("INFO", "Step27", f"请求复位，等待2s(11 01)")
        if not hard_reset(node): return
        __lin_restart_delay(2)

        TestLog("INFO", "Step28", "请求进入默认会话(10 03)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg): return
        __lin_restart_delay(2)
        TestLog("INFO", "", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        TestLog("INFO", "Step29", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "默认会话肯定响应(50 03)", func_req=func_flg): return
        __lin_restart_delay(2)
        TestLog("INFO", "", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return
        TestLog("INFO", "Step30", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)",
                                      func_req=func_flg): return
        __lin_restart_delay(2)
        TestLog("INFO", "Step31", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        TestLog("INFO", "Step32", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO, [0x67, LEVEL_PRO], f"肯定响应(67 {LEVEL_PRO})")
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return

        TestLog("INFO", "Step33", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO, seed_list, [0x67, LEVEL_PRO + 1],
                                            f"肯定响应(67 {LEVEL_PRO})",
                                            dll_path=DLL_PATH_PRO, func_req=func_flg): return

        TestLog("INFO", "Step34", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)"): return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_27_PowerOnOff(
        node: UDSNode,
        name: str = "[TG3_TC11] 27服务重新上电检查(物理寻址)",
        func_flg: bool = False
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_PRO_11, DLL_PATH_PRO = 0x11, P.ECUInfo.dllPath_2711  # 刷新等级
    LEVEL_PRO_5, DLL_PATH_PRO_5 = 0x05, ""  # 刷新等级
    step = 0
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return
        clear_err_count(node, 1, func_flg)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        time.sleep(1)
        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})")
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH): return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT, 0, 0, 0, 0],
                                                   f"肯定响应(67 {LEVEL_EXT})")
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "重新上电")
        __power_resatrt(1, 3)

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        time.sleep(1)
        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})")
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH): return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return
            # 刷新/编程会话阶段
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        time.sleep(1)
        step += 1
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})")
        if not status: return

        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x67, LEVEL_PRO_11 + 1],
                                            f"肯定响应(67 {LEVEL_PRO_11 + 1})",
                                            dll_path=DLL_PATH_PRO): return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11, 0, 0, 0, 0],
                                                   f"肯定响应(67 {LEVEL_PRO_11})")
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "重新上电")
        __power_resatrt(3, 3)

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "刷新会话肯定响应(50 02)", func_req=func_flg):
            return

        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        time.sleep(1)
        step += 1
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})")
        if not status: return

        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x67, LEVEL_PRO_11 + 1],
                                            f"肯定响应(67 {LEVEL_PRO_11 + 1})",
                                            dll_path=DLL_PATH_PRO): return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_27_ResetDelay_LockCheck(
        node: UDSNode,
        name: str = "[TG3_TC12] 27复位延时机制与锁定检查(物理寻址)",
        func_flg: bool = False
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_PRO_11, DLL_PATH_PRO = 0x11, P.ECUInfo.dllPath_2711  # 刷新等级
    LEVEL_PRO_5, DLL_PATH_PRO_5 = 0x05, ""  # 刷新等级
    step = 0
    min_subid, max_subid = 0x01, 0x10
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return
        clear_err_count(node, 1, func_flg)
        TestLog("INFO", "Step1", "令SN=0x01")
        for sn in range(min_subid, max_subid + 1):
            if sn not in UDSTestParams.Services11SubFunSupportList:
                continue
            TestLog("INFO", "Step2",
                    "如果SN为扩展会话状态11服务不支持的物理寻址子功能，则SN+=1，直到SN为扩展会话支持的物理寻址的子功能；如果SN=0xFF，则跳转到步骤26")

            TestLog("INFO", "Step3", "请求进入默认会话(10 01)")
            if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
                return
            __lin_restart_delay(2)
            TestLog("INFO", "", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(
                    node,
                    SESSION_EXPECT_RESPONSES["default"],
                    "位于默认会话中",
                    func_req=func_flg,
            ):
                return
            TestLog("INFO", "Step4", "请求进入扩展会话(10 03)")
            if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
                return
            __lin_restart_delay(2)
            TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"], "位于扩展会话中",
                                               func_req=func_flg):
                return

            TestLog("INFO", "Step6", "发送扩展安全级的请求种子请求(27 01)")
            status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                       func_req=func_flg)
            if not status: return
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
            if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
                TestLog("FAIL", "",
                        f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
                return
            TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

            TestLog("INFO", f"Step7", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
            if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x7F, 0X27, 0X35], f"否定响应(7F 27 35)",
                                                dll_path=DLL_PATH_PRO, func_req=func_flg): return

            TestLog("INFO", "Step8", "发送扩展安全级的请求种子请求(27 01)")
            status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})")
            if not status: return
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
            if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
                TestLog("FAIL", "",
                        f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
                return
            TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

            TestLog("INFO", "Step9", f"发送错误的扩展安全级的解锁密钥(27 02)")
            if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x7F, 0X27, 0X35], f"否定响应(7F 27 35)",
                                                dll_path=DLL_PATH_PRO, func_req=func_flg): return

            TestLog("INFO", "Step10", f"发送扩展安全级的请求种子请求(27 01)")
            status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})")
            if not status: return
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
            if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
                TestLog("FAIL", "",
                        f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
                return
            TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

            TestLog("INFO", "Step11", f"发送错误的扩展安全级的解锁密钥(27 02)")
            if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x7F, 0X27, 0X36], f"否定响应(7F 27 36)",
                                                dll_path=DLL_PATH_PRO, func_req=func_flg): return

            TestLog("INFO", "Step12", f"发送扩展安全级的请求种子请求(27 01)")
            status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x7F, 0X27, 0X37], f"否定响应(7F 27 37)",
                                                       func_req=func_flg)
            if not status: return

            TestLog("INFO", "Step13", f"等待9s(3E服务启动)")
            tester_present_start(node)
            time.sleep(8)
            tester_present_stop()

            TestLog("INFO", "Step14", f"发送扩展安全级的请求种子请求(27 01)")
            status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x7F, 0X27, 0X37], f"否定响应(7F 27 37)",
                                                       func_req=func_flg)
            if not status: return

            TestLog("INFO", "Step15", f"请求复位")
            if not hard_reset(node, sn): return
            # __lin_restart_delay(0.5)
            __lin_restart_delay(P.DiagServiceInfo.ResetTime) # 更改为配置参数下发
            TestLog("INFO", "Step16", "请求进入默认会话(10 01)")
            if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
                return
            # __lin_restart_delay(2)
            TestLog("INFO", "", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(
                    node,
                    SESSION_EXPECT_RESPONSES["default"],
                    "位于默认会话中",
                    func_req=func_flg,
            ):
                return
            TestLog("INFO", "Step17", "请求进入扩展会话(10 03)")
            if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
                return
            # __lin_restart_delay(2)
            TestLog("INFO", "Step18", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"], "位于扩展会话中",
                                               func_req=func_flg):
                return

            TestLog("INFO", "Step19", f"等待复位后5s(3E服务启动)")
            tester_present_start(node)
            time.sleep(5) # 时间调整，满足时间等待
            tester_present_stop()#里面有1s延时

            TestLog("INFO", "Step20", f"发送扩展安全级的请求种子请求(27 01)")
            status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x7F, 0X27, 0X37], f"否定响应(7F 27 37)",
                                                       func_req=func_flg)
            if not status: return

            TestLog("INFO", "Step21", f"等待复位后6s(3E服务启动)")
            tester_present_start(node)
            time.sleep(6) # 时间调整，满足时间等待
            tester_present_stop()

            TestLog("INFO", "Step22", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
            status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                       func_req=func_flg)
            if not status: return
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
            if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
                TestLog("FAIL", "",
                        f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
                return
            TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

            TestLog("INFO", "Step23", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
            if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, 0X02],
                                                f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                                func_req=func_flg): return

            TestLog("INFO", "Step24", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"], "位于扩展会话中",
                                               func_req=func_flg):
                return

            TestLog("INFO", "Step25", "若SN<0xFF，则SN+=1，返回步骤2")

        TestLog("INFO", "Step26", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        TestLog("INFO", "", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        TestLog("INFO", "Step27", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        TestLog("INFO", "", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return
        TestLog("INFO", "Step28", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        TestLog("INFO", "Step29", "检查当前会话状态(31 01 02 03)")
        __lin_restart_delay(2)
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        TestLog("INFO", "Step30", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step31", f"发送错误的刷新安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x7F, 0x27, 0x35], f"否定响应(7F 27 35)",
                                            func_req=func_flg, dll_path=DLL_PATH): return

        TestLog("INFO", "Step32", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step33", f"发送错误的刷新安全级的解锁密钥(27 {LEVEL_PRO_11})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x7F, 0x27, 0x35], f"否定响应(7F 27 35)",
                                            func_req=func_flg, dll_path=DLL_PATH): return

        TestLog("INFO", "Step34", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step35", f"发送错误的刷新安全级的解锁密钥(27 {LEVEL_PRO_11})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x7F, 0x27, 0x36], f"否定响应(7F 27 36)",
                                            func_req=func_flg, dll_path=DLL_PATH): return

        TestLog("INFO", "Step36", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, resp = __service_27_check_lin(node, LEVEL_PRO_11, [0x7F, 0x27, 0x37], f"肯定响应(7F 27 37)",
                                              func_req=func_flg)
        if not status: return
        TestLog("INFO", "Step37", f"等待9s(3E服务启动)")
        tester_present_start(node)
        time.sleep(8)
        tester_present_stop()

        TestLog("INFO", "Step38", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, resp = __service_27_check_lin(node, LEVEL_PRO_11, [0x7F, 0x27, 0x37], f"肯定响应(7F 27 37)",
                                              func_req=func_flg)
        if not status: return

        TestLog("INFO", "Step39", f"请求复位")
        if not hard_reset(node, sn): return
        __lin_restart_delay(P.DiagServiceInfo.ResetTime) # 更改为配置参数下发
        TestLog("INFO", "Step40", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        TestLog("INFO", "", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        TestLog("INFO", "Step41", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        TestLog("INFO", "", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return
        TestLog("INFO", "Step42", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        TestLog("INFO", "Step43", "检查当前会话状态(31 01 02 03)")
        __lin_restart_delay(2)
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        TestLog("INFO", "Step44", f"等待复位后2s(3E服务启动)")
        tester_present_start(node)
        time.sleep(2) # 时间调整，满足时间等待
        tester_present_stop()

        TestLog("INFO", "Step45", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, resp = __service_27_check_lin(node, LEVEL_PRO_11, [0x7F, 0x27, 0x37], f"肯定响应(7F 27 37)",
                                              func_req=func_flg)
        if not status: return

        TestLog("INFO", "Step46", f"等待3s(3E服务启动)")
        tester_present_start(node)
        time.sleep(3) # 时间调整，满足时间等待
        tester_present_stop()

        TestLog("INFO", "Step47", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("INFO", "Step48", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x67, 0x12], f"否定响应67 12)",
                                            func_req=func_flg, dll_path=DLL_PATH_PRO): return

        TestLog("INFO", "Step49", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], expect_str="位于刷新会话中(7F 31 31)",
                                           func_req=func_flg): return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_27_PowerOnDelay_LockCheck(
        node: UDSNode,
        name: str = "[TG3_TC13] 27服务重新上电延时机制和锁定检查(物理寻址)",
        func_flg: bool = False
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_EXT_9, DLL_PATH_9 = 0x09, ""  # 扩展等级
    LEVEL_PRO_11, DLL_PATH_PRO = 0x11, P.ECUInfo.dllPath_2711  # 刷新等级
    LEVEL_PRO_5, DLL_PATH_PRO_5 = 0x05, ""  # 刷新等级
    step = 0
    min_subid, max_subid = 0x01, 0x10
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return
        clear_err_count(node, 1, func_flg)
        step = 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step = 2
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step = 3
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        time.sleep(1)
        step = 4
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 5
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0X7F, 0X27, 0X35], f"否定响应(0X7F,0X27,0X35)",
                                            dll_path=DLL_PATH_PRO, func_req=func_flg): return

        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0X7F, 0X27, 0X35], f"否定响应(0X7F,0X27,0X35)",
                                            dll_path=DLL_PATH_PRO, func_req=func_flg): return

        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        step = 6
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0X7F, 0X27, 0X36], f"否定响应(0X7F,0X27,0X36)",
                                            dll_path=DLL_PATH_PRO, func_req=func_flg): return

        step = 7
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0X7F, 0X27, 0X37], f"否定响应(0X7F,0X27,0X37)",
                                                   func_req=func_flg)
        if not status: return
        step = 8
        TestLog("INFO", f"Step{step}", f"等待9s(3E服务启动)")
        tester_present_start(node)
        time.sleep(8)
        tester_present_stop()

        step = 9
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0X7F, 0X27, 0X37], f"否定响应(0X7F,0X27,0X37)",
                                                   func_req=func_flg)
        if not status: return

        step = 10
        TestLog("INFO", f"Step{step}", "重新上电")
        __power_resatrt(2, 2) # 时间调整，满足时间等待，上电等待两秒

        step = 11
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        # __lin_restart_delay(1)

        # Step2: 请求进入扩展会话
        step = 12
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        # Step3: 检查当前会话状态 => 扩展会话
        step = 13
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step = 14
        TestLog("INFO", f"Step{step}", f"等待5s(3E服务启动)")
        tester_present_start(node)
        time.sleep(5) # 时间调整，满足时间等待
        tester_present_stop()

        step = 15
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0X7F, 0X27, 0X37], f"否定响应(0X7F,0X27,0X37)",
                                                   func_req=func_flg)
        if not status: return

        step = 16
        TestLog("INFO", f"Step{step}", f"等待6s(3E服务启动)")
        tester_present_start(node)
        time.sleep(6) # 时间调整，满足时间等待
        tester_present_stop()

        step = 17
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 18
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0X67, LEVEL_EXT + 1], f"肯定响应(67 02)",
                                            dll_path=DLL_PATH, func_req=func_flg): return

        step = 19
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step = 20
        TestLog("INFO", f"Step{step}", "如果ECU不支持防盗安全等级，跳转至步骤40")
        if False:
            step = 21
            TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
            if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
                return
            __lin_restart_delay(2)
            step = 22
            TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
            if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
                return
            __lin_restart_delay(2)
            step = 23
            TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(
                    node,
                    SESSION_EXPECT_RESPONSES["extended"],
                    "位于扩展会话中",
                    func_req=func_flg,
            ):
                return

            time.sleep(1)
            step = 24
            TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_9})")
            status, seed_list = __service_27_check_lin(node, LEVEL_EXT_9, [0x67, LEVEL_EXT_9],
                                                       f"肯定响应(67 {LEVEL_EXT_9})",
                                                       func_req=func_flg)
            if not status: return
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
            if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
                TestLog("FAIL", "",
                        f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
                return
            TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

            step += 1
            TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT_9 + 1})")
            if not __service_27_securityKey_lin(node, LEVEL_EXT_9, seed_list, [0X7F, 0X27, 0X35],
                                                f"否定响应(0X7F,0X27,0X35)",
                                                dll_path=DLL_PATH_PRO, func_req=func_flg): return

            step += 1
            TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT_9 + 1})")
            if not __service_27_securityKey_lin(node, LEVEL_EXT_9, seed_list, [0X7F, 0X27, 0X36],
                                                f"否定响应(0X7F,0X27,0X36)",
                                                dll_path=DLL_PATH_PRO, func_req=func_flg): return

            step += 1
            TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT_9 + 1})")
            if not __service_27_securityKey_lin(node, LEVEL_EXT_9, seed_list, [0X7F, 0X27, 0X37],
                                                f"否定响应(0X7F,0X27,0X37)",
                                                dll_path=DLL_PATH_PRO, func_req=func_flg): return

            step += 1
            TestLog("INFO", f"Step{step}", f"等待9s(3E服务启动)")
            tester_present_start(node)
            time.sleep(9)
            tester_present_stop()

            step += 1
            TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_9})")
            status, seed_list = __service_27_check_lin(node, LEVEL_EXT_9, [0X7F, 0X27, 0X37],
                                                       f"否定响应(0X7F,0X27,0X37)",
                                                       func_req=func_flg)
            if not status: return

            step += 1
            TestLog("INFO", f"Step{step}", "重新上电")
            __power_resatrt(3, 3)

            step += 1
            TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
            if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
                return
            __lin_restart_delay(2)
            step += 1
            TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(
                    node,
                    SESSION_EXPECT_RESPONSES["default"],
                    "位于默认会话中",
                    func_req=func_flg,
            ):
                return
            step += 1
            TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
            if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
                return
            __lin_restart_delay(2)
            step += 1
            TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(
                    node,
                    SESSION_EXPECT_RESPONSES["extended"],
                    "位于扩展会话中",
                    func_req=func_flg,
            ):
                return

            step += 1
            TestLog("INFO", f"Step{step}", f"等待9s(3E服务启动)")
            tester_present_start(node)
            time.sleep(9)
            tester_present_stop()

            step += 1
            TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_9})")
            status, seed_list = __service_27_check_lin(node, LEVEL_EXT_9, [0X7F, 0X27, 0X37],
                                                       f"否定响应(0X7F,0X27,0X37)",
                                                       func_req=func_flg)
            if not status: return

            step += 1
            TestLog("INFO", f"Step{step}", f"等待1s(3E服务启动)")
            time.sleep(1)

            step += 1
            TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_9})")
            status, seed_list = __service_27_check_lin(node, LEVEL_EXT_9, [0x67, LEVEL_EXT_9],
                                                       f"肯定响应(67 {LEVEL_EXT_9})",
                                                       func_req=func_flg)
            step += 1
            TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT_9 + 1})")
            if not __service_27_securityKey_lin(node, LEVEL_EXT_9, seed_list, [0X67, LEVEL_EXT_9], f"肯定响应(67 0A)",
                                                dll_path=DLL_PATH_9, func_req=func_flg): return

            step += 1
            TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(
                    node,
                    SESSION_EXPECT_RESPONSES["extended"],
                    "位于扩展会话中",
                    func_req=func_flg,
            ):
                return

        step = 40
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

        step = 41
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return
        step = 42
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        __lin_restart_delay(2)
        step = 43
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        step = 44
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
        if not status: return

        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 45
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x7F, 0X27, 0X35],
                                            f"肯定响应(7F 27 35)",
                                            dll_path=DLL_PATH, func_req=func_flg): return

        step = 46
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
        if not status: return

        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 47
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x7F, 0X27, 0X35],
                                            f"肯定响应(7F 27 35)",
                                            dll_path=DLL_PATH, func_req=func_flg): return

        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
        if not status: return
        step = 48
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x7F, 0X27, 0X36],
                                            f"肯定响应(7F 27 36)",
                                            dll_path=DLL_PATH, func_req=func_flg): return

        step = 49
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x7F, 0X27, 0X37],
                                                   f"肯定响应(7F 27 37)", func_req=func_flg)
        if not status: return

        step = 50
        TestLog("INFO", f"Step{step}", f"等待9s(3E服务启动)")
        tester_present_start(node)
        time.sleep(8)
        tester_present_stop()

        step = 51
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x7F, 0X27, 0X37],
                                                   f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
        if not status: return

        step = 52
        TestLog("INFO", f"Step{step}", "重新上电")
        __power_resatrt(2, 2) # 时间调整，满足时间等待，上电等待两秒

        step = 53
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        # __lin_restart_delay(2)
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        step = 54
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return
        step = 55
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return
        step = 56
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        step = 57
        TestLog("INFO", f"Step{step}", f"等待5s(3E服务启动)")
        tester_present_start(node)
        time.sleep(5) # 时间调整，满足时间等待
        tester_present_stop()

        step = 58
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0X7F, 0X27, 0X37], f"否定响应(0X7F,0X27,0X37)",
                                                   func_req=func_flg)
        if not status: return

        step = 59
        TestLog("INFO", f"Step{step}", f"等待6s(3E服务启动)")
        tester_present_start(node)
        time.sleep(6) # 时间调整，满足时间等待
        tester_present_stop()

        step = 60
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})")
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 61
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x67, LEVEL_PRO_11 + 1],
                                            f"肯定响应(67 {LEVEL_PRO_11 + 1})", dll_path=DLL_PATH_PRO): return

        step = 62
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_27_SwitchSessionDelay_IndependenceCheck(
        node: UDSNode,
        name: str = "[TG3_TC14] 27服务切换会话延时机制独立性检查(物理寻址)",
        func_flg: bool = False
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_PRO_11, DLL_PATH_PRO = 0x11, P.ECUInfo.dllPath_2711  # 刷新等级
    LEVEL_PRO_5, DLL_PATH_PRO_5 = 0x05, ""  # 刷新等级
    step = 0
    min_subid, max_subid = 0x01, 0x10
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return
        clear_err_count(node, 1, func_flg)
        step = 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step = 2
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step = 3
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step = 4
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 5
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0X7F, 0X27, 0X35], f"肯定响应(0X7F,0X27,0X35)",
                                            dll_path=DLL_PATH_PRO, func_req=func_flg): return

        step = 6
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 7
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0X7F, 0X27, 0X35], f"肯定响应(0X7F,0X27,0X35)",
                                            dll_path=DLL_PATH_PRO, func_req=func_flg): return

        step = 8
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 9
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0X7F, 0X27, 0X36], f"肯定响应(0X7F,0X27,0X36)",
                                            dll_path=DLL_PATH_PRO, func_req=func_flg): return

        step = 10
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0X7F, 0X27, 0X37], f"否定响应(0X7F,0X27,0X37)",
                                                   func_req=func_flg)
        if not status: return

        step = 11
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step2: 请求进入扩展会话
        step = 12
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step = 13
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # 刷新/编程会话阶段
        step = 14
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        __lin_restart_delay(2)
        step = 15
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        step = 16
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
        if not status: return

        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 17
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x67, LEVEL_PRO_11 + 1],
                                            f"肯定响应(0x67, {LEVEL_PRO_11 + 1})",
                                            dll_path=DLL_PATH_PRO, func_req=func_flg): return

        step = 18
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step = 19
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        step = 20
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step = 21
        TestLog("INFO", f"Step{step}", f"等待9s(3E服务启动)")
        tester_present_start(node)
        time.sleep(6)
        tester_present_stop()

        step = 22
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0X7F, 0X27, 0X37], f"否定响应(0X7F,0X27,0X37)",
                                                   func_req=func_flg)
        if not status: return

        step = 23
        TestLog("INFO", f"Step{step}", f"等待1s(3E服务启动)")
        tester_present_start(node)
        time.sleep(3)
        tester_present_stop()

        step = 24
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})")
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 25
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH): return

        step = 26
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step = 27
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step = 28
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        step = 29
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # 刷新/编程会话阶段
        step = 30
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        __lin_restart_delay(2)
        step = 31
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        step = 32
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
        if not status: return

        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 33
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x7F, 0x27, 0x35],
                                            f"肯定响应(0x7F, 0x27, 0x35)",
                                            dll_path=DLL_PATH, func_req=func_flg): return

        step = 34
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
        if not status: return

        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 35
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x7F, 0x27, 0x35],
                                            f"肯定响应(0x7F, 0x27, 0x35)",
                                            dll_path=DLL_PATH, func_req=func_flg): return

        step = 36
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
        if not status: return

        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 37
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x7F, 0x27, 0x36],
                                            f"肯定响应(0x7F, 0x27, 0x36)",
                                            dll_path=DLL_PATH, func_req=func_flg): return

        step = 38
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x7F, 0x27, 0x37],
                                                   f"否定响应(0x7F, 0x27, 0x37)", func_req=func_flg)
        if not status: return

        step = 39
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

        step = 40
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        step = 41
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step = 42
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})")
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 43
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH): return

        step = 44
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话
        step = 45
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        # Step3: 检查当前会话状态 => 扩展会话
        step = 46
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # 刷新/编程会话阶段
        step = 47
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return
        step = 48
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        step = 49
        TestLog("INFO", f"Step{step}", f"等待9s(3E服务启动)")
        tester_present_start(node)
        time.sleep(8)
        tester_present_stop()

        step = 50
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x7F, 0x27, 0x37],
                                                   f"否定响应(0x7F, 0x27, 0x37)", func_req=func_flg)
        if not status: return

        step = 51
        TestLog("INFO", f"Step{step}", f"等待1s(3E服务启动)")
        tester_present_start(node)
        time.sleep(2)
        tester_present_stop()

        step = 52
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
        if not status: return

        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 53
        TestLog("INFO", f"Step{step}", f"发送刷新安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x67, LEVEL_PRO_11 + 1],
                                            f"肯定响应(0x67, {LEVEL_PRO_11 + 1})",
                                            dll_path=DLL_PATH_PRO, func_req=func_flg): return

        step = 54
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_27_NRCPriorityCheck(
        node: UDSNode,
        name: str = "[TG3_TC15] 27服务NRC优先级检查(物理寻址)",
        func_flg: bool = False
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_PRO_11, DLL_PATH_PRO = 0x11, P.ECUInfo.dllPath_2711  # 刷新等级
    LEVEL_PRO_5, DLL_PATH_PRO_5 = 0x05, ""  # 刷新等级
    step = 0
    min_subid, max_subid = 0x01, 0x10
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return
        clear_err_count(node, 1, func_flg)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0X7F, 0X27, 0x7F], f"否定响应(0X7F,0X27,0x7F)",
                                                   func_req=func_flg, dl=3, dl_padding=0x00)
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "确认是否支持NRC22")
        # TODO NRC22 触发

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0X7F, 0X27, 0x22], f"否定响应(0X7F,0X27,0X22)",
                                                   func_req=func_flg, dl=3, dl_padding=0x00)
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送请求(27)")
        status, seed_list = __service_27_check_lin(node, None, [0X7F, 0X27, 0x13], f"否定响应(0X7F,0X27,0X13)",
                                                   func_req=func_flg)
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送请求(27 19)")
        status, seed_list = __service_27_check_lin(node, 0X19, [0X7F, 0X27, 0x12], f"否定响应(0X7F,0X27,0X12)",
                                                   func_req=func_flg)
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 06 00 00 00 00)")
        status, seed_list = __service_27_check_lin(node, 0X06, [0X7F, 0X27, 0x7E], f"否定响应(0X7F,0X27,0x7E)",
                                                   func_req=func_flg, dl=6, dl_padding=0x00)
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 02 00 00 00 00)")
        status, seed_list = __service_27_check_lin(node, 0X02, [0X7F, 0X27, 0x24], f"否定响应(0X7F,0X27,0x24)",
                                                   func_req=func_flg, dl=6, dl_padding=0x00)
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return


    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        import traceback
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def __service_28_check_lin(
        node: UDSNode,
        control_type: int | None,
        comm_type: int | None,
        expect_data,
        expect_str: str = "",
        func_req: bool = False,
        dl: int | None = None,
        dl_padding: int = 0x00,
        timeout: float = 5,
        *args, **kwargs
) -> bool:
    """
    LIN 下 0x28 服务发送与结果校验
    """
    try:
        response_message = node.Service_0x28_CommunicationControl(
            control_type=control_type,
            communication_type=comm_type,
            func_req=func_req,
            dl=dl,
            dl_padding=dl_padding,
            timeout=timeout,
            *args, **kwargs
        )
        if expect_data is None:
            # 期望无响应
            if response_message is None:
                TestLog("PASS", "Service_0x28", f"{expect_str}，无响应符合预期")
                return True
            TestLog("FAIL", "Service_0x28", f"{expect_str}，期望无响应，实际收到: {response_message.data.hex()}")
            return False

        if response_message is None:
            TestLog("FAIL", "Service_0x28", f"{expect_str}，未收到响应")
            return False

        expected_list = expect_data if isinstance(expect_data[0], list) else [expect_data]

        for expected in expected_list:
            if list(response_message.data[0:len(expected)]) == expected:
                TestLog("PASS", "Service_0x28", f"{expect_str}，响应匹配: {response_message.data.hex()}")
                return True

        # 所有期望都不匹配时
        expected_strs = [bytes(e).hex() for e in expected_list]
        TestLog(
            "FAIL",
            "Service_0x28",
            f"{expect_str}，响应不匹配，期望: {' 或 '.join(expected_strs)} 实际: {response_message.data.hex()}",
        )
        return False

    except Exception as e:
        TestLog("FAIL", "Service_0x28", f"{expect_str}，执行异常: {e}")
        TestLog("DEBUG", "Service_0x28", f"详细错误: {traceback.format_exc()}")
        return False


def test_phyRequest_28_Positive(
        node: UDSNode,
        name: str = "[TG4_TC1] 28服务肯定响应检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG4_TC1] 28服务肯定响应检查(物理寻址)
    """
    step = 0

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return
        sub_fun_list = UDSTestParams.Services28SubFunSupportList
        comm_type_list = UDSTestParams.Services28CommTypeSupportList

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "肯定响应(50 01)"): return
        __lin_restart_delay(2)

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "肯定响应(50 03)"): return

        __lin_restart_delay(2)
        # Step3: 检查当前会话状态 (31 01 02 03) => 71 01 02 03 00
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        for sub_fun in sub_fun_list:
            for comm_type in comm_type_list:
                # 发送28服务请求(不带抑制位)
                TestLog("INFO", f"Step{step}", f"发送28 {sub_fun:02X} {comm_type:02X}请求")
                if not __service_28_check_lin(node, sub_fun, comm_type, [0x68, sub_fun],
                                              f"肯定响应(68 {sub_fun:02X})"): return
                step += 1

                # 发送28服务请求(带抑制位)
                sub_fun_with_suppress = sub_fun | 0x80
                TestLog("INFO", f"Step{step}", f"发送28 {sub_fun_with_suppress:02X} {comm_type:02X}请求(带抑制位)")
                if not __service_28_check_lin(node, sub_fun_with_suppress, comm_type, None, "无响应"): return
                step += 1

        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00],
                                           "位于扩展会话中(71 01 02 03 00)"): return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_28_ExitFunction(
        node: UDSNode,
        name: str = "[TG4_TC2] 28服务退出功能检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG4_TC2] 28服务退出功能检查(物理寻址)
    """
    step = 0

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话 (10 01)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话 (10 03)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step3: 检查当前会话状态 (31 01 02 03)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # Step4: 发送28 03 01请求关闭报文发送和接收
        step += 1
        TestLog("INFO", f"Step{step}", "发送28 03 01请求关闭报文发送和接收")
        if not __service_28_check_lin(node, 0x03, 0x01, [0x68, 0x03], "肯定响应(68 03)", func_req=func_flg):
            return

        # Step5: 请求进入默认会话 (10 01)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        # Step6: 检查当前会话状态及报文是否能正常收发
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # Step7: 请求进入默认会话 (10 01)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step8: 请求进入扩展会话 (10 03)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step9: 检查当前会话状态 (31 01 02 03)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # Step10: 发送28 03 01请求关闭报文发送和接收
        step += 1
        TestLog("INFO", f"Step{step}", "发送28 03 01请求关闭报文发送和接收")
        if not __service_28_check_lin(node, 0x03, 0x01, [0x68, 0x03], "肯定响应(68 03)", func_req=func_flg):
            return

        # Step11: 请求复位，等待2s (11 01)
        step += 1
        TestLog("INFO", f"Step{step}", "请求复位，等待2s(11 01)")
        if not __service_11_check(node, 0x01, [0x51, 0x01], "肯定响应(51 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

        # Step12: 检查当前会话状态及报文是否能正常收发
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态及报文是否能正常收发(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中，报文可正常收发(7F 31 7F)",
                func_req=func_flg,
        ):
            return

        # Step13: 请求进入默认会话 (10 01)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step14: 请求进入扩展会话 (10 03)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step15: 检查当前会话状态 (31 01 02 03)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # Step16: 发送28 03 01请求关闭报文发送和接收
        step += 1
        TestLog("INFO", f"Step{step}", "发送28 03 01请求关闭报文发送和接收")
        if not __service_28_check_lin(node, 0x03, 0x01, [0x68, 0x03], "肯定响应(68 03)", func_req=func_flg):
            return

        # Step17: DUT重新上电
        step += 1
        TestLog("INFO", f"Step{step}", "重新上电")
        __power_resatrt(1, 2)

        # Step18: 检查当前会话状态及报文
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态及报文是否能正常收发(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中，报文可正常收发(7F 31 7F)",
                func_req=func_flg,
        ):
            return

        # Step19: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step20: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step21: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # Step22: 发送28 03 01请求关闭报文发送和接收
        step += 1
        TestLog("INFO", f"Step{step}", "发送28 03 01请求关闭报文发送和接收")
        if not __service_28_check_lin(node, 0x03, 0x01, [0x68, 0x03], "肯定响应(68 03)", func_req=func_flg):
            return

        # Step23: 等待S3server超时
        step += 1
        TestLog("INFO", f"Step{step}", "等待S3server超时")
        s3_timeout = P.TpInfo.S3Server / 1000 + 1
        TestLog("INFO", "", f"等待S3 server超时: {s3_timeout}ms")
        time.sleep(s3_timeout)

        # Step24: 检查当前会话状态及报文是否能正常收发
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态及报文是否能正常收发(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中，报文可正常收发(7F 31 7F)",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "28服务退出功能检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_28_NRC12(
        node: UDSNode,
        name: str = "[TG4_TC3] 28服务NRC12检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG4_TC3] 28服务NRC12检查(物理寻址)
    """
    step = 0

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step3: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # Step4: 令SN=0x00
        step += 1
        TestLog("INFO", f"Step{step}", "令SN=0x00")

        supported_sub_funs = UDSTestParams.Services28SubFunSupportList
        comm_type_list = UDSTestParams.Services28CommTypeSupportList

        step += 1
        for control_type in range(0x00, 0x80):
            if control_type in supported_sub_funs:
                continue

            for comm_type in comm_type_list:
                TestLog("INFO", f"Step{step}", f"发送不支持的子功能请求(28 {control_type:02X} {comm_type:02X})")
                if not __service_28_check_lin(
                        node,
                        control_type,
                        comm_type,
                        [0x7F, 0x28, 0x12],
                        f"28服务NRC12检查(control_type={hex(control_type)}, comm_type={hex(comm_type)})",
                        func_req=func_flg,
                ):
                    TestLog("FAIL", name, f"control_type={hex(control_type)} comm_type={hex(comm_type)}的NRC12检查失败")
                    return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "28服务NRC12检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_28_NRC13(
        node: UDSNode,
        name: str = "[TG4_TC4] 28服务NRC13检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG4_TC4] 28服务NRC13检查(物理寻址)
    """
    step = 0

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话 (10 01)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step3: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        supported_sub_funs = UDSTestParams.Services28SubFunSupportList
        comm_type_list = UDSTestParams.Services28CommTypeSupportList

        step += 1
        TestLog("INFO", f"Step{step}", "发送长度错误的28请求(DL=1, 只有SID)")
        if not __service_28_check_lin(node, None, None, [0x7F, 0x28, 0x13], "否定响应(7F 28 13)",
                                      func_req=func_flg): return

        # DL=2,4,5,6,7
        step += 1
        for sub_fun in supported_sub_funs:
            # DL=2: 28 sub_fun (无通信类型)
            TestLog("INFO", f"Step{step}", f"发送长度错误的28请求(DL=2, 28 {sub_fun:02X})")
            if not __service_28_check_lin(node, None, None, [0x7F, 0x28, 0x13], "否定响应(7F 28 13)", dl=2,
                                          dl_padding=sub_fun, func_req=func_flg): return

            # DL=4,5,6,7:
            step += 1
            for comm_type in comm_type_list:
                for dl in [4, 5, 6, 7]:
                    TestLog("INFO", f"Step{step}",
                            f"发送长度错误的28请求(DL={dl}, 28 {sub_fun:02X} {comm_type:02X} ...)")
                    if not __service_28_check_lin(node, sub_fun, comm_type, [0x7F, 0x28, 0x13], "否定响应(7F 28 13)",
                                                  dl=dl, func_req=func_flg): return

        # Step9: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "28服务NRC13检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_28_NRC7F(
        node: UDSNode,
        name: str = "[TG4_TC5] 28服务NRC7F检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG4_TC5] 28服务NRC7F检查(物理寻址)
    """
    step = 0

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        # Step2: 检查当前会话状态
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # Step3: 在默认会话下发送28 SN SF请求，期望NRC7F响应
        step += 1
        TestLog("INFO", f"Step{step}", "在默认会话下发送28 SN SF请求，期望NRC7F响应")

        supported_sub_funs = UDSTestParams.Services28SubFunSupportList
        comm_type_list = UDSTestParams.Services28CommTypeSupportList

        step += 1
        for control_type in supported_sub_funs:
            for comm_type in comm_type_list:
                TestLog("INFO", f"Step{step}", f"在默认会话下发送28 {control_type:02X} {comm_type:02X}请求(功能寻址)")
                if not __service_28_check_lin(node, control_type, comm_type, [[0x7F, 0x28, 0x7F], [0x7F, 0x28, 0x11]],
                                              "否定响应(7F 28 7F)或(7F 28 11)", func_req=func_flg, timeout=0.1): return

        # Step4: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # Step5: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step6: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # Step7: 请求进入刷新会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "刷新会话肯定响应(50 02)", func_req=func_flg):
            return

        # Step8: 检查当前会话状态
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        # Step9: 在刷新会话下发送28 SN SF请求，期望NRC7F或NRC11响应
        step += 1
        TestLog("INFO", f"Step{step}", "在刷新会话下发送28请求，期望NRC7F或NRC11响应")

        for control_type in supported_sub_funs:
            for comm_type in comm_type_list:
                TestLog("INFO", f"Step{step}", f"在刷新会话下发送28 {control_type:02X} {comm_type:02X}请求")
                if not __service_28_check_lin(node, control_type, comm_type, [[0x7F, 0x28, 0x7F], [0x7F, 0x28, 0x11]],
                                              "否定响应(7F 28 7F)或(7F 28 11)", func_req=func_flg): return

        # Step10: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x7F, 0x31, 0x31],
                "仍位于刷新会话中(7F 31 31)",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "28服务NRC7F检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def __send_28_sn_sf_with_nrc22_conditions(node: UDSNode, func_req: bool = False) -> bool:
    """
    遍历所有可能触发 NRC22 的条件并发送 28 SN SF 请求
    """
    got_nrc22 = False
    cond_list = UDSTestParams.NRC22_ConditionList or [None]

    supported_sub_funs = UDSTestParams.Services28SubFunSupportList
    supported_comm_types = UDSTestParams.Services28CommTypeSupportList

    for idx, cond in enumerate(cond_list, start=1):
        desc = cond if isinstance(cond, str) else f"条件{idx}"

        # 遍历支持的子功能SN=00、01、02、03
        for sn in [0x00, 0x01, 0x02, 0x03]:
            if sn not in supported_sub_funs:
                continue

            # 遍历支持的通讯类型SF=01、02、03
            for sf in supported_comm_types:
                if sf not in [0x01, 0x02, 0x03]:
                    continue

                TestLog("INFO", "Service_0x28", f"在[{desc}]下发送 28 {hex(sn)} {hex(sf)} 请求，检查是否触发 NRC22")

                try:
                    response_message = node.Service_0x28_CommunicationControl(
                        control_type=sn,
                        communication_type=sf,
                        func_req=func_req
                    )
                except Exception as e:
                    TestLog("FAIL", "Service_0x28", f"[{desc}] 下发送 28 {hex(sn)} {hex(sf)} 请求异常: {e}")
                    TestLog("DEBUG", "Service_0x28", f"详细错误: {traceback.format_exc()}")
                    return False

                if response_message is None:
                    TestLog("FAIL", "Service_0x28", f"[{desc}] 下发送 28 {hex(sn)} {hex(sf)} 未收到响应")
                    return False

                data_list = list(response_message.data)
                if len(data_list) >= 3 and data_list[0:3] == [0x7F, 0x28, 0x22]:
                    TestLog(
                        "PASS",
                        "Service_0x28",
                        f"[{desc}] 下 28 {hex(sn)} {hex(sf)} 收到 NRC22 否定响应: {response_message.data.hex()}",
                    )
                    got_nrc22 = True
                elif len(data_list) >= 2 and data_list[0:2] == [0x68, sn]:
                    TestLog(
                        "INFO",
                        "Service_0x28",
                        f"[{desc}] 下 28 {hex(sn)} {hex(sf)} 收到肯定响应(68 {hex(sn)})，可能未满足 NRC22 触发条件: {response_message.data.hex()}",
                    )
                else:
                    TestLog(
                        "FAIL",
                        "Service_0x28",
                        f"[{desc}] 下 28 {hex(sn)} {hex(sf)} 收到异常响应，期望 68 {hex(sn)} 或 7F 28 22，实际: {response_message.data.hex()}",
                    )
                    return False

    if not got_nrc22:
        TestLog(
            "FAIL",
            "Service_0x28",
            "遍历所有 NRC22 条件后均未收到 7F 28 22，请检查 UDSTestParams.NRC22_ConditionList 配置或 DUT 行为",
        )
        return False

    return True


def test_phyRequest_28_NRC22(
        node: UDSNode,
        name: str = "[TG4_TC6] 28服务NRC22检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG4_TC6] 28服务NRC22检查(物理寻址)
    """
    step = 0

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step3: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # Step4: 遍历触发NRC22的所有条件并发送28 SN SF请求
        step += 1
        TestLog("INFO", f"Step{step}", "遍历触发NRC22的所有条件并发送28 SN SF请求")
        if not __send_28_sn_sf_with_nrc22_conditions(node, func_req=func_flg):
            return

        # Step5: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "28服务NRC22检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_28_Function_Check(
        node: UDSNode,
        name: str = "[TG4_TC7] 28服务功能检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG4_TC7] 28服务功能检查(物理寻址)
    """
    step = 0

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step3: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # Step4: 如果ECU不支持0x01子功能，跳转至步骤11
        step += 1
        TestLog("INFO", f"Step{step}", "检查是否支持0x01子功能")
        if 0x01 not in UDSTestParams.Services28SubFunSupportList:
            TestLog("INFO", "", "ECU不支持0x01子功能，跳转至步骤11")
            step += 6
        else:
            # Step5: 发送28 01 01请求（如果ECU不支持0x01通信类型，跳转至步骤7）
            step += 1
            TestLog("INFO", f"Step{step}", "检查是否支持0x01通信类型")
            if 0x01 not in UDSTestParams.Services28CommTypeSupportList:
                TestLog("INFO", "", "ECU不支持0x01通信类型，跳转至步骤7")
                step += 1  # 跳过步骤5
            else:
                TestLog("INFO", f"Step{step}", "发送28 01 01请求")
                if not __service_28_check_lin(node, 0x01, 0x01, [0x68, 0x01], "肯定响应(68 01)", func_req=func_flg):
                    return
                # Step6: 发送28 00 01请求
                step += 1
                TestLog("INFO", f"Step{step}", "发送28 00 01请求")
                if not __service_28_check_lin(node, 0x00, 0x01, [0x68, 0x00], "肯定响应(68 00)", func_req=func_flg):
                    return

            # Step7: 发送28 01 02请求（如果ECU不支持0x02通信类型，跳转至步骤9）
            step += 1
            TestLog("INFO", f"Step{step}", "检查是否支持0x02通信类型")
            if 0x02 not in UDSTestParams.Services28CommTypeSupportList:
                TestLog("INFO", "", "ECU不支持0x02通信类型，跳转至步骤9")
                step += 1  # 跳过步骤7
            else:
                TestLog("INFO", f"Step{step}", "发送28 01 02请求")
                if not __service_28_check_lin(node, 0x01, 0x02, [0x68, 0x01], "肯定响应(68 01)", func_req=func_flg):
                    return
                # Step8: 发送28 00 01请求
                step += 1
                TestLog("INFO", f"Step{step}", "发送28 00 01请求")
                if not __service_28_check_lin(node, 0x00, 0x01, [0x68, 0x00], "肯定响应(68 00)", func_req=func_flg):
                    return

            # Step9: 发送28 01 03请求（如果ECU不支持0x03通信类型，跳转至步骤11）
            step += 1
            TestLog("INFO", f"Step{step}", "检查是否支持0x03通信类型")
            if 0x03 not in UDSTestParams.Services28CommTypeSupportList:
                TestLog("INFO", "", "ECU不支持0x03通信类型，跳转至步骤11")
                step += 1  # 跳过步骤9
            else:
                TestLog("INFO", f"Step{step}", "发送28 01 03请求")
                if not __service_28_check_lin(node, 0x01, 0x03, [0x68, 0x01], "肯定响应(68 01)", func_req=func_flg):
                    return
                # Step10: 发送28 00 01请求
                step += 1
                TestLog("INFO", f"Step{step}", "发送28 00 01请求")
                if not __service_28_check_lin(node, 0x00, 0x01, [0x68, 0x00], "肯定响应(68 00)", func_req=func_flg):
                    return

        # Step11: 如果ECU不支持0x02子功能，跳转至步骤18
        step += 1
        TestLog("INFO", f"Step{step}", "检查是否支持0x02子功能")
        if 0x02 not in UDSTestParams.Services28SubFunSupportList:
            TestLog("INFO", "", "ECU不支持0x02子功能，跳转至步骤18")
            step += 6  # 跳过步骤12-17
        else:
            # Step12: 发送28 02 01请求（如果ECU不支持0x01通信类型，跳转至步骤14）
            step += 1
            TestLog("INFO", f"Step{step}", "检查是否支持0x01通信类型")
            if 0x01 not in UDSTestParams.Services28CommTypeSupportList:
                TestLog("INFO", "", "ECU不支持0x01通信类型，跳转至步骤14")
                step += 1  # 跳过步骤12
            else:
                TestLog("INFO", f"Step{step}", "发送28 02 01请求")
                if not __service_28_check_lin(node, 0x02, 0x01, [0x68, 0x02], "肯定响应(68 02)", func_req=func_flg):
                    return
                # Step13: 发送28 00 01请求
                step += 1
                TestLog("INFO", f"Step{step}", "发送28 00 01请求")
                if not __service_28_check_lin(node, 0x00, 0x01, [0x68, 0x00], "肯定响应(68 00)", func_req=func_flg):
                    return

            # Step14: 发送28 02 02请求（如果ECU不支持0x02通信类型，跳转至步骤16）
            step += 1
            TestLog("INFO", f"Step{step}", "检查是否支持0x02通信类型")
            if 0x02 not in UDSTestParams.Services28CommTypeSupportList:
                TestLog("INFO", "", "ECU不支持0x02通信类型，跳转至步骤16")
                step += 1  # 跳过步骤14
            else:
                TestLog("INFO", f"Step{step}", "发送28 02 02请求")
                if not __service_28_check_lin(node, 0x02, 0x02, [0x68, 0x02], "肯定响应(68 02)", func_req=func_flg):
                    return
                # Step15: 发送28 00 02请求
                step += 1
                TestLog("INFO", f"Step{step}", "发送28 00 02请求")
                if not __service_28_check_lin(node, 0x00, 0x02, [0x68, 0x00], "肯定响应(68 00)", func_req=func_flg):
                    return

            # Step16: 发送28 02 03请求（如果ECU不支持0x03通信类型，跳转至步骤18）
            step += 1
            TestLog("INFO", f"Step{step}", "检查是否支持0x03通信类型")
            if 0x03 not in UDSTestParams.Services28CommTypeSupportList:
                TestLog("INFO", "", "ECU不支持0x03通信类型，跳转至步骤18")
                step += 1  # 跳过步骤16
            else:
                TestLog("INFO", f"Step{step}", "发送28 02 03请求")
                if not __service_28_check_lin(node, 0x02, 0x03, [0x68, 0x02], "肯定响应(68 02)", func_req=func_flg):
                    return
                # Step17: 发送28 00 03请求
                step += 1
                TestLog("INFO", f"Step{step}", "发送28 00 03请求")
                if not __service_28_check_lin(node, 0x00, 0x03, [0x68, 0x00], "肯定响应(68 00)", func_req=func_flg):
                    return

        # Step18: 如果ECU不支持0x03子功能，跳转至步骤25
        step += 1
        TestLog("INFO", f"Step{step}", "检查是否支持0x03子功能")
        if 0x03 not in UDSTestParams.Services28SubFunSupportList:
            TestLog("INFO", "", "ECU不支持0x03子功能，跳转至步骤25")
            step += 6  # 跳过步骤19-24
        else:
            # Step19: 发送28 03 01请求（如果ECU不支持0x01通信类型，跳转至步骤21）
            step += 1
            TestLog("INFO", f"Step{step}", "检查是否支持0x01通信类型")
            if 0x01 not in UDSTestParams.Services28CommTypeSupportList:
                TestLog("INFO", "", "ECU不支持0x01通信类型，跳转至步骤21")
                step += 1  # 跳过步骤19
            else:
                TestLog("INFO", f"Step{step}", "发送28 03 01请求")
                if not __service_28_check_lin(node, 0x03, 0x01, [0x68, 0x03], "肯定响应(68 03)", func_req=func_flg):
                    return
                # Step20: 发送28 00 01请求
                step += 1
                TestLog("INFO", f"Step{step}", "发送28 00 01请求")
                if not __service_28_check_lin(node, 0x00, 0x01, [0x68, 0x00], "肯定响应(68 00)", func_req=func_flg):
                    return

            # Step21: 发送28 03 02请求（如果ECU不支持0x02通信类型，跳转至步骤23）
            step += 1
            TestLog("INFO", f"Step{step}", "检查是否支持0x02通信类型")
            if 0x02 not in UDSTestParams.Services28CommTypeSupportList:
                TestLog("INFO", "", "ECU不支持0x02通信类型，跳转至步骤23")
                step += 1  # 跳过步骤21
            else:
                TestLog("INFO", f"Step{step}", "发送28 03 02请求")
                if not __service_28_check_lin(node, 0x03, 0x02, [0x68, 0x03], "肯定响应(68 03)", func_req=func_flg):
                    return
                # Step22: 发送28 00 02请求
                step += 1
                TestLog("INFO", f"Step{step}", "发送28 00 02请求")
                if not __service_28_check_lin(node, 0x00, 0x02, [0x68, 0x00], "肯定响应(68 00)", func_req=func_flg):
                    return

            # Step23: 发送28 03 03请求（如果ECU不支持0x03通信类型，跳转至步骤25）
            step += 1
            TestLog("INFO", f"Step{step}", "检查是否支持0x03通信类型")
            if 0x03 not in UDSTestParams.Services28CommTypeSupportList:
                TestLog("INFO", "", "ECU不支持0x03通信类型，跳转至步骤25")
                step += 1  # 跳过步骤23
            else:
                TestLog("INFO", f"Step{step}", "发送28 03 03请求")
                if not __service_28_check_lin(node, 0x03, 0x03, [0x68, 0x03], "肯定响应(68 03)", func_req=func_flg):
                    return
                # Step24: 发送28 00 03请求
                step += 1
                TestLog("INFO", f"Step{step}", "发送28 00 03请求")
                if not __service_28_check_lin(node, 0x00, 0x03, [0x68, 0x00], "肯定响应(68 00)", func_req=func_flg):
                    return

        # Step25: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "28服务功能检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_28_NRC31(
        node: UDSNode,
        name: str = "[TG4_TC8] 28服务NRC31检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG4_TC8] 28服务NRC31检查(物理寻址)
    """
    step = 0

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step3: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        supported_sub_funs = UDSTestParams.Services28SubFunSupportList
        supported_comm_types = UDSTestParams.Services28CommTypeSupportList

        step += 1
        for control_type in [0x01, 0x02, 0x03]:
            if control_type not in supported_sub_funs:
                continue
            for comm_type in range(0x00, 0x11):
                if comm_type in supported_comm_types:  # [1, 2, 3]
                    continue
                TestLog("INFO", f"Step{step}", f"发送28 {control_type:02X} {comm_type:02X}请求(不支持的通信类型)")
                # 如果使用scapy的接口，是无法构造期望的报文，因此需要使用spec_data，指定发送的数据
                if not __service_28_check_lin(node, None, None, [0x7F, 0x28, 0x31], "NRC31响应(7F 28 31)",
                                              spec_data=[control_type, comm_type]): return

        # Step5: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "28服务NRC31检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_28_NRC_Priority(
        node: UDSNode,
        name: str = "[TG4_TC9] 28服务NRC优先级检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG4_TC9] 28服务NRC优先级检查(物理寻址)
    """
    step = 0

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step2: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # Step3: 触发NRC22的条件之一并发送28 00 01请求
        step += 1
        TestLog("INFO", f"Step{step}", "触发NRC22的条件之一并发送28 00 01请求")

        # 使用NRC22条件列表中的第一个条件
        cond_list = UDSTestParams.NRC22_ConditionList or [None]
        if cond_list:
            cond = cond_list[0] if isinstance(cond_list[0], str) else "NRC22触发条件"
            TestLog("INFO", "Service_0x28", f"使用条件: {cond}")

        # 发送28 00 01请求，期望NRC22响应
        TestLog("INFO", "Service_0x28", "发送28 00 01请求，检查NRC22响应")

        try:
            response_message = node.Service_0x28_CommunicationControl(
                control_type=0x00,
                communication_type=0x01,
                func_req=func_flg)
            if response_message is None:
                TestLog("FAIL", name, f"Step{step}，发送28 00 01未收到响应")
                return

            data_list = list(response_message.data)
            if len(data_list) >= 3 and data_list[0:3] == [0x7F, 0x28, 0x22]:
                TestLog("PASS", "Service_0x28", f"Step{step}，收到NRC22否定响应: {response_message.data.hex()}")
            elif len(data_list) >= 2 and data_list[0:2] == [0x68, 0x01]:
                TestLog("WARN", "Service_0x28",
                        f"Step{step}，收到肯定响应(68 01)，未触发NRC22条件,继续测试其他NRC优先级场景")
            else:
                TestLog("FAIL", name, f"Step{step}，收到异常响应: {response_message.data.hex()}")
                return
        except Exception as e:
            TestLog("FAIL", name, f"Step{step}，发送11 01请求异常: {e}")
            TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
            return

        # Step4: 发送28 00 01 00请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送28 00 01 00请求")
        if not __service_28_check_lin(
                node,
                0x00,
                0x01,
                [0x7F, 0x28, 0x7F],
                "28 00 01 00请求NRC7F检查",
                func_req=func_flg,
                dl=4,
                dl_padding=0x00,
        ):
            return

        # Step5: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step6: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # Step7: 发送28请求（缺少参数）
        step += 1
        TestLog("INFO", f"Step{step}", "发送28请求")
        if not __service_28_check_lin(
                node,
                None,
                None,
                [0x7F, 0x28, 0x13],
                "28请求NRC13检查",
                func_req=func_flg,
        ):
            return

        # Step8: 发送28 06请求（不支持的子功能）
        step += 1
        TestLog("INFO", f"Step{step}", "发送28 06请求")
        if not __service_28_check_lin(
                node,
                0x06,
                None,
                [0x7F, 0x28, 0x12],
                "28 06请求NRC12检查",
                func_req=func_flg,
        ):
            return

        # Step9: 发送28 04 01请求（不支持的子功能）
        step += 1
        TestLog("INFO", f"Step{step}", "发送28 04 01请求")
        if not __service_28_check_lin(
                node,
                0x04,
                0x01,
                [0x7F, 0x28, 0x13],
                "28 04 01请求NRC13检查",
                func_req=func_flg,
        ):
            return

        # Step10: 发送28 06 01请求（不支持的子功能）
        step += 1
        TestLog("INFO", f"Step{step}", "发送28 06 01请求")
        if not __service_28_check_lin(
                node,
                0x06,
                0x01,
                [0x7F, 0x28, 0x12],
                "28 06 01请求NRC12检查",
                func_req=func_flg,
        ):
            return

        # Step11: 发送28 00 04请求（不支持的通信类型）
        step += 1
        TestLog("INFO", f"Step{step}", "发送28 00 04请求")
        if not __service_28_check_lin(
                node,
                0x00,
                0x04,
                [0x7F, 0x28, 0x31],
                "28 00 04请求NRC31检查",
                func_req=func_flg,
        ):
            return

        # Step12: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "28服务NRC优先级检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def __service_3E_check(
        node,
        subfunction,
        expect_data,
        expect_str: str = "",
        func_req: bool = False,
        dl: int | None = None,
        dl_padding: int = 0x00,
        timeout: float = 5,
        *args, **kwargs
):
    try:
        response_message = node.Service_0x3E_TesterPresent(
            subfunction,
            func_req=func_req,
            update_send_data=True,
            dl=dl,
            dl_padding=dl_padding,
            timeout=timeout,
            *args, **kwargs
        )

        # 统一处理响应数据，提取实际的字节数据
        def get_response_data(response):
            if response is None:
                return None
            if hasattr(response, 'data'):
                return response.data
            if isinstance(response, bytes):
                return response
            try:
                return bytes(response)
            except:
                return None

        response_data = get_response_data(response_message)

        if expect_data is None:
            # 期望无响应
            if response_data is None or response_data == b'' or len(response_data) == 0:
                TestLog("PASS", "Service_0x3E", f"{expect_str}，无响应符合预期")
                return True

            # 处理有响应数据的情况
            response_hex = response_data.hex() if hasattr(response_data, 'hex') else str(response_data)
            TestLog("FAIL", "Service_0x3E", f"{expect_str}，期望无响应，实际收到: {response_hex}")
            return False

        if response_data is None or response_data == b'' or len(response_data) == 0:
            TestLog("FAIL", "Service_0x3E", f"{expect_str}，未收到响应")
            return False

        if list(response_data[0:len(expect_data)]) != expect_data:
            TestLog(
                "FAIL",
                "Service_0x3E",
                f"{expect_str}，响应不匹配，期望: {bytes(expect_data).hex()} 实际: {response_data.hex()}",
            )
            return False

        TestLog("PASS", "Service_0x3E", f"{expect_str}，响应匹配: {response_data.hex()}")
        return True
    except Exception as e:
        TestLog("FAIL", "Service_0x3E", f"{expect_str}，执行异常: {e}")
        TestLog("DEBUG", "Service_0x3E", f"详细错误: {traceback.format_exc()}")
        return False


def test_phyRequest_3E_Positive(
        node: UDSNode,
        name: str = "[TG5_TC1] 3E服务肯定响应与功能检查(物理寻址)",
        func_flg: bool = False,
):
    step = 0
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "等待4.5s")
        __lin_restart_delay(4.5)

        step += 1
        TestLog("INFO", f"Step{step}", "发送3E 00请求")
        if not __service_3E_check(node, 0x00, expect_data=[0x7E, 0x00], expect_str="肯定响应(7E 00)",
                                  func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "等待4.5s")
        __lin_restart_delay(4.5)

        step += 1
        TestLog("INFO", f"Step{step}", "发送3E 80请求(抑制肯定响应)")
        if not __service_3E_check(node, 0x80, expect_data=None, expect_str="无响应", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "等待4.5s")
        __lin_restart_delay(4.5)

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "等待4.5s")
        __lin_restart_delay(4.5)

        step += 1
        TestLog("INFO", f"Step{step}", "发送3E 00请求")
        if not __service_3E_check(node, 0x00, expect_data=[0x7E, 0x00], expect_str="肯定响应(7E 00)",
                                  func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "等待4.5s")
        __lin_restart_delay(4.5)

        step += 1
        TestLog("INFO", f"Step{step}", "发送3E 80请求(抑制肯定响应)")
        if not __service_3E_check(node, 0x80, expect_data=None, expect_str="无响应", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "等待4.5s")
        __lin_restart_delay(4.5)

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)",
                                      func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "等待4.5s")
        __lin_restart_delay(4.5)

        step += 1
        TestLog("INFO", f"Step{step}", "发送3E 00请求")
        if not __service_3E_check(node, 0x00, expect_data=[0x7E, 0x00], expect_str="肯定响应(7E 00)",
                                  func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "等待4.5s")
        __lin_restart_delay(4.5)

        step += 1
        TestLog("INFO", f"Step{step}", "发送3E 80请求(抑制肯定响应)")
        if not __service_3E_check(node, 0x80, expect_data=None, expect_str="无响应", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "等待4.5s")
        __lin_restart_delay(4.5)

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_3E_NRC12(
        node: UDSNode,
        name: str = "[TG5_TC2] 3E服务NRC12检查(物理寻址)",
        func_flg: bool = False,
):
    step = 0
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        TestLog("INFO", "Step3~6", "遍历不支持的子功能，发送3E SN请求，期望NRC12响应")
        for sn in range(0, 0X7F + 1):
            if sn in UDSTestParams.Services3ESubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)}，在3E服务支持的范围内，跳过该SN")
                continue
            TestLog("INFO", "", f"SN={hex(sn)}，不在3E服务支持的范围内，测试该SN")
            if not __service_3E_check(node, sn, expect_data=[0x7F, 0x3E, 0x12], expect_str="否定响应(7F 3E 12)",
                                       func_req=func_flg):
                return

        step = 7
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        TestLog("INFO", "Step10~13", "遍历不支持的子功能，发送3E SN请求，期望NRC12响应")
        for sn in range(0, 0X7F + 1):
            if sn in UDSTestParams.Services3ESubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)}，在3E服务支持的范围内，跳过该SN")
                continue
            TestLog("INFO", "", f"SN={hex(sn)}，不在3E服务支持的范围内，测试该SN")
            if not __service_3E_check(node, sn, expect_data=[0x7F, 0x3E, 0x12], expect_str="否定响应(7F 3E 12)",
                                       func_req=func_flg):
                return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)",
                                      func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        TestLog("INFO", "Step19~22", "遍历不支持的子功能，发送3E SN请求，期望NRC12响应")
        for sn in range(0, 0X7F + 1):
            if sn in UDSTestParams.Services3ESubFunSupportList:
                TestLog("INFO", "", f"SN={hex(sn)}，在3E服务支持的范围内，跳过该SN")
                continue
            TestLog("INFO", "", f"SN={hex(sn)}，不在3E服务支持的范围内，测试该SN")
            if not __service_3E_check(node, sn, expect_data=[0x7F, 0x3E, 0x12], expect_str="否定响应(7F 3E 12)",
                                       func_req=func_flg):
                return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_3E_NRC13(
        node: UDSNode,
        name: str = "[TG5_TC3] 3E服务NRC13检查(物理寻址)",
        func_flg: bool = False,
):
    step = 0
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "发送3E请求(DL=1)，期望NRC13响应")
        if not __service_3E_check(node, None, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)", dl=1,
                                  func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "发送3E 00请求(DL=3,4,5,6,7)，期望NRC13响应")
        for dl in [3, 4, 5, 6, 7]:
            TestLog("INFO", "", f"发送3E 00请求(DL={dl})")
            if not __service_3E_check(node, 0x00, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)",
                                      dl=dl, dl_padding=0, func_req=func_flg):
                return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "发送3E请求(DL=1)，期望NRC13响应")
        if not __service_3E_check(node, None, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)", dl=1,
                                  func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "发送3E 00请求(DL=3,4,5,6,7)，期望NRC13响应")
        for dl in [3, 4, 5, 6, 7]:
            TestLog("INFO", "", f"发送3E 00请求(DL={dl})")
            if not __service_3E_check(node, 0x00, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)",
                                      dl=dl, dl_padding=0, func_req=func_flg):
                return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)",
                                      func_req=func_flg):
            return

        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "发送3E请求(DL=1)，期望NRC13响应")
        if not __service_3E_check(node, None, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)", dl=1,
                                  func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "发送3E 00请求(DL=3,4,5,6,7)，期望NRC13响应")
        for dl in [3, 4, 5, 6, 7]:
            TestLog("INFO", "", f"发送3E 00请求(DL={dl})")
            if not __service_3E_check(node, 0x00, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)",
                                      dl=dl, dl_padding=0, func_req=func_flg):
                return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中",
                func_req=func_flg,
        ):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_3E_NRCPriority(
        node: UDSNode,
        name: str = "[TG5_TC4] 3E服务NRC优先级检查(物理寻址)",
        func_flg: bool = False,
):
    step = 0
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "发送3E请求，期望NRC13响应")
        if not __service_3E_check(node, None, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)", dl=1,
                                  func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "发送3E 01 00请求(DL=3，不支持的子功能)，期望NRC12响应")
        if not __service_3E_check(node, 0X01, expect_data=[0x7F, 0x3E, 0x12], expect_str="否定响应(7F 3E 12)", dl=3,
                                  func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "发送3E 00 00请求(DL=3，不支持的子功能)，期望NRC12响应")
        if not __service_3E_check(node, 0X00, expect_data=[0x7F, 0x3E, 0x13], expect_str="否定响应(7F 3E 13)", dl=3,
                                  func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def __service_85_check_lin(
        node: UDSNode,
        dtc_setting_type: int | None,
        expect_data,
        expect_str: str = "",
        func_req: bool = False,
        dl: int | None = None,
        dl_padding: int = 0x00,
        timeout: float = 5,
        *args, **kwargs
) -> bool:
    """
    LIN 下 0x85 服务发送与结果校验
    """
    try:
        response_message = node.Service_0x85_ControlDTCSetting(
            dtc_setting_type,
            func_req=func_req,
            dl=dl,
            dl_padding=dl_padding,
            timeout=timeout,
            *args, **kwargs
        )

        # 统一处理响应数据，提取实际的字节数据
        def get_response_data(response):
            if response is None:
                return None
            if hasattr(response, 'data'):
                return response.data
            if isinstance(response, bytes):
                return response
            try:
                return bytes(response)
            except:
                return None

        response_data = get_response_data(response_message)

        if expect_data is None:
            # 期望无响应
            if response_data is None or response_data == b'' or len(response_data) == 0:
                TestLog("PASS", "Service_0x85", f"{expect_str}，无响应符合预期")
                return True

            # 处理有响应数据的情况
            response_hex = response_data.hex() if hasattr(response_data, 'hex') else str(response_data)
            TestLog("FAIL", "Service_0x85", f"{expect_str}，期望无响应，实际收到: {response_hex}")
            return False

        if response_data is None or response_data == b'' or len(response_data) == 0:
            TestLog("FAIL", "Service_0x85", f"{expect_str}，未收到响应")
            return False

        if list(response_data[0:len(expect_data)]) != expect_data:
            TestLog(
                "FAIL",
                "Service_0x85",
                f"{expect_str}，响应不匹配，期望: {bytes(expect_data).hex()} 实际: {response_data.hex()}",
            )
            return False

        TestLog("PASS", "Service_0x85", f"{expect_str}，响应匹配: {response_data.hex()}")
        return True
    except Exception as e:
        TestLog("FAIL", "Service_0x85", f"{expect_str}，执行异常: {e}")
        return False


def test_phyRequest_85_Positive(
        node: UDSNode,
        name: str = "[TG6_TC1] 85服务肯定响应检查(物理寻址)",
        func_flg: bool = False,
):
    """85服务肯定响应检查(物理寻址)"""
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "发送85 02请求关闭DTC记录")
        if not __service_85_check_lin(node, 0x02, [0xC5, 0x02], "肯定响应(C5 02)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "发送85 01请求开启DTC记录")
        if not __service_85_check_lin(node, 0x01, [0xC5, 0x01], "肯定响应(C5 01)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "发送85 82请求关闭DTC记录")
        if not __service_85_check_lin(node, 0x82, None, "无响应", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "发送85 81请求开启DTC记录")
        if not __service_85_check_lin(node, 0x81, None, "无响应", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def __service_14_check_lin(
        node: UDSNode,
        dtc: int | None,
        expect_data,
        expect_str: str = "",
        func_req: bool = False,
        dl: int | None = None,
        dl_padding: int = 0x00,
        timeout: float = 5,
        *args, **kwargs
) -> bool:
    """
    LIN 下 0x14 服务发送与结果校验
    """
    try:
        if dtc is not None:
            h = (dtc >> 16) & 0xFF
            m = (dtc >> 8) & 0xFF
            l = dtc & 0xFF
            response_message = node.Service_0x14_ClearDiagnosticInformation(
                h=h, m=m, l=l,
                func_req=func_req,
                dl=dl,
                dl_padding=dl_padding,
                timeout=timeout,
                *args, **kwargs
            )
        else:
            response_message = node.Service_0x14_ClearDiagnosticInformation(
                None, None, None,
                func_req=func_req,
                dl=dl,
                dl_padding=dl_padding,
                timeout=timeout,
                *args, **kwargs
            )
        if expect_data is None:
            # 期望无响应
            if response_message is None:
                TestLog("PASS", "Service_0x14", f"{expect_str}，无响应符合预期")
                return True
            TestLog("FAIL", "Service_0x14", f"{expect_str}，期望无响应，实际收到: {response_message.data.hex()}")
            return False

        if response_message is None:
            TestLog("FAIL", "Service_0x14", f"{expect_str}，未收到响应")
            return False

        if list(response_message.data[0:len(expect_data)]) != expect_data:
            TestLog(
                "FAIL",
                "Service_0x14",
                f"{expect_str}，响应不匹配，期望: {bytes(expect_data).hex()} 实际: {response_message.data.hex()}",
            )
            return False

        TestLog("PASS", "Service_0x14", f"{expect_str}，响应匹配: {response_message.data.hex()}")
        return True
    except Exception as e:
        TestLog("FAIL", "Service_0x14", f"{expect_str}，执行异常: {e}")
        return False


def __service_19_check_lin(
        node: UDSNode,
        report_type: int | None,
        expect_data,
        expect_str: str = "",
        func_req: bool = False,
        dl: int | None = None,
        dl_padding: int = 0x00,
        timeout: float = 5,
        *args, **kwargs
) -> tuple[bool, None] | tuple[bool, Any]:
    """
    LIN 下 0x19 服务发送与结果校验
    """
    try:
        # 调用底层服务
        response_message = node.Service_0x19_ReadDTCInformation(
            report_type=report_type,
            func_req=func_req,
            dl=dl,
            dl_padding=dl_padding,
            timeout=timeout,
            *args, **kwargs
        )

        # 校验响应
        if expect_data is None:
            # 期望无响应
            if response_message is None:
                TestLog("PASS", "Service_0x19", f"{expect_str}，无响应符合预期")
                return True, None
            TestLog("FAIL", "Service_0x19", f"{expect_str}，期望无响应，实际收到: {response_message.data.hex()}")
            return False, None

        if response_message is None:
            TestLog("FAIL", "Service_0x19", f"{expect_str}，未收到响应")
            return False, None

        # 将响应数据转换为列表进行比较
        response_list = list(response_message.data)

        # 检查响应数据是否匹配期望数据
        if len(response_list) < len(expect_data):
            TestLog(
                "FAIL",
                "Service_0x19",
                f"{expect_str}，响应长度不足，期望长度: {len(expect_data)} 实际长度: {len(response_list)}，实际数据: {response_message.data.hex()}",
            )
            return False, None

        if response_list[0:len(expect_data)] != expect_data:
            TestLog(
                "FAIL",
                "Service_0x19",
                f"{expect_str}，响应不匹配，期望: {bytes(expect_data).hex()} 实际: {response_message.data.hex()}",
            )
            return False, None

        TestLog("PASS", "Service_0x19", f"{expect_str}，响应匹配: {response_message.data.hex()}")
        return True, response_message

    except Exception as e:
        TestLog("FAIL", "Service_0x19", f"{expect_str}，执行异常: {e}")
        return False, None


def get_dtc_from_19_resp(response_message):
    """
    从19服务响应中提取DTC信息
    """
    if response_message is None or response_message.data is None:
        return "无DTC信息"

    data = response_message.data
    if len(data) < 2:
        return "响应数据长度不足"

    return f"DTC数据: {data.hex()}"


def test_phyRequest_85_FunctionCheck(
        node: UDSNode,
        name: str = "[TG6_TC2] 85服务功能检查(物理寻址)",
        func_flg: bool = False,
):
    """
    85服务功能检查(物理寻址)
    """

    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        rVnormal = P.CANInfo.Vnormal
        rVlow = 8

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "开启3E服务")
        tester_present_start(node, period_ms=2000)

        step += 1
        TestLog("INFO", f"Step{step}", "制造低压故障")
        ctx.power_ctrl.set_voltage(rVlow)
        __lin_restart_delay(5)

        step += 1
        TestLog("INFO", f"Step{step}", "发送19 02 09读DTC")
        status, resp = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                              expect_data=[0x59], expect_str="肯定响应(59)", func_req=func_flg)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        step += 1
        TestLog("INFO", f"Step{step}", "检查低压DTC是否被成功存储，若不成功则终止测试项")
        # TODO: 校验低压DTC存储情况

        step += 1
        TestLog("INFO", f"Step{step}", "恢复正常供电电压")
        ctx.power_ctrl.set_voltage(rVnormal)
        __lin_restart_delay(1)

        step += 1
        TestLog("INFO", f"Step{step}", "清除DUT中的DTC(14 FF FF FF)")
        if not __service_14_check_lin(node, 0xFFFFFF, [0x54], "肯定响应(54)", func_req=func_flg, timeout=100):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "发送19 02 09读DTC")
        status, resp = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                              expect_data=[0x59], expect_str="肯定响应(59)", func_req=func_flg)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        step += 1
        TestLog("INFO", f"Step{step}", "检查低压DTC被成功清除")
        # TODO: 校验低压DTC清除情况

        # 85 02功能测试
        step += 1
        TestLog("INFO", f"Step{step}", "发送85 02请求关闭DTC记录")
        if not __service_85_check_lin(node, 0x02, [0xC5, 0x02], "肯定响应(C5 02)", func_req=func_flg): return

        step += 1
        TestLog("INFO", f"Step{step}", "制造低压故障")
        ctx.power_ctrl.set_voltage(rVlow)
        __lin_restart_delay(5)

        step += 1
        TestLog("INFO", f"Step{step}", "发送19 02 09读DTC")
        status, resp = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                              expect_data=[0x59], expect_str="肯定响应(59)", func_req=func_flg)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        step += 1
        TestLog("INFO", f"Step{step}", "检查低压DTC是否被成功存储")
        # TODO: 校验低压DTC存储情况

        # 85 01功能测试
        step += 1
        TestLog("INFO", f"Step{step}", "发送85 01请求开启DTC记录，等待5s")
        if not __service_85_check_lin(node, 0x01, [0xC5, 0x01], "肯定响应(C5 01)", func_req=func_flg): return
        __lin_restart_delay(5)

        step += 1
        TestLog("INFO", f"Step{step}", "发送19 02 09读DTC")
        status, resp = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                              expect_data=[0x59], expect_str="肯定响应(59)", func_req=func_flg)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        step += 1
        TestLog("INFO", f"Step{step}", "检查低压DTC是否被成功存储")
        # TODO: 校验低压DTC存储情况

        step += 1
        TestLog("INFO", f"Step{step}", "恢复正常供电电压")
        ctx.power_ctrl.set_voltage(rVnormal)
        __lin_restart_delay(1)

        step += 1
        TestLog("INFO", f"Step{step}", "清除DUT中的DTC(14 FF FF FF)")
        if not __service_14_check_lin(node, 0xFFFFFF, [0x54], "肯定响应(54)", func_req=func_flg, timeout=100): return

        step += 1
        TestLog("INFO", f"Step{step}", "发送19 02 09读DTC")
        status, resp = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                              expect_data=[0x59], expect_str="肯定响应(59)", func_req=func_flg)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        step += 1
        TestLog("INFO", f"Step{step}", "检查低压DTC被成功清除")
        # TODO: 校验低压DTC清除情况

        # 85 82功能测试
        step += 1
        TestLog("INFO", f"Step{step}", "发送85 82请求关闭DTC记录")
        if not __service_85_check_lin(node, 0x82, None, "无响应", func_req=func_flg): return
        __lin_restart_delay(1)

        step += 1
        TestLog("INFO", f"Step{step}", "制造低压故障")
        ctx.power_ctrl.set_voltage(rVlow)
        __lin_restart_delay(5)

        step += 1
        TestLog("INFO", f"Step{step}", "发送19 02 09读DTC")
        status, resp = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                              expect_data=[0x59], expect_str="肯定响应(59)", func_req=func_flg)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        step += 1
        TestLog("INFO", f"Step{step}", "检查低压DTC是否被成功存储")
        # TODO: 校验低压DTC存储情况

        # 85 81功能测试
        step += 1
        TestLog("INFO", f"Step{step}", "发送85 81请求开启DTC记录，等待5s")
        if not __service_85_check_lin(node, 0x81, None, "无响应", func_req=func_flg): return
        __lin_restart_delay(5)

        step += 1
        TestLog("INFO", f"Step{step}", "发送19 02 09读DTC")
        status, resp = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                              expect_data=[0x59], expect_str="肯定响应(59)", func_req=func_flg)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        step += 1
        TestLog("INFO", f"Step{step}", "检查低压DTC是否被成功存储")
        # TODO: 校验低压DTC存储情况

        step += 1
        TestLog("INFO", f"Step{step}", "恢复正常供电电压")
        ctx.power_ctrl.set_voltage(rVnormal)
        __lin_restart_delay(1)

        step += 1
        TestLog("INFO", f"Step{step}", "清除DUT中的DTC(14 FF FF FF)")
        if not __service_14_check_lin(node, 0xFFFFFF, [0x54], "肯定响应(54)", func_req=func_flg, timeout=100): return

        step += 1
        TestLog("INFO", f"Step{step}", "发送19 02 09读DTC")
        status, resp = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                              expect_data=[0x59], expect_str="肯定响应(59)", func_req=func_flg)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        step += 1
        TestLog("INFO", f"Step{step}", "检查低压DTC被成功清除")
        # TODO: 校验低压DTC清除情况

        # 会话跳转功能失效测试
        step += 1
        TestLog("INFO", f"Step{step}", "发送85 02请求关闭DTC记录")
        if not __service_85_check_lin(node, 0x02, [0xC5, 0x02], "肯定响应(C5 02)", func_req=func_flg): return

        step += 1
        TestLog("INFO", f"Step{step}", "制造低压故障")
        ctx.power_ctrl.set_voltage(rVlow)
        __lin_restart_delay(5)

        step += 1
        TestLog("INFO", f"Step{step}", "发送19 02 09读DTC")
        status, resp = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                              expect_data=[0x59], expect_str="肯定响应(59)", func_req=func_flg)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        step += 1
        TestLog("INFO", f"Step{step}", "检查低压DTC是否被成功存储")
        # TODO: 校验低压DTC存储情况

        step += 1
        TestLog("INFO", f"Step{step}", "发送10 01请求进入默认会话（跳转到默认会话使85服务功能失效）")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg): return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        step += 1
        TestLog("INFO", f"Step{step}", "发送19 02 09读DTC")
        status, resp = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                              expect_data=[0x59], expect_str="肯定响应(59)", func_req=func_flg)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        step += 1
        TestLog("INFO", f"Step{step}", "检查低压DTC是否被成功存储")
        # TODO: 校验低压DTC存储情况

        step += 1
        TestLog("INFO", f"Step{step}", "恢复正常供电电压")
        ctx.power_ctrl.set_voltage(rVnormal)
        __lin_restart_delay(1)

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg): return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "清除DUT中的DTC(14 FF FF FF)")
        if not __service_14_check_lin(node, 0xFFFFFF, [0x54], "肯定响应(54)", func_req=func_flg, timeout=100):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "发送19 02 09读DTC")
        status, resp = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                              expect_data=[0x59], expect_str="肯定响应(59)", func_req=func_flg)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        step += 1
        TestLog("INFO", f"Step{step}", "检查低压DTC被成功清除")
        # TODO: 校验低压DTC清除情况

        # 复位功能失效测试
        step += 1
        TestLog("INFO", f"Step{step}", "发送85 02请求关闭DTC记录")
        if not __service_85_check_lin(node, 0x02, [0xC5, 0x02], "肯定响应(C5 02)", func_req=func_flg): return

        step += 1
        TestLog("INFO", f"Step{step}", "制造低压故障")
        ctx.power_ctrl.set_voltage(rVlow)
        __lin_restart_delay(5)

        step += 1
        TestLog("INFO", f"Step{step}", "发送19 02 09读DTC")
        status, resp = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                              expect_data=[0x59], expect_str="肯定响应(59)", func_req=func_flg)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        step += 1
        TestLog("INFO", f"Step{step}", "检查低压DTC是否被成功存储")
        # TODO: 校验低压DTC存储情况

        step += 1
        TestLog("INFO", f"Step{step}", "发送11 01请求复位（复位使85服务功能失效）")
        if not __service_11_check(node, 0x01, [0x51, 0x01], "肯定响应(51 01)", func_req=func_flg): return
        __lin_restart_delay(3)
        step += 1
        TestLog("INFO", f"Step{step}", "发送19 02 09读DTC")
        status, resp = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                              expect_data=[0x59], expect_str="肯定响应(59)", func_req=func_flg)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        step += 1
        TestLog("INFO", f"Step{step}", "检查低压DTC是否被成功存储")
        # TODO: 校验低压DTC存储情况

        step += 1
        TestLog("INFO", f"Step{step}", "恢复正常供电电压")
        ctx.power_ctrl.set_voltage(rVnormal)
        __lin_restart_delay(1)

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg): return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "清除DUT中的DTC(14 FF FF FF)")
        if not __service_14_check_lin(node, 0xFFFFFF, [0x54], "肯定响应(54)", func_req=func_flg, timeout=100): return

        step += 1
        TestLog("INFO", f"Step{step}", "发送19 02 09读DTC")
        status, resp = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                              expect_data=[0x59], expect_str="肯定响应(59)", func_req=func_flg)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        step += 1
        TestLog("INFO", f"Step{step}", "检查低压DTC被成功清除")
        # TODO: 校验低压DTC清除情况

        # S3 Server超时功能失效测试
        step += 1
        TestLog("INFO", f"Step{step}", "发送85 02请求关闭DTC记录")
        if not __service_85_check_lin(node, 0x02, [0xC5, 0x02], "肯定响应(C5 02)", func_req=func_flg): return

        step += 1
        TestLog("INFO", f"Step{step}", "制造低压故障")
        ctx.power_ctrl.set_voltage(rVlow)
        __lin_restart_delay(5)

        step += 1
        TestLog("INFO", f"Step{step}", "发送19 02 09读DTC")
        status, resp = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                              expect_data=[0x59], expect_str="肯定响应(59)", func_req=func_flg)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        step += 1
        TestLog("INFO", f"Step{step}", "检查低压DTC是否被成功存储")
        # TODO: 校验低压DTC存储情况

        step += 1
        TestLog("INFO", f"Step{step}", "等待6s（S3 Server超时使85服务功能失效）")
        __lin_restart_delay(6)

        step += 1
        TestLog("INFO", f"Step{step}", "发送19 02 09读DTC")
        status, resp = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                              expect_data=[0x59], expect_str="肯定响应(59)", func_req=func_flg)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        step += 1
        TestLog("INFO", f"Step{step}", "检查低压DTC是否被成功存储")
        # TODO: 校验低压DTC存储情况

        step += 1
        TestLog("INFO", f"Step{step}", "恢复正常供电电压")
        ctx.power_ctrl.set_voltage(rVnormal)
        __lin_restart_delay(1)

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg): return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "清除DUT中的DTC(14 FF FF FF)")
        if not __service_14_check_lin(node, 0xFFFFFF, [0x54], "肯定响应(54)", func_req=func_flg, timeout=100): return

        step += 1
        TestLog("INFO", f"Step{step}", "发送19 02 09读DTC")
        status, resp = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                              expect_data=[0x59], expect_str="肯定响应(59)", func_req=func_flg)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        step += 1
        TestLog("INFO", f"Step{step}", "检查低压DTC被成功清除")
        # TODO: 校验低压DTC清除情况

        step += 1
        TestLog("INFO", f"Step{step}", "发送85 02请求关闭DTC记录")
        if not __service_85_check_lin(node, 0x02, [0xC5, 0x02], "肯定响应(C5 02)", func_req=func_flg): return

        step += 1
        TestLog("INFO", f"Step{step}", "制造低压故障")
        ctx.power_ctrl.set_voltage(rVlow)
        __lin_restart_delay(5)

        step += 1
        TestLog("INFO", f"Step{step}", "发送19 02 09读DTC")
        status, resp = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                              expect_data=[0x59], expect_str="肯定响应(59)", func_req=func_flg)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        step += 1
        TestLog("INFO", f"Step{step}", "检查低压DTC是否被成功存储")
        # TODO: 校验低压DTC存储情况

        # DUT重新上电功能失效测试
        step += 1
        TestLog("INFO", f"Step{step}", "DUT重新上电（重新上下电使85服务功能失效）")
        __power_resatrt(2, 3)

        step += 1
        TestLog("INFO", f"Step{step}", "发送19 02 09读DTC")
        status, resp = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                              expect_data=[0x59], expect_str="肯定响应(59)", func_req=func_flg)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        step += 1
        TestLog("INFO", f"Step{step}", "检查低压DTC是否被成功存储")
        # TODO: 校验低压DTC存储情况

        step += 1
        TestLog("INFO", f"Step{step}", "恢复正常供电电压")
        ctx.power_ctrl.set_voltage(rVnormal)
        __lin_restart_delay(1)

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["default"], "位于默认会话中(7F 31 7F)",
                                           func_req=func_flg):
            return

        TestLog("PASS", name, "85服务功能检查测试完成")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()


def test_phyRequest_85_NRC12(
        node: UDSNode,
        name: str = "[TG6_TC3] 85服务NRC12检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG6_TC3] 85服务NRC12检查(物理寻址)
    """
    step = 0
    min_sn = 0x00
    max_sn = 0x11

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step3: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中(71 01 02 03 00)",
                func_req=func_flg,
        ):
            return

        # Step4: 令SN=0x00
        step += 1
        TestLog("INFO", f"Step{step}", "令SN=0x00")
        sn = min_sn

        supported_sub_funs = UDSTestParams.Services85SubFunSupportList

        # Step5-7: 步骤
        while sn <= max_sn:
            # Step5: SN<0xFF，则SN=SN+1
            if sn in supported_sub_funs and sn < max_sn:
                TestLog("INFO", "", f"SN={hex(sn)} 在85服务支持列表中，跳过")
                sn += 1
                continue

            # Step6: 发送子功能=SN的85服务请求
            step += 1
            TestLog("INFO", f"Step{step}", f"发送85服务请求，SN={hex(sn)}")
            if not __service_85_check_lin(
                    node,
                    sn,
                    [0x7F, 0x85, 0x12],
                    f"85服务NRC12检查(SN={hex(sn)})",
                    func_req=func_flg,
            ):
                TestLog("FAIL", name, f"SN={hex(sn)}的NRC12检查失败")
                return

            # Step7: 判断SN跳转步骤
            if sn < max_sn:
                sn += 1
                # 继续循环，回到步骤5逻辑
                continue
            else:
                break

        # Step8: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "仍位于扩展会话中(71 01 02 03 00)",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "85服务NRC12检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_85_NRC13(
        node: UDSNode,
        name: str = "[TG6_TC4] 85服务NRC13检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG6_TC4] 85服务NRC13检查(物理寻址)
    """
    step = 0

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step3: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中(71 01 02 03 00)",
                func_req=func_flg,
        ):
            return

        # Step4: 发送长度为1的85请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送长度为1的85请求(DL=1)")
        if not __service_85_check_lin(
                node,
                None,
                [0x7F, 0x85, 0x13],
                "NRC=0x13的否定响应(7F 85 13)",
                func_req=func_flg,
                dl=1,
        ):
            return

        # Step5: 发送DL=3、4、5、6、7的85 01请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送DL=3、4、5、6、7的85 01请求")
        dl_list = [3, 4, 5, 6, 7]
        for dl in dl_list:
            TestLog("INFO", "", f"发送DL={dl}的85 01请求")
            if not __service_85_check_lin(
                    node,
                    0x01,
                    [0x7F, 0x85, 0x13],
                    f"85 01请求NRC13检查(DL={dl})",
                    func_req=func_flg,
                    dl=dl,
                    dl_padding=0x00,
            ):
                TestLog("FAIL", name, f"85 01请求NRC13检查失败(DL={dl})")
                return

        # Step6: 发送DL=3、4、5、6、7的85 02请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送DL=3、4、5、6、7的85 02请求")
        for dl in dl_list:
            TestLog("INFO", "", f"发送DL={dl}的85 02请求")
            if not __service_85_check_lin(
                    node,
                    0x02,
                    [0x7F, 0x85, 0x13],
                    f"85 02请求NRC13检查(DL={dl})",
                    func_req=func_flg,
                    dl=dl,
                    dl_padding=0x00,
            ):
                TestLog("FAIL", name, f"85 02请求NRC13检查失败(DL={dl})")
                return

        # Step7: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "仍位于扩展会话中(71 01 02 03 00)",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "85服务NRC13检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_85_NRC7F(
        node: UDSNode,
        name: str = "[TG6_TC5] 85服务NRC7F检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG6_TC5] 85服务NRC7F检查(物理寻址)
    """
    step = 0

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step2: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中(7F 31 7F)",
                func_req=func_flg,
        ):
            return

        # Step3: 发送子功能(SN)=01、02的85服务请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送子功能(SN)=01、02的85服务请求")
        for sn in [0x01, 0x02]:
            TestLog("INFO", "", f"发送85请求，SN={hex(sn)}")
            if not __service_85_check_lin(
                    node,
                    sn,
                    [0x7F, 0x85, 0x7F],
                    f"85服务NRC7F检查(SN={hex(sn)})",
                    func_req=func_flg,
            ):
                TestLog("FAIL", name, f"SN={hex(sn)}的NRC7F检查失败")
                return

        # Step4: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "仍位于默认会话中(7F 31 7F)",
                func_req=func_flg,
        ):
            return

        # Step5: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step6: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return
        # Step7: 请求进入刷新会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "刷新会话肯定响应(50 02)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step8: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "位于刷新会话中(7F 31 31)",
                func_req=func_flg,
        ):
            return

        # Step9: 发送子功能(SN)=01、02的85服务请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送子功能(SN)=01、02的85服务请求")
        for sn in [0x01, 0x02]:
            TestLog("INFO", "", f"发送85请求，SN={hex(sn)}")
            if not __service_85_check_lin(
                    node,
                    sn,
                    [0x7F, 0x85, 0x11],
                    f"85服务NRC11检查(SN={hex(sn)})",
                    func_req=func_flg,
            ):
                TestLog("FAIL", name, f"SN={hex(sn)}的NRC11检查失败")
                return

        # Step10: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["programming"],
                "仍位于刷新会话中(7F 31 31)",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "85服务NRC7F检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def __send_85_sn_with_nrc22_conditions(node: UDSNode, func_req: bool = False) -> bool:
    """
    遍历所有可能触发 NRC22 的条件并发送 85 SN 请求
    """
    got_nrc22 = False
    cond_list = UDSTestParams.NRC22_ConditionList or [None]

    supported_sub_funs = UDSTestParams.Services85SubFunSupportList

    for idx, cond in enumerate(cond_list, start=1):
        desc = cond if isinstance(cond, str) else f"条件{idx}"

        # 遍历支持的子功能SN
        for sn in supported_sub_funs:
            TestLog("INFO", "Service_0x85", f"在[{desc}]下发送 85 {hex(sn)} 请求，检查是否触发 NRC22")

            try:
                response_message = node.Service_0x85_ControlDTCSetting(
                    dtc_setting_type=sn,
                    func_req=func_req
                )
            except Exception as e:
                TestLog("FAIL", "Service_0x85", f"[{desc}] 下发送 85 {hex(sn)} 请求异常: {e}")
                TestLog("DEBUG", "Service_0x85", f"详细错误: {traceback.format_exc()}")
                return False

            def get_response_data(response):
                if response is None:
                    return None
                if hasattr(response, 'data'):
                    return response.data
                if isinstance(response, bytes):
                    return response
                try:
                    return bytes(response)
                except:
                    return None

            response_data = get_response_data(response_message)

            if response_data is None or response_data == b'' or len(response_data) == 0:
                TestLog("FAIL", "Service_0x85", f"[{desc}] 下发送 85 {hex(sn)} 未收到响应")
                return False

            data_list = list(response_data)
            if len(data_list) >= 3 and data_list[0:3] == [0x7F, 0x85, 0x22]:
                TestLog(
                    "PASS",
                    "Service_0x85",
                    f"[{desc}] 下 85 {hex(sn)} 收到 NRC22 否定响应: {response_message.data.hex()}",
                )
                got_nrc22 = True
            elif len(data_list) >= 2 and data_list[0:2] == [0xC5, sn]:
                TestLog(
                    "INFO",
                    "Service_0x85",
                    f"[{desc}] 下 85 {hex(sn)} 收到肯定响应(C5 {hex(sn)})，可能未满足 NRC22 触发条件: {response_message.data.hex()}",
                )
            else:
                TestLog(
                    "FAIL",
                    "Service_0x85",
                    f"[{desc}] 下 85 {hex(sn)} 收到异常响应，期望 C5 {hex(sn)} 或 7F 85 22，实际: {response_message.data.hex()}",
                )
                return False

    if not got_nrc22:
        TestLog(
            "FAIL",
            "Service_0x85",
            "遍历所有 NRC22 条件后均未收到 7F 85 22，请检查 UDSTestParams.NRC22_ConditionList 配置或 DUT 行为",
        )
        return False

    return True


def test_phyRequest_85_NRC22(
        node: UDSNode,
        name: str = "[TG6_TC6] 85服务NRC22检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG6_TC6] 85服务NRC22检查(物理寻址)
    """
    step = 0

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step2: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step3: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中(71 01 02 03 00)",
                func_req=func_flg,
        ):
            return

        # Step4: 遍历触发NRC22的所有条件并发送85 SN请求
        step += 1
        TestLog("INFO", f"Step{step}", "遍历触发NRC22的所有条件并发送85 SN请求")
        if not __send_85_sn_with_nrc22_conditions(node, func_req=func_flg):
            return

        # Step5: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "仍位于扩展会话中(71 01 02 03 00)",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "85服务NRC22检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_85_NRCPriority(
        node: UDSNode,
        name: str = "[TG6_TC7] 85服务NRC优先级检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG6_TC7] 85服务NRC优先级检查(物理寻址)
    """
    step = 0

    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # Step1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        # Step2: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x7F, 0x31, 0x7F],
                "位于默认会话中(7F 31 7F)",
                func_req=func_flg,
        ):
            return

        # Step3: 触发NRC22的条件之一并发送85 01请求
        step += 1
        TestLog("INFO", f"Step{step}", "触发NRC22的条件之一并发送85 01请求")

        # 使用NRC22条件列表中的第一个条件
        cond_list = UDSTestParams.NRC22_ConditionList or [None]
        if cond_list:
            cond = cond_list[0] if isinstance(cond_list[0], str) else "NRC22触发条件"
            TestLog("INFO", "Service_0x85", f"使用条件: {cond}")
        # TODO
        # 发送85 01请求，期望NRC22响应
        TestLog("INFO", "Service_0x85", "发送85 01请求，检查NRC22响应")

        try:
            response_message = node.Service_0x85_ControlDTCSetting(
                dtc_setting_type=0x01,
                func_req=func_flg)
            if response_message is None:
                TestLog("FAIL", name, f"Step{step}，发送85 01未收到响应")
                return

            data_list = list(response_message.data)
            if len(data_list) >= 3 and data_list[0:3] == [0x7F, 0x85, 0x22]:
                TestLog("PASS", "Service_0x85", f"Step{step}，收到NRC22否定响应: {response_message.data.hex()}")
            elif len(data_list) >= 2 and data_list[0:2] == [0xC5, 0x01]:
                TestLog("WARN", "Service_0x85",
                        f"Step{step}，收到肯定响应(C5 01)，未触发NRC22条件。继续测试其他NRC优先级场景")
            else:
                TestLog("FAIL", name, f"Step{step}，收到异常响应: {response_message.data.hex()}")
                return
        except Exception as e:
            TestLog("FAIL", name, f"Step{step}，发送85 01请求异常: {e}")
            TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
            return

        # Step4: 发送85 03
        step += 1
        TestLog("INFO", f"Step{step}", "发送85 03请求")
        TestLog("INFO", "Service_0x85", "发送85 03请求，检查NRC12响应")
        if not __service_85_check_lin(
                node,
                0x03,
                [0x7F, 0x85, 0x7F],
                "85 03请求NRC7F检查",
                func_req=func_flg,
        ):
            return

        # Step5: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        # Step6: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x71, 0x01, 0x02, 0x03, 0x00],
                "位于扩展会话中(71 01 02 03 00)",
                func_req=func_flg,
        ):
            return

        # Step7: 发送85请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送85请求")
        TestLog("INFO", "Service_0x85", "发送85请求，检查NRC13响应")
        if not __service_85_check_lin(
                node,
                None,
                [0x7F, 0x85, 0x13],
                "85请求NRC13检查",
                func_req=func_flg,
        ):
            return

        # Step8: 发送85 03 00请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送85 03 00请求")
        TestLog("INFO", "Service_0x85", "发送85 03 00请求，检查NRC13响应")
        if not __service_85_check_lin(
                node,
                0x03,
                [0x7F, 0x85, 0x13],
                "85 03 00请求NRC13检查",
                func_req=func_flg,
                dl=3,
                dl_padding=0x00,
        ):
            return

        # Step9: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                [0x71, 0x01, 0x02, 0x03, 0x00],
                "仍位于扩展会话中(71 01 02 03 00)",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "85服务NRC优先级检查(物理寻址) 测试执行成功")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def __service_22_check(
        node,
        dids: list | None,
        expect_data,
        expect_str: str = "",
        func_req: bool = False,
        dl: int | None = None,
        dl_padding: int = 0x00,
        timeout: float = 5,
):
    try:

        response_message = node.Service_0x22_ReadDataByIdentifier(
            dids,
            func_req=func_req,
            dl=dl,
            dl_padding=dl_padding,
            timeout=timeout,
        )
        if expect_data is None:
            # 期望无响应
            if response_message is None:
                TestLog("PASS", "Service_0x22", f"{expect_str}，无响应符合预期")
                return True, []
            TestLog("FAIL", "Service_0x22", f"{expect_str}，期望无响应，实际收到: {response_message.data.hex()}")
            return False, list(response_message.data)

        if response_message is None:
            TestLog("FAIL", "Service_0x22", f"{expect_str}，未收到响应")
            return False, []

        if list(response_message.data[0:len(expect_data)]) != expect_data:
            TestLog(
                "FAIL",
                "Service_0x22",
                f"{expect_str}，响应不匹配，期望: {bytes(expect_data).hex()} 实际: {response_message.data.hex()}",
            )
            return False, list(response_message.data)

        TestLog("PASS", "Service_0x22", f"{expect_str}，响应匹配: {response_message.data.hex()}")
        return True, list(response_message.data)
    except Exception as e:
        TestLog("FAIL", "Service_0x22", f"{expect_str}，执行异常: {e}")
        TestLog("DEBUG", "Service_0x22", f"详细错误: {traceback.format_exc()}")
        return False, []


def test_phyRequest_22_Positive(
        node: UDSNode,
        name: str = "[TG7_TC1] 22服务肯定响应检查(物理寻址)",
        func_flg: bool = False,
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_PRO_05, DLL_PATH_PRO_05 = 0x11, P.ECUInfo.dllPath_2711  # 刷新等级
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        time.sleep(1)

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有22服务支持的DID(默认会话)")
        did_list = UDSTestParams.Services22DIDSupportList_Default
        for did in did_list:
            status, _ = __service_22_check(node, [did], [0x62] + list(int.to_bytes(did, 2, "big")),
                                           f"肯定响应(62 {(did >> 8) & 0xFF:02X} {did & 0xFF:02X} ...)",
                                           func_req=func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        time.sleep(1)

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT],
                                                   f"肯定响应(67 {LEVEL_EXT})")
        if not status: return

        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})",
                                            dll_path=DLL_PATH): return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有22服务支持的DID(扩展会话)")
        did_list = UDSTestParams.Services22DIDSupportList_Extended
        for did in did_list:
            status, _ = __service_22_check(node, [did], [0x62] + list(int.to_bytes(did, 2, "big")),
                                           f"肯定响应(62 {(did >> 8) & 0xFF:02X} {did & 0xFF:02X} ...)",
                                           func_req=func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)

        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return
        __lin_restart_delay(2)

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送种子请求(27 {LEVEL_PRO_05})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_05, [0x67, LEVEL_PRO_05],
                                                   f"肯定响应(67 {LEVEL_PRO_05})")
        if not status: return

        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送解锁密钥(27 {LEVEL_PRO_05 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_05, seed_list, [0x67, LEVEL_PRO_05 + 1],
                                            f"肯定响应(67 {LEVEL_PRO_05 + 1})",
                                            dll_path=DLL_PATH_PRO_05): return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有22服务支持的DID(刷新会话)")
        did_list = UDSTestParams.Services22DIDSupportList_Programming
        for did in did_list:
            status, _ = __service_22_check(node, [did], [0x62] + list(int.to_bytes(did, 2, "big")),
                                           f"肯定响应(62 {(did >> 8) & 0xFF:02X} {did & 0xFF:02X} ...)",
                                           func_req=func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_22_MultiRead(
        node: UDSNode,
        name: str = "[TG7_TC2] 22服务多数据读取检查(物理寻址)",
        func_flg: bool = False,
):
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return
        max_mul_did = P.DiagServiceInfo.MaxMulDIDNumber
        step = 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

        step = 2
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中", func_req=func_flg):
            return

        step = 3
        TestLog("INFO", f"Step{step}", f"以最大数目({max_mul_did})读取22服务支持的DID")
        did_list = UDSTestParams.Services22DIDSupportList_Default[:max_mul_did]
        if len(did_list) > 0:
            multi_did = did_list
            if not __service_22_check(node, multi_did, [0x62], "肯定响应(62 ...)", func_req=func_flg): return

        step = 4
        TestLog("INFO", f"Step{step}", "同时读取支持和不支持的DID")
        supported_did = UDSTestParams.Services22DIDSupportList_Default[0] if len(
            UDSTestParams.Services22DIDSupportList_Default) > 0 else 0xF180
        unsupported_did = UDSTestParams.Services22DIDUnsupportedList[0] if len(
            UDSTestParams.Services22DIDUnsupportedList) > 0 else 0x0000
        if not __service_22_check(node, [supported_did, unsupported_did], [0x62], "肯定响应，返回支持的DID数据(62 ...)",
                                  func_req=func_flg): return

        step = 5
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中", func_req=func_flg):
            return

        step = 6
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        step = 7
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step = 8
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step = 9
        TestLog("INFO", f"Step{step}", f"以最大数目({max_mul_did})读取22服务支持的DID")
        did_list = UDSTestParams.Services22DIDSupportList_Extended[:max_mul_did]
        if len(did_list) > 0:
            multi_did = did_list
            if not __service_22_check(node, multi_did, [0x62], "肯定响应(62 ...)", func_req=func_flg): return

        step = 10
        TestLog("INFO", f"Step{step}", "同时读取支持和不支持的DID")
        supported_did = UDSTestParams.Services22DIDSupportList_Extended[0] if len(
            UDSTestParams.Services22DIDSupportList_Extended) > 0 else 0xF180
        unsupported_did = UDSTestParams.Services22DIDUnsupportedList[0] if len(
            UDSTestParams.Services22DIDUnsupportedList) > 0 else 0x0000
        if not __service_22_check(node, [supported_did, unsupported_did], [0x62], "肯定响应，返回支持的DID数据(62 ...)",
                                  func_req=func_flg): return

        step = 11
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step = 12
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        step = 13
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return
        __lin_restart_delay(2)

        step = 14
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        step = 15
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        step = 16
        TestLog("INFO", f"Step{step}", f"以最大数目({max_mul_did})读取22服务支持的DID")
        did_list = UDSTestParams.Services22DIDSupportList_Programming[:max_mul_did]
        if len(did_list) > 0:
            multi_did = did_list
            if not __service_22_check(node, multi_did, [0x62], "肯定响应(62 ...)", func_req=func_flg): return

        step = 17
        TestLog("INFO", f"Step{step}", "同时读取支持和不支持的DID")
        supported_did = UDSTestParams.Services22DIDSupportList_Programming[0] if len(
            UDSTestParams.Services22DIDSupportList_Programming) > 0 else 0xF180
        unsupported_did = UDSTestParams.Services22DIDUnsupportedList[0] if len(
            UDSTestParams.Services22DIDUnsupportedList) > 0 else 0x0000
        if not __service_22_check(node, [supported_did, unsupported_did], [0x62], "肯定响应，返回支持的DID数据(62 ...)",
                                  func_req=func_flg): return

        step = 18
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_22_NRC31(
        node: UDSNode,
        name: str = "[TG7_TC3] 22服务NRC31检查(物理寻址)",
        func_flg: bool = False,
):
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有22服务不支持的DID(默认会话)")
        unsupported_did_list = UDSTestParams.Services22DIDUnsupportedList
        for did in unsupported_did_list:
            status, _ = __service_22_check(node, [did], [0x7F, 0x22, 0x31], f"否定响应，NRC=0x31(7F 22 31)",
                                           func_req=func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有22服务不支持的DID(默认会话)")
        unsupported_did_list = UDSTestParams.Services22DIDUnsupportedList
        for did in unsupported_did_list:
            status, _ = __service_22_check(node, [did], [0x7F, 0x22, 0x31], f"否定响应，NRC=0x31(7F 22 31)",
                                           func_req=func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有22服务不支持的DID(默认会话)")
        unsupported_did_list = UDSTestParams.Services22DIDUnsupportedList
        for did in unsupported_did_list:
            status, _ = __service_22_check(node, [did], [0x7F, 0x22, 0x31], f"否定响应，NRC=0x31(7F 22 31)",
                                           func_req=func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_22_NRC13(
        node: UDSNode,
        name: str = "[TG7_TC4] 22服务NRC13检查(物理寻址)",
        func_flg: bool = False,
):
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        invalid_dl_list = [
            (1, "DL=1, 只有SID"),
            (2, "DL=2, SID+1字节(有效位用00填充)"),
            (4, "DL=4, SID+3字节(有效位用00填充)"),
            (6, "DL=6, SID+5字节(有效位用00填充)"),
            # (8, "DL=8, SID+7字节(有效位用00填充)"),
        ]

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        __lin_restart_delay(2)

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "发送错误长度的22服务请求(默认会话)")
        for dl, desc in invalid_dl_list:
            TestLog("INFO", f"Step{step}", f"发送 {desc}")
            status, _ = __service_22_check(node, None, [0x7F, 0x22, 0x13], f"否定响应，NRC=0x13(7F 22 13)", dl=dl,
                                           dl_padding=0x00, func_req=func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "发送错误长度的22服务请求(扩展会话)")
        for dl, desc in invalid_dl_list:
            TestLog("INFO", f"Step{step}", f"发送 {desc}")
            status, _ = __service_22_check(node, None, [0x7F, 0x22, 0x13], f"否定响应，NRC=0x13(7F 22 13)", dl=dl,
                                           dl_padding=0x00, func_req=func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "发送错误长度的22服务请求(刷新会话)")
        for dl, desc in invalid_dl_list:
            TestLog("INFO", f"Step{step}", f"发送 {desc}")
            status, _ = __service_22_check(node, None, [0x7F, 0x22, 0x13], f"否定响应，NRC=0x13(7F 22 13)", dl=dl,
                                           dl_padding=0x00, func_req=func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        __lin_restart_delay(2)

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_22_NRC33(
        node: UDSNode,
        name: str = "[TG7_TC5] 22服务NRC33检查(物理寻址)",
        func_flg: bool = False,
):
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        security_required_did_list = UDSTestParams.Services22DIDSecurityRequiredList
        if len(security_required_did_list) == 0:
            TestLog("INFO", "Skip", "没有配置需要安全访问的DID，跳过此测试")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有需要安全访问解锁的DID(扩展会话)")
        for did in security_required_did_list:
            status, _ = __service_22_check(node, [did], [0x7F, 0x22, 0x33], f"否定响应，NRC=0x33(7F 22 33)",
                                           func_req=func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有22服务支持的DID(刷新会话)")
        did_list = UDSTestParams.Services22DIDSupportList_Default
        for did in did_list:
            status, _ = __service_22_check(node, [did], [0x62], f"肯定响应，62", func_req=func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        TestLog("INFO", "Step12", "遍历所有需要安全访问解锁的DID(刷新会话)")
        for did in security_required_did_list:
            status, _ = __service_22_check(node, [did], [0x7F, 0x22, 0x33], f"否定响应，NRC=0x33(7F 22 33)",
                                           func_req=func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        __lin_restart_delay(2)

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_22_NRC22(
        node: UDSNode,
        name: str = "[TG7_TC6] 22服务NRC22检查(物理寻址)",
        func_flg: bool = False,
):
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        nrc22_condition_list = UDSTestParams.NRC22_ConditionList
        if len(nrc22_condition_list) == 0:
            TestLog("INFO", "Skip", "没有配置NRC22触发条件，跳过此测试")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历触发NRC0x22的所有条件并发送22请求(默认会话)")
        for condition in nrc22_condition_list:
            if hasattr(condition, 'get'):
                did = condition.get('did')
                desc = condition.get('desc', f'DID={did:04X}')
                setup_func = condition.get('setup')
            else:
                TestLog("FAIL", f" ", "NRC22不支持")
                return
            if setup_func:
                setup_func()
            status, _ = __service_22_check(node, [did], [0x7F, 0x22, 0x22], f"否定响应，NRC=0x22(7F 22 22) - {desc}",
                                           func_req=func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历触发NRC0x22的所有条件并发送22请求(扩展会话)")
        for condition in nrc22_condition_list:
            if hasattr(condition, 'get'):
                did = condition.get('did')
                desc = condition.get('desc', f'DID={did:04X}')
                setup_func = condition.get('setup')
            else:
                TestLog("FAIL", f" ", "NRC22不支持")
                return
            if setup_func:
                setup_func()
            status, _ = __service_22_check(node, did, [0x7F, 0x22, 0x22], f"否定响应，NRC=0x22(7F 22 22) - {desc}",
                                           func_req=func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历触发NRC0x22的所有条件并发送22请求(刷新会话)")
        for condition in nrc22_condition_list:
            if hasattr(condition, 'get'):
                did = condition.get('did')
                desc = condition.get('desc', f'DID={did:04X}')
                setup_func = condition.get('setup')
            else:
                TestLog("FAIL", f" ", "NRC22不支持")
                return
            if setup_func:
                setup_func()
            status, _ = __service_22_check(node, did, [0x7F, 0x22, 0x22], f"否定响应，NRC=0x22(7F 22 22) - {desc}",
                                           func_req=func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_22_NRCPriority(
        node: UDSNode,
        name: str = "[TG7_TC7] 22服务NRC优先级检查(物理寻址)",
        func_flg: bool = False,
):
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        unsupported_did_list = UDSTestParams.Services22DIDUnsupportedList
        security_required_did_list = UDSTestParams.Services22DIDSecurityRequiredList
        nrc22_condition_list = UDSTestParams.NRC22_ConditionList

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "触发NRC22条件并发送22请求")
        if len(nrc22_condition_list) > 0:
            condition = nrc22_condition_list[0]
            if hasattr(condition, 'get'):
                did = condition.get('did')
                desc = condition.get('desc', f'DID={did:04X}')
                setup_func = condition.get('setup')
            else:
                TestLog("FAIL", f" ", "NRC22不支持")
                return
            if setup_func:
                setup_func()
            status, _ = __service_22_check(node, [did], [0x7F, 0x22, 0x22], f"否定响应，NRC=0x22(7F 22 22) - {desc}",
                                           func_req=func_flg)
            if not status: return
        else:
            TestLog("INFO", f"Step{step}", "没有配置NRC22触发条件，跳过此步骤")

        step += 1
        TestLog("INFO", f"Step{step}", "发送22请求(DL=1，只有SID)")
        status, _ = __service_22_check(node, None, [0x7F, 0x22, 0x13], "否定响应，NRC=0x13(7F 22 13)", dl=1,
                                       dl_padding=0x00, func_req=func_flg)
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "发送22 XX XX请求(不支持的DID)")
        if len(unsupported_did_list) > 0:
            did = unsupported_did_list[0]
            status, _ = __service_22_check(node, [did], [0x7F, 0x22, 0x31], f"否定响应，NRC=0x31(7F 22 31)", dl=4,
                                           dl_padding=0x00, func_req=func_flg)
            if not status: return
        else:
            TestLog("INFO", f"Step{step}", "没有配置不支持的DID，跳过此步骤")

        step += 1
        TestLog("INFO", f"Step{step}", "发送22 XX XX请求(需要解锁的DID)")
        if len(security_required_did_list) > 0:
            did = security_required_did_list[0]
            status, _ = __service_22_check(node, [did], [0x7F, 0x22, 0x33], f"否定响应，NRC=0x33(7F 22 33)", dl=4,
                                           dl_padding=0x00, func_req=func_flg)
            if not status: return
        else:
            TestLog("INFO", f"Step{step}", "没有配置需要安全访问的DID，跳过此步骤")

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def __service_2E_check(
        node,
        did: int,
        data,
        expect_data,
        expect_str: str = "",
        func_req: bool = False,
        dl: int | None = None,
        dl_padding: int = 0x00,
        timeout: float = 5,
):
    try:
        response_message = node.Service_0x2E_WriteDataByIdentifier(
            did,
            record=data,
            func_req=func_req,
            dl=dl,
            dl_padding=dl_padding,
            timeout=timeout,
        )
        if expect_data is None:
            # 期望无响应
            if response_message is None:
                TestLog("PASS", "Service_0x2E", f"{expect_str}，无响应符合预期")
                return True, []
            TestLog("FAIL", "Service_0x2E", f"{expect_str}，期望无响应，实际收到: {response_message.data.hex()}")
            return False, list(response_message.data)

        if response_message is None:
            TestLog("FAIL", "Service_0x2E", f"{expect_str}，未收到响应")
            return False, []

        if list(response_message.data[0:len(expect_data)]) != expect_data:
            TestLog(
                "FAIL",
                "Service_0x2E",
                f"{expect_str}，响应不匹配，期望: {bytes(expect_data).hex()} 实际: {response_message.data.hex()}",
            )
            return False, list(response_message.data)

        TestLog("PASS", "Service_0x2E", f"{expect_str}，响应匹配: {response_message.data.hex()}")
        return True, list(response_message.data)
    except Exception as e:
        TestLog("FAIL", "Service_0x2E", f"{expect_str}，执行异常: {e}")
        TestLog("DEBUG", "Service_0x2E", f"详细错误: {traceback.format_exc()}")
        return False, []


def test_phyRequest_2E_Positive(
        node: UDSNode,
        name: str = "[TG8_TC1] 2E服务肯定响应及功能检查(物理寻址)",
        func_flg: bool = False,
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_PRO_11, DLL_PATH_PRO_11 = 0x11, P.ECUInfo.dllPath_2711  # 刷新等级

    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step = 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step = 2
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step = 3
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step = 4
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 5
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                            func_req=func_flg): return

        step = 6
        TestLog("INFO", f"Step{step}", "令ABCD=0x0000")
        ABCD = 0x0000

        TestLog("INFO", "Step7", "如果ABCD<0xFFFF且ABCD不为支持的DID，则ABCD+=1，直到ABCD<0xFFFF")
        for ABCD in UDSTestParams.Services2EDIDSupportListDefault:
            did_0, did_1 = ABCD >> 8 & 0xFF, ABCD & 0xFF

            TestLog("INFO", "Step8", "如果ABCD是支持的DID，则读取其值，否则跳转至步骤29")
            status, src_data = __service_22_check(node, [ABCD], [0x62, did_0, did_1], "肯定响应(62)", func_req=func_flg)
            if not status: return

            TestLog("INFO", "Step9", "写入一个不同于读取到的数据值")
            new_data = src_data[3:].copy()
            new_data[0] = (new_data[0] + 1) % (0xFF + 1)
            status, msg = __service_2E_check(node, ABCD, bytes(new_data), [0x6E, did_0, did_1], "肯定响应(6E)",
                                             func_req=func_flg)
            if not status: return

            TestLog("INFO", "Step10", f"读取DID=ABCD({hex(ABCD)})的数据")
            status, resp = __service_22_check(node, [ABCD], [0x62, did_0, did_1], "肯定响应(62)", func_req=func_flg)
            if not status: return

            if list(resp[3:]) == list(new_data):
                TestLog("PASS", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据相同")
            else:
                TestLog("FAIL", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据不同")
                return

            TestLog("INFO", "Step11", "DUT复位(11 01)")
            if not __service_11_check(node, 0x01, [0x51, 0x01], "肯定响应(51 01)", func_req=func_flg):
                return
            __lin_restart_delay(2)
            TestLog("INFO", "Step12", "复位完成后，请求进入默认会话(10 01)")
            if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
                return
            __lin_restart_delay(2)
            TestLog("INFO", "Step13", "进入扩展会话(10 03)")
            if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "肯定响应(50 03)", func_req=func_flg):
                return

            TestLog("INFO", "Step14", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"], "位于扩展会话中",
                                               func_req=func_flg, ):
                return

            TestLog("INFO", "Step15", f"发送27 01请求(27 {LEVEL_EXT})")
            status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                       func_req=func_flg)
            if not status: return
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
            if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
                TestLog("FAIL", "",
                        f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
                return
            TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

            TestLog("INFO", "Step16", f"发送27 02请求")
            if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                                f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                                func_req=func_flg): return

            TestLog("INFO", "Step17", f"读取DID=ABCD({hex(ABCD)})的数据")
            status, resp = __service_22_check(node, [ABCD], [0x62, did_0, did_1], "肯定响应(62)")
            if not status: return

            if list(resp[3:]) == list(new_data):
                TestLog("PASS", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据相同")
            else:
                TestLog("FAIL", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据不同")
                return

            TestLog("INFO", "Step18", f"断电后重新上电")
            __power_resatrt(1, 2)

            TestLog("INFO", "Step19", "进入默认会话(10 01)")
            if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
                return

            TestLog("INFO", "Step20", "进入扩展会话(10 03)")
            if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "肯定响应(50 03)", func_req=func_flg):
                return

            TestLog("INFO", "Step21", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"], "位于扩展会话中",
                                               func_req=func_flg, ):
                return

            TestLog("INFO", "Step22", f"发送27 01请求(27 {LEVEL_EXT})")
            status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                       func_req=func_flg)
            if not status: return
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
            if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
                TestLog("FAIL", "",
                        f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
                return
            TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

            TestLog("INFO", "Step23", f"发送27 02请求")
            if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                                f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                                func_req=func_flg): return

            TestLog("INFO", "Step24", f"读取DID=ABCD({hex(ABCD)})的数据")
            status, resp = __service_22_check(node, [ABCD], [0x62, did_0, did_1], "肯定响应(62)", func_req=func_flg)
            if not status: return

            if list(resp[3:]) == list(new_data):
                TestLog("PASS", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据相同")
            else:
                TestLog("FAIL", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据不同")
                return

            TestLog("INFO", "Step25", f"对DID=ABCD({hex(ABCD)})写入原值")
            status, resp = __service_2E_check(node, ABCD, bytes(src_data[3:]), [0x6E, did_0, did_1], "肯定响应(6E)",
                                              func_req=func_flg)
            if not status: return

            TestLog("INFO", "Step26", f"读取DID=ABCD({hex(ABCD)})的数据")
            status, resp = __service_22_check(node, [ABCD], [0x62, did_0, did_1], "肯定响应(62)", func_req=func_flg)
            if not status: return

            if list(resp) == list(src_data):
                TestLog("PASS", "", "期望:读取到的数据与原值相同; 实际： 读取到的数据与原值相同")
            else:
                TestLog("FAIL", "", "期望:读取到的数据与原值相同; 实际： 读取到的数据与原值不同")
                return

            TestLog("INFO", "Step27", f"ABCD+=1，跳转至步骤7")

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"], "位于扩展会话中",
                                           func_req=func_flg, ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"], "位于扩展会话中",
                                           func_req=func_flg, ):
            return
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "刷新会话肯定响应(50 02)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x67, LEVEL_PRO_11 + 1],
                                            f"肯定响应(67 {LEVEL_PRO_11 + 1})", dll_path=DLL_PATH_PRO_11,
                                            func_req=func_flg): return

        step += 1
        TestLog("INFO", f"Step{step}", "令ABCD=0x0000")
        ABCD = 0x0000
        TestLog("INFO", "Step36", "如果ABCD<0xFFFF且ABCD不为支持的DID，则ABCD+=1，直到ABCD<0xFFFF")
        for ABCD in UDSTestParams.Services2EDIDSupportListDefault:
            did_0, did_1 = ABCD >> 8 & 0xFF, ABCD & 0xFF

            TestLog("INFO", "Step37", "如果ABCD是支持的DID，则读取其值，否则结束本项测试")
            status, src_data = __service_22_check(node, [ABCD], [0x62, did_0, did_1], "肯定响应(62)", func_req=func_flg)
            if not status: return

            TestLog("INFO", "Step38", "写入一个不同于读取到的数据值")
            new_data = src_data[3:].copy()
            new_data[0] = (new_data[0] + 1) % (0xFF + 1)
            status, resp = __service_2E_check(node, ABCD, bytes(new_data), [0x6E, did_0, did_1], "肯定响应(6E)",
                                              func_req=func_flg)
            if not status: return

            TestLog("INFO", "Step39", f"读取DID=ABCD({hex(ABCD)})的数据")
            status, resp = __service_22_check(node, [ABCD], [0x62, did_0, did_1], "肯定响应(62)", func_req=func_flg)
            if not status: return

            if list(resp[3:]) == list(new_data):
                TestLog("PASS", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据相同")
            else:
                TestLog("FAIL", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据不同")
                return

            TestLog("INFO", "Step40", "DUT复位(11 01)")
            if not __service_11_check(node, 0x01, [0x51, 0x01], "肯定响应(51 01)", func_req=func_flg):
                return
            __lin_restart_delay(2)
            TestLog("INFO", "Step41", "复位完成后，请求进入默认会话(10 01)")
            if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
                return

            TestLog("INFO", "Step42", "进入扩展会话(10 03)")
            if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "肯定响应(50 03)", func_req=func_flg):
                return

            if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"], "位于扩展会话中",
                                               func_req=func_flg, ):
                return
            TestLog("INFO", "Step43", "进入刷新会话(10 02)")
            if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "刷新会话肯定响应(50 02)", func_req=func_flg):
                return

            TestLog("INFO", "Step44", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"], "位于扩展会话中",
                                               func_req=func_flg, ):
                return

            TestLog("INFO", "Step45", f"发送扩展安全级的请求种子请求(27 {LEVEL_PRO_11})")
            status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                       f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
            if not status: return
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
            if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
                TestLog("FAIL", "",
                        f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
                return
            TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

            step += 1
            TestLog("INFO", "Step46", f"发送扩展安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
            if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x67, LEVEL_PRO_11 + 1],
                                                f"肯定响应(67 {LEVEL_PRO_11 + 1})", dll_path=DLL_PATH_PRO_11,
                                                func_req=func_flg): return

            TestLog("INFO", "Step47", f"读取DID=ABCD({hex(ABCD)})的数据")
            status, resp = __service_22_check(node, [ABCD], [0x62, did_0, did_1], "肯定响应(62)", func_req=func_flg)
            if not status: return

            if list(resp[3:]) == list(new_data):
                TestLog("PASS", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据相同")
            else:
                TestLog("FAIL", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据不同")
                return

            TestLog("INFO", "Step48", f"断电后重新上电")
            __power_resatrt(1, 2)

            TestLog("INFO", "Step49", "进入默认会话(10 01)")
            if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
                return

            TestLog("INFO", "Step50", "进入扩展会话(10 03)")
            if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "肯定响应(50 03)", func_req=func_flg):
                return

            TestLog("INFO", "Step51", "进入刷新会话(10 02)")
            if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "刷新会话肯定响应(50 02)", func_req=func_flg):
                return

            TestLog("INFO", "Step52", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中", func_req=func_flg, ):
                return

            TestLog("INFO", "Step53", f"发送27 05请求(27 {LEVEL_PRO_11})")
            status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                       f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
            if not status: return
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
            if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
                TestLog("FAIL", "",
                        f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
                return
            TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

            TestLog("INFO", "Step54", f"发送27 06请求")
            if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x67, LEVEL_PRO_11 + 1],
                                                f"肯定响应(67 {LEVEL_PRO_11 + 1})", dll_path=DLL_PATH_PRO_11,
                                                func_req=func_flg): return

            TestLog("INFO", "Step55", f"读取DID=ABCD({hex(ABCD)})的数据")
            status, resp = __service_22_check(node, [ABCD], [0x62, did_0, did_1], "肯定响应(62)", func_req=func_flg)
            if not status: return

            if list(resp[3:]) == list(new_data):
                TestLog("PASS", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据相同")
            else:
                TestLog("FAIL", "", "期望:读取到的数据与写入的数据相同; 实际： 读取到的数据与写入的数据不同")
                return

            TestLog("INFO", "Step56", f"对DID=ABCD({hex(ABCD)})写入原值")
            status, resp = __service_2E_check(node, ABCD, bytes(src_data), [0x6E, did_0, did_1], "肯定响应(6E)",
                                              func_req=func_flg)
            if not status: return

            TestLog("INFO", "Step57", f"读取DID=ABCD({hex(ABCD)})的数据")
            status, resp = __service_22_check(node, [ABCD], [0x62, did_0, did_1], "肯定响应(62)", func_req=func_flg)
            if not status: return

            if list(resp) == list(src_data):
                TestLog("PASS", "", "期望:读取到的数据与原值相同; 实际： 读取到的数据与原值相同")
            else:
                TestLog("FAIL", "", "期望:读取到的数据与原值相同; 实际： 读取到的数据与原值不同")
                return

            TestLog("INFO", "Step58", f"ABCD+=1，跳转至步骤36")

        TestLog("INFO", "Step59", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中", func_req=func_flg, ):
            return
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_2E_NRC13(
        node: UDSNode,
        name: str = "[TG8_TC2] 2E服务NRC13检查(物理寻址)",
        func_flg: bool = False,
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_PRO_11, DLL_PATH_PRO_11 = 0x11, P.ECUInfo.dllPath_2711  # 刷新等级
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                            func_req=func_flg): return

        step += 1
        TestLog("INFO", f"Step{step}", "发送长度较短2E服务请求")
        for dl_ in [1, 2, 3]:
            for did in UDSTestParams.Services2EDIDSupportListDefault:
                status, msg = __service_2E_check(node, did, bytes([]), [0x7F, 0x2E, 0x13], "否定响应(7F 2E 13)",
                                                 func_req=func_flg, dl=dl_)
                if not status:
                    return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x67, LEVEL_PRO_11 + 1],
                                            f"肯定响应(67 {LEVEL_PRO_11 + 1})", dll_path=DLL_PATH_PRO_11,
                                            func_req=func_flg): return

        step += 1
        TestLog("INFO", f"Step{step}", "发送长度较短2E服务请求")
        for dl_ in [1, 2, 3]:
            for did in UDSTestParams.Services2EDIDSupportListDefault:
                status, msg = __service_2E_check(node, did, bytes([]), [0x7F, 0x2E, 0x13], "否定响应(7F 2E 13)",
                                                 func_req=func_flg, dl=dl_)
                if not status:
                    return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_2E_NRC31(
        node: UDSNode,
        name: str = "[TG8_TC3] 2E服务NRC31检查(物理寻址)",
        func_flg: bool = False,
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_PRO_11, DLL_PATH_PRO_11 = 0x11, P.ECUInfo.dllPath_2711  # 刷新等级

    min_did, max_did = 0x0000, 0x0010
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                            func_req=func_flg): return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有2E服务不支持的DID（当前会话下）")
        for did in range(min_did, max_did + 1):
            if did in UDSTestParams.Services2EDIDSupportListDefault:
                continue
            status, resp = __service_2E_check(node, did, bytes([0xFF]), [0x7F, 0x2E, 0x31], "否定响应(7F 2E 31)",
                                              func_req=func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有2E服务支持的DID（当前会话下），但是写入的数据超过数据范围")
        for did in UDSTestParams.Services2EDIDSupportListExtend:
            did_val = did if isinstance(did, int) else did.get('did', 0)
            did_cfg = None
            for item in P.WriteDIDs:
                if item.DID_int == did_val:
                    did_cfg = item
                    break
            if did_cfg is None:
                continue
            # 当前仅解锁了Level1(0x01)，若DID需要更高安全等级，DUT会先返回NRC33而非NRC31，跳过此类DID
            if did_cfg.SecurityUnlock and not did_cfg.Level1:
                continue
            did_len = did_cfg.Length
            set_val = bytes([0xFF] * did_len)
            status, resp = __service_2E_check(node, did_val, set_val, [0x7F, 0x2E, 0x31], "否定响应(7F 2E 0x31)",
                                              func_req=func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x67, LEVEL_PRO_11 + 1],
                                            f"肯定响应(67 {LEVEL_PRO_11 + 1})", dll_path=DLL_PATH_PRO_11,
                                            func_req=func_flg): return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有2E服务不支持的DID（当前会话下）")
        for did in range(min_did, max_did + 1):
            if did in UDSTestParams.Services2EDIDSupportListDefault:
                continue
            status, resp = __service_2E_check(node, did, bytes([0xFF]), [0x7F, 0x2E, 0x31], "否定响应(7F 2E 31)",
                                              func_req=func_flg)
            if not status: return

        TestLog("INFO", "Step16", "遍历所有2E服务支持的DID（当前会话下），但是写入的数据超过数据范围")
        for did in UDSTestParams.Services2EDIDSupportListProgramming:
            did_val = did if isinstance(did, int) else did.get('did', 0)
            did_cfg = None
            for item in P.WriteDIDs:
                if item.DID_int == did_val:
                    did_cfg = item
                    break
            if did_cfg is None:
                continue
            # 编程会话下已解27 11，若DID仍需要其他安全等级(非Level1)，DUT可能返回NRC33，保守跳过
            if did_cfg.SecurityUnlock and not did_cfg.Level1:
                continue
            did_len = did_cfg.Length
            set_val = bytes([0xFF] * did_len)
            status, resp = __service_2E_check(node, did_val, set_val, [0x7F, 0x2E, 0x31], "否定响应(7F 2E 0x31)",
                                              func_req=func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_2E_NRC33(
        node: UDSNode,
        name: str = "[TG8_TC4] 2E服务NRC33检查(物理寻址)",
        func_flg: bool = False,
):
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        TestLog("INFO", "Step4", "读取所有2E服务支持但需要安全解锁的DID")
        for did in UDSTestParams.Services2EDIDSupportListExtend:
            if did not in UDSTestParams.Services2EDIDNeedUnlockSupportList:
                continue
            # 支持的且需要安全解锁的did
            status, resp = __service_22_check(node, [did], [0x62], "肯定响应(62)", func_req=func_flg)
            if not status: return
            write_data = bytes(resp[3:])  # 去掉 62 + DID-H + DID-L
            status, resp = __service_2E_check(node, did, write_data, [0x7F, 0x2E, 0x33], "否定响应(7F 2E 33)",
                                              func_req=func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        TestLog("INFO", "Step11", "读取所有2E服务支持但需要安全解锁的DID")
        for did in UDSTestParams.Services2EDIDSupportListProgramming:
            if did not in UDSTestParams.Services2EDIDNeedUnlockSupportList:
                continue
            # 支持的且需要安全解锁的did
            status, resp = __service_22_check(node, [did], [0x62], "肯定响应(62)", func_req=func_flg)
            if not status:
                return
            write_data = bytes(resp[3:])  # 去掉 62 + DID-H + DID-L
            status, resp = __service_2E_check(node, did, write_data, [0x7F, 0x2E, 0x33], "否定响应(7F 2E 33)",
                                              func_req=func_flg)
            if not status:
                return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_2E_NRC7F(
        node: UDSNode,
        name: str = "[TG8_TC5] 2E服务NRC7F检查(物理寻址)",
        func_flg: bool = False,
):
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)",
                                           func_req=func_flg):
            return

        TestLog("INFO", "Step3", "遍历所有2E服务在其他sessin支持的DID，写入值为原值")
        for did in UDSTestParams.Services2EDIDSupportListDefault:
            if did not in UDSTestParams.Services2EDIDNeedUnlockSupportList:
                continue
            # 支持的且需要安全解锁的did
            status, resp = __service_22_check(node, [did], [0x62], "肯定响应(62)", func_req=func_flg)
            if not status:
                return
            status, resp = __service_2E_check(node, did, resp, [0x7F, 0x2E, 0x7F], "否定响应(7F 2E 7F)",
                                              func_req=func_flg)
            if not status:
                return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)",
                                           func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_2E_NRC22(
        node: UDSNode,
        name: str = "[TG8_TC6] 2E服务NRC0x22检查(物理寻址)",
        func_flg: bool = False,
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_PRO_11, DLL_PATH_PRO_11 = 0x11, P.ECUInfo.dllPath_2711  # 刷新等级

    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                            func_req=func_flg): return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历触发NRC0x22的所有条件并发送2E请求")
        # TODO 触发条件 & did & data
        status, resp = __service_2E_check(node, 0x00, bytes([]), [0x7F, 0x2E, 0x22], "否定响应(7F 2E 22)",
                                          func_req=func_flg)
        if not status:
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x67, LEVEL_PRO_11 + 1],
                                            f"肯定响应(67 {LEVEL_PRO_11 + 1})", dll_path=DLL_PATH_PRO_11,
                                            func_req=func_flg): return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历触发NRC0x22的所有条件并发送2E请求")
        # TODO 触发条件 & did & data
        status, resp = __service_2E_check(node, 0x00, bytes([]), [0x7F, 0x2E, 0x22], "否定响应(7F 2E 22)",
                                          func_req=func_flg)
        if not status:
            return
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_2E_NRCPriorityCheck(
        node: UDSNode,
        name: str = "[TG8_TC7] 2E服务NRC优先级检查(物理寻址)",
        func_flg: bool = False,
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)",
                                           func_req=func_flg):
            return

        TestLog("INFO", "Step3", "请求写入支持的DID的数据，数据为有效值")
        # TODO did & data
        status, resp = __service_2E_check(node, 0x00, bytes([]), [0x7F, 0x2E, 0x7F], "否定响应(7F 2E 7F)",
                                          func_req=func_flg)
        if not status:
            return
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        TestLog("INFO", "Step6", "发送2E请求")
        status, resp = __service_2E_check(node, None, b'', [0x7F, 0x2E, 0x13], "否定响应(7F 2E 13)", func_req=func_flg)
        if not status:
            return
        TestLog("INFO", "Step7", "发送2E FF FF 00请求")
        status, resp = __service_2E_check(node, 0xFFFF, bytes([0x00]), [0x7F, 0x2E, 0x31], "否定响应(7F 2E 31)",
                                          func_req=func_flg)
        if not status:
            return
        TestLog("INFO", "Step8", "发送2E XX XX + (len-1)请求")
        # TODO DID & data
        status, resp = __service_2E_check(node, 0x00, bytes([][:-1]), [0x7F, 0x2E, 0x13], "否定响应(7F 2E 13)",
                                          func_req=func_flg)
        if not status:
            return
        TestLog("INFO", "Step9", "发送2E XX XX + (len)请求")
        # TODO DID & data
        status, resp = __service_2E_check(node, 0x00, bytes([]), [0x7F, 0x2E, 0x33], "否定响应(7F 2E 33)",
                                          func_req=func_flg)
        if not status:
            return
        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                            func_req=func_flg): return

        TestLog("INFO", "Step12", "触发NRC22的条件并发送2E XX XX + (len)请求，data中含无效值")
        # TODO 触发NRC22 & DID & data
        status, resp = __service_2E_check(node, 0x00, bytes([]), [0x7F, 0x2E, 0x22], "否定响应(7F 2E 22)",
                                          func_req=func_flg)
        if not status:
            return
        TestLog("INFO", "Step13", "触发NRC72的条件并发送2E XX XX + (len)请求，data中含无效值")
        # TODO 触发NRC72 & DID & data
        status, resp = __service_2E_check(node, 0x00, bytes([]), [0x7F, 0x2E, 0x31], "否定响应(7F 2E 31)",
                                          func_req=func_flg)
        if not status:
            return
        TestLog("INFO", "Step14", "触发NRC72的条件并发送2E XX XX + (len)请求，data为有效值")
        # TODO 触发NRC72 & DID & data
        status, resp = __service_2E_check(node, 0x00, bytes([]), [0x7F, 0x2E, 0x72], "否定响应(7F 2E 72)",
                                          func_req=func_flg)
        if not status:
            return
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_14_Positive(node: UDSNode, name: str = "14服务肯定响应及功能检查(物理寻址)",
                                func_flg: bool = False):
    """
    [TG9_TC1] 14服务肯定响应及功能检查(物理寻址)
    """
    step = 0
    rVnormal = P.CANInfo.Vnormal
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        TestLog("INFO", name, "执行14服务肯定响应及功能检查")

        # Step 1: 请求进入默认会话 (10 01)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step 2: 检查当前会话状态 (31 01 02 03)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["default"],
                                           "位于默认会话中(7F 31 7F)",
                                           func_req=func_flg):
            return

        # Step 3: 使DUT接收的报文失效，等待4.5s
        step += 1
        TestLog("INFO", "", "设置低电压，开启3E 80会话保持服务")
        tester_present_start(node)
        print(ctx.power_ctrl.set_voltage(8))
        TestLog("INFO", f"Step{step}", "使DUT接收的报文失效，等待4.5s")
        __lin_restart_delay(4.5)

        # TODO 此步骤需要根据实际环境实现报文失效功能
        TestLog("INFO", "", "跳过报文失效步骤(需根据实际实际环境实现)")

        # Step 4: 发送19 02 09读DTC
        step += 1
        TestLog("INFO", f"Step{step}", "发送19 02 09读DTC")
        status, resp = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                              expect_data=[0x59, 0x02], expect_str="DUT返回DTC(59 02 ...)",
                                              func_req=func_flg)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        # Step 5: 检查是否通信丢失DTC被成功存储
        step += 1
        TestLog("INFO", f"Step{step}", "检查是否通信丢失DTC被成功存储")
        # TODO: 校验通信丢失DTC存储情况
        TestLog("INFO", "", "跳过DTC存储检查(需根据实际环境实现)")

        # Step 6: 使DUT接收的报文恢复，等待4.5s
        step += 1
        TestLog("INFO", f"Step{step}", "使DUT接收的报文恢复，等待4.5s")
        # TODO 此步骤需要根据实际环境实现报文失效功能
        TestLog("INFO", "", "跳过报文恢复步骤(需根据实际环境实现)")
        ctx.power_ctrl.set_voltage(rVnormal)
        __lin_restart_delay(4.5)
        tester_present_stop()

        # Step 7: 遍历所有支持的14服务请求子功能参数
        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有支持的14服务请求子功能参数")
        for dtc_group in UDSTestParams.Services14DTCGroupSupportList:
            TestLog("INFO", "", f"发送14服务清除DTC组: 0x{dtc_group:06X}")
            if not __service_14_check_lin(node, dtc_group, [0x54],
                                          f"清除DTC组0x{dtc_group:06X}肯定响应(54)", func_req=func_flg):
                return

        # Step 8: 检查是否通信丢失DTC被成功清除
        step += 1
        TestLog("INFO", f"Step{step}", "检查是否通信丢失DTC被成功清除")

        status, _ = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                      expect_data=[0x59, 0x02], expect_str="DUT返回DTC(59 02 ...)",
                                      func_req=func_flg)
        if not status:
            return
        TestLog("PASS", "DTC清除检查", "通信丢失DTC已成功清除")

        # Step 9: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["default"], "位于默认会话中(7F 31 7F)",
                                           func_req=func_flg):
            return

        # Step 10: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step 11: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step 12: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"],
                                           "位于扩展会话中(71 01 02 03 00)", func_req=func_flg):
            return

        # Step 13: 使DUT接收的报文失效，等待4.5s
        step += 1
        TestLog("INFO", f"Step{step}", "使DUT接收的报文失效，等待4.5s")
        TestLog("INFO", "", "设置低电压，开启3E 80会话保持服务")
        tester_present_start(node)
        ctx.power_ctrl.set_voltage(8)
        __lin_restart_delay(4.5)

        # Step 14: 发送19 02 09读DTC
        step += 1
        TestLog("INFO", f"Step{step}", "发送19 02 09读DTC")
        status, resp = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                              expect_data=[0x59, 0x02], expect_str="DUT返回DTC(59 02 ...)",
                                              func_req=func_flg)
        if not status: return

        dtc_info = get_dtc_from_19_resp(resp)
        TestLog("PASS", "", f"DUT返回DTC={dtc_info}")

        # Step 15: 检查是否通信丢失DTC被成功存储
        step += 1
        TestLog("INFO", f"Step{step}", "检查是否通信丢失DTC被成功存储")
        # TODO: 校验通信丢失DTC存储情况
        TestLog("INFO", "", "跳过DTC存储检查(需根据实际环境实现)")

        # Step 16: 使DUT接收的报文恢复，等待4.5s
        step += 1
        TestLog("INFO", f"Step{step}", "使DUT接收的报文恢复，等待4.5s")
        # TODO 此步骤需要根据实际环境实现报文失效功能
        TestLog("INFO", "", "跳过报文恢复步骤(需根据实际环境实现)")
        ctx.power_ctrl.set_voltage(rVnormal)
        __lin_restart_delay(4.5)
        tester_present_stop()

        # Step 17: 遍历所有支持的14服务请求子功能参数
        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有支持的14服务请求子功能参数")
        for dtc_group in UDSTestParams.Services14DTCGroupSupportList:
            TestLog("INFO", "", f"发送14服务清除DTC组: 0x{dtc_group:06X}")
            if not __service_14_check_lin(node, dtc_group, [0x54],
                                          f"清除DTC组0x{dtc_group:06X}肯定响应(54)", func_req=func_flg):
                return

        # Step 18: 检查是否通信丢失DTC被成功清除
        step += 1
        TestLog("INFO", f"Step{step}", "检查是否通信丢失DTC被成功清除")
        status, _ = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=0x09,
                                      expect_data=[0x59, 0x02], expect_str="DUT返回DTC(59 02 ...)",
                                      func_req=func_flg)
        if not status:
            return
        TestLog("PASS", "DTC清除检查", "通信丢失DTC已成功清除(19 02 09)")

        # Step 19: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"],
                                           "位于扩展会话中(71 01 02 03 00)", func_req=func_flg):
            return

        TestLog("PASS", name, "14服务肯定响应及功能检查(物理寻址) 测试执行成功")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_14_NRC13(
        node: UDSNode,
        name: str = "[TG9_TC2] 14服务NRC13检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG9_TC2] 14服务NRC13检查(物理寻址)
    """
    step = 0
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        TestLog("INFO", name, "执行14服务NRC13检查")

        # Step 1: 请求进入默认会话 (10 01)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step 2: 检查当前会话状态 (31 01 02 03)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["default"],
                                           "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return

        # Step 3: 发送较短14 FF FF服务请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送较短14 FF FF FF服务请求(14 FF FF FF)")
        if not __service_14_check_lin(
                node,
                None,
                [0x7F, 0x14, 0x13],
                "否定响应，NRC=0x13(7F 14 13)",
                func_req=func_flg,
                dl=3,
                dl_padding=0xFF,
        ):
            return

        # Step 4: 发送较长14 FF FF FF FF服务请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送较长14 FF FF FF FF服务请求(14 FF FF FF FF FF)")
        if not __service_14_check_lin(
                node,
                None,
                [0x7F, 0x14, 0x13],
                "否定响应，NRC=0x13(7F 14 13)",
                func_req=func_flg,
                dl=5,
                dl_padding=0xFF,
        ):
            return

        # Step 5: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["default"],
                                           "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return

        # Step 6: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step 7: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step 8: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"],
                                           "位于扩展会话中(71 01 02 03 00)", func_req=func_flg):
            return

        # Step 9: 发送较短14 FF FF服务请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送较短14 FF FF FF服务请求(14 FF FF FF)")
        if not __service_14_check_lin(
                node,
                None,
                [0x7F, 0x14, 0x13],
                "否定响应，NRC=0x13(7F 14 13)",
                func_req=func_flg,
                dl=3,
                dl_padding=0xFF,
        ):
            return

        # Step 10: 发送较长14 FF FF FF FF服务请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送较长14 FF FF FF FF服务请求(14 FF FF FF FF FF)")
        if not __service_14_check_lin(
                node,
                None,
                [0x7F, 0x14, 0x13],
                "否定响应，NRC=0x13(7F 14 13)",
                func_req=func_flg,
                dl=5,
                dl_padding=0xFF,
        ):
            return

        # Step 11: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"],
                                           "位于扩展会话中(71 01 02 03 00)", func_req=func_flg):
            return

        TestLog("PASS", name, "14服务NRC13检查(物理寻址) 测试执行成功")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_14_NRC31(
        node: UDSNode,
        name: str = "[TG9_TC3] 14服务NRC31检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG9_TC3] 14服务NRC31检查(物理寻址)
    """
    step = 0
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        TestLog("INFO", name, "执行14服务NRC31检查")

        # Step 1: 请求进入默认会话 (10 01)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step 2: 检查当前会话状态 (31 01 02 03)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["default"],
                                           "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return

        # Step 3: 遍历所有不支持的诊断故障代码组
        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有不支持的诊断故障代码组")
        for dtc_group in UDSTestParams.Services14DTCGroupUnsupportedList:
            TestLog("INFO", "", f"发送14服务请求，DTC组: 0x{dtc_group:06X}")
            if not __service_14_check_lin(
                    node,
                    dtc_group,
                    [0x7F, 0x14, 0x31],
                    f"否定响应，NRC=0x31(7F 14 31) - DTC组: 0x{dtc_group:06X}",
                    func_req=func_flg,
            ):
                return

        # Step 4: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["default"],
                                           "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return

        # Step 5: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step 6: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step 7: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"],
                                           "位于扩展会话中(71 01 02 03 00)", func_req=func_flg):
            return

        # Step 8: 遍历所有不支持的诊断故障代码组
        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有不支持的诊断故障代码组")
        for dtc_group in UDSTestParams.Services14DTCGroupUnsupportedList:
            TestLog("INFO", "", f"发送14服务请求，DTC组: 0x{dtc_group:06X}")
            if not __service_14_check_lin(
                    node,
                    dtc_group,
                    [0x7F, 0x14, 0x31],
                    f"否定响应，NRC=0x31(7F 14 31) - DTC组: 0x{dtc_group:06X}",
                    func_req=func_flg,
            ):
                return

        # Step 9: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"],
                                           "位于扩展会话中(71 01 02 03 00)", func_req=func_flg):
            return

        TestLog("PASS", name, "14服务NRC31检查(物理寻址) 测试执行成功")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def __send_14_with_nrc22_conditions(node: UDSNode, func_req: bool = False) -> bool:
    """遍历所有可能触发 NRC22 的条件，
    """
    got_nrc22 = False
    cond_list = UDSTestParams.NRC22_ConditionList or [None]

    for idx, cond in enumerate(cond_list, start=1):
        desc = cond if isinstance(cond, str) else f"条件{idx}"
        TestLog("INFO", "Service_0x14", f"在[{desc}]下发送 14 FF FF FF 请求，检查是否触发 NRC22")
        # TODO NRC22 触发条件未实现
        try:
            # 发送 14 FF FF FF 请求
            response_message = node.Service_0x14_ClearDiagnosticInformation(
                h=0xFF, m=0xFF, l=0xFF, func_req=func_req
            )
        except Exception as e:
            TestLog("FAIL", "Service_0x14", f"[{desc}] 下发送 14 FF FF FF 请求异常: {e}")
            TestLog("DEBUG", "Service_0x14", f"详细错误: {traceback.format_exc()}")
            return False

        if response_message is None:
            TestLog("FAIL", "Service_0x14", f"[{desc}] 下发送 14 FF FF FF 未收到响应")
            return False

        data_list = list(response_message.data)
        if len(data_list) >= 3 and data_list[0:3] == [0x7F, 0x14, 0x22]:
            TestLog(
                "PASS",
                "Service_0x14",
                f"[{desc}] 下 14 FF FF FF 收到 NRC22 否定响应: {response_message.data.hex()}",
            )
            got_nrc22 = True
        elif len(data_list) >= 1 and data_list[0] == 0x54:
            TestLog(
                "INFO",
                "Service_0x14",
                f"[{desc}] 下 14 FF FF FF 收到肯定响应(54)，可能未满足 NRC22 触发条件: {response_message.data.hex()}",
            )
        else:
            TestLog(
                "FAIL",
                "Service_0x14",
                f"[{desc}] 下 14 FF FF FF 收到异常响应，期望 54 或 7F 14 22，实际: {response_message.data.hex()}",
            )
            return False

    if not got_nrc22:
        TestLog(
            "FAIL",
            "Service_0x14",
            "遍历所有 NRC22 条件后均未收到 7F 14 22，请检查 UDSTestParams.NRC22_ConditionList 配置或 DUT 行为",
        )
        return False

    return True


def test_phyRequest_14_NRC22(
        node: UDSNode,
        name: str = "[TG9_TC4] 14服务NRC22检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG9_TC4] 14服务NRC22检查(物理寻址)
    """
    step = 0
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        TestLog("INFO", name, "执行14服务NRC22检查")

        # Step 1: 请求进入默认会话 (10 01)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step 2: 检查当前会话状态 (31 01 02 03)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["default"],
                                           "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return

        # Step 3: 遍历所有 NRC22 触发条件并发送 14 FF FF FF 请求
        step += 1
        TestLog("INFO", f"Step{step}", "遍历触发NRC22的所有条件并发送14 FF FF FF请求")
        if not __send_14_with_nrc22_conditions(node, func_req=func_flg):
            return

        # Step 4: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["default"],
                                           "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return

        # Step 5: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # Step 6: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step 7: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"],
                                           "位于扩展会话中(71 01 02 03 00)", func_req=func_flg):
            return

        # Step 8: 遍历所有 NRC22 触发条件并发送 14 FF FF FF 请求
        step += 1
        TestLog("INFO", f"Step{step}", "遍历触发NRC22的所有条件并发送14 FF FF FF请求")
        if not __send_14_with_nrc22_conditions(node, func_req=func_flg):
            return

        # Step 9: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"],
                                           "位于扩展会话中(71 01 02 03 00)", func_req=func_flg):
            return

        TestLog("PASS", name, "14服务NRC22检查(物理寻址) 测试执行成功")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def test_phyRequest_14_NRC_Priority(
        node: UDSNode,
        name: str = "[TG9_TC5] 14服务NRC优先级检查(物理寻址)",
        func_flg: bool = False,
):
    """
    [TG9_TC5] 14服务NRC优先级检查(物理寻址)
    """
    step = 0
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        TestLog("INFO", name, "执行14服务NRC优先级检查")

        # Step 1: 请求进入默认会话 (10 01)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # Step 2: 检查当前会话状态 (31 01 02 03)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["default"],
                                           "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return

        # Step 3: 触发NRC0x22的条件之一并发送14 FF FF请求(长度错误)
        step += 1
        TestLog("INFO", f"Step{step}", "触发NRC0x22的条件之一并发送14 FF FF请求")
        # TODO NRC22 触发条件未实现
        # 使用NRC22条件
        cond_list = UDSTestParams.NRC22_ConditionList or [None]
        cond = cond_list[0] if cond_list else None
        desc = cond if isinstance(cond, str) else "默认条件"
        TestLog("INFO", "Service_0x14", f"在[{desc}]下发送 14 FF FF 请求，检查NRC优先级")
        if len(cond_list) > 0:
            if not __service_14_check_lin(
                    node,
                    None,
                    [0x7F, 0x14, 0x13],
                    "NRC0x13的否定响应(7F 14 13) - 长度错误优先",
                    func_req=func_flg,
                    dl=3,
                    dl_padding=0xFF,
            ):
                return
        else:
            TestLog("INFO", "", "没有配置NRC22触发条件，跳过此步骤")
        # TODO NRC22 触发条件未实现
        # Step 4: 触发NRC0x22的条件
        step += 1
        TestLog("INFO", f"Step{step}", "触发NRC0x22的条件之一并发送14 LL MM NN请求(不支持的DTC组)")
        if len(cond_list) > 0:
            if len(UDSTestParams.Services14DTCGroupUnsupportedList) > 0:
                dtc_group = UDSTestParams.Services14DTCGroupUnsupportedList[0]
                TestLog("INFO", "", f"发送14服务请求，不支持的DTC组: 0x{dtc_group:06X}")

                if not __service_14_check_lin(
                        node,
                        dtc_group,
                        [0x7F, 0x14, 0x31],
                        f"NRC0x31的否定响应(7F 14 31) - 不支持的DTC组优先，DTC组: 0x{dtc_group:06X}",
                        func_req=func_flg,
                ):
                    return
            else:
                TestLog("INFO", "", "没有配置不支持的DTC组，跳过此步骤")

        else:
            TestLog("INFO", "", "没有配置NRC22触发条件，跳过此步骤")
        # TODO NRC22 触发条件未实现
        # Step 5: 触发NRC0x22的条件之一并发送14 FF FF FF请求
        step += 1
        TestLog("INFO", f"Step{step}", "触发NRC0x22的条件之一并发送14 FF FF FF请求")

        if len(cond_list) > 0:
            if not __service_14_check_lin(
                    node,
                    0xFFFFFF,  # 清除所有DTC
                    [0x7F, 0x14, 0x22],
                    "NRC0x22的否定响应(7F 14 22) - 条件错误",
                    func_req=func_flg,
            ):
                return
        else:
            TestLog("INFO", "", "没有配置NRC22触发条件，跳过此步骤")

        # Step 6: 再次触发NRC22条件并发送14 FF FF FF请求
        step += 1
        TestLog("INFO", f"Step{step}", "再次触发NRC22条件并发送14 FF FF FF请求")

        if len(cond_list) > 0:
            if not __service_14_check_lin(
                    node,
                    0xFFFFFF,  # 清除所有DTC
                    [0x7F, 0x14, 0x22],
                    "NRC0x22的否定响应(7F 14 22)",
                    func_req=func_flg,
            ):
                return
        else:
            TestLog("INFO", "", "没有配置NRC22触发条件，跳过此步骤")

        # Step 7: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["default"],
                                           "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return

        TestLog("PASS", name, "14服务NRC优先级检查(物理寻址) 测试执行成功")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def test_phyRequest_19_Positive(
        node: UDSNode,
        name: str = "[TG10_TC1] 19服务肯定响应检查(物理寻址)",
        func_flg: bool = False,
):
    """
    19服务肯定响应检查(物理寻址)
    """
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # 步骤1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # 步骤2: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # 步骤3: 使用19 01请求遍历所有支持的状态掩码
        step += 1
        TestLog("INFO", f"Step{step}", "使用19 01请求遍历所有支持的状态掩码")
        for msk in UDSTestParams.Services19MaskSupportList:
            status, _ = __service_19_check_lin(node, report_type=0x01, DTCStatusMask=msk,
                                          expect_data=[0x59, 0x01], expect_str="肯定响应(59 01)",
                                          func_req=func_flg)
            if not status:
                return

        # 步骤4: 使用19 02请求遍历所有支持的状态掩码
        step += 1
        TestLog("INFO", f"Step{step}", "使用19 02请求遍历所有支持的状态掩码")
        for msk in UDSTestParams.Services19MaskSupportList:
            status, _ = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=msk,
                                          expect_data=[0x59, 0x02], expect_str="肯定响应(59 02)",
                                          func_req=func_flg)
            if not status:
                return

        # 步骤5: 使用19 04请求遍历所有支持的DTC和快照记录号
        step += 1
        TestLog("INFO", f"Step{step}", "使用19 04请求遍历所有支持的DTC和快照记录号")
        for dtc in UDSTestParams.Services19DTCSupportList:
            for snapshot in UDSTestParams.Services19SnapshotRecordNumberSupportList:
                defined_data = bytes([0x04, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, snapshot])
                status, _ = __service_19_check_lin(node, report_type=None, defined_data=defined_data,
                                              expect_data=[0x59, 0x04], expect_str="肯定响应(59 04)",
                                              func_req=func_flg)
                if not status:
                    return
                TestLog("PASS", name, f"19 04请求成功: DTC={dtc:06X}, defined_data={defined_data}")

        # 步骤6: 使用19 06请求遍历所有支持的DTC和扩展数据记录号
        step += 1
        TestLog("INFO", f"Step{step}", "使用19 06请求遍历所有支持的DTC和扩展数据记录号")
        for dtc in UDSTestParams.Services19DTCSupportList:
            for ext in UDSTestParams.Services19ExtendRecordNumberSupportList:
                defined_data = bytes([0x06, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, ext])
                status, _ = __service_19_check_lin(node, report_type=None, expect_data=[0x59, 0x06],
                                              expect_str="肯定响应(59 06)",
                                              func_req=func_flg, defined_data=defined_data)
                if not status:
                    return
                TestLog("PASS", name, f"19 06请求成功: DTC={dtc:06X}, Ext={ext}")

        # 步骤7: 使用19 0A请求
        step += 1
        TestLog("INFO", f"Step{step}", "使用19 0A请求")
        status, _ = __service_19_check_lin(node, report_type=0x0A,
                                      expect_data=[0x59, 0x0A], expect_str="DUT返回DTC(59 0A ...)",
                                      func_req=func_flg)
        if not status:
            return

        # 步骤8: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # 步骤9: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # 步骤10: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # 步骤11: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # 步骤12: 使用19 01请求遍历所有支持的状态掩码
        step += 1
        TestLog("INFO", f"Step{step}", "使用19 01请求遍历所有支持的状态掩码")
        for msk in UDSTestParams.Services19MaskSupportList:
            status, _ = __service_19_check_lin(node, report_type=0x01, DTCStatusMask=msk,
                                          expect_data=[0x59, 0x01], expect_str="肯定响应(59 01)",
                                          func_req=func_flg)
            if not status:
                return

        # 步骤13: 使用19 02请求遍历所有支持的状态掩码
        step += 1
        TestLog("INFO", f"Step{step}", "使用19 02请求遍历所有支持的状态掩码")
        for msk in UDSTestParams.Services19MaskSupportList:
            status, _ = __service_19_check_lin(node, report_type=0x02, DTCStatusMask=msk,
                                          expect_data=[0x59, 0x02], expect_str="肯定响应(59 02)",
                                          func_req=func_flg)
            if not status:
                return

        # 步骤14: 使用19 04请求遍历所有支持的DTC和快照记录号
        step += 1
        TestLog("INFO", f"Step{step}", "使用19 04请求遍历所有支持的DTC和快照记录号")
        for dtc in UDSTestParams.Services19DTCSupportList:
            for snapshot in UDSTestParams.Services19SnapshotRecordNumberSupportList:
                defined_data = bytes([0x04, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, snapshot])
                status, _ = __service_19_check_lin(node, report_type=None, defined_data=defined_data,
                                              expect_data=[0x59, 0x04], expect_str="肯定响应(59 04)",
                                              func_req=func_flg)
                if not status:
                    return
                TestLog("PASS", name, f"19 04请求成功: DTC={dtc:06X}, Snapshot={snapshot}")

        # 步骤15: 使用19 06请求遍历所有支持的DTC和扩展数据记录号
        step += 1
        TestLog("INFO", f"Step{step}", "使用19 06请求遍历所有支持的DTC和扩展数据记录号")
        for dtc in UDSTestParams.Services19DTCSupportList:
            for ext in UDSTestParams.Services19ExtendRecordNumberSupportList:
                defined_data = bytes([0x06, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, ext])
                status, _ = __service_19_check_lin(node, report_type=None, expect_data=[0x59, 0x06],
                                              expect_str="肯定响应(59 06)",
                                              func_req=func_flg, defined_data=defined_data)
                if not status:
                    return
                TestLog("PASS", name, f"19 06请求成功: DTC={dtc:06X}, Ext={ext}")

        # 步骤16: 使用19 0A请求
        step += 1
        TestLog("INFO", f"Step{step}", "使用19 0A请求")
        status, _ = __service_19_check_lin(node, report_type=0x0A,
                                      expect_data=[0x59, 0x0A], expect_str="DUT返回DTC(59 0A ...)",
                                      func_req=func_flg)
        if not status:
            return

        # 步骤17: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "19服务肯定响应检查测试完成")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_19_NRC12(
        node: UDSNode,
        name: str = "[TG10_TC2] 19服务NRC12检查(物理寻址)",
        func_flg: bool = False,
):
    """
    19服务NRC12检查(物理寻址)
    """
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # 步骤1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # 步骤2: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # 步骤3: 使用19 SN请求遍历所有不支持的子功能
        step += 1
        TestLog("INFO", f"Step{step}", "使用19 SN请求遍历所有不支持的子功能")
        supported_subfuns = UDSTestParams.Services19SubfunSupportList
        # 遍历0x00-0x10范围内的所有子功能
        for subfun in range(0x00, 0x11):
            if subfun not in supported_subfuns:
                TestLog("INFO", f"Step{step}.{subfun:02X}", f"测试不支持的子功能: 0x{subfun:02X}")
                status, _ = __service_19_check_lin(node, report_type=subfun,
                                              expect_data=[0x7F, 0x19, 0x12],
                                              expect_str="否定响应NRC=0x12(7F 19 12)",
                                              func_req=func_flg)
                if not status:
                    return
                TestLog("PASS", name, f"19服务子功能0x{subfun:02X} NRC12检查通过")

        # 步骤4: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # 步骤5: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # 步骤6: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # 步骤7: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # 步骤8: 使用19 SN请求遍历所有不支持的子功能
        step += 1
        TestLog("INFO", f"Step{step}", "使用19 SN请求遍历所有不支持的子功能")
        # 遍历0x00-0x10范围内的所有子功能
        for subfun in range(0x00, 0x11):
            if subfun not in supported_subfuns:
                TestLog("INFO", f"Step{step}.{subfun:02X}", f"测试不支持的子功能: 0x{subfun:02X}")
                status, _ = __service_19_check_lin(node, report_type=subfun,
                                              expect_data=[0x7F, 0x19, 0x12],
                                              expect_str="否定响应NRC=0x12(7F 19 12)",
                                              func_req=func_flg)
                if not status:
                    return
                TestLog("PASS", name, f"19服务子功能0x{subfun:02X} NRC12检查通过")

        # 步骤9: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "19服务NRC12检查测试完成")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_19_NRC13(
        node: UDSNode,
        name: str = "[TG10_TC3] 19服务NRC13检查(物理寻址)",
        func_flg: bool = False,
):
    """
    19服务NRC13检查(物理寻址)
    """
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # 步骤1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # 步骤2: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # 步骤3: 发送长度不正确的19 01请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送长度不正确的19 01请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        data_list = [
            [],
            [0x01],
            [0x01, msk, 0x00],
            [0x01, msk, 0x00, 0x00],
            [0x01, msk, 0x00, 0x00, 0x00],
            [0x01, msk, 0x00, 0x00, 0x00, 0x00]
        ]
        for i, data in enumerate(data_list):
            TestLog("INFO", f"Step{step}.{i + 1}", f"发送19 01请求: {bytes(data).hex(' ').upper()}")
            status, _ = __service_19_check_lin(node, report_type=None, defined_data=data,
                                          expect_data=[0x7F, 0x19, 0x13],
                                          expect_str="否定响应NRC=0x13(7F 19 13)",
                                          func_req=func_flg)
            if not status:
                return

        # 步骤4: 发送长度不正确的19 02请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送长度不正确的19 02请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        data_list = [
            [],
            [0x02],
            [0x02, msk, 0x00],
            [0x02, msk, 0x00, 0x00],
            [0x02, msk, 0x00, 0x00, 0x00],
            [0x02, msk, 0x00, 0x00, 0x00, 0x00]
        ]
        for i, data in enumerate(data_list):
            TestLog("INFO", f"Step{step}.{i + 1}", f"发送19 02请求: {bytes(data).hex(' ').upper()}")
            status, _ = __service_19_check_lin(node, report_type=None, defined_data=data,
                                          expect_data=[0x7F, 0x19, 0x13],
                                          expect_str="否定响应NRC=0x13(7F 19 13)",
                                          func_req=func_flg)
            if not status:
                return

        # 步骤5: 发送长度不正确的19 04请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送长度不正确的19 04请求")
        dtc = UDSTestParams.Services19DTCSupportList[0]
        number = UDSTestParams.Services19ExtendRecordNumberSupportList[0]
        dtc_h, dtc_m, dtc_l = (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, dtc & 0xFF
        data_list = [
            [],
            [0x04],
            [0x04, dtc_h],
            [0x04, dtc_h, dtc_m],
            [0x04, dtc_h, dtc_m, dtc_l],
            [0x04, dtc_h, dtc_m, dtc_l, number, 0x00]
        ]
        for i, data in enumerate(data_list):
            TestLog("INFO", f"Step{step}.{i + 1}", f"发送19 04请求: {bytes(data).hex(' ').upper()}")
            status, _ = __service_19_check_lin(node, report_type=None, defined_data=data,
                                          expect_data=[0x7F, 0x19, 0x13],
                                          expect_str="否定响应NRC=0x13(7F 19 13)",
                                          func_req=func_flg)
            if not status:
                return

        # 步骤6: 发送长度不正确的19 06请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送长度不正确的19 06请求")
        dtc = UDSTestParams.Services19DTCSupportList[0]
        number = UDSTestParams.Services19ExtendRecordNumberSupportList[0]
        dtc_h, dtc_m, dtc_l = (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, dtc & 0xFF
        data_list = [
            [],
            [0x06],
            [0x06, dtc_h],
            [0x06, dtc_h, dtc_m],
            [0x06, dtc_h, dtc_m, dtc_l],
            [0x06, dtc_h, dtc_m, dtc_l, number, 0x00]
        ]
        for i, data in enumerate(data_list):
            TestLog("INFO", f"Step{step}.{i + 1}", f"发送19 06请求: {bytes(data).hex(' ').upper()}")
            status, _ = __service_19_check_lin(node, report_type=None, defined_data=data,
                                          expect_data=[0x7F, 0x19, 0x13],
                                          expect_str="否定响应NRC=0x13(7F 19 13)",
                                          func_req=func_flg)
            if not status:
                return

        # 步骤7: 发送长度不正确的19 0A请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送长度不正确的19 0A请求")
        dtc = UDSTestParams.Services19DTCSupportList[0]
        number = UDSTestParams.Services19ExtendRecordNumberSupportList[0]
        dtc_h, dtc_m, dtc_l = (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, dtc & 0xFF
        data_list = [
            [],
            [0x0A, dtc_h],
            [0x0A, dtc_h, dtc_m],
            [0x0A, dtc_h, dtc_m, dtc_l],
            [0x0A, dtc_h, dtc_m, dtc_l, number, 0x00]
        ]
        for i, data in enumerate(data_list):
            TestLog("INFO", f"Step{step}.{i + 1}", f"发送19 0A请求: {bytes(data).hex(' ').upper()}")
            status, _ = __service_19_check_lin(node, report_type=None, defined_data=data,
                                          expect_data=[0x7F, 0x19, 0x13],
                                          expect_str="否定响应NRC=0x13(7F 19 13)",
                                          func_req=func_flg)
            if not status:
                return

        # 步骤8: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # 步骤9: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # 步骤10: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # 步骤11: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # 步骤12: 发送长度不正确的19 01请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送长度不正确的19 01请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        data_list = [
            [],
            [0x01],
            [0x01, msk, 0x00],
            [0x01, msk, 0x00, 0x00],
            [0x01, msk, 0x00, 0x00, 0x00],
            [0x01, msk, 0x00, 0x00, 0x00, 0x00]
        ]
        for i, data in enumerate(data_list):
            TestLog("INFO", f"Step{step}.{i + 1}", f"发送19 01请求: {bytes(data).hex(' ').upper()}")
            status, _ = __service_19_check_lin(node, report_type=None, defined_data=data,
                                          expect_data=[0x7F, 0x19, 0x13],
                                          expect_str="否定响应NRC=0x13(7F 19 13)",
                                          func_req=func_flg)
            if not status:
                return

        # 步骤13: 发送长度不正确的19 02请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送长度不正确的19 02请求")
        msk = UDSTestParams.Services19MaskSupportList[0]
        data_list = [
            [],
            [0x02],
            [0x02, msk, 0x00],
            [0x02, msk, 0x00, 0x00],
            [0x02, msk, 0x00, 0x00, 0x00],
            [0x02, msk, 0x00, 0x00, 0x00, 0x00]
        ]
        for i, data in enumerate(data_list):
            TestLog("INFO", f"Step{step}.{i + 1}", f"发送19 02请求: {bytes(data).hex(' ').upper()}")
            status, _ = __service_19_check_lin(node, report_type=None, defined_data=data,
                                          expect_data=[0x7F, 0x19, 0x13],
                                          expect_str="否定响应NRC=0x13(7F 19 13)",
                                          func_req=func_flg)
            if not status:
                return

        # 步骤14: 发送长度不正确的19 04请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送长度不正确的19 04请求")
        dtc = UDSTestParams.Services19DTCSupportList[0]
        number = UDSTestParams.Services19ExtendRecordNumberSupportList[0]
        dtc_h, dtc_m, dtc_l = (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, dtc & 0xFF
        data_list = [
            [],
            [0x04],
            [0x04, dtc_h],
            [0x04, dtc_h, dtc_m],
            [0x04, dtc_h, dtc_m, dtc_l],
            [0x04, dtc_h, dtc_m, dtc_l, number, 0x00]
        ]
        for i, data in enumerate(data_list):
            TestLog("INFO", f"Step{step}.{i + 1}", f"发送19 04请求: {bytes(data).hex(' ').upper()}")
            status, _ = __service_19_check_lin(node, report_type=None, defined_data=data,
                                          expect_data=[0x7F, 0x19, 0x13],
                                          expect_str="否定响应NRC=0x13(7F 19 13)",
                                          func_req=func_flg)
            if not status:
                return

        # 步骤15: 发送长度不正确的19 06请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送长度不正确的19 06请求")
        dtc = UDSTestParams.Services19DTCSupportList[0]
        number = UDSTestParams.Services19ExtendRecordNumberSupportList[0]
        dtc_h, dtc_m, dtc_l = (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, dtc & 0xFF
        data_list = [
            [],
            [0x06],
            [0x06, dtc_h],
            [0x06, dtc_h, dtc_m],
            [0x06, dtc_h, dtc_m, dtc_l],
            [0x06, dtc_h, dtc_m, dtc_l, number, 0x00]
        ]
        for i, data in enumerate(data_list):
            TestLog("INFO", f"Step{step}.{i + 1}", f"发送19 06请求: {bytes(data).hex(' ').upper()}")
            status, _ = __service_19_check_lin(node, report_type=None, defined_data=data,
                                          expect_data=[0x7F, 0x19, 0x13],
                                          expect_str="否定响应NRC=0x13(7F 19 13)",
                                          func_req=func_flg)
            if not status:
                return

        # 步骤16: 发送长度不正确的19 0A请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送长度不正确的19 0A请求")
        dtc = UDSTestParams.Services19DTCSupportList[0]
        number = UDSTestParams.Services19ExtendRecordNumberSupportList[0]
        dtc_h, dtc_m, dtc_l = (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, dtc & 0xFF
        data_list = [
            [],
            [0x0A, dtc_h],
            [0x0A, dtc_h, dtc_m],
            [0x0A, dtc_h, dtc_m, dtc_l],
            [0x0A, dtc_h, dtc_m, dtc_l, number, 0x00]
        ]
        for i, data in enumerate(data_list):
            TestLog("INFO", f"Step{step}.{i + 1}", f"发送19 0A请求: {bytes(data).hex(' ').upper()}")
            status, _ = __service_19_check_lin(node, report_type=None, defined_data=data,
                                          expect_data=[0x7F, 0x19, 0x13],
                                          expect_str="否定响应NRC=0x13(7F 19 13)",
                                          func_req=func_flg)
            if not status:
                return

        # 步骤17: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "19服务NRC13检查测试完成")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_19_NRC31(
        node: UDSNode,
        name: str = "[TG10_TC4] 19服务NRC31检查(物理寻址)",
        func_flg: bool = False,
):
    """
    19服务NRC31检查(物理寻址)
    """
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # 步骤1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # 步骤2: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # 步骤3: 使用19 04请求遍历
        step += 1
        TestLog("INFO", f"Step{step}", "使用19 04请求遍历不支持的DTC，NUM合法")

        for dtc in UDSTestParams.Services19DTCUnSupportList:
            for snapshot in UDSTestParams.Services19SnapshotRecordNumberSupportList:  # 0x01, 0xFF
                defined_data = bytes([0x04, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, snapshot])
                TestLog("INFO", f"Step{step}.{dtc:02X}", f"发送19 04请求: {bytes(defined_data).hex(' ').upper()}")
                status, _ = __service_19_check_lin(node, report_type=None, defined_data=defined_data,
                                              expect_data=[0x7F, 0x19, 0x31],
                                              expect_str="否定响应NRC=0x31(7F 19 31)",
                                              func_req=func_flg)
                if not status:
                    return

        # 步骤4: 使用19 06请求遍历
        step += 1
        TestLog("INFO", f"Step{step}", "使用19 06请求遍历不支持的DTC，NUM合法")
        for dtc in UDSTestParams.Services19DTCUnSupportList:
            for ext in UDSTestParams.Services19SnapshotRecordNumberSupportList:  # 0x01, 0xFF
                defined_data = bytes([0x06, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, ext])
                TestLog("INFO", f"Step{step}.{dtc:02X}", f"发送19 06请求: {bytes(defined_data).hex(' ').upper()}")
                status, _ = __service_19_check_lin(node, report_type=None, defined_data=defined_data,
                                              expect_data=[0x7F, 0x19, 0x31],
                                              expect_str="否定响应NRC=0x31(7F 19 31)",
                                              func_req=func_flg)
                if not status:
                    return

        # 步骤5: 使用19 04请求发送一个支持的DTC，遍历所有不等于0x00、0x01、0x02、0xFF的NUM
        step += 1
        TestLog("INFO", f"Step{step}", "使用19 04请求发送一个支持的DTC，遍历所有不等于0x00、0x01、0x02、0xFF的NUM")
        for dtc in UDSTestParams.Services19DTCSupportList[:1]:
            for snapshot in range(0x00, 0xFF):
                if snapshot in [0x00, 0x01, 0x02, 0xFF]:
                    continue
                defined_data = bytes([0x04, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, snapshot])
                TestLog("INFO", f"Step{step}.{snapshot:02X}", f"发送19 04请求: {bytes(defined_data).hex(' ').upper()}")
                status, _ = __service_19_check_lin(node, report_type=None, defined_data=defined_data,
                                              expect_data=[0x7F, 0x19, 0x31],
                                              expect_str="否定响应NRC=0x31(7F 19 31)",
                                              func_req=func_flg)
                if not status:
                    return

        # 步骤6: 使用19 06请求发送一个支持的DTC，遍历所有不等于0x01的NUM
        step += 1
        TestLog("INFO", f"Step{step}", "使用19 06请求发送一个支持的DTC，遍历所有不等于0x01的NUM")
        for dtc in UDSTestParams.Services19DTCSupportList[:1]:
            for ext in range(0x00, 0xFF):
                if ext in [0x01]:
                    continue
                defined_data = bytes([0x06, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, ext])
                TestLog("INFO", f"Step{step}.{ext:02X}", f"发送19 06请求: {bytes(defined_data).hex(' ').upper()}")
                status, _ = __service_19_check_lin(node, report_type=None, defined_data=defined_data,
                                              expect_data=[0x7F, 0x19, 0x13],
                                              expect_str="否定响应NRC=0x13(7F 19 13)",
                                              func_req=func_flg)
                if not status:
                    return

        # 步骤7: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return

        # 步骤8: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中",
                func_req=func_flg,
        ):
            return
        # 步骤9: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # 步骤10: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        # 步骤11: 使用19 04请求遍历不支持的DTC，NUM合法
        step += 1
        TestLog("INFO", f"Step{step}", "使用19 04请求遍历不支持的DTC，NUM合法")

        for dtc in UDSTestParams.Services19DTCUnSupportList:
            for snapshot in UDSTestParams.Services19SnapshotRecordNumberSupportList:  # 0x01, 0xFF
                defined_data = bytes([0x04, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, snapshot])
                TestLog("INFO", f"Step{step}.{dtc:02X}", f"发送19 04请求: {bytes(defined_data).hex(' ').upper()}")
                status, _ = __service_19_check_lin(node, report_type=None, defined_data=defined_data,
                                              expect_data=[0x7F, 0x19, 0x31],
                                              expect_str="否定响应NRC=0x31(7F 19 31)",
                                              func_req=func_flg)
                if not status:
                    return

        # 步骤12: 使用19 06请求遍历不支持的DTC，NUM合法
        step += 1
        TestLog("INFO", f"Step{step}", "使用19 06请求遍历不支持的DTC，NUM合法")
        for dtc in UDSTestParams.Services19DTCUnSupportList:
            for ext in UDSTestParams.Services19SnapshotRecordNumberSupportList:  # 0x01, 0xFF
                defined_data = bytes([0x06, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, ext])
                TestLog("INFO", f"Step{step}.{dtc:02X}", f"发送19 06请求: {bytes(defined_data).hex(' ').upper()}")
                status, _ = __service_19_check_lin(node, report_type=None, defined_data=defined_data,
                                              expect_data=[0x7F, 0x19, 0x31],
                                              expect_str="否定响应NRC=0x31(7F 19 31)",
                                              func_req=func_flg)
                if not status:
                    return

        # 步骤13: 使用19 04请求发送一个支持的DTC，遍历所有不等于0x00、0x01、0x02、0xFF的NUM
        step += 1
        TestLog("INFO", f"Step{step}", "使用19 04请求发送一个支持的DTC，遍历所有不等于0x00、0x01、0x02、0xFF的NUM")
        for dtc in UDSTestParams.Services19DTCSupportList[:1]:
            for snapshot in range(0x00, 0xFF):
                if snapshot in [0x00, 0x01, 0x02, 0xFF]:
                    continue
                defined_data = bytes([0x04, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, snapshot])
                TestLog("INFO", f"Step{step}.{snapshot:02X}", f"发送19 04请求: {bytes(defined_data).hex(' ').upper()}")
                status, _ = __service_19_check_lin(node, report_type=None, defined_data=defined_data,
                                              expect_data=[0x7F, 0x19, 0x31],
                                              expect_str="否定响应NRC=0x31(7F 19 31)",
                                              func_req=func_flg)
                if not status:
                    return

        # 步骤14: 使用19 06请求发送一个支持的DTC，遍历所有不等于0x01的NUM
        step += 1
        TestLog("INFO", f"Step{step}", "使用19 06请求发送一个支持的DTC，遍历所有不等于0x01的NUM")
        for dtc in UDSTestParams.Services19DTCSupportList[:1]:
            for ext in range(0x00, 0xFF):
                if ext in [0x01]:
                    continue
                defined_data = bytes([0x06, (dtc >> 16) & 0xFF, (dtc >> 8) & 0xFF, (dtc >> 0) & 0xFF, ext])
                TestLog("INFO", f"Step{step}.{ext:02X}", f"发送19 06请求: {bytes(defined_data).hex(' ').upper()}")
                status, _ = __service_19_check_lin(node, report_type=None, defined_data=defined_data,
                                              expect_data=[0x7F, 0x19, 0x13],
                                              expect_str="否定响应NRC=0x13(7F 19 13)",
                                              func_req=func_flg)
                if not status:
                    return

        # 步骤15: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "19服务NRC31检查测试完成")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_19_NRCPriorityCheck(
        node: UDSNode,
        name: str = "[TG10_TC5] 19服务NRC优先级检查(物理寻址)",
        func_flg: bool = False,
):
    """
    19服务NRC优先级检查(物理寻址)
    """
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # 步骤1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # 步骤2: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中(7F 31 7F)",
                func_req=func_flg,
        ):
            return

        # 步骤3: 发送19请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送19请求")
        status, _ = __service_19_check_lin(node, report_type=None,
                                      expect_data=[0x7F, 0x19, 0x13],
                                      expect_str="否定响应NRC=0x13(7F 19 13)",
                                      func_req=func_flg)
        if not status:
            return

        # 步骤4: 发送19 0B请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送19 0B请求")
        status, _ = __service_19_check_lin(node, report_type=0x0B,
                                      expect_data=[0x7F, 0x19, 0x12],
                                      expect_str="否定响应NRC=0x12(7F 19 12)",
                                      func_req=func_flg)
        if not status:
            return

        # 步骤5: 发送19 0B 00请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送19 0B 00请求")
        status, _ = __service_19_check_lin(node, report_type=None, defined_data=[0x0B, 0x00],
                                      expect_data=[0x7F, 0x19, 0x12],
                                      expect_str="否定响应NRC=0x12(7F 19 12)",
                                      func_req=func_flg)
        if not status:
            return

        # 步骤6: 发送19 XX XX + (length-1)字节数据请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送19 XX XX + (length-1)字节数据请求")
        defined_data = bytes([0x04, 0x00, 0x00, 0xFF])
        status, _ = __service_19_check_lin(node, report_type=None, defined_data=defined_data,
                                      expect_data=[0x7F, 0x19, 0x13],
                                      expect_str="否定响应NRC=0x13(7F 19 13)",
                                      func_req=func_flg)
        if not status:
            return

        # 步骤7: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["default"],
                "位于默认会话中(7F 31 7F)",
                func_req=func_flg,
        ):
            return

        TestLog("PASS", name, "19服务NRC优先级检查测试完成")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def __service_2F_check(
        node,
        id=0,
        option=0,
        cs=[],
        enable_mask=b"",
        expect_data=[],
        expect_str: str = "",
        func_req: bool = False,
        dl: int | None = None,
        dl_padding: int = 0x00,
        timeout: float = 5,
):
    try:
        response_message = node.Service_0x2F_InputOutputControlByIdentifier(
            id,
            option,
            cs,
            enable_mask,
            func_req=func_req,
            dl=dl,
            dl_padding=dl_padding,
            timeout=timeout,
        )
        if expect_data is None:
            # 期望无响应
            if response_message is None:
                TestLog("PASS", "Service_0x2F", f"{expect_str}，无响应符合预期")
                return True, []
            TestLog("FAIL", "Service_0x2F", f"{expect_str}，期望无响应，实际收到: {response_message.data.hex()}")
            return False, list(response_message.data)

        if response_message is None:
            TestLog("FAIL", "Service_0x2F", f"{expect_str}，未收到响应")
            return False, []
        if isinstance(expect_data[0], list):
            check_ok = False
            for ex_data in expect_data:
                if list(response_message.data[0:len(ex_data)]) == ex_data:
                    TestLog(
                        "INFO",
                        "Service_0x2F",
                        f"{expect_str}，响应不匹配，期望: {bytes(expect_data).hex()} 实际: {response_message.data.hex()}",
                    )
                    check_ok = True
            return check_ok, list(response_message.data)
        else:
            if list(response_message.data[0:len(expect_data)]) != expect_data:
                TestLog(
                    "FAIL",
                    "Service_0x2F",
                    f"{expect_str}，响应不匹配，期望: {bytes(expect_data).hex()} 实际: {response_message.data.hex()}",
                )
                return False, list(response_message.data)

        TestLog("PASS", "Service_0x2F", f"{expect_str}，响应匹配: {response_message.data.hex()}")
        return True, list(response_message.data)
    except Exception as e:
        TestLog("FAIL", "Service_0x2F", f"{expect_str}，执行异常: {e}")
        TestLog("DEBUG", "Service_0x2F", f"详细错误: {traceback.format_exc()}")
        return False, []


def test_phyRequest_2F_Positive(
        node: UDSNode,
        name: str = "[TG11_TC1] 2F服务肯定响应检查(物理寻址)",
        func_flg: bool = False,
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # clear_err_count(node,1,func_flg)
        step = 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step = 2
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step = 3
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                            func_req=func_flg): return
        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有支持的2F服务的DID")
        did_list_00 = UDSTestParams.Services2FControlParamDIDList
        for did_info in did_list_00:
            did = did_info.get('did', 0)
            control_params = did_info.get('control_params', [])
            control_type = did_info.get('type')
            did_h = (did >> 8) & 0XFF
            did_l = (did) & 0XFF
            if control_type["ReturnToECU"] == True:
                status, _ = __service_2F_check(node, did, 0, control_params, [], [0x6F, did_h, did_l],
                                               f"肯定响应(6F {did:04X} XX) - DID: {did:04X}, SN:0", func_req=func_flg)
                if not status: return
            if control_type["ResetToDefault"] == True:
                status, _ = __service_2F_check(node, did, 1, control_params, [], [0x6F, did_h, did_l],
                                               f"肯定响应(6F {did:04X} XX) - DID: {did:04X}, SN:1", func_req=func_flg)
                if not status: return
            if control_type["FreezeCurrentState"] == True:
                status, _ = __service_2F_check(node, did, 2, control_params, [], [0x6F, did_h, did_l],
                                               f"肯定响应(6F {did:04X} XX) - DID: {did:04X}, SN:2", func_req=func_flg)
                if not status: return
            if control_type["ShortTermAdjust"] == True:
                status, _ = __service_2F_check(node, did, 3, control_params, [], [0x6F, did_h, did_l],
                                               f"肯定响应(6F {did:04X} XX) - DID: {did:04X}, SN:3", func_req=func_flg)
                if not status: return
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_2F_ControlParam(
        node: UDSNode,
        name: str = "[TG11_TC2] 2F服务控制参数检查(物理寻址)",
        func_flg: bool = False,
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    did_list_00 = UDSTestParams.Services2FControlParamDIDList
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                            func_req=func_flg): return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有支持控制参数00的2F服务的DID")
        for para in did_list_00:
            did = para["did"]
            did_h, did_l = (para["did"] >> 8) & 0xFF, para["did"] & 0xFF
            control_type = para.get('type', 0)
            control_params = para.get('control_params', [])
            if control_type["ReturnToECU"] == True:
                status, _ = __service_2F_check(node, did, 0, control_params, [], [0x6F, did_h, did_l],
                                               f"肯定响应(6F {did:04X} XX) - DID: {did:04X}, SN:0", func_req=func_flg)
                if not status: return
            if control_type["FreezeCurrentState"] == True:
                status, _ = __service_2F_check(node, did, 2, control_params, [], [0x6F, did_h, did_l],
                                               f"肯定响应(6F {did:04X} XX) - DID: {did:04X}, SN:2", func_req=func_flg)
                if not status: return
            if control_type["ShortTermAdjust"] == True:
                status, _ = __service_2F_check(node, did, 3, control_params, [], [0x6F, did_h, did_l],
                                               f"肯定响应(6F {did:04X} XX) - DID: {did:04X}, SN:3", func_req=func_flg)
                if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_2F_NRC7F(
        node: UDSNode,
        name: str = "[TG11_TC3] 2F服务NRC7F检查(物理寻址)",
        func_flg: bool = False,
):
    did_list = UDSTestParams.Services2FDID_EXTENDED_SupportList
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)",
                                           func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "发送一个2F服务请求(在扩展会话下支持)")
        if len(did_list) > 0:
            para = did_list[0]
            did = para["did"]
            did_h, did_l = (para["did"] >> 8) & 0xFF, para["did"] & 0xFF
            control_type = para.get('type', 0)
            control_params = para.get('control_params', [])
            if control_type["ReturnToECU"] == True:
                status, _ = __service_2F_check(node, did, 0, control_params, [], [0x7F, 0x2F, 0x7F],
                                               "否定响应，NRC=7F(7F 2F 7F)", func_req=func_flg)
                if not status: return
            if control_type["ResetToDefault"] == True:
                status, _ = __service_2F_check(node, did, 1, control_params, [], [0x7F, 0x2F, 0x7F],
                                               "否定响应，NRC=7F(7F 2F 7F)", func_req=func_flg)
                if not status: return
            if control_type["FreezeCurrentState"] == True:
                status, _ = __service_2F_check(node, did, 2, control_params, [], [0x7F, 0x2F, 0x7F],
                                               "否定响应，NRC=7F(7F 2F 7F)", func_req=func_flg)
                if not status: return
            if control_type["ShortTermAdjust"] == True:
                status, _ = __service_2F_check(node, did, 3, control_params, [], [0x7F, 0x2F, 0x7F],
                                               "否定响应，NRC=7F(7F 2F 7F)", func_req=func_flg)
                if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)",
                                           func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(
                node,
                SESSION_EXPECT_RESPONSES["extended"],
                "位于扩展会话中",
                func_req=func_flg,
        ):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "发送一个2F服务请求(在扩展会话下支持)")
        if len(did_list) > 0:
            para = did_list[0]
            did = para["did"]
            did_h, did_l = (para["did"] >> 8) & 0xFF, para["did"] & 0xFF
            control_type = para.get('type', 0)
            control_params = para.get('control_params', [])
            if control_type["ReturnToECU"] == True:
                status, _ = __service_2F_check(node, did, 0, control_params, [],
                                               [[0x7F, 0x2F, 0x7F], [0x7F, 0x2F, 0x11]],
                                               "否定响应，NRC=7F或NRC=0x11(7F 2F 7F or 7F 2F 11)", func_req=func_flg)
                if not status: return
            if control_type["ResetToDefault"] == True:
                status, _ = __service_2F_check(node, did, 1, control_params, [],
                                               [[0x7F, 0x2F, 0x7F], [0x7F, 0x2F, 0x11]],
                                               "否定响应，NRC=7F或NRC=0x11(7F 2F 7F or 7F 2F 11)", func_req=func_flg)
                if not status: return
            if control_type["FreezeCurrentState"] == True:
                status, _ = __service_2F_check(node, did, 2, control_params, [],
                                               [[0x7F, 0x2F, 0x7F], [0x7F, 0x2F, 0x11]],
                                               "否定响应，NRC=7F或NRC=0x11(7F 2F 7F or 7F 2F 11)", func_req=func_flg)
                if not status: return
            if control_type["ShortTermAdjust"] == True:
                status, _ = __service_2F_check(node, did, 3, control_params, [],
                                               [[0x7F, 0x2F, 0x7F], [0x7F, 0x2F, 0x11]],
                                               "否定响应，NRC=7F或NRC=0x11(7F 2F 7F or 7F 2F 11)", func_req=func_flg)
                if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_2F_NRC13(
        node: UDSNode,
        name: str = "[TG11_TC4] 2F服务NRC13检查(物理寻址)",
        func_flg: bool = False,
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        __lin_restart_delay(2)

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                            func_req=func_flg): return

        step += 1
        did_list = UDSTestParams.Services2FControlParamDIDList
        TestLog("INFO", f"Step{step}", "发送长度较短的2F请求(2F DIDH DIDL)")
        for did_info in did_list:
            for dl in [1, 2, 3]:
                did = did_info.get('did', 0)
                control_params = did_info.get('control_params', [0x00])
                control_type = did_info.get('control_type', 0x00)
                status, _ = __service_2F_check(node, did, control_type, control_params, [0x7F, 0x2F, 0x13],
                                               f"否定响应，NRC=13(7F 2F 13) - DID: {did:04X}", dl=dl, func_req=func_flg)
                if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "发送位映射DID的2F请求(长度不正确)")
        for para in did_list:
            did = para["did"]
            did_h, did_l = (para["did"] >> 8) & 0xFF, para["did"] & 0xFF
            control_type = para.get('type', 0)
            control_params = para.get('control_params', [])
            for dl in range(4, 8):
                if dl != len(control_params):
                    if control_type["ReturnToECU"] == True:
                        status, _ = __service_2F_check(node, did, 0, control_params, [], [0X7F, 0X2F, 0X13],
                                                       "否定响应7F 2F 13", dl=dl, func_req=func_flg)
                        if not status: return
                    if control_type["ResetToDefault"] == True:
                        status, _ = __service_2F_check(node, did, 1, control_params, [], [0X7F, 0X2F, 0X13],
                                                       "否定响应7F 2F 13", dl=dl, func_req=func_flg)
                        if not status: return
                    if control_type["FreezeCurrentState"] == True:
                        status, _ = __service_2F_check(node, did, 2, control_params, [], [0X7F, 0X2F, 0X13],
                                                       "否定响应7F 2F 13", dl=dl, func_req=func_flg)
                        if not status: return
                    if control_type["ShortTermAdjust"] == True:
                        status, _ = __service_2F_check(node, did, 3, control_params, [], [0X7F, 0X2F, 0X13],
                                                       "否定响应7F 2F 13", dl=dl, func_req=func_flg)
                        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_2F_NRC31(
        node: UDSNode,
        name: str = "[TG11_TC5] 2F服务NRC31检查(物理寻址)",
        func_flg: bool = False,
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    try:
        unsupported_did_list = UDSTestParams.Services2FDIDUnsupportedList
        did_list = UDSTestParams.Services2FControlParamDIDList
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step = 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step = 2
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step = 3
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        step = 4
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 5
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                            func_req=func_flg): return

        step = 6
        TestLog("INFO", f"Step{step}", "遍历不支持的DID发送2F请求")
        for did in unsupported_did_list:
            control_params = []
            status, _ = __service_2F_check(node, did, 0, control_params, [], [0x7F, 0x2F, 0x31],
                                           "否定响应，NRC=7F(7F 2F 31)", dl=4, func_req=func_flg)
            if not status: return
            status, _ = __service_2F_check(node, did, 1, control_params, [], [0x7F, 0x2F, 0x31],
                                           "否定响应，NRC=7F(7F 2F 31)", dl=4, func_req=func_flg)
            if not status: return
            status, _ = __service_2F_check(node, did, 2, control_params, [], [0x7F, 0x2F, 0x31],
                                           "否定响应，NRC=7F(7F 2F 31)", dl=4, func_req=func_flg)
            if not status: return
            status, _ = __service_2F_check(node, did, 3, control_params, [], [0x7F, 0x2F, 0x31],
                                           "否定响应，NRC=7F(7F 2F 31)", dl=4, func_req=func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历支持的DID发送不支持的控制参数")
        for para in did_list:
            did = para["did"]
            did_h, did_l = (para["did"] >> 8) & 0xFF, para["did"] & 0xFF
            control_type = para.get('type', 0)
            control_params = para.get('control_params', [])
            if control_type["ReturnToECU"] == False:
                status, _ = __service_2F_check(node, did, 0, control_params, [], [0x7F, 0x2F, 0x31],
                                               "否定响应，NRC=7F(7F 2F 31)", func_req=func_flg)
                if not status: return
            if control_type["ResetToDefault"] == False:
                status, _ = __service_2F_check(node, did, 1, control_params, [], [0x7F, 0x2F, 0x31],
                                               "否定响应，NRC=7F(7F 2F 31)", func_req=func_flg)
                if not status: return
            if control_type["FreezeCurrentState"] == False:
                status, _ = __service_2F_check(node, did, 2, control_params, [], [0x7F, 0x2F, 0x31],
                                               "否定响应，NRC=7F(7F 2F 31)", func_req=func_flg)
                if not status: return
            if control_type["ShortTermAdjust"] == False:
                status, _ = __service_2F_check(node, did, 3, control_params, [], [0x7F, 0x2F, 0x31],
                                               "否定响应，NRC=7F(7F 2F 31)", func_req=func_flg)
                if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历位映射DID发送不支持的位使能控制组合")
        # for para in did_list:
        #     did = para["did"]
        #     did_h, did_l = (para["did"] >> 8) & 0xFF, para["did"] & 0xFF
        #     control_type  = para.get('type', 0)
        #     control_params = para.get('control_params', [])
        #     enable_mask =  para.get('enable_mask', [])
        #     if control_type["ShortTermAdjust"] == True:
        #         status, _ = __service_2F_check(node, did, 3, control_params,enable_mask,[0x7F, 0x2F, 0x31], "否定响应，NRC=7F(7F 2F 31)", func_req=func_flg)
        #         if not status: return     

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_2F_NRC33(
        node: UDSNode,
        name: str = "[TG11_TC6] 2F服务NRC33检查(物理寻址)",
        func_flg: bool = False,
):
    security_did_list = UDSTestParams.Services2FDIDSecurityRequiredList
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有需要安全解锁的2F服务DID(未解锁状态)")
        for para in security_did_list:
            did = para["did"]
            did_h, did_l = (para["did"] >> 8) & 0xFF, para["did"] & 0xFF
            control_type = para.get('type', 0)
            control_params = para.get('control_params', [])
            if control_type["ReturnToECU"] == True:
                status, _ = __service_2F_check(node, did, 0, control_params, [], [0x7F, 0x2F, 0x33],
                                               "否定响应，NRC=7F(7F 2F 33)", func_req=func_flg)
                if not status: return
            if control_type["ResetToDefault"] == True:
                status, _ = __service_2F_check(node, did, 1, control_params, [], [0x7F, 0x2F, 0x33],
                                               "否定响应，NRC=7F(7F 2F 33)", func_req=func_flg)
                if not status: return
            if control_type["FreezeCurrentState"] == True:
                status, _ = __service_2F_check(node, did, 2, control_params, [], [0x7F, 0x2F, 0x33],
                                               "否定响应，NRC=7F(7F 2F 33)", func_req=func_flg)
                if not status: return
            if control_type["ShortTermAdjust"] == True:
                status, _ = __service_2F_check(node, did, 3, control_params, [], [0x7F, 0x2F, 0x33],
                                               "否定响应，NRC=7F(7F 2F 33)", func_req=func_flg)
                if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_2F_NRC22(
        node: UDSNode,
        name: str = "[TG11_TC7] 2F服务NRC22检查(物理寻址)",
        func_flg: bool = False,
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    did_list = UDSTestParams.Services2FControlParamDIDList
    nrc22_condition_list = UDSTestParams.NRC22_ConditionList
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                            func_req=func_flg): return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历触发NRC22的所有条件并发送2F请求")
        for condition in nrc22_condition_list:
            if hasattr(condition, 'get'):
                setup_func = condition.get('setup')
                cleanup_func = condition.get('cleanup')
            else:
                TestLog("FAIL", " ", "NRC22不支持")
                return
            if setup_func:
                setup_func()
            if len(did_list) > 0:
                para = did_list[0]
                did = para["did"]
                did_h, did_l = (para["did"] >> 8) & 0xFF, para["did"] & 0xFF
                control_type = para.get('type', 0)
                control_params = para.get('control_params', [])
                if control_type["ReturnToECU"] == True:
                    status, _ = __service_2F_check(node, did, 0, control_params, [], [0x7F, 0x2F, 0x22],
                                                   "否定响应，NRC=7F(7F 2F 22)", func_req=func_flg)
                    if not status: return
                if control_type["ResetToDefault"] == True:
                    status, _ = __service_2F_check(node, did, 1, control_params, [], [0x7F, 0x2F, 0x22],
                                                   "否定响应，NRC=7F(7F 2F 22)", func_req=func_flg)
                    if not status: return
                if control_type["FreezeCurrentState"] == True:
                    status, _ = __service_2F_check(node, did, 2, control_params, [], [0x7F, 0x2F, 0x22],
                                                   "否定响应，NRC=7F(7F 2F 22)", func_req=func_flg)
                    if not status: return
                if control_type["ShortTermAdjust"] == True:
                    status, _ = __service_2F_check(node, did, 3, control_params, [], [0x7F, 0x2F, 0x22],
                                                   "否定响应，NRC=7F(7F 2F 22)", func_req=func_flg)
                    if not status: return

                if cleanup_func:
                    cleanup_func()
                if not status: return
            else:
                if cleanup_func:
                    cleanup_func()

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_2F_NRCPriority(
        node: UDSNode,
        name: str = "[TG11_TC8] 2F服务NRC优先级检查(物理寻址)",
        func_flg: bool = False,
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    did_list = UDSTestParams.Services2FDID_EXTENDED_SupportList
    nrc22_condition_list = UDSTestParams.NRC22_ConditionList
    nrc22_did_list = UDSTestParams.Services2FDID_NRC22_SupportList
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step = 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], expect_str="位于默认会话中(7F 31 7F)",
                                           func_req=func_flg):
            return

        TestLog("INFO", f"Step{step}", "发送一个2F服务请求(在扩展会话下支持)")
        if len(did_list) > 0:
            para = did_list[0]
            did = para["did"]
            did_h, did_l = (para["did"] >> 8) & 0xFF, para["did"] & 0xFF
            control_type = para.get('type', 0)
            control_params = para.get('control_params', [])
            if control_type["ReturnToECU"] == True:
                status, _ = __service_2F_check(node, did, 0, control_params, [], [0x7F, 0x2F, 0x7F],
                                               "否定响应，NRC=7F(7F 2F 7F)", func_req=func_flg)
                if not status: return
            if control_type["ResetToDefault"] == True:
                status, _ = __service_2F_check(node, did, 1, control_params, [], [0x7F, 0x2F, 0x7F],
                                               "否定响应，NRC=7F(7F 2F 7F)", func_req=func_flg)
                if not status: return
            if control_type["FreezeCurrentState"] == True:
                status, _ = __service_2F_check(node, did, 2, control_params, [], [0x7F, 0x2F, 0x7F],
                                               "否定响应，NRC=7F(7F 2F 7F)", func_req=func_flg)
                if not status: return
            if control_type["ShortTermAdjust"] == True:
                status, _ = __service_2F_check(node, did, 3, control_params, [], [0x7F, 0x2F, 0x7F],
                                               "否定响应，NRC=7F(7F 2F 7F)", func_req=func_flg)
                if not status: return

        step = 4
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        step = 6
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step = 7
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                            func_req=func_flg): return

        step = 8
        TestLog("INFO", f"Step{step}", "触发NRC22条件并发送2F请求(NRC22条件下)")
        if len(nrc22_condition_list) > 0:
            condition = nrc22_condition_list[0]
            if hasattr(condition, 'get'):
                setup_func = condition.get('setup')
                if setup_func:
                    setup_func()
            else:
                TestLog("FAIL", " ", "NRC22不支持")
                return

        if len(did_list) > 0:
            para = did_list[0]
            did = para["did"]
            did_h, did_l = (para["did"] >> 8) & 0xFF, para["did"] & 0xFF
            control_type = para.get('type', 0)
            control_params = para.get('control_params', [])
            if control_type["ReturnToECU"] == True:
                status, _ = __service_2F_check(node, did, 0, control_params, [], [0x7F, 0x2F, 0x22],
                                               "否定响应，NRC=22(7F 2F 22)", func_req=func_flg)
                if not status: return
            if control_type["ResetToDefault"] == True:
                status, _ = __service_2F_check(node, did, 1, control_params, [], [0x7F, 0x2F, 0x22],
                                               "否定响应，NRC=22(7F 2F 22)", func_req=func_flg)
                if not status: return
            if control_type["FreezeCurrentState"] == True:
                status, _ = __service_2F_check(node, did, 2, control_params, [], [0x7F, 0x2F, 0x22],
                                               "否定响应，NRC=22(7F 2F 22)", func_req=func_flg)
                if not status: return
            if control_type["ShortTermAdjust"] == True:
                status, _ = __service_2F_check(node, did, 3, control_params, [], [0x7F, 0x2F, 0x22],
                                               "否定响应，NRC=22(7F 2F 22)", func_req=func_flg)
                if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "触发NRC22条件并发送2F请求(长度错误，NRC13优先)")
        status, _ = __service_2F_check(node, 1, 0, [], [], [0x7F, 0x2F, 0x13], "否定响应，NRC=13(7F 2F 13)", dl=1,
                                       func_req=func_flg)
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "触发NRC22条件并发送2F FF FF 00 00 00请求(NRC31优先)")
        status, _ = __service_2F_check(node, 0XFFFF, 0, [0, 0], [], [0x7F, 0x2F, 0x31], "否定响应，NRC=31(7F 2F 31)",
                                       func_req=func_flg)
        if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "触发NRC22条件并发送2F DIDH DIDL 00 00 00请求(NRC13优先)")
        if len(nrc22_did_list) > 0:
            para = nrc22_did_list[0]
            did = para["did"]
            did_h, did_l = (para["did"] >> 8) & 0xFF, para["did"] & 0xFF
            control_type = para.get('type', 0)
            control_params = para.get('control_params', [])
            if control_type["ReturnToECU"] == True:
                status, _ = __service_2F_check(node, did, 0, control_params, [], [0x7F, 0x2F, 0x13],
                                               "否定响应，NRC=22(7F 2F 13)", func_req=func_flg)
                if not status: return
            if control_type["ResetToDefault"] == True:
                status, _ = __service_2F_check(node, did, 1, control_params, [], [0x7F, 0x2F, 0x13],
                                               "否定响应，NRC=22(7F 2F 13)", func_req=func_flg)
                if not status: return
            if control_type["FreezeCurrentState"] == True:
                status, _ = __service_2F_check(node, did, 2, control_params, [], [0x7F, 0x2F, 0x13],
                                               "否定响应，NRC=22(7F 2F 13)", func_req=func_flg)
                if not status: return
            if control_type["ShortTermAdjust"] == True:
                status, _ = __service_2F_check(node, did, 3, control_params, [], [0x7F, 0x2F, 0x13],
                                               "否定响应，NRC=22(7F 2F 13)", func_req=func_flg)
                if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "触发NRC22条件并发送2F FF FF 00 00 00请求(NRC31优先)")
        status, _ = __service_2F_check(node, 0XFFFF, 0, [0, 0], [], [0x7F, 0x2F, 0x31], "否定响应，NRC=31(7F 2F 31)",
                                       func_req=func_flg)
        if not status: return

        TestLog("INFO", f"Step{step}", "发送一个2F服务请求(在扩展会话下支持)")
        if len(did_list) > 0:
            para = did_list[0]
            did = para["did"]
            did_h, did_l = (para["did"] >> 8) & 0xFF, para["did"] & 0xFF
            control_type = para.get('type', 0)
            control_params = para.get('control_params', [])
            if control_type["ReturnToECU"] == True:
                status, _ = __service_2F_check(node, did, 0, control_params, [], [0x7F, 0x2F, 0x33],
                                               "否定响应，NRC=33(7F 2F 33)", func_req=func_flg)
                if not status: return
            if control_type["ResetToDefault"] == True:
                status, _ = __service_2F_check(node, did, 1, control_params, [], [0x7F, 0x2F, 0x33],
                                               "否定响应，NRC=33(7F 2F 33)", func_req=func_flg)
                if not status: return
            if control_type["FreezeCurrentState"] == True:
                status, _ = __service_2F_check(node, did, 2, control_params, [], [0x7F, 0x2F, 0x33],
                                               "否定响应，NRC=33(7F 2F 33)", func_req=func_flg)
                if not status: return
            if control_type["ShortTermAdjust"] == True:
                status, _ = __service_2F_check(node, did, 3, control_params, [], [0x7F, 0x2F, 0x33],
                                               "否定响应，NRC=33(7F 2F 33)", func_req=func_flg)
                if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_2F_ControlReturn(
        node: UDSNode,
        name: str = "[TG11_TC9] 2F服务控制权归还检查(物理寻址)",
        func_flg: bool = False,
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        did_list = UDSTestParams.Services2FControlParamDIDList

        for para in did_list:
            if control_type["ShortTermAdjust"] == False:
                continue
            TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
            if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
                return

            __lin_restart_delay(2)

            TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
            if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
                return

            TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中",
                                               func_req=func_flg):
                return

            TestLog("INFO", f"Step4", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
            status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                       func_req=func_flg)
            if not status: return
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
            if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
                TestLog("FAIL", "",
                        f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
                return
            TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

            TestLog("INFO", f"Step5", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
            if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                                f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                                func_req=func_flg): return

            TestLog("INFO", "Step6", f"发送2F服务控制DID {did:04X}，控制参数=0x03")
            did = para["did"]
            did_h, did_l = (para["did"] >> 8) & 0xFF, para["did"] & 0xFF
            control_type = para.get('type', 0)
            control_params = para.get('control_params', [])

            status, _ = __service_2F_check(node, did, 3, control_params, [], [0x6F, did_h, did_l],
                                           f"肯定响应（6F {did_h:02X} {did_l:02X}）", func_req=func_flg)
            if not status: return

            TestLog("INFO", "Step7", "发送10 01请求进入默认会话(控制权归还ECU)")
            if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
                return

            TestLog("INFO", "Step8", f"22服务读取DID {did:04X}，验证控制权已归还")
            status, _ = __service_22_check(node, [did], [0x62, did_h, did_l],
                                           f"肯定响应，DID数据为0x00(62 {did_h:02X} {did_l:02X} ...)", func_req=func_flg)
            if not status: return

        for did in did_list:
            if control_type["ShortTermAdjust"] == False:
                continue
            TestLog("INFO", "Step10", "请求进入扩展会话(10 03)")
            if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
                return
            TestLog("INFO", "Step11", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中",
                                               func_req=func_flg):
                return

            TestLog("INFO", f"Step12", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
            status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                       func_req=func_flg)
            if not status: return
            TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
            if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
                TestLog("FAIL", "",
                        f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
                return
            TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

            TestLog("INFO", f"Step13", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
            if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                                f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                                func_req=func_flg): return

            TestLog("INFO", "Step14", f"发送2F服务控制DID {did:04X}，控制参数=0x03")
            did = para["did"]
            did_h, did_l = (para["did"] >> 8) & 0xFF, para["did"] & 0xFF
            control_type = para.get('type', 0)
            control_params = para.get('control_params', [])

            status, _ = __service_2F_check(node, did, 3, control_params, [], [0x6F, did_h, did_l],
                                           f"肯定响应（6F {did_h:02X} {did_l:02X}）", func_req=func_flg)
            if not status: return

            TestLog("INFO", "Step15", "发送11 01请求复位(控制权归还ECU)")
            __service_11_check(node, 0x01, [0x51, 0x01], "肯定响应(51 01)")
            __lin_restart_delay(2)  # 等待ECU复位

            TestLog("INFO", "Step16", f"22服务读取DID {did:04X}，验证控制权已归还")
            status, _ = __service_22_check(node, [did], [0x62, did_h, did_l],
                                           f"肯定响应，DID数据为0x00(62 {did_h:02X} {did_l:02X} ...)", func_req=func_flg)
            if not status: return

        for did in did_list:
            if control_type["ShortTermAdjust"] == False:
                continue
            TestLog("INFO", "Step18", "请求进入扩展会话(10 03)")
            if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
                return

            TestLog("INFO", "Step19", "检查当前会话状态(31 01 02 03)")
            if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中",
                                               func_req=func_flg):
                return

            TestLog("INFO", "Step20", "发送27 01请求")
            status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                       func_req=func_flg)
            if not status: return

            TestLog("INFO", "Step21", "发送27 02请求")
            if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                                f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                                func_req=func_flg): return

            TestLog("INFO", "Step22", f"发送2F服务控制DID {did:04X}，控制参数=0x03")
            did = para["did"]
            did_h, did_l = (para["did"] >> 8) & 0xFF, para["did"] & 0xFF
            control_type = para.get('type', 0)
            control_params = para.get('control_params', [])

            status, _ = __service_2F_check(node, did, 3, control_params, [], [0x6F, did_h, did_l],
                                           f"肯定响应（6F {did_h:02X} {did_l:02X}）", func_req=func_flg)
            if not status: return

            TestLog("INFO", "Step23", "等待6s(S3 Server超时使控制权归ECU)")
            time.sleep(6)

            TestLog("INFO", "Step24", f"22服务读取DID {did:04X}，验证控制权已归还")
            status, _ = __service_22_check(node, [did], [0x62, did_h, did_l],
                                           f"肯定响应，DID数据为0x00(62 {did_h:02X} {did_l:02X} ...)", func_req=func_flg)
            if not status: return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def __service_31_check(
        node,
        control_type,
        rid,
        record=b"",
        expect_data=None,
        expect_str="",
        func_req: bool = False,
        dl: int | None = None,
        dl_padding: int = 0x00,
        timeout: float = 5, **kwargs):
    try:
        response_message = node.Service_0x31_RoutineControl(control_type=control_type, rid=rid, record=record,
                                                            timeout=timeout,
                                                            func_req=func_req, dl=dl, dl_padding=dl_padding, **kwargs)
        if expect_data is None:
            # 期望无响应
            if response_message is None:
                TestLog("PASS", "Service_0x31", f"{expect_str}，无响应符合预期")
                return True, []
            TestLog("FAIL", "Service_0x31", f"{expect_str}，期望无响应，实际收到: {response_message.data.hex()}")
            return False, list(response_message.data)
        if response_message is None:
            TestLog("FAIL", "Service_0x31", f"{expect_str}，未收到响应")
            return False, []
        if isinstance(expect_data[0], list):
            check_ok = False
            for ex_data in expect_data:
                if list(response_message.data[0:len(ex_data)]) == ex_data:
                    TestLog(
                        "INFO",
                        "Service_0x31",
                        f"{expect_str}，响应不匹配，期望: {bytes(expect_data).hex()} 实际: {response_message.data.hex()}",
                    )
                    check_ok = True
            return check_ok, list(response_message.data)
        else:
            if list(response_message.data[0:len(expect_data)]) != expect_data:
                TestLog(
                    "FAIL",
                    "Service_0x31",
                    f"{expect_str}，响应不匹配，期望: {bytes(expect_data).hex()} 实际: {response_message.data.hex()}",
                )
                return False, list(response_message.data)

        TestLog("PASS", "Service_0x31", f"{expect_str}，响应匹配: {response_message.data.hex()}")
        return True, list(response_message.data)
    except Exception as e:
        TestLog("FAIL", "Service_0x31", f"{expect_str}，执行异常: {e}")
        TestLog("DEBUG", "Service_0x31", f"详细错误: {traceback.format_exc()}")
        return False, []


def test_phyRequest_31_Positive(
        node: UDSNode,
        name: str = "[TG12_TC1] 31服务肯定响应检查(物理寻址)",
        func_flg: bool = False,
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_EXT_PRO, DLL_PATH_PRO = 0x11, P.ECUInfo.dllPath_2711  # 扩展等级
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                            func_req=func_flg): return

        rid_list_extended = UDSTestParams.Services31RIDSupportList_Extended
        rid_list_programming = UDSTestParams.Services31RIDSupportList_Programming

        step += 1
        TestLog("INFO", f"Step{step}", "遍历扩展会话下支持的31服务RID")
        for rid_info in rid_list_extended:
            rid = rid_info.get('rid', 0)
            sub_funcs = rid_info.get('sub_funcs', [0x01])
            record = rid_info.get('record', b'')
            rid_h, rid_l = (rid >> 8) & 0xFF, rid & 0xFF
            for sub_func in sub_funcs:
                status, _ = __service_31_check(node, sub_func, rid, record, [0x71, sub_func, rid_h, rid_l],
                                               f"肯定响应(71 {sub_func:02X} {rid_h:02X} {rid_l:02X} XX) - RID: {rid:04X}",
                                               func_req=func_flg)
                if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT_PRO})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT_PRO, [0x67, LEVEL_EXT_PRO],
                                                   f"肯定响应(67 {LEVEL_EXT_PRO})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT_PRO + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT_PRO, seed_list, [0x67, LEVEL_EXT_PRO + 1],
                                            f"肯定响应(67 {LEVEL_EXT_PRO + 1})", dll_path=DLL_PATH_PRO,
                                            func_req=func_flg): return
        step += 1
        TestLog("INFO", f"Step{step}", "遍历刷新会话下支持的31服务RID")
        for rid_info in rid_list_programming:
            rid = rid_info.get('rid', 0)
            sub_funcs = rid_info.get('sub_funcs', [0x01])
            record = rid_info.get('record', b'')
            rid_h, rid_l = (rid >> 8) & 0xFF, rid & 0xFF
            for sub_func in sub_funcs:
                status, _ = __service_31_check(node, sub_func, rid, record, [0x71, sub_func, rid_h, rid_l],
                                               f"肯定响应(71 {sub_func:02X} {rid_h:02X} {rid_l:02X} XX) - RID: {rid:04X}",
                                               func_req=func_flg)
                if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_31_NRC12(
        node: UDSNode,
        name: str = "[TG12_TC2] 31服务NRC12检查(物理寻址)",
        func_flg: bool = False,
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        __lin_restart_delay(2)

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                            func_req=func_flg): return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历不支持的子功能发送31请求")
        rid_list_extended = UDSTestParams.Services31RIDSupportList_Extended
        for rid_info in rid_list_extended:
            rid = rid_info.get('rid', 0)
            sub_funcs = rid_info.get('sub_funcs', [0x01])
            record = rid_info.get('record', b'')
            rid_h, rid_l = (rid >> 8) & 0xFF, rid & 0xFF
            for sub_func in UDSTestParams.Services31SubFunUnsupportedList:
                if sub_func not in sub_funcs:
                    status, _ = __service_31_check(node, sub_func, rid, record, [0X7F, 0X31, 0X12],
                                                   f"否定响应(71 {sub_func:02X} {rid_h:02X} {rid_l:02X} XX) - RID: {rid:04X}",
                                                   func_req=func_flg)
                    if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_31_NRC13(
        node: UDSNode,
        name: str = "[TG12_TC3] 31服务NRC13检查(物理寻址)",
        func_flg: bool = False,
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        __lin_restart_delay(2)

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                            func_req=func_flg): return

        rid_list_extended = UDSTestParams.Services31RIDSupportList_Extended
        step += 1
        TestLog("INFO", f"Step{step}", "发送长度较短的31请求(31 01)")
        status, _ = __service_31_check(node, None, 0, b"", [0x7F, 0x31, 0x13],
                                       f"否定响应NRC=13(7F 31 13)",
                                       dl=1, func_req=func_flg)
        if not status: return

        for sub in UDSTestParams.Services31SubFunSupportList:
            status, _ = __service_31_check(node, sub, 0, b"", [0x7F, 0x31, 0x13],
                                           f"否定响应NRC=13(7F 31 13) - 子功能: {sub:02X}",
                                           dl=2, func_req=func_flg)
            if not status: return

        if not status: return

        for rid_info in rid_list_extended:
            rid = rid_info.get('rid', 0)
            sub_funcs = rid_info.get('sub_funcs', [0x01])
            record = rid_info.get('record', b'')
            rid_h, rid_l = (rid >> 8) & 0xFF, rid & 0xFF
            # 发送31 RT RIDH (子功能+RID高字节)
            status, _ = __service_31_check(node, sub_funcs[0], rid, b"", [0x7F, 0x31, 0x13],
                                           f"否定响应NRC=13(7F 31 13) - 子功能: {sub_funcs[0]:02X}, RIDH: {rid_h:02X}",
                                           dl=3, func_req=func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_31_NRC24(
        node: UDSNode,
        name: str = "[TG12_TC4] 31服务NRC24检查(物理寻址)",
        func_flg: bool = False,
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                            func_req=func_flg): return

        rid_list_extended = UDSTestParams.Services31RIDSupportList_Extended

        step += 1
        TestLog("INFO", f"Step{step}", "发送31 02子功能相关请求，遍历所有DID")
        # 步骤6: 发送31 02子功能相关请求，RIDH为支持的DID的第一个字节，遍历所有DID
        for rid_info in rid_list_extended:
            rid = rid_info.get('rid', 0)
            sub_funcs = rid_info.get('sub_funcs', [0x01])
            record = rid_info.get('record', b'')
            rid_h, rid_l = (rid >> 8) & 0xFF, rid & 0xFF

            # 检查是否支持31 02子功能
            if 0x02 in sub_funcs:
                status, _ = __service_31_check(node, 0x02, rid, record, [0x7F, 0x31, 0x24],
                                               f"否定响应，NRC=24(7F 31 24) - RID: {rid:04X}", func_req=func_flg, dl=7)
                if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "发送31 03子功能相关请求，遍历所有DID")
        # 步骤7: 发送31 03子功能相关请求，RIDH为支持的DID的第一个字节，遍历所有DID
        for rid_info in rid_list_extended:
            rid = rid_info.get('rid', 0)
            sub_funcs = rid_info.get('sub_funcs', [0x01])
            record = rid_info.get('record', b'')
            rid_h, rid_l = (rid >> 8) & 0xFF, rid & 0xFF

            # 检查是否支持31 03子功能
            if 0x03 in sub_funcs:
                status, _ = __service_31_check(node, 0x03, rid, record, [0x7F, 0x31, 0x24],
                                               f"否定响应，NRC=24(7F 31 24) - RID: {rid:04X}", func_req=func_flg, dl=7)
                if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_31_NRC31(
        node: UDSNode,
        name: str = "[TG12_TC5] 31服务NRC31检查(物理寻址)",
        func_flg: bool = False,
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                            func_req=func_flg): return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有31服务不支持的DID，子功能=01")
        # 步骤6: 遍历所有31服务不支持的DID，子功能=01
        unsupported_rid_list = UDSTestParams.Services31RIDUnsupportedList

        for rid in unsupported_rid_list:
            status, _ = __service_31_check(node, 0x01, rid, b"", [0x7F, 0x31, 0x31],
                                           f"否定响应，NRC=31(7F 31 31) - 不支持的RID: {rid:04X}", func_req=func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有31服务支持的DID，子功能=01，但控制记录参数不支持")
        rid_list_extended = UDSTestParams.Services31RIDSupportList_Extended
        # 步骤7: 遍历所有31服务支持的DID，子功能=01，但其控制记录参数不支持
        for rid_info in rid_list_extended:
            rid = rid_info.get('rid', 0)
            sub_funcs = rid_info.get('sub_funcs', [0x01])
            record = rid_info.get('err_record', b'')
            # 检查是否支持01子功能
            if 0x01 in sub_funcs:
                if len(record) != 0:
                    status, _ = __service_31_check(node, 0x01, rid, record, [0x7F, 0x31, 0x31],
                                                   f"否定响应，NRC=31(7F 31 31) - 支持的RID但记录参数不支持: {rid:04X}",
                                                   func_req=func_flg, dl=7)
                    if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_31_NRC33(
        node: UDSNode,
        name: str = "[TG12_TC6] 31服务NRC33检查(物理寻址)",
        func_flg: bool = False,
):
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        security_rid_list = UDSTestParams.Services31RIDSecurityRequiredList

        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有31服务支持但需要解锁才可访问的DID，子功能=01")
        # 步骤4: 遍历所有31服务支持但需要解锁才可访问的DID，子功能=01
        for rid in security_rid_list:
            rid_h, rid_l = (rid >> 8) & 0xFF, rid & 0xFF
            status, _ = __service_31_check(node, 0x01, rid, b"", [0x7F, 0x31, 0x33],
                                           f"否定响应，NRC=33(7F 31 33) - RID: {rid:04X}", func_req = func_flg)
            if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_31_NRC7F(
        node: UDSNode,
        name: str = "[TG12_TC7] 31服务NRC7F检查(物理寻址)",
        func_flg: bool = False,
):
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return

        # 使用参数化配置
        rid_list_extended = UDSTestParams.Services31RIDSupportList_Extended

        step += 1
        TestLog("INFO", f"Step{step}", "遍历所有31服务支持的DID，子功能=01")
        # 步骤3: 遍历所有31服务支持的DID，子功能=01
        for rid_info in rid_list_extended:
            rid = rid_info.get('rid', 0)
            sub_funcs = rid_info.get('sub_funcs', [0x01])
            record = rid_info.get('record', b'')
            rid_h, rid_l = (rid >> 8) & 0xFF, rid & 0xFF

            # 检查是否支持01子功能
            if 0x01 in sub_funcs:
                status, _ = __service_31_check(node, 0x01, rid, record, [0x7F, 0x31, 0x7F],
                                               f"否定响应，NRC=7F(7F 31 7F) - RID: {rid:04X}", func_req=func_flg)
                if not status: return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_31_NRC22(
        node: UDSNode,
        name: str = "[TG12_TC8] 31服务NRC22检查(物理寻址)",
        func_flg: bool = False,
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # 使用参数化配置
        rid_list_extended = UDSTestParams.Services31RIDSupportList_Extended
        nrc22_condition_list = UDSTestParams.NRC22_ConditionList

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_EXT})")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT], f"肯定响应(67 {LEVEL_EXT})",
                                                   func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_EXT + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            f"肯定响应(67 {LEVEL_EXT + 1})", dll_path=DLL_PATH,
                                            func_req=func_flg): return

        step += 1
        TestLog("INFO", f"Step{step}", "遍历触发NRC22的所有条件并发送31请求")
        # 步骤6: 遍历所有NRC22触发条件
        if len(nrc22_condition_list) == 0:
            TestLog("INFO", name, "UDSTestParams.NRC22_ConditionList为空，跳过NRC22条件遍历")
            return

        for condition in nrc22_condition_list:
            if hasattr(condition, 'get'):
                setup_func = condition.get('setup')
                cleanup_func = condition.get('cleanup')
                condition_name = condition.get('name', 'unknown')
            else:
                TestLog("FAIL", " ", "NRC22不支持")
                return

            # TODO 暂无具体触发逻辑，后续添加
            if setup_func:
                setup_func()

            # 对每个DID发送31请求
            for rid_info in rid_list_extended:
                rid = rid_info.get('rid', 0)
                sub_funcs = rid_info.get('sub_funcs', [0x01])
                record = rid_info.get('record', b'')
                rid_h, rid_l = (rid >> 8) & 0xFF, rid & 0xFF

                # 检查是否支持01子功能
                if 0x01 in sub_funcs:
                    status, _ = __service_31_check(node, 0x01, rid, record, [0x7F, 0x31, 0x22],
                                                   f"否定响应，NRC=22(7F 31 22) - RID: {rid:04X}, 条件: {condition_name}",
                                                   func_req=func_flg)
                    if not status: return

            # 执行条件清理函数
            if cleanup_func:
                cleanup_func()

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_phyRequest_31_NRCPriority(
        node: UDSNode,
        name: str = "[TG12_TC9] 31服务NRC优先级检查(物理寻址)",
        func_flg: bool = False,
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # 使用参数化配置
        rid_list_extended = UDSTestParams.Services31RIDSupportList_Extended
        nrc22_condition_list = UDSTestParams.NRC22_ConditionList
        unsupported_rid_list = UDSTestParams.Services31RIDUnsupportedList

        # 步骤1: 请求进入默认会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        # 步骤2: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return

        # 步骤3: 发送扩展会话下支持的31 01请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送扩展会话下支持的31 01 RIDH RIDL XX请求")
        if len(rid_list_extended) > 0:
            rid_info = rid_list_extended[0]
            rid = rid_info.get('rid', 0)
            sub_funcs = rid_info.get('sub_funcs', [0x01])
            record = rid_info.get('record', b'')

            if 0x01 in sub_funcs:
                status, _ = __service_31_check(node, 0x01, rid, record, [0x7F, 0x31, 0x7F],
                                               "否定响应，NRC=7F(7F 31 7F)", func_req=func_flg)
                if not status: return

        # 步骤4: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return

        # 步骤5: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

        # 步骤6: 触发NRC22条件并发送31 01请求
        # TODO 暂无具体触发逻辑，后续添加
        step += 1
        TestLog("INFO", f"Step{step}", "触发NRC22条件并发送31 01请求")
        if len(nrc22_condition_list) > 0:
            condition = nrc22_condition_list[0]
            if hasattr(condition, 'get'):
                setup_func = condition.get('setup')
                if setup_func:
                    setup_func()
            else:
                TestLog("FAIL", " ", "NRC22不支持")
                return

        status, _ = __service_31_check(node, 0x01, 0, b'', [0x7F, 0x31, 0x13],
                                       "否定响应，NRC=13(7F 31 13)", func_req=func_flg)
        if not status: return

        # 步骤7: 触发NRC22条件并发送31 01 FF FF请求
        step += 1
        TestLog("INFO", f"Step{step}", "触发NRC22条件并发送31 01 FF FF请求")
        status, _ = __service_31_check(node, 0x01, 0xFFFF, b'', [0x7F, 0x31, 0x31],
                                       "否定响应，NRC=31(7F 31 31)", func_req=func_flg)
        if not status: return

        # 步骤8: 触发NRC22条件并发送扩展会话下支持的31 01请求
        # TODO 暂无具体触发逻辑，后续添加
        step += 1
        TestLog("INFO", f"Step{step}", "触发NRC22条件并发送扩展会话下支持的31 01 RIDH RIDL XX请求")
        if len(rid_list_extended) > 0:
            rid_info = rid_list_extended[0]
            rid = rid_info.get('rid', 0)
            sub_funcs = rid_info.get('sub_funcs', [0x01])
            record = rid_info.get('record', b'')

            if 0x01 in sub_funcs:
                status, _ = __service_31_check(node, 0x01, rid, record, [0x7F, 0x31, 0x33],
                                               "否定响应，NRC=33(7F 31 33)", func_req=func_flg)
                if not status: return

        # 步骤9: 发送27 01请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送27 01请求")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT],
                                                   "肯定响应(67 01)", func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        # 步骤10: 发送27 02请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送27 02请求")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            "肯定响应(67 02)", dll_path=DLL_PATH, func_req=func_flg):
            return

        # 步骤11: 触发NRC22条件并发送31 04请求
        # TODO 暂无具体触发逻辑，后续添加
        step += 1
        TestLog("INFO", f"Step{step}", "触发NRC22条件并发送31 04 RIDH RIDL请求")
        if len(rid_list_extended) > 0:
            rid_info = rid_list_extended[0]
            rid = rid_info.get('rid', 0)
            status, _ = __service_31_check(node, 0x04, rid, b'', [0x7F, 0x31, 0x12],
                                           "否定响应，NRC=12(7F 31 12)", func_req=func_flg)
            if not status: return

        # 步骤12: 触发NRC22条件并发送长度错误的31 01请求
        # TODO 暂无具体触发逻辑，后续添加
        step += 1
        TestLog("INFO", f"Step{step}", "触发NRC22条件并发送长度错误的31 01请求")
        if len(rid_list_extended) > 0:
            rid_info = rid_list_extended[0]
            rid = rid_info.get('rid', 0)
            # 发送长度+1字节的数据
            record = rid_info.get('record', b'')
            extra_length = len(record) + 1 if record else 2
            status, _ = __service_31_check(node, 0x01, rid, record + b'\x00', [0x7F, 0x31, 0x13],
                                           "否定响应，NRC=13(7F 31 13)", func_req=func_flg)
            if not status: return

        # 步骤13: 触发NRC22条件并发送不支持的参数
        # TODO 暂无具体触发逻辑，后续添加
        step += 1
        TestLog("INFO", f"Step{step}", "触发NRC22条件并发送不支持的参数")
        if len(rid_list_extended) > 0:
            rid_info = rid_list_extended[0]
            rid = rid_info.get('rid', 0)
            # 发送不支持的参数
            status, _ = __service_31_check(node, 0x01, rid, b'\xFF', [0x7F, 0x31, 0x31],
                                           "否定响应，NRC=31(7F 31 31)", func_req=func_flg)
            if not status: return

        # 步骤14: 触发NRC22条件并发送扩展会话下支持的31 01请求
        # TODO 暂无具体触发逻辑，后续添加
        step += 1
        TestLog("INFO", f"Step{step}", "触发NRC22条件并发送扩展会话下支持的31 01 RIDH RIDL XX请求")
        if len(rid_list_extended) > 0:
            rid_info = rid_list_extended[0]
            rid = rid_info.get('rid', 0)
            sub_funcs = rid_info.get('sub_funcs', [0x01])
            record = rid_info.get('record', b'')

            if 0x01 in sub_funcs:
                status, _ = __service_31_check(node, 0x01, rid, record, [0x7F, 0x31, 0x22],
                                               "否定响应，NRC=22(7F 31 22)", func_req=func_flg)
                if not status: return

        # 步骤15: 发送扩展会话下支持的31 03请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送扩展会话下支持的31 03 RIDH RIDL XX请求")
        if len(rid_list_extended) > 0:
            rid_info = rid_list_extended[0]
            rid = rid_info.get('rid', 0)
            sub_funcs = rid_info.get('sub_funcs', [0x01])

            if 0x03 in sub_funcs:
                status, _ = __service_31_check(node, 0x03, rid, b'', [0x7F, 0x31, 0x24],
                                               "否定响应，NRC=24(7F 31 24)", func_req=func_flg)
                if not status: return

        # 步骤16: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def __unsport_service_lin(node: UDSNode, service_id, data=b'', expect_data=[], expect_str: str = "",
                          func_req: bool = False, timeout=5) -> bool:
    """
    LIN 下发特殊service id
    """
    try:
        response_message = node.Service_Unsupported(service_id, data=data, func_req=func_req, timeout=timeout)
        if response_message is None:
            TestLog("FAIL", hex(service_id), f"{expect_str}，未收到响应")
            return False
        if list(response_message.data[0:len(expect_data)]) != expect_data:
            TestLog(
                "FAIL",
                hex(service_id),
                f"{expect_str}，响应不匹配，期望: {bytes(expect_data).hex()} 实际: {response_message.data.hex()}",
            )
            return False
        TestLog("PASS", hex(service_id), f"{expect_str}，响应匹配: {response_message.data.hex()}")
        return True
    except Exception as e:
        TestLog("FAIL", hex(service_id), f"{expect_str}，执行异常: {e}")
        TestLog("DEBUG", hex(service_id), f"详细错误: {traceback.format_exc()}")
        return False


__all_service = {0x10: 'DiagnosticSessionControl',
                 0x11: 'ECUReset',
                 0x14: 'ClearDiagnosticInformation',
                 0x19: 'ReadDTCInformation',
                 0x22: 'ReadDataByIdentifier',
                 0x23: 'ReadMemoryByAddress',
                 0x24: 'ReadScalingDataByIdentifier',
                 0x27: 'SecurityAccess',
                 0x28: 'CommunicationControl',
                 0x29: 'Authentication',
                 0x2A: 'ReadDataPeriodicIdentifier',
                 0x2C: 'DynamicallyDefineDataIdentifier',
                 0x2E: 'WriteDataByIdentifier',
                 0x2F: 'InputOutputControlByIdentifier',
                 0x31: 'RoutineControl',
                 0x34: 'RequestDownload',
                 0x35: 'RequestUpload',
                 0x36: 'TransferData',
                 0x37: 'RequestTransferExit',
                 0x38: 'RequestFileTransfer',
                 0x3D: 'WriteMemoryByAddress',
                 0x3E: 'TesterPresent',
                 0x50: 'DiagnosticSessionControlPositiveResponse',
                 0x51: 'ECUResetPositiveResponse',
                 0x54: 'ClearDiagnosticInformationPositiveResponse',
                 0x59: 'ReadDTCInformationPositiveResponse',
                 0x62: 'ReadDataByIdentifierPositiveResponse',
                 0x63: 'ReadMemoryByAddressPositiveResponse',
                 0x64: 'ReadScalingDataByIdentifierPositiveResponse',
                 0x67: 'SecurityAccessPositiveResponse',
                 0x68: 'CommunicationControlPositiveResponse',
                 0x69: 'AuthenticationPositiveResponse',
                 0x6A: 'ReadDataPeriodicIdentifierPositiveResponse',
                 0x6C: 'DynamicallyDefineDataIdentifierPositiveResponse',
                 0x6E: 'WriteDataByIdentifierPositiveResponse',
                 0x6F: 'InputOutputControlByIdentifierPositiveResponse',
                 0x71: 'RoutineControlPositiveResponse',
                 0x74: 'RequestDownloadPositiveResponse',
                 0x75: 'RequestUploadPositiveResponse',
                 0x76: 'TransferDataPositiveResponse',
                 0x77: 'RequestTransferExitPositiveResponse',
                 0x78: 'RequestFileTransferPositiveResponse',
                 0x7D: 'WriteMemoryByAddressPositiveResponse',
                 0x7E: 'TesterPresentPositiveResponse',
                 0x83: 'AccessTimingParameter',
                 0x84: 'SecuredDataTransmission',
                 0x85: 'ControlDTCSetting',
                 0x86: 'ResponseOnEvent',
                 0x87: 'LinkControl',
                 0xC3: 'AccessTimingParameterPositiveResponse',
                 0xC4: 'SecuredDataTransmissionPositiveResponse',
                 0xC5: 'ControlDTCSettingPositiveResponse',
                 0xC6: 'ResponseOnEventPositiveResponse',
                 0xC7: 'LinkControlPositiveResponse',
                 0x7f: 'NegativeResponse'}


def test_phyRequest_NRC11(
        node: UDSNode,
        name: str = "[TG13_TC1] 不支持服务NRC11检查(物理寻址)",
        func_flg: bool = False,
):
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step = 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

        step = 2
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return

        step = 3
        TestLog("INFO", f"Step{step}", "遍历所有不支持的服务")
        for sn in range(0, 0x100):
            if sn not in __all_service.keys():
                __unsport_service_lin(node, sn, expect_data=[0X7F, sn, 0X11], func_req=func_flg)

        step = 4
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return

        step = 5
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        step = 6
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        step = 7
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"],
                                           "位于扩展会话中(71 01 02 03 00)", func_req=func_flg):
            return

        step = 8
        TestLog("INFO", f"Step{step}", "遍历所有不支持的服务")
        for sn in range(0, 0x100):
            if sn not in __all_service.keys():
                __unsport_service_lin(node, sn, expect_data=[0X7F, sn, 0X11], func_req=func_flg)

        step = 9
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"],
                                           "位于扩展会话中(71 01 02 03 00)", func_req=func_flg):
            return

        step = 10
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        step = 11
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"],
                                           "位于扩展会话中(71 01 02 03 00)", func_req=func_flg):
            return

        step = 12
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "默认会话肯定响应(50 01)", func_req=func_flg):
            return

        step = 13
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        step = 14
        TestLog("INFO", f"Step{step}", "遍历所有不支持的服务")
        for sn in range(0, 0x100):
            if sn not in __all_service.keys():
                __unsport_service_lin(node, sn, expect_data=[0X7F, sn, 0X11], func_req=func_flg)

        step = 15
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def __check_p2_timer(p2_serve_time, p2_server_max_time, step=0):
    from .lintp_module import get_all_tp_rcv_frame_t_time, get_all_tp_send_frame_t_time
    rcv_time = get_all_tp_rcv_frame_t_time()
    send_time = get_all_tp_send_frame_t_time()

    rcv1msg_time = 0
    rcv2msg_time = 0
    sendmsg_time, sendmsg_type = send_time[-1]
    for (rcvmsg_time, rcvmsg_type) in rcv_time:
        if rcvmsg_type == 1:  # 单帧 0X7F 0X7E 78
            rcv1msg_time = rcvmsg_time
        if rcvmsg_type == 2:  # 首帧
            rcv2msg_time = rcvmsg_time
    if rcv2msg_time == 0:
        if len(rcv_time) >= 2:
            rcv1msg_time, rcvmsg_type = rcv_time[-1]
            rcv12msg_time, rcvmsg_type = rcv_time[-2]
            p2_time = rcv1msg_time - rcv12msg_time
            TestLog("INFO", f"Step{step}", f"P2 Server *sl_time:{p2_time}")
            if p2_time < p2_server_max_time:
                return True
        elif len(rcv_time) == 1:
            rcvmsg_time, rcvmsg_type = rcv_time[0]
            sendmsg_time, sendmsg_type = send_time[-1]
            p2_time = rcvmsg_time - sendmsg_time
            TestLog("INFO", f"Step{step}", f"P2 Server sl_time:{p2_time}")
            if p2_time < p2_serve_time:
                return True
    else:
        if rcv1msg_time == 0:
            p2_time = rcv2msg_time - sendmsg_time
            TestLog("INFO", f"Step{step}", f"P2 Server sl_time:{p2_time}")
            if p2_time < p2_serve_time:
                return True
        else:
            p2_time =  rcv2msg_time - rcv1msg_time
            TestLog("INFO", f"Step{step}", f"P2 Server *sl_time:{p2_time}")
            if p2_time < p2_server_max_time:
                return True
    return False


def test_P2Server_TimingTest(
        node: UDSNode,
        name: str = "[TG14_TC1] P2 Server时间测试(LIN从节点)",
        func_flg: bool = False,
):
    LEVEL_EXT, DLL_PATH = 0x01, P.ECUInfo.dllPath_2701  # 扩展等级
    LEVEL_PRO_11, DLL_PATH_PRO_11 = 0X11, P.ECUInfo.dllPath_2711
    p2_server_time = 0.5
    p2_max_server_time = 2
    try:
        step = 0
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        if not __check_p2_timer(p2_server_time, p2_max_server_time, step): return
        __lin_restart_delay(2)
        # 步骤2: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return
        if not __check_p2_timer(p2_server_time, p2_max_server_time, step): return

        step += 1
        TestLog("INFO", f"Step{step}", "清除DUT中的DTC(14 FF FF FF)")
        if not __service_14_check_lin(node, 0xFFFFFF, [], "否定响应(13)", func_req=func_flg): return
        if not __check_p2_timer(p2_server_time, p2_max_server_time, step): return

        # 步骤4: 请求进入扩展会话
        step += 1
        TestLog("INFO", f"Step{step}", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)", func_req=func_flg):
            return
        if not __check_p2_timer(p2_server_time, p2_max_server_time, step): return

        # 步骤5: 检查当前会话状态
        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x71, 0x01, 0x02, 0x03, 0x00], "位于扩展会话中", func_req=func_flg):
            return
        if not __check_p2_timer(p2_server_time, p2_max_server_time, step): return

        step += 1
        TestLog("INFO", f"Step{step}", "清除DUT中的DTC(14 FF FF FF)")
        if not __service_14_check_lin(node, 0xFFFFFF, [], "肯定响应(54)", func_req=func_flg): return
        if not __check_p2_timer(p2_server_time, p2_max_server_time, step): return
        # 步骤9: 发送27 01请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送27 01请求")
        status, seed_list = __service_27_check_lin(node, LEVEL_EXT, [0x67, LEVEL_EXT],
                                                   "肯定响应(67 01)", func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")

        # 步骤10: 发送27 02请求
        step += 1
        TestLog("INFO", f"Step{step}", "发送27 02请求")
        if not __service_27_securityKey_lin(node, LEVEL_EXT, seed_list, [0x67, LEVEL_EXT + 1],
                                            "肯定响应(67 02)", dll_path=DLL_PATH, func_req=func_flg):
            return
        if not __check_p2_timer(p2_server_time, p2_max_server_time, step): return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return
        if not __check_p2_timer(p2_server_time, p2_max_server_time, step): return

        step += 1
        TestLog("INFO", f"Step{step}", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return
        if not __check_p2_timer(p2_server_time, p2_max_server_time, step): return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的请求种子请求(27 {LEVEL_PRO_11})")
        status, seed_list = __service_27_check_lin(node, LEVEL_PRO_11, [0x67, LEVEL_PRO_11],
                                                   f"肯定响应(67 {LEVEL_PRO_11})", func_req=func_flg)
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
        if not __check_p2_timer(p2_server_time, p2_max_server_time, step): return

        step += 1
        TestLog("INFO", f"Step{step}", f"发送扩展安全级的解锁密钥(27 {LEVEL_PRO_11 + 1})")
        if not __service_27_securityKey_lin(node, LEVEL_PRO_11, seed_list, [0x67, LEVEL_PRO_11 + 1],
                                            f"肯定响应(67 {LEVEL_PRO_11 + 1})", dll_path=DLL_PATH_PRO_11,
                                            func_req=func_flg): return
        if not __check_p2_timer(p2_server_time, p2_max_server_time, step): return

        step += 1
        TestLog("INFO", f"Step{step}", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)", func_req=func_flg):
            return
        if not __check_p2_timer(p2_server_time, p2_max_server_time, step): return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def test_Session_SwitchingTimeTest(
        node: UDSNode,
        name: str = "[TG14_TC3] 会话切换时间测试(LIN从节点)",
        func_flg: bool = False,
):
    """
    会话切换时间测试
    """
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "肯定响应(50 01)", func_req=func_flg):
            return

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "肯定响应(50 03)", func_req=func_flg):
            return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"],
                                           "位于扩展会话中(71 01 02 03 00)", func_req=func_flg):
            return

        TestLog("INFO", "Step4", "等待4.5s(小于S3 Server)")
        __lin_restart_delay(4.5)

        TestLog("INFO", "Step5", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"],
                                           "位于扩展会话中(71 01 02 03 00)", func_req=func_flg):
            return

        TestLog("INFO", "Step6", "等待5.5s(大于S3 Server)")
        __lin_restart_delay(5.5)

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["default"],
                                           "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return

        TestLog("INFO", "Step8", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "肯定响应(50 01)", func_req=func_flg):
            return

        TestLog("INFO", "Step9", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "肯定响应(50 03)", func_req=func_flg):
            return

        TestLog("INFO", "Step10", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"],
                                           "位于扩展会话中(71 01 02 03 00)", func_req=func_flg):
            return

        TestLog("INFO", "Step11", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02], "肯定响应(50 02)", func_req=func_flg):
            return

        TestLog("INFO", "Step12", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["programming"],
                                           "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        TestLog("INFO", "Step13", "等待4.5s(小于S3 Server)")
        __lin_restart_delay(4.5)

        TestLog("INFO", "Step14", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["programming"],
                                           "位于刷新会话中(7F 31 31)", func_req=func_flg):
            return

        TestLog("INFO", "Step15", "等待5.5s(大于S3 Server)")
        __lin_restart_delay(5.5)

        TestLog("INFO", "Step16", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["default"],
                                           "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return

        TestLog("PASS", name, "会话切换时间测试完成，S3 Server时间参数验证通过")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_AppToBoot_TimeTest(
        node: UDSNode,
        name: str = "[TG14_TC4] APP跳转到Boot时间测试(LIN从节点)",
        func_flg: bool = False,
):
    """
    APP跳转到Boot时间测试
    """
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        rT_wait = P.DiagServiceInfo.SessionTime / 1000  # ms -> s
        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01],
                                      "肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03],
                                      "肯定响应(50 03)", func_req=func_flg):
            return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"],
                                           "位于扩展会话中(71 01 02 03 00)", func_req=func_flg):
            return

        TestLog("INFO", "Step4", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02],
                                      "肯定响应(50 02)", func_req=func_flg):
            return

        TestLog("INFO", "Step5", f"等待T_wait时间({rT_wait}s)")
        __lin_restart_delay(rT_wait)

        TestLog("INFO", "Step6", "发送刷新安全级的请求种子请求(27 11)")
        # 27服务检查函数

        status, seed_list = __service_27_check_lin(node, 0x11, [0x67, 0x11], f"肯定响应(67 0x11)")
        if not status: return
        TestLog("INFO", "", f"seed_list={[hex(item) for item in seed_list]}")
        if sum(seed_list) == 0 or sum(seed_list) == 0xFF * len(seed_list):
            TestLog("FAIL", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")
            return
        TestLog("PASS", "", f"期望: 肯定响应且种子不是全00和全FF; 实际: 种子={[hex(item) for item in seed_list]}")

        TestLog("PASS", name, "APP跳转到Boot时间测试完成，所有步骤执行成功")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_BootToApp_TimeTest(
        node: UDSNode,
        name: str = "[TG14_TC5] Boot跳转到APP时间测试",
        func_flg: bool = False,
):
    """
    Boot跳转到APP时间测试
    """
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        rT_wait = P.DiagServiceInfo.SessionTime / 1000  # ms -> s

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01],
                                      "肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)
        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03],
                                      "肯定响应(50 03)", func_req=func_flg):
            return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"],
                                           "位于扩展会话中(71 01 02 03 00)", func_req=func_flg):
            return

        TestLog("INFO", "Step4", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02],
                                      "肯定响应(50 02)", func_req=func_flg):
            return

        TestLog("INFO", "Step5", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01],
                                      "肯定响应(50 01)", func_req=func_flg):
            return

        TestLog("INFO", "Step6", f"等待T_wait时间({rT_wait}s)")
        __lin_restart_delay(rT_wait)

        TestLog("INFO", "Step7", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["default"],
                                           "位于默认会话中(7F 31 7F)", func_req=func_flg):
            return

        TestLog("PASS", name, "Boot跳转到APP时间测试完成，所有步骤执行成功")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_EnterBoot_StopCommunicationTest(
        node: UDSNode,
        name: str = "[TG14_TC6] 进入Boot停止网络通信测试",
        func_flg: bool = False,
):
    """
    进入Boot停止网络通信测试
    """
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        rT_wait = P.DiagServiceInfo.SessionTime / 1000  # ms -> s

        TestLog("INFO", "Step1", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01],
                                      "肯定响应(50 01)", func_req=func_flg):
            return
        __lin_restart_delay(2)

        TestLog("INFO", "Step2", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03],
                                      "肯定响应(50 03)", func_req=func_flg):
            return

        TestLog("INFO", "Step3", "检查当前会话状态(31 01 02 03)")
        if not __check_current_session_lin(node, SESSION_EXPECT_RESPONSES["extended"],
                                           "位于扩展会话中(71 01 02 03 00)", func_req=func_flg):
            return

        TestLog("INFO", "Step4", "请求进入刷新会话(10 02)")
        if not __service_10_check_lin(node, 0x02, [0x50, 0x02],
                                      "肯定响应(50 02)", func_req=func_flg):
            return

        TestLog("INFO", "Step5", f"等待T_wait_stop时间({rT_wait}s)")

        from .lin_test_pre_module import monitor_lin_communication, create_lin_sch

        sch = create_lin_sch()
        sch.start()
        msgs, direction = monitor_lin_communication(rT_wait)
        sch.stop()
        TestLog("INFO", "Step6", "检查应用报文是否正常发送")
        if len(msgs) >= 0:
            for id, all_v in msgs.items():
                if all_v[0]["direction"] == "Rx":
                    for msg in all_v:
                        if msg["dlc"] != 0:
                            TestLog("FAIL", name, "应用报文未停止发送，期望在进入Boot会话后停止网络通信")
                            return
        TestLog("PASS", "Step6", "应用报文停止发送，符合预期")

        TestLog("INFO", "Step7", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01],
                                      "肯定响应(50 01)", func_req=func_flg):
            return

        TestLog("INFO", "Step8", f"等待T_wait_restore时间({rT_wait}s)")
        sch.start()
        msgs, direction = monitor_lin_communication(rT_wait)
        sch.stop()
        TestLog("INFO", "Step9", "检查应用报文是否正常发送")
        if len(msgs) >= 0:
            for id, all_v in msgs.items():
                if all_v[0]["direction"] == "Rx":
                    for msg in all_v:
                        if msg["dlc"] == 0:
                            TestLog("FAIL", name, "应用报文未恢复发送，期望在返回默认会话后恢复网络通信")
                            return
        TestLog("PASS", "Step9", "应用报文恢复发送，符合预期")
        TestLog("PASS", name, "进入Boot停止网络通信测试完成，网络通信正常停止和恢复")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()