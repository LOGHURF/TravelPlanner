"""Centralized logging setup."""

from __future__ import annotations

import logging
import sys

from app.config.settings import settings

_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, str(settings.LOG_LEVEL).upper(), logging.INFO))

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root.addHandler(console)

    # Keep third-party transport noise out of normal business logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)