import sys
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


class Driver:
    def __init__(self, input_stream: TextIO = sys.stdin, output_stream: TextIO = sys.stdout):
        self.input_stream = input_stream
        self.output_stream = output_stream
        self.original_tcgetattr: list[int | list[int | bytes]] | None = None

    def start(self) -> None:
        self.original_tcgetattr = termios.tcgetattr(self.input_stream)
        mode = deepcopy(self.original_tcgetattr)

        mode[LFLAG] = mode[LFLAG] & ~(termios.ECHO | termios.ICANON)  # type: ignore[operator]
        mode[CC][termios.VMIN] = 1  # type: ignore[index]
        mode[CC][termios.VTIME] = 0  # type: ignore[index]

        termios.tcsetattr(self.input_stream.fileno(), termios.TCSADRAIN, mode)

        self.output_stream.write(ALT_SCREEN_ON)  # alt screen on
        self.output_stream.write(CURSOR_OFF)  # cursor off
        self.output_stream.write(CLEAR_SCREEN)  # clear screen, move to 0,0

        self.output_stream.flush()

    def stop(self) -> None:
        self.output_stream.write(ALT_SCREEN_OFF)  # alt screen off
        self.output_stream.write(CURSOR_ON)  # cursor on
        self.output_stream.flush()

        if self.original_tcgetattr is None:
            return

        termios.tcsetattr(self.input_stream.fileno(), termios.TCSADRAIN, self.original_tcgetattr)

    def apply_paint(self, paint: dict[Position, str]) -> None:
        logger.debug("Applying paint", len=len(paint))
        for pos, char in paint.items():
            # moving is silly right now but will make more sense
            # once we paint diffs instead of full screens
            self.output_stream.write(f"\x1b[{pos.y+1};{pos.x+1}f{char or ' '}")

        self.output_stream.flush()


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
