from __future__ import annotations

import logging
import os
import termios
from asyncio import TimerHandle, get_running_loop
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta
from typing import TextIO

from counterweight.events import AnyEvent
from counterweight.input_parsing import parse_input

logger = logging.getLogger(__name__)

# How long a lone ESC (or the start of an escape sequence) at the end of a read waits for the rest of a sequence
# before it is the Escape key.
ESCAPE_TIMEOUT = timedelta(milliseconds=50)


@dataclass(slots=True)
class KeyReader:
    """
    The state of reading a stream between `start_reading_keys` and `stop_reading_keys`.
    `pending` is the start of an escape sequence cut off by the end of a read,
    held until more input arrives or `escape_timer` fires.
    """

    stream: TextIO
    put_event: Callable[[AnyEvent], None]
    pending: bytes = b""
    escape_timer: TimerHandle | None = None


def start_reading_keys(stream: TextIO, put_event: Callable[[AnyEvent], None]) -> KeyReader:
    """
    Read `stream` whenever it has input, on the running event loop, and put each input parsed from it,
    until `stop_reading_keys` (or the end of the input).

    Reading on the event loop rather than a thread makes stopping immediate, since nothing can be partway through
    a read when `stop_reading_keys` returns.
    """
    reader = KeyReader(stream=stream, put_event=put_event)
    get_running_loop().add_reader(stream.fileno(), read_keys, reader)
    return reader


def stop_reading_keys(reader: KeyReader) -> None:
    """
    Stop reading `reader`'s stream, leaving any input that arrives afterward for whatever reads it next.
    Input held waiting for the rest of an escape sequence is put as it stands, since no more of it is coming.
    """
    get_running_loop().remove_reader(reader.stream.fileno())

    if reader.pending:
        put_parsed_keys(reader, reader.pending, is_final=True)


def read_keys(reader: KeyReader) -> None:
    """
    Read the input waiting on `reader`'s stream and put each input parsed from it.
    At the end of the input, stop reading the stream, since it stays readable and the event loop would call this forever.
    """
    bytes = os.read(reader.stream.fileno(), 2**10)

    if not bytes:
        stop_reading_keys(reader)
        return

    put_parsed_keys(reader, reader.pending + bytes, is_final=False)


def put_parsed_keys(reader: KeyReader, buffer: bytes, is_final: bool) -> None:
    """
    Parse `buffer` and put each input parsed from it,
    holding any cut-off escape sequence in `reader` until `ESCAPE_TIMEOUT` passes with nothing following it.
    """
    if reader.escape_timer is not None:
        reader.escape_timer.cancel()
        reader.escape_timer = None

    parsed = parse_input(buffer, is_final=is_final)
    reader.pending = parsed.remainder

    if reader.pending:
        reader.escape_timer = get_running_loop().call_later(
            ESCAPE_TIMEOUT.total_seconds(), put_parsed_keys, reader, reader.pending, True
        )

    logger.debug(
        "Parsed user input",
        extra={"inputs": parsed.events, "skipped": parsed.skipped, "pending": reader.pending, "bytes": buffer},
    )
    for event in parsed.events:
        reader.put_event(event)


LFLAG = 3
CC = 6

TCGetAttr = list[int | list[int | bytes]]


def start_input_control(stream: TextIO) -> TCGetAttr:
    original = termios.tcgetattr(stream)

    modified = deepcopy(original)

    modified[LFLAG] = original[LFLAG] & ~(termios.ECHO | termios.ICANON)
    modified[CC][termios.VMIN] = 1
    modified[CC][termios.VTIME] = 0

    termios.tcsetattr(stream.fileno(), termios.TCSADRAIN, modified)

    return original


def stop_input_control(stream: TextIO, original: TCGetAttr) -> None:
    termios.tcsetattr(stream.fileno(), termios.TCSADRAIN, original)
