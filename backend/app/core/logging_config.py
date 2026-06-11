"""Structured JSON logging configuration.

Provides automatic request-id correlation via contextvars without
adding new dependencies — uses only stdlib ``logging``.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class JsonFormatter(logging.Formatter):
    """Emit log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Include structured extra fields
        for key in ("request_id", "telegram_event", "telegram_user_id",
                     "tool", "tool_name", "latency_ms", "user_role",
                     "agent_action", "match_type", "duration_ms",
                     "method", "path", "status"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info and record.exc_info[1]:
            payload["exception"] = str(record.exc_info[1])
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Set up structured JSON logging on stdout.

    Call once at application startup.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.setLevel(level)

    root = logging.getLogger()
    root.handlers.clear()  # Remove uvicorn defaults
    root.setLevel(level)
    root.addHandler(handler)

    # Keep noisy libs at WARNING
    for noisy in ("httpx", "httpcore", "urllib3", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
