import pytest

from counterweight.events import AnyEvent, KeyPressed, MouseDownRaw, MouseMovedRaw, MouseUpRaw
from counterweight.geometry import Position
from counterweight.keys import Key, vt_inputs


@pytest.mark.parametrize(
    "buffer, expected",
    [
        # single characters, raw
        (b"f", [KeyPressed(key="f")]),
        (b"foo", [KeyPressed(key="f"), KeyPressed(key="o"), KeyPressed(key="o")]),
        # single bytes, transformed
        (b"\x1b", [KeyPressed(key=Key.Escape)]),
        (b"\t", [KeyPressed(key=Key.Tab)]),
        (b"\n", [KeyPressed(key=Key.Enter)]),
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
        (b"\x0B", [KeyPressed(key=Key.ControlK)]),
        (b"\x0C", [KeyPressed(key=Key.ControlL)]),
        (b"\x0E", [KeyPressed(key=Key.ControlN)]),
        (b"\x0F", [KeyPressed(key=Key.ControlO)]),
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
        (b"\x1A", [KeyPressed(key=Key.ControlZ)]),
        (b"\x7f", [KeyPressed(key=Key.Backspace)]),
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
        (b"\x1b[3;3~", [KeyPressed(key=Key.AltDelete)]),
        (b"\x1b[3;5~", [KeyPressed(key=Key.ControlDelete)]),
        (b"\x1b[3;6~", [KeyPressed(key=Key.ControlShiftInsert)]),
        # Mouse events
        (b"\x1b[<35;1;1m", [MouseMovedRaw(position=Position(x=0, y=0), button=None)]),
        (b"\x1b[<35;2;1m", [MouseMovedRaw(position=Position(x=1, y=0), button=None)]),
        (b"\x1b[<32;2;1m", [MouseMovedRaw(position=Position(x=1, y=0), button=1)]),
        (b"\x1b[<33;2;1m", [MouseMovedRaw(position=Position(x=1, y=0), button=2)]),
        (b"\x1b[<34;2;1m", [MouseMovedRaw(position=Position(x=1, y=0), button=3)]),
        (b"\x1b[<35;1;2m", [MouseMovedRaw(position=Position(x=0, y=1), button=None)]),
        (b"\x1b[<35;2;2m", [MouseMovedRaw(position=Position(x=1, y=1), button=None)]),
        (b"\x1b[<35;95;1m", [MouseMovedRaw(position=Position(x=94, y=0), button=None)]),
        (b"\x1b[<35;1;95m", [MouseMovedRaw(position=Position(x=0, y=94), button=None)]),
        (b"\x1b[<35;95;95m", [MouseMovedRaw(position=Position(x=94, y=94), button=None)]),
        (b"\x1b[<35;500;500m", [MouseMovedRaw(position=Position(x=499, y=499), button=None)]),
        (b"\x1b[<35;1000;1000m", [MouseMovedRaw(position=Position(x=999, y=999), button=None)]),
        (b"\x1b[<0;1;1M", [MouseDownRaw(position=Position(x=0, y=0), button=1)]),
        (b"\x1b[<0;1;1m", [MouseUpRaw(position=Position(x=0, y=0), button=1)]),
        (b"\x1b[<1;1;1M", [MouseDownRaw(position=Position(x=0, y=0), button=2)]),
        (b"\x1b[<1;1;1m", [MouseUpRaw(position=Position(x=0, y=0), button=2)]),
        (b"\x1b[<2;1;1M", [MouseDownRaw(position=Position(x=0, y=0), button=3)]),
        (b"\x1b[<2;1;1m", [MouseUpRaw(position=Position(x=0, y=0), button=3)]),
        # It seems like some systems will use an M even in the mouse up state for motion...
        (b"\x1b[<35;2;1M", [MouseMovedRaw(position=Position(x=1, y=0), button=None)]),
        (b"\x1b[<32;2;1M", [MouseMovedRaw(position=Position(x=1, y=0), button=1)]),
        (b"\x1b[<33;2;1M", [MouseMovedRaw(position=Position(x=1, y=0), button=2)]),
        (b"\x1b[<34;2;1M", [MouseMovedRaw(position=Position(x=1, y=0), button=3)]),
    ],
)
def test_vt_input_parsing(buffer: bytes, expected: list[AnyEvent]) -> None:
    assert vt_inputs.parse(buffer) == expected
