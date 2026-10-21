"""
Input handling: Controls

A window title editor whose keys return controls: set the title, restore it, ring the bell, or edit it in your editor.
"""

import asyncio

from counterweight import app
from counterweight.components import component
from counterweight.controls import Bell
from counterweight.controls import RestoreTitle
from counterweight.controls import SetTitle
from counterweight.controls import Suspend
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.programs import Edited
from counterweight.programs import EditOutcome
from counterweight.styles.utilities import *
from counterweight.widgets import text_input

# --8<-- [start:example]


@component
def title_editor() -> Div:
    draft, set_draft = use_state("")
    title, set_title = use_state("")

    def edited(outcome: EditOutcome) -> None:
        match outcome:
            case Edited(text=text):
                set_draft(text.strip())
            case _:
                pass

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Enter):
                if not draft:
                    return Bell()
                set_title(draft)
                return SetTitle(draft)
            case KeyPressed(key=Key.Escape):
                set_title("")
                return RestoreTitle()
            case KeyPressed(key=Key.ControlO):
                return Suspend.to_edit_text(draft, on_edit=edited)
            case _:
                return None

    return Div(
        style=col | width(60),
        on_input=on_input,
        children=(
            text_input(draft, set_draft, placeholder="Window title", auto_focus=True),
            Text(content=f"Window title: {title or "the terminal's own"}"),
            Text(
                content="Enter: set · Escape: restore · Ctrl+O: edit",
                style=text_color("slate", 400),
            ),
        ),
    )


# --8<-- [end:example]


ROOTS = (title_editor,)

# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import paced
from counterweight.controls import AdvanceClock
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still


def typed(text: str) -> tuple[KeyPressed, ...]:
    return tuple(KeyPressed(key=character) for character in text)


DIMENSIONS = (62, 6)
ENTER = KeyPressed(key=Key.Enter)
SET = (*typed("Build logs"), ENTER)

STILLS = [
    Still("input-controls-title", title_editor(), DIMENSIONS, steps=SET),
]

DEMOS = [
    Demo(
        "input-controls-title",
        title_editor(),
        DIMENSIONS,
        steps=[
            *paced([ENTER, *SET, KeyPressed(key=Key.Escape)], pause=AdvanceClock(by=timedelta(milliseconds=300))),
            AdvanceClock(by=timedelta(seconds=2)),
        ],
    )
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(title_editor()))
