from slplus.can import sl_can, sl_canmsg

class Reg:
    """
    寄存器地址表
    """
    # Byte1 - 通道选择
    TCAN1 = (1, 0)          # CAN1 测试通道
    TCAN2 = (1, 1)          # CAN2 测试通道
    TLIN1 = (1, 4)          # LIN1 测试通道
    TLIN2 = (1, 5)          # LIN2 测试通道
    TEST_BUS = (1, 7)       # 测试通道类型: 0=CAN, 1=LIN

    # Byte2 - CAN故障/断开
    CAN_H_ENGAGE = (2, 0)   # CANH断开
    CAN_L_ENGAGE = (2, 1)   # CANL断开
    CAN_ENGAGE = (2, 2)     # CANH和CANL同时断开
    CAN_SHORT = (2, 3)      # CANH和CANL短路
    CAN_H_KL30 = (2, 4)     # CANH与KL30连通
    CAN_L_KL30 = (2, 5)     # CANL与KL30连通
    CAN_H_GND = (2, 6)      # CANH与GND连通
    CAN_L_GND = (2, 7)      # CANL与GND连通

    # Byte3 - 外接设备
    DEVICE_SCOPE = (3, 0)   # 示波器
    DEVICE_VH6501 = (3, 1)  # 干扰仪
    DEVICE_MUL = (3, 2)     # 万用表
    DEVICE_LIN_SG = (3, 5)  # 信号发生器

    # Byte4 - CAN近端电阻/LIN断开
    CAN1_N_120 = (4, 0)     # CAN1 近端120Ω
    CAN2_N_120 = (4, 1)     # CAN2 近端120Ω
    LIN_N_ENGAGE = (4, 4)   # LIN近端闭合
    LIN_F_ENGAGE = (4, 5)   # LIN远端闭合

    # Byte5 - CAN远端电阻/LIN电阻电容
    CAN1_F_120 = (5, 0)     # CAN1 远端120Ω
    CAN2_F_120 = (5, 1)     # CAN2 远端120Ω
    LIN_1K_GND = (5, 4)     # LIN-GND 1kΩ
    LIN_30K_GND = (5, 5)    # LIN-GND 30kΩ
    LIN_1K_VCC = (5, 6)     # LIN-KL30 1kΩ
    LIN_9NF = (5, 7)        # LIN-GND 9nF

    # Byte6 - 电源控制/LIN故障
    ECU_KL30 = (6, 0)       # ECU接入KL30
    PWR_ENGAGE = (6, 1)     # 电源通断
    PGND_ENGAGE = (6, 2)    # 地通断
    ECU_KL15 = (6, 4)       # ECU接入KL15
    LIN_KL30 = (6, 6)       # LIN与KL30短路
    LIN_GND = (6, 7)        # LIN与GND短路

    # Byte7 - CAN终端电阻组
    CAN_128 = (7, 0)        # 128Ω
    CAN_120 = (7, 1)        # 120Ω
    CAN_72 = (7, 2)         # 72Ω
    CAN_60 = (7, 3)         # 60Ω
    CAN_45 = (7, 4)         # 45Ω
    CAN_40 = (7, 5)         # 40Ω
    CAN_30 = (7, 6)         # 30Ω

    # 电阻值映射
    RESISTANCE_MAP = {
        128: (7, 0), 120: (7, 1), 72: (7, 2), 60: (7, 3),
        45: (7, 4), 40: (7, 5), 30: (7, 6)
    }

    # 设备映射
    DEVICE_MAP = {
        'SCOPE': (3, 0), 'VH6501': (3, 1),
        'MUL': (3, 2), 'LIN_SG': (3, 5)
    }

    # CAN故障映射
    CAN_FAULT_MAP = {
        ('H', 'OPEN'): (2, 0), ('L', 'OPEN'): (2, 1),
        ('HL', 'OPEN'): (2, 2), ('HL', 'SHORT'): (2, 3),
        ('H', 'KL30'): (2, 4), ('L', 'KL30'): (2, 5),
        ('H', 'GND'): (2, 6), ('L', 'GND'): (2, 7),
    }


class WK5249Controller:
    """
    WK5249板卡控制

    使用示例:
        ctrl = WK5249Controller(can=2)
        ctrl.set_test_channel('CAN1', True)   # CAN1接入测试通道
        ctrl.set_can_fault('H', 'OPEN')       # CANH开路
        ctrl.set_resistance(60, True)         # 接入60Ω终端电阻
        ctrl.set_power('KL30', True)          # 接入KL30
        ctrl.reset()                          # 复位
    """

    CTRL_MSG_ID = 0x100
    ACK_MSG_ID = 0x101
    DMM_SET_ID = 0x77
    DMM_DATA_ID = 0x79

    def __init__(self, control_can: int = 2):
        self.control_can = control_can
        self.state = bytearray(8)  
        self.read_response_provider = None

    def _set_bit(self, byte_idx: int, bit_idx: int, value: bool):
        if value:
            self.state[byte_idx] |= (1 << bit_idx)
        else:
            self.state[byte_idx] &= ~(1 << bit_idx)

    def _send(self) -> bool:
        try:
            payload = bytes(self.state)
            sl_can(self.control_can).send_canmsg(
                sl_canmsg(id=self.CTRL_MSG_ID, is_fd=False, dlc=8, payload=payload)
            )
            return True
        except Exception as e:
            print(f"ERROR WK5249 send failed: {e}")
            return False

    def set_test_channel(self, channel: str, enable: bool = True) -> bool:
        """
        设置测试通道

        channel: CAN1, CAN2, LIN1, LIN2
        enable: True=接入测试通道, False=接入直连通道
        """
        reg_map = {'CAN1': Reg.TCAN1, 'CAN2': Reg.TCAN2,
                   'LIN1': Reg.TLIN1, 'LIN2': Reg.TLIN2}
        if "_" in channel:
            channel = channel.split("_")[0]

        if channel not in reg_map:
            return False
        byte_idx, bit_idx = reg_map[channel]
        self._set_bit(byte_idx, bit_idx, enable)
        # 设置总线类型
        is_lin = channel.startswith('LIN')
        self._set_bit(*Reg.TEST_BUS, is_lin)
        return self._send()

    def set_can_engage(self, line: str, enable: bool = True) -> bool:
        """
        设置CAN通道断开/连通

        line: H=CANH, L=CANL, HL=同时断开
        enable: True=断开, False=连通
        """
        reg_map = {'H': Reg.CAN_H_ENGAGE, 'L': Reg.CAN_L_ENGAGE, 'HL': Reg.CAN_ENGAGE}
        if line not in reg_map:
            return False
        self._set_bit(*reg_map[line], enable)
        return self._send()

    def set_can_fault(self, line: str, kind: str, enable: bool = True) -> bool:
        """
        设置CAN故障注入

        line: H, L, HL
        kind: OPEN, SHORT, KL30, GND
        enable: True=注入故障, False=清除故障
        """
        if "_" in line:
            line = line.split("_")[-1]

        if "_" in kind:
            kind = kind.split("_")[-1]
        key = (line, kind)
        if key not in Reg.CAN_FAULT_MAP:
            return False
        self._set_bit(*Reg.CAN_FAULT_MAP[key], enable)
        return self._send()

    def set_resistance(self, ohm: int, enable: bool = True) -> bool:
        """
        设置CAN终端电阻

        ohm: 30, 40, 45, 60, 72, 120, 128
        enable: True=接入, False=断开
        """
        if ohm not in Reg.RESISTANCE_MAP:
            return False
        self._set_bit(*Reg.RESISTANCE_MAP[ohm], enable)
        return self._send()

    def set_can_120(self, channel: int, near: bool = True, enable: bool = True) -> bool:
        """
        设置CAN通道120Ω电阻

        channel: 1=CAN1, 2=CAN2
        near: True=近端, False=远端
        enable: True=接入, False=断开
        """
        if channel == 1:
            reg = Reg.CAN1_N_120 if near else Reg.CAN1_F_120
        elif channel == 2:
            reg = Reg.CAN2_N_120 if near else Reg.CAN2_F_120
        else:
            return False
        self._set_bit(*reg, enable)
        return self._send()

    def set_device(self, device: str, enable: bool = True) -> bool:
        """
        设置外接设备接入

        device: SCOPE=示波器, VH6501=干扰仪, MUL=万用表, LIN_SG=信号发生器
        enable: True=接入, False=断开
        """
        if device not in Reg.DEVICE_MAP:
            return False
        self._set_bit(*Reg.DEVICE_MAP[device], enable)
        return self._send()

    def set_power(self, kind: str, enable: bool = True) -> bool:
        """
        设置ECU电源

        kind: KL30, KL15
        enable: True=接入, False=断开
        """
        if kind == 'KL30':
            self._set_bit(*Reg.ECU_KL30, enable)
            self._set_bit(*Reg.PWR_ENGAGE, enable)
            self._set_bit(*Reg.PGND_ENGAGE, enable)
        elif kind == 'KL15':
            self._set_bit(*Reg.ECU_KL15, enable)
        elif kind == 'GND':
            self._set_bit(*Reg.ECU_KL30, enable)
            self._set_bit(*Reg.PGND_ENGAGE, enable)
        else:
            return False
        return self._send()

    def set_lin_engage(self, near: bool = True, enable: bool = True) -> bool:
        """
        设置LIN通道闭合/断开

        near: True=近端, False=远端
        enable: True=闭合, False=断开
        """
        reg = Reg.LIN_N_ENGAGE if near else Reg.LIN_F_ENGAGE
        self._set_bit(*reg, enable)
        return self._send()

    def set_lin_fault(self, kind: str, enable: bool = True) -> bool:
        """
        设置LIN故障注入

        kind: KL30/SHORT_KL30=短接KL30, GND/SHORT_GND=短接GND, OPEN=断开
        enable: True=注入, False=清除
        """
        if "_" in kind:
            kind = kind.split("_")[-1]

        if kind == 'KL30':
            self._set_bit(*Reg.LIN_KL30, enable)
        elif kind == 'GND':
            self._set_bit(*Reg.LIN_GND, enable)
        elif kind == 'OPEN':
            return self.set_lin_engage(near=True, enable=enable)
        else:
            return False
        return self._send()

    def set_lin_load(self, load: str, enable: bool = True) -> bool:
        """
        设置LIN负载

        load: 1K_GND, 30K_GND, 1K_VCC, 9NF
        enable: True=接入, False=断开
        """
        reg_map = {
            '1K_GND': Reg.LIN_1K_GND, '30K_GND': Reg.LIN_30K_GND,
            '1K_VCC': Reg.LIN_1K_VCC, '9NF': Reg.LIN_9NF
        }
        if load not in reg_map:
            return False
        self._set_bit(*reg_map[load], enable)
        return self._send()

    def init(self) -> bool:
        """初始化板卡"""
        return self.reset()

    def reset(self) -> bool:
        """复位板卡"""
        self.state = bytearray(8)
        return self._send()

