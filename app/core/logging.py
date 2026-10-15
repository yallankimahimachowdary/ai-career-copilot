import logging
import sys
from app.core.config import settings


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
    return logger


logger = setup_logging()
