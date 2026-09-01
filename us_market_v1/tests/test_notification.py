import base64
import hashlib
import hmac

from src.providers.notification import DryRunNotificationProvider, FeishuNotificationProvider


def test_dry_run_notification_never_uses_network():
    provider = DryRunNotificationProvider()
    result = provider.send_markdown("title", "content")
    assert result.success
    assert result.detail == "not sent"
    assert provider.messages == [("title", "content")]


def test_feishu_signature_and_payload_never_require_real_secret(monkeypatch):
    provider = FeishuNotificationProvider("https://example.test/hook", "secret")
    timestamp = "1700000000"
    monkeypatch.setattr("src.providers.notification.time.time", lambda: 1700000000)
    expected = base64.b64encode(
        hmac.new(f"{timestamp}\nsecret".encode(), digestmod=hashlib.sha256).digest()
    ).decode()
    assert provider._signature(timestamp) == expected
    payload = provider._payload("title", "**content**")
    assert payload["msg_type"] == "interactive"
    assert payload["sign"] == expected


def test_feishu_retries_and_returns_failure_without_network(monkeypatch):
    provider = FeishuNotificationProvider("https://example.test/hook", retries=3)
    attempts = []

    def fail(_payload):
        attempts.append(1)
        raise OSError("offline")

    monkeypatch.setattr(provider, "_send", fail)
    monkeypatch.setattr("src.providers.notification.time.sleep", lambda _seconds: None)
    result = provider.send_text("hello")
    assert not result.success
    assert len(attempts) == 3
    assert "failed_after_3_attempts" in result.detail


def test_feishu_error_detail_redacts_credentials():
    provider = FeishuNotificationProvider("https://example.test/hook?token=secret-url", "secret")
    error = provider._safe_error(OSError("https://example.test/hook?token=secret-url secret"))
    assert "secret-url" not in error
    assert "secret" not in error

