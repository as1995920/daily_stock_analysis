"""Safe application logging with basic secret redaction."""

from __future__ import annotations

import logging
import re


_SECRET_PATTERN = re.compile(
    r"(?i)(webhook|secret|token|api[_-]?key|authorization)(\s*[=:]\s*)[^\s,;]+"
)


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Materialize %-style arguments before clearing them; otherwise the
        # formatter would receive a message containing literal ``%s`` tokens.
        record.msg = _SECRET_PATTERN.sub(r"\1\2[REDACTED]", record.getMessage())
        record.args = ()
        return True


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("us_market_daily")
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        handler.addFilter(SecretRedactionFilter())
        logger.addHandler(handler)
    return logger

