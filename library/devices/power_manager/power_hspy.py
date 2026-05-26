import time
import serial
import traceback


class PowerHSPYController:
    def __init__(self, port, baudrate=9600, bytesize=8, stopbits=2, device_addr=0):
        """
            @param port: 串口号，e.g. “COM7”。包含大写的"COM"
            @param baudrate: 波特率，默认9600
            @param device_addr: 程控电源的地址，地址获取：点按旋钮进入配置页面->U/I翻页，找到"RS_Adde"
        """
        self.name = "HSPY"
        self.ser = serial.Serial()  # 获取串口
        self.ser.port = port  # 设置端口号
        self.ser.baudrate = baudrate  # 设置波特率
        self.ser.bytesize = bytesize  # 设置数据位
        self.ser.stopbits = stopbits  # 设置停止位
        self.device_addr = device_addr

    def open(self):
        """
            打开串口
        """
        if not self.ser.is_open:
            self.ser.open()

    def close(self):
        """
            关闭串口
        """
        if self.ser.is_open:
            self.ser.close()

    def write_read(self, bytes_data, timeout=0.001):
        """
            发送数据，并等待响应
        """
        self.open()
        self.ser.timeout = timeout
        # self.ser.write(bytes_data + b"\x0A")
        self.ser.write(bytes_data)
        time.sleep(0.1)
        # 检查缓冲区是否有数据
        if self.ser.in_waiting:
            # 读取缓冲区中的所有数据
            response = self.ser.read(self.ser.in_waiting)
            return response
        return []

    def write(self, bytes_data):
        """
            发送数据
        """
        self.open()  # 打开串口,要找到对的串口号才会成功
        self.ser.write(bytes_data)
        # self.close()

    def modbus_crc16(self, data: bytes):
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc & 0xFFFF

    def set_current(self, current):
        """
            设置电流
        """
        set_bytes = [self.device_addr, 0x10, 0x10, 0x01, 0x00, 0x01, 0x02, 0x03, 0xE8]
        # HSPY 30-10
        # set_bytes[7] = (int(current * 100) >> 8) & 0xFF
        # set_bytes[8] = int(current * 100) & 0xFF
        # HSPY 30-05
        set_bytes[7] = (int(current * 1000) >> 8) & 0xFF
        set_bytes[8] = int(current * 1000) & 0xFF
        crc_byte = self.modbus_crc16(bytearray(set_bytes))
        set_bytes = bytearray(set_bytes) + int.to_bytes(crc_byte, length=2, byteorder="little")
        self.write_read(set_bytes)

    def set_voltage(self, voltage):
        """
            设置电压
        """
        set_bytes = [self.device_addr, 0x10, 0x10, 0x00, 0x00, 0x01, 0x02, 0x0E, 0x10]
        set_bytes[7] = (int(voltage * 100) >> 8) & 0xFF
        set_bytes[8] = int(voltage * 100) & 0xFF
        crc_byte = self.modbus_crc16(bytearray(set_bytes))
        set_bytes = bytearray(set_bytes) + int.to_bytes(crc_byte, length=2, byteorder="little")
        print([hex(i) for i in set_bytes])
        self.write_read(set_bytes)

    def format_voltage(self, result_list):
        if len(result_list) == 0:
            return result_list
        length = result_list[2]
        result = []
        for i in range(3, 3 + length):
            result.append(result_list[i].to_bytes(1))
        result = b"".join(result)
        return int.from_bytes(result) / 100

    def format_current(self, result_list):
        if len(result_list) == 0:
            return result_list
        length = result_list[2]
        result = []
        for i in range(3, 3 + length):
            result.append(result_list[i].to_bytes(1))
        result = b"".join(result)
        # HSPY 30-10
        # return int.from_bytes(result) / 100
        # HSPY 30-05
        return int.from_bytes(result) / 1000

    def format_output_status(self, status_result):
        if len(status_result) == 0:
            return status_result
        length = status_result[2]
        result = []
        for i in range(3, 3 + length):
            result.append(status_result[i].to_bytes(1))
        result = b"".join(result)
        return int.from_bytes(result)

    def read_setting_voltage(self):
        for _ in range(5):
            set_bytes = [self.device_addr, 0x03, 0x10, 0x00, 0x00, 0x01]
            crc_byte = self.modbus_crc16(bytearray(set_bytes))
            set_bytes = bytearray(set_bytes) + int.to_bytes(crc_byte, length=2, byteorder="little")
            results = self.write_read(set_bytes)
            if len(results) != 7:
                time.sleep(0.3)
                continue
            voltage = self.format_voltage(results)
            return voltage
        return -1

    def read_display_voltage(self):
        for _ in range(5):
            set_bytes = [self.device_addr, 0x03, 0x10, 0x02, 0x00, 0x01]
            crc_byte = self.modbus_crc16(bytearray(set_bytes))
            set_bytes = bytearray(set_bytes) + int.to_bytes(crc_byte, length=2, byteorder="little")
            results = self.write_read(set_bytes)
            if len(results) != 7:
                time.sleep(0.3)
                continue
            voltage = self.format_voltage(results)
            return voltage
        return -1

    def read_setting_current(self):
        for _ in range(5):
            set_bytes = [self.device_addr, 0x03, 0x10, 0x01, 0x00, 0x01]
            crc_byte = self.modbus_crc16(bytearray(set_bytes))
            set_bytes = bytearray(set_bytes) + int.to_bytes(crc_byte, length=2, byteorder="little")
            results = self.write_read(set_bytes)
            if len(results) != 7:
                time.sleep(0.3)
                continue
            current = self.format_current(results)
            return current
        return -1

    def read_display_current(self):
        for _ in range(5):
            set_bytes = [self.device_addr, 0x03, 0x10, 0x03, 0x00, 0x01]
            crc_byte = self.modbus_crc16(bytearray(set_bytes))
            set_bytes = bytearray(set_bytes) + int.to_bytes(crc_byte, length=2, byteorder="little")
            results = self.write_read(set_bytes)
            if len(results) != 7:
                time.sleep(0.3)
                continue
            current = self.format_current(results)
            return current
        return -1

    def read_output_status(self):
        for _ in range(5):
            set_bytes = [self.device_addr, 0x03, 0x10, 0x04, 0x00, 0x01]
            crc_byte = self.modbus_crc16(bytearray(set_bytes))
            set_bytes = bytearray(set_bytes) + int.to_bytes(crc_byte, length=2, byteorder="little")
            results = self.write_read(set_bytes)
            if len(results) != 7:
                time.sleep(0.3)
                continue
            status = self.format_output_status(results)
            return status
        return None

    def switch_on(self):
        """
            切换为ON
        """
        set_bytes = [self.device_addr, 0x10, 0x10, 0x04, 0x00, 0x01, 0x02, 0x00, 0x01]
        crc_byte = self.modbus_crc16(bytearray(set_bytes))
        set_bytes = bytearray(set_bytes) + int.to_bytes(crc_byte, length=2, byteorder="little")
        self.write_read(set_bytes)

    def switch_off(self):
        """
            切换为OFF
        """
        set_bytes = [self.device_addr, 0x10, 0x10, 0x04, 0x00, 0x01, 0x02, 0x00, 0x00]
        crc_byte = self.modbus_crc16(bytearray(set_bytes))
        set_bytes = bytearray(set_bytes) + int.to_bytes(crc_byte, length=2, byteorder="little")
        self.write_read(set_bytes)

    def auto_on(self):
        """
            上电自动ON状态，只需要设置一次
        """
        set_bytes = [self.device_addr, 0x10, 0x10, 0x0A, 0x00, 0x01, 0x02, 0x00, 0x01]
        crc_byte = self.modbus_crc16(bytearray(set_bytes))
        set_bytes = bytearray(set_bytes) + int.to_bytes(crc_byte, length=2, byteorder="little")
        self.write_read(set_bytes)

    def auto_off(self):
        """
            上电OFF状态
        """
        set_bytes = [self.device_addr, 0x10, 0x10, 0x0A, 0x00, 0x01, 0x02, 0x00, 0x00]
        crc_byte = self.modbus_crc16(bytearray(set_bytes))
        set_bytes = bytearray(set_bytes) + int.to_bytes(crc_byte, length=2, byteorder="little")
        self.write_read(set_bytes)

    def addressing_check(self, address=None):
        """
        设备寻址
        """
        if address is not None:
            target = [address]
        else:
            target = range(0, 256)
        for i in target:
            set_bytes = [i, 0x03, 0x10, 0x00, 0x00, 0x01]
            crc_byte = self.modbus_crc16(bytearray(set_bytes))
            set_bytes = bytearray(set_bytes) + int.to_bytes(crc_byte, length=2, byteorder="little")
            ret = self.write_read(set_bytes)
            if len(ret) > 0:
                self.device_addr = i  # 设备地址
                return i
        return None


def HSPYController_Init(port="COM3", device_addr=0):
    hspy_ctrl = PowerHSPYController(port, device_addr=device_addr)
    try:
        hspy_ctrl.open()
        return True, hspy_ctrl
    except Exception as e:
        return False, traceback.format_exc()


def HSPYController_Deinit(hspy_ctrl: PowerHSPYController):
    return hspy_ctrl.close()


def HSPYController_PowerOn(hspy_ctrl: PowerHSPYController):
    return hspy_ctrl.switch_on()


def HSPYController_PowerOff(hspy_ctrl: PowerHSPYController):
    return hspy_ctrl.switch_off()


def HSPYController_GetCurrent(hspy_ctrl: PowerHSPYController):
    return hspy_ctrl.read_display_current()


def HSPYController_GetVoltage(hspy_ctrl: PowerHSPYController):
    return hspy_ctrl.read_display_voltage()


def HSPYController_SetCurrent(hspy_ctrl: PowerHSPYController, current):
    return hspy_ctrl.set_current(current)


def HSPYController_SetVoltage(hspy_ctrl: PowerHSPYController, voltage):
    return hspy_ctrl.set_voltage(voltage)


if __name__ == '__main__':
    status, dp = HSPYController_Init("COM3")
    HSPYController_PowerOn(dp)
    HSPYController_PowerOff(dp)
