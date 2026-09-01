from pathlib import Path


def test_github_actions_schedule_and_secret_boundaries():
    workflow = Path(__file__).parents[1] / ".github" / "workflows" / "us_market_daily.yml"
    content = workflow.read_text(encoding="utf-8")
    assert 'cron: "30 21 * * *"' in content
    assert "python -m src.main --phase f" in content
    assert "secrets.FEISHU_WEBHOOK_URL" in content
    assert "secrets.FEISHU_SECRET" in content
    assert "FEISHU_SECRET is not configured in GitHub Secrets." in content
    assert "workflow_dispatch:" in content
    assert "contents: read" in content
    assert "actions/cache/restore@v4" in content
    assert "actions/cache/save@v4" in content
    assert "concurrency:" in content
    assert "FEISHU_WEBHOOK_URL=" not in content

