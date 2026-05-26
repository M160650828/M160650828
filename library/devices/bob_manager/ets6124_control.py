import time
from slplus.can import sl_can, sl_canmsg


class Reg:
    """
    寄存器地址表
    """
    # Page0
    HW_VERSION = 0
    SW_VERSION = 1
    SW_DATE = 2

    # Page1 Byte0
    CAN1_TR120 = 3
    CAN1_TR1240 = 4
    CAN2_TR120 = 5
    CAN2_TR1240 = 6

    # Page1 Byte1
    CAN1H_OPEN = 7
    CAN1L_OPEN = 8
    CAN2H_OPEN = 9
    CAN2L_OPEN = 10

    LIN1_OPEN = 7
    LIN2_OPEN = 8
    LIN3_OPEN = 9
    LIN4_OPEN = 10

    CAN1_SHORT = 11
    CAN2_SHORT = 12

    # Page1 Byte2
    CAN1H_KL30 = 13
    CAN1L_KL30 = 14
    CAN2H_KL30 = 15
    CAN2L_KL30 = 16

    CAN1H_GND = 17
    CAN1L_GND = 18
    CAN2H_GND = 19
    CAN2L_GND = 20

    LIN1_KL30 = 13
    LIN2_KL30 = 14
    LIN3_KL30 = 15
    LIN4_KL30 = 16

    LIN1_GND = 17
    LIN2_GND = 18
    LIN3_GND = 19
    LIN4_GND = 20

    # Page1 Byte3
    ECU_KL30_1 = 21
    ECU_KL30_2 = 22
    ECU_KL15_1 = 23
    ECU_KL15_2 = 24
    ECU_ACC_1 = 25
    ECU_ACC_2 = 26
    GND1_OFF = 27
    GND2_OFF = 28

    # Page2
    CH0_CURRENT = 29
    CH0_VOLTAGE = 30
    CH1_CURRENT = 31
    CH1_VOLTAGE = 32

    RELAY_RESET = 33
    CTRL_ID = 34

    _FAULT_BASE = {'OPEN': 7, 'SHORT_KL30': 13, 'SHORT_GND': 17}

    _POWER_BASE = {'KL30': ECU_KL30_1, 'KL15': ECU_KL15_1, 'ACC': ECU_ACC_1, 'GND': GND1_OFF}
    
    _CHANNEL = {
        'CAN1_H': 0, 'CAN1_L': 1, 'CAN2_H': 2, 'CAN2_L': 3,
        'LIN1': 0, 'LIN2': 1, 'LIN3': 2, 'LIN4': 3,
    }

    @classmethod
    def fault(cls, target: str, kind: str) -> int:
        """计算故障寄存器地址"""
        return cls._FAULT_BASE[kind] + cls._CHANNEL[target]

    @classmethod
    def power(cls, kind: str, channel: int) -> int:
        """计算电源寄存器地址"""
        return cls._POWER_BASE[kind] + (channel - 1)


class ETS6124Controller:
    """
    ETS6124控制

    使用示例:
        ctrl = ETS6124Controller(can=2, addr=0x00)
        ctrl.set_power('KL30', True)           # KL30开
        ctrl.set_fault('CAN1_H', 'OPEN')       # CAN1 H线开路
        ctrl.set_fault('LIN2', 'SHORT_GND')    # LIN2短接地
        ctrl.reset()                           # 复位
    """

    BOARD_TYPE = 0x21
    DEFAULT_CTRL_ID = 0x100

    def __init__(self, control_can: int = 2, addr: int = 0, power_ch: int = 1):
        self.control_can = control_can
        self.addr = addr
        self.power_ch = power_ch  
        self.ctrl_ids = {}
        self.read_response_provider = None

    def _write(self, reg: int, value: int = 1) -> bool:
        """写寄存器"""
        try:
            ctrl_id = self.ctrl_ids.get(self.addr, self.DEFAULT_CTRL_ID)
            # 控制字节: [bit0]=写(1), [bit3-5]=长度(1), 固定为 0x09
            payload = bytes([self.BOARD_TYPE, self.addr, reg, 0x09, value, 0, 0, 0])
            sl_can(self.control_can).send_canmsg(sl_canmsg(id=ctrl_id, is_fd=False, dlc=8, payload=payload))
            return True
        except Exception as e:
            print(f"ERROR ETS6124 write failed: {e}")
            return False

    def _read(self, reg: int, timeout: float = 0.5) -> bytes | None:
        """读寄存器"""
        try:
            ctrl_id = self.ctrl_ids.get(self.addr, self.DEFAULT_CTRL_ID)
            # 测量寄存器(29-32)是4字节，其他1字节
            reg_len = 4 if reg in (29, 30, 31, 32) else 1
            # 控制字节: [bit0]=读(0), [bit3-5]=长度
            ctrl_byte = reg_len << 3

            payload = bytes([self.BOARD_TYPE, self.addr, reg, ctrl_byte, 0, 0, 0, 0])
            sl_can(self.control_can).send_canmsg(sl_canmsg(id=ctrl_id, is_fd=False, dlc=8, payload=payload))

            if not self.read_response_provider:
                return None

            data = self.read_response_provider(ctrl_id + 1, timeout)
            if data and len(data) >= 4 + reg_len:
                if data[0] == self.BOARD_TYPE and data[1] == self.addr and data[2] == reg:
                    return bytes(data[4:4 + reg_len])
            return None
        except Exception as e:
            print(f"ERROR ETS6124 read failed: {e}")
            return None

    def set_power(self, kind: str, on: bool, ch: int = None) -> bool:
        """
        电源控制

        kind: KL30, KL15, ACC, GND
        on: True=开/接入, False=关/断开
        ch: 通道1-2, None用默认power_ch
        """
        ch = ch or self.power_ch
        value = (0 if on else 1) if kind == 'GND' else (1 if on else 0)
        return self._write(Reg.power(kind, ch), value)

    def set_can_tr120(self, on: bool, ch: int = None) -> bool:
        """CAN 120Ω终端电阻"""
        ch = ch or self.power_ch
        reg = Reg.CAN1_TR120 if ch == 1 else Reg.CAN2_TR120
        return self._write(reg, 1 if on else 0)

    def set_fault(self, target: str, kind: str, enable: bool = True) -> bool:
        """
        故障注入

        target: CAN1_H, CAN1_L, CAN2_H, CAN2_L, LIN1-4, CAN1/CAN2 (H-L短接)
        kind: OPEN, SHORT_KL30, SHORT_GND, SHORT
        enable: True=注入, False=清除
        """
        if kind == 'SHORT' and target in ('CAN1', 'CAN2'):
            reg = Reg.CAN1_SHORT if target == 'CAN1' else Reg.CAN2_SHORT
            return self._write(reg, 1 if enable else 0)

        return self._write(Reg.fault(target, kind), 1 if enable else 0)

    def read_current(self, ch: int = None, timeout: float = 0.5) -> float | None:
        """读取电流 (mA)"""
        ch = (ch or self.power_ch) - 1
        if ch not in (0, 1):
            return None
        reg = Reg.CH0_CURRENT if ch == 0 else Reg.CH1_CURRENT
        raw = self._read(reg, timeout)
        return int.from_bytes(raw, 'big', signed=True) / 1_000 if raw else None

    def read_voltage(self, ch: int = None, timeout: float = 0.5) -> float | None:
        """读取电压 (V)"""
        ch = (ch or self.power_ch) - 1
        if ch not in (0, 1):
            return None
        reg = Reg.CH0_VOLTAGE if ch == 0 else Reg.CH1_VOLTAGE
        raw = self._read(reg, timeout)
        return int.from_bytes(raw, 'big', signed=True) / 1_000_000 if raw else None

    def init(self, ctrl_id: int = None) -> bool:
        """初始化板卡"""
        if ctrl_id:
            self.ctrl_ids[self.addr] = ctrl_id
        return self.reset()
        
    def reset(self) -> bool:
        """复位板卡"""
        return self._write(Reg.RELAY_RESET, 1)
