import time
import traceback

import pyvisa


class IT6431Controller:
    def __init__(self):
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
            return False, f"No Found SDM Device"

        for item in results:
            try:
                self.inst = self.rm.open_resource(item, read_termination="\n", write_termination="\n")
                device_info = self.get_idn()
                if "SDM" in str(device_info):
                    break
            except Exception as e:
                print(e)
                return False, traceback.format_exc()

        return True, None

    def close(self):
        self.inst.close()

    def get_idn(self):
        """
            获取设备信息
        """
        if self.inst is None:
            return False, "No Connect"
        return True, self.inst.query("*IDN?")

    def set_local(self):
        if self.inst is None:
            return False, "No Connect"
        return True, self.inst.write("SYSTem:LOCal")

    def set_remote(self):
        if self.inst is None:
            return False, "No Connect"
        return True, self.inst.write("SYSTem:REMote")

    def init(self):
        try:
            self.open_usb()
            self.set_remote()
            time.sleep(0.2)
            return True, "init success"
        except:
            return False, f"init failed: {traceback.format_exc()}"

    def deinit(self):
        try:
            self.close()
            return True, "deinit success"
        except:
            return False, f"deinit failed: {traceback.format_exc()}"

    def set_output_on(self):
        if self.inst is None:
            return False, "No Connect"
        self.inst.write("OUTPut ON")
        return True, ""

    def set_output_off(self):
        if self.inst is None:
            return False, "No Connect"
        self.inst.write("OUTPut OFF")
        return True, ""

    def set_voltage(self, voltage):
        if self.inst is None:
            return False, "No Connect"
        if not (voltage <= 15.1):
            return False, f"Voltage must be under 15.1."
        self.inst.write(f"VOLTage {voltage}")
        time.sleep(0.2)
        return True, ""

    def set_current(self, current):
        if self.inst is None:
            return False, "No Connect"
        if not (0.01 <= current <= 10.05):
            return False, f"Current must be between 0.01 and 10.05."
        self.inst.write("CURRent:PROTection:STATe ON")
        time.sleep(0.2)
        self.inst.write(f"CURRent {current}")
        time.sleep(0.2)
        return True, ""

    def get_voltage(self):
        if self.inst is None:
            return False, "No Connect"
        result = self.inst.query("MEASure:VOLTage:ACDC?")
        if result == "+9.90000000E+37":
            return False, eval("+9.90000000E+37")
        return True, eval(result)

    def get_current(self):
        if self.inst is None:
            return False, "No Connect"
        result = self.inst.query("MEASure:CURRent?")
        if result == "+9.90000000E+37":
            return False, eval("+9.90000000E+37")
        return True, eval(result)
