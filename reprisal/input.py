from __future__ import annotations

import os
import selectors
import termios
from copy import deepcopy
from queue import Queue
from selectors import DefaultSelector
from typing import TextIO

from parsy import ParseError
from structlog import get_logger

from reprisal.events import AnyEvent, KeyPressed
from reprisal.keys import vt_keys

logger = get_logger()


def read_keys(queue: Queue[AnyEvent], stream: TextIO) -> None:
    """
    Based on https://github.com/Textualize/textual/blob/bb9cc6281aa717054c8133ce4a2eac5ad082c574/src/textual/drivers/linux_driver.py#L236
    """
    selector = DefaultSelector()
    selector.register(stream, selectors.EVENT_READ)

    while True:
        for _ in selector.select(timeout=0.001):
            buffer = os.read(stream.fileno(), 1024).decode("utf-8")
            logger.debug(f"read {buffer=}")
            try:
                keys = vt_keys.parse(buffer)
                logger.debug("Parsed user input", keys=keys)
                for key in keys:
                    queue.put(KeyPressed(key=key))
            except (ParseError, KeyError) as e:
                logger.error("Failed to parse input", error=str(e), buffer=repr(buffer))


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
