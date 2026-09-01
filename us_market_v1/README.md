# US Market Daily Intelligence V1

This directory is the personal US-market daily intelligence pipeline deployed through GitHub Actions. It preserves the verified V1 data/report contract while using the parent project only as the repository and automation shell.

## Scope

- NYSE session-aware daily report at 06:30 Japan time (21:30 UTC).
- Market indices: S&P 500, Nasdaq 100, Dow Jones, Russell 2000.
- Risk indicators: VIX, US 10Y, DXY, gold, WTI.
- Portfolio context: VOO and IQQ; watchlist is currently empty.
- Evidence labels: FACT, ANALYSIS, SCENARIO; missing values remain DATA_UNAVAILABLE.
- IQQ technical history may use the explicitly documented Nasdaq-100 proxy and is labeled accordingly.
- No trading, brokerage, account, or order operations are performed.

## GitHub Actions setup

Add these repository secrets under Settings -> Secrets and variables -> Actions -> Secrets:

- FEISHU_WEBHOOK_URL
- FEISHU_SECRET

Run **US Market Daily Intelligence V1** manually with dry-run enabled first. Scheduled runs use the same entry point and send the mobile summary only after report generation succeeds. Reports, inputs, logs, and the duplicate-send state are uploaded as workflow artifacts/cache data.

## Local run

```powershell
python -m src.main --phase f --dry-run
python -m src.main --phase f
```

Do not commit a real .env file or any webhook value.
