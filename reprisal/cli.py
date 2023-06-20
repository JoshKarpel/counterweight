from __future__ import annotations

import sys
from queue import Queue
from textwrap import dedent
from threading import Thread

from click import echo
from typer import Typer

from reprisal.constants import PACKAGE_NAME, __version__
from reprisal.input import read_keys, start_input_control, stop_input_control
from reprisal.logging import tail_devlog

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
def keys() -> None:
    event_queue = Queue()

    input_stream = sys.stdin

    key_thread = Thread(target=read_keys, args=(event_queue, input_stream), daemon=True)
    key_thread.start()

    original = start_input_control(stream=input_stream)
    try:
        while True:
            print("Waiting for input...")
            key = event_queue.get()
            print(f"Event: {key!r}")
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        stop_input_control(stream=input_stream, original=original)
