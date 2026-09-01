"""Deterministic market-regime classification from index technical states."""

from __future__ import annotations

from typing import Any


def classify_market_regime(
    analyses: dict[str, dict[str, Any]],
    quotes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    score = 0
    drivers: list[str] = []
    unavailable: list[str] = []
    used = 0

    for label, ticker in (("S&P 500", "^GSPC"), ("Nasdaq 100", "^NDX"), ("Russell 2000", "^RUT")):
        analysis = analyses.get(ticker, {})
        if analysis.get("status") != "OK":
            unavailable.append(label)
            continue
        used += 1
        technical = analysis.get("trend", {})
        moving_averages = analysis.get("moving_averages", {})
        close = analysis.get("price", {}).get("close")
        ma50 = moving_averages.get("ma50")
        return20 = analysis.get("returns", {}).get("twenty_day")
        if close is not None and ma50 is not None and close > ma50:
            score += 1
            drivers.append(f"{label} above MA50")
        else:
            score -= 1
            drivers.append(f"{label} below MA50")
        if return20 is not None and return20 > 0:
            score += 1
            drivers.append(f"{label} 20-day return positive")
        elif return20 is not None:
            score -= 1
            drivers.append(f"{label} 20-day return non-positive")
        if technical.get("label") in {"BULLISH", "STRONG_BULLISH"}:
            drivers.append(f"{label} trend classified bullish")

    vix = quotes.get("^VIX", {})
    vix_close = vix.get("close") if vix.get("status") == "OK" else None
    if vix_close is None:
        unavailable.append("VIX")
    elif vix_close < 20:
        score += 1
        drivers.append("VIX below 20")
    elif vix_close > 25:
        score -= 1
        drivers.append("VIX above 25")
    else:
        drivers.append("VIX in intermediate range")

    if used < 2:
        return {
            "status": "DATA_UNAVAILABLE",
            "state": "UNKNOWN",
            "score": score,
            "drivers": drivers,
            "unavailable_inputs": unavailable,
            "rule": "At least two of S&P 500, Nasdaq 100 and Russell 2000 are required.",
        }

    if score >= 3:
        state = "RISK_ON"
        display = "🟢 偏强"
    elif score <= -3:
        state = "RISK_OFF"
        display = "🔴 偏弱"
    else:
        state = "NEUTRAL"
        display = "🟡 中性"
    return {
        "status": "OK",
        "state": state,
        "display": display,
        "score": score,
        "drivers": drivers,
        "unavailable_inputs": unavailable,
        "rule": "Index close vs MA50, 20-day returns and VIX thresholds; rule-based, not a forecast.",
    }

