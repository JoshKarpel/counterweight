import asyncio

from more_itertools import grouper
from structlog import get_logger

from reprisal.app import app
from reprisal.cell_paint import CellPaint
from reprisal.components import Chunk, Div, Text, component
from reprisal.styles.utilities import *

logger = get_logger()


def canvas(
    width: int,
    height: int,
    cells: dict[tuple[int, int], Color],
) -> list[CellPaint]:
    black = Color.from_name("black")
    c = []
    for y_top, y_bot in grouper(range(height), 2):
        for x in range(width):
            logger.debug((y_top, y_bot, x))
            c.append(
                CellPaint(
                    char="▀",
                    style=CellStyle(
                        foreground=cells.get((x, y_top), black),
                        background=cells.get((x, y_bot), black),
                    ),
                )
            )
        c.append(CellPaint(char="\n"))
    return c[:-1]  # strip off last newline


@component
def root() -> Div:
    c = canvas(
        width=10,
        height=10,
        cells={
            (0, 0): text_cyan_700.typography.style.foreground,
            (5, 5): text_blue_300.typography.style.foreground,
            (9, 9): text_pink_300.typography.style.foreground,
            (0, 9): text_amber_600.typography.style.foreground,
            (9, 0): text_lime_500.typography.style.foreground,
        },
    )

    return Div(
        style=col | align_children_center | justify_children_space_around,
        children=[
            Text(
                content=[
                    Chunk(
                        content="Canvas",
                        style=text_amber_600.typography.style,
                    ),
                    Chunk.space(),
                    Chunk(
                        content="Demo",
                        style=text_cyan_600.typography.style,
                    ),
                    Chunk.newline(),
                    Chunk(
                        content="App",
                        style=text_pink_300.typography.style,
                    ),
                ],
                style=border_heavy | border_slate_400 | pad_x_2 | pad_y_1 | text_justify_center,
            ),
            Text(
                content=c,
                style=border_heavy | border_slate_400,
            ),
        ],
    )


asyncio.run(app(root))
