from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Union

from ._base import Fmt


@dataclass
class ChannelMappingCfg:
    raw: Union[List[Dict[str, Any]], Dict[str, Any]]

    @staticmethod
    def _parse_channel_str(val: Any) -> Tuple[str, int]:
        """
        支持以下格式：
        - "30513024300058 ：1" -> ("30513024300058", 1)
        - "30513024300058:2"   -> ("30513024300058", 2)
        - 纯数字 1 或 "1"     -> ("", 1)
        返回: (sn, channel_num)
        """
        if val is None:
            return ("", 0)
        s = str(val).strip()
        for sep in ['：', ':']:
            if sep in s:
                parts = s.split(sep, 1)
                sn = parts[0].strip()
                ch_str = parts[1].strip() if len(parts) > 1 else "0"
                ch = Fmt.as_int(ch_str, 0)
                return (sn, ch)
        ch = Fmt.as_int(s, 0)
        return ("", ch)

    @property
    def map_net_to_channel(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        items: List[Dict[str, Any]]
        if isinstance(self.raw, list):
            items = [it for it in self.raw if isinstance(it, dict)]
        elif isinstance(self.raw, dict):
            items = [self.raw]
        else:
            items = []
        for it in items:
            try:
                net = str(it.get("Net"))
                _, ch = self._parse_channel_str(it.get("CANoeCANChannel"))
                if net and ch:
                    out[net] = ch
            except Exception:
                pass
        return out

    @property
    def map_net_to_hwid(self) -> Dict[str, str]:
        out: Dict[str, str] = {}
        items: List[Dict[str, Any]]
        if isinstance(self.raw, list):
            items = [it for it in self.raw if isinstance(it, dict)]
        elif isinstance(self.raw, dict):
            items = [self.raw]
        else:
            items = []
        for it in items:
            try:
                net = str(it.get("Net"))
                sn, ch = self._parse_channel_str(it.get("CANoeCANChannel"))
                if net and sn and ch:
                    out[net] = f"{sn}_CAN_{ch}"
            except Exception:
                pass
        return out

    @property
    def all_hwids(self) -> List[str]:
        return list(set(self.map_net_to_hwid.values()))

    @property
    def entries(self) -> List[Dict[str, Any]]:
        if isinstance(self.raw, list):
            return [it for it in self.raw if isinstance(it, dict)]
        if isinstance(self.raw, dict):
            return [self.raw]
        return []

    @property
    def normalized_entries(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for it in self.entries:
            try:
                sn, ch = self._parse_channel_str(it.get('CANoeCANChannel'))
                e = {
                    'Net': str(it.get('Net')),
                    'CANoeCANChannel': ch,
                    'CANoeCANChannel_SN': sn,
                    'CANoeCANChannel_HWID': f"{sn}_CAN_{ch}" if sn and ch else "",
                    'NMMsgID_int': Fmt.hx(it.get('NMMsgID', 0), 0),
                    'WakeupMsgId_int': Fmt.hx(it.get('WakeupMsgId', 0), 0),
                    'WakeupMsgCANType': str(it.get('WakeupMsgCANType', '')),
                    'WakeupMsgDLC': Fmt.as_int(it.get('WakeupMsgDLC', 0), 0),
                    'WakeupMsgData_hex': str(it.get('WakeupMsgData', '')),
                    'WakeupMsgData_bytes': Fmt.hex_bytes(it.get('WakeupMsgData', '')),
                    'WakeupMsgPeriod_ms': Fmt.as_int(it.get('WakeupMsgPeriod', 0), 0),
                }
                out.append(e)
            except Exception:
                pass
        return out

    def net_to_channel(self, net: str, default: int = 1) -> int:
        return int(self.map_net_to_channel.get(str(net), default))

    def net_to_hwid(self, net: str, default: str = "") -> str:
        return self.map_net_to_hwid.get(str(net), default)

