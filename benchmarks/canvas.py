"""
High churn: four half-block canvases of random walkers, where every walker moves every frame,
each drawn as a `Text` of half-block chunks.

Nearly every painted cell changes each frame, so caches keyed on content never hit;
this measures raw paint, diff and output throughput, and laying out text that's really a picture.
"""

import random
from dataclasses import dataclass
from itertools import product

from benchmarks.harness import Workload
from counterweight.components import Component
from counterweight.components import component
from counterweight.elements import NEWLINE
from counterweight.elements import Canvas
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.geometry import Position
from counterweight.geometry import clamp
from counterweight.painters._pixels import HalfBlocks
from counterweight.painters._pixels import Pixels
from counterweight.styles._styles import COLORS_BY_NAME
from counterweight.styles._styles import CellStyle
from counterweight.styles._styles import Color
from counterweight.styles.utilities import align_children_center
from counterweight.styles.utilities import amber_600
from counterweight.styles.utilities import border
from counterweight.styles.utilities import border_color
from counterweight.styles.utilities import border_heavy
from counterweight.styles.utilities import col
from counterweight.styles.utilities import cyan_600
from counterweight.styles.utilities import justify_children_space_evenly
from counterweight.styles.utilities import pink_600
from counterweight.styles.utilities import row
from counterweight.styles.utilities import text_justify_center

WIDTH = 30
HEIGHT = 30
WALKERS = 30
CANVASES = 4

BLACK = Color.from_name("black")

MOVES = [(dx, dy) for dx, dy in product((-1, 0, 1), repeat=2) if (dx, dy) != (0, 0)]

type Walkers = tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class Model:
    tick: int
    colors: tuple[tuple[Color, ...], ...]
    walkers: tuple[Walkers, ...]


def initial() -> Model:
    rng = random.Random(0)
    palette = list(COLORS_BY_NAME.values())
    return Model(
        tick=0,
        colors=tuple(tuple(rng.sample(palette, k=WALKERS)) for _ in range(CANVASES)),
        walkers=tuple(
            tuple((rng.randrange(WIDTH), rng.randrange(HEIGHT)) for _ in range(WALKERS)) for _ in range(CANVASES)
        ),
    )


def step(model: Model) -> Model:
    rng = random.Random(model.tick)
    return Model(
        tick=model.tick + 1,
        colors=model.colors,
        walkers=tuple(walk(walkers, rng) for walkers in model.walkers),
    )


def walk(walkers: Walkers, rng: random.Random) -> Walkers:
    return tuple(
        (clamp(0, x + dx, WIDTH - 1), clamp(0, y + dy, HEIGHT - 1))
        for (x, y), (dx, dy) in zip(walkers, [rng.choice(MOVES) for _ in walkers], strict=True)
    )


def view(model: Model) -> Div:
    return layout(
        tuple(walker_canvas(colors, walkers) for colors, walkers in zip(model.colors, model.walkers, strict=True))
    )


def element_view(model: Model) -> Div:
    return layout(
        tuple(
            walker_canvas_element(colors, walkers) for colors, walkers in zip(model.colors, model.walkers, strict=True)
        )
    )


def layout(canvases: tuple[Component, ...]) -> Div:
    return Div(
        style=col | align_children_center | justify_children_space_evenly,
        children=(
            header(),
            Div(style=row | justify_children_space_evenly, children=canvases[:2]),
            Div(style=row | justify_children_space_evenly, children=canvases[2:]),
        ),
    )


@component
def header() -> Text:
    return Text(
        content=(
            Chunk(content="Canvas", style=CellStyle(foreground=amber_600)),
            Chunk.space(),
            Chunk(content="Demo", style=CellStyle(foreground=cyan_600)),
            Chunk.newline(),
            Chunk(content="App", style=CellStyle(foreground=pink_600)),
        ),
        style=text_justify_center,
    )


@component
def walker_canvas(colors: tuple[Color, ...], walkers: Walkers) -> Text:
    return Text(
        content=half_block_chunks(dict(zip(walkers, colors, strict=True))),
        style=border | border_heavy | border_color("slate", 400),
    )


def half_block_chunks(pixels: dict[tuple[int, int], Color]) -> tuple[Chunk, ...]:
    """The `WIDTH` by `HEIGHT` pixels as rows of half-block chunks, black but for `pixels`."""
    rows = (
        [
            Chunk(
                content="▀",
                style=CellStyle(foreground=pixels.get((x, y), BLACK), background=pixels.get((x, y + 1), BLACK)),
            )
            for x in range(WIDTH)
        ]
        for y in range(0, HEIGHT, 2)
    )
    return tuple(chunk for i, row in enumerate(rows) for chunk in ([NEWLINE] if i else []) + row)


@component
def walker_canvas_element(colors: tuple[Color, ...], walkers: Walkers) -> Canvas:
    pixels = Pixels.from_points(
        WIDTH, HEIGHT, {Position(x, y): color for (x, y), color in zip(walkers, colors, strict=True)}, default=BLACK
    )
    return Canvas(painter=HalfBlocks(pixels), style=border | border_heavy | border_color("slate", 400))


WORKLOAD = Workload(
    name="canvas",
    description=__doc__ or "",
    initial=initial,
    step=step,
    view=view,
    dimensions=(80, 40),
)

ELEMENT_WORKLOAD = Workload(
    name="canvas-element",
    description="`canvas`, with each canvas drawn by a `Canvas` element and a `HalfBlocks` painter rather than as text.",
    initial=initial,
    step=step,
    view=element_view,
    dimensions=(80, 40),
)
