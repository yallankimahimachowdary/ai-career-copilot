import logging
import sys
from app.core.config import settings
from app.core.redaction import redact_credentials


class RedactingFilter(logging.Filter):
    """Logging filter that sanitizes sensitive credentials and API query parameters."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_credentials(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: redact_credentials(v) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(redact_credentials(a) if isinstance(a, str) else a for a in record.args)
        return True


def setup_logging() -> logging.Logger:
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Suppress verbose debug trace emissions from third-party HTTP & hub libraries
    # to avoid shutdown stream errors on closed stdout during atexit session cleanup.
    for noisy_logger in ("httpcore", "httpx", "huggingface_hub", "urllib3"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    logger = logging.getLogger("ai_career_copilot")
    redacting_filter = RedactingFilter()
    logger.addFilter(redacting_filter)
    for handler in logging.root.handlers:
        handler.addFilter(redacting_filter)

    return logger


logger = setup_logging()

