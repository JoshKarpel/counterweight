"""
The devlog: a running app's log records, written as JSON lines to one file, and the reader that renders them.

The app only encodes JSON; rendering a record for a human happens in `counterweight devlog`,
at read time, so the render loop pays for one encoding per record rather than one per output.
"""

import json
import logging
from asyncio import sleep
from collections.abc import AsyncIterator
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Mapping
from contextlib import asynccontextmanager
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from shutil import get_terminal_size
from tempfile import gettempdir

from without_cli import Writer
from without_logging import Level
from without_logging import capture
from without_logging import render_json
from without_logging import to_stream
from without_streams.wiring import compose
from without_streams.wiring import offload

from counterweight.constants import PACKAGE_NAME

DEVLOG_FILE = Path(gettempdir()) / f"{PACKAGE_NAME}.log.jsonl"
TAIL_POLL = timedelta(milliseconds=10)

ENVELOPE = frozenset({"timestamp", "level", "logger", "message", "exception"})

# The levels every app's devlog starts from: counterweight's records at every level, and everyone else's from INFO up.
BASE_LOG_LEVELS: frozendict[str, int] = frozendict({"": logging.INFO, PACKAGE_NAME: logging.DEBUG})


def app_log_levels(app_module: str, overrides: Mapping[str, int]) -> frozendict[str, int]:
    """
    The levels the devlog captures for an app whose root component is defined in `app_module`:
    `BASE_LOG_LEVELS`, with the top-level package of `app_module` at `DEBUG`, then `overrides`, which win.

    The top-level package covers every logger an app names with `getLogger(__name__)`,
    including `__main__` for an app run as a script.
    """
    return frozendict({**BASE_LOG_LEVELS, app_module.partition(".")[0]: logging.DEBUG, **overrides})


@asynccontextmanager
async def devlog(path: Path = DEVLOG_FILE, levels: Mapping[str, int] = BASE_LOG_LEVELS) -> AsyncIterator[None]:
    """
    Capture log records into a freshly truncated `path` for the duration of the block,
    at the levels `levels` gives by logger name, as `logging.config` does, with `""` the root logger.

    A logger the mapping doesn't name inherits its level from its nearest named ancestor, as stdlib loggers do,
    and the root logger captures from the lowest level in the mapping if it isn't named.
    Raising a logger's level skips its records before they're built, which is where most of a record's cost is,
    so a library that logs at `DEBUG` on a hot path costs the app nothing unless the mapping asks for it.

    The queue is unbounded because a dropped record is worse than a late one in a debugging aid,
    and it can't grow without bound while the loop runs: with a single sink (no `tee`),
    the sink drains everything queued each time the event loop gets a turn.
    """
    with path.open("w") as file:
        async with (
            offload(to_stream(file)) as write,
            capture(compose(render_json(), write), level=min(levels.values(), default=Level.DEBUG), capacity=None),
            # After `capture`, which lowers the root logger to its level, so these levels win until exit.
            logger_levels(levels),
        ):
            yield


@asynccontextmanager
async def logger_levels(levels: Mapping[str, int]) -> AsyncIterator[None]:
    """Set each named logger's level for the duration of the block, then restore the levels they had."""
    loggers = {logging.getLogger(name): level for name, level in levels.items()}
    previous = {logger: logger.level for logger in loggers}
    for logger, level in loggers.items():
        logger.setLevel(level)
    try:
        yield
    finally:
        for logger, level in previous.items():
            logger.setLevel(level)


def render_line(record: Mapping[str, object]) -> str:
    """
    Render one devlog record (a parsed JSON line) for a human:
    local time, level, logger, message, then the record's fields and any traceback.
    """
    when = datetime.fromisoformat(str(record["timestamp"])).astimezone()
    parts = [when.strftime("%H:%M:%S.%f"), f"{record['level']:<8}", str(record["logger"]), str(record["message"])]
    parts.extend(f"{key}={value!r}" for key, value in record.items() if key not in ENVELOPE)
    line = " ".join(parts)
    exception = record.get("exception")
    if not isinstance(exception, Mapping):
        return line
    return "\n".join([line, *(f"  {traceback_line}" for traceback_line in render_exception(exception))])


def render_exception(exception: Mapping[str, object]) -> list[str]:
    """The lines of a traceback encoded by `without_logging.exception_to_dict`, its cause first, as Python prints it."""
    cause = exception.get("cause")
    lines = (
        [*render_exception(cause), "", "The above exception led to the following exception:", ""]
        if isinstance(cause, Mapping)
        else []
    )
    lines.append("Traceback (most recent call last):")
    frames = exception.get("frames")
    for frame in frames if isinstance(frames, list) else []:
        lines.append(f'  File "{frame["file"]}", line {frame["line"]}, in {frame["function"]}')
        if frame["code"]:
            lines.append(f"    {frame['code']}")
    lines.append(str(exception["message"]))
    return lines


def format_line(line: str, raw: bool) -> str:
    return line.rstrip("\n") if raw else render_line(json.loads(line))


async def wait_for_more() -> None:
    """Wait one `TAIL_POLL` on the event loop for the devlog to grow."""
    await sleep(TAIL_POLL.total_seconds())


async def tail_devlog(
    out: Writer,
    raw: bool = False,
    path: Path = DEVLOG_FILE,
    wait: Callable[[], Awaitable[None]] = wait_for_more,
) -> None:
    """
    Write the devlog to `out` as it's written, starting over when an app truncates it.
    Only complete lines are written, since the writer may be partway through one.
    `wait` is awaited whenever there is nothing new to read.

    Waiting for more on the event loop, not in a blocking sleep, is what lets the first Ctrl-C stop it:
    under `asyncio.run` that cancels the main task, which a blocking loop would never notice.
    """
    while True:
        path.touch(exist_ok=True)  # noqa: ASYNC240 (a local file, read with blocking calls anyway)
        with path.open(mode="r") as f:
            pending = ""
            while True:
                pending += f.readline()
                if pending.endswith("\n"):
                    out.write(f"{format_line(pending, raw)}\n")
                    out.flush()
                    pending = ""
                elif f.tell() > path.stat().st_size:  # noqa: ASYNC240 (as above)
                    out.write(f"{' DevLog Rotated '.center(get_terminal_size().columns, '━')}\n")
                    break
                else:
                    await wait()


def last_devlog(out: Writer, n: int, raw: bool = False, path: Path = DEVLOG_FILE) -> None:
    """Write the last `n` complete lines of the devlog to `out`."""
    path.touch(exist_ok=True)
    lines = [line for line in path.read_text().splitlines(keepends=True) if line.endswith("\n")]
    for line in lines[-n:]:
        out.write(f"{format_line(line, raw)}\n")
