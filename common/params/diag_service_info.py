from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from ._base import Fmt


def _parse_hex_list(val: Any, default: List[int]) -> List[int]:
    """解析逗号分隔的十六进制字符串为 int 列表

    支持格式:
        "0x00,0x03"          -> [0, 3]
        "0x10, 0x11, 0x14"   -> [16, 17, 20]
        [0, 3]               -> [0, 3]  (已经是列表直接返回)
        None / ""            -> default
    """
    if val is None:
        return list(default)
    if isinstance(val, list):
        return [Fmt.hx(v, 0) for v in val]
    s = str(val).strip()
    if not s:
        return list(default)
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if not parts:
        return list(default)
    return [Fmt.hx(p, 0) for p in parts]


def _parse_bounded_hex(val: Any, default: int, minimum: int, maximum: int) -> int:
    parsed = Fmt.hx(val, default)
    return max(minimum, min(maximum, parsed))


def _parse_bounded_int(val: Any, default: int, minimum: int, maximum: int) -> int:
    parsed = Fmt.as_int(val, default)
    return max(minimum, min(maximum, parsed))


@dataclass
class DiagServiceInfoCfg:
    raw: Dict[str, Any]

    @property
    def SID10SubFunSupportList(self) -> List[int]:
        return _parse_hex_list(
            self.raw.get("SID10SubFunSupportList"),
            [0x01, 0x02, 0x03],
        )

    @property
    def SID11SubFunSupportList(self) -> List[int]:
        return _parse_hex_list(
            self.raw.get("SID11SubFunSupportList"),
            [0x01],
        )

    @property
    def SID19SubFunSupportList(self) -> List[int]:
        return _parse_hex_list(
            self.raw.get("SID19SubFunSupportList"),
            [0x01, 0x02, 0x03, 0x04, 0x06, 0x0A],
        )

    @property
    def SID27SubFunSupportList(self) -> List[int]:
        return _parse_hex_list(
            self.raw.get("SID27SubFunSupportList"),
            [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x09, 0x0A, 0x11, 0x12],
        )

    @property
    def SID28SubFunSupportList(self) -> List[int]:
        return _parse_hex_list(
            self.raw.get("SID28SubFunSupportList"),
            [0x00, 0x03],
        )

    @property
    def SID28CommTypeSupportList(self) -> List[int]:
        return _parse_hex_list(
            self.raw.get("SID28CommTypeSupportList"),
            [0x01, 0x03],
        )

    @property
    def SID3ESubFunSupportList(self) -> List[int]:
        return _parse_hex_list(
            self.raw.get("SID3ESubFunSupportList"),
            [0x00, 0x80],
        )

    @property
    def SID85SubFunSupportList(self) -> List[int]:
        return _parse_hex_list(
            self.raw.get("SID85SubFunSupportList"),
            [0x01, 0x02],
        )

    @property
    def SID31SubFunSupportList(self) -> List[int]:
        return _parse_hex_list(
            self.raw.get("SID31SubFunSupportList"),
            [0x01, 0x02, 0x03],
        )

    @property
    def MinSubID(self) -> int:
        return _parse_bounded_hex(self.raw.get("MinSubID"), 0x00, 0x00, 0xFF)

    @property
    def MaxSubID(self) -> int:
        return _parse_bounded_hex(self.raw.get("MaxSubID"), 0x10, 0x00, 0xFF)

    @property
    def MinDID(self) -> int:
        return _parse_bounded_hex(self.raw.get("MinDID"), 0x0000, 0x0000, 0xFFFF)

    @property
    def MaxDID(self) -> int:
        return _parse_bounded_hex(self.raw.get("MaxDID"), 0x0010, 0x0000, 0xFFFF)

    @property
    def MaxMulDIDNumber(self) -> int:
        return _parse_bounded_int(self.raw.get("MaxMulDIDNumber"), 1, 1, 10)

    @property
    def DTCStatusAvlMask(self) -> int:
        return Fmt.hx(self.raw.get("DTCStatusAvlMask", "0x09"), 0x09)

    @property
    def WaitFaultCheckTime(self) -> int:
        return Fmt.as_int(self.raw.get("WaitFaultCheckTime", 5000), 5000)

    @property
    def SessionTime(self) -> int:
        return Fmt.as_int(self.raw.get("SessionTime", 200), 200)

    @property
    def ResetTime(self) -> int:
        return Fmt.as_int(self.raw.get("ResetTime", 2000), 2000)

    @property
    def SID11_DefaultSession(self) -> bool:
        return Fmt.as_int(self.raw.get("SID11_DefaultSession", 0), 0) == 1

    @property
    def SID85_Programming(self) -> bool:
        return Fmt.as_int(self.raw.get("SID85_Programming", 0), 0) == 1

    @property
    def SID11_Sub03_APP(self) -> bool:
        return Fmt.as_int(self.raw.get("SID11_Sub03_APP", 0), 0) == 1

    @property
    def SID11_Sub03_Boot(self) -> bool:
        return Fmt.as_int(self.raw.get("SID11_Sub03_Boot", 0), 0) == 1

    @property
    def FunRequestTimelnterval(self) -> int:
        return Fmt.as_int(self.raw.get("FunRequestTimelnterval", 2000), 2000)

    @property
    def FirstSnapshotNum(self) -> int:
        return _parse_bounded_hex(self.raw.get("FirstSnapshotNum"), 0x00, 0x00, 0xFF)

    @property
    def LastSnapshotNum(self) -> int:
        return _parse_bounded_hex(self.raw.get("LastSnapshotNum"), 0x00, 0x00, 0xFF)


    @property
    def ServicesSupportedList(self) -> List[int]:
        return _parse_hex_list(
            self.raw.get("ServicesSupportedList"),
            [0x10, 0x11, 0x14, 0x19, 0x22, 0x27, 0x28,
             0x2E, 0x2F, 0x31, 0x34, 0x35, 0x36, 0x37, 0x3E, 0x85],
        )
