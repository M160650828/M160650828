from library.devices.bob_manager.ets6124_control import ETS6124Controller
from library.devices.bob_manager.wk5249_control import WK5249Controller


def BobInit(name: str, control_can: int = 2, **kwargs):
    """
    初始化BOB
    """
    name_lower = str(name).lower()

    if name_lower == "ets6124":
        addr = kwargs.get('addr', 0x00)
        power_ch = kwargs.get('power_ch', 1)
        ctrl = ETS6124Controller(control_can=control_can, addr=addr, power_ch=power_ch)
        if ctrl.init():
            return True, ctrl
        return False, "ETS6124 init failed"

    elif name_lower == "wk5249":
        ctrl = WK5249Controller(control_can=control_can)
        if ctrl.init():
            return True, ctrl
        return False, "WK5249 init failed"

    return False, f"BobInit: Unknown BOB name '{name}'"


def BobReset(ctrl):
    """复位BOB"""
    if hasattr(ctrl, 'reset'):
        return (True, "ok") if ctrl.reset() else (False, "reset failed")
    return False, "reset not supported"


def BobSetPower(ctrl, kind: str, on: bool, **kwargs):
    """
    电源控制 
    """
    name = _get_ctrl_name(ctrl)

    if name == "ets6124":
        ch = kwargs.get('ch', None)
        return (True, "ok") if ctrl.set_power(kind, on, ch) else (False, "fail")

    elif name == "wk5249":
        return (True, "ok") if ctrl.set_power(kind, on) else (False, "fail")

    return False, f"BobSetPower: Unknown controller"


def BobSetFault(ctrl, target: str, kind: str, enable: bool = True):
    """
    故障注入
    """
    name = _get_ctrl_name(ctrl)
    
    if name == "ets6124":
        return (True, "ok") if ctrl.set_fault(target, kind, enable) else (False, "fail")
    
    elif name == "wk5249":
        ctrl.set_test_channel(target, enable)
        if target.upper().startswith('LIN'):
            return (True, "ok") if ctrl.set_lin_fault(kind, enable) else (False, "fail")
        else:
            return (True, "ok") if ctrl.set_can_fault(target, kind, enable) else (False, "fail")
    
    return False, f"BobSetFault: Unknown controller"


def BobSetResistance(ctrl, ohm: int, enable: bool = True, **kwargs):
    """
    设置终端电阻
    """
    name = _get_ctrl_name(ctrl)
    
    if name == "ets6124":
        ch = kwargs.get('ch', None)
        return (True, "ok") if ctrl.set_can_tr120(enable, ch) else (False, "fail")
    
    elif name == "wk5249":
        return (True, "ok") if ctrl.set_resistance(ohm, enable) else (False, "fail")
    
    return False, f"BobSetResistance: Unknown controller"


def BobSetDevice(ctrl, device: str, enable: bool = True):
    """
    设置外接设备 (仅WK5249)
    
    Args:
        ctrl: 控制器
        device: SCOPE, VH6501, MUL, LIN_SG
        enable: True=接入, False=断开
    """
    name = _get_ctrl_name(ctrl)
    
    if name == "wk5249":
        return (True, "ok") if ctrl.set_device(device, enable) else (False, "fail")
    
    return False, f"BobSetDevice: Not supported for {name}"


def BobSetTestChannel(ctrl, channel: str, enable: bool = True):
    """
    设置测试通道 (仅WK5249)
    
    Args:
        ctrl: 控制器
        channel: CAN1, CAN2, LIN1, LIN2
        enable: True=测试通道, False=直连通道
    """
    name = _get_ctrl_name(ctrl)
    
    if name == "wk5249":
        return (True, "ok") if ctrl.set_test_channel(channel, enable) else (False, "fail")
    
    return False, f"BobSetTestChannel: Not supported for {name}"


def BobReadCurrent(ctrl, **kwargs):
    """读取电流 (mA), 仅ETS6124"""
    name = _get_ctrl_name(ctrl)
    
    if name == "ets6124":
        ch = kwargs.get('ch', None)
        timeout = kwargs.get('timeout', 0.5)
        current = ctrl.read_current(ch, timeout)
        return (True, current) if current is not None else (False, None)
    
    return False, f"BobReadCurrent: Not supported for {name}"


def BobReadVoltage(ctrl, **kwargs):
    """读取电压 (V), 仅ETS6124"""
    name = _get_ctrl_name(ctrl)
    
    if name == "ets6124":
        ch = kwargs.get('ch', None)
        timeout = kwargs.get('timeout', 0.5)
        voltage = ctrl.read_voltage(ch, timeout)
        return (True, voltage) if voltage is not None else (False, None)
    
    return False, f"BobReadVoltage: Not supported for {name}"


def _get_ctrl_name(ctrl) -> str:
    if isinstance(ctrl, ETS6124Controller):
        return "ets6124"
    elif isinstance(ctrl, WK5249Controller):
        return "wk5249"
    return "unknown"

