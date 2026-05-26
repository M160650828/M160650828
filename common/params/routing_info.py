from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Union

from ._base import Fmt


@dataclass
class RoutingInfoCfg:
    raw: Union[List[Dict[str, Any]], Dict[str, Any]]

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
                e = dict(it)
                # 源报文
                e['SrcMsgId'] = Fmt.hx(it.get('SrcMsgId'), 0)
                e['SrcMsgDLC'] = Fmt.as_int(it.get('SrcMsgDLC', 8), 8)
                e['SrcMsgCycleTime'] = Fmt.as_int(it.get('SrcMsgCycleTime', 10), 10)
                e['SrcMsgFrameType'] = str(it.get('SrcMsgFrameType', '')).upper()
                # 目的报文
                e['DestMsgId'] = Fmt.hx(it.get('DestMsgId'), 0)
                e['DestMsgDLC'] = Fmt.as_int(it.get('DestMsgDLC', 8), 8)
                e['DestMsgCycleTime'] = Fmt.as_int(it.get('DestMsgCycleTime', 0) or 0, 0)
                e['DestMsgMinUpdateTime'] = Fmt.as_int(it.get('DestMsgMinUpdateTime', 0) or 0, 0)
                e['RoutingType'] = str(it.get('RoutingType', ''))
                e['SrcNet'] = str(it.get('SrcNet', ''))
                e['DestNet'] = str(it.get('DestNet', ''))
                e['SrcNode'] = str(it.get('SrcNode', ''))
                e['SrcMsgE2EDataID'] = Fmt.hx(it.get('SrcMsgE2EDataID', 0), 0)
                e['SrcMsgMinUpdateTime'] = Fmt.as_int(it.get('SrcMsgMinUpdateTime', 0) or 0, 0)
                e['SrcMsgName'] = str(it.get('SrcMsgName', ''))
                e['SrcSignalName'] = str(it.get('SrcSignalName', ''))
                e['SrcStartBit'] = Fmt.as_int(it.get('SrcStartBit', 0), 0)
                e['SrcBitLength'] = Fmt.as_int(it.get('SrcBitLength', 0), 0)
                e['SrcByteOrder'] = str(it.get('SrcByteOrder', ''))
                e['DestMessageName'] = str(it.get('DestMessageName', ''))
                e['DestSignalName'] = str(it.get('DestSignalName', ''))
                e['DestStartBit'] = Fmt.as_int(it.get('DestStartBit', 0), 0)
                e['DestBitLength'] = Fmt.as_int(it.get('DestBitLength', 0), 0)
                e['DestByteOrder'] = str(it.get('DestByteOrder', ''))
                e['DestInitValue'] = Fmt.hx(it.get('DestInitValue', 0), 0)  # 支持 "0x0" 格式
                e['Ttimeout'] = Fmt.as_int(it.get('Ttimeout', 0), 0)
                e['TimeOutValue'] = Fmt.hx(it.get('TimeOutValue', 0), 0)  # 支持 "0x1FF" 等十六进制格式
                e['TriggerMode'] = str(it.get('TriggerMode', ''))
                e['TransmitDelayTime'] = Fmt.as_int(it.get('TransmitDelayTime', 0), 0)
                out.append(e)
            except Exception:
                out.append(dict(it))
        return out

