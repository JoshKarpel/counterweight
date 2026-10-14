"""
A terminal emulator, which turns the bytes a program writes to its terminal into what that terminal shows,
and the immutable [`Screen`][counterweight.emulator.Screen] values it shows them as.

The emulator is [libghostty-vt](https://ghostty.org), through [pyghostty](https://github.com/AnswerDotAI/pyghostty)'s
cffi bindings, which the `emulator` extra installs (`counterweight[emulator]`).
Nothing outside this module touches it, so everything else sees only `Screen` and `Modes` values.
An `Emulator` is a place: the bytes fed to it change it. `snapshot` turns what it shows into a `Screen`.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from types import TracebackType
from typing import Literal
from typing import Self

from pyghostty import Terminal
from pyghostty._ffi import check
from pyghostty._ffi import ffi
from pyghostty._ffi import lib
from pyghostty.core import init_sized

from counterweight.elements import Rows
from counterweight.elements import StyledGrapheme
from counterweight.geometry import Position
from counterweight.graphemes import grapheme_width
from counterweight.graphemes import graphemes
from counterweight.styles.styles import CELL_STYLE_DEFAULTS
from counterweight.styles.styles import UNSET
from counterweight.styles.styles import CellStyle
from counterweight.styles.styles import Color

type MouseTracking = Literal["none", "x10", "normal", "button", "any"]
"""Which mouse events a program asked its terminal to report, from fewest to most."""


@dataclass(frozen=True, slots=True)
class Modes:
    """The modes a program has set that change how its input must be encoded."""

    application_cursor_keys: bool = False
    """DECCKM (`?1`): cursor keys send `ESC O A` rather than `ESC [ A`."""

    bracketed_paste: bool = False
    """`?2004`: pastes are wrapped in `ESC [ 200 ~` and `ESC [ 201 ~`."""

    mouse_tracking: MouseTracking = "none"
    """Which mouse events the program asked for (`?9`, `?1000`, `?1002`, `?1003`), if any."""

    sgr_mouse: bool = False
    """`?1006`: mouse events are reported in SGR format."""

    focus_events: bool = False
    """`?1004`: the program wants `ESC [ I` and `ESC [ O` when it gains and loses focus."""

    alternate_screen: bool = False
    """`?1049` (or `?47`, `?1047`): the program is drawing on the alternate screen, as full-screen programs do."""


@dataclass(frozen=True, slots=True, eq=False)
class Screen:
    """
    What a program's terminal shows at one moment: its rows of cells, its cursor, its modes and its title.

    Compared by identity: a snapshot of a terminal that changed is a new `Screen`, and a snapshot of one that didn't
    is the same `Screen` as before, so a canvas drawing it draws again only when the program's output changed it.
    A row the program didn't change is the same tuple as in the previous snapshot.
    """

    columns: int
    rows: int

    lines: Rows
    """
    One row of cells for each of the terminal's rows, each taking exactly `columns` cells.

    A cell in the program's default colors leaves them unset, so they follow the style of the canvas showing it.
    Where the emulator and [`grapheme_width`][counterweight.graphemes.grapheme_width] disagree on how wide
    a grapheme cluster is, the row keeps the emulator's columns, which the program laid its line out by:
    a cluster narrower here is followed by spaces, and one wider here, or with no width, is drawn as spaces.
    """

    cursor: Position | None
    """Where the cursor is, or `None` if the program hid it."""

    modes: Modes
    title: str

    foreground: Color
    background: Color
    """
    The colors that the program's default colors stand for wherever a cell has to name them:
    where the program swapped a cell's colors (inverse video, and the drawn cursor)
    or made its text the color of its background (invisible text).
    """


class Emulator:
    """
    A terminal emulator `columns` wide and `rows` tall, fed what a program writes.

    `on_reply` receives the bytes the emulator answers the program's queries with
    (cursor position reports, device attributes), which belong on the program's input, as a terminal would send them.
    `foreground` and `background` are the colors the program's default colors stand for wherever a cell has to name them
    (see [`Screen.background`][counterweight.emulator.Screen.background]), until the program changes them.

    Use it as a context manager, or call `close`, to free the emulator's memory as soon as it's done with.
    """

    def __init__(
        self,
        columns: int,
        rows: int,
        on_reply: Callable[[bytes], None],
        foreground: Color = CELL_STYLE_DEFAULTS.foreground,
        background: Color = CELL_STYLE_DEFAULTS.background,
    ) -> None:
        self.terminal = Terminal(cols=columns, rows=rows, scrollback=0, fg=foreground, bg=background)
        self.terminal.on_reply(on_reply)

        self.state = ffi.new("GhosttyRenderState*")
        check(lib.ghostty_render_state_new(ffi.NULL, self.state), "render_state_new")
        self.row_iterator = ffi.new("GhosttyRenderStateRowIterator*")
        check(lib.ghostty_render_state_row_iterator_new(ffi.NULL, self.row_iterator), "row_iterator_new")
        self.cells = ffi.new("GhosttyRenderStateRowCells*")
        check(lib.ghostty_render_state_row_cells_new(ffi.NULL, self.cells), "row_cells_new")
        self.free = weakref.finalize(
            self,
            free_render_state,
            self.state[0],
            self.row_iterator[0],
            self.cells[0],
        )

        self.cursor = init_sized("GhosttyRenderStateCursor")
        self.colors = init_sized("GhosttyRenderStateColors")
        self.style = init_sized("GhosttyStyle")
        self.rgb = ffi.new("GhosttyColorRgb*")
        self.cells_view = ffi.new("GhosttyCellsView*")
        self.wide = ffi.new("int*")
        self.has_styling = ffi.new("bool*")
        self.content_tag = ffi.new("int*")
        self.codepoint = ffi.new("uint32_t*")
        self.style_id = ffi.new("GhosttyStyleId*")
        self.classify_keys = ffi.new(
            "GhosttyCellData[5]",
            [
                lib.GHOSTTY_CELL_DATA_WIDE,
                lib.GHOSTTY_CELL_DATA_HAS_STYLING,
                lib.GHOSTTY_CELL_DATA_CONTENT_TAG,
                lib.GHOSTTY_CELL_DATA_CODEPOINT,
                lib.GHOSTTY_CELL_DATA_STYLE_ID,
            ],
        )
        self.classify_values = ffi.new(
            "void*[5]",
            [
                ffi.cast("void*", self.wide),
                ffi.cast("void*", self.has_styling),
                ffi.cast("void*", self.content_tag),
                ffi.cast("void*", self.codepoint),
                ffi.cast("void*", self.style_id),
            ],
        )
        self.grapheme_length = ffi.new("uint32_t*")
        self.grapheme_buffer = ffi.new("uint32_t[32]")
        self.is_dirty = ffi.new("bool*")
        self.row_id = ffi.new("GhosttyRenderStateRowId*")
        self.title_out = ffi.new("GhosttyString*")

        # The cells of each cell value with no style, which holds only a codepoint and its width,
        # so each maps to the same cells for good. A styled cell's value holds a style id that means something
        # only within its page, so those are kept only while converting one row.
        self.plain: dict[int, tuple[StyledGrapheme, ...]] = {}
        # Each row's cells by libghostty's row id, kept from one snapshot to the next for rows that aren't dirty,
        # so a program that changes one row has one row converted rather than all of them.
        self.converted: dict[tuple[int, int], tuple[StyledGrapheme, ...]] = {}
        self.last: Screen | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def feed(self, data: bytes) -> None:
        """Feed the emulator bytes the program wrote, raising whatever `on_reply` raised while it ran."""
        self.terminal.feed(data)

    def resize(self, columns: int, rows: int) -> None:
        """Resize the terminal, reflowing what it shows, as resizing a terminal window does."""
        self.terminal.resize(columns, rows)

    def close(self) -> None:
        """Free the emulator's memory. It can't be fed or snapshotted after."""
        self.free()
        self.terminal.close()

    def snapshot(self) -> Screen:
        """What the terminal shows now."""
        state = self.state[0]
        check(lib.ghostty_render_state_update(state, self.terminal._t[0]), "render_state_update")  # noqa: SLF001

        check(lib.ghostty_render_state_get(state, lib.GHOSTTY_RENDER_STATE_DATA_COLORS, self.colors), "colors")
        foreground = rgb_color(self.colors.foreground)
        background = rgb_color(self.colors.background)
        last = self.last
        if last is not None and (foreground, background) != (last.foreground, last.background):
            # Inverse and invisible cells name the default colors, so they change with them.
            self.converted = {}

        check(
            lib.ghostty_render_state_get(state, lib.GHOSTTY_RENDER_STATE_DATA_ROW_ITERATOR, self.row_iterator), "rows"
        )
        rows = self.row_iterator[0]
        previous = self.converted
        converted: dict[tuple[int, int], tuple[StyledGrapheme, ...]] = {}
        lines = []
        while lib.ghostty_render_state_row_iterator_next(rows):
            lib.ghostty_render_state_row_get(rows, lib.GHOSTTY_RENDER_STATE_ROW_DATA_DIRTY, self.is_dirty)
            lib.ghostty_render_state_row_get(rows, lib.GHOSTTY_RENDER_STATE_ROW_DATA_ID, self.row_id)
            key = (self.row_id.bits[0], self.row_id.bits[1])
            line = None if self.is_dirty[0] else previous.get(key)
            if line is None:
                line = self.convert_row(rows, foreground, background)
            converted[key] = line
            lines.append(line)
        check(lib.ghostty_render_state_clean(state), "render_state_clean")
        self.converted = converted

        columns, row_count = self.terminal.size
        screen = Screen(
            columns=columns,
            rows=row_count,
            lines=tuple(lines),
            cursor=self.cursor_position(),
            modes=self.modes(),
            title=self.title(),
            foreground=foreground,
            background=background,
        )
        if last is not None and is_unchanged(last, screen):
            return last
        self.last = screen
        return screen

    def convert_row(self, rows: object, foreground: Color, background: Color) -> tuple[StyledGrapheme, ...]:
        """
        The cells of the row `rows` is at.

        A styled cell's value holds its style's id within the row's page, so within one row,
        a cell value that's a lone codepoint maps to the same cells wherever it recurs,
        and a style id to the same style, which saves reading the style's colors and attributes again.
        """
        view = self.cells_view
        check(lib.ghostty_render_state_row_get(rows, lib.GHOSTTY_RENDER_STATE_ROW_DATA_CELLS_RAW, view), "cells_raw")
        values = memoryview(ffi.buffer(view.ptr, view.len * CELL_SIZE)).cast("Q").tolist()
        # Read the cells one at a time only for those whose values haven't been met, for their styles and graphemes.
        check(lib.ghostty_render_state_row_get(rows, lib.GHOSTTY_RENDER_STATE_ROW_DATA_CELLS, self.cells), "cells")
        cells = self.cells[0]
        get = lib.ghostty_render_state_row_cells_get
        select = lib.ghostty_render_state_row_cells_select
        plain = self.plain
        seen: dict[int, tuple[StyledGrapheme, ...]] = {}
        styles: dict[int, CellStyle] = {}
        row: list[StyledGrapheme] = []
        for x, value in enumerate(values):
            known = plain.get(value)
            if known is None:
                known = seen.get(value)
            if known is not None:
                row.extend(known)
                continue

            lib.ghostty_cell_get_multi(value, 5, self.classify_keys, self.classify_values, ffi.NULL)
            wide = self.wide[0]
            if wide == lib.GHOSTTY_CELL_WIDE_SPACER_TAIL:
                # The wide cell before it drew both its columns.
                (seen if self.has_styling[0] else plain)[value] = ()
                continue
            columns = 2 if wide == lib.GHOSTTY_CELL_WIDE_WIDE else 1
            content = self.content_tag[0]

            if content == lib.GHOSTTY_CELL_CONTENT_CODEPOINT:
                text = chr(self.codepoint[0] or SPACE)
                if not self.has_styling[0]:
                    if len(plain) >= PLAIN_CELLS_KEPT:
                        plain.clear()
                    known = plain[value] = cells_for(text, columns, UNSTYLED)
                else:
                    style_id = self.style_id[0]
                    if (style := styles.get(style_id)) is None:
                        check(select(cells, x), "select")
                        style = styles[style_id] = self.read_style(cells, foreground, background)
                    known = seen[value] = cells_for(text, columns, style)
                row.extend(known)
                continue

            check(select(cells, x), "select")
            if content == lib.GHOSTTY_CELL_CONTENT_CODEPOINT_GRAPHEME:
                get(cells, lib.GHOSTTY_RENDER_STATE_ROW_CELLS_DATA_GRAPHEMES_LEN, self.grapheme_length)
                get(cells, lib.GHOSTTY_RENDER_STATE_ROW_CELLS_DATA_GRAPHEMES_BUF, self.grapheme_buffer)
                text = "".join(map(chr, self.grapheme_buffer[0 : self.grapheme_length[0]]))
                row.extend(cells_for(text, columns, self.read_style(cells, foreground, background)))
                continue

            # A blank cell whose background the program set by erasing, which its value holds rather than a style.
            known = seen[value] = cells_for(" ", columns, self.read_style(cells, foreground, background))
            row.extend(known)
        return tuple(row)

    def read_style(self, cells: object, foreground: Color, background: Color) -> CellStyle:
        """
        The style of the cell `cells` is at, leaving colors that are the program's defaults unset,
        but where it has to name them, as `foreground` and `background`.
        """
        get = lib.ghostty_render_state_row_cells_get
        rgb = self.rgb
        cell_foreground: Color | None = None
        if get(cells, lib.GHOSTTY_RENDER_STATE_ROW_CELLS_DATA_FG_COLOR, rgb) == lib.GHOSTTY_SUCCESS:
            cell_foreground = rgb_color(rgb[0])
        cell_background: Color | None = None
        if get(cells, lib.GHOSTTY_RENDER_STATE_ROW_CELLS_DATA_BG_COLOR, rgb) == lib.GHOSTTY_SUCCESS:
            cell_background = rgb_color(rgb[0])
        style = self.style
        get(cells, lib.GHOSTTY_RENDER_STATE_ROW_CELLS_DATA_STYLE, style)
        if style.inverse:
            cell_foreground, cell_background = (
                background if cell_background is None else cell_background,
                foreground if cell_foreground is None else cell_foreground,
            )
        if style.invisible:
            cell_foreground = background if cell_background is None else cell_background
        return cell_style(
            cell_foreground,
            cell_background,
            bool(style.bold),
            bool(style.faint),
            bool(style.italic),
            style.underline != 0,
            bool(style.strikethrough),
        )

    def cursor_position(self) -> Position | None:
        """Where the cursor is, at the first column of a wide cell it's on, or `None` if it's hidden."""
        cursor = self.cursor
        check(lib.ghostty_render_state_get(self.state[0], lib.GHOSTTY_RENDER_STATE_DATA_CURSOR, cursor), "cursor")
        if not (cursor.visible and cursor.viewport_has_value):
            return None
        return Position(cursor.viewport_x - cursor.wide_tail, cursor.viewport_y)

    def modes(self) -> Modes:
        """The input modes the program has set."""
        mode = self.terminal.mode
        # The most detailed tracking mode set wins, as in xterm.
        tracking: MouseTracking
        if mode(1003):
            tracking = "any"
        elif mode(1002):
            tracking = "button"
        elif mode(1000):
            tracking = "normal"
        elif mode(9):
            tracking = "x10"
        else:
            tracking = "none"
        return Modes(
            application_cursor_keys=mode(1),
            bracketed_paste=mode(2004),
            mouse_tracking=tracking,
            sgr_mouse=mode(1006),
            focus_events=mode(1004),
            alternate_screen=mode(1049) or mode(1047) or mode(47),
        )

    def title(self) -> str:
        """The title the program set (with OSC 0 or 2), or an empty one."""
        title = self.title_out
        check(
            lib.ghostty_terminal_get(self.terminal._t[0], lib.GHOSTTY_TERMINAL_DATA_TITLE, title),  # noqa: SLF001
            "title",
        )
        if not title.len:
            return ""
        return bytes(ffi.buffer(title.ptr, title.len)).decode(errors="replace")


# How many cell values with no style an emulator keeps the cells of, before starting over.
PLAIN_CELLS_KEPT = 2**12

SPACE = ord(" ")
CELL_SIZE = ffi.sizeof("GhosttyCell")
UNSTYLED = CellStyle()


def free_render_state(state: object, row_iterator: object, cells: object) -> None:
    """Free an emulator's render state, which pyghostty's `Terminal` doesn't own."""
    lib.ghostty_render_state_row_cells_free(cells)
    lib.ghostty_render_state_row_iterator_free(row_iterator)
    lib.ghostty_render_state_free(state)


def rgb_color(rgb: object) -> Color:
    """A libghostty color as a `Color`."""
    return Color(rgb.r, rgb.g, rgb.b)  # type: ignore[attr-defined]


def is_unchanged(last: Screen, screen: Screen) -> bool:
    """Whether `screen` shows the same as `last`, so that a snapshot can return `last` instead."""
    return (
        len(last.lines) == len(screen.lines)
        and all(a is b for a, b in zip(last.lines, screen.lines, strict=True))
        and (last.columns, last.rows, last.cursor, last.modes, last.title, last.foreground, last.background)
        == (
            screen.columns,
            screen.rows,
            screen.cursor,
            screen.modes,
            screen.title,
            screen.foreground,
            screen.background,
        )
    )


@lru_cache(maxsize=2**10)
def cell_style(
    foreground: Color | None,
    background: Color | None,
    bold: bool,
    dim: bool,
    italic: bool,
    underline: bool,
    strikethrough: bool,
) -> CellStyle:
    """The style of a styled cell, leaving a color the program left as its default unset."""
    return CellStyle(
        foreground=UNSET if foreground is None else foreground,
        background=UNSET if background is None else background,
        bold=bold,
        dim=dim,
        italic=italic,
        underline=underline,
        strikethrough=strikethrough,
    )


@lru_cache(maxsize=2**12)
def cells_for(text: str, columns: int, style: CellStyle) -> tuple[StyledGrapheme, ...]:
    """
    The cells that show one of libghostty's cells, `text` taking `columns` columns, in `style`.

    libghostty and counterweight split text into grapheme clusters and measure them by different rules,
    so a libghostty cell can be several clusters here (it attaches zero-width spaces and marks to the cell before),
    of another width in all.
    The cells keep libghostty's `columns`, which the program laid its line out by:
    clusters narrower in all are followed by spaces, and ones wider, or with no width, are drawn as spaces.
    """
    clusters = graphemes(text)
    width = sum(map(grapheme_width, clusters))
    if not 0 < width <= columns:
        return (StyledGrapheme(grapheme=" ", style=style),) * columns
    return (
        *(StyledGrapheme(grapheme=cluster, style=style) for cluster in clusters),
        *(StyledGrapheme(grapheme=" ", style=style),) * (columns - width),
    )


__all__ = ["Emulator", "Modes", "MouseTracking", "Screen"]
