"""Provider boundary for market data, independent of the concrete vendor."""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol


class MarketDataProvider(Protocol):
    def get_quote(self, ticker: str, market_date: date) -> dict[str, Any]: ...

    def get_history(self, ticker: str, start: date, end: date) -> list[dict[str, Any]]: ...

    def get_market_history(self, ticker: str, start: date, end: date) -> list[dict[str, Any]]: ...

    def get_volume(self, ticker: str, market_date: date) -> int | float | None: ...

    def get_company_info(self, ticker: str) -> dict[str, Any]: ...

    def get_news(self, ticker: str, since: date) -> list[dict[str, Any]]: ...

