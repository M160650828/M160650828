"""
从CAN报文中解析信号值

使用示例:
    from common.signal_parser import sig

    # 方式1：在CAN回调中实时更新
    def _on_canmsg(bustype, busid, msg, cookie):
        sig.update(msg)

    # 方式2：批量加载缓存报文
    sig.load_messages(ctx.can.messages)

    # 读取信号值
    speed = sig.VehicleSpeed.phy       # 最新物理值
    raw = sig.VehicleSpeed.raw         # 最新原始值
    ts = sig.VehicleSpeed.time         # 最新时间戳

    # 历史访问
    first = sig.VehicleSpeed[0]        # 第一个
    last = sig.VehicleSpeed[-1]        # 最后一个
    recent = sig.VehicleSpeed[-5:]     # 最近5个
    all_data = sig.VehicleSpeed[:]     # 全部历史

    # 清空缓存
    sig.clear()
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Union, Tuple
from collections import defaultdict
import time

from .db_parser import sigdb, extract_signal

@dataclass
class SignalValue:
    phy: float
    raw: int
    time_ms: float

class Signal:
    def __init__(self, name: str, cache: 'SignalCache'):
        self._name = name
        self._cache = cache

    @property
    def phy(self) -> Optional[float]:
        v = self._cache._get_latest(self._name)
        return v.phy if v else None

    @property
    def raw(self) -> Optional[int]:
        v = self._cache._get_latest(self._name)
        return v.raw if v else None

    @property
    def time(self) -> Optional[float]:
        v = self._cache._get_latest(self._name)
        return v.time_ms if v else None

    @property
    def info(self) -> Optional[SignalValue]:
        return self._cache._get_latest(self._name)

    def __getitem__(self, index) -> Union[Optional[SignalValue], List[SignalValue]]:
        history = self._cache._get_history(self._name)
        if isinstance(index, slice):
            return history[index]
        else:
            if not history:
                return None
            try:
                return history[index]
            except IndexError:
                return None

    def __len__(self) -> int:
        return len(self._cache._get_history(self._name))

    def __iter__(self):
        return iter(self._cache._get_history(self._name))

    def __bool__(self) -> bool:
        return len(self) > 0

    def __repr__(self) -> str:
        phy = self.phy
        return f"<Signal {self._name}: {phy}>" if phy is not None else f"<Signal {self._name}: None>"


class SignalCache:
    def __init__(self):
        self._msg_cache: Dict[int, List[Tuple[bytes, float]]] = defaultdict(list)
        self._signal_cache: Dict[str, List[SignalValue]] = defaultdict(list)

    def update(self, msg) -> None:
        try:
            msg_id = getattr(msg, 'msgid', None)
            if msg_id is None:
                return

            payload = getattr(msg, 'payload', b'') or b''
            ts_ns = getattr(msg, 'timestamp_ns', None)
            if ts_ns is not None:
                time_ms = float(ts_ns) / 1_000_000.0
            else:
                time_ms = time.time() * 1000.0

            self._cache_and_parse(msg_id, payload, time_ms)

        except Exception as e:
            print(f"[SignalParser] update error: {e}")

    def load_messages(self, messages) -> None:
        for m in messages:
            msg_id = getattr(m, 'id', None)
            if msg_id is None:
                continue

            payload_hex = getattr(m, 'payload_hex', '')
            time_ms = getattr(m, 'time_ms', time.time() * 1000.0)

            try:
                payload = bytes.fromhex(payload_hex) if payload_hex else b''
            except Exception:
                payload = b''

            self._cache_and_parse(msg_id, payload, time_ms)

    def clear(self) -> None:
        self._msg_cache.clear()
        self._signal_cache.clear()


    def get(self, name: str) -> Optional[SignalValue]:
        return self._get_latest(name)

    def signals(self) -> List[str]:
        return list(self._signal_cache.keys())

    def __getattr__(self, name: str) -> Signal:
        if name.startswith('_'):
            raise AttributeError(name)
        return Signal(name, self)

    def _cache_and_parse(self, msg_id: int, payload: bytes, time_ms: float) -> None:
        self._msg_cache[msg_id].append((payload, time_ms))

        sig_names = sigdb.get_msg_signals(msg_id)
        for sig_name in sig_names:
            sig_def = sigdb.get_signal_def(sig_name)
            if sig_def:
                raw, phy = extract_signal(payload, sig_def)
                sv = SignalValue(phy=phy, raw=raw, time_ms=time_ms)
                self._signal_cache[sig_name].append(sv)

    def _get_latest(self, name: str) -> Optional[SignalValue]:
        history = self._signal_cache.get(name)
        return history[-1] if history else None

    def _get_history(self, name: str) -> List[SignalValue]:
        return self._signal_cache.get(name, [])
        
sig = SignalCache()
