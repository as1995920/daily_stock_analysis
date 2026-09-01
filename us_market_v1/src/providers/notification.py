"""Notification interface plus the Phase F Feishu webhook adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
import base64
import hashlib
import hmac
import json
import os
import time
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class NotificationResult:
    success: bool
    provider: str
    detail: str = ""


class NotificationProvider(Protocol):
    def send_text(self, text: str) -> NotificationResult: ...
    def send_markdown(self, title: str, content: str) -> NotificationResult: ...
    def send_error(self, message: str) -> NotificationResult: ...


@dataclass
class DryRunNotificationProvider:
    messages: list[tuple[str, str]] = field(default_factory=list)

    def send_text(self, text: str) -> NotificationResult:
        self.messages.append(("text", text))
        return NotificationResult(True, "dry-run", "not sent")

    def send_markdown(self, title: str, content: str) -> NotificationResult:
        self.messages.append((title, content))
        return NotificationResult(True, "dry-run", "not sent")

    def send_error(self, message: str) -> NotificationResult:
        self.messages.append(("error", message))
        return NotificationResult(True, "dry-run", "not sent")


@dataclass
class FeishuNotificationProvider:
    """Send a Feishu custom-bot card without exposing credentials in code."""

    webhook_url: str
    secret: str = ""
    timeout: float = 15.0
    retries: int = 3

    @classmethod
    def from_env(cls) -> "FeishuNotificationProvider":
        webhook_url = os.environ.get("FEISHU_WEBHOOK_URL", "").strip()
        secret = os.environ.get("FEISHU_SECRET", "").strip()
        if not webhook_url:
            raise ValueError("FEISHU_WEBHOOK_URL is not configured")
        return cls(webhook_url=webhook_url, secret=secret)

    def _signature(self, timestamp: str) -> str:
        string_to_sign = f"{timestamp}\n{self.secret}".encode("utf-8")
        digest = hmac.new(string_to_sign, digestmod=hashlib.sha256).digest()
        return base64.b64encode(digest).decode("ascii")

    def _payload(self, title: str, content: str) -> dict[str, object]:
        payload: dict[str, object] = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {"title": {"tag": "plain_text", "content": title}},
                "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": content}}],
            },
        }
        if self.secret:
            timestamp = str(int(time.time()))
            payload["timestamp"] = timestamp
            payload["sign"] = self._signature(timestamp)
        return payload

    def _send(self, payload: dict[str, object]) -> NotificationResult:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self.webhook_url,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            response_body = response.read().decode("utf-8", errors="replace")
        try:
            response_json = json.loads(response_body) if response_body else {}
        except json.JSONDecodeError:
            response_json = {}
        code = response_json.get("code", 0)
        if code not in (0, "0", None):
            return NotificationResult(False, "feishu", f"api_code={code}")
        return NotificationResult(True, "feishu", "sent")

    def _safe_error(self, exc: Exception) -> str:
        detail = str(exc).replace(self.webhook_url, "<redacted>")
        return detail.replace(self.secret, "<redacted>") if self.secret else detail

    def send_markdown(self, title: str, content: str) -> NotificationResult:
        last_detail = "unknown"
        for attempt in range(1, max(1, self.retries) + 1):
            try:
                result = self._send(self._payload(title, content))
                if result.success:
                    return result
                last_detail = result.detail
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                last_detail = f"{type(exc).__name__}: {self._safe_error(exc)}"
            if attempt < max(1, self.retries):
                time.sleep(min(2 ** (attempt - 1), 4))
        return NotificationResult(False, "feishu", f"failed_after_{max(1, self.retries)}_attempts: {last_detail}")

    def send_text(self, text: str) -> NotificationResult:
        return self.send_markdown("US Market Daily Intelligence", text)

    def send_error(self, message: str) -> NotificationResult:
        return self.send_text(f"⚠️ Notification error\n\n{message}")

