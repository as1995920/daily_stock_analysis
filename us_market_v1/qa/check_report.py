from datetime import date

from src.report import render_data_unavailable_report, report_path


def test_report_path_uses_year_month_archive():
    path = report_path("reports", date(2026, 8, 28))
    assert str(path).replace("\\", "/") == (
        "reports/2026/08/2026-08-28_US_MARKET_DAILY.md"
    )


def test_unavailable_report_is_explicit():
    content = render_data_unavailable_report(date(2026, 8, 28), "provider timeout")
    assert "DATA_UNAVAILABLE" in content
    assert "provider timeout" in content

