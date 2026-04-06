"""Application logging setup with structured daily-rotated logs."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from app.config import settings


class JsonLogFormatter(logging.Formatter):
    """Emit one JSON object per log entry for machine-readable logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    """Configure console + rotating file log handlers once."""
    root = logging.getLogger()
    if getattr(root, "_beacon_logging_configured", False):
        return

    level_name = str(getattr(settings, "backend_log_level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    logs_dir = Path(getattr(settings, "logs_dir", "./logs"))
    logs_dir.mkdir(parents=True, exist_ok=True)
    app_log_path = logs_dir / str(getattr(settings, "app_log_filename", "app.log"))

    root.setLevel(level)
    root.handlers.clear()

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

    rotating_handler = TimedRotatingFileHandler(
        app_log_path,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
        utc=True,
    )
    rotating_handler.setLevel(level)
    rotating_handler.setFormatter(JsonLogFormatter())

    root.addHandler(stream_handler)
    root.addHandler(rotating_handler)
    setattr(root, "_beacon_logging_configured", True)
