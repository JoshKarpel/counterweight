import sys
import termios
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from io import UnsupportedOperation
from queue import Queue
from typing import Any, TextIO

from structlog import get_logger

from reprisal.input import CSI_LOOKUP, ESC_LOOKUP, EXECUTE_LOOKUP, PRINT, Action
from reprisal.types import KeyQueueItem

logger = get_logger()

LFLAG = 3
CC = 6

try:
    ORIGINAL_TCGETATTR: list[Any] | None = termios.tcgetattr(sys.stdin)
except (UnsupportedOperation, termios.error):
    ORIGINAL_TCGETATTR = None


def start_no_echo(stream: TextIO) -> None:
    if ORIGINAL_TCGETATTR is None:
        return

    mode = deepcopy(ORIGINAL_TCGETATTR)

    mode[LFLAG] = mode[LFLAG] & ~(termios.ECHO | termios.ICANON)
    mode[CC][termios.VMIN] = 1
    mode[CC][termios.VTIME] = 0

    termios.tcsetattr(stream.fileno(), termios.TCSADRAIN, mode)


def reset_tty(stream: TextIO) -> None:
    if ORIGINAL_TCGETATTR is None:
        return

    termios.tcsetattr(stream.fileno(), termios.TCSADRAIN, ORIGINAL_TCGETATTR)


@contextmanager
def no_echo() -> Iterator[None]:
    try:
        start_no_echo(sys.stdin)
        yield
    finally:
        reset_tty(sys.stdin)


def queue_keys(
    action: Action,
    intermediate_chars: tuple[int, ...],
    params: tuple[int, ...],
    char: int,
    queue: Queue[KeyQueueItem],
) -> None:
    logger.debug(f"{intermediate_chars=} {params=} {action=} {char=} {chr(char)=} {hex(char)=}")
    keys: KeyQueueItem | None
    match action, intermediate_chars, params, char:
        case Action.CSI_DISPATCH, _, params, char:
            keys = CSI_LOOKUP.get((params, char), None)
        case Action.ESC_DISPATCH, intermediate_chars, _, char:
            keys = ESC_LOOKUP.get((intermediate_chars, char), None)
        case Action.PRINT, _, _, char:
            # some PRINT characters are just plain ascii and should get passed through
            keys = PRINT.get(char, chr(char))
        case Action.EXECUTE, _, _, char:
            keys = EXECUTE_LOOKUP[char]
        case _:
            keys = None

    if keys:
        queue.put(keys)
    else:
        logger.debug("unrecognized")
