"""Phase D news and upcoming-event collection, filtering and deduplication."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import re
from typing import Any

from .config import WatchlistConfig
from .market_snapshot import collect_market_snapshot
from .providers.events import EventProvider
from .providers.market_data import MarketDataProvider
from .providers.news import NewsProvider


def _news_key(item: dict[str, Any]) -> str:
    title = re.sub(r"[^a-z0-9]+", "", str(item.get("title", "")).lower())
    url = str(item.get("source_url", ""))
    return hashlib.sha256((title or url).encode("utf-8")).hexdigest()


def deduplicate_news(items: list[dict[str, Any]], max_per_event: int = 2) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        groups.setdefault(_news_key(item), []).append(item)
    tier_order = {"TIER_1": 1, "TIER_2": 2, "TIER_3": 3}
    result: list[dict[str, Any]] = []
    for group in groups.values():
        group.sort(key=lambda item: item.get("published_at", ""), reverse=True)
        group.sort(key=lambda item: tier_order.get(item.get("tier", "TIER_3"), 3))
        result.extend(group[:max_per_event])
    result.sort(key=lambda item: item.get("published_at", ""), reverse=True)
    result.sort(key=lambda item: tier_order.get(item.get("tier", "TIER_3"), 3))
    return result


def _event_dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    result = []
    for item in sorted(items, key=lambda value: (value.get("event_date", ""), value.get("event_type", ""))):
        key = (item.get("ticker"), item.get("event_type"), item.get("event_date"), item.get("title"))
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def collect_news_events_snapshot(
    news_provider: NewsProvider,
    event_providers: list[EventProvider],
    config: WatchlistConfig,
    market_date: date,
    as_of: datetime | None = None,
    market_snapshot: dict[str, Any] | None = None,
    market_data_provider: MarketDataProvider | None = None,
) -> dict[str, Any]:
    as_of = as_of or datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    since = as_of - timedelta(hours=48)
    tickers = list(config.all_tickers)
    if market_snapshot:
        tickers = list(dict.fromkeys(item["ticker"] for item in market_snapshot["assets"].values()))
    elif market_data_provider:
        snapshot = collect_market_snapshot(market_data_provider, config, market_date)
        tickers = list(snapshot["assets"])

    news_items: list[dict[str, Any]] = []
    news_errors: list[str] = []
    for ticker in tickers:
        try:
            news_items.extend(news_provider.get_news(ticker, since, as_of))
        except Exception as exc:
            news_errors.append(f"{ticker}: {type(exc).__name__}")
    news_items = deduplicate_news(news_items)
    news_status = "OK" if news_items or len(news_errors) < len(tickers) else "DATA_UNAVAILABLE"

    event_start = market_date
    event_end = market_date + timedelta(days=7)
    event_items: list[dict[str, Any]] = []
    event_errors: list[str] = []
    event_tickers = list(config.all_tickers)
    for index, provider in enumerate(event_providers):
        try:
            event_items.extend(provider.get_events(event_tickers, event_start, event_end))
            event_errors.extend(
                f"provider_{index}: {error}"
                for error in getattr(provider, "last_errors", [])
            )
        except Exception as exc:
            event_errors.append(f"provider_{index}: {type(exc).__name__}")
    event_items = _event_dedupe(event_items)
    event_status = "OK" if event_items or not event_errors else "DATA_UNAVAILABLE"

    return {
        "schema_version": "phase-d.v1",
        "market_date": market_date.isoformat(),
        "generated_at_utc": as_of.astimezone(timezone.utc).isoformat(),
        "news_window": {"since": since.astimezone(timezone.utc).isoformat(), "until": as_of.astimezone(timezone.utc).isoformat()},
        "event_window": {"start": event_start.isoformat(), "end": event_end.isoformat()},
        "news": {"status": news_status, "items": news_items, "errors": news_errors},
        "events": {"status": event_status, "items": event_items, "errors": event_errors},
        "policy": "News is source/time filtered and deduplicated; event dates are not inferred when official sources fail.",
    }

