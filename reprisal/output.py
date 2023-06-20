from typing import TextIO

from structlog import get_logger

from reprisal.compositor import Position

CURSOR_ON = "\x1b[?25h"
ALT_SCREEN_OFF = "\x1b[?1049l"
CLEAR_SCREEN = "\x1b[2J"
CURSOR_OFF = "\x1b[?25l"
ALT_SCREEN_ON = "\x1b[?1049h"

logger = get_logger()


def start_output_control(stream: TextIO) -> None:
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
        stream.write(f"\x1b[{pos.y+1};{pos.x+1}f{char}")

    stream.flush()

    logger.debug("Applied paint", cells=len(paint))
