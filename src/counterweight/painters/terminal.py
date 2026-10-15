"""
Painters for what a terminal emulator shows, from the [`Screen`][counterweight.emulator.Screen] values it produces:
[`ScreenView`][counterweight.painters.terminal.ScreenView], a terminal's screen as it is now,
and [`Transcript`][counterweight.painters.terminal.Transcript], everything a program printed.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from itertools import accumulate
from typing import Self

from more_itertools import first
from more_itertools import locate

from counterweight.elements import Rows
from counterweight.elements import StyledGrapheme
from counterweight.emulator import Emulator
from counterweight.emulator import Screen
from counterweight.styles.styles import UNSET
from counterweight.styles.styles import CellStyle


@dataclass(frozen=True, slots=True)
class ScreenView:
    """
    A [`Canvas`][counterweight.elements.Canvas] painter that draws a terminal's `screen`,
    with its cursor as a cell with its colors swapped when `show_cursor` is set,
    such as while the canvas is focused.

    The box sizes the terminal, not the other way round, so its natural size is zero:
    size the canvas with its style, and resize the terminal to the canvas's content box.
    Cells in the program's default colors follow the canvas's `text_style`,
    and rows and columns past the box's edges are cut off.
    """

    screen: Screen
    show_cursor: bool = False

    @property
    def natural_size(self) -> tuple[int, int]:
        return 0, 0

    @property
    def keeps_aspect_ratio(self) -> bool:
        return False

    def draw(self, width: int, height: int) -> Rows:
        """The screen's top `height` rows, with the cursor drawn if it's shown and among them."""
        screen = self.screen
        lines = screen.lines[:height]
        cursor = screen.cursor
        if not self.show_cursor or cursor is None or cursor.y >= len(lines):
            return lines
        line = lines[cursor.y]
        index = column_index(line, cursor.x)
        if index is None:
            return lines
        under = line[index]
        cursor_line = (*line[:index], reversed_cell(under, screen), *line[index + 1 :])
        return (*lines[: cursor.y], cursor_line, *lines[cursor.y + 1 :])


def column_index(line: tuple[StyledGrapheme, ...], column: int) -> int | None:
    """
    The index in `line` of the cell drawn at `column`, counting each cell's width,
    or `None` if the line ends before it.
    A line from a terminal has one entry per grapheme cluster rather than per column,
    so after a wide cluster the two differ.
    """
    return first(locate(accumulate(cell.width for cell in line), lambda end: end > column), None)


def reversed_cell(cell: StyledGrapheme, screen: Screen) -> StyledGrapheme:
    """`cell` with its colors swapped, naming the screen's default colors for those it leaves unset."""
    style = cell.style
    foreground = screen.foreground if style.foreground is UNSET else style.foreground
    background = screen.background if style.background is UNSET else style.background
    return StyledGrapheme(
        grapheme=cell.grapheme,
        style=style | CellStyle(foreground=background, background=foreground),
    )


MAX_LINES = 10_000
"""How many lines a transcript keeps by default, dropping the oldest past it."""

BLANK = StyledGrapheme(grapheme=" ", style=CellStyle())


@dataclass(frozen=True, slots=True)
class Transcript:
    """
    A [`Canvas`][counterweight.elements.Canvas] painter that draws everything a program printed,
    as a terminal would have shown it: the rows that scrolled off the top of its terminal's screen,
    then the screen, down to its last row that isn't blank.
    It keeps the last `max_lines` of them, dropping the oldest.

    Its natural size is `columns` wide, the width of the terminal the program printed to,
    and as tall as its lines, so a canvas takes its height from them,
    and a [`scroll_area`][counterweight.widgets.scroll_area] around it scrolls what doesn't fit.
    It keeps no aspect ratio, so a canvas wider than `columns` doesn't make it taller.
    Cells in the program's default colors follow the canvas's `text_style`.

    Build one from output recorded ahead of time with [`of`][counterweight.painters.terminal.Transcript.of],
    and from a running program with [`use_command`][counterweight.commands.use_command].
    """

    columns: int
    history: Rows = ()
    """The rows that scrolled off the top of the screen, oldest first, at most `max_lines` of them."""
    screen: Rows = ()
    """The screen's rows, down to its last row that isn't blank."""
    max_lines: int = MAX_LINES
    lines: Rows = field(init=False, repr=False, compare=False)
    """The `history`, then the `screen`, keeping the last `max_lines` rows."""

    def __post_init__(self) -> None:
        object.__setattr__(self, "lines", (self.history + self.screen)[-self.max_lines :])

    @classmethod
    def of(cls, output: bytes, columns: int, rows: int = 24, max_lines: int = MAX_LINES) -> Self:
        """
        The transcript of `output`, recorded from a program run on a terminal `columns` by `rows`,
        such as with `script`, as a slide or a docs screenshot shows a command's output without running it.
        Queries in the output, which a program would wait for its terminal to answer, go unanswered.
        """
        with Emulator(columns, rows, on_reply=ignore_reply, scrollback=max_lines) as emulator:
            emulator.feed(output)
            return cls(columns=columns, max_lines=max_lines).followed_by(emulator.scrolled_off(), emulator.snapshot())

    def followed_by(self, scrolled_off: Rows, screen: Screen) -> Self:
        """
        This transcript, after the rows in `scrolled_off` scrolled off the top of the terminal's screen,
        which now shows `screen`, as [`Emulator.scrolled_off`][counterweight.emulator.Emulator.scrolled_off]
        and [`Emulator.snapshot`][counterweight.emulator.Emulator.snapshot] report them.
        """
        return type(self)(
            columns=self.columns,
            history=(self.history + scrolled_off)[-self.max_lines :],
            screen=without_trailing_blank_rows(screen.lines),
            max_lines=self.max_lines,
        )

    @property
    def natural_size(self) -> tuple[int, int]:
        return self.columns, len(self.lines)

    @property
    def keeps_aspect_ratio(self) -> bool:
        return False

    def draw(self, width: int, height: int) -> Rows:
        """The transcript's first `height` lines."""
        return self.lines[:height]


def without_trailing_blank_rows(lines: Rows) -> Rows:
    """`lines` without the rows at their end that are all blank, unstyled cells."""
    end = len(lines)
    while end and all(cell == BLANK for cell in lines[end - 1]):
        end -= 1
    return lines[:end]


def ignore_reply(reply: bytes) -> None:
    """Drops a reply to a query in recorded output, which has no program to answer."""


__all__ = ["MAX_LINES", "ScreenView", "Transcript"]
