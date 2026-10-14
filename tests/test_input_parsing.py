from dataclasses import dataclass

import pytest
from hypothesis import given
from hypothesis import strategies as st

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
    Pasted,
)
from counterweight.geometry import Position
from counterweight.input_parsing import PASTE_START, parse_input
from counterweight.keys import Key


@dataclass(frozen=True, slots=True)
class Parsed:
    """What `parse_input` found in a buffer, with the bytes it held back rather than where it stopped."""

    events: tuple[AnyEvent, ...]
    skipped: tuple[bytes, ...]
    remainder: bytes


def parse(buffer: bytes, *, is_final: bool) -> Parsed:
    parsed = parse_input(buffer, is_final=is_final)
    return Parsed(events=parsed.events, skipped=parsed.skipped, remainder=buffer[parsed.end :])


@pytest.mark.parametrize(
    "buffer, expected",
    [
        # single characters, raw
        (b"f", [KeyPressed(key="f")]),
        (b"foo", [KeyPressed(key="f"), KeyPressed(key="o"), KeyPressed(key="o")]),
        # single bytes, transformed
        (b"\x1b", [KeyPressed(key=Key.Escape)]),
        (b"\t", [KeyPressed(key=Key.Tab)]),
        (b"\n", [KeyPressed(key=Key.ControlJ)]),
        (b" ", [KeyPressed(key=Key.Space)]),
        (b"\x00", [KeyPressed(key=Key.ControlSpace)]),
        (b"\x01", [KeyPressed(key=Key.ControlA)]),
        (b"\x02", [KeyPressed(key=Key.ControlB)]),
        (b"\x03", [KeyPressed(key=Key.ControlC)]),
        (b"\x04", [KeyPressed(key=Key.ControlD)]),
        (b"\x05", [KeyPressed(key=Key.ControlE)]),
        (b"\x06", [KeyPressed(key=Key.ControlF)]),
        (b"\x07", [KeyPressed(key=Key.ControlG)]),
        (b"\x08", [KeyPressed(key=Key.Backspace)]),
        (b"\x0b", [KeyPressed(key=Key.ControlK)]),
        (b"\x0c", [KeyPressed(key=Key.ControlL)]),
        (b"\x0e", [KeyPressed(key=Key.ControlN)]),
        (b"\x0f", [KeyPressed(key=Key.ControlO)]),
        (b"\x10", [KeyPressed(key=Key.ControlP)]),
        (b"\x11", [KeyPressed(key=Key.ControlQ)]),
        (b"\x12", [KeyPressed(key=Key.ControlR)]),
        (b"\x13", [KeyPressed(key=Key.ControlS)]),
        (b"\x14", [KeyPressed(key=Key.ControlT)]),
        (b"\x15", [KeyPressed(key=Key.ControlU)]),
        (b"\x16", [KeyPressed(key=Key.ControlV)]),
        (b"\x17", [KeyPressed(key=Key.ControlW)]),
        (b"\x18", [KeyPressed(key=Key.ControlX)]),
        (b"\x19", [KeyPressed(key=Key.ControlY)]),
        (b"\x1a", [KeyPressed(key=Key.ControlZ)]),
        (b"\x7f", [KeyPressed(key=Key.Backspace)]),
        (b"\r", [KeyPressed(key=Key.Enter)]),
        # text beyond ASCII, one event per grapheme cluster
        ("aé".encode(), [KeyPressed(key="a"), KeyPressed(key="é")]),
        ("日本".encode(), [KeyPressed(key="日"), KeyPressed(key="本")]),
        ("e\u0301".encode(), [KeyPressed(key="e\u0301")]),
        ("👩‍💻!".encode(), [KeyPressed(key="👩‍💻"), KeyPressed(key="!")]),
        # an ESC that doesn't begin a sequence is Alt with the key that follows it
        (b"\x1bb", [KeyPressed(key="alt+b")]),
        (b"\x1bB", [KeyPressed(key="alt+B")]),
        (b"\x1bbc", [KeyPressed(key="alt+b"), KeyPressed(key="c")]),
        ("\x1bé".encode(), [KeyPressed(key="alt+é")]),
        ("\x1b👩‍💻!".encode(), [KeyPressed(key="alt+👩‍💻"), KeyPressed(key="!")]),
        (b"\x1b ", [KeyPressed(key=Key.AltSpace)]),
        (b"\x1b\r", [KeyPressed(key=Key.AltEnter)]),
        (b"\x1b\x7f", [KeyPressed(key=Key.AltBackspace)]),
        (b"\x1b\x08", [KeyPressed(key=Key.AltBackspace)]),
        (b"\x1b\t", [KeyPressed(key=Key.AltTab)]),
        (b"\x1b\n", [KeyPressed(key=Key.ControlAltJ)]),
        (b"\x1b\x00", [KeyPressed(key=Key.ControlAltSpace)]),
        (b"\x1b\x01", [KeyPressed(key=Key.ControlAltA)]),
        (b"\x1b\x1a", [KeyPressed(key=Key.ControlAltZ)]),
        # or with the key whose escape sequence follows it, as rxvt sends Alt with those keys
        (b"\x1b\x1b[A", [KeyPressed(key=Key.AltUp)]),
        (b"\x1b\x1b[5~", [KeyPressed(key=Key.AltPageUp)]),
        (b"\x1b\x1bOP", [KeyPressed(key=Key.AltF1)]),
        # an ESC followed by anything else is the Escape key
        (b"\x1b\x1b", [KeyPressed(key=Key.Escape), KeyPressed(key=Key.Escape)]),
        (b"\x1b\x1bb", [KeyPressed(key=Key.Escape), KeyPressed(key="alt+b")]),
        (b"\x1b\x1b[1;3A", [KeyPressed(key=Key.Escape), KeyPressed(key=Key.AltUp)]),
        (b"\x1b\x1b[25~", [KeyPressed(key=Key.Escape), KeyPressed(key=Key.F13)]),
        (b"\x1b\x1b[<0;1;1M", [KeyPressed(key=Key.Escape), MouseDown(absolute=Position(x=0, y=0), button=1)]),
        (b"\x1b\x1b[200~a\x1b[201~", [KeyPressed(key=Key.Escape), Pasted(text="a")]),
        # f1 to f4
        (b"\x1bOP", [KeyPressed(key=Key.F1)]),
        (b"\x1bOQ", [KeyPressed(key=Key.F2)]),
        (b"\x1bOR", [KeyPressed(key=Key.F3)]),
        (b"\x1bOS", [KeyPressed(key=Key.F4)]),
        # shift-tab
        (b"\x1b[Z", [KeyPressed(key=Key.BackTab)]),
        # CSI lookups
        (b"\x1b[A", [KeyPressed(key=Key.Up)]),
        (b"\x1b[B", [KeyPressed(key=Key.Down)]),
        (b"\x1b[C", [KeyPressed(key=Key.Right)]),
        (b"\x1b[D", [KeyPressed(key=Key.Left)]),
        (b"\x1b[2~", [KeyPressed(key=Key.Insert)]),
        (b"\x1b[3~", [KeyPressed(key=Key.Delete)]),
        (b"\x1b[F", [KeyPressed(key=Key.End)]),
        (b"\x1b[11~", [KeyPressed(key=Key.F1)]),
        (b"\x1b[12~", [KeyPressed(key=Key.F2)]),
        (b"\x1b[13~", [KeyPressed(key=Key.F3)]),
        (b"\x1b[14~", [KeyPressed(key=Key.F4)]),
        (b"\x1b[17~", [KeyPressed(key=Key.F6)]),
        (b"\x1b[18~", [KeyPressed(key=Key.F7)]),
        (b"\x1b[19~", [KeyPressed(key=Key.F8)]),
        (b"\x1b[20~", [KeyPressed(key=Key.F9)]),
        (b"\x1b[21~", [KeyPressed(key=Key.F10)]),
        (b"\x1b[23~", [KeyPressed(key=Key.F11)]),
        (b"\x1b[24~", [KeyPressed(key=Key.F12)]),
        (b"\x1b[25~", [KeyPressed(key=Key.F13)]),
        (b"\x1b[26~", [KeyPressed(key=Key.F14)]),
        (b"\x1b[28~", [KeyPressed(key=Key.F15)]),
        (b"\x1b[29~", [KeyPressed(key=Key.F16)]),
        (b"\x1b[31~", [KeyPressed(key=Key.F17)]),
        (b"\x1b[32~", [KeyPressed(key=Key.F18)]),
        (b"\x1b[33~", [KeyPressed(key=Key.F19)]),
        (b"\x1b[34~", [KeyPressed(key=Key.F20)]),
        (b"\x1b[1;2A", [KeyPressed(key=Key.ShiftUp)]),
        (b"\x1b[1;2B", [KeyPressed(key=Key.ShiftDown)]),
        (b"\x1b[1;2C", [KeyPressed(key=Key.ShiftRight)]),
        (b"\x1b[1;2D", [KeyPressed(key=Key.ShiftLeft)]),
        (b"\x1b[1;5A", [KeyPressed(key=Key.ControlUp)]),
        (b"\x1b[1;5B", [KeyPressed(key=Key.ControlDown)]),
        (b"\x1b[1;5C", [KeyPressed(key=Key.ControlRight)]),
        (b"\x1b[1;5D", [KeyPressed(key=Key.ControlLeft)]),
        (b"\x1b[1;6A", [KeyPressed(key=Key.ControlShiftUp)]),
        (b"\x1b[1;6B", [KeyPressed(key=Key.ControlShiftDown)]),
        (b"\x1b[1;6C", [KeyPressed(key=Key.ControlShiftRight)]),
        (b"\x1b[1;6D", [KeyPressed(key=Key.ControlShiftLeft)]),
        (b"\x1b[1;3A", [KeyPressed(key=Key.AltUp)]),
        (b"\x1b[1;3B", [KeyPressed(key=Key.AltDown)]),
        (b"\x1b[1;3C", [KeyPressed(key=Key.AltRight)]),
        (b"\x1b[1;3D", [KeyPressed(key=Key.AltLeft)]),
        (b"\x1b[1;3H", [KeyPressed(key=Key.AltHome)]),
        (b"\x1b[1;3F", [KeyPressed(key=Key.AltEnd)]),
        (b"\x1b[2;3~", [KeyPressed(key=Key.AltInsert)]),
        (b"\x1b[3;3~", [KeyPressed(key=Key.AltDelete)]),
        (b"\x1b[5;3~", [KeyPressed(key=Key.AltPageUp)]),
        (b"\x1b[6;3~", [KeyPressed(key=Key.AltPageDown)]),
        (b"\x1b[3;5~", [KeyPressed(key=Key.ControlDelete)]),
        (b"\x1b[3;6~", [KeyPressed(key=Key.ControlShiftDelete)]),
        (b"\x1b[2;6~", [KeyPressed(key=Key.ControlShiftInsert)]),
        (b"\x1b[H", [KeyPressed(key=Key.Home)]),
        (b"\x1b[1~", [KeyPressed(key=Key.Home)]),
        (b"\x1b[7~", [KeyPressed(key=Key.Home)]),
        (b"\x1bOH", [KeyPressed(key=Key.Home)]),
        (b"\x1b[4~", [KeyPressed(key=Key.End)]),
        (b"\x1b[8~", [KeyPressed(key=Key.End)]),
        (b"\x1bOF", [KeyPressed(key=Key.End)]),
        (b"\x1b[5~", [KeyPressed(key=Key.PageUp)]),
        (b"\x1b[6~", [KeyPressed(key=Key.PageDown)]),
        (b"\x1bOA", [KeyPressed(key=Key.Up)]),
        (b"\x1bOD", [KeyPressed(key=Key.Left)]),
        (b"\x1b[1;2H", [KeyPressed(key=Key.ShiftHome)]),
        (b"\x1b[1;5F", [KeyPressed(key=Key.ControlEnd)]),
        (b"\x1b[1;6H", [KeyPressed(key=Key.ControlShiftHome)]),
        (b"\x1b[2;2~", [KeyPressed(key=Key.ShiftInsert)]),
        (b"\x1b[3;2~", [KeyPressed(key=Key.ShiftDelete)]),
        (b"\x1b[5;2~", [KeyPressed(key=Key.ShiftPageUp)]),
        (b"\x1b[6;5~", [KeyPressed(key=Key.ControlPageDown)]),
        (b"\x1b[5;6~", [KeyPressed(key=Key.ControlShiftPageUp)]),
        # xterm reports Shift with F1 through F12 as F13 through F24
        (b"\x1b[1;2P", [KeyPressed(key=Key.F13)]),
        (b"\x1b[24;2~", [KeyPressed(key=Key.F24)]),
        (b"\x1b[1;5S", [KeyPressed(key=Key.ControlF4)]),
        (b"\x1b[15;5~", [KeyPressed(key=Key.ControlF5)]),
        (b"\x1b[1;6Q", [KeyPressed(key=Key.ControlF14)]),
        (b"\x1b[24;6~", [KeyPressed(key=Key.ControlF24)]),
        (b"\x1b[1;3P", [KeyPressed(key=Key.AltF1)]),
        (b"\x1b[15;3~", [KeyPressed(key=Key.AltF5)]),
        (b"\x1b[24;3~", [KeyPressed(key=Key.AltF12)]),
        # Mouse events
        (b"\x1b[<35;1;1m", [MouseMoved(absolute=Position(x=0, y=0), button=None)]),
        (b"\x1b[<35;2;1m", [MouseMoved(absolute=Position(x=1, y=0), button=None)]),
        (b"\x1b[<32;2;1m", [MouseMoved(absolute=Position(x=1, y=0), button=1)]),
        (b"\x1b[<33;2;1m", [MouseMoved(absolute=Position(x=1, y=0), button=2)]),
        (b"\x1b[<34;2;1m", [MouseMoved(absolute=Position(x=1, y=0), button=3)]),
        (b"\x1b[<35;1;2m", [MouseMoved(absolute=Position(x=0, y=1), button=None)]),
        (b"\x1b[<35;2;2m", [MouseMoved(absolute=Position(x=1, y=1), button=None)]),
        (b"\x1b[<35;95;1m", [MouseMoved(absolute=Position(x=94, y=0), button=None)]),
        (b"\x1b[<35;1;95m", [MouseMoved(absolute=Position(x=0, y=94), button=None)]),
        (b"\x1b[<35;95;95m", [MouseMoved(absolute=Position(x=94, y=94), button=None)]),
        (b"\x1b[<35;500;500m", [MouseMoved(absolute=Position(x=499, y=499), button=None)]),
        (b"\x1b[<35;1000;1000m", [MouseMoved(absolute=Position(x=999, y=999), button=None)]),
        (b"\x1b[<0;1;1M", [MouseDown(absolute=Position(x=0, y=0), button=1)]),
        (b"\x1b[<0;1;1m", [MouseUp(absolute=Position(x=0, y=0), button=1)]),
        (b"\x1b[<1;1;1M", [MouseDown(absolute=Position(x=0, y=0), button=2)]),
        (b"\x1b[<1;1;1m", [MouseUp(absolute=Position(x=0, y=0), button=2)]),
        (b"\x1b[<2;1;1M", [MouseDown(absolute=Position(x=0, y=0), button=3)]),
        (b"\x1b[<2;1;1m", [MouseUp(absolute=Position(x=0, y=0), button=3)]),
        # It seems like some systems will use an M even in the mouse up state for motion...
        (b"\x1b[<35;2;1M", [MouseMoved(absolute=Position(x=1, y=0), button=None)]),
        (b"\x1b[<32;2;1M", [MouseMoved(absolute=Position(x=1, y=0), button=1)]),
        (b"\x1b[<33;2;1M", [MouseMoved(absolute=Position(x=1, y=0), button=2)]),
        (b"\x1b[<34;2;1M", [MouseMoved(absolute=Position(x=1, y=0), button=3)]),
        (b"\x1b[<64;2;1M", [MouseScrolledUp(absolute=Position(x=1, y=0))]),
        (b"\x1b[<65;2;1M", [MouseScrolledDown(absolute=Position(x=1, y=0))]),
        (b"\x1b[<66;2;1M", [MouseScrolledLeft(absolute=Position(x=1, y=0))]),
        (b"\x1b[<67;2;1M", [MouseScrolledRight(absolute=Position(x=1, y=0))]),
        # Shift (4), Meta (8, which terminals send for Alt), and Control (16) are modifiers on the event the rest is
        (b"\x1b[<68;2;1M", [MouseScrolledUp(absolute=Position(x=1, y=0), is_shift_held=True)]),
        (b"\x1b[<69;2;1M", [MouseScrolledDown(absolute=Position(x=1, y=0), is_shift_held=True)]),
        (b"\x1b[<73;2;1M", [MouseScrolledDown(absolute=Position(x=1, y=0), is_alt_held=True)]),
        (b"\x1b[<82;2;1M", [MouseScrolledLeft(absolute=Position(x=1, y=0), is_control_held=True)]),
        (b"\x1b[<71;2;1M", [MouseScrolledRight(absolute=Position(x=1, y=0), is_shift_held=True)]),
        (b"\x1b[<4;3;4M", [MouseDown(absolute=Position(x=2, y=3), button=1, is_shift_held=True)]),
        (b"\x1b[<8;3;4M", [MouseDown(absolute=Position(x=2, y=3), button=1, is_alt_held=True)]),
        (b"\x1b[<16;3;4M", [MouseDown(absolute=Position(x=2, y=3), button=1, is_control_held=True)]),
        (
            b"\x1b[<28;3;4M",
            [
                MouseDown(
                    absolute=Position(x=2, y=3), button=1, is_shift_held=True, is_alt_held=True, is_control_held=True
                )
            ],
        ),
        (b"\x1b[<21;3;4m", [MouseUp(absolute=Position(x=2, y=3), button=2, is_shift_held=True, is_control_held=True)]),
        (b"\x1b[<44;3;4M", [MouseMoved(absolute=Position(x=2, y=3), button=1, is_shift_held=True, is_alt_held=True)]),
        (b"\x1b[<39;3;4M", [MouseMoved(absolute=Position(x=2, y=3), button=None, is_shift_held=True)]),
        (b"\x1b[<136;3;4M", [MouseDown(absolute=Position(x=2, y=3), button=8, is_alt_held=True)]),
        # Buttons 8 through 11
        (b"\x1b[<128;3;4M", [MouseDown(absolute=Position(x=2, y=3), button=8)]),
        (b"\x1b[<129;3;4m", [MouseUp(absolute=Position(x=2, y=3), button=9)]),
        (b"\x1b[<160;3;4M", [MouseMoved(absolute=Position(x=2, y=3), button=8)]),
    ],
)
def test_known_input_parses_to_its_events(buffer: bytes, expected: list[AnyEvent]) -> None:
    assert parse(buffer, is_final=True) == Parsed(events=tuple(expected), skipped=(), remainder=b"")


@pytest.mark.parametrize(
    "buffer, expected",
    [
        (b"\x1b[200~hello\x1b[201~", [Pasted(text="hello")]),
        (b"\x1b[200~\x1b[201~", [Pasted(text="")]),
        ("\x1b[200~é👩‍💻\x1b[201~".encode(), [Pasted(text="é👩‍💻")]),
        # what would be keys or sequences outside a paste are text inside one
        (b"\x1b[200~a\tb\x03\x1b[Ac\x1b[200~\x1b[201~", [Pasted(text="a\tb\x03\x1b[Ac\x1b[200~")]),
        # terminals send pasted line breaks as carriage returns
        (b"\x1b[200~a\rb\r\nc\nd\x1b[201~", [Pasted(text="a\nb\nc\nd")]),
        (
            b"x\x1b[200~y\x1b[201~z",
            [KeyPressed(key="x"), Pasted(text="y"), KeyPressed(key="z")],
        ),
        (
            b"\x1b[200~a\x1b[201~\x1b[200~b\x1b[201~",
            [Pasted(text="a"), Pasted(text="b")],
        ),
    ],
)
def test_bracketed_paste_parses_to_one_event_holding_its_text(buffer: bytes, expected: list[AnyEvent]) -> None:
    assert parse(buffer, is_final=False) == Parsed(events=tuple(expected), skipped=(), remainder=b"")


def test_a_held_paste_is_searched_for_its_end_only_past_what_was_searched_before() -> None:
    buffer = b"\x1b[200~a\x1b[201~"

    assert parse_input(buffer, is_final=False, paste_searched=len(buffer) + len(PASTE_START)).end == 0


def test_bytes_in_a_paste_that_are_not_utf8_are_skipped() -> None:
    assert parse(b"\x1b[200~a\xffb\x1b[201~", is_final=True) == Parsed(
        events=(Pasted(text="ab"),), skipped=(b"\xff",), remainder=b""
    )


@pytest.mark.parametrize(
    "buffer, expected",
    [
        # well-formed CSI and SS3 sequences we don't know the meaning of
        (b"\x1b[1;5p", Parsed(events=(), skipped=(b"\x1b[1;5p",), remainder=b"")),
        (b"\x1b[5^", Parsed(events=(), skipped=(b"\x1b[5^",), remainder=b"")),
        (b"\x1b[a", Parsed(events=(), skipped=(b"\x1b[a",), remainder=b"")),
        (b"\x1b[I", Parsed(events=(), skipped=(b"\x1b[I",), remainder=b"")),
        (b"\x1b[201~", Parsed(events=(), skipped=(b"\x1b[201~",), remainder=b"")),
        (b"\x1b[1 q", Parsed(events=(), skipped=(b"\x1b[1 q",), remainder=b"")),
        (b"\x1bOx", Parsed(events=(), skipped=(b"\x1bOx",), remainder=b"")),
        (b"\x1b[<35;1M", Parsed(events=(), skipped=(b"\x1b[<35;1M",), remainder=b"")),
        (
            b"a\x1b[1;5pb",
            Parsed(events=(KeyPressed(key="a"), KeyPressed(key="b")), skipped=(b"\x1b[1;5p",), remainder=b""),
        ),
        # a sequence cut short by a byte that can't be in one is skipped up to that byte
        (
            b"\x1b[1;\x03",
            Parsed(events=(KeyPressed(key=Key.ControlC),), skipped=(b"\x1b[1;",), remainder=b""),
        ),
        (
            "\x1b[1;é".encode(),
            Parsed(events=(KeyPressed(key="é"),), skipped=(b"\x1b[1;",), remainder=b""),
        ),
        # control bytes with no key
        (b"\x1c", Parsed(events=(), skipped=(b"\x1c",), remainder=b"")),
        # Alt with a control byte with no key, or with a key with no name with Alt
        (b"\x1b\x1c", Parsed(events=(), skipped=(b"\x1b\x1c",), remainder=b"")),
        (b"\x1b[25;3~", Parsed(events=(), skipped=(b"\x1b[25;3~",), remainder=b"")),
        # an ESC before input that is skipped is the Escape key
        (
            b"\x1b\xffa",
            Parsed(events=(KeyPressed(key=Key.Escape), KeyPressed(key="a")), skipped=(b"\xff",), remainder=b""),
        ),
        (
            b"\x1b\x1b[1;5p",
            Parsed(events=(KeyPressed(key=Key.Escape),), skipped=(b"\x1b[1;5p",), remainder=b""),
        ),
        (
            b"\x1b\x1b[1;\x03",
            Parsed(
                events=(KeyPressed(key=Key.Escape), KeyPressed(key=Key.ControlC)), skipped=(b"\x1b[1;",), remainder=b""
            ),
        ),
        # bytes that aren't UTF-8 are skipped, and everything around them kept
        (
            b"a\xffb",
            Parsed(events=(KeyPressed(key="a"), KeyPressed(key="b")), skipped=(b"\xff",), remainder=b""),
        ),
        (
            b"a\xc3\x1b[A",
            Parsed(events=(KeyPressed(key="a"), KeyPressed(key=Key.Up)), skipped=(b"\xc3",), remainder=b""),
        ),
        (
            b"\xff\xcc\x81",
            Parsed(events=(KeyPressed(key="\u0301"),), skipped=(b"\xff",), remainder=b""),
        ),
    ],
)
def test_input_that_is_not_an_event_is_skipped(buffer: bytes, expected: Parsed) -> None:
    assert parse(buffer, is_final=True) == expected


@pytest.mark.parametrize(
    "buffer, expected",
    [
        (b"\x1b", Parsed(events=(), skipped=(), remainder=b"\x1b")),
        (b"a\x1b", Parsed(events=(KeyPressed(key="a"),), skipped=(), remainder=b"\x1b")),
        (b"\x1b[", Parsed(events=(), skipped=(), remainder=b"\x1b[")),
        (b"\x1b[<35;1", Parsed(events=(), skipped=(), remainder=b"\x1b[<35;1")),
        (b"\x1bO", Parsed(events=(), skipped=(), remainder=b"\x1bO")),
        (b"\x1b\x1b", Parsed(events=(), skipped=(), remainder=b"\x1b\x1b")),
        (b"\x1b\x1b[1;3", Parsed(events=(), skipped=(), remainder=b"\x1b\x1b[1;3")),
        (b"\x1b\xc3", Parsed(events=(), skipped=(), remainder=b"\x1b\xc3")),
        (b"a\xc3", Parsed(events=(KeyPressed(key="a"),), skipped=(), remainder=b"\xc3")),
        (b"\xf0\x9f\x98", Parsed(events=(), skipped=(), remainder=b"\xf0\x9f\x98")),
        (b"\x1b[200~ab", Parsed(events=(), skipped=(), remainder=b"\x1b[200~ab")),
        (b"\x1b[200~ab\x1b[20", Parsed(events=(), skipped=(), remainder=b"\x1b[200~ab\x1b[20")),
        (
            b"a\x1b[200~b\x1b[201~\x1b[200~c",
            Parsed(events=(KeyPressed(key="a"), Pasted(text="b")), skipped=(), remainder=b"\x1b[200~c"),
        ),
    ],
)
def test_input_that_may_continue_is_held_over_until_final(buffer: bytes, expected: Parsed) -> None:
    assert parse(buffer, is_final=False) == expected


@pytest.mark.parametrize(
    "buffer, expected",
    [
        (b"\x1b", Parsed(events=(KeyPressed(key=Key.Escape),), skipped=(), remainder=b"")),
        # Alt+[ and Alt+O begin escape sequences, so they're Alt with those keys only if nothing follows
        (b"\x1b[", Parsed(events=(KeyPressed(key="alt+["),), skipped=(), remainder=b"")),
        (b"\x1bO", Parsed(events=(KeyPressed(key="alt+O"),), skipped=(), remainder=b"")),
        (
            b"\x1b[1;",
            Parsed(
                events=(KeyPressed(key="alt+["), KeyPressed(key="1"), KeyPressed(key=";")), skipped=(), remainder=b""
            ),
        ),
        (
            b"\x1b\x1b[",
            Parsed(events=(KeyPressed(key=Key.Escape), KeyPressed(key="alt+[")), skipped=(), remainder=b""),
        ),
        (
            b"\x1b\x1b",
            Parsed(events=(KeyPressed(key=Key.Escape), KeyPressed(key=Key.Escape)), skipped=(), remainder=b""),
        ),
        (b"\x1b\xc3", Parsed(events=(KeyPressed(key=Key.Escape),), skipped=(b"\xc3",), remainder=b"")),
        (b"a\xc3", Parsed(events=(KeyPressed(key="a"),), skipped=(b"\xc3",), remainder=b"")),
        (b"\x1b[200~ab", Parsed(events=(Pasted(text="ab"),), skipped=(), remainder=b"")),
        (b"\x1b[200~", Parsed(events=(Pasted(text=""),), skipped=(), remainder=b"")),
    ],
)
def test_final_input_is_not_held_over(buffer: bytes, expected: Parsed) -> None:
    assert parse(buffer, is_final=True) == expected


def parse_reads(reads: list[bytes]) -> Parsed:
    """
    Parse `reads` one after another, the way the input reader does,
    holding what each parse stopped short of, and how much of a held paste it searched, for the next read.
    """
    events: list[AnyEvent] = []
    skipped: list[bytes] = []
    held = bytearray()
    paste_searched: int | None = None
    for index, read in enumerate(reads):
        held += read
        parsed = parse_input(held, is_final=index == len(reads) - 1, paste_searched=paste_searched)
        events.extend(parsed.events)
        skipped.extend(parsed.skipped)
        del held[: parsed.end]
        paste_searched = parsed.paste_searched
    return Parsed(events=tuple(events), skipped=(b"".join(skipped),), remainder=bytes(held))


SPLIT_CORPUS = b"".join(
    [
        b"\x1b[<35;12;4M",
        "aé日😀".encode(),
        b"\x1b[1;5p",
        b"\x1bOP",
        b"\x1b",
        b"\x1b[3;5~",
        b"\x1bb",
        b"\x1b\r",
        b"\x1b\x1b[A",
        "\x1bé".encode(),
        b"\xff",
        b"\x03",
        b"\x1b[200~p\x1b[A\r\n\x1b[201~",
    ]
)


@pytest.mark.parametrize("offset", range(1, len(SPLIT_CORPUS)))
def test_input_split_across_reads_parses_the_same_as_one_read(offset: int) -> None:
    assert parse_reads([SPLIT_CORPUS[:offset], SPLIT_CORPUS[offset:]]) == parse_reads([SPLIT_CORPUS])


def test_an_escape_held_at_the_end_of_a_read_is_alt_with_the_key_the_next_read_starts_with() -> None:
    assert parse_reads([b"\x1b", b"bc"]).events == (KeyPressed(key="alt+b"), KeyPressed(key="c"))


def test_grapheme_cluster_split_across_reads_is_two_key_presses() -> None:
    assert parse_reads([b"e", "\u0301".encode()]).events == (KeyPressed(key="e"), KeyPressed(key="\u0301"))


@given(st.binary())
def test_final_parse_of_any_bytes_holds_nothing_over(buffer: bytes) -> None:
    assert parse(buffer, is_final=True).remainder == b""


TOKENS = st.one_of(
    st.sampled_from(
        [
            b"\x1b",
            b"\x1b[",
            b"\x1b[A",
            b"\x1b[1;5p",
            b"\x1bOP",
            b"\x1b[<0;3;7m",
            b"\x1b[<64;1;1M",
            b"\x03",
            b"\x1c",
            b"\xc3",
            b"\xff",
            b";",
            b"~",
            b"\x1b[200~",
            b"\x1b[201~",
            b"\r",
            b"\x7f",
        ]
    ),
    st.text().map(str.encode),
)


@given(st.lists(TOKENS).map(b"".join))
def test_paste_searched_counts_the_held_bytes_only_when_they_are_a_paste(buffer: bytes) -> None:
    parsed = parse_input(buffer, is_final=False)
    held = buffer[parsed.end :]

    assert parsed.paste_searched == (len(held) if held.startswith(PASTE_START) else None)


def join_text(parsed: Parsed) -> tuple[object, ...]:
    """The events in `parsed`, with each run of text joined into one string, since reads may split a grapheme cluster."""
    joined: list[object] = []
    for event in parsed.events:
        if not isinstance(event, KeyPressed) or isinstance(event.key, Key):
            joined.append(event)
        elif joined and isinstance(previous := joined[-1], str):
            joined[-1] = previous + event.key
        else:
            joined.append(event.key)
    return (*joined, parsed.skipped, parsed.remainder)


@given(st.lists(TOKENS).map(b"".join), st.lists(st.integers(min_value=0)))
def test_input_split_anywhere_parses_to_the_same_text_and_events(buffer: bytes, offsets: list[int]) -> None:
    cuts = sorted({offset % (len(buffer) + 1) for offset in offsets})
    reads = [buffer[start:end] for start, end in zip([0, *cuts], [*cuts, len(buffer)], strict=True)]

    assert join_text(parse_reads(reads)) == join_text(parse_reads([buffer]))


def test_key_repr_is_its_qualified_name() -> None:
    assert repr(Key.Up) == "Key.Up"
