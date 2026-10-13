import pytest
from hypothesis import given
from hypothesis import strategies as st

from counterweight.events import (
    AnyEvent,
    KeyPressed,
    MouseDown,
    MouseMoved,
    MouseScrolledDown,
    MouseScrolledUp,
    MouseUp,
)
from counterweight.geometry import Position
from counterweight.input_parsing import ParsedInput, parse_input
from counterweight.keys import Key


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
        # an ESC that doesn't begin a sequence is the Escape key
        (b"\x1bx", [KeyPressed(key=Key.Escape), KeyPressed(key="x")]),
        (b"\x1b\x1b", [KeyPressed(key=Key.Escape), KeyPressed(key=Key.Escape)]),
        (b"\x1b\x1b[A", [KeyPressed(key=Key.Escape), KeyPressed(key=Key.Up)]),
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
        (b"\x1b[3;3~", [KeyPressed(key=Key.AltDelete)]),
        (b"\x1b[3;5~", [KeyPressed(key=Key.ControlDelete)]),
        (b"\x1b[3;6~", [KeyPressed(key=Key.ControlShiftInsert)]),
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
        (b"\x1b[<64;2;1M", [MouseScrolledDown(absolute=Position(x=1, y=0))]),
        (b"\x1b[<65;2;1M", [MouseScrolledUp(absolute=Position(x=1, y=0))]),
    ],
)
def test_known_input_parses_to_its_events(buffer: bytes, expected: list[AnyEvent]) -> None:
    assert parse_input(buffer, is_final=True) == ParsedInput(events=tuple(expected), skipped=(), remainder=b"")


@pytest.mark.parametrize(
    "buffer, expected",
    [
        # well-formed CSI and SS3 sequences we don't know the meaning of
        (b"\x1b[1;5p", ParsedInput(events=(), skipped=(b"\x1b[1;5p",), remainder=b"")),
        (b"\x1b[5^", ParsedInput(events=(), skipped=(b"\x1b[5^",), remainder=b"")),
        (b"\x1b[a", ParsedInput(events=(), skipped=(b"\x1b[a",), remainder=b"")),
        (b"\x1b[I", ParsedInput(events=(), skipped=(b"\x1b[I",), remainder=b"")),
        (b"\x1b[200~", ParsedInput(events=(), skipped=(b"\x1b[200~",), remainder=b"")),
        (b"\x1b[1 q", ParsedInput(events=(), skipped=(b"\x1b[1 q",), remainder=b"")),
        (b"\x1bOx", ParsedInput(events=(), skipped=(b"\x1bOx",), remainder=b"")),
        (b"\x1b[<35;1M", ParsedInput(events=(), skipped=(b"\x1b[<35;1M",), remainder=b"")),
        (
            b"a\x1b[1;5pb",
            ParsedInput(events=(KeyPressed(key="a"), KeyPressed(key="b")), skipped=(b"\x1b[1;5p",), remainder=b""),
        ),
        # a sequence cut short by a byte that can't be in one is skipped up to that byte
        (
            b"\x1b[1;\x03",
            ParsedInput(events=(KeyPressed(key=Key.ControlC),), skipped=(b"\x1b[1;",), remainder=b""),
        ),
        (
            "\x1b[1;é".encode(),
            ParsedInput(events=(KeyPressed(key="é"),), skipped=(b"\x1b[1;",), remainder=b""),
        ),
        # control bytes with no key
        (b"\x1c", ParsedInput(events=(), skipped=(b"\x1c",), remainder=b"")),
        # bytes that aren't UTF-8 are skipped, and everything around them kept
        (
            b"a\xffb",
            ParsedInput(events=(KeyPressed(key="a"), KeyPressed(key="b")), skipped=(b"\xff",), remainder=b""),
        ),
        (
            b"a\xc3\x1b[A",
            ParsedInput(events=(KeyPressed(key="a"), KeyPressed(key=Key.Up)), skipped=(b"\xc3",), remainder=b""),
        ),
        (
            b"\xff\xcc\x81",
            ParsedInput(events=(KeyPressed(key="\u0301"),), skipped=(b"\xff",), remainder=b""),
        ),
    ],
)
def test_input_that_is_not_an_event_is_skipped(buffer: bytes, expected: ParsedInput) -> None:
    assert parse_input(buffer, is_final=True) == expected


@pytest.mark.parametrize(
    "buffer, expected",
    [
        (b"\x1b", ParsedInput(events=(), skipped=(), remainder=b"\x1b")),
        (b"a\x1b", ParsedInput(events=(KeyPressed(key="a"),), skipped=(), remainder=b"\x1b")),
        (b"\x1b[", ParsedInput(events=(), skipped=(), remainder=b"\x1b[")),
        (b"\x1b[<35;1", ParsedInput(events=(), skipped=(), remainder=b"\x1b[<35;1")),
        (b"\x1bO", ParsedInput(events=(), skipped=(), remainder=b"\x1bO")),
        (b"a\xc3", ParsedInput(events=(KeyPressed(key="a"),), skipped=(), remainder=b"\xc3")),
        (b"\xf0\x9f\x98", ParsedInput(events=(), skipped=(), remainder=b"\xf0\x9f\x98")),
    ],
)
def test_input_that_may_continue_is_held_over_until_final(buffer: bytes, expected: ParsedInput) -> None:
    assert parse_input(buffer, is_final=False) == expected


@pytest.mark.parametrize(
    "buffer, expected",
    [
        (b"\x1b", ParsedInput(events=(KeyPressed(key=Key.Escape),), skipped=(), remainder=b"")),
        (
            b"\x1b[",
            ParsedInput(events=(KeyPressed(key=Key.Escape), KeyPressed(key="[")), skipped=(), remainder=b""),
        ),
        (
            b"\x1bO",
            ParsedInput(events=(KeyPressed(key=Key.Escape), KeyPressed(key="O")), skipped=(), remainder=b""),
        ),
        (b"a\xc3", ParsedInput(events=(KeyPressed(key="a"),), skipped=(b"\xc3",), remainder=b"")),
    ],
)
def test_final_input_is_not_held_over(buffer: bytes, expected: ParsedInput) -> None:
    assert parse_input(buffer, is_final=True) == expected


def parse_reads(reads: list[bytes]) -> ParsedInput:
    """Parse `reads` one after another, the way the input reader does, carrying each remainder into the next read."""
    events: list[AnyEvent] = []
    skipped: list[bytes] = []
    pending = b""
    for index, read in enumerate(reads):
        parsed = parse_input(pending + read, is_final=index == len(reads) - 1)
        events.extend(parsed.events)
        skipped.extend(parsed.skipped)
        pending = parsed.remainder
    return ParsedInput(events=tuple(events), skipped=(b"".join(skipped),), remainder=pending)


SPLIT_CORPUS = b"".join(
    [
        b"\x1b[<35;12;4M",
        "aé日😀".encode(),
        b"\x1b[1;5p",
        b"\x1bOP",
        b"\x1b",
        b"\x1b[3;5~",
        b"\xff",
        b"\x03",
    ]
)


@pytest.mark.parametrize("offset", range(1, len(SPLIT_CORPUS)))
def test_input_split_across_reads_parses_the_same_as_one_read(offset: int) -> None:
    assert parse_reads([SPLIT_CORPUS[:offset], SPLIT_CORPUS[offset:]]) == parse_reads([SPLIT_CORPUS])


def test_grapheme_cluster_split_across_reads_is_two_key_presses() -> None:
    assert parse_reads([b"e", "\u0301".encode()]).events == (KeyPressed(key="e"), KeyPressed(key="\u0301"))


@given(st.binary())
def test_final_parse_of_any_bytes_holds_nothing_over(buffer: bytes) -> None:
    assert parse_input(buffer, is_final=True).remainder == b""


@given(st.binary())
def test_held_over_bytes_are_a_suffix_of_the_input(buffer: bytes) -> None:
    assert buffer.endswith(parse_input(buffer, is_final=False).remainder)


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
        ]
    ),
    st.text().map(str.encode),
)


def join_text(parsed: ParsedInput) -> tuple[object, ...]:
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
