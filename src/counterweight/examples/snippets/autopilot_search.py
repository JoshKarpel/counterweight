"""
Autopilot: Driving an app

An autopilot typing into a fruit search, paced as a person types, with chapters marked for its recording.
"""

import asyncio
from collections.abc import Iterable
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from pathlib import Path

from counterweight.app import app
from counterweight.asciicast import Recording
from counterweight.autopilot import AutopilotStep
from counterweight.autopilot import paced
from counterweight.clock import FrozenClock
from counterweight.components import component
from counterweight.controls import Marker
from counterweight.controls import Quit
from counterweight.controls import ScrollBy
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.handlers import first
from counterweight.handlers import focus_receiver_on_press
from counterweight.handlers import scroll_on_wheel
from counterweight.headless import use_text_input
from counterweight.hooks import ElementHandle
from counterweight.hooks import Setter
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles import CellStyle
from counterweight.styles.utilities import *

# The fruit search from the `use_text_input` page, which this page drives.

FRUITS = ("apple", "banana", "cherry", "grape", "lemon", "mango", "orange", "papaya")

CURSOR = (text_color("slate", 900) | text_bg("amber", 300)).text_style


@component
def search_box(query: str, set_query: Setter[str]) -> Text:
    field = use_text_input(query, set_query, auto_focus=True)
    cursor = CURSOR if field.focus.is_focused else CellStyle()
    return Text(
        content=(
            Chunk(content="search: ", style=text_color("amber", 400).text_style),
            Chunk(content=field.before_cursor),
            Chunk(content=field.at_cursor, style=cursor),
            Chunk(content=field.after_cursor),
        ),
        on_input=first(field.on_input, focus_receiver_on_press),
    )


@component
def search() -> Div:
    query, set_query = use_state("")
    results, _ = use_state(ElementHandle)
    matches = [fruit for fruit in FRUITS if query in fruit]

    def scroll_results(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Up):
                return ScrollBy(results, y=-1)
            case KeyPressed(key=Key.Down):
                return ScrollBy(results, y=1)
            case _:
                return None

    return Div(
        style=col | gap(1),
        on_input=scroll_results,
        children=(
            search_box(query, set_query),
            Div(
                style=col | max_height(5) | overflow_y_scroll,
                handle=results,
                on_input=scroll_on_wheel(1),
                children=(Text(content="\n".join(matches) or "no matches", style=text_color("slate", 400)),),
            ),
        ),
    )


# --8<-- [start:chapters]

PAUSE = timedelta(milliseconds=400)


def chapter(label: str, steps: Iterable[AutopilotStep]) -> list[AutopilotStep]:
    return [Marker(label), *paced(steps, every=PAUSE, hold=PAUSE)]


DEMO = [
    *chapter("Scroll the results", [KeyPressed(key=Key.Down)] * 2),
    *chapter("Search", [KeyPressed(key="a"), KeyPressed(key="n")]),
    *chapter("Clear the search", [KeyPressed(key=Key.Backspace)] * 2),
]


async def record_demo() -> None:
    await app(
        search(),
        headless=True,
        dimensions=(30, 8),
        clock=FrozenClock(datetime(2026, 3, 14, tzinfo=UTC)),
        recording=Recording(Path("search.cast"), input=True),
        autopilot=[*DEMO, Quit()],
    )


# --8<-- [end:chapters]


ROOTS = (search,)

# --8<-- [start:scenes]

from counterweight.controls import AdvanceClock
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still

TYPED = [KeyPressed(key="a"), KeyPressed(key="n")]
MANGO = [KeyPressed(key=character) for character in "mango"]

STILLS = [Still("autopilot-typed", search(), (30, 8), steps=TYPED)]

DEMOS = [
    Demo(
        "autopilot-mango",
        search(),
        (30, 8),
        steps=paced(MANGO, every=timedelta(milliseconds=300)),
    ),
    Demo("autopilot-chapters", search(), (30, 8), steps=[*DEMO, AdvanceClock(by=timedelta(seconds=2))]),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(search()))
