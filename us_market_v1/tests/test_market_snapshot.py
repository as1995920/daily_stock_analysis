from datetime import date

from src.config import WatchlistConfig
from src.market_snapshot import collect_market_snapshot


class FakeProvider:
    source_name = "fake"

    def get_quote(self, ticker, market_date):
        if ticker == "IQQ":
            return {"ticker": ticker, "market_date": market_date.isoformat(), "status": "DATA_UNAVAILABLE", "source": self.source_name, "error": "not found"}
        return {
            "ticker": ticker,
            "market_date": market_date.isoformat(),
            "close": 100,
            "previous_close": 99,
            "high": 101,
            "low": 98,
            "volume": 1000,
            "source": self.source_name,
        }


def test_snapshot_groups_assets_and_preserves_unavailable_status():
    snapshot = collect_market_snapshot(
        FakeProvider(),
        WatchlistConfig(("VOO", "IQQ"), ("NVDA",)),
        date(2026, 8, 28),
    )
    assert snapshot["schema_version"] == "phase-b.v1"
    assert snapshot["groups"]["portfolio"]["VOO"]["status"] == "OK"
    assert snapshot["groups"]["portfolio"]["IQQ"]["status"] == "DATA_UNAVAILABLE"
    assert snapshot["groups"]["watchlist"]["NVDA"]["status"] == "OK"

