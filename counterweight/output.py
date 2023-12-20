from typing import TextIO

from structlog import get_logger

from counterweight.geometry import Position
from counterweight.paint import Paint
from counterweight.styles.styles import CellStyle

CURSOR_ON = "\x1b[?25h"
CURSOR_OFF = "\x1b[?25l"

ALT_SCREEN_ON = "\x1b[?1049h"
ALT_SCREEN_OFF = "\x1b[?1049l"

# https://www.xfree86.org/current/ctlseqs.html
SET_ANY_EVENT_MOUSE = "\x1b[?1003h"
UNSET_ANY_EVENT_MOUSE = "\x1b[?1003l"

CLEAR_SCREEN = "\x1b[2J"

BELL = "\x07"

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
    stream.write(SET_ANY_EVENT_MOUSE)

    stream.flush()


def stop_mouse_reporting(stream: TextIO) -> None:
    stream.write(UNSET_ANY_EVENT_MOUSE)

    stream.flush()


def move_from_position(position: Position) -> str:
    return f"\x1b[{position.y + 1};{position.x + 1}f"


def sgr_from_cell_style(style: CellStyle) -> str:
    fg_r, fg_g, fg_b = style.foreground
    bg_r, bg_g, bg_b = style.background

    sgr = f"\x1b[38;2;{fg_r};{fg_g};{fg_b}m\x1b[48;2;{bg_r};{bg_g};{bg_b}m"

    if style.bold:
        sgr += "\x1b[1m"

    if style.dim:
        sgr += "\x1b[2m"

    if style.italic:
        sgr += "\x1b[3m"

    if style.underline:
        sgr += "\x1b[4m"

    if style.strikethrough:
        sgr += "\x1b[9m"

    return sgr


def paint_to_instructions(paint: Paint) -> str:
    return "".join(
        f"{move_from_position(pos)}{sgr_from_cell_style(cell.style)}{cell.char}\x1b[0m" for pos, cell in paint.items()
    )
