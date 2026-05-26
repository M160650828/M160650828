from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Union

from ._base import Fmt


@dataclass
class E2EInfoCfg:
    raw: Union[Dict[str, Any], List[Any]]

    @property
    def data(self) -> Union[Dict[str, Any], List[Any]]:
        return self.raw

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
                sg = it.get("SiganlGroupName") or it.get("SignalGroupName") or {}
                fr = it.get("Frame") or {}
                info = it.get("Info") or {}
                name = sg.get("SiganlName") or sg.get("SignalName") or fr.get("FrameName")
                if not name:
                    continue
                e = {
                    'SignalName': str(name),
                    'StartByte': Fmt.hx(sg.get('StartByte'), 0),
                    'SignalLength': Fmt.hx(sg.get('SignalLength'), 0),
                    'DataID': Fmt.hx(sg.get('DataID'), 0),
                    'FrameName': str(fr.get('FrameName') or name),
                    'CANID_int': Fmt.hx(fr.get('CANID'), 0),
                    'DataLength': Fmt.hx(fr.get('DataLength'), 8),
                    'Cycle': Fmt.hx(fr.get('Cycle'), 0),
                    'CANFD': Fmt.hx(fr.get('CANFD'), 0),
                    'Extended': Fmt.hx(fr.get('Extended'), 0),
                    'Cluster': str(info.get('Cluster', '')),
                    'Sender': str(info.get('Sender', '')),
                    'Receiver': str(info.get('Receiver', '')),
                }
                out.append(e)
            except Exception:
                pass
        return out

