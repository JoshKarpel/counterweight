"""
Gradients three ways: a panel whose gradients never change, one whose gradient turns a few degrees every frame,
and the background of a tall text in a scroll container that scrolls a row every frame.

The still panel's gradients should cost what solid colors do once they're drawn,
the turning one rebuilds its field and rewrites its cells every frame,
and the scrolled one rebuilds the text's cells in view on every step.
"""

from dataclasses import dataclass

import waxy

from benchmarks.harness import Workload
from counterweight.components import component
from counterweight.controls import ScrollBy
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.focus import ElementHandle
from counterweight.gradients import conic_gradient
from counterweight.gradients import linear_gradient
from counterweight.gradients import radial_gradient
from counterweight.styles._styles import CellStyle
from counterweight.styles._styles import Style
from counterweight.styles.utilities import amber_400
from counterweight.styles.utilities import blue_500
from counterweight.styles.utilities import border
from counterweight.styles.utilities import border_light
from counterweight.styles.utilities import col
from counterweight.styles.utilities import emerald_400
from counterweight.styles.utilities import full
from counterweight.styles.utilities import gray_950
from counterweight.styles.utilities import grow
from counterweight.styles.utilities import pad
from counterweight.styles.utilities import pink_500
from counterweight.styles.utilities import red_500
from counterweight.styles.utilities import row
from counterweight.styles.utilities import sky_700
from counterweight.styles.utilities import slate_50
from counterweight.styles.utilities import violet_600

LOG = ElementHandle()
LOG_ROWS = 2000


@dataclass(frozen=True, slots=True)
class Model:
    tick: int


def initial() -> Model:
    return Model(tick=0)


def step(model: Model) -> Model:
    return Model(tick=model.tick + 1)


def view(model: Model) -> Div:
    return Div(
        style=row | full,
        children=(
            Div(style=col | grow(1), children=(still(), turning(model.tick))),
            log(),
        ),
    )


@component
def still() -> Div:
    return Div(
        style=grow(1)
        | border
        | border_light
        | pad(1)
        | Style(
            content_color=linear_gradient(sky_700, gray_950, angle=160),
            padding_color=radial_gradient(violet_600, gray_950),
            border_style=CellStyle(foreground=linear_gradient(amber_400, pink_500, to="right")),
        ),
        children=(
            Text(
                content=(
                    Chunk(content="Gradients that hold still "),
                    Chunk(content="cost what solid colors do", style=CellStyle(foreground=emerald_400)),
                ),
                style=Style(text_style=CellStyle(foreground=linear_gradient(slate_50, amber_400, to="right"))),
            ),
        ),
    )


@component
def turning(tick: int) -> Div:
    return Div(
        style=grow(1)
        | Style(content_color=conic_gradient(red_500, amber_400, emerald_400, blue_500, red_500, start=3 * tick)),
    )


LOG_TEXT = "\n".join(f"line {index}" for index in range(LOG_ROWS))


@component
def log() -> Div:
    return Div(
        style=grow(1) | Style(layout=waxy.Style(overflow_y=waxy.Overflow.Scroll)),
        handle=LOG,
        children=(
            Text(
                content=LOG_TEXT,
                style=Style(
                    text_style=CellStyle(background=linear_gradient(blue_500, violet_600, pink_500, amber_400)),
                ),
            ),
        ),
    )


WORKLOAD = Workload(
    name="gradients",
    description=__doc__ or "",
    initial=initial,
    step=step,
    view=view,
    dimensions=(160, 50),
    cycled_interjections=(ScrollBy(LOG, y=1),),
)
