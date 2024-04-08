import asyncio
from functools import lru_cache
from itertools import cycle

from more_itertools import take
from structlog import get_logger

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.hooks import use_hovered, use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *

logger = get_logger()

long_text = "\n".join(take(20, cycle(("foo", "bar", "baz"))))


@component
def root() -> Div:
    return Div(
        style=col | align_children_center | border_heavy,
        children=[
            Div(
                style=row | align_self_stretch | border_heavy,
                children=[
                    scrollable_text(),
                    scrollable_text(),
                ],
            ),
            Div(
                style=row | align_self_stretch | border_heavy,
                children=[
                    scrollable_text(),
                    scrollable_text(),
                ],
            ),
        ],
    )


@component
def scrollable_text() -> Div | Text:
    offset, set_offset = use_state(0)
    hovered = use_hovered()
    # TODO: content areas extend downwards infinitely right now because they don't get cut off!

    def on_key(e: KeyPressed) -> None:
        if not hovered.border:
            return

        match e.key:
            case Key.Down:
                set_offset(lambda o: clamp(0, o + 1, None))
            case Key.Up:
                set_offset(lambda o: clamp(0, o - 1, None))

    # the problem here seems to be the intermediate div not picking up the height change
    # from two levels above. with no intermediate div the text height gets capped appropriately
    # it is when the flex child content height gets set in the second pass on parents,
    # that doesn't propagate more than one layer down

    # presumably a similar problem for width?

    return Div(
        children=[
            Text(
                on_key=on_key,
                style=border_lightrounded,
                content=long_text,
                offset=(0, offset),
            ),
            Text(
                style=absolute(x=1, y=0),
                content=f" {offset} ",
            ),
        ]
    )

    # return Text(
    #     on_key=on_key,
    #     style=border_lightrounded,
    #     content=long_text,
    # )


@lru_cache(maxsize=2**12)
def clamp(min_: int, val: int, max_: int | None) -> int:
    return max(min_, min(val, max_) if max_ is not None else val)


if __name__ == "__main__":
    asyncio.run(app(root))
