from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING
from typing import TextIO
from typing import assert_never
from xml.etree.ElementTree import indent as indent_svg
from xml.etree.ElementTree import tostring

from counterweight.geometry import Position
from counterweight.graphemes import LINE_BREAKS
from counterweight.graphemes import graphemes
from counterweight.graphemes import visible
from counterweight.paint import Cell
from counterweight.paint import Paint
from counterweight.paint import Run
from counterweight.paint import svg
from counterweight.styles.styles import AnyColor
from counterweight.styles.styles import Color
from counterweight.styles.styles import IndexedColor
from counterweight.styles.styles import ResolvedCellStyle
from counterweight.styles.styles import TerminalDefault

if TYPE_CHECKING:
    pass
# https://www.xfree86.org/current/ctlseqs.html
# https://invisible-island.net/xterm/ctlseqs/ctlseqs.pdf

CURSOR_ON = "\x1b[?25h"
CURSOR_OFF = "\x1b[?25l"

ALT_SCREEN_ON = "\x1b[?1049h"
ALT_SCREEN_OFF = "\x1b[?1049l"

# https://github.com/contour-terminal/vt-extensions/blob/master/synchronized-output.md
# Terminals that don't support mode 2026 ignore it, as they do any private mode they don't recognize.
SYNCHRONIZED_OUTPUT_ON = "\x1b[?2026h"
SYNCHRONIZED_OUTPUT_OFF = "\x1b[?2026l"

# 1003 = any event
# 1006 = sgr format
SET_ANY_EVENT_MOUSE_SGR_FORMAT = "\x1b[?1003h\x1b[?1006h"
UNSET_ANY_EVENT_MOUSE_SGR_FORMAT = "\x1b[?1003l\x1b[?1006l"

# https://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h2-Bracketed-Paste-Mode
BRACKETED_PASTE_ON = "\x1b[?2004h"
BRACKETED_PASTE_OFF = "\x1b[?2004l"

CLEAR_SCREEN = "\x1b[2J"

# xterm's title stack: the app saves the title it found, and restores it when it hands the terminal back.
# Terminals without a title stack ignore these, and keep the last title the app set.
SAVE_TITLE = "\x1b[22;0t"
RESTORE_TITLE = "\x1b[23;0t"

RESET_STYLE = "\x1b[0m"

# https://gist.github.com/egmontkob/eb114294efbcd5adb1944c9f3cb5feda
# A hyperlink is open from its OSC 8 sequence until the next one, across cursor moves and style resets,
# so the one with an empty URI closes it.
HYPERLINK_END = "\x1b]8;;\x1b\\"

BELL = "\x07"

logger = logging.getLogger(__name__)


OUTPUT_CONTROL_START = ALT_SCREEN_ON + CURSOR_OFF + CLEAR_SCREEN + SAVE_TITLE
"""What the app writes when it takes its terminal over, which a recording of it starts with too."""


def start_output_control(stream: TextIO) -> None:
    stream.write(OUTPUT_CONTROL_START)

    stream.flush()


def stop_output_control(stream: TextIO) -> None:
    stream.write(ALT_SCREEN_OFF)
    stream.write(CURSOR_ON)
    stream.write(RESTORE_TITLE)

    stream.flush()


def start_mouse_tracking(stream: TextIO) -> None:
    stream.write(SET_ANY_EVENT_MOUSE_SGR_FORMAT)

    stream.flush()


def stop_mouse_tracking(stream: TextIO) -> None:
    stream.write(UNSET_ANY_EVENT_MOUSE_SGR_FORMAT)

    stream.flush()


def start_bracketed_paste(stream: TextIO) -> None:
    """Have the terminal mark the start and end of pasted text, so it's read as one `Pasted` rather than as keys."""
    stream.write(BRACKETED_PASTE_ON)

    stream.flush()


def stop_bracketed_paste(stream: TextIO) -> None:
    stream.write(BRACKETED_PASTE_OFF)

    stream.flush()


def move_to(position: Position) -> str:
    return f"\x1b[{position.y + 1};{position.x + 1}f"


def sgr_color(color: AnyColor, base: int) -> str:
    """
    The SGR parameters that set the foreground (`base` 30) or background (`base` 40) to `color`.
    The first 16 palette entries take their short forms, which every terminal with colors understands.
    """
    match color:
        case Color(red, green, blue):
            return f"{base + 8};2;{red};{green};{blue}"
        case IndexedColor(index=index) if index < 8:
            return f"{base + index}"
        case IndexedColor(index=index) if index < 16:
            return f"{base + 60 + index - 8}"
        case IndexedColor(index=index):
            return f"{base + 8};5;{index}"
        case TerminalDefault():
            return f"{base + 9}"
        case _ as unreachable:
            assert_never(unreachable)


@lru_cache(maxsize=2**10)
def sgr_from_cell_style(style: ResolvedCellStyle) -> str:
    sgr = f"\x1b[{sgr_color(style.foreground, 30)}m\x1b[{sgr_color(style.background, 40)}m"

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


def hyperlink(link: str | None) -> str:
    """The OSC 8 sequence that makes the cells written after it a hyperlink to `link`, or no hyperlink for `None`."""
    return HYPERLINK_END if link is None else f"\x1b]8;;{link}\x1b\\"


def paint_to_instructions(runs: Iterable[Run]) -> str:
    """
    Terminal instructions that draw `runs`: one cursor move per run,
    and a style change only where a cell's style differs from the cell drawn before it.

    Every run must stay within one row of the screen, since each cell advances the cursor one column:
    a two-cell-wide cluster advances it two, and its continuation cell, whose `grapheme` is empty, writes nothing.
    """
    parts = []
    style = None
    link = None
    for x, y, cells in runs:
        parts.append(move_to(Position(x, y)))
        for cell in cells:
            # The SGR sequence only turns attributes like bold on, so a change of style resets first.
            # Identity is the fast path; equality keeps the output from depending on styles being interned.
            if cell.style is not style and cell.style != style:
                style = cell.style
                parts.append(RESET_STYLE)
                parts.append(sgr_from_cell_style(style))
                if style.link != link:
                    link = style.link
                    parts.append(hyperlink(link))
            parts.append(cell.grapheme)
    if parts:
        parts.append(RESET_STYLE)
    if link is not None:
        parts.append(HYPERLINK_END)
    return "".join(parts)


def synchronized(instructions: str) -> str:
    """
    Terminal instructions that apply `instructions` as one update,
    so the terminal shows the screen as it was before them until it has applied all of them,
    instead of showing a partly drawn frame.
    """
    return f"{SYNCHRONIZED_OUTPUT_ON}{instructions}{SYNCHRONIZED_OUTPUT_OFF}"


def title_instructions(title: str | None) -> str:
    """
    Terminal instructions that set the window title to `title`,
    with its line breaks as spaces and its other control characters as the symbols `visible` draws for them,
    since a control character in the title, like an escape or a bell, would end it early
    and run the rest as instructions.

    For `None`, they restore the title the app saved when it took over the terminal, and save it again,
    so the title stack still holds it for when the app hands the terminal back.
    """
    if title is None:
        return RESTORE_TITLE + SAVE_TITLE

    shown = "".join(" " if grapheme in LINE_BREAKS else visible(grapheme) for grapheme in graphemes(title))
    return f"\x1b]2;{shown}\x1b\\"


def paint_to_str(paint: Paint, *, ansi: bool = True) -> str:
    """Render a Paint as a 2D character grid.

    Parameters:
        ansi: If `True`, include ANSI color/style escape codes in the output.
            If `False`, produce a plain character grid.
    """
    if ansi:
        return "\n".join(ansi_row(row) for row in paint.rows())
    return "\n".join("".join(cell.grapheme for cell in row) for row in paint.rows())


def ansi_row(row: Iterable[Cell]) -> str:
    """
    One row of `paint_to_str`'s ANSI output: each cell's style around its grapheme,
    and one hyperlink for each run of cells that link to the same URI, closed by the end of the row.
    """
    parts = []
    link = None
    for cell in row:
        if cell.style.link != link:
            link = cell.style.link
            parts.append(hyperlink(link))
        parts.append(f"{sgr_from_cell_style(cell.style)}{cell.grapheme}{RESET_STYLE}")
    if link is not None:
        parts.append(HYPERLINK_END)
    return "".join(parts)


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
