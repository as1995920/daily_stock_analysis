from datetime import date

from src.providers.official_macro_events import OfficialMacroEventProvider


def test_bls_ics_parser_extracts_only_supported_events():
    text = """BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART;TZID=America/New_York:20260904T083000\nSUMMARY:Employment Situation\nEND:VEVENT\nBEGIN:VEVENT\nDTSTART;VALUE=DATE:20260910\nSUMMARY:Consumer Price Index\nEND:VEVENT\nBEGIN:VEVENT\nDTSTART;VALUE=DATE:20260911\nSUMMARY:Other release\nEND:VEVENT\nEND:VCALENDAR\n"""
    events = OfficialMacroEventProvider._parse_bls_ics(
        text, date(2026, 9, 1), date(2026, 9, 10), "https://www.bls.gov/schedule/news_release/bls.ics"
    )
    assert [(event["event_type"], event["event_date"]) for event in events] == [
        ("NONFARM", "2026-09-04"),
        ("CPI", "2026-09-10"),
    ]


def test_bls_fallback_suppresses_primary_error_when_ics_succeeds(monkeypatch):
    provider = OfficialMacroEventProvider()
    ics = "BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART;VALUE=DATE:20260904\nSUMMARY:Employment Situation\nEND:VEVENT\nEND:VCALENDAR"

    def fake_raw(url):
        if url.endswith(".ics"):
            return ics
        raise OSError("blocked")

    monkeypatch.setattr("src.providers.official_macro_events._get_raw_text", fake_raw)
    monkeypatch.setattr("src.providers.official_macro_events._get_page_text", fake_raw)
    events = provider.get_events([], date(2026, 9, 1), date(2026, 9, 7))
    assert events[0]["event_type"] == "NONFARM"
    assert not any(error.startswith("BLS:") for error in provider.last_errors)


def test_bls_month_parser_uses_page_month_and_explicit_release_title():
    text = "4 Employment Situation\nAugust 2026\n08:30 AM\n11 Consumer Price Index\nAugust 2026\n08:30 AM"
    events = OfficialMacroEventProvider._parse_bls_month(
        text, date(2026, 9, 1), date(2026, 9, 30),
        "https://www.bls.gov/schedule/2026/09_sched.htm",
    )
    assert [(event["event_type"], event["event_date"]) for event in events] == [
        ("NONFARM", "2026-09-04"),
        ("CPI", "2026-09-11"),
    ]

