import asyncio
from itertools import combinations, product
from random import randint

from more_itertools import flatten
from structlog import get_logger

from counterweight.app import run_app
from counterweight.components import component
from counterweight.control import Control
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *
from examples.canvas import clamp

logger = get_logger()

E = list(product(reversed(list(flatten(combinations(BorderEdge, r) for r in range(1, 5)))), repeat=4))


@component
def root() -> Div:
    border_edge_idx, set_border_edge_idx = use_state(0)

    (top_left, top_right, bottom_left, bottom_right) = E[border_edge_idx]

    def on_key(event: KeyPressed) -> Control | None:
        match event.key:
            case Key.Right:
                set_border_edge_idx(lambda i: clamp(0, i + 1, len(E) - 1))
            case Key.Left:
                set_border_edge_idx(lambda i: clamp(0, i - 1, len(E) - 1))
            case "r":
                set_border_edge_idx(randint(0, len(E) - 1))
            case Key.Space:
                return Control.ToggleBorderHealing

        return None

    return Div(
        style=col | align_children_center | justify_children_center,
        children=[
            Div(
                style=align_children_end,
                children=[
                    box(e=frozenset(top_left)),
                    box(e=frozenset(top_right)),
                ],
            ),
            Div(
                style=align_children_start,
                children=[
                    box(e=frozenset(bottom_left)),
                    box(e=frozenset(bottom_right)),
                ],
            ),
        ],
        on_key=on_key,
    )


@component
def box(e: frozenset[BorderEdge]) -> Text:
    return Text(
        content=f"Border Join Demo\n{', '.join(be.name for be in e)}",
        style=Style(border=Border(edges=e)) | text_justify_center | text_bg_amber_800,
    )


if __name__ == "__main__":
    asyncio.run(run_app(root))
    # print(len(E))
    # print(E[0])
