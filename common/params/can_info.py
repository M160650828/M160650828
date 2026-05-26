from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from ._base import Fmt


@dataclass
class CANInfoCfg:
    raw: Dict[str, Any]

    @property
    def Vnormal(self) -> float:
        return Fmt.as_float(self.raw.get("Vnormal", 12.0), 12.0)

    @property
    def Tstable_ms(self) -> int:
        return Fmt.as_int(self.raw.get("Tstable", 1000), 1000)

    @property
    def Tstable_s(self) -> float:
        return Fmt.ms_to_s(self.Tstable_ms, 1000)

    @property
    def TdefaultWait_s(self) -> float:
        return Fmt.as_float(self.raw.get("TdefaultWait", 5), 5.0)

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
    def BRarbitration_kbps(self) -> float:
        return Fmt.as_float(self.raw.get("BRarbitration", 500.0), 500.0)

    @property
    def BRarbitration_bps(self) -> float:
        try:
            return float(self.BRarbitration_kbps) * 1000.0
        except Exception:
            return 500000.0

    @property
    def BRdata_kbps(self) -> float:
        return Fmt.as_float(self.raw.get("BRdata", 2000.0), 2000.0)

    @property
    def BRdata_bps(self) -> float:
        try:
            return float(self.BRdata_kbps) * 1000.0
        except Exception:
            return 2000000.0

    @property
    def ExtendMsgID(self) -> int:
        return Fmt.hx(self.raw.get("ExtendMsgID", 0x001), 0x001)

    @property
    def ExtendandRemoteMsgID(self) -> int:
        return Fmt.hx(self.raw.get("ExtendandRemoteMsgID", 0x001), 0x001)

    @property
    def RemoteMsgID(self) -> int:
        return Fmt.hx(self.raw.get("RemoteMsgID", 0x001), 0x001)

    @property
    def ErrorMsgID(self) -> int:
        return Fmt.hx(self.raw.get("ErrorMsgID", 0x001), 0x001)

    @property
    def TvStepDelay_ms(self) -> int:
        return Fmt.as_int(self.raw.get("TvStepDelay", 500), 500)

    @property
    def TvStepDelay_s(self) -> float:
        return Fmt.ms_to_s(self.TvStepDelay_ms, 500)

    @property
    def BusloadNormal_pct(self) -> float:
        return Fmt.as_float(self.raw.get("BusloadNormal", 20.0), 20.0)

    @property
    def BusloadMedium_pct(self) -> float:
        return Fmt.as_float(self.raw.get("BusloadMedium", 50.0), 50.0)

    @property
    def BusloadHigh_pct(self) -> float:
        return Fmt.as_float(self.raw.get("BusloadHigh", 90.0), 90.0)

    @property
    def TperiodDeviation1_pct(self) -> float:
        return Fmt.as_float(self.raw.get("TperiodDeviation1", 10.0), 10.0)

    @property
    def TperiodDeviation2_pct(self) -> float:
        return Fmt.as_float(self.raw.get("TperiodDeviation2", 5.0), 5.0)

    @property
    def TperiodDeviation3_pct(self) -> float:
        return Fmt.as_float(self.raw.get("TperiodDeviation3", 0.0), 0.0)

    @property
    def TperiodDeviation4_pct(self) -> float:
        return Fmt.as_float(self.raw.get("TperiodDeviation4", 0.0), 0.0)

    @property
    def TperiodDeviationDelay_min(self) -> int:
        return Fmt.as_int(self.raw.get("TperiodDeviationDelay", 1), 1)

    @property
    def Tinitial_s(self) -> int:
        return Fmt.as_int(self.raw.get("Tinitial", 0), 0)

    @property
    def Tinitial_min(self) -> float:
        try:
            return float(self.Tinitial_s) / 60.0
        except Exception:
            return 1.0 / 60.0

    @property
    def UnuseBitValue(self) -> int:
        return Fmt.as_int(self.raw.get("UnuseBitValue", 0), 0)

    @property
    def TreceiveMsgDelay_min(self) -> int:
        return Fmt.as_int(self.raw.get("TreceiveMsgDelay", 0), 0)

    @property
    def TreceiveMsgDelay_s(self) -> float:
        try:
            return float(self.TreceiveMsgDelay_min) * 60.0
        except Exception:
            return 60.0

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
    def TfaultRecoveryMax_ms(self) -> int:
        return Fmt.as_int(self.raw.get("TfaultRecoveryMax", 600), 600)

    @property
    def TfaultRecoveryMax_s(self) -> float:
        return Fmt.ms_to_s(self.TfaultRecoveryMax_ms, 600)

    @property
    def NdefaultRepeat(self) -> int:
        return Fmt.as_int(self.raw.get("NdefaultRepeat", 1), 1)

    @property
    def NfaultRepeat(self) -> int:
        return Fmt.as_int(self.raw.get("NfaultRepeat", 1), 1)

    @property
    def Tcount(self) -> int:
        return Fmt.as_int(self.raw.get("Tcount", 10), 10)

    @property
    def TwakeupMax_ms(self) -> int:
        return Fmt.as_int(self.raw.get("TwakeupMax", 100), 100)

    def PowerModeMsgID(self) -> int:
        return Fmt.hx(self.raw.get("PowerModeMsgID", 1), 1)

    @property
    def SpeedMsgID(self) -> int:
        return Fmt.hx(self.raw.get("SpeedMsgID", 1), 1)

    @property
    def TimeMsgID(self) -> int:
        return Fmt.hx(self.raw.get("TimeMsgID", 1), 1)

    @property
    def EngineSpeedMsgID(self) -> int:
        return Fmt.hx(self.raw.get("EngineSpeedMsgID", 1), 1)

    @property
    def GearMsgID(self) -> int:
        return Fmt.hx(self.raw.get("GearMsgID", 1), 1)

    @property
    def OccurrenceCounterExtendedDataID(self) -> int:
        return Fmt.hx(self.raw.get("OccurrenceCounterExtendedDataID", 0x0), 0x0)

    @property
    def OccurrenceCounterByteIndex(self) -> int:
        return Fmt.as_int(self.raw.get("OccurrenceCounterByteIndex", 0), 0)

    @property
    def AgeingCounterExtendedDataID(self) -> int:
        return Fmt.hx(self.raw.get("AgeingCounterExtendedDataID", 0x0), 0x0)

    @property
    def AgeingCounterByteIndex(self) -> int:
        return Fmt.as_int(self.raw.get("AgeingCounterByteIndex", 0), 0)

    @property
    def OperationCycle(self) -> int:
        return Fmt.as_int(self.raw.get("OperationCycle", 0), 0)

    @property
    def supportignitionOn(self) -> int:
        return Fmt.as_int(self.raw.get("supportignitionOn", 0), 0)

    @property
    def EnableDTCMessaegID_int(self) -> int:
        return Fmt.hx(self.raw.get("EnableDTCMessaegID", 0x0), 0x0)

    @property
    def EnableDTCSignalName(self) -> str:
        return str(self.raw.get("EnableDTCSignalName", "PowerMode"))

    @property
    def EnableDTCSignalStartBit(self) -> int:
        return Fmt.as_int(self.raw.get("EnableDTCSignalStartBit", 0), 0)

    @property
    def EnableDTCSignalBitLength(self) -> int:
        return Fmt.as_int(self.raw.get("EnableDTCSignalBitLength", 0), 0)

    @property
    def Partner_Msg_int(self) -> int:
        return Fmt.hx(self.raw.get("Partner_Msg", 0x0), 0x0)

