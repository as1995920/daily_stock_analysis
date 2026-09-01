from datetime import date, timedelta

from src.analysis_snapshot import collect_analysis_snapshot
from src.config import WatchlistConfig


class FakeProvider:
    source_name = "fake"

    def get_quote(self, ticker, market_date):
        return {
            "ticker": ticker, "market_date": market_date.isoformat(), "close": 100,
            "previous_close": 99, "high": 101, "low": 98, "volume": 1000,
            "source": self.source_name,
        }

    def get_history(self, ticker, start, end):
        return [
            {"market_date": (date(2025, 1, 1) + timedelta(days=i)).isoformat(), "close": 100 + i * 0.1,
             "high": 101 + i * 0.1, "low": 99 + i * 0.1, "volume": 1000 + i}
            for i in range(220)
        ]


class ProxyProvider(FakeProvider):
    def get_history(self, ticker, start, end):
        rows = super().get_history(ticker, start, end)
        return rows if ticker == "^NDX" else rows[:37]


def test_analysis_snapshot_contains_assets_and_regime():
    snapshot = collect_analysis_snapshot(
        FakeProvider(), WatchlistConfig(("VOO", "IQQ"), ()), date(2026, 8, 28)
    )
    assert snapshot["schema_version"] == "phase-c.v1"
    assert snapshot["assets"]["VOO"]["status"] == "OK"
    assert snapshot["market_regime"]["state"] == "RISK_ON"


def test_analysis_snapshot_uses_explicit_proxy_without_relabeling_history():
    snapshot = collect_analysis_snapshot(
        ProxyProvider(), WatchlistConfig(("IQQ",), ()), date(2026, 8, 28),
        instrument_overrides={
            "IQQ": type("Override", (), {
                "history_proxy": "^NDX",
                "history_proxy_reason": "test proxy",
                "source_url": "https://example.test/iqq",
            })()
        },
    )
    result = snapshot["assets"]["IQQ"]
    assert result["status"] == "OK_WITH_PROXY"
    assert result["ticker"] == "IQQ"
    assert result["history_ticker"] == "^NDX"
    assert result["direct_history_rows"] == 37
    assert result["price"]["close"] == 100

