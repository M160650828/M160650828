import time
import traceback

import pyvisa


class SDM3055XEConsts:
    # 电阻量程范围
    RES_AUTO = "AUTO"
    RES_200 = str(200)
    RES_2K = str(2 * 1000)
    RES_20K = str(20 * 1000)
    RES_200K = str(200 * 1000)
    RES_2M = str(2 * 1000 * 1000)
    RES_10M = str(10 * 1000 * 1000)
    RES_100M = str(100 * 1000 * 1000)

    VOL_AUTO = "AUTO"
    VOL_200MV = "200mV"
    VOL_2V = "2V"
    VOL_200V = "200V"
    VOL_DC_1000V = "1000V"
    VOL_AC_750V = "750V"

    CUR_AUTO = "AUTO"
    CUR_200UA = "200uA"
    CUR_2MA = "2mA"
    CUR_20MA = "20mA"
    CUR_200MA = "200mA"
    CUR_2A = "2A"
    CUR_10A = "10A"

    CAP_AUTO = "AUTO"
    CAP_2NF = "2nF"
    CAP_20NF = "20nF"
    CAP_200NF = "200nF"
    CAP_2uF = "2uF"
    CAP_20uF = "20uF"
    CAP_200uF = "200uF"
    CAP_10000uF = "10000uF"


class SDM3055XEController:
    def __init__(self):
        self.name = "SDM3055"
        self.rm = pyvisa.ResourceManager()
        self.instrument = None

    def open_tcp(self, ip):
        qstr = f"TCPIP0::{ip}::inst0::INSTR"
        try:
            self.instrument = self.rm.open_resource(qstr, read_termination="\n", write_termination="\n")
        except Exception as e:
            return False, traceback.format_exc()
        return True, None

    def open_usb(self):
        qstr = f"USB?::?*::?*::?*::INSTR"
        results = self.rm.list_resources(qstr)
        if len(results) == 0:
            return False, f"No Found SDM Device"

        for item in results:
            try:
                self.instrument = self.rm.open_resource(item, read_termination="\n", write_termination="\n")
                device_info = self.get_idn()
                if "SDM3055" in str(device_info):
                    self.instrument.timeout = 2000  # default value is 2000(2s)
                    self.instrument.chunk_size = 20 * 1024 * 1024  # default value is 20*1024(20k bytes)
                    self.instrument.write_termination = '\n'  # 写入终止字符
                    # self.instrument.read_termination = '\r'  # 读取终止字符
                    return True, device_info
            except Exception as e:
                print(e)
                return False, traceback.format_exc()

        return False, "SDM3055连接失败"

    def get_idn(self):
        if self.instrument is None:
            return False, "No Connect"
        return True, self.instrument.query("*IDN?")

    def measure_base(self, cmd_conf, cmd_measure, retry=3):
        if self.instrument is None:
            return False, "No Connect"

        err_list = []
        for i in range(retry):
            try:
                # 设置电阻测量模式
                self.instrument.write(cmd_conf)
                time.sleep(0.2)

                # 测量电阻
                result = self.instrument.query(cmd_measure)
                if result == "+9.90000000E+37":
                    return False, eval("+9.90000000E+37")

                return True, eval(result)
            except Exception as e:
                err_list.append(traceback.format_exc())
                continue
        return False, ""

    def measure_resistance(self, measure_range=SDM3055XEConsts.RES_AUTO, retry=3) -> (bool, float):
        return self.measure_base(f"CONFigure:RESistance {measure_range}",
                                 f"MEASure:RESistance? {measure_range}", retry=retry)

    def measure_voltage(self, measure_range=SDM3055XEConsts.VOL_AUTO, retry=3) -> (bool, float):
        return self.measure_base(f"CONFigure:VOLTage:DC {measure_range}",
                                 f"MEASure:VOLTage:DC? {measure_range}", retry=retry)

    def measure_current(self, measure_range=SDM3055XEConsts.CUR_AUTO, retry=3) -> (bool, float):
        return self.measure_base(f"CONFigure:CURRent:DC {measure_range}",
                                 f"MEASure:CURRent:DC? {measure_range}", retry=retry)

    def measure_capacitance(self, measure_range=SDM3055XEConsts.CAP_AUTO, retry=3) -> (bool, float):
        return self.measure_base(f"CONFigure:CAPacitance {measure_range}",
                                 f"MEASure:CAPacitance? {measure_range}", retry=retry)

    def close(self):
        self.instrument.close()

    def deinit(self):
        try:
            self.close()
            return True, ""
        except:
            return False, f"deinit failed: {traceback.format_exc()}"


def SDM3055_Init(ip=None):
    """
        @brief: 初始化万用表
        @param ip: 如果是空的，则使用USB的方式进行连接，否则直接使用指定的IP地址，通过以太网连接
        @return: (status, 万用表的控制句柄)
    """
    multimeter_ctrl = SDM3055XEController()
    if ip is None:
        status, msg = multimeter_ctrl.open_usb()
    else:
        status, msg = multimeter_ctrl.open_tcp(ip)
    if not status:
        return False, msg
    return True, multimeter_ctrl


def SDM3055_MeasureVoltage(ctrl: SDM3055XEController, measure_range=SDM3055XEConsts.VOL_AUTO, retry=3) -> (bool, float):
    """
        @brief: 测量电压
        @param ctrl: 万用表的控制句柄
        @param measure_range: 量程，SDM3055XEConsts中VOL_开头的参数
        @param retry: 尝试次数，可能会存在接口调用失败的情况，默认最多尝试3次
        @return: (status, 测量值)
    """
    return ctrl.measure_voltage(measure_range=measure_range, retry=retry)


def SDM3055_MeasureCurrent(ctrl: SDM3055XEController, measure_range=SDM3055XEConsts.CUR_AUTO, retry=3) -> (bool, float):
    """
        @brief: 测量电流
        @param ctrl: 万用表的控制句柄
        @param measure_range: 量程，SDM3055XEConsts中VOL_开头的参数
        @param retry: 尝试次数，可能会存在接口调用失败的情况，默认最多尝试3次
        @return: (status, 测量值)
    """
    return ctrl.measure_current(measure_range=measure_range, retry=retry)


def SDM3055_MeasureCapacitance(ctrl: SDM3055XEController, measure_range=SDM3055XEConsts.CAP_AUTO, retry=3) -> (bool, float):
    """
        @brief: 测量电电容
        @param ctrl: 万用表的控制句柄
        @param measure_range: 量程，SDM3055XEConsts中VOL_开头的参数
        @param retry: 尝试次数，可能会存在接口调用失败的情况，默认最多尝试3次
        @return: (status, 测量值)
    """
    return ctrl.measure_capacitance(measure_range=measure_range, retry=retry)


def SDM3055_MeasureResistance(ctrl: SDM3055XEController, measure_range=SDM3055XEConsts.RES_AUTO, retry=3) -> (bool, float):
    """
        @brief: 测量电阻
        @param ctrl: 万用表的控制句柄
        @param measure_range: 量程，SDM3055XEConsts中VOL_开头的参数
        @param retry: 尝试次数，可能会存在接口调用失败的情况，默认最多尝试3次
        @return: (status, 测量值)
    """
    return ctrl.measure_resistance(measure_range=measure_range, retry=retry)


def SDM3055_DeInit(ctrl: SDM3055XEController):
    """
        @brief: 资源回收
        @param ctrl: 万用表的控制句柄
    """
    ctrl.deinit()


if __name__ == '__main__':
    # ctrl = SDM3055XEController()
    # status, msg = ctrl.open_usb()
    # if not status:
    #     raise Exception(msg)
    # # print(ctrl.measure_capacitance(SDM3055XEConsts.CAP_2NF))
    # # print(ctrl.measure_voltage(SDM3055XEConsts.VOL_200V))
    # print(ctrl.measure_resistance(SDM3055XEConsts.RES_200K))
    # # print(ctrl.measure_current(SDM3055XEConsts.CUR_2MA))

    ctrl = SDM3055XEController()
    status, msg = ctrl.open_tcp("10.11.13.220")
    # if not status:
    #     raise Exception(msg)
    # # print(ctrl.measure_capacitance(SDM3055XEConsts.CAP_2NF))
    # # print(ctrl.measure_voltage(SDM3055XEConsts.VOL_200V))
    print(ctrl.measure_resistance(SDM3055XEConsts.RES_200K))
    # print(ctrl.measure_current(SDM3055XEConsts.CUR_2MA))
