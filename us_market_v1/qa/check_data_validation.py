from src.data_validation import validate_market_data


def test_core_market_data_is_validated_before_analysis():
    result = validate_market_data(
        {
            "market_date": "2026-08-28",
            "ticker": "VOO",
            "close": 100.0,
            "previous_close": 99.0,
            "high": 101.0,
            "low": 98.0,
            "volume": 12345,
        }
    )
    assert result.valid
    assert result.errors == ()


def test_missing_core_price_data_returns_invalid():
    result = validate_market_data({"ticker": "VOO", "market_date": "2026-08-28"})
    assert not result.valid
    assert "missing:close" in result.errors
    assert "missing:volume" in result.errors

