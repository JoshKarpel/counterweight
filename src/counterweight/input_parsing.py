"""
Turns the bytes a terminal sends into events: typed text, control keys, the escape sequences for special keys,
and mouse reports.

Parsing is pure and incremental, so the reader that feeds it owns all of the timing:
`parse_input` returns the events in the bytes read so far, and the trailing bytes that may be the start
of something longer (an escape sequence or a UTF-8 character cut off by the end of a read),
which the reader puts in front of its next read.
"""

from __future__ import annotations

import re
from codecs import getincrementaldecoder
from collections.abc import Mapping
from dataclasses import dataclass

from counterweight.events import (
    AnyEvent,
    KeyPressed,
    MouseDown,
    MouseMoved,
    MouseScrolledDown,
    MouseScrolledUp,
    MouseUp,
)
from counterweight.geometry import Position
from counterweight.graphemes import graphemes
from counterweight.keys import Key

ESC = 0x1B

CONTROL_KEYS: Mapping[int, Key] = {
    0x00: Key.ControlSpace,
    0x01: Key.ControlA,
    0x02: Key.ControlB,
    0x03: Key.ControlC,
    0x04: Key.ControlD,
    0x05: Key.ControlE,
    0x06: Key.ControlF,
    0x07: Key.ControlG,
    0x08: Key.Backspace,
    0x09: Key.Tab,
    0x0A: Key.Enter,
    0x0B: Key.ControlK,
    0x0C: Key.ControlL,
    0x0D: Key.Enter,
    0x0E: Key.ControlN,
    0x0F: Key.ControlO,
    0x10: Key.ControlP,
    0x11: Key.ControlQ,
    0x12: Key.ControlR,
    0x13: Key.ControlS,
    0x14: Key.ControlT,
    0x15: Key.ControlU,
    0x16: Key.ControlV,
    0x17: Key.ControlW,
    0x18: Key.ControlX,
    0x19: Key.ControlY,
    0x1A: Key.ControlZ,
    0x7F: Key.Backspace,
}

SEQUENCE_KEYS: Mapping[bytes, Key] = {
    b"\x1bOP": Key.F1,
    b"\x1bOQ": Key.F2,
    b"\x1bOR": Key.F3,
    b"\x1bOS": Key.F4,
    b"\x1b[A": Key.Up,
    b"\x1b[B": Key.Down,
    b"\x1b[C": Key.Right,
    b"\x1b[D": Key.Left,
    b"\x1b[F": Key.End,
    b"\x1b[Z": Key.BackTab,
    b"\x1b[2~": Key.Insert,
    b"\x1b[3~": Key.Delete,
    b"\x1b[11~": Key.F1,
    b"\x1b[12~": Key.F2,
    b"\x1b[13~": Key.F3,
    b"\x1b[14~": Key.F4,
    b"\x1b[15~": Key.F5,
    b"\x1b[17~": Key.F6,
    b"\x1b[18~": Key.F7,
    b"\x1b[19~": Key.F8,
    b"\x1b[20~": Key.F9,
    b"\x1b[21~": Key.F10,
    b"\x1b[23~": Key.F11,
    b"\x1b[24~": Key.F12,
    b"\x1b[25~": Key.F13,
    b"\x1b[26~": Key.F14,
    b"\x1b[28~": Key.F15,
    b"\x1b[29~": Key.F16,
    b"\x1b[31~": Key.F17,
    b"\x1b[32~": Key.F18,
    b"\x1b[33~": Key.F19,
    b"\x1b[34~": Key.F20,
    b"\x1b[1;2A": Key.ShiftUp,
    b"\x1b[1;2B": Key.ShiftDown,
    b"\x1b[1;2C": Key.ShiftRight,
    b"\x1b[1;2D": Key.ShiftLeft,
    b"\x1b[1;5A": Key.ControlUp,
    b"\x1b[1;5B": Key.ControlDown,
    b"\x1b[1;5C": Key.ControlRight,
    b"\x1b[1;5D": Key.ControlLeft,
    b"\x1b[1;6A": Key.ControlShiftUp,
    b"\x1b[1;6B": Key.ControlShiftDown,
    b"\x1b[1;6C": Key.ControlShiftRight,
    b"\x1b[1;6D": Key.ControlShiftLeft,
    b"\x1b[3;3~": Key.AltDelete,
    b"\x1b[3;5~": Key.ControlDelete,
    b"\x1b[3;6~": Key.ControlShiftInsert,
}

# The shape of a CSI sequence (ESC [, parameter bytes, intermediate bytes, a final byte) or an SS3 one (ESC O, a final byte),
# per ECMA-48, independent of what it means. Without its final byte, the match is a sequence cut short:
# by the end of the input if it reaches the end, or by a byte that can't appear in a sequence if it doesn't.
ESCAPE_SEQUENCE = re.compile(rb"\x1b(?:\[[\x30-\x3f]*[\x20-\x2f]*|O)([\x40-\x7e])?")

# https://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h3-Extended-coordinates
SGR_MOUSE = re.compile(rb"\x1b\[<(\d+);(\d+);(\d+)([Mm])")

CONTROL_BYTE = re.compile(rb"[\x00-\x1f\x7f]")

SURROGATES = re.compile(r"([\ud800-\udfff]+)")


@dataclass(frozen=True, slots=True)
class ParsedInput:
    events: tuple[AnyEvent, ...]

    skipped: tuple[bytes, ...]
    """
    Input that isn't any event: escape sequences with no known meaning or cut short by another byte,
    control bytes with no `Key`, and bytes that aren't UTF-8.
    """

    remainder: bytes
    """The trailing bytes that may be the start of a longer escape sequence or UTF-8 character."""


@dataclass(frozen=True, slots=True)
class Step:
    """What parsing found from one position in the input, and where it stopped."""

    end: int
    events: tuple[AnyEvent, ...] = ()
    skipped: tuple[bytes, ...] = ()


def parse_input(buffer: bytes, *, is_final: bool) -> ParsedInput:
    """
    The events in `buffer`, and the bytes at its end that need more input to make sense of.

    With `is_final`, no more input is coming soon, so nothing is held back:
    a lone `ESC` is the Escape key, and an incomplete UTF-8 character is skipped.
    """
    events: list[AnyEvent] = []
    skipped: list[bytes] = []

    position = 0
    while position < len(buffer):
        byte = buffer[position]
        if byte == ESC:
            step = parse_escape(buffer, position, is_final)
        elif CONTROL_BYTE.match(buffer, position):
            step = parse_control(buffer, position)
        else:
            step = parse_text(buffer, position, is_final)

        events.extend(step.events)
        skipped.extend(step.skipped)

        if step.end == position:
            break
        position = step.end

    return ParsedInput(events=tuple(events), skipped=tuple(skipped), remainder=buffer[position:])


def parse_escape(buffer: bytes, start: int, is_final: bool) -> Step:
    """
    Parse from an `ESC`, which may begin an escape sequence or be the Escape key on its own.
    Stops where it started if there isn't enough input yet to tell which.
    """
    match = ESCAPE_SEQUENCE.match(buffer, start)

    if match is None:
        is_last_byte = start + 1 == len(buffer)
        if is_last_byte and not is_final:
            return Step(end=start)
        return Step(end=start + 1, events=(KeyPressed(key=Key.Escape),))

    sequence = match[0]

    if match[1] is not None:
        event = sequence_event(sequence)
        if event is None:
            return Step(end=match.end(), skipped=(sequence,))
        return Step(end=match.end(), events=(event,))

    if match.end() < len(buffer):
        return Step(end=match.end(), skipped=(sequence,))

    if not is_final:
        return Step(end=start)

    return Step(end=start + 1, events=(KeyPressed(key=Key.Escape),))


def sequence_event(sequence: bytes) -> AnyEvent | None:
    """The event a complete escape sequence stands for, or `None` if it isn't one we know."""
    if key := SEQUENCE_KEYS.get(sequence):
        return KeyPressed(key=key)

    if mouse := SGR_MOUSE.fullmatch(sequence):
        return mouse_event(int(mouse[1]), Position(x=int(mouse[2]) - 1, y=int(mouse[3]) - 1), mouse[4])

    return None


def mouse_event(button_info: int, position: Position, final: bytes) -> AnyEvent:
    """The event for an SGR mouse report; `final` is `M` for a press or motion and `m` for a release."""
    moving = button_info & 32
    button = (button_info & 0b11) + 1

    if button_info == 65:
        return MouseScrolledUp(absolute=position)
    elif button_info == 64:
        return MouseScrolledDown(absolute=position)
    elif moving:
        # Motion with no button held reports button 3, which is 4 here.
        return MouseMoved(absolute=position, button=button if button != 4 else None)
    elif final == b"m":
        return MouseUp(absolute=position, button=button)
    else:
        return MouseDown(absolute=position, button=button)


def parse_control(buffer: bytes, start: int) -> Step:
    """Parse one control byte other than `ESC`."""
    if key := CONTROL_KEYS.get(buffer[start]):
        return Step(end=start + 1, events=(KeyPressed(key=key),))
    return Step(end=start + 1, skipped=(buffer[start : start + 1],))


def parse_text(buffer: bytes, start: int, is_final: bool) -> Step:
    """
    Parse a run of text up to the next control byte, one `KeyPressed` per grapheme cluster.
    Stops before a UTF-8 character cut off by the end of the input, unless `is_final`.
    """
    control = CONTROL_BYTE.search(buffer, start)
    end = control.start() if control else len(buffer)

    # surrogateescape turns each byte that isn't UTF-8 into a lone surrogate, rather than raising or replacing it,
    # so it can be skipped without dropping the rest of the run.
    decoder = getincrementaldecoder("utf-8")("surrogateescape")
    text = decoder.decode(buffer[start:end], final=is_final or control is not None)
    held, _ = decoder.getstate()

    # Odd pieces are the runs of surrogates, split out before segmenting so a combining mark can't join one.
    pieces = SURROGATES.split(text)
    return Step(
        end=end - len(held),
        events=tuple(KeyPressed(key=grapheme) for piece in pieces[::2] for grapheme in graphemes(piece)),
        skipped=tuple(piece.encode("utf-8", "surrogateescape") for piece in pieces[1::2]),
    )
