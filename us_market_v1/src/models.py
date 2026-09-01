"""Small domain models shared by Phase A modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class MarketDataRecord:
    ticker: str
    market_date: date | str | None
    close: float | None
    previous_close: float | None
    high: float | None
    low: float | None
    volume: int | float | None
    source: str | None = None
    raw: dict[str, Any] | None = None

