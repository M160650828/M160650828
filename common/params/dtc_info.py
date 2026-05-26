from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ._base import Fmt

#
# @dataclass
# class GlobalDataItem:
#     raw: Dict[str, Any]
#
#     @property
#     def DID(self) -> int:
#         return Fmt.hx(self.raw.get("DID", 0), 0)
#
#     def Length(self) -> int:
#         return Fmt.hx(self.raw.get("Length", 0), 0)
#
#     @property
#     def Notes(self) -> str:
#         return str(self.raw.get("备注", ""))
#
#
# @dataclass
# class GlobalDataCfg:
#     raw: Any
#
#     def __post_init__(self):
#         self._items: List[GlobalDataItem] = []
#         if isinstance(self.raw, list):
#             for item in self.raw:
#                 if isinstance(item, dict):
#                     self._items.append(GlobalDataItem(item))
#         elif isinstance(self.raw, dict):
#             self._items.append(GlobalDataItem(self.raw))
#
#     @property
#     def items(self) -> List[GlobalDataItem]:
#         return self._items
#
#     def __iter__(self):
#         return iter(self._items)
#
#     def __len__(self) -> int:
#         return len(self._items)
#
#     def __getitem__(self, idx: int) -> GlobalDataItem:
#         return self._items[idx]
#


@dataclass
class DTCInfoItem:
    raw: Dict[str, Any]

    @property
    def SignalGroupName(self) -> str:
        return str(self.raw.get("SignalGroupName", ""))

    @property
    def Cluster(self) -> str:
        return str(self.raw.get("Cluster", ""))

    @property
    def SAE5(self) -> str:
        return str(self.raw.get("SAE5", ""))

    @property
    def TYPE(self) -> str:
        return str(self.raw.get("TYPE", ""))

    @property
    def DTC(self) -> str:
        return str(self.raw.get("DTC", ""))

    @property
    def DTC_int(self) -> int:
        return Fmt.hx(self.raw.get("DTC", 0), 0)


@dataclass
class DTCInfoCfg:
    raw: Any

    def __post_init__(self):
        self._items: List[DTCInfoItem] = []
        if isinstance(self.raw, list):
            for item in self.raw:
                if isinstance(item, dict):
                    self._items.append(DTCInfoItem(item))
        elif isinstance(self.raw, dict):
            self._items.append(DTCInfoItem(self.raw))

    @property
    def items(self) -> List[DTCInfoItem]:
        return self._items

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, idx: int) -> DTCInfoItem:
        return self._items[idx]


@dataclass
class AllSupportDTCItem:
    raw: Dict[str, Any]

    @property
    def DTCCode(self) -> int:

        return Fmt.hx(self.raw.get("DTCCode", 0), 0)

    @property
    def DTCCode_hex(self) -> str:
        return f"0x{self.DTCCode:04X}"

    @property
    def FailureType(self) -> int:
        return Fmt.hx(self.raw.get("FailureType", 0), 0)

    @property
    def FailureType_hex(self) -> str:
        return f"0x{self.FailureType:02X}"

    @property
    def is_eof(self) -> bool:
        dtc_val = self.raw.get("DTCCode", "")
        return str(dtc_val).upper() == "EOF"



@dataclass
class LostCommDTCItem:
    raw: Dict[str, Any]

    @property
    def DTCCode(self) -> int:
        return Fmt.hx(self.raw.get("DTC Code", 0), 0)

    @property
    def DTCCode_hex(self) -> str:
        return f"0x{self.DTCCode:04X}"

    @property
    def FailureType(self) -> int:
        return Fmt.hx(self.raw.get("Failure Type", 0), 0)

    @property
    def FailureType_hex(self) -> str:
        return f"0x{self.FailureType:02X}"

    @property
    def MonitorMessageID(self) -> int:
        return Fmt.hx(self.raw.get("Montior Message ID", 0), 0)

    @property
    def MonitorPDUID(self) -> int:
        return Fmt.as_int(self.raw.get("Montior PDU ID", 0), 0)

    @property
    def MonitorMessageChannel(self) -> str:
        return str(self.raw.get("Montior Message Channel", ""))

    @property
    def MonitorMessageDLC(self) -> int:
        return Fmt.as_int(self.raw.get("Montior Message DLC", 0), 0)

    @property
    def MonitorMessagePeriod(self) -> int:
        return Fmt.as_int(self.raw.get("Montior Message Period", 0), 0)

    @property
    def LostTime(self) -> int:
        return Fmt.as_int(self.raw.get("Lost Time", 0), 0)

    @property
    def PassTime(self) -> int:
        return Fmt.as_int(self.raw.get("Pass Time", 0), 0)

    @property
    def ConfigDID(self) -> int:
        return Fmt.hx(self.raw.get("Config DID", 0), 0)

    @property
    def ConfigDIDLength(self) -> int:
        return Fmt.as_int(self.raw.get("Config DID Length", 0), 0)

    @property
    def ConfigByte(self) -> int:
        return Fmt.as_int(self.raw.get("Config Byte", 0), 0)

    @property
    def ConfigBit(self) -> int:
        return Fmt.as_int(self.raw.get("Config Bit", 0), 0)

    @property
    def FDF(self) -> bool:
        val = self.raw.get("FDF")
        return bool(val) if val is not None else False

    @property
    def IsContainE2E(self) -> bool:
        val = self.raw.get("IsContainE2E")
        return bool(val) if val is not None else False

    @property
    def DataID(self) -> int:
        return Fmt.hx(self.raw.get("DataID", 0), 0)

    @property
    def VDiagLowStopMin(self) -> float:
        return Fmt.as_float(self.raw.get("VDiagLowStopMin", 0), 0.0)

    @property
    def VDiagLowStopMax(self) -> float:
        return Fmt.as_float(self.raw.get("VDiagLowStopMax", 0), 0.0)

    @property
    def VDiagLowStartMin(self) -> float:
        return Fmt.as_float(self.raw.get("VDiagLowStartMin", 0), 0.0)

    @property
    def VDiagLowStartMax(self) -> float:
        return Fmt.as_float(self.raw.get("VDiagLowStartMax", 0), 0.0)

    @property
    def VDiagHighStopMin(self) -> float:
        return Fmt.as_float(self.raw.get("VDiagHighStopMin", 0), 0.0)

    @property
    def VDiagHighStopMax(self) -> float:
        return Fmt.as_float(self.raw.get("VDiagHighStopMax", 0), 0.0)

    @property
    def VDiagHighStartMin(self) -> float:
        return Fmt.as_float(self.raw.get("VDiagHighStartMin", 0), 0.0)

    @property
    def VDiagHighStartMax(self) -> float:
        return Fmt.as_float(self.raw.get("VDiagHighStartMax", 0), 0.0)

    @property
    def SeverityLevel(self) -> str:
        return str(self.raw.get("SeverityLevel", ""))

    @property
    def DTCType(self) -> str:
        return str(self.raw.get("DTCType", ""))

    @property
    def Notes(self) -> str:
        return str(self.raw.get("Notes", ""))

    @property
    def is_eof(self) -> bool:
        dtc_val = self.raw.get("DTC Code", "")
        return str(dtc_val).upper() == "EOF"


@dataclass
class BusOffDTCItem:
    raw: Dict[str, Any]

    @property
    def DTCCode(self) -> int:
        return Fmt.hx(self.raw.get("DTC Code", 0), 0)

    @property
    def DTCCode_hex(self) -> str:
        return f"0x{self.DTCCode:04X}"

    @property
    def FailureType(self) -> int:
        return Fmt.hx(self.raw.get("Failure Type", 0), 0)

    @property
    def FailureType_hex(self) -> str:
        return f"0x{self.FailureType:02X}"

    @property
    def ChannelName(self) -> str:
        return str(self.raw.get("Channel Name", ""))

    @property
    def ConfigDID(self) -> int:
        return Fmt.hx(self.raw.get("Config DID", 0), 0)

    @property
    def ConfigDIDLength(self) -> int:
        return Fmt.as_int(self.raw.get("Config DID Length", 0), 0)

    @property
    def ConfigByte(self) -> int:
        return Fmt.as_int(self.raw.get("Config Byte", 0), 0)

    @property
    def ConfigBit(self) -> int:
        return Fmt.as_int(self.raw.get("Config Bit", 0), 0)

    @property
    def BusOffMax(self) -> int:
        return Fmt.as_int(self.raw.get("BusOFF_MAX", 0), 0)

    @property
    def Notes(self) -> str:
        return str(self.raw.get("Notes", ""))

    @property
    def is_eof(self) -> bool:
        dtc_val = self.raw.get("DTC Code", "")
        return str(dtc_val).upper() == "EOF"



@dataclass
class VoltageDTCItem:
    raw: Dict[str, Any]

    @property
    def DTCCode(self) -> int:
        return Fmt.hx(self.raw.get("DTC Code", 0), 0)

    @property
    def DTCCode_hex(self) -> str:
        return f"0x{self.DTCCode:04X}"

    @property
    def FailureType(self) -> int:
        return Fmt.hx(self.raw.get("Failure Type", 0), 0)

    @property
    def FailureType_hex(self) -> str:
        return f"0x{self.FailureType:02X}"

    @property
    def ChannelName(self) -> str:
        return str(self.raw.get("Channel Name", ""))

    @property
    def ConfigDID(self) -> int:
        return Fmt.hx(self.raw.get("Config DID", 0), 0)

    @property
    def ConfigDIDLength(self) -> int:
        return Fmt.as_int(self.raw.get("Config DID Length", 0), 0)

    @property
    def ConfigByte(self) -> int:
        return Fmt.as_int(self.raw.get("Config Byte", 0), 0)

    @property
    def ConfigBit(self) -> int:
        return Fmt.as_int(self.raw.get("Config Bit", 0), 0)

    @property
    def Notes(self) -> str:
        return str(self.raw.get("Notes", ""))

    @property
    def is_eof(self) -> bool:
        dtc_val = self.raw.get("DTC Code", "")
        return str(dtc_val).upper() == "EOF"



@dataclass
class InvalidDataDTCItem:
    raw: Dict[str, Any]

    @property
    def DTCCode(self) -> int:
        return Fmt.hx(self.raw.get("DTC Code", 0), 0)

    @property
    def DTCCode_hex(self) -> str:
        return f"0x{self.DTCCode:04X}"

    @property
    def FailureType(self) -> int:
        return Fmt.hx(self.raw.get("Failure Type", 0), 0)

    @property
    def FailureType_hex(self) -> str:
        return f"0x{self.FailureType:02X}"

    @property
    def MonitorMessageID(self) -> int:
        return Fmt.hx(self.raw.get("Montior Message ID", 0), 0)

    @property
    def MonitorPDUID(self) -> int:
        return Fmt.as_int(self.raw.get("Montior PDU ID", 0), 0)

    @property
    def MonitorMessageChannel(self) -> str:
        return str(self.raw.get("Montior Message Channel", ""))

    @property
    def MonitorMessageDLC(self) -> int:
        return Fmt.as_int(self.raw.get("Montior Message DLC", 0), 0)

    @property
    def MonitorMessagePeriod(self) -> int:
        return Fmt.as_int(self.raw.get("Montior Message Period", 0), 0)

    @property
    def LostTime(self) -> int:
        return Fmt.as_int(self.raw.get("Lost Time", 0), 0)

    @property
    def PassTime(self) -> int:
        return Fmt.as_int(self.raw.get("Pass Time", 0), 0)

    @property
    def FDF(self) -> bool:
        val = self.raw.get("FDF")
        return bool(val) if val is not None else False

    @property
    def IsContainE2E(self) -> bool:
        val = self.raw.get("IsContainE2E")
        return bool(val) if val is not None else False

    @property
    def DataID(self) -> int:
        return Fmt.hx(self.raw.get("DataID", 0), 0)

    @property
    def ValidPayload(self) -> bytes:
        data_str = self.raw.get("Valid Payload", "00 00 00 00 00 00 00 00")
        return Fmt.hex_bytes(data_str)

    @property
    def InvalidPayload(self) -> bytes:
        data_str = self.raw.get("Invalid Payload", "00 00 00 00 00 00 00 00")
        return Fmt.hex_bytes(data_str)

    @property
    def Type(self) -> str:
        return str(self.raw.get("Type", ""))

    @property
    def Notes(self) -> str:
        return str(self.raw.get("Notes", ""))

    @property
    def is_eof(self) -> bool:
        dtc_val = self.raw.get("DTC Code", "")
        return str(dtc_val).upper() == "EOF"



@dataclass
class LostCommDTCCfg:
    raw: Any

    def __post_init__(self):
        self._items: List[LostCommDTCItem] = []
        if isinstance(self.raw, list):
            for item in self.raw:
                if isinstance(item, dict):
                    dtc_item = LostCommDTCItem(item)
                    if not dtc_item.is_eof:
                        self._items.append(dtc_item)
        elif isinstance(self.raw, dict):
            dtc_item = LostCommDTCItem(self.raw)
            if not dtc_item.is_eof:
                self._items.append(dtc_item)

    @property
    def items(self) -> List[LostCommDTCItem]:
        return self._items

    @property
    def valid_items(self) -> List[LostCommDTCItem]:
        """获取有效项（排除DTC为0的）"""
        return [item for item in self._items if item.DTCCode != 0]

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, idx: int) -> LostCommDTCItem:
        return self._items[idx]

    def get_by_dtc(self, dtc: int) -> Optional[LostCommDTCItem]:
        for item in self._items:
            if item.DTCCode == dtc:
                return item
        return None


@dataclass
class BusOffDTCCfg:
    raw: Any

    def __post_init__(self):
        self._items: List[BusOffDTCItem] = []
        if isinstance(self.raw, list):
            for item in self.raw:
                if isinstance(item, dict):
                    dtc_item = BusOffDTCItem(item)
                    if not dtc_item.is_eof:
                        self._items.append(dtc_item)
        elif isinstance(self.raw, dict):
            dtc_item = BusOffDTCItem(self.raw)
            if not dtc_item.is_eof:
                self._items.append(dtc_item)

    @property
    def items(self) -> List[BusOffDTCItem]:
        return self._items

    @property
    def valid_items(self) -> List[BusOffDTCItem]:
        return [item for item in self._items if item.DTCCode != 0]

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, idx: int) -> BusOffDTCItem:
        return self._items[idx]

    def get_by_dtc(self, dtc: int) -> Optional[BusOffDTCItem]:
        for item in self._items:
            if item.DTCCode == dtc:
                return item
        return None


@dataclass
class VoltageDTCCfg:
    raw: Any

    def __post_init__(self):
        self._items: List[VoltageDTCItem] = []
        if isinstance(self.raw, list):
            for item in self.raw:
                if isinstance(item, dict):
                    dtc_item = VoltageDTCItem(item)
                    if not dtc_item.is_eof:
                        self._items.append(dtc_item)
        elif isinstance(self.raw, dict):
            dtc_item = VoltageDTCItem(self.raw)
            if not dtc_item.is_eof:
                self._items.append(dtc_item)

    @property
    def items(self) -> List[VoltageDTCItem]:
        return self._items

    @property
    def valid_items(self) -> List[VoltageDTCItem]:
        return [item for item in self._items if item.DTCCode != 0]

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, idx: int) -> VoltageDTCItem:
        return self._items[idx]

    def get_by_dtc(self, dtc: int) -> Optional[VoltageDTCItem]:
        for item in self._items:
            if item.DTCCode == dtc:
                return item
        return None


@dataclass
class AllSupportDTCCfg:
    raw: Any

    def __post_init__(self):
        self._items: List[AllSupportDTCItem] = []
        if isinstance(self.raw, list):
            for item in self.raw:
                if isinstance(item, dict):
                    dtc_item = AllSupportDTCItem(item)
                    if not dtc_item.is_eof:
                        self._items.append(dtc_item)
        elif isinstance(self.raw, dict):
            dtc_item = AllSupportDTCItem(self.raw)
            if not dtc_item.is_eof:
                self._items.append(dtc_item)
        # print(self._items)

    @property
    def items(self) -> List[AllSupportDTCItem]:
        return self._items

    @property
    def valid_items(self) -> List[AllSupportDTCItem]:
        return [item for item in self._items if item.DTCCode != 0]

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, idx: int) -> AllSupportDTCItem:
        return self._items[idx]

    def get_by_dtc(self, dtc: int) -> Optional[AllSupportDTCItem]:
        for item in self._items:
            if item.DTCCode == dtc:
                return item
        return None


@dataclass
class InvalidDataDTCCfg:
    raw: Any

    def __post_init__(self):
        self._items: List[InvalidDataDTCItem] = []
        if isinstance(self.raw, list):
            for item in self.raw:
                if isinstance(item, dict):
                    dtc_item = InvalidDataDTCItem(item)
                    if not dtc_item.is_eof:
                        self._items.append(dtc_item)
        elif isinstance(self.raw, dict):
            dtc_item = InvalidDataDTCItem(self.raw)
            if not dtc_item.is_eof:
                self._items.append(dtc_item)

    @property
    def items(self) -> List[InvalidDataDTCItem]:
        return self._items

    @property
    def valid_items(self) -> List[InvalidDataDTCItem]:
        return [item for item in self._items if item.DTCCode != 0]

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, idx: int) -> InvalidDataDTCItem:
        return self._items[idx]

    def get_by_dtc(self, dtc: int) -> Optional[InvalidDataDTCItem]:
        for item in self._items:
            if item.DTCCode == dtc:
                return item
        return None


@dataclass
class ExtendedDTCInfoCfg:
    lost_communication: LostCommDTCCfg
    bus_off: BusOffDTCCfg
    voltage: VoltageDTCCfg
    all_support: AllSupportDTCCfg
    invalid_data: InvalidDataDTCCfg

    @property
    def all_items(self) -> List:
        return (
            list(self.lost_communication.items) +
            list(self.bus_off.items) +
            list(self.voltage.items)
        )

    def get_by_dtc(self, dtc: int):
        for cat in [self.lost_communication, self.bus_off, self.voltage]:
            item = cat.get_by_dtc(dtc)
            if item:
                return item
        return None

