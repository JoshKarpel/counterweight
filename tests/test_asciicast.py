from __future__ import annotations

import io
import json
from collections.abc import Iterable
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from itertools import accumulate
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from counterweight import app
from counterweight._input_parsing import parse_input
from counterweight._output import BRACKETED_PASTE_OFF
from counterweight._output import BRACKETED_PASTE_ON
from counterweight._output import OUTPUT_CONTROL_START
from counterweight._output import SET_ANY_EVENT_MOUSE_SGR_FORMAT
from counterweight._output import UNSET_ANY_EVENT_MOUSE_SGR_FORMAT
from counterweight._output import Frame
from counterweight._output import clipboard_instructions
from counterweight._output import stop_output_control
from counterweight._viewports import FullScreen
from counterweight.asciicast import SUSPENDED
from counterweight.asciicast import Recorder
from counterweight.asciicast import Recording
from counterweight.asciicast import Theme
from counterweight.asciicast import event_line
from counterweight.asciicast import header_line
from counterweight.asciicast import input_bytes
from counterweight.asciicast import milliseconds
from counterweight.autopilot import AutopilotStep
from counterweight.autopilot import Wait
from counterweight.autopilot import advance
from counterweight.clock import FrozenClock
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import AdvanceClock
from counterweight.controls import Bell
from counterweight.controls import CopyToClipboard
from counterweight.controls import Marker
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.controls import SetTitle
from counterweight.controls import Suspend
from counterweight.elements import Text
from counterweight.emulator import Emulator
from counterweight.events import InputEvent
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseMoved
from counterweight.events import MouseScrolledUp
from counterweight.events import MouseUp
from counterweight.events import Pasted
from counterweight.events import Receiver
from counterweight.events import TerminalResized
from counterweight.geometry import Position
from counterweight.hooks import use_clock
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles._styles import Color
from counterweight.styles.utilities import text_black
from tests.terminal import Terminal

STARTED = datetime(2026, 3, 14, 15, 9, 26, tzinfo=UTC)

THEME = Theme(
    foreground=Color(200, 201, 202),
    background=Color(10, 11, 12),
    palette=tuple(Color(index, index + 1, index + 2) for index in range(0, 160, 20)),
)


def test_a_header_holds_the_version_the_size_the_terminal_type_and_when_the_recording_started(tmp_path: Path) -> None:
    header = json.loads(header_line(Recording(tmp_path / "x.cast"), cols=12, rows=7, started=STARTED))

    assert header == {
        "version": 3,
        "term": {"cols": 12, "rows": 7, "type": "xterm-256color"},
        "timestamp": int(STARTED.timestamp()),
    }


def test_a_header_holds_the_title_idle_time_limit_and_theme_it_is_given(tmp_path: Path) -> None:
    recording = Recording(
        tmp_path / "x.cast", title="démo", idle_time_limit=timedelta(seconds=1, milliseconds=500), theme=THEME
    )

    header = json.loads(header_line(recording, cols=12, rows=7, started=STARTED))

    assert header["title"] == "démo"
    assert header["idle_time_limit"] == 1.5
    assert header["term"]["theme"] == {
        "fg": "#c8c9ca",
        "bg": "#0a0b0c",
        "palette": "#000102:#141516:#28292a:#3c3d3e:#505152:#646566:#78797a:#8c8d8e",
    }


@pytest.mark.parametrize("count", [8, 16])
def test_a_theme_takes_a_palette_of_8_or_16_colors(count: int) -> None:
    assert len(Theme(foreground=Color(1, 2, 3), background=Color(4, 5, 6), palette=(Color(7, 8, 9),) * count).palette)


@pytest.mark.parametrize("count", [7, 9, 15, 17])
def test_a_theme_rejects_a_palette_of_any_other_size(count: int) -> None:
    with pytest.raises(ValueError, match=str(count)):
        Theme(foreground=Color(1, 2, 3), background=Color(4, 5, 6), palette=(Color(7, 8, 9),) * count)


def test_an_event_line_is_its_interval_in_seconds_its_code_and_its_data() -> None:
    assert json.loads(event_line(1234, "o", "\x1b[1mhé")) == [1.234, "o", "\x1b[1mhé"]


def test_an_event_line_escapes_control_characters() -> None:
    assert "\\u001b" in event_line(0, "o", "\x1b")


@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [
        (timedelta(), 0),
        (timedelta(microseconds=499), 0),
        (timedelta(microseconds=501), 1),
        (timedelta(seconds=2, microseconds=345_600), 2346),
    ],
)
def test_milliseconds_rounds_to_the_nearest_millisecond(elapsed: timedelta, expected: int) -> None:
    assert milliseconds(elapsed) == expected


@given(st.lists(st.integers(min_value=0, max_value=10**8), max_size=50))
def test_rounded_intervals_add_up_to_the_rounded_total_however_many_there_are(gaps: list[int]) -> None:
    times = iter([timedelta(microseconds=total) for total in accumulate(gaps)])
    stream = io.StringIO()
    recorder = Recorder(stream=stream, elapsed=lambda: next(times), is_recording_input=False, size=(1, 1))

    for _ in gaps:
        recorder.output("")

    intervals = [json.loads(line)[0] for line in stream.getvalue().splitlines()]
    assert round(sum(intervals) * 1000) == milliseconds(timedelta(microseconds=sum(gaps)))


@pytest.mark.parametrize(
    "event",
    [
        KeyPressed(key="a"),
        KeyPressed(key="é"),
        KeyPressed(key=Key.Up),
        KeyPressed(key=Key.ControlC),
        KeyPressed(key="alt+b"),
        Pasted(text="pasted text"),
        MouseMoved(absolute=Position(3, 4), button=None),
        MouseDown(absolute=Position(5, 6), button=1),
        MouseUp(absolute=Position(5, 6), button=1),
        MouseScrolledUp(absolute=Position(7, 8)),
    ],
    ids=repr,
)
def test_input_is_recorded_as_the_bytes_that_parse_back_to_it(event: InputEvent) -> None:
    assert parse_input(input_bytes(event), is_final=True).events == (event,)


type Event = list[object]


def read(path: Path) -> tuple[dict[str, object], list[Event]]:
    """The header and events of the recording at `path`."""
    header, *events = (json.loads(line) for line in path.read_text().splitlines())
    return header, events


def times(events: Iterable[Event]) -> list[tuple[int, str, str]]:
    """Each event's time from the start of its recording, in milliseconds, with its code and data."""
    total = 0
    timed = []
    for interval, code, data in events:
        total += round(float(str(interval)) * 1000)
        timed.append((total, str(code), str(data)))
    return timed


@component
def typing() -> Text:
    content, set_content = use_state("typed:")

    def on_input(event: InputEvent, _: Receiver) -> None:
        if isinstance(event, KeyPressed):
            set_content(lambda c: c + event.key)

    return Text(content=content, style=text_black, on_input=on_input)


async def record(
    path: Path,
    autopilot: list[AutopilotStep],
    root: Component | None = None,
    dimensions: tuple[int, int] = (10, 2),
    is_recording_input: bool = False,
) -> list[tuple[int, str, str]]:
    """Each event a headless app with a frozen clock records, timed from the start of its recording."""
    await app(
        root or typing(),
        headless=True,
        dimensions=dimensions,
        clock=FrozenClock(STARTED),
        autopilot=[*autopilot, Quit()],
        recording=Recording(path, input=is_recording_input),
    )
    return times(read(path)[1])


async def test_a_recording_starts_with_a_header_of_the_apps_size_and_starting_time(tmp_path: Path) -> None:
    path = tmp_path / "x.cast"

    await record(path, [], dimensions=(9, 3))

    assert read(path)[0] == {
        "version": 3,
        "term": {"cols": 9, "rows": 3, "type": "xterm-256color"},
        "timestamp": int(STARTED.timestamp()),
    }


async def test_a_recording_creates_the_directories_it_is_written_in(tmp_path: Path) -> None:
    path = tmp_path / "a" / "b" / "x.cast"

    await record(path, [])

    assert path.exists()


async def test_a_recording_takes_the_terminal_over_draws_the_first_frame_and_exits_with_0(tmp_path: Path) -> None:
    events = await record(tmp_path / "x.cast", [])

    assert [(time, code) for time, code, _ in events] == [(0, "o"), (0, "o"), (0, "x")]
    assert events[0][2] == OUTPUT_CONTROL_START
    assert events[-1][2] == "0"


async def test_a_frozen_clock_recording_is_timed_by_its_advances(tmp_path: Path) -> None:
    events = await record(
        tmp_path / "x.cast",
        [
            AdvanceClock(by=timedelta(milliseconds=300)),
            KeyPressed(key="a"),
            AdvanceClock(by=timedelta(seconds=2, milliseconds=5)),
            KeyPressed(key="b"),
        ],
    )

    assert [time for time, code, _ in events if code == "o"][-2:] == [300, 2305]


async def test_a_wait_moves_a_frozen_clock_recording_on_by_exactly_its_duration(tmp_path: Path) -> None:
    events = await record(tmp_path / "x.cast", [Wait(timedelta(milliseconds=20)), KeyPressed(key="a")])

    assert [time for time, code, _ in events if code == "o"][-1] == 20


async def test_a_frame_records_only_what_changed(tmp_path: Path) -> None:
    events = await record(tmp_path / "x.cast", [KeyPressed(key="a")])

    last_frame = [data for _, code, data in events if code == "o"][-1]
    assert "typed" not in last_frame
    assert "a" in last_frame


@component
def ticks_without_changing() -> Text:
    use_clock(timedelta(milliseconds=10))
    return Text(content="still")


async def test_a_render_that_changes_no_cell_records_no_frame(tmp_path: Path) -> None:
    events = await record(tmp_path / "x.cast", [*advance(timedelta(milliseconds=30))], root=ticks_without_changing())

    assert [(time, code) for time, code, _ in events] == [(0, "o"), (0, "o"), (30, "x")]


async def test_playing_a_recordings_output_back_shows_the_last_frame(tmp_path: Path) -> None:
    frames: list[Frame] = []
    path = tmp_path / "x.cast"

    await record(
        path,
        [KeyPressed(key="a"), TerminalResized(dimensions=(12, 3)), KeyPressed(key="b"), Screenshot(frames.append)],
    )

    with Emulator(10, 2, on_reply=lambda reply: None) as emulator:
        for _, code, data in read(path)[1]:
            match code:
                case "o":
                    emulator.feed(str(data).encode())
                case "r":
                    emulator.resize(*(int(n) for n in str(data).split("x")))
                case _:
                    pass
        played = ["".join(cell.grapheme for cell in line) for line in emulator.snapshot().lines]

    assert played == frames[-1].text(ansi=False).split("\n")


async def test_a_recording_leaves_input_out_unless_asked_for_it(tmp_path: Path) -> None:
    events = await record(tmp_path / "x.cast", [KeyPressed(key="a"), Pasted(text="b")])

    assert "i" not in {code for _, code, _ in events}


async def test_a_recording_asked_for_input_records_the_input_the_app_handles(tmp_path: Path) -> None:
    events = await record(
        tmp_path / "x.cast",
        [KeyPressed(key="a"), Pasted(text="b"), MouseDown(absolute=Position(1, 0), button=1)],
        is_recording_input=True,
    )

    assert [data for _, code, data in events if code == "i"] == ["a", "\x1b[200~b\x1b[201~", "\x1b[<0;2;1M"]


async def test_a_resize_to_a_new_size_records_it(tmp_path: Path) -> None:
    events = await record(
        tmp_path / "x.cast", [TerminalResized(dimensions=(10, 2)), TerminalResized(dimensions=(12, 3))]
    )

    assert [data for _, code, data in events if code == "r"] == ["12x3"]


async def test_a_marker_records_its_label(tmp_path: Path) -> None:
    events = await record(tmp_path / "x.cast", [AdvanceClock(by=timedelta(seconds=1)), Marker("chapter one")])

    assert [(time, data) for time, code, data in events if code == "m"] == [(1000, "chapter one")]


async def test_a_marker_without_a_recording_does_nothing() -> None:
    frames: list[Frame] = []

    await app(typing(), headless=True, dimensions=(10, 1), autopilot=[Marker("x"), Screenshot(frames.append), Quit()])

    assert frames[0].text(ansi=False) == "typed:    "


async def test_a_recording_records_the_bell_and_titles_even_headless(tmp_path: Path) -> None:
    events = await record(tmp_path / "x.cast", [Bell(), SetTitle(title="hi")])

    outputs = [data for _, code, data in events if code == "o"]
    assert "\a" in outputs
    assert "\x1b]2;hi\x1b\\" in outputs


class Boom(Exception):
    pass


@component
def explodes() -> Text:
    def on_input(event: InputEvent, _: Receiver) -> None:
        raise Boom

    return Text(content="", on_input=on_input)


async def test_an_app_that_stops_with_an_error_records_an_exit_of_1(tmp_path: Path) -> None:
    path = tmp_path / "x.cast"

    with pytest.raises(Boom):
        await app(
            explodes(), headless=True, dimensions=(3, 1), autopilot=[KeyPressed(key="x")], recording=Recording(path)
        )

    assert read(path)[1][-1][1:] == ["x", "1"]


def test_a_suspension_is_cut_out_of_the_recording_and_marked() -> None:
    stream = io.StringIO()
    now = [timedelta()]
    recorder = Recorder(stream=stream, elapsed=lambda: now[0], is_recording_input=False, size=(1, 1))

    now[0] = timedelta(seconds=1)
    recorder.suspend()
    now[0] += timedelta(seconds=10)
    recorder.resume()
    now[0] += timedelta(seconds=2)
    recorder.output("a")

    events = times(json.loads(line) for line in stream.getvalue().splitlines())
    assert [(time, code, data) for time, code, data in events] == [(1000, "m", SUSPENDED), (3000, "o", "a")]


async def test_an_app_marks_where_it_was_suspended_in_its_recording(tmp_path: Path) -> None:
    path = tmp_path / "x.cast"

    await record(path, [AdvanceClock(by=timedelta(seconds=1)), Suspend(handler=lambda streams: None)])

    assert [(time, data) for time, code, data in times(read(path)[1]) if code == "m"] == [(1000, SUSPENDED)]


async def test_a_headful_recording_holds_what_the_app_draws_on_its_terminal(tmp_path: Path, terminal: Terminal) -> None:
    output = io.StringIO()
    path = tmp_path / "x.cast"

    await app(
        typing(),
        output_stream=output,
        input_stream=terminal.stream,
        dimensions=(10, 2),
        autopilot=[KeyPressed(key="a"), Bell(), SetTitle(title="hi"), Quit()],
        recording=Recording(path),
    )

    hand_back = io.StringIO()
    stop_output_control(hand_back, viewport=FullScreen())
    drawn = (
        output.getvalue()
        .replace(SET_ANY_EVENT_MOUSE_SGR_FORMAT + BRACKETED_PASTE_ON, "")
        .removesuffix(BRACKETED_PASTE_OFF + UNSET_ANY_EVENT_MOUSE_SGR_FORMAT + hand_back.getvalue())
    )
    assert "".join(str(data) for _, code, data in read(path)[1] if code == "o") == drawn


async def test_a_recording_leaves_out_a_copy_the_app_writes_to_its_terminal(tmp_path: Path, terminal: Terminal) -> None:
    output = io.StringIO()
    path = tmp_path / "x.cast"

    await app(
        typing(),
        output_stream=output,
        input_stream=terminal.stream,
        dimensions=(10, 2),
        autopilot=[CopyToClipboard(text="hi"), Quit()],
        recording=Recording(path),
    )

    copy = clipboard_instructions("hi")
    assert copy in output.getvalue()
    assert not any(copy in str(data) for _, code, data in read(path)[1] if code == "o")
