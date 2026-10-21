"""
Hooks: use_ref

A line entry that keeps what it needs between renders in a ref.
"""

import asyncio

from counterweight import app
from counterweight.components import component
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import use_focus
from counterweight.hooks import use_ref
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *

# --8<-- [start:example]


@component
def line_entry() -> Text:
    use_focus(auto_focus=True)
    typed = use_ref(list[str]())
    line, set_line = use_state("")

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Enter):
                set_line("".join(typed.current))
                typed.current.clear()
                return ()
            case KeyPressed(key=key) if len(key) == 1:
                typed.current.append(key)
                return ()
            case _:
                return None

    return Text(
        content=f"Last line: {line}",
        style=border | border_lightrounded | pad_x(1) | text_color("amber", 400),
        on_input=on_input,
    )


# --8<-- [end:example]


def typed(text: str) -> list[KeyPressed]:
    return [KeyPressed(key=character) for character in text]


ROOTS = (line_entry,)

# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import paced
from counterweight.controls import AdvanceClock
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still

ENTER = KeyPressed(key=Key.Enter)

STILLS = [
    Still("use-ref-line-entry", line_entry(), (30, 3), steps=[*typed("hello"), ENTER, *typed("wor")]),
]

DEMOS = [
    Demo(
        "use-ref-line-entry",
        line_entry(),
        (30, 3),
        steps=[
            *paced(
                [*typed("hello"), ENTER, *typed("world"), ENTER], pause=AdvanceClock(by=timedelta(milliseconds=250))
            ),
            AdvanceClock(by=timedelta(seconds=2)),
        ],
    ),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(line_entry()))
