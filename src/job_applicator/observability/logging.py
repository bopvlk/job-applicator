import base64
from datetime import UTC, datetime
import json
import logging
import queue
import sys
import threading
from typing import Any
import urllib.request

import sentry_sdk

from job_applicator.config import config


def init_sentry() -> None:
    """Initialization Sentry APM and errors catching."""
    if config.sentry_dsn:
        sentry_sdk.init(
            dsn=config.sentry_dsn,
            traces_sample_rate=1.0,
            send_default_pii=True,
        )


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
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        for key, val in record.__dict__.items():
            if key not in self.BUILTIN_ATTRS and not key.startswith("_"):
                log_data[key] = val

        return json.dumps(log_data, default=str)


class LokiHandler(logging.Handler):
    """Non-blocking background handler that pushes structured JSON logs to Grafana Cloud Loki."""

    def __init__(self, url: str, user: str, token: str, app_name: str = "job-applicator"):
        super().__init__()
        self.url = url
        self.app_name = app_name
        auth_str = f"{user}:{token}"
        self.auth_header = f"Basic {base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')}"
        self.queue: queue.Queue = queue.Queue(maxsize=1000)
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            formatted = self.format(record)
            # Наносекундний timestamp для Loki
            ts_ns = str(int(record.created * 1e9))
            self.queue.put_nowait((record.levelname, ts_ns, formatted))
        except Exception:
            pass

    def _worker(self) -> None:
        while True:
            try:
                level, ts_ns, log_line = self.queue.get()
                payload = {
                    "streams": [
                        {
                            "stream": {
                                "app": self.app_name,
                                "level": level,
                            },
                            "values": [[ts_ns, log_line]],
                        }
                    ]
                }
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    self.url,
                    data=data,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": self.auth_header,
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5):
                    pass
            except Exception:
                pass
            finally:
                self.queue.task_done()


def setup_logging(level: str = "INFO") -> None:
    """Initialize root logger with JSON stdout and optional Grafana Loki stream."""
    json_formatter = JsonFormatter()
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(json_formatter)
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())
    root_logger.handlers.clear()
    root_logger.addHandler(stdout_handler)

    loki_handler = LokiHandler(
        url=config.grafana_loki_url,
        user=config.grafana_loki_user,
        token=config.grafana_loki_token,
        app_name="job-applicator",
    )
    loki_handler.setFormatter(json_formatter)
    root_logger.addHandler(loki_handler)
