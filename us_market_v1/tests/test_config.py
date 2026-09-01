from pathlib import Path
import os

from src.config import load_instrument_overrides, load_local_env, load_watchlist


def test_default_watchlist_is_editable_yaml():
    config = load_watchlist(Path(__file__).parents[1] / "config" / "watchlist.yaml")
    assert config.portfolio == ("VOO", "IQQ")
    assert config.watchlist == ()
    assert config.all_tickers == ("VOO", "IQQ")


def test_watchlist_normalizes_and_deduplicates(tmp_path):
    path = tmp_path / "watchlist.yaml"
    path.write_text("portfolio: [voo, VOO]\nwatchlist: [nvda, AAPL]\n", encoding="utf-8")
    config = load_watchlist(path)
    assert config.portfolio == ("VOO",)
    assert config.watchlist == ("NVDA", "AAPL")


def test_instrument_override_documents_benchmark_proxy():
    overrides = load_instrument_overrides(Path(__file__).parents[1] / "config" / "instrument_overrides.yaml")
    assert overrides["IQQ"].history_proxy == "^NDX"
    assert "insufficient" in overrides["IQQ"].history_proxy_reason


def test_local_env_loads_values_without_overriding_existing_environment(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("FEISHU_WEBHOOK_URL='https://example.test/hook'\nNEW_VALUE=loaded\n", encoding="utf-8")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "existing")
    monkeypatch.delenv("NEW_VALUE", raising=False)
    load_local_env(path)
    assert os.environ["FEISHU_WEBHOOK_URL"] == "existing"
    assert os.environ["NEW_VALUE"] == "loaded"

