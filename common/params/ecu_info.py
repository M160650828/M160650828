from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from ._base import Fmt

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "testinputs" / "json"
SEC_DLL_DIR = DEFAULT_DIR.parent / "sec_dll"


@dataclass
class ECUInfoCfg:
    raw: Dict[str, Any]

    @property
    def ECUName(self) -> str:
        return str(self.raw.get("ECUName", ""))

    @property
    def PowerMode(self) -> int:
        return Fmt.as_int(self.raw.get("PowerMode", 0), 0)

    @property
    def DiagReqID_int(self) -> int:
        return Fmt.hx(self.raw.get("DiagReqID", "0x7E0"), 0x7E0)

    @property
    def DiagRespID_int(self) -> int:
        return Fmt.hx(self.raw.get("DiagRespID", "0x7E8"), 0x7E8)

    @property
    def DiagFuncID_int(self) -> int:
        return Fmt.hx(self.raw.get("DiagFuncID", "0x7DF"), 0x7DF)

    @property
    def BOBControlCan(self) -> int:
        return Fmt.as_int(self.raw.get("BOBControlCan", 2), 2)

    @property
    def ETS6124ECUChannel(self) -> int:
        return Fmt.as_int(self.raw.get("ETS6124ECUChannel", self.raw.get("CommCANChannelNum", 1)), 1)

    @property
    def ETS6124CanChannel(self) -> int:
        return Fmt.as_int(self.raw.get("ETS6124CanChannel", 1), 1)

    @property
    def ETS6124LinChannel(self) -> int:
        return Fmt.as_int(self.raw.get("ETS6124LinChannel", 3), 3)

    @property
    def CommCANChannelNum(self) -> int:
        return Fmt.as_int(self.raw.get("CommCANChannelNum", 1), 1)

    @property
    def ECUIndex(self) -> int:
        return Fmt.as_int(self.raw.get("ECUIndex", 1), 1)

    @property
    def NetWorkName(self) -> str:
        return str(self.raw.get("NetWorkName", ""))

    @property
    def ETS6124Addr(self) -> str:
        return str(self.raw.get("ETS6124Addr", ""))

    @property
    def ETS6124Addr_int(self) -> int:
        return Fmt.hx(self.raw.get("ETS6124Addr", 0), 0)

    @property
    def WakeupMsgCANChannelNum(self) -> int:
        return Fmt.as_int(self.raw.get("WakeupMsgCANChannelNum", self.CommCANChannelNum), self.CommCANChannelNum)

    @property
    def DiagCANChannelName(self) -> str:
        return str(self.raw.get("DiagCANChannelName", ""))

    @property
    def DiagType(self) -> int:
        return Fmt.as_int(self.raw.get("DiagType", 1), 1)

    @property
    def CommCANChannelName(self) -> str:
        return str(self.raw.get("CommCANChannelName", ""))

    @property
    def LINChannelName(self) -> str:
        return str(self.raw.get("LINChannelName", ""))

    @property
    def LINChannelNum(self) -> int:
        return Fmt.as_int(self.raw.get("LINChannelNum", 1), 1)

    @property
    def DiagCANChannelNum(self) -> int:
        return Fmt.as_int(self.raw.get("DiagCANChannelNum", self.CommCANChannelNum), self.CommCANChannelNum)

    @property
    def NMMsgID_int(self) -> int:
        return Fmt.hx(self.raw.get("NMMsgID", 0), 0)

    @property
    def WakeupMsgID_int(self) -> int:
        return Fmt.hx(self.raw.get("WakeupMsgID", 0x47F), 0x47F)

    @property
    def WakeupMsgDLC(self) -> int:
        return Fmt.as_int(self.raw.get("WakeupMsgDLC", 8), 8)

    @property
    def WakeupMsgType(self) -> str:
        return str(self.raw.get("WakeupMsgType", "CAN"))

    @property
    def WakeupMsgData_hex(self) -> str:
        return str(self.raw.get("WakeupMsgData", ""))

    @property
    def WakeupMsgData_bytes(self) -> bytes:
        data_str = self.raw.get("WakeupMsgData", "00 00 00 00 00 00 00 00")
        return Fmt.hex_bytes(data_str)

    @property
    def WakeupMsgPeriod_s(self) -> float:
        return Fmt.ms_to_s(self.raw.get("WakeupMsgPeriod", 100), 100)

    @property
    def WakeupMsgPeriod_ms(self) -> int:
        return Fmt.as_int(self.raw.get("WakeupMsgPeriod", 100), 100)

    @property
    def ISleep(self) -> float:
        return Fmt.as_float(self.raw.get("ISleep", 0), 0.0)

    @property
    def DataBasePath(self) -> str:
        return str(self.raw.get("DataBasePath", ""))

    @property
    def DataBaseType(self) -> str:
        path = self.DataBasePath
        if not path:
            return ""
        ext = "." + str(path).replace("\\", "/").split("/")[-1].split(".")[-1].lower() if "." in path else ""
        if ext == ".dbc":
            return "dbc"
        elif ext in (".arxml", ".json"):
            return "arxml"
        elif ext == ".ldf":
            return "ldf"
        return ""

    @property
    def DataBaseDBCName(self) -> str:
        path = self.DataBasePath
        if not path:
            return ""
        name = str(path).replace("\\", "/").split("/")[-1]
        ext = "." + name.split(".")[-1].lower() if "." in name else ""
        return name if ext in (".dbc", ".arxml", ".json") else ""

    @property
    def DataBaseLDFName(self) -> str:
        path = self.DataBasePath
        if not path:
            return ""
        name = str(path).replace("\\", "/").split("/")[-1]
        ext = "." + name.split(".")[-1].lower() if "." in name else ""
        return name if ext == ".ldf" else ""

    @property
    def dllPath_2701(self) -> str:
        raw = str(self.raw.get("dllPath_2701", "SHA_XXX_2701.dll") or "").strip()
        if not raw:
            return ""
        p = Path(raw)
        if p.is_absolute():
            return str(p)
        return str(SEC_DLL_DIR / p)

    @property
    def dllPath_2711(self) -> str:
        raw = str(self.raw.get("dllPath_2711", "SHA_XXX_2711.dll") or "").strip()
        if not raw:
            return ""
        p = Path(raw)
        if p.is_absolute():
            return str(p)
        return str(SEC_DLL_DIR / p)
