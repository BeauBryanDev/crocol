import contextvars
import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = ("%(asctime)s %(levelname)s %(name)s rid=%(rid)s tid=%(tid)s "
              "%(message)s")
LOG_FILE_BYTES = 5_000_000
LOG_FILE_COUNT = 5
QUIET_LOGGERS = ("httpx", "httpcore", "httpx2", "google_genai", "anthropic",
                 "chromadb", "urllib3", "openai")
REQUEST_ID: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-")
TRACE_ID: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id", default="-")


class ContextFilter(logging.Filter):
    """Stamps every record with the current request and trace ids."""

    def filter(self, record: logging.LogRecord) -> bool:

        record.rid = REQUEST_ID.get()
        record.tid = TRACE_ID.get()
        return True


def bind_request(request_id: str) -> None:

    REQUEST_ID.set(request_id)


def bind_trace(trace_id: str) -> None:

    TRACE_ID.set(trace_id)


def elapsed_ms(started: float) -> int:

    return int((time.perf_counter() - started) * 1000)


def build_handlers(log_file: Path | None) -> list[logging.Handler]:

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(
            log_file, maxBytes=LOG_FILE_BYTES, backupCount=LOG_FILE_COUNT,
            encoding="utf-8"))

    formatter = logging.Formatter(LOG_FORMAT)
    for handler in handlers:
        handler.setFormatter(formatter)
        handler.addFilter(ContextFilter())
    return handlers


def setup_logging(level: str = "INFO", log_file: Path | None = None) -> None:
    """Configure the root logger once; calling it again replaces handlers."""
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()

    for handler in build_handlers(log_file):
        root.addHandler(handler)
    root.setLevel(level.upper())

    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
