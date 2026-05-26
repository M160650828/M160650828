from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from ._base import Fmt


@dataclass
class LINInfoCfg:
    raw: Dict[str, Any]

    @property
    def GeneralParameters(self) -> Any:
        return self.raw.get("GeneralParameters")

    @property
    def Vnormal(self) -> float:
        return Fmt.as_float(self.raw.get("Vnormal", 12.0), 12.0)

    @property
    def VlowStand(self) -> float:
        return Fmt.as_float(self.raw.get("VlowStand", 8.0), 8.0)

    @property
    def VhighStand(self) -> float:
        return Fmt.as_float(self.raw.get("VhighStand", 18.0), 18.0)

    @property
    def Vstep(self) -> float:
        return Fmt.as_float(self.raw.get("Vstep", 0.1), 0.1)

    @property
    def VtestRange(self) -> float:
        return Fmt.as_float(self.raw.get("VtestRange", 2.0), 2.0)

    @property
    def TvStepDelay_ms(self) -> int:
        return Fmt.as_int(self.raw.get("TvStepDelay", 500), 500)

    @property
    def TvStepDelay_s(self) -> float:
        return Fmt.ms_to_s(self.TvStepDelay_ms, 500)

    @property
    def TfaultRecoveryMax_ms(self) -> int:
        return Fmt.as_int(self.raw.get("TfaultRecoveryMax", 600), 600)

    @property
    def TdefaultWait_s(self) -> float:
        return Fmt.ms_to_s(self.raw.get("TdefaultWait", 1000), 1000)

    @property
    def TdefaultWait_ms(self) -> int:
        return Fmt.as_int(self.raw.get("TdefaultWait", 1000), 1000)

    @property
    def TfaultDelay_min(self) -> int:
        return Fmt.as_int(self.raw.get("TfaultDelay", 1), 1)

    @property
    def TfaultDelay_s(self) -> float:
        try:
            return float(self.TfaultDelay_min) * 60.0
        except Exception:
            return 60.0

    @property
    def Tawake_ms(self) -> int:
        return Fmt.as_int(self.raw.get("Tawake", 100), 100)

    @property
    def Tawake_s(self) -> float:
        return Fmt.ms_to_s(self.Tawake_ms, 100)

    @property
    def NdefaultRepeat(self) -> int:
        return Fmt.as_int(self.raw.get("NdefaultRepeat", 0), 0)

    @property
    def NfaultRepeat(self) -> int:
        return Fmt.as_int(self.raw.get("NfaultRepeat", 0), 0)

    @property
    def RespId_int(self) -> int:
        return Fmt.hx(self.raw.get("RespId", 0), 0)

    @property
    def SimulationActivate(self) -> int:
        return Fmt.as_int(self.raw.get("SimulationActivate", 0), 0)

    @property
    def BRnominal(self) -> int:
        return Fmt.as_float(self.raw.get("BRnominal", 19.2), 19.2)

    @property
    def BRdeviationominal(self) -> int:
        return Fmt.as_int(self.raw.get("BRdeviation", 2), 2)

    @property
    def TdriftDelay(self) -> int:
        return Fmt.as_int(self.raw.get("TdriftDelay", 1), 1)

    @property
    def VgroundDrift(self) -> int:
        return Fmt.as_float(self.raw.get("VgroundDrift", 2), 2)

    @property
    def SlopeMin(self) -> int:
        return Fmt.as_float(self.raw.get("SlopeMin", 1), 1)

    @property
    def SlopeMax(self) -> int:
        return Fmt.as_float(self.raw.get("SlopeMax", 3), 3)

    @property
    def DutyRatio_min(self) -> int:
        return Fmt.as_float(self.raw.get("DutyRatio1", 0.396), 0.396)

    @property
    def DutyRatio_max(self) -> int:
        return Fmt.as_float(self.raw.get("DutyRatio2", 0.581), 0.581)

    @property    
    def SleepCurrent(self) -> int:
        return Fmt.as_float(self.raw.get("Isleep", 0.006), 0.006)  
    
    @property    
    def SilentTime(self) -> int:
        return Fmt.as_float(self.raw.get("SilentTime", 5), 5)  

    @property    
    def TperiodDeviation(self) -> int:
        return Fmt.as_float(self.raw.get("TperiodDeviation", 10), 10)  