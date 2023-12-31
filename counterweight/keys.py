from __future__ import annotations

from collections.abc import Generator, Mapping
from enum import Enum
from string import printable

from parsy import Parser, char_from, generate, match_item
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
    b"\x0B": Key.ControlK,
    b"\x0C": Key.ControlL,
    b"\x0E": Key.ControlN,
    b"\x0F": Key.ControlO,
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
    b"\x1A": Key.ControlZ,
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
    keys = yield esc >> (f1to4 | (left_bracket >> (mouse | two_params | zero_or_one_params)))

    return keys


F1TO4 = {
    b"P": Key.F1,
    b"Q": Key.F2,
    b"R": Key.F3,
    b"S": Key.F4,
}

O_PQRS = match_item(b"O") >> char_from(b"PQRS")


@generate
def f1to4() -> Generator[Parser, bytes, AnyEvent]:
    final = yield O_PQRS

    return KeyPressed(key=F1TO4[final])


left_angle = match_item(b"<")
mM = char_from(b"mM")


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

    buttons = int(buttons_) % 32
    x = int(x_) - 1
    y = int(y_) - 1

    pos = Position(x=x, y=y)

    match (buttons & 0b10) == 0b10, (buttons & 0b01) == 0b01, m:
        case False, False, b"m":
            return MouseUp(position=pos, button=1)
        case False, True, b"m":
            return MouseUp(position=pos, button=2)
        case True, False, b"m":
            return MouseUp(position=pos, button=3)
        case True, True, b"m":
            # low bits are 11 (mouse release)
            # and last char is m (mouse up),
            # so this is just the mouse moving with no buttons pressed
            return MouseMoved(position=pos)
        case False, False, b"M":
            return MouseDown(position=pos, button=1)
        case False, True, b"M":
            return MouseDown(position=pos, button=2)
        case True, False, b"M":
            return MouseDown(position=pos, button=3)
        case _:  # pragma: unreachable
            raise Exception("unreachable")


CSI_LOOKUP: Mapping[tuple[bytes, ...], str] = {
    (b"", b"A"): Key.Up,
    (b"", b"B"): Key.Down,
    (b"", b"C"): Key.Right,
    (b"", b"D"): Key.Left,
    (b"", b"F"): Key.End,
    (b"", b"Z"): Key.BackTab,
    (b"2", b"~"): Key.Insert,
    (b"3", b"~"): Key.Delete,
    (b"11", b"~"): Key.F1,
    (b"12", b"~"): Key.F2,
    (b"13", b"~"): Key.F3,
    (b"14", b"~"): Key.F4,
    (b"15", b"~"): Key.F5,
    # skip 16
    (b"17", b"~"): Key.F6,
    (b"18", b"~"): Key.F7,
    (b"19", b"~"): Key.F8,
    (b"20", b"~"): Key.F9,
    (b"21", b"~"): Key.F10,
    # skip 22
    (b"23", b"~"): Key.F11,
    (b"24", b"~"): Key.F12,
    (b"25", b"~"): Key.F13,
    (b"26", b"~"): Key.F14,
    # skip 27
    (b"28", b"~"): Key.F15,
    (b"29", b"~"): Key.F16,
    # skip 30
    (b"31", b"~"): Key.F17,
    (b"32", b"~"): Key.F18,
    (b"33", b"~"): Key.F19,
    (b"34", b"~"): Key.F20,
    (b"1", b"2", b"A"): Key.ShiftUp,
    (b"1", b"2", b"B"): Key.ShiftDown,
    (b"1", b"2", b"C"): Key.ShiftRight,
    (b"1", b"2", b"D"): Key.ShiftLeft,
    (b"1", b"5", b"A"): Key.ControlUp,
    (b"1", b"5", b"B"): Key.ControlDown,
    (b"1", b"5", b"C"): Key.ControlRight,
    (b"1", b"5", b"D"): Key.ControlLeft,
    (b"1", b"6", b"A"): Key.ControlShiftUp,
    (b"1", b"6", b"B"): Key.ControlShiftDown,
    (b"1", b"6", b"C"): Key.ControlShiftRight,
    (b"1", b"6", b"D"): Key.ControlShiftLeft,
    (b"3", b"3", b"~"): Key.AltDelete,
    (b"3", b"5", b"~"): Key.ControlDelete,
    (b"3", b"6", b"~"): Key.ControlShiftInsert,
}

FINAL_CHARS = b"".join(sorted(set(key[-1] for key in CSI_LOOKUP)))
final_char = char_from(FINAL_CHARS)

semicolon = match_item(b";")


@generate
def two_params() -> Generator[Parser, bytes, AnyEvent]:
    p1 = yield decimal_digits
    yield semicolon
    p2 = yield decimal_digits
    e = yield final_char

    return KeyPressed(key=CSI_LOOKUP[(p1, p2, e)])


@generate
def zero_or_one_params() -> Generator[Parser, bytes, AnyEvent]:
    # zero params => ""
    p1 = yield decimal_digits
    e = yield final_char

    return KeyPressed(key=CSI_LOOKUP[(p1, e)])


@generate
def vt_inputs() -> Generator[Parser, list[AnyEvent], list[AnyEvent]]:
    commands = yield (escape_sequence | single_char).many()
    return commands
