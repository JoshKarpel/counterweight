from logging import NOTSET
from pathlib import Path
from shutil import get_terminal_size
from tempfile import gettempdir
from time import sleep

import structlog
from structlog import WriteLoggerFactory

from counterweight.constants import PACKAGE_NAME

DEVLOG_FILE = Path(gettempdir()) / f"{PACKAGE_NAME}.log"


def configure_logging() -> None:
    DEVLOG_FILE.write_text("")  # truncate file and make sure it exists

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S.%f", utc=False),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(NOTSET),
        context_class=dict,
        logger_factory=WriteLoggerFactory(DEVLOG_FILE.open(mode="w")),
        cache_logger_on_first_use=True,
    )


def tail_devlog() -> None:
    while True:
        DEVLOG_FILE.touch(exist_ok=True)
        with DEVLOG_FILE.open(mode="r") as f:
            w, _ = get_terminal_size()
            while True:
                line = f.readline()
                if line:
                    print(line, end="")
                else:
                    if f.tell() > DEVLOG_FILE.stat().st_size:
                        # the file is shorter than our current position, so it was truncated
                        print(" DevLog Rotated ".center(w, "━"))
                        break
                    else:
                        sleep(0.01)
