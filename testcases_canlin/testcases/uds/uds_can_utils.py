import threading
import time
import queue
from can import Message

from library.uds.uds_node import UDSNode
from library.uds.bus_sim import BusSim
from slplus.cantp import sl_cantp
from uvtest.testlog import TestLog
from env.config import DEFAULT_CAN_CHANNELS
from common.params import P
from common.context import ctx
from library.security.security import Seed2Key


class UDSConst:
    HardReset = 0x01  # 硬复位
    KeyOffOnReset = 0x02  # 关钥匙复位
    SoftReset = 0x03  # 软复位
    SuppressBit = 0x80


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
    ServicesSupportedList = [0x10, 0x11, 0x14, 0x19, 0x22, 0x27, 0x28, 0x2E, 0x2F, 0x31, 0x34, 0x35, 0x36, 0x37, 0x3E, 0x85]
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
    Services2FControlParam01DIDList = []
    Services2FControlParam02DIDList = []
    Services2FControlParam03DIDList = []
    # RoutineDIDs Sheet
    Services31RIDSupportList_Extended = []
    Services31RIDSupportList_Programming = []
    Services31RIDSecurityRequiredList = []
    # Conditions Sheet
    NRC22_ConditionList = []

    @classmethod
    def get_nrc22_conditions_for_service(cls, service_id: int):
        def _token_matches(token, sid: int) -> bool:
            if isinstance(token, int):
                return token == sid
            text = str(token).strip()
            if not text:
                return False
            try:
                if text.lower().startswith("0x"):
                    return int(text[2:], 16) == sid
                return int(text, 16) == sid or int(text, 10) == sid
            except ValueError:
                return False

        condition_list = []
        for condition in cls.NRC22_ConditionList:
            services = getattr(condition, "SupportServices", [])

            if isinstance(services, (list, tuple, set)):
                service_tokens = list(services)
            else:
                service_tokens = str(services).replace("，", ",").replace(";", ",").split(",")
            for token in service_tokens:
                if _token_matches(token, service_id):
                    condition_list.append(condition)
                    break
        return condition_list

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
            cls.Services22DIDSupportList_Programming = [i.DID_int for i in P.ReadDIDs if i.DID != "EOF" and i.Support_Boot]
            cls.Services22DIDSecurityRequiredList = [i.DID_int for i in P.ReadDIDs if i.DID != "EOF" and i.SecurityUnlock]

            cls.Services2EDIDSupportListDefault = [i.DID_int for i in P.WriteDIDs if i.DID != "EOF" and i.Support_App]
            cls.Services2EDIDSupportListExtend = cls.Services2EDIDSupportListDefault.copy()
            cls.Services2EDIDSupportListProgramming = [i.DID_int for i in P.WriteDIDs if i.DID != "EOF" and i.Support_Boot]
            cls.Services2EDIDNeedUnlockSupportList = [i.DID_int for i in P.WriteDIDs if i.DID != "EOF" and i.SecurityUnlock]

            # 2F 服务
            cls._load_control_dids()
            # 31 服务
            cls._load_routine_dids()
            # 条件：只加载具备信号仿真必要字段的条件，避免占位空配置导致 NRC22 用例误执行
            condition_items = []
            for item in P.Conditions:
                if item.is_eof:
                    continue
                if not getattr(item, "IsSignalConditionConfigured", False):
                    TestLog("WARNING", "NRC22条件", f"{item.ConditionName} 配置不完整，未加入NRC22条件列表")
                    continue
                condition_items.append(item)
            cls.NRC22_ConditionList = condition_items

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
        cls.Services2FControlParam01DIDList = []
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
                cls.Services2FControlParam01DIDList.append(item.DID_int)
            if item.ControlOption_02:
                params.append(0x02)
                cls.Services2FControlParam02DIDList.append(item.DID_int)
            if item.ControlOption_03:
                params.append(0x03)
                cls.Services2FControlParam03DIDList.append(item.DID_int)

            cls.Services2FDIDSupportList.append({'did': item.DID_int, 'control_params': params, 'need_security': item.SecurityUnlock})
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


class CANBusSim(BusSim):
    def __init__(self):
        self._busid = None
        self._sa = None
        self._ta = None
        self._fa = None
        self._is_canfd = False
        self._recv_queue = queue.Queue()
        self._cantp = None

    @property
    def tx_id(self) -> int:
        return self._sa

    @property
    def rx_id(self) -> int:
        return self._ta

    @property
    def func_id(self) -> int:
        return self._fa

    @property
    def is_canfd(self) -> bool:
        return self._is_canfd

    def init(self, busid: int, sa: int, ta: int, fa: int, is_canfd: bool = False, config: dict = None):
        self._busid = busid
        self._sa = sa
        self._ta = ta
        self._fa = fa
        self._is_canfd = is_canfd

        def on_error(tpid, err):
            TestLog("ERROR", "BusSim", f"CANTP错误 tpid:{tpid}, err:{err}")
            return 0

        def on_notify(tpid, event):
            return 0

        def on_recv(tpid, is_func, data, user_data):
            if data is None or len(data) == 0:
                return 0
            # TestLog("INFO", "BusSim", f"收到数据: {data.hex()}")
            self._recv_queue.put((is_func, data))
            return 0

        callbacks = {
            "on_error": on_error,
            "on_notify": on_notify,
            "on_recv": on_recv,
        }

        self._cantp = sl_cantp(
            busid=self._busid,
            role=sl_cantp.Role.REQUESTER,
            reqid=self._sa,
            funcid=self._fa,
            rspid=self._ta,
            callbacks=callbacks
        )

        if self._cantp is None:
            TestLog("ERROR", "BusSim", "CANTP 创建失败")
            return

        cfg = self._build_config(config)
        if not self._cantp.set_config(cfg):
            TestLog("ERROR", "BusSim", "CANTP 配置失败")
            return

        if not self._cantp.active():
            TestLog("ERROR", "BusSim", "CANTP 激活失败")
            return

        TestLog("INFO", "BusSim", f"CANTP 初始化成功 (sa=0x{self._sa:X}, ta=0x{self._ta:X}, fa=0x{self._fa:X})")

    def _build_config(self, custom_config: dict = None) -> dict:
        tp = P.TpInfo

        cfg = {
            "trans": {
                "fdf": tp.CanFDMode if self._is_canfd else False,
                "brs": False,
                "padflg": True,
                "padval": tp.Can_Padding_Byte,
                "mpl": 4095,
                "mtu": tp.MaxCanFDDataLength if self._is_canfd else tp.Cantp_dlc,
            },
            "fc": {
                "fc_flag": True,
                "blocksize_flag": True,
                "stmin_flag": True,
                "block_size": 0,
                "stmin_lowth": 0,
                "stmin": tp.STmin_Client,
                "fc_delay": 1,
                "wftmax": 3,
            },
            "timing": {
                "as": tp.N_AsTimeout,
                "ar": tp.N_ArTimeout,
                "bs": tp.N_BsTimeout,
                "br": tp.N_Ar_BrTiming,
                "cs": tp.N_Cs_AsTiming,
                "cr": tp.N_CrTimeout,
            }
        }

        if custom_config:
            for key in ["trans", "fc", "timing"]:
                if key in custom_config:
                    cfg[key].update(custom_config[key])

        return cfg

    def send(self, data: bytes, func_req: bool = False):
        if self._cantp is None:
            TestLog("ERROR", "BusSim", "CANTP 未初始化，发送失败")
            return

        tx_id = self._fa if func_req else self._sa
        # TestLog("INFO", "BusSim", f"发送数据: ID=0x{tx_id:X}, data={data.hex()}, func={func_req}")
        self._cantp.send(func_req, data)

    def recv(self, timeout=10):
        try:
            is_func, data = self._recv_queue.get(timeout=timeout)
            msg = Message(
                arbitration_id=self._ta,
                data=data,
                dlc=len(data),
                is_extended_id=False
            )
            return True, msg
        except queue.Empty:
            TestLog("WARNING", "BusSim", f"接收超时 ({timeout}s)")
            return False, None

    def close(self):
        if self._cantp is not None:
            self._cantp.destroy()
            self._cantp = None
            TestLog("INFO", "BusSim", "CANTP 已关闭")


_can_node: UDSNode = None


def get_can_node(sa, ta, fa, is_canfd=False) -> UDSNode:
    global _can_node
    close_can_node()
    bus_obj = CANBusSim()
    bus_obj.init(DEFAULT_CAN_CHANNELS[0], sa, ta, fa, is_canfd)
    _can_node = UDSNode(bus_obj)
    return _can_node


def close_can_node():
    global _can_node
    if _can_node:
        try:
            _can_node.bus.close()
        except Exception:
            pass
        _can_node = None


def check_expect_response(response_message, expect_data: list) -> tuple[bool, str]:
    response_data = _response_bytes(response_message)
    if not response_data:
        return False, "未检测到有效响应数据"

    expect = bytes(expect_data)
    expect_text = expect.hex(" ").upper()
    actual_text = response_data.hex(" ").upper()
    if expect in response_data:
        return True, f"检测到期望响应报文, 期望={expect_text}, 实际={actual_text}"

    return False, f"非期望响应报文, 期望={expect_text}, 实际={actual_text}"


def _response_bytes(response_message):
    if response_message is None or response_message == b'':
        return None
    response_data = getattr(response_message, "data", response_message)
    try:
        return bytes(response_data)
    except (TypeError, ValueError):
        return None


def _response_text(response_message):
    response_data = _response_bytes(response_message)
    if response_data is None:
        return "无响应"
    return response_data.hex(" ").upper()


def get_seed_from_27_resp(response_message: Message) -> list:
    response_data = list(response_message.data)
    return response_data[2:]

def get_dtc_from_19_resp(response_message: Message) -> list:
    response_data = list(response_message.data)
    return response_data[2:]

def get_info_from_22_resp(response_message: Message) -> list:
    response_data = list(response_message.data)
    return response_data[3:]

def calc_key_by_seed(level, seed: list, *args, **kwargs):
    # TODO 根据种子计算密钥
    return [0xB7, 0x7D, 0x86, 0x0E]


def service_10_check(node, session, expect_data, expect_str, func_req=False, *args, **kwargs):
    resp = node.Service_0x10_SessionControl(session, func_req=func_req, *args, **kwargs)
    pending_flag = False
    if expect_data is None:
        TestLog("INFO", "", f"{expect_data=}, {resp=}")
        if resp is None:
            return True  # 期望检测不到，实际也检测不到
        else:
            # 出现了78，继续检测正响应
            expect_data = [0x50, session & 0x7F]
            expect_str = "肯定响应"
            pending_flag = True

    status, msg = check_expect_response(resp, expect_data)
    if status is False:
        if pending_flag is True:
            TestLog("WARNING", "", f"期望: {expect_str}; 实际:{msg}")
            return True
        else:
            TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
            return False
    TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
    return True

def service_11_check(node, reset_type, expect_data, expect_str, func_req=False, dl=None, dl_padding=0x00, timeout=5, *args, **kwargs):
    resp = node.Service_0x11_ECUReset(reset_type, func_req=func_req, dl=dl, dl_padding=dl_padding, timeout=timeout, *args, **kwargs)

    if expect_data is None:
        if resp is None or resp == b'':
            TestLog("PASS", "", f"期望: {expect_str}; 实际:无响应")
            return True
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:收到响应 {_response_text(resp)}")
        return False

    status, msg = check_expect_response(resp, expect_data)
    if status is False:
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
        return False
    TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
    return True

def service_14_check(node, dtc, expect_data, expect_str, func_req=False, *args, **kwargs):
    if dtc is not None:
        h, m, l = (dtc >> 16 & 0xFF), (dtc >> 8 & 0xFF), dtc & 0xFF
        resp = node.Service_0x14_ClearDiagnosticInformation(h, m, l, func_req=func_req, *args, **kwargs)
    else:
        resp = node.Service_0x14_ClearDiagnosticInformation(None, None, None, func_req=func_req, *args, **kwargs)
    #responsedata = list(resp.data)
    if expect_data is None:
        if resp is None:
            return True, None  # 期望无响应，实际也无响应
        TestLog("FAIL", "", f"期望: {expect_str}; 实际: 收到响应 {_response_text(resp)}")
        return False, resp  # 期望无响应，实际收到响应

    status, msg = check_expect_response(resp, expect_data)
    if status is False:
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
        return False, resp
    TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
    return True, resp


def service_19_check(node, report_type, expect_data, expect_str, func_req=False, *args, **kwargs):
    resp = node.Service_0x19_ReadDTCInformation(report_type=report_type, func_req=func_req, *args, **kwargs)
    if expect_data is None:
        if resp is None or resp == b'':
            TestLog("PASS", "", f"期望: {expect_str}; 实际:无响应")
            return True, resp  # 期望检测不到，实际也检测不到
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:收到响应 {_response_text(resp)}")
        return False, resp  # 期望检测不到，实际检测到，

    status, msg = check_expect_response(resp, expect_data)
    if status is False:
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
        return False, ""
    TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
    return True, resp


def check_current_session(node, expect_data, expect_str):
    resp = node.Service_0x31_RoutineControl(0x01, 0x0203)
    status, msg = check_expect_response(resp, expect_data)
    if status is False:
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
        return False
    TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
    return True



def service_27_check(node, level, expect_data, expect_str, func_req=False, *args, **kwargs):
    resp = node.Service_0x27_SecurityAccess(level, func_req=func_req, *args, **kwargs)
    status, msg = check_expect_response(resp, expect_data)
    if status is False:
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
        return False, ""
    TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
    return True, resp


def service_2E_check(node, id, record=b"", expect_data=[], expect_str="", func_req=False, *args, **kwargs):
    resp = node.Service_0x2E_WriteDataByIdentifier(id, record, func_req=func_req, *args, **kwargs)
    status, msg = check_expect_response(resp, expect_data)
    if status is False:
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
        return False
    TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
    return True

class AlgorithmType:
    EXTENDED = "extended"  # 扩展安全级算法
    EXTENDED_ERROR = "extended_error"  # 错误的扩展安全级算法
    PROGRAMMING_ERROR = "programming_error"  # 错误的扩展安全级算法
    IMMOBILIZER = "immobilizer"  # 防盗安全级算法
    PROGRAMMING = "programming"  # 刷新安全级算法
    DIRECT2702 = "direct2702"  # 直接发送27 02时携带的key
    DIRECT2712 = "direct2712"  # 直接发送27 12时携带的key


def service_27_xx_check(node, level, seed_data, expect_data, expect_str, alg_type="", func_req=False):
    # TODO 实现不同算法
    if str(alg_type).lower() == AlgorithmType.EXTENDED:  # 扩展安全级算法
        key = Seed2Key(P.ECUInfo.dllPath_2701, seed_data)
    elif str(alg_type).lower() == AlgorithmType.EXTENDED_ERROR:  # 错误的扩展安全级算法
        key = Seed2Key(P.ECUInfo.dllPath_2701, seed_data)
        key[0] = (key[0] + 1) % 0xFF
    elif str(alg_type).lower() == AlgorithmType.IMMOBILIZER:  # 防盗安全级算法
        key = calc_key_by_seed(level, seed_data)
    elif str(alg_type).lower() == AlgorithmType.PROGRAMMING:  # 刷新安全级算法
        key = Seed2Key(P.ECUInfo.dllPath_2711, seed_data)
    elif str(alg_type).lower() == AlgorithmType.PROGRAMMING_ERROR:  # 错误的刷新安全级算法
        key = Seed2Key(P.ECUInfo.dllPath_2711, seed_data)
        key[0] = (key[0] + 1) % 0xFF
    elif str(alg_type).lower() == AlgorithmType.DIRECT2702:  # 直接发送27 02时携带的key
        key = calc_key_by_seed(level, seed_data)
    elif str(alg_type).lower() == AlgorithmType.DIRECT2712:  # 直接发送27 12时携带的key
        key = calc_key_by_seed(level, seed_data)
    else:
        TestLog("FAIL", "", f"未知的算法类型")
        return False

    resp = node.Service_0x27_SecurityAccess(level, seed_key=key, func_req=func_req)
    status, msg = check_expect_response(resp, expect_data)
    if status is False:
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
        return False
    TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
    return True

def service_28_check(node, control_type, comm_type, expect_data, expect_str, func_req=False, *args, **kwargs):
    resp = node.Service_0x28_CommunicationControl(control_type, comm_type, func_req=func_req, *args, **kwargs)
    if expect_data is None:
        if resp is None or resp == b'':
            TestLog("PASS", "", f"期望: {expect_str}; 实际:无响应")
            return True
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:收到响应")
        return False

    if isinstance(expect_data[0], list):
        for exp in expect_data:
            status, msg = check_expect_response(resp, exp)
            if status:
                TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
                return True
        _, msg = check_expect_response(resp, expect_data[0])
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
        return False
    else:
        status, msg = check_expect_response(resp, expect_data)
        if status is False:
            TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
            return False
        TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
        return True

def service_3E_check(node, subfunction, expect_data, expect_str, func_req=False, *args, **kwargs):
    resp = node.Service_0x3E_TesterPresent(subfunction, func_req=func_req, update_send_data=True, *args, **kwargs)
    if expect_data is None:
        if resp is None or resp == b'':
            TestLog("PASS", "", f"期望: {expect_str}; 实际:无响应")
            return True
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:收到响应")
        return False

    status, msg = check_expect_response(resp, expect_data)
    if status is False:
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
        return False
    TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
    return True
	
def service_85_check(node, dtc_setting_type, expect_data, expect_str, func_req=False, *args, **kwargs):
    resp = node.Service_0x85_ControlDTCSetting(dtc_setting_type, func_req=func_req, *args, **kwargs)
    if expect_data is None:
        if resp is None:
            return True  # 期望检测不到，实际也检测不到
        return False  # 期望检测不到，实际检测到，

    status, msg = check_expect_response(resp, expect_data)
    if status is False:
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
        return False
    TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
    return True
    
def service_22_check(node, dids, expect_data, expect_str, func_req=False, dl=None, dl_padding=0x00, timeout=5, *args, **kwargs):
    resp = node.Service_0x22_ReadDataByIdentifier(id=dids, func_req=func_req, dl=dl, dl_padding=dl_padding, timeout=timeout, *args, **kwargs)

    if expect_data is None:
        if resp is None:
            TestLog("PASS", "", f"期望: {expect_str}; 实际:无响应")
            return True, None  # 期望无响应，实际无响应
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:收到响应")
        return False, resp  # 期望无响应，实际有响应

    status, msg = check_expect_response(resp, expect_data)
    if status is False:
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
        return False, resp
    TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
    return True, resp

def service_2F_check(node, did, option, expect_data, expect_str, enable_mask=b"", func_req=False, *args, **kwargs):
    resp = node.Service_0x2F_InputOutputControlByIdentifier(id=did, option=option, enable_mask=enable_mask,
                                                            func_req=func_req, *args, **kwargs)
    if expect_data is None:
        if resp is None or resp == b'':
            TestLog("PASS", "", f"期望: {expect_str}; 实际:无响应")
            return True, None
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:收到响应 {_response_text(resp)}")
        return False, resp

    if isinstance(expect_data[0], list):
        for exp in expect_data:
            status, msg = check_expect_response(resp, exp)
            if status:
                TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
                return True, resp
        _, msg = check_expect_response(resp, expect_data[0])
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
        return False, resp
    else:
        status, msg = check_expect_response(resp, expect_data)
        if status is False:
            TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
            return False, resp
        TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
        return True, resp


def service_31_check(node, control_type, rid, expect_data, expect_str, record=b"", func_req=False, *args, **kwargs):
    resp = node.Service_0x31_RoutineControl(control_type=control_type, rid=rid, record=record,
                                            func_req=func_req, *args, **kwargs)
    if expect_data is None:
        if resp is None or resp == b'':
            TestLog("PASS", "", f"期望: {expect_str}; 实际:无响应")
            return True, None
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:收到响应 {_response_text(resp)}")
        return False, resp

    if isinstance(expect_data[0], list):
        for exp in expect_data:
            status, msg = check_expect_response(resp, exp)
            if status:
                TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
                return True, resp
        _, msg = check_expect_response(resp, expect_data[0])
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
        return False, resp
    else:
        status, msg = check_expect_response(resp, expect_data)
        if status is False:
            TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
            return False, resp
        TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
        return True, resp


def service_unsupported_check(node, service_id, expect_data, expect_str, func_req=False, *args, **kwargs):
    resp = node.Service_Unsupported(service_id, func_req=func_req, *args, **kwargs)
    if expect_data is None:
        if resp is None or resp == b'':
            TestLog("PASS", "", f"期望: {expect_str}; 实际:无响应")
            return True
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:收到响应")
        return False

    status, msg = check_expect_response(resp, expect_data)
    if status is False:
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
        return False
    TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
    return True

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
        while TesterPresentManager.flag is True:
            node.Service_0x3E_TesterPresent(0x80, func_req=True, update_send_data=False)
            time.sleep(period_ms / 1000.0)

    TesterPresentManager.flag = True
    threading.Thread(target=run, args=(node, period_ms), daemon=True).start()
    TesterPresentManager.status = "running"

def tester_present_stop():
    """
        停止周期发送3E 80
    """
    TesterPresentManager.flag = False
    TesterPresentManager.status = "stopped"



class RunTimeInfo:
    def __init__(self):
        self.flag_run = True

        self.send_list = []  # 记录Tester发送的报文列表
        self.recv_list = []  # 记录DUT响应的报文列表


    def clear(self):
        self.flag_run = True

        self.send_list.clear()
        self.recv_list.clear()

    def start_run(self):
        self.flag_run = True

    def stop_run(self):
        self.flag_run = False
        self.send_list.clear()
        self.recv_list.clear()

    # ------------------------------
    def get_send_list(self):
        return self.send_list

    def get_send_item_timestamp(self, index):
        if index > len(self.send_list):
            return 0
        return self.send_list[index]["timestamp"]

    def get_send_item_payload(self, index):
        if index > len(self.send_list):
            return []
        return self.send_list[index]["payload"]

    def get_recv_list(self):
        return self.recv_list

    def get_recv_item_timestamp(self, index):
        if index > len(self.recv_list):
            return 0
        return self.recv_list[index]["timestamp"]

    def get_recv_item_payload(self, index):
        if index > len(self.recv_list):
            return []
        return self.recv_list[index]["payload"]


def check_msg_thread_start(rt: RunTimeInfo, diag_req_id: int, diag_resp_id: int):
    """
        save_req_send: 是否记录请求报文的时间
        save_fc_send:  是否记录流控报文的时间(3_)
    """
    def run():
        start_pos = 0
        ctx.can.messages.clear()
        ctx.can.set_filter(diag_req_id)
        ctx.can.add_filter_by_id(diag_resp_id)
        last_msg = None
        while rt.flag_run is True:
            try:
                can_messages = ctx.can.messages
                if start_pos < len(can_messages):
                    msg = can_messages[start_pos]
                    start_pos += 1
                    # if msg.id != diag_resp_id:
                    if msg.id not in [diag_req_id, diag_resp_id]:
                        continue
                    if msg == last_msg:  # 相同的报文
                        continue
                    last_msg = msg
                    print("recv: ", msg)

                    # 发送的报文列表
                    if msg.id == diag_req_id:
                        rt.send_list.append({
                           "timestamp":  msg.time_ms,
                           "payload":  list(bytes.fromhex(msg.payload_hex)),
                        })
                    # 接收的报文列表
                    if msg.id == diag_resp_id:
                        rt.recv_list.append({
                           "timestamp":  msg.time_ms,
                           "payload":  list(bytes.fromhex(msg.payload_hex)),
                        })

            except Exception as e:
                import traceback
                traceback.print_exc()
            time.sleep(0.001)

    rt.clear()
    rt.start_run()
    threading.Thread(target=run, daemon=True).start()


def check_msg_thread_stop(rt: RunTimeInfo):
    rt.stop_run()
    try:
        ctx.can.clear_filter_by_id()
    except Exception:
        pass

def get_msg_timestamp_ms_with_78_flag(msg_list, expect_data):
    """
    从msg_list中查找包含expect_data的报文，返回其时间戳
    失败返回None
    :param msg_list: 发送 or 接收 报文列表, e.g. [{"timestamp": xxx, "payload": [...]}, ...]
    :param expect_data: 期望的报文, e.g. [0x10, 0x01]
    """
    flag_78 = False
    timestamp_last_78 = 0
    if len(expect_data) == 0:
        return None, flag_78, timestamp_last_78
    for item in msg_list:
        payload = item["payload"]
        if payload[1] == 0x7F and payload[3] == 0x78:
            flag_78 = True
            timestamp_last_78 = item["timestamp"]
        if bytes(expect_data) in bytes(payload):
            return item["timestamp"], flag_78, timestamp_last_78
    return None, flag_78, timestamp_last_78

def check_msg_time_diff_ms(rt: RunTimeInfo, exp_send, exp_recv, exp_max_time_ms):
    """
    计算发送报文和接收报文的时间差，单位毫秒
    """
    t1, _, _ = get_msg_timestamp_ms_with_78_flag(rt.send_list, expect_data=exp_send)
    if t1 is None:
        TestLog("FAIL", "", f"未能获取到{[hex(item) for item in exp_send]}的时间戳")
        return False
    # 获取接收的报文的时间戳
    t2, _, _ = get_msg_timestamp_ms_with_78_flag(rt.recv_list, expect_data=exp_recv)
    if t2 is None:
        TestLog("FAIL", "", f"未能获取到{[hex(item) for item in exp_send]}的时间戳")
        return False
    if t2 - t1 < exp_max_time_ms:
        TestLog("PASS", "", f"在{exp_max_time_ms}ms时间内给出响应，响应时间={t2 - t1}ms")
        return True
    else:
        TestLog("FAIL", "", f"未在{exp_max_time_ms}ms时间内给出响应，响应时间={t2 - t1}ms")
        return False

def check_msg_time_diff_ms_with_78_flag(rt: RunTimeInfo, exp_send, exp_recv, exp_max_time_ms, exp_max_enhance_time_ms):
    """
    计算发送报文和接收报文的时间差，单位毫秒
    """
    t1, _, _ = get_msg_timestamp_ms_with_78_flag(rt.send_list, expect_data=exp_send)
    if t1 is None: TestLog("FAIL", "", f"未能获取到{[hex(item) for item in exp_send]}的时间戳");return False
    # 获取接收的报文的时间戳
    t2, flag_78, timestamp_78 = get_msg_timestamp_ms_with_78_flag(rt.recv_list, expect_data=exp_recv)
    if t2 is None: TestLog("FAIL", "", f"未能获取到{[hex(item) for item in exp_send]}的时间戳");return False

    if flag_78 is True:
        t1 = timestamp_78
        expect_ms = exp_max_enhance_time_ms
        TestLog("INFO", "", f"检测到7F 78响应，响应时间要求为{expect_ms}ms")
    else:
        expect_ms = exp_max_time_ms
        TestLog("INFO", "", f"未检测到7F 78响应，响应时间要求为{expect_ms}ms")

    if t2 - t1 < expect_ms:
        TestLog("PASS", "", f"在{expect_ms}ms时间内给出响应，响应时间={t2 - t1}ms")
        return True
    else:
        TestLog("FAIL", "", f"未在{expect_ms}ms时间内给出响应，响应时间={t2 - t1}ms")
        return False

def check_app_communication(check_id_list=[], wait_time_s=2, check_time_s=1):
    """
        等待 wait_time_s 后检查 check_time_s 内是否有应用通信报文
    """
    time.sleep(wait_time_s)
    ctx.can.clear_messages()
    time.sleep(check_time_s)

    for msg in ctx.can.messages:
        if msg.id in check_id_list:
            return True
    return False


def get_app_msg_count(normal_app_id_list):
    count = 0
    for msg in ctx.can.messages:
        if msg.id in normal_app_id_list:
            count += 1
    return count

def get_nm_msg_count(nm_id_list):
    count = 0
    for msg in ctx.can.messages:
        if msg.id in nm_id_list:
            count += 1
    return count


def unlock_27_extended(node, level, need_wait=False):
    # 默认会话
    if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return False, "进入默认会话失败"

    time.sleep(1)

    # 扩展会话
    if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return False, "进入扩展会话失败"

    time.sleep(1)

    if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return False, "未进入扩展会话"

    if need_wait is True:
        tester_present_start(node)
        time.sleep(15)
        tester_present_stop()

    # 27 level
    status, resp = service_27_check(node, level, [0x67, level], f"肯定响应(67 {level})")
    if not status:
        if not resp:
            return False, "无响应"
        if resp and bytes([0x7F, 0x27, 0x37]) in resp.data:
            return False, "收到NRC37，等待计时器结束后重试"

    seed_list = get_seed_from_27_resp(resp)

    # 27 level + 1
    if not service_27_xx_check(node, level + 1, seed_list, [0x67, level + 1], f"肯定响应(67 {level + 1})", alg_type=AlgorithmType.EXTENDED): 
        return False, f"27 {level + 1}非正响应"

    return True, f"27 {level}解锁成功"


def unlock_27_programming(node, level, need_wait=False):
    # 默认会话
    if not service_10_check(node, 0x01, expect_data=[0x50, 0x01], expect_str="肯定响应(50 01)"): return False, "进入默认会话失败"

    time.sleep(1)

    # 扩展会话
    if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"): return False, "进入扩展会话失败"

    time.sleep(1)

    if not check_current_session(node, [0x71, 0x01, 0x02, 0x03, 0x00], expect_str="位于扩展会话中(71 01 02 03 00)"): return False, "未进入扩展会话"

    # 扩展会话
    if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return False, "进入刷新会话失败"

    if need_wait is True:
        tester_present_start(node)
        time.sleep(15)
        tester_present_stop()

    # 27 level
    status, resp = service_27_check(node, level, [0x67, level], f"肯定响应(67 {level})")
    if not status:
        if not resp:
            return False, "无响应"
        if resp and bytes([0x7F, 0x27, 0x37]) in resp.data:
            return False, "收到NRC37，等待计时器结束后重试"

    seed_list = get_seed_from_27_resp(resp)

    # 27 level + 1
    if not service_27_xx_check(node, level + 1, seed_list, [0x67, level + 1], f"肯定响应(67 {level + 1})", alg_type=AlgorithmType.PROGRAMMING): 
        return False, f"27 {level + 1}非正响应"

    return True, f"27 {level}解锁成功"


def clear_27_error_timer(node, do_times=3):
    """
        清空27错误计数器，默认3次正常解锁
            发送第1次错误密钥，回NRC35，错误计数器+1
            发送第2次错误密钥，回NRC35，错误计数器+1
            发送第3次错误密钥，回NRC36，错误计数器+1
            接下来开启NRC37计时器
        因此尝试正常解锁3次，清除计时器
    """
    LEVEL_EXT, LEVEL_EXT_STR = 0x01, "01"  # 扩展等级
    LEVEL_EXT_2, LEVEL_EXT_2_STR = 0x02, "02"  # 扩展等级+1
    LEVEL_PRO_11, LEVEL_PRO_11_STR = 0x11, "11"  # 刷新等级
    LEVEL_PRO_12, LEVEL_PRO_12_STR = 0x12, "12"  # 刷新等级+1

    # 扩展会话下正常解锁=========================================================================================================
    cnt = 0
    need_wait = False
    unlock_status = False
    for _ in range(do_times + 3):
        status, msg = unlock_27_extended(node, LEVEL_EXT, need_wait=need_wait)
        if status is True:
            cnt += 1
            if cnt == do_times:
                unlock_status = True
                break
        else:
            if "NRC37" in msg:
                need_wait = True
    if not unlock_status:
        TestLog("FAIL", "", f"错误计数器清除失败27 {LEVEL_EXT}")
        return False


    # 刷新会话下正常解锁=========================================================================================================
    cnt = 0
    need_wait = False
    unlock_status = False
    for _ in range(do_times + 3):
        status, msg = unlock_27_programming(node, LEVEL_PRO_11, need_wait=need_wait)
        if status is True:
            cnt += 1
            if cnt == do_times:
                unlock_status = True
                break
        else:
            if "NRC37" in msg:
                need_wait = True
    if not unlock_status:
        TestLog("FAIL", "", f"错误计数器清除失败27 {LEVEL_PRO_11}")
        return False

    TestLog("INFO", "", f"错误计数器清除成功")
    time.sleep(1)
    return True