import termios
from copy import deepcopy
from queue import Queue
from typing import TextIO

from structlog import get_logger

from reprisal.compositor import Position
from reprisal.input import CSI_LOOKUP, ESC_LOOKUP, EXECUTE_LOOKUP, PRINT, Action
from reprisal.types import KeyQueueItem

CURSOR_ON = "\x1b[?25h"
ALT_SCREEN_OFF = "\x1b[?1049l"
CLEAR_SCREEN = "\x1b[2J"
CURSOR_OFF = "\x1b[?25l"
ALT_SCREEN_ON = "\x1b[?1049h"

logger = get_logger()

LFLAG = 3
CC = 6


def start_output_control(stream: TextIO) -> list[int | list[int | bytes]]:
    stream.write(ALT_SCREEN_ON)
    stream.write(CURSOR_OFF)
    stream.write(CLEAR_SCREEN)

    stream.flush()


def stop_output_control(stream: TextIO) -> None:
    stream.write(ALT_SCREEN_OFF)
    stream.write(CURSOR_ON)

    stream.flush()


def apply_paint(stream: TextIO, paint: dict[Position, str]) -> None:
    for pos, char in paint.items():
        # moving is silly right now but will make more sense
        # once we paint diffs instead of full screens
        stream.write(f"\x1b[{pos.y+1};{pos.x+1}f{char or ' '}")

    stream.flush()

    logger.debug("Applied paint", cells=len(paint))


TCGetAttr = list[int | list[int | bytes]]


def start_input_control(stream: TextIO) -> TCGetAttr:
    original = termios.tcgetattr(stream)

    modified = deepcopy(original)

    modified[LFLAG] = original[LFLAG] & ~(termios.ECHO | termios.ICANON)  # type: ignore[operator]
    modified[CC][termios.VMIN] = 1  # type: ignore[index]
    modified[CC][termios.VTIME] = 0  # type: ignore[index]

    termios.tcsetattr(stream.fileno(), termios.TCSADRAIN, modified)

    return original


def stop_input_control(stream: TextIO, original: TCGetAttr) -> None:
    termios.tcsetattr(stream.fileno(), termios.TCSADRAIN, original)


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
