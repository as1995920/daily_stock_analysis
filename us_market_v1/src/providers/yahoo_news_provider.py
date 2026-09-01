"""Yahoo Finance news adapter with normalized source metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yfinance as yf


TIER_1_DOMAINS = {
    "sec.gov", "reuters.com", "bloomberg.com", "cnbc.com", "wsj.com", "ft.com",
    "nasdaq.com", "nyse.com", "federalreserve.gov", "bls.gov", "bea.gov",
}
TIER_2_DOMAINS = {
    "marketwatch.com", "barrons.com", "businesswire.com", "prnewswire.com",
    "theglobeandmail.com", "investors.com",
}


def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower().split(":", 1)[0]
    return host[4:] if host.startswith("www.") else host


def source_tier(url: str, provider_name: str = "") -> str:
    domain = _domain(url)
    if any(domain == value or domain.endswith("." + value) for value in TIER_1_DOMAINS):
        return "TIER_1"
    if any(domain == value or domain.endswith("." + value) for value in TIER_2_DOMAINS):
        return "TIER_2"
    return "TIER_3"


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class YahooNewsProvider:
    source_name = "Yahoo Finance news"

    def __init__(self, cache_dir: str | Path = "data/cache/yfinance"):
        cache_path = Path(cache_dir)
        cache_path.mkdir(parents=True, exist_ok=True)
        yf.set_tz_cache_location(str(cache_path))

    def get_news(self, ticker: str, since: datetime, until: datetime) -> list[dict[str, Any]]:
        since_utc = since.astimezone(timezone.utc) if since.tzinfo else since.replace(tzinfo=timezone.utc)
        until_utc = until.astimezone(timezone.utc) if until.tzinfo else until.replace(tzinfo=timezone.utc)
        raw_items = yf.Ticker(ticker).news or []
        normalized: list[dict[str, Any]] = []
        for item in raw_items:
            content = item.get("content", item) if isinstance(item, dict) else {}
            title = content.get("title")
            published_at = _parse_datetime(content.get("pubDate") or content.get("displayTime"))
            click = content.get("clickThroughUrl") or {}
            canonical = content.get("canonicalUrl") or {}
            url = click.get("url") or canonical.get("url")
            provider = content.get("provider") or {}
            provider_name = provider.get("displayName") or self.source_name
            if not title or not published_at or not url:
                continue
            published_utc = published_at.astimezone(timezone.utc)
            if published_utc < since_utc or published_utc > until_utc:
                continue
            normalized.append(
                {
                    "ticker": ticker,
                    "title": str(title).strip(),
                    "summary": (content.get("summary") or content.get("description") or "").strip(),
                    "published_at": published_utc.isoformat(),
                    "source": provider_name,
                    "source_url": url,
                    "tier": source_tier(url, provider_name),
                }
            )
        return normalized

