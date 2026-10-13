from dataclasses import replace

import pytest

from counterweight.controls import Bell, ClearFocus, FocusNext, FocusOn, FocusPrevious, Quit, ToggleBorderHealing
from counterweight.events import (
    InputEvent,
    InputHandler,
    InputResponse,
    KeyPressed,
    MouseDown,
    MouseMoved,
    MouseScrolledDown,
    MouseUp,
    Receiver,
)
from counterweight.focus import FocusHandle, Subtree
from counterweight.geometry import Position, Rects, Region
from counterweight.handlers import (
    clear_focus,
    each,
    first,
    focus_on_press,
    focus_receiver_on_press,
    on_click,
    tab_focus,
)
from counterweight.hooks.impls import NodeKey
from counterweight.keys import Key

BORDER = Region(left=2, top=1, right=7, bottom=4)
RECEIVER = Receiver(
    rects=Rects(content=BORDER, padding=BORDER, border=BORDER, margin=BORDER),
    is_target=True,
    focus_handle=None,
    is_focused=False,
    subtree=Subtree(key=NodeKey(7)),
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
