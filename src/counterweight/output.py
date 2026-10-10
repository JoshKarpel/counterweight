from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TextIO
from xml.etree.ElementTree import indent as indent_svg
from xml.etree.ElementTree import tostring

from structlog import get_logger

from counterweight.geometry import Position
from counterweight.paint import Paint, svg
from counterweight.styles.styles import CellStyle

if TYPE_CHECKING:
    pass
# https://www.xfree86.org/current/ctlseqs.html
# https://invisible-island.net/xterm/ctlseqs/ctlseqs.pdf

CURSOR_ON = "\x1b[?25h"
CURSOR_OFF = "\x1b[?25l"

ALT_SCREEN_ON = "\x1b[?1049h"
ALT_SCREEN_OFF = "\x1b[?1049l"

# 1003 = any event
# 1006 = sgr format
SET_ANY_EVENT_MOUSE_SGR_FORMAT = "\x1b[?1003h\x1b[?1006h"
UNSET_ANY_EVENT_MOUSE_SGR_FORMAT = "\x1b[?1003l\x1b[?1006l"

CLEAR_SCREEN = "\x1b[2J"

BELL = "\x07"

logger = get_logger()


def start_output_control(stream: TextIO) -> None:  # pragma: untestable
    stream.write(ALT_SCREEN_ON)
    stream.write(CURSOR_OFF)
    stream.write(CLEAR_SCREEN)

    stream.flush()


def stop_output_control(stream: TextIO) -> None:  # pragma: untestable
    stream.write(ALT_SCREEN_OFF)
    stream.write(CURSOR_ON)

    stream.flush()


def start_mouse_tracking(stream: TextIO) -> None:  # pragma: untestable
    stream.write(SET_ANY_EVENT_MOUSE_SGR_FORMAT)

    stream.flush()


def stop_mouse_tracking(stream: TextIO) -> None:  # pragma: untestable
    stream.write(UNSET_ANY_EVENT_MOUSE_SGR_FORMAT)

    stream.flush()


def move_to(position: Position) -> str:
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
    return "".join(f"{move_to(pos)}{sgr_from_cell_style(cell.style)}{cell.char}\x1b[0m" for pos, cell in paint.items())


def paint_to_str(paint: Paint, *, ansi: bool = True) -> str:
    """Render a Paint as a 2D character grid (spaces for empty cells).

    Parameters:
        ansi: If `True`, include ANSI color/style escape codes in the output.
            If `False`, produce a plain character grid.
    """
    if not paint:
        return ""
    min_x = min(p.x for p in paint)
    max_x = max(p.x for p in paint)
    min_y = min(p.y for p in paint)
    max_y = max(p.y for p in paint)
    rows = []
    for y in range(min_y, max_y + 1):
        row = ""
        for x in range(min_x, max_x + 1):
            cell = paint.get(Position(x, y))
            if cell:
                row += f"{sgr_from_cell_style(cell.style)}{cell.char}\x1b[0m" if ansi else cell.char
            else:
                row += " "
        rows.append(row)
    return "\n".join(rows)


@dataclass(frozen=True, slots=True)
class Frame:
    """
    One rendered frame of the UI, as captured by a [`Screenshot`][counterweight.controls.Screenshot].

    Encode it with [`svg`][counterweight.output.Frame.svg] or [`text`][counterweight.output.Frame.text].
    """

    paint: Paint

    def svg(self) -> str:
        """The frame as an SVG image, indented one space per level so that it diffs line by line."""
        root = svg(self.paint)
        indent_svg(root, space=" ")
        return tostring(root, encoding="unicode")

    def text(self, ansi: bool = True) -> str:
        """
        The frame as a grid of characters, one line per terminal row, with spaces for empty cells.

        Parameters:
            ansi: If `True`, include ANSI escape codes for colors and styles,
                which show when the text is printed to a terminal.
                If `False`, produce plain characters, useful for layout debugging and tests.
        """
        return paint_to_str(self.paint, ansi=ansi)
