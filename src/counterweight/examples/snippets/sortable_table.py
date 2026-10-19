"""
Cookbook: Sortable tables

A table sorted by the header clicked.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.handlers import on_click
from counterweight.hooks import use_state
from counterweight.styles.utilities import *

# --8<-- [start:example]


@dataclass(frozen=True, slots=True)
class Peak:
    name: str
    height: int
    first_ascent: int


PEAKS = (
    Peak("Everest", 8849, 1953),
    Peak("K2", 8611, 1954),
    Peak("Kangchenjunga", 8586, 1955),
    Peak("Lhotse", 8516, 1956),
    Peak("Makalu", 8485, 1955),
    Peak("Cho Oyu", 8188, 1954),
    Peak("Annapurna I", 8091, 1950),
)


@dataclass(frozen=True, slots=True)
class Column:
    label: str
    width: int
    value: Callable[[Peak], str | int]


COLUMNS = (
    Column("Peak", 15, lambda peak: peak.name),
    Column("Height (m)", 12, lambda peak: peak.height),
    Column("First ascent", 14, lambda peak: peak.first_ascent),
)


@dataclass(frozen=True, slots=True)
class Sort:
    column: int
    is_descending: bool

    def by(self, column: int) -> Sort:
        """Sorted by `column`, and the other way if it's already sorted by it."""
        return Sort(column, not self.is_descending if column == self.column else False)


CELL = content_box | border | pad_x(1)


@component
def peak_table() -> Div:
    sort, set_sort = use_state(Sort(column=1, is_descending=True))

    def sort_by(column: int) -> None:
        set_sort(lambda sort: sort.by(column))

    arrow = "↓" if sort.is_descending else "↑"
    header = Div(
        style=row | border_collapse,
        children=tuple(
            Text(
                content=f"{column.label} {arrow if index == sort.column else ' '}",
                style=CELL | width(column.width) | text_color("amber", 300) | text_bold,
                on_input=on_click(partial(sort_by, index)),
            )
            for index, column in enumerate(COLUMNS)
        ),
    )
    peaks = sorted(PEAKS, key=COLUMNS[sort.column].value, reverse=sort.is_descending)
    rows = tuple(
        Div(
            style=row | border_collapse,
            children=tuple(
                Text(content=str(column.value(peak)), style=CELL | width(column.width) | text_color("slate", 300))
                for column in COLUMNS
            ),
        )
        for peak in peaks
    )
    return Div(style=col | border_collapse, children=(header, *rows))


# --8<-- [end:example]


ROOTS = (peak_table,)

# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import paced
from counterweight.events import MouseDown
from counterweight.events import MouseUp
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still
from counterweight.geometry import Position


def click(x: int) -> tuple[MouseDown, MouseUp]:
    """A click on the header, `x` cells from the table's left edge."""
    return MouseDown(absolute=Position(x, 1), button=1), MouseUp(absolute=Position(x, 1), button=1)


PEAK, HEIGHT, FIRST_ASCENT = 5, 25, 40
DIMENSIONS = (52, 17)

STILLS = [Still("sortable-table", peak_table(), DIMENSIONS, steps=click(FIRST_ASCENT))]

DEMOS = [
    Demo(
        "sortable-table",
        peak_table(),
        DIMENSIONS,
        steps=paced(
            [*click(FIRST_ASCENT), *click(PEAK), *click(PEAK), *click(HEIGHT)], every=timedelta(milliseconds=800)
        ),
    )
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(peak_table()))
