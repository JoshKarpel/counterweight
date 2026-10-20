"""
Components: Keys

A to-do list whose rows keep their own state, with and without keys, as items are removed.
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
from counterweight.handlers import on_click
from counterweight.hooks import use_state
from counterweight.styles.utilities import *

# --8<-- [start:row]


@component
def todo_row(title: str) -> Text:
    done, set_done = use_state(False)

    return Text(content=f"[{'x' if done else ' '}] {title}", on_input=on_click(lambda: set_done(not done)))


# --8<-- [end:row]

# --8<-- [start:unkeyed]


@component
def todo_list(titles: tuple[str, ...]) -> Div:
    return Div(style=col, children=tuple(todo_row(title) for title in titles))


# --8<-- [end:unkeyed]

# --8<-- [start:keyed]


@component
def keyed_todo_list(titles: tuple[str, ...]) -> Div:
    return Div(style=col, children=tuple(todo_row(title).with_key(title) for title in titles))


# --8<-- [end:keyed]

# --8<-- [start:side-by-side]

TITLES: tuple[str, ...] = ("a", "b", "c", "d")


@component
def side_by_side() -> Div:
    titles, set_titles = use_state(TITLES)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key="x"):
                set_titles(lambda t: t[1:])
                return ()
            case KeyPressed(key="r"):
                set_titles(lambda t: t[-1:] + t[:-1])
                return ()
            case _:
                return None

    return Div(
        style=col | gap(1),
        on_input=on_input,
        children=(
            Div(
                style=row | gap(2),
                children=(
                    Div(
                        style=col | width(18) | border | pad_x(1),
                        children=(Text(content="without keys", style=text_color("rose", 400)), todo_list(titles)),
                    ),
                    Div(
                        style=col | width(18) | border | pad_x(1),
                        children=(Text(content="with keys", style=text_color("emerald", 400)), keyed_todo_list(titles)),
                    ),
                ),
            ),
            Text(content="click: check  x: remove the first  r: rotate", style=text_color("slate", 400)),
        ),
    )


# --8<-- [end:side-by-side]


ROOTS = (side_by_side,)

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


CHECK_A_IN_BOTH = (*click(3, 2), *click(23, 2))
REMOVE_FIRST = KeyPressed(key="x")
ROTATE = KeyPressed(key="r")

STILLS = [
    Still("components-keys-checked", side_by_side(), (46, 9), steps=CHECK_A_IN_BOTH),
    Still("components-keys-removed", side_by_side(), (46, 9), steps=(*CHECK_A_IN_BOTH, REMOVE_FIRST)),
]

DEMOS = [
    Demo(
        "components-keys",
        side_by_side(),
        (46, 9),
        steps=[
            *paced(
                [*CHECK_A_IN_BOTH, *click(3, 3), *click(23, 3), ROTATE, ROTATE, ROTATE],
                pause=AdvanceClock(by=timedelta(milliseconds=700)),
            ),
            AdvanceClock(by=timedelta(seconds=2)),
        ],
    )
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(side_by_side()))
