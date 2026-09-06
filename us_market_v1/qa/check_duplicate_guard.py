from datetime import date

from src.duplicate_guard import DuplicateGuard
from src.main import main


def test_guard_only_allows_new_market_date(tmp_path):
    guard = DuplicateGuard(tmp_path / "state.json")
    first = date(2026, 8, 27)
    second = date(2026, 8, 28)
    assert guard.should_generate(first)
    guard.mark_reported(first)
    assert not guard.should_generate(first)
    assert guard.should_generate(second)


def test_guard_persists_state(tmp_path):
    path = tmp_path / "nested" / "state.json"
    DuplicateGuard(path).mark_reported(date(2026, 8, 27))
    assert DuplicateGuard(path).last_reported_market_date() == date(2026, 8, 27)

def test_phase_f_duplicate_stops_before_data_collection(tmp_path, monkeypatch):
    market_date = date(2026, 8, 28)
    state_path = tmp_path / "state.json"
    DuplicateGuard(state_path).mark_reported(market_date)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("market data must not be collected for a duplicate market date")

    monkeypatch.setattr("src.main.collect_market_snapshot", fail_if_called)

    assert main(
        [
            "--phase",
            "f",
            "--date",
            market_date.isoformat(),
            "--state-output",
            str(state_path),
        ]
    ) == 0
