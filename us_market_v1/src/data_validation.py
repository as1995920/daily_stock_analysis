"""Validation helpers. Invalid core data must never be turned into analysis."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
import math
from typing import Any

from .models import ValidationResult


CORE_FIELDS = (
    "market_date",
    "ticker",
    "close",
    "previous_close",
    "high",
    "low",
    "volume",
)


def _is_missing(value: Any) -> bool:
    if value is None or value == "":
        return True
    try:
        return bool(math.isnan(value))
    except (TypeError, ValueError):
        return False


def validate_market_data(record: Mapping[str, Any]) -> ValidationResult:
    """Validate the minimum fields required before price analysis."""

    errors: list[str] = []
    for field in CORE_FIELDS:
        if field not in record or _is_missing(record[field]):
            errors.append(f"missing:{field}")

    ticker = record.get("ticker")
    if ticker is not None and (not isinstance(ticker, str) or not ticker.strip()):
        errors.append("invalid:ticker")

    market_date = record.get("market_date")
    if market_date is not None and not isinstance(market_date, (date, datetime, str)):
        errors.append("invalid:market_date")

    for field in ("close", "previous_close", "high", "low", "volume"):
        value = record.get(field)
        if not _is_missing(value):
            try:
                if float(value) < 0:
                    errors.append(f"invalid:{field}")
            except (TypeError, ValueError):
                errors.append(f"invalid:{field}")

    return ValidationResult(valid=not errors, errors=tuple(errors))

