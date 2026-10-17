from __future__ import annotations

import pytest

from counterweight.emulator import Modes
from counterweight.emulator import MouseTracking
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseEvent
from counterweight.events import MouseMoved
from counterweight.events import MouseScrolledDown
from counterweight.events import MouseScrolledLeft
from counterweight.events import MouseScrolledRight
from counterweight.events import MouseScrolledUp
from counterweight.events import MouseUp
from counterweight.geometry import Position
from counterweight.input_encoding import encode_focus
from counterweight.input_encoding import encode_key
from counterweight.input_encoding import encode_mouse
from counterweight.input_encoding import encode_paste
from counterweight.input_encoding import key_sequences
from counterweight.input_parsing import parse_input
from counterweight.keys import Key

SAME_BYTES_AS_ANOTHER_KEY = {
    Key.ControlH: Key.Backspace,
    Key.ControlI: Key.Tab,
    Key.ControlM: Key.Enter,
    Key.ShiftEscape: Key.Escape,
}

PLAIN = Modes()


def parsed(data: bytes) -> tuple[object, ...]:
    return parse_input(data, is_final=True).events


@pytest.mark.parametrize("key", [key for key in Key if key not in SAME_BYTES_AS_ANOTHER_KEY])
def test_every_key_encodes_to_bytes_that_parse_back_to_it(key: Key) -> None:
    assert parsed(key_sequences()[key]) == (KeyPressed(key=key),)


@pytest.mark.parametrize(("key", "sent_as"), SAME_BYTES_AS_ANOTHER_KEY.items())
def test_a_key_a_terminal_sends_as_another_encodes_as_that_one(key: Key, sent_as: Key) -> None:
    assert parsed(key_sequences()[key]) == (KeyPressed(key=sent_as),)


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        (Key.Up, b"\x1b[A"),
        (Key.Home, b"\x1b[H"),
        (Key.End, b"\x1b[F"),
        (Key.F1, b"\x1bOP"),
        (Key.F4, b"\x1bOS"),
        (Key.F5, b"\x1b[15~"),
        (Key.F12, b"\x1b[24~"),
        (Key.F13, b"\x1b[1;2P"),
        (Key.F16, b"\x1b[1;2S"),
        (Key.F17, b"\x1b[15;2~"),
        (Key.ControlF1, b"\x1b[1;5P"),
        (Key.ControlF13, b"\x1b[1;6P"),
        (Key.AltF1, b"\x1b[1;3P"),
        (Key.ShiftHome, b"\x1b[1;2H"),
        (Key.ControlDelete, b"\x1b[3;5~"),
        (Key.AltUp, b"\x1b[1;3A"),
        (Key.Insert, b"\x1b[2~"),
        (Key.PageDown, b"\x1b[6~"),
        (Key.BackTab, b"\x1b[Z"),
        (Key.Backspace, b"\x7f"),
        (Key.Enter, b"\r"),
        (Key.Tab, b"\t"),
        (Key.Escape, b"\x1b"),
        (Key.Space, b" "),
        (Key.ControlSpace, b"\x00"),
        (Key.ControlC, b"\x03"),
        (Key.ControlAltA, b"\x1b\x01"),
        (Key.AltSpace, b"\x1b "),
        (Key.AltEnter, b"\x1b\r"),
        (Key.AltBackspace, b"\x1b\x7f"),
    ],
)
def test_a_key_is_encoded_as_xterm_sends_it(key: Key, expected: bytes) -> None:
    assert key_sequences()[key] == expected


def test_encode_key_sends_a_named_key_its_sequence() -> None:
    assert encode_key(Key.F13, PLAIN) == b"\x1b[1;2P"


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("a", b"a"),
        ("é", "é".encode()),
        ("👩‍💻", "👩‍💻".encode()),
        ("alt+b", b"\x1bb"),
        ("alt+é", b"\x1b" + "é".encode()),
    ],
)
def test_encode_key_sends_text_as_utf_8_after_escape_for_alt(key: str, expected: bytes) -> None:
    assert encode_key(key, PLAIN) == expected


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        (Key.Up, b"\x1bOA"),
        (Key.Down, b"\x1bOB"),
        (Key.Right, b"\x1bOC"),
        (Key.Left, b"\x1bOD"),
        (Key.Home, b"\x1bOH"),
        (Key.End, b"\x1bOF"),
        (Key.ControlUp, b"\x1b[1;5A"),
        (Key.F1, b"\x1bOP"),
        (Key.PageUp, b"\x1b[5~"),
    ],
)
def test_application_cursor_keys_send_the_cursor_keys_home_and_end_as_ss3(key: Key, expected: bytes) -> None:
    assert encode_key(key, Modes(application_cursor_keys=True)) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [("one", b"one"), ("one\ntwo", b"one\rtwo"), ("one\r\ntwo\n", b"one\rtwo\r")],
)
def test_a_paste_sends_its_line_breaks_as_carriage_returns(text: str, expected: bytes) -> None:
    assert encode_paste(text, PLAIN) == expected


def test_a_bracketed_paste_is_wrapped_in_its_markers() -> None:
    assert encode_paste("one\ntwo", Modes(bracketed_paste=True)) == b"\x1b[200~one\rtwo\x1b[201~"


@pytest.mark.parametrize(
    "text",
    ["a\x1b[201~b", "a\x1b[20\x1b[201~1~b", "a\x1b[2\x1b[20\x1b[201~1~01~b"],
    ids=["an end marker", "an end marker around one", "end markers nested twice"],
)
def test_a_bracketed_paste_drops_every_end_marker_in_its_text(text: str) -> None:
    encoded = encode_paste(text, Modes(bracketed_paste=True))

    assert encoded == b"\x1b[200~ab\x1b[201~"


SGR = "sgr"
LEGACY = "legacy"


def modes(tracking: MouseTracking, encoding: str = SGR) -> Modes:
    return Modes(mouse_tracking=tracking, sgr_mouse=encoding == SGR)


AT = Position(4, 6)

PRESS = MouseDown(absolute=Position(90, 90), button=1)
RELEASE = MouseUp(absolute=Position(90, 90), button=1)
DRAG = MouseMoved(absolute=Position(90, 90), button=1)
MOTION = MouseMoved(absolute=Position(90, 90), button=None)
WHEEL = MouseScrolledUp(absolute=Position(90, 90))


@pytest.mark.parametrize(
    ("tracking", "reported"),
    [
        ("none", ()),
        ("x10", (PRESS,)),
        ("normal", (PRESS, RELEASE, WHEEL)),
        ("button", (PRESS, RELEASE, WHEEL, DRAG)),
        ("any", (PRESS, RELEASE, WHEEL, DRAG, MOTION)),
    ],
)
def test_a_mouse_event_is_reported_only_if_the_programs_tracking_asks_for_it(
    tracking: MouseTracking, reported: tuple[MouseEvent, ...]
) -> None:
    sent = tuple(event for event in (PRESS, RELEASE, WHEEL, DRAG, MOTION) if encode_mouse(event, AT, modes(tracking)))

    assert sent == reported


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        (MouseDown(absolute=AT, button=1), b"\x1b[<0;5;7M"),
        (MouseDown(absolute=AT, button=3), b"\x1b[<2;5;7M"),
        (MouseUp(absolute=AT, button=1), b"\x1b[<0;5;7m"),
        (MouseMoved(absolute=AT, button=1), b"\x1b[<32;5;7M"),
        (MouseMoved(absolute=AT, button=None), b"\x1b[<35;5;7M"),
        (MouseDown(absolute=AT, button=8), b"\x1b[<128;5;7M"),
        (MouseDown(absolute=AT, button=11), b"\x1b[<131;5;7M"),
        (MouseScrolledUp(absolute=AT), b"\x1b[<64;5;7M"),
        (MouseScrolledDown(absolute=AT), b"\x1b[<65;5;7M"),
        (MouseScrolledLeft(absolute=AT), b"\x1b[<66;5;7M"),
        (MouseScrolledRight(absolute=AT), b"\x1b[<67;5;7M"),
        (MouseDown(absolute=AT, button=1, is_shift_held=True), b"\x1b[<4;5;7M"),
        (MouseDown(absolute=AT, button=1, is_alt_held=True), b"\x1b[<8;5;7M"),
        (MouseDown(absolute=AT, button=1, is_control_held=True), b"\x1b[<16;5;7M"),
    ],
)
def test_sgr_mouse_reports_name_the_button_motion_and_modifiers_at_a_1_based_position(
    event: MouseEvent, expected: bytes
) -> None:
    assert encode_mouse(event, AT, modes("any")) == expected


@pytest.mark.parametrize(
    "event",
    [
        MouseDown(absolute=AT, button=2, is_control_held=True),
        MouseUp(absolute=AT, button=1, is_shift_held=True),
        MouseMoved(absolute=AT, button=3),
        MouseMoved(absolute=AT, button=None, is_alt_held=True),
        MouseDown(absolute=AT, button=9),
        MouseScrolledDown(absolute=AT),
        MouseScrolledRight(absolute=AT, is_shift_held=True),
    ],
)
def test_an_sgr_mouse_report_parses_back_to_the_event_at_its_position(event: MouseEvent) -> None:
    encoded = encode_mouse(event, AT, modes("any"))

    assert encoded is not None
    assert parsed(encoded) == (event,)


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        (MouseDown(absolute=AT, button=1), b"\x1b[M\x20\x25\x27"),
        (MouseDown(absolute=AT, button=2, is_control_held=True), b"\x1b[M\x31\x25\x27"),
        (MouseUp(absolute=AT, button=2), b"\x1b[M\x23\x25\x27"),
        (MouseUp(absolute=AT, button=1, is_shift_held=True), b"\x1b[M\x27\x25\x27"),
        (MouseUp(absolute=AT, button=8), b"\x1b[M\x23\x25\x27"),
        (MouseMoved(absolute=AT, button=1), b"\x1b[M\x40\x25\x27"),
        (MouseScrolledUp(absolute=AT), b"\x1b[M\x60\x25\x27"),
    ],
)
def test_legacy_mouse_reports_send_a_release_as_button_3(event: MouseEvent, expected: bytes) -> None:
    assert encode_mouse(event, AT, modes("any", LEGACY)) == expected


def test_x10_mouse_reports_leave_out_the_modifiers() -> None:
    event = MouseDown(absolute=AT, button=1, is_shift_held=True, is_alt_held=True, is_control_held=True)

    assert encode_mouse(event, AT, modes("x10")) == b"\x1b[<0;5;7M"


@pytest.mark.parametrize(
    ("position", "is_reported"),
    [(Position(222, 222), True), (Position(223, 0), False), (Position(0, 223), False)],
)
def test_legacy_mouse_reports_reach_column_and_row_223(position: Position, is_reported: bool) -> None:
    encoded = encode_mouse(MouseDown(absolute=position, button=1), position, modes("normal", LEGACY))

    assert (encoded is not None) == is_reported


def test_sgr_mouse_reports_reach_past_column_223() -> None:
    position = Position(500, 300)

    assert encode_mouse(MouseDown(absolute=position, button=1), position, modes("normal")) == b"\x1b[<0;501;301M"


@pytest.mark.parametrize(("is_focused", "expected"), [(True, b"\x1b[I"), (False, b"\x1b[O")])
def test_focus_changes_are_sent_to_a_program_that_asked_for_them(is_focused: bool, expected: bytes) -> None:
    assert encode_focus(is_focused, Modes(focus_events=True)) == expected


@pytest.mark.parametrize("is_focused", [True, False])
def test_focus_changes_are_not_sent_to_a_program_that_didnt_ask(is_focused: bool) -> None:
    assert encode_focus(is_focused, PLAIN) is None
