"""Company event adapter based on yfinance's calendar endpoint."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yfinance as yf


class YahooCompanyEventProvider:
    source_name = "Yahoo Finance company calendar"

    def __init__(self, cache_dir: str | Path = "data/cache/yfinance"):
        cache_path = Path(cache_dir)
        cache_path.mkdir(parents=True, exist_ok=True)
        yf.set_tz_cache_location(str(cache_path))
        self.last_errors: list[str] = []

    def get_events(self, tickers: list[str], start: date, end: date) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        self.last_errors = []
        for ticker in tickers:
            try:
                calendar = yf.Ticker(ticker).calendar or {}
            except Exception as exc:
                self.last_errors.append(f"{ticker}: {type(exc).__name__}")
                continue
            earnings = calendar.get("Earnings Date", [])
            if isinstance(earnings, (date, str)):
                earnings = [earnings]
            for value in earnings:
                event_date = value if isinstance(value, date) else date.fromisoformat(str(value))
                if start <= event_date <= end:
                    events.append(
                        {
                            "ticker": ticker,
                            "event_type": "EARNINGS",
                            "title": f"{ticker} earnings date",
                            "event_date": event_date.isoformat(),
                            "source": self.source_name,
                            "source_url": f"https://finance.yahoo.com/quote/{ticker}/calendar/",
                            "tier": "TIER_3",
                        }
                    )
        return events

