import asyncio
from itertools import combinations, product
from random import randint
from typing import Literal

import waxy
from more_itertools import flatten
from structlog import get_logger

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import AnyControl, ToggleBorderHealing
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles import Style
from counterweight.styles.utilities import *
from examples.canvas import clamp

logger = get_logger()

Side = Literal["top", "bottom", "left", "right"]
ALL_SIDES: list[Side] = ["top", "bottom", "left", "right"]

E = list(product(reversed(list(flatten(combinations(ALL_SIDES, r) for r in range(1, 5)))), repeat=4))


@component
def root() -> Div:
    border_edge_idx, set_border_edge_idx = use_state(0)

    (top_left, top_right, bottom_left, bottom_right) = E[border_edge_idx]

    def on_key(event: KeyPressed) -> AnyControl | None:
        match event.key:
            case Key.Right:
                set_border_edge_idx(lambda i: clamp(0, i + 1, len(E) - 1))
            case Key.Left:
                set_border_edge_idx(lambda i: clamp(0, i - 1, len(E) - 1))
            case "r":
                set_border_edge_idx(randint(0, len(E) - 1))
            case Key.Space:
                return ToggleBorderHealing()

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
def box(e: frozenset[Side]) -> Text:
    return Text(
        content=f"Border Join Demo\n{', '.join(sorted(e))}",
        style=Style(
            layout=waxy.Style(
                border_top=waxy.Length(1 if "top" in e else 0),
                border_bottom=waxy.Length(1 if "bottom" in e else 0),
                border_left=waxy.Length(1 if "left" in e else 0),
                border_right=waxy.Length(1 if "right" in e else 0),
            ),
        )
        | text_justify_center
        | text_bg_amber_800,
    )


if __name__ == "__main__":
    asyncio.run(app(root))
    # print(len(E))
    # print(E[0])
