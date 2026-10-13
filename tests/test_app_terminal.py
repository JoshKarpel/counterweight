"""The render loop outside headless mode: what it writes to the terminal, and how it takes input from it."""

from __future__ import annotations

import io
import os
from asyncio import CancelledError, Event, create_task, get_running_loop, wait_for
from collections.abc import Iterator
from signal import SIGINT, SIGWINCH, raise_signal, signal

import pytest

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import AnyControl, Bell, Quit, Screenshot, Suspend
from counterweight.elements import Text
from counterweight.events import InputEvent, KeyPressed, Receiver
from counterweight.geometry import Position
from counterweight.hooks import Mouse, use_effect, use_mouse, use_state
from counterweight.output import (
    ALT_SCREEN_OFF,
    ALT_SCREEN_ON,
    CLEAR_SCREEN,
    CURSOR_OFF,
    CURSOR_ON,
    SET_ANY_EVENT_MOUSE_SGR_FORMAT,
    SYNCHRONIZED_OUTPUT_OFF,
    SYNCHRONIZED_OUTPUT_ON,
    UNSET_ANY_EVENT_MOUSE_SGR_FORMAT,
)
from counterweight.styles.utilities import text_black
from tests.devlog import devlog_lines
from tests.terminal import Terminal

TIMEOUT = 5

TAKE_OVER = ALT_SCREEN_ON + CURSOR_OFF + CLEAR_SCREEN + SET_ANY_EVENT_MOUSE_SGR_FORMAT
HAND_BACK = UNSET_ANY_EVENT_MOUSE_SGR_FORMAT + ALT_SCREEN_OFF + CURSOR_ON
HI = (
    SYNCHRONIZED_OUTPUT_ON
    + CLEAR_SCREEN
    + "\x1b[1;1f\x1b[0m\x1b[38;2;0;0;0m\x1b[48;2;0;0;0mhi \x1b[0m"
    + SYNCHRONIZED_OUTPUT_OFF
)


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


@component
def interrupt_on_key() -> Text:
    """Sends an interrupt for each key pressed, as ctrl+c would."""
    return Text(content="hi", style=text_black, on_input=lambda event, _: raise_signal(SIGINT))


def quit_on_q(event: InputEvent, _: Receiver) -> Quit | None:
    match event:
        case KeyPressed(key="q"):
            return Quit()
        case _:
            return None


@pytest.fixture
def replaced_interrupts() -> Iterator[list[int]]:
    """Installs an interrupt handler for the app to replace, and records the interrupts that reach it."""
    received: list[int] = []
    previous = signal(SIGINT, lambda signum, frame: received.append(signum))
    yield received
    signal(SIGINT, previous)


async def test_app_takes_over_the_terminal_draws_rings_the_bell_and_hands_it_back(terminal: Terminal) -> None:
    before = terminal.settings()
    output = Output()

    with devlog_lines() as lines:
        await app(
            hi(),
            output_stream=output,
            input_stream=terminal.stream,
            dimensions=(3, 1),
            autopilot=[Bell(), Screenshot(handler=lambda frame: None), Screenshot(handler=lambda frame: None), Quit()],
        )

    drawn = TAKE_OVER + HI
    assert [line for line in lines if "Wrote" in line] == [
        f"DEBUG    counterweight.app Wrote and flushed instructions to output stream bytes='{len(HI):_}'"
    ]
    assert output.getvalue() == drawn + "\a" + HAND_BACK
    assert output.flushed[2:4] == [drawn, drawn + "\a"]
    assert terminal.settings() == before


async def test_a_later_frame_draws_only_what_changed_in_one_synchronized_update(terminal: Terminal) -> None:
    output = Output()

    @component
    def root() -> Text:
        content, set_content = use_state("hi")
        return Text(content=content, style=text_black, on_input=lambda event, _: set_content("ho"))

    await app(
        root(),
        output_stream=output,
        input_stream=terminal.stream,
        dimensions=(3, 1),
        autopilot=[KeyPressed(key="o"), Quit()],
    )

    changed = "\x1b[1;2f\x1b[0m\x1b[38;2;0;0;0m\x1b[48;2;0;0;0mo\x1b[0m"
    assert output.getvalue() == TAKE_OVER + HI + SYNCHRONIZED_OUTPUT_ON + changed + SYNCHRONIZED_OUTPUT_OFF + HAND_BACK


async def test_suspend_hands_the_terminal_back_while_its_handler_runs(terminal: Terminal) -> None:
    before = terminal.settings()
    output = Output()
    during: list[tuple[str, object, bool]] = []

    def handler() -> None:
        is_read = get_running_loop().remove_reader(terminal.stream.fileno())
        during.append((output.getvalue(), terminal.settings(), is_read))

    await app(
        hi(),
        output_stream=output,
        input_stream=terminal.stream,
        dimensions=(3, 1),
        autopilot=[Suspend(handler=handler), Quit()],
    )

    frame = TAKE_OVER + HI + HAND_BACK
    assert during == [(frame, before, False)]
    assert output.getvalue() == frame + frame


async def test_app_reads_keys_from_the_terminal(terminal: Terminal) -> None:
    pressed: list[KeyPressed] = []

    def on_input(event: InputEvent, _: Receiver) -> AnyControl | None:
        assert isinstance(event, KeyPressed)
        pressed.append(event)
        return Quit() if event.key == "q" else None

    @component
    def root() -> Text:
        return Text(content="hi", on_input=on_input)

    os.write(terminal.keyboard, b"aq")

    await wait_for(app(root(), output_stream=Output(), input_stream=terminal.stream, dimensions=(3, 1)), TIMEOUT)

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
        return Text(content="", on_input=quit_on_q)

    await wait_for(app(root(), output_stream=Output(), input_stream=terminal.stream, dimensions=(9, 6)), TIMEOUT)

    assert seen[-1] == expected


@pytest.mark.parametrize(
    ("autopilot", "before_resize"),
    [
        pytest.param([], TAKE_OVER + HI, id="from-the-start"),
        pytest.param(
            [Suspend(handler=lambda: None)],
            TAKE_OVER + HI + HAND_BACK + TAKE_OVER + HI,
            id="after-a-suspension",
        ),
    ],
)
async def test_a_resize_signal_redraws_the_screen(
    terminal: Terminal, autopilot: list[AnyControl], before_resize: str
) -> None:
    output = Output()
    redraws = 0

    # The effect runs after each frame that redraws the whole screen,
    # except the first frame before a suspension, which cancels it before it starts.
    @component
    def root() -> Text:
        async def resize_then_quit_once_redrawn() -> None:
            nonlocal redraws
            redraws += 1
            if redraws == 1:
                raise_signal(SIGWINCH)
            else:
                os.write(terminal.keyboard, b"q")

        use_effect(resize_then_quit_once_redrawn)
        return Text(content="hi", style=text_black, on_input=quit_on_q)

    await wait_for(
        app(root(), output_stream=output, input_stream=terminal.stream, dimensions=(3, 1), autopilot=autopilot),
        TIMEOUT,
    )

    assert output.getvalue() == before_resize + HI + HAND_BACK


async def test_app_reads_keys_again_after_a_suspension(terminal: Terminal) -> None:
    pressed: list[KeyPressed] = []

    def on_input(event: InputEvent, _: Receiver) -> AnyControl | None:
        assert isinstance(event, KeyPressed)
        pressed.append(event)
        return Quit()

    @component
    def root() -> Text:
        return Text(content="hi", on_input=on_input)

    def type_quit_while_suspended() -> None:
        os.write(terminal.keyboard, b"q")

    await wait_for(
        app(
            root(),
            output_stream=Output(),
            input_stream=terminal.stream,
            dimensions=(3, 1),
            autopilot=[Suspend(handler=type_quit_while_suspended)],
        ),
        TIMEOUT,
    )

    assert pressed == [KeyPressed(key="q")]


async def test_cancelling_an_app_hands_the_terminal_back_and_cancels_the_caller(terminal: Terminal) -> None:
    before = terminal.settings()
    output = Output()
    started = Event()

    @component
    def root() -> Text:
        async def signal_started() -> None:
            started.set()

        use_effect(signal_started, deps=())
        return Text(content="hi", style=text_black)

    running = create_task(app(root(), output_stream=output, input_stream=terminal.stream, dimensions=(3, 1)))
    await wait_for(started.wait(), TIMEOUT)
    running.cancel()

    with pytest.raises(CancelledError):
        await running
    assert output.getvalue().endswith(HAND_BACK)
    assert terminal.settings() == before
    assert not get_running_loop().remove_reader(terminal.stream.fileno())


async def test_an_interrupt_quits_the_app_and_hands_the_terminal_back(
    terminal: Terminal, replaced_interrupts: list[int]
) -> None:
    before = terminal.settings()
    output = Output()
    os.write(terminal.keyboard, b"i")

    await wait_for(
        app(interrupt_on_key(), output_stream=output, input_stream=terminal.stream, dimensions=(3, 1)), TIMEOUT
    )

    assert output.getvalue().endswith(HAND_BACK)
    assert terminal.settings() == before
    assert replaced_interrupts == []


async def test_a_second_interrupt_reaches_the_handler_the_app_replaced(
    terminal: Terminal, replaced_interrupts: list[int]
) -> None:
    def interrupt_twice(event: InputEvent, _: Receiver) -> None:
        raise_signal(SIGINT)
        raise_signal(SIGINT)

    @component
    def root() -> Text:
        return Text(content="hi", on_input=interrupt_twice)

    os.write(terminal.keyboard, b"i")

    await wait_for(app(root(), output_stream=Output(), input_stream=terminal.stream, dimensions=(3, 1)), TIMEOUT)

    assert replaced_interrupts == [SIGINT]


async def test_the_app_puts_back_the_interrupt_handler_it_replaced_when_it_returns(
    terminal: Terminal, replaced_interrupts: list[int]
) -> None:
    await app(hi(), output_stream=Output(), input_stream=terminal.stream, dimensions=(3, 1), autopilot=[Quit()])
    raise_signal(SIGINT)

    assert replaced_interrupts == [SIGINT]


async def test_a_suspension_puts_back_the_interrupt_handler_while_its_handler_runs(
    terminal: Terminal, replaced_interrupts: list[int]
) -> None:
    await app(
        hi(),
        output_stream=Output(),
        input_stream=terminal.stream,
        dimensions=(3, 1),
        autopilot=[Suspend(handler=lambda: raise_signal(SIGINT)), Quit()],
    )

    assert replaced_interrupts == [SIGINT]


async def test_an_interrupt_quits_the_app_after_a_suspension(
    terminal: Terminal, replaced_interrupts: list[int]
) -> None:
    def type_while_suspended() -> None:
        os.write(terminal.keyboard, b"i")

    await wait_for(
        app(
            interrupt_on_key(),
            output_stream=Output(),
            input_stream=terminal.stream,
            dimensions=(3, 1),
            autopilot=[Suspend(handler=type_while_suspended)],
        ),
        TIMEOUT,
    )

    assert replaced_interrupts == []
