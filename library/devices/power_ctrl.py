"""
    电源控制类
        支持 HSPY(30-05)、ITECH6932A
    使用示例：
        pwr = PowerControl()
        pwr.init(name="HSPY", port="COM3")
        pwr.on()  # 切换到ON
        status, current = pwr.get_current()  # 读取电流
        status, voltage = pwr.get_voltage()  # 读取电压
        pwr.set_current(3)  # 设置电流
        pwr.set_voltage(12)  # 设置电压
        pwr.off()  # 切换到OFF
        pwr.deinit()
"""
from uvtest.testlog import TestLog

from library.devices.power_manager.power_manager import (PowerInit,
                                                         PowerDeinit,
                                                         PowerOn,
                                                         PowerOff,
                                                         PowerSetVoltage,
                                                         PowerSetCurrent,
                                                         PowerGetCurrent,
                                                         PowerGetVoltage)


class PowerControl:
    def __init__(self):
        self.controller = None

    def init(self, name, port="COM3", device_addr=0):
        """
            连接电源
        """
        if self.controller is not None:
            self.deinit()
        TestLog("DEBUG", "电源控制", f"初始化: name={name}, port={port}, device_addr={device_addr}")
        status, ctrl = PowerInit(name, port, device_addr)
        if status is False:
            self.controller = None
            return False, ctrl
        self.controller = ctrl
        return True, "power init ok"

    def deinit(self):
        """
            断开连接
        """
        if self.controller is None:
            return False, "no power init"
        TestLog("DEBUG", "电源控制", f"断开连接")
        status, msg = PowerDeinit(self.controller)
        if status is False:
            return False, msg
        self.controller = None
        return True, "power deinit ok"

    def on(self):
        """
            切换到ON状态
        """
        if self.controller is None:
            return False, "no power init"
        TestLog("DEBUG", "电源控制", f"ON")
        status, msg = PowerOn(self.controller)
        if status is False:
            return False, msg
        return True, "power on ok"

    def off(self):
        """
            切换到OFF状态
        """
        if self.controller is None:
            return False, "no power init"
        TestLog("DEBUG", "电源控制", f"OFF")
        status, msg = PowerOff(self.controller)
        if status is False:
            return False, msg
        return True, "power off ok"

    def set_voltage(self, voltage):
        """
            设置电压
        """
        if self.controller is None:
            return False, "no power init"
        TestLog("DEBUG", "", f"设置电压 {voltage:.2f}V")
        status, msg = PowerSetVoltage(self.controller, voltage)
        if status is False:
            return False, msg
        return True, "power set voltage ok"

    def set_current(self, current):
        """
            设置电流
        """
        if self.controller is None:
            return False, "no power init"
        TestLog("DEBUG", "电源控制", f"设置电流 {current} A")
        status, msg = PowerSetCurrent(self.controller, current)
        if status is False:
            return False, msg
        return True, "power set current ok"

    def get_current(self):
        """
            读取电流
        """
        if self.controller is None:
            return False, "no power init"
        # TestLog("INFO", "电源控制", f"读取电流")
        status, current = PowerGetCurrent(self.controller)
        # TestLog("INFO", "电源控制", f"读取到的数据: {current}")
        if status is False:
            return False, current
        return True, current

    def get_voltage(self):
        """
            读取电压
        """
        if self.controller is None:
            return False, "no power init"
        TestLog("DEBUG", "电源控制", f"读取电压")
        status, voltage = PowerGetVoltage(self.controller)
        TestLog("DEBUG", "电源控制", f"读取到的数据: {voltage}")
        if status is False:
            return False, voltage
        return True, voltage


if __name__ == '__main__':
    p = PowerControl()
    p2 = PowerControl()
    p.init("HSPY", "COM3")
    p2.init("HSPY", "COM4")

    p.off()
    p.on()

    print(p.get_voltage())
    print(p.get_current())

    p.set_current(2)
    p.set_voltage(12)
