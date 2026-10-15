"""
Pure encoding of input events back into the bytes a terminal sends a program, for a program running in an embedded
terminal: key presses, pastes, mouse events, and focus changes.

It's the inverse of `input_parsing`, and its key table is built from that module's tables, so the two can't drift:
every `Key` encodes to bytes that parse back to it, except those a terminal sends as another key
(Ctrl+H, Ctrl+I and Ctrl+M are Backspace, Tab and Enter) and Shift+Escape, which a terminal sends as Escape.
Where a key has several spellings, it's encoded as xterm sends it, since programs are told `TERM=xterm-256color`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import assert_never

from counterweight.emulator import Modes
from counterweight.events import MouseDown
from counterweight.events import MouseEvent
from counterweight.events import MouseMoved
from counterweight.events import MouseScrolledDown
from counterweight.events import MouseScrolledLeft
from counterweight.events import MouseScrolledRight
from counterweight.events import MouseScrolledUp
from counterweight.events import MouseUp
from counterweight.geometry import Position
from counterweight.input_parsing import ALT
from counterweight.input_parsing import ALT_KEYS
from counterweight.input_parsing import CONTROL
from counterweight.input_parsing import CONTROL_KEYS
from counterweight.input_parsing import CONTROL_SHIFT
from counterweight.input_parsing import FUNCTION_KEYS
from counterweight.input_parsing import LETTER_KEYS
from counterweight.input_parsing import NUMBERED_KEYS
from counterweight.input_parsing import PASTE_END
from counterweight.input_parsing import PASTE_START
from counterweight.input_parsing import SHIFT
from counterweight.input_parsing import modified
from counterweight.keys import Key

ESC = b"\x1b"
CSI = b"\x1b["
SS3 = b"\x1bO"
DEL = b"\x7f"

FOCUS_IN = b"\x1b[I"
FOCUS_OUT = b"\x1b[O"


def key_sequences() -> dict[str, bytes]:
    """
    The bytes for each `Key` a terminal can send, choosing among a key's spellings the one xterm sends:
    `CSI <letter>` for a cursor key and `SS3 <letter>` for F1 to F4, a letter over a number
    (`CSI H` for Home, `CSI 1 ; 2 P` for Shift+F1), xterm's modifier parameter over the VT220's numbers for F13 and up
    (`CSI 15 ; 2 ~` for Shift+F5), and `DEL` for Backspace.
    """
    sequences: dict[str, bytes] = {Key.BackTab: CSI + b"Z", Key.Escape: ESC, Key.Space: b" ", Key.Backspace: DEL}
    for final, key in LETTER_KEYS.items():
        sequences[key] = (SS3 if key in FUNCTION_KEYS else CSI) + final
    for modifier in (SHIFT, ALT, CONTROL, CONTROL_SHIFT):
        modified_sequences = [
            *((b"\x1b[1;%s%s" % (modifier, final), key) for final, key in LETTER_KEYS.items()),
            *((b"\x1b[%s;%s~" % (number, modifier), key) for number, key in NUMBERED_KEYS.items()),
        ]
        for sequence, key in modified_sequences:
            if (modified_key := modified(key, modifier)) is not None:
                sequences.setdefault(modified_key, sequence)
    for number, key in NUMBERED_KEYS.items():
        sequences.setdefault(key, b"\x1b[%s~" % number)
    for byte, key in CONTROL_KEYS.items():
        sequences.setdefault(key, bytes([byte]))
    # A terminal sends these as the keys they're the same bytes as.
    sequences[Key.ControlH] = b"\x08"
    sequences[Key.ControlI] = b"\x09"
    sequences[Key.ControlM] = b"\x0d"
    sequences[Key.ShiftEscape] = ESC
    # Alt with any other key is `ESC` and then the key, as xterm's `metaSendsEscape` sends it.
    for base, with_alt in ALT_KEYS.items():
        sequences.setdefault(with_alt, ESC + sequences[base])
    return sequences


KEY_SEQUENCES: Mapping[str, bytes] = key_sequences()

APPLICATION_CURSOR_KEYS: Mapping[str, bytes] = {
    key: SS3 + final for final, key in LETTER_KEYS.items() if key not in FUNCTION_KEYS
}
"""The cursor keys, Home and End as a program that set DECCKM (`?1`) expects them: `SS3 <letter>`."""


def encode_key(key: str, modes: Modes) -> bytes:
    """
    The bytes a terminal sends a program in `modes` for a [`KeyPressed`][counterweight.events.KeyPressed] of `key`:
    the key's sequence for a named key, the text's UTF-8 for text, and `ESC` before it for text typed with Alt.
    """
    if modes.application_cursor_keys and (sequence := APPLICATION_CURSOR_KEYS.get(key)) is not None:
        return sequence
    if (sequence := KEY_SEQUENCES.get(key)) is not None:
        return sequence
    if key.startswith("alt+"):
        return ESC + key.removeprefix("alt+").encode()
    return key.encode()


def encode_paste(text: str, modes: Modes) -> bytes:
    """
    The bytes a terminal sends a program in `modes` for a paste of `text`: its line breaks as carriage returns,
    as terminals send them, wrapped in bracketed paste's markers if the program set `?2004`.
    The end marker is removed from the text until none is left, so a paste can't end itself early
    and have the rest typed as keys.
    """
    body = text.replace("\r\n", "\r").replace("\n", "\r").encode()
    if not modes.bracketed_paste:
        return body
    while PASTE_END in body:
        body = body.replace(PASTE_END, b"")
    return PASTE_START + body + PASTE_END


WHEEL_CODES: Mapping[type[MouseEvent], int] = {
    MouseScrolledUp: 64,
    MouseScrolledDown: 65,
    MouseScrolledLeft: 66,
    MouseScrolledRight: 67,
}

LEGACY_MOUSE_LIMIT = 223
"""The furthest column or row the legacy mouse encoding can report, as a byte 32 past its 1-based number."""


def encode_mouse(event: MouseEvent, position: Position, modes: Modes) -> bytes | None:
    """
    The bytes a terminal sends a program in `modes` for `event` at `position` on its screen (from its top left, 0-based),
    or `None` if the program didn't ask for this event:
    `?9` reports presses only, `?1000` releases and the wheel too, `?1002` motion while a button is held,
    and `?1003` all motion.
    They're SGR reports (`CSI < code ; x ; y M` or `m`) if the program set `?1006`,
    and otherwise the legacy encoding, which can't report a position past column or row 223.
    """
    tracking = modes.mouse_tracking
    match event:
        case MouseDown(button=button):
            code, is_release = button_code(button), False
        case MouseUp(button=button):
            code, is_release = button_code(button), True
        case MouseMoved(button=held):
            code, is_release = (3 if held is None else button_code(held)) + 32, False
        case MouseScrolledUp() | MouseScrolledDown() | MouseScrolledLeft() | MouseScrolledRight():
            code, is_release = WHEEL_CODES[type(event)], False
        case _ as unreachable:
            assert_never(unreachable)

    if not is_reported(event, tracking):
        return None

    if tracking != "x10":
        code |= (
            (4 if event.is_shift_held else 0) | (8 if event.is_alt_held else 0) | (16 if event.is_control_held else 0)
        )

    x, y = position.x + 1, position.y + 1
    if modes.sgr_mouse:
        return b"\x1b[<%d;%d;%d%s" % (code, x, y, b"m" if is_release else b"M")
    if x > LEGACY_MOUSE_LIMIT or y > LEGACY_MOUSE_LIMIT:
        return None
    # The legacy encoding can't say which button was released: a release is button code 3.
    legacy = (code | 0b11) & ~128 if is_release else code
    return CSI + b"M" + bytes([32 + legacy, 32 + x, 32 + y])


def is_reported(event: MouseEvent, tracking: str) -> bool:
    """Whether a program whose mouse tracking is `tracking` asked for `event`."""
    match event:
        case MouseDown():
            return tracking != "none"
        case MouseUp() | MouseScrolledUp() | MouseScrolledDown() | MouseScrolledLeft() | MouseScrolledRight():
            return tracking in ("normal", "button", "any")
        case MouseMoved(button=None):
            return tracking == "any"
        case MouseMoved():
            return tracking in ("button", "any")
        case _ as unreachable:
            assert_never(unreachable)


def button_code(button: int) -> int:
    """The bits of a mouse report's code that say which button, numbered from 1: bit 128 and the low bits for 8 to 11."""
    if button >= 8:
        return 128 | (button - 8)
    return button - 1


def encode_focus(is_focused: bool, modes: Modes) -> bytes | None:
    """
    The bytes a terminal sends a program in `modes` when it gains focus (`CSI I`) or loses it (`CSI O`),
    or `None` if the program didn't ask for them with `?1004`.
    """
    if not modes.focus_events:
        return None
    return FOCUS_IN if is_focused else FOCUS_OUT


__all__ = [
    "KEY_SEQUENCES",
    "encode_focus",
    "encode_key",
    "encode_mouse",
    "encode_paste",
]
