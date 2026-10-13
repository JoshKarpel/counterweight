import pytest

from counterweight.controls import Bell, Quit, ToggleBorderHealing
from counterweight.events import (
    InputEvent,
    InputHandler,
    InputResponse,
    KeyPressed,
    MouseDown,
    MouseMoved,
    MouseUp,
    Receiver,
)
from counterweight.geometry import Position, Rects, Region
from counterweight.handlers import each, first, on_click

BORDER = Region(left=2, top=1, right=7, bottom=4)
RECEIVER = Receiver(rects=Rects(content=BORDER, padding=BORDER, border=BORDER, margin=BORDER), is_target=True)
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
