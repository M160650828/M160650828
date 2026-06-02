import dataclasses
import os
import threading
import time
import queue
from typing import List, Dict, Tuple

from can import Message

from library.uds.uds_node import UDSNode
from slplus.cantp import sl_cantp

from testcases_canlin.bootloader.utils.hex_parser import parse_hex
from testcases_canlin.bootloader.utils.s19_parser import parse_s19
from library.security.security import Seed2Key
from uvtest.testlog import TestLog
from env.config import DEFAULT_CAN_CHANNELS
from common.params import P
from common.context import ctx, Direction
from uvtest.testlog import TestLog
import xml.etree.ElementTree as ET
# from common.can_utils import canmsg_create, send_canmsg
from library.e2e import crc8_saej1850, crc16_ccitt

@dataclasses.dataclass
class E2ESignalGroupInfo:
    name: str
    startByte: int
    length: int
    dataid: int
    max_delta_counter_init: int

PROFILE_1A = "Profile1A"
PROFILE_5 = "Profile5"

PROFILE_COUNTER_MAX = {
    PROFILE_1A: 14,
    PROFILE_5: 0xFF,
}

def build_e2e_payload(sig: E2ESignalGroupInfo, profile: str,
                       data_len: int, counter: int,
                       crc_correct: bool = True,
                       counter_delta: int = 0,
                       data: bytes = None) -> bytes:
    payload = bytearray(data) if data else bytearray(data_len)
    payload.extend([0x00] * (data_len - len(payload)))
    # payload = bytearray(data_len)
    sb = sig.startByte

    if counter_delta == 0:
        actual_counter = counter
    elif counter_delta > 0:
        # Counter += delta
        actual_counter = counter + counter_delta
    elif counter_delta == -1:
        # 重复 Counter不变
        actual_counter = max(0, counter - 1)
    else:  # counter_delta == -2
        # 倒退 Counter -= 1
        actual_counter = max(0, counter - 2)

    if profile == PROFILE_1A:
        # Profile1A: [CRC(1B)][Counter(4bit)+Data(4bit)][Data...]
        # Counter范围: 0-14
        counter_val = actual_counter % 15
        payload[sb + 1] = (counter_val & 0x0F)  # Counter在低4位

        if crc_correct:
            crc = e2e_checksum_for_payload(bytes(payload), sig, profile)
        else:
            # 使用错误的CRC值
            crc = (e2e_checksum_for_payload(bytes(payload), sig, profile) + 0x55) & 0xFF
        payload[sb] = crc

    else:  # PROFILE_5
        # Profile5: [CRC_H(1B)][CRC_L(1B)][Counter(1B)][Data...]
        # Counter范围: 0-255
        counter_val = actual_counter & 0xFF
        payload[sb + 2] = counter_val

        if crc_correct:
            crc = e2e_checksum_for_payload(bytes(payload), sig, profile)
        else:
            # 使用错误的CRC值
            crc = (e2e_checksum_for_payload(bytes(payload), sig, profile) + 0x5555) & 0xFFFF
        payload[sb] = (crc >> 8) & 0xFF
        payload[sb + 1] = crc & 0xFF

    return bytes(payload)


def send_e2e_frame(channel: int, msg_id: int, payload: bytes,
                    is_canfd: bool = False) -> bool:
    try:
        # from common.can_utils import send_canmsg

        dlc = len(payload)
        fdf = 1 if is_canfd else 0
        brs = 1 if is_canfd else 0
        msg = send_canmsg(channel, msg_id=msg_id, dlc=dlc,
                         data=payload, fdf=fdf, brs=brs)
        return msg is not None
    except Exception as e:
        TestLog("FAIL", "发送E2E报文", f"发送失败: {e}")
        return False



# 计算 E2E 字段
def set_profile(use_canfd: bool) -> Tuple[str, int]:
    profile = PROFILE_5 if use_canfd else PROFILE_1A
    gCntrMax = PROFILE_COUNTER_MAX[profile]
    return profile, gCntrMax

def start_e2e_send_timer(channel: int, msg_id: int, sig: E2ESignalGroupInfo,
                        profile: str, data_len: int, cycle_ms: int,
                        is_canfd: bool = False) -> dict:
    from common.utils import TimerCyclic

    tx_ctrl = {
        'counter': 0,
        'crc_correct': True,
        'counter_delta': 0,  # Counter偏差：0=正常, >0=跳跃, -1=重复, -2=倒退
        'timer_id': f"e2e_tx_{msg_id:x}"
    }

    def send_fn():
        payload = build_e2e_payload(
            sig, profile, data_len,
            tx_ctrl['counter'],
            tx_ctrl['crc_correct'],
            tx_ctrl['counter_delta']
        )
        send_e2e_frame(channel, msg_id, payload, is_canfd)
        max_counter = PROFILE_COUNTER_MAX[profile]
        tx_ctrl['counter'] = (tx_ctrl['counter'] + 1) % (max_counter + 1)

    TimerCyclic.start(tx_ctrl['timer_id'], cycle_ms, send_fn)
    return tx_ctrl


def stop_e2e_send_timer(tx_ctrl: dict):
    if tx_ctrl:
        from common.utils import TimerCyclic
        TimerCyclic.stop(tx_ctrl.get('timer_id'))


def e2e_checksum_for_payload(payload: bytes, sig: E2ESignalGroupInfo, profile: str) -> int:
    sb = sig.startByte
    if profile == PROFILE_1A:
        offset = 1
        try:
            total_len = int(getattr(sig, 'length', 0))
        except Exception:
            total_len = 0
        avail = max(len(payload) - (sb + offset), 0)
        protected_max = max(total_len - offset, 0)
        bytelength = min(protected_max, avail) if protected_max > 0 else avail
        chk = bytearray()
        chk.append(sig.dataid & 0xFF)
        chk.append((sig.dataid >> 8) & 0xFF)
        chk.extend(payload[sb + offset: sb + offset + bytelength])
        return crc8_saej1850(bytes(chk))
    else:
        offset = 2
        bytelength = max(len(payload) - (sb + offset), 0)
        chk = bytearray()
        chk.extend(payload[sb + offset: sb + offset + bytelength])
        chk.append(sig.dataid & 0xFF)
        chk.append((sig.dataid >> 8) & 0xFF)
        return crc16_ccitt(bytes(chk))

def canmsg_create(msg_id, dlc, data=b"", rtr=0, fdf=0, brs=0, ext=0):
    """
    CAN/CANFD报文创建
    """
    try:
        from slplus.can import sl_canmsg

        # TestLog("DEBUG", "报文创建",
        #     f"开始创建报文 - ID=0x{msg_id:x}, DLC={dlc}, RTR={rtr}, FDF={fdf}, BRS={brs}, EXT={ext}")

        if fdf:
            dlc_to_bytes = {
                0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8,
                9: 12, 10: 16, 11: 20, 12: 24, 13: 32, 14: 48, 15: 64
            }
            data_len = dlc_to_bytes.get(int(dlc), 8)
            # TestLog("DEBUG", "报文创建", f"CANFD模式: DLC={dlc} -> 数据长度={data_len}")
        else:
            data_len = min(int(dlc), 8)
            # TestLog("DEBUG", "报文创建", f"CAN模式: DLC={dlc} -> 数据长度={data_len}")

        if isinstance(data, int):
            val = data & 0xFF
            payload = bytes([val]) * data_len
            data_dbg = f"0x{val:02X} x{data_len}"
        else:
            try:
                raw = bytes(data)
            except Exception:
                raw = b""
            payload = (raw + b"\x00" * data_len)[:data_len]
            data_dbg = [f"0x{x:02X}" for x in payload]

        # TestLog("DEBUG", "报文创建", f"创建载荷: {payload.hex().upper()} (长度={len(payload)})")

        msg = sl_canmsg(
            id=int(msg_id),
            is_fd=bool(fdf),
            dlc=int(dlc),
            payload=payload,
            brs=bool(brs),
            ide=bool(ext),
            rtr=bool(rtr)
        )

        # TestLog("INFO", "报文创建",
        #         f"成功创建报文: ID=0x{msg_id:x}, DLC={dlc}, FDF={fdf}, BRS={brs}, "
        #             f"RTR={rtr}, EXT={ext}, 数据长度={data_len}, 数据={data_dbg}")
        return msg

    except Exception as e:
        TestLog("FAIL", "报文创建", f"创建报文异常: {e}")
        return None


def send_canmsg(channel, msg=None, msg_id=None, dlc=None, rtr=0, fdf=0, brs=0, data=b"", ext=0):
    """发送 CAN/CANFD 报文"""
    try:
        from slplus.can import sl_can
        if msg is None:
            if msg_id is None or dlc is None:
                raise ValueError("msg 或 (msg_id, dlc) 必须提供其一")
            msg = canmsg_create(int(msg_id), int(dlc), data=data,
                                rtr=int(rtr), fdf=int(fdf), brs=int(brs), ext=int(ext))
        sl_can(int(channel)).send_canmsg(msg)
        return msg
    except Exception as e:
        TestLog("FAIL", "发送报文", f"发送失败: {e}")
        return None

class BusSim:
    def __init__(self):
        self._busid = None
        self._sa = None
        self._ta = None
        self._fa = None
        self._is_canfd = False
        self._recv_queue = queue.Queue()
        self._cantp = None

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
            if not (data[0] == 0x76 or (len(data) >= 3 and [data[0], data[1], data[2]] == [0x7F, 0x36, 0x78])):
                TestLog("INFO", " ", f"收到数据: {data.hex(' ').upper()}")
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
                "fdf": self._is_canfd,
                "brs": self._is_canfd,
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
                "fc_delay": 15,
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

    def send(self, tx_id, pkt: bytes):
        if self._cantp is None:
            TestLog("ERROR", "BusSim", "CANTP 未初始化，发送失败")
            return

        is_func = (tx_id == self._fa)
        if pkt[0] != 0x36:
            TestLog("INFO", " ", f"发送数据: data={pkt.hex()}")
        self._cantp.send(is_func, pkt)

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
            if not (data[0] == 0x76 or (data[0] == 0x7F and data[1] == 0x36 and data[2] == 0x78)):
                TestLog("INFO", " ", f"收到数据: {data.hex(' ').upper()}")
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
        TestLog("INFO", "BusSim", f"CANTP配置: fdf={cfg['trans']['fdf']}, mtu={cfg['trans']['mtu']}, is_canfd={self._is_canfd}")
        if not self._cantp.set_config(cfg):
            TestLog("ERROR", "BusSim", "CANTP 配置失败")
            return

        if not self._cantp.active():
            TestLog("ERROR", "BusSim", "CANTP 激活失败")
            return

        TestLog("INFO", "BusSim", f"CANTP 初始化成功 (sa=0x{self._sa:X}, ta=0x{self._ta:X}, fa=0x{self._fa:X}, _is_canfd={self._is_canfd})")

    def _build_config(self, custom_config: dict = None) -> dict:
        tp = P.TpInfo
        cfg = {
            "trans": {
                "fdf": self._is_canfd,
                "brs": self._is_canfd,
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
                "fc_delay": 15,
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
        if data[0] != 0x36:
            TestLog("INFO", " ", f"发送数据: data={data.hex(' ').upper()}")
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
            # TestLog("WARNING", "BusSim", f"===接收超时 ({timeout}s)")#uds_node模块禁止肯定响应也会
            return False, None

    def close(self):
        if self._cantp is not None:
            self._cantp.destroy()
            self._cantp = None
            TestLog("INFO", "BusSim", "CANTP 已关闭")


# from testcases_canlin.bootloader.utils.can_manager.can_manager import ZQWLBusSim
def get_can_node(sa, ta, fa, is_canfd=True) -> UDSNode:
    busid = DEFAULT_CAN_CHANNELS[0]
    bus_obj = CANBusSim()
    # bus_obj = ZQWLBusSim()
    bus_obj.init(busid, sa, ta, fa, is_canfd)
    node = UDSNode(bus_obj)
    return node


# ---------------------------------------------刷新配置参数  -s
class FlashFileType:
    driver = "DRIVER"
    app = "APP"

@dataclasses.dataclass
class FlashFileItem:
    type: str = "DRIVER"  # DRIVER/APP
    path_hexS19: str = ""  # hex/S19文件路径
    path_xml: str = ""  # XML描述文件路径

@dataclasses.dataclass
class FlashConfig:
    req_addr: int = 0x762  # 刷新请求地址
    resp_addr: int = 0x772  # 刷新响应地址
    func_addr: int = 0x7E4  # 刷新功能地址
    # 如果不支持AB分区，则使用A分区的文件作为刷新文件
    flash_files_a: list = dataclasses.field(default_factory=list)  # A区刷新文件列表，元素类型为FlashItem
    flash_files_b: list = dataclasses.field(default_factory=list)  # B区刷新文件列表，元素类型为FlashItem

    @staticmethod
    def check_driver(file: FlashFileItem):
        return file.type == FlashFileType.driver
    
    @staticmethod
    def check_app(file: FlashFileItem):
        return file.type == FlashFileType.app

def get_flash_config(type = ""):
    """
        获取正向刷写相关的配置参数
    """
    # 获取分区 A 的所有项
    a_flash_files = []
    a_items = P.BootloaderInfo.get_by_partition("A")
    for item in a_items:
        if type == "APP" and item.type not in [1, 2]:
            continue
        elif type == "CAL" and item.type not in [1, 3]:
            continue
        elif type == "Config" and item.type not in [1, 4]:
            continue

        if item.type == 1:
            a_flash_files.append(FlashFileItem(type=FlashFileType.driver, path_hexS19=item.path_file, path_xml=item.path_sig_file))
        elif item.type in [2,3,4]:
            a_flash_files.append(FlashFileItem(type=FlashFileType.app, path_hexS19=item.path_file, path_xml=item.path_sig_file))
        else:
            TestLog("INFO", " ", f"无效的刷写包类型: {item.type}")
        TestLog("INFO", " ", f"[A区] 类型={item.type}, 文件={item.path_file}, 签名={item.path_sig_file}")

    # 获取分区 B 的所有项
    b_flash_files = []
    b_items = P.BootloaderInfo.get_by_partition("B")
    for item in b_items:
        if type == "APP" and item.type not in [1, 2]:
            continue
        elif type == "CAL" and item.type not in [1, 3]:
            continue
        elif type == "Config" and item.type not in [1, 4]:
            continue

        if item.type == 1:
            b_flash_files.append(
                FlashFileItem(type=FlashFileType.driver, path_hexS19=item.path_file, path_xml=item.path_sig_file))
        elif item.type in [2,3,4]:
            b_flash_files.append(
                FlashFileItem(type=FlashFileType.app, path_hexS19=item.path_file, path_xml=item.path_sig_file))
        else:
            TestLog("INFO", " ", f"无效的刷写包类型: {item.type}")
        TestLog("INFO", " ", f"[B区] 类型={item.type}, 文件={item.path_file}, 签名={item.path_sig_file}")

    return FlashConfig(flash_files_a=a_flash_files, flash_files_b=b_flash_files)


    # import os
    # basic_path = r"D:\2_Project\24_SAIC\99_SolarONE\framework\testinputs\FlashFile\PLCM_BOD13A001_APP01.06.02_250927_HWV1.03"
    # hex_driver_file = os.path.join(basic_path, "1-driver.hex").replace("\\", "/")
    # hex_app_file = os.path.join(basic_path, "2-app.hex").replace("\\", "/")
    # xml_file = os.path.join(basic_path, "pkg-cfg.xml").replace("\\", "/")
    # flash_files = [
    #     FlashFileItem(type=FlashFileType.driver, path_hex=hex_driver_file, path_xml=xml_file),
    #     FlashFileItem(type=FlashFileType.app, path_hex=hex_app_file, path_xml=xml_file)
    # ]
    # return FlashConfig(flash_files_a=flash_files, flash_files_b=flash_files)

# ---------------------------------------------刷新配置参数  -e

# --------------------------
def check_expect_response(response_message: Message, expect_data: list) -> (bool, str):
    if response_message is None:
        return False, "未检测到响应报文"

    response_data = list(response_message.data)
    if bytes(expect_data) in bytes(response_data):
        return True, f"检测到期望响应报文, 期望={[hex(item) for item in expect_data]}, 实际={[hex(item) for item in response_data]}"

    return False, f"非期望响应报文, 期望={[hex(item) for item in expect_data]}, 实际={[hex(item) for item in response_data]}"

def service_10_check(node, session, expect_data, expect_str, func_req=False, *args, **kwargs):
    resp = node.Service_0x10_SessionControl(session, func_req=func_req, *args, **kwargs)
    if expect_data is None:
        if resp is None:
            return True  # 期望检测不到，实际也检测不到
        return False  # 期望检测不到，实际检测到，

    status, msg = check_expect_response(resp, expect_data)
    if status is False:
        TestLog("FAIL", " ", f"期望: {expect_str}; 实际:{msg}")
        return False
    TestLog("PASS", " ", f"期望: {expect_str}; 实际:{msg}")
    return True

def service_11_check(node, reset_type, expect_data, expect_str, func_req=False):
    resp = node.Service_0x11_ECUReset(reset_type, func_req=func_req)
    status, msg = check_expect_response(resp, expect_data)
    if status is False:
        TestLog("FAIL", " ", f"期望: {expect_str}; 实际:{msg}");
        return False
    TestLog("PASS", " ", f"期望: {expect_str}; 实际:{msg}")
    return True

def service_19_check(node, report_type, expect_data, expect_str, func_req=False, *args, **kwargs):
    resp = node.Service_0x19_ReadDTCInformation(report_type=report_type, func_req=func_req, *args, **kwargs)
    if expect_data is None:
        if resp is None:
            return True  # 期望检测不到，实际也检测不到
        return False  # 期望检测不到，实际检测到，

    status, msg = check_expect_response(resp, expect_data)
    if status is False:
        TestLog("FAIL", " ", f"期望: {expect_str}; 实际:{msg}")
        return False, ""
    TestLog("PASS", " ", f"期望: {expect_str}; 实际:{msg}")
    return True, resp

def service_22_check(node, did, expect_data, expect_str, func_req=False, *args, **kwargs):
    resp = node.Service_0x22_ReadDataByIdentifier(id=did, func_req=func_req, *args, **kwargs)
    if expect_data is None:
        if resp is None:
            TestLog("PASS", " ", f"期望: {expect_str}; 实际:无响应")
            return True, None  # 期望无响应，实际无响应
        TestLog("FAIL", " ", f"期望: {expect_str}; 实际:收到响应")
        return False, resp  # 期望无响应，实际有响应

    status, msg = check_expect_response(resp, expect_data)
    if status is False:
        TestLog("FAIL", " ", f"期望: {expect_str}; 实际:{msg}")
        return False, resp
    TestLog("PASS", " ", f"期望: {expect_str}; 实际:{msg}")
    return True, resp

def service_31_check(node, control_type, rid, expect_data, expect_str, record=b"", func_req=False, *args, **kwargs):
    resp = node.Service_0x31_RoutineControl(control_type=control_type, rid=rid, record=record,
                                            func_req=func_req, *args, **kwargs)
    if expect_data is None:
        if resp is None or resp == b'':
            TestLog("PASS", " ", f"期望: {expect_str}; 实际:无响应")
            return True, None
        TestLog("FAIL", " ", f"期望: {expect_str}; 实际:收到响应 {resp.hex() if resp else 'None'}")
        return False, resp

    if isinstance(expect_data[0], list):
        for exp in expect_data:
            status, msg = check_expect_response(resp, exp)
            if status:
                TestLog("PASS", " ", f"期望: {expect_str}; 实际:{msg}")
                return True, resp
        _, msg = check_expect_response(resp, expect_data[0])
        TestLog("FAIL", " ", f"期望: {expect_str}; 实际:{msg}")
        return False, resp
    else:
        status, msg = check_expect_response(resp, expect_data)
        if status is False:
            TestLog("FAIL", " ", f"期望: {expect_str}; 实际:{msg}")
            return False, resp
        TestLog("PASS", " ", f"期望: {expect_str}; 实际:{msg}")
        return True, resp

def check_resp(resp, expect_data, expect_str):
    if not resp:
        TestLog("FAIL", " ", f"期望: {expect_str}，实际:未检测到响应报文")
        return False, f"期望: {expect_str}，实际:未检测到响应报文"
    data = resp.data
    if data[0:len(expect_data)] != bytes(expect_data):
        TestLog("FAIL", " ", f"期望: {expect_str}，实际:非期望报文{data.hex(' ').upper()}")
        return False, f"期望: {expect_str}，实际:非期望报文{data.hex(' ').upper()}"
    TestLog("PASS", " ", f"期望: {expect_str}，实际:期望报文{data.hex(' ').upper()}")
    return True, f"期望: {expect_str}，实际:期望报文{data.hex(' ').upper()}"

def security_access(node: UDSNode, level):
    """
        安全访问
    """
    # 27 11
    resp = node.Service_0x27_SecurityAccess(level)
    status, msg = check_resp(resp, [0x67, level], f"肯定响应(67 {level: X})")
    if not status: 
        TestLog("FAIL", " ", f"27 {level}失败: {msg}")
        return False

    seed = list(resp.data[2:])
    if level == 0x01:
        key = Seed2Key(P.ECUInfo.dllPath_2701, seed)
    else:
        key = Seed2Key(P.ECUInfo.dllPath_2711, seed)
    TestLog("INFO", " ", f"获取到的seed: {[hex(s) for s in seed]}")
    TestLog("INFO", " ", f"计算得到的密钥: {[hex(k) for k in key]}")

    # 27 12
    resp = node.Service_0x27_SecurityAccess(level+1, key)
    status, msg = check_resp(resp, [0x67, level+1], f"肯定响应(67 {level+1: X})")
    if not status: 
        TestLog("FAIL", " ", f"27 {level+1}失败: {msg}")
        return False
    return True

def make_fingerprint(finger_print: str) -> bytearray:
    """
        生成指纹数据
    """
    out_array = bytearray()
    # 获取本地时间
    t = time.localtime()
    # 年份后两位
    out_array.append((t.tm_year - 2000) & 0xFF)
    # 月份
    out_array.append((t.tm_mon) & 0xFF)
    # 日
    out_array.append((t.tm_mday) & 0xFF)

    out_array.extend([0x20] * 16)
    return out_array
    # 将字符串转成12字节的utf-8编码（不足补0，超出截断）
    # encoded = finger_print.encode('utf-8')
    # if len(encoded) > 16:
    #     encoded = encoded[:16]
    # elif len(encoded) < 16:
    #     encoded = encoded + b'\x20' * (16 - len(encoded))
    # out_array.extend(encoded)
    # return out_array

def write_fingerprint(node, expect_data=[0x6E, 0xF1, 0x84], expect_str="肯定响应(6E F1 84)"):
    """
        写入指纹
    """
    fingerprint = make_fingerprint("TEST")
    resp = node.Service_0x2E_WriteDataByIdentifier(0xF184, fingerprint)
    status, msg = check_resp(resp, expect_data, expect_str)
    if not status: 
        TestLog("FAIL", " ", f"写入指纹失败: {msg}")
        return False
    return True

def check_programming_dependencies1(node: UDSNode):
    """
        检查编程依赖
    """
    resp = node.Service_0x31_RoutineControl(0x01, 0xFF01)
    status, msg = check_resp(resp, [0x71, 0x01, 0xFF, 0x01, 0x00], "肯定响应(71 01 FF 01 00)")
    if not status: 
        TestLog("FAIL", " ", f"检查编程依赖失败: {msg}")
        return False
    if resp.data[4] == 0x01:
        TestLog("FAIL", " ", f"检查编程依赖失败: 依赖检查失败")
        return False
    return True

def check_programming_dependencies(node: UDSNode):
    """
        检查编程依赖
    """
    resp = node.Service_0x31_RoutineControl(0x01, 0xFF01)
    status, msg = check_resp(resp, [0x71, 0x01, 0xFF, 0x01], "肯定响应(71 01 FF 01)")
    if not status:
        TestLog("FAIL", " ", f"检查编程依赖失败: {msg}")
        return False
    if resp.data[4] not in [0x00, 0x05]:
        TestLog("FAIL", " ", f"检查编程依赖失败: resp.data[4]=0x{resp.data[4]:02X} ")
        return False
    return True


def check_programming_dependencies_with_power_off(node: UDSNode, power_off_func=None, power_off_delay=0):
    """
        检查编程依赖，在请求发送后立即断电
        power_off_func: 断电函数
        power_off_delay: 断电延迟(秒)
    """
    def send_request():
        resp = node.Service_0x31_RoutineControl(0x01, 0xFF01)
        return resp

    import threading
    resp_holder = [None]
    def thread_send():
        resp_holder[0] = send_request()

    t = threading.Thread(target=thread_send)
    t.start()
    time.sleep(power_off_delay)
    if power_off_func:
        power_off_func()
    t.join(timeout=15)
    resp = resp_holder[0]
    if resp is None:
        TestLog("INFO", " ", "断电导致响应丢失，符合预期")
        return True
    if resp.data[0] == 0x71:
        TestLog("INFO", " ", f"收到肯定响应(71): {resp.data.hex(' ').upper()}")
    return True


def check_programming_dependencies_fail(node: UDSNode):
    """
        检查编程依赖
    """
    respMsg = node.Service_0x31_RoutineControl(0x01, 0xFF01)
    if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
    ok_pos = len(resp) >= 5 and resp[:5] == [0x71, 0x01, 0xFF, 0x01, 0x00]
    if ok_pos:
        TestLog("FAIL", " ", f"检查编程依赖成功: {resp.hex(' ').upper()}")
        return True
    else:
        TestLog("INFO", " ", f"检查编程依赖失败: 依赖检查失败")
        return False
    # status, msg = check_resp(resp, [0x71, 0x01, 0xFF, 0x01], "肯定响应(71 01 FF 01)")
    # if not status:
    #     TestLog("FAIL", " ", f"检查编程依赖失败: {msg}")
    #     return False
    # if resp.data[4] == 0x01:
    #     TestLog("INFO", " ", f"检查编程依赖失败: 依赖检查失败")
    #     return False
    # return True

def parse_signature_xml(xml_path):
    """
        解析给定的Common XML内容，返回FileFactory下每个list的字典列表
    """
    with open(xml_path, "r") as f:
        xml_content = f.read()
    result = []
    try:
        root = ET.fromstring(xml_content)
        file_factory = root.find('FileFactory')
        if file_factory is not None:
            for file_item in file_factory.findall('list'):
                item = {}
                order = file_item.find('order')
                file_type = file_item.find('fileType')
                name = file_item.find('name')
                sig_val = file_item.find('sigVal')
                if order is not None:
                    item['order'] = int(order.text)
                if file_type is not None:
                    item['fileType'] = int(file_type.text)
                if name is not None:
                    item['name'] = name.text
                if sig_val is not None:
                    item['sigVal'] = bytes.fromhex(sig_val.text)
                result.append(item)
    except Exception as e:
        TestLog("INFO", " ", f"解析XML时出错: {e}")
    return result

def get_max_nummber_of_blocklength_from_0x74(resp: Message):
    """
        从74获取最大块数量
        e.g. 74 20 0F FF -> 2表示从0x0F到0xFF，即0x0FFF
    """
    data = resp.data
    max_n = 0
    n = data[1] >> 4
    for i in range(n):
        max_n = max_n | (data[2 + i] << (8 * (n - i - 1)))
    return max_n

def download_file(node: UDSNode, file_path: str):
    """
        下载文件
    """
    TestLog("INFO", " ", f"hex_path={file_path}")
    block_infos, start_addr = parse_flashFile(file_path)
    if start_addr is None:
        TestLog("INFO", " ", f"<parse_flashFile> Failed to find start address.")
        return -1
    for idx, block in enumerate(block_infos):
        start_address = block["address"]
        data = block["data"]
        length = len(data)
        resp = node.Service_0x34_RequestDownload(dataformat=0x00, 
                                                 size_len=4, 
                                                 address_len=4, 
                                                 size=length,
                                                 address=start_address)
        if not (resp.data[0] == 0x74):
            TestLog("FAIL", " ", f"RequestDownload(34)失败: 非肯定响应{resp}")
            return False

        TestLog("INFO", " ", "开始数据传输")
        TestLog("INFO", " ", "数据传输36...")
        maxNumberOfBlockLength = get_max_nummber_of_blocklength_from_0x74(resp)
        maxNumberOfBlockLength = maxNumberOfBlockLength - 2
        counter = 1
        while True:
            record = data[:maxNumberOfBlockLength]
            resp = node.Service_0x36_TransferData_WithoutPrint(counter, record, timeout=10)
            if resp is None:
                TestLog("FAIL", " ", f"TransferData(36)失败: 未检测到响应报文")
                return False
            if not (resp.data[0] == 0x76):
                TestLog("FAIL", " ", f"TransferData(36)失败: 非肯定响应{resp}")
                return False
            time.sleep(0.001)
            data = data[maxNumberOfBlockLength:]
            if len(data) == 0:
                break
            counter += 1
            if counter == 0xFF + 1:
                counter = 0
        TestLog("INFO", " ", "完成数据传输")
        resp = node.Service_0x37_RequestTransferExit()
        if not (resp.data[0] == 0x77):
            TestLog("FAIL", " ", f"RequestTransferExit(37)失败: 非肯定响应{resp.data}")
            return False
    return True

def download_file_stop_within_transfer_data(node: UDSNode, file_path: str, stopType: str):
    """
        下载文件过程
    """
    TestLog("INFO", " ", f"hex_path={file_path}")
    block_infos, start_addr = parse_flashFile(file_path)
    if start_addr is None:
        TestLog("INFO", " ", f"<parse_flashFile> Failed to find start address.")
        return -1, None
    for idx, block in enumerate(block_infos):
        start_address = block["address"]
        data = block["data"]
        length = len(data)
        resp = node.Service_0x34_RequestDownload(dataformat=0x00,
                                                 size_len=4,
                                                 address_len=4,
                                                 size=length,
                                                 address=start_address)
        if not (resp.data[0] == 0x74):
            TestLog("FAIL", " ", f"RequestDownload(34)失败: 非肯定响应{resp.data}")
            return False, None

        TestLog("INFO", " ", "开始数据传输")
        TestLog("INFO", " ", "数据传输36...")
        maxNumberOfBlockLength = get_max_nummber_of_blocklength_from_0x74(resp)
        maxNumberOfBlockLength = maxNumberOfBlockLength - 2
        counter = 1
        while True:
            # record = data[:maxNumberOfBlockLength]
            # resp = node.Service_0x36_TransferData(counter, record)
            # return True, resp.data
            if counter > 2:
                if stopType == "HighVoltage":
                    ctx.power_ctrl.set_voltage(P.TpInfo.HighVoltage)
                    time.sleep(2)
                elif stopType == "LowVoltage":
                    ctx.power_ctrl.set_voltage(P.TpInfo.LowVoltage)
                    time.sleep(2)

            record = data[:maxNumberOfBlockLength]
            resp = node.Service_0x36_TransferData_WithoutPrint(counter, record, timeout=10)
            if resp is None:
                TestLog("FAIL", " ", f"TransferData(36)失败: 未检测到响应报文")
                return False

            if counter > 2:
                return True, resp.data

            if not (resp.data[0] == 0x76):
                TestLog("FAIL", " ", f"TransferData(36)失败: 非肯定响应{resp}")
                return False
            time.sleep(0.001)
            data = data[maxNumberOfBlockLength:]
            if len(data) == 0:
                break

            counter += 1
            if counter == 0xFF + 1:
                counter = 0

    return True, None

def download_file_stop_within_transfer_data_more_2_bytes(node: UDSNode, file_path: str):
    """
        下载文件过程
    """
    TestLog("INFO", " ", f"hex_path={file_path}")
    block_infos, start_addr = parse_flashFile(file_path)
    if start_addr is None:
        TestLog("INFO", " ", f"<parse_flashFile> Failed to find start address.")
        return -1, None
    for idx, block in enumerate(block_infos):
        start_address = block["address"]
        data = block["data"]
        length = len(data)
        resp = node.Service_0x34_RequestDownload(dataformat=0x00,
                                                 size_len=4,
                                                 address_len=4,
                                                 size=length,
                                                 address=start_address)
        if not (resp.data[0] == 0x74):
            TestLog("FAIL", " ", f"RequestDownload(34)失败: 非肯定响应{resp}")
            return False, None

        maxNumberOfBlockLength = get_max_nummber_of_blocklength_from_0x74(resp)
        maxNumberOfBlockLength = maxNumberOfBlockLength - 2
        counter = 1
        while True:
            record = data[:maxNumberOfBlockLength + 2]
            resp = node.Service_0x36_TransferData(counter, record)
            return True, resp.data
    return True, None

def download_file_stop_within_transfer_data_less_2_bytes(node: UDSNode, file_path: str):
    """
        下载文件过程
    """
    TestLog("INFO", " ", f"hex_path={file_path}")
    block_infos, start_addr = parse_flashFile(file_path)
    if start_addr is None:
        TestLog("INFO", " ", f"<parse_flashFile> Failed to find start address.")
        return -1, None
    for idx, block in enumerate(block_infos):
        start_address = block["address"]
        data = block["data"]
        length = len(data)
        resp = node.Service_0x34_RequestDownload(dataformat=0x00,
                                                 size_len=4,
                                                 address_len=4,
                                                 size=length,
                                                 address=start_address)
        if not (resp.data[0] == 0x74):
            TestLog("FAIL", " ", f"RequestDownload(34)失败: 非肯定响应{resp.data}")
            return False, None

        maxNumberOfBlockLength = get_max_nummber_of_blocklength_from_0x74(resp)
        maxNumberOfBlockLength = maxNumberOfBlockLength - 2
        counter = 1
        while True:
            record = data[:maxNumberOfBlockLength - 2]
            resp = node.Service_0x36_TransferData(counter, record)
            return True, resp.data
    return True, None

def download_file_stop_within_transfer_data_skip_counter(node: UDSNode, file_path: str):
    """
        下载文件过程
    """
    TestLog("INFO", " ", f"hex_path={file_path}")
    block_infos, start_addr = parse_flashFile(file_path)
    if start_addr is None:
        TestLog("INFO", " ", f"<parse_flashFile> Failed to find start address.")
        return -1, None
    for idx, block in enumerate(block_infos):
        start_address = block["address"]
        data = block["data"]
        length = len(data)
        resp = node.Service_0x34_RequestDownload(dataformat=0x00,
                                                 size_len=4,
                                                 address_len=4,
                                                 size=length,
                                                 address=start_address)
        if not (resp.data[0] == 0x74):
            TestLog("FAIL", " ", f"RequestDownload(34)失败: 非肯定响应{resp.data}")
            return False, None

        maxNumberOfBlockLength = get_max_nummber_of_blocklength_from_0x74(resp)
        maxNumberOfBlockLength = maxNumberOfBlockLength - 2
        counter = 1
        while True:
            record = data[:maxNumberOfBlockLength]
            if counter != 2:
                resp = node.Service_0x36_TransferData(counter, record)
            if counter == 3:
                return True, resp.data
            time.sleep(0.001)
            data = data[maxNumberOfBlockLength:]
            if len(data) == 0:
                break
            counter += 1
            if counter == 0xFF + 1:
                counter = 0
    return True, None

def download_file_stop_within_transfer_data_with_same_counter(node: UDSNode, file_path: str):
    """
        下载文件过程
    """
    TestLog("INFO", " ", f"hex_path={file_path}")
    block_infos, start_addr = parse_flashFile(file_path)
    if start_addr is None:
        TestLog("INFO", " ", f"<parse_flashFile> Failed to find start address.")
        return -1, None
    for idx, block in enumerate(block_infos):
        start_address = block["address"]
        data = block["data"]
        length = len(data)
        resp = node.Service_0x34_RequestDownload(dataformat=0x00,
                                                 size_len=4,
                                                 address_len=4,
                                                 size=length,
                                                 address=start_address)
        if not (resp.data[0] == 0x74):
            TestLog("FAIL", " ", f"RequestDownload(34)失败: 非肯定响应{resp.data}")
            return False, None

        maxNumberOfBlockLength = get_max_nummber_of_blocklength_from_0x74(resp)
        maxNumberOfBlockLength = maxNumberOfBlockLength - 2
        resp = None
        for counter in [1, 1]:
            resp = None
            record = data[:maxNumberOfBlockLength]
            resp = node.Service_0x36_TransferData(counter, record)
            time.sleep(0.001)
            data = data[maxNumberOfBlockLength:]
        return True, resp.data
    return True, None

def download_file_without_transfer_data(node: UDSNode, file_path: str):
    """
        下载文件过程
    """
    TestLog("INFO", " ", f"hex_path={file_path}")
    block_infos, start_addr = parse_flashFile(file_path)
    if start_addr is None:
        TestLog("INFO", " ", f"<parse_flashFile> Failed to find start address.")
        return -1, None
    for idx, block in enumerate(block_infos):
        start_address = block["address"]
        data = block["data"]
        length = len(data)
        resp = node.Service_0x34_RequestDownload(dataformat=0x00,
                                                 size_len=4,
                                                 address_len=4,
                                                 size=length,
                                                 address=start_address)
        if not (resp.data[0] == 0x74):
            TestLog("FAIL", " ", f"RequestDownload(34)失败: 非肯定响应{resp.data}")
            return False, None

        TestLog("INFO", " ", "跳过应用数据传输步骤")

        resp = node.Service_0x37_RequestTransferExit()
        return True, resp.data
    return True, None

def check_memory(node: UDSNode, xml_path: str, target_name: str):
    """
        校验安全签名
    """
    file_list = parse_signature_xml(xml_path)
    target_name = os.path.basename(target_name)
    # TestLog("INFO", " ", f"{file_list}")
    sig_data = ""
    for item in file_list:
        if item["name"] == target_name:
            sig_data = item["sigVal"]
            break
    if len(sig_data) == 0:
        TestLog("INFO", " ", f"未找到<{target_name}>的签名")
        return False
    resp = node.Service_0x31_RoutineControl(0x01, 0xDD02, record=bytes(sig_data), timeout=10)
    status, msg = check_resp(resp, [0x71, 0x01, 0xDD, 0x02, 0x00], "肯定响应(71 01 DD 02 00)")
    if not status: 
        TestLog("FAIL", " ", f"安全签名验证失败: {msg}")
        return False
    return True

def check_memory_error(node: UDSNode, xml_path: str, target_name: str):
    """
        校验安全签名
    """
    file_list = parse_signature_xml(xml_path)
    target_name = os.path.basename(target_name)
    # TestLog("INFO", " ", f"{file_list}")
    sig_data = ""
    for item in file_list:
        if item["name"] == target_name:
            sig_data = item["sigVal"]
            break
    if len(sig_data) == 0:
        TestLog("INFO", " ", f"未找到<{target_name}>的签名")
        return False
    respMsg = node.Service_0x31_RoutineControl(0x01, 0xDD02, record=bytes(sig_data), timeout=10)
    if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
    status, msg = check_resp(respMsg, [0x71, 0x01, 0xDD, 0x02], "肯定响应(71 01 DD 02)")
    if not status:
        TestLog("FAIL", " ", f"期望: 肯定响应(71 01 DD 02); 实际: {resp.hex(' ').upper()}")
        return False
    if resp[4] not in [0x01, 0x02]:
        # TestLog("FAIL", " ", f"期望: 肯定响应(71 01 DD 02 01/02); 实际: {resp.hex(' ').upper()}")
        return False
    TestLog("PASS", " ", f"期望: 肯定响应(71 01 DD 02 01/02); 实际: {resp.hex(' ').upper()}")
    return True
def check_memory_with_power_off(node: UDSNode, xml_path: str, target_name: str, power_off_func=None, power_off_delay=0):
    """
        校验安全签名，在请求发送后立即断电
        power_off_func: 断电函数
        power_off_delay: 断电延迟(秒)
    """
    file_list = parse_signature_xml(xml_path)
    target_name = os.path.basename(target_name)
    sig_data = ""
    for item in file_list:
        if item["name"] == target_name:
            sig_data = item["sigVal"]
            break
    if len(sig_data) == 0:
        TestLog("INFO", " ", f"未找到<{target_name}>的签名")
        return False

    def send_request():
        resp = node.Service_0x31_RoutineControl(0x01, 0xDD02, record=bytes(sig_data), timeout=10)
        return resp

    import threading
    resp_holder = [None]
    def thread_send():
        resp_holder[0] = send_request()

    t = threading.Thread(target=thread_send)
    t.start()
    time.sleep(power_off_delay)
    if power_off_func:
        power_off_func()
    t.join(timeout=15)
    resp = resp_holder[0]
    if resp is None:
        TestLog("INFO", " ", "断电导致响应丢失，符合预期")
        return True
    if resp.data[0] == 0x71:
        TestLog("INFO", " ", f"收到肯定响应(71): {resp.data.hex(' ').upper()}")
    return True

def erase_memory(node: UDSNode, hex_path: str):
    block_infos, start_addr = parse_flashFile(hex_path)
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
        resp = node.Service_0x31_RoutineControl(0x01, 0xFF00, record=record)
        if not (resp.data[0: 5] == bytearray([0x71, 0x01, 0xFF, 0x00, 0x00])):
            return False
    return True

def erase_memory_without_response(node: UDSNode, hex_path: str):
    block_infos, start_addr = parse_flashFile(hex_path)
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
        # 发送指令后，不等待响应
        resp = node.Service_0x31_RoutineControl(0x01, 0xFF00, record=record, wait_resp=False)
        return True
    return True

def download_driver(node, flash_files):
    """
        下载driver文件
    """
    TestLog("INFO", "Driver", "")
    fhasl_flag = False
    for item in flash_files:
        if not FlashConfig.check_driver(item):
            continue
        TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
        TestLog("INFO", " ", f"DRIVER文件下载: {item.path_hexS19}")
        if not download_file(node, item.path_hexS19):
            TestLog("FAIL", " ", f"DRIVER文件下载失败: {item.path_hexS19}")
            return False

        TestLog("INFO", " ", f"DRIVER文件安全签名验证: {item.path_xml}")
        if not check_memory(node, item.path_xml, item.path_hexS19):
            TestLog("FAIL", " ", f"DRIVER文件安全签名验证失败: {item.path_xml}")
            return False

        fhasl_flag = True
    return fhasl_flag

def download_driver_without_signature(node, flash_files):
    """
        下载driver文件
    """
    TestLog("INFO", "Driver", "")
    fhasl_flag = False
    for item in flash_files:
        if not FlashConfig.check_driver(item):
            continue
        TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
        TestLog("INFO", " ", f"DRIVER文件下载: {item.path_hexS19}")
        if not download_file(node, item.path_hexS19):
            TestLog("FAIL", " ", f"DRIVER文件下载失败: {item.path_hexS19}")
            return False

        TestLog("INFO", " ", f"跳过DRIVER文件安全签名验证: {item.path_xml}")

        fhasl_flag = True
    return fhasl_flag

def download_driver_stop_within_transfer_data(node, flash_files):
    """
        下载driver文件----数据传输中停止
    """
    TestLog("INFO", "Driver", "")
    fhasl_flag = False
    for item in flash_files:
        if not FlashConfig.check_driver(item):
            continue
        TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
        TestLog("INFO", " ", f"DRIVER文件下载: {item.path_hexS19}")
        if not download_file_stop_within_transfer_data(node, item.path_hexS19, "None"):
            TestLog("FAIL", " ", f"DRIVER文件下载失败: {item.path_hexS19}")
            return False

        TestLog("INFO", " ", f"DRIVER文件安全签名验证: {item.path_xml}")
        if not check_memory(node, item.path_xml, item.path_hexS19):
            TestLog("FAIL", " ", f"DRIVER文件安全签名验证失败: {item.path_xml}")
            return False

        fhasl_flag = True
        return True
    return fhasl_flag

def download_app(node, flash_files):
    """
        下载APP文件
    """
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
        if not check_memory(node, item.path_xml, item.path_hexS19):
            TestLog("FAIL", " ", f"APP文件安全签名验证失败: {item.path_xml}")
            return False

        fhasl_flag = True
    return fhasl_flag

def download_app_without_signature(node, flash_files):
    """
        下载APP文件
    """
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

        TestLog("INFO", " ", f"跳过APP文件安全签名验证: {item.path_xml}")
        fhasl_flag = True
    return fhasl_flag

def download_app_until_erase_memory(node, flash_files):
    """
        下载APP文件----直到擦除内存
    """
    for item in flash_files:
        if not FlashConfig.check_app(item):
            continue
        TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
        TestLog("INFO", " ", f"APP内存擦除: {item.path_hexS19}")
        if not erase_memory(node, item.path_hexS19):
            TestLog("FAIL", " ", f"APP内存擦除失败: {item.path_hexS19}")
            return False
    return True

def download_app_before_erase_memory(node, flash_files):
    """
        下载APP文件----擦除内存前
    """
    for item in flash_files:
        if not FlashConfig.check_app(item):
            continue
        TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
    return True

def download_app_doing_erase_memory(node, flash_files):
    """
        下载APP文件----直到擦除内存
    """
    for item in flash_files:
        if not FlashConfig.check_app(item):
            continue
        TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
        TestLog("INFO", " ", f"APP内存擦除: {item.path_hexS19}")
        erase_memory_without_response(node, item.path_hexS19)
        return True
    return True

def download_app_stop_witin_transfer_data(node, flash_files, stopType: str):
    """
        下载APP文件，在数据传输过程中停止
    """
    TestLog("INFO", "APP", "")
    for item in flash_files:
        if not FlashConfig.check_app(item):
            continue
        TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
        TestLog("INFO", " ", f"APP内存擦除: {item.path_hexS19}")
        if not erase_memory(node, item.path_hexS19):
            TestLog("FAIL", " ", f"APP内存擦除失败: {item.path_hexS19}")
            return False, None

        TestLog("INFO", " ", f"APP文件下载: {item.path_hexS19}")
        return download_file_stop_within_transfer_data(node, item.path_hexS19, stopType)
    return True, None

def download_app_stop_witin_transfer_data_more_2_bytes(node, flash_files):
    """
        下载APP文件，在数据传输过程中停止
    """
    TestLog("INFO", "APP", "")
    for item in flash_files:
        if not FlashConfig.check_app(item):
            continue
        TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
        TestLog("INFO", " ", f"APP内存擦除: {item.path_hexS19}")
        if not erase_memory(node, item.path_hexS19):
            TestLog("FAIL", " ", f"APP内存擦除失败: {item.path_hexS19}")
            return False

        TestLog("INFO", " ", f"APP文件下载: {item.path_hexS19}")
        return download_file_stop_within_transfer_data_more_2_bytes(node, item.path_hexS19)
    return True, None

def download_app_stop_witin_transfer_data_less_2_bytes(node, flash_files):
    """
        下载APP文件，在数据传输过程中停止
    """
    TestLog("INFO", "APP", "")
    for item in flash_files:
        if not FlashConfig.check_app(item):
            continue
        TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
        TestLog("INFO", " ", f"APP内存擦除: {item.path_hexS19}")
        if not erase_memory(node, item.path_hexS19):
            TestLog("FAIL", " ", f"APP内存擦除失败: {item.path_hexS19}")
            return False

        TestLog("INFO", " ", f"APP文件下载: {item.path_hexS19}")
        return download_file_stop_within_transfer_data_less_2_bytes(node, item.path_hexS19)
    return True, None

def download_app_stop_witin_transfer_data_skip_counter(node, flash_files):
    """
        下载APP文件，在数据传输过程中停止
    """
    TestLog("INFO", "APP", "")
    for item in flash_files:
        if not FlashConfig.check_app(item):
            continue
        TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
        TestLog("INFO", " ", f"APP内存擦除: {item.path_hexS19}")
        if not erase_memory(node, item.path_hexS19):
            TestLog("FAIL", " ", f"APP内存擦除失败: {item.path_hexS19}")
            return False

        TestLog("INFO", " ", f"APP文件下载: {item.path_hexS19}")
        return download_file_stop_within_transfer_data_skip_counter(node, item.path_hexS19)
    return True, None

def download_app_stop_witin_transfer_data_with_same_counter(node, flash_files):
    """
        下载APP文件，在数据传输过程中停止
    """
    TestLog("INFO", "APP", "")
    for item in flash_files:
        if not FlashConfig.check_app(item):
            continue
        TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
        TestLog("INFO", " ", f"APP内存擦除: {item.path_hexS19}")
        if not erase_memory(node, item.path_hexS19):
            TestLog("FAIL", " ", f"APP内存擦除失败: {item.path_hexS19}")
            return False

        TestLog("INFO", " ", f"APP文件下载: {item.path_hexS19}")
        return download_file_stop_within_transfer_data_with_same_counter(node, item.path_hexS19)
    return True, None

def download_app_stop_without_transfer_data(node, flash_files):
    """
        下载APP文件，在数据传输过程中停止
    """
    TestLog("INFO", "APP", "")
    for item in flash_files:
        if not FlashConfig.check_app(item):
            continue
        TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
        TestLog("INFO", " ", f"APP内存擦除: {item.path_hexS19}")
        if not erase_memory(node, item.path_hexS19):
            TestLog("FAIL", " ", f"APP内存擦除失败: {item.path_hexS19}")
            return False

        TestLog("INFO", " ", f"APP文件下载: {item.path_hexS19}")
        return download_file_without_transfer_data(node, item.path_hexS19)
    return True, None

def phase_programming_within_transfer_data(node, flash_files):
    """
        下载APP文件----数据传输中
    """
    TestLog("INFO", "APP", "")
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
        return True
    return True

def download_file_with_22_after_34_interference(node: UDSNode, file_path: str, did: int = 0xF089):
    """
        下载文件，并在第一个34请求后发送22服务干扰
    """
    TestLog("INFO", " ", f"hex_path={file_path}, interference_did=0x{did:04X}")
    block_infos, start_addr = parse_flashFile(file_path)
    if start_addr is None:
        TestLog("INFO", " ", f"<parse_flashFile> Failed to find start address.")
        return -1

    first_34_done = False
    for idx, block in enumerate(block_infos):
        start_address = block["address"]
        data = block["data"]
        length = len(data)
        resp = node.Service_0x34_RequestDownload(dataformat=0x00,
                                                 size_len=4,
                                                 address_len=4,
                                                 size=length,
                                                 address=start_address)
        if not (resp.data[0] == 0x74):
            TestLog("FAIL", " ", f"RequestDownload(34)失败: 非肯定响应{resp}")
            return False

        if not first_34_done:
            TestLog("INFO", " ", f"在34请求后发送22服务诊断请求(22 {did:04X})")
            resp_22 = node.Service_0x22_ReadDataByIdentifier(id=did)
            if resp_22 is not None:
                TestLog("INFO", " ", f"DUT响应了22服务请求: {resp_22.data.hex(' ').upper()}")
            else:
                TestLog("INFO", " ", "DUT忽略22服务请求，不回复响应报文(符合预期)")
            first_34_done = True

        TestLog("INFO", " ", "开始数据传输")
        TestLog("INFO", " ", "数据传输36...")
        maxNumberOfBlockLength = get_max_nummber_of_blocklength_from_0x74(resp)
        maxNumberOfBlockLength = maxNumberOfBlockLength - 2
        counter = 1
        while True:
            record = data[:maxNumberOfBlockLength]
            resp = node.Service_0x36_TransferData_WithoutPrint(counter, record, timeout=10)
            if resp is None:
                TestLog("FAIL", " ", f"TransferData(36)失败: 未检测到响应报文")
                return False
            if not (resp.data[0] == 0x76):
                TestLog("FAIL", " ", f"TransferData(36)失败: 非肯定响应{resp}")
                return False
            time.sleep(0.001)
            data = data[maxNumberOfBlockLength:]
            if len(data) == 0:
                break
            counter += 1
            if counter == 0xFF + 1:
                counter = 0
        TestLog("INFO", " ", "完成数据传输")
        resp = node.Service_0x37_RequestTransferExit()
        if not (resp.data[0] == 0x77):
            TestLog("FAIL", " ", f"RequestTransferExit(37)失败: 非肯定响应{resp.data}")
            return False
    return True

def download_file_with_22_after_36_interference(node: UDSNode, file_path: str, did: int = 0xF089):
    """
        下载文件，并在36传输完成后(37之前)发送22服务干扰
    """
    TestLog("INFO", " ", f"hex_path={file_path}, interference_did=0x{did:04X}")
    block_infos, start_addr = parse_flashFile(file_path)
    if start_addr is None:
        TestLog("INFO", " ", f"<parse_flashFile> Failed to find start address.")
        return -1

    for idx, block in enumerate(block_infos):
        start_address = block["address"]
        data = block["data"]
        length = len(data)
        resp = node.Service_0x34_RequestDownload(dataformat=0x00,
                                                 size_len=4,
                                                 address_len=4,
                                                 size=length,
                                                 address=start_address)
        if not (resp.data[0] == 0x74):
            TestLog("FAIL", " ", f"RequestDownload(34)失败: 非肯定响应{resp}")
            return False

        TestLog("INFO", " ", "开始数据传输")
        TestLog("INFO", " ", "数据传输36...")
        maxNumberOfBlockLength = get_max_nummber_of_blocklength_from_0x74(resp)
        maxNumberOfBlockLength = maxNumberOfBlockLength - 2
        counter = 1
        while True:
            record = data[:maxNumberOfBlockLength]
            resp = node.Service_0x36_TransferData_WithoutPrint(counter, record, timeout=10)
            if resp is None:
                TestLog("FAIL", " ", f"TransferData(36)失败: 未检测到响应报文")
                return False
            if not (resp.data[0] == 0x76):
                TestLog("FAIL", " ", f"TransferData(36)失败: 非肯定响应{resp}")
                return False
            time.sleep(0.001)
            data = data[maxNumberOfBlockLength:]
            if len(data) == 0:
                break
            counter += 1
            if counter == 0xFF + 1:
                counter = 0
        TestLog("INFO", " ", "完成数据传输")

        TestLog("INFO", " ", f"在36传输完成后发送22服务诊断请求(22 {did:04X})")
        resp_22 = node.Service_0x22_ReadDataByIdentifier(id=did)
        if resp_22 is not None:
            TestLog("INFO", " ", f"DUT响应了22服务请求: {resp_22.data.hex(' ').upper()}")
        else:
            TestLog("INFO", " ", "DUT忽略22服务请求，不回复响应报文(符合预期)")

        resp = node.Service_0x37_RequestTransferExit()
        if not (resp.data[0] == 0x77):
            TestLog("FAIL", " ", f"RequestTransferExit(37)失败: 非肯定响应{resp.data}")
            return False
    return True


def steps_before_download(node: UDSNode, support_partition_ab=False):
    TestLog("INFO", "进入编程会话", "10 02")
    if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return False, f"编程阶段失败: 进入编程会话失败"

    TestLog("INFO", "安全访问", "27 11")
    if not security_access(node, 0x11):
        return False, "编程阶段失败: 安全访问失败"

    # 默认A分区的文件
    part = "A"

    if support_partition_ab is True:
        status, resp = service_22_check(node, 0xF0F0, expect_data=[0x62, 0xF0, 0xF0], expect_str="肯定响应62 F0 F0")
        if not status:
            return False, "编程阶段失败: 支持AB分区时，22 F0 F0非肯定响应"
        if resp.data[3] == 0x41:
            # A分区有效，选B分区
            part = "B"
        elif resp.data[3] == 0x42:
            # B分区有效，选A分区
            part = "A"
        else:
            return False, "编程阶段失败: 支持AB分区时，22 F0 F0的响应分区不在有效范围[0, 1]内"

    TestLog("INFO", "写入指纹", "2E F1 84")
    if not write_fingerprint(node):
        return False, "编程阶段失败: 写入指纹失败"
    return True, part


def steps_before_download_without_fingerprint(node: UDSNode, support_partition_ab=False):
    TestLog("INFO", "进入编程会话", "10 02")
    if not service_10_check(node, 0x02, expect_data=[0x50, 0x02], expect_str="肯定响应(50 02)"): return False, f"编程阶段失败: 进入编程会话失败"

    TestLog("INFO", "安全访问", "27 11")
    if not security_access(node, 0x11):
        return False, "编程阶段失败: 安全访问失败"

    # 默认A分区的文件
    part = "A"

    if support_partition_ab is True:
        status, resp = service_22_check(node, 0xF0F0, expect_data=[0x62, 0xF0, 0xF0], expect_str="肯定响应62 F0 F0")
        if not status:
            return False, "编程阶段失败: 支持AB分区时，22 F0 F0非肯定响应"
        if resp.data[3] == 0:
            # A分区有效，选B分区
            part = "B"
        elif resp.data[3] == 1:
            # B分区有效，选A分区
            part = "A"
        else:
            return False, "编程阶段失败: 支持AB分区时，22 F0 F0的响应分区不在有效范围[0, 1]内"

    TestLog("INFO", " ", "跳过写入指纹(2E F1 84)")
    return True, part

class TesterPresentManager:
    flag = False
    status = "stopped"

def tester_present_start(node, period_ms=2000):
    """
        开始周期发送3E 80
    """
    can_channel = DEFAULT_CAN_CHANNELS[0] if DEFAULT_CAN_CHANNELS else 1
    rTesterPresentMsgData = [0x02,0x3E,0x80,0x00,0x00,0x00,0x00,0x00]
    msg = canmsg_create(node.func_id, 8, data=rTesterPresentMsgData, rtr=0, fdf=P.TpInfo.CanFDMode, brs=0, ext=0)
    if TesterPresentManager.status == "running":
        return
    def run(node, period_ms):
        while TesterPresentManager.flag is True:
            send_canmsg(can_channel, msg)
            # node.Service_0x3E_TesterPresent(0x80, func_req=True)
            time.sleep(period_ms/1000)

    TesterPresentManager.flag = True
    threading.Thread(target=run, args=(node, period_ms), daemon=True).start()
    TesterPresentManager.status = "running"

def tester_present_stop():
    """
        停止周期发送3E 80
    """
    TesterPresentManager.flag = False
    TesterPresentManager.status = "stopped"

class VoltageJitter:
    flag = False
    status = "stopped"

def voltage_jitter_start(period_ms=1000):
    """
        开始电压抖动
    """
    rLowVoltage = 9  # 低压测试电压值（规范要求9V）
    rHighVoltage = 16  # 高压测试电压值（规范要求16V）
    rVstep = 0.1  # 电压步进值（规范要求0.1V/s）
    current_voltage = rLowVoltage
    ctx.power_ctrl.set_voltage(rLowVoltage)
    time.sleep(1)
    if VoltageJitter.status == "running":
        return
    def run(period_ms):
        nonlocal current_voltage, rVstep
        while VoltageJitter.flag is True:
            current_voltage += rVstep
            if current_voltage > rHighVoltage:
                current_voltage = rHighVoltage
                rVstep = -abs(rVstep)
            if current_voltage < rLowVoltage:
                current_voltage = rLowVoltage
                rVstep = abs(rVstep)
            ctx.power_ctrl.set_voltage(current_voltage)
            time.sleep(period_ms/1000)

    VoltageJitter.flag = True
    threading.Thread(target=run, args=(period_ms,), daemon=True).start()
    VoltageJitter.status = "running"

def voltage_jitter_stop():
    """
        停止电压抖动
    """
    VoltageJitter.flag = False
    VoltageJitter.status = "stopped"

def get_flash_file(msg_22F0F0, flash_config: FlashConfig):
    """
        根据22 F0 F0的响应结果，判断选择使用哪个分区文件
    """
    if msg_22F0F0 == "A":
        TestLog("INFO", " ", "选择分区A的文件进行刷写")
        return flash_config.flash_files_a
    else:
        TestLog("INFO", " ", "选择分区B的文件进行刷写")
        return flash_config.flash_files_b

# 预编程阶段
def phase_pre_programming(node: UDSNode):
    TestLog("INFO", "默认会话", "10 01")
    resp = node.Service_0x10_SessionControl(0x01)
    status, msg = check_resp(resp, [0x50, 0x01], "肯定响应(50 01)")
    if not status: return False, f"预编程阶段失败: {msg}"
    TestLog("PASS", " ", "进入默认会话成功(50 01)")

    tester_present_stop()

    TestLog("INFO", "扩展会话", "10 83")
    node.Service_0x10_SessionControl(0x83, func_req=True)
    time.sleep(0.02)

    # 开启周期发送3E 80
    TestLog("INFO", " ", "开始周期发送3E 80")
    tester_present_start(node)

    TestLog("INFO", "检查编程条件", "31 01 02 03")
    resp = node.Service_0x31_RoutineControl(0x01, 0x0203)
    status, msg = check_resp(resp, [0x71, 0x01, 0x02, 0x03, 0x00], "肯定响应(71 01 02 03 00)")
    if not status: return False, f"预编程阶段失败: {msg}"

    TestLog("INFO", "关闭DTC", "85 82")
    node.Service_0x85_ControlDTCSetting(0x82, func_req=True)
    time.sleep(0.2)

    TestLog("INFO", "关闭通讯", "28 83 03")
    node.Service_0x28_CommunicationControl(0x83, 0x03, func_req=True)
    time.sleep(0.2)

    return True, "预编程阶段完成"

# 预编程阶段
def phase_pre_programming_without_precondition_check(node: UDSNode):
    TestLog("INFO", "默认会话", "10 01")
    resp = node.Service_0x10_SessionControl(0x01)
    status, msg = check_resp(resp, [0x50, 0x01], "肯定响应(50 01)")
    if not status: return False, f"预编程阶段失败: {msg}"
    TestLog("PASS", " ", "进入默认会话成功(50 01)")

    tester_present_stop()

    TestLog("INFO", "扩展会话", "10 83")
    node.Service_0x10_SessionControl(0x83, func_req=True)
    time.sleep(0.2)

    # 开启周期发送3E 80
    tester_present_start(node)

    TestLog("INFO", "跳过检查编程条件", "")

    TestLog("INFO", "关闭DTC", "85 82")
    node.Service_0x85_ControlDTCSetting(0x82, func_req=True)
    time.sleep(0.2)

    TestLog("INFO", "关闭通讯", "28 83 03")
    node.Service_0x28_CommunicationControl(0x83, 0x03, func_req=True)
    time.sleep(0.2)

    return True, "预编程阶段完成"

# 编程阶段
def phase_programming(node: UDSNode, flash_config: FlashConfig, support_partition_ab=False):
    # 下载前的步骤：编程会话、安全访问、写指纹
    status, part_msg = steps_before_download(node, support_partition_ab)
    if not status:
        return False, part_msg

    ff = get_flash_file(part_msg, flash_config)

    # 下载driver
    if not download_driver(node, ff):
        return False, "编程阶段失败: 下载DRIVER失败"

    # 下载app
    if not download_app(node, ff):
        return False, "编程阶段失败: 下载APP失败"

    TestLog("INFO", "检查编程依赖性", "31 01 FF 01")
    if not check_programming_dependencies(node):
        return False, "编程阶段失败: 检查编程依赖失败"

    return True, "编程阶段完成"

# 编程阶段
def phase_programming_with_prevent_switch_part(node: UDSNode, flash_config: FlashConfig, support_partition_ab=False):
    # 下载前的步骤：编程会话、安全访问、写指纹
    status, part_msg = steps_before_download(node, support_partition_ab)
    if not status:
        return False, part_msg

    ff = get_flash_file(part_msg, flash_config)

    # 下载driver
    if not download_driver(node, ff):
        return False, "编程阶段失败: 下载DRIVER失败"

    # 下载app
    if not download_app(node, ff):
        return False, "编程阶段失败: 下载APP失败"

    TestLog("INFO", "阻止自动切区", "31 01 DD 0F")
    status, resp = service_31_check(node, 0x01, 0xDD0F, expect_data=[0x71, 0x01, 0xDD, 0x0F, 0x00],
                                    expect_str="肯定响应(71 01 DD 0F 00)")
    if not status:
        return False, "阻止自动切区失败: 下载APP失败"

    TestLog("INFO", "检查编程依赖性", "31 01 FF 01")
    if not check_programming_dependencies(node):
        return False, "编程阶段失败: 检查编程依赖失败"

    return True, "编程阶段完成"

# 编程阶段
def phase_programming_until_erase_memory(node: UDSNode, flash_config: FlashConfig, support_partition_ab=False):
    # 下载前的步骤：编程会话、安全访问、写指纹
    status, part_msg = steps_before_download(node, support_partition_ab)
    if not status:
        return False, part_msg

    ff = get_flash_file(part_msg, flash_config)

    # 下载driver
    if not download_driver(node, ff):
        return False, "编程阶段失败: 下载DRIVER失败"

    # 下载app
    if not download_app_until_erase_memory(node, ff):
        return False, "编程阶段失败: 内存擦除失败"

    return True, "编程阶段完成"

# 编程阶段
def phase_programming_before_erase_memory(node: UDSNode, flash_config: FlashConfig, support_partition_ab=False):
    # 下载前的步骤：编程会话、安全访问、写指纹
    status, part_msg = steps_before_download(node, support_partition_ab)
    if not status:
        return False, part_msg

    ff = get_flash_file(part_msg, flash_config)

    # 下载driver
    if not download_driver(node, ff):
        return False, "编程阶段失败: 下载DRIVER失败"

    # 下载app
    if not download_app_before_erase_memory(node, ff):
        return False, "编程阶段失败: 内存擦除失败"

    return True, "编程阶段完成"

# 编程阶段
def phase_programming_doing_erase_memory(node: UDSNode, flash_config: FlashConfig, support_partition_ab=False):
    # 下载前的步骤：编程会话、安全访问、写指纹
    status, part_msg = steps_before_download(node, support_partition_ab)
    if not status:
        return False, part_msg

    ff = get_flash_file(part_msg, flash_config)

    # 下载driver
    if not download_driver(node, ff):
        return False, "编程阶段失败: 下载DRIVER失败"

    # 下载app
    download_app_doing_erase_memory(node, ff)

    return True, "编程阶段完成"

# 编程阶段
def phase_programming_stop_within_transfer_data(node: UDSNode, flash_config: FlashConfig, stopType: str, support_partition_ab=False):
    # 下载前的步骤：编程会话、安全访问、写指纹
    status, part_msg = steps_before_download(node, support_partition_ab)
    if not status:
        return False, part_msg

    ff = get_flash_file(part_msg, flash_config)

    # 下载driver
    if not download_driver(node, ff):
        return False, "编程阶段失败: 下载DRIVER失败"

    # 下载app
    return download_app_stop_witin_transfer_data(node, ff, stopType)


# 编程阶段
def phase_programming_stop_within_transfer_data_more_2_bytes(node: UDSNode, flash_config: FlashConfig, support_partition_ab=False):
    # 下载前的步骤：编程会话、安全访问、写指纹
    status, part_msg = steps_before_download(node, support_partition_ab)
    if not status:
        return False, part_msg

    ff = get_flash_file(part_msg, flash_config)

    # 下载driver
    if not download_driver(node, ff):
        return False, "编程阶段失败: 下载DRIVER失败"

    # 下载app
    return download_app_stop_witin_transfer_data_more_2_bytes(node, ff)

# 编程阶段
def phase_programming_stop_within_transfer_data_skip_counter(node: UDSNode, flash_config: FlashConfig, support_partition_ab=False):
    # 下载前的步骤：编程会话、安全访问、写指纹
    status, part_msg = steps_before_download(node, support_partition_ab)
    if not status:
        return False, part_msg

    ff = get_flash_file(part_msg, flash_config)

    # 下载driver
    if not download_driver(node, ff):
        return False, "编程阶段失败: 下载DRIVER失败"

    # 下载app
    return download_app_stop_witin_transfer_data_skip_counter(node, ff)

# 编程阶段
def phase_programming_stop_within_transfer_data_with_same_counter(node: UDSNode, flash_config: FlashConfig, support_partition_ab=False):
    # 下载前的步骤：编程会话、安全访问、写指纹
    status, part_msg = steps_before_download(node, support_partition_ab)
    if not status:
        return False, part_msg

    ff = get_flash_file(part_msg, flash_config)

    # 下载driver
    if not download_driver(node, ff):
        return False, "编程阶段失败: 下载DRIVER失败"

    # 下载app
    return download_app_stop_witin_transfer_data_with_same_counter(node, ff)

# 编程阶段 - 在driver传输数据中停止
def phase_programming_stop_driver_within_transfer_data(node: UDSNode, flash_config: FlashConfig, support_partition_ab=False):
    # 下载前的步骤：编程会话、安全访问、写指纹
    status, part_msg = steps_before_download(node, support_partition_ab)
    if not status:
        return False, part_msg

    ff = get_flash_file(part_msg, flash_config)

    # 下载driver - 在传输数据中停止
    if not download_driver_stop_within_transfer_data(node, ff):
        return False, "编程阶段失败: 下载DRIVER失败"

    return True, "DRIVER传输中停止"
# 编程阶段
def phase_programming_stop_without_transfer_data(node: UDSNode, flash_config: FlashConfig, support_partition_ab=False):
    # 下载前的步骤：编程会话、安全访问、写指纹
    status, part_msg = steps_before_download(node, support_partition_ab)
    if not status:
        return False, part_msg

    ff = get_flash_file(part_msg, flash_config)

    # 下载driver
    if not download_driver(node, ff):
        return False, "编程阶段失败: 下载DRIVER失败"

    # 下载app
    return download_app_stop_without_transfer_data(node, ff)

# 编程阶段
def phase_programming_skip_dependencies(node: UDSNode, flash_config: FlashConfig, support_partition_ab=False):
    # 下载前的步骤：编程会话、安全访问、写指纹
    status, part_msg = steps_before_download(node, support_partition_ab)
    if not status:
        return False, part_msg

    ff = get_flash_file(part_msg, flash_config)

    # 下载driver
    if not download_driver(node, ff):
        return False, "编程阶段失败: 下载DRIVER失败"

    # 下载app
    if not download_app(node, ff):
        return False, "编程阶段失败: 下载APP失败"

    TestLog("INFO", "跳过检查编程依赖性", "")

    return True, "编程阶段完成"


# 后编程阶段
def phase_pro_programming(node: UDSNode):
    TestLog("INFO", "打开通讯", "28 80 03")
    node.Service_0x28_CommunicationControl(0x80, 0x03)
    time.sleep(0.2)

    tester_present_stop()

    TestLog("INFO", "ECU复位", "11 01")
    resp = node.Service_0x11_ECUReset(0x01)
    status, msg = check_resp(resp, [0x51, 0x01], "肯定响应(51 01)")
    if not status: return False, f"后编程阶段失败: {msg}"

    time.sleep(P.DiagServiceInfo.ResetTime/1000)

    TestLog("INFO", "扩展会话", "10 03")
    resp = node.Service_0x10_SessionControl(0x03)
    status, msg = check_resp(resp, [0x50, 0x03], "肯定响应(50 03)")
    if not status: return False, f"后编程阶段失败: {msg}"

    TestLog("INFO", "清除DTC", "14 FF FF FF")
    resp = node.Service_0x14_ClearDiagnosticInformation(h=0xFF, m=0xFF, l=0xFF)
    status, msg = check_resp(resp, [0x54], "肯定响应(54)")
    if not status: return False, f"后编程阶段失败: {msg}"

    TestLog("INFO", "打开DTC", "85 81")
    node.Service_0x85_ControlDTCSetting(0x81, func_req=True)
    time.sleep(0.2)

    TestLog("INFO", "默认会话", "10 81")
    node.Service_0x10_SessionControl(0x81, func_req=True)
    time.sleep(0.2)

    return True, "后编程阶段完成"

def main_flash(node, flash_config: FlashConfig, support_partition_ab=False):
    """
        完整的刷写流程
    """
    # return True
    # 预编程阶段
    status, msg = phase_pre_programming(node)
    if not status:
        TestLog("FAIL", " ", "预编程阶段失败")
        return False

    # 编程阶段
    status, msg = phase_programming(node, flash_config, support_partition_ab)
    if not status:
        TestLog("FAIL", " ", "编程阶段失败")
        return False

    # 后编程阶段
    status, msg = phase_pro_programming(node)
    if not status:
        TestLog("FAIL", " ", "后编程阶段失败")
        return False
    return True

def main_flash_until_erase_memory(node, flash_config: FlashConfig, support_partition_ab=False):
    """
        完整的刷写流程
    """
    # 预编程阶段
    status, msg = phase_pre_programming(node)
    if not status:
        TestLog("FAIL", " ", "预编程阶段失败")
        return False

    # 编程阶段
    status, msg = phase_programming_until_erase_memory(node, flash_config, support_partition_ab)
    if not status:
        TestLog("FAIL", " ", "编程阶段失败")
        return False
    return True

def clear_ctx_can_messages():
    """清空 CAN 消息"""
    ctx.can.clear_messages()
    time.sleep(0.002)

def get_ctx_can_msg():
    time.sleep(2)
    msg = {}
    msg = [m for m in ctx.can.messages if m.channel == P.ECUInfo.CommCANChannelNum and m.direction == Direction.RX]
    return msg


def powerOn_WithoutCheck(normal_voltage=None, stable_time=None):
    """
    CAN电源设置与通信检查
    包括：电源设置、KL30上电、唤醒启动、CAN通信状态检查
    """
    from common.wakeup import WakeupStart

    try:
        # Step: 执行KL30上电
        TestLog("INFO", " ", "执行KL30上电")
        ctx.bob_ctrl.set_power('KL30', True)

        # Step: 根据DUT通信唤醒方式启动唤醒
        TestLog("INFO", " ", "根据DUT通信唤醒方式，启动ECU唤醒")
        WakeupStart()

        return 0

    except Exception as e:
        TestLog("FAIL", "CAN测试设置", f"CAN测试设置失败: {e}")
        import traceback
        TestLog("DEBUG", "CAN测试设置", f"详细错误: {traceback.format_exc()}")
        return -1

def powerOff():
    """
    CAN电源设置与通信检查
    包括：电源设置、KL30上电、唤醒启动、CAN通信状态检查
    """
    from common.wakeup import WakeupStop
    try:
        # 停止唤醒信号
        TestLog("INFO", " ", "停止唤醒信号")
        WakeupStop()

        # 关闭DUT电源
        TestLog("INFO", " ", "关闭DUT电源")
        ctx.bob_ctrl.set_power('KL30', False)
        time.sleep(2)
        ctx.bob_ctrl.set_power('KL15', False)
        time.sleep(2)

    except Exception as e:
        TestLog("FAIL", "CAN测试设置", f"CAN测试设置失败: {e}")
        import traceback
        TestLog("DEBUG", "CAN测试设置", f"详细错误: {traceback.format_exc()}")
        return -1

def switchPart(node: UDSNode, oldPart):
    TestLog("INFO", " ", f"已测试分区{oldPart}, 切换分区, 对另一个分区进行测试")
    TestLog("INFO", "Step1", f"读取当前运行分区(22 F0 F0)，记录读取结果数据为DATA")
    status, respMsg = service_22_check(node, 0xF0F0, expect_data=[0x62, 0xF0, 0xF0], expect_str="肯定响应62 F0 F0")
    if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
    if not status:
        return False
    data1 = f"0x{resp[3]:X}"
    TestLog("INFO", " ", f"DATA={data1}")
    if data1 != oldPart:
        TestLog("INFO", " ", f"已经处于另一个分区，无需切换")
        return True

    TestLog("INFO", "Step2", f"进入扩展会话，通过安全访问Level1")
    TestLog("INFO", " ", f"进入扩展会话")
    if not service_10_check(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
        return
    TestLog("INFO", " ", f"进入扩展会话")
    if not security_access(node, 0x01): return

    TestLog("INFO", "Step3",
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

    TestLog("INFO", "Step4", f"测试设备每间隔1s发送一次读取切区结果请求(31 03 DD 04)，"
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

    TestLog("INFO", "Step5", f"ECU复位(11 01)")
    if not service_11_check(node, 0x01, expect_data=[0x51, 0x01], expect_str="肯定响应(51 01)"):
        return False
    time.sleep(P.DiagServiceInfo.ResetTime / 1000)

    TestLog("INFO", "Step6", f"读取当前运行分区(22 F0 F0)，记录读取结果数据为DATA")
    status, respMsg = service_22_check(node, 0xF0F0, expect_data=[0x62, 0xF0, 0xF0], expect_str="肯定响应62 F0 F0")
    if (resp := (respMsg or type('', (), {'data': None})()).data) is None: return
    if not status:
        return False
    if data1 != oldPart:
        TestLog("PASS", " ", f"切换分区成功")
    else:
        TestLog("FAIL", " ", f"切换分区失败")
        return False

    return True

def parse_flashFile(file_path):
    file_path_lower = file_path.lower()
    if file_path_lower.endswith('.hex'):
        return parse_hex(file_path)
    elif file_path_lower.endswith('.s19'):
        return parse_s19(file_path)


def phase_programming_stop_after_request_download(node: UDSNode, flash_config: FlashConfig, support_partition_ab=False):
    """
        编程阶段 - 在34服务（请求下载）后停止
    """
    # 下载前的步骤：编程会话、安全访问、写指纹
    status, part_msg = steps_before_download(node, support_partition_ab)
    if not status:
        return False, part_msg

    ff = get_flash_file(part_msg, flash_config)

    # 下载driver
    if not download_driver(node, ff):
        return False, "编程阶段失败: 下载DRIVER失败"

    # 下载app - 只执行到34服务
    for item in ff:
        if not FlashConfig.check_app(item):
            continue
        TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
        TestLog("INFO", " ", f"APP内存擦除: {item.path_hexS19}")
        if not erase_memory(node, item.path_hexS19):
            TestLog("FAIL", " ", f"APP内存擦除失败: {item.path_hexS19}")
            return False, "编程阶段失败: 内存擦除失败"

        # 执行34服务
        block_infos, start_addr = parse_flashFile(item.path_hexS19)
        if start_addr is None:
            return False, "解析Flash文件失败"

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
                return False, "请求下载(34)失败"
            TestLog("INFO", " ", f"34服务完成，停止刷写流程")
            return True, "34服务后停止"

    return True, "编程阶段完成"


def phase_programming_stop_after_transfer_exit(node: UDSNode, flash_config: FlashConfig, support_partition_ab=False):
    """
        编程阶段 - 在37服务（传输退出）后停止
    """
    # 下载前的步骤：编程会话、安全访问、写指纹
    status, part_msg = steps_before_download(node, support_partition_ab)
    if not status:
        return False, part_msg

    ff = get_flash_file(part_msg, flash_config)

    # 下载driver
    if not download_driver(node, ff):
        return False, "编程阶段失败: 下载DRIVER失败"

    # 下载app - 执行到37服务后停止
    for item in ff:
        if not FlashConfig.check_app(item):
            continue
        TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
        TestLog("INFO", " ", f"APP内存擦除: {item.path_hexS19}")
        if not erase_memory(node, item.path_hexS19):
            TestLog("FAIL", " ", f"APP内存擦除失败: {item.path_hexS19}")
            return False, "编程阶段失败: 内存擦除失败"

        TestLog("INFO", " ", f"APP文件下载: {item.path_hexS19}")
        if not download_file(node, item.path_hexS19):
            TestLog("FAIL", " ", f"APP文件下载失败: {item.path_hexS19}")
            return False, "编程阶段失败: APP文件下载失败"

        TestLog("INFO", " ", f"37服务完成，停止刷写流程")
        return True, "37服务后停止"

    return True, "编程阶段完成"


def phase_programming_stop_after_erase_memory(node: UDSNode, flash_config: FlashConfig, support_partition_ab=False):
    """
        编程阶段 - 在擦除内存后停止
    """
    # 下载前的步骤：编程会话、安全访问、写指纹
    status, part_msg = steps_before_download(node, support_partition_ab)
    if not status:
        return False, part_msg

    ff = get_flash_file(part_msg, flash_config)

    # 下载driver
    if not download_driver(node, ff):
        return False, "编程阶段失败: 下载DRIVER失败"

    # 下载app - 只执行到擦除内存
    for item in ff:
        if not FlashConfig.check_app(item):
            continue
        TestLog("INFO", " ", f"开始刷写: {item.path_hexS19}")
        TestLog("INFO", " ", f"APP内存擦除: {item.path_hexS19}")
        if not erase_memory(node, item.path_hexS19):
            TestLog("FAIL", " ", f"APP内存擦除失败: {item.path_hexS19}")
            return False, "编程阶段失败: 内存擦除失败"

        TestLog("INFO", " ", f"擦除内存完成，停止刷写流程")
        return True, "擦除内存后停止"

    return True, "编程阶段完成"


def prepare_for_manual_transfer_data(node: UDSNode, flash_config: FlashConfig, support_partition_ab=False):
    # 下载前的步骤：编程会话、安全访问、写指纹
    status, part_msg = steps_before_download(node, support_partition_ab)
    if not status:
        return False, part_msg

    ff = get_flash_file(part_msg, flash_config)

    # 下载driver
    if not download_driver(node, ff):
        return False, "编程阶段失败: 下载DRIVER失败"

    # 找到APP文件并执行到34服务
    for item in ff:
        if not FlashConfig.check_app(item):
            continue

        app_hex_path = item.path_hexS19
        TestLog("INFO", " ", f"开始准备: {app_hex_path}")

        # 擦除APP内存
        TestLog("INFO", " ", f"APP内存擦除: {app_hex_path}")
        if not erase_memory(node, app_hex_path):
            TestLog("FAIL", " ", f"APP内存擦除失败: {app_hex_path}")
            return False, "编程阶段失败: 内存擦除失败"

        # 解析flash文件获取block信息
        block_infos, start_addr = parse_flashFile(app_hex_path)
        if start_addr is None:
            TestLog("FAIL", " ", "<parse_flashFile> Failed to find start address.")
            return False, "编程阶段失败: 解析flash文件失败"

        # 获取第一个block的信息
        if len(block_infos) == 0:
            return False, "编程阶段失败: flash文件中没有block数据"

        block = block_infos[0]
        start_address = block["address"]
        block_data = block["data"]
        data_len = len(block_data)

        # 执行34 RequestDownload
        TestLog("INFO", " ", f"执行34 RequestDownload, 地址=0x{start_address:08X}, 长度={data_len}")
        resp = node.Service_0x34_RequestDownload(dataformat=0x00,
                                                 size_len=4,
                                                 address_len=4,
                                                 size=data_len,
                                                 address=start_address)
        if resp is None:
            TestLog("FAIL", " ", "RequestDownload(34)失败: 未检测到响应报文")
            return False, "编程阶段失败: 34服务无响应"
        if resp.data[0] != 0x74:
            TestLog("FAIL", " ", f"RequestDownload(34)失败: 非肯定响应 {resp.data.hex(' ').upper()}")
            return False, "编程阶段失败: 34服务非肯定响应"

        # 从34响应中获取maxNumberOfBlockLength
        max_block_length = get_max_nummber_of_blocklength_from_0x74(resp)
        max_block_length = max_block_length - 2  # 减去counter和SID占用的字节

        TestLog("INFO", " ", f"34服务成功, maxNumberOfBlockLength={max_block_length}")

        result = {
            "app_hex_path": app_hex_path,
            "block_data": block_data,
            "start_address": start_address,
            "max_block_length": max_block_length
        }
        return True, result

    return False, "编程阶段失败: 未找到APP文件"

class SimMessageCtrl:
    def __init__(self):
        from common.utils import TimerCyclic
        self._TimerCyclic = TimerCyclic
        self._timers = []
        self._StopTimer = ""
        self.msgs = []

    # ---------- 一键全停 ----------
    def stop_all_timer(self):
        """全停，并清空列表。"""
        for tid in self._timers:
            self._TimerCyclic.stop(tid)
        self._timers.clear()

    def stop_timer(self, tid: str, remove=False):
        self._TimerCyclic.stop(tid)
        # 从列表里移除，不抛异常
        try:
            self._timers.remove(tid)
            self._StopTimer = tid
        except ValueError:
            pass

    def ids(self):
        """返回当前所有存活 ID。"""
        return self._timers.copy()

    def msgs(self):
        return self.msgs


sim_message_ctrl = SimMessageCtrl()


class EnvironmentSimulator:
    _SPEED_MSG_ID = P.CANInfo.SpeedMsgID
    _TIME_MSG_ID = P.CANInfo.TimeMsgID
    _POWERMODE_MSG_ID = P.CANInfo.PowerModeMsgID
    _POWERMODE_OFF = 0
    _POWERMODE_RUN = 1
    _POWERMODE_Invalid = 3
    _POWERMODE_ACC = 4
    _POWERMODE_CRANK = 5
    _EPT_READY_Unenable = 0
    _EPT_READY_Enable = 1

    def __init__(self):
        from common.utils import TimerCyclic
        # from common.can_utils import canmsg_create, send_canmsg
        self._active = False
        self._timer_ids = ['env_speed', 'env_time', 'env_powermode']
        self._config: Dict[str, Any] = {}
        self._TimerCyclic = TimerCyclic
        self._canmsg_create = canmsg_create
        self._send_canmsg = send_canmsg
        self._tx_cnt = {}

    def start(
        self,
        voltage: float = 13.5,
        speed: float = 90.0,
        odometer: int = 100,
        year: int = 2025, month: int = 6, day: int = 6,
        hour: int = 6, minute: int = 6, second: int = 6
    ) -> 'EnvironmentSimulator':
        self._config = {
            'voltage': voltage, 'speed': speed, 'odometer': odometer,
            'year': year, 'month': month, 'day': day,
            'hour': hour, 'minute': minute, 'second': second
        }

        TestLog("INFO", "环境模拟", f"启动: V={voltage}V, Speed={speed}km/h, ODO={odometer}km")

        self._set_voltage(voltage)
        msgs = self._set_can_messages()
        self._send_can_messages(msgs)

        self._active = True
        return self

    def stop(self) -> 'EnvironmentSimulator':
        print(self._timer_ids)
        from common.utils import TimerCyclic
        for tid in self._timer_ids:
            TimerCyclic.stop(tid)
        self._active = False
        TestLog("INFO", "环境模拟", "已停止")
        return self

    def _set_can_messages(self) -> List[Dict[str, object]]:
        from common.utils import TimerCyclic
        # from common.can_utils import canmsg_create, send_canmsg

        try:
            channel = DEFAULT_CAN_CHANNELS[0]
            is_canfd = P.ProjectInfo.ECUType == 2

        except Exception:
            channel, is_canfd = 1, False

        cfg = self._config
        msgs = []

        msgs.extend(self._build_speed_msg(self._SPEED_MSG_ID, cfg['speed'], cfg['odometer'], is_fdf=is_canfd))
        msgs.extend(self._build_time_msg(self._TIME_MSG_ID, cfg['year'], cfg['month'], cfg['day'],
                                cfg['hour'], cfg['minute'], cfg['second'], is_fdf=is_canfd))
        msgs.extend(self._build_powermode_msg(self._POWERMODE_MSG_ID, self._POWERMODE_RUN, is_fdf=is_canfd))
        msgs.extend(self._build_ept_ready_msg(self._EPT_READY_Enable, is_fdf=is_canfd))

        return msgs


    def _send_can_messages(self, msgs: List[Dict[str, object]]) -> None:
        try:
            ch = DEFAULT_CAN_CHANNELS[0]
            is_canfd = P.ProjectInfo.ECUType == 2

        except Exception:
            ch, is_canfd = 1, False

        for item in msgs:
            data = bytes(item['data'] or b'')
            dlc = int(item['dlc'] or 0)
            if not is_canfd:
                dlc = 8
            cycle_ms = int(item['cycle_ms'] or 0)
            data_id = item['data_id'] if item['data_id'] is not None else -1
            msg_id = int(item['msg_id'] or 0)

            TestLog("INFO", "报文创建",
                    f"创建报文: ID=0x{msg_id:x}, DLC={dlc}, FDF={is_canfd}, BRS={is_canfd}, 数据长度={len(data)}, 数据={' '.join(f'{b:02X}' for b in data)}")

            tid = f"sim_{msg_id:X}"
            self._tx_cnt.setdefault(tid, 0)
            profile, _ = set_profile(bool(is_canfd))

            def send_message(_msg_id=msg_id, _data=data, _dlc=dlc, _data_id=data_id, _is_canfd=is_canfd, _tid=tid, _profile=profile):
                if _data_id == -1:
                    msg = self._canmsg_create(_msg_id, _dlc, data=_data, fdf=int(_is_canfd), brs=int(_is_canfd))
                    if msg:
                        self._send_canmsg(ch, msg=msg)
                    return
                group = E2ESignalGroupInfo(
                    name="name",
                    startByte=0,
                    length=16 if _is_canfd else 8,
                    dataid=_data_id,
                    max_delta_counter_init=0,
                )
                tx_counter = self._tx_cnt[_tid]
                payload = build_e2e_payload(
                    group, _profile, _dlc,
                    tx_counter,
                    data=_data
                )
                msg = self._canmsg_create(_msg_id, _dlc, data=payload, fdf=int(_is_canfd), brs=int(_is_canfd))
                if msg:
                    self._send_canmsg(ch, msg=msg)
                max_counter = PROFILE_COUNTER_MAX[_profile]
                # tx_counter[tid] = (tx_counter[tid] + 1) % (max_counter + 1)
                self._tx_cnt[_tid] = (tx_counter + 1) % (max_counter + 1)

            self._timer_ids.append(tid)
            self._TimerCyclic.stop(tid)
            self._TimerCyclic.start(tid, cycle_ms, send_message)
            sim_message_ctrl._timers.append(tid)
        #
        # self._send_speed_message(self._SPEED_MSG_ID, cfg['speed'], cfg['odometer'], is_canfd=is_canfd)
        # # speed_data = self._build_speed_msg(cfg['speed'], cfg['odometer'])
        # # speed_msg = canmsg_create(self._SPEED_MSG_ID, len(speed_data), data=speed_data,
        # #                            fdf=1 if is_canfd else 0, brs=1 if is_canfd else 0)
        # # if speed_msg:
        # #     TimerCyclic.stop(self._timer_ids[0])
        # #     TimerCyclic.start(self._timer_ids[0], 100, send_canmsg, channel, msg=speed_msg)
        # #
        #
        # self._send_time_message(self._TIME_MSG_ID, cfg['year'], cfg['month'], cfg['day'],
        #                                   cfg['hour'], cfg['minute'], cfg['second'], is_canfd=is_canfd)
        # # time_data = self._build_time_msg(self._TIME_MSG_ID, cfg['year'], cfg['month'], cfg['day'],
        # #                                   cfg['hour'], cfg['minute'], cfg['second'])
        # # time_msg = canmsg_create(self._TIME_MSG_ID, 8, data=time_data,
        # #                           fdf=1 if is_canfd else 0, brs=1 if is_canfd else 0)
        # # if time_msg:
        # #     TimerCyclic.stop(self._timer_ids[1])
        # #     TimerCyclic.start(self._timer_ids[1], 500, send_canmsg, channel, msg=time_msg)
        #
        # self._send_powermode_message(self._POWERMODE_MSG_ID, self._POWERMODE_RUN, is_canfd=is_canfd)
        # # pm_data = self._build_powermode_msg(2)
        # # pm_msg = canmsg_create(self._POWERMODE_MSG_ID, 8, data=pm_data,
        # #                         fdf=1 if is_canfd else 0, brs=1 if is_canfd else 0)
        # # if pm_msg:
        # #     TimerCyclic.stop(self._timer_ids[2])
        # #     TimerCyclic.start(self._timer_ids[2], 20, send_canmsg, channel, msg=pm_msg)
        #
        # self._send_ept_ready_message(self._EPT_READY_Enable, is_canfd=is_canfd)

    def _build_speed_msg(self, speed_msg_id: int, speed_kmh: float, odometer: int, gear: str, is_fdf: bool) -> List[Dict[str, object]]:
        msgs: List[Dict[str, object]] = []
        speed_raw = int(speed_kmh / 0.05625)
        print(f'speed_kmh{speed_kmh}, {speed_raw}')
        gearmap = {'P': 0x0, 'R': 0x1, 'N': 0x2, 'D': 0x3}
        if speed_msg_id == 0x117:
            #车速
            dlc, cycle_ms, data_id, msg_id = 13, 10, 0x6117, 0x117
            data = bytearray(32)
            self._set_signal(self, data, 204, 13, speed_raw, False)
            self._set_signal(self, data, 205, 1, 1, False)  # 有效位
            msgs.append(
                {"data": data, "dlc": dlc, "cycle_ms": cycle_ms, "data_id": data_id, "msg_id": msg_id})

            #里程、档位
            gearmap = {'P': 0x0, 'R': 0x1, 'N': 0x2, 'D': 0x3}
            dlc, cycle_ms, data_id, msg_id = 13, 10, 0x611B, 0x11B
            data = bytearray(32)
            self._set_signal(self, data, 43, 20, odometer, False)
            #车速
            self._set_signal(self, data, 223, 13, speed_raw, False)
            self._set_signal(self, data, 226, 2, 1, False)  # 有效位
            #档位
            self._set_signal(self, data, 93, 2, gearmap[gear], False)
            self._set_signal(self, data, 94, 1, 1, False)  # 有效位
            self._set_signal(self, data, 89, 2, gearmap[gear], False)
            self._set_signal(self, data, 90, 1, 1, False)  # 有效位

            msgs.append(
                {"data": data, "dlc": dlc, "cycle_ms": cycle_ms, "data_id": data_id, "msg_id": msg_id})

            # 档位
            gearmap = {'P': 0x1, 'R': 0x2, 'N': 0x3, 'D': 0x4}
            dlc, cycle_ms, data_id, msg_id = 13, 20, 0x8184, 0x184
            data = bytearray(32)
            self._set_signal(self, data, 31, 4, gearmap[gear], False)
            self._set_signal(self, data, 205, 1, 1, False)  # 有效位
            msgs.append(
                {"data": data, "dlc": dlc, "cycle_ms": cycle_ms, "data_id": data_id, "msg_id": msg_id})

        elif speed_msg_id == 0x3AE:
            if is_fdf:
                data = bytearray(32)
                dlc, cycle_ms, data_id, msg_id = 13, 100, None, 0x3AE
            else:
                data = bytearray(8)
                dlc, cycle_ms, data_id, msg_id = 8, 100, None, 0x3AE
            #车速
            self._set_signal(self, data, 6, 13, speed_raw, False)
            self._set_signal(self, data, 7, 1, 1, False)  # 有效位
            #里程
            self._set_signal(self, data, 23, 20, speed_raw, False)
            #挡位
            self._set_signal(self, data, 35, 2, gearmap[gear], False)
            self._set_signal(self, data, 48, 1, 1, False)  # 有效位
            msgs.append(
                {"data": data, "dlc": dlc, "cycle_ms": cycle_ms, "data_id": data_id, "msg_id": msg_id})
        elif speed_msg_id == 0x340:
            #0x340
            dlc, cycle_ms, data_id, msg_id = 13, 100, None, 0x340
            data = bytearray(32)
            self._set_signal(self, data, 31, 13, speed_raw, False)
            self._set_signal(self, data, 34, 1, 1, False)  # 有效位
            msgs.append(
                {"data": data, "dlc": dlc, "cycle_ms": cycle_ms, "data_id": data_id, "msg_id": msg_id})

            #0x3AE
            dlc, cycle_ms, data_id, msg_id = 13 if is_fdf else 8, 100, None, 0x3AE
            data = bytearray(32 if is_fdf else 8)
            #车速
            self._set_signal(self, data, 6, 13, speed_raw, False)
            self._set_signal(self, data, 7, 1, 1, False)  # 有效位
            #里程
            self._set_signal(self, data, 23, 20, speed_raw, False)
            #挡位
            self._set_signal(self, data, 35, 2, gearmap[gear], False)
            self._set_signal(self, data, 48, 1, 1, False)  # 有效位
            msgs.append(
                {"data": data, "dlc": dlc, "cycle_ms": cycle_ms, "data_id": data_id, "msg_id": msg_id})
        elif speed_msg_id == 0x161:
            dlc, cycle_ms, data_id, msg_id = 13, 10, 0x2161, 0x161
            data = bytearray(32)
            self._set_signal(self, data, 28, 13, speed_raw, False)
            self._set_signal(self, data, 29, 1, 1, False)
            msgs.append(
                {"data": data, "dlc": dlc, "cycle_ms": cycle_ms, "data_id": data_id, "msg_id": msg_id})

        sim_message_ctrl.msgs.extend(msgs)
        return msgs

    def _build_gear_msg(self, gear_msg_id: int, gear: str, is_fdf: bool) -> List[Dict[str, object]]:
        msgs: List[Dict[str, object]] = []
        gearmap = {'P': 0x0, 'R': 0x1, 'N': 0x2, 'D': 0x3}
        if gear_msg_id == 0x1F0:
            #档位
            dlc, cycle_ms, data_id, msg_id = 13, 20, 0x21F0, 0x1F0
            data = bytearray(32)
            self._set_signal(self, data, 31, 2, gearmap[gear], False)
            self._set_signal(self, data, 50, 1, 1, False)  # 有效位
            msgs.append(
                {"data": data, "dlc": dlc, "cycle_ms": cycle_ms, "data_id": data_id, "msg_id": msg_id})

        sim_message_ctrl.msgs.extend(msgs)
        return msgs

    def _build_time_msg(self, time_msg_id: int, year: int, month: int, day: int,
                        hour: int, minute: int, second: int, is_fdf: bool) -> List[Dict[str, object]]:
        msgs: List[Dict[str, object]] = []

        dlc, cycle_ms, data_id, msg_id = 8, 500, None, 0x5E2
        data = bytearray(dlc)
        self._set_signal(self, data, 7, 8, year - 2000, False)
        self._set_signal(self, data, 11, 4, month, False)
        self._set_signal(self, data, 20, 5, day, False)
        self._set_signal(self, data, 28, 5, hour, False)
        self._set_signal(self, data, 37, 6, minute, False)
        self._set_signal(self, data, 45, 6, second, False)
        self._set_signal(self, data, 57, 2, 1, False)  # 有效位
        msgs.append(
            {"data": data, "dlc": dlc, "cycle_ms": cycle_ms, "data_id": data_id, "msg_id": msg_id})

        sim_message_ctrl.msgs.extend(msgs)
        return msgs

    def _build_powermode_msg(self, powermode_msg_id: int, mode: int, is_fdf: bool) -> List[Dict[str, object]]:
        msgs: List[Dict[str, object]] = []
        if is_fdf:
            if powermode_msg_id == 0x1D3:
                dlc, cycle_ms, data_id, msg_id = 13, 20, 0x41D3, 0x1D3
                data = bytearray(32)
                self._set_signal(self, data, 39, 2, mode, False)
                self._set_signal(self, data, 37, 2, 0, False)
                self._set_signal(self, data, 31, 4, 3, False)
                self._set_signal(self, data, 27, 4, 3, False)
                msgs.append(
                    {"data": data, "dlc": dlc, "cycle_ms": cycle_ms, "data_id": data_id, "msg_id": msg_id})
            else:
                dlc, cycle_ms, data_id, msg_id = 13, 20, 0x41D2, 0x1D2
                data = bytearray(32)
                self._set_signal(self, data, 39, 2, mode, False)
                self._set_signal(self, data, 37, 2, 0, False)
                self._set_signal(self, data, 31, 4, 3, False)
                self._set_signal(self, data, 27, 4, 3, False)
                msgs.append(
                    {"data": data, "dlc": dlc, "cycle_ms": cycle_ms, "data_id": data_id, "msg_id": msg_id})
        else:
            dlc, cycle_ms, data_id, msg_id = 8, 20, 0x00C2, 0x1C2
            data = bytearray(dlc)
            self._set_signal(self, data, 39, 2, mode, False)
            self._set_signal(self, data, 37, 2, 0, False)
            msgs.append(
                {"data": data, "dlc": dlc, "cycle_ms": cycle_ms, "data_id": data_id, "msg_id": msg_id})

        sim_message_ctrl.msgs.extend(msgs)
        return msgs

    def _build_ept_ready_msg(self, value: int, is_fdf: bool) -> List[Dict[str, object]]:
        msgs: List[Dict[str, object]] = []
        dlc, cycle_ms, data_id, msg_id = 13, 20, 0x8184, 0x184
        data = bytearray(32)
        self._set_signal(self, data, 35, 1, value, False)
        msgs.append(
            {"data": data, "dlc": dlc, "cycle_ms": cycle_ms, "data_id": data_id, "msg_id": msg_id})

        sim_message_ctrl.msgs.extend(msgs)
        return msgs

    def _build_engine_speed_msg(self, enginespeed_msg_id: int, speed: int, is_fdf: bool) -> List[Dict[str, object]]:
        msgs: List[Dict[str, object]] = []
        if enginespeed_msg_id == 0x122:
            dlc, cycle_ms, data_id, msg_id = 13, 10, 0x8122, 0x122
            data = bytearray(32)
            self._set_signal(self, data, 141, 13, speed, False)
            self._set_signal(self, data, 142, 1, 1, False)
            msgs.append(
                {"data": data, "dlc": dlc, "cycle_ms": cycle_ms, "data_id": data_id, "msg_id": msg_id})
        elif enginespeed_msg_id == 0x19A:
            dlc, cycle_ms, data_id, msg_id = 13, 20, 0x619A, 0x19A
            data = bytearray(32)
            self._set_signal(self, data, 148, 13, speed, False)
            self._set_signal(self, data, 140, 1, 1, False)
            msgs.append(
                {"data": data, "dlc": dlc, "cycle_ms": cycle_ms, "data_id": data_id, "msg_id": msg_id})

        sim_message_ctrl.msgs.extend(msgs)
        return msgs



    @staticmethod
    def _set_signal(self, data: bytearray, start_bit: int, bit_length: int, value: int, is_intel: bool) -> None:
        array_pos = self._get_pair(bit_pos = start_bit)
        for i in range(bit_length):
            if is_intel:
                bit_pos = start_bit - i
                byte_idx = bit_pos // 8
                bit_offset = 7 - (bit_pos % 8)
                if byte_idx < len(data):
                    bit_val = (value >> (bit_length - 1 - i)) & 1
                    if bit_val:
                        data[byte_idx] |= (1 << bit_offset)
                    else:
                        data[byte_idx] &= ~(1 << bit_offset)
            else:
                bit_pos = self._get_pair(array_pos = array_pos + bit_length -1 - i)
                byte_idx = bit_pos // 8
                bit_offset = bit_pos % 8
                if byte_idx >= len(data):
                    continue
                bit_val = value & (1 << i)
                if bit_val:
                    data[byte_idx] |= (1 << bit_offset)
                else:
                    data[byte_idx] &= ~(1 << bit_offset)
                # print(f'{start_bit}, {bit_length}, {i}, {bit_pos}, {byte_idx}, {bit_offset}, {bit_val}')

    def _get_pair(self, array_pos=None, bit_pos=None):
        array_pos_list = []
        bit_pos_list = []

        for i in range(1500):
            base = i * 8
            for j in range(8):
                bit_pos_list.append(7 - j + base)
                array_pos_list.append(j + base)

        if array_pos is not None:
            return bit_pos_list[array_pos]
        if bit_pos is not None:
            for i in bit_pos_list:
                if bit_pos_list[i] == bit_pos:
                    return array_pos_list[i]
        return 0

env_simulator = EnvironmentSimulator()

def send_speed_gear(speed_msg_id: int, speed_kmh: float, gear_msg_id: int, gear: str):
    is_canfd = P.ProjectInfo.ECUType == 2
    msgs = env_simulator._build_speed_msg(speed_msg_id, speed_kmh, 100, gear, is_canfd)
    msgs.extend(env_simulator._build_gear_msg(gear_msg_id, gear, is_canfd))
    env_simulator._send_can_messages(msgs)

def send_rpm(enginespeed_msg_id: int, speed: int):
    is_canfd = P.ProjectInfo.ECUType == 2
    msgs = env_simulator._build_engine_speed_msg(enginespeed_msg_id, speed, is_canfd)
    env_simulator._send_can_messages(msgs)

