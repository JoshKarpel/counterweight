import logging
import logging.config
from pathlib import Path
from shutil import get_terminal_size
from tempfile import gettempdir
from time import sleep

import structlog

from counterweight.constants import PACKAGE_NAME

DEVLOG_FILE = Path(gettempdir()) / f"{PACKAGE_NAME}.log"
DEVLOG_JSON_FILE = Path(gettempdir()) / f"{PACKAGE_NAME}.log.jsonl"


def configure_logging() -> None:
    DEVLOG_FILE.write_text("")
    DEVLOG_JSON_FILE.write_text("")

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S.%f", utc=False),
    ]

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "human": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processors": [
                        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                        structlog.dev.ConsoleRenderer(),
                    ],
                    "foreign_pre_chain": shared_processors,
                },
                "json": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processors": [
                        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                        structlog.processors.JSONRenderer(),
                    ],
                    "foreign_pre_chain": shared_processors,
                },
            },
            "handlers": {
                "human_file": {
                    "class": "logging.FileHandler",
                    "formatter": "human",
                    "filename": str(DEVLOG_FILE),
                    "mode": "w",
                },
                "json_file": {
                    "class": "logging.FileHandler",
                    "formatter": "json",
                    "filename": str(DEVLOG_JSON_FILE),
                    "mode": "w",
                },
            },
            "root": {
                "handlers": ["human_file", "json_file"],
                "level": "DEBUG",
            },
        }
    )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def tail_devlog(json: bool = False) -> None:
    path = DEVLOG_JSON_FILE if json else DEVLOG_FILE
    while True:
        path.touch(exist_ok=True)
        with path.open(mode="r") as f:
            w, _ = get_terminal_size()
            while True:
                line = f.readline()
                if line:
                    print(line, end="")
                else:
                    if f.tell() > path.stat().st_size:
                        # the file is shorter than our current position, so it was truncated
                        print(" DevLog Rotated ".center(w, "━"))
                        break
                    else:
                        sleep(0.01)


def last_devlog(n: int, json: bool = False) -> None:
    path = DEVLOG_JSON_FILE if json else DEVLOG_FILE
    path.touch(exist_ok=True)
    lines = path.read_text().splitlines(keepends=True)
    for line in lines[-n:]:
        print(line, end="")
