import logging

from src.logging_config import SecretRedactionFilter


def test_logging_redacts_secret_and_formats_arguments(capsys):
    logger = logging.getLogger("phase_a_logging_test")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.addFilter(SecretRedactionFilter())
    logger.addHandler(handler)
    try:
        logger.info("webhook=%s ticker=%s", "https://example.test/secret", "VOO")
    finally:
        logger.removeHandler(handler)
    output = capsys.readouterr().err
    assert "webhook=[REDACTED]" in output
    assert "ticker=VOO" in output

