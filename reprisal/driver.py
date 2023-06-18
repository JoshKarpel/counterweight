import sys
import termios
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from io import UnsupportedOperation
from queue import Queue
from typing import Any, TextIO

from reprisal.vtparser import CSI_LOOKUP, ESC_LOOKUP, EXECUTE_LOOKUP, UNESCAPED, Action, Keys

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


def queue_keys(action, intermediate_chars, params, char, queue: Queue[tuple[Keys, ...]]):
    print(f"{intermediate_chars=} {params=} {action=} {char=} {chr(char)=} {hex(char)=}")
    match action, intermediate_chars, params, char:
        case Action.CSI_DISPATCH, _, params, char:
            keys = CSI_LOOKUP[(params, char)]
        case Action.ESC_DISPATCH, intermediate_chars, _, char:
            keys = ESC_LOOKUP[(intermediate_chars, char)]
        case Action.PRINT, _, _, char:
            keys = UNESCAPED.get(char, chr(char))
        case Action.EXECUTE, _, _, char:
            keys = EXECUTE_LOOKUP[char]
        case _:
            print("unrecognized")
            keys = None

    if keys:
        queue.put(keys)
