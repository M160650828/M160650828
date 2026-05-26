from enum import IntEnum
from uvtest.testlog import TestLog

def canmsg_create(msg_id, dlc, data=b"", rtr=0, fdf=0, brs=0, ext=0):
    """
    CAN/CANFD报文创建
    """
    try:
        from slplus.can import sl_canmsg

        TestLog("DEBUG", "报文创建",
            f"开始创建报文 - ID=0x{msg_id:x}, DLC={dlc}, RTR={rtr}, FDF={fdf}, BRS={brs}, EXT={ext}")

        if fdf:
            dlc_to_bytes = {
                0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8,
                9: 12, 10: 16, 11: 20, 12: 24, 13: 32, 14: 48, 15: 64
            }
            data_len = dlc_to_bytes.get(int(dlc), 8)
            TestLog("DEBUG", "报文创建", f"CANFD模式: DLC={dlc} -> 数据长度={data_len}")
        else:
            data_len = min(int(dlc), 8)
            TestLog("DEBUG", "报文创建", f"CAN模式: DLC={dlc} -> 数据长度={data_len}")

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

        TestLog("DEBUG", "报文创建", f"创建载荷: {payload.hex().upper()} (长度={len(payload)})")

        msg = sl_canmsg(
            id=int(msg_id),
            is_fd=bool(fdf),
            dlc=int(dlc),
            payload=payload,
            brs=bool(brs),
            ide=bool(ext),
            rtr=bool(rtr)
        )

        TestLog("DEBUG", "报文创建",
                f"成功创建报文: ID=0x{msg_id:x}, DLC={dlc}, FDF={fdf}, BRS={brs}, "
                    f"RTR={rtr}, EXT={ext}, 数据长度={data_len}, 数据={data_dbg}")
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
        if msg is None:
            raise ValueError("报文创建失败，无法发送")
        sl_can(int(channel)).send_canmsg(msg)
        return msg
    except Exception as e:
        TestLog("FAIL", "发送报文", f"发送失败: {e}")
        return None
