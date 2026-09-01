"""Build a reproducible Phase C analysis snapshot from verified provider data."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

from .config import InstrumentOverride, WatchlistConfig, load_instrument_overrides
from .market_regime import classify_market_regime
from .market_snapshot import collect_market_snapshot
from .providers.market_data import MarketDataProvider
from .technical_analysis import analyze_history


def collect_analysis_snapshot(
    provider: MarketDataProvider,
    config: WatchlistConfig,
    market_date: date,
    market_snapshot: dict[str, Any] | None = None,
    instrument_overrides: dict[str, InstrumentOverride] | None = None,
) -> dict[str, Any]:
    snapshot = market_snapshot or collect_market_snapshot(provider, config, market_date)
    instrument_overrides = instrument_overrides if instrument_overrides is not None else load_instrument_overrides()
    analyses: dict[str, dict[str, Any]] = {}
    for ticker, quote in snapshot["assets"].items():
        if quote.get("status") != "OK":
            analyses[ticker] = {
                "status": "DATA_UNAVAILABLE",
                "validation_errors": ["quote_unavailable"],
                "source": quote.get("source"),
            }
            continue
        try:
            history = provider.get_history(ticker, market_date - timedelta(days=420), market_date)
            result = analyze_history(history)
            analyses[ticker] = {
                "ticker": ticker,
                "source": quote.get("source"),
                **result,
            }
            override = instrument_overrides.get(ticker)
            if override and result.get("status") != "OK" and override.history_proxy:
                proxy_history = provider.get_history(
                    override.history_proxy, market_date - timedelta(days=420), market_date
                )
                proxy_result = analyze_history(proxy_history)
                if proxy_result.get("status") == "OK":
                    analyses[ticker] = {
                        **proxy_result,
                        "ticker": ticker,
                        "status": "OK_WITH_PROXY",
                        "source": quote.get("source"),
                        "price": {
                            "close": quote.get("close"),
                            "previous_close": quote.get("previous_close"),
                            "high": quote.get("high"),
                            "low": quote.get("low"),
                            "volume": quote.get("volume"),
                            "daily_change_pct": (
                                (quote["close"] / quote["previous_close"] - 1) * 100
                                if quote.get("close") is not None and quote.get("previous_close")
                                else None
                            ),
                        },
                        "direct_ticker": ticker,
                        "direct_history_rows": len(history),
                        "history_ticker": override.history_proxy,
                        "history_basis": "BENCHMARK_PROXY",
                        "history_basis_note": override.history_proxy_reason,
                        "history_basis_source_url": override.source_url,
                        "proxy_source": getattr(provider, "source_name", provider.__class__.__name__),
                    }
        except Exception as exc:
            analyses[ticker] = {
                "ticker": ticker,
                "status": "DATA_UNAVAILABLE",
                "validation_errors": [f"history_provider_error:{exc}"],
                "source": quote.get("source"),
            }

    grouped: dict[str, dict[str, Any]] = {}
    for group, values in snapshot["groups"].items():
        grouped[group] = {label: analyses[ticker] for label, item in values.items() for ticker in [item["ticker"]]}

    return {
        "schema_version": "phase-c.v1",
        "market_date": market_date.isoformat(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "history_window": {"start": (market_date - timedelta(days=420)).isoformat(), "end": market_date.isoformat()},
        "methodology": {
            "minimum_history_rows": 200,
            "proxy_policy": "A documented benchmark proxy may provide context when direct history is insufficient; direct quotes remain direct.",
            "rsi": "14-period simple average gain/loss",
            "volume_ratio": "current volume divided by preceding 20-session average volume",
            "trend": "rule score using close/MA20, MA20/MA50, MA50/MA200, 5-day return and RSI14",
            "support_resistance": "20-session high/low and MA20/MA50 reference levels",
        },
        "groups": grouped,
        "assets": analyses,
        "market_regime": classify_market_regime(analyses, snapshot["assets"]),
    }


def write_analysis_snapshot(snapshot: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path

