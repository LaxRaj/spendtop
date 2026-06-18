from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Literal

from spendtop.core.cache import SpendEvent

ConnectorStatus = Literal["ok", "disconnected", "unconfigured"]


class SpendConnector(ABC):
    name: str

    @abstractmethod
    async def pull(self, since: datetime) -> list[SpendEvent]: ...

    def status(self) -> ConnectorStatus:
        return "unconfigured"
