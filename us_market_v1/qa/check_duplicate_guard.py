from datetime import date

from src.duplicate_guard import DuplicateGuard


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

