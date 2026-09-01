"""NYSE calendar provider and date helpers."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Protocol

import pandas_market_calendars as mcal


def normalize_market_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"unsupported market date: {type(value).__name__}")


class CalendarProvider(Protocol):
    def get_latest_completed_us_trading_session(self, as_of: datetime) -> date | None:
        """Return the latest completed NYSE session, or None when unavailable."""


class NyseCalendarProvider:
    """Use the NYSE schedule, including holidays and early closes."""

    def __init__(self, calendar_name: str = "NYSE"):
        self.calendar = mcal.get_calendar(calendar_name)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def get_latest_completed_us_trading_session(self, as_of: datetime) -> date | None:
        as_of_utc = self._as_utc(as_of)
        start = (as_of_utc - timedelta(days=31)).date()
        end = as_of_utc.date()
        schedule = self.calendar.schedule(start_date=start, end_date=end)
        completed = schedule[schedule["market_close"] <= as_of_utc]
        if completed.empty:
            return None
        return completed.index[-1].date()

    def is_trading_session(self, market_date: date) -> bool:
        schedule = self.calendar.schedule(start_date=market_date, end_date=market_date)
        return not schedule.empty

