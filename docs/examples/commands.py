import asyncio
import sys
from datetime import timedelta

from more_itertools import last

from counterweight.app import app
from counterweight.commands import Cancelled
from counterweight.commands import CommandRun
from counterweight.commands import Exited
from counterweight.commands import command_output
from counterweight.commands import use_command
from counterweight.components import component
from counterweight.controls import AdvanceClock
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.emulator import Emulator
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.handlers import first
from counterweight.handlers import tab_focus
from counterweight.hooks import ElementHandle
from counterweight.hooks import use_clock
from counterweight.hooks import use_effect
from counterweight.hooks import use_rects
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.painters.terminal import MAX_LINES
from counterweight.painters.terminal import Transcript
from counterweight.pseudoterminal import Running
from counterweight.styles.utilities import *
from counterweight.widgets import text_area
from docs.examples.screenshot_spec import CastSpec
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


CANCELLED_TESTS = b"\x1b[1m===== test session starts =====\x1b[0m\r\ntests/test_slow.py \x1b[32m....\x1b[0m"


@component
def recorded_cancel() -> Div:
    viewport, _ = use_state(ElementHandle)
    run = CommandRun(argv=("pytest",), output=Transcript.of(CANCELLED_TESTS, columns=36), outcome=Cancelled())
    return Div(children=(command_output(run, viewport, style=size(40, 5)),))


def streamed_build() -> tuple[tuple[timedelta, bytes], ...]:
    """A build's output in the chunks it printed them, each with how long after the build started."""
    progress = [
        (timedelta(milliseconds=600 + 200 * step), f"\r[{'#' * step}{'.' * (10 - step)}] {10 * step}%")
        for step in range(11)
    ]
    chunks = [
        (timedelta(milliseconds=200), "\x1b[1mBuilding\x1b[0m web v4.2.0\r\n"),
        *progress,
        (timedelta(milliseconds=2900), "\r\n\x1b[32m\u2713\x1b[0m compiled 42 modules\r\n"),
        (timedelta(milliseconds=3200), "\x1b[33m!\x1b[0m 2 warnings in \x1b[4msrc/app.ts\x1b[0m\r\n"),
        (timedelta(milliseconds=3600), "\x1b[2mBundling...\x1b[0m\r\n"),
        (timedelta(milliseconds=4400), "\x1b[32m\u2713\x1b[0m wrote \x1b[36mdist/web.js\x1b[0m (184 kB)\r\n"),
        (timedelta(milliseconds=4700), "\x1b[32m\u2713\x1b[0m wrote \x1b[36mdist/web.css\x1b[0m (12 kB)\r\n"),
        (timedelta(milliseconds=5000), "Done in 4.8s\r\n"),
    ]
    return tuple((at, text.encode()) for at, text in chunks)


def transcripts(output: tuple[tuple[timedelta, bytes], ...], columns: int) -> tuple[tuple[timedelta, Transcript], ...]:
    """The transcript after each chunk of `output`, as a run reports it while its program prints."""
    transcript = Transcript(columns=columns)
    shown = []
    with Emulator(columns, 24, on_reply=lambda reply: None, scrollback=MAX_LINES) as emulator:
        for at, chunk in output:
            emulator.feed(chunk)
            transcript = transcript.followed_by(emulator.scrolled_off(), emulator.snapshot())
            shown.append((at, transcript))
    return tuple(shown)


BUILD_TRANSCRIPTS = transcripts(streamed_build(), columns=36)
EXITS_AT = timedelta(milliseconds=5200)
TICK = timedelta(milliseconds=100)


@component
def streaming_build() -> Div:
    viewport, _ = use_state(ElementHandle)
    elapsed = use_clock(TICK).since_mount
    output = last((transcript for at, transcript in BUILD_TRANSCRIPTS if at <= elapsed), Transcript(columns=36))
    run = CommandRun(
        argv=("./build.sh",), output=output, outcome=Exited(status=0) if elapsed >= EXITS_AT else Running()
    )
    return Div(children=(command_output(run, viewport, style=size(40, 8)),))


SCREENSHOTS = [
    ScreenshotSpec(recorded_build(), "commands-recorded", (40, 8)),
    ScreenshotSpec(recorded_failure(), "commands-failed", (40, 7)),
    ScreenshotSpec(recorded_cancel(), "commands-cancelled", (40, 5)),
]

CASTS = [
    CastSpec(
        streaming_build(),
        "commands-streaming",
        (40, 8),
        steps=[*[AdvanceClock(by=TICK)] * (EXITS_AT // TICK), AdvanceClock(by=timedelta(seconds=3))],
    )
]


if __name__ == "__main__":
    roots = {
        "slide": lambda: slide("Disk usage", ("df", "-h")),
        "code_runner": code_runner,
        "recorded_build": recorded_build,
        "recorded_failure": recorded_failure,
        "recorded_cancel": recorded_cancel,
        "streaming_build": streaming_build,
    }
    asyncio.run(app(roots[sys.argv[1] if len(sys.argv) > 1 else "slide"]()))
