"""Configuration loading and validation for the daily intelligence system."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any

import yaml


_TICKER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,9}$")


@dataclass(frozen=True)
class WatchlistConfig:
    portfolio: tuple[str, ...]
    watchlist: tuple[str, ...]

    @property
    def all_tickers(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.portfolio, *self.watchlist)))


@dataclass(frozen=True)
class InstrumentOverride:
    """Documented metadata for instruments whose direct history is limited."""

    display_name: str
    history_proxy: str | None = None
    history_proxy_reason: str | None = None
    source_url: str | None = None


def _read_ticker_list(raw: Any, field_name: str) -> tuple[str, ...]:
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise ValueError(f"{field_name} must be a YAML list")

    normalized: list[str] = []
    for index, value in enumerate(raw):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name}[{index}] must be a non-empty string")
        ticker = value.strip().upper()
        if not _TICKER_PATTERN.fullmatch(ticker):
            raise ValueError(f"invalid ticker in {field_name}[{index}]: {value!r}")
        if ticker not in normalized:
            normalized.append(ticker)
    return tuple(normalized)


def load_watchlist(path: str | Path) -> WatchlistConfig:
    """Load the editable YAML watchlist without embedding tickers in code."""

    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"watchlist config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise ValueError("watchlist YAML root must be a mapping")

    return WatchlistConfig(
        portfolio=_read_ticker_list(raw.get("portfolio"), "portfolio"),
        watchlist=_read_ticker_list(raw.get("watchlist"), "watchlist"),
    )


def load_instrument_overrides(path: str | Path = "config/instrument_overrides.yaml") -> dict[str, InstrumentOverride]:
    """Load explicit instrument metadata without silently substituting prices."""

    config_path = Path(path)
    if not config_path.is_file():
        return {}
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise ValueError("instrument overrides YAML root must be a mapping")

    result: dict[str, InstrumentOverride] = {}
    for raw_ticker, raw_value in raw.items():
        ticker = str(raw_ticker).strip().upper()
        if not _TICKER_PATTERN.fullmatch(ticker):
            raise ValueError(f"invalid ticker in instrument overrides: {raw_ticker!r}")
        if not isinstance(raw_value, dict):
            raise ValueError(f"instrument override for {ticker} must be a mapping")
        display_name = str(raw_value.get("display_name", ticker)).strip()
        history_proxy = raw_value.get("history_proxy")
        if history_proxy is not None:
            history_proxy = str(history_proxy).strip()
            if not history_proxy:
                history_proxy = None
        result[ticker] = InstrumentOverride(
            display_name=display_name or ticker,
            history_proxy=history_proxy,
            history_proxy_reason=(str(raw_value["history_proxy_reason"]).strip()
                                  if raw_value.get("history_proxy_reason") else None),
            source_url=(str(raw_value["source_url"]).strip()
                        if raw_value.get("source_url") else None),
        )
    return result


def load_local_env(path: str | Path = ".env") -> None:
    """Load simple KEY=VALUE pairs without overriding CI environment variables."""

    env_path = Path(path)
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not key or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)

