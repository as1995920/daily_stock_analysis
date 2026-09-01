"""Rule-based technical analysis for verified daily market history."""

from __future__ import annotations

from collections.abc import Iterable
from statistics import mean
from typing import Any


MIN_HISTORY_ROWS = 200


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if value == value else None


def _round(value: float | None) -> float | None:
    return round(value, 6) if value is not None else None


def _return(closes: list[float], periods: int) -> float | None:
    if len(closes) <= periods:
        return None
    base = closes[-periods - 1]
    return _round(closes[-1] / base - 1) if base else None


def _rsi14(closes: list[float]) -> float | None:
    if len(closes) < 15:
        return None
    changes = [closes[index] - closes[index - 1] for index in range(1, len(closes))]
    window = changes[-14:]
    gains = [max(change, 0.0) for change in window]
    losses = [max(-change, 0.0) for change in window]
    average_gain = mean(gains)
    average_loss = mean(losses)
    if average_loss == 0:
        return 100.0 if average_gain else 50.0
    return _round(100 - (100 / (1 + average_gain / average_loss)))


def _unique_sorted(values: Iterable[float]) -> list[float]:
    return sorted({round(value, 6) for value in values})


def _levels(close: float, ma20: float, ma50: float, high20: float, low20: float) -> dict[str, float | None]:
    supports = _unique_sorted(value for value in (low20, ma20, ma50) if value < close)
    resistances = _unique_sorted(value for value in (high20, ma20, ma50) if value > close)
    return {
        "first_support": supports[-1] if supports else None,
        "second_support": supports[-2] if len(supports) >= 2 else None,
        "first_resistance": resistances[0] if resistances else None,
        "second_resistance": resistances[1] if len(resistances) >= 2 else None,
        "method": "20-day high/low and MA20/MA50 reference levels; technical reference only",
    }


def _trend(close: float, ma20: float, ma50: float, ma200: float, return5: float, rsi: float) -> dict[str, Any]:
    score = 0
    reasons: list[str] = []
    for condition, positive, negative in (
        (close > ma20, "close_above_ma20", "close_below_ma20"),
        (ma20 > ma50, "ma20_above_ma50", "ma20_below_ma50"),
        (ma50 > ma200, "ma50_above_ma200", "ma50_below_ma200"),
        (return5 > 0, "five_day_return_positive", "five_day_return_negative_or_flat"),
        (rsi >= 55, "rsi_supportive", "rsi_not_supportive"),
    ):
        score += 1 if condition else -1
        reasons.append(positive if condition else negative)

    if score >= 4:
        label = "STRONG_BULLISH"
        display = "🟢 偏强"
    elif score >= 2:
        label = "BULLISH"
        display = "🟢 偏强"
    elif score <= -4:
        label = "STRONG_BEARISH"
        display = "🔴 偏弱"
    elif score <= -2:
        label = "BEARISH"
        display = "🔴 偏弱"
    else:
        label = "NEUTRAL"
        display = "🟡 中性"
    return {"label": label, "display": display, "score": score, "reasons": reasons}


def analyze_history(history: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate the bounded V1 indicator set from chronological daily rows."""

    rows = sorted(history, key=lambda row: str(row.get("market_date", "")))
    if len(rows) < MIN_HISTORY_ROWS:
        return {
            "status": "DATA_UNAVAILABLE",
            "validation_errors": [f"insufficient_history:{len(rows)}<{MIN_HISTORY_ROWS}"],
        }

    closes = [_number(row.get("close")) for row in rows]
    volumes = [_number(row.get("volume")) for row in rows]
    if any(value is None for value in closes):
        return {
            "status": "DATA_UNAVAILABLE",
            "validation_errors": ["missing:close_in_history"],
        }
    close_values = [value for value in closes if value is not None]
    current_volume = volumes[-1]
    prior_volumes = [value for value in volumes[:-1] if value is not None]

    close = close_values[-1]
    previous_close = close_values[-2]
    ma20 = mean(close_values[-20:])
    ma50 = mean(close_values[-50:])
    ma200 = mean(close_values[-200:])
    return5 = _return(close_values, 5)
    return20 = _return(close_values, 20)
    rsi = _rsi14(close_values)
    average_volume20 = mean(prior_volumes[-20:]) if len(prior_volumes) >= 20 else None
    volume_ratio = current_volume / average_volume20 if current_volume is not None and average_volume20 else None
    high20 = max(close_values[-20:])
    low20 = min(close_values[-20:])
    daily_change = close / previous_close - 1 if previous_close else None
    if return5 is None or rsi is None:
        return {
            "status": "DATA_UNAVAILABLE",
            "validation_errors": ["insufficient_derived_inputs"],
        }
    warnings = [] if volume_ratio is not None else ["volume_ratio_unavailable"]

    return {
        "status": "OK",
        "validation_errors": [],
        "data_warnings": warnings,
        "as_of": rows[-1].get("market_date"),
        "price": {
            "close": _round(close),
            "previous_close": _round(previous_close),
            "daily_change_pct": _round(daily_change * 100 if daily_change is not None else None),
            "high": _round(_number(rows[-1].get("high"))),
            "low": _round(_number(rows[-1].get("low"))),
            "volume": current_volume,
        },
        "returns": {
            "five_day": return5,
            "twenty_day": return20,
        },
        "moving_averages": {
            "ma20": _round(ma20),
            "ma50": _round(ma50),
            "ma200": _round(ma200),
            "trend_50": "ABOVE_MA50" if close > ma50 else "BELOW_OR_AT_MA50",
            "trend_200": "ABOVE_MA200" if close > ma200 else "BELOW_OR_AT_MA200",
        },
        "rsi14": rsi,
        "volume": {
            "average_volume20_excluding_current": _round(average_volume20),
            "volume_ratio_20d": _round(volume_ratio),
        },
        "range20": {"high": _round(high20), "low": _round(low20)},
        "levels": _levels(close, ma20, ma50, high20, low20),
        "trend": _trend(close, ma20, ma50, ma200, return5, rsi),
    }

