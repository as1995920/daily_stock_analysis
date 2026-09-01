"""Command-line pipeline for the phased US market daily intelligence system."""

from __future__ import annotations

import argparse
from datetime import date
from datetime import datetime, timezone
import json
from pathlib import Path

from .calendar import NyseCalendarProvider
from .config import load_instrument_overrides, load_local_env, load_watchlist
from .duplicate_guard import DuplicateGuard
from .logging_config import configure_logging
from .analysis_snapshot import collect_analysis_snapshot, write_analysis_snapshot
from .market_snapshot import collect_market_snapshot, write_snapshot
from .news_events import collect_news_events_snapshot
from .providers.official_macro_events import OfficialMacroEventProvider
from .providers.yahoo_event_provider import YahooCompanyEventProvider
from .providers.yahoo_news_provider import YahooNewsProvider
from .reliability_audit import run_reliability_audit, write_reliability_audit
from .report import build_mobile_summary, build_report, report_path, write_text
from .providers.notification import DryRunNotificationProvider, FeishuNotificationProvider
from .providers.yfinance_provider import YFinanceMarketDataProvider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="US Market Daily Intelligence V1")
    parser.add_argument("--date", dest="market_date", help="historical market date YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="never send notifications")
    parser.add_argument("--phase", choices=("b", "c", "d", "e", "f"), default="b", help="pipeline phase to run")
    parser.add_argument(
        "--config", default="config/watchlist.yaml", help="watchlist YAML path"
    )
    parser.add_argument(
        "--sample-output", default="samples/sample_market_data.json",
        help="Phase B JSON snapshot output path",
    )
    parser.add_argument(
        "--analysis-output", default="samples/sample_analysis.json",
        help="Phase C JSON analysis output path",
    )
    parser.add_argument(
        "--news-events-output", default="samples/sample_news_events.json",
        help="Phase D JSON news/events output path",
    )
    parser.add_argument(
        "--report-output", default="samples/sample_report.md",
        help="Phase E Markdown report output path",
    )
    parser.add_argument(
        "--mobile-output", default="samples/sample_mobile_summary.txt",
        help="Phase E mobile summary output path",
    )
    parser.add_argument(
        "--audit", action="store_true", help="repeat Phase B collection and write a reliability audit"
    )
    parser.add_argument(
        "--audit-repeats", type=int, default=2, help="number of real collection attempts for --audit"
    )
    parser.add_argument(
        "--audit-output", default="samples/phase_b_reliability_audit.json",
        help="reliability audit output path",
    )
    parser.add_argument(
        "--state-output", default="data/state/notification_state.json",
        help="duplicate-send state path for Phase F",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logger = configure_logging()
    load_local_env()
    config = load_watchlist(Path(args.config))
    instrument_overrides = load_instrument_overrides()
    selected_date = date.fromisoformat(args.market_date) if args.market_date else None
    calendar = NyseCalendarProvider()
    if selected_date is None:
        selected_date = calendar.get_latest_completed_us_trading_session(datetime.now(timezone.utc))
    if selected_date is None:
        logger.info("No completed US trading session is available; exiting without a report")
        return 0
    if not calendar.is_trading_session(selected_date):
        logger.error("market_date=%s is not an NYSE trading session", selected_date)
        return 2

    logger.info(
        "START phase=%s dry_run=%s market_date=%s tickers=%s",
        args.phase.upper(), args.dry_run, selected_date, ",".join(config.all_tickers),
    )
    if args.audit:
        audit = run_reliability_audit(
            lambda: YFinanceMarketDataProvider(), config, selected_date, args.audit_repeats
        )
        audit_output = write_reliability_audit(audit, args.audit_output)
        logger.info(
            "DATA_RELIABILITY market_date=%s attempts=%s stable=%s unavailable=%s conclusion=%s",
            selected_date, audit["attempt_count"], audit["stable_asset_count"],
            len(audit["unavailable_assets"]), audit["conclusion"],
        )
        logger.info("DATA_RELIABILITY_OUTPUT path=%s", audit_output)
        return 0
    snapshot = collect_market_snapshot(YFinanceMarketDataProvider(), config, selected_date)
    output = write_snapshot(snapshot, args.sample_output)
    available = sum(1 for value in snapshot["assets"].values() if value["status"] == "OK")
    total = len(snapshot["assets"])
    logger.info("DATA_FETCH market_date=%s available=%s total=%s", selected_date, available, total)
    logger.info("DATA_VALIDATION snapshot=%s", output)
    if args.phase == "c":
        analysis = collect_analysis_snapshot(YFinanceMarketDataProvider(), config, selected_date, snapshot, instrument_overrides)
        analysis_output = write_analysis_snapshot(analysis, args.analysis_output)
        analysis_available = sum(1 for value in analysis["assets"].values() if value["status"] in {"OK", "OK_WITH_PROXY"})
        logger.info("ANALYSIS market_date=%s available=%s total=%s", selected_date, analysis_available, total)
        logger.info("ANALYSIS_OUTPUT path=%s regime=%s", analysis_output, analysis["market_regime"].get("state"))
    if args.phase == "d":
        news_events = collect_news_events_snapshot(
            YahooNewsProvider(),
            [YahooCompanyEventProvider(), OfficialMacroEventProvider()],
            config,
            selected_date,
            market_snapshot=snapshot,
        )
        output_path = Path(args.news_events_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(news_events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        logger.info("NEWS_EVENTS market_date=%s news=%s events=%s", selected_date, len(news_events["news"]["items"]), len(news_events["events"]["items"]))
        logger.info("NEWS_EVENTS_OUTPUT path=%s news_status=%s event_status=%s", output_path, news_events["news"]["status"], news_events["events"]["status"])
    if args.phase in {"e", "f"}:
        analysis = collect_analysis_snapshot(YFinanceMarketDataProvider(), config, selected_date, snapshot, instrument_overrides)
        analysis_output = write_analysis_snapshot(analysis, args.analysis_output)
        news_events = collect_news_events_snapshot(
            YahooNewsProvider(),
            [YahooCompanyEventProvider(), OfficialMacroEventProvider()],
            config,
            selected_date,
            market_snapshot=snapshot,
        )
        news_events_output = Path(args.news_events_output)
        news_events_output.parent.mkdir(parents=True, exist_ok=True)
        news_events_output.write_text(json.dumps(news_events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        logger.info("PHASE_E_INPUTS analysis=%s news_events=%s", analysis_output, news_events_output)
        archive = report_path("reports", selected_date)
        report = build_report(snapshot, analysis, news_events, archive)
        report_output = write_text(args.report_output, report)
        write_text(archive, report)
        mobile = build_mobile_summary(snapshot, analysis, news_events, archive)
        mobile_output = write_text(args.mobile_output, mobile)
        logger.info("REPORT_CREATED report=%s archive=%s mobile=%s", report_output, archive, mobile_output)
        if args.phase == "f":
            if not args.dry_run and not DuplicateGuard(args.state_output).should_generate(selected_date):
                logger.info("NOTIFICATION_SKIPPED market_date=%s reason=duplicate_guard", selected_date)
                return 0
            try:
                notification = (
                    DryRunNotificationProvider()
                    if args.dry_run
                    else FeishuNotificationProvider.from_env()
                )
                result = notification.send_markdown("📊 美股日报", mobile)
            except (OSError, ValueError) as exc:
                logger.error("ERROR notification_setup=%s", type(exc).__name__)
                return 1
            if not result.success:
                logger.error("ERROR notification_provider=%s detail=%s", result.provider, result.detail)
                return 1
            if not args.dry_run:
                DuplicateGuard(args.state_output).mark_reported(selected_date)
            logger.info("NOTIFICATION_SENT provider=%s dry_run=%s", result.provider, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

