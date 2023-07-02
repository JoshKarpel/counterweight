from typing import TextIO

from structlog import get_logger

from reprisal.layout import CellPaint, Position

CURSOR_ON = "\x1b[?25h"
CURSOR_OFF = "\x1b[?25l"

ALT_SCREEN_ON = "\x1b[?1049h"
ALT_SCREEN_OFF = "\x1b[?1049l"

UNSET_VT200_MOUSE = "\x1b[?1000l"
SET_VT200_MOUSE = "\x1b[?1000h"

SET_ANY_EVENT_MOUSE = "\x1b[?1003h"
UNSET_ANY_EVENT_MOUSE = "\x1b[?1003l"

CLEAR_SCREEN = "\x1b[2J"

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


def start_mouse_reporting(stream: TextIO) -> None:
    stream.write(SET_VT200_MOUSE)
    stream.write(SET_ANY_EVENT_MOUSE)

    stream.flush()


def stop_mouse_reporting(stream: TextIO) -> None:
    stream.write(UNSET_VT200_MOUSE)
    stream.write(UNSET_ANY_EVENT_MOUSE)

    stream.flush()


def apply_paint(stream: TextIO, paint: dict[Position, CellPaint]) -> None:
    for pos, cell in paint.items():
        fg_r, fg_g, fg_b = cell.style.fg.as_rgb_tuple(alpha=False)
        bg_r, bg_g, bg_b = cell.style.bg.as_rgb_tuple(alpha=False)

        parts = [
            f"\x1b[{pos.y+1};{pos.x+1}f",  # move
            f"\x1b[38;2;{fg_r};{fg_g};{fg_b}m",  # fg
            f"\x1b[48;2;{bg_r};{bg_g};{bg_b}m",  # bg
            cell.char,
            "\x1b[0m",  # reset
        ]

        stream.write("".join(parts))

    stream.flush()

    logger.debug("Applied paint", cells=len(paint))
