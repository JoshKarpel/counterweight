import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Suspend
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import use_state
from counterweight.programs import Edited
from counterweight.programs import EditOutcome
from counterweight.programs import Exited
from counterweight.programs import FailedToStart
from counterweight.programs import ProgramOutcome
from counterweight.programs import TerminalStreams
from counterweight.programs import run_program
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:pager]


@component
def log_viewer() -> Div:
    initial: ProgramOutcome | None = None
    outcome, set_outcome = use_state(initial)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key="l"):
                return Suspend.to_program(["git", "log", "--oneline"], on_exit=set_outcome)
            case _:
                return None

    match outcome:
        case None:
            status = "Press l to page through the log"
        case Exited(status=0):
            status = "Back from the log"
        case Exited(status=status_code):
            status = f"git log exited {status_code}"
        case FailedToStart(reason=reason):
            status = f"Couldn't start git: {reason}"

    return Div(on_input=on_input, children=(Text(content=status),))


# --8<-- [end:pager]

# --8<-- [start:file]


@component
def config_editor(path: Path) -> Div:
    contents, set_contents = use_state(path.read_text)

    def reload(outcome: ProgramOutcome) -> None:
        # Even an editor that exits with a failing status may have saved first, so read the file again.
        if isinstance(outcome, Exited):
            set_contents(path.read_text())

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key="e"):
                return Suspend.to_edit_file(path, on_exit=reload)
            case _:
                return None

    return Div(on_input=on_input, children=(Text(content=contents),))


# --8<-- [end:file]

# --8<-- [start:editor]


@component
def note(editor: Sequence[str] | None = None) -> Div:
    text, set_text = use_state("# Groceries\n\n- eggs\n- flour\n")
    problem, set_problem = use_state("")

    def on_edit(outcome: EditOutcome) -> None:
        match outcome:
            case Edited(text=edited):
                set_text(edited)
                set_problem("")
            case Exited(status=status):
                set_problem(f"The editor exited {status}, so the note is unchanged")
            case FailedToStart(reason=reason):
                set_problem(f"Couldn't start the editor: {reason}")

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key="e"):
                # Named .md, so the editor highlights it as Markdown.
                return Suspend.to_edit_text(text, on_edit=on_edit, file_name="note.md", editor=editor)
            case _:
                return None

    return Div(
        style=col | gap(1),
        on_input=on_input,
        children=(
            Text(content=text.rstrip("\n"), style=border | border_lightrounded | pad_x(1)),
            Text(
                content=problem or "Press e to edit the note in your editor",
                style=text_color("red", 400) if problem else text_color("slate", 400),
            ),
        ),
    )


# --8<-- [end:editor]

# --8<-- [start:own]


WAIT_FOR_ENTER = ("sh", "-c", 'printf "\\nPress Enter to go back to the app"; read line')


async def test_then_wait(terminal: TerminalStreams) -> None:
    await run_program(["make", "test"], terminal)
    await run_program(WAIT_FOR_ENTER, terminal)


def run_tests_on_t(event: InputEvent, _: Receiver) -> InputResponse:
    match event:
        case KeyPressed(key="t"):
            return Suspend(handler=test_then_wait)
        case _:
            return None


# --8<-- [end:own]

# Editors that a script stands in for, so the screenshots don't wait for a person:
# one that adds an item to the list and saves, and one that exits with a failing status, as vim's :cq does.
ADDS_BUTTER = ("sh", "-c", 'printf -- "- butter\\n" >> "$1"', "editor")
ABANDONS = ("sh", "-c", "exit 1", "editor")

SCREENSHOTS = [
    ScreenshotSpec(note(), "programs-note", (48, 8)),
    ScreenshotSpec(note(editor=ADDS_BUTTER), "programs-note-edited", (48, 9), events=[KeyPressed(key="e")]),
    ScreenshotSpec(note(editor=ABANDONS), "programs-note-abandoned", (48, 8), events=[KeyPressed(key="e")]),
]


if __name__ == "__main__":
    roots = {"note": note, "log_viewer": log_viewer, "config_editor": lambda: config_editor(Path("pyproject.toml"))}
    asyncio.run(app(roots[sys.argv[1] if len(sys.argv) > 1 else "note"]()))
