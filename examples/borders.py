import asyncio
from itertools import combinations, cycle

from more_itertools import flatten
from structlog import get_logger

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.hooks import use_ref, use_state
from counterweight.styles import Style
from counterweight.styles.utilities import *

logger = get_logger()

ALL_SIDES: list[Side] = ["top", "bottom", "left", "right"]


@component
def root() -> Div:
    border_kind_cycle_ref = use_ref(cycle(BorderKind))
    border_side_cycle_ref = use_ref(cycle(reversed(list(flatten(combinations(ALL_SIDES, r) for r in range(1, 5))))))

    def advance_border() -> BorderKind:
        return next(border_kind_cycle_ref.current)

    def advance_sides() -> frozenset[Side]:
        return frozenset(next(border_side_cycle_ref.current))

    border_kind, set_border_kind = use_state(advance_border)
    active_sides, set_active_sides = use_state(advance_sides)

    def on_key(event: KeyPressed) -> None:
        match event.key:
            case "k":
                set_border_kind(advance_border())
            case "e":
                set_active_sides(advance_sides())

    logger.debug("Rendering", border_kind=border_kind, active_sides=active_sides)

    return Div(
        style=col | align_children_center | justify_children_space_evenly,
        children=[
            Div(
                style=border_heavy,
                children=[
                    Text(
                        content=f"Border Edge Selection Demo\n{border_kind}\n{', '.join(sorted(active_sides))}",
                        style=border_sides(active_sides)
                        | Style(border_kind=border_kind)
                        | text_justify_center
                        | text_bg("amber", 800),
                    )
                ],
            ),
            Text(
                content="k  cycle border kind\ne  cycle active edges",
                style=border_color("slate", 400) | text("slate", 200) | border_lightrounded | pad_x(2) | pad_y(1),
            ),
        ],
        on_key=on_key,
    )


if __name__ == "__main__":
    asyncio.run(app(root))
