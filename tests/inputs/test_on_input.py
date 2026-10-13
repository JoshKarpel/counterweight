from counterweight import app
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.elements import Div
from counterweight.events import (
    InputEvent,
    KeyPressed,
    MouseDown,
    MouseEvent,
    MouseMoved,
    MouseScrolledDown,
    MouseScrolledUp,
    MouseUp,
    Receiver,
)
from counterweight.geometry import Position, Rects, Region
from counterweight.styles.utilities import border, inset_left, inset_top, margin, pad, position_absolute, size


async def test_on_input_receives_keys() -> None:
    recorder: list[InputEvent] = []

    @component
    def root() -> Div:
        return Div(
            on_input=lambda event, _: recorder.append(event),
            style=size(10, 10),
        )

    await app(
        root,
        headless=True,
        autopilot=(
            KeyPressed(key="f"),
            Quit(),
        ),
        check_purity=True,
    )

    assert recorder == [
        KeyPressed(key="f"),
    ]


async def test_one_on_input_receives_both_keys_and_mouse_events() -> None:
    recorder: list[InputEvent] = []

    @component
    def root() -> Div:
        return Div(
            on_input=lambda event, _: recorder.append(event),
            style=size(10, 10),
        )

    events: list[InputEvent] = [
        KeyPressed(key="j"),
        MouseScrolledDown(absolute=Position(2, 3)),
    ]

    await app(
        root,
        headless=True,
        autopilot=(*events, Quit()),
        check_purity=True,
    )

    assert recorder == events


async def test_on_input_only_captures_mouse_events_in_border_rect_with_history() -> None:
    recorder: list[InputEvent] = []

    @component
    def root() -> Div:
        return Div(
            on_input=lambda event, _: recorder.append(event),
            style=border | size(3, 3),
        )

    events: list[tuple[MouseEvent, bool]] = [
        (MouseMoved(absolute=Position(1, 1), button=None), True),  # in content rect
        (MouseMoved(absolute=Position(2, 0), button=None), True),  # on border
        (MouseMoved(absolute=Position(3, 0), button=None), True),  # outside, but included because previous was inside
        (MouseMoved(absolute=Position(3, 0), button=None), False),  # outside border, not included
        (MouseMoved(absolute=Position(1, 0), button=None), True),  # back inside
        (MouseDown(absolute=Position(1, 0), button=1), True),  # back inside
        (MouseMoved(absolute=Position(1, 1), button=1), True),
        (MouseUp(absolute=Position(1, 1), button=1), True),
        (MouseScrolledUp(absolute=Position(1, 1)), True),
        (MouseScrolledDown(absolute=Position(1, 1)), True),
    ]

    await app(
        root,
        headless=True,
        autopilot=(
            *(event for event, _ in events),
            Quit(),
        ),
        check_purity=True,
    )

    assert recorder == [event for event, tf in events if tf]


async def test_receiver_carries_the_receiving_elements_rects() -> None:
    receivers: list[Receiver] = []

    @component
    def root() -> Div:
        return Div(
            style=size(20, 10),
            children=[
                Div(
                    on_input=lambda _, receiver: receivers.append(receiver),
                    style=position_absolute | inset_left(4) | inset_top(2) | margin(1) | border | pad(2) | size(9, 9),
                )
            ],
        )

    await app(
        root,
        headless=True,
        autopilot=(
            KeyPressed(key="x"),
            Quit(),
        ),
        check_purity=True,
    )

    assert receivers == [
        Receiver(
            rects=Rects(
                content=Region(left=8, top=6, right=11, bottom=9),
                padding=Region(left=6, top=4, right=13, bottom=11),
                border=Region(left=5, top=3, right=14, bottom=12),
                margin=Region(left=4, top=2, right=15, bottom=13),
            )
        )
    ]


def test_receiver_relative_is_relative_to_the_content_box_top_left() -> None:
    receiver = Receiver(
        rects=Rects(
            content=Region(left=8, top=6, right=11, bottom=9),
            padding=Region(left=6, top=4, right=13, bottom=11),
            border=Region(left=5, top=3, right=14, bottom=12),
            margin=Region(left=4, top=2, right=15, bottom=13),
        )
    )

    assert receiver.relative(Position(x=10, y=7)) == Position(x=2, y=1)
