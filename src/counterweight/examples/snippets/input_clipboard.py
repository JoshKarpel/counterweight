"""
Input handling: Copying to the clipboard

A list of commands, any of which Enter or a click copies to the clipboard.
"""

import asyncio

from counterweight import app
from counterweight.components import component
from counterweight.controls import CopyToClipboard
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.geometry import clamp
from counterweight.handlers import on_click
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *

# --8<-- [start:example]

COMMANDS = (
    "git status",
    "git log --oneline --graph",
    "uv run pytest -x",
    "just docs-serve",
)


@component
def command_list() -> Div:
    selected, set_selected = use_state(0)
    copied, set_copied = use_state("")

    def copy(index: int) -> CopyToClipboard:
        set_selected(index)
        set_copied(COMMANDS[index])
        return CopyToClipboard(COMMANDS[index])

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Up):
                set_selected(lambda index: clamp(0, index - 1, len(COMMANDS) - 1))
                return ()
            case KeyPressed(key=Key.Down):
                set_selected(lambda index: clamp(0, index + 1, len(COMMANDS) - 1))
                return ()
            case KeyPressed(key=Key.Enter):
                return copy(selected)
            case _:
                return None

    def command_row(index: int) -> Text:
        return Text(
            content=f"$ {COMMANDS[index]}",
            style=pad_x(1) | (text_bg("sky", 800) if index == selected else text_color("slate", 300)),
            on_input=on_click(lambda: copy(index)),
        )

    return Div(
        style=col | width(40),
        on_input=on_input,
        children=(
            Div(
                style=col | border | border_lightrounded,
                children=tuple(command_row(index) for index in range(len(COMMANDS))),
            ),
            Text(
                content=f"Copied: {copied}" if copied else "Enter or click to copy",
                style=pad_x(1) | text_color("emerald" if copied else "slate", 400),
            ),
        ),
    )


# --8<-- [end:example]


ROOTS = (command_list,)

# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import paced
from counterweight.controls import AdvanceClock
from counterweight.events import MouseDown
from counterweight.events import MouseUp
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still
from counterweight.geometry import Position

DIMENSIONS = (42, 7)
DOWN = KeyPressed(key=Key.Down)
ENTER = KeyPressed(key=Key.Enter)


def click(x: int, y: int) -> list[MouseDown | MouseUp]:
    return [MouseDown(absolute=Position(x, y), button=1), MouseUp(absolute=Position(x, y), button=1)]


STILLS = [
    Still("input-clipboard", command_list(), DIMENSIONS, steps=[DOWN, ENTER]),
]

DEMOS = [
    Demo(
        "input-clipboard",
        command_list(),
        DIMENSIONS,
        steps=[
            *paced(
                [DOWN, ENTER, DOWN, DOWN, ENTER, KeyPressed(key=Key.Up), *click(8, 1)],
                pause=AdvanceClock(by=timedelta(milliseconds=500)),
            ),
            AdvanceClock(by=timedelta(seconds=2)),
        ],
    )
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(command_list()))
