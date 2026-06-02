import queue
from can import Message

from library.uds.uds_node import UDSNode
from library.uds.bus_sim import BusSim
from slplus.cantp import sl_cantp
from uvtest.testlog import TestLog
from env.config import DEFAULT_CAN_CHANNELS
from common.params import P

DTC_COMM_ERROR = 0     # 诊断通信错误/无响应
DTC_NO_DTC = 1         # 无任何DTC
DTC_OTHER_DTC = 2      # 有DTC，但非E2E相关
DTC_E2E_DTC = 3        # 有E2E相关的DTC


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


def get_can_node(sa, ta, fa, is_canfd=False) -> UDSNode:
    busid = DEFAULT_CAN_CHANNELS[0]
    bus_obj = CANBusSim()
    bus_obj.init(busid, sa, ta, fa, is_canfd)
    node = UDSNode(bus_obj)
    return node



def clear_dtc(node) -> bool:
    resp = node.Service_0x14_ClearDiagnosticInformation(0xFF, 0xFF, 0xFF, timeout=50)
    if resp is None:
        TestLog("FAIL", "清除DTC", "无响应")
        return False

    data = list(resp.data) if hasattr(resp, 'data') else []
    if data and data[0] == 0x54:
        TestLog("PASS", "清除DTC", "成功")
        return True
    if len(data) >= 3 and data[0] == 0x7F:
        TestLog("FAIL", "清除DTC", f"NRC=0x{data[2]:02X}")
    else:
        TestLog("FAIL", "清除DTC", "响应异常")
    return False


def read_dtc(node, e2e_dtc: int = None) -> int:
    resp = node.Service_0x19_ReadDTCInformation(report_type=0x02, DTCStatusMask=0xFF, timeout=50)
    if resp is None:
        TestLog("FAIL", "读取DTC", "无响应")
        return DTC_COMM_ERROR

    data = list(resp.data) if hasattr(resp, 'data') else []

    # 检查负响应
    if len(data) >= 3 and data[0] == 0x7F:
        TestLog("FAIL", "读取DTC", f"NRC=0x{data[2]:02X}")
        return DTC_COMM_ERROR

    # 检查正响应
    if len(data) < 3 or data[0] != 0x59:
        TestLog("WARNING", "读取DTC", f"响应格式异常: {[hex(b) for b in data]}")
        return DTC_COMM_ERROR

    dtc_data = data[3:]
    if len(dtc_data) < 4:
        TestLog("INFO", "读取DTC", "未检测到DTC")
        return DTC_NO_DTC

    dtc_count = len(dtc_data) // 4
    TestLog("INFO", "读取DTC", f"检测到{dtc_count}个DTC")

    found_e2e = False
    for i in range(0, len(dtc_data) - 3, 4):
        dtc = (dtc_data[i] << 16) | (dtc_data[i+1] << 8) | dtc_data[i+2]
        status = dtc_data[i+3]
        TestLog("INFO", "读取DTC", f"DTC=0x{dtc:06X}, Status=0x{status:02X}")

        if e2e_dtc is not None and dtc == e2e_dtc:
            found_e2e = True
            TestLog("INFO", "读取DTC", f"匹配到E2E DTC: 0x{dtc:06X}")

    if e2e_dtc is not None:
        return DTC_E2E_DTC if found_e2e else DTC_OTHER_DTC
    else:
        return DTC_OTHER_DTC
