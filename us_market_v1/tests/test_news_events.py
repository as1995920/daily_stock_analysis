from datetime import date, datetime, timezone

from src.config import WatchlistConfig
from src.news_events import collect_news_events_snapshot, deduplicate_news


def test_news_dedup_keeps_at_most_two_sources():
    items = [
        {"title": "Market event", "source_url": "https://a.example/1", "tier": "TIER_3", "published_at": "2026-08-28T10:00:00+00:00"},
        {"title": "Market event", "source_url": "https://b.example/2", "tier": "TIER_1", "published_at": "2026-08-28T11:00:00+00:00"},
        {"title": "Market event", "source_url": "https://c.example/3", "tier": "TIER_2", "published_at": "2026-08-28T12:00:00+00:00"},
    ]
    result = deduplicate_news(items)
    assert len(result) == 2
    assert result[0]["tier"] == "TIER_1"


class FakeNewsProvider:
    def get_news(self, ticker, since, until):
        return [{
            "ticker": ticker, "title": "Same event", "summary": "verified summary",
            "published_at": "2026-08-28T12:00:00+00:00", "source": "Example",
            "source_url": "https://example.test/news", "tier": "TIER_2",
        }]


class FakeEventProvider:
    def get_events(self, tickers, start, end):
        return [{
            "ticker": tickers[0], "event_type": "EARNINGS", "title": "Earnings date",
            "event_date": "2026-08-30", "source": "Example", "source_url": "https://example.test/calendar",
            "tier": "TIER_2",
        }]


def test_phase_d_snapshot_filters_window_and_preserves_provenance():
    snapshot = collect_news_events_snapshot(
        FakeNewsProvider(), [FakeEventProvider()], WatchlistConfig(("VOO",), ()),
        date(2026, 8, 28), datetime(2026, 8, 29, tzinfo=timezone.utc),
    )
    assert snapshot["schema_version"] == "phase-d.v1"
    assert snapshot["news"]["status"] == "OK"
    assert snapshot["news"]["items"][0]["source_url"]
    assert snapshot["events"]["items"][0]["event_date"] == "2026-08-30"


class FailingEventProvider:
    last_errors = ["BLS: HTTPError"]

    def get_events(self, tickers, start, end):
        return []


def test_event_source_failure_is_not_reported_as_success():
    snapshot = collect_news_events_snapshot(
        FakeNewsProvider(), [FailingEventProvider()], WatchlistConfig(("VOO",), ()),
        date(2026, 8, 28), datetime(2026, 8, 29, tzinfo=timezone.utc),
    )
    assert snapshot["events"]["status"] == "DATA_UNAVAILABLE"
    assert snapshot["events"]["errors"] == ["provider_0: BLS: HTTPError"]

