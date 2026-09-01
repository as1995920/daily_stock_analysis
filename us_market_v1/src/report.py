"""Deterministic Markdown report and mobile-summary rendering."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any


def report_path(reports_root: str | Path, market_date: date) -> Path:
    return (
        Path(reports_root)
        / f"{market_date:%Y}"
        / f"{market_date:%m}"
        / f"{market_date:%Y-%m-%d}_US_MARKET_DAILY.md"
    )


def render_data_unavailable_report(market_date: date, reason: str) -> str:
    return f"""# US Market Daily Intelligence

Market Date: {market_date.isoformat()}
Status: DATA_UNAVAILABLE

## Data Status

核心数据不可用，未生成行情或趋势判断。

Reason: {reason}

## Disclaimer

仅供个人信息整理和投研辅助，不是投资建议，最终投资决策由用户本人作出。
"""


def _price(value: Any) -> str:
    return "DATA_UNAVAILABLE" if value is None else f"${float(value):,.2f}"


def _pct(value: Any) -> str:
    return "DATA_UNAVAILABLE" if value is None else f"{float(value):+.2f}%"


def _ratio(value: Any) -> str:
    return "DATA_UNAVAILABLE" if value is None else f"{float(value):.2f}x"


def _risk_value(label: str, value: Any) -> str:
    if value is None:
        return "DATA_UNAVAILABLE"
    if label == "VIX":
        return f"{float(value):.2f}"
    if label == "US10Y":
        return f"{float(value):.2f}%"
    return _price(value)


def _date_time(value: Any) -> str:
    return str(value).replace("T", " ").replace("+00:00", " UTC") if value else "DATA_UNAVAILABLE"


def _analysis_usable(analysis: dict[str, Any]) -> bool:
    return analysis.get("status") in {"OK", "OK_WITH_PROXY"}


def _asset_line(label: str, quote: dict[str, Any], analysis: dict[str, Any]) -> str:
    if quote.get("status") != "OK" or not _analysis_usable(analysis):
        reason = ", ".join(analysis.get("validation_errors", [])) or quote.get("error", "unknown")
        return f"| {label} | DATA_UNAVAILABLE | DATA_UNAVAILABLE | {reason} |"
    price = analysis.get("price", {})
    trend = analysis.get("trend", {})
    return f"| {label} | {_price(price.get('close'))} | {_pct(price.get('daily_change_pct'))} | {trend.get('display', trend.get('label', 'DATA_UNAVAILABLE'))} |"


def _news_lines(ticker: str, news_items: list[dict[str, Any]], limit: int = 3) -> list[str]:
    matched = [item for item in news_items if item.get("ticker") == ticker]
    if not matched:
        return ["- FACT：未取得与该标的直接匹配的近期新闻（DATA_UNAVAILABLE）。"]
    return [
        f"- FACT：{item['title']}（{item.get('source', 'unknown')}，{item.get('tier', 'TIER_3')}，{_date_time(item.get('published_at'))}）"
        for item in matched[:limit]
    ]


def _scenarios(analysis: dict[str, Any], regime: dict[str, Any]) -> list[str]:
    if not _analysis_usable(analysis):
        return ["- SCENARIO：DATA_UNAVAILABLE，因历史数据不足，未生成情景分析。"] * 3
    trend = analysis.get("trend", {}).get("display", "🟡 中性")
    volume = analysis.get("volume", {}).get("volume_ratio_20d")
    volume_label = "基准成交量" if analysis.get("status") == "OK_WITH_PROXY" else "成交量"
    volume_condition = f"{volume_label}高于前20日均量" if volume is not None and volume >= 1 else f"{volume_label}确认信号尚不充分"
    state = regime.get("state", "UNKNOWN")
    basis = analysis.get("history_ticker") if analysis.get("status") == "OK_WITH_PROXY" else "该标的"
    return [
        f"- Bull Case（SCENARIO）：若{basis}重新站稳MA20，且{volume_condition}，同时市场状态维持{state}或转强，未来1—5个交易日走势可能进一步增强。",
        f"- Base Case（SCENARIO）：当前规则趋势为{trend}；若价格围绕MA20震荡且没有新的重大事件，未来1—5个交易日可能延续当前状态。",
        f"- Bear Case（SCENARIO）：若{basis}收盘失守MA20并伴随成交量放大，或市场状态转为RISK_OFF，未来1—5个交易日下行风险可能增加。",
    ]


def _instrument_section(
    label: str,
    ticker: str,
    quote: dict[str, Any],
    analysis: dict[str, Any],
    news_items: list[dict[str, Any]],
    events: list[dict[str, Any]],
    regime: dict[str, Any],
) -> str:
    if quote.get("status") != "OK" or not _analysis_usable(analysis):
        reason = ", ".join(analysis.get("validation_errors", [])) or quote.get("error", "unknown")
        return f"""### {label} ({ticker})

DATA_UNAVAILABLE：{reason}

未生成价格、技术指标或情景判断。
"""
    price = analysis["price"]
    moving = analysis["moving_averages"]
    volume = analysis["volume"]
    levels = analysis["levels"]
    technical_suffix = "（基准代理）" if analysis.get("status") == "OK_WITH_PROXY" else ""
    related_events = [item for item in events if item.get("ticker") in (None, ticker)]
    event_text = [
        f"- FACT：{item.get('event_type', 'EVENT')}，{item.get('title', '未命名事件')}，日期 {item.get('event_date')}（{item.get('source')}）"
        for item in related_events[:5]
    ] or ["- FACT：未来7日未取得与该标的直接匹配的事件（DATA_UNAVAILABLE或无匹配事件）。"]
    basis_note = ""
    if analysis.get("status") == "OK_WITH_PROXY":
        basis_note = (
            f"\n**技术指标口径**：采用 `{analysis.get('history_ticker', 'DATA_UNAVAILABLE')}` 作为基准代理；"
            "仅表示基准市场背景，不等同于该ETF自身历史表现。"
        )
    return f"""### {label} ({ticker})

| 项目 | 数值 |
|---|---:|
| 收盘价 | {_price(price.get('close'))} |
| 当日涨跌幅 | {_pct(price.get('daily_change_pct'))} |
| 当日最高/最低 | {_price(price.get('high'))} / {_price(price.get('low'))} |
| 成交量 | {volume.get('volume_ratio_20d') is not None and price.get('volume') or 'DATA_UNAVAILABLE'} |
| 相对前20日均量{technical_suffix} | {_ratio(volume.get('volume_ratio_20d'))} |
| 5日/20日收益率{technical_suffix} | {_pct((analysis.get('returns', {}).get('five_day') or 0) * 100) if analysis.get('returns', {}).get('five_day') is not None else 'DATA_UNAVAILABLE'} / {_pct((analysis.get('returns', {}).get('twenty_day') or 0) * 100) if analysis.get('returns', {}).get('twenty_day') is not None else 'DATA_UNAVAILABLE'} |
| MA20 / MA50 / MA200{technical_suffix} | {_price(moving.get('ma20'))} / {_price(moving.get('ma50'))} / {_price(moving.get('ma200'))} |
| RSI14{technical_suffix} | {analysis.get('rsi14', 'DATA_UNAVAILABLE')} |
| 50日/200日趋势{technical_suffix} | {moving.get('trend_50', 'DATA_UNAVAILABLE')} / {moving.get('trend_200', 'DATA_UNAVAILABLE')} |
| 趋势分类{technical_suffix} | {analysis.get('trend', {}).get('display', 'DATA_UNAVAILABLE')} |
{basis_note}

**技术位置{technical_suffix}（仅供参考，不是确定性预测）**

- First Support: {_price(levels.get('first_support'))}
- Second Support: {_price(levels.get('second_support'))}
- First Resistance: {_price(levels.get('first_resistance'))}
- Second Resistance: {_price(levels.get('second_resistance'))}

**Key News**

{chr(10).join(_news_lines(ticker, news_items))}

**Risk Events**

{chr(10).join(event_text)}

**情景分析**

{chr(10).join(_scenarios(analysis, regime))}
"""


def build_report(
    market_snapshot: dict[str, Any],
    analysis_snapshot: dict[str, Any],
    news_events_snapshot: dict[str, Any],
    archive_path: str | Path | None = None,
) -> str:
    market_date = market_snapshot.get("market_date", "DATA_UNAVAILABLE")
    generated_at = analysis_snapshot.get("generated_at_utc") or news_events_snapshot.get("generated_at_utc")
    analyses = analysis_snapshot.get("assets", {})
    quotes = market_snapshot.get("assets", {})
    news = news_events_snapshot.get("news", {})
    events = news_events_snapshot.get("events", {})
    regime = analysis_snapshot.get("market_regime", {})
    indexes = market_snapshot.get("groups", {}).get("major_indexes", {})
    risks = market_snapshot.get("groups", {}).get("risk_dashboard", {})
    portfolio = market_snapshot.get("groups", {}).get("portfolio", {})
    watchlist = market_snapshot.get("groups", {}).get("watchlist", {})

    index_rows = [
        _asset_line(label, quote, analyses.get(quote.get("ticker"), {}))
        for label, quote in indexes.items()
    ]
    risk_rows = [
        f"| {label} | {_risk_value(label, quote.get('close')) if quote.get('status') == 'OK' else 'DATA_UNAVAILABLE'} | {quote.get('status', 'DATA_UNAVAILABLE')} |"
        for label, quote in risks.items()
    ]
    changes = []
    for label, quote in indexes.items():
        if quote.get("status") == "OK":
            changes.append(f"{label} {_pct((quote.get('close') / quote.get('previous_close') - 1) * 100) if quote.get('previous_close') else 'DATA_UNAVAILABLE'}")
    top_events = [item.get("title", "未命名事件") for item in news.get("items", [])[:3]]
    key_points = [
        f"- FACT：主要指数当日表现：{'; '.join(changes) if changes else 'DATA_UNAVAILABLE'}。",
        f"- ANALYSIS：规则市场状态为 **{regime.get('state', 'UNKNOWN')}**（{regime.get('display', 'DATA_UNAVAILABLE')}，评分 {regime.get('score', 'DATA_UNAVAILABLE')}）。",
        f"- FACT：最近48小时取得 {len(news.get('items', []))} 条带来源新闻；事件模块状态为 {events.get('status', 'DATA_UNAVAILABLE')}。",
    ]
    if top_events:
        key_points[2] = f"- FACT：近期重点新闻包括：{'；'.join(top_events)}。"

    portfolio_sections = [
        _instrument_section(label, quote["ticker"], quote, analyses.get(quote["ticker"], {}), news.get("items", []), events.get("items", []), regime)
        for label, quote in portfolio.items()
    ]
    watchlist_sections = [
        _instrument_section(label, quote["ticker"], quote, analyses.get(quote["ticker"], {}), news.get("items", []), events.get("items", []), regime)
        for label, quote in watchlist.items()
    ]
    if not watchlist_sections:
        watchlist_sections = ["当前 watchlist 为空，未生成个股段落。"]
    risk_events = events.get("items", [])
    if events.get("status") != "OK":
        upcoming = f"DATA_UNAVAILABLE：事件源不可用。错误：{', '.join(events.get('errors', [])) or 'unknown'}"
    elif risk_events:
        upcoming = "\n".join(f"- FACT：{item.get('event_date')} — {item.get('title')}（{item.get('source')}）" for item in risk_events)
    else:
        upcoming = "未来7日未发现已取得的匹配事件；这不等于不存在风险事件。"
    sources = sorted({quote.get("source") for quote in quotes.values() if quote.get("source")} | {item.get("source") for item in news.get("items", []) if item.get("source")} | {item.get("source") for item in risk_events if item.get("source")})
    archive_line = f"\nArchive Path: {archive_path}" if archive_path else ""
    return f"""# US Market Daily Intelligence

Market Date: {market_date}
Generated At: {_date_time(generated_at)}{archive_line}

## 1. Executive Summary

**FACT / ANALYSIS boundary**

{chr(10).join(key_points)}

Market Regime: **{regime.get('display', 'DATA_UNAVAILABLE')} {regime.get('state', 'UNKNOWN')}**

## 2. Major Indexes

| 指数 | 收盘价 | 当日涨跌幅 | 状态 |
|---|---:|---:|---|
{chr(10).join(index_rows)}

## 3. Market Risk Dashboard

| 指标 | 数值 | 状态 |
|---|---:|---|
{chr(10).join(risk_rows)}

## 4. Portfolio ETF

VOO与IQQ存在潜在重叠持仓，不视为完全独立的资产类别。

{chr(10).join(portfolio_sections)}

## 5. Watchlist

{chr(10).join(watchlist_sections)}

## 6. Tomorrow / Next Session Watch

- ANALYSIS：下一交易日重点观察市场状态是否维持 {regime.get('state', 'UNKNOWN')}。
- FACT：高质量新闻和事件以来源字段为准；未取得的数据保持 DATA_UNAVAILABLE。

## 7. Upcoming 7-Day Risks

{upcoming}

## 8. Data Sources

{chr(10).join(f'- {source}' for source in sources) if sources else '- DATA_UNAVAILABLE'}

## 9. Disclaimer

仅供个人信息整理和投研辅助，不是投资建议，最终投资决策由用户本人作出。
"""


def build_mobile_summary(
    market_snapshot: dict[str, Any],
    analysis_snapshot: dict[str, Any],
    news_events_snapshot: dict[str, Any],
    report_file: str | Path,
) -> str:
    market_date = market_snapshot.get("market_date", "DATA_UNAVAILABLE")
    regime = analysis_snapshot.get("market_regime", {})
    quotes = market_snapshot.get("assets", {})
    analyses = analysis_snapshot.get("assets", {})
    portfolio = market_snapshot.get("groups", {}).get("portfolio", {})
    watchlist = market_snapshot.get("groups", {}).get("watchlist", {})
    news_items = news_events_snapshot.get("news", {}).get("items", [])
    events = news_events_snapshot.get("events", {})
    lines = [
        f"📊 美股日报 | {market_date}",
        f"市场：{regime.get('display', 'DATA_UNAVAILABLE')} {regime.get('state', 'UNKNOWN')}",
        f"S&P 500：{_price(quotes.get('^GSPC', {}).get('close'))}",
        f"Nasdaq 100：{_price(quotes.get('^NDX', {}).get('close'))}",
        f"VOO：{_price(quotes.get('VOO', {}).get('close'))}",
        f"IQQ：{_price(quotes.get('IQQ', {}).get('close'))}",
        "",
        "🔥 今日重点",
    ]
    for index, item in enumerate(news_items[:3], 1):
        lines.append(f"{index}. {item.get('title')}（{item.get('source')}）")
    if not news_items:
        lines.append("1. DATA_UNAVAILABLE：未取得近期新闻。")
    lines.extend([
        "",
        "🧭 今日结论",
        f"1. FACT：S&P 500、Nasdaq 100和Russell 2000的当日表现已纳入完整日报，市场状态规则评分为{regime.get('score', 'DATA_UNAVAILABLE')}。",
        f"2. ANALYSIS：当前Market Regime为{regime.get('state', 'UNKNOWN')}；该结果基于指数相对MA50、20日收益率和VIX规则，不是预测。",
        "3. ANALYSIS：VOO与IQQ不能视为完全独立资产；IQQ技术指标若使用基准代理，会明确标注且不等同于IQQ自身历史。",
    ])
    lines.extend(["", "📌 自选股"])
    if not watchlist:
        lines.append("当前watchlist为空。")
    for label, quote in watchlist.items():
        analysis = analyses.get(quote["ticker"], {})
        price = analysis.get("price", {})
        lines.append(f"{label} {_pct(price.get('daily_change_pct'))} 状态：{analysis.get('trend', {}).get('display', 'DATA_UNAVAILABLE')}")
    lines.extend(["", "📦 ETF"])
    for label, quote in portfolio.items():
        analysis = analyses.get(quote["ticker"], {})
        lines.append(f"{label}：{_pct(analysis.get('price', {}).get('daily_change_pct'))}，{analysis.get('trend', {}).get('display', 'DATA_UNAVAILABLE')}")
    lines.extend(["", "📈 市场变化"])
    for label, ticker in (("S&P 500", "^GSPC"), ("Nasdaq 100", "^NDX"), ("Russell 2000", "^RUT")):
        quote = quotes.get(ticker, {})
        change = None
        if quote.get("status") == "OK" and quote.get("previous_close"):
            change = (quote["close"] / quote["previous_close"] - 1) * 100
        lines.append(f"{label}：{_pct(change)}")
    lines.extend(["", "📊 风险指标"])
    lines.append(f"VIX：{_risk_value('VIX', quotes.get('^VIX', {}).get('close'))}")
    lines.append(f"US10Y：{_risk_value('US10Y', quotes.get('^TNX', {}).get('close'))}")
    lines.extend(["", "📍 技术观察"])
    for label, quote in portfolio.items():
        analysis = analyses.get(quote["ticker"], {})
        if _analysis_usable(analysis):
            returns = analysis.get("returns", {})
            suffix = "（基准代理技术背景，不等同于自身历史）" if analysis.get("status") == "OK_WITH_PROXY" else ""
            basis_label = f"{analysis.get('history_ticker')} " if analysis.get("status") == "OK_WITH_PROXY" else ""
            lines.append(f"{label}：{basis_label}5日 {_pct((returns.get('five_day') or 0) * 100)}，20日 {_pct((returns.get('twenty_day') or 0) * 100)}，MA20 {_price(analysis.get('moving_averages', {}).get('ma20'))}{suffix}")
            levels = analysis.get("levels", {})
            lines.append(f"{label}关键位置：支撑 {_price(levels.get('first_support'))} / {_price(levels.get('second_support'))}；阻力 {_price(levels.get('first_resistance'))} / {_price(levels.get('second_resistance'))}。")
        else:
            lines.append(f"{label}：DATA_UNAVAILABLE")
    lines.extend(["", "⚠️ 接下来关注"])
    if events.get("status") != "OK":
        lines.append("1. DATA_UNAVAILABLE：事件源不可用，不能确认未来7日事件日程。")
    elif events.get("items"):
        lines.extend(f"{i}. {item.get('event_date')}：{item.get('title')}" for i, item in enumerate(events["items"][:3], 1))
    else:
        lines.append("1. 暂未取得未来7日匹配事件，不代表不存在风险。")
    lines.extend([
        "",
        "📚 数据口径",
        "行情与技术指标来自已校验的日线数据；新闻保留来源与发布时间；缺失数据不作推断。",
        "仅供个人信息整理和投研辅助，不是投资建议。",
    ])
    lines.append(f"完整版已保存：{report_file}")
    return "\n".join(lines)


def write_text(path: str | Path, content: str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(target)
    return target

