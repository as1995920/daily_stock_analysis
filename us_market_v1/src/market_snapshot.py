"""Collect and serialize a validated Phase B market snapshot."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

from .config import WatchlistConfig
from .data_validation import validate_market_data
from .providers.market_data import MarketDataProvider


ASSET_GROUPS: dict[str, dict[str, str]] = {
    "major_indexes": {
        "S&P 500": "^GSPC",
        "Nasdaq 100": "^NDX",
        "Dow Jones": "^DJI",
        "Russell 2000": "^RUT",
    },
    "risk_dashboard": {
        "VIX": "^VIX",
        "US10Y": "^TNX",
        "DXY": "DX-Y.NYB",
        "Gold": "GC=F",
        "WTI": "CL=F",
    },
}


def _asset_specs(config: WatchlistConfig) -> dict[str, dict[str, str]]:
    specs = {group: dict(values) for group, values in ASSET_GROUPS.items()}
    specs["portfolio"] = {ticker: ticker for ticker in config.portfolio}
    specs["watchlist"] = {ticker: ticker for ticker in config.watchlist}
    return specs


def _unavailable(ticker: str, market_date: date, error: str, source: str) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "market_date": market_date.isoformat(),
        "status": "DATA_UNAVAILABLE",
        "source": source,
        "error": error,
        "validation_errors": [error],
    }


def collect_market_snapshot(
    provider: MarketDataProvider,
    config: WatchlistConfig,
    market_date: date,
) -> dict[str, Any]:
    specs = _asset_specs(config)
    tickers = tuple(dict.fromkeys(ticker for group in specs.values() for ticker in group.values()))
    assets: dict[str, dict[str, Any]] = {}
    for ticker in tickers:
        try:
            record = provider.get_quote(ticker, market_date)
            validation = validate_market_data(record)
            if record.get("status") == "DATA_UNAVAILABLE" or not validation.valid:
                assets[ticker] = {
                    **record,
                    "status": "DATA_UNAVAILABLE",
                    "validation_errors": list(validation.errors) or [record.get("error", "unknown")],
                }
            else:
                assets[ticker] = {**record, "status": "OK", "validation_errors": []}
        except Exception as exc:  # provider failures become data status, not fabricated prices
            source = getattr(provider, "source_name", provider.__class__.__name__)
            assets[ticker] = _unavailable(ticker, market_date, f"provider error: {exc}", source)

    grouped: dict[str, dict[str, Any]] = {}
    for group, group_specs in specs.items():
        grouped[group] = {label: assets[ticker] for label, ticker in group_specs.items()}

    return {
        "schema_version": "phase-b.v1",
        "market_date": market_date.isoformat(),
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_policy": "Every asset carries source and validation status; no unavailable value is inferred.",
        "groups": grouped,
        "assets": assets,
    }


def write_snapshot(snapshot: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path

