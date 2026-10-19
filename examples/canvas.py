import asyncio
import logging
import random
from asyncio import sleep
from itertools import product

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Canvas
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.geometry import Position
from counterweight.hooks import use_effect
from counterweight.hooks import use_state
from counterweight.painters.pixels import HalfBlocks
from counterweight.painters.pixels import Pixels
from counterweight.styles import Color
from counterweight.styles.styles import COLORS_BY_NAME
from counterweight.styles.utilities import *
from counterweight.utils import clamp

logger = logging.getLogger(__name__)

BLACK = Color.from_name("black")


@component
def root() -> Div:
    return Div(
        style=col | align_children_center | justify_children_space_evenly,
        children=(
            header(),
            Div(
                style=col | center_children,
                children=(
                    Div(
                        style=row | align_children_center | justify_children_space_evenly,
                        children=(
                            random_walkers(),
                            random_walkers(),
                        ),
                    ),
                    Div(
                        style=row | align_children_center | justify_children_space_evenly,
                        children=(
                            random_walkers(),
                            random_walkers(),
                        ),
                    ),
                ),
            ),
        ),
    )


@component
def header() -> Text:
    return Text(
        content=(
            Chunk(
                content="Canvas",
                style=text_color(amber_600),
            ),
            Chunk.space(),
            Chunk(
                content="Demo",
                style=text_color(cyan_600),
            ),
            Chunk.newline(),
            Chunk(
                content="App",
                style=text_color(pink_600),
            ),
        ),
        style=text_justify_center,
    )


moves = [(x, y) for x, y in product((-1, 0, 1), repeat=2) if (x, y) != (0, 0)]

w, h = 30, 30
n = 30


@component
def random_walkers() -> Canvas:
    colors, _set_colors = use_state(random.sample(list(COLORS_BY_NAME.values()), k=n))
    walkers, set_walkers = use_state([Position(random.randrange(w), random.randrange(h)) for _ in range(len(colors))])

    def update_movers(m: list[Position]) -> list[Position]:
        new = []
        for p in m:
            dx, dy = random.choice(moves)
            new.append(Position(clamp(0, p.x + dx, w - 1), clamp(0, p.y + dy, h - 1)))
        return new

    async def tick() -> None:
        while True:
            await sleep(0.5)
            set_walkers(update_movers)

    use_effect(tick, deps=())

    return Canvas(
        painter=HalfBlocks(Pixels.from_points(w, h, dict(zip(walkers, colors, strict=True)), default=BLACK)),
        style=border | border_heavy | border_color("slate", 400),
    )


if __name__ == "__main__":
    asyncio.run(app(root()))
