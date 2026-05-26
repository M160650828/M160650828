from abc import ABC, abstractmethod
from typing import Any, Optional


class BusSim(ABC):
    @abstractmethod
    def init(self, *args, **kwargs):
        pass

    @abstractmethod
    def send(self, data: bytes, func_req: bool = False) -> int:
        pass

    @abstractmethod
    def recv(self, timeout: float = 10) -> tuple[bool, Optional[Any]]:
        pass

    @abstractmethod
    def close(self):
        pass

    @property
    @abstractmethod
    def tx_id(self) -> Optional[int]:
        pass

    @property
    @abstractmethod
    def rx_id(self) -> Optional[int]:
        pass

    @property
    @abstractmethod
    def func_id(self) -> Optional[int]:
        pass

    @property
    def is_canfd(self) -> bool:
        return False

    def get_tx_id(self, func_req: bool = False) -> Optional[int]:
        return self.func_id if func_req else self.tx_id

