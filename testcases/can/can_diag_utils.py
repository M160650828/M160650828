import queue
from can import Message

from library.uds.uds_node import UDSNode
from library.uds.bus_sim import BusSim
from slplus.cantp import sl_cantp
from uvtest.testlog import TestLog
from env.config import DEFAULT_CAN_CHANNELS
from common.params import P


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


def check_expect_response(response_message, expect_data: list) -> (bool, str):
    if not response_message:
        return False, "未检测到响应报文"

    response_data = list(response_message.data)
    if bytes(expect_data) in bytes(response_data):
        return True, f"检测到期望响应报文, 期望={[hex(item) for item in expect_data]}, 实际={[hex(item) for item in response_data]}"

    return False, f"非期望响应报文, 期望={[hex(item) for item in expect_data]}, 实际={[hex(item) for item in response_data]}"


def service_10_check(node, session, expect_data, expect_str, func_req=False, *args, **kwargs):
    resp = node.Service_0x10_SessionControl(session, func_req=func_req, *args, **kwargs)
    pending_flag = False
    if expect_data is None:
        TestLog("INFO", "", f"{expect_data=}, {resp=}")
        if resp is None:
            return True  
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


def service_19_check(node, report_type, expect_data, expect_str, func_req=False, *args, **kwargs):
    resp = node.Service_0x19_ReadDTCInformation(report_type=report_type, func_req=func_req, *args, **kwargs)
    if expect_data is None:
        if resp is None:
            return True, resp 
        return False, resp 

    status, msg = check_expect_response(resp, expect_data)
    if status is False:
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
        return False, ""
    TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
    return True, resp


def service_22_check(node, dids, expect_data, expect_str, func_req=False, dl=None, dl_padding=0x00, timeout=5, *args, **kwargs):
    resp = node.Service_0x22_ReadDataByIdentifier(id=dids, func_req=func_req, dl=dl, dl_padding=dl_padding, timeout=timeout, *args, **kwargs)

    if expect_data is None:
        if resp is None:
            TestLog("PASS", "", f"期望: {expect_str}; 实际:无响应")
            return True, None  
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:收到响应")
        return False, resp  

    status, msg = check_expect_response(resp, expect_data)
    if status is False:
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
        return False, resp
    TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
    return True, resp


def service_14_check(node, dtc, expect_data, expect_str, func_req=False, *args, **kwargs):
    if dtc is not None:
        h, m, l = (dtc >> 16 & 0xFF), (dtc >> 8 & 0xFF), dtc & 0xFF
        resp = node.Service_0x14_ClearDiagnosticInformation(h, m, l, func_req=func_req, *args, **kwargs)
    else:
        resp = node.Service_0x14_ClearDiagnosticInformation(None, None, None, func_req=func_req, *args, **kwargs)

    if expect_data is None:
        if resp is None:
            return True, None 
        TestLog("FAIL", "", f"期望: {expect_str}; 实际: 收到响应 {resp.hex() if resp else 'None'}")
        return False, resp  

    status, msg = check_expect_response(resp, expect_data)
    if status is False:
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
        return False, resp
    TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
    return True, resp


def get_dtc_list_from_19_resp(response_message: Message) -> list:
    if response_message is None:
        return []

    resp_data = list(response_message.data) if hasattr(response_message, 'data') else list(response_message)

    dtc_list = []

    i = 3
    while i + 3 <= len(resp_data):
        dtc_high = resp_data[i]
        dtc_mid = resp_data[i + 1]
        dtc_low = resp_data[i + 2]
        dtc_status = resp_data[i + 3] if i + 3 < len(resp_data) else 0x00
        dtc_list.append({
            'dtc': (dtc_high, dtc_mid, dtc_low),
            'status': dtc_status
        })
        i += 4

    return dtc_list


def get_dtc_timeout(node, message_cycle=100, max_iterations=50, stop_sim_func=None, start_sim_func=None):
    """
    检测DTC超时阈值
    通过步进延时找到DTC超时的最小时间tTimeout.min
    @param node: UDS节点对象
    @param message_cycle: 报文周期(毫秒)，默认100ms
    @param max_iterations: 最大迭代次数，默认50
    @param stop_sim_func: 停止仿真报文的回调函数，无参数，默认None不执行
    @param start_sim_func: 启动仿真报文的回调函数，无参数，默认None不执行
    @return: (success, tTimeout_min) - success表示是否找到，tTimeout_min为超时时间(毫秒)
    """
    from slplus.time import sl_time

    Tdelay = int(0.8 * 10 * message_cycle)
    step_increment = int(10 * message_cycle * 0.05)
    tTimeout_min = None

    TestLog("INFO", "", f"开始检测DTC超时阈值，初始延时={Tdelay}ms，步进={step_increment}ms")

    for _ in range(max_iterations):
        service_14_check(node, dtc=0xFFFFFF, expect_data=[0x54], expect_str="$14 清除DTC")

        if stop_sim_func:
            stop_sim_func()

        sl_time().sleep(Tdelay)

        result_19, resp = service_19_check(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="$19 02 读取DTC",
            status_mask=0xFF
        )

        if result_19:
            dtc_list = get_dtc_list_from_19_resp(resp)
            if len(dtc_list) > 0:
                tTimeout_min = Tdelay
                TestLog("PASS", "", f"检测到DTC超时阈值 tTimeout.min = {tTimeout_min}ms")
                if start_sim_func:
                    start_sim_func()
                return True, tTimeout_min
                
        if start_sim_func:
            start_sim_func()

        Tdelay += step_increment

    TestLog("FAIL", "", f"在 {max_iterations} 次迭代内未能检测到DTC超时阈值")
    return False, None


def send_diagnostic_sequence(node, interval_ms=2000, dids_f189=0xF189, dids_f089=0xF089):
    from slplus.time import sl_time

    success = True

    # $10 01 
    if not service_10_check(node, session=0x01, expect_data=[0x50, 0x01], expect_str="$10 01 肯定响应(50 01)"):
        success = False
    sl_time().sleep(interval_ms)

    # $10 03
    if not service_10_check(node, session=0x03, expect_data=[0x50, 0x03], expect_str="$10 03 肯定响应(50 03)"):
        success = False
    sl_time().sleep(interval_ms)

    # $14 FF FF FF 
    try:
        node.Service_0x14_ClearDiagnosticInformation(h=0xFF, m=0xFF, l=0xFF)
    except Exception:
        pass
    sl_time().sleep(interval_ms)

    # $19 02 09 
    try:
        service_19_check(node, report_type=0x02, expect_data=[0x59, 0x02], expect_str="$19 02 肯定响应(59 02)", status_mask=0x09)
    except Exception:
        pass
    sl_time().sleep(interval_ms)

    # $22 F189 
    if not service_22_check(node, dids=[dids_f189], expect_data=[0x62], expect_str=f"$22 {dids_f189:04X} 肯定响应(62)")[0]:
        success = False
    sl_time().sleep(interval_ms)

    # $22 F089
    if not service_22_check(node, dids=[dids_f089], expect_data=[0x62], expect_str=f"$22 {dids_f089:04X} 肯定响应(62)")[0]:
        success = False
    sl_time().sleep(interval_ms)

    return success

