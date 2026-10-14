"""
Mostly static: a grid of bordered metric cards that never change, and one frame counter that changes every frame.

Nearly everything is identical from frame to frame, so this measures the fixed cost of a frame:
work that caches, or reuse of last frame's layout, could skip.
"""

from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import replace
from functools import partial

from benchmarks.harness import Workload
from counterweight.components import Component
from counterweight.components import component
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles.styles import CellStyle
from counterweight.styles.utilities import amber_400
from counterweight.styles.utilities import border
from counterweight.styles.utilities import border_collapse
from counterweight.styles.utilities import border_color
from counterweight.styles.utilities import col
from counterweight.styles.utilities import cyan_400
from counterweight.styles.utilities import fill
from counterweight.styles.utilities import justify_children_space_between
from counterweight.styles.utilities import pad
from counterweight.styles.utilities import row
from counterweight.styles.utilities import slate_100
from counterweight.styles.utilities import slate_400
from counterweight.styles.utilities import text_justify_center

METRICS = (
    ("CPU usage", "23.4%"),
    ("Memory", "1.21 GB"),
    ("Disk read", "44.8 MB/s"),
    ("Disk write", "12.1 MB/s"),
    ("Net in", "8.33 MB/s"),
    ("Net out", "2.17 MB/s"),
    ("Requests/s", "8,421"),
    ("Error rate", "0.02%"),
    ("P50 latency", "18 ms"),
    ("P99 latency", "142 ms"),
    ("Uptime", "14d 6h 22m"),
    ("Active conns", "1,047"),
)


@dataclass(frozen=True, slots=True)
class Model:
    tick: int


def initial() -> Model:
    return Model(tick=0)


def step(model: Model) -> Model:
    return Model(tick=model.tick + 1)


def view(model: Model, card_component: Callable[[str, str], Component]) -> Div:
    return layout(frame_counter(model.tick), card_component)


def layout(counter: Component, card_component: Callable[[str, str], Component]) -> Div:
    """
    Everything but the frame counter, which is passed in so `dashboard-local` can hold its tick elsewhere,
    with each metric card built by `card_component`, so `dashboard-memo` can declare it `memo`.
    """
    return Div(
        style=col | pad(1),
        children=(
            header(),
            Div(style=row | justify_children_space_between, children=(status(), counter)),
            Div(
                style=fill(1) | col | border_collapse,
                children=(
                    Div(
                        style=fill(1) | row | border_collapse,
                        children=tuple(card_component(label, value) for label, value in METRICS[:6]),
                    ),
                    Div(
                        style=fill(1) | row | border_collapse,
                        children=tuple(card_component(label, value) for label, value in METRICS[6:]),
                    ),
                ),
            ),
        ),
    )


@component
def header() -> Text:
    return Text(
        content=(
            Chunk(content="System", style=CellStyle(foreground=amber_400, bold=True)),
            Chunk.space(),
            Chunk(content="Dashboard", style=CellStyle(foreground=cyan_400, bold=True)),
        ),
        style=text_justify_center,
    )


@component
def status() -> Text:
    return Text(content=(Chunk(content="All systems normal", style=CellStyle(foreground=slate_400)),))


@component
def frame_counter(tick: int) -> Text:
    return frame_text(tick)


def frame_text(tick: int) -> Text:
    return Text(content=(Chunk(content=f"Frame: {tick:,}", style=CellStyle(foreground=slate_400)),))


def render_metric_card(label: str, value: str) -> Div:
    return Div(
        style=fill(1) | col | border | border_color("slate", 700) | pad(1),
        children=(
            Text(content=(Chunk(content=label, style=CellStyle(foreground=slate_400)),)),
            Text(content=(Chunk(content=value, style=CellStyle(foreground=slate_100, bold=True)),)),
        ),
    )


metric_card = component(render_metric_card)
memo_metric_card = component(memo=True)(render_metric_card)


WORKLOAD = Workload(
    name="dashboard",
    description=__doc__ or "",
    initial=initial,
    step=step,
    view=partial(view, card_component=metric_card),
    dimensions=(120, 30),
)

MEMO_WORKLOAD = replace(
    WORKLOAD,
    name="dashboard-memo",
    description="""
`dashboard`, with each metric card a `memo` component.

The cards' arguments never change, so every card is reused every frame and only the root and the frame counter re-run:
compared with `dashboard`, this measures what skipping unchanged components saves.
""",
    view=partial(view, card_component=memo_metric_card),
)
