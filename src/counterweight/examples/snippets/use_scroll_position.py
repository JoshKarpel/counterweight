"""
Hooks: use_scroll

A log that shows how far it's scrolled.
"""

import asyncio

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.handlers import scroll_on_wheel
from counterweight.hooks import ElementHandle
from counterweight.hooks import use_scroll
from counterweight.hooks import use_state
from counterweight.styles.utilities import *

LINES = tuple(f"{n:>2} GET /items/{n * 37 % 1000} {404 if n % 7 == 0 else 200}" for n in range(1, 31))

# --8<-- [start:example]


@component
def document(lines: tuple[str, ...] = LINES) -> Div:
    body, _ = use_state(ElementHandle)
    scroll = use_scroll(body)

    first = scroll.offset.y + 1
    last = min(scroll.offset.y + scroll.view_height, len(lines))
    percent = 100 * scroll.offset.y // scroll.max_offset.y if scroll.max_offset.y else 100

    return Div(
        style=col | border | border_lightrounded | size(30, 9),
        children=(
            Text(
                content=f" Lines {first}-{last} of {len(lines)} ({percent}%) ",
                style=position_absolute | inset_top(-1) | inset_left(1) | clip_to_border | text_color("amber", 400),
            ),
            Div(
                style=fill(1) | col | pad_x(1) | overflow_y_scroll,
                handle=body,
                on_input=scroll_on_wheel(),
                children=tuple(Text(content=line) for line in lines),
            ),
            Text(
                content=f" ↓ {len(lines) - last} more " if last < len(lines) else "",
                style=position_absolute | inset_bottom(-1) | inset_right(1) | clip_to_border | text_color("slate", 400),
            ),
        ),
    )


# --8<-- [end:example]


ROOTS = (document,)

# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import paced
from counterweight.controls import AdvanceClock
from counterweight.events import MouseScrolledDown
from counterweight.events import MouseScrolledUp
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still
from counterweight.geometry import Position

DOWN = MouseScrolledDown(absolute=Position(5, 4))
UP = MouseScrolledUp(absolute=Position(5, 4))


STILLS = [
    Still("use-scroll-position", document(LINES), (30, 9), steps=[DOWN, DOWN]),
]

DEMOS = [
    Demo(
        "use-scroll-position",
        document(LINES),
        (30, 9),
        steps=[
            *paced([*[DOWN] * 9, *[UP] * 9], pause=AdvanceClock(by=timedelta(milliseconds=400))),
            AdvanceClock(by=timedelta(seconds=2)),
        ],
    ),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(document()))
