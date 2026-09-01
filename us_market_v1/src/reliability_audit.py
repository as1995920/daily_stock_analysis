"""Evidence-based audit for repeated Phase B market-data collection."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Any

from .config import WatchlistConfig
from .data_validation import CORE_FIELDS, validate_market_data
from .market_snapshot import ASSET_GROUPS, collect_market_snapshot
from .providers.market_data import MarketDataProvider


def _expected_tickers(config: WatchlistConfig) -> tuple[str, ...]:
    configured = [ticker for group in ASSET_GROUPS.values() for ticker in group.values()]
    return tuple(dict.fromkeys((*configured, *config.all_tickers)))


def _fingerprint(record: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(record.get(field) for field in CORE_FIELDS)


def audit_snapshots(
    snapshots: list[dict[str, Any]],
    expected_tickers: tuple[str, ...],
) -> dict[str, Any]:
    if not snapshots:
        raise ValueError("at least one snapshot is required")
    market_dates = {snapshot.get("market_date") for snapshot in snapshots}
    per_asset: dict[str, Any] = {}
    for ticker in expected_tickers:
        records = [snapshot.get("assets", {}).get(ticker, {}) for snapshot in snapshots]
        statuses = [record.get("status") for record in records]
        validations = [validate_market_data(record) for record in records if record]
        valid_records = [record for record in records if record.get("status") == "OK" and validate_market_data(record).valid]
        fingerprints = [_fingerprint(record) for record in valid_records]
        per_asset[ticker] = {
            "attempt_statuses": statuses,
            "stable_across_attempts": len(valid_records) == len(records) and len(set(fingerprints)) == 1,
            "core_fields_complete_each_attempt": len(validations) == len(records) and all(item.valid for item in validations),
            "source_present_each_attempt": all(bool(record.get("source")) for record in records),
            "identity_consistent_each_attempt": all(
                record.get("ticker") == ticker and record.get("market_date") == snapshots[0].get("market_date")
                for record in records
            ),
            "unavailable_reasons": [
                record.get("error") or ",".join(validate_market_data(record).errors)
                for record in records if record.get("status") != "OK"
            ],
        }

    stable_assets = [ticker for ticker, result in per_asset.items() if result["stable_across_attempts"]]
    unavailable_assets = [ticker for ticker, result in per_asset.items() if any(status != "OK" for status in result["attempt_statuses"])]
    all_assets_ok = all(
        all(status == "OK" for status in result["attempt_statuses"])
        for result in per_asset.values()
    )
    return {
        "schema_version": "phase-b-reliability.v1",
        "market_date": next(iter(market_dates)) if len(market_dates) == 1 else None,
        "same_market_date_each_attempt": len(market_dates) == 1,
        "attempt_count": len(snapshots),
        "expected_asset_count": len(expected_tickers),
        "stable_asset_count": len(stable_assets),
        "stable_assets": stable_assets,
        "unavailable_assets": unavailable_assets,
        "all_assets_ok_each_attempt": all_assets_ok,
        "all_attempts_have_same_asset_set": all(
            set(snapshot.get("assets", {})) == set(expected_tickers) for snapshot in snapshots
        ),
        "per_asset": per_asset,
        "conclusion": (
            "RELIABLE_FOR_OBSERVED_SNAPSHOT"
            if len(market_dates) == 1
            and all_assets_ok
            and all(result["stable_across_attempts"] for result in per_asset.values())
            and all(result["core_fields_complete_each_attempt"] for result in per_asset.values())
            else "PARTIAL_OR_UNAVAILABLE"
        ),
    }


def run_reliability_audit(
    provider_factory: Callable[[], MarketDataProvider],
    config: WatchlistConfig,
    market_date: date,
    repeats: int = 2,
) -> dict[str, Any]:
    if repeats < 2:
        raise ValueError("reliability audit requires at least two attempts")
    snapshots = [collect_market_snapshot(provider_factory(), config, market_date) for _ in range(repeats)]
    audit = audit_snapshots(snapshots, _expected_tickers(config))
    audit["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    audit["provider"] = getattr(provider_factory(), "source_name", "unknown")
    return audit


def write_reliability_audit(audit: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path

