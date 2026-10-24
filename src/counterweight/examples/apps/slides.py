"""
Slides

A presentation whose slides each run a command when they're shown, and show what it printed beneath their notes.

Right goes to the next slide, and Left to the previous one.
Each slide's output is focused, so Up, Down, PageUp, PageDown, Home and End scroll it.
R runs the slide's command again, and Escape stops it.
E opens the slide's notes, which are Markdown, in your editor, and shows them as you saved them when it exits.
The commands run in a scratch directory of a few files, made when the presentation starts and removed when it ends.
"""

from __future__ import annotations

import asyncio
import shlex
import shutil
import tempfile
from dataclasses import dataclass
from dataclasses import replace
from functools import partial
from pathlib import Path

from counterweight import app
from counterweight.commands import command_output
from counterweight.commands import use_command
from counterweight.components import component
from counterweight.controls import Suspend
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.focus import ElementHandle
from counterweight.hooks import use_effect
from counterweight.hooks import use_rects
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.markdown import markdown_document
from counterweight.programs import Edited
from counterweight.programs import EditOutcome
from counterweight.styles.utilities import *


@dataclass(frozen=True, slots=True)
class Slide:
    title: str
    notes: str
    argv: tuple[str, ...]


SLIDES: tuple[Slide, ...] = (
    Slide(
        title="Every slide runs a command",
        notes="Each slide runs its command **when it's shown**, in a scratch directory of a few files.",
        argv=("ls", "-1F"),
    ),
    Slide(
        title="Files show as they are",
        notes="The output is what the command printed, line for line.",
        argv=("cat", "peaks.csv"),
    ),
    Slide(
        title="Colors come through",
        notes="The command runs on a terminal, so it colors its output as it would in yours.",
        argv=("printf", r"\033[32mgreen\033[0m and \033[1;33mbold yellow\033[0m\n"),
    ),
    Slide(
        title="Long output scrolls",
        notes="The box follows the end of the output while the command runs, and `Up` and `Down` scroll it.",
        argv=("sh", "-c", "for n in $(seq 60); do echo line $n; sleep 0.05; done"),
    ),
    Slide(
        title="Failures are results too",
        notes="A command that exits with a failing status shows it beneath its output.",
        argv=("cat", "missing.txt"),
    ),
)

# All in lowercase, and listed one to a line, so GNU's and BSD's `ls` sort and lay them out alike in every locale.
SCRATCH_FILES = {
    "about.md": "# Peaks\n\nThe four highest peaks, in meters.\n",
    "peaks.csv": "peak,height\nEverest,8849\nK2,8611\nKangchenjunga,8586\nLhotse,8516\n",
    "notes/": "",
}


def make_scratch_directory() -> Path:
    """A new directory holding `SCRATCH_FILES`, where a name ending in `/` is a directory."""
    directory = Path(tempfile.mkdtemp(prefix="counterweight-slides-"))
    for name, text in SCRATCH_FILES.items():
        if name.endswith("/"):
            (directory / name).mkdir()
        else:
            (directory / name).write_text(text)
    return directory


@component
def root() -> Div:
    slides, set_slides = use_state(SLIDES)
    index, set_index = use_state(0)
    unmade: Path | None = None
    scratch, set_scratch = use_state(unmade)

    async def keep_scratch_directory() -> None:
        directory = make_scratch_directory()
        try:
            set_scratch(directory)
            await asyncio.Event().wait()
        finally:
            shutil.rmtree(directory)

    use_effect(keep_scratch_directory, deps=())

    def edited(at: int, outcome: EditOutcome) -> None:
        match outcome:
            case Edited(text=text):
                set_slides(lambda slides: tuple(replace(s, notes=text) if i == at else s for i, s in enumerate(slides)))
            case _:
                pass

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Right):
                set_index(lambda i: min(i + 1, len(slides) - 1))
                return ()
            case KeyPressed(key=Key.Left):
                set_index(lambda i: max(i - 1, 0))
                return ()
            case KeyPressed(key="e"):
                return Suspend.to_edit_text(slides[index].notes, on_edit=partial(edited, index), file_name="notes.md")
            case _:
                return None

    return Div(
        style=col | full,
        on_input=on_input,
        children=(
            # Keyed by its index, so each slide starts with no run of its own.
            slide(slides[index], scratch).with_key(str(index)),
            Text(content=f" {index + 1} / {len(slides)}  ·  e: edit the notes", style=text_color("slate", 500)),
        ),
    )


@component
def slide(shown: Slide, scratch: Path | None) -> Div:
    viewport, _ = use_state(ElementHandle)
    command = use_command(columns=use_rects(viewport).content.width, cwd=scratch)

    async def start() -> None:
        if scratch is not None:
            command.run(shown.argv)

    use_effect(start, deps=(shown.argv, scratch))

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
            Text(content=shown.title, style=text_color("sky", 300) | text_bold),
            markdown_document(shown.notes),
            Text(content=f"$ {shlex.join(shown.argv)}", style=text_color("amber", 300)),
            command_output(command.latest, viewport, style=fill(1), auto_focus=True),
        ),
    )


# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import WaitFor
from counterweight.examples.scenes import Still


def shows(text: str) -> WaitFor:
    """Wait until the screen shows `text`, which a command prints in its own time."""
    return WaitFor(lambda frame: text in frame.text(ansi=False), timeout=timedelta(seconds=30))


RIGHT = KeyPressed(key=Key.Right)

STILLS = [
    Still("slides", root(), (80, 18), steps=[shows("exited 0")]),
    Still("slides-colors", root(), (80, 18), steps=[shows("exited 0"), RIGHT, RIGHT, shows("exited 0")]),
    Still("slides-failure", root(), (80, 18), steps=[*[RIGHT] * 4, shows("exited 1")]),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(root()))
