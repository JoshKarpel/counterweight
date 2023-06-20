from typing import TextIO

from structlog import get_logger

from reprisal.compositor import Position

UNSET_ANY_EVENT_MOUSE = "\x1b[?1003l"

UNSET_VT200_MOUSE = "\x1b[?1000l"

SET_ANY_EVENT_MOUSE = "\x1b[?1003h"

SET_VT200_MOUSE = "\x1b[?1000h"

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

    stream.write(SET_VT200_MOUSE)
    stream.write(SET_ANY_EVENT_MOUSE)

    stream.flush()


def stop_output_control(stream: TextIO) -> None:
    stream.write(ALT_SCREEN_OFF)
    stream.write(CURSOR_ON)

    stream.write(UNSET_VT200_MOUSE)
    stream.write(UNSET_ANY_EVENT_MOUSE)

    stream.flush()


def apply_paint(stream: TextIO, paint: dict[Position, str]) -> None:
    for pos, char in paint.items():
        stream.write(f"\x1b[{pos.y+1};{pos.x+1}f{char}")

    stream.flush()

    logger.debug("Applied paint", cells=len(paint))
