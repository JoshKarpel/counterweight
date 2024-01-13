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
    End = "end"
    Insert = "insert"
    Delete = "delete"

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

    ControlSpace = "ctrl-space"
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

    button_info = int(buttons_)
    x = int(x_) - 1
    y = int(y_) - 1

    pos = Position.flyweight(x=x, y=y)
    moving = button_info & 32
    button = (button_info & 0b11) + 1

    if moving:
        return MouseMoved(position=pos, button=button if button != 4 else None)  # raw 3 is released, becomes 4 above
    elif m == b"m":
        return MouseUp(position=pos, button=button)
    else:  # m == b"M"
        return MouseDown(position=pos, button=button)


CSI_LOOKUP: Mapping[tuple[bytes, ...], str] = {
    # 0 params
    (b"", b"A"): Key.Up,
    (b"", b"B"): Key.Down,
    (b"", b"C"): Key.Right,
    (b"", b"D"): Key.Left,
    (b"", b"F"): Key.End,
    (b"", b"Z"): Key.BackTab,
    # 1 param
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
    # 2 params
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
