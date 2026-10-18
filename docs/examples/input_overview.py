import asyncio
from collections.abc import Callable
from datetime import timedelta

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseUp
from counterweight.events import Receiver
from counterweight.geometry import Position
from counterweight.handlers import on_click
from counterweight.hooks import use_state
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import CastSpec
from docs.examples.screenshot_spec import ScreenshotSpec
from docs.examples.screenshot_spec import paced

# --8<-- [start:example]


@component
def button(label: str, action: Callable[[], None]) -> Text:
    return Text(
        content=label,
        style=border | border_lightrounded | pad_x(1) | border_color("indigo", 400),
        on_input=on_click(action),
    )


@component
def root() -> Div:
    count, set_count = use_state(0)

    def increment() -> None:
        set_count(lambda count: count + 1)

    def decrement() -> None:
        set_count(lambda count: count - 1)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key="+"):
                increment()
                return ()
            case KeyPressed(key="-"):
                decrement()
                return ()
            case KeyPressed(key="q"):
                return Quit()
            case _:
                return None

    return Div(
        style=col | align_children_center | justify_children_center | full,
        on_input=on_input,
        children=(
            Text(content=f"Count: {count}"),
            Div(style=row | gap(1), children=(button("-", decrement), button("+", increment))),
            Text(content="Press + or -, or click a button. q quits.", style=text_color("slate", 400)),
        ),
    )


# --8<-- [end:example]


def click(x: int, y: int) -> tuple[MouseDown, MouseUp]:
    return MouseDown(absolute=Position(x, y), button=1), MouseUp(absolute=Position(x, y), button=1)


DIMENSIONS = (44, 7)
PLUS = (24, 3)
MINUS = (19, 3)

KEYS = (KeyPressed(key="+"), KeyPressed(key="+"), KeyPressed(key="+"))
CLICKED = (*KEYS, *click(*MINUS))

SCREENSHOTS = [
    ScreenshotSpec(root(), "input-overview", DIMENSIONS, events=CLICKED),
]

CASTS = [
    CastSpec(
        root(),
        "input-overview",
        DIMENSIONS,
        steps=paced(
            [*KEYS, *click(*MINUS), *click(*PLUS), *click(*PLUS), KeyPressed(key="-")],
            every=timedelta(milliseconds=600),
        ),
    )
]


if __name__ == "__main__":
    asyncio.run(app(root()))
