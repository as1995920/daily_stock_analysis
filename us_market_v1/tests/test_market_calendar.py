from datetime import date, datetime, timezone

import pytest

from src.calendar import NyseCalendarProvider, normalize_market_date


def test_normalize_market_date():
    expected = date(2026, 8, 28)
    assert normalize_market_date("2026-08-28") == expected
    assert normalize_market_date(expected) == expected
    assert normalize_market_date(datetime(2026, 8, 28, 6, 30)) == expected


def test_normalize_market_date_rejects_unknown_type():
    with pytest.raises(TypeError):
        normalize_market_date(123)  # type: ignore[arg-type]


def test_nyse_calendar_handles_weekend_and_session_close():
    provider = NyseCalendarProvider()
    assert not provider.is_trading_session(date(2026, 8, 29))
    assert provider.get_latest_completed_us_trading_session(
        datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc)
    ) == date(2026, 8, 28)
    assert provider.get_latest_completed_us_trading_session(
        datetime(2026, 8, 28, 19, 0, tzinfo=timezone.utc)
    ) == date(2026, 8, 27)

