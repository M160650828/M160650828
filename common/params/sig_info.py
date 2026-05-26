from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ._base import Fmt



@dataclass
class SIGItem:
    raw: Dict[str, Any]

    @property
    def TS_Name(self) -> str:
        return self.raw.get("TS_Name")

    @property
    def Type(self) -> str:
        return self.raw.get("Type")

    @property
    def step(self) -> int:
        return Fmt.as_int(self.raw.get("STEP", 0), 0)

    @property
    def sig(self) -> str:
        return self.raw.get("SIG")

    @property
    def val(self) -> int:
        return Fmt.as_int(self.raw.get("VAL", 0), 0)

    @property
    def Notes(self) -> str:
        return self.raw.get("Notes")

    @property
    def msgid(self) -> int:
        return Fmt.as_int(self.raw.get("msgid", 0), 0)
    
    @property
    def bitlen(self) -> int:
        return Fmt.as_int(self.raw.get("bitlen", 0), 0)

    @property
    def startbit(self) -> int:
        return Fmt.as_int(self.raw.get("startbit", 0), 0)

    @property
    def msg_dlc(self) -> int:
        return Fmt.as_int(self.raw.get("msg_dlc", 0), 0)
    
@dataclass
class SIG_INFO_CFG:
    raw: Any
    def __post_init__(self):
        self._items: List[SIGItem] = []
        if isinstance(self.raw, list):
            for item in self.raw:
                if isinstance(item, dict):
                    sig_item = SIGItem(item)
                    self._items.append(sig_item)
        elif isinstance(self.raw, dict):
            sig_item = SIGItem(self.raw)
            self._items.append(sig_item)

    @property
    def items(self) -> List[SIGItem]:
        return self._items

    @property
    def valid_items(self) -> List[SIGItem]:
        return [item for item in self._items if item.sig != None]

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, idx: int) -> SIGItem:
        return self._items[idx]

    def get_by_ts_name(self, ts: str) -> list[SIGItem]:
        return [item for item in self._items if item.TS_Name == ts]
    
    def get_by_type(self, ty: str) -> list[SIGItem]:
        return [item for item in self._items if item.Type == ty]
