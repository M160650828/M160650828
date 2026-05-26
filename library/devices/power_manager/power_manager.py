from library.devices.power_manager.power_hspy import HSPYController_Init, PowerHSPYController
from library.devices.power_manager.power_it6932A import IT6932AController_Init, IT6932AController
from library.devices.power_manager.power_wk_ps import WKPSController_Init, PowerWKPSController


def PowerInit(name="ITECH", port="COM3", device_addr=0):
    name_lower = str(name).lower().replace("-", "").replace("_", "")

    if name_lower == "itech":
        status, ctrl = IT6932AController_Init()
    elif name_lower == "hspy":
        status, ctrl = HSPYController_Init(port, int(device_addr))
    elif name_lower == "wkps":
        # port 作为 control_can, device_addr 作为 channel
        control_can = int(port) if isinstance(port, (int, str)) and str(port).isdigit() else 2
        channel = int(device_addr) if device_addr else 1
        status, ctrl = WKPSController_Init(control_can=control_can, channel=channel)
    else:
        return False, "PowerInit: Unknown power manager name"
    if status is True:
        return True, ctrl
    return False, ctrl


def _get_power_type(power_ctrl) -> str:
    """获取电源类型"""
    name = str(power_ctrl.name).lower().replace("-", "").replace("_", "")
    if "itech" in name:
        return "itech"
    elif "hspy" in name:
        return "hspy"
    elif "wkps" in name:
        return "wkps"
    return "unknown"


def PowerDeinit(power_ctrl):
    ptype = _get_power_type(power_ctrl)
    if ptype in ("itech", "hspy", "wkps"):
        return True, power_ctrl.close()
    return False, "PowerDeinit: Unknown power manager name"


def PowerOn(power_ctrl):
    ptype = _get_power_type(power_ctrl)
    if ptype == "itech":
        power_ctrl.power_on()
        return True, "PowerOn: ok"
    elif ptype in ("hspy", "wkps"):
        power_ctrl.switch_on()
        return True, "PowerOn: ok"
    return False, "PowerOn: Unknown power manager name"


def PowerOff(power_ctrl):
    ptype = _get_power_type(power_ctrl)
    if ptype == "itech":
        power_ctrl.power_off()
        return True, "PowerOff: ok"
    elif ptype in ("hspy", "wkps"):
        power_ctrl.switch_off()
        return True, "PowerOff: ok"
    return False, "PowerOff: Unknown power manager name"


def PowerGetCurrent(power_ctrl):
    ptype = _get_power_type(power_ctrl)
    if ptype == "itech":
        return power_ctrl.get_current()
    elif ptype in ("hspy", "wkps"):
        current = power_ctrl.read_display_current()
        if current == -1:
            return False, -1
        return True, current
    return False, "PowerGetCurrent: Unknown power manager name"


def PowerGetVoltage(power_ctrl):
    ptype = _get_power_type(power_ctrl)
    if ptype == "itech":
        return power_ctrl.get_voltage()
    elif ptype in ("hspy", "wkps"):
        voltage = power_ctrl.read_display_voltage()
        if voltage == -1:
            return False, -1
        return True, voltage
    return False, "PowerGetVoltage: Unknown power manager name"


def PowerSetCurrent(power_ctrl, current):
    ptype = _get_power_type(power_ctrl)
    if ptype in ("itech", "hspy", "wkps"):
        power_ctrl.set_current(current)
        return True, "PowerSetCurrent: ok"
    return False, "PowerSetCurrent: Unknown power manager name"


def PowerSetVoltage(power_ctrl, voltage):
    ptype = _get_power_type(power_ctrl)
    if ptype in ("itech", "hspy", "wkps"):
        power_ctrl.set_voltage(voltage)
        return True, "PowerSetVoltage: ok"
    return False, "PowerSetVoltage: Unknown power manager name"


if __name__ == '__main__':
    pwr_name = "HSPY"
    status, ctrl = PowerInit(pwr_name, "COM3")
    PowerSetCurrent(ctrl, 5)
    PowerSetVoltage(ctrl, 12)