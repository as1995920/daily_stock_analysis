"""Persistent market-date guard for idempotent report generation."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import tempfile


class DuplicateGuard:
    def __init__(self, state_path: str | Path):
        self.state_path = Path(state_path)

    def last_reported_market_date(self) -> date | None:
        if not self.state_path.is_file():
            return None
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            value = payload.get("last_reported_market_date")
            return date.fromisoformat(value) if value else None
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            # A corrupt state file must not silently authorize a duplicate send.
            raise RuntimeError(f"invalid duplicate-guard state: {self.state_path}")

    def should_generate(self, market_date: date) -> bool:
        previous = self.last_reported_market_date()
        return previous is None or market_date > previous

    def mark_reported(self, market_date: date) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"last_reported_market_date": market_date.isoformat()}
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=self.state_path.parent,
            prefix=f"{self.state_path.stem}.", suffix=".tmp", delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temporary_path = Path(handle.name)
        temporary_path.replace(self.state_path)

