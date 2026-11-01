"""
A terminal emulator, which turns the bytes a program writes to its terminal into what that terminal shows,
and the immutable [`Screen`][counterweight.emulator.Screen] values it shows them as.

The emulator is [libghostty-vt](https://ghostty.org), through [evp](https://github.com/JoshKarpel/evp).
Nothing outside this module touches it, so everything else sees only `Screen` and `Modes` values.
An `Emulator` is a place: the bytes fed to it change it. `snapshot` turns what it shows into a `Screen`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from types import TracebackType
from typing import Literal
from typing import Self

from evp import RenderState
from evp import Row
from evp import Style
from evp import Terminal

from counterweight._graphemes import grapheme_width
from counterweight._graphemes import graphemes
from counterweight.elements import Rows
from counterweight.elements import StyledGrapheme
from counterweight.geometry import Position
from counterweight.styles._styles import DEFAULT_PALETTE
from counterweight.styles._styles import UNSET
from counterweight.styles._styles import AnyColor
from counterweight.styles._styles import CellStyle
from counterweight.styles._styles import Color
from counterweight.styles._styles import IndexedColor

WHITE = Color.from_name("white")
BLACK = Color.from_name("black")

type MouseTracking = Literal["none", "x10", "normal", "button", "any"]
"""Which mouse events a program asked its terminal to report, from fewest to most."""

type Line = tuple[StyledGrapheme, ...]


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
    The terminal sets aside memory for that many rows `columns` wide, however they're styled,
    so after a resize wider, or for rows whose every cell links somewhere different,
    it can hold fewer of them.

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
            columns,
            rows,
            max_scrollback_bytes=scrollback * columns * SCROLLBACK_BYTES_PER_CELL,
            on_write_pty=on_reply,
        )
        self.terminal.set_default_palette(DEFAULT_PALETTE_BYTES)
        self.set_default_colors(foreground, background)
        # One render state reads both the screen and the rows that scrolled off it.
        self.state = RenderState(self.terminal)

        # evp's styles by index, and each converted for the current default colors and palette, which they name.
        self.styles: list[Style] = []
        self.cell_styles: list[CellStyle] = []
        self.colors: tuple[tuple[int, int, int], tuple[int, int, int], bytes] | None = None
        self.foreground = foreground
        self.background = background
        self.palette = DEFAULT_PALETTE_BYTES
        # Each row's cells by the `Row` evp read it as, which evp hands back while the row is unchanged, even moved.
        self.lines: dict[Row, Line] = {}
        self.last: Screen | None = None
        # The rows that scrolled off the screen that `scrolled_off` hasn't returned yet, oldest first.
        self.pending: list[Line] = []

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

    def set_default_colors(self, foreground: Color, background: Color) -> None:
        """
        Changes the colors the program's default colors stand for wherever a cell has to name them
        (see [`Screen.background`][counterweight.emulator.Screen.background]),
        as the user changing their terminal's theme does, keeping everything else the terminal shows.
        A color the program set (with OSC 10 or 11) stays what it set.
        """
        self.terminal.set_default_colors(
            (foreground.red, foreground.green, foreground.blue),
            (background.red, background.green, background.blue),
        )

    def close(self) -> None:
        """Free the emulator's memory. It can't be fed or snapshotted after."""
        # evp frees the terminal and its render state when the last reference to them goes.
        del self.state, self.terminal

    def snapshot(self) -> Screen:
        """What the terminal shows now."""
        frame = self.state.frame()
        colors = (frame.foreground, frame.background, frame.palette)
        if colors != self.colors:
            # Styles name the default colors and the palette, so they're converted again, and the rows with them.
            self.colors = colors
            self.foreground = Color(*frame.foreground)
            self.background = Color(*frame.background)
            self.palette = frame.palette
            self.cell_styles = []
            self.lines = {}
        self.add_styles(frame.new_styles)
        # Set the rows that scrolled off aside before the scrollback can free them.
        self.set_aside_scrolled_off()

        previous = self.lines
        lines: dict[Row, Line] = {}
        for row in frame.rows:
            line = previous.get(row)
            if line is None:
                line = convert_row(row, self.cell_styles)
            lines[row] = line
        self.lines = lines

        columns, row_count = frame.size
        last = self.last
        screen = Screen(
            columns=columns,
            rows=row_count,
            lines=tuple(lines[row] for row in frame.rows),
            cursor=cursor_position(frame.cursor),
            modes=self.modes(),
            title=self.terminal.title(),
            foreground=self.foreground,
            background=self.background,
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
        self.set_aside_scrolled_off()
        scrolled_off = tuple(self.pending)
        self.pending = []
        return scrolled_off

    def history(self) -> Rows:
        """
        The rows above the screen, oldest first, the newest `scrollback` of them,
        as the terminal holds them now: rewrapped to its width by every resize since they scrolled off,
        as a terminal's scrollback is, where `scrolled_off` returns each as it was when it scrolled off.
        It converts every row each call, so it's for looking at a terminal now and then, not every frame.
        """
        if not self.scrollback:
            return ()
        self.set_aside_scrolled_off()
        history = self.state.history()
        self.add_styles(history.new_styles)
        return tuple(convert_row(row, self.cell_styles) for row in history.rows[-self.scrollback :])

    def set_aside_scrolled_off(self) -> None:
        """Converts the rows that scrolled off since the last call, keeping the newest `scrollback` not yet returned."""
        if not self.scrollback:
            return
        scrolled_off = self.state.scrolled_off()
        self.add_styles(scrolled_off.new_styles)
        self.pending.extend(convert_row(row, self.cell_styles) for row in scrolled_off.rows)
        del self.pending[: -self.scrollback]

    def add_styles(self, styles: tuple[Style, ...]) -> None:
        """Takes the styles evp delivered, and converts every style not yet converted for the current colors."""
        self.styles.extend(styles)
        cell_styles = self.cell_styles
        for style in self.styles[len(cell_styles) :]:
            # evp's first style is that of a cell with no styling, which leaves everything unset.
            cell_styles.append(self.cell_style(style) if cell_styles else UNSTYLED)

    def cell_style(self, style: Style) -> CellStyle:
        """
        `style` as a `CellStyle`, leaving colors that are the program's defaults unset,
        but where it has to name them, as the colors they stand for.
        """
        foreground = self.color(style.foreground)
        background = self.color(style.background)
        if style.inverse:
            foreground, background = (
                self.background if background is None else background,
                self.foreground if foreground is None else foreground,
            )
        if style.invisible:
            foreground = self.background if background is None else background
        return cell_style(
            foreground,
            background,
            style.bold,
            style.faint,
            style.italic,
            style.underline != 0,
            style.strikethrough,
        )

    def color(self, color: int | tuple[int, int, int] | None) -> AnyColor | None:
        """
        A style's color, or `None` for the program's default.
        A palette entry follows the user's theme as an `IndexedColor`,
        unless the program changed it, since the user's terminal doesn't know the color it changed it to.
        """
        if color is None:
            return None
        if isinstance(color, tuple):
            return Color(*color)
        start = 3 * color
        entry = self.palette[start : start + 3]
        if entry == DEFAULT_PALETTE_BYTES[start : start + 3]:
            return INDEXED_COLORS[color]
        return Color(*entry)

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

MAX_SCROLLBACK = 2**16 - 1
"""The most rows an emulator's scrollback can hold."""

# libghostty bounds its scrollback in bytes. A plain row takes about 9 bytes a cell, and a row whose every cell has
# its own colors, a grapheme cluster and a link about 45, or 55 with only distinct styles 300 columns wide.
SCROLLBACK_BYTES_PER_CELL = 64

DEFAULT_PALETTE_BYTES = bytes(channel for color in DEFAULT_PALETTE for channel in color)
INDEXED_COLORS = tuple(IndexedColor(index) for index in range(len(DEFAULT_PALETTE)))
UNSTYLED = CellStyle()


def cursor_position(cursor: tuple[int, int, bool] | None) -> Position | None:
    """Where the cursor is, at the first column of a wide cell it's on, or `None` if it's hidden."""
    if cursor is None:
        return None
    x, y, at_wide_tail = cursor
    return Position(x - at_wide_tail, y)


def convert_row(row: Row, cell_styles: list[CellStyle]) -> Line:
    """
    A row's cells, as counterweight draws them. A column of width 0 follows a wide character, which drew it.

    A cell repeated in the row is the same objects wherever it recurs, which `cells_for`'s cache alone
    doesn't promise once a row holds more distinct cells than it keeps.
    """
    cells: list[StyledGrapheme] = []
    seen: dict[tuple[str, int, int], Line] = {}
    for key in zip(row.graphemes, row.widths, row.styles, strict=True):
        grapheme, width, index = key
        if not width:
            continue
        known = seen.get(key)
        if known is None:
            known = seen[key] = cells_for(grapheme, width, cell_styles[index])
        cells.extend(known)
    return tuple(cells)


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
