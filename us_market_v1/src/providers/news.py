"""News provider boundary."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol


class NewsProvider(Protocol):
    def get_news(self, ticker: str, since: datetime, until: datetime) -> list[dict[str, Any]]: ...

