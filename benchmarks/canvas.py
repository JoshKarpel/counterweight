"""
High churn: four half-block canvases of random walkers, where every walker moves every frame.

Nearly every painted cell changes each frame, so caches keyed on content never hit;
this measures raw paint, diff and output throughput.
"""

import random
from dataclasses import dataclass
from itertools import product

from benchmarks.harness import Workload
from counterweight.components import component
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles.styles import COLORS_BY_NAME
from counterweight.styles.styles import CellStyle
from counterweight.styles.styles import Color
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
from counterweight.utils import canvas
from counterweight.utils import clamp

WIDTH = 30
HEIGHT = 30
WALKERS = 30
CANVASES = 4

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
    canvases = tuple(
        walker_canvas(colors, walkers) for colors, walkers in zip(model.colors, model.walkers, strict=True)
    )
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
        content=canvas(width=WIDTH, height=HEIGHT, cells=dict(zip(walkers, colors, strict=True))),
        style=border | border_heavy | border_color("slate", 400),
    )


WORKLOAD = Workload(
    name="canvas",
    description=__doc__ or "",
    initial=initial,
    step=step,
    view=view,
    dimensions=(80, 40),
)
