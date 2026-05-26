import time
import traceback

import serial


class Fluke8846Controller:
    def __init__(self, port, baudrate=9600, bytesize=8, stopbits=2):
        """
            @param port: 串口号，e.g. “COM7”。包含大写的"COM"
            @param baudrate: 波特率，默认9600
        """
        self.name = "Fluke8846"
        self.ser = serial.Serial()  # 获取串口
        self.ser.port = port  # 设置端口号
        self.ser.baudrate = baudrate  # 设置波特率
        self.ser.bytesize = bytesize  # 设置数据位
        self.ser.stopbits = stopbits  # 设置停止位

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
        return b""

    def write(self, bytes_data):
        """
            发送数据
        """
        self.open()  # 打开串口,要找到对的串口号才会成功
        self.ser.write(bytes_data)
        # self.close()

    def set_rst(self):
        self.ser.write(b"*RST\n")
        time.sleep(2)

    def set_language(self):
        self.ser.write(b"L1\n")
        time.sleep(2)

    def set_remote_ctrl(self):
        self.ser.write(b"SYSTem:REMote\n")
        time.sleep(2)

    def set_local_ctrl(self):
        self.ser.write(b"SYSTem:LOCal\n")
        time.sleep(2)

    def init(self):
        self.open()
        self.set_rst()
        self.set_language()
        self.set_remote_ctrl()

    def deinit(self):
        try:
            self.set_local_ctrl()
            self.close()
            return True, ""
        except:
            return False, f"deinit failed: {traceback.format_exc()}"

    def measure_base(self, cmd, error_info=""):
        try:
            result = self.write_read(cmd)
            if not result:
                return False, -1
            return True, float(result.decode())
        except Exception as e:
            return False, f"{error_info}: {traceback.format_exc()}"

    def measure_voltage(self):
        return self.measure_base(b"MEASure:VOLTage:DC?\n", "measure_voltage failed")

    def measure_current(self):
        return self.measure_base(b"MEASure:CURRent:DC?\n", "measure_current failed")

    def measure_resistance(self):
        return self.measure_base(b"MEASure:RESistance?\n", "measure_resistance failed")

    def measure_capacitance(self):
        return self.measure_base(b"MEASure:CAPacitance?\n", "measure_capacitance failed")


def Fluke8846_Init(port, baudrate=9600):
    """
        @brief: 初始化万用表
        @return: (status, 万用表的控制句柄)
    """
    multimeter_ctrl = Fluke8846Controller(port, baudrate)
    try:
        multimeter_ctrl.init()
        return True, multimeter_ctrl
    except Exception as e:
        return False, f"Fluke8846_Init Failed: {traceback.format_exc()}"


def Fluke8846_MeasureVoltage(ctrl: Fluke8846Controller) -> (bool, float):
    """
        @brief: 测量电压
        @param ctrl: 万用表的控制句柄
        @return: (status, 测量值)
    """
    return ctrl.measure_voltage()


def Fluke8846_MeasureCurrent(ctrl: Fluke8846Controller) -> (bool, float):
    """
        @brief: 测量电流
        @param ctrl: 万用表的控制句柄
        @return: (status, 测量值)
    """
    return ctrl.measure_current()


def Fluke8846_MeasureCapacitance(ctrl: Fluke8846Controller) -> (bool, float):
    """
        @brief: 测量电电容
        @param ctrl: 万用表的控制句柄
        @return: (status, 测量值)
    """
    return ctrl.measure_capacitance()


def Fluke8846_MeasureResistance(ctrl: Fluke8846Controller) -> (bool, float):
    """
        @brief: 测量电阻
        @param ctrl: 万用表的控制句柄
        @return: (status, 测量值)
    """
    return ctrl.measure_resistance()


def Fluke8846_DeInit(ctrl: Fluke8846Controller):
    """
        @brief: 资源回收
        @param ctrl: 万用表的控制句柄
    """
    ctrl.deinit()
