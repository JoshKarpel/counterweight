from collections.abc import Sequence
from dataclasses import dataclass

import pytest

from counterweight import app
from counterweight.components import Component, component
from counterweight.controls import AnyControl, Quit, Screenshot
from counterweight.elements import Div, Text
from counterweight.events import (
    InputEvent,
    InputHandler,
    InputResponse,
    MouseDown,
    MouseMoved,
    MouseScrolledDown,
    MouseScrolledLeft,
    MouseScrolledRight,
    MouseScrolledUp,
    MouseUp,
    Receiver,
)
from counterweight.geometry import Position, Rects, Region
from counterweight.handlers import each, on_click
from counterweight.hooks import use_state
from counterweight.output import Frame
from counterweight.styles import Style
from counterweight.styles.utilities import (
    inset_left,
    inset_top,
    margin,
    margin_color,
    position_absolute,
    size,
    z,
)


@dataclass(frozen=True, slots=True)
class Delivery:
    name: str
    event: InputEvent
    is_target: bool


def recording(name: str, deliveries: list[Delivery], response: InputResponse = None) -> InputHandler:
    def handler(event: InputEvent, receiver: Receiver) -> InputResponse:
        deliveries.append(Delivery(name=name, event=event, is_target=receiver.is_target))
        return response

    return handler


def names(deliveries: Sequence[Delivery]) -> list[str]:
    return [delivery.name for delivery in deliveries]


def box(x: int, y: int, w: int, h: int) -> Style:
    return position_absolute | inset_left(x) | inset_top(y) | size(w, h)


def click(x: int, y: int) -> tuple[MouseDown, MouseUp]:
    return MouseDown(absolute=Position(x, y), button=1), MouseUp(absolute=Position(x, y), button=1)


def held(x: int, y: int) -> MouseMoved:
    return MouseMoved(absolute=Position(x, y), button=1)


async def run(root: Component, autopilot: Sequence[InputEvent | AnyControl]) -> None:
    await app(root, headless=True, dimensions=(20, 10), autopilot=(*autopilot, Quit()), check_purity=True)


def parent_and_child(deliveries: list[Delivery], child_response: InputResponse) -> Component:
    @component
    def root() -> Div:
        return Div(
            style=size(20, 10),
            on_input=recording("parent", deliveries),
            children=[Div(style=box(2, 1, 5, 3), on_input=recording("child", deliveries, child_response))],
        )

    return root()


async def test_of_two_overlapping_siblings_only_the_topmost_receives_a_click() -> None:
    deliveries: list[Delivery] = []

    @component
    def root() -> Div:
        return Div(
            style=size(20, 10),
            children=[
                Div(style=box(0, 0, 5, 5), on_input=recording("below", deliveries, ())),
                Div(style=box(2, 2, 5, 5), on_input=recording("above", deliveries, ())),
            ],
        )

    await run(root(), click(3, 3))

    assert names(deliveries) == ["above", "above"]


async def test_a_sibling_raised_with_z_receives_a_click_over_a_later_sibling() -> None:
    deliveries: list[Delivery] = []

    @component
    def root() -> Div:
        return Div(
            style=size(20, 10),
            children=[
                Div(style=box(0, 0, 5, 5) | z(1), on_input=recording("raised", deliveries, ())),
                Div(style=box(2, 2, 5, 5), on_input=recording("later", deliveries, ())),
            ],
        )

    await run(root(), click(3, 3))

    assert names(deliveries) == ["raised", "raised"]


async def test_a_child_of_an_element_raised_with_z_receives_a_click_over_its_parent() -> None:
    deliveries: list[Delivery] = []

    @component
    def root() -> Div:
        return Div(
            style=size(20, 10),
            children=[
                Div(
                    style=box(0, 0, 10, 10) | z(1),
                    on_input=recording("parent", deliveries),
                    children=[Div(style=box(1, 1, 3, 3), on_input=recording("child", deliveries))],
                )
            ],
        )

    await run(root(), [MouseScrolledDown(absolute=Position(2, 2))])

    assert [(delivery.name, delivery.is_target) for delivery in deliveries] == [("child", True), ("parent", False)]


@pytest.mark.parametrize("position", [Position(10, 8), Position(30, 20)], ids=["inside the terminal", "outside it"])
async def test_a_pointer_outside_the_root_components_element_targets_the_root(position: Position) -> None:
    receivers: list[Receiver] = []

    @component
    def root() -> Div:
        return Div(style=size(5, 5), on_input=lambda _, receiver: receivers.append(receiver))

    await run(root(), [MouseScrolledDown(absolute=position)])

    assert [(receiver.is_target, receiver.rects.border) for receiver in receivers] == [
        (True, Region(left=0, top=0, right=5, bottom=5))
    ]


@pytest.mark.parametrize("child_style", [margin(1), margin(1) | margin_color("red", 600)], ids=["plain", "colored"])
async def test_a_press_in_a_childs_margin_targets_what_lies_beneath_it(child_style: Style) -> None:
    deliveries: list[Delivery] = []

    @component
    def root() -> Div:
        return Div(
            style=size(20, 10),
            on_input=recording("parent", deliveries, ()),
            children=[Div(style=box(2, 1, 5, 3) | child_style, on_input=recording("child", deliveries, ()))],
        )

    await run(root(), click(2, 1))

    assert [(delivery.name, delivery.is_target) for delivery in deliveries] == [("parent", True), ("parent", True)]


async def test_an_event_on_a_child_bubbles_to_its_parent() -> None:
    deliveries: list[Delivery] = []

    await run(parent_and_child(deliveries, None), [MouseScrolledDown(absolute=Position(3, 2))])

    assert names(deliveries) == ["child", "parent"]


async def test_the_parent_receives_the_same_event_with_its_own_receiver() -> None:
    receivers: list[tuple[str, InputEvent, Rects, bool]] = []

    @component
    def root() -> Div:
        return Div(
            style=size(20, 10),
            on_input=lambda event, receiver: receivers.append(("parent", event, receiver.rects, receiver.is_target)),
            children=[
                Div(
                    style=box(2, 1, 5, 3),
                    on_input=lambda event, receiver: receivers.append(
                        ("child", event, receiver.rects, receiver.is_target)
                    ),
                )
            ],
        )

    event = MouseScrolledDown(absolute=Position(3, 2))
    await run(root(), [event])

    child = Region(left=2, top=1, right=7, bottom=4)
    parent = Region(left=0, top=0, right=20, bottom=10)
    assert receivers == [
        ("child", event, unclipped(child, screen=parent), True),
        ("parent", event, unclipped(parent, screen=parent), False),
    ]


def unclipped(box: Region, screen: Region) -> Rects:
    """The rects of an element with no margin, border or padding, whose ancestors clip nothing."""
    return Rects(
        content=box,
        padding=box,
        border=box,
        margin=box,
        gutter_right=Region(left=box.right, top=box.top, right=box.right, bottom=box.bottom),
        gutter_bottom=Region(left=box.left, top=box.bottom, right=box.right, bottom=box.bottom),
        clip=screen,
        visible=box,
    )


async def test_an_empty_tuple_from_the_child_keeps_the_event_from_its_parent() -> None:
    deliveries: list[Delivery] = []

    await run(parent_and_child(deliveries, ()), [MouseScrolledDown(absolute=Position(3, 2))])

    assert names(deliveries) == ["child"]


async def test_a_control_from_the_child_is_applied_and_keeps_the_event_from_its_parent() -> None:
    deliveries: list[Delivery] = []
    frames: list[Frame] = []

    await run(
        parent_and_child(deliveries, Screenshot(handler=frames.append)), [MouseScrolledDown(absolute=Position(3, 2))]
    )

    assert (names(deliveries), len(frames)) == (["child"], 1)


async def test_a_tuple_of_controls_applies_each_in_order_and_stops_the_event() -> None:
    deliveries: list[Delivery] = []
    taken: list[str] = []
    screenshots = (
        Screenshot(handler=lambda _: taken.append("first")),
        Screenshot(handler=lambda _: taken.append("second")),
    )

    await run(parent_and_child(deliveries, screenshots), [MouseScrolledDown(absolute=Position(3, 2))])

    assert (names(deliveries), taken) == (["child"], ["first", "second"])


async def test_a_none_in_a_tuple_of_controls_is_skipped() -> None:
    deliveries: list[Delivery] = []
    taken: list[str] = []
    screenshots = (
        Screenshot(handler=lambda _: taken.append("first")),
        None,
        Screenshot(handler=lambda _: taken.append("second")),
    )

    await run(parent_and_child(deliveries, screenshots), [MouseScrolledDown(absolute=Position(3, 2))])

    assert (names(deliveries), taken) == (["child"], ["first", "second"])


async def test_a_tuple_of_only_none_stops_the_event() -> None:
    deliveries: list[Delivery] = []

    await run(parent_and_child(deliveries, (None,)), [MouseScrolledDown(absolute=Position(3, 2))])

    assert names(deliveries) == ["child"]


async def test_a_drag_keeps_reaching_the_element_that_claimed_it_until_the_release() -> None:
    deliveries: list[Delivery] = []

    @component
    def dragged() -> Div:
        handled, set_handled = use_state(0)

        def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
            deliveries.append(Delivery(name=f"dragged after {handled}", event=event, is_target=receiver.is_target))
            set_handled(handled + 1)
            return ()

        return Div(style=box(0, 0, 3, 3), on_input=on_input, children=[Text(content=str(handled))])

    @component
    def root() -> Div:
        return Div(style=size(20, 10), on_input=recording("root", deliveries), children=[dragged()])

    await run(
        root(),
        [
            MouseDown(absolute=Position(1, 1), button=1),
            held(10, 5),
            held(15, 8),
            MouseUp(absolute=Position(15, 8), button=1),
        ],
    )

    assert names(deliveries) == ["dragged after 0", "dragged after 1", "dragged after 2", "dragged after 3"]


async def test_after_the_release_an_event_outside_the_element_does_not_reach_it() -> None:
    deliveries: list[Delivery] = []

    @component
    def root() -> Div:
        return Div(
            style=size(20, 10),
            on_input=recording("root", deliveries),
            children=[Div(style=box(0, 0, 3, 3), on_input=recording("box", deliveries, ()))],
        )

    await run(
        root(),
        [
            *click(1, 1),
            MouseMoved(absolute=Position(10, 5), button=None),
            MouseDown(absolute=Position(10, 5), button=1),
        ],
    )

    assert names(deliveries) == ["box", "box", "root", "root"]


async def test_the_rest_of_a_press_goes_to_the_node_that_claimed_it_alone() -> None:
    deliveries: list[Delivery] = []

    def claim_presses(event: InputEvent, receiver: Receiver) -> InputResponse:
        deliveries.append(Delivery(name="claimer", event=event, is_target=receiver.is_target))
        return () if isinstance(event, MouseDown) else None

    @component
    def root() -> Div:
        return Div(
            style=size(20, 10),
            on_input=recording("root", deliveries),
            children=[
                Div(
                    style=box(0, 0, 10, 10),
                    on_input=claim_presses,
                    children=[Div(style=box(1, 1, 3, 3), on_input=recording("landed on", deliveries))],
                )
            ],
        )

    await run(
        root(), [MouseDown(absolute=Position(2, 2), button=1), held(2, 2), MouseUp(absolute=Position(2, 2), button=1)]
    )

    assert [(delivery.name, type(delivery.event), delivery.is_target) for delivery in deliveries] == [
        ("landed on", MouseDown, True),
        ("claimer", MouseDown, False),
        ("claimer", MouseMoved, True),
        ("claimer", MouseUp, True),
    ]


async def test_the_rest_of_a_press_nothing_claimed_reaches_no_handler() -> None:
    deliveries: list[Delivery] = []
    clicks: list[str] = []

    @component
    def root() -> Div:
        return Div(
            style=size(20, 10),
            on_input=recording("root", deliveries),
            children=[Text(content="click", style=box(10, 0, 5, 1), on_input=on_click(lambda: clicks.append("click")))],
        )

    await run(
        root(), [MouseDown(absolute=Position(2, 5), button=1), held(11, 0), MouseUp(absolute=Position(11, 0), button=1)]
    )

    assert (names(deliveries), clicks) == (["root"], [])


async def test_a_press_and_release_on_an_on_click_element_calls_its_action() -> None:
    clicks: list[str] = []

    @component
    def root() -> Div:
        return Div(
            style=size(20, 10),
            children=[Text(content="click", style=box(10, 0, 5, 1), on_input=on_click(lambda: clicks.append("click")))],
        )

    await run(root(), click(11, 0))

    assert clicks == ["click"]


async def test_the_rest_of_a_press_whose_captor_unmounted_reaches_no_handler() -> None:
    deliveries: list[Delivery] = []

    @component
    def root() -> Div:
        is_shown, set_shown = use_state(True)

        def unmount_on_press(event: InputEvent, receiver: Receiver) -> InputResponse:
            deliveries.append(Delivery(name="captor", event=event, is_target=receiver.is_target))
            set_shown(False)
            return ()

        return Div(
            style=size(20, 10),
            on_input=recording("root", deliveries),
            children=[Div(style=box(0, 0, 5, 5), on_input=unmount_on_press)] if is_shown else [],
        )

    await run(
        root(), [MouseDown(absolute=Position(1, 1), button=1), held(2, 2), MouseUp(absolute=Position(2, 2), button=1)]
    )

    assert names(deliveries) == ["captor"]


def captor_and_other(deliveries: list[Delivery]) -> Component:
    @component
    def root() -> Div:
        return Div(
            style=size(20, 10),
            children=[
                Div(style=box(0, 0, 5, 5), on_input=recording("captor", deliveries, ())),
                Div(style=box(10, 0, 5, 5), on_input=recording("other", deliveries, ())),
            ],
        )

    return root()


@pytest.mark.parametrize("wheel", [MouseScrolledDown, MouseScrolledUp, MouseScrolledLeft, MouseScrolledRight])
async def test_a_wheel_event_during_a_press_routes_by_position_and_the_capture_continues(
    wheel: type[MouseScrolledDown | MouseScrolledUp | MouseScrolledLeft | MouseScrolledRight],
) -> None:
    deliveries: list[Delivery] = []

    await run(
        captor_and_other(deliveries),
        [
            MouseDown(absolute=Position(1, 1), button=1),
            wheel(absolute=Position(11, 1)),
            held(12, 2),
            MouseUp(absolute=Position(12, 2), button=1),
        ],
    )

    assert names(deliveries) == ["captor", "other", "captor", "captor"]


async def test_another_buttons_mouse_down_during_a_press_goes_to_the_captor() -> None:
    deliveries: list[Delivery] = []

    await run(
        captor_and_other(deliveries),
        [MouseDown(absolute=Position(1, 1), button=1), MouseDown(absolute=Position(11, 1), button=3), held(12, 2)],
    )

    assert names(deliveries) == ["captor", "captor", "captor"]


async def test_a_press_holding_several_buttons_ends_when_the_last_is_released() -> None:
    deliveries: list[Delivery] = []

    await run(
        captor_and_other(deliveries),
        [
            MouseDown(absolute=Position(1, 1), button=1),
            MouseDown(absolute=Position(11, 1), button=3),
            MouseUp(absolute=Position(11, 1), button=1),
            MouseMoved(absolute=Position(12, 1), button=3),
            MouseUp(absolute=Position(12, 1), button=3),
            MouseDown(absolute=Position(12, 1), button=1),
        ],
    )

    assert names(deliveries) == ["captor", "captor", "captor", "captor", "captor", "other"]


@pytest.mark.parametrize(
    ("release", "expected_clicks"),
    [(Position(1, 1), ["first"]), (Position(11, 1), [])],
    ids=["over the first element", "over the second element"],
)
async def test_a_press_that_another_element_claims_a_second_button_of_still_belongs_to_the_first(
    release: Position, expected_clicks: list[str]
) -> None:
    clicks: list[str] = []

    def claim_presses(event: InputEvent, receiver: Receiver) -> InputResponse:
        return () if isinstance(event, MouseDown) else None  # pragma: never runs

    @component
    def root() -> Div:
        return Div(
            style=size(20, 10),
            children=[
                Div(style=box(0, 0, 5, 5), on_input=on_click(lambda: clicks.append("first"))),
                Div(style=box(10, 0, 5, 5), on_input=each(on_click(lambda: clicks.append("second")), claim_presses)),
            ],
        )

    await run(
        root(),
        [
            MouseDown(absolute=Position(1, 1), button=1),
            MouseDown(absolute=Position(11, 1), button=3),
            MouseUp(absolute=release, button=1),
            MouseUp(absolute=release, button=3),
        ],
    )

    assert clicks == expected_clicks


async def test_a_mouse_down_for_a_button_the_press_holds_routes_by_position_and_starts_a_new_press() -> None:
    deliveries: list[Delivery] = []

    await run(
        captor_and_other(deliveries),
        [MouseDown(absolute=Position(1, 1), button=1), MouseDown(absolute=Position(11, 1), button=1), held(2, 2)],
    )

    assert names(deliveries) == ["captor", "other", "other"]


async def test_a_mouse_up_for_a_button_the_press_doesnt_hold_reaches_no_handler_and_the_press_continues() -> None:
    deliveries: list[Delivery] = []

    await run(
        captor_and_other(deliveries),
        [MouseDown(absolute=Position(1, 1), button=1), MouseUp(absolute=Position(1, 1), button=3), held(12, 2)],
    )

    assert names(deliveries) == ["captor", "captor"]


async def test_a_move_with_no_button_held_during_a_press_routes_by_position_and_ends_the_press() -> None:
    deliveries: list[Delivery] = []

    await run(
        captor_and_other(deliveries),
        [
            MouseDown(absolute=Position(1, 1), button=1),
            MouseMoved(absolute=Position(11, 1), button=None),
            held(2, 2),
            MouseUp(absolute=Position(2, 2), button=1),
        ],
    )

    assert names(deliveries) == ["captor", "other"]
