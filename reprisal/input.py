from __future__ import annotations

import os
import selectors
import termios
from asyncio import AbstractEventLoop
from copy import deepcopy
from queue import Queue
from selectors import DefaultSelector
from time import perf_counter
from typing import TextIO

from parsy import ParseError
from structlog import get_logger

from reprisal.events import AnyEvent, KeyPressed, MouseMoved
from reprisal.keys import vt_keys

logger = get_logger()


def read_keys(queue: Queue[AnyEvent], stream: TextIO, loop: AbstractEventLoop) -> None:
    """
    Based on https://github.com/Textualize/textual/blob/bb9cc6281aa717054c8133ce4a2eac5ad082c574/src/textual/drivers/linux_driver.py#L236
    """
    selector = DefaultSelector()
    selector.register(stream, selectors.EVENT_READ)

    while True:
        selector.select()
        # We're just reading from one file,
        # so we can dispense with the ceremony of actually using the results of the select.

        start_parsing = perf_counter()
        # Read only up to 6 bytes at a time to make checking for multiple mouse events easier
        # TODO: would be better to not do bytes[4:] below...
        b = os.read(stream.fileno(), 6)
        bytes = list(b)

        if bytes[:4] == [27, 91, 77, 67]:
            x, y = bytes[4:]
            # there appear to be other states where the mouse might be up or down... hard to check on laptop
            loop.call_soon_threadsafe(queue.put_nowait, MouseMoved(x=x - 33, y=y - 33))
            logger.debug("Parsed mount event", bytes=bytes)
        else:
            buffer = b.decode("utf-8")
            try:
                keys = vt_keys.parse(buffer)
                for key in keys:
                    loop.call_soon_threadsafe(queue.put_nowait, KeyPressed(key=key))
                logger.debug(
                    "Parsed user input",
                    keys=keys,
                    buffer=repr(buffer),
                    bytes=bytes,
                    len_buffer=len(buffer),
                    elapsed_ms=(perf_counter() - start_parsing) * 1000,
                )
            except (ParseError, KeyError) as e:
                logger.error(
                    "Failed to parse input",
                    error=str(e),
                    buffer=repr(buffer),
                    len_buffer=len(buffer),
                    elapsed_ms=(perf_counter() - start_parsing) * 1000,
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
