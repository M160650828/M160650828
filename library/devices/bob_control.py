"""
BOB控制类
    支持: ETS6124, WK5249

使用示例:
    # ETS6124 + HSPY电源
    bob_ctrl.init("ETS6124", control_can=2, addr=0x00)
    power_ctrl.set_voltage(12.0)
    bob_ctrl.set_power('KL30', True)
    bob_ctrl.set_fault('CAN1_H', 'OPEN')

    # WK5249 + WK-PS电源
    power_ctrl.init("WK-PS", control_can=2)       
    bob_ctrl.init("WK5249", control_can=2)     
    power_ctrl.set_voltage(12.0)
    power_ctrl.set_current(5.0)
    power_ctrl.on()
    bob_ctrl.set_power('KL30', True)              # 开关
    bob_ctrl.set_test_channel('CAN1', True)       # 切换到测试通道
    bob_ctrl.set_fault('H', 'KL30')               # CANH短接KL30
    bob_ctrl.set_resistance(60, True)             # 接入60Ω电阻
    bob_ctrl.set_device('SCOPE', True)            # 接入示波器
"""
from uvtest.testlog import TestLog

from library.devices.bob_manager.bob_manager import (
    BobInit, BobReset, BobSetPower, BobSetFault,
    BobSetResistance, BobSetDevice, BobSetTestChannel,
    BobReadCurrent, BobReadVoltage
)


class BobControl:
    def __init__(self):
        self._ctrl = None
        self._name = None

    def init(self, name: str = "ETS6124", control_can: int = 2, **kwargs) -> tuple[bool, str]:
        """
        @brief: BOB初始化
        @param name: 控制器名称 (ETS6124, WK5249)
        @param control_can: 控制CAN通道
        @param kwargs: 
            - ETS6124: addr=0x00, power_ch=1
            - WK5249: 
        @return: (True, "pass") 或 (False, error_msg)
        """
        if self._ctrl is not None:
            self.deinit()

        TestLog("DEBUG", "BOB", f"初始化: name={name}, control_can={control_can}, {kwargs}")
        status, result = BobInit(name, control_can, **kwargs)

        if not status:
            self._ctrl = None
            self._name = None
            return False, result

        self._ctrl = result
        self._name = name.upper()
        return True, "bob init ok"

    def deinit(self) -> tuple[bool, str]:
        """
        @brief: 断开连接
        @return: (True, "pass") 或 (False, error_msg)
        """
        if self._ctrl is None:
            return False, "no bob init"
        TestLog("DEBUG", "BOB", "断开连接")
        self._ctrl = None
        self._name = None
        return True, "bob deinit ok"

    def reset(self) -> tuple[bool, str]:
        """
        @brief: 复位板卡
        @return: (True, "pass") 或 (False, error_msg)
        """
        if self._ctrl is None:
            return False, "no bob init"
        TestLog("INFO", "BOB", "复位")
        return BobReset(self._ctrl)

    def set_power(self, kind: str, on: bool, ch: int = None) -> tuple[bool, str]:
        """
        @brief: 电源开关控制 
        @param kind: KL30, KL15, ACC, GND
        @param on: True=开, False=关
        @param ch: 通道 (仅ETS6124, 1-2)
        @return: (True, "pass") 或 (False, error_msg)
        """
        if self._ctrl is None:
            return False, "no bob init"
        action = "开" if on else "关"
        TestLog("DEBUG", "BOB", f"电源控制 {kind} {action}")
        return BobSetPower(self._ctrl, kind, on, ch=ch)

    def set_fault(self, target: str, kind: str, enable: bool = True) -> tuple[bool, str]:
        """
        @brief: 故障注入
        @param target: 故障线路
            - ETS6124: CAN1_H, CAN1_L, CAN2_H, CAN2_L, LIN1~LIN4, CAN1, CAN2
            - WK5249: H, L, HL
        @param kind: 故障类型
            - ETS6124: OPEN, SHORT_KL30, SHORT_GND, SHORT
            - WK5249: OPEN, SHORT, KL30, GND
        @param enable: True=注入, False=清除
        @return: (True, "pass") 或 (False, error_msg)
        """
        if self._ctrl is None:
            return False, "no bob init"
        action = "注入" if enable else "清除"
        TestLog("DEBUG", "BOB", f"故障{action} {target} {kind}")
        return BobSetFault(self._ctrl, target, kind, enable)

    def set_resistance(self, ohm: int, enable: bool = True, ch: int = None) -> tuple[bool, str]:
        """
        @brief: 设置终端电阻
        @param ohm: 电阻值 (ETS6124: 120, WK5249: 30-128)
        @param enable: True=接入, False=断开
        @param ch: 通道 (仅ETS6124)
        @return: (True, "pass") 或 (False, error_msg)
        """
        if self._ctrl is None:
            return False, "no bob init"
        action = "接入" if enable else "断开"
        TestLog("DEBUG", "BOB", f"终端电阻 {ohm}Ω {action}")
        return BobSetResistance(self._ctrl, ohm, enable, ch=ch)

    def set_device(self, device: str, enable: bool = True) -> tuple[bool, str]:
        """
        @brief: 设置外接设备 (仅WK5249)
        @param device: SCOPE=示波器, VH6501=干扰仪, MUL=万用表, LIN_SG=信号发生器
        @param enable: True=接入, False=断开
        @return: (True, "pass") 或 (False, error_msg)
        """
        if self._ctrl is None:
            return False, "no bob init"
        action = "接入" if enable else "断开"
        TestLog("DEBUG", "BOB", f"外接设备 {device} {action}")
        return BobSetDevice(self._ctrl, device, enable)

    def set_test_channel(self, channel: str, enable: bool = True) -> tuple[bool, str]:
        """
        @brief: 设置测试通道 (仅WK5249)
        @param channel: CAN1, CAN2, LIN1, LIN2
        @param enable: True=测试通道, False=直连通道
        @return: (True, "pass") 或 (False, error_msg)
        """
        if self._ctrl is None:
            return False, "no bob init"
        mode = "测试通道" if enable else "直连通道"
        TestLog("DEBUG", "BOB", f"{channel} 切换到 {mode}")
        return BobSetTestChannel(self._ctrl, channel, enable)

    def read_current(self, ch: int = None, timeout: float = 0.5) -> float | None:
        """
        @brief: 读取电流 (仅ETS6124)
        @param ch: 通道
        @param timeout: 超时时间 (秒)
        @return: 电流值 (mA)
        """
        if self._ctrl is None:
            return None
        status, current = BobReadCurrent(self._ctrl, ch=ch, timeout=timeout)
        return current if status else None

    def read_voltage(self, ch: int = None, timeout: float = 0.5) -> float | None:
        """
        @brief: 读取电压 (仅ETS6124)
        @param ch: 通道
        @param timeout: 超时时间 (秒)
        @return: 电压值 (V)
        """
        if self._ctrl is None:
            return None
        status, voltage = BobReadVoltage(self._ctrl, ch=ch, timeout=timeout)
        return voltage if status else None

    @property
    def name(self) -> str | None:
        return self._name

    @property
    def controller(self):
        return self._ctrl


if __name__ == '__main__':
    from library.devices.power_ctrl import PowerControl

    # ETS6124 + HSPY 
    pwr = PowerControl()
    pwr.init("HSPY", "COM3")
    pwr.set_voltage(12.0)
    pwr.set_current(5.0)
    pwr.on()

    bob = BobControl()
    bob.init("ETS6124", control_can=2, addr=0x00)
    bob.set_power('KL30', True)
    bob.set_fault('CAN1_H', 'OPEN')
    bob.reset()
    bob.deinit()
    pwr.deinit()

    # WK5249 + WK-PS 
    pwr2 = PowerControl()
    pwr2.init("WK-PS", 2)  # control_can=2
    pwr2.set_voltage(12.0)
    pwr2.set_current(5.0)
    pwr2.on()

    bob2 = BobControl()
    bob2.init("WK5249", control_can=2)
    bob2.set_power('KL30', True)
    bob2.set_test_channel('CAN1', True)
    bob2.set_fault('H', 'KL30')
    bob2.set_resistance(60, True)
    bob2.set_device('SCOPE', True)
    bob2.reset()
    bob2.deinit()
    pwr2.deinit()

