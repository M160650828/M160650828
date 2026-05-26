from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, TYPE_CHECKING

from ._base import Fmt

if TYPE_CHECKING:
    from .ecu_info import ECUInfoCfg


@dataclass
class TpInfoCfg:
    raw: Dict[str, Any]
    ecu: "ECUInfoCfg"

    @property
    def CAN_LIN_PhyReqID_int(self) -> int:
        return Fmt.hx(self.raw.get("CAN_LIN_PhyReqID", self.ecu.DiagReqID_int), self.ecu.DiagReqID_int)

    @property
    def CAN_LIN_PhyRespID_int(self) -> int:
        return Fmt.hx(self.raw.get("CAN_LIN_PhyRespID", self.ecu.DiagRespID_int), self.ecu.DiagRespID_int)

    @property
    def CAN_LIN_FuncReqID_int(self) -> int:
        v = self.raw.get("CAN_LIN_FuncReqID")
        return Fmt.hx(v if v is not None else self.ecu.DiagFuncID_int, self.ecu.DiagFuncID_int)

    @property
    def nandid(self) -> int:
        return Fmt.as_int(self.raw.get("nandid", 1), 1)

    @property
    def Can_Padding_Byte(self) -> int:
        v = self.raw.get("CanTpPaddingByte", "0XAA")
        return Fmt.hx(v, 0xAA)

    @property
    def Cantp_dlc(self) -> int:
        v = self.raw.get("CantpPduLength", "8")
        return Fmt.as_int(v, 8)

    @property
    def CanTp_Bs_ms(self) -> int:
        v = self.raw.get("CanTp_Bs_ms", "150")
        return Fmt.as_int(v, 150)

    @property
    def CanTp_Cr_ms(self) -> int:
        v = self.raw.get("CanTp_Cr_ms", "150")
        return Fmt.as_int(v, 150)

    @property
    def CanTpFunReqID(self) -> int:
        return Fmt.hx(self.raw.get("CanTpFunReqID", "0x7DF"), 0x7DF)

    @property
    def CanTpPhyReqID(self) -> int:
        return Fmt.hx(self.raw.get("CanTpPhyReqID", "0x661"), 0x661)

    @property
    def CanTpRespID(self) -> int:
        return Fmt.hx(self.raw.get("CanTpRespID", "0x669"), 0x669)

    @property
    def P2ClientTimeout(self) -> int:
        return Fmt.as_int(self.raw.get("P2ClientTimeout", 150), 150)

    @property
    def P2EnhanceClientTimeout(self) -> int:
        return Fmt.as_int(self.raw.get("P2EnhanceClientTimeout", 5100), 5100)

    @property
    def DiagRequestTimeout(self) -> int:
        return Fmt.as_int(self.raw.get("DiagRequestTimeout", 5000), 5000)

    @property
    def MaxRespPedCount(self) -> int:
        return Fmt.as_int(self.raw.get("MaxRespPedCount", 10), 10)

    @property
    def WithFBL(self) -> bool:
        return Fmt.as_int(self.raw.get("WithFBL", 1), 1) == 1

    @property
    def CanFDMode(self) -> bool:
        return Fmt.as_int(self.raw.get("CanFDMode", 0), 0) == 1

    @property
    def MaxCanFDDataLength(self) -> int:
        return Fmt.as_int(self.raw.get("MaxCanFDDataLength", 8), 8)

    @property
    def MaxCanFDDataLengthToDLC(self) -> int:
        bytes_to_dlc = {
            0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8,
            12: 9, 16: 10, 20: 11, 24: 12,  32: 13,  48: 14, 64: 15
        }
        return bytes_to_dlc.get(self.MaxCanFDDataLength, 8)

    @property
    def DiagServicesIntervalTime(self) -> int:
        return Fmt.as_int(self.raw.get("DiagServicesIntervalTime", 2), 2)

    @property
    def APPFrameID(self) -> int:
        return Fmt.hx(self.raw.get("APPFrameID", "0x2F3"), 0x2F3)

    @property
    def NMFrameID(self) -> int:
        return Fmt.hx(self.raw.get("NMFrameID", "0x42E"), 0x42E)

    @property
    def LowVoltage(self) -> int:
        return Fmt.as_int(self.raw.get("LowVoltage", 7), 7)

    @property
    def HighVoltage(self) -> int:
        return Fmt.as_int(self.raw.get("HighVoltage", 18), 18)

    @property
    def Channel(self) -> int:
        return Fmt.as_int(self.raw.get("Channel", 1), 1)

    @property
    def DID(self) -> int:
        return Fmt.hx(self.raw.get("DID", "0xF184"), 0xF184)

    @property
    def N_AsTimeout(self) -> int:
        return Fmt.as_int(self.raw.get("N_AsTimeout", 500), 500)

    @property
    def N_ArTimeout(self) -> int:
        return Fmt.as_int(self.raw.get("N_ArTimeout", 500), 500)

    @property
    def N_BsTimeout(self) -> int:
        return Fmt.as_int(self.raw.get("N_BsTimeout", 1000), 1000)

    @property
    def N_CrTimeout(self) -> int:
        return Fmt.as_int(self.raw.get("N_CrTimeout", 1000), 1000)

    @property
    def N_Ar_BrTiming(self) -> int:
        return Fmt.as_int(self.raw.get("N_Ar_BrTiming", 25), 25)

    @property
    def N_Cs_AsTiming(self) -> int:
        return Fmt.as_int(self.raw.get("N_Cs_AsTiming", 50), 50)

    @property
    def P2Timeout(self) -> int:
        return Fmt.as_int(self.raw.get("P2Timeout", 50), 50)

    @property
    def P2_Client(self) -> int:
        return Fmt.as_int(self.raw.get("P2_Client", 150), 150)

    @property
    def STmin_Client(self) -> int:
        return Fmt.hx(self.raw.get("STmin_Client", "0x0"), 0x0)

    @property
    def STmin_Service(self) -> int:
        return Fmt.hx(self.raw.get("STmin_Service", "0xA"), 0xA)

    @property
    def PCIType_SF(self) -> int:
        return Fmt.hx(self.raw.get("PCIType_SF", "0x0"), 0x0)

    @property
    def PCIType_FF(self) -> int:
        return Fmt.hx(self.raw.get("PCIType_FF", "0x10"), 0x10)

    @property
    def PCIType_CF(self) -> int:
        return Fmt.hx(self.raw.get("PCIType_CF", "0x20"), 0x20)

    @property
    def PCIType_FC(self) -> int:
        return Fmt.hx(self.raw.get("PCIType_FC", "0x30"), 0x30)

    @property
    def N_AsTimeout_Boot(self) -> int:
        return Fmt.as_int(self.raw.get("N_AsTimeout_Boot", 25), 25)

    @property
    def N_ArTimeout_Boot(self) -> int:
        return Fmt.as_int(self.raw.get("N_ArTimeout_Boot", 25), 25)

    @property
    def N_BsTimeout_Boot(self) -> int:
        return Fmt.as_int(self.raw.get("N_BsTimeout_Boot", 25), 25)

    @property
    def N_CrTimeout_Boot(self) -> int:
        return Fmt.as_int(self.raw.get("N_CrTimeout_Boot", 25), 25)

    @property
    def N_Ar_BrTiming_Boot(self) -> int:
        return Fmt.as_int(self.raw.get("N_Ar_BrTiming_Boot", 2), 2)

    @property
    def N_Cs_AsTiming_Boot(self) -> int:
        return Fmt.as_int(self.raw.get("N_Cs_AsTiming_Boot", 2), 2)

    @property
    def ECUHWVersion(self) -> str:
        return str(self.raw.get("ECUHWVersion", ""))

    @property
    def ECUSoftID(self) -> str:
        return str(self.raw.get("ECUSoftID", ""))

    @property
    def StayInBootSupportFlag(self) -> int:
        return Fmt.as_int(self.raw.get("StayInBootSupportFlag", 0), 0)

    @property
    def PartSupportFlag(self) -> int:
        return Fmt.as_int(self.raw.get("PartSupportFlag", 0), 0)

    @property
    def S3Server(self) -> int:
        return Fmt.as_int(self.raw.get("S3Server", 5000), 5000)

    @property
    def WriteDID(self) -> int:
        return Fmt.hx(self.raw.get("WriteDID", 0x001), 0x001)

    @property
    def WriteDIDData_bytes(self) -> bytes:
        data_str = self.raw.get("WriteDIDData", "00 00 00 00 00 00 00 00")
        return Fmt.hex_bytes(data_str)

    @property
    def ConfigDataDID(self) -> int:
        return Fmt.hx(self.raw.get("ConfigDataDID", 0x001), 0x001)

    @property
    def ConfigDataDIDData(self) -> bytes:
        data_str = self.raw.get("ConfigDataDIDData", "00 00 00 00 00 00 00 00")
        return Fmt.hex_bytes(data_str)

    @property
    def SBLMemoryAddress(self) -> int:
        return Fmt.hx(self.raw.get("SBLMemoryAddress", 0x00000000), 0x00000000)

    @property
    def SBLMemorySize(self) -> int:
        return Fmt.hx(self.raw.get("SBLMemorySize", 0x00000000), 0x00000000)
    
    @property
    def WaitDigprotocalStable_ms(self) -> int:
        return Fmt.as_int(self.raw.get("WaitDigprotocalStable"), 5000)