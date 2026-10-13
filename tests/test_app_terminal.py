"""The render loop outside headless mode: what it writes to the terminal, and how it takes input from it."""

from __future__ import annotations

import io
import os
import termios
from asyncio import get_running_loop, wait_for
from signal import SIGWINCH, raise_signal

import pytest

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import AnyControl, Bell, Quit, Screenshot, Suspend
from counterweight.elements import Text
from counterweight.events import KeyPressed
from counterweight.geometry import Position
from counterweight.hooks import Mouse, use_effect, use_mouse
from counterweight.output import (
    ALT_SCREEN_OFF,
    ALT_SCREEN_ON,
    CLEAR_SCREEN,
    CURSOR_OFF,
    CURSOR_ON,
    SET_ANY_EVENT_MOUSE_SGR_FORMAT,
    UNSET_ANY_EVENT_MOUSE_SGR_FORMAT,
)
from counterweight.styles.utilities import text_black
from tests.devlog import devlog_lines
from tests.terminal import Terminal

TIMEOUT = 5

TAKE_OVER = ALT_SCREEN_ON + CURSOR_OFF + CLEAR_SCREEN + SET_ANY_EVENT_MOUSE_SGR_FORMAT
HAND_BACK = UNSET_ANY_EVENT_MOUSE_SGR_FORMAT + ALT_SCREEN_OFF + CURSOR_ON
BLANK_SCREEN = CLEAR_SCREEN + "\x1b[1;1f\x1b[0m\x1b[38;2;255;255;255m\x1b[48;2;0;0;0m   \x1b[0m"
HI = "\x1b[1;1f\x1b[0m\x1b[38;2;0;0;0m\x1b[48;2;0;0;0mhi \x1b[0m"


class Output(io.StringIO):
    """Terminal output that records everything written before each flush."""

    def __init__(self) -> None:
        super().__init__()
        self.flushed: list[str] = []

    def flush(self) -> None:
        self.flushed.append(self.getvalue())


@component
def hi() -> Text:
    return Text(content="hi", style=text_black)


async def test_app_takes_over_the_terminal_draws_rings_the_bell_and_hands_it_back(terminal: Terminal) -> None:
    before = termios.tcgetattr(terminal.stream)
    output = Output()

    with devlog_lines() as lines:
        await app(
            hi(),
            output_stream=output,
            input_stream=terminal.stream,
            dimensions=(3, 1),
            autopilot=[Bell(), Screenshot(handler=lambda frame: None), Screenshot(handler=lambda frame: None), Quit()],
        )

    drawn = TAKE_OVER + BLANK_SCREEN + HI
    assert [line for line in lines if "Wrote" in line] == [
        f"DEBUG    counterweight.app Wrote and flushed instructions to output stream bytes='{len(HI):_}'"
    ]
    assert output.getvalue() == drawn + "\a" + HAND_BACK
    assert output.flushed[2:4] == [drawn, drawn + "\a"]
    assert termios.tcgetattr(terminal.stream) == before


async def test_suspend_hands_the_terminal_back_while_its_handler_runs(terminal: Terminal) -> None:
    before = termios.tcgetattr(terminal.stream)
    output = Output()
    during: list[tuple[str, object, bool]] = []

    def handler() -> None:
        is_read = get_running_loop().remove_reader(terminal.stream.fileno())
        during.append((output.getvalue(), termios.tcgetattr(terminal.stream), is_read))

    await app(
        hi(),
        output_stream=output,
        input_stream=terminal.stream,
        dimensions=(3, 1),
        autopilot=[Suspend(handler=handler), Quit()],
    )

    frame = TAKE_OVER + BLANK_SCREEN + HI + HAND_BACK
    assert during == [(frame, before, False)]
    assert output.getvalue() == frame + frame


async def test_app_reads_keys_from_the_terminal(terminal: Terminal) -> None:
    pressed: list[KeyPressed] = []

    def on_key(event: KeyPressed) -> AnyControl | None:
        pressed.append(event)
        return Quit() if event.key == "q" else None

    @component
    def root() -> Text:
        return Text(content="hi", on_key=on_key)

    os.write(terminal.keyboard, b"aq")

    await app(root(), output_stream=Output(), input_stream=terminal.stream, dimensions=(3, 1))

    assert pressed == [KeyPressed(key="a"), KeyPressed(key="q")]


async def test_app_stops_reading_keys_when_it_returns(terminal: Terminal) -> None:
    await app(hi(), output_stream=Output(), input_stream=terminal.stream, dimensions=(3, 1), autopilot=[Quit()])

    assert not get_running_loop().remove_reader(terminal.stream.fileno())


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        pytest.param(
            b"\x1b[<35;3;4M",
            Mouse(absolute=Position(x=2, y=3), motion=Position(x=3, y=4), button=None),
            id="first-move-measures-motion-from-off-screen",
        ),
        pytest.param(
            b"\x1b[<0;3;4M",
            Mouse(absolute=Position(x=2, y=3), motion=Position(x=3, y=4), button=1),
            id="press-holds-its-button",
        ),
        pytest.param(
            b"\x1b[<0;2;2M\x1b[<32;4;3M\x1b[<0;7;5m",
            Mouse(absolute=Position(x=6, y=4), motion=Position(x=3, y=2), button=None),
            id="release-lets-go-of-the-button",
        ),
    ],
)
async def test_mouse_input_from_the_terminal_reaches_use_mouse(
    terminal: Terminal, typed: bytes, expected: Mouse
) -> None:
    seen: list[Mouse] = []

    @component
    def root() -> Text:
        mouse = use_mouse()

        async def type_mouse_input() -> None:
            os.write(terminal.keyboard, typed)

        use_effect(type_mouse_input, deps=())
        seen.append(mouse)
        if mouse.absolute == expected.absolute:
            os.write(terminal.keyboard, b"q")
        return Text(content="", on_key=lambda event: Quit() if event.key == "q" else None)

    await wait_for(app(root(), output_stream=Output(), input_stream=terminal.stream, dimensions=(9, 6)), TIMEOUT)

    assert seen[-1] == expected


@pytest.mark.parametrize(
    ("autopilot", "before_resize"),
    [
        pytest.param([], TAKE_OVER + BLANK_SCREEN + HI, id="from-the-start"),
        pytest.param(
            [Suspend(handler=lambda: None)],
            TAKE_OVER + BLANK_SCREEN + HI + HAND_BACK + TAKE_OVER + BLANK_SCREEN + HI,
            id="after-a-suspension",
        ),
    ],
)
async def test_a_resize_signal_redraws_the_screen(
    terminal: Terminal, autopilot: list[AnyControl], before_resize: str
) -> None:
    output = Output()

    @component
    def root() -> Text:
        async def resize_then_quit() -> None:
            raise_signal(SIGWINCH)
            os.write(terminal.keyboard, b"q")

        use_effect(resize_then_quit, deps=())
        return Text(content="hi", style=text_black, on_key=lambda event: Quit() if event.key == "q" else None)

    await wait_for(
        app(root(), output_stream=output, input_stream=terminal.stream, dimensions=(3, 1), autopilot=autopilot),
        TIMEOUT,
    )

    assert output.getvalue().startswith(before_resize + BLANK_SCREEN)
