"""
Painters for what a terminal emulator shows, from the [`Screen`][counterweight.emulator.Screen] values it produces.

They need the `emulator` extra (`counterweight[emulator]`).
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import accumulate

from more_itertools import first
from more_itertools import locate

from counterweight.elements import Rows
from counterweight.elements import StyledGrapheme
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


__all__ = ["ScreenView"]
