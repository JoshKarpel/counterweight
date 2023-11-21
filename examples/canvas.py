import asyncio
import random
from asyncio import sleep
from itertools import product

from more_itertools import grouper
from structlog import get_logger

from reprisal.app import app
from reprisal.cell_paint import CellPaint
from reprisal.components import Chunk, Div, Text, component
from reprisal.hooks import use_effect, use_state
from reprisal.styles.styles import COLORS_BY_NAME
from reprisal.styles.utilities import *

logger = get_logger()

black = Color.from_name("black")


def canvas(
    width: int,
    height: int,
    cells: dict[tuple[int, int], Color],
) -> list[CellPaint]:
    c = []
    for y_top, y_bot in grouper(range(height), 2):
        for x in range(width):
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


def clamp(min_: int, val: int, max_: int) -> int:
    return max(min_, min(val, max_))


@component
def root() -> Div:
    return Div(
        style=col | align_children_center | justify_children_space_evenly,
        children=[
            header(),
            Div(
                style=col | align_children_center | justify_children_center,
                children=[
                    Div(
                        style=row | align_children_center | justify_children_space_evenly,
                        children=[
                            random_walkers(),
                            random_walkers(),
                        ],
                    ),
                    Div(
                        style=row | align_children_center | justify_children_space_evenly,
                        children=[
                            random_walkers(),
                            random_walkers(),
                        ],
                    ),
                ],
            ),
        ],
    )


@component
def header() -> Text:
    return Text(
        content=[
            Chunk(
                content="Canvas",
                style=CellStyle(foreground=amber_600),
            ),
            Chunk.space(),
            Chunk(
                content="Demo",
                style=CellStyle(foreground=cyan_600),
            ),
            Chunk.newline(),
            Chunk(
                content="App",
                style=CellStyle(foreground=pink_600),
            ),
        ],
        style=text_justify_center,
    )


moves = [(x, y) for x, y in product((-1, 0, 1), repeat=2) if (x, y) != (0, 0)]

w, h = 30, 30
n = 30


@component
def random_walkers() -> Text:
    colors, set_colors = use_state(random.sample(list(COLORS_BY_NAME.values()), k=n))
    walkers, set_walkers = use_state([(random.randrange(w), random.randrange(h)) for _ in range(len(colors))])

    def update_movers(m: list[tuple[int, int]]) -> list[tuple[int, int]]:
        new = []
        for x, y in m:
            dx, dy = random.choice(moves)
            new.append(
                (
                    clamp(0, x + dx, w - 1),
                    clamp(0, y + dy, h - 1),
                )
            )
        return new

    async def tick() -> None:
        while True:
            await sleep(0.5)
            set_walkers(update_movers)

    use_effect(tick, deps=())

    return Text(
        content=(
            canvas(
                width=w,
                height=h,
                cells=dict(zip(walkers, colors)),
            )
        ),
        style=border_heavy | border_slate_400,
    )


asyncio.run(app(root))
