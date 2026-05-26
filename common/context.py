from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum
from typing import List, Dict, Any, Optional, Union

from library.devices.bob_control import BobControl
from library.devices.power_ctrl import PowerControl


class Direction(IntEnum):
    RX = 0
    TX = 1


@dataclass
class Message:
    id: int = 0
    dlc: int = 0
    channel: int = 0
    time_ms: float = 0.0
    payload_hex: str = ""
    direction: Direction = Direction.RX


class MessageLog:
    def __init__(self) -> None:
        self._data: List[Message] = []

    def append(self, *, id: int, time_ms: float, dlc: int, channel: int, payload_hex: str, direction: Union[Direction, int] = Direction.RX) -> Message:
        m = Message(id=int(id),
                    dlc=int(dlc),
                    channel=int(channel),
                    time_ms=float(time_ms),
                    payload_hex=str(payload_hex or "").upper(),
                    direction=Direction(direction) if not isinstance(direction, Direction) else direction)
        self._data.append(m)
        return m

    def clear(self) -> None:
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __getitem__(self, index):
        return self._data[index]

    def last(self) -> Optional[Message]:
        return self._data[-1] if self._data else None


class BusCtx:
    def __init__(self) -> None:
        self._messages: MessageLog = MessageLog()
        self._info: Dict[str, Any] = {}
        self._filter_channel_list = []
        self._filter_id_list = []
        self._filter_black_id_list = []

    def add_message(self, id: int, *, time_ms: float, dlc: int, channel: int, payload_hex: str, direction: Union[Direction, int] = Direction.RX) -> None:
        if len(self._filter_channel_list) > 0:
            if channel not in self._filter_channel_list:
                return

        if len(self._filter_id_list) > 0:
            if id not in self._filter_id_list:
                return

        if len(self._filter_black_id_list):
            rules = set(self._filter_black_id_list)
            if -id in rules:
                return

        self._messages.append(
            id=id,
            time_ms=time_ms,
            dlc=dlc,
            channel=channel,
            payload_hex=payload_hex,
            direction=direction,
        )

    def set_filter_by_channel(self, channel):
        self._filter_channel_list = [channel]

    def add_filter_by_channel(self, channel):
        if channel not in self._filter_channel_list:
            self._filter_channel_list.append(channel)

    def clear_filter_by_channel(self) -> None:
        self._filter_channel_list = []

    def set_filter_by_id(self, id):
        self._filter_id_list = [id]

    def add_filter_by_id(self, id):
        if id not in self._filter_id_list:
            self._filter_id_list.append(id)

    def clear_filter_by_id(self) -> None:
        self._filter_id_list = []

    def add_black_id(self, *ids: int) -> None:
        for i in ids:
            if -i not in self._filter_black_id_list:
                self._filter_black_id_list.append(-i)

    def clear_black_id(self) -> None:
        self._filter_black_id_list = []

    def clear_filters(self) -> None:
        self._filter_channel_list = []
        self._filter_id_list = []
        self._filter_black_id_list = []

    @property
    def messages(self) -> MessageLog:
        return self._messages

    def clear_messages(self) -> None:
        self._messages.clear()

    def set_filter(self, msg_id):
        self._filter_id_list = [msg_id]

    def set_info(self, key: str, value: Any) -> None:
        self._info[str(key)] = value

    def get_info(self, key: str) -> Any:
        return self._info.get(str(key))

    def clear_info(self) -> None:
        self._info.clear()

    @property
    def info(self) -> Dict[str, Any]:
        return self._info

    def reset_all(self) -> None:
        self.clear_messages()
        self.clear_info()
        self.clear_filters()


class Context:
    def __init__(self) -> None:
        self.can = BusCtx()
        self.lin = BusCtx()

        self.power_ctrl = PowerControl()
        self.bob_ctrl = BobControl()

    def reset_all(self) -> None:
        self.can.reset_all()
        self.lin.reset_all()


ctx = Context()
