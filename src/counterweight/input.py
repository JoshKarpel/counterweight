from __future__ import annotations

import logging
import os
import selectors
import termios
from collections.abc import Callable
from copy import deepcopy
from datetime import timedelta
from selectors import DefaultSelector
from threading import Event
from typing import TextIO

from counterweight.events import AnyEvent
from counterweight.input_parsing import parse_input

logger = logging.getLogger(__name__)

# How long a lone ESC (or the start of an escape sequence) at the end of a read waits for the rest of a sequence
# before it is the Escape key.
ESCAPE_TIMEOUT = timedelta(milliseconds=50)


def read_keys(
    stream: TextIO,
    put_event: Callable[[AnyEvent], None],
    allow: Event,
    waiting: Event,
) -> None:
    selector = DefaultSelector()
    selector.register(stream, selectors.EVENT_READ)

    pending = b""

    while True:
        if not allow.is_set():
            waiting.set()
            allow.wait()
            waiting.clear()

        # We're just reading from one file,
        # so we can dispense with the ceremony of actually using the results of the select,
        # other than knowing that it did return something.
        if selector.select(timeout=ESCAPE_TIMEOUT.total_seconds() if pending else 1 / 60):
            buffer, is_final = pending + os.read(stream.fileno(), 2**10), False
        elif pending:
            # Nothing followed the held-over bytes in time, so they aren't the start of anything longer.
            buffer, is_final = pending, True
        else:
            continue

        parsed = parse_input(buffer, is_final=is_final)
        pending = parsed.remainder

        for event in parsed.events:
            put_event(event)

        logger.debug(
            "Parsed user input",
            extra={"inputs": parsed.events, "skipped": parsed.skipped, "pending": pending, "bytes": buffer},
        )


LFLAG = 3
CC = 6

TCGetAttr = list[int | list[int | bytes]]


def start_input_control(stream: TextIO) -> TCGetAttr:  # pragma: untestable
    original = termios.tcgetattr(stream)

    modified = deepcopy(original)

    modified[LFLAG] = original[LFLAG] & ~(termios.ECHO | termios.ICANON)
    modified[CC][termios.VMIN] = 1
    modified[CC][termios.VTIME] = 0

    termios.tcsetattr(stream.fileno(), termios.TCSADRAIN, modified)

    return original


def stop_input_control(stream: TextIO, original: TCGetAttr) -> None:  # pragma: untestable
    termios.tcsetattr(stream.fileno(), termios.TCSADRAIN, original)
