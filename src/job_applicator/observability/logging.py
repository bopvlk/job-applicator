import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class JsonFormatter(logging.Formatter):
    """High-performance structured JSON formatter without third-party dependencies."""

    # Built-in attributes of LogRecord to exclude from extra payload
    BUILTIN_ATTRS = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        # 1. Base mandatory fields
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 2. Add stack trace if an exception occurred
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # 3. Merge custom contextual metadata passed via extra={...}
        for key, val in record.__dict__.items():
            if key not in self.BUILTIN_ATTRS and not key.startswith("_"):
                log_data[key] = val

        return json.dumps(log_data, default=str)


def setup_logging(level: str = "INFO") -> None:
    """Initialize root logger with JSON stdout formatter."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Clear existing handlers to prevent duplicate lines
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

