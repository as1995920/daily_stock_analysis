"""Best-effort official macro-calendar reader.

The provider never invents dates. A blocked or changed official page is
returned as an error by the Phase D collector and becomes DATA_UNAVAILABLE.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from html.parser import HTMLParser
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self.parts.append(text)


def _get_page_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "US-Market-Daily-Intelligence/0.1"})
    with urlopen(request, timeout=20) as response:
        parser = _TextParser()
        parser.feed(response.read().decode("utf-8", errors="replace"))
        return "\n".join(parser.parts)


def _get_raw_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "US-Market-Daily-Intelligence/0.1"})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def _date_from_month_day(year: int, month: str, day: int) -> date:
    return datetime.strptime(f"{year} {month} {day}", "%Y %B %d").date()


class OfficialMacroEventProvider:
    source_name = "Official US macro calendars"
    urls = {
        "BLS": (
            "https://www.bls.gov/schedule/news_release/us_sched.htm",
            "https://www.bls.gov/schedule/news_release/bls.ics",
        ),
        "BEA": "https://www.bea.gov/news/schedule",
        "FOMC": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
    }

    def __init__(self):
        self.last_errors: list[str] = []

    def get_events(self, tickers: list[str], start: date, end: date) -> list[dict[str, Any]]:
        del tickers
        events: list[dict[str, Any]] = []
        errors: list[str] = []
        for source, configured_url in self.urls.items():
            urls = configured_url if isinstance(configured_url, tuple) else (configured_url,)
            if source == "BLS":
                urls = (*urls, *self._bls_month_urls(start, end))
            source_succeeded = False
            source_errors: list[str] = []
            for url in urls:
                try:
                    text = _get_raw_text(url) if url.endswith(".ics") else _get_page_text(url)
                    if source == "FOMC":
                        parsed = self._parse_fomc(text, start, end, url)
                    elif source == "BEA":
                        parsed = self._parse_bea(text, start, end, url)
                    elif url.endswith(".ics"):
                        parsed = self._parse_bls_ics(text, start, end, url)
                    elif "/schedule/" in url and "_sched.htm" in url:
                        parsed = self._parse_bls_month(text, start, end, url)
                    else:
                        parsed = self._parse_bls(text, start, end, url)
                    events.extend(parsed)
                    source_succeeded = True
                    break
                except (HTTPError, URLError, TimeoutError, OSError) as exc:
                    source_errors.append(f"{source}: {url}: {type(exc).__name__}")
            if not source_succeeded:
                errors.extend(source_errors)
        self.last_errors = errors
        for event in events:
            event["provider_errors"] = errors
        return events

    @staticmethod
    def _bls_month_urls(start: date, end: date) -> tuple[str, ...]:
        urls: list[str] = []
        cursor = date(start.year, start.month, 1)
        last = date(end.year, end.month, 1)
        while cursor <= last:
            urls.append(f"https://www.bls.gov/schedule/{cursor.year}/{cursor.month:02d}_sched.htm")
            cursor = date(cursor.year + (cursor.month == 12), 1 if cursor.month == 12 else cursor.month + 1, 1)
        return tuple(urls)

    @staticmethod
    def _parse_fomc(text: str, start: date, end: date, url: str) -> list[dict[str, Any]]:
        year_start = text.find(f"{start.year} FOMC Meetings")
        prior_year_start = text.find(f"{start.year - 1} FOMC Meetings", year_start + 1)
        section = text[year_start:prior_year_start] if year_start >= 0 and prior_year_start > year_start else text[year_start:]
        months = "January February March April May June July August September October November December".split()
        events: list[dict[str, Any]] = []
        for month in months:
            match = re.search(rf"\b{month}\s+(\d{{1,2}})(?:-(\d{{1,2}}))?\*?", section)
            if not match:
                continue
            event_date = _date_from_month_day(start.year, month, int(match.group(1)))
            if start <= event_date <= end:
                events.append({
                    "event_type": "FOMC",
                    "title": f"FOMC meeting ({month})",
                    "event_date": event_date.isoformat(),
                    "source": "Federal Reserve",
                    "source_url": url,
                    "tier": "TIER_1",
                })
        return events

    @staticmethod
    def _parse_bea(text: str, start: date, end: date, url: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for match in re.finditer(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})\s+8:30 AM\s+(?:News\s+)?([^\n]+)", text):
            event_date = _date_from_month_day(start.year, match.group(1), int(match.group(2)))
            if start <= event_date <= end and "Personal Income and Outlays" in match.group(3):
                events.append({
                    "event_type": "PCE",
                    "title": match.group(3).strip(),
                    "event_date": event_date.isoformat(),
                    "source": "U.S. Bureau of Economic Analysis",
                    "source_url": url,
                    "tier": "TIER_1",
                })
        return events

    @staticmethod
    def _parse_bls(text: str, start: date, end: date, url: str) -> list[dict[str, Any]]:
        # The BLS page is intentionally parsed conservatively. If its layout
        # changes, no speculative CPI/nonfarm date is emitted.
        events: list[dict[str, Any]] = []
        pattern = r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})\s+8:30\s*AM\s+([^\n]+)"
        for match in re.finditer(pattern, text):
            title = match.group(3).strip()
            event_type = "CPI" if "Consumer Price Index" in title else "NONFARM" if "Employment Situation" in title else None
            if not event_type:
                continue
            event_date = _date_from_month_day(start.year, match.group(1), int(match.group(2)))
            if start <= event_date <= end:
                events.append({
                    "event_type": event_type,
                    "title": title,
                    "event_date": event_date.isoformat(),
                    "source": "U.S. Bureau of Labor Statistics",
                    "source_url": url,
                    "tier": "TIER_1",
                })
        return events

    @staticmethod
    def _parse_bls_ics(text: str, start: date, end: date, url: str) -> list[dict[str, Any]]:
        """Parse the official BLS calendar export without guessing dates."""
        unfolded = re.sub(r"\r?\n[ \t]", "", text)
        events: list[dict[str, Any]] = []
        for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", unfolded, flags=re.DOTALL | re.IGNORECASE):
            summary_match = re.search(r"^SUMMARY(?:;[^:]*)?:(.*)$", block, flags=re.MULTILINE | re.IGNORECASE)
            date_match = re.search(r"^DTSTART(?:;[^:]*)?:(\d{8})(?:T\d{6}(?:Z)?)?", block, flags=re.MULTILINE | re.IGNORECASE)
            if not summary_match or not date_match:
                continue
            title = summary_match.group(1).strip()
            event_type = "CPI" if "Consumer Price Index" in title else "NONFARM" if "Employment Situation" in title else None
            if not event_type:
                continue
            event_date = datetime.strptime(date_match.group(1), "%Y%m%d").date()
            if start <= event_date <= end:
                events.append({
                    "event_type": event_type,
                    "title": title,
                    "event_date": event_date.isoformat(),
                    "source": "U.S. Bureau of Labor Statistics",
                    "source_url": url,
                    "tier": "TIER_1",
                })
        return events

    @staticmethod
    def _parse_bls_month(text: str, start: date, end: date, url: str) -> list[dict[str, Any]]:
        """Parse the official BLS month-view text as a conservative fallback."""
        match = re.search(r"/schedule/(\d{4})/(\d{2})_sched\.htm", url)
        if not match:
            return []
        year, month = int(match.group(1)), int(match.group(2))
        events: list[dict[str, Any]] = []
        pattern = r"\b(\d{1,2})\s+(Employment Situation|Consumer Price Index)\b.*?\b08:30\s*AM\b"
        for item in re.finditer(pattern, text, flags=re.IGNORECASE | re.DOTALL):
            event_date = date(year, month, int(item.group(1)))
            if not start <= event_date <= end:
                continue
            title = item.group(2)
            events.append({
                "event_type": "CPI" if title.lower().startswith("consumer") else "NONFARM",
                "title": title,
                "event_date": event_date.isoformat(),
                "source": "U.S. Bureau of Labor Statistics",
                "source_url": url,
                "tier": "TIER_1",
            })
        return events

