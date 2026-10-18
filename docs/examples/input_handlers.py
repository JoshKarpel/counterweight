import asyncio
from collections.abc import Callable
from datetime import timedelta
from functools import partial

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseMoved
from counterweight.events import MouseUp
from counterweight.events import Receiver
from counterweight.geometry import Position
from counterweight.handlers import clear_focus
from counterweight.handlers import each
from counterweight.handlers import first
from counterweight.handlers import focus_receiver_on_press
from counterweight.handlers import on_click
from counterweight.handlers import tab_focus
from counterweight.hooks import use_focus
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles import Style
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import CastSpec
from docs.examples.screenshot_spec import ScreenshotSpec
from docs.examples.screenshot_spec import paced

# --8<-- [start:example]

FRUITS = ("Apples", "Pears", "Plums")


def button_style(is_focused: bool) -> Style:
    ring = border_color("amber", 400) | text_color("amber", 200) if is_focused else border_color("slate", 600)
    return border | border_lightrounded | pad_x(1) | ring


@component
def fruit_button(fruit: str, add: Callable[[], None]) -> Text:
    focus = use_focus()

    def add_on_enter(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Enter):
                add()
                return ()
            case _:
                return None

    return Text(
        content=fruit,
        style=button_style(focus.is_focused),
        on_input=first(add_on_enter, each(on_click(add), focus_receiver_on_press)),
    )


@component
def basket() -> Div:
    counts, set_counts = use_state(lambda: dict.fromkeys(FRUITS, 0))

    def add(fruit: str) -> None:
        set_counts(lambda counts: {**counts, fruit: counts[fruit] + 1})

    def empty() -> None:
        set_counts(dict.fromkeys(FRUITS, 0))

    def shortcuts(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key="q"):
                return Quit()
            case _:
                return None

    return Div(
        style=col | full | pad_x(1),
        on_input=first(shortcuts, tab_focus, clear_focus),
        children=(
            Div(
                style=row | gap(1),
                children=(
                    *(fruit_button(fruit, partial(add, fruit)) for fruit in FRUITS),
                    Text(content="Empty", style=button_style(False), on_input=each(on_click(empty), clear_focus)),
                ),
            ),
            Text(content=" · ".join(f"{fruit}: {counts[fruit]}" for fruit in FRUITS)),
            Text(content="Tab moves focus, Enter adds the focused fruit, q quits", style=text_color("slate", 400)),
        ),
    )


# --8<-- [end:example]


def press(x: int, y: int) -> tuple[MouseDown, MouseUp]:
    return MouseDown(absolute=Position(x, y), button=1), MouseUp(absolute=Position(x, y), button=1)


DIMENSIONS = (60, 6)
TAB = KeyPressed(key=Key.Tab)
ENTER = KeyPressed(key=Key.Enter)
APPLES = (4, 1)
PLUMS = (25, 1)
EMPTY = (35, 1)
BACKGROUND = (50, 1)

TABBED = (TAB, TAB, ENTER, ENTER)
PRESSED = (*TABBED, *press(*PLUMS))
RELEASED_OUTSIDE = (
    *PRESSED,
    MouseDown(absolute=Position(*APPLES), button=1),
    MouseMoved(absolute=Position(4, 4), button=1),
    MouseUp(absolute=Position(4, 4), button=1),
)
BLURRED = (*RELEASED_OUTSIDE, *press(*BACKGROUND))
EMPTIED = (*PRESSED, *press(*EMPTY))

SCREENSHOTS = [
    ScreenshotSpec(basket(), "input-handlers-tab", DIMENSIONS, events=TABBED),
    ScreenshotSpec(basket(), "input-handlers-press", DIMENSIONS, events=PRESSED),
    ScreenshotSpec(basket(), "input-handlers-release-outside", DIMENSIONS, events=RELEASED_OUTSIDE),
    ScreenshotSpec(basket(), "input-handlers-blur", DIMENSIONS, events=BLURRED),
    ScreenshotSpec(basket(), "input-handlers-empty", DIMENSIONS, events=EMPTIED),
]

CASTS = [
    CastSpec(
        basket(),
        "input-handlers",
        DIMENSIONS,
        steps=paced([*BLURRED, *press(*PLUMS), *press(*EMPTY)], every=timedelta(milliseconds=700)),
    )
]


if __name__ == "__main__":
    asyncio.run(app(basket()))
