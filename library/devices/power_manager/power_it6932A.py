import traceback

import pyvisa


class IT6932AController:
    def __init__(self):
        self.name = "ITECH"
        self.rm = pyvisa.ResourceManager()
        self.inst = None

    def open_tcp(self, ip):
        """
            通过以太网连接设备
        """
        qstr = f"TCPIP?*{ip}?*::?*::INSTR"
        results = self.rm.list_resources(qstr)
        if len(results) == 0:
            return False, f"No Found [{ip}]"
        self.inst = self.rm.open_resource(results[0], read_termination="\n", write_termination="\n")
        return True, None

    def open_usb(self):
        """
            通过USB连接设备
        """
        qstr = f"USB?::?*::?*::?*::INSTR"
        results = self.rm.list_resources(qstr)
        if len(results) == 0:
            return False, f"No Found ITECH Device"

        for item in results:
            try:
                self.inst = self.rm.open_resource(item, read_termination="\n", write_termination="\n")
                device_info = self.get_idn()
                if "ITECH" in str(device_info):
                    break
            except Exception as e:
                print(e)
                return False, traceback.format_exc()

        return True, None

    def get_idn(self):
        """
            获取设备信息
        """
        if self.inst is None:
            return False, "No Connect"
        return True, self.inst.query("*IDN?")

    def set_rst(self):
        """
            发送RST
        """
        if self.inst is None:
            return False, "No Connect"
        return True, self.inst.write("*RST")

    def set_voltage(self, voltage):
        if self.inst is None:
            return False, "No Connect"
        self.inst.write(f'VOLTage {voltage}V')
        time.sleep(0.1)
        return True, self.inst.query('MEAS:VOLTage?')

    def get_voltage(self):
        if self.inst is None:
            return False, "No Connect"
        return True, self.inst.query('MEAS:VOLTage?')

    def set_current(self, current):
        if self.inst is None:
            return False, "No Connect"
        self.inst.write(f'CURRent {current}A')
        time.sleep(0.1)
        return True, self.inst.query('MEAS:CURRent?')

    def get_current(self):
        if self.inst is None:
            return False, "No Connect"
        # return True, self.inst.query('CURRent?')  # 设置的电流
        return True, self.inst.query('MEAS:CURRent?')  # 实时的电流

    def set_remote(self):
        if self.inst is None:
            return False, "No Connect"
        return True, self.inst.write('SYSTem:REMote')

    def set_local(self):
        if self.inst is None:
            return False, "No Connect"
        return True, self.inst.write('SYSTem:LOCal')

    def power_on(self):
        if self.inst is None:
            return False, "No Connect"
        return True, self.inst.write('OUTPut ON')

    def power_off(self):
        if self.inst is None:
            return False, "No Connect"
        return True, self.inst.write('OUTPut OFF')

    def close(self):
        self.inst.close()
import time


def IT6932AController_Init():
    it6932a_ctrl = IT6932AController()
    status, msg = it6932a_ctrl.open_usb()
    if not status:
        return False, msg
    return True, it6932a_ctrl


def IT6932AController_Deinit(it6932a_ctrl: IT6932AController):
    return it6932a_ctrl.close()


def IT6932AController_PowerOn(it6932a_ctrl: IT6932AController):
    return it6932a_ctrl.power_on()


def IT6932AController_PowerOff(it6932a_ctrl: IT6932AController):
    return it6932a_ctrl.power_off()


def IT6932AController_GetCurrent(it6932a_ctrl: IT6932AController):
    return it6932a_ctrl.get_current()


def IT6932AController_GetVoltage(it6932a_ctrl: IT6932AController):
    return it6932a_ctrl.get_voltage()


def IT6932AController_SetCurrent(it6932a_ctrl: IT6932AController, current):
    return it6932a_ctrl.set_current(current)


def IT6932AController_SetVoltage(it6932a_ctrl: IT6932AController, voltage):
    return it6932a_ctrl.set_voltage(voltage)


if __name__ == '__main__':
    # status, ctrl = IT6932AController_Init()
    # ctrl.open_usb()
    # IT6932AController_PowerOn(ctrl)
    # print(f"currentֵ={IT6932AController_GetCurrent(ctrl)}")
    # print(f"voltage={IT6932AController_GetVoltage(ctrl)}")

    # IT6932AController_SetCurrent(ctrl,5)
    # IT6932AController_SetVoltage(ctrl,13)
    # IT6932AController_PowerOff(ctrl)
    # IT6932AController_Deinit(ctrl)
    # print(ctrl.get_voltage())
    # ctrl.power_on()
    # ctrl.set_local()
    # ctrl.set_voltage(13)
    # ctrl.set_current(7.5)
    # ctrl.power_off()
    # ctrl.set_rst()
    ctrl = IT6932AController()
    print(ctrl.open_usb())
    # ctrl.set_voltage(13)
    # ctrl.set_current(5)
    # # ctrl.set_local()
    print(ctrl.get_current())
    print(ctrl.get_voltage())