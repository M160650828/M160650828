from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from ._base import Fmt


@dataclass
class BootloaderItemCfg:
    raw: Dict[str, Any]

    @property
    def index(self) -> int:
        return Fmt.as_int(self.raw.get("index", 0), 0)

    @property
    def partition(self) -> str:
        return str(self.raw.get("partition", ""))

    @property
    def type(self) -> int:
        return Fmt.as_int(self.raw.get("type", 0), 0)

    @property
    def path_file(self) -> str:
        return str(self.raw.get("path_file", ""))

    @property
    def path_sig_file(self) -> str:
        return str(self.raw.get("path_sig_file", ""))


@dataclass
class BootloaderInfoCfg:
    items: List[BootloaderItemCfg] = field(default_factory=list)

    def __init__(self, raw: Any) -> None:
        self.items = []
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    self.items.append(BootloaderItemCfg(item))

    def get_by_partition(self, partition: str) -> List[BootloaderItemCfg]:
        return [it for it in self.items if it.partition == partition]

    def get_by_type(self, type_val: int) -> List[BootloaderItemCfg]:
        return [it for it in self.items if it.type == type_val]

