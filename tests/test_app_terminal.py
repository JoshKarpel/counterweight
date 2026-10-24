"""The render loop outside headless mode: what it writes to the terminal, and how it takes input from it."""

from __future__ import annotations

import io
import os
import termios
from asyncio import CancelledError
from asyncio import Event
from asyncio import create_task
from asyncio import get_running_loop
from asyncio import wait_for
from collections.abc import Callable
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from signal import SIGINT
from signal import SIGWINCH
from signal import raise_signal
from signal import signal
from typing import TextIO

import pytest

from counterweight import app
from counterweight._app import terminal_dimensions
from counterweight._output import ALT_SCREEN_OFF
from counterweight._output import ALT_SCREEN_ON
from counterweight._output import BRACKETED_PASTE_OFF
from counterweight._output import BRACKETED_PASTE_ON
from counterweight._output import CLEAR_SCREEN
from counterweight._output import CURSOR_OFF
from counterweight._output import CURSOR_ON
from counterweight._output import RESTORE_TITLE
from counterweight._output import SAVE_TITLE
from counterweight._output import SET_ANY_EVENT_MOUSE_SGR_FORMAT
from counterweight._output import SYNCHRONIZED_OUTPUT_OFF
from counterweight._output import SYNCHRONIZED_OUTPUT_ON
from counterweight._output import UNSET_ANY_EVENT_MOUSE_SGR_FORMAT
from counterweight._output import clipboard_instructions
from counterweight._output import title_instructions
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import AnyControl
from counterweight.controls import Bell
from counterweight.controls import CopyToClipboard
from counterweight.controls import FocusOn
from counterweight.controls import Quit
from counterweight.controls import RestoreTitle
from counterweight.controls import Screenshot
from counterweight.controls import SetTitle
from counterweight.controls import Suspend
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.focus import FocusHandle
from counterweight.geometry import Position
from counterweight.handlers import first
from counterweight.headless import use_text_input
from counterweight.hooks import Mouse
from counterweight.hooks import use_effect
from counterweight.hooks import use_focus
from counterweight.hooks import use_mouse
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.programs import TerminalStreams
from counterweight.styles.utilities import text_black
from tests.devlog import devlog_lines
from tests.terminal import Terminal

TIMEOUT = 5

TAKE_OVER = ALT_SCREEN_ON + CURSOR_OFF + CLEAR_SCREEN + SAVE_TITLE + SET_ANY_EVENT_MOUSE_SGR_FORMAT + BRACKETED_PASTE_ON
HAND_BACK = BRACKETED_PASTE_OFF + UNSET_ANY_EVENT_MOUSE_SGR_FORMAT + ALT_SCREEN_OFF + CURSOR_ON + RESTORE_TITLE


def drawn(row: str) -> str:
    """A frame that clears the screen and draws `row`, in `text_black`, as its only row."""
    return (
        SYNCHRONIZED_OUTPUT_ON
        + CLEAR_SCREEN
        + f"\x1b[1;1f\x1b[0m\x1b[38;2;0;0;0m\x1b[48;2;0;0;0m{row}\x1b[0m"
        + SYNCHRONIZED_OUTPUT_OFF
    )


HI = drawn("hi ")


class Output(io.StringIO):
    """Terminal output that records everything written before each flush."""

    def __init__(self) -> None:
        super().__init__()
        self.flushed: list[str] = []

    def flush(self) -> None:
        self.flushed.append(self.getvalue())


class TerminalOutput(Output):
    """Output that reports the file descriptor of a terminal, as `/dev/tty` opened for writing would."""

    def __init__(self, terminal: Terminal) -> None:
        super().__init__()
        self.terminal = terminal

    def fileno(self) -> int:
        return self.terminal.stream.fileno()


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
        f"DEBUG    counterweight._app Wrote and flushed instructions to output stream bytes='{len(HI):_}'"
    ]
    assert output.getvalue() == drawn + "\a" + HAND_BACK
    assert output.flushed[3:5] == [drawn, drawn + "\a"]
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

    def handler(streams: TerminalStreams) -> None:
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


async def test_a_suspend_handler_receives_the_streams_the_app_draws_on_and_reads_from(terminal: Terminal) -> None:
    output = Output()
    received: list[TerminalStreams] = []

    await app(
        hi(),
        output_stream=output,
        input_stream=terminal.stream,
        dimensions=(3, 1),
        autopilot=[Suspend(handler=received.append), Quit()],
    )

    assert received == [TerminalStreams(input=terminal.stream, output=output)]


async def test_set_title_sets_the_title_once_for_each_change(terminal: Terminal) -> None:
    output = Output()

    await app(
        hi(),
        output_stream=output,
        input_stream=terminal.stream,
        dimensions=(3, 1),
        autopilot=[SetTitle(title="one"), SetTitle(title="one"), SetTitle(title="two"), Quit()],
    )

    assert output.getvalue() == TAKE_OVER + HI + title_instructions("one") + title_instructions("two") + HAND_BACK


async def test_copy_to_clipboard_copies_the_last_text_copied_in_each_cycle(terminal: Terminal) -> None:
    output = Output()

    @component
    def root() -> Text:
        return Text(
            content="hi",
            style=text_black,
            on_input=lambda event, _: (CopyToClipboard(text="one"), CopyToClipboard(text="two")),
        )

    await app(
        root(),
        output_stream=output,
        input_stream=terminal.stream,
        dimensions=(3, 1),
        autopilot=[KeyPressed(key="c"), CopyToClipboard(text="two"), Quit()],
    )

    copy = clipboard_instructions("two")
    assert output.getvalue() == TAKE_OVER + HI + copy + copy + HAND_BACK
    assert TAKE_OVER + HI + copy in output.flushed


@pytest.mark.parametrize("is_the_apps", [False, True], ids=["copys-own", "apps"])
async def test_a_copy_to_a_handler_writes_nothing_to_the_terminal(terminal: Terminal, is_the_apps: bool) -> None:
    output = Output()
    copied: list[str] = []

    await app(
        hi(),
        output_stream=output,
        input_stream=terminal.stream,
        dimensions=(3, 1),
        autopilot=[CopyToClipboard(text="two", handler=None if is_the_apps else copied.append), Quit()],
        clipboard_handler=copied.append if is_the_apps else None,
    )

    assert output.getvalue() == TAKE_OVER + HI + HAND_BACK
    assert copied == ["two"]


async def test_the_title_app_is_given_is_set_before_the_first_frame(terminal: Terminal) -> None:
    output = Output()

    await app(
        hi(),
        output_stream=output,
        input_stream=terminal.stream,
        dimensions=(3, 1),
        autopilot=[SetTitle(title="start"), SetTitle(title="later"), Quit()],
        title="start",
    )

    assert output.getvalue() == TAKE_OVER + title_instructions("start") + HI + title_instructions("later") + HAND_BACK


async def test_restore_title_restores_the_original_title_only_after_another_was_set(terminal: Terminal) -> None:
    output = Output()

    await app(
        hi(),
        output_stream=output,
        input_stream=terminal.stream,
        dimensions=(3, 1),
        autopilot=[RestoreTitle(), SetTitle(title="mine"), RestoreTitle(), RestoreTitle(), Quit()],
    )

    assert output.getvalue() == TAKE_OVER + HI + title_instructions("mine") + RESTORE_TITLE + SAVE_TITLE + HAND_BACK


async def test_a_suspension_restores_the_title_while_its_handler_runs_then_sets_it_again(terminal: Terminal) -> None:
    output = Output()
    during: list[str] = []

    await app(
        hi(),
        output_stream=output,
        input_stream=terminal.stream,
        dimensions=(3, 1),
        autopilot=[SetTitle(title="mine"), Suspend(handler=lambda streams: during.append(output.getvalue())), Quit()],
    )

    titled = TAKE_OVER + HI + title_instructions("mine") + HAND_BACK
    assert during == [titled]
    assert output.getvalue() == titled + TAKE_OVER + title_instructions("mine") + HI + HAND_BACK


async def test_an_interrupt_in_a_suspend_handler_quits_without_handing_the_terminal_back_twice(
    terminal: Terminal,
) -> None:
    output = Output()

    def interrupted(streams: TerminalStreams) -> None:
        raise KeyboardInterrupt

    await app(
        hi(),
        output_stream=output,
        input_stream=terminal.stream,
        dimensions=(3, 1),
        autopilot=[Suspend(handler=interrupted)],
    )

    assert output.getvalue() == TAKE_OVER + HI + HAND_BACK


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


async def typed_into_text_input(terminal: Terminal, typed: bytes) -> str:
    """
    The value of a focused text input once `typed` reaches it in one read, followed by Enter,
    which the input passes on to quit before the edits render.
    """
    values: list[str] = []

    @component
    def root() -> Text:
        value, set_value = use_state("")

        def set_recorded(edit: Callable[[str], str]) -> None:
            def recorded(latest: str) -> str:
                values.append(edit(latest))
                return values[-1]

            set_value(recorded)

        field = use_text_input(value, set_recorded, auto_focus=True)
        return Text(content=value, on_input=first(field.on_input, lambda event, _: Quit()))

    os.write(terminal.keyboard, typed + b"\r")

    await wait_for(app(root(), output_stream=Output(), input_stream=terminal.stream, dimensions=(20, 1)), TIMEOUT)

    return values[-1]


async def test_keys_typed_in_one_read_each_edit_a_text_input_in_turn(terminal: Terminal) -> None:
    assert await typed_into_text_input(terminal, b"hello\x1b[D\x1b[DXY") == "helXYlo"


async def test_a_bracketed_paste_reaches_a_text_input_as_one_edit(terminal: Terminal) -> None:
    assert await typed_into_text_input(terminal, b"<>\x1b[D\x1b[200~one\rtwo\x1b[201~") == "<one two>"


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
            [Suspend(handler=lambda streams: None)],
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


async def test_app_sizes_the_screen_from_the_terminal_its_output_stream_writes_to(terminal: Terminal) -> None:
    output = TerminalOutput(terminal)
    termios.tcsetwinsize(terminal.stream, (1, 5))
    redraws = 0

    @component
    def root() -> Text:
        async def resize_then_quit_once_redrawn() -> None:
            nonlocal redraws
            redraws += 1
            if redraws == 1:
                termios.tcsetwinsize(terminal.stream, (1, 8))
                raise_signal(SIGWINCH)
            else:
                os.write(terminal.keyboard, b"q")

        use_effect(resize_then_quit_once_redrawn)
        return Text(content="hi", style=text_black, on_input=quit_on_q)

    await wait_for(app(root(), output_stream=output, input_stream=terminal.stream), TIMEOUT)

    assert output.getvalue() == TAKE_OVER + drawn("hi   ") + drawn("hi      ") + HAND_BACK


@pytest.mark.parametrize(
    ("reported", "expected"),
    [
        pytest.param((97, 31), (97, 31), id="both"),
        pytest.param((0, 0), (80, 24), id="neither"),
        pytest.param((0, 31), (80, 31), id="no-columns"),
        pytest.param((97, 0), (97, 24), id="no-rows"),
    ],
)
def test_terminal_dimensions_are_80_by_24_where_the_terminal_reports_0(
    terminal: Terminal, reported: tuple[int, int], expected: tuple[int, int]
) -> None:
    columns, rows = reported
    termios.tcsetwinsize(terminal.stream, (rows, columns))

    assert terminal_dimensions(terminal.stream) == expected


@pytest.mark.parametrize(
    ("reported", "expected"),
    [
        pytest.param((97, 31), (97, 31), id="terminal"),
        pytest.param((0, 0), (80, 24), id="unknown"),
    ],
)
def test_terminal_dimensions_ignore_the_environment(
    terminal: Terminal, monkeypatch: pytest.MonkeyPatch, reported: tuple[int, int], expected: tuple[int, int]
) -> None:
    monkeypatch.setenv("COLUMNS", "150")
    monkeypatch.setenv("LINES", "60")
    columns, rows = reported
    termios.tcsetwinsize(terminal.stream, (rows, columns))

    assert terminal_dimensions(terminal.stream) == expected


def pipe_stream(stack: ExitStack, tmp_path: Path) -> TextIO:
    """The write end of a pipe, which has a file descriptor that isn't a terminal."""
    read, write = os.pipe()
    stack.callback(os.close, read)
    return stack.enter_context(os.fdopen(write, "w"))


def file_stream(stack: ExitStack, tmp_path: Path) -> TextIO:
    """A regular file opened for writing, which has a file descriptor that isn't a terminal."""
    return stack.enter_context((tmp_path / "file").open("w"))


def closed_stream(stack: ExitStack, tmp_path: Path) -> TextIO:
    """A file that's already closed, whose `fileno` raises `ValueError`."""
    closed = (tmp_path / "closed").open("w")
    closed.close()
    return closed


def string_stream(stack: ExitStack, tmp_path: Path) -> TextIO:
    """A stream in memory, whose `fileno` raises `io.UnsupportedOperation`."""
    return io.StringIO()


@pytest.mark.parametrize("make_stream", [pipe_stream, file_stream, closed_stream, string_stream])
def test_streams_that_are_not_terminals_are_80_by_24(
    tmp_path: Path, make_stream: Callable[[ExitStack, Path], TextIO]
) -> None:
    with ExitStack() as stack:
        stream = make_stream(stack, tmp_path)

        assert terminal_dimensions(stream) == (80, 24)


async def test_app_reads_keys_again_after_a_suspension(terminal: Terminal) -> None:
    pressed: list[KeyPressed] = []

    def on_input(event: InputEvent, _: Receiver) -> AnyControl | None:
        assert isinstance(event, KeyPressed)
        pressed.append(event)
        return Quit()

    @component
    def root() -> Text:
        return Text(content="hi", on_input=on_input)

    def type_quit_while_suspended(streams: TerminalStreams) -> None:
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
        autopilot=[Suspend(handler=lambda streams: raise_signal(SIGINT)), Quit()],
    )

    assert replaced_interrupts == [SIGINT]


async def test_an_interrupt_quits_the_app_after_a_suspension(
    terminal: Terminal, replaced_interrupts: list[int]
) -> None:
    def type_while_suspended(streams: TerminalStreams) -> None:
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


def typing_root(
    keyboard: int,
    typed: bytes,
    pressed: list[KeyPressed],
    claims: bool,
    is_ready: Callable[[], bool] = lambda: True,
) -> Component:
    """
    A root that types `typed` on `keyboard` after each frame once `is_ready`, rather than before the app starts,
    since the terminal acts on each key as it arrives, in the mode it's in then,
    and records each key pressed, claiming each one if `claims`, and quitting on Ctrl+C if it claims it.
    """

    @component
    def root() -> Text:
        async def type_keys() -> None:
            if is_ready():
                os.write(keyboard, typed)

        use_effect(type_keys)

        def on_input(event: InputEvent, _: Receiver) -> InputResponse:
            assert isinstance(event, KeyPressed)
            pressed.append(event)
            if not claims:
                return None
            return Quit() if event.key == Key.ControlC else ()

        return Text(content="hi", on_input=on_input)

    return root()


async def test_ctrl_c_and_the_other_keys_a_terminal_acts_on_reach_the_app_as_key_presses(
    terminal: Terminal, replaced_interrupts: list[int]
) -> None:
    pressed: list[KeyPressed] = []
    root = typing_root(terminal.keyboard, b"\x1a\x1c\x13\x11\x03", pressed, claims=True)

    await wait_for(app(root, output_stream=Output(), input_stream=terminal.stream, dimensions=(3, 1)), TIMEOUT)

    assert pressed == [
        KeyPressed(key=Key.ControlZ),
        KeyPressed(key=Key.ControlBackslash),
        KeyPressed(key=Key.ControlS),
        KeyPressed(key=Key.ControlQ),
        KeyPressed(key=Key.ControlC),
    ]
    assert replaced_interrupts == []


async def test_ctrl_c_quits_an_app_that_does_not_claim_it(terminal: Terminal, replaced_interrupts: list[int]) -> None:
    pressed: list[KeyPressed] = []
    root = typing_root(terminal.keyboard, b"\x03", pressed, claims=False)

    await wait_for(app(root, output_stream=Output(), input_stream=terminal.stream, dimensions=(3, 1)), TIMEOUT)

    assert pressed == [KeyPressed(key=Key.ControlC)]
    assert replaced_interrupts == []


async def test_the_app_reads_raw_again_after_a_suspension(terminal: Terminal) -> None:
    pressed: list[KeyPressed] = []
    during: list[object] = []

    def record_settings(streams: TerminalStreams) -> None:
        during.append(terminal.settings())

    root = typing_root(terminal.keyboard, b"\x03", pressed, claims=True, is_ready=lambda: bool(during))

    before = terminal.settings()
    await wait_for(
        app(
            root,
            output_stream=Output(),
            input_stream=terminal.stream,
            dimensions=(3, 1),
            autopilot=[Suspend(handler=record_settings)],
        ),
        TIMEOUT,
    )

    assert during == [before]
    assert pressed == [KeyPressed(key=Key.ControlC)]


async def test_a_key_read_with_one_that_mounts_and_focuses_a_component_goes_to_the_component_focused_before(
    terminal: Terminal,
) -> None:
    received: list[tuple[str, str]] = []
    handle = FocusHandle()

    def recording(name: str) -> Callable[[InputEvent, Receiver], InputResponse]:
        def on_input(event: InputEvent, _: Receiver) -> InputResponse:
            match event:
                case KeyPressed(key="?" as key):
                    received.append((name, key))
                    return ()
                case _:
                    return None

        return on_input

    @component
    def late() -> Text:
        use_focus(handle=handle)

        async def type_once_mounted() -> None:
            os.write(terminal.keyboard, b"?q")

        use_effect(type_once_mounted, deps=())
        return Text(content="late", on_input=recording("late"))

    @component
    def root() -> Div:
        is_mounted, set_mounted = use_state(False)

        def on_input(event: InputEvent, _: Receiver) -> InputResponse:
            if event != KeyPressed(key="t"):
                return Quit()
            set_mounted(True)
            return FocusOn(handle)

        return Div(on_input=first(recording("root"), on_input), children=(late(),) if is_mounted else ())

    os.write(terminal.keyboard, b"t?")

    await wait_for(app(root(), output_stream=Output(), input_stream=terminal.stream, dimensions=(9, 1)), TIMEOUT)

    assert received == [("root", "?"), ("late", "?")]
