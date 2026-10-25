from dataclasses import replace

import pytest

from counterweight.controls import Bell
from counterweight.controls import ClearFocus
from counterweight.controls import FocusNext
from counterweight.controls import FocusOn
from counterweight.controls import FocusPrevious
from counterweight.controls import Quit
from counterweight.controls import ScrollBy
from counterweight.controls import ScrollTo
from counterweight.controls import ToggleBorderHealing
from counterweight.events import InputEvent
from counterweight.events import InputHandler
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseMoved
from counterweight.events import MouseScrolledDown
from counterweight.events import MouseScrolledLeft
from counterweight.events import MouseScrolledRight
from counterweight.events import MouseScrolledUp
from counterweight.events import MouseUp
from counterweight.events import Receiver
from counterweight.focus import ElementHandle
from counterweight.focus import FocusHandle
from counterweight.focus import Subtree
from counterweight.geometry import Position
from counterweight.geometry import Rects
from counterweight.geometry import Region
from counterweight.geometry import Scroll
from counterweight.handlers import clear_focus
from counterweight.handlers import each
from counterweight.handlers import first
from counterweight.handlers import focus_on_press
from counterweight.handlers import focus_receiver_on_press
from counterweight.handlers import on_click
from counterweight.handlers import page_down
from counterweight.handlers import page_up
from counterweight.handlers import scroll_on_keys
from counterweight.handlers import scroll_on_wheel
from counterweight.handlers import tab_focus
from counterweight.keys import Key

BORDER = Region(left=2, top=1, right=7, bottom=4)
RECEIVER = Receiver(
    rects=Rects(
        content=BORDER,
        padding=BORDER,
        border=BORDER,
        margin=BORDER,
        clip=Region(left=0, top=0, right=20, bottom=10),
        visible=BORDER,
        screen=Region(left=0, top=0, right=20, bottom=10),
    ),
    is_target=True,
    focus_handle=None,
    is_focused=False,
    subtree=Subtree(),
    scroll=None,
)
KEY = KeyPressed(key="k")
INSIDE = Position(3, 2)
OUTSIDE = Position(10, 2)


def responding(response: InputResponse, calls: list[str] | None = None, name: str = "") -> InputHandler:
    def handler(event: InputEvent, receiver: Receiver) -> InputResponse:
        if calls is not None:
            calls.append(name)
        return response

    return handler


def test_first_returns_the_first_response_that_is_not_none() -> None:
    assert first(responding(None), responding(Quit()), responding(Bell()))(KEY, RECEIVER) == Quit()


def test_first_stops_at_an_empty_tuple() -> None:
    calls: list[str] = []

    response = first(responding((), calls, "a"), responding(Quit(), calls, "b"))(KEY, RECEIVER)

    assert (response, calls) == ((), ["a"])


def test_first_returns_none_when_no_handler_responds() -> None:
    assert first(responding(None), responding(None))(KEY, RECEIVER) is None


def test_each_calls_every_handler_and_collects_their_controls_in_order() -> None:
    calls: list[str] = []

    response = each(
        responding(Quit(), calls, "a"),
        responding(None, calls, "b"),
        responding((Bell(), ToggleBorderHealing()), calls, "c"),
    )(KEY, RECEIVER)

    assert (response, calls) == ((Quit(), Bell(), ToggleBorderHealing()), ["a", "b", "c"])


def test_each_returns_an_empty_tuple_when_every_response_is_an_empty_tuple() -> None:
    assert each(responding(()), responding(()))(KEY, RECEIVER) == ()


def test_each_returns_none_when_no_handler_responds() -> None:
    assert each(responding(None), responding(None))(KEY, RECEIVER) is None


def test_each_skips_a_none_inside_a_handlers_tuple() -> None:
    assert each(responding((None, Quit())), responding((Bell(), None)))(KEY, RECEIVER) == (Quit(), Bell())


@pytest.mark.parametrize(
    "event",
    [MouseDown(absolute=INSIDE, button=1), MouseMoved(absolute=OUTSIDE, button=1)],
    ids=["press", "held move"],
)
def test_on_click_claims_the_press(event: InputEvent) -> None:
    clicks: list[str] = []

    assert (on_click(lambda: clicks.append("click"))(event, RECEIVER), clicks) == ((), [])


@pytest.mark.parametrize(
    "event",
    [KeyPressed(key="k"), MouseMoved(absolute=INSIDE, button=None), MouseDown(absolute=INSIDE, button=3)],
    ids=["key", "move with no button held", "other button"],
)
def test_on_click_does_not_handle_other_events(event: InputEvent) -> None:
    assert on_click(lambda: None)(event, RECEIVER) is None


def test_on_click_calls_its_action_for_a_release_inside_the_element() -> None:
    clicks: list[str] = []

    on_click(lambda: clicks.append("click"))(MouseUp(absolute=INSIDE, button=1), RECEIVER)

    assert clicks == ["click"]


def test_on_click_does_not_call_its_action_for_a_release_outside_the_element() -> None:
    clicks: list[str] = []

    response = on_click(lambda: clicks.append("click"))(MouseUp(absolute=OUTSIDE, button=1), RECEIVER)

    assert (response, clicks) == ((), [])


@pytest.mark.parametrize(
    "visible",
    [Region(left=2, top=1, right=3, bottom=4), None],
    ids=["clipped-at-the-release", "clipped-away-entirely"],
)
def test_on_click_does_not_call_its_action_for_a_release_inside_the_border_box_where_it_is_clipped_away(
    visible: Region | None,
) -> None:
    clicks: list[str] = []
    clipped = replace(RECEIVER, rects=replace(RECEIVER.rects, clip=visible, visible=visible))

    response = on_click(lambda: clicks.append("click"))(MouseUp(absolute=INSIDE, button=1), clipped)

    assert (response, clicks) == ((), [])


@pytest.mark.parametrize("action_response", [Quit(), (Quit(), Bell())], ids=["control", "tuple"])
def test_on_click_returns_its_actions_controls(action_response: InputResponse) -> None:
    assert on_click(lambda: action_response)(MouseUp(absolute=INSIDE, button=1), RECEIVER) == action_response


def test_on_click_returns_an_empty_tuple_when_its_action_returns_none() -> None:
    assert on_click(lambda: None)(MouseUp(absolute=INSIDE, button=1), RECEIVER) == ()


def test_tab_focus_moves_to_the_next_focusable_within_the_receivers_subtree_for_tab() -> None:
    assert tab_focus(KeyPressed(key=Key.Tab), RECEIVER) == FocusNext(within=RECEIVER.subtree)


def test_tab_focus_moves_to_the_previous_focusable_within_the_receivers_subtree_for_shift_tab() -> None:
    assert tab_focus(KeyPressed(key=Key.BackTab), RECEIVER) == FocusPrevious(within=RECEIVER.subtree)


@pytest.mark.parametrize(
    "event", [KeyPressed(key=Key.Enter), MouseDown(absolute=INSIDE, button=1)], ids=["other key", "press"]
)
def test_tab_focus_does_not_handle_other_events(event: InputEvent) -> None:
    assert tab_focus(event, RECEIVER) is None


@pytest.mark.parametrize("button", [1, 3])
def test_focus_receiver_on_press_focuses_the_receivers_handle(button: int) -> None:
    handle = FocusHandle()

    response = focus_receiver_on_press(
        MouseDown(absolute=INSIDE, button=button), replace(RECEIVER, focus_handle=handle)
    )

    assert response == FocusOn(handle)


def test_focus_receiver_on_press_raises_for_a_receiver_without_a_focus_handle() -> None:
    with pytest.raises(ValueError, match="isn't focusable"):
        focus_receiver_on_press(MouseDown(absolute=INSIDE, button=1), RECEIVER)


@pytest.mark.parametrize(
    "event",
    [KeyPressed(key="k"), MouseUp(absolute=INSIDE, button=1), MouseScrolledDown(absolute=INSIDE)],
    ids=["key", "release", "wheel"],
)
def test_focus_receiver_on_press_does_not_handle_other_events(event: InputEvent) -> None:
    assert focus_receiver_on_press(event, replace(RECEIVER, focus_handle=FocusHandle())) is None


@pytest.mark.parametrize("receiver_handle", [None, FocusHandle()], ids=["unfocusable receiver", "focusable receiver"])
def test_focus_on_press_focuses_its_handle_whatever_the_receivers_handle(receiver_handle: FocusHandle | None) -> None:
    handle = FocusHandle()

    response = focus_on_press(handle)(
        MouseDown(absolute=INSIDE, button=1), replace(RECEIVER, focus_handle=receiver_handle)
    )

    assert response == FocusOn(handle)


@pytest.mark.parametrize("event", [KeyPressed(key="k"), MouseUp(absolute=INSIDE, button=1)], ids=["key", "release"])
def test_focus_on_press_does_not_handle_other_events(event: InputEvent) -> None:
    assert focus_on_press(FocusHandle())(event, RECEIVER) is None


def test_clear_focus_clears_focus_for_a_press() -> None:
    assert clear_focus(MouseDown(absolute=INSIDE, button=1), RECEIVER) == ClearFocus()


@pytest.mark.parametrize("event", [KeyPressed(key="k"), MouseUp(absolute=INSIDE, button=1)], ids=["key", "release"])
def test_clear_focus_does_not_handle_other_events(event: InputEvent) -> None:
    assert clear_focus(event, RECEIVER) is None


SCROLLED = replace(
    RECEIVER, scroll=Scroll(offset=Position(4, 3), max_offset=Position(9, 8), view_width=5, view_height=3)
)


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        (MouseScrolledUp(absolute=INSIDE), ScrollBy(SCROLLED.subtree, y=-2)),
        (MouseScrolledDown(absolute=INSIDE), ScrollBy(SCROLLED.subtree, y=2)),
        (MouseScrolledLeft(absolute=INSIDE), ScrollBy(SCROLLED.subtree, x=-2)),
        (MouseScrolledRight(absolute=INSIDE), ScrollBy(SCROLLED.subtree, x=2)),
    ],
    ids=["up", "down", "left", "right"],
)
def test_scroll_on_wheel_scrolls_its_receiver_by_its_lines_toward_the_wheel(
    event: InputEvent, expected: ScrollBy
) -> None:
    assert scroll_on_wheel(2)(event, SCROLLED) == expected


@pytest.mark.parametrize(
    ("event", "offset"),
    [
        (MouseScrolledUp(absolute=INSIDE), Position(4, 0)),
        (MouseScrolledDown(absolute=INSIDE), Position(4, 8)),
        (MouseScrolledLeft(absolute=INSIDE), Position(0, 3)),
        (MouseScrolledRight(absolute=INSIDE), Position(9, 3)),
    ],
    ids=["up", "down", "left", "right"],
)
def test_scroll_on_wheel_does_not_handle_a_wheel_event_past_the_end_of_the_range(
    event: InputEvent, offset: Position
) -> None:
    assert SCROLLED.scroll is not None
    at_end = replace(SCROLLED, scroll=replace(SCROLLED.scroll, offset=offset))

    assert scroll_on_wheel(2)(event, at_end) is None


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        (MouseScrolledUp(absolute=INSIDE, is_shift_held=True), ScrollBy(SCROLLED.subtree, x=-2)),
        (MouseScrolledDown(absolute=INSIDE, is_shift_held=True), ScrollBy(SCROLLED.subtree, x=2)),
        (MouseScrolledLeft(absolute=INSIDE, is_shift_held=True), ScrollBy(SCROLLED.subtree, x=-2)),
        (MouseScrolledRight(absolute=INSIDE, is_shift_held=True), ScrollBy(SCROLLED.subtree, x=2)),
    ],
    ids=["up", "down", "left", "right"],
)
def test_scroll_on_wheel_scrolls_sideways_for_the_vertical_wheel_with_shift_held(
    event: InputEvent, expected: ScrollBy
) -> None:
    assert scroll_on_wheel(2)(event, SCROLLED) == expected


@pytest.mark.parametrize(
    "event",
    [
        MouseScrolledDown(absolute=INSIDE, is_alt_held=True),
        MouseScrolledDown(absolute=INSIDE, is_control_held=True),
    ],
    ids=["alt", "control"],
)
def test_scroll_on_wheel_scrolls_vertically_for_the_vertical_wheel_with_other_modifiers_held(
    event: InputEvent,
) -> None:
    assert scroll_on_wheel(2)(event, SCROLLED) == ScrollBy(SCROLLED.subtree, y=2)


@pytest.mark.parametrize(
    ("event", "offset"),
    [
        (MouseScrolledUp(absolute=INSIDE, is_shift_held=True), Position(0, 3)),
        (MouseScrolledDown(absolute=INSIDE, is_shift_held=True), Position(9, 3)),
    ],
    ids=["up", "down"],
)
def test_scroll_on_wheel_does_not_handle_a_shifted_wheel_event_past_the_sideways_end_of_the_range(
    event: InputEvent, offset: Position
) -> None:
    assert SCROLLED.scroll is not None
    at_end = replace(SCROLLED, scroll=replace(SCROLLED.scroll, offset=offset))

    assert scroll_on_wheel(2)(event, at_end) is None


def test_scroll_on_wheel_scrolls_three_lines_by_default() -> None:
    assert scroll_on_wheel()(MouseScrolledDown(absolute=INSIDE), SCROLLED) == ScrollBy(SCROLLED.subtree, y=3)


def test_scroll_on_wheel_raises_for_a_wheel_event_on_a_receiver_that_is_not_a_scroll_container() -> None:
    with pytest.raises(ValueError, match="isn't a scroll container"):
        scroll_on_wheel()(MouseScrolledDown(absolute=INSIDE), RECEIVER)


@pytest.mark.parametrize("event", [KEY, MouseDown(absolute=INSIDE, button=1)])
def test_scroll_on_wheel_does_not_handle_other_events(event: InputEvent) -> None:
    assert scroll_on_wheel()(event, SCROLLED) is None


TALL = replace(
    RECEIVER, scroll=Scroll(offset=Position(4, 30), max_offset=Position(9, 80), view_width=5, view_height=24)
)


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        (Key.Up, ScrollBy(TALL.subtree, y=-1)),
        (Key.Down, ScrollBy(TALL.subtree, y=1)),
        (Key.Left, ScrollBy(TALL.subtree, x=-1)),
        (Key.Right, ScrollBy(TALL.subtree, x=1)),
        (Key.PageUp, ScrollBy(TALL.subtree, y=-12)),
        (Key.PageDown, ScrollBy(TALL.subtree, y=12)),
        (Key.Home, ScrollTo(TALL.subtree, y=0)),
        (Key.End, ScrollTo(TALL.subtree, y=80)),
    ],
    ids=["up", "down", "left", "right", "page up", "page down", "home", "end"],
)
def test_scroll_on_keys_scrolls_its_receiver_for_each_scrolling_key(key: str, expected: ScrollBy | ScrollTo) -> None:
    assert scroll_on_keys(page=0.5)(KeyPressed(key=key), TALL) == expected


@pytest.mark.parametrize(
    ("key", "offset"),
    [
        (Key.Up, Position(4, 0)),
        (Key.Down, Position(4, 80)),
        (Key.Left, Position(0, 30)),
        (Key.Right, Position(9, 30)),
        (Key.PageUp, Position(4, 0)),
        (Key.PageDown, Position(4, 80)),
        (Key.Home, Position(4, 0)),
        (Key.End, Position(4, 80)),
    ],
    ids=["up", "down", "left", "right", "page up", "page down", "home", "end"],
)
def test_scroll_on_keys_does_not_handle_a_key_past_the_end_of_the_range(key: str, offset: Position) -> None:
    assert TALL.scroll is not None
    at_end = replace(TALL, scroll=replace(TALL.scroll, offset=offset))

    assert scroll_on_keys()(KeyPressed(key=key), at_end) is None


def test_scroll_on_keys_pages_by_seven_eighths_of_the_view_by_default() -> None:
    assert scroll_on_keys()(KeyPressed(key=Key.PageDown), TALL) == ScrollBy(TALL.subtree, y=21)


def test_scroll_on_keys_raises_for_a_scrolling_key_on_a_receiver_that_is_not_a_scroll_container() -> None:
    with pytest.raises(ValueError, match="isn't a scroll container"):
        scroll_on_keys()(KeyPressed(key=Key.Down), RECEIVER)


@pytest.mark.parametrize("event", [KEY, KeyPressed(key=Key.Enter), MouseScrolledDown(absolute=INSIDE)])
def test_scroll_on_keys_does_not_handle_other_events(event: InputEvent) -> None:
    assert scroll_on_keys()(event, RECEIVER) is None


@pytest.mark.parametrize(
    ("fraction", "rows"), [(0.875, 21), (0.5, 12), (1.0, 24), (0.01, 1)], ids=["chrome", "half", "whole", "tiny"]
)
def test_page_down_scrolls_down_by_a_fraction_of_the_view_rounded_down_and_at_least_one_row(
    fraction: float, rows: int
) -> None:
    assert TALL.scroll is not None
    handle = ElementHandle()

    assert page_down(handle, TALL.scroll, fraction) == ScrollBy(handle, y=rows)


def test_page_up_scrolls_up_by_as_much_as_page_down_scrolls_down() -> None:
    assert TALL.scroll is not None

    assert page_up(TALL.subtree, TALL.scroll, 0.5) == ScrollBy(TALL.subtree, y=-12)


@pytest.mark.parametrize("fraction", [0.0, -0.5])
def test_a_page_that_is_not_a_positive_fraction_raises(fraction: float) -> None:
    assert TALL.scroll is not None

    with pytest.raises(ValueError, match="positive fraction"):
        page_down(TALL.subtree, TALL.scroll, fraction)


def test_scroll_on_keys_with_a_page_that_is_not_a_positive_fraction_raises_before_any_key() -> None:
    with pytest.raises(ValueError, match="positive fraction"):
        scroll_on_keys(page=0.0)
