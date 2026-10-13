from __future__ import annotations

import sys
from asyncio import Queue, run
from textwrap import dedent
from typing import TextIO

from typer import Option, Typer

from counterweight.constants import PACKAGE_NAME, __version__
from counterweight.events import AnyEvent
from counterweight.input import start_input_control, start_reading_keys, stop_input_control, stop_reading_keys
from counterweight.logging import last_devlog, tail_devlog
from counterweight.output import start_mouse_tracking, stop_mouse_tracking

cli = Typer(
    name=PACKAGE_NAME,
    no_args_is_help=True,
    help=dedent(
        """\
        CLI tools for Counterweight.
        """
    ),
)


@cli.command()
def version() -> None:
    """
    Display version information.
    """
    print(__version__)


@cli.command()
def devlog(
    last: int | None = Option(default=None, help="Print the last N log messages and exit."),
    json: bool = Option(default=False, help="Print the raw JSON lines instead of rendering them."),
) -> None:
    """Tail the developer log file."""
    if last is not None:
        last_devlog(last, raw=json)
    else:
        tail_devlog(raw=json)


@cli.command()
def check_input(mouse: bool = Option(default=False, help="Also capture mouse inputs and show mouse events.")) -> None:
    """
    Enter the same input-capture state used during application mode,
    and show the results of reading input (e.g., key events).
    """

    try:
        run(_check_input(mouse=mouse, input_stream=sys.stdin, output_stream=sys.stdout))
    except KeyboardInterrupt:
        print("Exiting...")


async def _check_input(mouse: bool, input_stream: TextIO, output_stream: TextIO) -> None:
    """
    Print every input read from `input_stream`, under the same input control as an app, until cancelled.
    Then stop reading input before handing the terminal back.
    """
    event_queue: Queue[AnyEvent] = Queue()

    original = start_input_control(stream=input_stream)
    if mouse:
        start_mouse_tracking(stream=output_stream)
    start_reading_keys(stream=input_stream, put_event=event_queue.put_nowait)
    try:
        while True:
            print("Waiting for input (press ctrl+c to exit)...", file=output_stream)
            key = await event_queue.get()
            print(f"{key!r}", file=output_stream)
    finally:
        stop_reading_keys(stream=input_stream)
        stop_input_control(stream=input_stream, original=original)
        if mouse:
            stop_mouse_tracking(stream=output_stream)
