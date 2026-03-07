import asyncio
from itertools import combinations

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
BORDER_KINDS: list[BorderKind] = list(BorderKind)
SIDE_COMBOS: list[tuple[Side, ...]] = list(flatten(combinations(ALL_SIDES, r) for r in range(1, 5)))
FULL_SIDES_IDX: int = SIDE_COMBOS.index(tuple(ALL_SIDES))


@component
def root() -> Div:
    border_kind_idx = use_ref(0)
    border_side_idx = use_ref(FULL_SIDES_IDX)

    border_kind, set_border_kind = use_state(lambda: BORDER_KINDS[0])
    active_sides, set_active_sides = use_state(lambda: frozenset(SIDE_COMBOS[FULL_SIDES_IDX]))

    def on_key(event: KeyPressed) -> None:
        match event.key:
            case "k":
                border_kind_idx.current = (border_kind_idx.current + 1) % len(BORDER_KINDS)
                set_border_kind(BORDER_KINDS[border_kind_idx.current])
            case "K":
                border_kind_idx.current = (border_kind_idx.current - 1) % len(BORDER_KINDS)
                set_border_kind(BORDER_KINDS[border_kind_idx.current])
            case "e":
                border_side_idx.current = (border_side_idx.current + 1) % len(SIDE_COMBOS)
                set_active_sides(frozenset(SIDE_COMBOS[border_side_idx.current]))
            case "E":
                border_side_idx.current = (border_side_idx.current - 1) % len(SIDE_COMBOS)
                set_active_sides(frozenset(SIDE_COMBOS[border_side_idx.current]))

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
                content="k/K  cycle border kind\ne/E  cycle active edges",
                style=border_color("slate", 400) | text("slate", 200) | border_lightrounded | pad_x(2),
            ),
        ],
        on_key=on_key,
    )


if __name__ == "__main__":
    asyncio.run(app(root))
