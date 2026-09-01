"""Upcoming-event provider boundary."""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol


class EventProvider(Protocol):
    def get_events(self, tickers: list[str], start: date, end: date) -> list[dict[str, Any]]: ...

