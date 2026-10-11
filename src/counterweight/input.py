from __future__ import annotations

import logging
import os
import selectors
import termios
from collections.abc import Callable
from copy import deepcopy
from selectors import DefaultSelector
from threading import Event
from typing import TextIO

from counterweight.events import AnyEvent
from counterweight.keys import vt_inputs

logger = logging.getLogger(__name__)


def read_keys(
    stream: TextIO,
    put_event: Callable[[AnyEvent], None],
    allow: Event,
    waiting: Event,
) -> None:
    selector = DefaultSelector()
    selector.register(stream, selectors.EVENT_READ)

    while True:
        if not allow.is_set():
            waiting.set()
            allow.wait()
            waiting.clear()

        # We're just reading from one file,
        # so we can dispense with the ceremony of actually using the results of the select,
        # other than knowing that it did return something.
        if not selector.select(timeout=1 / 60):
            continue

        bytes = os.read(stream.fileno(), 2**10)

        if not bytes:
            continue

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
