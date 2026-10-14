"""
Pure encoding of input events back into the bytes a terminal would send a program, for an embedded program's input.

The inverse of `input_parsing`: the key tables are recovered from its tables, so the two can't drift apart.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import assert_never

from counterweight.emulator import Modes
from counterweight.events import (
    MouseDown,
    MouseEvent,
    MouseMoved,
    MouseScrolledDown,
    MouseScrolledLeft,
    MouseScrolledRight,
    MouseScrolledUp,
    MouseUp,
)
from counterweight.geometry import Position
from counterweight.input_parsing import CONTROL_KEYS, LETTER_KEYS, PASTE_END, PASTE_START, SEQUENCE_KEYS
from counterweight.keys import Key

ESC = b"\x1b"


def key_sequences() -> dict[str, bytes]:
    """
    The bytes for each key `input_parsing` recognizes, choosing among a key's several spellings
    the one xterm sends by default: `DEL` for Backspace, `CSI` rather than `SS3` for cursor keys.
    """
    sequences: dict[str, bytes] = {}
    for sequence, key in SEQUENCE_KEYS.items():
        # Prefer CSI over SS3, and the shorter of two CSI spellings (Home is both `CSI H` and `CSI 1 ~`).
        if (existing := sequences.get(key)) is None or (
            existing.startswith(b"\x1bO") and sequence.startswith(b"\x1b[")
        ):
            sequences[key] = sequence
        elif existing.startswith(b"\x1b[") and sequence.startswith(b"\x1b[") and len(sequence) < len(existing):
            sequences[key] = sequence
    for byte, key in CONTROL_KEYS.items():
        sequences.setdefault(key, bytes([byte]))
    sequences[Key.Backspace] = b"\x7f"
    sequences[Key.Escape] = ESC
    sequences[Key.Space] = b" "
    return sequences


KEY_SEQUENCES: Mapping[str, bytes] = key_sequences()

# DECCKM's cursor keys, which a program in application cursor key mode expects as `SS3 <letter>`.
APPLICATION_CURSOR_KEYS: Mapping[str, bytes] = {
    key: b"\x1bO" + final
    for final, key in LETTER_KEYS.items()
    if key in (Key.Up, Key.Down, Key.Right, Key.Left, Key.Home, Key.End)
}


def encode_key(key: str, modes: Modes) -> bytes | None:
    """
    The bytes a terminal sends for a `KeyPressed` with `key`, given the program's `modes`,
    or `None` for a key there's no legacy encoding for.
    """
    if modes.application_cursor_keys and (sequence := APPLICATION_CURSOR_KEYS.get(key)) is not None:
        return sequence
    if (sequence := KEY_SEQUENCES.get(key)) is not None:
        return sequence
    if key.startswith("ctrl+alt+") and (control := KEY_SEQUENCES.get(f"ctrl+{key.removeprefix('ctrl+alt+')}")):
        return ESC + control
    if key.startswith("alt+"):
        rest = key.removeprefix("alt+")
        inner = KEY_SEQUENCES.get(rest) or (rest.encode() if len(rest) == 1 or not rest.isascii() else None)
        return None if inner is None else ESC + inner
    if key in Key.__members__.values():
        return None
    return key.encode()


def encode_paste(text: str, modes: Modes) -> bytes:
    """
    The bytes a terminal sends for a paste of `text`: line breaks as carriage returns, as terminals send them,
    wrapped in bracketed paste markers if the program asked for them.
    An end marker inside the text is dropped, so a paste can't end itself early and type the rest as keys.
    """
    body = text.replace("\r\n", "\r").replace("\n", "\r").encode()
    if not modes.bracketed_paste:
        return body
    return PASTE_START + body.replace(PASTE_END, b"") + PASTE_END


WHEEL_CODES: Mapping[type[MouseEvent], int] = {
    MouseScrolledUp: 64,
    MouseScrolledDown: 65,
    MouseScrolledLeft: 66,
    MouseScrolledRight: 67,
}


def encode_mouse(event: MouseEvent, position: Position, modes: Modes) -> bytes | None:
    """
    The bytes a terminal sends for `event` at `position` in the program's screen,
    given the mouse tracking the program asked for, or `None` if it didn't ask for this event.
    """
    tracking = modes.mouse_tracking
    if tracking == "none":
        return None

    match event:
        case MouseDown(button=button):
            code, is_release = button_code(button), False
        case MouseUp(button=button):
            if tracking == "x10":
                return None
            code, is_release = button_code(button), True
        case MouseMoved(button=held):
            if held is None:
                if tracking != "any":
                    return None
                code, is_release = 3 + 32, False
            else:
                if tracking not in ("button", "any"):
                    return None
                code, is_release = button_code(held) + 32, False
        case MouseScrolledUp() | MouseScrolledDown() | MouseScrolledLeft() | MouseScrolledRight():
            code, is_release = WHEEL_CODES[type(event)], False
        case _ as unreachable:
            assert_never(unreachable)

    if tracking != "x10":
        code |= (
            (4 if event.is_shift_held else 0) | (8 if event.is_alt_held else 0) | (16 if event.is_control_held else 0)
        )

    x, y = position.x + 1, position.y + 1
    if modes.sgr_mouse:
        return b"\x1b[<%d;%d;%d%s" % (code, x, y, b"m" if is_release else b"M")
    if x > 223 or y > 223:
        return None
    # The legacy encoding has no release per button: a release is button code 3.
    legacy = (3 | (code & ~0b11)) if is_release else code
    return b"\x1b[M" + bytes([32 + legacy, 32 + x, 32 + y])


def button_code(button: int) -> int:
    """The low bits (and bit 128 for buttons 8 to 11) of a mouse report's code for `button`, numbered from 1."""
    if button >= 8:
        return 128 | (button - 8)
    return button - 1
