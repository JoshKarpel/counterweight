from __future__ import annotations

import sys
from asyncio import Queue, get_running_loop, run
from textwrap import dedent
from threading import Thread

from click import echo
from typer import Option, Typer

from counterweight._context_vars import current_event_queue
from counterweight.constants import PACKAGE_NAME, __version__
from counterweight.events import AnyEvent
from counterweight.input import read_keys, start_input_control, stop_input_control
from counterweight.logging import tail_devlog
from counterweight.output import start_mouse_reporting, stop_mouse_reporting

cli = Typer(
    name=PACKAGE_NAME,
    no_args_is_help=True,
    rich_markup_mode="rich",
    help=dedent(
        """\
        """
    ),
)


@cli.command()
def version() -> None:
    """
    Display version information.
    """
    echo(__version__)


@cli.command()
def devlog() -> None:
    """Tail the developer log file."""
    tail_devlog()


@cli.command()
def check_input(mouse: bool = Option(default=False, help="Also capture mouse inputs and show mouse events.")) -> None:
    """
    Enter the same input-capture state used during application mode,
    and show the results of reading input (e.g., key events).
    """

    run(_check_input(mouse=mouse))


async def _check_input(mouse: bool) -> None:
    event_queue: Queue[AnyEvent] = Queue()
    current_event_queue.set(event_queue)

    loop = get_running_loop()

    def put_event(event: AnyEvent) -> None:
        loop.call_soon_threadsafe(event_queue.put_nowait, event)

    input_stream = sys.stdin
    output_stream = sys.stdout

    key_thread = Thread(target=read_keys, args=(input_stream, put_event), daemon=True)
    key_thread.start()

    original = start_input_control(stream=input_stream)
    if mouse:
        start_mouse_reporting(stream=output_stream)
    try:
        while True:
            print("Waiting for input...")
            key = await event_queue.get()
            print(f"Event: {key!r}")
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        stop_input_control(stream=input_stream, original=original)
        if mouse:
            stop_mouse_reporting(stream=output_stream)
