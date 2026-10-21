from collections.abc import Sequence

import pytest

from counterweight import app
from counterweight._output import Frame
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import AnyControl
from counterweight.controls import FocusNext
from counterweight.controls import FocusOn
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.controls import ScrollTo
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseScrolledDown
from counterweight.events import Receiver
from counterweight.focus import ElementHandle
from counterweight.focus import FocusHandle
from counterweight.geometry import Position
from counterweight.headless import ScrollAxis
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles import AnyColor
from counterweight.styles import Style
from counterweight.styles.utilities import border
from counterweight.styles.utilities import border_color
from counterweight.styles.utilities import border_heavy
from counterweight.styles.utilities import col
from counterweight.styles.utilities import default
from counterweight.styles.utilities import fill
from counterweight.styles.utilities import size
from counterweight.styles.utilities import text_bg
from counterweight.widgets import ScrollAreaStyles
from counterweight.widgets import scroll_area

ROWS = tuple(f"row {i:02}" for i in range(20))
SETTLE = Screenshot(handler=lambda _: None)
INSIDE = Position(3, 2)


def area(
    content: tuple[str, ...] = ROWS,
    axis: ScrollAxis = "y",
    stick_to_end: bool = False,
    style: Style = default,
    styles: ScrollAreaStyles = ScrollAreaStyles(),
    wheel_lines: int = 3,
    page: float = 0.875,
    auto_focus: bool = True,
    is_focusable: bool = True,
    in_focus_order: bool = True,
) -> Component:
    """A root holding a `scroll_area` 12 cells wide and 6 tall, over `content`, a `Text` per line."""

    @component
    def root() -> Div:
        return Div(
            style=col,
            children=(
                scroll_area(
                    tuple(Text(content=line) for line in content),
                    axis=axis,
                    stick_to_end=stick_to_end,
                    style=size(12, 6) | style,
                    styles=styles,
                    wheel_lines=wheel_lines,
                    page=page,
                    auto_focus=auto_focus,
                    is_focusable=is_focusable,
                    in_focus_order=in_focus_order,
                ),
            ),
        )

    return root()


async def screenshot(root: Component, events: Sequence[InputEvent | AnyControl] = ()) -> Frame:
    frames: list[Frame] = []
    await app(
        root,
        headless=True,
        dimensions=(16, 8),
        autopilot=(*events, Screenshot(handler=frames.append), Quit()),
        check_purity=True,
    )
    return frames[-1]


def lines(frame: Frame) -> list[str]:
    return [line.rstrip() for line in frame.text(ansi=False).splitlines()]


def corner_color(frame: Frame) -> AnyColor | None:
    return next(iter(frame.paint.rows()))[0].style.foreground


FOCUSED = border_color("indigo", 400).border_style.foreground
UNFOCUSED = border_color("slate", 600).border_style.foreground


async def test_scroll_area_draws_its_children_in_a_padded_box() -> None:
    frame = await screenshot(area())

    assert lines(frame)[:6] == [
        "╭──────────╮",
        "│ row 00   │",
        "│ row 01   │",
        "│ row 02   │",
        "│ row 03   │",
        "╰──────────╯",
    ]


async def test_scroll_area_border_shows_whether_it_is_focused() -> None:
    focused = await screenshot(area())
    unfocused = await screenshot(area(auto_focus=False))

    assert (corner_color(focused), corner_color(unfocused)) == (FOCUSED, UNFOCUSED)


async def test_scroll_area_style_merges_under_the_focused_border_color() -> None:
    teal = border_color("teal", 400)
    focused = await screenshot(area(style=teal))
    unfocused = await screenshot(area(style=teal, auto_focus=False))

    assert (corner_color(focused), corner_color(unfocused)) == (FOCUSED, teal.border_style.foreground)


async def test_scroll_area_draws_its_box_with_the_given_styles() -> None:
    styles = ScrollAreaStyles(
        box=border | border_heavy | border_color("amber", 400), focused_box=border_color("teal", 400)
    )

    focused = await screenshot(area(styles=styles))
    unfocused = await screenshot(area(styles=styles, auto_focus=False))

    assert [(lines(frame)[1], corner_color(frame)) for frame in (focused, unfocused)] == [
        ("┃row 00    ┃", border_color("teal", 400).border_style.foreground),
        ("┃row 00    ┃", border_color("amber", 400).border_style.foreground),
    ]


async def test_scroll_area_scrolls_with_the_keys_while_focused() -> None:
    frame = await screenshot(area(), events=(KeyPressed(key=Key.Down),))

    assert lines(frame)[1] == "│ row 01   │"


async def test_scroll_area_scrolls_with_a_style_that_sets_overflow() -> None:
    frame = await screenshot(area(style=fill(1)), events=(KeyPressed(key=Key.Down),))

    assert lines(frame)[1] == "│ row 01   │"


async def test_a_press_on_scroll_area_focuses_it() -> None:
    frame = await screenshot(area(auto_focus=False), events=(MouseDown(absolute=INSIDE, button=1),))

    assert corner_color(frame) == FOCUSED


async def test_a_press_on_an_unfocusable_scroll_area_leaves_it_unfocused() -> None:
    frame = await screenshot(area(is_focusable=False), events=(MouseDown(absolute=INSIDE, button=1),))

    assert corner_color(frame) == UNFOCUSED


async def test_scroll_area_out_of_the_focus_order_is_skipped_by_tab() -> None:
    frame = await screenshot(area(auto_focus=False, in_focus_order=False), events=(FocusNext(),))

    assert corner_color(frame) == UNFOCUSED


async def test_scroll_area_that_sticks_to_its_end_starts_there() -> None:
    frame = await screenshot(area(stick_to_end=True))

    assert lines(frame)[1:5] == ["│ row 16   │", "│ row 17   │", "│ row 18   │", "│ row 19   │"]


async def test_scroll_area_scrolls_by_the_given_wheel_lines() -> None:
    frame = await screenshot(area(wheel_lines=2), events=(MouseScrolledDown(absolute=INSIDE),))

    assert lines(frame)[1] == "│ row 02   │"


async def test_scroll_area_pages_by_the_given_fraction_of_its_view() -> None:
    frame = await screenshot(area(page=0.5), events=(KeyPressed(key=Key.PageDown),))

    assert lines(frame)[1] == "│ row 02   │"


@pytest.mark.parametrize("axis", ["x", "both"])
async def test_scroll_area_that_scrolls_sideways_scrolls_lines_wider_than_its_box(axis: ScrollAxis) -> None:
    content = ("a line wider than the box", "short")

    frame = await screenshot(area(content, axis=axis), events=(KeyPressed(key=Key.Right),) * 3)

    assert lines(frame)[1:3] == ["│line wider│", "│ort       │"]


async def test_scroll_area_clips_a_line_too_long_for_the_axis_it_does_not_scroll() -> None:
    frame = await screenshot(area(("a line wider than the box",)))

    assert lines(frame)[1] == "│ a line wi│"


async def test_scroll_area_that_scrolls_vertically_stretches_its_children_across_the_box() -> None:
    @component
    def root() -> Div:
        return Div(
            style=col,
            children=(scroll_area((Text(content="row", style=text_bg("teal", 900)),), style=size(12, 6)),),
        )

    frame = await screenshot(root())

    assert list(frame.paint.rows())[1][9].style.background == text_bg("teal", 900).text_style.background


async def test_a_parent_focuses_and_scrolls_scroll_area_through_the_handles_it_passes() -> None:
    @component
    def root() -> Div:
        focus_handle, _ = use_state(FocusHandle)
        viewport, _ = use_state(ElementHandle)

        def on_key(event: InputEvent, _: Receiver) -> InputResponse:
            return (FocusOn(focus_handle), ScrollTo(viewport, y=5)) if event == KeyPressed(key="j") else None

        return Div(
            style=col,
            on_input=on_key,
            children=(
                scroll_area(
                    tuple(Text(content=line) for line in ROWS),
                    style=size(12, 6),
                    viewport=viewport,
                    handle=focus_handle,
                ),
            ),
        )

    frame = await screenshot(root(), events=(KeyPressed(key="j"), SETTLE))

    assert (lines(frame)[1], corner_color(frame)) == ("│ row 05   │", FOCUSED)
