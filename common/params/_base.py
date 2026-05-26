from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any, Dict, List, Union


DEFAULT_DIR = Path(__file__).resolve().parents[2] / "testinputs" / "json"

DEFAULT_MAP = {
    "ProjectInfo": "CANLinTestParameters.ProjectInfo.json",
    "ECUInfo": "CANLinTestParameters.ECUInfo.json",
    "CANInfo": "CANLinTestParameters.CANInfo.json",
    "LINInfo": "CANLinTestParameters.LINInfo.json",
    "NMInfo": "CANLinTestParameters.NMInfo.json",
    "TpInfo": "CANLinTestParameters.TpInfo.json",
    "E2EInfo": "CANLinTestParameters.E2EInfo.json",
    "ChannelMapping": "CANLinTestParameters.ChannelMapping.json",
    "RoutingInfo": "CANLinTestParameters.RoutingInfo.json",
    "E2E_DTCs": "CANLinTestParameters.E2E_DTCs.json",
    "BootloaderInfo": "CANLinTestParameters.Bootloader.json",
    "Conditions": "CANLinTestParameters.Conditions.json",
    "ReadDIDs": "CANLinTestParameters.ReadDIDs.json",
    "WriteDIDs": "CANLinTestParameters.WriteDIDs.json",
    "ControlDIDs": "CANLinTestParameters.ControlDIDs.json",
    "RoutineDIDs": "CANLinTestParameters.RoutineDIDs.json",
    "LostCommunicationDTCs": "CANLinTestParameters.LostCommunicationDTCs.json",
    "BusOffDTCs": "CANLinTestParameters.BusOffDTCs.json",
    "VoltageDTCs": "CANLinTestParameters.VoltageDTCs.json",
    "AllSupportDTCs": "CANLinTestParameters.AllSupportDTCs.json",
    "InvalidDataDTCs": "CANLinTestParameters.InvalidDataDTCs.json",
    "GlobalData": "CANLinTestParameters.GlobalData.json",
    "SIG_INFO": "CANLinTestParameters.SIG_INFO.json",
    "DiagServiceInfo": "CANLinTestParameters.DiagServiceInfo.json",
}


class ParamSource:
    def __init__(self, base_dir: Path, file_map: Dict[str, str]) -> None:
        self.base_dir = base_dir
        self.file_map = dict(file_map)

    def load(self, name: str) -> Union[Dict[str, Any], List[Any]]:
        path = self.base_dir / self.file_map.get(name, "")
        if not path.exists():
            warnings.warn(f"[parameters] JSON 文件不存在: {path}")
            return {} if name not in ("ChannelMapping", "RoutingInfo") else []
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            warnings.warn(f"[parameters] JSON 解析失败: {path} - {e}")
            return {} if name not in ("ChannelMapping", "RoutingInfo") else []


class Fmt:
    """参数格式转换"""
    @staticmethod
    def hx(val: Any, default: int = 0) -> int:
        """十六进制字符串/整数 → int"""
        if val is None:
            return int(default)
        if isinstance(val, int):
            return val
        if isinstance(val, float):
            try:
                return int(val)
            except Exception:
                return int(default)
        if isinstance(val, str):
            s = val.strip().lower()
            try:
                if s.startswith("0x"):
                    return int(s, 16)
                return int(s)
            except Exception:
                return int(default)
        try:
            return int(val)
        except Exception:
            return int(default)

    @staticmethod
    def as_float(val: Any, default: float) -> float:
        try:
            return float(val)
        except Exception:
            return float(default)

    @staticmethod
    def as_int(val: Any, default: int) -> int:
        try:
            return int(val)
        except Exception:
            return int(default)

    @staticmethod
    def ms_to_s(ms: Any, default_ms: int) -> float:
        try:
            return float(int(ms)) / 1000.0
        except Exception:
            return float(int(default_ms)) / 1000.0

    @staticmethod
    def hex_bytes(val: Any) -> bytes:
        """十六进制字符串 → bytes
        支持格式："0x7F0000..."、"7F 00 00 ..."、"7F0000..."
        """
        try:
            if val is None:
                return bytes()
            if isinstance(val, (bytes, bytearray)):
                return bytes(val)
            if isinstance(val, list):
                return bytes(int(x) & 0xFF for x in val)
            s = str(val).strip()
            s = s.replace(" ", "").replace(",", "")
            if s.lower().startswith("0x"):
                s = s[2:]
            if len(s) % 2 == 1:
                s = "0" + s
            return bytes.fromhex(s)
        except Exception:
            return bytes()

