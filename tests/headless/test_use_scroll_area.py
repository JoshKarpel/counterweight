from collections.abc import Callable, Sequence

import pytest

from counterweight import app
from counterweight.components import component
from counterweight.controls import AnyControl, FocusNext, Quit, Screenshot, ScrollTo
from counterweight.elements import Div, Text
from counterweight.events import (
    InputEvent,
    InputHandler,
    InputResponse,
    KeyPressed,
    MouseDown,
    MouseScrolledDown,
    MouseScrolledLeft,
    MouseScrolledRight,
    MouseScrolledUp,
    Pasted,
    Receiver,
)
from counterweight.geometry import Position
from counterweight.handlers import first, on_click
from counterweight.headless import ScrollArea, ScrollAxis, use_scroll_area
from counterweight.hooks import ElementHandle, use_scroll, use_state
from counterweight.keys import Key
from counterweight.output import Frame
from counterweight.styles.utilities import (
    align_children_start,
    col,
    fill,
    overflow_scroll,
    overflow_x_hidden,
    overflow_x_scroll,
    overflow_y_clip,
    overflow_y_scroll,
    size,
    stick_to_end_x,
    stick_to_end_y,
)

ROWS = tuple(f"row {i:02}" for i in range(20))
# Each line names its columns, so a scroll sideways shows which column comes first.
WIDE = tuple("".join(str(c % 10) for c in range(row, row + 30)) for row in range(20))
SIZE = (10, 4)
INSIDE = Position(2, 1)


def lines(frame: Frame) -> list[str]:
    return [line.rstrip() for line in frame.text(ansi=False).splitlines()]


async def run(
    events: Sequence[InputEvent | AnyControl],
    axis: ScrollAxis = "y",
    stick_to_end: bool = False,
    content: tuple[str, ...] = ROWS,
    auto_focus: bool = True,
    is_focusable: bool = True,
    in_focus_order: bool = True,
    wheel_lines: int = 3,
    on_parent: InputHandler | None = None,
    compose: Callable[[ScrollArea], InputHandler] = lambda area: area.on_input,
) -> tuple[list[str], list[ScrollArea]]:
    """
    Runs an area `SIZE` cells big at the top-left of the screen, scrolling `content` a line each,
    inside a parent with `on_parent`, whose root element takes `compose(area)`,
    and returns the lines of the screen at the end, and what each of the area's renders got.
    """
    areas: list[ScrollArea] = []
    frames: list[Frame] = []

    @component
    def area_component() -> Div:
        area = use_scroll_area(
            axis,
            stick_to_end,
            wheel_lines=wheel_lines,
            auto_focus=auto_focus,
            is_focusable=is_focusable,
            in_focus_order=in_focus_order,
        )
        areas.append(area)
        return Div(
            style=size(*SIZE) | col | align_children_start | area.style,
            handle=area.viewport,
            on_input=compose(area),
            children=tuple(Text(content=line) for line in content),
        )

    @component
    def parent() -> Div:
        return Div(style=col, on_input=on_parent, children=(area_component(),))

    await app(
        parent(),
        headless=True,
        dimensions=(20, 6),
        autopilot=(*events, Screenshot(handler=frames.append), Quit()),
        check_purity=True,
    )
    return lines(frames[-1]), areas


def recorder(seen: list[InputEvent]) -> InputHandler:
    """A handler that records every event that reaches it, and handles none of them."""

    def handler(event: InputEvent, _: Receiver) -> InputResponse:
        seen.append(event)
        return None

    return handler


def pressed(*keys: str) -> tuple[KeyPressed, ...]:
    return tuple(KeyPressed(key=key) for key in keys)


# A control that does nothing but take a render, after which `use_scroll` reports the scroll that render applied.
SETTLE = Screenshot(handler=lambda _: None)


def frame_by_frame(*keys: str) -> tuple[KeyPressed | Screenshot, ...]:
    """
    `keys` pressed a frame apart, as a person presses them,
    so the area's handler judges each by the scroll the one before it left.
    """
    return tuple(event for key in keys for event in (KeyPressed(key=key), SETTLE))


@pytest.mark.parametrize(
    ("axis", "expected"),
    [
        ("y", overflow_y_scroll | overflow_x_hidden),
        ("x", overflow_x_scroll | overflow_y_clip),
        ("both", overflow_scroll),
    ],
)
async def test_style_makes_the_viewport_scroll_on_the_axis_and_clip_on_the_other(
    axis: ScrollAxis, expected: object
) -> None:
    _, areas = await run((), axis=axis)

    assert areas[-1].style == expected


@pytest.mark.parametrize(
    ("axis", "expected"),
    [
        ("y", overflow_y_scroll | overflow_x_hidden | stick_to_end_y),
        ("x", overflow_x_scroll | overflow_y_clip | stick_to_end_x),
        ("both", overflow_scroll | stick_to_end_x | stick_to_end_y),
    ],
)
async def test_style_sticks_the_viewport_to_its_end_on_the_axis_if_asked(axis: ScrollAxis, expected: object) -> None:
    _, areas = await run((), axis=axis, stick_to_end=True)

    assert areas[-1].style == expected


async def test_an_area_that_sticks_to_its_end_starts_there() -> None:
    shown, _ = await run((), stick_to_end=True)

    assert shown[:4] == ["row 16", "row 17", "row 18", "row 19"]


@pytest.mark.parametrize(
    ("keys", "offset"),
    [
        ((Key.Down,), Position(0, 1)),
        ((Key.Down, Key.Down, Key.Up), Position(0, 1)),
        ((Key.PageDown,), Position(0, 3)),
        ((Key.Space,), Position(0, 3)),
        ((Key.PageDown, Key.PageDown, Key.PageUp), Position(0, 3)),
        ((Key.End,), Position(0, 16)),
        ((Key.End, Key.Home), Position(0, 0)),
    ],
)
async def test_keys_scroll_an_area_vertically(keys: tuple[Key, ...], offset: Position) -> None:
    _, areas = await run(frame_by_frame(*keys))

    assert areas[-1].scroll.offset == offset


async def test_a_page_is_the_given_fraction_of_the_view() -> None:
    areas: list[ScrollArea] = []

    @component
    def area_component() -> Div:
        area = use_scroll_area(page=0.5, auto_focus=True)
        areas.append(area)
        return Div(
            style=size(*SIZE) | col | area.style,
            handle=area.viewport,
            on_input=area.on_input,
            children=tuple(Text(content=line) for line in ROWS),
        )

    await app(
        area_component(),
        headless=True,
        dimensions=(20, 6),
        autopilot=(KeyPressed(key=Key.PageDown), SETTLE, Quit()),
    )

    assert areas[-1].scroll.offset == Position(0, 2)


async def test_a_page_that_is_not_positive_raises() -> None:
    @component
    def area_component() -> Div:
        return Div(style=use_scroll_area(page=0).style)

    with pytest.raises(ValueError, match="positive fraction"):
        await app(area_component(), headless=True, dimensions=(20, 6), autopilot=(Quit(),))


@pytest.mark.parametrize(
    ("keys", "offset"),
    [
        ((Key.Right,), Position(1, 0)),
        ((Key.Right, Key.Right, Key.Left), Position(1, 0)),
        ((Key.End,), Position(20, 0)),
        ((Key.End, Key.Home), Position(0, 0)),
    ],
)
async def test_arrows_home_and_end_scroll_an_area_that_only_scrolls_sideways(
    keys: tuple[Key, ...], offset: Position
) -> None:
    _, areas = await run(frame_by_frame(*keys), axis="x", content=WIDE[:4])

    assert areas[-1].scroll.offset == offset


@pytest.mark.parametrize(
    ("keys", "offset"),
    [((Key.Right, Key.End), Position(1, 16)), ((Key.Right, Key.End, Key.Home), Position(1, 0))],
)
async def test_home_and_end_scroll_an_area_that_scrolls_both_ways_vertically(
    keys: tuple[Key, ...], offset: Position
) -> None:
    _, areas = await run(frame_by_frame(*keys), axis="both", content=WIDE)

    assert areas[-1].scroll.offset == offset


@pytest.mark.parametrize(
    "key",
    [Key.Up, Key.PageUp, Key.Home, Key.Left, "a"],
)
async def test_a_key_that_would_not_scroll_the_area_bubbles(key: str) -> None:
    seen: list[InputEvent] = []

    await run(pressed(key), on_parent=recorder(seen))

    assert seen == [KeyPressed(key=key)]


async def test_a_paste_bubbles() -> None:
    seen: list[InputEvent] = []

    await run((Pasted(text="row"),), on_parent=recorder(seen))

    assert seen == [Pasted(text="row")]


async def test_end_bubbles_once_the_area_is_at_its_end() -> None:
    seen: list[InputEvent] = []

    await run(frame_by_frame(Key.End, Key.End), on_parent=recorder(seen))

    assert seen == [KeyPressed(key=Key.End)]


async def test_a_key_scrolls_the_area_rather_than_bubbling() -> None:
    seen: list[InputEvent] = []

    await run(pressed(Key.Down), on_parent=recorder(seen))

    assert seen == []


@pytest.mark.parametrize(
    ("event", "offset"),
    [
        (MouseScrolledDown(absolute=INSIDE), Position(0, 3)),
        (MouseScrolledRight(absolute=INSIDE), Position(3, 0)),
        (MouseScrolledDown(absolute=INSIDE, is_shift_held=True), Position(3, 0)),
    ],
)
async def test_the_wheel_scrolls_the_area_toward_its_direction(event: InputEvent, offset: Position) -> None:
    _, areas = await run((event,), axis="both", content=WIDE)

    assert areas[-1].scroll.offset == offset


@pytest.mark.parametrize(
    ("event", "offset"),
    [
        (MouseScrolledUp(absolute=INSIDE), Position(2, 0)),
        (MouseScrolledLeft(absolute=INSIDE), Position(0, 2)),
        (MouseScrolledUp(absolute=INSIDE, is_shift_held=True), Position(0, 2)),
    ],
)
async def test_the_wheel_scrolls_the_area_back_toward_its_direction(event: InputEvent, offset: Position) -> None:
    there = (MouseScrolledDown(absolute=INSIDE), SETTLE, MouseScrolledDown(absolute=INSIDE, is_shift_held=True), SETTLE)

    _, areas = await run((*there, event), axis="both", content=WIDE, wheel_lines=2)

    assert areas[-1].scroll.offset == offset


async def test_a_wheel_event_that_would_not_scroll_the_area_bubbles() -> None:
    seen: list[InputEvent] = []

    await run((MouseScrolledUp(absolute=INSIDE),), on_parent=recorder(seen))

    assert seen == [MouseScrolledUp(absolute=INSIDE)]


async def test_a_press_on_the_area_focuses_it() -> None:
    _, areas = await run((MouseDown(absolute=INSIDE, button=1),), auto_focus=False)

    assert (areas[0].focus.is_focused, areas[-1].focus.is_focused) == (False, True)


async def test_a_press_on_an_unfocusable_area_bubbles() -> None:
    seen: list[InputEvent] = []

    _, areas = await run((MouseDown(absolute=INSIDE, button=1),), is_focusable=False, on_parent=recorder(seen))

    assert (seen, areas[-1].focus.is_focused) == ([MouseDown(absolute=INSIDE, button=1)], False)


async def test_a_press_that_something_inside_the_area_claims_leaves_focus_where_it_is() -> None:
    areas: list[ScrollArea] = []
    clicked: list[bool] = []

    @component
    def area_component() -> Div:
        area = use_scroll_area()
        areas.append(area)
        return Div(
            style=size(*SIZE) | col | area.style,
            handle=area.viewport,
            on_input=area.on_input,
            children=(Text(content="button", on_input=on_click(lambda: clicked.append(True))),),
        )

    press = (MouseDown(absolute=Position(1, 0), button=1),)
    await app(area_component(), headless=True, dimensions=(20, 6), autopilot=(*press, Quit()))

    assert (clicked, areas[-1].focus.is_focused) == ([], False)


async def test_the_area_is_in_the_focus_order_unless_asked_not_to_be() -> None:
    _, focusable = await run((FocusNext(),), auto_focus=False)
    _, out_of_order = await run((FocusNext(),), auto_focus=False, in_focus_order=False)

    assert (focusable[-1].focus.is_focused, out_of_order[-1].focus.is_focused) == (True, False)


async def test_is_at_end_is_true_while_the_content_fits() -> None:
    _, areas = await run((), content=ROWS[:2])

    assert (areas[-1].is_at_start, areas[-1].is_at_end) == (True, True)


async def test_is_at_end_is_false_until_the_area_is_scrolled_to_its_end() -> None:
    _, at_start = await run(())
    _, at_end = await run(pressed(Key.End))

    assert [(a.is_at_start, a.is_at_end) for a in (at_start[-1], at_end[-1])] == [(True, False), (False, True)]


@pytest.mark.parametrize(
    ("keys", "expected"),
    [
        ((), (True, False)),
        ((Key.Right,), (False, False)),
        ((Key.End,), (False, False)),
        ((Key.End, Key.Right), (False, False)),
        ((Key.End, Key.Right, Key.Right, Key.Right) + (Key.Right,) * 20, (False, True)),
    ],
)
async def test_an_area_that_scrolls_both_ways_is_at_an_end_only_on_both_axes(
    keys: tuple[Key, ...], expected: tuple[bool, bool]
) -> None:
    _, areas = await run(pressed(*keys), axis="both", content=WIDE)

    assert (areas[-1].is_at_start, areas[-1].is_at_end) == expected


@pytest.mark.parametrize(
    ("axis", "offset"),
    [("y", Position(0, 16)), ("x", Position(20, 0)), ("both", Position(20, 16))],
)
async def test_to_end_scrolls_the_area_to_its_end_on_its_axes(axis: ScrollAxis, offset: Position) -> None:
    def jump(area: ScrollArea) -> InputHandler:
        def handler(event: InputEvent, _: Receiver) -> InputResponse:
            return area.to_end if event == KeyPressed(key="e") else None

        return first(handler, area.on_input)

    _, areas = await run(pressed("e"), axis=axis, content=WIDE, compose=jump)

    assert areas[-1].scroll.offset == offset


@pytest.mark.parametrize("axis", ["y", "x", "both"])
async def test_to_start_scrolls_the_area_to_its_start_on_its_axes(axis: ScrollAxis) -> None:
    def jump(area: ScrollArea) -> InputHandler:
        def handler(event: InputEvent, _: Receiver) -> InputResponse:
            return area.to_start if event == KeyPressed(key="s") else None

        return first(handler, area.on_input)

    away = (MouseScrolledDown(absolute=INSIDE), SETTLE, MouseScrolledDown(absolute=INSIDE, is_shift_held=True), SETTLE)
    _, areas = await run((*away, *pressed("s")), axis=axis, content=WIDE, compose=jump)

    assert areas[-1].scroll.offset == Position(0, 0)


async def test_a_parent_scrolls_and_reads_the_area_through_the_viewport_handle_it_passes() -> None:
    scrolls: list[Position] = []
    viewports: list[ElementHandle] = []

    @component
    def area_component(viewport: ElementHandle) -> Div:
        area = use_scroll_area(viewport=viewport)
        viewports.append(area.viewport)
        return Div(
            style=size(*SIZE) | col | area.style,
            handle=area.viewport,
            on_input=area.on_input,
            children=tuple(Text(content=line) for line in ROWS),
        )

    @component
    def parent() -> Div:
        viewport, _ = use_state(ElementHandle)
        scrolls.append(use_scroll(viewport).offset)

        def on_key(event: InputEvent, _: Receiver) -> InputResponse:
            return ScrollTo(viewport, y=5) if event == KeyPressed(key="j") else None

        return Div(on_input=on_key, children=(area_component(viewport),))

    await app(
        parent(),
        headless=True,
        dimensions=(20, 6),
        autopilot=(KeyPressed(key="j"), SETTLE, Quit()),
    )

    assert (scrolls[-1], len(set(viewports))) == (Position(0, 5), 1)


async def test_an_area_whose_viewport_is_inside_its_element_scrolls_it_from_anywhere_in_that_element() -> None:
    areas: list[ScrollArea] = []

    @component
    def titled() -> Div:
        area = use_scroll_area(auto_focus=True)
        areas.append(area)
        return Div(
            style=size(10, 5) | col,
            on_input=area.on_input,
            children=(
                Text(content="title"),
                Div(
                    style=fill(1) | col | area.style,
                    handle=area.viewport,
                    children=tuple(Text(content=line) for line in ROWS),
                ),
            ),
        )

    over_title = Position(1, 0)
    await app(
        titled(),
        headless=True,
        dimensions=(20, 6),
        autopilot=(
            MouseScrolledDown(absolute=over_title),
            KeyPressed(key=Key.Down),
            SETTLE,
            Quit(),
        ),
    )

    assert areas[-1].scroll.offset == Position(0, 4)
