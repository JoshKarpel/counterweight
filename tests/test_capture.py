"""Capturing what an app's code writes to `sys.stdout` and `sys.stderr`, and printing it as finished output."""

from __future__ import annotations

import fcntl
import io
import os
import pty
import struct
import sys
import termios
from collections.abc import Iterator
from dataclasses import dataclass
from threading import Thread
from typing import TextIO

import pytest

from counterweight import Inline
from counterweight import app
from counterweight._capture import CapturedLines
from counterweight.autopilot import AutopilotStep
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import AnyControl
from counterweight.controls import Quit
from counterweight.controls import Suspend
from counterweight.elements import Text
from counterweight.emulator import Emulator
from counterweight.events import InputEvent
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import use_state
from tests.terminal import Terminal

KEY = KeyPressed(key="x")


@dataclass(frozen=True, slots=True)
class Screen:
    """A pseudo-terminal for an app to draw on: the program side open for writing, and the side that reads it."""

    output: TextIO
    reader: int

    def shown(self) -> list[str]:
        """What a terminal the size of this one holds after what the app wrote to it."""
        with Emulator(16, 4, on_reply=lambda reply: None, scrollback=100) as emulator:
            emulator.feed(os.read(self.reader, 2**16))
            lines = emulator.history() + emulator.snapshot().lines
        return ["".join(cell.grapheme for cell in line).rstrip() for line in lines]


@pytest.fixture
def screen() -> Iterator[Screen]:
    reader, program = pty.openpty()
    fcntl.ioctl(program, termios.TIOCSWINSZ, struct.pack("HHHH", 4, 16, 0, 0))
    os.set_blocking(reader, False)
    with os.fdopen(program, "w") as output:
        yield Screen(output=output, reader=reader)
    os.close(reader)


@component
def printer(on_key: AnyControl | None = None) -> Text:
    """Prints a line for each key pressed, then returns `on_key`, and shows how many keys it's printed for."""
    count, set_count = use_state(0)

    def on_input(event: InputEvent, _: Receiver) -> AnyControl | None:
        print(f"printed {count}")
        set_count(count + 1)
        return on_key

    return Text(content=f"status {count}", on_input=on_input)


async def run(
    root: Component, screen: Screen, terminal: Terminal, steps: list[AutopilotStep], **kwargs: object
) -> None:
    await app(
        root,
        output_stream=screen.output,
        input_stream=terminal.stream,
        dimensions=(16, 4),
        viewport=Inline(),
        stdout=screen.output,
        autopilot=[*steps, Quit()],
        **kwargs,  # type: ignore[arg-type]
    )


async def test_a_print_in_a_handler_lands_above_the_region(screen: Screen, terminal: Terminal) -> None:
    await run(printer(), screen, terminal, [KEY, KEY])

    assert screen.shown() == ["printed 0", "printed 1", "status 2", ""]


async def test_a_print_in_a_handler_that_quits_is_printed_before_the_app_stops(
    screen: Screen, terminal: Terminal
) -> None:
    await run(printer(on_key=Quit()), screen, terminal, [KEY])

    assert screen.shown() == ["printed 0", "status 1", "", ""]


async def test_a_print_to_sys_stderr_goes_to_the_apps_stderr(screen: Screen, terminal: Terminal) -> None:
    stderr = io.StringIO()

    @component
    def warns() -> Text:
        return Text(content="region", on_input=lambda event, _: print("warning", file=sys.stderr))

    await run(warns(), screen, terminal, [KEY], stderr=stderr)

    assert stderr.getvalue() == "warning\n"


async def test_a_line_written_in_parts_is_printed_once_its_newline_is_written(
    screen: Screen, terminal: Terminal
) -> None:
    @component
    def parts() -> Text:
        def on_input(event: InputEvent, _: Receiver) -> None:
            print("one", end="")
            print(" two")

        return Text(content="region", on_input=on_input)

    await run(parts(), screen, terminal, [KEY])

    assert screen.shown() == ["one two", "region", "", ""]


async def test_a_line_left_unfinished_is_written_as_it_is_when_the_app_stops(
    screen: Screen, terminal: Terminal, capsys: pytest.CaptureFixture[str]
) -> None:
    @component
    def unfinished() -> Text:
        return Text(content="region", on_input=lambda event, _: print("left", end=""))

    await run(unfinished(), screen, terminal, [KEY])

    assert capsys.readouterr().out == "left"


async def test_a_line_printed_from_another_thread_is_printed(screen: Screen, terminal: Terminal) -> None:
    @component
    def threaded() -> Text:
        def on_input(event: InputEvent, _: Receiver) -> None:
            thread = Thread(target=print, args=("from a thread",))
            thread.start()
            thread.join()

        return Text(content="region", on_input=on_input)

    await run(threaded(), screen, terminal, [KEY, KeyPressed(key="y")])

    assert screen.shown()[0] == "from a thread"


async def test_the_streams_are_put_back_while_the_app_is_suspended_and_when_it_stops(
    screen: Screen, terminal: Terminal
) -> None:
    before = (sys.stdout, sys.stderr)
    during: list[tuple[TextIO, TextIO]] = []
    running: list[tuple[TextIO, TextIO]] = []

    @component
    def watches() -> Text:
        return Text(content="region", on_input=lambda event, _: running.append((sys.stdout, sys.stderr)))

    await run(
        watches(),
        screen,
        terminal,
        [KEY, Suspend(handler=lambda streams: during.append((sys.stdout, sys.stderr))), KEY],
    )

    assert during == [before]
    assert (sys.stdout, sys.stderr) == before
    assert len(running) == 2
    assert all(isinstance(stream, CapturedLines) for streams in running for stream in streams)


async def test_an_app_that_doesnt_capture_output_leaves_the_streams_alone(screen: Screen, terminal: Terminal) -> None:
    before = (sys.stdout, sys.stderr)
    running: list[tuple[TextIO, TextIO]] = []

    @component
    def watches() -> Text:
        return Text(content="region", on_input=lambda event, _: running.append((sys.stdout, sys.stderr)))

    await run(watches(), screen, terminal, [KEY], capture_output=False)

    assert running == [before]


async def test_a_headless_app_captures_nothing() -> None:
    before = (sys.stdout, sys.stderr)
    running: list[tuple[TextIO, TextIO]] = []

    @component
    def watches() -> Text:
        return Text(content="region", on_input=lambda event, _: running.append((sys.stdout, sys.stderr)))

    await app(watches(), headless=True, dimensions=(16, 4), viewport=Inline(), autopilot=[KEY, Quit()])

    assert running == [before]


def test_captured_lines_arent_a_terminal_and_take_their_encoding_from_the_stream_they_replace() -> None:
    original = io.TextIOWrapper(io.BytesIO(), encoding="latin-1")

    captured = CapturedLines(original, send=lambda line: None)

    assert (captured.isatty(), captured.writable(), captured.encoding) == (False, True, "latin-1")
