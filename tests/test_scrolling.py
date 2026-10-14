from __future__ import annotations

from collections.abc import Sequence

import pytest
import waxy

from counterweight.app import app, stale_scroll_readers
from counterweight.components import Component, component
from counterweight.controls import AnyControl, Quit, Screenshot, ScrollBy, ScrollTo
from counterweight.elements import AnyElement, Div, Text
from counterweight.events import (
    AnyEvent,
    InputEvent,
    InputResponse,
    KeyPressed,
    MouseDown,
    MouseScrolledDown,
    MouseScrolledRight,
    Receiver,
)
from counterweight.focus import ElementHandle, Subtree
from counterweight.geometry import ORIGIN, Position, Scroll
from counterweight.handlers import scroll_on_keys, scroll_on_wheel
from counterweight.hooks import use_focus, use_scroll, use_state
from counterweight.hooks.impls import NodeKey
from counterweight.keys import Key
from counterweight.layout import NO_LAYOUTS, Layouts, LayoutTree, PriorScroll, layout_changes
from counterweight.output import Frame
from counterweight.routing import RoutingTable, route_key
from counterweight.shadow import DuplicateElementHandle, update_shadow
from counterweight.styles import Style
from counterweight.styles.utilities import (
    border,
    border_light,
    clip_to_border,
    clip_to_screen,
    col,
    height,
    inset_left,
    inset_top,
    overflow_x_scroll,
    overflow_y_scroll,
    position_absolute,
    shrink,
    size,
    z,
)

# Marks where `frames_of` takes a screenshot in its autopilot, besides the one it takes at the end.
SHOT = Screenshot(handler=lambda frame: None)


async def frames_of(
    root: Component | AnyElement,
    dimensions: tuple[int, int],
    autopilot: Sequence[AnyEvent | AnyControl],
    check_purity: bool = True,
) -> list[Frame]:
    """The frames taken at each `SHOT` in `autopilot`, and once it ends, running `root` until then."""
    frames: list[Frame] = []

    @component
    def screen() -> AnyElement:
        return root  # type: ignore[return-value]

    await app(
        root if isinstance(root, Component) else screen(),
        headless=True,
        dimensions=dimensions,
        autopilot=[
            *(Screenshot(handler=frames.append) if event is SHOT else event for event in autopilot),
            Screenshot(handler=frames.append),
            Quit(),
        ],
        check_purity=check_purity,
    )
    return frames


def rows(frame: Frame) -> list[str]:
    return frame.text(ansi=False).split("\n")


async def last_rows(
    root: Component | AnyElement, dimensions: tuple[int, int], autopilot: Sequence[AnyEvent | AnyControl] = ()
) -> list[str]:
    return rows((await frames_of(root, dimensions, autopilot))[-1])


def lines(count: int, prefix: str = "line") -> tuple[Text, ...]:
    return tuple(Text(content=f"{prefix} {i}") for i in range(count))


HANDLE = ElementHandle()


def scrolled_to(offset: Position) -> PriorScroll:
    """A container scrolled to `offset` before a layout, with no anchor, and not at its end."""
    return PriorScroll(offset=offset, is_at_end_x=False, is_at_end_y=False, anchor=None)


def scroller(*children: Component | AnyElement, style: Style = Style(), handle: ElementHandle = HANDLE) -> Div:
    """A bordered box 8 wide and 4 tall that scrolls vertically, so 2 rows of its children are in view."""
    return Div(
        style=col | border | border_light | size(8, 4) | overflow_y_scroll | style,
        handle=handle,
        on_input=scroll_on_wheel(1),
        children=children,
    )


async def test_a_scrolled_container_paints_its_children_moved_up_by_its_offset_and_clipped_to_its_padding_box() -> None:
    root = Div(style=col, children=(scroller(*lines(6)), Text(content="below")))

    assert await last_rows(root, (8, 5), [ScrollTo(HANDLE, y=2)]) == [
        "┌──────┐",
        "│line 2│",
        "│line 3│",
        "└──────┘",
        "below   ",
    ]


async def test_a_container_that_scrolls_horizontally_moves_its_children_left_by_its_offset() -> None:
    wide = Text(content="abcdefghij", style=size(10, 1))
    container = Div(style=border | border_light | size(6, 3) | overflow_x_scroll, handle=HANDLE, children=(wide,))

    assert await last_rows(container, (6, 3), [ScrollTo(HANDLE, x=3)]) == ["┌────┐", "│defg│", "└────┘"]


def test_layout_reports_a_scrolled_containers_descendants_where_they_are_painted() -> None:
    child = Div(children=(Text(content="nested", style=size(6, 1)),), style=size(6, 1))
    container = Div(style=col | size(6, 2) | overflow_y_scroll, children=(*lines(2), child))
    shadow = update_shadow(container, None, NO_LAYOUTS).tree
    (first, second, nested_div) = shadow.root.children

    layouts = LayoutTree().compute(
        layout_changes(None, shadow), shadow, 6, 2, {shadow.root.key: scrolled_to(Position(0, 1))}
    )

    assert [layouts.by_key[node.key].border.top for node in (first, second, nested_div, nested_div.children[0])] == [
        -1,
        0,
        1,
        1,
    ]


async def test_a_press_on_a_scrolled_container_lands_on_the_child_painted_under_it() -> None:
    presses: list[str] = []

    def recording(name: str) -> Text:
        def handler(event: InputEvent, receiver: Receiver) -> InputResponse:
            presses.append(name)
            return ()

        return Text(content=name, on_input=handler)

    container = scroller(*(recording(f"item {i}") for i in range(6)))

    await frames_of(container, (8, 4), [ScrollTo(HANDLE, y=3), MouseDown(absolute=Position(2, 1), button=1)])

    assert presses == ["item 3"]


@component
def shrinking(start: int, handle: ElementHandle = HANDLE) -> Div:
    """A scroller of `start` lines that drops to 3 on any key, and whose root unmounts it on `u`."""
    count, set_count = use_state(start)
    is_mounted, set_mounted = use_state(True)

    def on_key(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key="u"):
                set_mounted(lambda mounted: not mounted)
            case _:
                set_count(3)
        return ()

    return Div(on_input=on_key, children=(scroller(*lines(count), handle=handle),) if is_mounted else ())


async def test_an_offset_is_clamped_when_the_content_shrinks() -> None:
    assert await last_rows(shrinking(8), (8, 4), [ScrollTo(HANDLE, y=100), KeyPressed(key="x")]) == [
        "┌──────┐",
        "│line 1│",
        "│line 2│",
        "└──────┘",
    ]


async def test_an_offset_is_dropped_when_its_container_unmounts() -> None:
    autopilot: list[AnyEvent | AnyControl] = [ScrollTo(HANDLE, y=3), KeyPressed(key="u"), KeyPressed(key="u")]

    assert (await last_rows(shrinking(8), (8, 4), autopilot))[1] == "│line 0│"


async def test_a_wheel_event_at_the_end_of_a_containers_range_scrolls_the_container_outside_it() -> None:
    inner_handle = ElementHandle()
    inner = Div(
        style=col | size(6, 2) | shrink(0) | overflow_y_scroll,
        handle=inner_handle,
        on_input=scroll_on_wheel(1),
        children=lines(3, "in"),
    )
    outer = Div(style=col | size(6, 3) | overflow_y_scroll, on_input=scroll_on_wheel(1), children=(inner, *lines(3)))
    wheel = MouseScrolledDown(absolute=Position(0, 0))

    assert await last_rows(outer, (6, 3), [ScrollTo(inner_handle, y=1), wheel]) == ["in 2  ", "line 0", "line 1"]


async def test_a_wheel_event_scrolls_the_container_under_the_pointer() -> None:
    root = Div(style=col, children=(scroller(*lines(6)), Text(content="below")))

    assert (await last_rows(root, (8, 5), [MouseScrolledDown(absolute=Position(2, 1))]))[1] == "│line 1│"


async def test_two_mounted_elements_with_the_same_handle_raise() -> None:
    with pytest.raises(DuplicateElementHandle):
        await frames_of(Div(children=(Div(handle=HANDLE), Text(content="", handle=HANDLE))), (4, 2), [])


async def test_a_control_naming_a_handle_on_no_mounted_element_does_nothing() -> None:
    root = Div(style=col, children=(scroller(*lines(6)), Text(content="below")))

    unscrolled = await last_rows(root, (8, 5))

    assert await last_rows(root, (8, 5), [ScrollTo(ElementHandle(), y=2), ScrollBy(ElementHandle(), y=2)]) == unscrolled


async def test_scroll_controls_compose_in_order() -> None:
    root = Div(style=col, children=(scroller(*lines(6)),))
    autopilot: list[AnyEvent | AnyControl] = [ScrollTo(HANDLE, y=3), ScrollBy(HANDLE, y=-2), ScrollBy(HANDLE, y=1)]

    assert (await last_rows(root, (8, 4), autopilot))[1] == "│line 2│"


def titled_panel(title: str) -> Div:
    return Div(
        style=border | border_light | height(3),
        children=(
            Text(content=title, style=position_absolute | inset_top(-1) | inset_left(1) | clip_to_border),
            Text(content="body"),
        ),
    )


async def test_a_titled_panel_scrolled_partly_out_of_view_loses_its_title_where_it_loses_its_border() -> None:
    panels = Div(
        style=col | size(8, 4) | overflow_y_scroll,
        handle=HANDLE,
        children=(titled_panel("one"), titled_panel("two")),
    )
    root = Div(style=col, children=(Text(content="above"), panels, Text(content="below")))

    assert await last_rows(root, (8, 6), [ScrollTo(HANDLE, y=1)]) == [
        "above   ",
        "│body  │",
        "└──────┘",
        "┌─two──┐",
        "│body  │",
        "below   ",
    ]


async def test_an_unclipped_element_moves_with_its_scroll_container() -> None:
    popup = Text(content="popup", style=z(1) | position_absolute | inset_top(1) | inset_left(2) | clip_to_screen)
    anchor = Div(children=(Text(content="anchor"), popup))
    container = Div(style=col | size(8, 2) | overflow_y_scroll, handle=HANDLE, children=(*lines(1, "top"), anchor))
    root = Div(style=col, children=(container, Text(content="12345678"), Text(content="abcdefgh")))

    unscrolled, scrolled = await frames_of(root, (8, 4), [SHOT, ScrollTo(HANDLE, y=1)])

    assert (rows(unscrolled), rows(scrolled)) == (
        ["top 0   ", "anchor  ", "12popup8", "abcdefgh"],
        ["anchor  ", "  popup ", "12345678", "abcdefgh"],
    )


async def test_an_absolutely_positioned_child_extends_how_far_its_container_scrolls() -> None:
    far = Text(content="far", style=position_absolute | inset_top(5) | inset_left(0))
    container = Div(style=col | size(6, 2) | overflow_y_scroll, handle=HANDLE, children=(Text(content="near"), far))

    assert await last_rows(container, (6, 2), [ScrollTo(HANDLE, y=100)]) == ["      ", "far   "]


@component
def counting(runs: list[str], name: str) -> Text:
    runs.append(name)
    return Text(content=name)


async def test_scrolling_does_not_rerun_components_that_do_not_read_where_they_are() -> None:
    runs: list[str] = []
    container = scroller(*(counting(runs, f"item {i}") for i in range(6)))

    await frames_of(container, (8, 4), [ScrollBy(HANDLE, y=1), ScrollBy(HANDLE, y=1)], check_purity=False)

    # Once for the warmup, and once on the first painted frame, which re-runs everything to start effects.
    assert runs.count("item 0") == 2


@component
def reporting(reports: list[Scroll] | None = None) -> Div:
    scroll = use_scroll()
    if reports is not None:
        reports.append(scroll)
    return Div(
        style=col | size(12, 3) | overflow_y_scroll,
        handle=HANDLE,
        children=(
            Text(content=f"{scroll.offset.y}/{scroll.max_offset.y} of {scroll.view_width}x{scroll.view_height}"),
            *lines(4),
        ),
    )


async def test_use_scroll_reports_the_offset_the_maximum_and_the_size_of_the_padding_box() -> None:
    assert (await last_rows(reporting(), (12, 3), [SHOT]))[0] == "0/2 of 12x3 "


async def test_a_component_that_calls_use_scroll_renders_again_once_it_has_scrolled() -> None:
    reports: list[Scroll] = []

    await frames_of(reporting(reports), (12, 3), [ScrollTo(HANDLE, y=1)], check_purity=False)

    assert [report.offset.y for report in reports] == [0, 0, 1]


async def test_use_scroll_reports_no_scroll_for_an_element_that_is_not_a_scroll_container() -> None:
    @component
    def plain() -> Text:
        scroll = use_scroll()
        return Text(content=f"{scroll.offset}/{scroll.max_offset} {scroll.view_width}")

    assert (await last_rows(plain(), (40, 1), [SHOT]))[0].strip() == f"{ORIGIN}/{ORIGIN} 0"


async def test_use_scroll_with_a_handle_reports_that_elements_scroll_once_it_has_scrolled() -> None:
    @component
    def beside() -> Div:
        scroll = use_scroll(HANDLE)
        return Div(style=col, children=(Text(content=f"{scroll.offset.y}/{scroll.max_offset.y}"), scroller(*lines(6))))

    assert (await last_rows(beside(), (8, 5), [ScrollTo(HANDLE, y=3), SHOT]))[0] == "3/4     "


async def test_use_scroll_reports_no_scroll_for_a_handle_on_no_mounted_element() -> None:
    @component
    def unnamed() -> Text:
        scroll = use_scroll(ElementHandle())
        return Text(content=f"{scroll.max_offset.y}")

    assert (await last_rows(Div(style=col, children=(unnamed(), scroller(*lines(6)))), (8, 5), [SHOT]))[0] == "0       "


OUTER = ElementHandle()


async def test_a_component_reading_two_scrolls_renders_again_once_either_has_scrolled() -> None:
    reports: list[tuple[int, int]] = []

    @component
    def both() -> Div:
        own = use_scroll()
        inner = use_scroll(HANDLE)
        reports.append((own.offset.y, inner.offset.y))
        return Div(
            style=col | size(8, 4) | overflow_y_scroll,
            handle=OUTER,
            children=(scroller(*lines(6), style=shrink(0)), *lines(2)),
        )

    await frames_of(both(), (8, 4), [ScrollTo(HANDLE, y=2), SHOT, ScrollTo(OUTER, y=1), SHOT], check_purity=False)

    assert reports[-1] == (1, 2)


async def test_a_receiver_carries_the_scroll_of_a_scroll_container_and_none_for_other_elements() -> None:
    scrolls: list[Scroll | None] = []

    def record(event: InputEvent, receiver: Receiver) -> None:
        scrolls.append(receiver.scroll)

    container = Div(style=col | size(6, 2) | overflow_y_scroll, handle=HANDLE, on_input=record, children=lines(3))
    root = Div(style=col, on_input=record, children=(container,))

    await frames_of(root, (6, 2), [ScrollTo(HANDLE, y=1), MouseDown(absolute=ORIGIN, button=1)])

    assert scrolls == [Scroll(offset=Position(0, 1), max_offset=Position(0, 1), view_width=6, view_height=2), None]


@component
def growing() -> Div:
    """A container 2 rows tall over 3 lines, where `a` adds a line and scrolls down a row, and `g` only adds one."""
    count, set_count = use_state(3)

    def on_key(event: InputEvent, receiver: Receiver) -> InputResponse:
        assert isinstance(event, KeyPressed)
        set_count(lambda c: c + 1)
        return ScrollBy(HANDLE, y=1) if event.key == "a" else ()

    return Div(
        style=col,
        on_input=on_key,
        children=(Div(style=col | size(6, 2) | overflow_y_scroll, handle=HANDLE, children=lines(count)),),
    )


async def test_a_scroll_returned_beside_a_state_change_scrolls_the_content_that_change_lays_out() -> None:
    autopilot: list[AnyEvent | AnyControl] = [ScrollTo(HANDLE, y=1), KeyPressed(key="a")]

    assert await last_rows(growing(), (6, 2), autopilot) == ["line 2", "line 3"]


async def test_a_scroll_that_moves_nothing_does_not_wait_to_move_a_later_layout() -> None:
    autopilot: list[AnyEvent | AnyControl] = [ScrollTo(HANDLE, y=1), ScrollBy(HANDLE, y=1), KeyPressed(key="g")]

    assert await last_rows(growing(), (6, 2), autopilot) == ["line 1", "line 2"]


def test_a_text_whose_overflow_is_scroll_raises() -> None:
    shadow = update_shadow(Text(content="x", style=overflow_y_scroll), None, NO_LAYOUTS).tree

    with pytest.raises(ValueError, match="Text doesn't scroll"):
        LayoutTree().compute(layout_changes(None, shadow), shadow, 4, 2, {})


def scroll_of_root(container: Div, offset: Position = ORIGIN) -> Scroll:
    shadow = update_shadow(container, None, NO_LAYOUTS).tree
    layouts = LayoutTree().compute(layout_changes(None, shadow), shadow, 10, 10, {shadow.root.key: scrolled_to(offset)})
    return layouts.scrolls[shadow.root.key]


def test_a_container_cannot_scroll_on_an_axis_whose_overflow_is_not_scroll() -> None:
    wide_and_tall = Text(content="\n".join(["abcdefgh"] * 6), style=size(8, 6))

    scroll = scroll_of_root(Div(style=size(4, 3) | overflow_y_scroll, children=(wide_and_tall,)), Position(2, 2))

    assert (scroll.offset, scroll.max_offset) == (Position(0, 2), Position(0, 3))


def test_a_container_that_scrolls_only_horizontally_cannot_scroll_vertically() -> None:
    wide_and_tall = Text(content="\n".join(["abcdefgh"] * 6), style=size(8, 6))

    scroll = scroll_of_root(Div(style=size(4, 3) | overflow_x_scroll, children=(wide_and_tall,)), Position(2, 2))

    assert (scroll.offset, scroll.max_offset) == (Position(2, 0), Position(4, 0))


def test_nested_horizontal_scroll_containers_move_their_content_by_the_sum_of_their_offsets() -> None:
    wide = Text(content="abcdefghij", style=size(10, 1))
    inner = Div(style=size(6, 1) | shrink(0) | overflow_x_scroll, children=(wide,))
    outer = Div(style=size(4, 1) | overflow_x_scroll, children=(inner,))
    shadow = update_shadow(outer, None, NO_LAYOUTS).tree
    inner_node = shadow.root.children[0]
    priors = {shadow.root.key: scrolled_to(Position(1, 0)), inner_node.key: scrolled_to(Position(2, 0))}

    layouts = LayoutTree().compute(layout_changes(None, shadow), shadow, 4, 1, priors)

    assert layouts.by_key[inner_node.children[0].key].border.left == -3


def test_the_view_excludes_the_space_a_scrollbar_width_reserves() -> None:
    reserved = Style(layout=waxy.Style(scrollbar_width=2))

    scroll = scroll_of_root(Div(style=border | size(10, 5) | overflow_y_scroll | reserved, children=lines(8)))

    assert (scroll.view_width, scroll.view_height) == (6, 3)


@pytest.mark.parametrize(
    ("offset", "expected"),
    [(Position(-1, 9), Position(0, 4)), (Position(5, -3), Position(2, 0)), (Position(1, 2), Position(1, 2))],
)
def test_clamp_moves_an_offset_onto_the_range_on_each_axis(offset: Position, expected: Position) -> None:
    scroll = Scroll(offset=ORIGIN, max_offset=Position(2, 4), view_width=3, view_height=5)

    assert scroll.clamp(offset) == expected


@pytest.mark.parametrize(
    ("control", "expected"),
    [
        (ScrollTo(HANDLE, x=4), Position(4, 7)),
        (ScrollTo(HANDLE, y=1), Position(3, 1)),
        (ScrollTo(HANDLE, x=0, y=0), ORIGIN),
        (ScrollTo(HANDLE), Position(3, 7)),
        (ScrollBy(HANDLE, x=2), Position(5, 7)),
        (ScrollBy(HANDLE, y=-3), Position(3, 4)),
    ],
)
def test_a_scroll_controls_destination(control: ScrollTo | ScrollBy, expected: Position) -> None:
    assert control.destination(Position(3, 7)) == expected


KEY = NodeKey(5)
SCROLLS = {KEY: Scroll(offset=Position(0, 2), max_offset=Position(0, 4), view_width=3, view_height=2)}


def scrolled_table(root: AnyElement, priors: dict[int, PriorScroll], width: int, height: int) -> RoutingTable:
    """
    The routing table of `root`, under a screen element, on a `width` by `height` screen,
    with the nodes at those pre-order indexes scrolled, where the screen element is node 0 and `root` node 1.
    """
    shadow = update_shadow(Div(children=(root,)), None, NO_LAYOUTS).tree
    by_index = {shadow.nodes[index].key: prior for index, prior in priors.items()}
    return RoutingTable.of(shadow, LayoutTree().compute(layout_changes(None, shadow), shadow, width, height, by_index))


# A container 2 rows tall, scrolled 2 rows into the 4 it can scroll, under the root.
SCROLLED_TABLE = scrolled_table(
    Div(children=(Div(style=col | size(6, 2) | overflow_y_scroll, handle=HANDLE, children=lines(6)),)),
    {2: scrolled_to(Position(0, 2))},
    6,
    3,
)


def test_scrolled_moves_the_named_container_within_its_range() -> None:
    key = SCROLLED_TABLE.key_of(HANDLE)
    assert key is not None

    assert SCROLLED_TABLE.scrolled(ScrollBy(HANDLE, y=5)).scrolls[key].offset == Position(0, 4)


@pytest.mark.parametrize(
    "control",
    [
        ScrollBy(HANDLE, x=3),
        ScrollTo(HANDLE, y=2),
        ScrollBy(ElementHandle(), y=1),
        ScrollBy(Subtree(key=SCROLLED_TABLE.root), y=1),
    ],
    ids=["clamped-back", "same-offset", "unmounted-handle", "not-a-scroll-container"],
)
def test_scrolled_is_the_same_table_when_nothing_moves(control: ScrollTo | ScrollBy) -> None:
    assert SCROLLED_TABLE.scrolled(control) is SCROLLED_TABLE


def test_a_key_bubbles_once_an_earlier_control_in_its_batch_scrolls_its_container_to_the_end() -> None:
    inner = Div(style=col | size(6, 2) | shrink(0) | overflow_y_scroll, on_input=scroll_on_keys(), children=lines(4))
    outer = Div(style=col | size(6, 2) | overflow_y_scroll, on_input=scroll_on_keys(), children=(inner, *lines(2)))
    # The outer container is the root, and the inner one 1 row short of its end.
    table = scrolled_table(outer, {2: scrolled_to(Position(0, 1))}, 6, 2)
    outer_key, inner_key = table.root, table.layouts.scroll_containers[1].key

    (moved,) = route_key(KeyPressed(key=Key.Down), inner_key, table)
    assert isinstance(moved, ScrollBy)

    assert route_key(KeyPressed(key=Key.Down), inner_key, table.scrolled(moved)) == (
        ScrollBy(Subtree(key=outer_key), y=1),
    )


def test_stale_scroll_readers_are_the_nodes_whose_scroll_changed() -> None:
    @component
    def reads() -> Div:
        use_scroll()
        return Div(style=overflow_y_scroll)

    shadow = update_shadow(Div(children=(reads(), Div(), reads())), None, NO_LAYOUTS).tree
    _, _, third = shadow.root.children
    moved = Layouts(in_paint_order=(), by_key={}, scrolls={third.key: SCROLLS[KEY]})

    assert (list(stale_scroll_readers(shadow, NO_LAYOUTS)), list(stale_scroll_readers(shadow, moved))) == (
        [],
        [third.key],
    )


def test_key_of_names_the_element_a_handle_or_subtree_names() -> None:
    other = ElementHandle()
    shadow = update_shadow(Div(children=(Div(children=(Div(handle=HANDLE),)),)), None, NO_LAYOUTS).tree
    layouts = LayoutTree().compute(layout_changes(None, shadow), shadow, 4, 2, {})
    table = RoutingTable.of(shadow, layouts)
    handled = shadow.root.children[0].children[0]

    assert (table.key_of(HANDLE), table.key_of(other), table.key_of(Subtree(key=NodeKey(9)))) == (
        handled.key,
        None,
        NodeKey(9),
    )


def test_an_element_handle_is_named_by_its_identity() -> None:
    handle = ElementHandle()

    assert (handle == ElementHandle(), repr(handle)) == (False, f"<ElementHandle at {id(handle):#x}>")


async def test_a_wheel_event_to_the_right_scrolls_a_container_horizontally() -> None:
    wide = Text(content="abcdefghij", style=size(10, 1))
    container = Div(style=size(4, 1) | overflow_x_scroll, on_input=scroll_on_wheel(2), children=(wide,))

    assert await last_rows(container, (4, 1), [MouseScrolledRight(absolute=ORIGIN)]) == ["cdef"]


async def test_a_wheel_event_down_with_shift_held_scrolls_a_container_to_the_right() -> None:
    wide = Text(content="abcdefghij", style=size(10, 1))
    container = Div(style=size(4, 1) | overflow_x_scroll, on_input=scroll_on_wheel(2), children=(wide,))

    assert await last_rows(container, (4, 1), [MouseScrolledDown(absolute=ORIGIN, is_shift_held=True)]) == ["cdef"]


@component
def keyed_scroller(*children: Component | AnyElement) -> Div:
    """A focusable box 6 wide and 4 tall that the keys scroll vertically, and that takes focus as it mounts."""
    use_focus(auto_focus=True)
    return Div(
        style=col | size(6, 4) | shrink(0) | overflow_y_scroll,
        on_input=scroll_on_keys(),
        children=children,
    )


async def test_page_down_clamps_at_the_end_of_the_range() -> None:
    page_down = KeyPressed(key=Key.PageDown)

    assert await last_rows(keyed_scroller(*lines(9)), (6, 4), [page_down, page_down]) == [
        "line 5",
        "line 6",
        "line 7",
        "line 8",
    ]


async def test_a_key_at_the_end_of_a_containers_range_scrolls_the_container_outside_it() -> None:
    outer = Div(
        style=col | size(6, 4) | overflow_y_scroll,
        on_input=scroll_on_keys(),
        children=(keyed_scroller(*lines(5, "in")), *lines(2)),
    )
    down = KeyPressed(key=Key.Down)

    assert await last_rows(outer, (6, 4), [down, down]) == ["in 2  ", "in 3  ", "in 4  ", "line 0"]
