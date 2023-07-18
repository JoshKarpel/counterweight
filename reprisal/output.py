from collections.abc import Iterable
from functools import lru_cache
from typing import TextIO

from structlog import get_logger

from reprisal.layout import Position
from reprisal.paint import CellPaint
from reprisal.styles.styles import CellStyle

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


@lru_cache(maxsize=2**20)
def move_from_position(position: Position) -> str:
    return f"\x1b[{position.y + 1};{position.x + 1}f"


@lru_cache(maxsize=2**20)
def sgr_from_cell_style(style: CellStyle) -> str:
    fg_r, fg_g, fg_b = style.foreground
    bg_r, bg_g, bg_b = style.background

    parts = [
        f"\x1b[38;2;{fg_r};{fg_g};{fg_b}m",  # fg
        f"\x1b[48;2;{bg_r};{bg_g};{bg_b}m",  # bg
    ]

    if style.bold:
        parts.append("\x1b[1m")

    if style.dim:
        parts.append("\x1b[2m")

    if style.italic:
        parts.append("\x1b[3m")

    return "".join(parts)


def paint_to_instructions(paint: Iterable[tuple[Position, CellPaint]]) -> str:
    return "".join(
        f"{move_from_position(pos)}{sgr_from_cell_style(cell.style)}{cell.char}\x1b[0m" for pos, cell in paint
    )
