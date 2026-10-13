from __future__ import annotations

import logging
from collections.abc import Generator, Mapping
from enum import Enum
from string import printable

from parsy import Parser, char_from, generate, match_item

from counterweight.events import (
    AnyEvent,
    KeyPressed,
    MouseDown,
    MouseMoved,
    MouseScrolledDown,
    MouseScrolledLeft,
    MouseScrolledRight,
    MouseScrolledUp,
    MouseUp,
)
from counterweight.geometry import Position

logger = logging.getLogger(__name__)


class Key(str, Enum):
    """
    Derived from https://github.com/Textualize/textual/blob/c966243b059f0352e2a23b9695776838195364a3/src/textual/keys.py
    """

    Escape = "escape"  # Also Control-[
    ShiftEscape = "shift+escape"

    ControlA = "ctrl+a"
    ControlB = "ctrl+b"
    ControlC = "ctrl+c"
    ControlD = "ctrl+d"
    ControlE = "ctrl+e"
    ControlF = "ctrl+f"
    ControlG = "ctrl+g"
    ControlH = "ctrl+h"
    ControlI = "ctrl+i"  # Tab
    ControlJ = "ctrl+j"  # Newline
    ControlK = "ctrl+k"
    ControlL = "ctrl+l"
    ControlM = "ctrl+m"  # Carriage return
    ControlN = "ctrl+n"
    ControlO = "ctrl+o"
    ControlP = "ctrl+p"
    ControlQ = "ctrl+q"
    ControlR = "ctrl+r"
    ControlS = "ctrl+s"
    ControlT = "ctrl+t"
    ControlU = "ctrl+u"
    ControlV = "ctrl+v"
    ControlW = "ctrl+w"
    ControlX = "ctrl+x"
    ControlY = "ctrl+y"
    ControlZ = "ctrl+z"

    Left = "left"
    Right = "right"
    Up = "up"
    Down = "down"
    Home = "home"
    End = "end"
    Insert = "insert"
    Delete = "delete"
    PageUp = "pageup"
    PageDown = "pagedown"

    ControlLeft = "ctrl+left"
    ControlRight = "ctrl+right"
    ControlUp = "ctrl+up"
    ControlDown = "ctrl+down"
    ControlHome = "ctrl+home"
    ControlEnd = "ctrl+end"
    ControlInsert = "ctrl+insert"
    ControlDelete = "ctrl+delete"
    ControlPageUp = "ctrl+pageup"
    ControlPageDown = "ctrl+pagedown"

    ShiftLeft = "shift+left"
    ShiftRight = "shift+right"
    ShiftUp = "shift+up"
    ShiftDown = "shift+down"
    ShiftHome = "shift+home"
    ShiftEnd = "shift+end"
    ShiftInsert = "shift+insert"
    ShiftDelete = "shift+delete"
    ShiftPageUp = "shift+pageup"
    ShiftPageDown = "shift+pagedown"

    ControlShiftLeft = "ctrl+shift+left"
    ControlShiftRight = "ctrl+shift+right"
    ControlShiftUp = "ctrl+shift+up"
    ControlShiftDown = "ctrl+shift+down"
    ControlShiftHome = "ctrl+shift+home"
    ControlShiftEnd = "ctrl+shift+end"
    ControlShiftInsert = "ctrl+shift+insert"
    ControlShiftDelete = "ctrl+shift+delete"
    ControlShiftPageUp = "ctrl+shift+pageup"
    ControlShiftPageDown = "ctrl+shift+pagedown"

    AltDelete = "alt+delete"

    BackTab = "shift+tab"  # shift + tab

    F1 = "f1"
    F2 = "f2"
    F3 = "f3"
    F4 = "f4"
    F5 = "f5"
    F6 = "f6"
    F7 = "f7"
    F8 = "f8"
    F9 = "f9"
    F10 = "f10"
    F11 = "f11"
    F12 = "f12"
    F13 = "f13"
    F14 = "f14"
    F15 = "f15"
    F16 = "f16"
    F17 = "f17"
    F18 = "f18"
    F19 = "f19"
    F20 = "f20"
    F21 = "f21"
    F22 = "f22"
    F23 = "f23"
    F24 = "f24"

    ControlF1 = "ctrl+f1"
    ControlF2 = "ctrl+f2"
    ControlF3 = "ctrl+f3"
    ControlF4 = "ctrl+f4"
    ControlF5 = "ctrl+f5"
    ControlF6 = "ctrl+f6"
    ControlF7 = "ctrl+f7"
    ControlF8 = "ctrl+f8"
    ControlF9 = "ctrl+f9"
    ControlF10 = "ctrl+f10"
    ControlF11 = "ctrl+f11"
    ControlF12 = "ctrl+f12"
    ControlF13 = "ctrl+f13"
    ControlF14 = "ctrl+f14"
    ControlF15 = "ctrl+f15"
    ControlF16 = "ctrl+f16"
    ControlF17 = "ctrl+f17"
    ControlF18 = "ctrl+f18"
    ControlF19 = "ctrl+f19"
    ControlF20 = "ctrl+f20"
    ControlF21 = "ctrl+f21"
    ControlF22 = "ctrl+f22"
    ControlF23 = "ctrl+f23"
    ControlF24 = "ctrl+f24"

    ControlSpace = "ctrl+space"
    Tab = "tab"
    Space = " "
    Enter = "enter"
    Backspace = "backspace"

    def __repr__(self) -> str:
        return str(self)


SINGLE_CHAR_TRANSFORMS: Mapping[bytes, Key] = {
    b"\x1b": Key.Escape,
    b"\t": Key.Tab,
    b"\n": Key.Enter,
    b" ": Key.Space,
    b"\x00": Key.ControlSpace,
    b"\x01": Key.ControlA,
    b"\x02": Key.ControlB,
    b"\x03": Key.ControlC,
    b"\x04": Key.ControlD,
    b"\x05": Key.ControlE,
    b"\x06": Key.ControlF,
    b"\x07": Key.ControlG,
    b"\x08": Key.Backspace,
    b"\x0b": Key.ControlK,
    b"\x0c": Key.ControlL,
    b"\x0e": Key.ControlN,
    b"\x0f": Key.ControlO,
    b"\x10": Key.ControlP,
    b"\x11": Key.ControlQ,
    b"\x12": Key.ControlR,
    b"\x13": Key.ControlS,
    b"\x14": Key.ControlT,
    b"\x15": Key.ControlU,
    b"\x16": Key.ControlV,
    b"\x17": Key.ControlW,
    b"\x18": Key.ControlX,
    b"\x19": Key.ControlY,
    b"\x1a": Key.ControlZ,
    b"\x7f": Key.Backspace,
}

single_transformable_char = char_from(b"".join((printable.encode("utf-8"), *SINGLE_CHAR_TRANSFORMS.keys())))
decimal_digits = char_from(b"0123456789").many().map(b"".join)


@generate
def single_char() -> Generator[Parser, bytes, AnyEvent]:
    c = yield single_transformable_char

    return KeyPressed(key=SINGLE_CHAR_TRANSFORMS.get(c) or c.decode("utf-8"))


esc = match_item(b"\x1b")
left_bracket = match_item(b"[")


@generate
def escape_sequence() -> Generator[Parser, AnyEvent, AnyEvent]:
    keys = yield esc >> (ss3 | (left_bracket >> (mouse | two_params | zero_or_one_params)))

    return keys


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

# xterm's modifier parameter is 1 plus the sum of Shift (1), Alt (2) and Control (4).
SHIFT = b"2"
ALT = b"3"
CONTROL = b"5"
CONTROL_SHIFT = b"6"


def modified(key: Key, modifier: bytes) -> Key | None:
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
            case _:
                return None

    match modifier:
        case b"2":
            return Key(f"shift+{key.value}")
        case b"5":
            return Key(f"ctrl+{key.value}")
        case b"6":
            return Key(f"ctrl+shift+{key.value}")
        case b"3" if key is Key.Delete:
            return Key.AltDelete
        case _:
            return None


def csi_lookup() -> dict[tuple[bytes, ...], Key]:
    """Every `CSI` key sequence's parameters and final byte, and the key it reports."""
    lookup: dict[tuple[bytes, ...], Key] = {(b"", b"Z"): Key.BackTab}
    for modifier in (None, SHIFT, ALT, CONTROL, CONTROL_SHIFT):
        for final, key in LETTER_KEYS.items():
            if modifier is None:
                # Unmodified F1 through F4 are only ever `SS3 <letter>`.
                if key not in FUNCTION_KEYS:
                    lookup[(b"", final)] = key
            elif (modified_key := modified(key, modifier)) is not None:
                lookup[(b"1", modifier, final)] = modified_key
        for number, key in NUMBERED_KEYS.items():
            if modifier is None:
                lookup[(number, b"~")] = key
            elif (modified_key := modified(key, modifier)) is not None:
                lookup[(number, modifier, b"~")] = modified_key
    return lookup


ss3_prefix = match_item(b"O")


@generate
def ss3() -> Generator[Parser, bytes, AnyEvent]:
    final = yield ss3_prefix >> char_from(b"".join(LETTER_KEYS))

    return KeyPressed(key=LETTER_KEYS[final])


left_angle = match_item(b"<")
mM = char_from(b"mM")

# The wheel event for each value of the low two bits of an SGR code with bit 64 set.
WHEEL_EVENTS: tuple[type[MouseScrolledDown | MouseScrolledUp | MouseScrolledLeft | MouseScrolledRight], ...] = (
    MouseScrolledUp,
    MouseScrolledDown,
    MouseScrolledLeft,
    MouseScrolledRight,
)


@generate
def mouse() -> Generator[Parser, bytes, AnyEvent]:
    # https://www.xfree86.org/current/ctlseqs.html
    # https://invisible-island.net/xterm/ctlseqs/ctlseqs.pdf
    yield left_angle

    buttons_ = yield decimal_digits
    yield semicolon
    x_ = yield decimal_digits
    yield semicolon
    y_ = yield decimal_digits
    m = yield mM

    button_info = int(buttons_)
    x = int(x_) - 1
    y = int(y_) - 1

    pos = Position(x=x, y=y)
    # Bits 4, 8, and 16 report Shift, Meta, and Control, which no event carries yet,
    # so every check below masks them off rather than comparing the whole code.
    low_bits = button_info & 0b11

    if button_info & 64:
        return WHEEL_EVENTS[low_bits](absolute=pos)

    # Bit 128 marks buttons 8 through 11 (back, forward, ...), numbered by the same low bits as buttons 1 through 4.
    button = low_bits + (8 if button_info & 128 else 1)
    if button_info & 32:
        return MouseMoved(absolute=pos, button=button if button != 4 else None)  # raw 3 is released, becomes 4 above
    elif m == b"m":
        return MouseUp(absolute=pos, button=button)
    else:  # m == b"M"
        return MouseDown(absolute=pos, button=button)


CSI_LOOKUP: Mapping[tuple[bytes, ...], Key] = csi_lookup()

final_csi_char = char_from(b"".join(sorted(set(key[-1] for key in CSI_LOOKUP))))
semicolon = match_item(b";")


@generate
def two_params() -> Generator[Parser, bytes, AnyEvent]:
    p1 = yield decimal_digits
    yield semicolon
    p2 = yield decimal_digits
    e = yield final_csi_char

    return KeyPressed(key=CSI_LOOKUP[(p1, p2, e)])


@generate
def zero_or_one_params() -> Generator[Parser, bytes, AnyEvent]:
    p1 = yield decimal_digits  # zero params => b""
    e = yield final_csi_char

    return KeyPressed(key=CSI_LOOKUP[(p1, e)])


@generate
def vt_inputs() -> Generator[Parser, list[AnyEvent], list[AnyEvent]]:
    commands = yield (escape_sequence | single_char).many()
    return commands
