from __future__ import annotations

from collections.abc import Generator, Mapping
from enum import Enum
from string import printable

from parsy import Parser, any_char, char_from, decimal_digit, generate, string
from structlog import get_logger

from counterweight.events import AnyEvent, KeyPressed, MouseDown, MouseMoved, MouseUp
from counterweight.geometry import Position

logger = get_logger()


class Key(str, Enum):
    """
    Derived from https://github.com/Textualize/textual/blob/c966243b059f0352e2a23b9695776838195364a3/src/textual/keys.py
    """

    Escape = "escape"  # Also Control-[
    ShiftEscape = "shift+escape"
    Return = "return"

    ControlAt = "ctrl+@"  # Also Control-Space.

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

    Control1 = "ctrl+1"
    Control2 = "ctrl+2"
    Control3 = "ctrl+3"
    Control4 = "ctrl+4"
    Control5 = "ctrl+5"
    Control6 = "ctrl+6"
    Control7 = "ctrl+7"
    Control8 = "ctrl+8"
    Control9 = "ctrl+9"
    Control0 = "ctrl+0"

    ControlShift1 = "ctrl+shift+1"
    ControlShift2 = "ctrl+shift+2"
    ControlShift3 = "ctrl+shift+3"
    ControlShift4 = "ctrl+shift+4"
    ControlShift5 = "ctrl+shift+5"
    ControlShift6 = "ctrl+shift+6"
    ControlShift7 = "ctrl+shift+7"
    ControlShift8 = "ctrl+shift+8"
    ControlShift9 = "ctrl+shift+9"
    ControlShift0 = "ctrl+shift+0"

    ControlBackslash = "ctrl+backslash"
    ControlSquareClose = "ctrl+right_square_bracket"
    ControlCircumflex = "ctrl+circumflex_accent"
    ControlUnderscore = "ctrl+underscore"

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

    # Matches any key.
    Any = "<any>"

    # Special.
    ScrollUp = "<scroll-up>"
    ScrollDown = "<scroll-down>"

    # For internal use: key which is ignored.
    # (The key binding for this key should not do anything.)
    Ignore = "<ignore>"

    # Some 'Key' aliases (for backward-compatibility).
    ControlSpace = "ctrl-at"
    Tab = "tab"
    Space = "space"
    Enter = "enter"
    Backspace = "backspace"

    def __repr__(self) -> str:
        return str(self)


SINGLE_CHAR_TRANSFORMS: Mapping[str, Key] = {
    "\x1b": Key.Escape,
    "\t": Key.Tab,
    "\n": Key.Enter,
    " ": Key.Space,
    "\x00": Key.ControlSpace,
    "\x01": Key.ControlA,
    "\x02": Key.ControlB,
    "\x03": Key.ControlC,
    "\x04": Key.ControlD,
    "\x05": Key.ControlE,
    "\x06": Key.ControlF,
    "\x07": Key.ControlG,
    "\x08": Key.Backspace,
    "\x0B": Key.ControlK,
    "\x0C": Key.ControlL,
    "\x0E": Key.ControlN,
    "\x0F": Key.ControlO,
    "\x10": Key.ControlP,
    "\x11": Key.ControlQ,
    "\x12": Key.ControlR,
    "\x13": Key.ControlS,
    "\x14": Key.ControlT,
    "\x15": Key.ControlU,
    "\x16": Key.ControlV,
    "\x17": Key.ControlW,
    "\x18": Key.ControlX,
    "\x19": Key.ControlY,
    "\x1A": Key.ControlZ,
    "\x7f": Key.Backspace,
}

CHARS = "".join((*printable, *SINGLE_CHAR_TRANSFORMS.keys()))


@generate
def single_char() -> Generator[Parser, str, AnyEvent]:
    c = yield char_from(CHARS)

    return KeyPressed(key=SINGLE_CHAR_TRANSFORMS.get(c, c))


@generate
def escape_sequence() -> Generator[Parser, AnyEvent, AnyEvent]:
    keys = yield string("\x1b") >> (
        f1to4 | (string("[") >> (mouse_position | mouse_button | shift_tab | two_params | zero_or_one_params))
    )

    return keys


F1TO4 = {
    "P": Key.F1,
    "Q": Key.F2,
    "R": Key.F3,
    "S": Key.F4,
}


@generate
def f1to4() -> Generator[Parser, str, AnyEvent]:
    yield string("O")
    final = yield char_from("PQRS")

    return KeyPressed(key=F1TO4[final])


@generate
def shift_tab() -> Generator[Parser, str, AnyEvent]:
    yield string("Z")

    return KeyPressed(key=Key.BackTab)


@generate
def mouse_position() -> Generator[Parser, str, AnyEvent]:
    # https://www.xfree86.org/current/ctlseqs.html
    yield string("MC")

    x_char = yield any_char
    y_char = yield any_char

    x = ord(x_char) - 33
    y = ord(y_char) - 33

    return MouseMoved(position=Position(x=x, y=y))


@generate
def mouse_button() -> Generator[Parser, str, AnyEvent]:
    # https://www.xfree86.org/current/ctlseqs.html
    yield string("M")

    buttons_char = yield any_char

    buttons = ord(buttons_char) - 32

    x_char = yield any_char
    y_char = yield any_char

    x = ord(x_char) - 33
    y = ord(y_char) - 33
    p = Position(x=x, y=y)

    # TODO: handle upper bits of buttons
    if buttons & 3 == 3:
        return MouseUp(position=p)
    elif buttons & 2 == 2:
        return MouseDown(position=p, button=3)
    elif buttons & 1 == 1:
        return MouseDown(position=p, button=2)
    else:  # low bits are 00, so this is mouse down with button 1
        return MouseDown(position=p, button=1)


CSI_LOOKUP: Mapping[tuple[str, ...], str] = {
    ("", "A"): Key.Up,
    ("", "B"): Key.Down,
    ("", "C"): Key.Right,
    ("", "D"): Key.Left,
    ("", "F"): Key.End,
    ("2", "~"): Key.Insert,
    ("3", "~"): Key.Delete,
    ("11", "~"): Key.F1,
    ("12", "~"): Key.F2,
    ("13", "~"): Key.F3,
    ("14", "~"): Key.F4,
    ("15", "~"): Key.F5,
    # skip 16
    ("17", "~"): Key.F6,
    ("18", "~"): Key.F7,
    ("19", "~"): Key.F8,
    ("20", "~"): Key.F9,
    ("21", "~"): Key.F10,
    # skip 22
    ("23", "~"): Key.F11,
    ("24", "~"): Key.F12,
    ("25", "~"): Key.F13,
    ("26", "~"): Key.F14,
    ("28", "~"): Key.F15,
    ("29", "~"): Key.F16,
    # skip 30
    ("31", "~"): Key.F17,
    ("32", "~"): Key.F18,
    ("33", "~"): Key.F19,
    ("34", "~"): Key.F20,
    ("1", "2", "A"): Key.ShiftUp,
    ("1", "2", "B"): Key.ShiftDown,
    ("1", "2", "C"): Key.ShiftRight,
    ("1", "2", "D"): Key.ShiftLeft,
    ("1", "5", "A"): Key.ControlUp,
    ("1", "5", "B"): Key.ControlDown,
    ("1", "5", "C"): Key.ControlRight,
    ("1", "5", "D"): Key.ControlLeft,
    ("1", "6", "A"): Key.ControlShiftUp,
    ("1", "6", "B"): Key.ControlShiftDown,
    ("1", "6", "C"): Key.ControlShiftRight,
    ("1", "6", "D"): Key.ControlShiftLeft,
    ("3", "3", "~"): Key.AltDelete,
    ("3", "5", "~"): Key.ControlDelete,
    ("3", "6", "~"): Key.ControlShiftInsert,
}

FINAL_CHARS = "".join(sorted(set(key[-1] for key in CSI_LOOKUP)))


@generate
def two_params() -> Generator[Parser, str, AnyEvent]:
    p1 = yield decimal_digit.many().concat()
    yield string(";")
    p2 = yield decimal_digit.many().concat()
    e = yield char_from(FINAL_CHARS)

    return KeyPressed(key=CSI_LOOKUP[(p1, p2, e)])


@generate
def zero_or_one_params() -> Generator[Parser, str, AnyEvent]:
    # zero params => ""
    p1 = yield decimal_digit.many().concat()

    e = yield char_from(FINAL_CHARS)

    return KeyPressed(key=CSI_LOOKUP[(p1, e)])


@generate
def vt_inputs() -> Generator[Parser, list[AnyEvent], list[AnyEvent]]:
    commands = yield (escape_sequence | single_char).many()
    return commands
