"""
Turns the bytes a terminal sends into events: typed text, control keys, the escape sequences for special keys,
keys pressed with Alt, mouse reports, and bracketed pastes.

Parsing is pure and incremental, so the reader that feeds it owns all of the timing:
`parse_input` returns the events in the bytes read so far, and where it stopped short of the trailing bytes
that may be the start of something longer (an escape sequence, a paste, or a UTF-8 character cut off by the end
of a read), which the reader keeps in front of its next read.
"""

from __future__ import annotations

import re
from codecs import getincrementaldecoder
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal
from typing import assert_never

from counterweight.events import AnyEvent
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseMoved
from counterweight.events import MouseScrolledDown
from counterweight.events import MouseScrolledLeft
from counterweight.events import MouseScrolledRight
from counterweight.events import MouseScrolledUp
from counterweight.events import MouseUp
from counterweight.events import Pasted
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
    0x0A: Key.ControlJ,
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

# The keys whose sequences end in a letter: `CSI <letter>`, `SS3 <letter>`, or `CSI 1 ; <modifier> <letter>`.
LETTER_KEYS: Mapping[bytes, Key] = {
    b"A": Key.Up,
    b"B": Key.Down,
    b"C": Key.Right,
    b"D": Key.Left,
    b"H": Key.Home,
    b"F": Key.End,
    b"P": Key.F1,
    b"Q": Key.F2,
    b"R": Key.F3,
    b"S": Key.F4,
}

# The keys whose sequences are `CSI <number> ~` or `CSI <number> ; <modifier> ~`.
# Home and End have two numbers each, from the VT220 and rxvt, and F1 through F4 have numbers besides their letters.
NUMBERED_KEYS: Mapping[bytes, Key] = {
    b"1": Key.Home,
    b"2": Key.Insert,
    b"3": Key.Delete,
    b"4": Key.End,
    b"5": Key.PageUp,
    b"6": Key.PageDown,
    b"7": Key.Home,
    b"8": Key.End,
    b"11": Key.F1,
    b"12": Key.F2,
    b"13": Key.F3,
    b"14": Key.F4,
    b"15": Key.F5,
    b"17": Key.F6,
    b"18": Key.F7,
    b"19": Key.F8,
    b"20": Key.F9,
    b"21": Key.F10,
    b"23": Key.F11,
    b"24": Key.F12,
    b"25": Key.F13,
    b"26": Key.F14,
    b"28": Key.F15,
    b"29": Key.F16,
    b"31": Key.F17,
    b"32": Key.F18,
    b"33": Key.F19,
    b"34": Key.F20,
}

FUNCTION_KEYS = [Key(f"f{number}") for number in range(1, 25)]


def alt_name(key: Key) -> str:
    """
    The name of `key` pressed with Alt, which `Key` may have no member for:
    `alt+` before its name, or after `ctrl+` for a Control key, as in `ctrl+alt+a`.
    """
    if key is Key.Space:
        return "alt+space"
    if key.value.startswith("ctrl+"):
        return f"ctrl+alt+{key.value.removeprefix('ctrl+')}"
    return f"alt+{key.value}"


KEY_NAMES = frozenset(key.value for key in Key)

# Each key that has a member of `Key` for it pressed with Alt, and that member.
ALT_KEYS: Mapping[str, Key] = {key: Key(alt_name(key)) for key in Key if alt_name(key) in KEY_NAMES}

# xterm's modifier parameter is 1 plus the sum of Shift (1), Alt (2) and Control (4).
type Modifier = Literal[b"2", b"3", b"5", b"6"]
SHIFT: Modifier = b"2"
ALT: Modifier = b"3"
CONTROL: Modifier = b"5"
CONTROL_SHIFT: Modifier = b"6"


def modified(key: Key, modifier: Modifier) -> Key | None:
    """
    The key xterm reports for `key` pressed with `modifier`, or `None` if `Key` has no member for it.

    xterm reports Shift with F1 through F12 as F13 through F24.
    """
    if key in FUNCTION_KEYS:
        number = FUNCTION_KEYS.index(key) + 1
        if number > 12:
            return None
        match modifier:
            case b"2":
                return FUNCTION_KEYS[number + 11]
            case b"5":
                return Key(f"ctrl+{key.value}")
            case b"6":
                return Key(f"ctrl+{FUNCTION_KEYS[number + 11].value}")
            case b"3":
                return ALT_KEYS[key]
            case _ as unreachable:
                assert_never(unreachable)

    match modifier:
        case b"2":
            return Key(f"shift+{key.value}")
        case b"5":
            return Key(f"ctrl+{key.value}")
        case b"6":
            return Key(f"ctrl+shift+{key.value}")
        case b"3":
            return ALT_KEYS.get(key)
        case _ as unreachable:
            assert_never(unreachable)


def sequence_keys() -> dict[bytes, Key]:
    """Every escape sequence for a key, and the key it reports."""
    lookup: dict[bytes, Key] = {b"\x1b[Z": Key.BackTab}
    for final, key in LETTER_KEYS.items():
        lookup[b"\x1bO" + final] = key
        # Unmodified F1 through F4 are only ever `SS3 <letter>`.
        if key not in FUNCTION_KEYS:
            lookup[b"\x1b[" + final] = key
    for number, key in NUMBERED_KEYS.items():
        lookup[b"\x1b[%s~" % number] = key
    for modifier in (SHIFT, ALT, CONTROL, CONTROL_SHIFT):
        modified_sequences = [
            *((b"\x1b[1;%s%s" % (modifier, final), key) for final, key in LETTER_KEYS.items()),
            *((b"\x1b[%s;%s~" % (number, modifier), key) for number, key in NUMBERED_KEYS.items()),
        ]
        for sequence, key in modified_sequences:
            if (modified_key := modified(key, modifier)) is not None:
                lookup[sequence] = modified_key
    return lookup


SEQUENCE_KEYS: Mapping[bytes, Key] = sequence_keys()

# The shape of a CSI sequence (ESC [, parameter bytes, intermediate bytes, a final byte) or an SS3 one (ESC O, a final byte),
# per ECMA-48, independent of what it means. Without its final byte, the match is a sequence cut short:
# by the end of the input if it reaches the end, or by a byte that can't appear in a sequence if it doesn't.
ESCAPE_SEQUENCE = re.compile(rb"\x1b(?:\[[\x30-\x3f]*[\x20-\x2f]*|O)([\x40-\x7e])?")

# https://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h3-Extended-coordinates
SGR_MOUSE = re.compile(rb"\x1b\[<(\d+);(\d+);(\d+)([Mm])")

# The wheel event for each value of the low two bits of an SGR code with bit 64 set.
WHEEL_EVENTS: tuple[type[MouseScrolledDown | MouseScrolledUp | MouseScrolledLeft | MouseScrolledRight], ...] = (
    MouseScrolledUp,
    MouseScrolledDown,
    MouseScrolledLeft,
    MouseScrolledRight,
)

CONTROL_BYTE = re.compile(rb"[\x00-\x1f\x7f]")

# https://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h2-Bracketed-Paste-Mode
PASTE_START = b"\x1b[200~"
PASTE_END = b"\x1b[201~"

SURROGATES = re.compile(r"([\ud800-\udfff]+)")


@dataclass(frozen=True, slots=True)
class ParsedInput:
    events: tuple[AnyEvent, ...]

    skipped: tuple[bytes, ...]
    """
    Input that isn't any event: escape sequences with no known meaning or cut short by another byte,
    control bytes with no `Key`, and bytes that aren't UTF-8.
    """

    end: int
    """
    How far parsing got: the bytes from here on may be the start of a longer escape sequence, paste,
    or UTF-8 character, so they're held for the next parse.
    """

    paste_searched: int | None = None
    """
    If the held bytes are a paste whose end hasn't arrived, how many of them have been searched for its end,
    so the next parse searches only what follows; `None` if they aren't.
    """


@dataclass(frozen=True, slots=True)
class Step:
    """What parsing found from one position in the input, and where it stopped."""

    end: int
    events: tuple[AnyEvent, ...] = ()
    skipped: tuple[bytes, ...] = ()
    paste_searched: int | None = None


def parse_input(buffer: bytes | bytearray, *, is_final: bool, paste_searched: int | None = None) -> ParsedInput:
    """
    The events in `buffer`, and how far it parsed before the bytes at its end that need more input to make sense of.

    With `is_final`, no more input is coming soon, so nothing is held back:
    a lone `ESC` is the Escape key, an incomplete UTF-8 character is skipped,
    and a paste whose end hasn't arrived is the paste.

    `paste_searched` MUST be the `paste_searched` of the parse that held the bytes `buffer` starts with,
    so a long paste arriving over many reads is searched once rather than once per read.
    """
    events: list[AnyEvent] = []
    skipped: list[bytes] = []

    position = 0
    step = Step(end=0)
    while position < len(buffer):
        byte = buffer[position]
        if byte == ESC and buffer.startswith(PASTE_START, position):
            step = parse_paste(buffer, position, is_final, (paste_searched or 0) if position == 0 else 0)
        elif byte == ESC:
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

    return ParsedInput(
        events=tuple(events),
        skipped=tuple(skipped),
        end=position,
        paste_searched=step.paste_searched,
    )


def parse_escape(buffer: bytes | bytearray, start: int, is_final: bool) -> Step:
    """
    Parse from an `ESC`, which may begin an escape sequence, be the Escape key on its own,
    or be Alt with the key that follows it.
    Stops where it started if there isn't enough input yet to tell which.
    """
    match = ESCAPE_SEQUENCE.match(buffer, start)

    if match is not None:
        sequence = bytes(match[0])
        if match[1] is not None:
            event = sequence_event(sequence)
            if event is None:
                return Step(end=match.end(), skipped=(sequence,))
            return Step(end=match.end(), events=(event,))
        if match.end() < len(buffer):
            return Step(end=match.end(), skipped=(sequence,))
        if not is_final:
            return Step(end=start)
        # No more input is coming, so this was never a sequence: it's Alt with `[` or `O`, and text after that.

    if start + 1 < len(buffer):
        return parse_alt(buffer, start, is_final)

    if not is_final:
        return Step(end=start)

    return Step(end=start + 1, events=(KeyPressed(key=Key.Escape),))


def parse_alt(buffer: bytes | bytearray, start: int, is_final: bool) -> Step:
    """
    Parse from an `ESC` that more input follows, which is Alt with the key the input after it starts with,
    since terminals send a key pressed with Alt as `ESC` and then the key (xterm's `metaSendsEscape`).
    An `ESC` followed by something other than a key that has a name with Alt is the Escape key on its own.
    Stops where it started if there isn't enough input yet to tell which key follows.
    """
    following = start + 1
    if buffer[following] == ESC:
        step = parse_escaped_sequence(buffer, following, is_final)
    elif CONTROL_BYTE.match(buffer, following):
        step = parse_control(buffer, following)
        if not step.events:
            return Step(end=step.end, skipped=(bytes(buffer[start : step.end]),))
    else:
        step = parse_text(buffer, following, is_final)

    if step.end == following:
        return Step(end=start)

    match step.events:
        case (KeyPressed(key=key), *rest) if is_key_at(buffer, following, key) and (alt := with_alt(key)) is not None:
            return Step(end=step.end, events=(KeyPressed(key=alt), *rest), skipped=step.skipped)
        case _:
            return Step(end=following, events=(KeyPressed(key=Key.Escape),))


def parse_escaped_sequence(buffer: bytes | bytearray, start: int, is_final: bool) -> Step:
    """
    Parse from an `ESC` that follows another, as some terminals send Alt with a key that has an escape sequence
    (rxvt sends Alt+Up as `ESC ESC [ A`): the event of the sequence that starts there, or no event if none does.
    Stops where it started if there isn't enough input yet to tell.
    """
    match = ESCAPE_SEQUENCE.match(buffer, start)
    if match is None:
        is_last_byte = start + 1 == len(buffer)
        return Step(end=start if is_last_byte and not is_final else start + 1)
    if match[1] is not None:
        event = sequence_event(bytes(match[0]))
        return Step(end=match.end(), events=() if event is None else (event,))
    if match.end() == len(buffer) and not is_final:
        return Step(end=start)
    return Step(end=start + 1)


def is_key_at(buffer: bytes | bytearray, start: int, key: str) -> bool:
    """
    Whether a parse from `start` that found a press of `key` first found it at `start`,
    rather than after input it skipped: a named key's always is, and text's is if its UTF-8 starts there.
    """
    return isinstance(key, Key) or buffer.startswith(key.encode(), start)


def with_alt(key: str) -> str | None:
    """
    The `KeyPressed.key` for `key` pressed with Alt: a member of `Key` for a named key, or `None` if it has none,
    and `alt+` before the text for text.
    """
    if isinstance(key, Key) or key == Key.Space:
        return ALT_KEYS.get(key)
    return f"alt+{key}"


def parse_paste(buffer: bytes | bytearray, start: int, is_final: bool, searched: int) -> Step:
    """
    Parse a bracketed paste: everything between `PASTE_START` and `PASTE_END`, control bytes and escapes included,
    is the pasted text.
    Stops where it started until `PASTE_END` arrives, unless `is_final`,
    when no more of the paste is coming soon and what has arrived is the paste.
    The first `searched` bytes from `start` have been searched for `PASTE_END` already,
    but for its first bytes, which the next read may complete.
    """
    text_start = start + len(PASTE_START)
    text_end = buffer.find(PASTE_END, max(text_start, start + searched - len(PASTE_END) + 1))

    if text_end == -1:
        if not is_final:
            return Step(end=start, paste_searched=len(buffer) - start)
        text_end = end = len(buffer)
    else:
        end = text_end + len(PASTE_END)

    # As in parse_text, each byte that isn't UTF-8 becomes a lone surrogate, so it can be skipped.
    pieces = SURROGATES.split(buffer[text_start:text_end].decode("utf-8", "surrogateescape"))
    text = "".join(pieces[::2]).replace("\r\n", "\n").replace("\r", "\n")
    return Step(
        end=end,
        events=(Pasted(text=text),),
        skipped=tuple(piece.encode("utf-8", "surrogateescape") for piece in pieces[1::2]),
    )


def sequence_event(sequence: bytes) -> AnyEvent | None:
    """The event a complete escape sequence stands for, or `None` if it isn't one we know."""
    if key := SEQUENCE_KEYS.get(sequence):
        return KeyPressed(key=key)

    if mouse := SGR_MOUSE.fullmatch(sequence):
        return mouse_event(int(mouse[1]), Position(x=int(mouse[2]) - 1, y=int(mouse[3]) - 1), mouse[4])

    return None


def mouse_event(button_info: int, position: Position, final: bytes) -> AnyEvent:
    """The event for an SGR mouse report; `final` is `M` for a press or motion and `m` for a release."""
    # Bits 4, 8, and 16 report Shift, Meta (which terminals send for Alt), and Control on top of every code,
    # so every check below masks them off rather than comparing the whole code.
    is_shift_held = bool(button_info & 4)
    is_alt_held = bool(button_info & 8)
    is_control_held = bool(button_info & 16)
    low_bits = button_info & 0b11

    if button_info & 64:
        return WHEEL_EVENTS[low_bits](
            absolute=position,
            is_shift_held=is_shift_held,
            is_alt_held=is_alt_held,
            is_control_held=is_control_held,
        )

    # Bit 128 marks buttons 8 through 11 (back, forward, ...), numbered by the same low bits as buttons 1 through 4.
    button = low_bits + (8 if button_info & 128 else 1)
    if button_info & 32:
        # Motion with no button held reports button 3, which is 4 here.
        return MouseMoved(
            absolute=position,
            button=button if button != 4 else None,
            is_shift_held=is_shift_held,
            is_alt_held=is_alt_held,
            is_control_held=is_control_held,
        )
    if final == b"m":
        return MouseUp(
            absolute=position,
            button=button,
            is_shift_held=is_shift_held,
            is_alt_held=is_alt_held,
            is_control_held=is_control_held,
        )
    return MouseDown(
        absolute=position,
        button=button,
        is_shift_held=is_shift_held,
        is_alt_held=is_alt_held,
        is_control_held=is_control_held,
    )


def parse_control(buffer: bytes | bytearray, start: int) -> Step:
    """Parse one control byte other than `ESC`."""
    if key := CONTROL_KEYS.get(buffer[start]):
        return Step(end=start + 1, events=(KeyPressed(key=key),))
    return Step(end=start + 1, skipped=(bytes(buffer[start : start + 1]),))


def parse_text(buffer: bytes | bytearray, start: int, is_final: bool) -> Step:
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
