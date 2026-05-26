from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from ._base import Fmt

@dataclass
class ProjectInfoCfg:
    raw: Dict[str, Any]

    @property
    def PowerType(self) -> str:
        return str(self.raw.get("PowerType", "HSPY"))

    @property
    def PowerPort(self) -> int:
        return Fmt.as_int(self.raw.get("PowerPort", 5), 5)

    @property
    def PowerPortName(self) -> str:
        return f"COM{self.PowerPort}"

    @property
    def PowerPortParam(self):
        if "wk" in self.PowerType.lower().replace("-", "").replace("_", ""):
            return self.PowerPort  # CAN通道号
        return self.PowerPortName  # 串口名 "COMx"

    @property
    def PowerDeviceAddr(self) -> int:
        return Fmt.as_int(self.raw.get("PowerDeviceAddr", 0), 0)

    @property
    def ECUType(self) -> int:
        return Fmt.as_int(self.raw.get("ECUType", 3), 3)

    @property
    def ECUIndex(self) -> int:
        return Fmt.as_int(self.raw.get("ECUIndex", 1), 1)

    @property
    def PowerOnFun(self) -> str:
        return str(self.raw.get("PowerOnFun", "POWERON"))

    @property
    def DigitalMultimeterType(self) -> str:
        return str(self.raw.get("DigitalMultimeterType", ""))

    @property
    def DigitalMultimeterPort(self) -> int:
        return Fmt.as_int(self.raw.get("DigitalMultimeterPort", 0), 0)

    @property
    def DigitalMultimeterName(self) -> str:
        return str(self.raw.get("DigitalMultimeterName", ""))

    @property
    def PowerSupply(self) -> str:
        return str(self.raw.get("PowerSupply", ""))

    @property
    def PowerName(self) -> str:
        return str(self.raw.get("PowerName", ""))

    @property
    def PowerBaudRate(self) -> int:
        return Fmt.as_int(self.raw.get("PowerBaudRate", 9600), 9600)

    @property
    def QuadrantPower(self) -> str:
        return str(self.raw.get("QuadrantPower", ""))

    @property
    def QuadrantPowerType(self) -> str:
        return str(self.raw.get("QuadrantPowerType", ""))

    @property
    def QuadrantPowerPort(self) -> int:
        return Fmt.as_int(self.raw.get("QuadrantPowerPort", 0), 0)

    @property
    def QuadrantPowerName(self) -> str:
        return str(self.raw.get("QuadrantPowerName", ""))

    @property
    def Scope(self) -> str:
        return str(self.raw.get("Scope", ""))

    @property
    def ScopeType(self) -> str:
        return str(self.raw.get("ScopeType", ""))

    @property
    def KeysightScopeName(self) -> str:
        return str(self.raw.get("KeysightScopeName", ""))

    @property
    def DUT(self) -> str:
        return str(self.raw.get("DUT", ""))

    @property
    def DutConnectType(self) -> str:
        return str(self.raw.get("DutConnectType", ""))

    @property
    def DutPowerOnType(self) -> str:
        return str(self.raw.get("DutPowerOnType", ""))

    @property
    def ECU(self) -> str:
        return str(self.raw.get("ECU", ""))

    @property
    def NetWorkHardwareSN(self) -> str:
        v = self.raw.get("NetWorkHardwareSN", "")
        if v is None:
            return ""
        return str(v)

