"""
Recording an app as an [asciicast v3](https://docs.asciinema.org/manual/asciicast/v3/) file,
which [asciinema-player](https://docs.asciinema.org/manual/player/) plays back.

The pure half encodes the file's lines: its header, and one line per event.
`Recorder` is the place the render loop records into: it timestamps each event, cuts suspensions out of the timing,
and writes the lines to the recording's file.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Literal
from typing import TextIO

from counterweight.emulator import Modes
from counterweight.events import InputEvent
from counterweight.events import KeyPressed
from counterweight.events import Pasted
from counterweight.input_encoding import encode_key
from counterweight.input_encoding import encode_mouse
from counterweight.input_encoding import encode_paste
from counterweight.styles.styles import Color

VERSION = 3

TERM_TYPE = "xterm-256color"

SUSPENDED = "suspended"
"""The label of the marker recorded where a suspension is cut out of a recording."""

APP_INPUT_MODES = Modes(bracketed_paste=True, mouse_tracking="any", sgr_mouse=True)
"""The modes the app sets on its terminal, so its input is recorded as the bytes that terminal sends it."""

type EventCode = Literal["o", "i", "r", "m", "x"]


@dataclass(frozen=True, slots=True)
class Theme:
    """
    The colors a player draws a recording in, where the app leaves the color to the terminal
    ([`TERMINAL_DEFAULT`][counterweight.styles.TERMINAL_DEFAULT] and [`IndexedColor`][counterweight.styles.IndexedColor]),
    as the header's `term.theme`.
    Without one, a player draws those colors in its own theme.

    Raises:
        ValueError: If `palette` holds other than 8 or 16 colors.
    """

    foreground: Color
    background: Color
    palette: tuple[Color, ...]
    """The first 8 or 16 indexed colors, from black to bright white."""

    def __post_init__(self) -> None:
        if len(self.palette) not in (8, 16):
            raise ValueError(f"A theme's palette has 8 or 16 colors, not {len(self.palette)}")


@dataclass(frozen=True, slots=True)
class Recording:
    """
    Record the app, as `app`'s `recording`, to an [asciicast v3](https://docs.asciinema.org/manual/asciicast/v3/) file
    at `path`, whether it's headless or not, which
    [asciinema-player](https://docs.asciinema.org/manual/player/) and `asciinema play` play back.

    The recording holds what the app draws, as it draws it on a terminal,
    with each frame's time as the app's clock reads it:
    with [`system_clock`][counterweight.clock.system_clock] that's real time,
    and with a [`frozen_clock`][counterweight.clock.frozen_clock] only
    [`AdvanceClock`][counterweight.controls.AdvanceClock] moves it,
    so an autopilot can record a minute of an app in milliseconds, the same on every run.
    [`Marker`][counterweight.controls.Marker] marks a point in it that players can jump to.

    While the app is suspended, the recording can't see what the program it hands the terminal to draws,
    so the time it spends suspended is cut out, and a `suspended` marker shows where.

    !!! warning "Recording input records everything typed"

        With `input`, the recording holds every key press, paste and mouse event the app handles,
        including passwords and tokens typed into it,
        in a file that's made to be shared.
        That's why it's off by default, and stays off under an autopilot, whose input is safe to share:
        turn it on yourself when you know what will be typed.
    """

    path: Path
    """Where to write the recording, creating its parent directories. It's overwritten if it exists."""
    title: str | None = None
    """The recording's title, which players show."""
    idle_time_limit: timedelta | None = None
    """The longest a player waits between events, cutting longer pauses short."""
    theme: Theme | None = None
    """The colors to play the recording in, where the app leaves the color to the terminal."""
    input: bool = False
    """Whether to record the input the app handles, which players can show as it's typed."""


def header_line(recording: Recording, cols: int, rows: int, started: datetime) -> str:
    """The header of a recording of a `cols` by `rows` terminal, made from `started`."""
    term: dict[str, object] = {"cols": cols, "rows": rows, "type": TERM_TYPE}
    if recording.theme is not None:
        term["theme"] = {
            "fg": recording.theme.foreground.hex,
            "bg": recording.theme.background.hex,
            "palette": ":".join(color.hex for color in recording.theme.palette),
        }
    header: dict[str, object] = {"version": VERSION, "term": term, "timestamp": int(started.timestamp())}
    if recording.idle_time_limit is not None:
        header["idle_time_limit"] = recording.idle_time_limit.total_seconds()
    if recording.title is not None:
        header["title"] = recording.title
    return json.dumps(header, ensure_ascii=False)


def event_line(interval_ms: int, code: EventCode, data: str) -> str:
    """One event, `interval_ms` milliseconds after the one before it."""
    return json.dumps([interval_ms / 1000, code, data], ensure_ascii=False)


def milliseconds(elapsed: timedelta) -> int:
    """
    `elapsed`, rounded to whole milliseconds, as the official recorder rounds.
    Intervals are differences between these, so rounding can't drift over a long recording.
    """
    return round(elapsed / timedelta(milliseconds=1))


def input_bytes(event: InputEvent) -> bytes:
    """The bytes the app's terminal sends it for `event`."""
    match event:
        case KeyPressed(key=key):
            return encode_key(key, APP_INPUT_MODES)
        case Pasted(text=text):
            return encode_paste(text, APP_INPUT_MODES)
        case _:
            # The app tracks every mouse event, so each one is reported.
            return encode_mouse(event, event.absolute, APP_INPUT_MODES) or b""


@dataclass(slots=True)
class Recorder:
    """
    A recording in progress: the file it's written to, and where the last event was on its timeline.
    `elapsed` reads the app's clock, from when it started.
    """

    stream: TextIO
    elapsed: Callable[[], timedelta]
    is_recording_input: bool
    size: tuple[int, int]
    last_ms: int = 0
    cut: timedelta = timedelta()
    """How much time suspensions have taken, which is cut out of every later event's time."""
    suspended_at: timedelta = timedelta()

    @classmethod
    def start(
        cls,
        recording: Recording,
        elapsed: Callable[[], timedelta],
        cols: int,
        rows: int,
        started: datetime,
        preamble: str,
    ) -> Recorder:
        """Open the recording's file and write its header, and `preamble` as its first output."""
        recording.path.parent.mkdir(parents=True, exist_ok=True)
        stream = recording.path.open("w", encoding="utf-8")
        recorder = cls(stream=stream, elapsed=elapsed, is_recording_input=recording.input, size=(cols, rows))
        stream.write(header_line(recording, cols, rows, started) + "\n")
        recorder.output(preamble)
        return recorder

    def event(self, code: EventCode, data: str) -> None:
        """Write an event at the app's time now, less the time suspensions took."""
        now = milliseconds(self.elapsed() - self.cut)
        self.stream.write(event_line(now - self.last_ms, code, data) + "\n")
        self.last_ms = now

    def output(self, instructions: str) -> None:
        """Record what the app writes to its terminal."""
        self.event("o", instructions)

    def input(self, event: InputEvent) -> None:
        """Record the input the app handles, if the recording records input."""
        if self.is_recording_input:
            self.event("i", input_bytes(event).decode())

    def resize(self, cols: int, rows: int) -> None:
        """Record the terminal's size, if it's changed."""
        if (cols, rows) == self.size:
            return
        self.size = (cols, rows)
        self.event("r", f"{cols}x{rows}")

    def marker(self, label: str) -> None:
        """Record a marker, which players show as a point to jump to."""
        self.event("m", label)

    def suspend(self) -> None:
        """Stop the recording's time while the app is suspended."""
        self.suspended_at = self.elapsed()

    def resume(self) -> None:
        """Cut the time since `suspend` out of the recording, and mark where."""
        self.cut += self.elapsed() - self.suspended_at
        self.marker(SUSPENDED)

    def stop(self, status: int) -> None:
        """Record the app's exit `status`, and close the file."""
        self.event("x", str(status))
        self.stream.close()


__all__ = [
    "Recording",
    "Theme",
]
