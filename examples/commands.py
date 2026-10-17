import asyncio
import sys
from datetime import timedelta

from counterweight.app import app
from counterweight.commands import CommandRun
from counterweight.commands import Exited
from counterweight.commands import command_output
from counterweight.commands import use_command
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.handlers import first
from counterweight.handlers import tab_focus
from counterweight.hooks import ElementHandle
from counterweight.hooks import use_effect
from counterweight.hooks import use_rects
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.painters.terminal import Transcript
from counterweight.styles.utilities import *
from counterweight.widgets import text_area
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:slide]


@component
def slide(title: str, argv: tuple[str, ...]) -> Div:
    # The box the output is shown in, which sets how wide the program's terminal is.
    viewport, _ = use_state(ElementHandle)
    command = use_command(columns=use_rects(viewport).content.width)

    async def start() -> None:
        command.run(argv)

    # Runs the command when the slide is shown, and again if it's shown with another one.
    use_effect(start, deps=(argv,))

    return Div(
        style=col | full | gap(1) | pad(1),
        children=(
            Text(content=title, style=text_color("sky", 300)),
            command_output(command.latest, viewport, style=fill(1)),
        ),
    )


# --8<-- [end:slide]

# --8<-- [start:runner]


@component
def code_runner() -> Div:
    code, set_code = use_state('for n in range(3):\n    print(f"{n} squared is {n * n}")')
    viewport, _ = use_state(ElementHandle)
    command = use_command(columns=use_rects(viewport).content.width, timeout=timedelta(seconds=10))

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.F5):
                command.run((sys.executable, "-c", code))
                return ()
            case KeyPressed(key=Key.Escape):
                command.cancel()
                return ()
            case _:
                return None

    return Div(
        style=col | full,
        on_input=first(on_input, tab_focus),
        children=(
            text_area(code, set_code, enter_inserts_newline=True, auto_focus=True, style=max_height(10)),
            command_output(command.latest, viewport, style=fill(1)),
            Text(content="F5 runs the code, Escape stops it, Tab moves to the output", style=text_color("slate", 500)),
        ),
    )


# --8<-- [end:runner]

# --8<-- [start:recorded]

BUILD = (
    b"\x1b[1mBuilding\x1b[0m web v4.2.0\r\n"
    b"[####......] 40%\r[##########] 100%\r\n"
    b"\x1b[32m\xe2\x9c\x93\x1b[0m compiled 42 modules\r\n"
    b"\x1b[33m!\x1b[0m 2 warnings in \x1b[4msrc/app.ts\x1b[0m\r\n"
    b"\x1b[32m\xe2\x9c\x93\x1b[0m wrote \x1b[36mdist/web.js\x1b[0m (184 kB)\r\n"
)


@component
def recorded_build() -> Div:
    viewport, _ = use_state(ElementHandle)
    # Recorded at the width of the box's content: 40 columns, less its border and padding.
    run = CommandRun(argv=("./build.sh",), output=Transcript.of(BUILD, columns=36), outcome=Exited(status=0))
    return Div(children=(command_output(run, viewport, style=size(40, 8)),))


# --8<-- [end:recorded]

FAILED_TESTS = (
    b"\x1b[1m===== test session starts =====\x1b[0m\r\n"
    b"tests/test_math.py \x1b[32m.\x1b[31mF\x1b[32m.\x1b[0m\r\n"
    b"\x1b[31mFAILED\x1b[0m test_math.py::test_divide\r\n"
    b"\x1b[31m===== 1 failed, 2 passed =====\x1b[0m\r\n"
)


@component
def recorded_failure() -> Div:
    viewport, _ = use_state(ElementHandle)
    run = CommandRun(argv=("pytest",), output=Transcript.of(FAILED_TESTS, columns=36), outcome=Exited(status=1))
    return Div(children=(command_output(run, viewport, style=size(40, 7)),))


SCREENSHOTS = [
    ScreenshotSpec(recorded_build(), "commands-recorded", (40, 8)),
    ScreenshotSpec(recorded_failure(), "commands-failed", (40, 7)),
]


if __name__ == "__main__":
    roots = {
        "slide": lambda: slide("Disk usage", ("df", "-h")),
        "code_runner": code_runner,
        "recorded_build": recorded_build,
        "recorded_failure": recorded_failure,
    }
    asyncio.run(app(roots[sys.argv[1] if len(sys.argv) > 1 else "slide"]()))
