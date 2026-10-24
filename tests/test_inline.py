"""Inline apps: drawing a region below the prompt, growing and shrinking it, and leaving it when they stop."""

from __future__ import annotations

import fcntl
import io
import json
import os
import pty
import struct
import termios
from asyncio import wait_for
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path
from threading import Event
from threading import Thread

import pytest

from counterweight import FullScreen
from counterweight import Inline
from counterweight import app
from counterweight._output import BRACKETED_PASTE_OFF
from counterweight._output import BRACKETED_PASTE_ON
from counterweight._output import ERASE_DOWN
from counterweight._output import INLINE_OUTPUT_CONTROL_START
from counterweight._output import Frame
from counterweight._output import output_control_stop
from counterweight.asciicast import Recording
from counterweight.autopilot import AutopilotStep
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import Print
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.controls import Suspend
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.emulator import Emulator
from counterweight.events import InputEvent
from counterweight.events import InputHandler
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseUp
from counterweight.events import Receiver
from counterweight.events import TerminalResized
from counterweight.geometry import Position
from counterweight.handlers import on_click
from counterweight.hooks import use_effect
from counterweight.hooks import use_state
from counterweight.styles.utilities import col
from counterweight.styles.utilities import min_height
from counterweight.styles.utilities import overflow_y_scroll
from counterweight.styles.utilities import text_wrap_none
from tests.rendering import TIMEOUT
from tests.terminal import Terminal


@component
def rows(count: int) -> Div:
    """`count` rows, then one more for each `+` pressed and one fewer for any other input."""
    shown, set_shown = use_state(count)

    def on_input(event: InputEvent, _: Receiver) -> None:
        set_shown(shown + 1 if event == KeyPressed(key="+") else shown - 1)

    return Div(
        style=col,
        on_input=on_input,
        children=tuple(Text(content=f"row {index} wraps", style=text_wrap_none) for index in range(shown)),
    )


def held(frame: Frame) -> list[str]:
    """What each row of the terminal holds, without trailing spaces."""
    return [line.rstrip() for line in frame.text(ansi=False).split("\n")]


async def terminal_frames(
    root: Component,
    steps: Sequence[AutopilotStep],
    dimensions: tuple[int, int] = (16, 4),
    include_scrollback: bool = True,
    mouse: bool = False,
) -> list[list[str]]:
    """What the terminal holds after each `Screenshot` among `steps`, which this fills in, of an inline app run headless."""
    frames: list[Frame] = []
    await app(
        root,
        headless=True,
        dimensions=dimensions,
        viewport=Inline(mouse=mouse),
        autopilot=[
            *(
                Screenshot(handler=frames.append, include_scrollback=include_scrollback)
                if isinstance(step, Screenshot)
                else step
                for step in steps
            ),
            Quit(),
        ],
    )
    return [held(frame) for frame in frames]


SHOT = Screenshot(handler=lambda frame: None)


async def test_an_inline_app_draws_its_region_at_the_top_of_an_empty_terminal() -> None:
    assert await terminal_frames(rows(2), [SHOT]) == [["row 0 wraps", "row 1 wraps", "", ""]]


async def test_a_screenshot_without_the_scrollback_is_the_region() -> None:
    assert await terminal_frames(rows(2), [SHOT], include_scrollback=False) == [["row 0 wraps", "row 1 wraps"]]


async def test_the_region_grows_and_shrinks_with_its_content() -> None:
    frames = await terminal_frames(
        rows(1), [KeyPressed(key="+"), KeyPressed(key="+"), SHOT, KeyPressed(key="-"), KeyPressed(key="-"), SHOT]
    )

    assert frames == [["row 0 wraps", "row 1 wraps", "row 2 wraps", ""], ["row 0 wraps", "", "", ""]]


async def test_a_region_taller_than_the_terminal_is_cut_off_at_the_bottom() -> None:
    assert await terminal_frames(rows(6), [SHOT], include_scrollback=False) == [
        ["row 0 wraps", "row 1 wraps", "row 2 wraps", "row 3 wraps"]
    ]


@component
def log_above_status() -> Div:
    return Div(
        style=col | min_height(0),
        children=(
            Div(style=col | overflow_y_scroll, children=tuple(Text(content=f"log {index}") for index in range(6))),
            Text(content="status"),
        ),
    )


async def test_a_root_that_can_shrink_shrinks_to_the_terminals_height() -> None:
    assert await terminal_frames(log_above_status(), [SHOT]) == [["log 0", "log 1", "log 2", "status"]]


@pytest.mark.parametrize(
    ("width", "expected"),
    [(8, ["row 0 wr", "row 1 wr", "", ""]), (24, ["row 0 wraps", "row 1 wraps", "", ""])],
    ids=["narrower", "wider"],
)
async def test_a_resize_redraws_the_region_from_its_top(width: int, expected: list[str]) -> None:
    frames = await terminal_frames(rows(2), [TerminalResized(dimensions=(width, 4)), SHOT])

    assert frames == [expected]


async def test_a_region_that_rewraps_onto_more_rows_leaves_none_of_them_behind() -> None:
    frames = await terminal_frames(
        rows(2), [TerminalResized(dimensions=(6, 4)), TerminalResized(dimensions=(16, 4)), SHOT]
    )

    assert frames == [["row 0 wraps", "row 1 wraps", "", ""]]


async def test_a_suspended_inline_app_redraws_its_region_where_it_was() -> None:
    frames = await terminal_frames(rows(2), [Suspend(handler=lambda streams: None), SHOT])

    assert frames == [["row 0 wraps", "row 1 wraps", "", ""]]


async def test_a_full_screen_apps_screenshot_is_the_same_with_or_without_the_scrollback() -> None:
    frames: list[Frame] = []
    await app(
        rows(2),
        headless=True,
        dimensions=(16, 3),
        autopilot=[
            Screenshot(handler=frames.append),
            Screenshot(handler=frames.append, include_scrollback=True),
            Quit(),
        ],
    )

    assert frames[0] == frames[1]
    assert held(frames[0]) == ["row 0 wraps", "row 1 wraps", ""]


def fake_history(lines: int) -> bytes:
    return b"".join(b"$ history %d\r\n" % index for index in range(lines))


async def run_on_terminal(
    terminal: Terminal, root: Component, steps: Sequence[AutopilotStep], viewport: Inline, dimensions: tuple[int, int]
) -> str:
    """What `root` writes to its terminal, run on one, as `viewport` takes it over and hands it back."""
    output = io.StringIO()
    await app(
        root,
        output_stream=output,
        input_stream=terminal.stream,
        dimensions=dimensions,
        viewport=viewport,
        autopilot=[*steps, Quit()],
    )
    return output.getvalue()


def shown_after(history: int, written: str, dimensions: tuple[int, int], then: bytes = b"") -> list[str]:
    """What a terminal holds after `history` lines of shell history, then what an app wrote, then `then`."""
    with Emulator(*dimensions, on_reply=lambda reply: None, scrollback=100) as emulator:
        emulator.feed(fake_history(history) + written.encode() + then)
        lines = emulator.history() + emulator.snapshot().lines
    return ["".join(cell.grapheme for cell in line).rstrip() for line in lines]


async def test_an_inline_app_on_a_terminal_draws_what_a_headless_one_shows_below_the_history(
    terminal: Terminal,
) -> None:
    steps: list[AutopilotStep] = [KeyPressed(key="+"), KeyPressed(key="-"), KeyPressed(key="-")]
    written = await run_on_terminal(terminal, rows(3), steps, Inline(), (16, 5))
    headless = await terminal_frames(rows(3), [*steps, SHOT], dimensions=(16, 5))

    assert without_trailing_blanks(shown_after(2, written, (16, 5))) == [
        "$ history 0",
        "$ history 1",
        *without_trailing_blanks(headless[0]),
    ]


def without_trailing_blanks(lines: list[str]) -> list[str]:
    while lines and not lines[-1]:
        lines = lines[:-1]
    return lines


async def test_an_inline_app_that_keeps_its_last_frame_leaves_the_prompt_below_it(terminal: Terminal) -> None:
    written = await run_on_terminal(terminal, rows(2), [], Inline(), (16, 5))

    assert shown_after(1, written, (16, 5), then=b"$ next") == [
        "$ history 0",
        "row 0 wraps",
        "row 1 wraps",
        "$ next",
        "",
    ]


async def test_an_inline_app_that_keeps_its_last_frame_scrolls_to_leave_the_prompt_below_it(
    terminal: Terminal,
) -> None:
    written = await run_on_terminal(terminal, rows(2), [], Inline(), (16, 3))

    assert shown_after(2, written, (16, 3), then=b"$ next") == [
        "$ history 0",
        "$ history 1",
        "row 0 wraps",
        "row 1 wraps",
        "$ next",
    ]


async def test_an_inline_app_that_doesnt_keep_its_last_frame_leaves_the_prompt_where_it_started(
    terminal: Terminal,
) -> None:
    written = await run_on_terminal(terminal, rows(2), [], Inline(keep_last_frame=False), (16, 5))

    assert shown_after(1, written, (16, 5), then=b"$ next") == ["$ history 0", "$ next", "", "", ""]


async def test_an_inline_app_takes_the_terminal_without_the_alternate_screen_or_the_mouse(terminal: Terminal) -> None:
    written = await run_on_terminal(terminal, rows(1), [], Inline(), (16, 5))

    assert written.startswith(INLINE_OUTPUT_CONTROL_START + BRACKETED_PASTE_ON)
    assert written.endswith(BRACKETED_PASTE_OFF + output_control_stop(Inline()))


async def test_a_suspended_inline_app_erases_its_region_before_handing_the_terminal_back(terminal: Terminal) -> None:
    during: list[str] = []
    output = io.StringIO()

    await app(
        rows(2),
        output_stream=output,
        input_stream=terminal.stream,
        dimensions=(16, 5),
        viewport=Inline(),
        autopilot=[Suspend(handler=lambda streams: during.append(output.getvalue())), Quit()],
    )

    assert during[0].endswith(ERASE_DOWN + BRACKETED_PASTE_OFF + output_control_stop(Inline()))
    assert shown_after(0, during[0], (16, 5)) == ["", "", "", "", ""]


async def test_a_full_screen_app_without_the_mouse_never_tracks_it(terminal: Terminal) -> None:
    output = io.StringIO()

    await app(
        rows(1),
        output_stream=output,
        input_stream=terminal.stream,
        dimensions=(16, 2),
        viewport=FullScreen(mouse=False),
        autopilot=[Suspend(handler=lambda streams: None), Quit()],
    )

    assert "\x1b[?100" not in output.getvalue()
    assert "\x1b[?1049h" in output.getvalue()


@component
def quits_on_a_key() -> Text:
    count, set_count = use_state(0)

    def on_input(event: InputEvent, _: Receiver) -> Quit:
        set_count(count + 1)
        return Quit()

    return Text(content=f"count {count}", on_input=on_input)


async def test_quitting_leaves_a_last_frame_of_what_the_last_handlers_set(terminal: Terminal) -> None:
    written = await run_on_terminal(terminal, quits_on_a_key(), [KeyPressed(key="x")], Inline(), (10, 3))

    assert shown_after(0, written, (10, 3)) == ["count 1", "", ""]


async def test_the_render_before_quitting_starts_no_effects() -> None:
    started: list[int] = []

    @component
    def counter() -> Text:
        count, set_count = use_state(0)

        async def start() -> None:
            started.append(count)

        use_effect(start, deps=(count,))

        def on_input(event: InputEvent, _: Receiver) -> Quit:
            set_count(count + 1)
            return Quit()

        return Text(content=f"count {count}", on_input=on_input)

    await app(counter(), headless=True, dimensions=(10, 2), autopilot=[KeyPressed(key="x")])

    assert started == [0]


async def test_an_inline_recording_takes_the_terminal_without_the_alternate_screen_and_leaves_the_region(
    tmp_path: Path,
) -> None:
    path = tmp_path / "inline.cast"

    await app(
        rows(2),
        headless=True,
        dimensions=(16, 4),
        viewport=Inline(),
        autopilot=[Quit()],
        recording=Recording(path),
    )

    header, *events = (json.loads(line) for line in path.read_text().splitlines())
    output = "".join(data for _, code, data in events if code == "o")
    assert header["term"] == {"cols": 16, "rows": 4, "type": "xterm-256color"}
    assert output.startswith(INLINE_OUTPUT_CONTROL_START)
    assert shown_after(0, output, (16, 4), then=b"$") == ["row 0 wraps", "row 1 wraps", "$", ""]


@component
def clickable() -> Div:
    """Two lines to click, a line that says which was clicked last, and a print for each key pressed."""
    clicked, set_clicked = use_state("nothing")

    def click(name: str) -> InputHandler:
        def clicked_on() -> Quit | None:
            set_clicked(name)
            return Quit() if name == "second" else None

        return on_click(clicked_on)

    return Div(
        style=col,
        on_input=lambda event, _: Print(Text(content="printed")) if isinstance(event, KeyPressed) else None,
        children=(
            Text(content="first", on_input=click("first")),
            Text(content="second", on_input=click("second")),
            Text(content=f"clicked {clicked}"),
        ),
    )


def click_at(y: int) -> list[AutopilotStep]:
    return [MouseDown(absolute=Position(x=1, y=y), button=1), MouseUp(absolute=Position(x=1, y=y), button=1)]


async def test_a_click_on_an_inline_region_below_what_it_printed_lands_on_the_element_under_it() -> None:
    frames = await terminal_frames(
        clickable(), [KeyPressed(key="x"), KeyPressed(key="x"), *click_at(2), SHOT], dimensions=(16, 6), mouse=True
    )

    assert frames == [["printed", "printed", "first", "second", "clicked first", ""]]


async def test_a_click_above_an_inline_region_is_dropped() -> None:
    frames = await terminal_frames(
        clickable(), [KeyPressed(key="x"), *click_at(1), *click_at(0), SHOT], dimensions=(16, 6), mouse=True
    )

    assert frames == [["printed", "first", "second", "clicked first", "", ""]]


async def test_a_click_on_an_inline_region_pushed_to_the_bottom_lands_on_the_element_under_it() -> None:
    frames = await terminal_frames(
        clickable(), [*[KeyPressed(key="x")] * 4, *click_at(3), SHOT], dimensions=(16, 6), mouse=True
    )

    assert frames == [["printed", "printed", "printed", "printed", "first", "second", "clicked first"]]


async def test_an_inline_app_that_tracks_the_mouse_turns_tracking_on(terminal: Terminal) -> None:
    written = await run_on_terminal(terminal, rows(1), [], Inline(mouse=True), (16, 5))

    assert written.startswith(INLINE_OUTPUT_CONTROL_START + "\x1b[?1003h\x1b[?1006h")


async def test_clicks_on_a_terminal_land_where_the_terminal_says_the_region_is() -> None:
    """
    A terminal below two lines of history, which answers the app's request for the cursor's position,
    and clicks the region's second line once it has answered and the region is drawn.
    """
    screen, program = pty.openpty()
    fcntl.ioctl(program, termios.TIOCSWINSZ, struct.pack("HHHH", 6, 16, 0, 0))
    clicked = Event()

    def be_the_terminal() -> None:
        answered = False

        def answer(reply: bytes) -> None:
            nonlocal answered
            os.write(screen, reply)
            answered = True

        with Emulator(16, 6, on_reply=answer) as emulator:
            emulator.feed(b"history 0\r\nhistory 1\r\n")
            with suppress(OSError):
                while data := os.read(screen, 2**12):  # pragma: no branch, Linux raises EIO at the end
                    emulator.feed(data)
                    lines = ["".join(cell.grapheme for cell in line).rstrip() for line in emulator.snapshot().lines]
                    if answered and "second" in lines and not clicked.is_set():
                        row = lines.index("second") + 1
                        os.write(screen, b"\x1b[<0;2;%dM\x1b[<0;2;%dm" % (row, row))
                        clicked.set()

    thread = Thread(target=be_the_terminal)
    thread.start()
    try:
        with os.fdopen(program, "w") as output, os.fdopen(os.dup(program)) as input_stream:
            await wait_for(
                app(
                    clickable(),
                    output_stream=output,
                    input_stream=input_stream,
                    dimensions=(16, 6),
                    viewport=Inline(mouse=True),
                ),
                TIMEOUT,
            )
    finally:
        thread.join()
        os.close(screen)

    assert clicked.is_set()
