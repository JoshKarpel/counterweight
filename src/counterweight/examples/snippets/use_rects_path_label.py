"""
Hooks: use_rects

Path labels that shorten to fit the width layout gives them.
"""

import asyncio

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import use_rects
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *

PATH = "src/counterweight/hooks/hooks.py"

# --8<-- [start:example]


def shortened(path: str, width: int) -> str:
    """`path` with as many leading directories as it takes to fit in `width` cells replaced by `…`."""
    parts = path.split("/")
    for start in range(len(parts)):
        candidate = "/".join(("…", *parts[start:]) if start else parts)
        if len(candidate) <= width:
            return candidate
    return parts[-1][:width]


@component
def path_label(path: str) -> Text:
    width = use_rects().content.width
    return Text(
        content=shortened(path, width), style=full_width | min_width(0) | text_wrap_none | text_color("amber", 400)
    )


@component
def split() -> Div:
    left_width, set_left_width = use_state(24)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Left):
                set_left_width(lambda width: max(width - 4, 8))
                return ()
            case KeyPressed(key=Key.Right):
                set_left_width(lambda width: min(width + 4, 40))
                return ()
            case _:
                return None

    pane = border | border_lightrounded | pad_x(1)

    return Div(
        style=row,
        on_input=on_input,
        children=(
            Div(style=pane | width(left_width), children=(path_label(PATH),)),
            Div(style=pane | fill(1), children=(path_label(PATH),)),
        ),
    )


# --8<-- [end:example]


ROOTS = (split,)

# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import paced
from counterweight.controls import AdvanceClock
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still

LEFT = KeyPressed(key=Key.Left)
RIGHT = KeyPressed(key=Key.Right)


STILLS = [
    Still("use-rects-path-label", split(), (48, 3), steps=[RIGHT, RIGHT, RIGHT]),
]

DEMOS = [
    Demo(
        "use-rects-path-label",
        split(),
        (48, 3),
        steps=[
            *paced(
                [RIGHT, RIGHT, RIGHT, RIGHT, LEFT, LEFT, LEFT, LEFT, LEFT, LEFT, LEFT],
                pause=AdvanceClock(by=timedelta(milliseconds=500)),
            ),
            AdvanceClock(by=timedelta(seconds=2)),
        ],
    ),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(split()))
