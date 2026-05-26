import time
import traceback

from scapy.contrib.automotive.uds import UDS, UDS_DSC, UDS_SA, UDS_ER, UDS_CC, UDS_TP, UDS_CDTCS, UDS_ROE, UDS_LC, \
    UDS_RDBI, UDS_RMBA, UDS_RSDBI, UDS_RDBPI, UDS_DDDI, UDS_WDBI, UDS_WMBA, UDS_CDTCI, UDS_RDTCI, UDS_IOCBI, UDS_RC, \
    UDS_RD, UDS_RU, UDS_TD, UDS_RTE, UDS_RFT, UDS_AUTH

from uvtest.testlog import TestLog
from library.uds.bus_sim import BusSim

def log_info(*args, **kwargs):
    TestLog("INFO", "", str(args))


def log_error(*args, **kwargs):
    TestLog("ERROR", "", str(args))


def format_request_data(data):
    data = data.__bytes__()
    tmp = []
    for i in data:
        new_i = hex(i)[2:]
        new_i = new_i if len(new_i) == 2 else "0" + new_i
        tmp.append(new_i.upper())
    return " ".join(tmp)


def format_response_data(data):
    tmp = []
    for i in data:
        new_i = hex(i)[2:]
        new_i = new_i if len(new_i) == 2 else "0" + new_i
        tmp.append(new_i.upper())
    return " ".join(tmp)


class UDSNode:
    def __init__(self, bus_obj: BusSim):
        self.bus = bus_obj
        self.send_data = None
        self.tx_id = bus_obj.tx_id
        self.rx_id = bus_obj.rx_id
        self.func_id = bus_obj.func_id

    def close(self):
        self.bus.close()

    def send_msg(self, pkt, func_req=False, update_send_data=True):
        try:
            # update_send_data为True时，才会更新send_data，否则会因为持续发送3E导致后续的报文判断错误，因为send_data会被覆盖
            # 正常情况下会更新send_data，只有持续发送3E报文时，才会手动指定为False
            if update_send_data is True:
                self.send_data = pkt.__bytes__()
            return self.bus.send(pkt.__bytes__(), func_req)
        except Exception as e:
            log_error("发送失败", e)
            return -1

    def recv_msg(self, timeout=10):
        current_time = time.time()
        backoff_s = 0.1

        while time.time() - current_time < timeout:
            try:
                success, resp_msg = self.bus.recv(timeout)
                if not success or resp_msg is None:
                    continue

                if hasattr(resp_msg, 'arbitration_id') and resp_msg.arbitration_id != self.rx_id:
                    continue

                resp_data = resp_msg.data if hasattr(resp_msg, 'data') else resp_msg

                if len(resp_data) > 8 and resp_data[2] == self.send_data[0] + 0x40:
                    return resp_msg

                if len(resp_data) >= 1 and resp_data[0] == self.send_data[0] + 0x40:
                    return resp_msg

                # pending or negative response
                if len(resp_data) >= 2 and resp_data[0] == 0x7F and resp_data[1] == self.send_data[0]:
                    return resp_msg

                continue
            except Exception as e:
                log_error("exception, retry...", traceback.format_exc())
                time.sleep(backoff_s)

        return None

    def handle_recv(self, timeout):
        for _ in range(100):
            resp_pending = self.recv_msg(timeout=timeout)
            if resp_pending is None:
                log_error("超时未收到响应数据")
                return None

            pdata = resp_pending.data if hasattr(resp_pending, 'data') else resp_pending
            if len(pdata) == 0:
                continue
            if len(pdata) >= 3 and [pdata[0], pdata[2]] == [0x7F, 0x78]:
                resp_id = resp_pending.arbitration_id if hasattr(resp_pending, 'arbitration_id') else self.rx_id
                log_info("\tECU响应数据", hex(resp_id), format_response_data(pdata))
                continue
            else:
                return resp_pending
        return None

    def handle_recv_pending(self, timeout):
        resp_pending = self.recv_msg(timeout=timeout)
        if resp_pending is None:
            return False, None

        pdata = resp_pending.data if hasattr(resp_pending, 'data') else resp_pending
        if len(pdata) == 0:
            return False, None

        if len(pdata) >= 3 and [pdata[0], pdata[2]] == [0x7F, 0x78]:
            resp_id = resp_pending.arbitration_id if hasattr(resp_pending, 'arbitration_id') else self.rx_id
            log_info("\tECU响应数据", hex(resp_id), format_response_data(pdata))
            return True, resp_pending
        elif len(pdata) >= 3 and [pdata[0]] == [0x7F]:
            resp_id = resp_pending.arbitration_id if hasattr(resp_pending, 'arbitration_id') else self.rx_id
            log_info("\tECU响应数据", hex(resp_id), format_response_data(pdata))
            return True, resp_pending
        else:
            return False, None


    def get_supress_bit(self, byte_value):
        if byte_value is None:
            return 0
        return (byte_value >> 7) & 1

    def Service_0x10_SessionControl(self, session, func_req=False, dl=None, dl_padding=0x00, timeout=5, **kwargs):
        pkt = UDS(service=0x10)
        if session is not None:
            pkt /= UDS_DSC(diagnosticSessionType=session)

        if dl is not None:
            current_len = len(bytes(pkt))
            if dl > current_len:
                padding = [dl_padding] * (dl - current_len)
                pkt /= bytes(padding)
            elif dl < current_len:
                pkt = UDS(service=pkt.__bytes__()[0])/(pkt.__bytes__()[1:dl])

        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        if self.get_supress_bit(session) == 1:
            # 检测78
            status, msg = self.handle_recv_pending(0.05)
            if status is False:
                # 如果未出现78，则直接返回空
                return None
            else:
                # 非pending报文，检测到的是否定响应，直接返回
                # 如果检测到pending报文，则继续handle_recv()
                if [msg.data[0], msg.data[2]] != [0x7F, 0x78]:
                    return msg
        return self.handle_recv(timeout)

    def Service_0x11_ECUReset(self, reset_type=None, func_req=False, dl=None, dl_padding=0x00, timeout=5, **kwargs):
        pkt = UDS(service=0x11)
        if reset_type is not None:
            pkt /= UDS_ER(resetType=reset_type)

        if dl is not None:
            current_len = len(bytes(pkt))
            if dl > current_len:
                padding = [dl_padding] * (dl - current_len)
                pkt /= bytes(padding)
            elif dl < current_len:
                pkt = UDS(service=pkt.__bytes__()[0])/(pkt.__bytes__()[1:dl])

        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        if self.get_supress_bit(reset_type) == 1:
            # 检测78
            status, msg = self.handle_recv_pending(0.05)
            if status is False:
                # 如果未出现78，则直接返回空
                return None
            else:
                # 非pending报文，检测到的是否定响应，直接返回
                # 如果检测到pending报文，则继续handle_recv()
                if [msg.data[0], msg.data[2]] != [0x7F, 0x78]:
                    return msg
        return self.handle_recv(timeout)

    def Service_0x27_SecurityAccess(self, access_type, seed_key=None, func_req=False, dl=None, dl_padding=0x00, timeout=5, **kwargs):
        pkt = UDS(service=0x27)
        if access_type is not None:
            if access_type % 2 != 0:  # 奇数
                pkt /= UDS_SA(securityAccessType=access_type)
            else:
                if seed_key is not None:
                    pkt /= UDS_SA(securityAccessType=access_type, securityKey=bytearray(seed_key))
                else:
                    pkt /= UDS_SA(securityAccessType=access_type)

        if dl is not None:
            current_len = len(bytes(pkt))
            if dl > current_len:
                padding = [dl_padding] * (dl - current_len)
                pkt /= bytes(padding)
            elif dl < current_len:
                pkt = UDS(service=pkt.__bytes__()[0])/(pkt.__bytes__()[1:dl])

        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        return self.handle_recv(timeout)

    def Service_0x28_CommunicationControl(self, control_type=None,
                                          communication_type=None,
                                          func_req=False,
                                          dl=None, dl_padding=0x00,
                                          spec_data=None,
                                          timeout=5, **kwargs):
        pkt = UDS(service=0x28)
        if control_type is not None:
            pkt /= UDS_CC(controlType=control_type, communicationType2=communication_type or 0)

        if dl is not None:
            current_len = len(bytes(pkt))
            if dl > current_len:
                padding = [dl_padding] * (dl - current_len)
                pkt /= bytes(padding)
            elif dl < current_len:
                pkt = UDS(service=pkt.__bytes__()[0])/(pkt.__bytes__()[1:dl])

        if spec_data is not None:
            if isinstance(spec_data, list):
                spec_data = bytes(spec_data)
            pkt /= spec_data

        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        if self.get_supress_bit(control_type) == 1:
            # 检测78
            status, msg = self.handle_recv_pending(0.05)
            if status is False:
                # 如果未出现78，则直接返回空
                return None
            else:
                # 非pending报文，检测到的是否定响应，直接返回
                # 如果检测到pending报文，则继续handle_recv()
                if [msg.data[0], msg.data[2]] != [0x7F, 0x78]:
                    return msg
        return self.handle_recv(timeout)

    def Service_0x29_Authentication(self, subfunction, func_req=False, timeout=5, **kwargs):
        if subfunction % 2 == 0:
            subfunction = subfunction | 1
        pkt = UDS() / UDS_AUTH(subFunction=subfunction, **kwargs)
        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        if self.get_supress_bit(subfunction) == 1:
            return b''
        return self.handle_recv(timeout)

    def Service_0x3E_TesterPresent(self, subfunction=0, func_req=False, dl=None, dl_padding=0x00, timeout=5, force_recv=False, update_send_data=False, **kwargs):
        pkt = UDS(service=0x3E)
        if subfunction is not None:
            pkt /= UDS_TP(subFunction=subfunction)

        if dl is not None:
            current_len = len(bytes(pkt))
            if dl > current_len:
                padding = [dl_padding] * (dl - current_len)
                pkt /= bytes(padding)
            elif dl < current_len:
                pkt = UDS(service=pkt.__bytes__()[0])/(pkt.__bytes__()[1:dl])

        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req, update_send_data=update_send_data)
        if force_recv is False:  # 如果强制接收为False，表示不强制处理接收，如果为True，则继续进行接收处理
            if self.get_supress_bit(subfunction) == 1:
                return b''
        return self.handle_recv(timeout)

    def Service_0x85_ControlDTCSetting(self, dtc_setting_type=0, record=b"", func_req=False, timeout=5, dl=None, dl_padding=0x00, **kwargs):
        pkt = UDS(service=0x85)
        if dtc_setting_type is not None:
            pkt /= UDS_CDTCS(DTCSettingType=dtc_setting_type,
                                DTCSettingControlOptionRecord=record)

        if dl is not None:
            current_len = len(bytes(pkt))
            if dl > current_len:
                padding = [dl_padding] * (dl - current_len)
                pkt /= bytes(padding)
            elif dl < current_len:
                pkt = UDS(service=pkt.__bytes__()[0])/(pkt.__bytes__()[1:dl])

        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        if self.get_supress_bit(dtc_setting_type) == 1:
            return b''
        return self.handle_recv(timeout)

    def Service_0x86_ResponseOnEvent(self, event_type=0, win_time=0, record=b"", func_req=False, timeout=5, **kwargs):
        pkt = UDS() / UDS_ROE(eventType=event_type, eventWindowTime=win_time,
                              eventTypeRecord=record)
        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        if self.get_supress_bit(event_type) == 1:
            return b''
        return self.handle_recv(timeout)

    def Service_0x87_LinkControl(self, control_type=0, id=0, h=0, m=0, l=0, func_req=False, timeout=5, **kwargs):
        pkt = UDS() / UDS_LC(linkControlType=control_type,
                             baudrateIdentifier=id,
                             baudrateHighByte=h,
                             baudrateMiddleByte=m,
                             baudrateLowByte=l)
        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        if self.get_supress_bit(control_type) == 1:
            return b''
        return self.handle_recv(timeout)

    def Service_0x22_ReadDataByIdentifier(self, id=None, func_req=False, dl=None, dl_padding=0x00, timeout=5, **kwargs):
        pkt = UDS(service=0x22)
        if id is not None:
            pkt /= UDS_RDBI(identifiers=id)

        if dl is not None:
            current_len = len(bytes(pkt))
            if dl > current_len:
                padding = [dl_padding] * (dl - current_len)
                pkt /= bytes(padding)
            elif dl < current_len:
                pkt = UDS(service=pkt.__bytes__()[0])/(pkt.__bytes__()[1:dl])

        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        return self.handle_recv(timeout)

    def Service_0x23_ReadMemoryByAddress(self, size_len=0, address_len=0, size=0, address=0, func_req=False, timeout=5,
                                         **kwargs):
        sz_field = {
            1: "memorySize1", 2: "memorySize2",
            3: "memorySize3", 4: "memorySize4",
        }
        addr_field = {
            1: "memoryAddress1", 2: "memoryAddress2",
            3: "memoryAddress3", 4: "memoryAddress4",
        }
        kw = {}
        if size_len in range(1, 5):
            kw = {sz_field[size_len]: size}
        if address_len in range(1, 5):
            kw.update({addr_field[address_len]: address})
        pkt = UDS() / UDS_RMBA(memorySizeLen=size_len, memoryAddressLen=address_len, **kw)
        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        return self.handle_recv(timeout)

    def Service_0x24_ReadScalingDataByIdentifier(self, id=0, func_req=False, timeout=5, **kwargs):
        pkt = UDS() / UDS_RSDBI(dataIdentifier=id)
        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        return self.handle_recv(timeout)

    def Service_0x2A_ReadDataByPeriodicIdentifier(self, mode=0, period_id=0, fur_period_id=b"", func_req=False,
                                                  timeout=5, **kwargs):
        pkt = UDS() / UDS_RDBPI(transmissionMode=mode,
                                periodicDataIdentifier=period_id,
                                furtherPeriodicDataIdentifier=fur_period_id)
        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        return self.handle_recv(timeout)

    def Service_0x2C_DynamicallyDefineDataIdentifier(self, subfunction=0, record=b"", func_req=False, timeout=5,
                                                     **kwargs):
        pkt = UDS() / UDS_DDDI(subFunction=subfunction, dataRecord=record)
        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        return self.handle_recv(timeout)

    def Service_0x2E_WriteDataByIdentifier(self, id=0, record=b"", func_req=False, timeout=5, dl=None, dl_padding=0x00, defined_data=None, **kwargs):
        pkt = UDS(service=0x2E)
        if id is not None:
            pkt /= UDS_WDBI(dataIdentifier=id) / bytes(record)

        if dl is not None:
            current_len = len(bytes(pkt))
            if dl > current_len:
                padding = [dl_padding] * (dl - current_len)
                pkt /= bytes(padding)
            elif dl < current_len:
                pkt = UDS(service=pkt.__bytes__()[0])/(pkt.__bytes__()[1:dl])

        if defined_data is not None:
            pkt /= bytes(defined_data)

        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        return self.handle_recv(timeout)

    def Service_0x3D_WriteMemoryByAddress(self, size_len=0, address_len=0, size=0, address=0, func_req=False, timeout=5,
                                          **kwargs):
        sz_field = {
            1: "memorySize1", 2: "memorySize2",
            3: "memorySize3", 4: "memorySize4",
        }
        addr_field = {
            1: "memoryAddress1", 2: "memoryAddress2",
            3: "memoryAddress3", 4: "memoryAddress4",
        }
        kw = {}
        if size_len in range(1, 5):
            kw = {sz_field[size_len]: size}
        if address_len in range(1, 5):
            kw.update({addr_field[address_len]: address})
        pkt = UDS() / UDS_WMBA(memorySizeLen=size_len, memoryAddressLen=address_len, **kw)
        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        return self.handle_recv(timeout)

    def Service_0x14_ClearDiagnosticInformation(self, h=0, m=0, l=0, func_req=False, timeout=5, dl=None, dl_padding=0x00, **kwargs):
        pkt = UDS(service=0x14)
        if h is not None or m is not None or l is not None:
            pkt /= UDS_CDTCI(groupOfDTCHighByte=h or 0,
                             groupOfDTCMiddleByte=m or 0,
                             groupOfDTCLowByte=l or 0)

        if dl is not None:
            current_len = len(bytes(pkt))
            if dl > current_len:
                padding = [dl_padding] * (dl - current_len)
                pkt /= bytes(padding)
            elif dl < current_len:
                pkt = UDS(service=pkt.__bytes__()[0])/(pkt.__bytes__()[1:dl])

        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        return self.handle_recv(timeout)

    def Service_0x19_ReadDTCInformation(self, report_type=0,
                                        func_req=False,
                                        timeout=5, dl=None, dl_padding=0x00, defined_data=None, **kwargs):
        pkt = UDS(service=0x19)
        if report_type is not None:
            pkt /= UDS_RDTCI(reportType=report_type, **kwargs)

        if dl is not None:
            current_len = len(bytes(pkt))
            if dl > current_len:
                padding = [dl_padding] * (dl - current_len)
                pkt /= bytes(padding)
            elif dl < current_len:
                pkt = UDS(service=pkt.__bytes__()[0])/(pkt.__bytes__()[1:dl])

        if defined_data is not None:
            pkt /= bytes(defined_data)

        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        return self.handle_recv(timeout)

    def Service_0x2F_InputOutputControlByIdentifier(self, id=0, option=None, cs=None, enable_mask=None,
                                                    func_req=False, timeout=5, dl=None, dl_padding=0x00, **kwargs):
        cs_bytes = bytes(cs) if cs else b""
        enable_mask_bytes = bytes(enable_mask) if enable_mask else b""
        pkt = UDS(service=0x2F)

        if id is not None:
            # 不同的scapy版本，UDS_IOCBI生成的字节数不一样，因此，使用直接bytes进行数据构造
            hex_data = hex(id).removeprefix("0x")
            pkt /= bytes.fromhex(hex_data.rjust(len(hex_data)+1 if len(hex_data)%2!=0 else len(hex_data), '0'))  # UDS_IOCBI(dataIdentifier=id)

        if option is not None:
            pkt /= (bytes([option]) + cs_bytes + enable_mask_bytes)

        if dl is not None:
            current_len = len(bytes(pkt))
            if dl > current_len:
                padding = [dl_padding] * (dl - current_len)
                pkt /= bytes(padding)
            elif dl < current_len:
                pkt = UDS(service=pkt.__bytes__()[0])/(pkt.__bytes__()[1:dl])

        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        return self.handle_recv(timeout)

    def Service_0x31_RoutineControl(self, control_type=None, rid=0, record=b"", func_req=False, timeout=10, wait_resp=True,
                                    dl=None, dl_padding=0x00, **kwargs):
        pkt = UDS(service=0x31)
        if control_type is not None:
            pkt /= UDS_RC(routineControlType=control_type, routineIdentifier=rid)
            if record:
                pkt /= record

        if dl is not None:
            current_len = len(bytes(pkt))
            if dl > current_len:
                padding = [dl_padding] * (dl - current_len)
                pkt /= bytes(padding)
            elif dl < current_len:
                pkt = UDS(service=0x31)/(pkt.__bytes__()[1:dl])

        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        if wait_resp is False:
            return None
        return self.handle_recv(timeout)

    def Service_0x34_RequestDownload(self, dataformat=0, size_len=0, address_len=0, size=0, address=0, func_req=False,
                                     timeout=5,
                                     **kwargs):
        sz_field = {
            1: "memorySize1", 2: "memorySize2",
            3: "memorySize3", 4: "memorySize4",
        }
        addr_field = {
            1: "memoryAddress1", 2: "memoryAddress2",
            3: "memoryAddress3", 4: "memoryAddress4",
        }
        kw = {}
        if size_len in range(1, 5):
            kw = {sz_field[size_len]: size}
        if address_len in range(1, 5):
            kw.update({addr_field[address_len]: address})
        pkt = UDS() / UDS_RD(dataFormatIdentifier=dataformat, memorySizeLen=size_len,
                             memoryAddressLen=address_len,
                             **kw)
        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        return self.handle_recv(timeout)

    def Service_0x35_RequestUpload(self, dataformat=0, size_len=0, address_len=0, size=0, address=0, func_req=False,
                                   timeout=5,
                                   **kwargs):
        sz_field = {
            1: "memorySize1", 2: "memorySize2",
            3: "memorySize3", 4: "memorySize4",
        }
        addr_field = {
            1: "memoryAddress1", 2: "memoryAddress2",
            3: "memoryAddress3", 4: "memoryAddress4",
        }
        kw = {}
        if size_len in range(1, 5):
            kw = {sz_field[size_len]: size}
        if address_len in range(1, 5):
            kw.update({addr_field[address_len]: address})
        pkt = UDS() / UDS_RU(dataFormatIdentifier=dataformat, memorySizeLen=size_len,
                             memoryAddressLen=address_len,
                             **kw)
        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        return self.handle_recv(timeout)

    def Service_0x36_TransferData(self, counter=0, record=b"", func_req=False, timeout=5, **kwargs):
        pkt = UDS() / UDS_TD(blockSequenceCounter=counter,
                             transferRequestParameterRecord=record)
        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        return self.handle_recv(timeout)

    def Service_0x36_TransferData_WithoutPrint(self, counter=0, record=b"", func_req=False, timeout=5, **kwargs):
        pkt = UDS() / UDS_TD(blockSequenceCounter=counter,
                             transferRequestParameterRecord=record)
        # log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        return self.handle_recv(timeout)

    def Service_0x37_RequestTransferExit(self, record=b"", func_req=False, timeout=5, **kwargs):
        pkt = UDS() / UDS_RTE(transferRequestParameterRecord=record)
        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        return self.handle_recv(timeout)

    def Service_0x38_RequestFileTransfer(self, mode=0, path_len=0, path=b"", compress=0, encrypt=0, param_len=None,
                                         fs_uncompress=b"", fs_compress=b"", func_req=False, timeout=5, **kwargs):
        kw = {}
        if mode not in [2, 5]:
            kw.update({
                "compressionMethod": compress,
                "encryptingMethod": encrypt,
            })
        if mode not in [2, 4, 5]:
            kw.update({
                "fileSizeParameterLength": param_len,
                "fileSizeUnCompressed": fs_uncompress,
                "fileSizeCompressed": fs_compress,
            })
        pkt = UDS() / UDS_RFT(modeOfOperation=mode,
                              filePathAndNameLength=path_len,
                              filePathAndName=path,
                              **kw)
        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        return self.handle_recv(timeout)

    def Service_Unsupported(self, service_id, data=b"", func_req=False, timeout=5, **kwargs):
        pkt = UDS(service=service_id)
        if data:
            pkt /= bytes(data)
        log_info("\t发送请求数据", hex(self.func_id if func_req else self.tx_id), format_request_data(pkt))
        self.send_msg(pkt, func_req)
        return self.handle_recv(timeout)
