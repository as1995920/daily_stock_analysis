"""Yahoo Finance adapter used by Phase B.

All yfinance-specific objects stay inside this module. Downstream code receives
plain dictionaries and can be tested with a fake MarketDataProvider.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf


class YFinanceMarketDataProvider:
    source_name = "Yahoo Finance via yfinance"

    def __init__(self, cache_dir: str | Path = "data/cache/yfinance"):
        # yfinance 1.7 persists timezone/cookie metadata in a SQLite cache.
        # Keep that state inside the project runtime directory so the provider
        # does not depend on an inaccessible global user cache location.
        cache_path = Path(cache_dir)
        cache_path.mkdir(parents=True, exist_ok=True)
        yf.set_tz_cache_location(str(cache_path))

    @staticmethod
    def _index_date(value: Any) -> date:
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is not None:
            timestamp = timestamp.tz_convert("America/New_York")
        return timestamp.date()

    def get_history(self, ticker: str, start: date, end: date) -> list[dict[str, Any]]:
        # yfinance's end parameter is exclusive, so include the requested end date.
        ticker_client = yf.Ticker(ticker)
        frame = ticker_client.history(
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            auto_adjust=False,
            actions=False,
        )
        if frame is None or frame.empty:
            return []

        rows = self._frame_to_rows(frame)
        # Yahoo may expose the latest row's high/low/volume before its close in
        # the range endpoint. Retry the same source with its short-window
        # endpoint, then replace only rows whose close is actually missing.
        if any(row["market_date"] == end.isoformat() and row.get("close") is None for row in rows):
            recent = ticker_client.history(period="1d", auto_adjust=False, actions=False)
            if recent is not None and not recent.empty:
                fallback_rows = {
                    row["market_date"]: row for row in self._frame_to_rows(recent)
                }
                rows = [
                    fallback_rows.get(row["market_date"], row)
                    if row.get("close") is None else row
                    for row in rows
                ]
        return rows

    def _frame_to_rows(self, frame: pd.DataFrame) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for index, row in frame.iterrows():
            rows.append(
                {
                    "market_date": self._index_date(index).isoformat(),
                    "open": self._number(row.get("Open")),
                    "high": self._number(row.get("High")),
                    "low": self._number(row.get("Low")),
                    "close": self._number(row.get("Close")),
                    "volume": self._number(row.get("Volume")),
                }
            )
        return rows

    def get_market_history(self, ticker: str, start: date, end: date) -> list[dict[str, Any]]:
        return self.get_history(ticker, start, end)

    @staticmethod
    def _number(value: Any) -> float | int | None:
        if value is None or pd.isna(value):
            return None
        number = float(value)
        return int(number) if number.is_integer() else number

    def get_quote(self, ticker: str, market_date: date) -> dict[str, Any]:
        history = self.get_history(ticker, market_date - timedelta(days=90), market_date)
        rows = [row for row in history if row["market_date"] <= market_date.isoformat()]
        target = next((row for row in rows if row["market_date"] == market_date.isoformat()), None)
        previous = rows[-2] if len(rows) >= 2 and target is not None else None

        if target is None:
            return {
                "ticker": ticker,
                "market_date": market_date.isoformat(),
                "status": "DATA_UNAVAILABLE",
                "source": self.source_name,
                "error": "target market date is absent from provider history",
            }

        record = {
            "ticker": ticker,
            "market_date": market_date.isoformat(),
            "close": target.get("close"),
            "previous_close": previous.get("close") if previous else None,
            "high": target.get("high"),
            "low": target.get("low"),
            "volume": target.get("volume"),
            "source": self.source_name,
        }
        return record

    def get_volume(self, ticker: str, market_date: date) -> int | float | None:
        return self.get_quote(ticker, market_date).get("volume")

    def get_company_info(self, ticker: str) -> dict[str, Any]:
        raise NotImplementedError("company info is planned for Phase D")

    def get_news(self, ticker: str, since: date) -> list[dict[str, Any]]:
        raise NotImplementedError("news is planned for Phase D")

