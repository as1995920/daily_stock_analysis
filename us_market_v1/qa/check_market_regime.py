from src.market_regime import classify_market_regime


def _analysis(close, ma50, return20, label="BULLISH"):
    return {
        "status": "OK",
        "price": {"close": close},
        "moving_averages": {"ma50": ma50},
        "returns": {"twenty_day": return20},
        "trend": {"label": label},
    }


def test_market_regime_is_rule_based_risk_on():
    result = classify_market_regime(
        {"^GSPC": _analysis(110, 100, 0.04), "^NDX": _analysis(120, 100, 0.08), "^RUT": _analysis(105, 100, 0.02)},
        {"^VIX": {"status": "OK", "close": 15}},
    )
    assert result["status"] == "OK"
    assert result["state"] == "RISK_ON"
    assert result["score"] >= 3


def test_market_regime_does_not_guess_without_two_indexes():
    result = classify_market_regime({"^GSPC": {"status": "DATA_UNAVAILABLE"}}, {})
    assert result["status"] == "DATA_UNAVAILABLE"
    assert result["state"] == "UNKNOWN"

