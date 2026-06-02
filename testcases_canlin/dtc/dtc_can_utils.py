import threading
import time
import queue
from dataclasses import dataclass, field
from itertools import cycle
from typing import Optional, Dict, Any, Tuple, List
from can import Message

from common.wakeup import WakeupStop, WakeupStart
from library.uds.uds_node import UDSNode
from library.uds.bus_sim import BusSim
from slplus.cantp import sl_cantp
from uvtest.testlog import TestLog
from env.config import DEFAULT_CAN_CHANNELS
from common.params import P
from common.context import ctx

# from ..e2e.e2e_module import (
#     E2ESignalGroupInfo, start_e2e_send_timer, set_profile
# )
from library.e2e import crc8_saej1850, crc16_ccitt
from testcases_canlin.nm.nm_autosar_utils import wait_dut_enter_sleep


@dataclass
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

class DTCStatusBit:
    TEST_FAILED = 0                      # bit0: testFailed 
    TEST_FAILED_THIS_CYCLE = 1           # bit1: testFailedThisOperationCycle
    PENDING_DTC = 2                      # bit2: pendingDTC
    CONFIRMED_DTC = 3                    # bit3: confirmedDTC 
    TEST_NOT_COMPLETED_SINCE_CLEAR = 4   # bit4: testNotCompletedSinceLastClear
    TEST_FAILED_SINCE_CLEAR = 5          # bit5: testFailedSinceLastClear
    TEST_NOT_COMPLETED_THIS_CYCLE = 6    # bit6: testNotCompletedThisOperationCycle
    WARNING_INDICATOR = 7                # bit7: warningIndicatorRequested 

def get_bit(value: int, bit_pos: int) -> bool:
    return ((value >> bit_pos) & 1) == 1

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


def check_dtc_list_status_bits(
    dtc_list: list,
    expected_bits: Dict[int, bool],
    step_name: str = ""
) -> bool:

    all_passed = True
    for dtc_info in dtc_list:
        dtc = dtc_info['dtc']
        status = dtc_info['status']
        dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"

        is_match = True
        actual = {}
        for bit_pos, expected_value in expected_bits.items():
            actual_value = get_bit(status, bit_pos)
            actual[bit_pos] = actual_value
            if actual_value != expected_value:
                is_match = False

        bit_str = ", ".join([f"bit{pos}={int(actual[pos])}" for pos in sorted(actual.keys())])

        if is_match:
            TestLog("PASS", step_name, f"DTC {dtc_str}: status=0x{status:02X}, {bit_str}")
        else:
            TestLog("FAIL", step_name, f"DTC {dtc_str}: status=0x{status:02X}, {bit_str}")
            all_passed = False

    return all_passed


@dataclass
class GlobalSnapshotData:
    dtc_code: Tuple[int, int, int] = (0, 0, 0)  # (high, mid, low)
    dtc_status: int = 0

    year: int = 0
    month: int = 0
    day: int = 0
    hour: int = 0
    minute: int = 0
    second: int = 0

    odometer: int = 0
    voltage: float = 0.0
    speed: float = 0.0
    power_mode: int = 0
    raw_data: bytes = field(default_factory=bytes)

    record_time: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dtc": f"{self.dtc_code[0]:02X}{self.dtc_code[1]:02X}{self.dtc_code[2]:02X}",
            "time": f"{self.year:04d}-{self.month:02d}-{self.day:02d} {self.hour:02d}:{self.minute:02d}:{self.second:02d}",
            "odometer_km": self.odometer,
            "voltage_v": self.voltage,
            "speed_kmh": self.speed,
            # "power_mode": self.power_mode,
        }


class GlobalSnapshotStore:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._storage: Dict[str, GlobalSnapshotData] = {}
        return cls._instance

    def save(self, key: str, data: GlobalSnapshotData) -> None:
        import datetime
        data.record_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._storage[key] = data
        TestLog("INFO", "", f"已保存快照数据 [{key}]: {data.to_dict()}")

    def get(self, key: str) -> Optional[GlobalSnapshotData]:
        data = self._storage.get(key)
        if data is None:
            TestLog("WARNING", "", f"未找到快照数据 [{key}]")
        return data

    def exists(self, key: str) -> bool:
        return key in self._storage

    def clear(self, key: str = None) -> None:
        if key is None:
            self._storage.clear()
            TestLog("INFO", "", "已清除所有快照数据")
        elif key in self._storage:
            del self._storage[key]
            TestLog("INFO", "", f"已清除快照数据 [{key}]")

    def compare(
        self,
        baseline_key: str,
        current: GlobalSnapshotData,
        case_name: str = "",
        voltage_tolerance: float = 0.5
    ) -> bool:
        baseline = self.get(baseline_key)
        if baseline is None:
            TestLog("FAIL", "", f"未找到基准快照数据 [{baseline_key}]，请确保已执行相关前置用例")
            return False

        all_pass = True

        time_match = (
            baseline.year == current.year and
            baseline.month == current.month and
            baseline.day == current.day and
            baseline.hour == current.hour and
            baseline.minute == current.minute and
            baseline.second == current.second
        )
        baseline_time = f"{baseline.year:04d}-{baseline.month:02d}-{baseline.day:02d} {baseline.hour:02d}:{baseline.minute:02d}:{baseline.second:02d}"
        current_time = f"{current.year:04d}-{current.month:02d}-{current.day:02d} {current.hour:02d}:{current.minute:02d}:{current.second:02d}"
        if time_match:
            TestLog("PASS", "", f"时间匹配: 期望={baseline_time}, 实际={current_time} (一致)")
        else:
            TestLog("FAIL", "", f"时间匹配: 期望={baseline_time}, 实际={current_time} (不一致)")
            all_pass = False

        if baseline.odometer == current.odometer:
            TestLog("PASS", "", f"里程值匹配: 期望={baseline.odometer}km, 实际={current.odometer}km (一致)")
        else:
            TestLog("FAIL", "", f"里程值匹配: 期望={baseline.odometer}km, 实际={current.odometer}km (不一致)")
            all_pass = False

        voltage_diff = abs(baseline.voltage - current.voltage)
        if voltage_diff <= voltage_tolerance:
            TestLog("PASS", "", f"电压值匹配: 期望={baseline.voltage}V, 实际={current.voltage}V, 偏差={voltage_diff:.2f}V (一致)")
        else:
            TestLog("FAIL", "", f"电压值匹配: 期望={baseline.voltage}V, 实际={current.voltage}V, 偏差={voltage_diff:.2f}V (超出容差{voltage_tolerance}V)")
            all_pass = False

        if baseline.speed == current.speed:
            TestLog("PASS", "", f"车速值匹配: 期望={baseline.speed}km/h, 实际={current.speed}km/h (一致)")
        else:
            TestLog("FAIL", "", f"车速值匹配: 期望={baseline.speed}km/h, 实际={current.speed}km/h (不一致)")
            all_pass = False

        # if baseline.power_mode == current.power_mode:
        #     TestLog("PASS", "", f"电源模式: 基准={baseline.power_mode}, 当前={current.power_mode} (一致)")
        # else:
        #     TestLog("FAIL", "", f"电源模式: 基准={baseline.power_mode}, 当前={current.power_mode} (不一致)")
        #     all_pass = False

        # if all_pass:
        #     TestLog("PASS", "", f"快照数据与 [{baseline_key}] 保持一致")
        # else:
        #     TestLog("FAIL", "", f"快照数据与 [{baseline_key}] 不一致")

        return all_pass

    def compare_to_expect(self, snapshot: GlobalSnapshotData, voltage, speed, odometer, time):
        if snapshot is not None:

            if P.GlobalData.items[0].DID != 0:
                if abs(snapshot.voltage - voltage) <= 0.5:
                    TestLog("PASS", "", f"电压值匹配: 期望≈{voltage}V, 实际={snapshot.voltage}V")
                else:
                    TestLog("FAIL", "", f"电压值不匹配: 期望≈{voltage}V, 实际={snapshot.voltage}V")

            speed_tolerance = 5.0
            if P.GlobalData.items[1].DID != 0:
                if abs(snapshot.speed - speed) <= speed_tolerance:
                    TestLog("PASS", "", f"车速值匹配: 期望≈{speed}km/h, 实际={snapshot.speed}km/h")
                else:
                    TestLog("FAIL", "", f"车速值不匹配: 期望≈{speed}km/h, 实际={snapshot.speed}km/h")

            if P.GlobalData.items[2].DID != 0:
                if snapshot.odometer == odometer:
                    TestLog("PASS", "", f"里程值匹配: 期望={odometer}km, 实际={snapshot.odometer}km")
                else:
                    TestLog("FAIL", "", f"里程值不匹配: 期望={odometer}km, 实际={snapshot.odometer}km")

            if P.GlobalData.items[3].DID != 0:
                current_time = (f"{snapshot.year:04d}-{snapshot.month:02d}-{snapshot.day:02d} "
                                f"{snapshot.hour:02d}:{snapshot.minute:02d}:{snapshot.second:02d}")
                if current_time == time:
                    TestLog("PASS", "", f"时间匹配: 期望={time}, 实际={current_time}")
                else:
                    TestLog("FAIL", "", f"时间不匹配: 期望={time}, 实际={current_time}")

        else:
            TestLog("FAIL", "", "快照数据解析失败")


    @staticmethod
    def parse(
        response_data: bytes,
        dtc_code: Tuple[int, int, int] = (0, 0, 0)
    ) -> Optional[GlobalSnapshotData]:
        if response_data is None or len(response_data) < 6:
            TestLog("WARNING", "", "响应数据过短，无法解析")
            return None

        data = list(response_data) if isinstance(response_data, bytes) else response_data

        if data[0] != 0x59 or data[1] != 0x04:
            TestLog("WARNING", "", f"非 19 04 肯定响应: {[hex(b) for b in data[:2]]}")
            return None

        snapshot = GlobalSnapshotData(
            dtc_code=dtc_code,
            raw_data=bytes(data)
        )

        # 跳过响应头 (59 04) + DTC (3 bytes) + Status (1 byte) + RecordNumber (1 byte) + NumOfDID (1 byte)
        idx = 8

        while idx + 2 < len(data):
            did_high = data[idx]
            did_low = data[idx + 1]
            did = (did_high << 8) | did_low
            idx += 2

            if did == P.GlobalData.items[0].DID:  # 电压
                Length = P.GlobalData.items[0].Length
                if idx + Length <= len(data):
                    invalid_value = (1 << (8 * Length)) - 1
                    if Length == 1:
                        raw_voltage = data[idx]
                        if raw_voltage != invalid_value:
                            snapshot.voltage = raw_voltage * P.GlobalData.items[0].Factor
                        else:
                            snapshot.voltage = raw_voltage
                    elif Length == 2:
                        raw_voltage = (data[idx] << 8) | data[idx + 1]
                        if raw_voltage != invalid_value:
                            snapshot.voltage = raw_voltage * P.GlobalData.items[0].Factor
                        else:
                            snapshot.voltage = raw_voltage
                    idx += Length

            elif did == P.GlobalData.items[1].DID:  # 车速
                Length = P.GlobalData.items[1].Length
                if idx + 2 <= len(data):
                    raw_speed = (data[idx] << 8) | data[idx + 1]
                    if raw_speed != (1 << (8 * Length)) - 1:
                        snapshot.speed = raw_speed * P.GlobalData.items[1].Factor
                    else:
                        snapshot.speed = raw_speed
                    idx += Length

            elif did == P.GlobalData.items[2].DID:  # 里程
                Length = P.GlobalData.items[2].Length
                if idx + 3 <= len(data):
                    raw_odometer = (data[idx] << 16) | (data[idx + 1] << 8) | data[idx + 2]
                    if raw_odometer != (1 << (8 * Length)) - 1:
                        snapshot.odometer = int(raw_odometer * P.GlobalData.items[2].Factor)
                    else:
                        snapshot.odometer = raw_odometer
                    idx += Length

            # elif did == 0xF013:  # 电源模式
            #     if idx + 1 <= len(data):
            #         snapshot.power_mode = data[idx]
            #         idx += 1

            elif did == P.GlobalData.items[3].DID:  # 时间戳
                Length = P.GlobalData.items[3].Length
                if idx + 6 <= len(data):
                    snapshot.year = 2000 + data[idx]
                    snapshot.month = data[idx + 1]
                    snapshot.day = data[idx + 2]
                    snapshot.hour = data[idx + 3]
                    snapshot.minute = data[idx + 4]
                    snapshot.second = data[idx + 5]
                    idx += Length
            else:
                TestLog("DEBUG", "", f"未知 DID: 0x{did:04X}")
                idx += 1

        # TestLog("INFO", "", f"解析完成: {snapshot.to_dict()}")
        return snapshot

snapshot_store = GlobalSnapshotStore()

class DTCTESTParams:
    _DEFAULT_STATUS_MASK = P.DiagServiceInfo.DTCStatusAvlMask
    _DEFAULT_OVERVOLTAGE_DTC = (0x91, 0x01, 0x12)
    _DEFAULT_UNDERVOLTAGE_DTC = (0x91, 0x01, 0x13)
    _DEFAULT_BUSOFF_DTC = (0x92, 0x01, 0x00)
    _DEFAULT_MAX_DTC_COUNT = 10
    _DEFAULT_MAX_SNAPSHOT_COUNT = 10
    _DEFAULT_DTC_CONFIG_DID = 0x0100
    _DEFAULT_DTC_TRIGGER_CAN_ID = 0x000
    _DEFAULT_NORMAL_VOLTAGE = 12.0
    _DEFAULT_LOW_VOLTAGE = 7.0
    _DEFAULT_HIGH_VOLTAGE = 18.0

    @staticmethod
    def _dtc_to_tuple(dtc_code: int) -> tuple:
        if dtc_code == 0:
            return (0, 0, 0)
        return ((dtc_code >> 16) & 0xFF, (dtc_code >> 8) & 0xFF, dtc_code & 0xFF)

    @property
    def ExpectedDTCList(self) -> list:
        try:
            item1 = []
            for item in P.ExtendedDTCInfo.all_support.valid_items:
                dtc_code = (item.DTCCode << 8) | item.FailureType
                item1.append(self._dtc_to_tuple(dtc_code))
            return item1
            return [item.DTCCode for item in P.ExtendedDTCInfo.all_support.valid_items]
        except Exception:
            return []

    @property
    def ExpectedDTCStatusAvailabilityMask(self) -> list:
        return self._DEFAULT_STATUS_MASK

    @property
    def OVERVOLTAGE_DTC(self) -> tuple:
        try:
            voltage_items = P.ExtendedDTCInfo.voltage.valid_items
            for item in voltage_items:
                notes = item.Notes.lower() if hasattr(item, 'Notes') else ""
                if "过压" in notes or "high" in notes or "over" in notes:
                    return self._dtc_to_tuple(item.DTCCode)
            if len(voltage_items) >= 2:
                return self._dtc_to_tuple(voltage_items[1].DTCCode)
        except Exception:
            pass
        return self._DEFAULT_OVERVOLTAGE_DTC

    @property
    def UNDERVOLTAGE_DTC(self) -> tuple:
        try:
            voltage_items = P.ExtendedDTCInfo.voltage.valid_items
            for item in voltage_items:
                notes = item.Notes.lower() if hasattr(item, 'Notes') else ""
                if "欠压" in notes or "low" in notes or "under" in notes:
                    return self._dtc_to_tuple(item.DTCCode)
            if len(voltage_items) >= 1:
                return self._dtc_to_tuple(voltage_items[0].DTCCode)
        except Exception:
            pass
        return self._DEFAULT_UNDERVOLTAGE_DTC

    @property
    def BUSOFF_DTC(self) -> tuple:
        try:
            busoff_items = P.ExtendedDTCInfo.bus_off.valid_items
            if len(busoff_items) >= 1:
                return self._dtc_to_tuple(busoff_items[0].DTCCode)
        except Exception:
            pass
        return self._DEFAULT_BUSOFF_DTC

    @property
    def MAX_DTC_COUNT(self) -> int:
        return self._DEFAULT_MAX_DTC_COUNT

    @property
    def MAX_SNAPSHOT_COUNT(self) -> int:
        return self._DEFAULT_MAX_SNAPSHOT_COUNT

    @property
    def DTC_CONFIG_DID(self) -> int:
        try:
            lost_comm_items = P.ExtendedDTCInfo.lost_communication.valid_items
            if lost_comm_items and lost_comm_items[0].ConfigDID != 0:
                return lost_comm_items[0].ConfigDID
        except Exception:
            pass
        return self._DEFAULT_DTC_CONFIG_DID

    @property
    def DTC_TRIGGER_CAN_ID(self) -> int:
        return self._DEFAULT_DTC_TRIGGER_CAN_ID

    @property
    def PARENT_CHILD_DTC_MAP(self) -> dict:
        return {}

    @property
    def NORMAL_VOLTAGE(self) -> float:
        try:
            return P.CANInfo.Vnormal
        except Exception:
            return self._DEFAULT_NORMAL_VOLTAGE

    @property
    def LOW_VOLTAGE(self) -> float:
        try:
            return P.CANInfo.VlowStand
        except Exception:
            return self._DEFAULT_LOW_VOLTAGE

    @property
    def HIGH_VOLTAGE(self) -> float:
        try:
            return P.CANInfo.VhighStand
        except Exception:
            return self._DEFAULT_HIGH_VOLTAGE

DTCTestParams = DTCTESTParams()



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
            TestLog("INFO", "BusSim", f"收到数据: {data.hex()}")
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

    def send(self, data: bytes, func_req: bool = False):
        if self._cantp is None:
            TestLog("ERROR", "BusSim", "CANTP 未初始化，发送失败")
            return

        tx_id = self._fa if func_req else self._sa
        TestLog("INFO", "BusSim", f"发送数据: ID=0x{tx_id:X}, data={data.hex()}, func={func_req}")
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


def get_can_node(sa=None, ta=None, fa=None, is_canfd=None) -> UDSNode:
    sa = sa if sa is not None else P.ECUInfo.DiagReqID_int
    ta = ta if ta is not None else P.ECUInfo.DiagRespID_int
    fa = fa if fa is not None else P.ECUInfo.DiagFuncID_int
    is_canfd = is_canfd if is_canfd is not None else P.TpInfo.CanFDMode

    busid = DEFAULT_CAN_CHANNELS[0]
    bus_obj = CANBusSim()
    bus_obj.init(busid, sa, ta, fa, is_canfd)
    node = UDSNode(bus_obj)
    return node


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
            return True
        return False

    status, msg = check_expect_response(resp, expect_data)
    if status is False:
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
        return False
    TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
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
            return True, None
        return False, resp

    status, msg = check_expect_response(resp, expect_data)
    if status is False:
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
        return False, resp
    TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
    return True, resp


def service_14_check(node, h=0xFF, m=0xFF, l=0xFF, expect_data=None, expect_str="", func_req=False, **kwargs):
    resp = node.Service_0x14_ClearDiagnosticInformation(
        h=h, m=m, l=l, func_req=func_req, **kwargs
    )

    if expect_data is None:
        if resp is None:
            return True, None
        return False, resp

    status, msg = check_expect_response(resp, expect_data)
    if status is False:
        TestLog("FAIL", "", f"期望: {expect_str}; 实际:{msg}")
        return False, resp
    TestLog("PASS", "", f"期望: {expect_str}; 实际:{msg}")
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

class TesterPresentManager:
    flag = False
    status = "stopped"

def tester_present_start(node, period_ms=2000):
    """
        开始周期发送3E 80
    """
    # from common.can_utils import canmsg_create, send_canmsg

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

def compare_dtc_list(read_dtc_list: list, expect_dtc_list: list) -> bool:
    read_dtcs = set([dtc_info['dtc'] for dtc_info in read_dtc_list])

    expect_dtcs = set(expect_dtc_list)

    if read_dtcs == expect_dtcs:
        TestLog("INFO", "", "读取的 DTC 列表与 FMS 定义完全一致")
        return True
    else:
        missing = expect_dtcs - read_dtcs
        extra = read_dtcs - expect_dtcs
        if missing:
            TestLog("INFO", "", f"缺少的 DTC: {[f'0x{d[0]:02X}{d[1]:02X}{d[2]:02X}' for d in missing]}")
        if extra:
            TestLog("INFO", "", f"多余的 DTC: {[f'0x{d[0]:02X}{d[1]:02X}{d[2]:02X}' for d in extra]}")
        return False

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

class FaultSimulator:
    def __init__(self, power_ctrl=None, bob_ctrl=None):
        from common.utils import TimerCyclic
        # from common.can_utils import canmsg_create, send_canmsg
        self._TimerCyclic = TimerCyclic
        self._canmsg_create = canmsg_create
        self._send_canmsg = send_canmsg

        self._power_ctrl = power_ctrl
        self._bob_ctrl = bob_ctrl
        self._timers: Dict[str, Dict[int, str]] = {'lost': {}, 'e2e': {}, 'invalid': {}}
        self._busoff_active = False
        self._tx_cnt = {}

    def _get_ctrl(self, name: str):
        ctrl = getattr(self, f'_{name}', None)
        return ctrl if ctrl else getattr(ctx, name, None)

    def set_power_ctrl(self, ctrl) -> 'FaultSimulator':
        self._power_ctrl = ctrl
        return self

    def set_bob_ctrl(self, ctrl) -> 'FaultSimulator':
        self._bob_ctrl = ctrl
        return self

    def voltage_fault(self, enable: bool, voltage: float = None) -> Tuple[bool, str]:
        power = self._get_ctrl('power_ctrl')
        if not power:
            TestLog("FAIL", "电压故障", "电源控制器未初始化")
            return False, "power controller not initialized"

        target = voltage if voltage is not None else (
            DTCTestParams.LOW_VOLTAGE if enable else DTCTestParams.NORMAL_VOLTAGE)
        status, msg = power.set_voltage(target)
        TestLog("PASS" if status else "FAIL", "电压故障", f"{'注入' if enable else '恢复'}电压: {target}V")
        return status, msg

    def lost_comm_fault(self, enable: bool, msg_id: int, channel: int = None,
                        dlc: int = 8, data: bytes = None, cycle_ms: int = 100,
                        is_canfd: bool = False, timer_id: str = None) -> Tuple[bool, str]:
        tid = timer_id or f"{msg_id:X}"
        ch = channel if channel is not None else DEFAULT_CAN_CHANNELS[0]
        is_canfd = is_canfd and (P.ProjectInfo.ECUType == 2)
        sim_tid = f"sim_{tid}"
        self._TimerCyclic.stop(tid)

        if enable:
            if sim_tid not in sim_message_ctrl._timers:
                TestLog("FAIL", "",
                        f"报文0x{msg_id:X}未在仿真周期发送列表中，无法注入丢失故障；"
                        f"请确认配置中的MonitorMessageID是否已由环境模拟注册")
                return False, f"sim timer {sim_tid} not registered"
            # 停止对应的仿真信号模拟
            sim_message_ctrl.stop_timer(sim_tid)
            self._timers['lost'].pop(msg_id, None)
            TestLog("INFO", "", f"报文0x{msg_id:X}已停止发送")
            return True, f"lost comm injected for msg 0x{msg_id:X}"

        #检查仿真信号中是否有相同ID的报文
        if sim_tid in sim_message_ctrl._timers:
            TestLog("INFO", "", f"报文0x{msg_id:X}已恢复发送")
            return True, f"lost comm recovered for msg 0x{msg_id:X}"

        payload = data or bytes(dlc)
        msg = self._canmsg_create(msg_id, dlc, data=payload, fdf=int(is_canfd), brs=int(is_canfd))
        if not msg:
            TestLog("FAIL", "", f"创建报文0x{msg_id:X}失败")
            return False, "failed to create message"

        try:
            if self._TimerCyclic.start(tid, cycle_ms, lambda: self._send_canmsg(ch, msg=msg)):
                self._timers['lost'][msg_id] = tid
                TestLog("INFO", "", f"报文0x{msg_id:X}已恢复发送")
                print(self._timers.values())
                return True, f"lost comm recovered for msg 0x{msg_id:X}"
        except Exception as e:
            TestLog("FAIL", "", f"测试执行出错: {e}")
        TestLog("FAIL", "", "启动周期发送失败")
        return False, "failed to start cyclic send"

    def busoff_fault(self, enable: bool, channel: int = 1, count: int = 1,
                     target: str = None, kind: str = "SHORT") -> Tuple[bool, str]:
        # if enable:
        #     ctx.bob_ctrl.set_test_channel('CAN1', True)
        #     ctx.bob_ctrl.set_fault("HL", "SHORT", True)
        # else:
        #     ctx.bob_ctrl.set_test_channel('CAN1', False)
        #     ctx.bob_ctrl.set_fault("HL", "SHORT", False)


        bob = self._get_ctrl('bob_ctrl')
        if not bob:
            TestLog("FAIL", "BusOff", "BOB控制器未初始化")
            return False, "bob controller not initialized"

        ch = channel if channel is not None else DEFAULT_CAN_CHANNELS[0]
        fault_target = target or f"CAN{ch}"

        if enable:
            for i in range(count):
                status, msg = bob.set_fault(fault_target, kind, enable=True)
                # if not status:
                #     TestLog("FAIL", "", f"注入失败(第{i+1}次): {msg}")
                #     return False, msg
                if count > 1:
                    time.sleep(0.1)
            self._busoff_active = True
            TestLog("INFO", "", f"故障已注入: 通道={ch}")
            return True, f"busoff injected on channel {ch}"

        status, msg = bob.set_fault(fault_target, kind, enable=False)
        # if not status:
        #     TestLog("FAIL", "", f"恢复失败: {msg}")
        #     return False, msg

        try:
            from slplus.can import sl_can
            sl_can(channel).deactive()
            time.sleep(0.1)
            sl_can(channel).active()
        except Exception as e:
            TestLog("WARNING", "BusOff", f"CAN通道重新激活警告: {e}")

        self._busoff_active = False
        TestLog("PASS", "", f"故障已恢复: 通道={channel}")
        return True, f"busoff recovered on channel {channel}"

    def crc_e2e_fault(self, enable: bool, msg_id: int, fault_type: str, channel: int = None,
                      dlc: int = 8, data: bytes = None, cycle_ms: int = 100,
                      is_canfd: bool = False, timer_id: str = None,
                      is_e2e: bool = False, data_id: int = 0x00) -> Tuple[bool, str]:
        tid = timer_id or f"{msg_id:X}"
        ch = channel if channel is not None else DEFAULT_CAN_CHANNELS[0]
        is_canfd = is_canfd and (P.ProjectInfo.ECUType == 2)
        if is_canfd:
            dlc_to_bytes = {
                0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8,
                9: 12, 10: 16, 11: 20, 12: 24, 13: 32, 14: 48, 15: 64
            }
            data_len = dlc_to_bytes.get(int(dlc), 8)
        else:
            data_len = min(int(dlc), 8)
        payload = bytearray(data) if data else bytearray(data_len)
        payload.extend([0x00] * (data_len - len(payload)))
        self._TimerCyclic.stop(tid)
        fixed_data = bytes(payload)

        if enable:
            # 停止对应的仿真信号模拟
            sim_message_ctrl.stop_timer(f"sim_{tid}")

        #检查仿真信号中是否有相同ID的报文
        if f"sim_{tid}" in sim_message_ctrl._timers:
            TestLog("INFO", "", f"已恢复正常: 报文0x{msg_id:X}")
            return True, f"crc/e2e fault recovered for msg 0x{msg_id:X}"

        if enable and fault_type.upper() == "E2E_CRC":
            def send_crc_fixed():
                msg = self._canmsg_create(msg_id, dlc, data=fixed_data, fdf=int(is_canfd), brs=int(is_canfd))
                if msg:
                    self._send_canmsg(ch, msg=msg)

            if self._TimerCyclic.start(tid, cycle_ms, send_crc_fixed):
                self._timers['e2e'][msg_id] = tid
                TestLog("INFO", "", f"故障已注入: 报文0x{msg_id:X}")
                return True, f"crc/e2e fault injected for msg 0x{msg_id:X}"
            TestLog("FAIL", "", "启动定时器失败")
            return False, "failed to start timer"

        self._tx_cnt.setdefault(tid, 0)
        profile, _ = set_profile(bool(is_canfd))

        if enable and fault_type.upper() == "E2E_COUNTER":
            def send_counter_fixed(_msg_id=msg_id, _data=fixed_data, _dlc=dlc, _data_id=data_id, _is_canfd=is_canfd, _tid=tid, _profile=profile):
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
                max_counter = PROFILE_COUNTER_MAX[profile]
                self._tx_cnt[_tid] = 0

            if self._TimerCyclic.start(tid, cycle_ms, send_counter_fixed):
                self._timers['e2e'][msg_id] = tid
                TestLog("INFO", "", f"故障已注入: 报文0x{msg_id:X}")
                return True, f"crc/e2e fault injected for msg 0x{msg_id:X}"
            TestLog("FAIL", "", "启动定时器失败")
            return False, "failed to start timer"

        def send_correct(_msg_id=msg_id, _data=fixed_data, _dlc=dlc, _data_id=data_id, _is_canfd=is_canfd, _tid=tid, _profile=profile):
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
            self._tx_cnt[_tid] = (tx_counter + 1) % (max_counter + 1)

        if self._TimerCyclic.start(tid, cycle_ms, send_correct):
            self._timers['e2e'][msg_id] = tid
            TestLog("INFO", "", f"已恢复正常: 报文0x{msg_id:X}")
            return True, f"crc/e2e fault recovered for msg 0x{msg_id:X}"
        TestLog("FAIL", "", "启动正常发送失败")
        return False, "failed to start normal send"

    def invalid_data_fault(self, enable: bool, msg_id: int,
                           channel: int = None, dlc: int = 8, data: bytes = None,
                           cycle_ms: int = 100, is_canfd: bool = False,
                           timer_id: str = None, is_e2e: bool = False, data_id: int = 0x00) -> Tuple[bool, str]:
        tid = timer_id or f"{msg_id:X}"
        ch = channel if channel is not None else DEFAULT_CAN_CHANNELS[0]
        is_canfd = is_canfd and (P.ProjectInfo.ECUType == 2)
        if is_canfd:
            dlc_to_bytes = {
                0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8,
                9: 12, 10: 16, 11: 20, 12: 24, 13: 32, 14: 48, 15: 64
            }
            data_len = dlc_to_bytes.get(int(dlc), 8)
        else:
            data_len = min(int(dlc), 8)
        payload = bytearray(data) if data else bytearray(data_len)
        payload.extend([0x00] * (data_len - len(payload)))
        self._TimerCyclic.stop(tid)
        fixed_data = bytes(payload)

        if enable:
            # 停止对应的仿真信号模拟
            sim_message_ctrl.stop_timer(f"sim_{tid}")

        # 检查仿真信号中是否有相同ID的报文
        if f"sim_{tid}" in sim_message_ctrl._timers:
            TestLog("INFO", "", f"{'注入' if enable else '恢复'}成功: 0x{msg_id:X}")
            return True, f"invalid data {'injected' if enable else 'recovered'} for msg 0x{msg_id:X}"

        tx_state = {'counter': 0}
        group = E2ESignalGroupInfo(
            name="name",
            startByte=0,
            length=16 if is_canfd else 8,
            dataid=data_id,
            max_delta_counter_init=0,
        )
        profile, _ = set_profile(bool(is_canfd))

        def send_data():
            if is_e2e == True and data_id != 0:
                payload = build_e2e_payload(
                    group, profile, dlc,
                    tx_state['counter'],
                    data = fixed_data
                )
                msg = self._canmsg_create(msg_id, dlc, data=payload, fdf=int(is_canfd), brs=int(is_canfd))
                if msg:
                    self._send_canmsg(ch, msg=msg)
                max_counter = PROFILE_COUNTER_MAX[profile]
                tx_state['counter'] = (tx_state['counter'] + 1) % (max_counter + 1)
            else:
                msg = self._canmsg_create(msg_id, dlc, data=fixed_data, fdf=int(is_canfd), brs=int(is_canfd))
                if msg:
                    self._send_canmsg(ch, msg=msg)

        if self._TimerCyclic.start(tid, cycle_ms, send_data):
            self._timers['invalid'][msg_id] = tid
            hex_str = ' '.join(f'{b:02X}' for b in fixed_data)
            TestLog("INFO", "", f"{'注入' if enable else '恢复'}成功: 0x{msg_id:X}, {hex_str}")
            return True, f"invalid data {'injected' if enable else 'recovered'} for msg 0x{msg_id:X}"
        TestLog("FAIL", "", "启动定时器失败")
        return False, "failed to start timer"

    def stop_fault_msg(self, msg_id: int, fault_type: str = None) -> Tuple[bool, str]:
        stopped = False
        for category in (['e2e', 'invalid'] if fault_type is None else [fault_type]):
            if msg_id in self._timers.get(category, {}):
                self._TimerCyclic.stop(self._timers[category].pop(msg_id))
                stopped = True
        return (True, f"stopped 0x{msg_id:X}") if stopped else (False, f"no active fault")

    def inject_dtc_faults(self, lost_comm_dtcs=None, invalid_data_dtcs=None,
                          inject_lost_comm=True, inject_e2e=True,
                          inject_invalid_data=True) -> Tuple[list, int]:
        injected, max_wait = [], 0
        lost_comm_dtcs, invalid_data_dtcs = lost_comm_dtcs or [], invalid_data_dtcs or []

        if inject_lost_comm and lost_comm_dtcs:
            item = lost_comm_dtcs[0]
            self.lost_comm_fault(False, item.MonitorMessageID, dlc=item.MonitorMessageDLC,
                                 cycle_ms=item.MonitorMessagePeriod or 100, is_canfd=item.FDF)
            time.sleep((item.PassTime or 1000) / 1000)
            self.lost_comm_fault(True, item.MonitorMessageID)
            injected.append(('lost', item))
            max_wait = max(max_wait, item.LostTime)

        if inject_invalid_data and invalid_data_dtcs:
            invalid_items = [i for i in invalid_data_dtcs if i.Type == "InvalidData"]
            if invalid_items:
                item = invalid_items[0]
                self.invalid_data_fault(True, item.MonitorMessageID, signal_value=0, start_bit=0, bit_length=1,
                                        dlc=item.MonitorMessageDLC, cycle_ms=item.MonitorMessagePeriod or 100,
                                        data = item.Payload, is_canfd=item.FDF)
                injected.append(('invalid', item))
                max_wait = max(max_wait, item.LostTime)

        if inject_e2e:
            e2e_items = [i for i in invalid_data_dtcs if i.Type == "E2E" and i.IsContainE2E == 1 and i.DataID != 0]
            if e2e_items:
                item = e2e_items[0]
                self.crc_e2e_fault(True, item.MonitorMessageID, item.Type, dlc=item.MonitorMessageDLC,
                                   cycle_ms=item.MonitorMessagePeriod or 100, is_canfd=item.FDF,
                                   data = item.Payload)
                injected.append(('e2e', item))
                max_wait = max(max_wait, item.LostTime)

        return injected, max_wait

    def recover_dtc_faults(self, faults: list):
        for fault_type, item in faults:
            try:
                if fault_type == 'lost':
                    self.lost_comm_fault(False, item.MonitorMessageID, dlc=item.MonitorMessageDLC,
                                         cycle_ms=item.MonitorMessagePeriod or 100, is_canfd=item.FDF)
                elif fault_type == 'e2e':
                    self.crc_e2e_fault(False, item.MonitorMessageID, item.Type, dlc=item.MonitorMessageDLC,
                                       cycle_ms=item.MonitorMessagePeriod or 100, is_canfd=item.FDF)
                elif fault_type == 'invalid':
                    self.stop_fault_msg(item.MonitorMessageID, 'invalid')
            except Exception as e:
                TestLog("WARNING", "故障恢复", f"恢复失败: {e}")

    def stop_all_timer(self):
        print("stop_all_timer")
        print(self._timers.values())
        for timers in self._timers.values():
            for tid in list(timers.values()):
                self._TimerCyclic.stop(tid)
            timers.clear()

    def reset_all(self):
        for timers in self._timers.values():
            for tid in list(timers.values()):
                self._TimerCyclic.stop(tid)
            timers.clear()

        power = self._get_ctrl('power_ctrl')
        if power:
            self.voltage_fault(False)

        bob = self._get_ctrl('bob_ctrl')
        if bob:
            bob.reset()

        self._busoff_active = False
        TestLog("INFO", "故障模拟器", "所有故障状态已重置")

fault_simulator = FaultSimulator()


class OperationCycle:
    """
    操作循环控制(ECU休眠 -> ECU唤醒)

    使用示例:
        OperationCycle.run()              # 执行1次
        OperationCycle.run(40)            # 执行40次
        OperationCycle.run(40, callback=check_dtc)
    """

    SLEEP_CURRENT_MA = 10.0
    SLEEP_TIMEOUT_S = 60.0
    WAKEUP_STABLE_S = 2.0
    POWERMODE_MSG_ID = 0x1F1
    POWERMODE_CYCLE_MS = 20

    @classmethod
    def send_powermode(cls, mode: int) -> None:
        from common.utils import TimerCyclic
        # from common.can_utils import canmsg_create, send_canmsg

        try:
            ch = DEFAULT_CAN_CHANNELS[0]
            is_canfd = P.TpInfo.CanFDMode

            data = bytearray(8)
            data[3] = (mode & 0x03) << 6

            msg = canmsg_create(cls.POWERMODE_MSG_ID, 8, data=bytes(data),
                               fdf=1 if is_canfd else 0, brs=1 if is_canfd else 0)
            if msg:
                TimerCyclic.stop("powermode_timer")
                TimerCyclic.start("powermode_timer", cls.POWERMODE_CYCLE_MS, send_canmsg, ch, msg=msg)
                mode_names = {0: "OFF", 1: "ACC", 2: "RUN", 3: "CRANK"}
                TestLog("INFO", "PowerMode", f"发送PowerMode={mode_names.get(mode, str(mode))}")
        except Exception as e:
            TestLog("WARNING", "PowerMode", f"发送失败: {e}")

    @classmethod
    def stop_all_msgs(cls) -> None:
        from common.wakeup import WakeupMsgSimulationStop
        from common.utils import TimerCyclic

        try:
            WakeupMsgSimulationStop()
            TimerCyclic.stop("powermode_timer")
            TimerCyclic.stop("wakeup_timer")
            TestLog("INFO", "仿真报文", "已停止所有仿真报文")
        except Exception:
            pass

    @classmethod
    def wait_sleep(cls, threshold_ma: float = None, timeout_s: float = None) -> bool:
        threshold = threshold_ma or cls.SLEEP_CURRENT_MA
        timeout = timeout_s or cls.SLEEP_TIMEOUT_S

        start = time.time()
        while (time.time() - start) < timeout:
            try:
                currents = []
                for _ in range(5):
                    c = ctx.bob_ctrl.read_current()
                    if c is not None:
                        currents.append(c)
                    time.sleep(0.02)
                if currents:
                    avg = sum(currents) / len(currents)
                    if avg <= threshold:
                        TestLog("PASS", "休眠检测", f"电流={avg:.2f}mA, 已休眠")
                        return True
            except Exception:
                pass
            time.sleep(1.0)

        TestLog("FAIL", "休眠检测", f"超时{timeout}s未进入休眠")
        return False

    @classmethod
    def do_wakeup(cls, stable_s: float = None) -> bool:
        from common.wakeup import WakeupStart

        stable = stable_s or cls.WAKEUP_STABLE_S
        try:
            WakeupStart()
            time.sleep(stable)
            TestLog("PASS", "唤醒", "ECU已唤醒")
            return True
        except Exception as e:
            TestLog("FAIL", "唤醒", f"失败: {e}")
            return False

    @classmethod
    def run(cls,
            count: int = 1,
            sleep_current_ma: float = None,
            sleep_timeout_s: float = None,
            stable_time_s: float = None,
            callback: callable = None) -> int:
        from common.wakeup import WakeupStop

        TestLog("INFO", "操作循环", f"开始执行{count}次循环切换")

        for i in range(count):
            if count > 1:
                TestLog("INFO", "操作循环", f"--- 第{i+1}/{count}次 ---")

            try:
                cls.send_powermode(0)  # OFF
                time.sleep(0.5)
                WakeupStop()
                cls.stop_all_msgs()

                if not cls.wait_sleep(sleep_current_ma, sleep_timeout_s):
                    TestLog("FAIL", "操作循环", f"第{i+1}次失败: 休眠超时")
                    return i

                if not cls.do_wakeup(stable_time_s):
                    TestLog("FAIL", "操作循环", f"第{i+1}次失败: 唤醒失败")
                    return i

                cls.send_powermode(2)  # RUN
                time.sleep(0.5)

            except Exception as e:
                TestLog("FAIL", "操作循环", f"第{i+1}次异常: {e}")
                return i

            if callback:
                try:
                    if not callback(i):
                        TestLog("INFO", "操作循环", "回调请求停止")
                        return i + 1
                except Exception as e:
                    TestLog("WARNING", "操作循环", f"回调异常: {e}")

        TestLog("PASS", "操作循环", f"完成{count}次循环")
        return count


def inject_fault_and_read_global_snapshot(
    node,
    sim: FaultSimulator,
    case_name: str,
    wait_time_s: float = 5.0
) -> Tuple[bool, Optional[GlobalSnapshotData], Optional[Tuple[int, int, int]], list]:
    import time
    from env.config import P

    injected_faults = []

    try:
        TestLog("INFO", "Step1", "模拟产生故障")
        injected_faults, max_wait_ms = sim.inject_dtc_faults(
            lost_comm_dtcs=P.ExtendedDTCInfo.lost_communication.valid_items,
            invalid_data_dtcs=P.ExtendedDTCInfo.invalid_data.valid_items
        )
        actual_wait = max((max_wait_ms * 2 / 1000) + 2, wait_time_s)
        TestLog("INFO", "", f"等待故障确认时间: {actual_wait:.1f}s")
        time.sleep(actual_wait)

        TestLog("INFO", "Step2", "发送 19 02 08 请求读取DTC信息")
        success, resp = service_19_check(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0x08
        )

        if not success:
            TestLog("FAIL", "", "Step2: 未收到肯定响应")
            return False, None, None, injected_faults

        dtc_list = get_dtc_list_from_19_resp(resp)
        TestLog("INFO", "", f"Step2: 读取到 {len(dtc_list)} 个 DTC")

        if len(dtc_list) == 0:
            TestLog("FAIL", "", "Step2: 未读取到任何 DTC")
            return False, None, None, injected_faults

        target_dtc = dtc_list[0]['dtc']
        dtc_str = f"{target_dtc[0]:02X}{target_dtc[1]:02X}{target_dtc[2]:02X}"
        TestLog("INFO", "", f"Step2: 选取 DTC {dtc_str} 进行快照读取测试")

        TestLog("INFO", "Step3", f"发送 19 04 {dtc_str} 01 请求读取全局快照")
        success, snapshot_resp = service_19_check(
            node,
            report_type=0x04,
            expect_data=[0x59, 0x04],
            expect_str="肯定响应(59 04)",
            func_req=False,
            h=target_dtc[0],
            m=target_dtc[1],
            l=target_dtc[2],
            snapshot=0x01,
            timeout=5
        )

        if not success or snapshot_resp is None:
            TestLog("FAIL", "", "Step3: 未收到快照响应")
            return False, None, target_dtc, injected_faults

        snapshot_data = list(snapshot_resp.data) if hasattr(snapshot_resp, 'data') else list(snapshot_resp)
        TestLog("INFO", "", f"收到快照响应: {[hex(b) for b in snapshot_data]}")

        TestLog("INFO", "Step4", "解析快照数据")
        parsed_snapshot = snapshot_store.parse(
            response_data=bytes(snapshot_data),
            dtc_code=target_dtc
        )

        if parsed_snapshot is None:
            TestLog("FAIL", "", "Step4: 快照数据解析失败")
            return False, None, target_dtc, injected_faults

        TestLog("INFO", "", f"已解析快照数据: 电压={parsed_snapshot.voltage}V, "
                            f"车速={parsed_snapshot.speed}km/h, "
                           f"里程={parsed_snapshot.odometer}km, "
                           f"时间={parsed_snapshot.year:04d}-{parsed_snapshot.month:02d}-{parsed_snapshot.day:02d} "
                           f"{parsed_snapshot.hour:02d}:{parsed_snapshot.minute:02d}:{parsed_snapshot.second:02d}")

        return True, parsed_snapshot, target_dtc, injected_faults

    except Exception as e:
        TestLog("FAIL", "", f"故障注入/快照读取出错: {e}")
        return False, None, None, injected_faults

def read_dtc_and_global_snapshot(
    node,
    dtc_select: str,
) -> tuple[bool, Optional[GlobalSnapshotData]]:
    import time
    from env.config import P

    try:
        TestLog("INFO", "Step", "发送 19 02 08 请求读取DTC信息")
        success, resp = service_19_check(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0x08
        )

        if not success:
            TestLog("FAIL", "", "未收到肯定响应")
            return False, None

        dtc_list = get_dtc_list_from_19_resp(resp)
        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        if len(dtc_list) == 0:
            TestLog("FAIL", "", "未读取到任何 DTC")
            return False, None

        result = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"
            if dtc_str == dtc_select:
                TestLog("INFO", "", f"读取到故障码 {dtc_select}")
                result = True
        if not result:
            TestLog("FAIL", "", f"期望结果：读取到故障码 {dtc_select}, "
                                f"实际结果：没有读取到故障码 {dtc_select}")

        # high, mid, low = bytes.fromhex(dtc_select)
        defined_data = bytes([0x04, *bytes.fromhex(dtc_select), 0x01])
        # dtc_select = dtc_select.zfill(6)
        dtc_select_tuple: tuple[int, int, int] = tuple(bytes.fromhex(dtc_select))
        # print(f'{dtc_select}{dtc_select_tuple}')
        TestLog("INFO", "Step", f"发送 19 04 {dtc_select} 01 请求读取全局快照")
        success, snapshot_resp = service_19_check(node, None, expect_data=[0x59, 0x04], expect_str="肯定响应(59 04)", defined_data=defined_data)

        if not success or snapshot_resp is None:
            TestLog("FAIL", "", "未收到快照响应")
            return False, None

        snapshot_data = list(snapshot_resp.data) if hasattr(snapshot_resp, 'data') else list(snapshot_resp)
        TestLog("INFO", "", f"收到快照响应: {[hex(b) for b in snapshot_data]}")

        TestLog("INFO", "", "解析快照数据")
        parsed_snapshot = snapshot_store.parse(
            response_data=bytes(snapshot_data),
            dtc_code=dtc_select_tuple
        )

        if parsed_snapshot is None:
            TestLog("FAIL", "", "快照数据解析失败")
            return False, None

        TestLog("INFO", "", f"已解析快照数据: 电压={parsed_snapshot.voltage}V, "
                            f"车速={parsed_snapshot.speed}km/h, "
                           f"里程={parsed_snapshot.odometer}km, "
                           f"时间={parsed_snapshot.year:04d}-{parsed_snapshot.month:02d}-{parsed_snapshot.day:02d} "
                           f"{parsed_snapshot.hour:02d}:{parsed_snapshot.minute:02d}:{parsed_snapshot.second:02d}")

        return True, parsed_snapshot

    except Exception as e:
        TestLog("FAIL", "", f"快照读取出错: {e}")
        return False, None

def read_global_snapshot(
    node,
    dtc_select: str,
) -> tuple[bool, Optional[GlobalSnapshotData]]:
    import time
    from env.config import P

    try:
         # high, mid, low = bytes.fromhex(dtc_select)
        defined_data = bytes([0x04, *bytes.fromhex(dtc_select), 0x01])
        # dtc_select = dtc_select.zfill(6)
        dtc_select_tuple: tuple[int, int, int] = tuple(bytes.fromhex(dtc_select))
        # print(f'{dtc_select}{dtc_select_tuple}')
        TestLog("INFO", "", f"发送 19 04 {dtc_select} 01 请求读取全局快照")
        success, snapshot_resp = service_19_check(node, None, expect_data=[0x59, 0x04], expect_str="肯定响应(59 04)", defined_data=defined_data)

        if not success or snapshot_resp is None:
            TestLog("FAIL", "", "未收到快照响应")
            return False, None

        snapshot_data = list(snapshot_resp.data) if hasattr(snapshot_resp, 'data') else list(snapshot_resp)
        TestLog("INFO", "", f"收到快照响应: {[hex(b) for b in snapshot_data]}")

        TestLog("INFO", "", "解析快照数据")
        parsed_snapshot = snapshot_store.parse(
            response_data=bytes(snapshot_data),
            dtc_code=dtc_select_tuple
        )

        if parsed_snapshot is None:
            TestLog("FAIL", "", "快照数据解析失败")
            return False, None

        TestLog("INFO", "", f"已解析快照数据: 电压={parsed_snapshot.voltage}V, "
                            f"车速={parsed_snapshot.speed}km/h, "
                           f"里程={parsed_snapshot.odometer}km, "
                           f"时间={parsed_snapshot.year:04d}-{parsed_snapshot.month:02d}-{parsed_snapshot.day:02d} "
                           f"{parsed_snapshot.hour:02d}:{parsed_snapshot.minute:02d}:{parsed_snapshot.second:02d}")

        return True, parsed_snapshot

    except Exception as e:
        TestLog("FAIL", "", f"快照读取出错: {e}")
        return False, None

def find_DTC_by_status_mask(node, mask, dtc_select: str):

    try:
        success, resp = service_19_check(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=mask
        )

        if not success:
            TestLog("FAIL", "", "未收到肯定响应")
            return False, 0

        dtc_list = get_dtc_list_from_19_resp(resp)
        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        if len(dtc_list) == 0:
            TestLog("FAIL", "", "未读取到任何 DTC")
            return False, 0

        result = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"
            if dtc_str == dtc_select:
                TestLog("INFO", "", f"读取到故障码 {dtc_select}")
                result = True
                return True, status
        if not result:
            TestLog("FAIL", "", f"期望结果：读取到故障码 {dtc_select}, "
                                f"实际结果：没有读取到故障码 {dtc_select}")
        return False, 0

    except Exception as e:
        TestLog("FAIL", "", f"故障码读取出错: {e}")
        return False, 0


def read_extend_data(node, dtc_select: str):
    occurrence_counter = None
    pending_counter = None
    aged_counter = None
    ageing_counter = None
    result=False
    try:
        if P.CANInfo.OccurrenceCounterExtendedDataID != 0:
            TestLog("INFO", "", f"发送 19 06 {dtc_select} {P.CANInfo.OccurrenceCounterExtendedDataID} 请求读取全局快照")
            defined_data = bytes([0x06, *bytes.fromhex(dtc_select), P.CANInfo.OccurrenceCounterExtendedDataID])
            success, resp1 = service_19_check(node, None, expect_data=[0x59, 0x06], expect_str="肯定响应(59 06)",
                                                      defined_data=defined_data)
            if not success:
                TestLog("FAIL", "", "未收到肯定响应")
                result = False

            if resp1 is not None:
                resp_data = list(resp1.data) if hasattr(resp1, 'data') else list(resp1)
                if P.CANInfo.OccurrenceCounterByteIndex > 0 or P.CANInfo.AgeingCounterByteIndex > 0:
                    if len(resp_data) >= 11:
                        occurrence_counter = resp_data[7]
                        pending_counter = resp_data[8]
                        aged_counter = resp_data[9]
                        ageing_counter = resp_data[10]
                else:
                    if len(resp_data) >= 8:
                        occurrence_counter = resp_data[7]
                result = True

        if P.CANInfo.AgeingCounterExtendedDataID != 0:
            TestLog("INFO", "", f"发送 19 06 {dtc_select} {P.CANInfo.AgeingCounterExtendedDataID} 请求读取全局快照")
            defined_data = bytes([0x06, *bytes.fromhex(dtc_select), P.CANInfo.AgeingCounterExtendedDataID])
            success, resp2 = service_19_check(node, None, expect_data=[0x59, 0x06], expect_str="肯定响应(59 06)",
                                              defined_data=defined_data)
            if not success:
                TestLog("FAIL", "", "未收到肯定响应")
                result = False

            if resp2 is not None:
                resp_data = list(resp2.data) if hasattr(resp2, 'data') else list(resp2)
                if P.CANInfo.OccurrenceCounterByteIndex > 0 or P.CANInfo.AgeingCounterByteIndex > 0:
                    if len(resp_data) >= 11:
                        occurrence_counter = resp_data[7]
                        pending_counter = resp_data[8]
                        aged_counter = resp_data[9]
                        ageing_counter = resp_data[10]
                else:
                    if len(resp_data) >= 8:
                        ageing_counter = resp_data[7]
                result = True

        TestLog("INFO", "", f"获取扩展数据：OccurrenceCounter={occurrence_counter}, PendingCounter={pending_counter}, "
                            f"AgedCounter={aged_counter}, AgeingCounter={ageing_counter}")
        return result, occurrence_counter, pending_counter, aged_counter, ageing_counter

    except Exception as e:
        TestLog("FAIL", "", f"扩展数据读取出错: {e}")
        return False

def recover_fault_and_read_global_snapshot(
    node,
    sim: FaultSimulator,
    case_name: str,
    target_dtc: Tuple[int, int, int],
    injected_faults: list,
    recovery_wait_s: float = 2.0
) -> Tuple[bool, Optional[GlobalSnapshotData]]:
    import time

    try:
        TestLog("INFO", "恢复故障", "模拟故障恢复")
        sim.recover_dtc_faults(injected_faults)
        time.sleep(recovery_wait_s)

        dtc_str = f"{target_dtc[0]:02X}{target_dtc[1]:02X}{target_dtc[2]:02X}"

        TestLog("INFO", "读取快照", f"发送 19 04 {dtc_str} 01 请求读取全局快照")
        success, snapshot_resp = service_19_check(
            node,
            report_type=0x04,
            expect_data=[0x59, 0x04],
            expect_str="肯定响应(59 04)",
            func_req=False,
            h=target_dtc[0],
            m=target_dtc[1],
            l=target_dtc[2],
            snapshot=0x01,
            timeout=5
        )

        if not success or snapshot_resp is None:
            TestLog("FAIL", "", "恢复后读取快照失败")
            return False, None

        snapshot_data = list(snapshot_resp.data) if hasattr(snapshot_resp, 'data') else list(snapshot_resp)
        TestLog("INFO", "", f"收到快照响应: {[hex(b) for b in snapshot_data]}")

        parsed_snapshot = snapshot_store.parse(
            response_data=bytes(snapshot_data),
            dtc_code=target_dtc
        )

        if parsed_snapshot is None:
            TestLog("FAIL", "", "恢复后快照解析失败")
            return False, None

        return True, parsed_snapshot

    except Exception as e:
        TestLog("FAIL", "", f"故障恢复/快照读取出错: {e}")
        return False, None


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

    def start_from_snapshot(self, snapshot: GlobalSnapshotData) -> 'EnvironmentSimulator':
        return self.start(
            voltage=snapshot.voltage,
            speed=snapshot.speed,
            odometer=snapshot.odometer,
            year=snapshot.year, month=snapshot.month, day=snapshot.day,
            hour=snapshot.hour, minute=snapshot.minute, second=snapshot.second
        )

    def stop(self) -> 'EnvironmentSimulator':
        from common.utils import TimerCyclic
        for tid in self._timer_ids:
            TimerCyclic.stop(tid)
        for tid in self._timer_ids:
            try:
                sim_message_ctrl._timers.remove(tid)
            except ValueError:
                pass
        self._timer_ids = ['env_speed', 'env_time', 'env_powermode']
        self._active = False
        TestLog("INFO", "环境模拟", "已停止")
        return self

    def _set_voltage(self, voltage: float) -> None:
        try:
            if ctx.power_ctrl:
                ctx.power_ctrl.set_voltage(voltage)
        except Exception as e:
            TestLog("WARNING", "环境模拟", f"电压设置失败: {e}")

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

            if tid not in self._timer_ids:
                self._timer_ids.append(tid)
            self._TimerCyclic.stop(tid)
            self._TimerCyclic.start(tid, cycle_ms, send_message)
            if tid not in sim_message_ctrl._timers:
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

    def _build_speed_msg(self, speed_msg_id: int, speed_kmh: float, odometer: int, is_fdf: bool) -> List[Dict[str, object]]:
        msgs: List[Dict[str, object]] = []
        speed_raw = int(round(float(speed_kmh) / 0.05625))
        print(f'speed_kmh{speed_kmh}, {speed_raw}')
        if speed_msg_id == 0x117:
            #车速
            dlc, cycle_ms, data_id, msg_id = 13, 10, 0x6117, 0x117
            data = bytearray(32)
            self._set_signal(self, data, 204, 13, speed_raw, False)
            self._set_signal(self, data, 205, 1, 1, False)  # 有效位
            msgs.append(
                {"data": data, "dlc": dlc, "cycle_ms": cycle_ms, "data_id": data_id, "msg_id": msg_id})

            #里程
            dlc, cycle_ms, data_id, msg_id = 13, 10, 0x611B, 0x11B
            data = bytearray(32)
            self._set_signal(self, data, 43, 20, odometer, False)
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
            self._set_signal(self, data, 23, 20, odometer, False)
            #挡位
            self._set_signal(self, data, 35, 2, 0x03, False)
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
            self._set_signal(self, data, 23, 20, odometer, False)
            #挡位
            self._set_signal(self, data, 35, 2, 0x03, False)
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
    #
    # def _set_speed_message(self, speed_msg_id: int, speed_kmh: float, odometer: int, is_canfd: bool):
    #     ch = DEFAULT_CAN_CHANNELS[0]
    #     msgs = self._build_speed_msg(speed_msg_id, speed_kmh, odometer, is_canfd)
    #     return msgs
    #
    # def _set_powermode_message(self, powermode_msg_id: int, mode: int, is_canfd: bool):
    #     ch = DEFAULT_CAN_CHANNELS[0]
    #     msgs = self._build_powermode_msg(powermode_msg_id, mode, is_canfd)
    #     return msgs
    #
    # def _set_ept_ready_message(self, value: int, is_canfd: bool):
    #     ch = DEFAULT_CAN_CHANNELS[0]
    #     msgs = self._build_ept_ready_msg(value, is_canfd)
    #     return msgs
    #
    # def _set_time_message(self, time_msg_id: int, year: int, month: int, day: int,
    #                     hour: int, minute: int, second: int, is_canfd: bool):
    #     ch = DEFAULT_CAN_CHANNELS[0]
    #     msgs = self._build_time_msg(time_msg_id, year, month, day, hour, minute, second, is_canfd)
    #     return msgs
    #
    # def _set_engine_speed_message(self, enginespeed_msg_id: int, speed: int, is_canfd: bool):
    #     ch = DEFAULT_CAN_CHANNELS[0]
    #     msgs = self._build_engine_speed_msg(enginespeed_msg_id, speed, is_canfd)
    #     return msgs

env_simulator = EnvironmentSimulator()


def write_dtc_config(
    node,
    did: int,
    config_data: bytes,
    expect_positive: bool = True,
    case_name: str = ""
) -> bool:
    try:
        TestLog("INFO", case_name, f"发送 2E {did:04X} 写入DTC配置")
        resp = node.Service_0x2E_WriteDataByIdentifier(
            did=did,
            record=config_data,
            func_req=False,
            timeout=5
        )

        if resp is None:
            if expect_positive:
                TestLog("FAIL", "", "2E服务: 未收到响应")
                return False
            else:
                TestLog("PASS", "", "2E服务: 未收到响应 (符合预期)")
                return True

        resp_data = list(resp.data) if hasattr(resp, 'data') else list(resp)

        if len(resp_data) >= 3 and resp_data[0] == 0x6E:
            resp_did = (resp_data[1] << 8) | resp_data[2]
            if resp_did == did:
                if expect_positive:
                    TestLog("PASS", "", f"2E服务: 收到肯定响应 6E {did:04X}")
                    return True
                else:
                    TestLog("FAIL", "", f"2E服务: 收到肯定响应 6E {did:04X}，但期望否定响应")
                    return False

        if len(resp_data) >= 3 and resp_data[0] == 0x7F and resp_data[1] == 0x2E:
            nrc = resp_data[2]
            if not expect_positive:
                TestLog("PASS", "", f"2E服务: 收到否定响应 NRC=0x{nrc:02X} (符合预期)")
                return True
            else:
                TestLog("FAIL", "", f"2E服务: 收到否定响应 NRC=0x{nrc:02X}")
                return False

        TestLog("WARNING", case_name, f"2E服务: 收到未知响应 {[hex(b) for b in resp_data]}")
        return False

    except Exception as e:
        TestLog("FAIL", "", f"2E服务执行出错: {e}")
        return False


def enable_dtc_config(node, did: int, dtc_index: int = 0, case_name: str = "") -> bool:
    try:
        TestLog("INFO", case_name, f"读取当前DTC配置 (DID: 0x{did:04X})")
        resp = node.Service_0x22_ReadDataByIdentifier(did=did, func_req=False, timeout=5)

        if resp is None:
            TestLog("FAIL", "", "无法读取当前DTC配置")
            return False

        resp_data = list(resp.data) if hasattr(resp, 'data') else list(resp)

        if len(resp_data) < 3 or resp_data[0] != 0x62:
            TestLog("FAIL", "", f"DTC配置读取响应格式错误: {[hex(b) for b in resp_data]}")
            return False

        config_data = bytearray(resp_data[3:])
        if len(config_data) == 0:
            TestLog("FAIL", "", "DTC配置数据为空")
            return False

        byte_index = dtc_index // 8
        bit_index = dtc_index % 8
        if byte_index < len(config_data):
            config_data[byte_index] |= (1 << bit_index)
            TestLog("INFO", case_name, f"设置配置位[{dtc_index}]为1 (启用)")
        else:
            TestLog("WARNING", case_name, f"DTC索引 {dtc_index} 超出配置数据范围")

        return write_dtc_config(node, did, bytes(config_data), expect_positive=True, case_name=case_name)

    except Exception as e:
        TestLog("FAIL", "", f"启用DTC配置出错: {e}")
        return False


def disable_dtc_config(node, did: int, dtc_index: int = 0, case_name: str = "") -> bool:
    try:
        TestLog("INFO", case_name, f"读取当前DTC配置 (DID: 0x{did:04X})")
        resp = node.Service_0x22_ReadDataByIdentifier(did=did, func_req=False, timeout=5)

        if resp is None:
            TestLog("FAIL", "", "无法读取当前DTC配置")
            return False

        resp_data = list(resp.data) if hasattr(resp, 'data') else list(resp)

        if len(resp_data) < 3 or resp_data[0] != 0x62:
            TestLog("FAIL", "", f"DTC配置读取响应格式错误: {[hex(b) for b in resp_data]}")
            return False

        config_data = bytearray(resp_data[3:])
        if len(config_data) == 0:
            TestLog("FAIL", "", "DTC配置数据为空")
            return False

        byte_index = dtc_index // 8
        bit_index = dtc_index % 8
        if byte_index < len(config_data):
            config_data[byte_index] &= ~(1 << bit_index)
            TestLog("INFO", case_name, f"设置配置位[{dtc_index}]为0 (禁用)")
        else:
            TestLog("WARNING", case_name, f"DTC索引 {dtc_index} 超出配置数据范围")

        return write_dtc_config(node, did, bytes(config_data), expect_positive=True, case_name=case_name)

    except Exception as e:
        TestLog("FAIL", "", f"禁用DTC配置出错: {e}")
        return False


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


def tc13(node, sim, fault_type):
    import time
    case_name = "TC13"

    try:
        TestLog("INFO", "TC13", "")
        TestLog("INFO", "Step1", "使用0x14服务清除所有DTC")
        clear_dtc(node)
        time.sleep(1)

        TestLog("INFO", "Step2", "模拟产生故障")
        dtc_select = inject_fault(sim, type=fault_type)
        TestLog("INFO", "Step3", "发送 19 02 FF 请求读取DTC信息")
        success, status = find_DTC_by_status_mask(node, 0xFF, dtc_select)
        if not success:
            TestLog("FAIL", "", "未查询到测试的DTC")
            return

        expect = f"状态位0x{0x2F & P.DiagServiceInfo.DTCStatusAvlMask: 02X}"
        actual = f"状态位0x{status: 02X}"
        if status & (0x2F & P.DiagServiceInfo.DTCStatusAvlMask) == (0x2F & P.DiagServiceInfo.DTCStatusAvlMask):
            TestLog("PASS", "", f"期望结果：{expect}, 实际结果：{actual}")
        else:
            TestLog("FAIL", "", f"期望结果：{expect}, 实际结果：{actual}")

        TestLog("INFO", "Step4", "发送 19 06 XX XX XX RecordNumber 请求读取DTC扩展信息")
        success, occurrence_counter, pending_counter, aged_counter, ageing_counter = read_extend_data(node, dtc_select)
        if not success:
            TestLog("FAIL", "", "未获取到扩展数据")
            return

        expected_counter = (1, 1, 0, 0)
        actual_counter = (occurrence_counter, pending_counter, aged_counter, ageing_counter)
        expect = (f"扩展数据 OccurrenceCounter= {expected_counter[0]}, PendingCounter={expected_counter[1]}, "
                  f"AgedCounter={expected_counter[2]}, AgeingCounter={expected_counter[3]}")
        actual = (f"扩展数据 OccurrenceCounter={actual_counter[0]}, PendingCounter={actual_counter[1]}, "
                  f"AgedCounter={actual_counter[2]}, AgeingCounter={actual_counter[3]}")
        if all(a is None or a == e for a, e in zip(actual_counter, expected_counter)):
            TestLog("PASS", "", f"期望结果：{expect}, 实际结果：{actual}")
        else:
            TestLog("FAIL", "", f"期望结果：{expect}, 实际结果：{actual}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        return

def tc14(node, sim, fault_type, dtc_select):
    case_name = "TC14"

    try:
        TestLog("INFO", "TC14", "")
        TestLog("INFO", "Step1", "恢复故障")
        recovery_fault(sim, type=fault_type, dtc_select=dtc_select)
        TestLog("INFO", "Step2", "发送 19 02 FF 请求读取DTC信息")
        success, status = find_DTC_by_status_mask(node, 0xFF, dtc_select)
        if not success:
            TestLog("FAIL", "", "未查询到测试的DTC")
            return

        expect = f"状态位0x{0x2E & P.DiagServiceInfo.DTCStatusAvlMask: 02X}"
        actual = f"状态位0x{status: 02X}"
        if status & (0x2E & P.DiagServiceInfo.DTCStatusAvlMask) == (0x2E & P.DiagServiceInfo.DTCStatusAvlMask):
            TestLog("PASS", "", f"期望结果：{expect}, 实际结果：{actual}")
        else:
            TestLog("FAIL", "", f"期望结果：{expect}, 实际结果：{actual}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        return

def tc15(node, sim, fault_type, dtc_select):
    import time
    case_name = "TC15"

    try:
        TestLog("INFO", case_name, "")
        TestLog("INFO", "Step1", "使用0x14服务清除所有DTC")
        clear_dtc(node)
        time.sleep(1)

        N = 3
        for i in range(N):
            TestLog("INFO", "Step1", f"进入第{i+1}个操作循环")
            operation_cycle_jump(sim)

            TestLog("INFO", "Step2", "模拟产生故障")
            dtc_select = inject_fault(sim, type=fault_type)
            
        TestLog("INFO", "Step2", "发送 19 02 FF 请求读取DTC信息")
        success, status = find_DTC_by_status_mask(node, 0xFF, dtc_select)
        if not success:
            TestLog("FAIL", "", "未查询到测试的DTC")
            return

        expect = f"状态位0x{0x2F & P.DiagServiceInfo.DTCStatusAvlMask: 02X}"
        actual = f"状态位0x{status: 02X}"
        if status & (0x2F & P.DiagServiceInfo.DTCStatusAvlMask) == (0x2F & P.DiagServiceInfo.DTCStatusAvlMask):
            TestLog("PASS", "", f"期望结果：{expect}, 实际结果：{actual}")
        else:
            TestLog("FAIL", "", f"期望结果：{expect}, 实际结果：{actual}")

        TestLog("INFO", "Step3", "发送 19 06 XX XX XX RecordNumber 请求读取DTC扩展信息")
        success, occurrence_counter, pending_counter, aged_counter, ageing_counter = read_extend_data(node,
                                                                                                      dtc_select)
        if not success:
            TestLog("FAIL", "", "未获取到扩展数据")
            return

        expected_counter = (N, N, 0, 0)
        actual_counter = (occurrence_counter, pending_counter, aged_counter, ageing_counter)
        expect = (f"扩展数据 OccurrenceCounter= {expected_counter[0]}, PendingCounter={expected_counter[1]}, "
                  f"AgedCounter={expected_counter[2]}, AgeingCounter={expected_counter[3]}")
        actual = (f"扩展数据 OccurrenceCounter={actual_counter[0]}, PendingCounter={actual_counter[1]}, "
                  f"AgedCounter={actual_counter[2]}, AgeingCounter={actual_counter[3]}")
        if all(a is None or a == e for a, e in zip(actual_counter, expected_counter)):
            TestLog("PASS", "", f"期望结果：{expect}, 实际结果：{actual}")
        else:
            TestLog("FAIL", "", f"期望结果：{expect}, 实际结果：{actual}")


    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        return

def tc16(node, sim, fault_type):
    import time
    case_name = "TC16"

    try:
        TestLog("INFO", case_name, "")
        TestLog("INFO", "Step1", "进入下一个操作循环")
        operation_cycle_jump(sim)

        TestLog("INFO", "Step2", "模拟产生故障")
        dtc_select = inject_fault(sim, type=fault_type)
        TestLog("INFO", "Step3", "发送 19 02 FF 请求读取DTC信息")
        success, status = find_DTC_by_status_mask(node, 0xFF, dtc_select)
        if not success:
            TestLog("FAIL", "", "未查询到测试的DTC")
            return

        expect = f"状态位0x{0x2F & P.DiagServiceInfo.DTCStatusAvlMask: 02X}"
        actual = f"状态位0x{status: 02X}"
        if status & (0x2F & P.DiagServiceInfo.DTCStatusAvlMask) == (0x2F & P.DiagServiceInfo.DTCStatusAvlMask):
            TestLog("PASS", "", f"期望结果：{expect}, 实际结果：{actual}")
        else:
            TestLog("FAIL", "", f"期望结果：{expect}, 实际结果：{actual}")

        TestLog("INFO", "Step4", "发送 19 06 XX XX XX RecordNumber 请求读取DTC扩展信息")
        success, occurrence_counter, pending_counter, aged_counter, ageing_counter = read_extend_data(node, dtc_select)
        if not success:
            TestLog("FAIL", "", "未获取到扩展数据")
            return

        expected_counter = (2, 1, 0, 0)
        actual_counter = (occurrence_counter, pending_counter, aged_counter, ageing_counter)
        expect = (f"扩展数据 OccurrenceCounter= {expected_counter[0]}, PendingCounter={expected_counter[1]}, "
                  f"AgedCounter={expected_counter[2]}, AgeingCounter={expected_counter[3]}")
        actual = (f"扩展数据 OccurrenceCounter={actual_counter[0]}, PendingCounter={actual_counter[1]}, "
                  f"AgedCounter={actual_counter[2]}, AgeingCounter={actual_counter[3]}")
        if all(a is None or a == e for a, e in zip(actual_counter, expected_counter)):
            TestLog("PASS", "", f"期望结果：{expect}, 实际结果：{actual}")
        else:
            TestLog("FAIL", "", f"期望结果：{expect}, 实际结果：{actual}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        return

def tc17(node, sim, fault_type, dtc_select):
    import time
    case_name = "TC17"

    try:
        TestLog("INFO", case_name, "")
        TestLog("INFO", "Step1", "恢复故障")
        recovery_fault(sim, type=fault_type, dtc_select=dtc_select)

        TestLog("INFO", "Step2", "进入下一个操作循环")
        operation_cycle_jump(sim)

        TestLog("INFO", "Step3", "发送 19 02 FF 请求读取DTC信息")
        success, status = find_DTC_by_status_mask(node, 0xFF, dtc_select)
        if not success:
            TestLog("FAIL", "", "未查询到测试的DTC")
            return

        expect = f"状态位0x{0x2C & P.DiagServiceInfo.DTCStatusAvlMask: 02X}"
        actual = f"状态位0x{status: 02X}"
        if status & (0x2C & P.DiagServiceInfo.DTCStatusAvlMask) == (0x2C & P.DiagServiceInfo.DTCStatusAvlMask):
            TestLog("PASS", "", f"期望结果：{expect}, 实际结果：{actual}")
        else:
            TestLog("FAIL", "", f"期望结果：{expect}, 实际结果：{actual}")

        TestLog("INFO", "Step4", "发送 19 06 XX XX XX RecordNumber 请求读取DTC扩展信息")
        success, occurrence_counter, pending_counter, aged_counter, ageing_counter = read_extend_data(node, dtc_select)
        if not success:
            TestLog("FAIL", "", "未获取到扩展数据")
            return

        expected_counter = (2, 1, 0, 0)
        actual_counter = (occurrence_counter, pending_counter, aged_counter, ageing_counter)
        expect = (f"扩展数据 OccurrenceCounter= {expected_counter[0]}, PendingCounter={expected_counter[1]}, "
                  f"AgedCounter={expected_counter[2]}, AgeingCounter={expected_counter[3]}")
        actual = (f"扩展数据 OccurrenceCounter={actual_counter[0]}, PendingCounter={actual_counter[1]}, "
                  f"AgedCounter={actual_counter[2]}, AgeingCounter={actual_counter[3]}")
        if all(a is None or a == e for a, e in zip(actual_counter, expected_counter)):
            TestLog("PASS", "", f"期望结果：{expect}, 实际结果：{actual}")
        else:
            TestLog("FAIL", "", f"期望结果：{expect}, 实际结果：{actual}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        return

def tc18(node, fault_type, dtc_select):
    import time
    case_name = "TC18"

    try:
        TestLog("INFO", case_name, "")
        TestLog("INFO", "Step1", "进入第2个操作循环")
        operation_cycle_jump()

        TestLog("INFO", "Step2", "发送 19 02 FF 请求读取DTC信息")
        success, status = find_DTC_by_status_mask(node, 0xFF, dtc_select)
        if not success:
            TestLog("FAIL", "", "未查询到测试的DTC")
            return

        expect = f"状态位0x{0x28 & P.DiagServiceInfo.DTCStatusAvlMask: 02X}"
        actual = f"状态位0x{status: 02X}"
        if status & (0x28 & P.DiagServiceInfo.DTCStatusAvlMask) == (0x28 & P.DiagServiceInfo.DTCStatusAvlMask):
            TestLog("PASS", "", f"期望结果：{expect}, 实际结果：{actual}")
        else:
            TestLog("FAIL", "", f"期望结果：{expect}, 实际结果：{actual}")

        TestLog("INFO", "Step3", "发送 19 06 XX XX XX RecordNumber 请求读取DTC扩展信息")
        success, occurrence_counter, pending_counter, aged_counter, ageing_counter = read_extend_data(node, dtc_select)
        if not success:
            TestLog("FAIL", "", "未获取到扩展数据")
            return

        expected_counter = (2, 1, 0, 1)
        actual_counter = (occurrence_counter, pending_counter, aged_counter, ageing_counter)
        expect = (f"扩展数据 OccurrenceCounter= {expected_counter[0]}, PendingCounter={expected_counter[1]}, "
                  f"AgedCounter={expected_counter[2]}, AgeingCounter={expected_counter[3]}")
        actual = (f"扩展数据 OccurrenceCounter={actual_counter[0]}, PendingCounter={actual_counter[1]}, "
                  f"AgedCounter={actual_counter[2]}, AgeingCounter={actual_counter[3]}")
        if all(a is None or a == e for a, e in zip(actual_counter, expected_counter)):
            TestLog("PASS", "", f"期望结果：{expect}, 实际结果：{actual}")
        else:
            TestLog("FAIL", "", f"期望结果：{expect}, 实际结果：{actual}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        return

def tc19(node, fault_type, dtc_select):
    import time
    case_name = "TC19"

    try:
        TestLog("INFO", case_name, "")
        TestLog("INFO", "Step1", "进入第3个操作循环")
        operation_cycle_jump()

        TestLog("INFO", "Step2", "发送 19 02 FF 请求读取DTC信息")
        success, status = find_DTC_by_status_mask(node, 0xFF, dtc_select)
        if not success:
            TestLog("FAIL", "", "未查询到测试的DTC")
            return

        expect = f"状态位0x{0x28 & P.DiagServiceInfo.DTCStatusAvlMask: 02X}"
        actual = f"状态位0x{status: 02X}"
        if status & (0x28 & P.DiagServiceInfo.DTCStatusAvlMask) == (0x28 & P.DiagServiceInfo.DTCStatusAvlMask):
            TestLog("PASS", "", f"期望结果：{expect}, 实际结果：{actual}")
        else:
            TestLog("FAIL", "", f"期望结果：{expect}, 实际结果：{actual}")

        TestLog("INFO", "Step3", "发送 19 06 XX XX XX RecordNumber 请求读取DTC扩展信息")
        success, occurrence_counter, pending_counter, aged_counter, ageing_counter = read_extend_data(node, dtc_select)
        if not success:
            TestLog("FAIL", "", "未获取到扩展数据")
            return

        expected_counter = (2, 1, 0, 2)
        actual_counter = (occurrence_counter, pending_counter, aged_counter, ageing_counter)
        expect = (f"扩展数据 OccurrenceCounter= {expected_counter[0]}, PendingCounter={expected_counter[1]}, "
                  f"AgedCounter={expected_counter[2]}, AgeingCounter={expected_counter[3]}")
        actual = (f"扩展数据 OccurrenceCounter={actual_counter[0]}, PendingCounter={actual_counter[1]}, "
                  f"AgedCounter={actual_counter[2]}, AgeingCounter={actual_counter[3]}")
        if all(a is None or a == e for a, e in zip(actual_counter, expected_counter)):
            TestLog("PASS", "", f"期望结果：{expect}, 实际结果：{actual}")
        else:
            TestLog("FAIL", "", f"期望结果：{expect}, 实际结果：{actual}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        return

def tc20(node, fault_type, dtc_select):
    import time
    case_name = "TC20"

    try:
        TestLog("INFO", case_name, "")
        TestLog("INFO", "Step1", "进入第4个操作循环")
        operation_cycle_jump()

        TestLog("INFO", "Step2", "发送 19 02 FF 请求读取DTC信息")
        success, status = find_DTC_by_status_mask(node, 0xFF, dtc_select)
        if not success:
            TestLog("FAIL", "", "未查询到测试的DTC")
            return

        expect = f"状态位0x{0x28 & P.DiagServiceInfo.DTCStatusAvlMask: 02X}"
        actual = f"状态位0x{status: 02X}"
        if status & (0x28 & P.DiagServiceInfo.DTCStatusAvlMask) == (0x28 & P.DiagServiceInfo.DTCStatusAvlMask):
            TestLog("PASS", "", f"期望结果：{expect}, 实际结果：{actual}")
        else:
            TestLog("FAIL", "", f"期望结果：{expect}, 实际结果：{actual}")

        TestLog("INFO", "Step3", "发送 19 06 XX XX XX RecordNumber 请求读取DTC扩展信息")
        success, occurrence_counter, pending_counter, aged_counter, ageing_counter = read_extend_data(node, dtc_select)
        if not success:
            TestLog("FAIL", "", "未获取到扩展数据")
            return

        expected_counter = (2, 1, 0, 3)
        actual_counter = (occurrence_counter, pending_counter, aged_counter, ageing_counter)
        expect = (f"扩展数据 OccurrenceCounter= {expected_counter[0]}, PendingCounter={expected_counter[1]}, "
                  f"AgedCounter={expected_counter[2]}, AgeingCounter={expected_counter[3]}")
        actual = (f"扩展数据 OccurrenceCounter={actual_counter[0]}, PendingCounter={actual_counter[1]}, "
                  f"AgedCounter={actual_counter[2]}, AgeingCounter={actual_counter[3]}")
        if all(a is None or a == e for a, e in zip(actual_counter, expected_counter)):
            TestLog("PASS", "", f"期望结果：{expect}, 实际结果：{actual}")
        else:
            TestLog("FAIL", "", f"期望结果：{expect}, 实际结果：{actual}")

        for i in range(5,41):
            TestLog("INFO", "Step1", f"进入第{i}个操作循环")
            operation_cycle_jump()

            TestLog("INFO", "Step2", "发送 19 02 FF 请求读取DTC信息")
            success, status = find_DTC_by_status_mask(node, 0xFF, dtc_select)
            if not success:
                TestLog("FAIL", "", "未查询到测试的DTC")
                return

            expect = f"状态位0x{0x28 & P.DiagServiceInfo.DTCStatusAvlMask: 02X}"
            actual = f"状态位0x{status: 02X}"
            if status & (0x28 & P.DiagServiceInfo.DTCStatusAvlMask) == (0x28 & P.DiagServiceInfo.DTCStatusAvlMask):
                TestLog("PASS", "", f"期望结果：{expect}, 实际结果：{actual}")
            else:
                TestLog("FAIL", "", f"期望结果：{expect}, 实际结果：{actual}")

            TestLog("INFO", "Step3", "发送 19 06 XX XX XX RecordNumber 请求读取DTC扩展信息")
            success, occurrence_counter, pending_counter, aged_counter, ageing_counter = read_extend_data(node,
                                                                                                          dtc_select)
            if not success:
                TestLog("FAIL", "", "未获取到扩展数据")
                return

            expected_counter = (2, 0, 0, i-1)
            actual_counter = (occurrence_counter, pending_counter, aged_counter, ageing_counter)
            expect = (f"扩展数据 OccurrenceCounter= {expected_counter[0]}, PendingCounter={expected_counter[1]}, "
                      f"AgedCounter={expected_counter[2]}, AgeingCounter={expected_counter[3]}")
            actual = (f"扩展数据 OccurrenceCounter={actual_counter[0]}, PendingCounter={actual_counter[1]}, "
                      f"AgedCounter={actual_counter[2]}, AgeingCounter={actual_counter[3]}")
            if all(a is None or a == e for a, e in zip(actual_counter, expected_counter)):
                TestLog("PASS", "", f"期望结果：{expect}, 实际结果：{actual}")
            else:
                TestLog("FAIL", "", f"期望结果：{expect}, 实际结果：{actual}")


    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        return

def tc21(node, fault_type, dtc_select):
    import time
    case_name = "TC21"

    try:
        TestLog("INFO", case_name, "")
        TestLog("INFO", "Step1", "进入第41个操作循环")
        operation_cycle_jump()

        TestLog("INFO", "Step2", "发送 19 02 FF 请求读取DTC信息")
        success, resp = service_19_check(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0xFF
        )

        if not success:
            TestLog("FAIL", "", "未收到肯定响应")
            return

        dtc_list = get_dtc_list_from_19_resp(resp)
        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        if len(dtc_list) == 0:
            TestLog("FAIL", "", "未读取到任何 DTC")
            return

        result = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"
            if dtc_str == dtc_select:
                TestLog("INFO", "", f"读取到故障码 {dtc_select}")
                result = True
        if not result:
            TestLog("INFO", "", f"期望结果：读取到故障码 {dtc_select}, "
                                f"实际结果：没有读取到故障码 {dtc_select}")

        TestLog("INFO", "Step3", "发送 19 06 XX XX XX RecordNumber 请求读取DTC扩展信息")
        success, occurrence_counter, pending_counter, aged_counter, ageing_counter = read_extend_data(node, dtc_select)
        if not success:
            TestLog("FAIL", "", "未获取到扩展数据")
            return

        expected_counter = (0, 0, None, 0)
        actual_counter = (occurrence_counter, pending_counter, aged_counter, ageing_counter)
        expect = (f"扩展数据 OccurrenceCounter= {expected_counter[0]}, PendingCounter={expected_counter[1]}, "
                  f"AgedCounter={expected_counter[2]}, AgeingCounter={expected_counter[3]}")
        actual = (f"扩展数据 OccurrenceCounter={actual_counter[0]}, PendingCounter={actual_counter[1]}, "
                  f"AgedCounter={actual_counter[2]}, AgeingCounter={actual_counter[3]}")
        if all(a is None or a == e for a, e in zip(actual_counter, expected_counter)):
            TestLog("PASS", "", f"期望结果：{expect}, 实际结果：{actual}")
        else:
            TestLog("FAIL", "", f"期望结果：{expect}, 实际结果：{actual}")

    except Exception as e:
        TestLog("FAIL", case_name, f"测试执行出错: {e}")
        return

def inject_fault(sim, type=""):
    dtc_select = None
    if type == "低压":
        for item in P.ExtendedDTCInfo.voltage.valid_items:
            if "低压" not in item.Notes:
                continue

            TestLog("INFO", "", "模拟产生故障_低压")
            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{5000} ms")
            ctx.power_ctrl.set_voltage(P.TpInfo.LowVoltage)
            operation_after_low_voltage()

            wait_time_s = 5
            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)
            break

    elif type == "busoff":
        for item in P.ExtendedDTCInfo.bus_off.valid_items:
            TestLog("INFO", "", "模拟产生故障_Busoff")
            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{5000} ms")
            sim.busoff_fault(True)

            wait_time_s = 5
            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)

            sim.busoff_fault(False)
            time.sleep(wait_time_s)
            break

    elif type == "e2e":
        for item in P.ExtendedDTCInfo.invalid_data.valid_items:
            injected_faults = []
            if "E2E" not in item.Type.upper():
                continue

            TestLog("INFO", "", "模拟产生故障_校验错误")
            dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
            TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{item.PassTime} ms")
            sim.crc_e2e_fault(True, item.MonitorMessageID, item.Type,
                              dlc=item.MonitorMessageDLC, cycle_ms=item.MonitorMessagePeriod or 100,
                              data=item.ValidPayload, is_canfd=item.FDF,
                              is_e2e=item.IsContainE2E, data_id=item.DataID)
            injected_faults.append(('e2e', item))

            wait_time_s = (item.LostTime or 5000) / 1000
            TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
            time.sleep(wait_time_s)
            break
    #
    # elif type == "lost":
    #     for item in P.ExtendedDTCInfo.lost_communication.valid_items:
    #         TestLog("INFO", "", "模拟产生故障_丢失通讯")
    #         dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
    #         TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{item.LostTime} ms")
    #         sim.lost_comm_fault(True, item.MonitorMessageID)
    #
    #         wait_time_s = (item.LostTime or 5000) / 1000
    #         TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
    #         time.sleep(wait_time_s)
    #         break

    return dtc_select

def inject_all_fault(node, sim):
    simulated_dtc = []

    for item in P.ExtendedDTCInfo.lost_communication.valid_items:
        TestLog("INFO", "", "模拟产生故障_丢失通讯")
        dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
        TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{item.LostTime} ms")
        sim.lost_comm_fault(True, item.MonitorMessageID)

        wait_time_s = (item.LostTime or 5000) / 1000
        TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
        time.sleep(wait_time_s)

        TestLog("INFO", "Step2", "发送 19 02 FF 请求读取DTC信息")
        success, status = find_DTC_by_status_mask(node, 0xFF, dtc_select)
        if not success:
            TestLog("FAIL", "", "未查询到测试的DTC")
            continue

        if (status & 0x01) != 0:
            TestLog("PASS", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为1, "
                                f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为1")
            simulated_dtc.append(dtc_select)
        else:
            TestLog("FAIL", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为1, "
                                f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为0")

        TestLog("INFO", "", f"恢复故障DTC(0x{dtc_select})，等待故障恢复时间: {wait_time_s:.1f}s")
        check_and_recovery_env_simulator(item.MonitorMessageID)
        sim.lost_comm_fault(False, item.MonitorMessageID, dlc=item.MonitorMessageDLC,
                            cycle_ms=item.MonitorMessagePeriod or 100, is_canfd=item.FDF)
        wait_time_s = (item.PassTime or 1000) / 1000
        time.sleep(wait_time_s)

    for item in P.ExtendedDTCInfo.invalid_data.valid_items:
        injected_faults = []
        if item.Type != "InvalidData":
            continue
        TestLog("INFO", "", "模拟产生故障_无效数据")

        dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x","")
        TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC相关的报文并等待{item.PassTime} ms")
        sim.invalid_data_fault(True, item.MonitorMessageID,
                                    dlc=item.MonitorMessageDLC, cycle_ms=item.MonitorMessagePeriod or 100,
                                    data = item.InvalidPayload, is_canfd=item.FDF,
                                    is_e2e = item.IsContainE2E, data_id = item.DataID)
        injected_faults.append(('invalid', item))

        wait_time_s = (item.LostTime or 5000) / 1000
        TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
        time.sleep(wait_time_s)

        TestLog("INFO", "Step2", "发送 19 02 FF 请求读取DTC信息")
        success, status = find_DTC_by_status_mask(node, 0xFF, dtc_select)
        if not success:
            TestLog("FAIL", "", "未查询到测试的DTC")
            continue

        if (status & 0x01) != 0:
            TestLog("PASS", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为1, "
                                f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为1")
            simulated_dtc.append(dtc_select)
        else:
            TestLog("FAIL", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为1, "
                                f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为0")

        TestLog("INFO", "", f"恢复故障DTC(0x{dtc_select})，等待故障确认时间: {wait_time_s:.1f}s")
        check_and_recovery_env_simulator(item.MonitorMessageID)
        sim.invalid_data_fault(False, item.MonitorMessageID,
                               dlc=item.MonitorMessageDLC, cycle_ms=item.MonitorMessagePeriod or 100,
                               data=item.ValidPayload, is_canfd=item.FDF,
                               is_e2e=item.IsContainE2E, data_id=item.DataID)
        wait_time_s = (item.PassTime or 1000) / 1000
        time.sleep(wait_time_s)

    for item in P.ExtendedDTCInfo.voltage.valid_items:
        if "低压" not in item.Notes:
            continue

        TestLog("INFO", "", "模拟产生故障_低压")
        dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
        TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC并等待{5000} ms")
        ctx.power_ctrl.set_voltage(P.TpInfo.LowVoltage)
        operation_after_low_voltage()

        wait_time_s = 5
        TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
        time.sleep(wait_time_s)

        TestLog("INFO", "Step2", "发送 19 02 FF 请求读取DTC信息")
        success, status = find_DTC_by_status_mask(node, 0xFF, dtc_select)
        if not success:
            TestLog("FAIL", "", "未查询到测试的DTC")
            continue

        if (status & 0x01) != 0:
            TestLog("PASS", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为1, "
                                f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为1")
            simulated_dtc.append(dtc_select)
        else:
            TestLog("FAIL", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为1, "
                                f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为0")

        TestLog("INFO", "", f"恢复故障DTC(0x{dtc_select})，等待故障恢复时间: {wait_time_s:.1f}s")
        ctx.power_ctrl.set_voltage(P.CANInfo.Vnormal)
        time.sleep(wait_time_s)
        break

    first_e2e_skipped = False
    for item in P.ExtendedDTCInfo.invalid_data.valid_items:
        if "E2E" in item.Type.upper() and not first_e2e_skipped:
            first_e2e_skipped = True  # 只跳一次
            continue
        if "E2E" not in item.Type.upper():
            continue
        TestLog("INFO", "", "模拟产生故障_E2E")

        dtc_select = (item.DTCCode_hex + item.FailureType_hex).replace("0x", "")
        TestLog("INFO", "", f"选取(0x{dtc_select})作为测试DTC，仿真测试DTC相关的报文并等待{item.PassTime} ms")
        sim.crc_e2e_fault(True, item.MonitorMessageID, item.Type,
                          dlc=item.MonitorMessageDLC, cycle_ms=item.MonitorMessagePeriod or 100,
                          data=item.ValidPayload, is_canfd=item.FDF,
                          is_e2e=item.IsContainE2E, data_id=item.DataID)

        wait_time_s = (item.LostTime or 5000) / 1000
        TestLog("INFO", "", f"等待故障确认时间: {wait_time_s:.1f}s")
        time.sleep(wait_time_s)

        TestLog("INFO", "Step2", "发送 19 02 FF 请求读取DTC信息")
        success, status = find_DTC_by_status_mask(node, 0xFF, dtc_select)
        if not success:
            TestLog("FAIL", "", "未查询到测试的DTC")
            continue

        if (status & 0x01) != 0:
            TestLog("PASS", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为1, "
                                f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为1")
            simulated_dtc.append(dtc_select)
        else:
            TestLog("FAIL", "", f"期望结果：故障码{dtc_select}的statusOfDTC的bit0置为1, "
                                f"实际结果：故障码{dtc_select}的statusOfDTC的bit0置为0")

        TestLog("INFO", "", f"恢复故障DTC(0x{dtc_select})，等待故障确认时间: {wait_time_s:.1f}s")
        check_and_recovery_env_simulator(item.MonitorMessageID)
        sim.crc_e2e_fault(False, item.MonitorMessageID, item.Type,
                          dlc=item.MonitorMessageDLC, cycle_ms=item.MonitorMessagePeriod or 100,
                          data=item.ValidPayload, is_canfd=item.FDF,
                          is_e2e=item.IsContainE2E, data_id=item.DataID)
        wait_time_s = (item.PassTime or 1000) / 1000
        time.sleep(wait_time_s)

    return simulated_dtc

def select_fault_type(node, sim):
    fault_type = None
    dtc_select = None

    clear_dtc(node)
    time.sleep(1)

    if fault_type is None:
        dtc_select = inject_fault(sim, type="低压")
        if dtc_select is not None:
            TestLog("INFO", "", "发送 19 02 09 请求读取DTC信息")
            success, status = find_DTC_by_status_mask(node, 0x09, dtc_select)
            if not success:
                TestLog("INFO", "", "不支持低压故障")
            else:
                fault_type = "低压"
        recovery_fault(sim, "低压", dtc_select)

    if fault_type is None:
        dtc_select = inject_fault(sim, type="busoff")
        if dtc_select is not None:
            TestLog("INFO", "", "发送 19 02 09 请求读取DTC信息")
            success, status = find_DTC_by_status_mask(node, 0x09, dtc_select)
            if not success:
                TestLog("INFO", "", "不支持busoff故障")
            else:
                fault_type = "busoff"

    if fault_type is None:
        dtc_select = inject_fault(sim, type="e2e")
        if dtc_select is not None:
            TestLog("INFO", "", "发送 19 02 09 请求读取DTC信息")
            success, status = find_DTC_by_status_mask(node, 0x09, dtc_select)
            if not success:
                TestLog("INFO", "", "不支持e2e故障")
            else:
                fault_type = "e2e"

    # if fault_type is None:
    #     dtc_select = inject_fault(sim, type="lost")
    #     if dtc_select is not None:
    #         TestLog("INFO", "", "发送 19 02 09 请求读取DTC信息")
    #         success, status = find_DTC_by_status_mask(node, 0x09, dtc_select)
    #         if not success:
    #             TestLog("INFO", "", "不支持丢失通讯故障")
    #         else:
    #             fault_type = "lost"

    clear_dtc(node)
    time.sleep(1)

    return fault_type, dtc_select

def recovery_fault(sim, type="", dtc_select=""):
    if type == "低压":
        for item in P.ExtendedDTCInfo.voltage.valid_items:
            if "低压" not in item.Notes:
                continue
            wait_time_s = 5
            TestLog("INFO", "", f"恢复故障DTC(0x{dtc_select})，等待故障恢复时间: {wait_time_s:.1f}s")
            ctx.power_ctrl.set_voltage(P.CANInfo.Vnormal)
            time.sleep(wait_time_s)
    elif type == "busoff":
        TestLog("INFO", "", f"恢复故障DTC(0x{dtc_select}")
    elif type == "e2e":
        for item in P.ExtendedDTCInfo.invalid_data.valid_items:
            if "E2E" not in item.Type.upper():
                continue
            TestLog("INFO", "", f"恢复故障DTC(0x{dtc_select}，等待故障恢复时间: {item.PassTime:.1f}s")
            check_and_recovery_env_simulator(item.MonitorMessageID)
            sim.crc_e2e_fault(False, item.MonitorMessageID, item.Type,
                              dlc=item.MonitorMessageDLC, cycle_ms=item.MonitorMessagePeriod or 100,
                              data=item.ValidPayload, is_canfd=item.FDF,
                          is_e2e=item.IsContainE2E, data_id=item.DataID)
            wait_time_s = (item.PassTime or 1000) / 1000
            time.sleep(wait_time_s)
            break
    # else:
    #     for item in P.ExtendedDTCInfo.lost_communication.valid_items:
    #         TestLog("INFO", "", f"恢复故障DTC(0x{dtc_select})，等待故障恢复时间: {item.PassTime:.1f}s")
    #         check_and_recovery_env_simulator(item.MonitorMessageID)
    #         sim.lost_comm_fault(False, item.MonitorMessageID, dlc=item.MonitorMessageDLC,
    #                             cycle_ms=item.MonitorMessagePeriod or 100, is_canfd=item.FDF)
    #         wait_time_s = (item.PassTime or 1000) / 1000
    #         time.sleep(wait_time_s)
    #         break

def operation_cycle_jump(sim: FaultSimulator = None):
    if sim is None:
        sim = FaultSimulator()

    WakeupStop()
    is_canfd = P.ProjectInfo.ECUType == 2
    msgs = env_simulator._build_powermode_msg(P.CANInfo.PowerModeMsgID, env_simulator._POWERMODE_OFF, is_canfd)
    if P.ECUInfo.ECUName == "PICU":
        msgs.extend(env_simulator._build_ept_ready_msg(env_simulator._EPT_READY_Unenable, is_canfd))
    env_simulator._send_can_messages(msgs)
    time.sleep(1)
    sim.stop_all_timer()
    env_simulator.stop()
    print("aaaxxxxxxxxxxxxx")

    ctx.bob_ctrl.set_power('KL15', False)
    time.sleep(2)

    # 等待DUT进入睡眠模式
    status, msg = wait_dut_enter_sleep(P.ECUInfo.ISleep / 1000, P.NMInfo.TpowerOnInitial_s)
    if status is False:
        TestLog("FAIL", "", f"DUT未进入睡眠模式: {msg}")

    WakeupStart()
    ctx.bob_ctrl.set_power('KL15', True)
    dtc_enable_conditions(True, env_simulator._POWERMODE_RUN)
    time.sleep(5)


def dtc_enable_conditions(enable = True, mode = 1):
    is_canfd = P.ProjectInfo.ECUType == 2
    if enable:
        TestLog("INFO", "", f"发送模拟信号: powermode = {mode}, ept_ready = {env_simulator._EPT_READY_Enable}")
        msgs = env_simulator._build_powermode_msg(P.CANInfo.PowerModeMsgID, mode, is_canfd)
        if P.ECUInfo.ECUName == "PICU":
            msgs.extend(env_simulator._build_ept_ready_msg(env_simulator._EPT_READY_Enable, is_canfd))
        env_simulator._send_can_messages(msgs)
        time.sleep(2)
    else:
        from common.utils import TimerCyclic
        env_simulator.stop()

def sim_engine_rpm_msg(enable = True):
    is_canfd = P.ProjectInfo.ECUType == 2
    durationtime = 3
    if enable:
        msgs = env_simulator._build_engine_speed_msg(P.CANInfo.EngineSpeedMsgID, 0, is_canfd)
        env_simulator._send_can_messages(msgs)

        steptime = durationtime/10
        for i in range(10):
            currentrpm = 0+(i*80)
            msgs = env_simulator._build_engine_speed_msg(P.CANInfo.EngineSpeedMsgID, currentrpm, is_canfd)
            env_simulator._send_can_messages(msgs)
            time.sleep(steptime)
        time.sleep(2)
    else:
        from common.utils import TimerCyclic
        tid = f"sim_{P.CANInfo.SpeedMsgID:X}"
        TimerCyclic.stop(tid)

def check_and_recovery_env_simulator(test_msg_id):
    msg = []
    print(sim_message_ctrl._StopTimer)
    print(sim_message_ctrl._timers)
    if f"sim_{test_msg_id:X}" == sim_message_ctrl._StopTimer:
        for item in reversed(sim_message_ctrl.msgs):
            msg_id = int(item['msg_id'] or 0)
            if msg_id == test_msg_id:
                msg.append(item)
                env_simulator._send_can_messages(msg)
                sim_message_ctrl._StopTimer = ""
                break

def clear_dtc(node):
    is_canfd = P.ProjectInfo.ECUType == 2
    if P.ECUInfo.ECUName == "PICU":
        msgs = env_simulator._build_ept_ready_msg(env_simulator._EPT_READY_Unenable, is_canfd)
        env_simulator._send_can_messages(msgs)
        time.sleep(2)
        service_14_check(node, expect_data=[0x54], expect_str="肯定响应(54)")
        msgs = env_simulator._build_ept_ready_msg(env_simulator._EPT_READY_Enable, is_canfd)
        env_simulator._send_can_messages(msgs)
        time.sleep(1)
    else:
        service_14_check(node, expect_data=[0x54], expect_str="肯定响应(54)")

def operation_after_low_voltage():
    if P.ECUInfo.ECUName == "PICU":
        for i in range(10):
            time.sleep(10)
            ctx.bob_ctrl.set_power('KL15', False)
            time.sleep(10)
            ctx.bob_ctrl.set_power('KL15', True)

def hard_reset(node):
    is_canfd = P.ProjectInfo.ECUType == 2
    if P.ECUInfo.ECUName == "PICU":
        msgs = env_simulator._build_ept_ready_msg(env_simulator._EPT_READY_Unenable, is_canfd)
        env_simulator._send_can_messages(msgs)
        time.sleep(2)
        service_11_check(node, 0x01, expect_data=[0x51, 0x01], expect_str="肯定响应(51 01)")
        msgs = env_simulator._build_ept_ready_msg(env_simulator._EPT_READY_Enable, is_canfd)
        env_simulator._send_can_messages(msgs)
        time.sleep(1)
    else:
        service_11_check(node, 0x01, expect_data=[0x51, 0x01], expect_str="肯定响应(51 01)")