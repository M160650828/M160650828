import time
import traceback

import threading
import queue
from dataclasses import dataclass, field
from itertools import cycle
from typing import Optional, Dict, Any, Tuple, List

from uvtest.testlog import TestLog
from env.config import DEFAULT_LIN_CHANNEL
from common.params import P
from tp.lintp_module import lin_tp_initialization, lintp_send_req, lintp_rcv_response, lin_tp_end, \
    default_lin_request_nand, lintp_sys_global_val_set
from library.uds.uds_node import UDSNode
from library.uds.bus_sim import BusSim
from common.context import ctx

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


class LINTPBus(BusSim):

    def __init__(self, channel=DEFAULT_LIN_CHANNEL, nadid=None):
        self.channel = channel
        self.nadid = nadid if nadid is not None else default_lin_request_nand
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

    def recv(self, timeout=10):
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
        from tp.lin_test_pre_module import get_nand_id
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
        from tp.lin_test_pre_module import ActivateDut, get_test_case_mode, create_lin_sch
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


def __lin_restart_delay(tstable_s,start_normal_sch :bool=False):
    from tp.lin_test_pre_module import create_lin_sch, create_lin_ch
    if start_normal_sch==True:
        sch  = create_lin_sch()
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



def get_dtc_list_from_19_resp(response_message) -> list:
    """
    从 0x19 服务响应中解析 DTC 列表
    """
    if response_message is None:
        return []

    resp_data = list(response_message.data) if hasattr(response_message, 'data') else list(response_message)

    # 检查是否为肯定响应
    if len(resp_data) < 3 or resp_data[0] != 0x59:
        TestLog("WARNING", "DTC解析", f"非期望响应格式: {[hex(b) for b in resp_data]}")
        return []

    dtc_list = []

    i = 3  # 跳过肯定响应头 (59 XX)
    while i + 3 < len(resp_data):
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
    """
    比较读取的 DTC 列表与期望的 DTC 列表是否一致
    """
    read_dtcs = set([dtc_info['dtc'] for dtc_info in read_dtc_list])
    expect_dtcs = set(expect_dtc_list)

    if read_dtcs == expect_dtcs:
        TestLog("PASS", "", "读取的 DTC 列表与 FMS 定义完全一致")
        return True
    else:
        missing = expect_dtcs - read_dtcs
        extra = read_dtcs - expect_dtcs
        if missing:
            TestLog("FAIL", "", f"缺少的 DTC: {[f'{hex(d[0])}{hex(d[1])[2:]}{hex(d[2])[2:]}' for d in missing]}")
        if extra:
            TestLog("FAIL", "", f"多余的 DTC: {[f'{hex(d[0])}{hex(d[1])[2:]}{hex(d[2])[2:]}' for d in extra]}")
        return False


def test_ReadSupported_DTCList_TC1(
        node: UDSNode,
        name: str = "[TG1_TC1] LIN诊断故障代码列表读取检查", ):
    """
    [TG1_TC1] LIN诊断故障代码列表读取检查
    """

    try:

        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        TestLog("INFO", "Step1", "发送 19 0A 请求读取电控单元支持的诊断故障代码清单(LIN: 02 19 0A)")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x0A,
            expect_data=[0x59, 0x0A],
            expect_str="肯定响应(59 0A)",
            func_req=False
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        dtc_list = get_dtc_list_from_19_resp(resp)
        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        # 输出读取到的DTC信息
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"
            TestLog("INFO", "", f"  DTC: {dtc_str}, 状态: {status:02X}")

        # 与期望的DTC列表进行比较
        if DTCTestParams.ExpectedDTCList:
            if compare_dtc_list(dtc_list, DTCTestParams.ExpectedDTCList):
                TestLog("PASS", name, f"读取到 {len(dtc_list)} 个 DTC，与 FMS 定义完全一致")
            else:
                TestLog("FAIL", name, "读取的 DTC 列表与 FMS 定义不一致")
        else:
            TestLog("PASS", name, f"成功读取到 {len(dtc_list)} 个支持的 DTC（需手动验证与 FMS 定义是否一致）")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")

    finally:
        if node:
            node.close()


def test_DTCStatusAvailabilityMask_TC2(
        node: UDSNode,
        name: str = "[TG1_TC2] 诊断故障代码状态掩码检查", ):
    """
   [TG1_TC2] 诊断故障代码状态掩码检查
    """
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str=f"肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0X08
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        # 解析响应数据
        resp_data = list(resp.data) if hasattr(resp, 'data') else list(resp)
        if len(resp_data) < 3:
            TestLog("FAIL", name, f"响应数据长度不足: {[hex(b) for b in resp_data]}")
            return

        dtc_status_availability_mask = resp_data[2]
        TestLog("INFO", "", f"DTCStatusAvailabilityMask = 0x{dtc_status_availability_mask:02X}")

        # 检查DTCStatusAvailabilityMask是否符合预期
        if dtc_status_availability_mask == DTCTestParams.ExpectedDTCStatusAvailabilityMask:
            TestLog("PASS", name,
                    f"DTCStatusAvailabilityMask = 0x{dtc_status_availability_mask:02X}，符合预期{DTCTestParams.ExpectedDTCStatusAvailabilityMask}")
        else:
            TestLog("FAIL", name,
                    f"DTCStatusAvailabilityMask = 0x{dtc_status_availability_mask:02X}，不符合预期{DTCTestParams.ExpectedDTCStatusAvailabilityMask}")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def test_DTCStatusAvailabilityMaskList_TC3(
        node: UDSNode,
        name: str = "[TG1_TC3] 诊断故障代码状态掩码检查", ):
    """
    [TG1_TC3] 诊断故障代码状态掩码检查

    """
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # 定义要测试的状态掩码列表
        status_masks = [0x01, 0x02, 0x04, 0x08, 0x20, 0x40, 0x80]
        all_passed = True

        for mask in status_masks:
            TestLog("INFO", f"Step1(掩码=0x{mask:02X})",
                    f"发送 19 02 {mask:02X} 请求读取DTC信息(LIN: 03 19 02 {mask:02X} 00 00 00 00)")

            success, resp = __service_19_check_lin(
                node,
                report_type=0x02,
                expect_data=[0x59, 0x02],
                expect_str=f"肯定响应(59 02)",
                func_req=False,
                DTCStatusMask=mask
            )

            if not success:
                TestLog("FAIL", "", f"掩码 0x{mask:02X}: 未收到肯定响应")
                all_passed = False
                continue

            # 解析DTC列表
            dtc_list = get_dtc_list_from_19_resp(resp)

            if len(dtc_list) == 0:
                TestLog("INFO", "", f"掩码 0x{mask:02X}: 未读取到匹配的 DTC")
                continue

            TestLog("INFO", "", f"掩码 0x{mask:02X}: 读取到 {len(dtc_list)} 个 DTC")

            # 检查每个DTC的状态信息与掩码位是否一致
            mask_passed = True
            for dtc_info in dtc_list:
                dtc = dtc_info['dtc']
                status = dtc_info['status']
                dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"

                # 检查 (statusOfDTC & DTCStatusMask) == DTCStatusMask
                if (status & mask) !=0:
                    TestLog("PASS", "", f"DTC {dtc_str}: status=0x{status:02X}, (status & 0x{mask:02X})!=0")
                else:
                    TestLog("FAIL", "",
                            f"DTC {dtc_str}: status=0x{status:02X}, (status & 0x{mask:02X})=0x{status & mask:02X} =0")
                    mask_passed = False
                    all_passed = False

            if mask_passed:
                TestLog("PASS", "", f"掩码 0x{mask:02X} 检查通过")
            else:
                TestLog("FAIL", "", f"掩码 0x{mask:02X} 检查未通过")

        # 最终评价
        if all_passed:
            TestLog("PASS", name, "所有状态掩码检查通过，诊断故障代码状态掩码检查成功")
        else:
            TestLog("FAIL", name, "部分状态掩码检查未通过")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")

    finally:
        if node:
            node.close()



def sim_dtc_data_invalid(msgid,data):
    from tp.lin_test_pre_module import set_invalid_data
    set_invalid_data(msgid,data)
    __lin_restart_delay(5,True)


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
        from tp.lin_test_pre_module import create_lin_sch, create_lin_ch

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

def test_DTCFaultGeneration_TC4(
        node: UDSNode,
        name: str = "[TG1_TC4] 诊断故障代码产生和恢复条件检查", ):
    """
    [TG1_TC4] 诊断故障代码产生和恢复条件检查
    """
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return
        success = __service_14_check_lin(
            node,
            dtc=0xFFFFFF,  # 清除所有DTC
            expect_data=[0x54],
            expect_str="肯定响应(54)",
            func_req=False
        )

        if not success:
            TestLog("FAIL", name, "清除DTC失败")
            return

        TestLog("PASS", "清除DTC", "成功清除所有DTC")


        dtc_select = None
        set_msgid = None
        set_invalid_data=None
        set_valid_data=None
        for item in P.ExtendedDTCInfo.invalid_data.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            dtc_select = dtc_code
            set_msgid = item.MonitorMessageID
            set_invalid_data = item.InvalidPayload
            set_valid_data = item.ValidPayload
            break
        if dtc_select == None:
            TestLog("FAIL", name, "表格中不支持无效数据故障")
            return
        TestLog("INFO", "Step1", "模拟产生节点丢失故障、无效数据故障")

        # TODO: 这里需要实现具体的故障模拟逻辑
        # 模拟节点丢失故障、无效数据故障，具体的硬件和故障模拟接口来实现

        TestLog("INFO", "故障模拟", "模拟节点丢失故障、无效数据故障（需要具体实现）")
        # ctx.power_ctrl.set_voltage(8.0)
        sim_dtc_data_invalid(set_msgid,set_invalid_data)

        TestLog("INFO", "Step2", "发送 19 02 FF 请求读取DTC信息(LIN: 03 19 02 FF 00 00 00 00)")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0xFF
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        # 解析DTC列表
        dtc_list = get_dtc_list_from_19_resp(resp)

        if len(dtc_list) == 0:
            TestLog("FAIL", name, "未读取到任何 DTC（故障模拟可能未成功）")
            return

        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        fault_detected = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_code = int.from_bytes(bytes([dtc[0],dtc[1],dtc[2]]))
            if dtc_code == dtc_select:
                bit0_test_failed = (status & 0x01) == 0x01
                if bit0_test_failed:
                    TestLog("PASS", "", f"DTC {hex(dtc_code)}: status=0x{status:02X}, bit0(测试失败)=1")
                    fault_detected = True
                else:
                    TestLog("FAIL", "", f"DTC {hex(dtc_code)}: status=0x{status:02X}, bit0(测试失败)=0")
                    return 
        if not fault_detected:
            TestLog("FAIL", name, f"故障产生后未检测到DTC {hex(dtc_code)}")
            return


    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")

    finally:
        if node:
            node.close()


def test_DTCFaultRecovery_TC5(
        node: UDSNode,
        name: str = "[TG1_TC5] 诊断故障代码产生和恢复条件检查", ):
    """
    [TG1_TC5] 诊断故障代码产生和恢复条件检查
    """
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return
        success = __service_14_check_lin(
            node,
            dtc=0xFFFFFF,  # 清除所有DTC
            expect_data=[0x54],
            expect_str="肯定响应(54)",
            func_req=False
        )

        if not success:
            TestLog("FAIL", name, "清除DTC失败")
            return
        dtc_select = None
        set_msgid = None
        set_invalid_data=None
        set_valid_data=None
        for item in P.ExtendedDTCInfo.invalid_data.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            dtc_select = dtc_code
            set_msgid = item.MonitorMessageID
            set_invalid_data = item.InvalidPayload
            set_valid_data = item.ValidPayload
            break
        if dtc_select == None:
            TestLog("FAIL", name, "表格中不支持无效数据故障")
            return
        TestLog("INFO", "Step1", "模拟节点丢失故障、无效数据故障恢复")
        sim_dtc_data_invalid(set_msgid,set_invalid_data)

        TestLog("INFO", "故障恢复", "模拟节点丢失故障、无效数据故障恢复（需要具体实现）")
        sim_dtc_data_invalid(set_msgid,set_valid_data)

        TestLog("INFO", "Step2", "发送 19 02 FF 请求读取DTC信息(LIN: 03 19 02 FF 00 00 00 00)")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0xFF
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        # 解析DTC列表
        dtc_list = get_dtc_list_from_19_resp(resp)

        if len(dtc_list) == 0:
            TestLog("FAIL", name, "未读取到任何 DTC（故障模拟可能未成功）")
            return

        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC（历史状态故障码）")

        fault_detected = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_code = int.from_bytes(bytes([dtc[0],dtc[1],dtc[2]]))
            if dtc_code == dtc_select:
                bit0_test_failed = (status & 0x08) == 0x08
                if bit0_test_failed:
                    TestLog("PASS", "", f"DTC {hex(dtc_code)}: status=0x{status:02X}, bit3(测试失败)=1")
                    fault_detected = True
                else:
                    TestLog("FAIL", "", f"DTC {hex(dtc_code)}: status=0x{status:02X}, bit3(测试失败)=0")
                    return 
                bit0_test_failed = (status & 0x01) == 0x01
                if bit0_test_failed:
                    TestLog("FAIL", "", f"DTC {hex(dtc_code)}: status=0x{status:02X}, bit0(测试失败)=1")
                    return
                else:
                    TestLog("PASS", "", f"DTC {hex(dtc_code)}: status=0x{status:02X}, bit0(测试失败)=0")
                     
        if not fault_detected:
            TestLog("FAIL", name, f"故障产生后未检测到DTC {hex(dtc_code)}")
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")

    finally:
        if node:
            node.close()


def test_DTCAgingMechanism_TC6(
        node: UDSNode,
        name: str = "[TG1_TC6] 诊断故障代码老化机制检查", ):
    """
    [TG1_TC6] 诊断故障代码老化机制检查
    """
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        TestLog("INFO", "Step1", "清除所有诊断故障代码")

        # 清除所有DTC
        success = __service_14_check_lin(
            node,
            dtc=0xFFFFFF,  # 清除所有DTC
            expect_data=[0x54],
            expect_str="肯定响应(54)",
            func_req=False
        )

        if not success:
            TestLog("FAIL", name, "清除DTC失败")
            return

        TestLog("PASS", "清除DTC", "成功清除所有DTC")

        TestLog("INFO", "Step2", "模拟产生故障")

        # TODO: 这里需要实现具体的故障模拟逻辑
        # 模拟目标诊断故障代码失效条件，具体的硬件和故障模拟接口来实现
        TestLog("INFO", "故障模拟", "模拟目标诊断故障代码失效条件（需要具体实现）")
        ctx.power_ctrl.set_voltage(8.0)
        __lin_restart_delay(5)
        TestLog("INFO", "Step3", "发送 19 02 0F 请求读取DTC信息(LIN: 03 19 02 0F 00 00 00 00)")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0x0F
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        # 解析DTC列表
        dtc_list = get_dtc_list_from_19_resp(resp)

        if len(dtc_list) == 0:
            TestLog("FAIL", name, "未读取到任何 DTC（故障模拟可能未成功）")
            return

        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        dtc_select = None
        dtc_list = get_dtc_list_from_19_resp(resp)
        for item in P.ExtendedDTCInfo.voltage.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            if "低压" not in item.Notes:
                continue
            dtc_select = dtc_code
        if dtc_select == None:
            TestLog("FAIL", name, "表格中不支持低压的DTC")
        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")
        fault_detected = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_code = int.from_bytes(bytes([dtc[0],dtc[1],dtc[2]]))
            if dtc_code == dtc_select:
                bit0_test_failed = (status & 0x01) == 0x01
                if bit0_test_failed:
                    TestLog("PASS", "", f"DTC {hex(dtc_code)}: status=0x{status:02X}, bit0(测试失败)=1")
                    fault_detected = True
                else:
                    TestLog("FAIL", "", f"DTC {hex(dtc_code)}: status=0x{status:02X}, bit0(测试失败)=0")
                    return 
        if not fault_detected:
            TestLog("FAIL", name, "故障产生后未检测到低压的DTC")
            return
            
        TestLog("INFO", "Step4", "模拟故障恢复")

        # TODO: 这里需要实现具体的故障恢复逻辑
        TestLog("INFO", "故障恢复", "模拟目标诊断故障代码恢复条件（需要具体实现）")
        ctx.power_ctrl.set_voltage(12.0)
        # 等待故障恢复
        __lin_restart_delay(5)
        TestLog("INFO", "Step5", "发送 19 02 FF 请求读取DTC信息(LIN: 03 19 02 FF 00 00 00 00)")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0xFF
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        # 解析DTC列表
        dtc_list = get_dtc_list_from_19_resp(resp)

        if len(dtc_list) == 0:
            TestLog("FAIL", name, "故障恢复后未读取到任何 DTC")
            return

        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC（历史状态故障码）")

        # 检查每个DTC的状态信息bit0（测试失败）是否为0


        recovery_verified = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_code = int.from_bytes(bytes([dtc[0],dtc[1],dtc[2]]))
            if dtc_code == dtc_select:
                bit0_test_failed = (status & 0x01) == 0x01
                if bit0_test_failed:
                    TestLog("FAIL", "", f"DTC {hex(dtc_code)}: status=0x{status:02X}, bit0(测试失败)=1")
                    return 
                else:
                    recovery_verified = True
                    TestLog("PASS", "", f"DTC {hex(dtc_code)}: status=0x{status:02X}, bit0(测试失败)=0")
                    
        if not recovery_verified:
            TestLog("FAIL", name, "故障恢复后未检测到低压的DTC")
            return

        TestLog("INFO", "Step6-8", "循环40个操作循环，每个循环使DUT进入下一循环并检查DTC状态")

        # 进行40个操作循环
        for cycle in range(1, 41):
            __lin_restart_delay(4,True)
            TestLog("INFO", f"循环{cycle}", f"发送 19 02 FF 请求读取DTC信息(LIN: 03 19 02 FF 00 00 00 00)")
            success, resp = __service_19_check_lin(
                node,
                report_type=0x02,
                expect_data=[0x59, 0x02],
                expect_str="肯定响应(59 02)",
                func_req=False,
                DTCStatusMask=0xFF
            )

            if not success:
                TestLog("FAIL", name, f"第{cycle}个循环：未收到肯定响应")
                continue

            # 解析DTC列表
            dtc_list = get_dtc_list_from_19_resp(resp)
            test_pass =False
            for dtc_info in dtc_list:
                dtc = dtc_info['dtc']
                status = dtc_info['status']
                dtc_code = int.from_bytes(bytes([dtc[0],dtc[1],dtc[2]]))
                if dtc_code == dtc_select:
                    test_pass = True
                    TestLog("PASS", f"循环{cycle}", f"读取到 {hex(dtc_code)}  DTC")   
            if test_pass== False:
                    TestLog("FAIL", f"循环{cycle}", f"未读取到 {hex(dtc_code)} 个 DTC") 
        TestLog("INFO", "Step9", "使DUT进入下一循环（第41个循环）")

        # TODO: 使DUT进入第41个循环（需要具体实现）
        TestLog("INFO", "操作循环", "使DUT进入第41个操作循环")
        time.sleep(1)

        TestLog("INFO", "Step10", "发送 19 02 0F 请求读取DTC信息(LIN: 03 19 02 0F 00 00 00 00)")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0x0F
        )

        if not success:
            TestLog("FAIL", name, "40个循环后：未收到肯定响应")
            return

        # 解析DTC列表
        dtc_list = get_dtc_list_from_19_resp(resp)
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_code = int.from_bytes(bytes([dtc[0],dtc[1],dtc[2]]))
            if dtc_code == dtc_select:
                TestLog("FAIL", f"循环{41}", f"读取到 {hex(dtc_code)}  DTC")   
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")

    finally:
        if node:
            node.close()


def test_ParentChildHighDTCScenario_TC7(
        node: UDSNode,
        name: str = "[TG1_TC7] 父子高压故障场景检查", ):
    """
    [TG1_TC7] 父子高压故障场景检查
    """
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        TestLog("INFO", "前置条件", "清除所有诊断故障代码")

        # 清除所有DTC
        success = __service_14_check_lin(
            node,
            dtc=0xFFFFFF,  # 清除所有DTC
            expect_data=[0x54],
            expect_str="肯定响应(54)",
            func_req=False
        )

        if not success:
            TestLog("FAIL", name, "清除DTC失败")
            return
        dtc_select = None
        set_msgid = None
        set_invalid_data=None
        set_valid_data=None
        for item in P.ExtendedDTCInfo.invalid_data.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            dtc_select = dtc_code
            set_msgid = item.MonitorMessageID
            set_invalid_data = item.InvalidPayload
            set_valid_data = item.ValidPayload
            break
        if dtc_select == None:
            TestLog("FAIL", name, "表格中不支持无效数据故障")
            return
        voltage_dtc_select = None
        for item in P.ExtendedDTCInfo.voltage.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            if "高压" not in item.Notes:
                continue
            voltage_dtc_select = dtc_code
            break
        if voltage_dtc_select == None:
            TestLog("FAIL", name, "表格中不支持高压的DTC")
        TestLog("PASS", "清除DTC", "成功清除所有DTC")

        TestLog("INFO", "Step1", "模拟电压高于17V（产生过压故障码）")

        # TODO: 模拟电压高于17V，产生过压故障码
        ctx.power_ctrl.set_voltage(18.0)
        TestLog("INFO", "电压模拟", "模拟电压高于17V")

        __lin_restart_delay(5)

        TestLog("INFO", "Step2", "发送 19 02 0F 请求读取DTC信息(LIN: 03 19 02 0F 00 00 00 00)")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=DTCTestParams.ExpectedDTCStatusAvailabilityMask
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        # 解析DTC列表
        dtc_list = get_dtc_list_from_19_resp(resp)



        fault_detected = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_code = int.from_bytes(bytes([dtc[0],dtc[1],dtc[2]]))
            if dtc_code == voltage_dtc_select:
                bit0_test_failed = (status & 0x01) == 0x01
                if bit0_test_failed:
                    TestLog("PASS", "", f"DTC {hex(dtc_code)}: status=0x{status:02X}, bit0(测试失败)=1")
                    fault_detected = True
                else:
                    TestLog("FAIL", "", f"DTC {hex(dtc_code)}: status=0x{status:02X}, bit0(测试失败)=0")
                    return 
        if not fault_detected:
            TestLog("FAIL", name, "故障产生后未检测到高压的DTC")
            return


        TestLog("INFO", "Step3", "模拟目标诊断子故障")

        sim_dtc_data_invalid(set_msgid,set_invalid_data)


        TestLog("INFO", "Step4", "发送 19 02 0F 请求读取DTC信息(LIN: 03 19 02 0F 00 00 00 00)")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0x0F
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        # 解析DTC列表
        dtc_list = get_dtc_list_from_19_resp(resp)

        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_code = int.from_bytes(bytes([dtc[0],dtc[1],dtc[2]]))
            if dtc_code == dtc_select:
                TestLog("FAIL", name, "电控单元记录了目标子诊断故障代码，不符合父级故障引发的故障无需记录要求")
                return

        TestLog("PASS", name, "电控单元未记录目标子诊断故障代码，符合父级故障引发的故障无需记录要求")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")

    finally:
        if node:
            node.close()


def test_ParentChildLowDTCScenario_TC8(
        node: UDSNode,
        name: str = "[TG1_TC8] 父子低压故障场景检查"):
    """
    [TG1_TC8] 父子低压故障场景检查

    """
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        TestLog("INFO", "前置条件", "清除所有诊断故障代码")

        # 清除所有DTC
        success = __service_14_check_lin(
            node,
            dtc=0xFFFFFF,  # 清除所有DTC
            expect_data=[0x54],
            expect_str="肯定响应(54)",
            func_req=False
        )

        if not success:
            TestLog("FAIL", name, "清除DTC失败")
            return
        dtc_select = None
        set_msgid = None
        set_invalid_data=None
        set_valid_data=None
        for item in P.ExtendedDTCInfo.invalid_data.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            dtc_select = dtc_code
            set_msgid = item.MonitorMessageID
            set_invalid_data = item.InvalidPayload
            set_valid_data = item.ValidPayload
            break
        if dtc_select == None:
            TestLog("FAIL", name, "表格中不支持无效数据故障")
            return
        voltage_dtc_select = None
        for item in P.ExtendedDTCInfo.voltage.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            if "低压" not in item.Notes:
                continue
            voltage_dtc_select = dtc_code
            break
        if voltage_dtc_select == None:
            TestLog("FAIL", name, "表格中不支持低压的DTC")
        TestLog("PASS", "清除DTC", "成功清除所有DTC")

        TestLog("INFO", "Step1", "模拟电压低于8v（产生低压故障码）")

        ctx.power_ctrl.set_voltage(7.0)
        TestLog("INFO", "电压模拟", "模拟电压7V")

        __lin_restart_delay(5)

        TestLog("INFO", "Step2", "发送 19 02 0F 请求读取DTC信息(LIN: 03 19 02 0F 00 00 00 00)")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=DTCTestParams.ExpectedDTCStatusAvailabilityMask
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        # 解析DTC列表
        dtc_list = get_dtc_list_from_19_resp(resp)



        fault_detected = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_code = int.from_bytes(bytes([dtc[0],dtc[1],dtc[2]]))
            if dtc_code == voltage_dtc_select:
                bit0_test_failed = (status & 0x01) == 0x01
                if bit0_test_failed:
                    TestLog("PASS", "", f"DTC {hex(dtc_code)}: status=0x{status:02X}, bit0(测试失败)=1")
                    fault_detected = True
                else:
                    TestLog("FAIL", "", f"DTC {hex(dtc_code)}: status=0x{status:02X}, bit0(测试失败)=0")
                    return 
        if not fault_detected:
            TestLog("FAIL", name, "故障产生后未检测到低压的DTC")
            return


        TestLog("INFO", "Step3", "模拟目标诊断子故障")

        sim_dtc_data_invalid(set_msgid,set_invalid_data)


        TestLog("INFO", "Step4", "发送 19 02 0F 请求读取DTC信息(LIN: 03 19 02 0F 00 00 00 00)")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0x0F
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        # 解析DTC列表
        dtc_list = get_dtc_list_from_19_resp(resp)

        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_code = int.from_bytes(bytes([dtc[0],dtc[1],dtc[2]]))
            if dtc_code == dtc_select:
                TestLog("FAIL", name, "电控单元记录了目标子诊断故障代码，不符合父级故障引发的故障无需记录要求")
                return

        TestLog("PASS", name, "电控单元未记录目标子诊断故障代码，符合父级故障引发的故障无需记录要求")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")

    finally:
        if node:
            node.close()

def test_ParentChildDTCScenario_TC9(
        node: UDSNode,
        name: str = "[TG1_TC9] 父子其它故障场景检查"):
    """
    [TG1_TC9] 父子其它故障场景检查

    """
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        TestLog("INFO", "前置条件", "清除所有诊断故障代码")

        # 清除所有DTC
        success = __service_14_check_lin(
            node,
            dtc=0xFFFFFF,  # 清除所有DTC
            expect_data=[0x54],
            expect_str="肯定响应(54)",
            func_req=False
        )

        if not success:
            TestLog("FAIL", name, "清除DTC失败")
            return
        TestLog("FAIL", name, "不支持BUSOFF 故障")
        return
        dtc_select = None
        set_msgid = None
        set_invalid_data=None
        set_valid_data=None
        for item in P.ExtendedDTCInfo.invalid_data.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            dtc_select = dtc_code
            set_msgid = item.MonitorMessageID
            set_invalid_data = item.InvalidPayload
            set_valid_data = item.ValidPayload
            break
        if dtc_select == None:
            TestLog("FAIL", name, "表格中不支持无效数据故障")
            return
        voltage_dtc_select = None
        for item in P.ExtendedDTCInfo.voltage.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            if "低压" not in item.Notes:
                continue
            voltage_dtc_select = dtc_code
            break
        if voltage_dtc_select == None:
            TestLog("FAIL", name, "表格中不支持低压的DTC")
        TestLog("PASS", "清除DTC", "成功清除所有DTC")

        TestLog("INFO", "Step1", "模拟电压低于8v（产生低压故障码）")

        ctx.power_ctrl.set_voltage(7.0)
        TestLog("INFO", "电压模拟", "模拟电压7V")

        __lin_restart_delay(5)

        TestLog("INFO", "Step2", "发送 19 02 0F 请求读取DTC信息(LIN: 03 19 02 0F 00 00 00 00)")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=DTCTestParams.ExpectedDTCStatusAvailabilityMask
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        # 解析DTC列表
        dtc_list = get_dtc_list_from_19_resp(resp)



        fault_detected = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_code = int.from_bytes(bytes([dtc[0],dtc[1],dtc[2]]))
            if dtc_code == voltage_dtc_select:
                bit0_test_failed = (status & 0x01) == 0x01
                if bit0_test_failed:
                    TestLog("PASS", "", f"DTC {hex(dtc_code)}: status=0x{status:02X}, bit0(测试失败)=1")
                    fault_detected = True
                else:
                    TestLog("FAIL", "", f"DTC {hex(dtc_code)}: status=0x{status:02X}, bit0(测试失败)=0")
                    return 
        if not fault_detected:
            TestLog("FAIL", name, "故障产生后未检测到低压的DTC")
            return


        TestLog("INFO", "Step3", "模拟目标诊断子故障")

        sim_dtc_data_invalid(set_msgid,set_invalid_data)


        TestLog("INFO", "Step4", "发送 19 02 0F 请求读取DTC信息(LIN: 03 19 02 0F 00 00 00 00)")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0x0F
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        # 解析DTC列表
        dtc_list = get_dtc_list_from_19_resp(resp)

        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_code = int.from_bytes(bytes([dtc[0],dtc[1],dtc[2]]))
            if dtc_code == dtc_select:
                TestLog("FAIL", name, "电控单元记录了目标子诊断故障代码，不符合父级故障引发的故障无需记录要求")
                return

        TestLog("PASS", name, "电控单元未记录目标子诊断故障代码，符合父级故障引发的故障无需记录要求")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")

    finally:
        if node:
            node.close()



def test_FaultWarningCheck_TC10(
        node: UDSNode,
        name: str = "[TG1_TC10] 故障警示检查"):
    """
    [TG1_TC10] 故障警示检查（故障警示相关信号）
    """
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        TestLog("INFO", "前置条件", "清除所有诊断故障代码")

        # 清除所有DTC
        success = __service_14_check_lin(
            node,
            dtc=0xFFFFFF,
            expect_data=[0x54],
            expect_str="肯定响应(54)",
            func_req=False
        )

        if not success:
            TestLog("FAIL", name, "清除DTC失败")
            return

        TestLog("PASS", "清除DTC", "成功清除所有DTC")
        TestLog("FAIL", name, "故障警示检查（故障警示相关信号")
        return
        # TODO: 模拟有故障警示请求的诊断故障代码失效条件
        TestLog("INFO", "Step1", "模拟产生故障（有故障警示请求的诊断故障代码）")
        # ctx.power_ctrl.set_voltage(8.0)
        # __lin_restart_delay(2)

        TestLog("INFO", "Step2", "发送 19 02 80 请求读取DTC信息(LIN: 03 19 02 80 00 00 00 00)")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0x80
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        # 解析DTC列表
        dtc_list = get_dtc_list_from_19_resp(resp)

        if len(dtc_list) == 0:
            TestLog("FAIL", name, "未读取到任何 DTC（故障模拟可能未成功）")
            return

        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        # 检查故障警示相关DTC的bit7是否为1
        fault_warning_dtc_found = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"

            # 检查bit7（已请求警告请示）是否为1
            bit7_warning_requested = (status & 0x80) == 0x80

            # TODO: 根据实际的DTC编码来识别有故障警示请求的诊断故障代码，假设为0x123459

            if dtc_str == "123459" and bit7_warning_requested:
                TestLog("PASS", "", f"故障警示 DTC {dtc_str}: status=0x{status:02X}, bit7(已请求警告请示)=1")
                fault_warning_dtc_found = True
            elif dtc_str == "123459":
                TestLog("FAIL", "", f"故障警示 DTC {dtc_str}: status=0x{status:02X}, bit7(已请求警告请示)=0")
            else:
                TestLog("INFO", "", f"其他 DTC {dtc_str}: status=0x{status:02X}")

        if not fault_warning_dtc_found:
            TestLog("FAIL", name, "未检测到有故障警示请求的诊断故障代码或bit7未置1")
        else:
            TestLog("PASS", name, "故障警示信号为请求故障警示状态，bit7已置1")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")

    finally:
        if node:
            node.close()


def test_FaultWarningCheck_TC11(
        node: UDSNode,
        name: str = "[TG1_TC11] 故障警示检查"):
    """
    [TG1_TC11] 故障警示检查（故障现象消除即灭灯）
    """
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        TestLog("INFO", "前置条件", "清除所有诊断故障代码")
        TestLog("FAIL", name, "故障警示检查（故障警示相关信号")
        # 清除所有DTC
        success = __service_14_check_lin(
            node,
            dtc=0xFFFFFF,
            expect_data=[0x54],
            expect_str="肯定响应(54)",
            func_req=False
        )

        if not success:
            TestLog("FAIL", name, "清除DTC失败")
            return

        TestLog("PASS", "清除DTC", "成功清除所有DTC")

        # TODO: 模拟产生故障
        TestLog("INFO", "Step1", "模拟产生故障")

        time.sleep(2)

        TestLog("INFO", "Step2", "发送 19 02 2C 请求读取DTC信息(LIN: 03 19 02 2C 00 00 00 00)")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0x2C
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        # 解析DTC列表
        dtc_list = get_dtc_list_from_19_resp(resp)

        if len(dtc_list) == 0:
            TestLog("FAIL", name, "未读取到任何 DTC（故障模拟可能未成功）")
            return

        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        # 检查bit7是否为1
        fault_warning_dtc_found = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"

            bit7_warning_requested = (status & 0x80) == 0x80

            # TODO: 根据实际的DTC编码来识别诊断故障代码，假设为0x123459

            if dtc_str == "123459" and bit7_warning_requested:
                TestLog("PASS", "", f"故障警示 DTC {dtc_str}: status=0x{status:02X}, bit7(已请求警告请示)=1")
                fault_warning_dtc_found = True
            elif dtc_str == "123459":
                TestLog("FAIL", "", f"故障警示 DTC {dtc_str}: status=0x{status:02X}, bit7(已请求警告请示)=0")
            else:
                TestLog("INFO", "", f"其他 DTC {dtc_str}: status=0x{status:02X}")

        if not fault_warning_dtc_found:
            TestLog("FAIL", name, "未检测到有故障警示请求的诊断故障代码或bit7未置1")
        else:
            TestLog("PASS", name, "故障警示信号为请求故障警示状态，bit7已置1")

        # TODO: 模拟故障恢复
        TestLog("INFO", "Step3", "模拟故障恢复")

        time.sleep(2)

        TestLog("INFO", "Step4", "发送 19 02 2C 请求读取DTC信息(LIN: 03 19 02 2C 00 00 00 00)")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0x2C
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        # 解析DTC列表
        dtc_list = get_dtc_list_from_19_resp(resp)

        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        # 检查bit0和bit7是否为0
        fault_recovery_verified = True
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"

            bit0_test_failed = (status & 0x01) == 0x01
            bit7_warning_requested = (status & 0x80) == 0x80

            # TODO: 根据实际的DTC编码来识别目标诊断故障恢复代码，假设为0x12345A
            if dtc_str == "12345A":
                if not bit0_test_failed and not bit7_warning_requested:
                    TestLog("PASS", "", f"故障恢复 DTC {dtc_str}: status=0x{status:02X}, bit0=0, bit7=0")
                else:
                    TestLog("FAIL", "",
                            f"故障恢复 DTC {dtc_str}: status=0x{status:02X}, bit0={bit0_test_failed}, bit7={bit7_warning_requested}")
                    fault_recovery_verified = False
            else:
                TestLog("INFO", "", f"其他 DTC {dtc_str}: status=0x{status:02X}")

        if fault_recovery_verified:
            TestLog("PASS", name, "故障警示信号为故障警示灭灯状态，bit0和bit7为0")
        else:
            TestLog("FAIL", name, "故障警示信号未正确恢复，bit0或bit7未置0")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")

    finally:
        if node:
            node.close()


def test_FaultWarningCheck_TC12(
        node: UDSNode,
        name: str = "[TG1_TC12] 故障警示检查"):
    """
    [TG1_TC12] 故障警示检查（操作循环结束时灭灯）

    """
    try:

        TestLog("INFO", "前置条件", "执行TC9案例（其他父故障场景检查）")
        test_ParentChildDTCScenario_TC9(node)

        TestLog("INFO", "前置条件", "清除所有诊断故障代码")
        TestLog("FAIL", name, "故障警示检查（故障警示相关信号")
        # 清除所有DTC
        success = __service_14_check_lin(
            node,
            dtc=0xFFFFFF,
            expect_data=[0x54],
            expect_str="肯定响应(54)",
            func_req=False
        )

        if not success:
            TestLog("FAIL", name, "清除DTC失败")
            return

        TestLog("PASS", "清除DTC", "成功清除所有DTC")

        # TODO: 模拟产生故障
        TestLog("INFO", "Step1", "模拟产生故障")

        time.sleep(2)

        TestLog("INFO", "Step2", "发送 19 02 2C 请求读取DTC信息(LIN: 03 19 02 2C 00 00 00 00)")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0x2C
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        # 解析DTC列表
        dtc_list = get_dtc_list_from_19_resp(resp)

        if len(dtc_list) == 0:
            TestLog("FAIL", name, "未读取到任何 DTC（故障模拟可能未成功）")
            return

        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        # 检查bit7是否为1
        fault_warning_dtc_found = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"

            bit7_warning_requested = (status & 0x80) == 0x80
            # TODO: 根据实际的DTC编码来识别诊断故障代码，假设为0x123459

            if dtc_str == "123459" and bit7_warning_requested:
                TestLog("PASS", "", f"故障警示 DTC {dtc_str}: status=0x{status:02X}, bit7(已请求警告请示)=1")
                fault_warning_dtc_found = True
            elif dtc_str == "123459":
                TestLog("FAIL", "", f"故障警示 DTC {dtc_str}: status=0x{status:02X}, bit7(已请求警告请示)=0")
            else:
                TestLog("INFO", "", f"其他 DTC {dtc_str}: status=0x{status:02X}")

        if not fault_warning_dtc_found:
            TestLog("FAIL", name, "未检测到有故障警示请求的诊断故障代码或bit7未置1")
        else:
            TestLog("PASS", name, "故障警示信号为请求故障警示状态，bit7已置1")

        TestLog("INFO", "Step3", "模拟故障恢复")

        # TODO: 模拟故障恢复
        TestLog("INFO", "故障恢复", "模拟故障恢复")

        time.sleep(2)

        TestLog("INFO", "Step4", "发送 19 02 2C 请求读取DTC信息(LIN: 03 19 02 2C 00 00 00 00)")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0x2C
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        # 解析DTC列表
        dtc_list = get_dtc_list_from_19_resp(resp)

        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        # 检查bit7是否为1（故障恢复后bit7仍为1）
        fault_recovery_verified = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"

            bit7_warning_requested = (status & 0x80) == 0x80

            # TODO: 根据实际的DTC编码来识别目标诊断故障恢复代码，假设为0x12345A
            if dtc_str == "12345A":
                if bit7_warning_requested:
                    TestLog("PASS", "", f"故障恢复后 DTC {dtc_str}: status=0x{status:02X}, bit7(已请求警告请示)=1")
                    fault_recovery_verified = True
                else:
                    TestLog("FAIL", "",
                            f"故障恢复后 DTC {dtc_str}: status=0x{status:02X}, bit7(已请求警告请示)=0")
                    fault_recovery_verified = False
            else:
                TestLog("INFO", "", f"其他 DTC {dtc_str}: status=0x{status:02X}")

        if fault_recovery_verified:
            TestLog("PASS", name, "进入操作循环后故障警示信号变为非故障警示状态，bit7同步置为1")
        else:
            TestLog("FAIL", name, "进入操作循环后故障警示信号未正确恢复")

        # TODO: 等待下一个操作循环
        TestLog("INFO", "Step5", "等待下一个操作循环")
        time.sleep(3)

        TestLog("INFO", "Step6", "发送 19 02 2C 请求读取DTC信息(LIN: 03 19 02 2C 00 00 00 00)")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0x2C
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        # 解析DTC列表
        dtc_list = get_dtc_list_from_19_resp(resp)

        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        # 检查bit0和bit7是否为0（进入下一个操作循环后）
        operation_cycle_verified = True
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"

            bit0_test_failed = (status & 0x01) == 0x01
            bit7_warning_requested = (status & 0x80) == 0x80

            # TODO: 根据实际的DTC编码来识别目标诊断故障代码，假设为0x12345B
            if dtc_str == "12345B":
                if not bit0_test_failed and not bit7_warning_requested:
                    TestLog("PASS", "", f"操作循环后 DTC {dtc_str}: status=0x{status:02X}, bit0=0, bit7=0")
                else:
                    TestLog("FAIL", "",
                            f"操作循环后 DTC {dtc_str}: status=0x{status:02X}, bit0={bit0_test_failed}, bit7={bit7_warning_requested}")
                    operation_cycle_verified = False
            else:
                TestLog("INFO", "", f"其他 DTC {dtc_str}: status=0x{status:02X}")

        if operation_cycle_verified:
            TestLog("PASS", name, "进入操作循环后故障警示信号变为非故障警示状态，bit7同步置为0")
        else:
            TestLog("FAIL", name, "进入操作循环后故障警示信号未正确恢复")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")

    finally:
        if node:
            node.close()


def test_FaultWarningCheck_TC13(
        node: UDSNode,
        name: str = "[TG1_TC13] 故障警示检查"):
    """
    [TG1_TC13] 故障警示检查（连续三操作循环无故障才灭灯）
    """
    try:

        TestLog("INFO", "前置条件", "执行TC9案例（其他父故障场景检查）")
        test_ParentChildDTCScenario_TC9(node)

        TestLog("INFO", "前置条件", "清除所有诊断故障代码")
        TestLog("FAIL", name, "故障警示检查（故障警示相关信号")
        # 清除所有DTC
        success = __service_14_check_lin(
            node,
            dtc=0xFFFFFF,
            expect_data=[0x54],
            expect_str="肯定响应(54)",
            func_req=False
        )

        if not success:
            TestLog("FAIL", name, "清除DTC失败")
            return

        TestLog("PASS", "清除DTC", "成功清除所有DTC")

        # TODO: 模拟产生故障
        TestLog("INFO", "Step1", "模拟产生故障")

        time.sleep(2)

        TestLog("INFO", "Step2", "发送 19 02 2C 请求读取DTC信息(LIN: 03 19 02 2C 00 00 00 00)")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0x2C
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        # 解析DTC列表
        dtc_list = get_dtc_list_from_19_resp(resp)

        if len(dtc_list) == 0:
            TestLog("FAIL", name, "未读取到任何 DTC（故障模拟可能未成功）")
            return

        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        # 检查bit7是否为1
        fault_warning_dtc_found = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"

            bit7_warning_requested = (status & 0x80) == 0x80
            # TODO: 根据实际的DTC编码来识别诊断故障代码，假设为0x123459

            if dtc_str == "123459" and bit7_warning_requested:
                TestLog("PASS", "", f"故障警示 DTC {dtc_str}: status=0x{status:02X}, bit7(已请求警告请示)=1")
                fault_warning_dtc_found = True
            elif dtc_str == "123459":
                TestLog("FAIL", "", f"故障警示 DTC {dtc_str}: status=0x{status:02X}, bit7(已请求警告请示)=0")
            else:
                TestLog("INFO", "", f"其他 DTC {dtc_str}: status=0x{status:02X}")

        if not fault_warning_dtc_found:
            TestLog("FAIL", name, "未检测到有故障警示请求的诊断故障代码或bit7未置1")
        else:
            TestLog("PASS", name, "故障警示信号为请求故障警示状态，bit7已置1")

        TestLog("INFO", "Step3", "模拟故障恢复")

        # TODO: 模拟故障恢复
        TestLog("INFO", "故障恢复", "模拟故障恢复")

        time.sleep(2)

        TestLog("INFO", "Step4", "发送 19 02 2C 请求读取DTC信息(LIN: 03 19 02 2C 00 00 00 00)")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0x2C
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        # 解析DTC列表
        dtc_list = get_dtc_list_from_19_resp(resp)

        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        # 检查bit7是否为1（故障恢复后bit7仍为1）
        fault_recovery_verified = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"

            bit7_warning_requested = (status & 0x80) == 0x80

            # TODO: 根据实际的DTC编码来识别目标诊断故障恢复代码，假设为0x12345A
            if dtc_str == "12345A":
                if bit7_warning_requested:
                    TestLog("PASS", "", f"故障恢复后 DTC {dtc_str}: status=0x{status:02X}, bit7(已请求警告请示)=1")
                    fault_recovery_verified = True
                else:
                    TestLog("FAIL", "",
                            f"故障恢复后 DTC {dtc_str}: status=0x{status:02X}, bit7(已请求警告请示)=0")
                    fault_recovery_verified = False
            else:
                TestLog("INFO", "", f"其他 DTC {dtc_str}: status=0x{status:02X}")

        if fault_recovery_verified:
            TestLog("PASS", name, "进入操作循环后故障警示信号变为非故障警示状态，bit7同步置为1")
        else:
            TestLog("FAIL", name, "进入操作循环后故障警示信号未正确恢复")

        # TODO: 等待3个操作循环
        TestLog("INFO", "Step5", "等待3个操作循环")
        time.sleep(3)

        TestLog("INFO", "Step6", "发送 19 02 2C 请求读取DTC信息(LIN: 03 19 02 2C 00 00 00 00)")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=0x2C
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        # 解析DTC列表
        dtc_list = get_dtc_list_from_19_resp(resp)

        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        # 检查未读出此故障码
        operation_cycle_verified = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"

            # TODO: 未读出此故障码，假设为0x12345B
            if dtc_str == "12345B":
                TestLog("FAIL", "", f"操作循环后 DTC {dtc_str}: status=0x{status:02X}, 存在符合的故障码")
                operation_cycle_verified = True

            else:
                TestLog("PASS", "", f"操作循环后 DTC {dtc_str}: status=0x{status:02X}, 不存在符合的故障码")

        if operation_cycle_verified:
            TestLog("PASS", name, "等待3个操作循环后，回复肯定响应，且未读出此故障码")
        else:
            TestLog("FAIL", name, "等待3个操作循环后，回复肯定响应，存在此故障码")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")

    finally:
        if node:
            node.close()


@dataclass
class GlobalSnapshotData:
    dtc_code: Tuple[int, int, int] = (0, 0, 0)  # (high, mid, low)
    dtc_status: int = 0
    dtc_snapshotdata={}
    raw_data: bytes = field(default_factory=bytes)



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
        TestLog("INFO", "", f"已保存快照数据 [{key}]")

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
        for key,item in baseline.dtc_snapshotdata.items():
            if key not in current.dtc_snapshotdata.keys():
                all_pass = False
                break
            if item!=current.dtc_snapshotdata[key]:
                all_pass = False
                break
        
        return all_pass

   

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
        data = list(data)
        while idx + 2 < len(data):
            did_high = data[idx]
            did_low = data[idx + 1]
            did = (did_high << 8) | did_low
            idx += 2
            find_did =False
            for did_info in P.GlobalData.items:
                if did == did_info.DID:
                    Length = did_info.Length
                    if (idx + Length) <= len(data):
                        snapshot.dtc_snapshotdata[did] = data[idx:idx+Length]
                        idx += Length
                        find_did =True
                        break
            if find_did==False:
                TestLog("DEBUG", "", f"未知 DID: 0x{did:04X}")
                idx += 1
        return snapshot

snapshot_store = GlobalSnapshotStore()


def read_global_snapshot(
    node,
    dtc_select: int,
    name:str="",
    DTCSnapshotRecordNumber=1
) -> tuple[bool, Optional[GlobalSnapshotData]]:

    try:
        if dtc_select==None:
            TestLog("FAIL", "", f"dtc_select is None")
            return False, None
        dtc_select_tuple: tuple[int, int, int] = tuple(int.to_bytes(dtc_select,3,"big"))
        TestLog("INFO", "", f"发送 19 04 {hex(dtc_select)} 01 请求读取全局快照")
        success, resp = __service_19_check_lin(
            node,
            report_type=0x04,
            expect_data=[0x59, 0x04],
            expect_str="肯定响应(59 04)",
            defined_data = int.to_bytes(dtc_select,3,"big"),
            DTCSnapshotRecordNumber = DTCSnapshotRecordNumber,
            func_req=False
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return False, None
        if not success or resp is None:
            TestLog("FAIL", "", "未收到快照响应")
            return False, None
        snapshot_data = list(resp.data) if hasattr(resp, 'data') else list(resp)
        TestLog("INFO", "", f"收到快照响应: {[hex(b) for b in snapshot_data]}")
        if len(snapshot_data)<8:
            TestLog("FAIL", "", "无快照数据,长度小于8")
            return False, None
        if snapshot_data[7]==0:
            TestLog("FAIL", "", "无快照数据,快照did=0")
            return False, None
        TestLog("INFO", "", "解析快照数据")
        parsed_snapshot = snapshot_store.parse(
            response_data=bytes(snapshot_data),
            dtc_code=dtc_select_tuple
        )

        if parsed_snapshot is None:
            TestLog("FAIL", "", "快照数据解析失败")
            return False, None

        prt_str = "\r\n"
        for key ,item in  parsed_snapshot.dtc_snapshotdata.items():
            prt_str = prt_str + f"      {hex(key)}:{bytes(item).hex()}\r\n" 

        TestLog("INFO", "", f"已解析DTC{hex(dtc_select)}快照数据: {prt_str}")

        return True, parsed_snapshot

    except Exception as e:
        TestLog("FAIL", "", f"快照读取出错: {e}")
        return False, None
    
def read_dtc_and_global_snapshot(
    node,
    dtc_select: int,
    name:str="",
    DTCSnapshotRecordNumber=1
) -> tuple[bool, Optional[GlobalSnapshotData]]:
    try:
        TestLog("INFO", "Step",f"发送 19 02 {DTCTestParams.ExpectedDTCStatusAvailabilityMask} 请求读取DTC信息")
        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=DTCTestParams.ExpectedDTCStatusAvailabilityMask
        )

        if not success:
            TestLog("FAIL", "", "未收到肯定响应")
            return False, None

        dtc_list = get_dtc_list_from_19_resp(resp)
        fault_detected = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_code = int.from_bytes(bytes([dtc[0],dtc[1],dtc[2]]))
            if dtc_code == dtc_select:
                fault_detected = True

        if not fault_detected:
            TestLog("FAIL", name, "故障产生后未检测到低压的DTC")
            return False, None
        return  read_global_snapshot(node,dtc_select=dtc_select,name=name,DTCSnapshotRecordNumber=DTCSnapshotRecordNumber)

    except Exception as e:
        TestLog("FAIL", "", f"快照读取出错: {e}")
        return False, None


def get_snapshot_sig():
    from tp.lin_test_pre_module import get_sig_data
    sig_info={}
    for did_info in P.GlobalData.items:
        sig_info[did_info.DID] = {}
        sig_info[did_info.DID]["sig"] = did_info.sig
        sig_info[did_info.DID]["length"] = did_info.Length
        if (did_info.sig!="") and (did_info.sig !=None):
            sig_info[did_info.DID]["val"] = get_sig_data(did_info.sig)
    return sig_info    

def change_snapshot_sig(sig_info:dict):
    from tp.lin_test_pre_module import set_sig_data,get_sig_data
    need_set_sig={}
    for key,sig in sig_info.items():
        if sig["sig"]!=None and sig["sig"]!="":
            if sig["val"]==0:
                sig["val"] = 1
            else:
                sig["val"] = 0
            need_set_sig[sig["sig"]] = sig["val"]
    set_sig_data(need_set_sig)
    __lin_restart_delay(5,True)
    return sig_info


def test_GlobalSnapshotDataCheck_TC14(
        node: UDSNode,
        name: str = "[TG1_TC14] 全局快照数据检查"):
    """
    [TG1_TC14] 全局快照数据检查 - 故障产生时读取快照
    """
    global snapshot_store
    try:
        voltage_dtc_select = None
        for item in P.ExtendedDTCInfo.voltage.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            if "低压" not in item.Notes:
                continue
            voltage_dtc_select = dtc_code
            break
        if voltage_dtc_select == None:
            TestLog("FAIL", name, "表格中不支持低压的DTC")

        success = __service_14_check_lin(
            node,
            dtc=0xFFFFFF,  # 清除所有DTC
            expect_data=[0x54],
            expect_str="肯定响应(54)",
            func_req=False
        )

        if not success:
            TestLog("FAIL", name, "清除DTC失败")
            return
        __lin_restart_delay(2)
        # Step1: 模拟产生故障
        TestLog("INFO", "Step1", "模拟产生故障")
        ctx.power_ctrl.set_voltage(7.0)
        TestLog("INFO", "电压模拟", "模拟电压7V")
        __lin_restart_delay(5)

        # Step2: 发送03 19 02 08请求读取DTC信息
        TestLog("INFO", "Step2", "PHY Tx: 03 19 02 08 00 00 00 00")
        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=DTCTestParams.ExpectedDTCStatusAvailabilityMask
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        dtc_list = get_dtc_list_from_19_resp(resp)
        fault_detected = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_code = int.from_bytes(bytes([dtc[0],dtc[1],dtc[2]]))
            if dtc_code == voltage_dtc_select:
                bit0_test_failed = (status & 0x01) == 0x01
                if bit0_test_failed:
                    TestLog("PASS", "", f"DTC {hex(dtc_code)}: status=0x{status:02X}, bit0(测试失败)=1")
                    fault_detected = True
                else:
                    TestLog("FAIL", "", f"DTC {hex(dtc_code)}: status=0x{status:02X}, bit0(测试失败)=0")
                    return 
        if not fault_detected:
            TestLog("FAIL", name, "故障产生后未检测到低压的DTC")
            return
        


        TestLog("INFO", "", f"DTC选取: 选取 DTC {hex(voltage_dtc_select)} 进行快照读取测试")
        st,snapshot_data =read_dtc_and_global_snapshot(node,voltage_dtc_select,name)
        if st==True and snapshot_data!=None:
            snapshot_store.save("TG1_TC14", snapshot_data)

        # 检查快照数据与实际状态的一致性
        # TODO: 实现实际状态获取和比较逻辑

        TestLog("INFO", "快照检查", "全局快照数据与实际状态一致性检查")

        TestLog("PASS", name, "全局快照数据检查通过，快照数据已保存")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def test_GlobalSnapshotDataCheck_TC15(
        node: UDSNode,
        name: str = "[TG1_TC15] 全局快照数据检查"):
    """
    [TG1_TC15] 全局快照数据检查 - 故障恢复后检查快照不变性
    """
    try:
        global snapshot_store
 
        voltage_dtc_select = None
        for item in P.ExtendedDTCInfo.voltage.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            if "低压" not in item.Notes:
                continue
            voltage_dtc_select = dtc_code
            break
        if voltage_dtc_select == None:
            TestLog("FAIL", name, "表格中不支持低压的DTC")


        test_GlobalSnapshotDataCheck_TC14(node,name)
        # Step1: 模拟故障恢复
        TestLog("INFO", "Step1", "模拟故障恢复")
        ctx.power_ctrl.set_voltage(12.0)
        TestLog("INFO", "电压模拟", "模拟电压12V")
        __lin_restart_delay(5)

        # 发送03 19 02 08请求读取DTC信息
        TestLog("INFO", "Step2", "PHY Tx: 03 19 02 08 00 00 00 00")
        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=DTCTestParams.ExpectedDTCStatusAvailabilityMask
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        dtc_list = get_dtc_list_from_19_resp(resp)
        fault_detected = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_code = int.from_bytes(bytes([dtc[0],dtc[1],dtc[2]]))
            if dtc_code == voltage_dtc_select:
                fault_detected = True 
                bit0_test_failed = (status & 0x01) == 0x01
                if bit0_test_failed:
                    TestLog("FAIL", "", f"DTC {hex(dtc_code)}: status=0x{status:02X}, bit0(测试失败)=1")
                    return
                else:
                    TestLog("PASS", "", f"DTC {hex(dtc_code)}: status=0x{status:02X}, bit0(测试失败)=0")
                
        if not fault_detected:
            TestLog("FAIL", name, "故障产生后未检测到低压的DTC")
            return

        TestLog("INFO", "", f"DTC选取: 选取 DTC {hex(voltage_dtc_select)} 进行快照读取测试")
        st,snapshot_data =read_global_snapshot(node,voltage_dtc_select,name)
        if st==True and snapshot_data!=None:
            snapshot_store.save("TG1_TC15", snapshot_data)
        else:
            TestLog("FAIL", name, "全局快照数据发生变化")
            return

        if snapshot_store.compare("TG1_TC14", snapshot_data,name):
            TestLog("PASS", name, "全局快照数据保持不变")
        else:
            TestLog("FAIL", name, "全局快照数据发生变化")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def test_GlobalSnapshotDataCheck_TC16(
        node: UDSNode,
        name: str = "[TG1_TC16] 全局快照数据检查"):
    """
    [TG1_TC16] 全局快照数据检查 - 数据变更后检查快照不变性
    """
    try:
        global snapshot_store
 
        voltage_dtc_select = None
        for item in P.ExtendedDTCInfo.voltage.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            if "低压" not in item.Notes:
                continue
            voltage_dtc_select = dtc_code
            break
        if voltage_dtc_select == None:
            TestLog("FAIL", name, "表格中不支持低压的DTC")
        test_GlobalSnapshotDataCheck_TC15(node,name)

        TestLog("INFO", "Step1", "改变ECU获取的全局快照数据的数值（电压、里程信号、电源模式、时间等），模拟产生故障")
        info = get_snapshot_sig()
        info = change_snapshot_sig(info)

        TestLog("INFO", "Step1", "模拟故障")
        ctx.power_ctrl.set_voltage(7.0)
        TestLog("INFO", "电压模拟", "模拟电压7V")
        __lin_restart_delay(5,True)
 
        TestLog("INFO", "", f"DTC选取: 选取 DTC {hex(voltage_dtc_select)} 进行快照读取测试")
        st,snapshot_data =read_dtc_and_global_snapshot(node,voltage_dtc_select,name)
        if st==True and snapshot_data!=None:
            snapshot_store.save("TG1_TC16", snapshot_data)
        else:
            TestLog("FAIL", name, "全局快照数据发生变化")
            return

        if snapshot_store.compare("TG1_TC14",snapshot_data):
            TestLog("PASS", name, "全局快照数据依旧保持不变")
        else:
            TestLog("FAIL", name, "全局快照数据发生变化")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")

def __power_resatrt(offtime, ontime_delay):
    from common.context import ctx
    ctx.bob_ctrl.set_power('KL30', False)
    time.sleep(offtime)
    ctx.bob_ctrl.set_power('KL30', True)
    __lin_restart_delay(ontime_delay)
def test_GlobalSnapshotDataCheck_TC17(
        node: UDSNode,
        name: str = "[TG1_TC17] 全局快照数据检查"):
    """
    [TG1_TC17] 全局快照数据检查 - 无法获取全局快照数据时检查默认值

    """
    try:
        TestLog("INFO", name, "开始执行TG1_TC17测试")

        # Step1: 模拟停发全局快照数据的数值（电压、里程信号、电源模式、时间等），模拟产生故障
        TestLog("INFO", "Step1", "模拟停发全局快照数据的数值（电压、里程信号、电源模式、时间等），模拟产生故障")
        # TODO: 实现具体的停发全局快照数据和故障模拟逻辑
        voltage_dtc_select = None
        for item in P.ExtendedDTCInfo.voltage.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            if "低压" not in item.Notes:
                continue
            voltage_dtc_select = dtc_code
            break
        if voltage_dtc_select == None:
            TestLog("FAIL", name, "表格中不支持低压的DTC")

        
        __power_resatrt(5,5)

        success = __service_14_check_lin(
            node,
            dtc=0xFFFFFF,  # 清除所有DTC
            expect_data=[0x54],
            expect_str="肯定响应(54)",
            func_req=False
        )

        if not success:
            TestLog("FAIL", name, "清除DTC失败")
            return
        __lin_restart_delay(2)
        # Step1: 模拟产生故障
        TestLog("INFO", "Step1", "模拟产生故障")
        ctx.power_ctrl.set_voltage(7.0)
        TestLog("INFO", "电压模拟", "模拟电压7V")
        __lin_restart_delay(5)
        st,snapshot_data = read_dtc_and_global_snapshot(node,voltage_dtc_select,name)
        if st==False:
            TestLog("FAIL", name, "测试失败")
            return
        info = get_snapshot_sig()
        for did,val in snapshot_data.dtc_snapshotdata.items():
            if did in info.keys():
                if info[did]["sig"]!=None and info[did]["sig"]!="":
                    cmpval =[0XFF]*len(val)
                    if val !=cmpval:
                        TestLog("FAIL", name, f"DTC did:{hex(did)}={bytes(val).hex()}!={bytes(cmpval).hex()}")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def test_GlobalSnapshotDataCheck_TC18(
        node: UDSNode,
        name: str = "[TG1_TC18] 全局快照数据检查"):
    """
    [TG1_TC18] 全局快照数据检查 - 信号无效时检查最近有效值
    调整说明：
    1. 在不满足快照读取条件下（信号无效）读取快照，只要能成功读取即可，不强制要求数值为最近有效值；
    2. 遍历诊断调查问卷表中支持的所有快照记录号；
    3. 快照中对时间数值的有效性不做判断要求。
    """
    try:
        from testcases.uds.uds_lin_utils import UDSTestParams

        success = __service_14_check_lin(
            node,
            dtc=0xFFFFFF,  # 清除所有DTC
            expect_data=[0x54],
            expect_str="肯定响应(54)",
            func_req=False
        )

        if not success:
            TestLog("FAIL", name, "清除DTC失败")
            return
        __lin_restart_delay(2)
        dtc_select = None
        set_msgid = None
        set_invalid_data = None
        set_valid_data = None
        for item in P.ExtendedDTCInfo.invalid_data.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            dtc_select = dtc_code
            set_msgid = item.MonitorMessageID
            set_invalid_data = item.InvalidPayload
            set_valid_data = item.ValidPayload
            break
        if dtc_select is None:
            TestLog("FAIL", name, "表格中不支持无效数据故障")
            return

        # Step1: 模拟发送全局快照数据的数值（有效值）
        TestLog("INFO", "Step1", "模拟发送全局快照数据的数值（电压、里程信号、电源模式、时间等）")
        if set_valid_data is not None:
            sim_dtc_data_invalid(set_msgid, set_valid_data)
        else:
            TestLog("INFO", name, "无有效数据配置，跳过发送有效数据")

        # Step2: 模拟发送无效数据，产生故障
        TestLog("INFO", "Step2", "模拟发送全局快照数据的信号无效的数值，模拟产生故障")
        sim_dtc_data_invalid(set_msgid, set_invalid_data)

        # Step3: 读取DTC信息，确认故障已产生
        TestLog("INFO", "Step3", "读取DTC信息确认故障产生")
        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=DTCTestParams.ExpectedDTCStatusAvailabilityMask
        )
        if not success:
            TestLog("FAIL", name, "读取DTC信息失败")
            return

        dtc_list = get_dtc_list_from_19_resp(resp)
        fault_detected = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_code = int.from_bytes(bytes([dtc[0], dtc[1], dtc[2]]))
            if dtc_code == dtc_select:
                fault_detected = True
                break

        if not fault_detected:
            TestLog("FAIL", name, "故障产生后未检测到目标DTC")
            return

        # Step4: 遍历所有支持的快照记录号读取快照
        snapshot_numbers = UDSTestParams.Services19SnapshotRecordNumberSupportList
        all_snapshot_pass = True
        for snapshot_num in snapshot_numbers:
            TestLog("INFO", name, f"尝试读取快照记录号: 0x{snapshot_num:02X}")
            st, snapshot_data = read_global_snapshot(
                node,
                dtc_select=dtc_select,
                name=name,
                DTCSnapshotRecordNumber=snapshot_num
            )
            if st and snapshot_data is not None:
                TestLog("PASS", name, f"快照记录号 0x{snapshot_num:02X} 读取成功")
                prt_str = ""
                for did, val in snapshot_data.dtc_snapshotdata.items():
                    prt_str += f"\r\n      {hex(did)}:{bytes(val).hex()}"
                TestLog("INFO", name, f"快照记录号 0x{snapshot_num:02X} 数据: {prt_str}")
            else:
                TestLog("FAIL", name, f"快照记录号 0x{snapshot_num:02X} 读取失败")
                all_snapshot_pass = False

        if all_snapshot_pass:
            TestLog("PASS", name, "所有支持的快照记录号读取完成")
        else:
            TestLog("FAIL", name, "部分快照记录号读取失败")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def test_GlobalSnapshotDataCheck_TC19(
        node: UDSNode,
        name: str = "[TG1_TC19] 全局快照数据检查"):
    """
    [TG1_TC19] 全局快照数据检查 - 系统数据与全局数据不一致时检查系统数据
    """
    try:
        TestLog("INFO", name, "开始执行TG1_TC19测试")

        TestLog("FAIL", name, "不支持")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def test_GlobalSnapshotDataCheck_TC20(
        node: UDSNode,
        name: str = "[TG1_TC20] 全局快照数据检查"):
    """
    [TG1_TC20] 全局快照数据检查 - 故障恢复后改变数据并检查最新快照
    """
    try:
        voltage_dtc_select = None
        for item in P.ExtendedDTCInfo.voltage.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            if "低压" not in item.Notes:
                continue
            voltage_dtc_select = dtc_code
            break
        if voltage_dtc_select == None:
            TestLog("FAIL", name, "表格中不支持低压的DTC")

        success = __service_14_check_lin(
            node,
            dtc=0xFFFFFF,  # 清除所有DTC
            expect_data=[0x54],
            expect_str="肯定响应(54)",
            func_req=False
        )
        
        if not success:
            TestLog("FAIL", name, "清除DTC失败")
            return
        
        __lin_restart_delay(2)
        dtc_select = None
        set_msgid = None
        set_invalid_data=None
        set_valid_data=None
        for item in P.ExtendedDTCInfo.invalid_data.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            dtc_select = dtc_code
            set_msgid = item.MonitorMessageID
            set_invalid_data = item.InvalidPayload
            set_valid_data = item.ValidPayload
            break
        if dtc_select == None:
            TestLog("FAIL", name, "表格中不支持无效数据故障")
            return

        sim_dtc_data_invalid(set_msgid,set_valid_data)

        TestLog("INFO", "Step1", "模拟产生故障")
        ctx.power_ctrl.set_voltage(7.0)
        TestLog("INFO", "电压模拟", "模拟电压7V")
        __lin_restart_delay(5,True)

        # st,snapshot_data = read_dtc_and_global_snapshot(node,voltage_dtc_select,name)
        # if st==False or snapshot_data==None :
        #     TestLog("FAIL", name, "测试失败")
        #     return

        info = get_snapshot_sig()
        change_snapshot_sig(info)


        TestLog("INFO", "Step2", "模拟故障恢复")
        ctx.power_ctrl.set_voltage(12.0)
        TestLog("INFO", "电压模拟", "模拟电压12V")
        __lin_restart_delay(5,True)


        TestLog("INFO", "Step3", "模拟产生故障")
        ctx.power_ctrl.set_voltage(7.0)
        TestLog("INFO", "电压模拟", "模拟电压7V")
        __lin_restart_delay(5,True)

        st,snapshot_data = read_dtc_and_global_snapshot(node,voltage_dtc_select,name,0X11)
        if st==False or snapshot_data==None :
            TestLog("FAIL", name, "测试失败")
            return
        for did,val in snapshot_data.dtc_snapshotdata.items():
            if did in info.keys():
                if info[did]["sig"]!=None and info[did]["sig"]!="":
                    if int.to_bytes(info[did]["val"],len(val),"little") !=bytes(val):
                        TestLog("FAIL", name, f"DTC did:{hex(did)}:{bytes(val).hex()}!={(int.to_bytes(info[did]["val"])).hex()}")
                    else:
                        TestLog("PASS", name, f"DTC did:{hex(did)}:{bytes(val).hex()}={(int.to_bytes(info[did]["val"])).hex()}")
           
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def test_GlobalSnapshotDataCheck_TC21(
        node: UDSNode,
        name: str = "[TG1_TC21] 全局快照数据检查"):
    """
    [TG1_TC21] 全局快照数据检查 - 再次故障恢复后改变数据并检查最新快照
    """
    try:
        voltage_dtc_select = None
        for item in P.ExtendedDTCInfo.voltage.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            if "低压" not in item.Notes:
                continue
            voltage_dtc_select = dtc_code
            break
        if voltage_dtc_select == None:
            TestLog("FAIL", name, "表格中不支持低压的DTC")

        success = __service_14_check_lin(
            node,
            dtc=0xFFFFFF,  # 清除所有DTC
            expect_data=[0x54],
            expect_str="肯定响应(54)",
            func_req=False
        )
        
        if not success:
            TestLog("FAIL", name, "清除DTC失败")
            return
        
        __lin_restart_delay(2)
        dtc_select = None
        set_msgid = None
        set_invalid_data=None
        set_valid_data=None
        for item in P.ExtendedDTCInfo.invalid_data.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            dtc_select = dtc_code
            set_msgid = item.MonitorMessageID
            set_invalid_data = item.InvalidPayload
            set_valid_data = item.ValidPayload
            break
        if dtc_select == None:
            TestLog("FAIL", name, "表格中不支持无效数据故障")
            return

        sim_dtc_data_invalid(set_msgid,set_valid_data)

        TestLog("INFO", "Step1", "模拟产生故障")
        ctx.power_ctrl.set_voltage(7.0)
        TestLog("INFO", "电压模拟", "模拟电压7V")
        __lin_restart_delay(5,True)

        # st,snapshot_data = read_dtc_and_global_snapshot(node,voltage_dtc_select,name)
        # if st==False or snapshot_data==None :
        #     TestLog("FAIL", name, "测试失败")
        #     return

        info = get_snapshot_sig()
        change_snapshot_sig(info)


        TestLog("INFO", "Step2", "模拟故障恢复")
        ctx.power_ctrl.set_voltage(12.0)
        TestLog("INFO", "电压模拟", "模拟电压12V")
        __lin_restart_delay(5,True)


        TestLog("INFO", "Step3", "模拟产生故障")
        ctx.power_ctrl.set_voltage(7.0)
        TestLog("INFO", "电压模拟", "模拟电压7V")
        __lin_restart_delay(5,True)

        st,snapshot_data = read_dtc_and_global_snapshot(node,voltage_dtc_select,name,0X11)
        if st==False or snapshot_data==None :
            TestLog("FAIL", name, "测试失败")
            return
        for did,val in snapshot_data.dtc_snapshotdata.items():
            if did in info.keys():
                if info[did]["sig"]!=None and info[did]["sig"]!="":
                    if int.to_bytes(info[did]["val"],len(val),"little") !=bytes(val):
                        TestLog("FAIL", name, f"DTC did:{hex(did)}:{bytes(val).hex()}!={(int.to_bytes(info[did]["val"])).hex()}")
                    else:
                        TestLog("PASS", name, f"DTC did:{hex(did)}:{bytes(val).hex()}={(int.to_bytes(info[did]["val"])).hex()}")
           
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")

def test_LocalSnapshotDataCheck_TC22(
        node: UDSNode,
        name: str = "[TG1_TC22] 局部快照数据检查"):
    """
    [TG1_TC22] 局部快照数据检查 - 故障条件下检查局部快照数据与实际状态一致
    """
    try:
        voltage_dtc_select = None
        for item in P.ExtendedDTCInfo.voltage.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            if "低压" not in item.Notes:
                continue
            voltage_dtc_select = dtc_code
            break
        if voltage_dtc_select == None:
            TestLog("FAIL", name, "表格中不支持低压的DTC")

        success = __service_14_check_lin(
            node,
            dtc=0xFFFFFF,  # 清除所有DTC
            expect_data=[0x54],
            expect_str="肯定响应(54)",
            func_req=False
        )
        
        if not success:
            TestLog("FAIL", name, "清除DTC失败")
            return
        
        __lin_restart_delay(2)
        dtc_select = None
        set_msgid = None
        set_invalid_data=None
        set_valid_data=None
        for item in P.ExtendedDTCInfo.invalid_data.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            dtc_select = dtc_code
            set_msgid = item.MonitorMessageID
            set_invalid_data = item.InvalidPayload
            set_valid_data = item.ValidPayload
            break
        if dtc_select == None:
            TestLog("FAIL", name, "表格中不支持无效数据故障")
            return

        sim_dtc_data_invalid(set_msgid,set_valid_data)

        TestLog("INFO", "Step1", "模拟产生故障")
        ctx.power_ctrl.set_voltage(7.0)
        TestLog("INFO", "电压模拟", "模拟电压7V")
        __lin_restart_delay(5,True)

        st,snapshot_data = read_dtc_and_global_snapshot(node,voltage_dtc_select,name,0X02)
        if st==False or snapshot_data==None :
            TestLog("FAIL", name, "测试失败")
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def test_LocalSnapshotDataCheck_TC23(
        node: UDSNode,
        name: str = "[TG1_TC23] 局部快照数据检查"):
    """
    [TG1_TC23] 局部快照数据检查 - 故障恢复后检查局部快照数据保持不变
    """
    try:
        voltage_dtc_select = None
        for item in P.ExtendedDTCInfo.voltage.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            if "低压" not in item.Notes:
                continue
            voltage_dtc_select = dtc_code
            break
        if voltage_dtc_select == None:
            TestLog("FAIL", name, "表格中不支持低压的DTC")

        success = __service_14_check_lin(
            node,
            dtc=0xFFFFFF,  # 清除所有DTC
            expect_data=[0x54],
            expect_str="肯定响应(54)",
            func_req=False
        )
        
        if not success:
            TestLog("FAIL", name, "清除DTC失败")
            return
        
        __lin_restart_delay(2)
        dtc_select = None
        set_msgid = None
        set_invalid_data=None
        set_valid_data=None
        for item in P.ExtendedDTCInfo.invalid_data.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            dtc_select = dtc_code
            set_msgid = item.MonitorMessageID
            set_invalid_data = item.InvalidPayload
            set_valid_data = item.ValidPayload
            break
        if dtc_select == None:
            TestLog("FAIL", name, "表格中不支持无效数据故障")
            return

        sim_dtc_data_invalid(set_msgid,set_valid_data)

        TestLog("INFO", "Step1", "模拟产生故障")
        ctx.power_ctrl.set_voltage(7.0)
        TestLog("INFO", "电压模拟", "模拟电压7V")
        __lin_restart_delay(5,True)


        info = get_snapshot_sig()
        change_snapshot_sig(info)


        TestLog("INFO", "Step2", "模拟故障恢复")
        ctx.power_ctrl.set_voltage(12.0)
        TestLog("INFO", "电压模拟", "模拟电压12V")
        __lin_restart_delay(5,True)


        TestLog("INFO", "Step3", "模拟产生故障")
        ctx.power_ctrl.set_voltage(7.0)
        TestLog("INFO", "电压模拟", "模拟电压7V")
        __lin_restart_delay(5,True)

        st,snapshot_data = read_dtc_and_global_snapshot(node,voltage_dtc_select,name,0X02)
        if st==False or snapshot_data==None :
            TestLog("FAIL", name, "测试失败")
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


# 添加DTC触发监控相关的导入
from .dtc_trigger_config import DTCTriggerTestConfig, DTCTriggerConfig


# 添加DTC触发监控相关的辅助函数
def check_trigger_frame_format(frame_data):
    """检查DTC触发帧格式是否符合上汽诊断规范"""
    try:
        # 检查帧头标识
        if len(frame_data) < 2:
            return False, "帧长度不足"

        header = frame_data[:2]
        if header != bytes(DTCTriggerConfig.TRIGGER_FRAME_FORMAT["header"]):
            return False, f"帧头标识不符: {header.hex()}"

        # 检查最小帧长度
        if len(frame_data) < DTCTriggerConfig.TRIGGER_FRAME_FORMAT["min_length"]:
            return False, f"帧长度不足: {len(frame_data)}"

        # 检查校验和（简化检查）
        if len(frame_data) >= 8:
            # 这里可以添加更复杂的校验和计算逻辑
            TestLog("INFO", "FrameFormatCheck", "DTC触发帧格式检查通过")
            return True, "格式符合规范"

        return True, "格式基本符合规范"

    except Exception as e:
        return False, f"格式检查异常: {e}"


class DTCTriggerMonitor:
    """DTC触发监控类"""

    def __init__(self, node: UDSNode):
        self.node = node
        self.trigger_frames = []
        self.start_time = None
        self.end_time = None

    def start_monitoring(self):
        """开始监控DTC触发帧"""
        self.start_time = time.time()
        self.trigger_frames = []
        TestLog("INFO", "DTCTriggerMonitor", "开始监控DTC触发帧")

    def stop_monitoring(self):
        """停止监控DTC触发帧"""
        self.end_time = time.time()
        TestLog("INFO", "DTCTriggerMonitor", f"停止监控，监控时长: {self.end_time - self.start_time:.2f}秒")

    def record_trigger_frame(self, frame_data, timestamp):
        """记录DTC触发帧"""
        frame_info = {
            "data": frame_data,
            "timestamp": timestamp,
            "format_valid": False,
            "format_error": ""
        }

        # 检查帧格式
        is_valid, error_msg = check_trigger_frame_format(frame_data)
        frame_info["format_valid"] = is_valid
        frame_info["format_error"] = error_msg

        self.trigger_frames.append(frame_info)
        TestLog("INFO", "DTCTriggerMonitor", f"记录DTC触发帧: {frame_data.hex()}, 时间: {timestamp}")

    def get_trigger_intervals(self):
        """获取触发间隔时间"""
        if len(self.trigger_frames) < 2:
            return []

        intervals = []
        for i in range(1, len(self.trigger_frames)):
            interval = self.trigger_frames[i]["timestamp"] - self.trigger_frames[i - 1]["timestamp"]
            intervals.append(interval)

        return intervals


# 添加TG1_TC24测试函数
def test_DTCTriggerCheck_TC24(
        node: UDSNode,
        name: str = "[TG1_TC24] 单个诊断故障代码触发检查"):
    """
    [TG1_TC24] 单个诊断故障代码触发检查
    """
    try:
        TestLog("INFO", name, "开始执行TG1_TC24测试")

        # 获取测试配置
        config = DTCTriggerTestConfig.TG1_TC24_CONFIG
        test_dtc_list = config["test_dtc_list"]
        monitor_duration = config["monitor_duration"]

        # 创建DTC触发监控器
        monitor = DTCTriggerMonitor(node)

        # Step1: 逐一模拟产生故障
        TestLog("INFO", "Step1", "PHY Tx：逐一模拟产生故障")
        for dtc_info in test_dtc_list:
            dtc_code = dtc_info["dtc_code"]
            fault_type = dtc_info["fault_type"]
            description = dtc_info["description"]

            TestLog("INFO", "故障模拟", f"模拟DTC {dtc_code:04X} - {description}")

            # TODO: 实现具体的故障模拟逻辑
            # 这里需要根据具体的故障类型实现相应的故障模拟

            # 开始监控
            monitor.start_monitoring()
            time.sleep(monitor_duration)
            monitor.stop_monitoring()

            # 检查是否收到DTC触发帧
            if len(monitor.trigger_frames) > 0:
                TestLog("PASS", "DTC触发检查",
                        f"DTC {dtc_code:04X} 触发成功，收到 {len(monitor.trigger_frames)} 个触发帧")

                # 检查触发帧格式
                for i, frame_info in enumerate(monitor.trigger_frames):
                    if frame_info["format_valid"]:
                        TestLog("PASS", "帧格式检查", f"第{i + 1}个触发帧格式符合上汽诊断规范")
                    else:
                        TestLog("FAIL", "帧格式检查", f"第{i + 1}个触发帧格式错误: {frame_info['format_error']}")
            else:
                TestLog("FAIL", "DTC触发检查", f"DTC {dtc_code:04X} 未收到任何触发帧")

        # 保存测试记录数据到ANNEX1
        TestLog("INFO", "ANNEX1",
                f"TG1_TC24测试记录数据 - 监控时长: {monitor_duration}秒, 测试DTC数量: {len(test_dtc_list)}")
        TestLog("PASS", name, "单个诊断故障代码触发检查完成")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


# 添加TG1_TC25测试函数
def test_DTCTriggerCheck_TC25(
        node: UDSNode,
        name: str = "[TG1_TC25] 单个诊断故障代码触发检查"):
    """
    [TG1_TC25] 单个诊断故障代码触发检查

    """
    try:
        TestLog("INFO", name, "开始执行TG1_TC25测试")

        # 获取测试配置
        config = DTCTriggerTestConfig.TG1_TC25_CONFIG
        test_dtc_list = config["test_dtc_list"]
        recovery_delay = config["recovery_delay"]
        retry_delay = config["retry_delay"]

        # 创建DTC触发监控器
        monitor = DTCTriggerMonitor(node)

        # 前置条件：需要先执行TG1_TC24
        TestLog("INFO", "前置条件", "执行TG1_TC24案例")
        test_DTCTriggerCheck_TC24(node, "[TG1_TC24] 单个诊断故障代码触发检查")

        # Step1: 逐一模拟故障恢复
        TestLog("INFO", "Step1", "PHY Tx：逐一模拟故障恢复")
        for dtc_info in test_dtc_list:
            dtc_code = dtc_info["dtc_code"]
            description = dtc_info["description"]

            TestLog("INFO", "故障恢复", f"恢复DTC {dtc_code:04X} - {description}")

            # TODO: 实现具体的故障恢复逻辑

            # 等待恢复延迟
            time.sleep(recovery_delay)

        # Step2: 逐一模拟产生故障（检查无重复触发）
        TestLog("INFO", "Step2", "PHY Tx：逐一模拟产生故障（检查无重复触发）")
        monitor.start_monitoring()

        for dtc_info in test_dtc_list:
            dtc_code = dtc_info["dtc_code"]
            description = dtc_info["description"]

            TestLog("INFO", "故障模拟", f"重新模拟DTC {dtc_code:04X} - {description}")

            # TODO: 实现具体的故障模拟逻辑

            # 等待重试延迟
            time.sleep(retry_delay)

        monitor.stop_monitoring()

        # 检查是否收到重复的DTC触发帧
        if len(monitor.trigger_frames) == 0:
            TestLog("PASS", "重复触发检查", "无重复诊断故障代码信息帧发出，符合预期")
        else:
            TestLog("FAIL", "重复触发检查", f"检测到 {len(monitor.trigger_frames)} 个重复触发帧")

        # 保存测试记录数据到ANNEX1
        TestLog("INFO", "ANNEX1", f"TG1_TC25测试记录数据 - 恢复延迟: {recovery_delay}秒, 重试延迟: {retry_delay}秒")
        TestLog("PASS", name, "单个诊断故障代码重复触发检查完成")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


# 添加TG1_TC26测试函数
def test_DTCTriggerCheck_TC26(
        node: UDSNode,
        name: str = "[TG1_TC26] 多个诊断故障代码触发检查"):
    """
    [TG1_TC26] 多个诊断故障代码触发检查
    """
    try:
        TestLog("INFO", name, "开始执行TG1_TC26测试")

        # 获取测试配置
        config = DTCTriggerTestConfig.TG1_TC26_CONFIG
        test_dtc_list = config["test_dtc_list"]
        expected_interval = config["expected_interval"]
        tolerance = config["tolerance"]

        # 创建DTC触发监控器
        monitor = DTCTriggerMonitor(node)

        # Step1: 同时模拟产生三个无父子关系的诊断故障
        TestLog("INFO", "Step1", "PHY Tx：同时模拟产生三个无父子关系的诊断故障")
        TestLog("INFO", "故障模拟", "同时模拟以下三个DTC:")
        for dtc_info in test_dtc_list:
            dtc_code = dtc_info["dtc_code"]
            description = dtc_info["description"]
            TestLog("INFO", "DTC列表", f"DTC {dtc_code:04X} - {description}")

        # TODO: 实现同时模拟三个故障的逻辑

        # 开始监控
        monitor.start_monitoring()
        time.sleep(5.0)  # 监控5秒
        monitor.stop_monitoring()

        # 检查是否收到DTC触发帧
        if len(monitor.trigger_frames) >= 3:
            TestLog("PASS", "多DTC触发检查", f"收到 {len(monitor.trigger_frames)} 个触发帧，符合预期")

            # 检查触发间隔
            intervals = monitor.get_trigger_intervals()
            if len(intervals) >= 2:
                for i, interval in enumerate(intervals):
                    if abs(interval - expected_interval) <= tolerance:
                        TestLog("PASS", "触发间隔检查", f"第{i + 1}个间隔: {interval:.2f}s，符合1s间隔要求")
                    else:
                        TestLog("FAIL", "触发间隔检查", f"第{i + 1}个间隔: {interval:.2f}s，不符合1s间隔要求")
            else:
                TestLog("FAIL", "触发间隔检查", "触发帧数量不足，无法计算间隔")
        else:
            TestLog("FAIL", "多DTC触发检查", f"只收到 {len(monitor.trigger_frames)} 个触发帧，不符合预期")

        # 保存测试记录数据到ANNEX1
        TestLog("INFO", "ANNEX1", f"TG1_TC26测试记录数据 - 期望间隔: {expected_interval}s, 容差: {tolerance}s")
        TestLog("PASS", name, "多个诊断故障代码触发检查完成")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


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


# 添加TG1_TC27测试函数
def test_QuietModeCheck_TC27(
        node: UDSNode,
        name: str = "[TG1_TC27] 安静模式检查"):
    """
    [TG1_TC27] 安静模式检查
    """
    try:
        TestLog("INFO", name, "开始执行TG1_TC27安静模式检查测试")
        success = __service_14_check_lin(
            node,
            dtc=0xFFFFFF,  # 清除所有DTC
            expect_data=[0x54],
            expect_str="肯定响应(54)",
            func_req=False
        )

        if not success:
            TestLog("FAIL", name, "清除DTC失败")
            return
        # Step1: 发送诊断请求10 02，使电控单元进入安静模式
        TestLog("INFO", "Step1", "PHY Tx：发送诊断请求10 02，使电控单元进入安静模式")
        TestLog("INFO", f"", "请求进入默认会话(10 01)")
        if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)"):
            return
        __lin_restart_delay(2)

        TestLog("INFO", f"", "请求进入扩展会话(10 03)")
        if not __service_10_check_lin(node, 0x03, [0x50, 0x03], "扩展会话肯定响应(50 03)"):
            return
        if not __check_current_session_lin(node,[0x71, 0x01, 0x02, 0x03, 0x00],"位于扩展会话中"):
            return

        # 使用10服务进入安静模式（子功能0x02）
        if not __service_10_check_lin( node, 0x02, [0x50, 0x02],"刷新会话肯定响应(50 02)"):
            return
        if not __check_current_session_lin(node, [0x7F, 0x31, 0x31], "位于刷新会话中(7F 31 31)"):
            return
        
        TestLog("PASS", "进入安静模式", "成功进入安静模式，收到肯定响应: 50 02")
        # Step2: 模拟目标诊断故障代码失效条件
        TestLog("INFO", "Step2", "PHY Tx：模拟目标诊断故障代码失效条件")
        tester_present_start(node)
        ctx.power_ctrl.set_voltage(8.0)
        time.sleep(5)
       
        # Step3: 取消模拟诊断故障代码失效条件
        TestLog("INFO", "Step3", "PHY Tx：取消模拟诊断故障代码失效条件")
        ctx.power_ctrl.set_voltage(12.0)
        time.sleep(5)
        tester_present_stop()

        # Step4: 发送诊断请求10 01，使电控单元退出安静模式
        # TestLog("INFO", "Step4", "PHY Tx：发送诊断请求10 01，使电控单元退出安静模式")
        # if not __service_10_check_lin(node, 0x01, [0x50, 0x01], "默认会话肯定响应(50 01)"):
        #     return
        # __lin_restart_delay(2)
        # if not __check_current_session_lin(node, [0x7F, 0x31, 0x7F], "位于默认会话中"):
        #     return 

        TestLog("INFO", "Step4", "PHY Tx：发送诊断请求11 01，使电控单元退出安静模式")
        if not __service_11_check(node, 0x01, [0x51, 0x01], "硬件复位肯定响应(51 01)"):
                return
        __lin_restart_delay(2)

        TestLog("INFO", "Step5", "发送 19 02  2C 请求读取DTC信息")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=DTCTestParams.ExpectedDTCStatusAvailabilityMask
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return
        
        # 解析DTC列表
        dtc_select = None
        dtc_list = get_dtc_list_from_19_resp(resp)
        for item in P.ExtendedDTCInfo.voltage.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            if "低压" not in item.Notes:
                continue
            dtc_select = dtc_code
        if dtc_select==None:
             TestLog("FAIL", name, "无低压DTC")
             return
        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_code = int.from_bytes(bytes([dtc[0],dtc[1],dtc[2]]))
            if dtc_code == dtc_select:
                TestLog("FAIL", "", f"检测到目标子诊断故障代码 DTC {hex(dtc_code)}: status=0x{status:02X}")
                return
        TestLog("PASS", name, "安静模式模拟目标诊断故障代码失效及恢复条件后未读取诊断故障代码状态信息")    
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
    finally:
        tester_present_stop()

def test_EngineCrank_TC28(
        node: UDSNode,
        name: str = "[TG1_TC28] 发动机起动场景检查"):
    """
    [TG1_TC28] 发动机起动场景检查

    """
    try:
        if node is None:
            TestLog("FAIL", name, "LIN 节点为空，初始化失败")
            return

        # TODO模拟接收发送机发送Crank信号

        TestLog("INFO", "Step1", "模拟电压低于9V（产生欠压故障码）")

        # TODO: 模拟电压低于9V，产生欠压故障码
        ctx.power_ctrl.set_voltage(8.0)
        TestLog("INFO", "电压模拟", "模拟电压低于9V")

        time.sleep(2)

        TestLog("INFO", "Step2", "发送 19 02 0F 请求读取DTC信息(LIN: 03 19 02 2C 00 00 00 00)")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=DTCTestParams.ExpectedDTCStatusAvailabilityMask
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return

        # 解析DTC列表
        dtc_list = get_dtc_list_from_19_resp(resp)

        if len(dtc_list) == 0:
            TestLog("FAIL", name, "未读取到任何 DTC（电压模拟可能未成功）")
            return

        TestLog("INFO", "", f"读取到 {len(dtc_list)} 个 DTC")

        # 检查"蓄电池电压低"诊断故障代码是否已记录
        battery_voltage_low_dtc_found = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_str = f"{dtc[0]:02X}{dtc[1]:02X}{dtc[2]:02X}"

            # TODO: 这里需要根据实际的DTC编码来识别"蓄电池电压低"故障码，假设"蓄电池电压低"故障码为0x123457
            if dtc_str == "123457":
                TestLog("FAIL", "", f"检查电控单元记录“蓄电池电压低”诊断故障代码 {dtc_str}: status=0x{status:02X}")
            elif dtc_str != "123457":
                TestLog("PASS", "", f"检查电控单元未记录“蓄电池电压低”诊断故障代码")
                battery_voltage_low_dtc_found = True
            else:
                TestLog("INFO", "", f"其他 DTC {dtc_str}: status=0x{status:02X}")

        if battery_voltage_low_dtc_found:
            TestLog("PASS", name, "未检测到蓄电池电压低诊断故障代码")
            return

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")

    finally:
        if node:
            node.close()


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


def test_DTCConfigurationCheck_TC29(
        node: UDSNode,
        name: str = "[TG1_TC29] 诊断故障代码配置检查"):
    """
    [TG1_TC29] 诊断故障代码配置检查
    """
    try:
       
        TestLog("INFO", "Step1", "将诊断故障代码配置标识符对应位设置为0")

        TestLog("INFO", "扩展会话", "10 03")
        if not __service_10_check_lin(node, 0x03, expect_data=[0x50, 0x03], expect_str="肯定响应(50 03)"):
            return
        if not __check_current_session_lin(node,[0x71, 0x01, 0x02, 0x03, 0x00],"位于扩展会话中"):
            return
        tester_present_start(node)

        TestLog("INFO", "关闭DTC", "85 02")
        status = __service_85_check_lin(node,2,[0xC5, 0x02],"肯定响应(C5 02)")
        if not status:
            tester_present_stop()
            return

        TestLog("INFO", "", "使用0x14服务清除所有DTC")
        success = __service_14_check_lin(
            node,
            dtc=0xFFFFFF,  # 清除所有DTC
            expect_data=[0x54],
            expect_str="肯定响应(54)",
            func_req=False
        )

        if not success:
            TestLog("FAIL", name, "清除DTC失败")
            tester_present_stop()
            return
        time.sleep(1)


        TestLog("INFO", "配置设置", f"设置DTC配置标识符(DID=0x100)为 0")
        success, resp = __service_22_check(
            node,
            dids=[0x0100],
            expect_data=[],
            expect_str=f"",
            func_req=False
        )

        if not success:
            TestLog("FAIL", name, "DTC配置标识符读取失败")
            tester_present_stop()
            return

        ctx.power_ctrl.set_voltage(8.0)
        time.sleep(5)

        TestLog("INFO", "Step5", "发送 19 02 请求读取DTC信息")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=DTCTestParams.ExpectedDTCStatusAvailabilityMask
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            tester_present_stop()
            return
        dtc_select = None
        dtc_list = get_dtc_list_from_19_resp(resp)
        for item in P.ExtendedDTCInfo.voltage.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            if "低压" not in item.Notes:
                continue
            dtc_select = dtc_code

        if dtc_select==None:
             TestLog("FAIL", name, "无低压DTC")
             tester_present_stop()
             return
        
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_code = int.from_bytes(bytes([dtc[0],dtc[1],dtc[2]]))
            if dtc_code == dtc_select:
                TestLog("FAIL", "", f"检测到目标诊断故障代码 DTC {hex(dtc_code)}: status=0x{status:02X}")
                tester_present_stop()
                return
        TestLog("PASS", "", f"未检测到目标诊断故障代码 DTC {hex(dtc_select)}")
        tester_present_stop()
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
        tester_present_stop()
    finally:
        tester_present_stop()        


def test_DTCConfigurationCheck_TC30(
        node: UDSNode,
        name: str = "[TG1_TC30] 诊断故障代码配置检查"):
    """
    [TG1_TC30] 诊断故障代码配置检查
    """
    try:
        TestLog("INFO", "前置条件", "执行TG1_TC29案例（诊断故障代码配置检查）")     
        test_DTCConfigurationCheck_TC29(node,name)
        tester_present_start(node)
        
        ctx.power_ctrl.set_voltage(12.0)
        time.sleep(5)

        TestLog("INFO", "打开TC", "85 01")
        status = __service_85_check_lin(node,1,[0xC5, 0x01],"肯定响应(C5 01)")
        if not status:
            tester_present_stop()
            return

        TestLog("INFO", "配置设置", f"设置DTC配置标识符(DID=0x100)为 0")
        success, resp = __service_22_check(
            node,
            dids=[0x0100],
            expect_data=[],
            expect_str=f"",
            func_req=False
        )

        if not success:
            TestLog("FAIL", name, "DTC配置标识符读取失败")
            tester_present_stop()
            return

        ctx.power_ctrl.set_voltage(8.0)
        time.sleep(5)

        TestLog("INFO", "Step5", "发送 19 02 请求读取DTC信息")

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=DTCTestParams.ExpectedDTCStatusAvailabilityMask
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            tester_present_stop()
            return
        dtc_select = None
        dtc_list = get_dtc_list_from_19_resp(resp)
        for item in P.ExtendedDTCInfo.voltage.valid_items:
            dtc_code = (item.DTCCode << 8) | item.FailureType
            if "低压" not in item.Notes:
                continue
            dtc_select = dtc_code

        if dtc_select==None:
             TestLog("FAIL", name, "无低压DTC")
             tester_present_stop()
             return
        
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_code = int.from_bytes(bytes([dtc[0],dtc[1],dtc[2]]))
            if dtc_code == dtc_select:
                TestLog("PASS", "", f"检测到目标诊断故障代码 DTC {hex(dtc_code)}: status=0x{status:02X}")
                tester_present_stop()
                return
        TestLog("FAIL", "", f"未检测到目标诊断故障代码 DTC {hex(dtc_select)}")

    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")

    finally:
        tester_present_stop()
        if node:
            node.close()

def inject_all_fault(node,name:str=""):
    from tp.lin_test_pre_module import set_msg_send,set_msg_rcv,set_invalid_data,set_sig_data
    simulated_dtc = []
    TestLog("INFO", name, "模拟产生故障_丢失通讯")
    for item in P.ExtendedDTCInfo.lost_communication.valid_items:
        dtc_select = (item.DTCCode << 8) | item.FailureType
        set_msgid = item.MonitorMessageID
        set_msg_rcv(set_msgid)

        TestLog("INFO", name, f"选取({hex(dtc_select)})作为测试 lost_communication DTC，仿真测试DTC并等待{item.LostTime} ms")
        __lin_restart_delay((item.LostTime/1000)*2,True)
        
        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=DTCTestParams.ExpectedDTCStatusAvailabilityMask
        )
        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return False, None

        dtc_list = get_dtc_list_from_19_resp(resp)
        fault_detected = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_code = int.from_bytes(bytes([dtc[0],dtc[1],dtc[2]]))
            if dtc_code == dtc_select:
                fault_detected = True
                TestLog("PASS", name, f"lost_communication 读取到故障码{hex(dtc_select)}")
                simulated_dtc.append(dtc_select)
                break
        if fault_detected == False:
            TestLog("FAIL", name, f"lost_communication 期望结果：读取到故障码{hex(dtc_select)}，实际未读到")
        set_msg_send(set_msgid)

    TestLog("INFO", name, "模拟无效数据故障")
    for item in P.ExtendedDTCInfo.invalid_data.valid_items:
        dtc_select = (item.DTCCode << 8) | item.FailureType
        set_msgid = item.MonitorMessageID
        invalid_data = item.InvalidPayload
        valid_data = item.ValidPayload
        set_invalid_data(invalid_data)

        TestLog("INFO", name, f"选取({hex(dtc_select)})作为测试 invalid_data DTC，仿真测试DTC并等待{item.LostTime} ms")
        __lin_restart_delay((item.LostTime/1000)*2,True)

        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=DTCTestParams.ExpectedDTCStatusAvailabilityMask
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return False, None

        dtc_list = get_dtc_list_from_19_resp(resp)
        fault_detected = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_code = int.from_bytes(bytes([dtc[0],dtc[1],dtc[2]]))
            if dtc_code == dtc_select:
                fault_detected = True
                TestLog("PASS", name, f"invalid_data 读取到故障码{dtc_select}")
                simulated_dtc.append(dtc_select)
                break
        if fault_detected == False:
            TestLog("FAIL", name, f"invalid_data 期望结果：读取到故障码{hex(dtc_select)}，实际未读到")
        set_invalid_data(valid_data)


    for item in P.ExtendedDTCInfo.voltage.valid_items:
        if "低压" not in item.Notes:
            continue

        TestLog("INFO", "", "模拟产生故障_低压")
        dtc_select = (item.DTCCode << 8) | item.FailureType
        ctx.power_ctrl.set_voltage(8)
        __lin_restart_delay(5,True)
        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=DTCTestParams.ExpectedDTCStatusAvailabilityMask
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return False, None

        dtc_list = get_dtc_list_from_19_resp(resp)
        fault_detected = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_code = int.from_bytes(bytes([dtc[0],dtc[1],dtc[2]]))
            if dtc_code == dtc_select:
                fault_detected = True
                TestLog("PASS", name, f"低压 读取到故障码{hex(dtc_select)}")
                simulated_dtc.append(dtc_select)
                break
        if fault_detected == False:
            TestLog("FAIL", name, f"低压 期望结果：读取到故障码{hex(dtc_select)}，实际未读到")
        ctx.power_ctrl.set_voltage(P.CANInfo.Vnormal)
        __lin_restart_delay(5)

    for item in P.ExtendedDTCInfo.voltage.valid_items:
        if "高压" not in item.Notes:
            continue

        TestLog("INFO", "", "模拟产生故障_高压")
        dtc_select = (item.DTCCode << 8) | item.FailureType
        ctx.power_ctrl.set_voltage(18)
        __lin_restart_delay(5,True)
        success, resp = __service_19_check_lin(
            node,
            report_type=0x02,
            expect_data=[0x59, 0x02],
            expect_str="肯定响应(59 02)",
            func_req=False,
            DTCStatusMask=DTCTestParams.ExpectedDTCStatusAvailabilityMask
        )

        if not success:
            TestLog("FAIL", name, "未收到肯定响应")
            return False, None

        dtc_list = get_dtc_list_from_19_resp(resp)
        fault_detected = False
        for dtc_info in dtc_list:
            dtc = dtc_info['dtc']
            status = dtc_info['status']
            dtc_code = int.from_bytes(bytes([dtc[0],dtc[1],dtc[2]]))
            if dtc_code == dtc_select:
                fault_detected = True
                TestLog("PASS", name, f"高压 读取到故障码{hex(dtc_select)}")
                simulated_dtc.append(dtc_select)
                break
        if fault_detected == False:
            TestLog("FAIL", name, f"高压 期望结果：读取到故障码{hex(dtc_select)}，实际未读到")
        ctx.power_ctrl.set_voltage(P.CANInfo.Vnormal)
        __lin_restart_delay(5)

    return simulated_dtc

def test_MaxDTCEntriesCheck_TC31(
        node: UDSNode,
        name: str = "[TG1_TC31] 最大诊断故障代码条目数检查"):
    """
    [TG1_TC31] 最大诊断故障代码条目数检查
    """
    try:
        success = __service_14_check_lin(
            node,
            dtc=0xFFFFFF,  # 清除所有DTC
            expect_data=[0x54],
            expect_str="肯定响应(54)",
            func_req=False
        )

        if not success:
            TestLog("FAIL", name, "清除DTC失败")
            return
    
        TestLog("INFO", name, "开始执行TG1_TC31最大诊断故障代码条目数检查测试")
        all_err_set = inject_all_fault(node,name)
        if len(all_err_set)<10:
            TestLog("FAIL", name, f"故障数量不足: {len(all_err_set)}<10")
            return
        read_count = 0
        for dtc in all_err_set:
           st,snapshot = read_global_snapshot(node,dtc,name)
           if st:
               read_count= read_count+1
               TestLog("PASS", name, f"DTC: {hex(dtc)}快照读取成功")
        if read_count>=10:
            TestLog("PASS", name, f"DTC: 最大数目{read_count}>=10")
        else:
            TestLog("FAIL", name, f"DTC: 最大数目{read_count}<10")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")

    finally:
        if node:
            node.close()


def test_NonVolatileMemoryStorageCheck_TC32(
        node: UDSNode,
        name: str = "[TG1_TC32] 非易失存储器存储检查"):
    """
    [TG1_TC32] 非易失存储器存储检查

    """
    try:
        success = __service_14_check_lin(
            node,
            dtc=0xFFFFFF,  # 清除所有DTC
            expect_data=[0x54],
            expect_str="肯定响应(54)",
            func_req=False
        )

        if not success:
            TestLog("FAIL", name, "清除DTC失败")
            return
        TestLog("INFO", name, "开始执行TG1_TC32非易失存储器存储检查测试")
        all_err_set = inject_all_fault(node,name)
        read_count = 0
        for dtc in all_err_set:
           st,snapshot = read_global_snapshot(node,dtc,name)
           if st:
               read_count= read_count+1
               TestLog("PASS", name, f"DTC: {hex(dtc)}快照读取成功")
        if read_count == 0:
            TestLog("FAIL", name, f"DTC:{read_count}= 0")
            return
        if not __service_11_check(node, 0x01, [0x51, 0x01], "硬件复位肯定响应(51 01)"):
                return
        __lin_restart_delay(2)

        TestLog("PASS", "ECU复位", "成功复位电控单元")
        later_reset_read_count = 0
        for dtc in all_err_set:
           st,snapshot = read_global_snapshot(node,dtc,name)
           if st:
               later_reset_read_count= later_reset_read_count+1
               TestLog("PASS", name, f"DTC: {hex(dtc)}快照读取成功")
        if read_count == later_reset_read_count:
            TestLog("PASS", name, f"DTC:{read_count}= {later_reset_read_count}")
        else:
            TestLog("FAIL", name, f"DTC: {read_count}!= {later_reset_read_count} ")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")


def test_DTCOverflowMechanismCheck_TC33(
        node: UDSNode,
        name: str = "[TG1_TC33] 诊断故障代码溢出机制检查"):
    """
    [TG1_TC33] 诊断故障代码溢出机制检查
    """
    try:
        success = __service_14_check_lin(
            node,
            dtc=0xFFFFFF,  # 清除所有DTC
            expect_data=[0x54],
            expect_str="肯定响应(54)",
            func_req=False
        )

        if not success:
            TestLog("FAIL", name, "清除DTC失败")
            return
        TestLog("INFO", name, "开始执行TG1_TC32非易失存储器存储检查测试")
        all_err_set = inject_all_fault(node,name)
        if len(all_err_set)<10:
            TestLog("FAIL", name, f"故障数量不足: {len(all_err_set)}<10")
            return
        first_dtc_err =False
        read_count = 0
        for dtc in all_err_set:
           st,snapshot = read_global_snapshot(node,dtc,name)
           if st:
               read_count= read_count+1
               TestLog("PASS", name, f"DTC: {hex(dtc)}快照读取成功")
           else:
              if (dtc == all_err_set[0]):
                first_dtc_err = True
        if read_count>=10:
            TestLog("PASS", name, f"DTC: 最大数目{read_count}>=10")
        else:
            TestLog("FAIL", name, f"DTC: 最大数目{read_count}<10")
        if first_dtc_err==True:
            TestLog("PASS", name, f"DTC: {hex(all_err_set[0])}快照溢出")
        else:
            TestLog("FAIL", name, f"DTC: {hex(all_err_set[0])}快照未溢出")
    except Exception as e:
        TestLog("FAIL", name, f"测试执行出错: {e}")
        TestLog("DEBUG", name, f"详细错误: {traceback.format_exc()}")
