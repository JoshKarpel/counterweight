from __future__ import annotations

import sys
from asyncio import Queue
from typing import Never, TextIO

from without_cli import INT, Streams, command, flag, group, option, optional, run

from counterweight.constants import PACKAGE_NAME, __version__
from counterweight.events import AnyEvent
from counterweight.input import start_input_control, start_reading_keys, stop_input_control, stop_reading_keys
from counterweight.logging import last_devlog, tail_devlog
from counterweight.output import start_bracketed_paste, start_mouse_tracking, stop_bracketed_paste, stop_mouse_tracking

SIGINT_EXIT = 130


@command("version")
async def version(streams: Streams) -> int:
    """Display version information."""
    streams.stdout.write(f"{__version__}\n")
    return 0


@command(
    "devlog",
    option("--last", optional(INT), summary="Print the last N log messages and exit."),
    flag("--json", summary="Print the raw JSON lines instead of rendering them."),
)
async def devlog(streams: Streams, last: int | None, json: bool) -> int:
    """Tail the developer log file."""
    if last is not None:
        last_devlog(streams.stdout, last, raw=json)
    else:
        await tail_devlog(streams.stdout, raw=json)
    return 0


@command("check-input", flag("--mouse", summary="Also capture mouse inputs and show mouse events."))
async def check_input(streams: Streams, mouse: bool) -> int:
    """Show the events read from input (such as key presses), in the input-capture state an app runs in."""
    # Input capture and mouse tracking need the real terminal, which `streams` doesn't carry.
    return await _check_input(mouse=mouse, input_stream=sys.stdin, output_stream=sys.stdout)


async def _check_input(mouse: bool, input_stream: TextIO, output_stream: TextIO) -> Never:
    """
    Print every input read from `input_stream`, under the same input control as an app, until cancelled.
    Then stop reading input before handing the terminal back.
    """
    event_queue: Queue[AnyEvent] = Queue()

    original = start_input_control(stream=input_stream)
    key_reader = start_reading_keys(stream=input_stream, put_event=event_queue.put_nowait)
    try:
        start_bracketed_paste(stream=output_stream)
        if mouse:
            start_mouse_tracking(stream=output_stream)
        while True:
            output_stream.write("Waiting for input (press ctrl+c to exit)...\n")
            output_stream.flush()
            key = await event_queue.get()
            output_stream.write(f"{key!r}\n")
    finally:
        stop_reading_keys(key_reader)
        stop_input_control(stream=input_stream, original=original)
        stop_bracketed_paste(stream=output_stream)
        if mouse:
            stop_mouse_tracking(stream=output_stream)


cli = group(
    PACKAGE_NAME,
    commands=(version, devlog, check_input),
    summary="CLI tools for Counterweight.",
    version=__version__,
)


def main() -> None:
    """The `counterweight` console script."""
    try:
        code = run(cli)
    except KeyboardInterrupt:
        code = SIGINT_EXIT
    raise SystemExit(code)
