from __future__ import annotations

import logging
import os
import termios
from asyncio import Queue, get_running_loop, wait_for
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TextIO

import pytest

from counterweight.events import AnyEvent, KeyPressed, MouseMoved
from counterweight.geometry import Position
from counterweight.input import (
    read_keys,
    start_input_control,
    start_reading_keys,
    stop_input_control,
    stop_reading_keys,
)
from counterweight.keys import Key
from tests.terminal import Terminal

TIMEOUT = 5


def test_input_control_turns_off_echo_and_line_buffering_and_reads_each_byte_at_once(terminal: Terminal) -> None:
    before = terminal.settings()

    original = start_input_control(terminal.stream)
    during = terminal.settings()

    lflag = during[3]
    cc = during[6]
    assert isinstance(lflag, int)
    assert isinstance(cc, list)
    assert original == before
    assert not lflag & (termios.ECHO | termios.ICANON)
    assert lflag & termios.ISIG
    assert cc[termios.VMIN] == 1
    assert cc[termios.VTIME] == 0


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
class KeyReader:
    events: Queue[AnyEvent]
    records: Queue[logging.LogRecord]


@pytest.fixture
async def key_reader(terminal: Terminal) -> AsyncIterator[KeyReader]:
    """`read_keys` reading `terminal`, under input control, on the running event loop."""
    logger = logging.getLogger("counterweight.input")
    records: Queue[logging.LogRecord] = Queue()
    handler = QueueHandler(records)
    previous_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    start_input_control(terminal.stream)
    reader = KeyReader(events=Queue(), records=records)
    start_reading_keys(terminal.stream, reader.events.put_nowait)

    yield reader

    stop_reading_keys(terminal.stream)
    logger.removeHandler(handler)
    logger.setLevel(previous_level)


async def next_in[T](queue: Queue[T]) -> T:
    return await wait_for(queue.get(), TIMEOUT)


def is_read(stream: TextIO) -> bool:
    """Whether the event loop is reading `stream`, which this stops if it is."""
    return get_running_loop().remove_reader(stream.fileno())


async def test_read_keys_puts_each_parsed_input(terminal: Terminal, key_reader: KeyReader) -> None:
    os.write(terminal.keyboard, b"a\x1b[A")

    assert [await next_in(key_reader.events), await next_in(key_reader.events)] == [
        KeyPressed(key="a"),
        KeyPressed(key=Key.Up),
    ]


async def test_read_keys_logs_what_it_parsed(terminal: Terminal, key_reader: KeyReader) -> None:
    os.write(terminal.keyboard, b"z")

    record = await next_in(key_reader.records)

    assert (record.levelno, record.getMessage()) == (logging.DEBUG, "Parsed user input")
    assert (record.inputs, record.bytes) == ([KeyPressed(key="z")], b"z")  # type: ignore[attr-defined]


async def test_read_keys_logs_input_it_cannot_parse_and_keeps_reading(
    terminal: Terminal, key_reader: KeyReader
) -> None:
    os.write(terminal.keyboard, b"\xff")

    record = await next_in(key_reader.records)
    os.write(terminal.keyboard, b"b")

    assert (record.levelno, record.getMessage()) == (logging.ERROR, "Failed to parse input")
    assert record.bytes == b"\xff"  # type: ignore[attr-defined]
    assert "ParseError" in record.error  # type: ignore[attr-defined]
    assert await next_in(key_reader.events) == KeyPressed(key="b")


async def test_read_keys_reads_a_burst_of_input_whole(terminal: Terminal, key_reader: KeyReader) -> None:
    os.write(terminal.keyboard, b"\x1b[<35;10;20M" * 3)

    moved = MouseMoved(absolute=Position(x=9, y=19), button=None)
    assert [await next_in(key_reader.events) for _ in range(3)] == [moved, moved, moved]
    assert (await next_in(key_reader.records)).inputs == [moved, moved, moved]  # type: ignore[attr-defined]


async def test_stopping_reading_keys_stops_the_event_loop_reading_the_stream(
    terminal: Terminal, key_reader: KeyReader
) -> None:
    stop_reading_keys(terminal.stream)

    assert not is_read(terminal.stream)


async def test_read_keys_stops_reading_at_the_end_of_its_input() -> None:
    read_end, write_end = os.pipe()
    events: list[AnyEvent] = []
    with os.fdopen(read_end) as stream:
        start_reading_keys(stream, events.append)
        os.write(write_end, b"a")
        os.close(write_end)

        read_keys(stream, events.append)
        read_keys(stream, events.append)

        assert events == [KeyPressed(key="a")]
        assert not is_read(stream)


def test_read_keys_lets_an_error_putting_an_event_propagate() -> None:
    read_end, write_end = os.pipe()
    os.write(write_end, b"a")

    def put_event(event: AnyEvent) -> None:
        raise ValueError("the queue is gone")

    with os.fdopen(read_end) as stream, pytest.raises(ValueError, match="the queue is gone"):
        read_keys(stream, put_event)
    os.close(write_end)
