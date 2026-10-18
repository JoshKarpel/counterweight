import asyncio
from datetime import timedelta

from counterweight.app import app
from counterweight.autopilot import Wait
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import MouseDown
from counterweight.events import MouseMoved
from counterweight.events import MouseUp
from counterweight.geometry import Position
from counterweight.hooks import use_mouse
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import CastSpec
from docs.examples.screenshot_spec import ScreenshotSpec
from docs.examples.screenshot_spec import paced

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

# use_mouse subscribes in an effect, and effects only start while the app waits for something,
# which an autopilot that hands it a step every frame never does; a moment's wait lets it subscribe.
SUBSCRIBE = Wait(timedelta(milliseconds=1))


def path(start: Position, end: Position, moves: int, button: int | None) -> list[MouseMoved]:
    """`moves` even steps of the pointer from just past `start` to `end`, as a hand moves the mouse."""
    return [
        MouseMoved(
            absolute=Position(start.x + (end.x - start.x) * step // moves, start.y + (end.y - start.y) * step // moves),
            button=button,
        )
        for step in range(1, moves + 1)
    ]


SCREENSHOTS = [
    ScreenshotSpec(
        pointer(),
        "use-mouse",
        (40, 8),
        events=[
            SUBSCRIBE,
            MouseMoved(absolute=Position(10, 3), button=None),
            MouseMoved(absolute=Position(12, 4), button=None),
        ],
    ),
    ScreenshotSpec(
        pointer(),
        "use-mouse-pressed",
        (40, 8),
        events=[
            SUBSCRIBE,
            MouseMoved(absolute=Position(10, 3), button=None),
            MouseDown(absolute=Position(10, 3), button=1),
            MouseMoved(absolute=Position(13, 5), button=1),
        ],
    ),
]

CASTS = [
    CastSpec(
        pointer(),
        "use-mouse",
        (40, 8),
        steps=[
            SUBSCRIBE,
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


if __name__ == "__main__":
    asyncio.run(app(pointer()))
