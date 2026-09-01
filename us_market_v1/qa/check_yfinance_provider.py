from datetime import date

import pandas as pd

from src.providers import yfinance_provider
from src.providers.yfinance_provider import YFinanceMarketDataProvider


def test_latest_close_fallback_replaces_only_missing_close(monkeypatch, tmp_path):
    class FakeTicker:
        def history(self, **kwargs):
            if "period" in kwargs:
                return pd.DataFrame(
                    {"Open": [709], "High": [713], "Low": [706], "Close": [707], "Volume": [8000]},
                    index=pd.DatetimeIndex(["2026-08-28"], tz="America/New_York"),
                )
            return pd.DataFrame(
                {"Open": [708, 709], "High": [710, 713], "Low": [705, 706], "Close": [708, None], "Volume": [7000, 8000]},
                index=pd.DatetimeIndex(["2026-08-27", "2026-08-28"], tz="America/New_York"),
            )

    monkeypatch.setattr(yfinance_provider.yf, "Ticker", lambda ticker: FakeTicker())
    provider = YFinanceMarketDataProvider(tmp_path / "cache")
    rows = provider.get_history("VOO", date(2026, 8, 27), date(2026, 8, 28))
    assert rows[-1]["close"] == 707

