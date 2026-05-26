from library.devices.multimeter_manager.fluke8846 import (Fluke8846_Init,
                                                          Fluke8846Controller,
                                                          Fluke8846_DeInit,
                                                          Fluke8846_MeasureVoltage,
                                                          Fluke8846_MeasureCurrent,
                                                          Fluke8846_MeasureCapacitance,
                                                          Fluke8846_MeasureResistance)
from library.devices.multimeter_manager.sdm3055_x_e import (SDM3055_Init,
                                                            SDM3055XEController,
                                                            SDM3055_DeInit,
                                                            SDM3055_MeasureVoltage,
                                                            SDM3055_MeasureCurrent,
                                                            SDM3055_MeasureCapacitance,
                                                            SDM3055_MeasureResistance)


def Multimeter_Init(name, **kwargs):
    """
        @brief: 初始化万用表
        @return: (status, 万用表的控制句柄)
    """
    if "fluke" in str(name).lower():
        port = kwargs.get("port")
        baudrate = int(kwargs.get("baudrate", 9600))
        return Fluke8846_Init(port, baudrate)
    elif "sdm" in str(name).lower():
        ip = kwargs.get("ip", None)
        return SDM3055_Init(ip=ip)
    else:
        return False, "invalid multemeter name, only [fluke8846, sdm3055]"


def Multimeter_MeasureVoltage(ctrl: Fluke8846Controller or SDM3055XEController) -> (bool, float):
    """
        @brief: 测量电压
        @param ctrl: 万用表的控制句柄
        @return: (status, 测量值)
    """
    if "fluke" in str(ctrl.name).lower():
        return SDM3055_MeasureVoltage(ctrl)
    elif "sdm" in str(ctrl.name).lower():
        return Fluke8846_MeasureVoltage(ctrl)
    else:
        return False, "invalid multemeter name, only [fluke8846, sdm3055]"


def Multimeter_MeasureCurrent(ctrl: Fluke8846Controller or SDM3055XEController) -> (bool, float):
    """
        @brief: 测量电流
        @param ctrl: 万用表的控制句柄
        @return: (status, 测量值)
    """
    if "fluke" in str(ctrl.name).lower():
        return SDM3055_MeasureCurrent(ctrl)
    elif "sdm" in str(ctrl.name).lower():
        return Fluke8846_MeasureCurrent(ctrl)
    else:
        return False, "invalid multemeter name, only [fluke8846, sdm3055]"


def Multimeter_MeasureCapacitance(ctrl: Fluke8846Controller or SDM3055XEController) -> (bool, float):
    """
        @brief: 测量电电容
        @param ctrl: 万用表的控制句柄
        @return: (status, 测量值)
    """
    if "fluke" in str(ctrl.name).lower():
        return SDM3055_MeasureCapacitance(ctrl)
    elif "sdm" in str(ctrl.name).lower():
        return Fluke8846_MeasureCapacitance(ctrl)
    else:
        return False, "invalid multemeter name, only [fluke8846, sdm3055]"


def Multimeter_MeasureResistance(ctrl: Fluke8846Controller or SDM3055XEController) -> (bool, float):
    """
        @brief: 测量电阻
        @param ctrl: 万用表的控制句柄
        @return: (status, 测量值)
    """
    if "fluke" in str(ctrl.name).lower():
        return SDM3055_MeasureResistance(ctrl)
    elif "sdm" in str(ctrl.name).lower():
        return Fluke8846_MeasureResistance(ctrl)
    else:
        return False, "invalid multemeter name, only [fluke8846, sdm3055]"


def Multimeter_DeInit(ctrl: Fluke8846Controller or SDM3055XEController):
    """
        @brief: 资源回收
        @param ctrl: 万用表的控制句柄
    """
    if "fluke" in str(ctrl.name).lower():
        return Fluke8846_DeInit(ctrl)
    elif "sdm" in str(ctrl.name).lower():
        return SDM3055_DeInit(ctrl)
    else:
        return False, "invalid multemeter name, only [fluke8846, sdm3055]"
