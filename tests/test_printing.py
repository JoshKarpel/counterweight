"""`Print`: rendering content once, and writing it above an inline region or to a stream of its own."""

from __future__ import annotations

import fcntl
import io
import json
import os
import pty
import struct
import termios
from collections.abc import Sequence
from pathlib import Path

import pytest

from counterweight import FullScreen
from counterweight import Inline
from counterweight import app
from counterweight._output import BLANK
from counterweight._output import RESET_STYLE
from counterweight._output import Frame
from counterweight._output import plain_rows
from counterweight._output import printed_rows
from counterweight._output import sgr_from_cell_style
from counterweight._paint import Cell
from counterweight._paint import Paint
from counterweight.asciicast import Recording
from counterweight.autopilot import AutopilotStep
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import Print
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.controls import Suspend
from counterweight.controls import ToggleBorderHealing
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.emulator import Emulator
from counterweight.events import InputEvent
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.geometry import Rects
from counterweight.hooks import use_effect
from counterweight.hooks import use_rects
from counterweight.hooks import use_state
from counterweight.styles import CellStyle
from counterweight.styles._styles import Color
from counterweight.styles._styles import as_solid
from counterweight.styles._styles import resolve_cell_style
from counterweight.styles.utilities import border
from counterweight.styles.utilities import border_collapse
from counterweight.styles.utilities import border_light
from counterweight.styles.utilities import col
from counterweight.styles.utilities import row
from counterweight.styles.utilities import text_wrap_stable
from tests.terminal import Terminal

RED = as_solid(resolve_cell_style(CellStyle(foreground=Color.from_name("red"))))


def test_printed_rows_end_at_their_last_cell_that_isnt_blank() -> None:
    paint = Paint(4, 2, [Cell("a", RED), BLANK, Cell(" ", RED), BLANK, BLANK, BLANK, BLANK, BLANK])

    assert printed_rows(paint, "\r\n") == (
        f"{RESET_STYLE}{sgr_from_cell_style(RED)}a\x1b[38;2;255;255;255m \x1b[38;2;255;0;0m {RESET_STYLE}\r\n\r\n"
    )


def test_a_printed_link_is_closed_at_the_end_of_its_row() -> None:
    linked = as_solid(resolve_cell_style(CellStyle(link="https://example.com")))

    assert printed_rows(Paint(1, 1, [Cell("a", linked)]), "\n").endswith(f"a{RESET_STYLE}\x1b]8;;\x1b\\\n")


def test_plain_rows_are_the_graphemes_up_to_the_last_cell_that_isnt_blank() -> None:
    paint = Paint(3, 2, [Cell("a", RED), Cell("b", RED), BLANK, BLANK, BLANK, BLANK])

    assert plain_rows(paint) == "ab\n\n"


@component
def logger_app(lines: Sequence[str], stream: str = "stdout") -> Div:
    """Prints each of `lines` in turn, one for each key pressed, above a status of how many it has printed."""
    printed, set_printed = use_state(0)

    def on_input(event: InputEvent, _: Receiver) -> Print:
        set_printed(printed + 1)
        return Print(
            Text(content=lines[printed], style=text_wrap_stable), stream="stderr" if stream == "stderr" else "stdout"
        )

    return Div(style=col, on_input=on_input, children=(Text(content=f"status {printed}"),))


def held(frame: Frame) -> list[str]:
    return [line.rstrip() for line in frame.text(ansi=False).split("\n")]


async def terminal_frames(
    root: Component, steps: Sequence[AutopilotStep], dimensions: tuple[int, int] = (16, 4), **kwargs: object
) -> list[list[str]]:
    """What the terminal of an inline app run headless holds after each `Screenshot` among `steps`."""
    frames: list[Frame] = []
    await app(
        root,
        headless=True,
        dimensions=dimensions,
        viewport=Inline(),
        autopilot=[
            *(Screenshot(handler=frames.append, include_scrollback=True) if step is SHOT else step for step in steps),
            Quit(),
        ],
        **kwargs,  # type: ignore[arg-type]
    )
    return [held(frame) for frame in frames]


SHOT = Screenshot(handler=lambda frame: None)
KEY = KeyPressed(key="x")


async def test_a_print_goes_above_the_region() -> None:
    frames = await terminal_frames(logger_app(("one", "two")), [KEY, SHOT, KEY, SHOT])

    assert frames == [["one", "status 1", "", ""], ["one", "two", "status 2", ""]]


async def test_prints_scroll_the_terminal_once_the_region_reaches_its_bottom() -> None:
    frames = await terminal_frames(logger_app(("a", "b", "c", "d", "e")), [KEY] * 5 + [SHOT], dimensions=(16, 3))

    assert frames == [["a", "b", "c", "d", "e", "status 5"]]


async def test_a_print_taller_than_the_terminal_reaches_the_scrollback_whole() -> None:
    @component
    def tall() -> Text:
        return Text(
            content="region",
            on_input=lambda event, _: Print(Div(style=col, children=tuple(Text(content=f"{n}") for n in range(5)))),
        )

    assert await terminal_frames(tall(), [KEY, SHOT], dimensions=(8, 3)) == [["0", "1", "2", "3", "4", "region"]]


async def test_a_print_and_the_state_its_handler_set_land_in_one_frame(tmp_path: Path) -> None:
    path = tmp_path / "printed.cast"

    await app(
        logger_app(("one",)),
        headless=True,
        dimensions=(16, 4),
        viewport=Inline(),
        autopilot=[KEY, Quit()],
        recording=Recording(path),
    )

    _, *events = (json.loads(line) for line in path.read_text().splitlines())
    frames = [data for _, code, data in events if code == "o"]
    assert [index for index, frame in enumerate(frames) if "one" in frame] == [
        index for index, frame in enumerate(frames) if "status 1" in frame
    ]


async def test_prints_in_one_cycle_keep_their_order_across_both_streams() -> None:
    @component
    def both() -> Text:
        return Text(
            content="region",
            on_input=lambda event, _: (
                Print(Text(content="out 1")),
                Print(Text(content="err 1"), stream="stderr"),
                Print(Text(content="out 2")),
            ),
        )

    terminal = io.StringIO()
    frames = await terminal_frames(both(), [KEY, SHOT], output_stream=terminal, stdout=terminal, stderr=terminal)

    assert frames == [["out 1", "err 1", "out 2", "region"]]


async def test_a_printed_components_effects_never_start_and_it_measures_nothing() -> None:
    started: list[str] = []
    measured: list[Rects] = []

    @component
    def printed() -> Text:
        async def start() -> None:
            started.append("printed")  # pragma: never runs

        use_effect(start, deps=())
        measured.append(use_rects())
        return Text(content="printed")

    @component
    def root() -> Text:
        return Text(content="region", on_input=lambda event, _: Print(printed()))

    frames = await terminal_frames(root(), [KEY, SHOT])

    assert frames == [["printed", "region", "", ""]]
    assert started == []
    assert [rects.border.width for rects in measured] == [0]


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
async def test_a_print_to_a_stream_that_isnt_a_terminal_is_plain_text_as_wide_as_it_is(stream: str) -> None:
    streams = {"stdout": io.StringIO(), "stderr": io.StringIO()}
    long = "a line longer than the terminal is wide"

    frames = await terminal_frames(
        logger_app((long,), stream), [KEY, SHOT], dimensions=(16, 3), stdout=streams["stdout"], stderr=streams["stderr"]
    )

    assert {name: written.getvalue() for name, written in streams.items()} == {
        "stdout": "",
        "stderr": "",
        stream: f"{long}\n",
    }
    assert frames == [["status 1", "", ""]]


def set_size(fd: int, columns: int, rows: int) -> None:
    """Sets the size of the pseudo-terminal `fd` is a side of, as a terminal emulator does when its window resizes."""
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))


async def test_a_print_to_another_terminal_is_styled_at_its_width(terminal: Terminal) -> None:
    reader, program = pty.openpty()
    set_size(program, 6, 5)
    try:
        with os.fdopen(program, "w") as other:
            await app(
                logger_app(("wraps at six",)),
                output_stream=io.StringIO(),
                input_stream=terminal.stream,
                dimensions=(16, 4),
                viewport=Inline(),
                stdout=other,
                autopilot=[KEY, Quit()],
            )
            written = os.read(reader, 2**12)
    finally:
        os.close(reader)

    with Emulator(6, 5, on_reply=lambda reply: None) as emulator:
        emulator.feed(written)
        lines = ["".join(cell.grapheme for cell in line).rstrip() for line in emulator.snapshot().lines]
    assert lines[:2] == ["wraps", "at six"]
    assert b"\x1b[" in written


async def test_a_print_to_the_same_terminal_as_the_app_goes_above_the_region(terminal: Terminal) -> None:
    screen, program = pty.openpty()
    set_size(program, 16, 4)
    os.set_blocking(screen, False)
    try:
        with os.fdopen(program, "w") as output, os.fdopen(os.dup(program), "w") as same:
            await app(
                logger_app(("printed",)),
                output_stream=output,
                input_stream=terminal.stream,
                dimensions=(16, 4),
                viewport=Inline(),
                stdout=same,
                autopilot=[KEY, Quit()],
            )
        written = os.read(screen, 2**16).decode()
    finally:
        os.close(screen)

    assert shown(written, (16, 4)) == ["printed", "status 1", "", ""]


def shown(written: str, dimensions: tuple[int, int]) -> list[str]:
    with Emulator(*dimensions, on_reply=lambda reply: None, scrollback=100) as emulator:
        emulator.feed(written.encode())
        lines = emulator.history() + emulator.snapshot().lines
    return ["".join(cell.grapheme for cell in line).rstrip() for line in lines]


@pytest.mark.parametrize("hand_back", ["exit", "suspend"])
async def test_a_full_screen_app_prints_what_it_held_when_it_hands_the_screen_back(
    terminal: Terminal, hand_back: str
) -> None:
    output = io.StringIO()
    during: list[str] = []
    suspend = [Suspend(handler=lambda streams: during.append(output.getvalue()))] if hand_back == "suspend" else []

    await app(
        logger_app(("one", "two")),
        output_stream=output,
        input_stream=terminal.stream,
        dimensions=(16, 4),
        stdout=output,
        autopilot=[KEY, KEY, *suspend, Quit()],
    )

    handed_back = during[0] if during else output.getvalue()
    main_screen = handed_back[handed_back.rindex("\x1b[?1049l") :]
    assert shown(main_screen, (16, 4))[:2] == ["one", "two"]
    assert output.getvalue().count("one") == 1


async def test_a_headless_full_screen_app_prints_nothing_to_its_terminal() -> None:
    output = io.StringIO()

    await app(
        logger_app(("one",)),
        output_stream=output,
        headless=True,
        dimensions=(16, 4),
        stdout=output,
        viewport=FullScreen(),
        autopilot=[KEY, Quit()],
    )

    assert output.getvalue() == ""


@pytest.mark.parametrize(("toggles", "junction"), [((), "┬"), ((ToggleBorderHealing(),), "┌")], ids=["healed", "not"])
async def test_printed_borders_are_healed_as_the_apps_are(
    toggles: tuple[ToggleBorderHealing, ...], junction: str
) -> None:
    boxes = Div(
        style=row | border_collapse,
        children=tuple(Text(content=letter, style=border | border_light) for letter in "ab"),
    )

    @component
    def root() -> Text:
        return Text(content="region", on_input=lambda event, _: Print(boxes))

    frames = await terminal_frames(root(), [*toggles, KEY, SHOT], dimensions=(8, 5))

    assert frames[0][0][2] == junction
