from src.reliability_audit import audit_snapshots


def _snapshot(close=100):
    record = {
        "ticker": "VOO", "market_date": "2026-08-27", "close": close,
        "previous_close": 99, "high": 101, "low": 98, "volume": 1000,
        "source": "fake", "status": "OK",
    }
    return {"market_date": "2026-08-27", "assets": {"VOO": record}}


def test_audit_proves_stable_complete_repeated_data():
    result = audit_snapshots([_snapshot(), _snapshot()], ("VOO",))
    assert result["conclusion"] == "RELIABLE_FOR_OBSERVED_SNAPSHOT"
    assert result["stable_asset_count"] == 1
    assert result["per_asset"]["VOO"]["core_fields_complete_each_attempt"]


def test_audit_reports_changed_data_as_partial():
    result = audit_snapshots([_snapshot(100), _snapshot(101)], ("VOO",))
    assert result["conclusion"] == "PARTIAL_OR_UNAVAILABLE"
    assert not result["per_asset"]["VOO"]["stable_across_attempts"]

