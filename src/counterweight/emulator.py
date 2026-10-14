"""
A terminal emulator for embedding a program's output, and the immutable `Screen` values it produces.

Spike: the emulator is [libghostty-vt](https://ghostty.org), through `pyghostty`'s cffi bindings.
Everything outside this module sees only `Screen` and `Modes`, so the emulator behind them can be swapped.
The emulator object is a place (bytes fed to it change it); `snapshot` turns it into a value once per frame.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal

from pyghostty import Terminal
from pyghostty._ffi import check, ffi, lib
from pyghostty.core import init_sized

from counterweight.elements import Rows
from counterweight.geometry import Position
from counterweight.paint import Cell
from counterweight.styles.styles import CELL_STYLE_DEFAULTS, Color, ResolvedCellStyle

type MouseTracking = Literal["none", "x10", "normal", "button", "any"]


@dataclass(frozen=True, slots=True)
class Modes:
    """The modes the embedded program has set that change how input must be encoded for it."""

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
    What an embedded program's terminal shows at one moment: its rows of cells, its cursor, its modes and its title.

    Compared by identity: each snapshot of a changed terminal is a new `Screen`,
    so a `Canvas` drawing one is drawn again only when the program's output changed it.
    Rows the program didn't change are the same tuples as in the previous snapshot.
    """

    columns: int
    rows: int
    lines: tuple[tuple[Cell, ...], ...]
    cursor: Position | None
    """Where the cursor is, or `None` if the program hid it."""
    modes: Modes
    title: str


@dataclass(frozen=True, slots=True)
class ScreenView:
    """A `Canvas` painter for a `Screen`, drawing its cursor as a reversed cell when `show_cursor`."""

    screen: Screen
    show_cursor: bool

    def __call__(self, width: int, height: int) -> Rows:
        lines = self.screen.lines[:height]
        cursor = self.screen.cursor
        if not self.show_cursor or cursor is None or cursor.y >= len(lines) or cursor.x >= len(lines[cursor.y]):
            return lines
        line = lines[cursor.y]
        under = line[cursor.x]
        if under.is_continuation:
            return lines
        reversed_style = replace(under.style, foreground=under.style.background, background=under.style.foreground)
        cursor_line = (*line[: cursor.x], Cell(under.grapheme, reversed_style), *line[cursor.x + 1 :])
        return (*lines[: cursor.y], cursor_line, *lines[cursor.y + 1 :])


BLANK_SCREEN = Screen(columns=0, rows=0, lines=(), cursor=None, modes=Modes(), title="")


class Emulator:
    """
    A terminal emulator fed an embedded program's output.

    `replies` receives the bytes the emulator answers the program's queries with (cursor position reports,
    device attributes), which belong on the program's input, as a terminal would send them.
    """

    def __init__(
        self,
        columns: int,
        rows: int,
        replies: Callable[[bytes], None],
        defaults: ResolvedCellStyle = CELL_STYLE_DEFAULTS,
    ) -> None:
        self.terminal = Terminal(cols=columns, rows=rows)
        self.terminal.on_reply(replies)
        self.defaults = defaults
        self.state = ffi.new("GhosttyRenderState*")
        check(lib.ghostty_render_state_new(ffi.NULL, self.state), "render_state_new")
        self.row_iterator = ffi.new("GhosttyRenderStateRowIterator*")
        check(lib.ghostty_render_state_row_iterator_new(ffi.NULL, self.row_iterator), "row_iterator_new")
        self.cells = ffi.new("GhosttyRenderStateRowCells*")
        check(lib.ghostty_render_state_row_cells_new(ffi.NULL, self.cells), "row_cells_new")
        self.style = init_sized("GhosttyStyle")
        self.rgb = ffi.new("GhosttyColorRgb*")
        self.raw = ffi.new("GhosttyCell*")
        self.wide = ffi.new("int*")
        self.grapheme_length = ffi.new("uint32_t*")
        self.grapheme_buffer = ffi.new("uint32_t[32]")
        self.dirty = ffi.new("bool*")
        # An unstyled cell's raw value holds only its codepoint and width, so it maps to one Cell for good.
        # A styled cell's raw value holds a style id that only means something within its page, so it can't be cached.
        self.plain: dict[int, Cell] = {}
        self.has_styling = ffi.new("bool*")
        self.content_tag = ffi.new("int*")
        self.codepoint = ffi.new("uint32_t*")
        self.classify_keys = ffi.new(
            "GhosttyCellData[4]",
            [
                lib.GHOSTTY_CELL_DATA_WIDE,
                lib.GHOSTTY_CELL_DATA_HAS_STYLING,
                lib.GHOSTTY_CELL_DATA_CONTENT_TAG,
                lib.GHOSTTY_CELL_DATA_CODEPOINT,
            ],
        )
        self.classify_values = ffi.new(
            "void*[4]",
            [
                ffi.cast("void*", self.wide),
                ffi.cast("void*", self.has_styling),
                ffi.cast("void*", self.content_tag),
                ffi.cast("void*", self.codepoint),
            ],
        )
        self.row_id = ffi.new("GhosttyRenderStateRowId*")
        self.title_out = ffi.new("GhosttyString*")
        # Converted rows by libghostty's row id, kept from one snapshot to the next for rows that aren't dirty,
        # so a program scrolling by a line converts one row rather than all of them.
        self.converted: dict[tuple[int, int], tuple[Cell, ...]] = {}
        self.colors: dict[tuple[int, int, int], Color] = {}
        self.last: Screen = BLANK_SCREEN

    def feed(self, data: bytes) -> None:
        self.terminal.feed(data)

    def resize(self, columns: int, rows: int) -> None:
        self.terminal.resize(columns, rows)

    def snapshot(self) -> Screen:
        """The screen as the emulator shows it now."""
        terminal = self.terminal._t[0]
        state = self.state[0]
        check(lib.ghostty_render_state_update(state, terminal), "render_state_update")
        check(
            lib.ghostty_render_state_get(state, lib.GHOSTTY_RENDER_STATE_DATA_ROW_ITERATOR, self.row_iterator), "rows"
        )
        rows = self.row_iterator[0]
        converted: dict[tuple[int, int], tuple[Cell, ...]] = {}
        lines = []
        while lib.ghostty_render_state_row_iterator_next(rows):
            lib.ghostty_render_state_row_get(rows, lib.GHOSTTY_RENDER_STATE_ROW_DATA_DIRTY, self.dirty)
            lib.ghostty_render_state_row_get(rows, lib.GHOSTTY_RENDER_STATE_ROW_DATA_ID, self.row_id)
            key = (self.row_id.bits[0], self.row_id.bits[1])
            line = None if self.dirty[0] else self.converted.get(key)
            if line is None:
                line = self.convert_row(rows)
            converted[key] = line
            lines.append(line)
        lib.ghostty_render_state_clean(state)
        self.converted = converted

        columns, row_count = self.terminal.size
        x, y = self.terminal.cursor
        screen = Screen(
            columns=columns,
            rows=row_count,
            lines=tuple(lines),
            cursor=Position(x, y) if self.terminal.mode(25) else None,
            modes=self.modes(),
            title=self.title(),
        )
        self.last = screen
        return screen

    def convert_row(self, rows: object) -> tuple[Cell, ...]:
        cells_handle = self.cells
        check(lib.ghostty_render_state_row_get(rows, lib.GHOSTTY_RENDER_STATE_ROW_DATA_CELLS, cells_handle), "cells")
        cells = cells_handle[0]
        style = self.style
        rgb = self.rgb
        defaults = self.defaults
        row: list[Cell] = []
        get = lib.ghostty_render_state_row_cells_get
        plain = self.plain
        while lib.ghostty_render_state_row_cells_next(cells):
            get(cells, lib.GHOSTTY_RENDER_STATE_ROW_CELLS_DATA_RAW, self.raw)
            raw = self.raw[0]
            if (cell := plain.get(raw)) is not None:
                row.append(cell)
                continue
            lib.ghostty_cell_get_multi(raw, 4, self.classify_keys, self.classify_values, ffi.NULL)
            wide = self.wide[0]
            is_plain = not self.has_styling[0] and self.content_tag[0] == lib.GHOSTTY_CELL_CONTENT_CODEPOINT
            if is_plain and wide != lib.GHOSTTY_CELL_WIDE_SPACER_TAIL:
                cell = plain[raw] = Cell(chr(self.codepoint[0]) if self.codepoint[0] else " ", defaults)
                row.append(cell)
                continue
            if wide == lib.GHOSTTY_CELL_WIDE_SPACER_TAIL:
                row.append(Cell("", row[-1].style if row else defaults))
                continue
            get(cells, lib.GHOSTTY_RENDER_STATE_ROW_CELLS_DATA_GRAPHEMES_LEN, self.grapheme_length)
            length = self.grapheme_length[0]
            if length:
                get(cells, lib.GHOSTTY_RENDER_STATE_ROW_CELLS_DATA_GRAPHEMES_BUF, self.grapheme_buffer)
                grapheme = "".join(map(chr, self.grapheme_buffer[0:length]))
            else:
                grapheme = " "
            foreground = (
                self.color(rgb)
                if get(cells, lib.GHOSTTY_RENDER_STATE_ROW_CELLS_DATA_FG_COLOR, rgb) == lib.GHOSTTY_SUCCESS
                else defaults.foreground
            )
            background = (
                self.color(rgb)
                if get(cells, lib.GHOSTTY_RENDER_STATE_ROW_CELLS_DATA_BG_COLOR, rgb) == lib.GHOSTTY_SUCCESS
                else defaults.background
            )
            get(cells, lib.GHOSTTY_RENDER_STATE_ROW_CELLS_DATA_STYLE, style)
            if style.inverse:
                foreground, background = background, foreground
            if style.invisible:
                foreground = background
            row.append(
                Cell(
                    grapheme,
                    cell_style(
                        foreground,
                        background,
                        style.bold,
                        style.faint,
                        style.italic,
                        style.underline != 0,
                        style.strikethrough,
                    ),
                )
            )
        return tuple(row)

    def color(self, rgb: object) -> Color:
        key = (rgb.r, rgb.g, rgb.b)  # type: ignore[attr-defined]
        try:
            return self.colors[key]
        except KeyError:
            color = self.colors[key] = Color(*key)
            return color

    def modes(self) -> Modes:
        mode = self.terminal.mode
        # The most detailed tracking mode set wins, as in xterm.
        tracking: MouseTracking = (
            "any"
            if mode(1003)
            else "button"
            if mode(1002)
            else "normal"
            if mode(1000)
            else "x10"
            if mode(9)
            else "none"
        )
        return Modes(
            application_cursor_keys=mode(1),
            bracketed_paste=mode(2004),
            mouse_tracking=tracking,
            sgr_mouse=mode(1006),
            focus_events=mode(1004),
            alternate_screen=mode(1049) or mode(1047) or mode(47),
        )

    def title(self) -> str:
        result = lib.ghostty_terminal_get(self.terminal._t[0], lib.GHOSTTY_TERMINAL_DATA_TITLE, self.title_out)
        if result != lib.GHOSTTY_SUCCESS or not self.title_out.len:
            return ""
        return bytes(ffi.buffer(self.title_out.ptr, self.title_out.len)).decode(errors="replace")

    def close(self) -> None:
        lib.ghostty_render_state_row_cells_free(self.cells[0])
        lib.ghostty_render_state_row_iterator_free(self.row_iterator[0])
        lib.ghostty_render_state_free(self.state[0])
        self.terminal.close()


_STYLES: dict[tuple[Color, Color, bool, bool, bool, bool, bool], ResolvedCellStyle] = {}


def cell_style(
    foreground: Color, background: Color, bold: bool, dim: bool, italic: bool, underline: bool, strikethrough: bool
) -> ResolvedCellStyle:
    key = (foreground, background, bold, dim, italic, underline, strikethrough)
    try:
        return _STYLES[key]
    except KeyError:
        style = _STYLES[key] = ResolvedCellStyle(
            foreground=foreground,
            background=background,
            bold=bold,
            dim=dim,
            italic=italic,
            underline=underline,
            strikethrough=strikethrough,
            link=None,
        )
        return style
