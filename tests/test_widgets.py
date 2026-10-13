from collections.abc import Sequence

from counterweight import app
from counterweight.components import Component, component
from counterweight.controls import AnyControl, Quit, Screenshot
from counterweight.elements import Div
from counterweight.events import InputEvent, KeyPressed, MouseDown, MouseScrolledUp
from counterweight.geometry import Position
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.output import Frame
from counterweight.styles import Style
from counterweight.styles.utilities import col, default, max_height, width
from counterweight.widgets import CURSOR, text_area, text_input


def field(initial: str = "", placeholder: str = "", auto_focus: bool = True, is_focusable: bool = True) -> Component:
    @component
    def root() -> Div:
        value, set_value = use_state(initial)
        return Div(
            style=col,
            children=[
                text_input(
                    value,
                    set_value,
                    placeholder=placeholder,
                    style=width(12),
                    auto_focus=auto_focus,
                    is_focusable=is_focusable,
                )
            ],
        )

    return root()


async def screenshot(
    root: Component, events: Sequence[InputEvent | AnyControl] = (), dimensions: tuple[int, int] = (14, 3)
) -> Frame:
    frames: list[Frame] = []
    await app(
        root,
        headless=True,
        dimensions=dimensions,
        autopilot=(*events, Screenshot(handler=frames.append), Quit()),
        check_purity=True,
    )
    return frames[-1]


def lines(frame: Frame) -> list[str]:
    return [line.rstrip() for line in frame.text(ansi=False).splitlines()]


def cursor_cells(frame: Frame) -> list[tuple[int, int, str]]:
    """The position and grapheme of each cell drawn in the cursor's colors."""
    return [
        (x, y, cell.grapheme)
        for y, row in enumerate(frame.paint.rows())
        for x, cell in enumerate(row)
        if cell.style.background == CURSOR.background
    ]


async def test_text_input_draws_its_value_in_a_box_of_the_given_width() -> None:
    frame = await screenshot(field(initial="hi"))

    assert lines(frame) == ["╭──────────╮", "│ hi       │", "╰──────────╯"]


async def test_text_input_draws_the_cursor_while_focused() -> None:
    frame = await screenshot(field(initial="hi"), events=(KeyPressed(key="!"), KeyPressed(key="left")))

    assert cursor_cells(frame) == [(4, 1, "!")]


async def test_text_input_draws_no_cursor_while_unfocused() -> None:
    frame = await screenshot(field(initial="hi", auto_focus=False))

    assert cursor_cells(frame) == []


async def test_text_input_shows_its_placeholder_while_empty_with_the_cursor_on_its_first_character() -> None:
    frame = await screenshot(field(placeholder="Name"))

    assert (lines(frame)[1], cursor_cells(frame)) == ("│ Name     │", [(2, 1, "N")])


async def test_text_input_replaces_its_placeholder_with_what_is_typed() -> None:
    frame = await screenshot(field(placeholder="Name"), events=(KeyPressed(key="J"),))

    assert lines(frame)[1] == "│ J        │"


async def test_a_press_on_a_text_input_focuses_it() -> None:
    frame = await screenshot(
        field(initial="hi", auto_focus=False), events=(MouseDown(absolute=Position(x=3, y=1), button=1),)
    )

    assert cursor_cells(frame) == [(4, 1, " ")]


async def test_an_unfocusable_text_input_takes_no_keys() -> None:
    frame = await screenshot(field(initial="hi", is_focusable=False), events=(KeyPressed(key="!"),))

    assert (lines(frame)[1], cursor_cells(frame)) == ("│ hi       │", [])


def area(
    initial: str = "", placeholder: str = "", enter_inserts_newline: bool = False, style: Style = default
) -> Component:
    @component
    def root() -> Div:
        value, set_value = use_state(initial)
        return Div(
            style=col,
            children=[
                text_area(
                    value,
                    set_value,
                    placeholder=placeholder,
                    enter_inserts_newline=enter_inserts_newline,
                    style=width(12) | style,
                    auto_focus=True,
                )
            ],
        )

    return root()


async def test_text_area_wraps_its_value_to_its_box_and_grows_to_fit_its_rows() -> None:
    frame = await screenshot(area(initial="hello world foo"), dimensions=(14, 6))

    assert lines(frame) == ["╭──────────╮", "│ hello    │", "│ world    │", "│ foo      │", "╰──────────╯", ""]


async def test_text_area_draws_the_cursor_after_the_last_row() -> None:
    frame = await screenshot(area(initial="hello world foo"), dimensions=(14, 6))

    assert cursor_cells(frame) == [(5, 3, " ")]


async def test_text_area_shows_its_placeholder_while_empty_with_the_cursor_on_its_first_character() -> None:
    frame = await screenshot(area(placeholder="Notes"))

    assert (lines(frame)[1], cursor_cells(frame)) == ("│ Notes    │", [(2, 1, "N")])


async def test_text_area_passes_on_whether_enter_inserts_a_line_break() -> None:
    frame = await screenshot(
        area(initial="ab", enter_inserts_newline=True),
        events=(KeyPressed(key="enter"), KeyPressed(key="c")),
        dimensions=(14, 5),
    )

    assert lines(frame)[1:3] == ["│ ab       │", "│ c        │"]


async def test_text_area_past_its_max_height_scrolls_to_keep_the_cursor_in_view_as_it_types() -> None:
    frame = await screenshot(
        area(style=max_height(4)),
        events=tuple(KeyPressed(key=c) for c in "aaaaaa bbbbbb cccccc dd"),
        dimensions=(14, 5),
    )

    assert (lines(frame)[:4], cursor_cells(frame)) == (
        ["╭──────────╮", "│ cccccc   │", "│ dd       │", "╰──────────╯"],
        [(4, 2, " ")],
    )


async def test_text_area_past_its_max_height_scrolls_to_keep_the_cursor_in_view_as_it_moves() -> None:
    frame = await screenshot(
        area(initial="aaaaaa bbbbbb cccccc dd", style=max_height(4)),
        events=(KeyPressed(key=Key.Left),),
        dimensions=(14, 5),
    )

    assert lines(frame)[1:3] == ["│ cccccc   │", "│ dd       │"]


async def test_the_wheel_scrolls_a_text_area_past_its_max_height() -> None:
    frame = await screenshot(
        area(style=max_height(4)),
        events=(
            *(KeyPressed(key=c) for c in "aaaaaa bbbbbb cccccc dd"),
            MouseScrolledUp(absolute=Position(x=3, y=1)),
        ),
        dimensions=(14, 5),
    )

    assert lines(frame)[1:3] == ["│ aaaaaa   │", "│ bbbbbb   │"]
