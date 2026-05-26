import time
import threading
from typing import List, Tuple, Optional
from uvtest.testlog import TestLog
from common.can_utils import send_canmsg, canmsg_create
from common.context import ctx
from slplus.time import sl_time
from env.config import P


class IsoTpRunTimeInfo:
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

    def get_recv_list(self):
        return self.recv_list

    def get_recv_item_payload(self, index):
        if index >= len(self.recv_list):
            return []
        return self.recv_list[index]["payload"]

    def get_recv_item_timestamp(self, index):
        if index >= len(self.recv_list):
            return 0
        return self.recv_list[index]["timestamp"]


def isotp_monitor_start(rt: IsoTpRunTimeInfo, diag_req_id: int, diag_resp_id: int):
    def run():
        start_pos = 0
        ctx.can.messages.clear()
        while rt.flag_run:
            try:
                can_messages = ctx.can.messages
                if start_pos < len(can_messages):
                    msg = can_messages[start_pos]
                    start_pos += 1
                    if msg.id not in [diag_req_id, diag_resp_id]:
                        continue
                    # 发送的报文列表
                    if msg.id == diag_req_id:
                        rt.send_list.append({
                            "timestamp": msg.time_ms,
                            "payload": list(bytes.fromhex(msg.payload_hex)),
                        })
                    # 接收的报文列表
                    if msg.id == diag_resp_id:
                        rt.recv_list.append({
                            "timestamp": msg.time_ms,
                            "payload": list(bytes.fromhex(msg.payload_hex)),
                        })
            except Exception as e:
                import traceback
                traceback.print_exc()
            time.sleep(0.001)

    rt.clear()
    rt.start_run()
    threading.Thread(target=run, daemon=True).start()


def isotp_monitor_stop(rt: IsoTpRunTimeInfo):
    """停止报文监控"""
    rt.stop_run()


def get_fc_stmin_ms(payload: List[int]) -> int:
    """从流控帧payload获取STmin(ms)"""
    if len(payload) < 3:
        return 2
    stmin = payload[2]
    if stmin <= 2 or 0xF1 <= stmin <= 0xF9:
        return 2
    return stmin


def wait_for_fc(rt: IsoTpRunTimeInfo, timeout_ms: int) -> Optional[List[int]]:
    """等待流控帧(FC)响应"""
    timeout_s = timeout_ms / 1000.0
    start_time = sl_time().timestamp()
    end_time = start_time + timeout_s

    while sl_time().timestamp() < end_time:
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload and (payload[0] >> 4) == 3:  # FC帧的PCI高4位为3
                return payload
        time.sleep(0.001)
    return None


def build_isotp_first_frame(data: bytes, padding_byte: int = 0xAA, 
                            is_canfd: bool = False) -> Tuple[List[int], int]:
    """
    构造首帧(FF)
    """
    total_len = len(data)
    if is_canfd:
        max_data_len = P.TpInfo.MaxCanFDDataLength - 2  # 减去PCI的2字节
    else:
        max_data_len = 6  # CAN 2.0: 8字节 - 2字节PCI = 6字节数据

    # 首帧PCI: 1nnn nnnn (高4位=1, 低12位=数据长度)
    b0 = 0x10 | ((total_len >> 8) & 0x0F)
    b1 = total_len & 0xFF

    ff_data_len = min(max_data_len, total_len)
    ff_payload = [b0, b1] + list(data[:ff_data_len])

    frame_len = P.TpInfo.MaxCanFDDataLength if is_canfd else 8
    if len(ff_payload) < frame_len:
        ff_payload += [padding_byte] * (frame_len - len(ff_payload))

    return ff_payload, ff_data_len


def build_isotp_consecutive_frames(data: bytes, first_frame_data_len: int,
                                   padding_byte: int = 0xAA,
                                   is_canfd: bool = False) -> List[List[int]]:
    """
    构造连续帧(CF)列表
    """
    remaining_data = data[first_frame_data_len:]
    frame_len = P.TpInfo.MaxCanFDDataLength if is_canfd else 8
    max_data_per_cf = frame_len - 1  # 减去1字节PCI

    cf_list = []
    seq = 1
    offset = 0

    while offset < len(remaining_data):
        seg_len = min(max_data_per_cf, len(remaining_data) - offset)
        cf_payload = [0x20 | (seq & 0x0F)] + list(remaining_data[offset:offset + seg_len])
        
        if len(cf_payload) < frame_len:
            cf_payload += [padding_byte] * (frame_len - len(cf_payload))
        
        cf_list.append(cf_payload)
        offset += seg_len
        seq = (seq + 1) & 0x0F

    return cf_list

