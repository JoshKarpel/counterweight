from __future__ import annotations

from collections.abc import Callable, Sequence

import pytest

from counterweight.components import component
from counterweight.controls import AnyControl, ScrollBy, ScrollTo
from counterweight.elements import AnyElement, Div, Text
from counterweight.events import AnyEvent, InputEvent, InputResponse, KeyPressed, Receiver, TerminalResized
from counterweight.geometry import Position
from counterweight.hooks import use_state
from counterweight.layout import (
    NO_LAYOUTS,
    Anchor,
    Layouts,
    LayoutTree,
    PriorScroll,
    layout_changes,
    prior_scrolls,
    requested_offset,
)
from counterweight.shadow import ShadowTree, update_shadow
from counterweight.styles import Style
from counterweight.styles.utilities import (
    clip_to_screen,
    col,
    height,
    overflow_anchor_none,
    overflow_y_scroll,
    position_absolute,
    shrink,
    stick_to_end_x,
    stick_to_end_y,
    text_wrap_stable,
    unstick_y,
)
from tests.test_scrolling import HANDLE, last_rows

# Eight messages that each take one row of a screen 12 wide, and two of one 8 wide.
MESSAGES = tuple((i, f"m{i} aaaa bbb") for i in range(8))


@component
def message(content: str) -> Text:
    return Text(content=content, style=text_wrap_stable)


def transcript_children(messages: Sequence[tuple[int, str]]) -> list[AnyElement]:
    return [message(content).with_key(str(id)) for id, content in messages]  # type: ignore[misc]


type Messages = tuple[tuple[int, str], ...]

EDITS: dict[str, Callable[[Messages], Messages]] = {
    "g": lambda ms: (*ms[:-1], (ms[-1][0], f"{ms[-1][1]}\ngrown")),
    "d": lambda ms: ms[1:],
    "x": lambda ms: (*ms[:2], *ms[3:]),
    "e": lambda ms: ((ms[0][0], f"{ms[0][1]}\nmore\nmore"), *ms[1:]),
    "i": lambda ms: ((-1, "new"), *ms),
    "a": lambda ms: (*ms, (len(ms), f"m{len(ms)} aaaa bbb")),
}


@component
def transcript(container_style: Style, start: Messages = MESSAGES) -> Div:
    """
    A transcript 4 rows tall, keyed by message, where `g` grows the last message by a row, `d` drops the first,
    `x` drops the third, `e` expands the first by two rows, `i` inserts a message before the first,
    and `a` appends one after the last.
    """
    messages, set_messages = use_state(start)

    def on_key(event: InputEvent, receiver: Receiver) -> InputResponse:
        assert isinstance(event, KeyPressed)
        set_messages(EDITS[event.key])
        return ()

    return Div(
        style=col,
        on_input=on_key,
        children=[
            Div(
                style=col | height(4) | overflow_y_scroll | container_style,
                handle=HANDLE,
                children=transcript_children(messages),
            )
        ],
    )


def padded(*texts: str, width: int = 12) -> list[str]:
    return [text.ljust(width) for text in texts]


NARROWED = TerminalResized(dimensions=(8, 4))

# How the transcript changes below the view, above it, and everywhere at once.
CHANGES: list[tuple[str, AnyEvent]] = [
    ("streaming-message-grows", KeyPressed(key="g")),
    ("message-above-dropped", KeyPressed(key="d")),
    ("message-above-expands", KeyPressed(key="e")),
]


@pytest.mark.parametrize(("change", "event"), CHANGES, ids=[name for name, _ in CHANGES])
async def test_a_transcript_that_sticks_to_its_end_stays_at_its_end_when_it_changes(
    change: str, event: AnyEvent
) -> None:
    expected = {
        "streaming-message-grows": padded("m5 aaaa bbb", "m6 aaaa bbb", "m7 aaaa bbb", "grown"),
        "message-above-dropped": padded("m4 aaaa bbb", "m5 aaaa bbb", "m6 aaaa bbb", "m7 aaaa bbb"),
        "message-above-expands": padded("m4 aaaa bbb", "m5 aaaa bbb", "m6 aaaa bbb", "m7 aaaa bbb"),
    }[change]

    assert await last_rows(transcript(stick_to_end_y), (12, 4), [event]) == expected


async def test_a_transcript_that_sticks_to_its_end_stays_at_its_end_when_the_terminal_narrows() -> None:
    assert await last_rows(transcript(stick_to_end_y), (12, 4), [NARROWED]) == padded(
        "m6 aaaa", "bbb", "m7 aaaa", "bbb", width=8
    )


@pytest.mark.parametrize(("change", "event"), CHANGES, ids=[name for name, _ in CHANGES])
async def test_a_transcript_read_back_keeps_its_anchor_in_place_when_it_changes(change: str, event: AnyEvent) -> None:
    autopilot: list[AnyEvent | AnyControl] = [ScrollTo(HANDLE, y=1), event]

    assert await last_rows(transcript(stick_to_end_y), (12, 4), autopilot) == padded(
        "m1 aaaa bbb", "m2 aaaa bbb", "m3 aaaa bbb", "m4 aaaa bbb"
    )


async def test_a_transcript_read_back_keeps_its_anchor_in_place_when_the_terminal_narrows() -> None:
    autopilot: list[AnyEvent | AnyControl] = [ScrollTo(HANDLE, y=1), NARROWED]

    assert await last_rows(transcript(stick_to_end_y), (12, 4), autopilot) == padded(
        "m1 aaaa", "bbb", "m2 aaaa", "bbb", width=8
    )


async def test_a_container_scrolled_back_to_its_end_sticks_to_it_again() -> None:
    autopilot: list[AnyEvent | AnyControl] = [ScrollTo(HANDLE, y=1), ScrollBy(HANDLE, y=100), KeyPressed(key="g")]

    assert (await last_rows(transcript(stick_to_end_y), (12, 4), autopilot))[-1] == padded("grown")[0]


async def test_a_container_that_does_not_stick_to_its_end_stays_at_the_top_as_its_content_grows() -> None:
    root = transcript(unstick_y, start=MESSAGES[:2])

    assert await last_rows(root, (12, 4), [KeyPressed(key="a")] * 4) == padded(
        "m0 aaaa bbb", "m1 aaaa bbb", "m2 aaaa bbb", "m3 aaaa bbb"
    )


async def test_a_container_that_sticks_to_its_end_and_starts_short_follows_its_end_once_it_overflows() -> None:
    root = transcript(stick_to_end_y, start=MESSAGES[:2])

    assert await last_rows(root, (12, 4), [KeyPressed(key="a")] * 4) == padded(
        "m2 aaaa bbb", "m3 aaaa bbb", "m4 aaaa bbb", "m5 aaaa bbb"
    )


async def test_a_container_that_sticks_to_its_end_starts_at_its_end() -> None:
    assert (await last_rows(transcript(stick_to_end_y), (12, 4)))[-1] == padded("m7 aaaa bbb")[0]


async def test_a_container_with_anchoring_off_only_clamps() -> None:
    autopilot: list[AnyEvent | AnyControl] = [ScrollTo(HANDLE, y=1), KeyPressed(key="e")]

    assert await last_rows(transcript(overflow_anchor_none), (12, 4), autopilot) == padded(
        "more", "more", "m1 aaaa bbb", "m2 aaaa bbb"
    )


async def test_a_container_scrolled_to_the_top_does_not_anchor_so_content_added_above_shows() -> None:
    assert (await last_rows(transcript(Style()), (12, 4), [KeyPressed(key="i")]))[0] == padded("new")[0]


async def test_a_container_whose_anchor_unmounted_only_clamps() -> None:
    autopilot: list[AnyEvent | AnyControl] = [ScrollTo(HANDLE, y=2), KeyPressed(key="x")]

    assert await last_rows(transcript(Style()), (12, 4), autopilot) == padded(
        "m3 aaaa bbb", "m4 aaaa bbb", "m5 aaaa bbb", "m6 aaaa bbb"
    )


@component
def block_then_lines() -> Div:
    """A container whose first child is a block of three lines, the first of which `e` expands by a row."""
    is_expanded, set_expanded = use_state(False)

    def on_key(event: InputEvent, receiver: Receiver) -> InputResponse:
        set_expanded(True)
        return ()

    return Div(
        style=col,
        on_input=on_key,
        children=[
            Div(
                style=col | height(3) | overflow_y_scroll,
                handle=HANDLE,
                children=[
                    Div(
                        style=col,
                        children=[
                            Text(content="a\nexpanded" if is_expanded else "a"),
                            Text(content="b"),
                            Text(content="c"),
                        ],
                    ),
                    *(Text(content=f"line {i}") for i in range(4)),
                ],
            )
        ],
    )


async def test_a_node_partly_in_view_is_descended_into_for_an_anchor_wholly_in_view() -> None:
    autopilot: list[AnyEvent | AnyControl] = [ScrollTo(HANDLE, y=1), KeyPressed(key="e")]

    assert await last_rows(block_then_lines(), (6, 3), autopilot) == ["b     ", "c     ", "line 0"]


def laid_out(root: AnyElement, width: int, height: int) -> tuple[ShadowTree, Layouts]:
    shadow = update_shadow(root, None, NO_LAYOUTS).tree
    return shadow, LayoutTree().compute(layout_changes(None, shadow), shadow, width, height, {})


def test_the_anchor_is_picked_where_a_scroll_since_the_layout_has_moved_the_content() -> None:
    shadow, layouts = laid_out(Div(style=col | height(2) | overflow_y_scroll, children=lines_of(5)), 6, 2)

    assert prior_scrolls(layouts, {shadow.root.key: Position(0, 3)})[shadow.root.key] == PriorScroll(
        offset=Position(0, 3),
        is_at_end_x=True,
        is_at_end_y=True,
        anchor=Anchor(key=shadow.root.children[3].key, distance=0),
    )


def lines_of(count: int) -> list[AnyElement]:
    return [Text(content=f"line {i}") for i in range(count)]


@pytest.mark.parametrize(
    "excluded",
    [clip_to_screen | position_absolute, overflow_anchor_none],
    ids=["unclipped", "anchoring-off"],
)
def test_an_excluded_node_is_never_the_anchor_nor_anything_inside_it(excluded: Style) -> None:
    skipped = Div(style=col | excluded, children=lines_of(2))
    root = Div(style=col | height(3) | overflow_y_scroll, children=[Text(content="above"), skipped, *lines_of(3)])
    shadow, layouts = laid_out(root, 6, 3)

    anchor = prior_scrolls(layouts, {shadow.root.key: Position(0, 1)})[shadow.root.key].anchor

    assert anchor is not None and anchor.key == shadow.root.children[2].key


def test_a_nested_scroll_container_is_the_anchor_without_being_descended_into() -> None:
    nested = Div(style=col | height(3) | shrink(0) | overflow_y_scroll, children=lines_of(4))
    shadow, layouts = laid_out(
        Div(style=col | height(2) | overflow_y_scroll, children=[Text(content="x"), nested]), 6, 2
    )
    outer, inner = shadow.root, shadow.root.children[1]

    assert prior_scrolls(layouts, {outer.key: Position(0, 2), inner.key: Position(0, 0)})[outer.key].anchor == Anchor(
        key=inner.key, distance=-1
    )


def test_a_node_exactly_filling_the_view_is_the_anchor_without_being_descended_into() -> None:
    root = Div(
        style=col | height(2) | overflow_y_scroll,
        children=[*lines_of(1), Div(style=col, children=lines_of(2)), *lines_of(2)],
    )
    shadow, layouts = laid_out(root, 6, 2)

    assert prior_scrolls(layouts, {shadow.root.key: Position(0, 1)})[shadow.root.key].anchor == Anchor(
        key=shadow.root.children[1].key, distance=0
    )


def test_a_container_with_nothing_it_can_anchor_in_view_has_no_anchor() -> None:
    root = Div(
        style=col | height(2) | overflow_y_scroll, children=[Div(style=overflow_anchor_none, children=lines_of(4))]
    )
    shadow, layouts = laid_out(root, 6, 2)

    assert prior_scrolls(layouts, {shadow.root.key: Position(0, 1)})[shadow.root.key].anchor is None


def test_a_container_at_the_end_it_sticks_to_picks_no_anchor() -> None:
    root = Div(style=col | height(2) | overflow_y_scroll | stick_to_end_y, children=lines_of(4))
    shadow, layouts = laid_out(root, 6, 2)

    assert prior_scrolls(layouts, {shadow.root.key: Position(0, 2)})[shadow.root.key].anchor is None


def test_a_node_starting_at_the_bottom_of_the_view_is_not_in_view() -> None:
    covering = Div(style=col | overflow_anchor_none, children=lines_of(3))
    root = Div(style=col | height(2) | overflow_y_scroll, children=[covering, *lines_of(2)])
    shadow, layouts = laid_out(root, 6, 2)

    assert prior_scrolls(layouts, {shadow.root.key: Position(0, 1)})[shadow.root.key].anchor is None


def test_a_leaf_partly_in_view_is_the_anchor() -> None:
    root = Div(style=col | height(2) | overflow_y_scroll, children=[Text(content="a\nb\nc"), *lines_of(2)])
    shadow, layouts = laid_out(root, 6, 2)

    assert prior_scrolls(layouts, {shadow.root.key: Position(0, 1)})[shadow.root.key].anchor == Anchor(
        key=shadow.root.children[0].key, distance=-1
    )


def test_a_nested_container_keeps_its_anchor_in_place_inside_a_scrolled_container() -> None:
    inner = Div(style=col | height(2) | shrink(0) | overflow_y_scroll, children=lines_of(6))
    outer = Div(style=col | height(2) | overflow_y_scroll, children=[Text(content="top"), inner])
    shadow = update_shadow(outer, None, NO_LAYOUTS).tree
    inner_node = shadow.root.children[1]
    priors = {
        shadow.root.key: PriorScroll(offset=Position(0, 1), is_at_end_x=False, is_at_end_y=False, anchor=None),
        inner_node.key: PriorScroll(
            offset=Position(0, 1),
            is_at_end_x=False,
            is_at_end_y=False,
            anchor=Anchor(key=inner_node.children[2].key, distance=0),
        ),
    }

    layouts = LayoutTree().compute(layout_changes(None, shadow), shadow, 6, 2, priors)

    assert layouts.scrolls[inner_node.key].offset == Position(0, 2)


MAX_OFFSET = Position(5, 7)


@pytest.mark.parametrize(
    ("prior", "style", "expected"),
    [
        (None, stick_to_end_x, 5),
        (None, Style(), 0),
        (PriorScroll(offset=Position(2, 0), is_at_end_x=True, is_at_end_y=False, anchor=None), stick_to_end_x, 5),
        (PriorScroll(offset=Position(2, 0), is_at_end_x=False, is_at_end_y=False, anchor=None), stick_to_end_x, 2),
        (PriorScroll(offset=Position(2, 0), is_at_end_x=True, is_at_end_y=False, anchor=None), Style(), 2),
    ],
    ids=["new-sticks", "new", "at-end-sticks", "not-at-end", "at-end-does-not-stick"],
)
def test_a_container_that_sticks_to_its_end_horizontally_follows_it_only_from_its_end(
    prior: PriorScroll | None, style: Style, expected: int
) -> None:
    assert requested_offset(prior, {}, 0, MAX_OFFSET, style.resolved).x == expected
