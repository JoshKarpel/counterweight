from __future__ import annotations

import os
import selectors
import termios
from collections.abc import Callable
from copy import deepcopy
from selectors import DefaultSelector
from time import perf_counter_ns
from typing import TextIO

from structlog import get_logger

from counterweight.events import AnyEvent
from counterweight.keys import vt_inputs

logger = get_logger()


def read_keys(stream: TextIO, put_event: Callable[[AnyEvent], None]) -> None:
    """
    Based on https://github.com/Textualize/textual/blob/bb9cc6281aa717054c8133ce4a2eac5ad082c574/src/textual/drivers/linux_driver.py#L236
    """
    selector = DefaultSelector()
    selector.register(stream, selectors.EVENT_READ)

    while True:
        selector.select()
        # We're just reading from one file,
        # so we can dispense with the ceremony of actually using the results of the select.

        start_parsing = perf_counter_ns()
        bytes = os.read(stream.fileno(), 1_000)
        try:
            inputs = vt_inputs.parse(bytes)

            for i in inputs:
                put_event(i)

            logger.debug(
                "Parsed user input",
                inputs=inputs,
                bytes=bytes,
                elapsed_ns=f"{perf_counter_ns() - start_parsing:_}",
            )
        except Exception as e:
            logger.error(
                "Failed to parse input",
                error=repr(e),
                bytes=bytes,
                elapsed_ns=f"{perf_counter_ns() - start_parsing:_}",
            )


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
