from src.report import build_mobile_summary, build_report


def _inputs():
    quote = {
        "ticker": "VOO", "market_date": "2026-08-28", "close": 100,
        "previous_close": 99, "high": 101, "low": 98, "volume": 1000,
        "source": "fake", "status": "OK",
    }
    analysis = {
        "status": "OK", "price": {"close": 100, "daily_change_pct": 1.01, "high": 101, "low": 98, "volume": 1000},
        "returns": {"five_day": 0.02, "twenty_day": 0.04},
        "moving_averages": {"ma20": 99, "ma50": 95, "ma200": 90, "trend_50": "ABOVE_MA50", "trend_200": "ABOVE_MA200"},
        "rsi14": 60, "volume": {"volume_ratio_20d": 1.2},
        "levels": {"first_support": 98, "second_support": 95, "first_resistance": 101, "second_resistance": 105},
        "trend": {"display": "🟢 偏强", "label": "BULLISH"},
    }
    return (
        {"market_date": "2026-08-28", "assets": {"VOO": quote}, "groups": {"major_indexes": {}, "risk_dashboard": {}, "portfolio": {"VOO": quote}, "watchlist": {}}},
        {"market_date": "2026-08-28", "generated_at_utc": "2026-08-29T00:00:00+00:00", "assets": {"VOO": analysis}, "market_regime": {"state": "RISK_ON", "display": "🟢 偏强", "score": 4}},
        {"news": {"status": "OK", "items": [{"ticker": "VOO", "title": "Verified headline", "source": "Reuters", "tier": "TIER_1", "published_at": "2026-08-28T12:00:00+00:00"}]}, "events": {"status": "OK", "items": [], "errors": []}},
    )


def test_report_contains_required_boundaries_and_sections():
    report = build_report(*_inputs(), "reports/2026/08/report.md")
    for heading in ("Executive Summary", "Major Indexes", "Market Risk Dashboard", "Portfolio ETF", "Watchlist", "Upcoming 7-Day Risks", "Disclaimer"):
        assert heading in report
    assert "FACT" in report
    assert "ANALYSIS" in report
    assert "SCENARIO" in report
    assert "目标价" not in report


def test_mobile_summary_is_short_and_references_archive():
    market, analysis, news_events = _inputs()
    summary = build_mobile_summary(market, analysis, news_events, "reports/2026/08/report.md")
    assert len(summary) >= 700
    assert len(summary) < 2000
    assert "完整版已保存" in summary
    assert "VOO" in summary

