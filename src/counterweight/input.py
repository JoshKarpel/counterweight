from __future__ import annotations

import logging
import os
import termios
from asyncio import TimerHandle, get_running_loop
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TextIO

from counterweight.events import AnyEvent
from counterweight.input_parsing import parse_input

logger = logging.getLogger(__name__)

# How many bytes each read asks for. A terminal hands over at most a few kilobytes per read however many are asked for,
# so this matters only for input that isn't a terminal, such as a pipe.
READ_SIZE = 2**16

# How long a lone ESC (or the start of an escape sequence) at the end of a read waits for the rest of a sequence
# before it is the Escape key.
ESCAPE_TIMEOUT = timedelta(milliseconds=50)

# How long a paste whose end hasn't arrived waits for more of it before what has arrived is the paste.
# Each read restarts the wait, so a paste only times out if its input stalls, as over a slow connection.
PASTE_TIMEOUT = timedelta(seconds=1)


@dataclass(slots=True)
class KeyReader:
    """
    The state of reading a stream between `start_reading_keys` and `stop_reading_keys`.
    `held` is the start of an escape sequence or a paste cut off by the end of a read,
    and `paste_searched` how much of a held paste the parser has searched for its end,
    both held until more input arrives or `hold_timer` fires.
    """

    stream: TextIO
    put_event: Callable[[AnyEvent], None]
    held: bytearray = field(default_factory=bytearray)
    paste_searched: int | None = None
    hold_timer: TimerHandle | None = None


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
    Input held waiting for the rest of an escape sequence or paste is put as it stands, since no more of it is coming.
    """
    get_running_loop().remove_reader(reader.stream.fileno())

    if reader.held:
        put_parsed_keys(reader, b"", is_final=True)


def read_keys(reader: KeyReader) -> None:
    """
    Read the input waiting on `reader`'s stream and put each input parsed from it.
    At the end of the input, stop reading the stream, since it stays readable and the event loop would call this forever.
    """
    read = os.read(reader.stream.fileno(), READ_SIZE)

    if not read:
        stop_reading_keys(reader)
        return

    put_parsed_keys(reader, read, is_final=False)


def put_parsed_keys(reader: KeyReader, read: bytes, is_final: bool) -> None:
    """
    Parse the input held in `reader` followed by `read`, and put each input parsed from it,
    holding any cut-off escape sequence or paste in `reader` until `ESCAPE_TIMEOUT` or `PASTE_TIMEOUT`
    passes with nothing following it.
    """
    if reader.hold_timer is not None:
        reader.hold_timer.cancel()
        reader.hold_timer = None

    # Appending to the held bytes and deleting from their front, rather than building a new buffer from them,
    # keeps a long paste arriving over many reads from being copied once per read.
    reader.held += read
    parsed = parse_input(reader.held, is_final=is_final, paste_searched=reader.paste_searched)
    del reader.held[: parsed.end]
    reader.paste_searched = parsed.paste_searched

    if reader.held:
        timeout = ESCAPE_TIMEOUT if parsed.paste_searched is None else PASTE_TIMEOUT
        reader.hold_timer = get_running_loop().call_later(timeout.total_seconds(), put_parsed_keys, reader, b"", True)

    logger.debug(
        "Parsed user input",
        extra={"inputs": parsed.events, "skipped": parsed.skipped, "held": len(reader.held), "bytes": read},
    )
    for event in parsed.events:
        reader.put_event(event)


IFLAG = 0
LFLAG = 3
CC = 6

TCGetAttr = list[int | list[int | bytes]]


def start_input_control(stream: TextIO) -> TCGetAttr:
    original = termios.tcgetattr(stream)

    modified = deepcopy(original)

    # Enter sends a carriage return and Ctrl+J a line feed, so neither is translated into the other.
    modified[IFLAG] = original[IFLAG] & ~(termios.ICRNL | termios.INLCR | termios.IGNCR)
    modified[LFLAG] = original[LFLAG] & ~(termios.ECHO | termios.ICANON)
    modified[CC][termios.VMIN] = 1
    modified[CC][termios.VTIME] = 0

    termios.tcsetattr(stream.fileno(), termios.TCSADRAIN, modified)

    return original


def stop_input_control(stream: TextIO, original: TCGetAttr) -> None:
    termios.tcsetattr(stream.fileno(), termios.TCSADRAIN, original)
