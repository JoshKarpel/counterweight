"""
A presentation whose slides each run a command when they're shown, and show what it printed.

Run it with `uv run python -m examples.slides`.
Right goes to the next slide, and Left to the previous one.
Each slide's output is focused, so Up, Down, PageUp, PageDown, Home and End scroll it.
R runs the slide's command again, and Escape stops it.
"""

from __future__ import annotations

import asyncio
import shlex
from dataclasses import dataclass

from counterweight.app import app
from counterweight.commands import command_output
from counterweight.commands import use_command
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import ElementHandle
from counterweight.hooks import use_effect
from counterweight.hooks import use_rects
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *


@dataclass(frozen=True, slots=True)
class Slide:
    title: str
    note: str
    argv: tuple[str, ...]


SLIDES = (
    Slide(
        title="Where am I?",
        note="Each slide runs its command when it's shown.",
        argv=("uname", "-a"),
    ),
    Slide(
        title="Colors come through",
        note="The command runs on a terminal, so it colors its output as it would in yours.",
        argv=("ls", "-la", "--color=auto", "/"),
    ),
    Slide(
        title="Long output scrolls",
        note="The box follows the end of the output while the command runs, and Up and Down scroll it.",
        argv=("sh", "-c", "for n in $(seq 60); do echo line $n; sleep 0.05; done"),
    ),
    Slide(
        title="Failures are results too",
        note="A command that exits with a failing status shows it beneath its output.",
        argv=("ls", "/no/such/directory"),
    ),
)


@component
def root() -> Div:
    index, set_index = use_state(0)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Right):
                set_index(lambda i: min(i + 1, len(SLIDES) - 1))
                return ()
            case KeyPressed(key=Key.Left):
                set_index(lambda i: max(i - 1, 0))
                return ()
            case _:
                return None

    return Div(
        style=col | full,
        on_input=on_input,
        children=(
            # Keyed by its index, so each slide starts with no run of its own.
            slide(SLIDES[index]).with_key(str(index)),
            Text(content=f" {index + 1} / {len(SLIDES)}", style=text_color("slate", 500)),
        ),
    )


@component
def slide(shown: Slide) -> Div:
    viewport, _ = use_state(ElementHandle)
    command = use_command(columns=use_rects(viewport).content.width)

    async def start() -> None:
        command.run(shown.argv)

    use_effect(start, deps=(shown.argv,))

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key="r"):
                command.run(shown.argv)
                return ()
            case KeyPressed(key=Key.Escape):
                command.cancel()
                return ()
            case _:
                return None

    return Div(
        style=col | fill(1) | gap(1) | pad_x(2) | pad_y(1),
        on_input=on_input,
        children=(
            Text(content=shown.title, style=text_color("sky", 300)),
            Text(content=shown.note, style=text_wrap_stable | text_color("slate", 400)),
            Text(content=f"$ {shlex.join(shown.argv)}", style=text_color("amber", 300)),
            command_output(command.latest, viewport, style=fill(1), auto_focus=True),
        ),
    )


if __name__ == "__main__":
    asyncio.run(app(root()))
