from __future__ import annotations

import pytest

from counterweight.components import component
from counterweight.controls import AnyControl
from counterweight.controls import FocusNext
from counterweight.controls import FocusOn
from counterweight.controls import ScrollAlignment
from counterweight.controls import ScrollBy
from counterweight.controls import ScrollIntoView
from counterweight.controls import ScrollTo
from counterweight.elements import AnyElement
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import AnyEvent
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.focus import ElementHandle
from counterweight.focus import FocusHandle
from counterweight.hooks import use_focus
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.layout import aligned
from counterweight.styles import Style
from counterweight.styles.utilities import clip_to_screen
from counterweight.styles.utilities import col
from counterweight.styles.utilities import display_none
from counterweight.styles.utilities import inset_top
from counterweight.styles.utilities import overflow_x_scroll
from counterweight.styles.utilities import overflow_y_scroll
from counterweight.styles.utilities import position_absolute
from counterweight.styles.utilities import row
from counterweight.styles.utilities import shrink
from counterweight.styles.utilities import size
from tests.test_scrolling import HANDLE
from tests.test_scrolling import frames_of
from tests.test_scrolling import last_rows
from tests.test_scrolling import rows

ITEMS = tuple(ElementHandle() for _ in range(8))


def items(prefix: str = "item") -> tuple[AnyElement, ...]:
    return tuple(Text(content=f"{prefix} {i}", handle=handle) for i, handle in enumerate(ITEMS))


def column(*children: AnyElement, style: Style = Style()) -> Div:
    """A box 8 wide and 3 tall that scrolls vertically, so 3 rows of its children are in view."""
    return Div(style=col | size(8, 3) | overflow_y_scroll | style, handle=HANDLE, children=children)


def showing(*indexes: int) -> list[str]:
    return [f"item {i}".ljust(8) for i in indexes]


@pytest.mark.parametrize(
    ("block", "expected"),
    [("start", showing(4, 5, 6)), ("center", showing(3, 4, 5)), ("end", showing(2, 3, 4))],
)
async def test_scroll_into_view_aligns_its_target_vertically_by_block(
    block: ScrollAlignment, expected: list[str]
) -> None:
    assert await last_rows(column(*items()), (8, 3), [ScrollIntoView(ITEMS[4], block=block)]) == expected


@pytest.mark.parametrize(
    ("start", "expected"),
    [(0, showing(2, 3, 4)), (5, showing(4, 5, 6))],
    ids=["from-above", "from-below"],
)
async def test_scroll_into_view_nearest_scrolls_its_target_just_into_view_from_either_side(
    start: int, expected: list[str]
) -> None:
    autopilot: list[AnyEvent | AnyControl] = [ScrollTo(HANDLE, y=start), ScrollIntoView(ITEMS[4], block="nearest")]

    assert await last_rows(column(*items()), (8, 3), autopilot) == expected


async def test_scroll_into_view_nearest_leaves_a_target_already_in_view_alone() -> None:
    autopilot: list[AnyEvent | AnyControl] = [ScrollTo(HANDLE, y=2), ScrollIntoView(ITEMS[3], block="nearest")]

    assert await last_rows(column(*items()), (8, 3), autopilot) == showing(2, 3, 4)


async def test_scroll_into_view_aligns_its_target_horizontally_by_inline() -> None:
    cells = tuple(Text(content=f"[{i}]", style=size(4, 1) | shrink(0), handle=handle) for i, handle in enumerate(ITEMS))
    container = Div(style=row | size(8, 1) | overflow_x_scroll, children=cells)

    assert await last_rows(container, (8, 1), [ScrollIntoView(ITEMS[5], inline="start")]) == ["[5] [6] "]


async def test_scroll_into_view_scrolls_each_container_above_its_target_from_the_innermost_out() -> None:
    inner = Div(style=col | size(8, 2) | shrink(0) | overflow_y_scroll, children=items())
    outer = Div(style=col | size(8, 3) | overflow_y_scroll, children=(*lines_of(3, "out"), inner, *lines_of(2, "end")))

    assert await last_rows(outer, (8, 3), [ScrollIntoView(ITEMS[6])]) == [*showing(6, 7), "end 0   "]


@pytest.mark.parametrize(
    ("inline", "expected"),
    [("start", "[5] [6] "), ("end", "[4] [5] ")],
)
async def test_scroll_into_view_scrolls_nested_horizontal_containers_from_the_innermost_out(
    inline: ScrollAlignment, expected: str
) -> None:
    cells = tuple(Text(content=f"[{i}]", style=size(4, 1) | shrink(0), handle=handle) for i, handle in enumerate(ITEMS))
    inner = Div(style=row | size(12, 1) | shrink(0) | overflow_x_scroll, children=cells)
    edge = Text(content="....", style=shrink(0))
    outer = Div(style=row | size(8, 1) | overflow_x_scroll, children=(edge, inner, edge))

    assert await last_rows(outer, (8, 1), [ScrollIntoView(ITEMS[5], inline=inline)]) == [expected]


def lines_of(count: int, prefix: str) -> tuple[AnyElement, ...]:
    return tuple(Text(content=f"{prefix} {i}") for i in range(count))


async def test_scroll_into_view_of_a_scroll_container_scrolls_the_containers_above_it_and_not_itself() -> None:
    inner_handle = ElementHandle()
    inner = Div(style=col | size(8, 2) | shrink(0) | overflow_y_scroll, handle=inner_handle, children=items())
    outer = Div(style=col | size(8, 2) | overflow_y_scroll, children=(*lines_of(3, "out"), inner))
    autopilot: list[AnyEvent | AnyControl] = [ScrollTo(inner_handle, y=1), ScrollIntoView(inner_handle)]

    assert await last_rows(outer, (8, 2), autopilot) == showing(1, 2)


@pytest.mark.parametrize(
    "target",
    [ElementHandle(), ITEMS[0]],
    ids=["unmounted", "hidden"],
)
async def test_scroll_into_view_of_an_element_that_is_not_laid_out_does_nothing(target: ElementHandle) -> None:
    hidden = Div(style=display_none, children=(Text(content="hidden", handle=ITEMS[0]),))
    container = column(*lines_of(6, "line"), hidden)
    autopilot: list[AnyEvent | AnyControl] = [ScrollTo(HANDLE, y=1), ScrollIntoView(target)]

    assert (await last_rows(container, (8, 3), autopilot))[0] == "line 1  "


async def test_scroll_into_view_applies_each_request_from_where_the_last_left_the_scroll() -> None:
    def both(event: InputEvent, receiver: Receiver) -> InputResponse:
        return ScrollIntoView(ITEMS[5]), ScrollIntoView(ITEMS[4], block="nearest")

    container = Div(style=col | size(8, 3) | overflow_y_scroll, on_input=both, children=items())

    assert await last_rows(container, (8, 3), [KeyPressed(key="x")]) == showing(4, 5, 6)


async def test_scroll_controls_in_one_response_apply_in_the_order_they_were_returned() -> None:
    def both(event: InputEvent, receiver: Receiver) -> InputResponse:
        return ScrollIntoView(ITEMS[4]), ScrollBy(HANDLE, y=1)

    container = Div(style=col | size(8, 3) | overflow_y_scroll, handle=HANDLE, on_input=both, children=items())

    assert await last_rows(container, (8, 3), [KeyPressed(key="x")]) == showing(5, 6, 7)


async def test_scroll_into_view_scrolls_no_container_above_an_unclipped_element() -> None:
    popup = Div(
        style=position_absolute | inset_top(1) | size(8, 2) | clip_to_screen | col | overflow_y_scroll,
        children=items(),
    )
    outer = Div(style=col | size(8, 2) | overflow_y_scroll, children=(Div(children=(Text(content="field"), popup)),))

    assert await last_rows(outer, (8, 3), [ScrollIntoView(ITEMS[3])]) == ["field   ", *showing(3, 4)]


async def test_scroll_into_view_of_a_hidden_element_leaves_later_requests_to_apply() -> None:
    def both(event: InputEvent, receiver: Receiver) -> InputResponse:
        return ScrollIntoView(ITEMS[0]), ScrollIntoView(ITEMS[1])

    hidden = Div(style=display_none, children=(Text(content="hidden", handle=ITEMS[0]),))
    shown = Text(content="shown", handle=ITEMS[1])
    container = Div(
        style=col | size(8, 3) | overflow_y_scroll, on_input=both, children=(*lines_of(6, "line"), hidden, shown)
    )

    assert (await last_rows(container, (8, 3), [KeyPressed(key="x")]))[-1] == "shown   "


@component
def highlighted_list() -> Div:
    """A list whose highlight any key moves down, which scrolls the highlighted item into view as it moves."""
    focus = use_focus(auto_focus=True)
    highlighted, set_highlighted = use_state(0)
    handle, _ = use_state(ElementHandle)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        set_highlighted(highlighted + 1)
        return ScrollIntoView(handle, block="nearest")

    return Div(
        style=col | size(8, 3) | overflow_y_scroll,
        on_input=on_input,
        children=tuple(
            Text(
                content=f"{'>' if i == highlighted and focus.is_focused else ' '}item {i}",
                handle=handle if i == highlighted else None,
            )
            for i in range(8)
        ),
    )


async def test_scroll_into_view_shows_in_the_same_frame_as_the_state_change_returned_beside_it() -> None:
    down = KeyPressed(key=Key.Down)

    (frame,) = await frames_of(highlighted_list(), (8, 3), [down, down, down])

    assert rows(frame) == [" item 1 ", " item 2 ", ">item 3 "]


@component
def focusable_item(name: str, handle: FocusHandle, auto_focus: bool = False) -> Text:
    focus = use_focus(handle=handle, auto_focus=auto_focus)
    return Text(content=f"{'>' if focus.is_focused else ' '}{name}")


FIELDS = tuple(FocusHandle() for _ in range(3))


def nested_fields(auto_focus: bool = False) -> Div:
    """Three focusable fields at the end of an inner scroll container, below an outer one's view."""
    inner = Div(
        style=col | size(8, 2) | shrink(0) | overflow_y_scroll,
        children=(
            *lines_of(4, "in"),
            *(focusable_item(f"f{i}", handle, auto_focus and i == 2) for i, handle in enumerate(FIELDS)),
        ),
    )
    return Div(
        style=col | size(8, 3) | overflow_y_scroll,
        children=(*lines_of(4, "out"), inner, *lines_of(2, "end")),
    )


async def test_focusing_an_element_scrolled_out_of_view_scrolls_it_into_view_through_nested_containers() -> None:
    assert await last_rows(nested_fields(), (8, 3), [FocusOn(FIELDS[1])]) == ["out 3   ", " f0     ", ">f1     "]


async def test_moving_focus_with_tab_scrolls_the_newly_focused_element_into_view() -> None:
    assert await last_rows(nested_fields(), (8, 3), [FocusNext(), FocusNext()]) == ["out 3   ", " f0     ", ">f1     "]


async def test_an_element_that_takes_focus_as_it_mounts_is_scrolled_into_view() -> None:
    assert await last_rows(nested_fields(auto_focus=True), (8, 3)) == ["out 3   ", " f1     ", ">f2     "]


@component
def revealing() -> Div:
    """`nested_fields`, which mounts on any key, with its last field taking focus as it mounts."""
    is_shown, set_shown = use_state(False)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        set_shown(True)
        return ()

    return Div(on_input=on_input, children=(nested_fields(auto_focus=True),) if is_shown else ())


async def test_an_element_that_takes_focus_as_it_mounts_after_startup_is_scrolled_into_view() -> None:
    assert await last_rows(revealing(), (8, 3), [KeyPressed(key="x")]) == ["out 3   ", " f1     ", ">f2     "]


@pytest.mark.parametrize(
    ("alignment", "offset", "expected"),
    [
        ("start", 0, 7),
        ("center", 0, 5),
        ("end", 0, 3),
        ("nearest", 0, 3),
        ("nearest", 9, 7),
        ("nearest", 5, 5),
    ],
    ids=["start", "center", "end", "nearest-cut-at-end", "nearest-cut-at-start", "nearest-in-view"],
)
def test_aligned_puts_a_box_that_fits_where_its_alignment_says(
    alignment: ScrollAlignment, offset: int, expected: int
) -> None:
    assert aligned(alignment, 8, 10, 1, 7, offset) == expected


@pytest.mark.parametrize(
    ("offset", "expected"),
    [(0, 8), (11, 10), (9, 9)],
    ids=["cut-at-end-aligns-the-start", "cut-at-start-aligns-the-end", "covering-the-view"],
)
def test_aligned_nearest_scrolls_least_for_a_box_larger_than_the_view(offset: int, expected: int) -> None:
    assert aligned("nearest", 9, 15, 1, 5, offset) == expected
