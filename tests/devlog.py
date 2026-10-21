from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

STANDARD_ATTRIBUTES = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime", "taskName"}


def devlog_line(record: logging.LogRecord) -> str:
    """A record as `counterweight devlog` shows it, without the timestamp: level, logger, message, then its fields."""
    fields = (f"{key}={value!r}" for key, value in record.__dict__.items() if key not in STANDARD_ATTRIBUTES)
    return " ".join([f"{record.levelname:<8}", record.name, record.getMessage(), *fields])


class Lines(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(devlog_line(record))


@contextmanager
def devlog_lines(logger_name: str = "counterweight._app") -> Iterator[list[str]]:
    """The devlog lines `logger_name` logs inside the block."""
    logger = logging.getLogger(logger_name)
    handler = Lines()
    previous_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        yield handler.lines
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
