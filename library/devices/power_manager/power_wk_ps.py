"""
WK-PS 电源板卡控制

使用示例:
    status, ctrl = WKPSController_Init(control_can=2)
    ctrl.set_voltage(12.0)
    ctrl.set_current(5.0)
    ctrl.switch_on()
    voltage = ctrl.read_display_voltage()
    ctrl.switch_off()
    ctrl.close()
"""
import threading
from slplus.can import sl_can, sl_canmsg, register_canmsg_handler, unregister_canmsg_handler


class Reg:
    """WK-PS 寄存器定义"""
    PS1_SET = 0x80      # PS1控制报文
    PS1_READ = 0x81     # PS1请求回复
    PS1_ACK = 0x82      # PS1状态回复
    
    PS2_SET = 0x83      # PS2控制报文
    PS2_READ = 0x84     # PS2请求回复
    PS2_ACK = 0x85      # PS2状态回复


class PowerWKPSController:
    def __init__(self, control_can: int = 2, channel: int = 1):
        self.name = "WK-PS"
        self.control_can = control_can
        self.channel = channel
        self._voltage = 0.0
        self._current = 0.0
        self._on = False
        
        if channel == 1:
            self.set_id = Reg.PS1_SET
            self.read_id = Reg.PS1_READ
            self.ack_id = Reg.PS1_ACK
        else:
            self.set_id = Reg.PS2_SET
            self.read_id = Reg.PS2_READ
            self.ack_id = Reg.PS2_ACK

    def open(self):
        """打开连接"""
        pass

    def close(self):
        """关闭连接"""
        self.switch_off()

    def _send(self, msg_id: int, data: bytes) -> bool:
        """发送CAN报文"""
        try:
            msg = sl_canmsg(id=msg_id, is_fd=False, dlc=len(data), payload=data)
            sl_can(self.control_can).send_canmsg(msg)
            return True
        except Exception as e:
            return False

    def _build_data(self) -> bytes:

        v_int = int(self._voltage)                    
        v_dec = int((self._voltage - v_int) * 100)    
        v_int = max(5, min(v_int, 18))               
        v_dec = max(0, min(v_dec, 99))

        i_int = int(self._current)                    
        i_dec = int((self._current - i_int) * 100)    
        i_int = max(0, min(i_int, 2))                
        i_dec = max(0, min(i_dec, 99))

        data = bytearray(8)
        data[0] = 1 if self._on else 0   
        data[1] = 0
        data[2] = v_int                  
        data[3] = v_dec                   
        data[4] = i_int                   
        data[5] = i_dec                   
        return bytes(data)

    def _send_ctrl(self) -> bool:
        """发送控制报文"""
        return self._send(self.set_id, self._build_data())

    def switch_on(self) -> bool:
        """开启电源输出"""
        self._on = True
        return self._send_ctrl()

    def switch_off(self) -> bool:
        """关闭电源输出"""
        self._on = False
        return self._send_ctrl()

    def set_voltage(self, voltage: float) -> bool:
        """设置电压 (V)"""
        self._voltage = voltage
        return self._send_ctrl()

    def set_current(self, current: float) -> bool:
        """设置电流 (A)"""
        self._current = current
        return self._send_ctrl()

    def read_display_voltage(self, timeout: float = 0.5) -> float:
        """读取输出电压"""
        status = self._read_status(timeout)
        return status['voltage'] if status else -1

    def read_display_current(self, timeout: float = 0.5) -> float:
        """读取输出电流"""
        status = self._read_status(timeout)
        return status['current'] if status else -1

    def _read_status(self, timeout: float = 0.5) -> dict | None:
        """读取电源状态"""
        response_data = [None]
        event = threading.Event()
        ack_id = self.ack_id

        def _on_response(bustype, busid, msg, cookie):
            del bustype, busid, cookie
            msg_id = getattr(msg, 'msgid', 0)
            dirv = getattr(msg, 'dirv', 0)
            if dirv == 0 and msg_id == ack_id:
                payload = getattr(msg, 'payload', b'') or b''
                response_data[0] = bytes(payload)
                event.set()

        try:
            register_canmsg_handler(_on_response)
            self._send(self.read_id, bytearray([1, 0, 0, 0, 0, 0, 0, 0]))
            event.wait(timeout=timeout)

            raw = response_data[0]
            if raw is None or len(raw) < 6:
                return None

            return {
                'voltage': raw[2] + raw[3] / 100.0,
                'current': raw[4] + raw[5] / 100.0,
                'on': bool(raw[0] & 0x01)
            }
        except Exception:
            return None
        finally:
            try:
                unregister_canmsg_handler(_on_response)
            except Exception:
                pass


def WKPSController_Init(control_can: int = 2, channel: int = 1):
    try:
        ctrl = PowerWKPSController(control_can=control_can, channel=channel)
        return True, ctrl
    except Exception as e:
        return False, f"WK-PS init failed: {e}"

