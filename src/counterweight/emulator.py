"""
A terminal emulator, which turns the bytes a program writes to its terminal into what that terminal shows,
and the immutable [`Screen`][counterweight.emulator.Screen] values it shows them as.

The emulator is [libghostty-vt](https://ghostty.org), through [pyghostty](https://github.com/AnswerDotAI/pyghostty)'s
cffi bindings.
Nothing outside this module touches it, so everything else sees only `Screen` and `Modes` values.
An `Emulator` is a place: the bytes fed to it change it. `snapshot` turns what it shows into a `Screen`.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
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
from counterweight.styles.styles import DEFAULT_PALETTE
from counterweight.styles.styles import UNSET
from counterweight.styles.styles import AnyColor
from counterweight.styles.styles import CellStyle
from counterweight.styles.styles import Color
from counterweight.styles.styles import IndexedColor

WHITE = Color.from_name("white")
BLACK = Color.from_name("black")

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

    A cell in the program's default colors leaves them unset, so they follow the style of the canvas showing it,
    and one in a palette color is an [`IndexedColor`][counterweight.styles.IndexedColor], which follows the user's theme,
    unless the program changed that palette entry (with OSC 4), which makes it the RGB `Color` the program chose.
    Where the emulator and counterweight's `grapheme_width` disagree on how wide
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
    Its palette starts as [`DEFAULT_PALETTE`][counterweight.styles.DEFAULT_PALETTE].

    `scrollback` is how many of the rows that scroll off the top of the screen
    [`scrolled_off`][counterweight.emulator.Emulator.scrolled_off] can return, at most `MAX_SCROLLBACK`.

    Use it as a context manager, or call `close`, to free the emulator's memory as soon as it's done with.
    """

    def __init__(
        self,
        columns: int,
        rows: int,
        on_reply: Callable[[bytes], None],
        foreground: Color = WHITE,
        background: Color = BLACK,
        scrollback: int = 0,
    ) -> None:
        if not 0 <= scrollback <= MAX_SCROLLBACK:
            raise ValueError(f"An emulator's scrollback must be from 0 to {MAX_SCROLLBACK:_}, but got {scrollback:_}")
        self.scrollback = scrollback
        self.terminal = Terminal(
            cols=columns,
            rows=rows,
            scrollback=scrollback and scrollback + rows_per_page(columns),
            fg=foreground,
            bg=background,
        )
        check(
            lib.ghostty_terminal_set(
                self.terminal._t[0],  # noqa: SLF001
                lib.GHOSTTY_TERMINAL_OPT_COLOR_PALETTE,
                ffi.new("GhosttyColorRgb[]", [{"r": r, "g": g, "b": b} for r, g, b in DEFAULT_PALETTE]),
            ),
            "color_palette",
        )
        if scrollback:
            # libghostty also caps its scrollback at 10,000 bytes by default, a few hundred rows,
            # so only the line limit above bounds it.
            check(
                lib.ghostty_terminal_set(
                    self.terminal._t[0],  # noqa: SLF001
                    lib.GHOSTTY_TERMINAL_OPT_SCROLLBACK_MAX_BYTES,
                    ffi.NULL,
                ),
                "scrollback_max_bytes",
            )
        self.terminal.on_reply(on_reply)

        # One render state reads both the screen and the rows that scrolled off it:
        # an update takes the terminal's dirty rows, so a second render state would hide them from the first.
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
        self.palette_index = ffi.new("GhosttyColorPaletteIndex*")
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
        self.overscan = ffi.new("GhosttyRenderStateOverscan*")
        self.captured = ffi.new("GhosttyRenderStateOverscan*")
        if scrollback:
            self.request_overscan(min(rows, scrollback))

        # The cells of each cell value with no style, which holds only a codepoint and its width,
        # so each maps to the same cells for good. A styled cell's value holds a style id that means something
        # only within its page, so those are kept only while converting one row.
        self.plain: dict[int, tuple[StyledGrapheme, ...]] = {}
        # Each row's cells by libghostty's row id, kept from one snapshot to the next for rows that aren't dirty,
        # so a program that changes one row has one row converted rather than all of them.
        self.converted: dict[tuple[int, int], tuple[StyledGrapheme, ...]] = {}
        self.last: Screen | None = None
        # The palette as of the last update, as libghostty's RGB bytes, to tell which entries the program changed.
        self.palette: bytes
        # The rows that scrolled off the screen that `scrolled_off` hasn't returned yet, oldest first,
        # and the id of the newest of them, which marks where the rows not yet set aside start.
        self.pending: list[tuple[StyledGrapheme, ...]] = []
        self.last_scrolled_off: tuple[int, int] | None = None

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
        foreground, background = self.update()
        last = self.last
        if last is not None and (foreground, background) != (last.foreground, last.background):
            # Inverse and invisible cells name the default colors, so they change with them.
            self.converted = {}

        check(
            lib.ghostty_render_state_get(state, lib.GHOSTTY_RENDER_STATE_DATA_ROW_ITERATOR, self.row_iterator), "rows"
        )
        rows = self.row_iterator[0]
        for _ in range(self.captured.above):
            lib.ghostty_render_state_row_iterator_next(rows)
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

    def scrolled_off(self) -> Rows:
        """
        The rows that scrolled off the top of the screen since the last call, oldest first,
        or the newest `scrollback` of them if more did.

        It returns each row once, as it was when it scrolled off, so a program's whole output
        is what each call returns in turn, followed by the screen.
        Erasing the scrollback (`ESC [ 3 J`) doesn't take back rows it already returned,
        and a program drawing on the alternate screen scrolls nothing off.
        """
        self.update()
        scrolled_off = tuple(self.pending)
        self.pending = []
        return scrolled_off

    def update(self) -> tuple[Color, Color]:
        """
        Brings the render state up to date with the terminal, setting aside the rows that scrolled off the screen
        since the last update, and returns the colors the program's default colors stand for.

        The render state's rows stay dirty until a snapshot cleans them, however many updates come first.
        """
        state = self.state[0]
        terminal = self.terminal._t[0]  # noqa: SLF001
        check(lib.ghostty_render_state_update(state, terminal), "render_state_update")
        check(lib.ghostty_render_state_get(state, lib.GHOSTTY_RENDER_STATE_DATA_OVERSCAN, self.captured), "overscan")
        check(lib.ghostty_render_state_get(state, lib.GHOSTTY_RENDER_STATE_DATA_COLORS, self.colors), "colors")
        foreground = rgb_color(self.colors.foreground)
        background = rgb_color(self.colors.background)
        # Cells in a palette entry the program changed name the color it changed it to.
        # Changing the palette marks every row dirty, so the rows converted before are converted again.
        self.palette = bytes(ffi.buffer(self.colors.palette))
        if not self.scrollback:
            return foreground, background

        last = self.last_scrolled_off
        while True:
            ids = self.row_ids(self.captured.above)
            if last in ids:
                start = len(ids) - ids[::-1].index(last)
                break
            requested = self.overscan.above
            if self.captured.above < requested or requested == self.scrollback:
                # Every row above the screen is new, or at least the newest `scrollback` of them are.
                start = 0
                break
            # The last row set aside is further up than the rows captured above the screen, so capture twice as many.
            self.request_overscan(min(requested * 2, self.scrollback))
            check(lib.ghostty_render_state_update(state, terminal), "render_state_update")
            check(
                lib.ghostty_render_state_get(state, lib.GHOSTTY_RENDER_STATE_DATA_OVERSCAN, self.captured), "overscan"
            )

        scrolled = len(ids) - start
        if scrolled:
            self.last_scrolled_off = ids[-1]
            check(
                lib.ghostty_render_state_get(state, lib.GHOSTTY_RENDER_STATE_DATA_ROW_ITERATOR, self.row_iterator),
                "rows",
            )
            rows = self.row_iterator[0]
            for index in range(len(ids)):
                lib.ghostty_render_state_row_iterator_next(rows)
                if index >= start:
                    self.pending.append(self.convert_row(rows, foreground, background))
            del self.pending[: -self.scrollback]

        # Capturing rows above the screen costs time for each row, and changing how many marks every row dirty,
        # so the next update captures what this one needed, rounded up to the screen's rows times a power of two.
        needed = self.terminal.size[1]
        while needed < 2 * scrolled:
            needed *= 2
        if (needed := min(needed, self.scrollback)) != self.overscan.above:
            self.request_overscan(needed)
        return foreground, background

    def request_overscan(self, above: int) -> None:
        """Asks the next update to capture `above` rows above the screen, or as many as there are."""
        self.overscan.above = above
        check(
            lib.ghostty_render_state_set(self.state[0], lib.GHOSTTY_RENDER_STATE_OPTION_OVERSCAN, self.overscan),
            "overscan",
        )

    def row_ids(self, count: int) -> list[tuple[int, int]]:
        """The ids of the first `count` rows the render state captured, top to bottom."""
        check(
            lib.ghostty_render_state_get(self.state[0], lib.GHOSTTY_RENDER_STATE_DATA_ROW_ITERATOR, self.row_iterator),
            "rows",
        )
        rows = self.row_iterator[0]
        row_id = self.row_id
        ids = []
        for _ in range(count):
            lib.ghostty_render_state_row_iterator_next(rows)
            lib.ghostty_render_state_row_get(rows, lib.GHOSTTY_RENDER_STATE_ROW_DATA_ID, row_id)
            ids.append((row_id.bits[0], row_id.bits[1]))
        return ids

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
        classified = len(self.classify_keys)
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

            lib.ghostty_cell_get_multi(value, classified, self.classify_keys, self.classify_values, ffi.NULL)
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
            known = seen[value] = cells_for(" ", columns, self.erased_style(value, content))
            row.extend(known)
        return tuple(row)

    def erased_style(self, value: int, content: int) -> CellStyle:
        """The style of a blank cell whose value holds the background the program erased it with, and no style."""
        if content == lib.GHOSTTY_CELL_CONTENT_BG_COLOR_PALETTE:
            check(lib.ghostty_cell_get(value, lib.GHOSTTY_CELL_DATA_COLOR_PALETTE, self.palette_index), "color_palette")
            return erased(self.palette_color(self.palette_index[0]))
        check(lib.ghostty_cell_get(value, lib.GHOSTTY_CELL_DATA_COLOR_RGB, self.rgb), "color_rgb")
        return erased(rgb_color(self.rgb[0]))

    def read_style(self, cells: object, foreground: Color, background: Color) -> CellStyle:
        """
        The style of the cell `cells` is at, leaving colors that are the program's defaults unset,
        but where it has to name them, as `foreground` and `background`.
        """
        style = self.style
        check(
            lib.ghostty_render_state_row_cells_get(cells, lib.GHOSTTY_RENDER_STATE_ROW_CELLS_DATA_STYLE, style), "style"
        )
        cell_foreground = self.style_color(style.fg_color)
        cell_background = self.style_color(style.bg_color)
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

    def style_color(self, color: object) -> AnyColor | None:
        """A style's color, or `None` for the program's default."""
        tag = color.tag  # type: ignore[attr-defined]
        if tag == lib.GHOSTTY_STYLE_COLOR_PALETTE:
            return self.palette_color(color.value.palette)  # type: ignore[attr-defined]
        if tag == lib.GHOSTTY_STYLE_COLOR_RGB:
            return rgb_color(color.value.rgb)  # type: ignore[attr-defined]
        return None

    def palette_color(self, index: int) -> AnyColor:
        """
        Palette entry `index`, which follows the user's theme as an `IndexedColor`,
        unless the program changed it, since the user's terminal doesn't know the color it changed it to.
        """
        start = 3 * index
        entry = self.palette[start : start + 3]
        if entry == DEFAULT_PALETTE_BYTES[start : start + 3]:
            return INDEXED_COLORS[index]
        return Color(*entry)

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
        # libghostty ignores a title that isn't UTF-8.
        return bytes(ffi.buffer(title.ptr, title.len)).decode()


SNAPSHOT_INTERVAL = timedelta(seconds=1 / 60)
"""
The least time between two snapshots of a running program's terminal, so at most one is taken a frame
however fast the program writes.
"""

BLANK_SCREEN = Screen(
    columns=0,
    rows=0,
    lines=(),
    cursor=None,
    modes=Modes(),
    title="",
    foreground=WHITE,
    background=BLACK,
)
"""A screen with nothing on it, for before a terminal's first snapshot."""

# How many cell values with no style an emulator keeps the cells of, before starting over.
PLAIN_CELLS_KEPT = 2**12

MAX_SCROLLBACK = 2**16 - 1
"""The most rows an emulator's scrollback can hold: as many as libghostty captures above its screen at once."""


def rows_per_page(columns: int) -> int:
    """
    At least as many rows as one of libghostty's pages holds at `columns` wide.
    libghostty drops scrollback a page at a time, so it can keep a page fewer rows than its line limit.
    A page holds about 46,000 cells, more than a row of each width.
    """
    return -(-(2**16) // columns)


SPACE = ord(" ")
DEFAULT_PALETTE_BYTES = bytes(channel for color in DEFAULT_PALETTE for channel in color)
INDEXED_COLORS = tuple(IndexedColor(index) for index in range(len(DEFAULT_PALETTE)))
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
    foreground: AnyColor | None,
    background: AnyColor | None,
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


def erased(background: AnyColor) -> CellStyle:
    """The style of a blank cell the program erased with `background`."""
    return cell_style(None, background, False, False, False, False, False)


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


__all__ = ["BLANK_SCREEN", "MAX_SCROLLBACK", "SNAPSHOT_INTERVAL", "Emulator", "Modes", "MouseTracking", "Screen"]
