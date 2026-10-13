"""
The devlog: every log record from a running app, written as JSON lines to one file, and the reader that renders them.

The app only encodes JSON; rendering a record for a human happens in `counterweight devlog`,
at read time, so the render loop pays for one encoding per record rather than one per output.
"""

import json
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from shutil import get_terminal_size
from tempfile import gettempdir
from time import sleep

from without_logging import Level, capture, render_json, to_stream
from without_streams.wiring import compose, offload

from counterweight.constants import PACKAGE_NAME

DEVLOG_FILE = Path(gettempdir()) / f"{PACKAGE_NAME}.log.jsonl"

# How long `tail_devlog` waits before checking the devlog again.
POLL_INTERVAL = timedelta(milliseconds=10)

ENVELOPE = frozenset({"timestamp", "level", "logger", "message", "exception"})


@asynccontextmanager
async def devlog(path: Path = DEVLOG_FILE) -> AsyncIterator[None]:
    """
    Capture every log record, at every level, into a freshly truncated `path` for the duration of the block.

    The queue is unbounded because a dropped record is worse than a late one in a debugging aid,
    and it can't grow without bound while the loop runs: with a single sink (no `tee`),
    the sink drains everything queued each time the event loop gets a turn.
    """
    with path.open("w") as file:
        async with (
            offload(to_stream(file)) as write,
            capture(compose(render_json(), write), level=Level.DEBUG, capacity=None),
        ):
            yield


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


def tail_devlog(
    raw: bool = False,
    path: Path = DEVLOG_FILE,
    wait: Callable[[], None] = partial(sleep, POLL_INTERVAL.total_seconds()),
) -> None:
    """
    Print the devlog as it's written, starting over when an app truncates it.
    Only complete lines are printed, since the writer may be partway through one.
    `wait` is called whenever there is nothing new to read.
    """
    while True:
        path.touch(exist_ok=True)
        with path.open(mode="r") as f:
            pending = ""
            while True:
                pending += f.readline()
                if pending.endswith("\n"):
                    print(format_line(pending, raw))
                    pending = ""
                elif f.tell() > path.stat().st_size:
                    print(" DevLog Rotated ".center(get_terminal_size().columns, "━"))
                    break
                else:
                    wait()


def last_devlog(n: int, raw: bool = False, path: Path = DEVLOG_FILE) -> None:
    """Print the last `n` complete lines of the devlog."""
    path.touch(exist_ok=True)
    lines = [line for line in path.read_text().splitlines(keepends=True) if line.endswith("\n")]
    for line in lines[-n:]:
        print(format_line(line, raw))
