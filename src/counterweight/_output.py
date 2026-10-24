from __future__ import annotations

import logging
from base64 import b64encode
from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal
from typing import TextIO
from typing import assert_never
from xml.etree.ElementTree import indent as indent_svg
from xml.etree.ElementTree import tostring

from counterweight._graphemes import LINE_BREAKS
from counterweight._graphemes import graphemes
from counterweight._graphemes import visible
from counterweight._paint import BLANK
from counterweight._paint import Cell
from counterweight._paint import Paint
from counterweight._paint import Run
from counterweight._paint import svg
from counterweight._viewports import FullScreen
from counterweight._viewports import Inline
from counterweight._viewports import Viewport
from counterweight.geometry import Position
from counterweight.styles._styles import AnyColor
from counterweight.styles._styles import Color
from counterweight.styles._styles import IndexedColor
from counterweight.styles._styles import ResolvedCellStyle
from counterweight.styles._styles import TerminalDefault

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

# From the cursor to the end of the screen, after a carriage return, which moves it to the start of its row.
ERASE_DOWN = "\r\x1b[J"

# Device status report 6: the terminal replies with where the cursor is, `CSI row ; column R`.
REQUEST_CURSOR_POSITION = "\x1b[6n"

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
"""What a full-screen app writes when it takes its terminal over, which a recording of it starts with too."""

INLINE_OUTPUT_CONTROL_START = CURSOR_OFF + SAVE_TITLE
"""What an inline app writes when it takes its terminal over, leaving the main screen showing."""


def output_control_start(viewport: Viewport) -> str:
    """What an app drawing in `viewport` writes when it takes its terminal over, which a recording of it starts with too."""
    match viewport:
        case FullScreen():
            return OUTPUT_CONTROL_START
        case Inline():
            return INLINE_OUTPUT_CONTROL_START
        case _ as unreachable:
            assert_never(unreachable)


def output_control_stop(viewport: Viewport) -> str:
    """What an app drawing in `viewport` writes when it hands its terminal back."""
    match viewport:
        case FullScreen():
            return ALT_SCREEN_OFF + CURSOR_ON + RESTORE_TITLE
        case Inline():
            return CURSOR_ON + RESTORE_TITLE
        case _ as unreachable:
            assert_never(unreachable)


def start_output_control(stream: TextIO, viewport: Viewport) -> None:
    stream.write(output_control_start(viewport))

    stream.flush()


def stop_output_control(stream: TextIO, viewport: Viewport) -> None:
    stream.write(output_control_stop(viewport))

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


def rows_down(rows: int) -> str:
    """Moves the cursor down `rows` rows, without scrolling: nothing for 0, since `CSI 0 B` moves one row, as `CSI 1 B` does."""
    return f"\x1b[{rows}B" if rows else ""


def rows_up(rows: int) -> str:
    """Moves the cursor up `rows` rows, without scrolling: nothing for 0, since `CSI 0 A` moves one row, as `CSI 1 A` does."""
    return f"\x1b[{rows}A" if rows else ""


def to_column(x: int) -> str:
    """Moves the cursor to column `x` of its row, counting from 0."""
    return f"\x1b[{x + 1}G"


def reserve_rows(height: int) -> str:
    """
    From the region's top-left, makes sure the `height` rows from there are on the screen,
    scrolling the terminal up if the region reaches the bottom, and comes back to the region's top-left.
    Line feeds scroll at the bottom of the screen where cursor moves stop, and moving back up doesn't scroll.
    """
    return "\n" * (height - 1) + rows_up(height - 1) if height > 1 else ""


def region_change(previous: int | None, height: int) -> str:
    """
    From the region's top-left, what changes an inline region `previous` rows tall to one `height` rows tall,
    erasing whatever the screen shows from the region's top down first if `previous` is `None`, as for the first frame,
    and leaving the cursor at the region's top-left.

    Every row below the region is blank, because a region that shrinks erases the rows it leaves,
    so a region that grows only has to make room for its new rows.
    A terminal that rewraps the region on a resize keeps the cursor at the start of its first row,
    so erasing down from there erases the region however many rows the rewrap made of it.
    """
    if previous is None:
        return ERASE_DOWN + reserve_rows(height)
    if height > previous:
        return reserve_rows(height)
    if height < previous:
        return rows_down(height) + "\x1b[J" + rows_up(height)
    return ""


def leave_region(height: int, keep: bool) -> str:
    """
    From the region's top-left, what an inline app `height` rows tall writes as it stops:
    the cursor to the start of the row below the region if it's `keep`ing the region, scrolling if it has to,
    and otherwise the region erased, leaving the cursor where the region started.
    """
    return "\n" * height + "\r" if keep else ERASE_DOWN


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
def sgr_from_cell_style(style: ResolvedCellStyle[AnyColor]) -> str:
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


def style_change(previous: ResolvedCellStyle[AnyColor] | None, style: ResolvedCellStyle[AnyColor]) -> str:
    """
    The SGR sequences that change the style of the cells written next from `previous` to `style`:
    only the colors that changed, if that's all that did, as between the cells of a gradient,
    and otherwise a reset, since an SGR sequence only turns attributes like bold on, and the whole of `style`.
    """
    if (
        previous is None
        or previous.bold != style.bold
        or previous.dim != style.dim
        or previous.italic != style.italic
        or previous.underline != style.underline
        or previous.strikethrough != style.strikethrough
    ):
        return RESET_STYLE + sgr_from_cell_style(style)
    foreground = "" if previous.foreground == style.foreground else f"\x1b[{sgr_color(style.foreground, 30)}m"
    background = "" if previous.background == style.background else f"\x1b[{sgr_color(style.background, 40)}m"
    return foreground + background


def hyperlink(link: str | None) -> str:
    """The OSC 8 sequence that makes the cells written after it a hyperlink to `link`, or no hyperlink for `None`."""
    return HYPERLINK_END if link is None else f"\x1b]8;;{link}\x1b\\"


type CursorMoves = Literal["absolute", "relative"]
"""
How frame instructions move the cursor: to a row and column of the screen, as a full-screen app does,
or by rows from where it starts, the top-left of an inline region, whose row on the screen the app doesn't know.
"""


def paint_to_instructions(runs: Iterable[Run], moves: CursorMoves = "absolute") -> str:
    """
    Terminal instructions that draw `runs`: one cursor move per run,
    and a style change only where a cell's style differs from the cell drawn before it,
    which is only its colors where nothing else differs (see `style_change`).

    With `relative` moves, the cursor starts at the top-left of the cells' rows,
    and the instructions move it back there after drawing.

    Every run must stay within one row of the screen, since each cell advances the cursor one column:
    a two-cell-wide cluster advances it two, and its continuation cell, whose `grapheme` is empty, writes nothing.
    """
    parts = []
    style: ResolvedCellStyle[AnyColor] | None = None
    link = None
    row = 0
    for x, y, cells in runs:
        if moves == "absolute":
            parts.append(move_to(Position(x, y)))
        else:
            parts.append((rows_down(y - row) if y > row else rows_up(row - y)) + to_column(x))
            row = y
        style, link = draw_cells(parts, cells, style, link)
    if parts:
        parts.append(RESET_STYLE)
    if link is not None:
        parts.append(HYPERLINK_END)
    if parts and moves == "relative":
        parts.append(rows_up(row) + "\r")
    return "".join(parts)


def draw_cells(
    parts: list[str], cells: Iterable[Cell], style: ResolvedCellStyle[AnyColor] | None, link: str | None
) -> tuple[ResolvedCellStyle[AnyColor] | None, str | None]:
    """
    Appends to `parts` the instructions that draw `cells` from the cursor rightward,
    when the cells drawn before them were drawn in `style` and linked to `link`,
    and returns the style and link the last cell leaves set.
    """
    for cell in cells:
        # Identity is the fast path; equality keeps the output from depending on styles being interned.
        if cell.style is not style and cell.style != style:
            parts.append(style_change(style, cell.style))
            style = cell.style
            if style.link != link:
                link = style.link
                parts.append(hyperlink(link))
        parts.append(cell.grapheme)
    return style, link


def printed_cells(row: Sequence[Cell]) -> Sequence[Cell]:
    """
    `row` up to its last cell that isn't blank, as it's printed,
    so a terminal that's narrowed doesn't rewrap the padding onto rows of its own.
    """
    end = len(row)
    while end and row[end - 1] == BLANK:
        end -= 1
    return row[:end]


def printed_rows(paint: Paint, line_end: str) -> str:
    """
    Instructions that print `paint`'s rows from the start of the cursor's row, each ended by `line_end`,
    with the style reset before it, so a line end that scrolls doesn't fill the new row with a background color.
    """
    parts: list[str] = []
    for row in paint.rows():
        cells = printed_cells(row)
        if cells:
            _, link = draw_cells(parts, cells, None, None)
            parts.append(RESET_STYLE)
            if link is not None:
                parts.append(HYPERLINK_END)
        parts.append(line_end)
    return "".join(parts)


def plain_rows(paint: Paint) -> str:
    """`paint`'s rows as plain text, each ended by a newline, for a stream that isn't a terminal."""
    return "".join("".join(cell.grapheme for cell in printed_cells(row)) + "\n" for row in paint.rows())


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


def clipboard_instructions(text: str) -> str:
    """
    Terminal instructions that set the system clipboard to `text`:
    OSC 52 with the `c` (clipboard) target and the text's UTF-8 in base64,
    which can't hold a control character that would end the sequence early.
    """
    return f"\x1b]52;c;{b64encode(text.encode()).decode()}\x1b\\"


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

    Encode it with [`svg`][counterweight.paint.Frame.svg] or [`text`][counterweight.paint.Frame.text].
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
