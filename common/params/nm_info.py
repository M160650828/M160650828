from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from ._base import Fmt


@dataclass
class NMInfoCfg:
    raw: Dict[str, Any]

    # 电压
    @property
    def Vnormal(self) -> float:
        return Fmt.as_float(self.raw.get("Vnormal", 12.0), 12.0)

    @property
    def TrepeatMessage_ms(self) -> int:
        return Fmt.as_int(self.raw.get("TrepeatMessage", 1500), 1500)

    @property
    def TrepeatMessage_s(self) -> float:
        return Fmt.ms_to_s(self.TrepeatMessage_ms, 1500)

    @property
    def TnormalCycle_ms(self) -> int:
        return Fmt.as_int(self.raw.get("TnormalCycle", 500), 500)

    @property
    def TnormalCycle_s(self) -> float:
        return Fmt.ms_to_s(self.TnormalCycle_ms, 500)

    @property
    def TimmediateCycle_ms(self) -> int:
        return Fmt.as_int(self.raw.get("TimmediateCycle", 20), 20)

    @property
    def TimmediateCycle_s(self) -> float:
        return Fmt.ms_to_s(self.TimmediateCycle_ms, 20)

    # 上电/唤醒/超时
    @property
    def TpowerOnInitial_s(self) -> float:
        return Fmt.as_float(self.raw.get("TpowerOnInitial", 5), 5.0)

    @property
    def TpowerOnInitial_ms(self) -> int:
        try:
            return int(self.TpowerOnInitial_s * 1000)
        except Exception:
            return 5000

    @property
    def TactiveWakeup_ms(self) -> int:
        return Fmt.as_int(self.raw.get("TactiveWakeup", 100), 100)

    @property
    def TactiveWakeup_s(self) -> float:
        return Fmt.ms_to_s(self.TactiveWakeup_ms, 100)

    @property
    def TpassiveWakeup_ms(self) -> int:
        return Fmt.as_int(self.raw.get("TpassiveWakeup", 100), 100)

    @property
    def TpassiveWakeup_s(self) -> float:
        return Fmt.ms_to_s(self.TpassiveWakeup_ms, 100)

    @property
    def GeneralParameters(self) -> Any:
        return self.raw.get("GeneralParameters")

    @property
    def NMmsgIDMin_int(self) -> int:
        return Fmt.hx(self.raw.get("NMmsgIDMin", 0), 0)

    @property
    def NMmsgIDMax_int(self) -> int:
        return Fmt.hx(self.raw.get("NMmsgIDMax", 0), 0)

    @property
    def TwakeupTimeout_ms(self) -> int:
        return Fmt.as_int(self.raw.get("TwakeupTimeout", 10000), 10000)

    @property
    def TwakeupTimeout_s(self) -> float:
        return Fmt.ms_to_s(self.TwakeupTimeout_ms, 10000)

    @property
    def TNMtimeout_ms(self) -> int:
        return Fmt.as_int(self.raw.get("TNMtimeout", 2000), 2000)

    @property
    def TNMtimeout_s(self) -> float:
        return Fmt.ms_to_s(self.TNMtimeout_ms, 2000)

    @property
    def TactiveKeep_s(self) -> float:
        return Fmt.as_float(self.raw.get("TactiveKeep", 1.0), 1.0)

    @property
    def TactiveKeep_ms(self) -> int:
        try:
            return int(self.TactiveKeep_s * 1000)
        except Exception:
            return 1000

    @property
    def TpassiveKeep_s(self) -> float:
        return Fmt.as_float(self.raw.get("TpassiveKeep", 1.0), 1.0)

    @property
    def TpassiveKeep_ms(self) -> int:
        try:
            return int(self.TpassiveKeep_s * 1000)
        except Exception:
            return 1000

    @property
    def TactiveKeep_min(self) -> float:
        return Fmt.as_float(self.raw.get("TactiveKeep", 1.0), 1.0)

    @property
    def TactiveKeepLong_ms(self) -> int:
        try:
            return int(self.TactiveKeep_min * 60 * 1000)
        except Exception:
            return 60000

    @property
    def TpassiveKeep_min(self) -> float:
        return Fmt.as_float(self.raw.get("TpassiveKeep", 1.0), 1.0)

    @property
    def TpassiveKeepLong_ms(self) -> int:
        try:
            return int(self.TpassiveKeep_min * 60 * 1000)
        except Exception:
            return 60000

    @property
    def NimmediateSend(self) -> int:
        return Fmt.as_int(self.raw.get("NimmediateSend", 10), 10)

    @property
    def TimmediateDeviation_pct(self) -> float:
        return Fmt.as_float(self.raw.get("TimmediateDeviation", 20.0), 20.0)

    @property
    def TnormalDeviation_pct(self) -> float:
        return Fmt.as_float(self.raw.get("TnormalDeviation", 10.0), 10.0)

    @property
    def RepeatMessageBit0(self) -> int:
        return Fmt.as_int(self.raw.get("RepeatMessageBit0", 0), 0)

    @property
    def ReptMsgBit0(self) -> int:
        return Fmt.as_int(self.raw.get("ReptMsgBit0", 0), 0)

    @property
    def WakeUpHardWireType(self) -> int:
        return Fmt.as_int(self.raw.get("WakeUpHardWireType", 0), 0)

    @property
    def TenableTx_ms(self) -> int:
        return Fmt.as_int(self.raw.get("TenableTx", 0), 0)

    @property
    def TinitialCycle_ms(self) -> int:
        return Fmt.as_int(self.raw.get("TinitialCycle", 0), 0)

    @property
    def TlongKeep_min(self) -> float:
        return Fmt.as_float(self.raw.get("TlongKeep", 1.0), 1.0)

    @property
    def TlongKeep_ms(self) -> int:
        try:
            return int(self.TlongKeep_min * 60 * 1000)
        except Exception:
            return 60000

    @property
    def NtimeRepeat(self) -> int:
        return Fmt.as_int(self.raw.get("NtimeRepeat", 0), 0)

    @property
    def TwaitBusIdle_ms(self) -> int:
        return Fmt.as_int(self.raw.get("TwaitBusIdle", 0), 0)

    @property
    def SpecificlParameters(self) -> Any:
        return self.raw.get("SpecificlParameters")

    @property
    def TwaitBusSleep_ms(self) -> int:
        return Fmt.as_int(self.raw.get("TwaitBusSleep", 0), 0)

    @property
    def Tstartup_ms(self) -> int:
        return Fmt.as_int(self.raw.get("Tstartup", 0), 0)

    @property
    def CalibrationParameters(self) -> Any:
        return self.raw.get("CalibrationParameters")

    @property
    def ReserveBit1(self) -> int:
        return Fmt.as_int(self.raw.get("ReserveBit1", 0), 0)

    @property
    def ReserveBit2(self) -> int:
        return Fmt.as_int(self.raw.get("ReserveBit2", 0), 0)

    @property
    def ReserveBit3(self) -> int:
        return Fmt.as_int(self.raw.get("ReserveBit3", 0), 0)

    @property
    def ReserveBit4(self) -> int:
        return Fmt.as_int(self.raw.get("ReserveBit4", 0), 0)

    @property
    def ReserveBit5(self) -> int:
        return Fmt.as_int(self.raw.get("ReserveBit5", 0), 0)

    @property
    def ReserveBit6(self) -> int:
        return Fmt.as_int(self.raw.get("ReserveBit6", 0), 0)

    @property
    def ReserveBit7(self) -> int:
        return Fmt.as_int(self.raw.get("ReserveBit7", 0), 0)

    @property
    def ActiveWakeupBit4(self) -> int:
        return Fmt.as_int(self.raw.get("ActiveWakeupBit4", 0), 0)

    @property
    def ReserveBitValue(self) -> int:
        return Fmt.as_int(self.raw.get("ReserveBitValue", 0), 0)

    @property
    def NormalStateToRepeatMessageState(self) -> int:
        return Fmt.as_int(self.raw.get("NormalStateToRepeatMessageState", 0), 0)

    @property
    def ReadySleepStateToRepeatMessageState(self) -> int:
        return Fmt.as_int(self.raw.get("ReadySleepStateToRepeatMessageState", 0), 0)

    @property
    def DiagRequestKeepWakeup_NMPDUSend(self) -> int:
        return Fmt.as_int(self.raw.get("DiagRequestKeepWakeup_NMPDUSend", 0), 0)

    @property
    def NMByte0_int(self) -> int:
        return Fmt.hx(self.raw.get("NMByte0", 0), 0) & 0xFF

    @property
    def NMByte1_int(self) -> int:
        return Fmt.hx(self.raw.get("NMByte1", 0), 0) & 0xFF

    @property
    def NMByte2_int(self) -> int:
        return Fmt.hx(self.raw.get("NMByte2", 0), 0) & 0xFF

    @property
    def NMByte3_int(self) -> int:
        return Fmt.hx(self.raw.get("NMByte3", 0), 0) & 0xFF

    @property
    def NMByte4_int(self) -> int:
        return Fmt.hx(self.raw.get("NMByte4", 0), 0) & 0xFF

    @property
    def NMByte5_int(self) -> int:
        return Fmt.hx(self.raw.get("NMByte5", 0), 0) & 0xFF

    @property
    def NMByte6_int(self) -> int:
        return Fmt.hx(self.raw.get("NMByte6", 0), 0) & 0xFF

    @property
    def NMByte7_int(self) -> int:
        return Fmt.hx(self.raw.get("NMByte7", 0), 0) & 0xFF

    @property
    def NM_DLC(self) -> int:
        return Fmt.as_int(self.raw.get("NM_DLC", 8), 8)

    @property
    def IndirectNMParameters(self) -> Any:
        return self.raw.get("IndirectNMParameters")
    
    @property
    def NLoopTime(self) -> int:
        return Fmt.as_int(self.raw.get("NLoopTime", 1), 1)

