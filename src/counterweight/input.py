from __future__ import annotations

import logging
import os
import termios
from asyncio import get_running_loop
from collections.abc import Callable
from copy import deepcopy
from typing import TextIO

from counterweight.events import AnyEvent
from counterweight.keys import vt_inputs

logger = logging.getLogger(__name__)


def start_reading_keys(stream: TextIO, put_event: Callable[[AnyEvent], None]) -> None:
    """
    Read `stream` whenever it has input, on the running event loop, and put each input parsed from it,
    until `stop_reading_keys` (or the end of the input).

    Reading on the event loop rather than a thread makes stopping immediate, since nothing can be partway through
    a read when `stop_reading_keys` returns, and keeps waxy objects off one more thread that could drop them
    in a garbage collection: waxy's types can't be dropped off the main thread.
    """
    get_running_loop().add_reader(stream.fileno(), read_keys, stream, put_event)


def stop_reading_keys(stream: TextIO) -> None:
    """Stop reading `stream`, leaving any input that arrives afterward for whatever reads it next."""
    get_running_loop().remove_reader(stream.fileno())


def read_keys(stream: TextIO, put_event: Callable[[AnyEvent], None]) -> None:
    """
    Read the input waiting on `stream` and put each input parsed from it.
    At the end of the input, stop reading `stream`, since it stays readable and the event loop would call this forever.
    """
    bytes = os.read(stream.fileno(), 2**10)

    if not bytes:
        stop_reading_keys(stream)
        return

    try:
        inputs = vt_inputs.parse(bytes)

        for i in inputs:
            put_event(i)

        logger.debug("Parsed user input", extra={"inputs": inputs, "bytes": bytes})
    except Exception as e:
        logger.error("Failed to parse input", extra={"error": repr(e), "bytes": bytes})


LFLAG = 3
CC = 6

TCGetAttr = list[int | list[int | bytes]]


def start_input_control(stream: TextIO) -> TCGetAttr:
    original = termios.tcgetattr(stream)

    modified = deepcopy(original)

    modified[LFLAG] = original[LFLAG] & ~(termios.ECHO | termios.ICANON)
    modified[CC][termios.VMIN] = 1
    modified[CC][termios.VTIME] = 0

    termios.tcsetattr(stream.fileno(), termios.TCSADRAIN, modified)

    return original


def stop_input_control(stream: TextIO, original: TCGetAttr) -> None:
    termios.tcsetattr(stream.fileno(), termios.TCSADRAIN, original)
