from __future__ import annotations

import logging
import os
import termios
from asyncio import Queue
from asyncio import get_running_loop
from asyncio import to_thread
from asyncio import wait_for
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta
from typing import TextIO

import pytest

from counterweight._input import ESCAPE_TIMEOUT
from counterweight._input import PASTE_TIMEOUT
from counterweight._input import KeyReader
from counterweight._input import read_keys
from counterweight._input import start_input_control
from counterweight._input import start_reading_keys
from counterweight._input import stop_input_control
from counterweight._input import stop_reading_keys
from counterweight.events import AnyEvent
from counterweight.events import KeyPressed
from counterweight.events import MouseMoved
from counterweight.events import Pasted
from counterweight.geometry import Position
from counterweight.keys import Key
from tests.terminal import Terminal

TIMEOUT = 5


def test_input_control_turns_off_echo_line_buffering_and_signal_keys_and_reads_each_byte_at_once(
    terminal: Terminal,
) -> None:
    before = terminal.settings()

    original = start_input_control(terminal.stream)
    during = terminal.settings()

    iflag = during[0]
    lflag = during[3]
    cc = during[6]
    assert isinstance(iflag, int)
    assert isinstance(lflag, int)
    assert isinstance(cc, list)
    assert original == before
    assert not iflag & (termios.ICRNL | termios.INLCR | termios.IGNCR)
    assert not lflag & (termios.ECHO | termios.ICANON | termios.ISIG)
    assert cc[termios.VMIN] == 1
    assert cc[termios.VTIME] == 0


@pytest.mark.parametrize("translation", [termios.ICRNL, termios.INLCR, termios.IGNCR])
def test_input_control_turns_off_each_line_ending_translation(terminal: Terminal, translation: int) -> None:
    attributes = terminal.settings()
    iflag = attributes[0]
    assert isinstance(iflag, int)
    attributes[0] = iflag | translation
    termios.tcsetattr(terminal.stream, termios.TCSANOW, attributes)

    start_input_control(terminal.stream)

    during = terminal.settings()[0]
    assert isinstance(during, int)
    assert not during & translation


@pytest.mark.parametrize(
    ("field", "flag"),
    [
        pytest.param(3, termios.ISIG, id="signal-keys"),
        pytest.param(3, termios.IEXTEN, id="literal-next-and-discard"),
        pytest.param(0, termios.IXON, id="flow-control"),
    ],
)
def test_input_control_stops_the_terminal_acting_on_keys(terminal: Terminal, field: int, flag: int) -> None:
    attributes = terminal.settings()
    flags = attributes[field]
    assert isinstance(flags, int)
    attributes[field] = flags | flag
    termios.tcsetattr(terminal.stream, termios.TCSANOW, attributes)

    start_input_control(terminal.stream)

    during = terminal.settings()[field]
    assert isinstance(during, int)
    assert not during & flag


def test_stopping_input_control_restores_the_original_attributes(terminal: Terminal) -> None:
    before = terminal.settings()

    stop_input_control(terminal.stream, start_input_control(terminal.stream))

    assert terminal.settings() == before


class QueueHandler(logging.Handler):
    """Hands each log record to a queue, so a test can wait for the reader to log one."""

    def __init__(self, records: Queue[logging.LogRecord]) -> None:
        super().__init__(level=logging.DEBUG)
        self.records = records

    def emit(self, record: logging.LogRecord) -> None:
        self.records.put_nowait(record)


@dataclass(frozen=True, slots=True)
class KeyReading:
    reader: KeyReader
    events: Queue[AnyEvent]
    records: Queue[logging.LogRecord]


@pytest.fixture
async def key_reading(terminal: Terminal) -> AsyncIterator[KeyReading]:
    """`read_keys` reading `terminal`, under input control, on the running event loop."""
    logger = logging.getLogger("counterweight._input")
    records: Queue[logging.LogRecord] = Queue()
    handler = QueueHandler(records)
    previous_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    start_input_control(terminal.stream)
    events: Queue[AnyEvent] = Queue()
    reading = KeyReading(
        reader=start_reading_keys(terminal.stream, events.put_nowait),
        events=events,
        records=records,
    )

    yield reading

    stop_reading_keys(reading.reader)
    logger.removeHandler(handler)
    logger.setLevel(previous_level)


async def next_in[T](queue: Queue[T]) -> T:
    return await wait_for(queue.get(), TIMEOUT)


def type_all(keyboard: int, typed: bytes) -> None:
    """
    Write all of `typed` to `keyboard`, which blocks once the terminal's input queue is full
    (on macOS, at about a kilobyte) until the program side reads it, so run it off the event loop.
    """
    while typed:
        typed = typed[os.write(keyboard, typed) :]


def is_read(stream: TextIO) -> bool:
    """Whether the event loop is reading `stream`, which this stops if it is."""
    return get_running_loop().remove_reader(stream.fileno())


async def test_read_keys_puts_each_parsed_input(terminal: Terminal, key_reading: KeyReading) -> None:
    os.write(terminal.keyboard, b"a\x1b[A")

    assert [await next_in(key_reading.events), await next_in(key_reading.events)] == [
        KeyPressed(key="a"),
        KeyPressed(key=Key.Up),
    ]


async def test_enter_and_ctrl_j_reach_the_app_as_different_keys(terminal: Terminal, key_reading: KeyReading) -> None:
    os.write(terminal.keyboard, b"\r\n")

    assert [await next_in(key_reading.events), await next_in(key_reading.events)] == [
        KeyPressed(key=Key.Enter),
        KeyPressed(key=Key.ControlJ),
    ]


async def test_read_keys_logs_what_it_parsed(terminal: Terminal, key_reading: KeyReading) -> None:
    os.write(terminal.keyboard, b"z")

    record = await next_in(key_reading.records)

    assert (record.levelno, record.getMessage()) == (logging.DEBUG, "Parsed user input")
    assert (record.inputs, record.bytes) == ((KeyPressed(key="z"),), b"z")  # type: ignore[attr-defined]


async def test_read_keys_logs_input_it_skips_and_keeps_reading(terminal: Terminal, key_reading: KeyReading) -> None:
    os.write(terminal.keyboard, b"\xff")

    record = await next_in(key_reading.records)
    os.write(terminal.keyboard, b"b")

    assert (record.inputs, record.skipped) == ((), (b"\xff",))  # type: ignore[attr-defined]
    assert await next_in(key_reading.events) == KeyPressed(key="b")


async def test_read_keys_reads_a_burst_of_input_whole(terminal: Terminal, key_reading: KeyReading) -> None:
    os.write(terminal.keyboard, b"\x1b[<35;10;20M" * 3)

    moved = MouseMoved(absolute=Position(x=9, y=19), button=None)
    assert [await next_in(key_reading.events) for _ in range(3)] == [moved, moved, moved]
    assert (await next_in(key_reading.records)).inputs == (moved, moved, moved)  # type: ignore[attr-defined]


async def test_read_keys_puts_a_paste_longer_than_one_read_as_one_event(
    terminal: Terminal, key_reading: KeyReading
) -> None:
    text = "0123456789" * 250
    await to_thread(type_all, terminal.keyboard, b"\x1b[200~" + text.encode() + b"\x1b[201~q")

    assert [await next_in(key_reading.events), await next_in(key_reading.events)] == [
        Pasted(text=text),
        KeyPressed(key="q"),
    ]


@pytest.mark.parametrize(
    ("typed", "hold"),
    [
        (b"\x1b", ESCAPE_TIMEOUT),
        (b"\x1b[200~ab", PASTE_TIMEOUT),
    ],
)
async def test_held_input_waits_as_long_as_its_kind_needs(
    terminal: Terminal, key_reading: KeyReading, typed: bytes, hold: timedelta
) -> None:
    os.write(terminal.keyboard, typed)
    await next_in(key_reading.records)
    timer = key_reading.reader.hold_timer

    assert timer is not None
    assert timer.when() - get_running_loop().time() == pytest.approx(hold.total_seconds(), abs=0.04)


async def test_a_held_paste_keeps_how_much_of_it_was_searched_for_its_end(
    terminal: Terminal, key_reading: KeyReading
) -> None:
    os.write(terminal.keyboard, b"\x1b[200~abc")
    await next_in(key_reading.records)

    assert key_reading.reader.paste_searched == len(b"\x1b[200~abc")


async def test_stopping_reading_keys_stops_the_event_loop_reading_the_stream(
    terminal: Terminal, key_reading: KeyReading
) -> None:
    stop_reading_keys(key_reading.reader)

    assert not is_read(terminal.stream)


async def test_read_keys_stops_reading_at_the_end_of_its_input() -> None:
    read_end, write_end = os.pipe()
    events: list[AnyEvent] = []
    with os.fdopen(read_end) as stream:
        reader = start_reading_keys(stream, events.append)
        os.write(write_end, b"a")
        os.close(write_end)

        read_keys(reader)
        read_keys(reader)

        assert events == [KeyPressed(key="a")]
        assert not is_read(stream)


def test_read_keys_lets_an_error_putting_an_event_propagate() -> None:
    read_end, write_end = os.pipe()
    os.write(write_end, b"a")

    def put_event(event: AnyEvent) -> None:
        raise ValueError("the queue is gone")

    with os.fdopen(read_end) as stream, pytest.raises(ValueError, match="the queue is gone"):
        read_keys(KeyReader(stream=stream, put_event=put_event))
    os.close(write_end)


async def test_an_escape_at_the_end_of_input_is_the_escape_key_once_input_stops(
    terminal: Terminal, key_reading: KeyReading
) -> None:
    os.write(terminal.keyboard, b"a\x1b")

    assert [await next_in(key_reading.events), await next_in(key_reading.events)] == [
        KeyPressed(key="a"),
        KeyPressed(key=Key.Escape),
    ]


async def test_an_escape_sequence_split_across_reads_is_one_key(terminal: Terminal, key_reading: KeyReading) -> None:
    os.write(terminal.keyboard, b"\x1b")
    held = await next_in(key_reading.records)
    os.write(terminal.keyboard, b"[A")

    assert held.held == 1  # type: ignore[attr-defined]
    assert await next_in(key_reading.events) == KeyPressed(key=Key.Up)


async def test_alt_with_a_key_reaches_the_app_as_one_key(terminal: Terminal, key_reading: KeyReading) -> None:
    os.write(terminal.keyboard, b"\x1b\rq")

    assert [await next_in(key_reading.events), await next_in(key_reading.events)] == [
        KeyPressed(key=Key.AltEnter),
        KeyPressed(key="q"),
    ]


async def test_an_escape_held_until_the_next_read_is_alt_with_the_key_it_starts_with(
    terminal: Terminal, key_reading: KeyReading
) -> None:
    os.write(terminal.keyboard, b"\x1b")
    held = await next_in(key_reading.records)
    os.write(terminal.keyboard, b"b")

    assert held.held == 1  # type: ignore[attr-defined]
    assert await next_in(key_reading.events) == KeyPressed(key="alt+b")


async def test_an_escape_that_times_out_before_the_next_read_is_the_escape_key(
    terminal: Terminal, key_reading: KeyReading
) -> None:
    os.write(terminal.keyboard, b"\x1b")
    escape = await next_in(key_reading.events)
    os.write(terminal.keyboard, b"b")

    assert [escape, await next_in(key_reading.events)] == [KeyPressed(key=Key.Escape), KeyPressed(key="b")]


async def test_stopping_reading_keys_puts_a_held_escape(terminal: Terminal, key_reading: KeyReading) -> None:
    os.write(terminal.keyboard, b"\x1b")
    await next_in(key_reading.records)

    stop_reading_keys(key_reading.reader)

    assert key_reading.events.get_nowait() == KeyPressed(key=Key.Escape)


async def test_stopping_reading_keys_cancels_the_hold_timeout(terminal: Terminal, key_reading: KeyReading) -> None:
    os.write(terminal.keyboard, b"\x1b")
    await next_in(key_reading.records)
    timer = key_reading.reader.hold_timer

    stop_reading_keys(key_reading.reader)

    assert timer is not None
    assert timer.cancelled()
