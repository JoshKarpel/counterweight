import asyncio
import sys
from datetime import timedelta

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import use_state
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import CastSpec
from docs.examples.screenshot_spec import ScreenshotSpec
from docs.examples.screenshot_spec import paced

# --8<-- [start:counter]


@component
def counter() -> Div:
    count, set_count = use_state(0)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key="+"):
                set_count(lambda count: count + 1)
                return ()
            case KeyPressed(key="-"):
                set_count(lambda count: count - 1)
                return ()
            case KeyPressed(key="0"):
                set_count(0)
                return ()
            case _:
                return None

    return Div(
        style=col | border | border_lightrounded | pad_x(1),
        on_input=on_input,
        children=(
            Text(content=f"Count: {count}", style=text_color("amber", 400)),
            Text(content="+ and - count, 0 resets", style=text_color("slate", 400)),
        ),
    )


# --8<-- [end:counter]

# --8<-- [start:twice]


@component
def plus_two() -> Div:
    by_value, set_by_value = use_state(0)
    by_function, set_by_function = use_state(0)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key="+"):
                set_by_value(by_value + 1)
                set_by_value(by_value + 1)
                set_by_function(lambda n: n + 1)
                set_by_function(lambda n: n + 1)
                return ()
            case _:
                return None

    return Div(
        style=col | border | border_lightrounded | pad_x(1),
        on_input=on_input,
        children=(
            Text(content=f"By value:    {by_value}", style=text_color("red", 400)),
            Text(content=f"By function: {by_function}", style=text_color("emerald", 400)),
        ),
    )


# --8<-- [end:twice]

PLUS = KeyPressed(key="+")
MINUS = KeyPressed(key="-")

SCREENSHOTS = [
    ScreenshotSpec(counter(), "use-state-counter", (30, 4), events=[PLUS, PLUS, PLUS]),
    ScreenshotSpec(plus_two(), "use-state-plus-two", (30, 4), events=[PLUS, PLUS, PLUS]),
]

CASTS = [
    CastSpec(
        counter(),
        "use-state-counter",
        (30, 4),
        steps=paced(
            [PLUS, PLUS, PLUS, PLUS, MINUS, PLUS, KeyPressed(key="0"), PLUS], every=timedelta(milliseconds=500)
        ),
    ),
]


if __name__ == "__main__":
    roots = {root.__name__: root for root in (counter, plus_two)}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else counter()))
