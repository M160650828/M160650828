import threading
import time
from uvtest.testlog import TestLog
from common.can_utils import send_canmsg, canmsg_create
from common.context import ctx
from common.utils import TimerCyclic
from typing import List
from slplus.time import sl_time
from typing import List, Tuple, Union
from slplus.time import sl_time
from common.params import P

def emit_can_busload_high(can_channel):
    data_length = 8
    bitrate = 500000
    bits_per_frame = 47 + data_length * 8 + 15
    max_frames_per_sec = (bitrate * 0.5) / bits_per_frame
    interval_sec = 1.0 / max_frames_per_sec
    msg = canmsg_create(0x01, 8, data=[0x3C] * 8)

    j = 25
    timer_id_start = 1
    timer_id_end = j
    for i in range(timer_id_start, timer_id_end + 1):
        TimerCyclic.start(i, interval_sec * 10000.0, send_canmsg, can_channel, msg=msg)
    return timer_id_start, timer_id_end


def emit_can_busload_high_stop(timer_id_start, timer_id_end):
    for i in range(timer_id_start, timer_id_end + 1):
        TimerCyclic.stop(i)


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

def get_fc_st_min_ms(payload):
    if payload[2] <= 2 or 0xF1 <= payload[2] <= 0xF9:
        return 2
    return payload[2]

def create_ff_cfs(req_id: int,
                  sid: int,
                  did: List[int],
                  length: int,
                  padding: int = 0xAA,
                  rtr: int = 0,
                  fdf: int = 0,
                  brs: int = 0,
                  ext: int = 0,
                  dlc: int = 8) -> Tuple[bool, Union[str, List[any]]]:
    """
    构造并打印多帧请求（ISO-TP 风格），兼容 CAN 与 CAN-FD。
    """
    frames = []

    # 1. 基础校验
    if len(did) != 2:
        return False, "did 必须是 2 字节 [0x11,0x22] 格式"

    # ISO-TP 单帧通常最多 7 字节(CAN)或 62 字节(CAN-FD)，此处处理 length > 7 的情况
    if not (7 < length <= 0xFFF):
        return False, "多帧请求 length 必须大于 7 且小于等于 4095 (0xFFF)"

    # 2. 确定物理层单帧最大字节数 (使用 get() 安全映射)
    dlc_to_bytes = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8,
                    9: 12, 10: 16, 11: 20, 12: 24, 13: 32, 14: 48, 15: 64}

    # 如果是 FD 模式则查表，否则固定为 8
    phy_len = dlc_to_bytes.get(dlc, 8) if fdf else 8

    if phy_len < 8:
        return False, f"DLC {dlc} 对应的物理长度过短，无法构造多帧"

    # 准备原始数据池 (SID + DID + 模拟数据)
    # 注意：这里的模拟数据逻辑沿用原代码：(i+3)&0xFF
    total_payload = [sid, did[0], did[1]]
    data_needed = length - len(total_payload)
    if data_needed > 0:
        total_payload += [(i + 3) & 0xFF for i in range(data_needed)]

    cursor = 0  # 已处理的数据指针

    # ---------- 3. 构造首帧 (First Frame, PCI = 0x10) ----------
    # 首帧 PCI 占用 2 字节: [0x10 | HighNibble, LowByte]
    b0 = 0x10 | ((length >> 8) & 0x0F)
    b1 = length & 0xFF

    ff_pci = [b0, b1]
    ff_max_data_len = phy_len - len(ff_pci)  # 首帧能装下的有效数据长度

    ff_data = total_payload[cursor: cursor + ff_max_data_len]
    ff_frame = ff_pci + ff_data

    # 如果首帧数据不足 phy_len（理论上多帧不会发生，但做健壮性处理），补 padding
    if len(ff_frame) < phy_len:
        ff_frame += [padding] * (phy_len - len(ff_frame))

    frames.append(ff_frame)
    cursor += len(ff_data)

    # ---------- 4. 构造连续帧 (Consecutive Frame, PCI = 0x20) ----------
    seq = 1
    cf_max_data_len = phy_len - 1  # 连续帧 PCI 占用 1 字节 [0x2x]

    while cursor < length:
        # 计算当前帧序列号 (0-15 循环)
        cf_pci = [0x20 | (seq & 0x0F)]

        # 截取剩余数据
        cf_data = total_payload[cursor: cursor + cf_max_data_len]
        cf_frame = cf_pci + cf_data

        # 补齐 Padding 到 phy_len
        if len(cf_frame) < phy_len:
            cf_frame += [padding] * (phy_len - len(cf_frame))

        frames.append(cf_frame)
        cursor += len(cf_data)
        seq += 1

    # ---------- 5. 实例化消息对象 ----------
    frame_list = []
    try:
        for frame in frames:
            # 假设 canmsg_create 已定义
            msg = canmsg_create(req_id, dlc=dlc, data=frame, rtr=rtr, fdf=fdf, brs=brs, ext=ext)
            frame_list.append(msg)
    except NameError:
        return False, "未找到 canmsg_create 函数定义"

    return True, frame_list

def check_resp_FC_ok(rN_BsTimeout_ms,start_time,rt):
    # from slplus.time import sl_time
    timeout_s = rN_BsTimeout_ms / 1000.0
    start_time = sl_time().timestamp()
    end_time = start_time + timeout_s

    while sl_time().timestamp() < end_time:
        TestLog("INFO", "",
                f"current={sl_time().timestamp()},start_time={start_time},time.time() - start_time={sl_time().timestamp() - start_time},len(recv_list)={len(rt.get_recv_list())}")
        recv_list = rt.get_recv_list()  # 原子取当前列表
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload and payload[0]>>4 == 3:  # 命中
                return payload  # 立即返回
        time.sleep(0.001)  # 1 ms 级空转，降低 CPU

    return None  # 超时未命中

def check_resp_FF_ok(rN_BsTimeout_ms, rt):
    """
        超时时间内查找首字节 = 0x10 的报文
        :param rN_BsTimeout_ms: 监控时长（毫秒）
        :param rt:              接收器对象（含 get_recv_list / get_recv_item_payload）
        :return:                命中报文的 payload 或 None
        """
    timeout_s = rN_BsTimeout_ms / 1000.0
    start_time = sl_time().timestamp()
    end_time = start_time + timeout_s

    while sl_time().timestamp()  < end_time:
        TestLog("INFO", "",
                f"current={sl_time().timestamp()},start_time={start_time},sl_time.timestamp() - start_time={sl_time().timestamp() - start_time},len(recv_list)={len(rt.get_recv_list())}")
        recv_list = rt.get_recv_list()  # 原子取当前列表
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload and payload[0]>>4 == 0x1:  # 命中
                return payload  # 立即返回
        time.sleep(0.001)  # 1 ms 级空转，降低 CPU

    #回复NRC78处理
    recv_list = rt.get_recv_list()
    payload_10 = None
    for item in recv_list:
        payload = item.get("payload", [])
        if payload and (payload[0] & 0xF0) == 0x10:
            payload_10 = payload
            break
        elif payload[1] == 0x7F and payload[2] == 0x19 and payload[3] == 0x78:
            TestLog("WARNING","","期望结果：收到首帧(FF)。实际结果：收到NRC0x78")
            break

    rt.clear()
    start_time = sl_time().timestamp()

    while True:
        # 超时检测
        if sl_time().timestamp() - start_time >= 5:
            payload_10 = None
            break
        recv_list = rt.get_recv_list()
        for item in recv_list:
            payload = item.get("payload", [])
            if payload and (payload[0] >> 4) == 0x01:
                payload_10 = payload
                break                # 跳出 for

        else:                        # for 正常结束（没 break）才到这里
            sl_time().sleep(0.005)   # 稍等再轮询
            continue                 # 继续 while
        break                        # 收到帧后跳出 while

    if payload_10 is not None:
        return payload_10
    #回复NRC78处理结束

    return None  # 超时未命中

def check_first_cf(rN_BsTimeout_ms ,start_time, rt):
    timeout_s = rN_BsTimeout_ms  / 1000.0
    start_time = sl_time().timestamp()
    end_time = start_time + timeout_s

    while sl_time().timestamp() < end_time:
        # TestLog("INFO", "",
        #         f"current={sl_time().timestamp()},start_time={start_time},sl_time().timestamp() - start_time={sl_time().timestamp() - start_time},len(recv_list)={len(rt.get_recv_list())}")
        recv_list = rt.get_recv_list()  # 原子取当前列表
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[0] == 0x21:  # 命中
                return payload  # 立即返回
        time.sleep(0.001)  # 1 ms 级空转，降低 CPU

    return None  # 超时未命中

def check_default_session(rP2_Client_ms,rt):
    timeout_s = rP2_Client_ms / 1000.0
    start_time = sl_time().timestamp()
    end_time = start_time + timeout_s

    while sl_time().timestamp() < end_time:
        recv_list = rt.get_recv_list()
        for i in range(len(recv_list)):
            payload = rt.get_recv_item_payload(i)
            if payload[1] == 0x50 and payload[2] == 0x01:
                return payload  # 立即返回
        time.sleep(0.001)  # 1 ms 级空转，降低 CPU
    return None

def check_negative_resp(rt):
    recv_list = rt.get_recv_list()
    for i in range(len(recv_list)):
        payload = rt.get_recv_item_payload(i)
        if payload[1] == 0x7F:
            return False,"否定响应"
    return True,"肯定响应"
def wait_stable_communcation():
    sl_time().sleep(P.TpInfo.WaitDigprotocalStable_ms)