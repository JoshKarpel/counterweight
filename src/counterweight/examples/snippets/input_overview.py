"""
Input handling: Input

Light switches turned on and off with keys and clicks.
"""

import asyncio
from collections.abc import Callable
from functools import partial

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.handlers import on_click
from counterweight.hooks import use_state
from counterweight.styles.utilities import *

# --8<-- [start:example]

ROOMS = ("Kitchen", "Hall", "Porch")


@component
def switch(room: str, is_on: bool, toggle: Callable[[], None]) -> Text:
    return Text(
        content=f"{'●' if is_on else '○'} {room}",
        style=border
        | border_lightrounded
        | pad_x(1)
        | (border_color("amber", 400) | text_color("amber", 300) if is_on else border_color("slate", 600)),
        on_input=on_click(toggle),
    )


@component
def root() -> Div:
    lit, set_lit = use_state(frozenset[str]())

    def toggle(room: str) -> None:
        set_lit(lambda lit: lit ^ {room})

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key="1" | "2" | "3" as key):
                toggle(ROOMS[int(key) - 1])
                return ()
            case KeyPressed(key="0"):
                set_lit(frozenset())
                return ()
            case _:
                return None

    return Div(
        style=col | align_children_center | justify_children_center | full,
        on_input=on_input,
        children=(
            Div(style=row | gap(1), children=tuple(switch(room, room in lit, partial(toggle, room)) for room in ROOMS)),
            Text(content="Press 1, 2 or 3, or click a switch. 0 turns them all off.", style=text_color("slate", 400)),
        ),
    )


# --8<-- [end:example]


ROOTS = (root,)

# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import paced
from counterweight.controls import AdvanceClock
from counterweight.events import MouseDown
from counterweight.events import MouseUp
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still
from counterweight.geometry import Position


def click(x: int, y: int) -> tuple[MouseDown, MouseUp]:
    return MouseDown(absolute=Position(x, y), button=1), MouseUp(absolute=Position(x, y), button=1)


DIMENSIONS = (60, 6)
KITCHEN = (12, 2)
PORCH = (42, 2)

KEYS = (KeyPressed(key="1"), KeyPressed(key="2"))
CLICKED = (*KEYS, *click(*PORCH))

STILLS = [
    Still("input-overview", root(), DIMENSIONS, steps=CLICKED),
]

DEMOS = [
    Demo(
        "input-overview",
        root(),
        DIMENSIONS,
        steps=[
            *paced(
                [*KEYS, *click(*PORCH), *click(*KITCHEN), KeyPressed(key="2"), KeyPressed(key="0")],
                pause=AdvanceClock(by=timedelta(milliseconds=600)),
            ),
            AdvanceClock(by=timedelta(seconds=2)),
        ],
    )
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(root()))
