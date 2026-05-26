from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ._base import Fmt


@dataclass
class DIDItem:
    raw: Dict[str, Any]

    @property
    def DID(self) -> int:
        return Fmt.hx(self.raw.get("DID"), 0)

    @property
    def DID_int(self) -> int:
        return self.DID

    @property
    def DID_hex(self) -> str:
        return f"0x{self.DID:04X}"

    @property
    def Length(self) -> int:
        return Fmt.as_int(self.raw.get("Length", 0), 0)

    @property
    def Factor(self) -> float:
        value = self.raw.get("Factor", self.raw.get("系数"))
        if value in (None, ""):
            raise ValueError(f"DID {self.DID_hex} 未配置 Factor")
        return float(value)

    @property
    def DataContent(self) -> str:
        return str(self.raw.get("数据内容（16进制）", self.raw.get("数据内容(16进制）", "")))

    @property
    def Notes(self) -> str:
        return str(self.raw.get("Notes", self.raw.get("备注", "")))

    @property
    def Security22(self) -> str:
        return str(self.raw.get("Security$22", self.raw.get("Security $22", "")))

    @property
    def is_eof(self) -> bool:
        did_val = self.raw.get("DID", "")
        return str(did_val).upper() == "EOF"

    @property
    def sig(self) -> str:
        return self.raw.get("SIG", "")
    
@dataclass
class ConfigDIDItem(DIDItem):
    @property
    def Security2E(self) -> str:
        return str(self.raw.get("Security $2E", ""))


@dataclass
class ControlDIDItem(DIDItem):
    """2F 服务控制 DID"""

    @property
    def ControlOption_00(self) -> int:
        return Fmt.as_int(self.raw.get("Control\nOption_00", 0), 0)

    @property
    def ControlOption_01(self) -> bool:
        val = str(self.raw.get("Control\nOption_01", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def ControlOption_02(self) -> bool:
        val = str(self.raw.get("Control\nOption_02", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def ControlOption_03(self) -> bool:
        val = str(self.raw.get("Control\nOption_03", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def SecurityUnlock(self) -> bool:
        val = str(self.raw.get("Security \nUnlock", self.raw.get("Security Unlock", ""))).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def Level1(self) -> bool:
        val = str(self.raw.get("Level1", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def Level2(self) -> bool:
        val = str(self.raw.get("Level2", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def Level3(self) -> bool:
        val = str(self.raw.get("Level3", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def Level4(self) -> bool:
        val = str(self.raw.get("Level4", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def Level5(self) -> bool:
        val = str(self.raw.get("Level5", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def NRC22(self) -> bool:
        val = str(self.raw.get("NRC22", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def NRC8x(self) -> bool:
        val = str(self.raw.get("NRC8x", "")).strip().lower()
        return val in ("yes", "true", "1")


@dataclass
class RoutineDIDItem(DIDItem):
    """31 服务例程 DID"""

    @property
    def ReqLength_31_01(self) -> int:
        return Fmt.as_int(self.raw.get("$31 01 ReqLength", 0), 0)

    @property
    def RespLength_31_01(self) -> int:
        return Fmt.as_int(self.raw.get("$31 01 RespLength", 0), 0)

    @property
    def ReqLength_31_02(self) -> str:
        return str(self.raw.get("$31 02 ReqLength", "No"))

    @property
    def RespLength_31_02(self) -> str:
        return str(self.raw.get("$31 02 RespLength", "No"))

    @property
    def ReqLength_31_03(self) -> int:
        return Fmt.as_int(self.raw.get("$31 03 ReqLength", 0), 0)

    @property
    def RespLength_31_03(self) -> int:
        return Fmt.as_int(self.raw.get("$31 03 RespLength", 0), 0)

    @property
    def Support_App(self) -> bool:
        val = str(self.raw.get("Support \nApp", self.raw.get("Support_App", ""))).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def Support_Boot(self) -> bool:
        val = str(self.raw.get("Support \nBoot", self.raw.get("Support_Boot", ""))).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def SecurityUnlock(self) -> bool:
        val = str(self.raw.get("Security Unlock", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def Level1(self) -> bool:
        val = str(self.raw.get("Level1", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def Level3(self) -> bool:
        val = str(self.raw.get("Level3", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def Level5(self) -> bool:
        val = str(self.raw.get("Level5", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def NRC22(self) -> bool:
        val = str(self.raw.get("NRC22", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def NRC8x(self) -> bool:
        val = str(self.raw.get("NRC8x", "")).strip().lower()
        return val in ("yes", "true", "1")


@dataclass
class ReadDIDItem(DIDItem):
    """22 服务读取 DID"""

    @property
    def Support_App(self) -> bool:
        val = str(self.raw.get("Support App", self.raw.get("Support_App", ""))).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def Support_Boot(self) -> bool:
        val = str(self.raw.get("Support Boot", self.raw.get("Support_Boot", ""))).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def SecurityUnlock(self) -> bool:
        val = str(self.raw.get("Security Unlock", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def Level1(self) -> bool:
        val = str(self.raw.get("Level1", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def Level3(self) -> bool:
        val = str(self.raw.get("Level3", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def Level5(self) -> bool:
        val = str(self.raw.get("Level5", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def NRC22(self) -> bool:
        val = str(self.raw.get("NRC22", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def NRC8x(self) -> bool:
        val = str(self.raw.get("NRC8x", "")).strip().lower()
        return val in ("yes", "true", "1")


@dataclass
class WriteDIDItem(DIDItem):
    """2E 服务写入 DID"""

    @property
    def Support_App(self) -> bool:
        val = str(self.raw.get("Support App", self.raw.get("Support_App", ""))).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def Support_Boot(self) -> bool:
        val = str(self.raw.get("Support Boot", self.raw.get("Support_Boot", ""))).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def SecurityUnlock(self) -> bool:
        val = str(self.raw.get("Security Unlock", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def Level1(self) -> bool:
        val = str(self.raw.get("Level1", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def Level3(self) -> bool:
        val = str(self.raw.get("Level3", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def Level5(self) -> bool:
        val = str(self.raw.get("Level5", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def NRC22(self) -> bool:
        val = str(self.raw.get("NRC22", "")).strip().lower()
        return val in ("yes", "true", "1")

    @property
    def NRC8x(self) -> bool:
        val = str(self.raw.get("NRC8x", "")).strip().lower()
        return val in ("yes", "true", "1")


@dataclass
class ConditionItem:
    raw: Dict[str, Any]

    def __int__(self) -> int:
        return self.MessageID

    def __index__(self) -> int:
        return self.MessageID

    @property
    def ConditionName(self) -> str:
        return str(self.raw.get("ConditionName", ""))

    @property
    def SupportServices(self) -> List[Any]:
        services = self.raw.get("SupportServices", [])
        if isinstance(services, str):
            return [s.strip() for s in services.replace("，", ",").replace(";", ",").split(",") if s.strip()]
        if isinstance(services, (list, tuple, set)):
            return list(services)
        return []

    @property
    def MessageChannel(self) -> int:
        return Fmt.as_int(self.raw.get("MessageChannel", 0), 0)

    @property
    def MessageID(self) -> int:
        return Fmt.hx(self.raw.get("MessageID", 0), 0)

    @property
    def MessageDLC(self) -> int:
        return Fmt.as_int(self.raw.get("MessageDLC", 8), 8)

    @property
    def MessagePeriod(self) -> int:
        return Fmt.as_int(self.raw.get("MessagePeriod", 100), 100)

    @property
    def MessageType(self) -> str:
        return str(self.raw.get("MessageType", "CAN"))

    @property
    def MessageDatabaseType(self) -> Any:
        return self.raw.get("MessageDatabaseType", 1)

    @property
    def MessageE2EFlag(self) -> int:
        return Fmt.as_int(self.raw.get("MessageE2EFlag", 0), 0)

    @property
    def SignalName(self) -> str:
        return str(self.raw.get("SignalName", ""))

    @property
    def SignalStartBit(self) -> int:
        return Fmt.as_int(self.raw.get("SignalStartBit", 0), 0)

    @property
    def SignalLength(self) -> int:
        return Fmt.as_int(self.raw.get("SignalLength", 0), 0)

    @property
    def SignalValue(self) -> int:
        return Fmt.hx(self.raw.get("SignalValue", 0), 0)

    @property
    def SignalValidBitName(self) -> str:
        return str(self.raw.get("SignalValidBitName", ""))

    @property
    def SignalValidBitStartBit(self) -> int:
        return Fmt.as_int(self.raw.get("SignalValidBitStartBit", 0), 0)

    @property
    def SignalValidBitLength(self) -> int:
        return Fmt.as_int(self.raw.get("SignalValidBitLength", 0), 0)

    @property
    def VehicleSpeedCoefficientValue(self) -> float:
        return Fmt.as_float(self.raw.get("VehicleSpeedCoefficientValue", 1.0), 1.0)

    @property
    def TriggerPhysicalValue(self) -> float:
        return Fmt.as_float(self.raw.get("TriggerPhysicalValue", 0.0), 0.0)

    @property
    def NormalPhysicalValue(self) -> float:
        return Fmt.as_float(self.raw.get("NormalPhysicalValue", 0.0), 0.0)

    @property
    def TriggerRawValue(self) -> int:
        return Fmt.hx(self.raw.get("TriggerRawValue", 0), 0)

    @property
    def NormalRawValue(self) -> int:
        return Fmt.hx(self.raw.get("NormalRawValue", 0), 0)

    @property
    def IsSignalConditionConfigured(self) -> bool:
        return self.MessageID != 0 and self.MessageDLC > 0 and self.SignalLength > 0

    @property
    def is_eof(self) -> bool:
        return self.ConditionName.upper() == "EOF"


def _create_did_item(raw: Dict[str, Any], category: str) -> DIDItem:
    if category == "Config":
        return ConfigDIDItem(raw)
    elif category == "Control":
        return ControlDIDItem(raw)
    elif category == "Routine":
        return RoutineDIDItem(raw)
    else:
        return DIDItem(raw)


@dataclass
class DIDCategoryCfg:
    raw: Any
    category: str = ""

    def __post_init__(self):
        self._items: List[DIDItem] = []
        if isinstance(self.raw, list):
            for item in self.raw:
                if isinstance(item, dict):
                    did_item = _create_did_item(item, self.category)
                    if not did_item.is_eof:
                        self._items.append(did_item)
        elif isinstance(self.raw, dict):
            did_item = _create_did_item(self.raw, self.category)
            if not did_item.is_eof:
                self._items.append(did_item)

    @property
    def items(self) -> List[DIDItem]:
        return self._items

    @property
    def valid_items(self) -> List[DIDItem]:
        return [item for item in self._items if item.DID != 0]

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, idx: int) -> DIDItem:
        return self._items[idx]

    def get_by_did(self, did: int) -> Optional[DIDItem]:
        for item in self._items:
            if item.DID == did:
                return item
        return None


@dataclass
class DIDInfoCfg:
    logistic: DIDCategoryCfg
    internal: DIDCategoryCfg
    config: DIDCategoryCfg
    control: DIDCategoryCfg
    routine: DIDCategoryCfg

    @property
    def all_items(self) -> List[DIDItem]:
        return (
            self.logistic.items +
            self.internal.items +
            self.config.items +
            self.control.items +
            self.routine.items
        )

    def get_by_did(self, did: int) -> Optional[DIDItem]:
        for cat in [self.logistic, self.internal, self.config, self.control, self.routine]:
            item = cat.get_by_did(did)
            if item:
                return item
        return None


@dataclass
class DataItemCfg:
    raw: Any

    def __post_init__(self):
        self._items: List[DIDItem] = []
        if isinstance(self.raw, list):
            for item in self.raw:
                if isinstance(item, dict):
                    did_item = DIDItem(item)
                    if not did_item.is_eof:
                        self._items.append(did_item)
        elif isinstance(self.raw, dict):
            did_item = DIDItem(self.raw)
            if not did_item.is_eof:
                self._items.append(did_item)

    @property
    def items(self) -> List[DIDItem]:
        return self._items

    @property
    def valid_items(self) -> List[DIDItem]:
        return [item for item in self._items if item.DID != 0]

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, idx: int) -> DIDItem:
        return self._items[idx]

    def get_by_did(self, did: int) -> Optional[DIDItem]:
        for item in self._items:
            if item.DID == did:
                return item
        return None


@dataclass
class ReadDIDsCfg:
    """22 服务 ReadDIDs"""
    raw: Any

    def __post_init__(self):
        self._items: List[ReadDIDItem] = []
        if isinstance(self.raw, list):
            for item in self.raw:
                if isinstance(item, dict):
                    did_item = ReadDIDItem(item)
                    if not did_item.is_eof:
                        self._items.append(did_item)
        elif isinstance(self.raw, dict):
            did_item = ReadDIDItem(self.raw)
            if not did_item.is_eof:
                self._items.append(did_item)

    @property
    def items(self) -> List[ReadDIDItem]:
        return self._items

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, idx: int) -> ReadDIDItem:
        return self._items[idx]

    def get_by_did(self, did: int) -> Optional[ReadDIDItem]:
        for item in self._items:
            if item.DID == did:
                return item
        return None


@dataclass
class WriteDIDsCfg:
    """2E 服务 WriteDIDs"""
    raw: Any

    def __post_init__(self):
        self._items: List[WriteDIDItem] = []
        if isinstance(self.raw, list):
            for item in self.raw:
                if isinstance(item, dict):
                    did_item = WriteDIDItem(item)
                    if not did_item.is_eof:
                        self._items.append(did_item)
        elif isinstance(self.raw, dict):
            did_item = WriteDIDItem(self.raw)
            if not did_item.is_eof:
                self._items.append(did_item)

    @property
    def items(self) -> List[WriteDIDItem]:
        return self._items

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, idx: int) -> WriteDIDItem:
        return self._items[idx]

    def get_by_did(self, did: int) -> Optional[WriteDIDItem]:
        for item in self._items:
            if item.DID == did:
                return item
        return None


@dataclass
class ConditionsCfg:
    raw: Any

    def __post_init__(self):
        self._items: List[ConditionItem] = []
        if isinstance(self.raw, list):
            for item in self.raw:
                if isinstance(item, dict):
                    cond_item = ConditionItem(item)
                    if not cond_item.is_eof:
                        self._items.append(cond_item)
        elif isinstance(self.raw, dict):
            cond_item = ConditionItem(self.raw)
            if not cond_item.is_eof:
                self._items.append(cond_item)

    @property
    def items(self) -> List[ConditionItem]:
        return self._items

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, idx: int) -> ConditionItem:
        return self._items[idx]

    def get_by_id(self, condition_id: str) -> Optional[ConditionItem]:
        for item in self._items:
            if item.ConditionName == condition_id:
                return item
        return None
