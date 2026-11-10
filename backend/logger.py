"""Small rotating activity log."""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime
from logging.handlers import RotatingFileHandler

from backend.paths import LOG_DIR, LOG_FILE

_LOGGER_NAME = "bfl.activity"
_MAX_BYTES = 512_000
_BACKUP_COUNT = 3


class _ISOFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        return datetime.fromtimestamp(record.created).astimezone().isoformat(timespec="seconds")


def _get_logger() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    handler.setFormatter(_ISOFormatter("[%(asctime)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def _clean(event: object) -> str:
    return " ".join(str(event).replace("\r", " ").splitlines())


def log_event(event: str) -> None:
    _get_logger().info(_clean(event))


def recent_events(limit: int = 20) -> list[str]:
    if limit <= 0:
        return []
    if not LOG_FILE.exists():
        return ["No activity recorded yet."]
    with LOG_FILE.open("r", encoding="utf-8", errors="replace") as stream:
        lines = deque((line.rstrip("\n") for line in stream), maxlen=limit)
    return list(lines) or ["No activity recorded yet."]
