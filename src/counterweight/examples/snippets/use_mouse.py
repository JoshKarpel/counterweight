"""
Hooks: use_mouse

The pointer's position, how it moved, and the button held.
"""

import asyncio

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.hooks import use_mouse
from counterweight.styles.utilities import *

# --8<-- [start:example]


@component
def pointer() -> Div:
    mouse = use_mouse()
    is_on_screen = mouse.absolute.x >= 0

    return Div(
        style=full,
        children=(
            Text(
                content=(
                    f"At {mouse.absolute.x},{mouse.absolute.y}"
                    f", moved {mouse.motion.x:+},{mouse.motion.y:+}"
                    f", button {mouse.button}"
                ),
                style=text_color("slate", 400),
            ),
            *(
                (
                    Text(
                        content="●" if mouse.button is not None else "◆",
                        style=position_absolute
                        | inset_left(mouse.absolute.x)
                        | inset_top(mouse.absolute.y)
                        | text_color("red" if mouse.button is not None else "amber", 400),
                    ),
                )
                if is_on_screen
                else ()
            ),
        ),
    )


# --8<-- [end:example]


ROOTS = (pointer,)

# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import paced
from counterweight.events import MouseDown
from counterweight.events import MouseMoved
from counterweight.events import MouseUp
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still
from counterweight.geometry import Position


def path(start: Position, end: Position, moves: int, button: int | None) -> list[MouseMoved]:
    """`moves` even steps of the pointer from just past `start` to `end`, as a hand moves the mouse."""
    return [
        MouseMoved(
            absolute=Position(start.x + (end.x - start.x) * step // moves, start.y + (end.y - start.y) * step // moves),
            button=button,
        )
        for step in range(1, moves + 1)
    ]


STILLS = [
    Still(
        "use-mouse",
        pointer(),
        (40, 8),
        steps=[
            MouseMoved(absolute=Position(10, 3), button=None),
            MouseMoved(absolute=Position(12, 4), button=None),
        ],
    ),
    Still(
        "use-mouse-pressed",
        pointer(),
        (40, 8),
        steps=[
            MouseMoved(absolute=Position(10, 3), button=None),
            MouseDown(absolute=Position(10, 3), button=1),
            MouseMoved(absolute=Position(13, 5), button=1),
        ],
    ),
]

DEMOS = [
    Demo(
        "use-mouse",
        pointer(),
        (40, 8),
        steps=[
            *paced(
                [
                    *path(Position(2, 6), Position(14, 2), moves=12, button=None),
                    MouseDown(absolute=Position(14, 2), button=1),
                    *path(Position(14, 2), Position(30, 6), moves=10, button=1),
                    MouseUp(absolute=Position(30, 6), button=1),
                    *path(Position(30, 6), Position(36, 3), moves=6, button=None),
                ],
                every=timedelta(milliseconds=60),
            ),
        ],
    )
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(pointer()))
