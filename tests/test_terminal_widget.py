from __future__ import annotations

import io
import os
from asyncio import CancelledError
from asyncio import Event
from asyncio import create_task
from asyncio import timeout
from asyncio import wait_for
from collections.abc import AsyncIterator
from collections.abc import Callable
from contextlib import asynccontextmanager
from contextlib import suppress
from dataclasses import dataclass
from dataclasses import field

import pytest

from counterweight.app import app
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import Screenshot
from counterweight.elements import Div
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import use_effect
from counterweight.keys import Key
from counterweight.output import Frame
from counterweight.styles import Style
from counterweight.styles.utilities import border
from counterweight.styles.utilities import border_color
from counterweight.styles.utilities import border_heavy
from counterweight.styles.utilities import col
from counterweight.styles.utilities import fill
from counterweight.styles.utilities import full
from counterweight.widgets import TerminalStyles
from counterweight.widgets import terminal
from tests.rendering import TIMEOUT
from tests.terminal import Terminal

READY_THEN_ECHO = ("/bin/sh", "-c", "echo ready; exec cat")


@dataclass(slots=True)
class Shots:
    """Takes a screenshot whenever Ctrl+S reaches `shoot`, and wakes a test waiting for one."""

    frames: list[Frame] = field(default_factory=list)
    taken: Event = field(default_factory=Event)
    started: Event = field(default_factory=Event)
    """Set once the app is running, so the terminal it reads is raw, and Ctrl+S is a key rather than flow control."""

    def shoot(self, event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.ControlS):
                return Screenshot(handler=self.take)
            case _:
                return None

    async def start(self) -> None:
        self.started.set()

    def take(self, frame: Frame) -> None:
        self.frames.append(frame)
        self.taken.set()

    async def until(self, keyboard: int, is_done: Callable[[list[str]], bool]) -> list[str]:
        """Takes screenshots, each after a render, until one's rows satisfy `is_done`, and returns those rows."""
        async with timeout(TIMEOUT):
            await self.started.wait()
            while True:
                self.taken.clear()
                os.write(keyboard, b"\x13")
                await self.taken.wait()
                rows = [line.rstrip() for line in self.frames[-1].text(ansi=False).splitlines()]
                if is_done(rows):
                    return rows


@asynccontextmanager
async def running(root: Component, keyboard: Terminal, dimensions: tuple[int, int]) -> AsyncIterator[None]:
    task = create_task(app(root, output_stream=io.StringIO(), input_stream=keyboard.stream, dimensions=dimensions))
    try:
        yield
    finally:
        task.cancel()
        with suppress(CancelledError):
            await wait_for(task, TIMEOUT)


def has(text: str) -> Callable[[list[str]], bool]:
    return lambda rows: any(text in row for row in rows)


def has_spaced(words: str) -> Callable[[list[str]], bool]:
    """Like `has`, but for space-separated `words` in rows spaced any amount, as macOS's `od` pads its columns wider."""
    return lambda rows: any(words in " ".join(row.split()) for row in rows)


@component
def focused_terminal(shots: Shots) -> Div:
    use_effect(shots.start, deps=())
    return Div(
        style=col | full,
        on_input=shots.shoot,
        children=(terminal(READY_THEN_ECHO, style=fill(1), intercept=shots.shoot, auto_focus=True),),
    )


async def test_a_focused_terminal_shows_its_program_in_a_box_and_sends_it_typing(terminal: Terminal) -> None:
    shots = Shots()
    async with running(focused_terminal(shots), terminal, (12, 5)):
        await shots.until(terminal.keyboard, has("ready"))
        os.write(terminal.keyboard, b"hi")
        rows = await shots.until(terminal.keyboard, has("hi"))

    assert rows == ["╭──────────╮", "│ready     │", "│hi        │", "│          │", "╰──────────╯"]


@component
def unfocused_terminal(shots: Shots, argv: tuple[str, ...]) -> Div:
    use_effect(shots.start, deps=())
    return Div(
        style=col | full,
        on_input=shots.shoot,
        children=(terminal(argv, style=fill(1), intercept=shots.shoot),),
    )


async def test_pressing_a_terminal_focuses_it_and_tells_a_program_that_asked(terminal: Terminal) -> None:
    shots = Shots()
    argv = ("/bin/sh", "-c", "stty raw -echo; printf '\\033[?1004h'; echo ready; head -c 3 | od -An -tx1; sleep 10")
    async with running(unfocused_terminal(shots, argv), terminal, (30, 5)):
        await shots.until(terminal.keyboard, has("ready"))
        os.write(terminal.keyboard, b"\x1b[<0;3;3M\x1b[<0;3;3m")
        rows = await shots.until(terminal.keyboard, has_spaced("1b 5b 49"))

    assert rows[0] == "╭────────────────────────────╮"


BOX = border | border_heavy
STYLE = border_color("amber", 300)
FOCUSED_BOX = border_color("indigo", 400)


@pytest.mark.parametrize(("is_focused", "expected"), [(False, BOX | STYLE), (True, BOX | STYLE | FOCUSED_BOX)])
def test_a_terminals_box_is_styled_by_its_box_then_its_style_then_its_focused_box_while_focused(
    is_focused: bool, expected: Style
) -> None:
    assert TerminalStyles(box=BOX, focused_box=FOCUSED_BOX).box_style(STYLE, is_focused) == expected
