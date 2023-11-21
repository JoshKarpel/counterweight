import asyncio
from itertools import combinations, cycle

from more_itertools import flatten
from structlog import get_logger

from reprisal.app import app
from reprisal.components import Div, Text, component
from reprisal.events import KeyPressed
from reprisal.hooks import use_ref, use_state
from reprisal.styles.utilities import *

logger = get_logger()


@component
def root() -> Div:
    border_kind_cycle_ref = use_ref(cycle(BorderKind))
    border_edge_cycle_ref = use_ref(
        cycle(flatten(combinations(("top", "right", "bottom", "left"), r) for r in range(1, 5)))
    )

    def advance_border() -> BorderKind:
        return next(border_kind_cycle_ref.current)

    def advance_edges() -> set[str]:
        return frozenset(next(border_edge_cycle_ref.current))

    border_kind, set_border_kind = use_state(advance_border)
    border_edges, set_border_edges = use_state(advance_edges)

    def on_key(event: KeyPressed) -> None:
        match event.key:
            case "k":
                set_border_kind(advance_border())
            case "e":
                set_border_edges(advance_edges())

    logger.debug("Rendering", border_kind=border_kind, border_edges=border_edges)

    return Div(
        style=col | align_children_center | justify_children_space_evenly,
        children=[
            Div(
                style=border_heavy,
                children=[
                    Text(
                        content=f"Border Edge Selection Demo\n{border_kind}\n{border_edges}",
                        style=Style(border=Border(kind=border_kind, edges=border_edges))
                        | text_justify_center
                        | text_bg_amber_800,
                    )
                ],
            )
        ],
        on_key=on_key,
    )


asyncio.run(app(root))
