from datetime import date, timedelta

from src.technical_analysis import analyze_history


def _history(count=220):
    rows = []
    for index in range(count):
        value = 100 + index * 0.2
        rows.append({
            "market_date": (date(2026, 1, 1) + timedelta(days=index)).isoformat(),
            "close": value,
            "high": value + 1,
            "low": value - 1,
            "volume": 1000 + index,
        })
    return rows


def test_technical_analysis_calculates_required_v1_fields():
    result = analyze_history(_history())
    assert result["status"] == "OK"
    assert result["returns"]["five_day"] > 0
    assert result["moving_averages"]["ma200"] is not None
    assert result["moving_averages"]["trend_50"] == "ABOVE_MA50"
    assert result["moving_averages"]["trend_200"] == "ABOVE_MA200"
    assert result["rsi14"] == 100.0
    assert result["volume"]["volume_ratio_20d"] > 1
    assert result["trend"]["label"] == "STRONG_BULLISH"


def test_technical_analysis_rejects_insufficient_history():
    result = analyze_history(_history(50))
    assert result["status"] == "DATA_UNAVAILABLE"
    assert "insufficient_history" in result["validation_errors"][0]


def test_missing_volume_only_disables_volume_ratio():
    history = _history()
    for row in history:
        row["volume"] = None
    result = analyze_history(history)
    assert result["status"] == "OK"
    assert result["volume"]["volume_ratio_20d"] is None
    assert result["data_warnings"] == ["volume_ratio_unavailable"]

