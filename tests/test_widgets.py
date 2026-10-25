import io
import os
from asyncio import wait_for
from collections.abc import Sequence
from typing import Literal

import pytest

from counterweight import app
from counterweight._output import Frame
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import AnyControl
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.controls import ScrollBy
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseMoved
from counterweight.events import MouseScrolledDown
from counterweight.events import MouseScrolledUp
from counterweight.events import MouseUp
from counterweight.events import Pasted
from counterweight.events import Receiver
from counterweight.focus import ElementHandle
from counterweight.geometry import Position
from counterweight.handlers import first
from counterweight.handlers import scroll_on_keys
from counterweight.handlers import tab_focus
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles import AnyColor
from counterweight.styles import CellStyle
from counterweight.styles import Style
from counterweight.styles.utilities import align_self_start
from counterweight.styles.utilities import border
from counterweight.styles.utilities import border_color
from counterweight.styles.utilities import border_heavy
from counterweight.styles.utilities import border_none
from counterweight.styles.utilities import col
from counterweight.styles.utilities import default
from counterweight.styles.utilities import fill
from counterweight.styles.utilities import height
from counterweight.styles.utilities import max_height
from counterweight.styles.utilities import overflow_y_scroll
from counterweight.styles.utilities import pad_x
from counterweight.styles.utilities import pad_y
from counterweight.styles.utilities import row
from counterweight.styles.utilities import text_color
from counterweight.styles.utilities import width
from counterweight.widgets import ComboboxStyles
from counterweight.widgets import TextFieldStyles
from counterweight.widgets import combobox
from counterweight.widgets import text_area
from counterweight.widgets import text_input
from tests.rendering import TIMEOUT
from tests.terminal import Terminal

CURSOR = TextFieldStyles().cursor
ALPHABET = "abcdefghijklmnopqrstuvwxyz"

CUSTOM = TextFieldStyles(
    box=border | border_heavy | border_color("amber", 400) | pad_x(1),
    focused_box=border_color("green", 400),
    cursor=CellStyle(bold=True),
    placeholder=CellStyle(italic=True),
)


def custom_drawn(frame: Frame) -> tuple[str, AnyColor, bool, bool, bool]:
    """
    How a focused field drawn with `CUSTOM` and the placeholder "Name" looks: its top-left corner and that corner's color,
    whether the cursor on the placeholder's first character is bold and italic, and whether the next character is italic.
    """
    top, middle, *_ = frame.paint.rows()
    return (
        top[0].grapheme,
        top[0].style.foreground,
        middle[2].style.bold,
        middle[2].style.italic,
        middle[3].style.italic,
    )


CUSTOM_DRAWN = ("┏", border_color("green", 400).border_style.foreground, True, True, True)


def field(
    initial: str = "",
    placeholder: str = "",
    auto_focus: bool = True,
    is_focusable: bool = True,
    style: Style = default,
    styles: TextFieldStyles = TextFieldStyles(),
) -> Component:
    @component
    def root() -> Div:
        value, set_value = use_state(initial)
        return Div(
            style=col,
            children=(
                text_input(
                    value,
                    set_value,
                    placeholder=placeholder,
                    style=width(12) | style,
                    styles=styles,
                    auto_focus=auto_focus,
                    is_focusable=is_focusable,
                ),
            ),
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


async def test_a_press_on_a_text_input_focuses_it_with_the_cursor_on_the_cell_pressed() -> None:
    frame = await screenshot(
        field(initial="hi", auto_focus=False), events=(MouseDown(absolute=Position(x=3, y=1), button=1),)
    )

    assert cursor_cells(frame) == [(3, 1, "i")]


async def test_a_press_past_a_text_inputs_value_puts_the_cursor_at_its_end() -> None:
    frame = await screenshot(field(initial="hi"), events=(MouseDown(absolute=Position(x=8, y=1), button=1),))

    assert cursor_cells(frame) == [(4, 1, " ")]


async def test_a_press_on_a_scrolled_text_input_puts_the_cursor_on_the_cell_pressed() -> None:
    frame = await screenshot(field(initial=ALPHABET), events=(MouseDown(absolute=Position(x=3, y=1), button=1),))

    assert cursor_cells(frame) == [(3, 1, "u")]


async def test_a_press_of_another_button_focuses_a_text_input_and_leaves_its_cursor() -> None:
    frame = await screenshot(
        field(initial="hi", auto_focus=False), events=(MouseDown(absolute=Position(x=2, y=1), button=3),)
    )

    assert cursor_cells(frame) == [(4, 1, " ")]


async def test_a_press_on_an_unfocusable_text_input_does_nothing() -> None:
    frame = await screenshot(
        field(initial="hi", auto_focus=False, is_focusable=False),
        events=(MouseDown(absolute=Position(x=2, y=1), button=1),),
    )

    assert cursor_cells(frame) == []


async def test_text_input_whose_value_is_wider_than_its_box_starts_scrolled_to_the_cursor_at_its_end() -> None:
    frame = await screenshot(field(initial=ALPHABET))

    assert (lines(frame)[1], cursor_cells(frame)) == ("│ tuvwxyz  │", [(9, 1, " ")])


async def test_text_input_scrolls_its_value_to_bring_the_cursor_into_view_as_it_moves_back() -> None:
    frame = await screenshot(field(initial=ALPHABET), events=(KeyPressed(key=Key.Home),))

    assert (lines(frame)[1], cursor_cells(frame)) == ("│ abcdefgh │", [(2, 1, "a")])


async def test_text_input_scrolls_its_value_to_bring_the_cursor_into_view_as_it_moves_on() -> None:
    frame = await screenshot(
        field(initial=ALPHABET),
        events=(KeyPressed(key=Key.Home), *(KeyPressed(key=Key.Right) for _ in range(10))),
    )

    assert (lines(frame)[1], cursor_cells(frame)) == ("│ defghijk │", [(9, 1, "k")])


async def test_text_input_shrinks_beside_its_siblings_and_scrolls_rather_than_grow_to_fit_its_value() -> None:
    @component
    def root() -> Div:
        value, set_value = use_state(ALPHABET)
        return Div(
            style=row | width(20),
            children=(text_input(value, set_value, style=align_self_start), Text(content="|right")),
        )

    frame = await screenshot(root(), dimensions=(20, 3))

    assert lines(frame) == ["╭────────────╮|right", "│ rstuvwxyz  │", "╰────────────╯"]


async def test_text_input_in_a_column_that_overflows_keeps_its_height() -> None:
    @component
    def root() -> Div:
        value, set_value = use_state("hi")
        return Div(
            style=col | height(2) | overflow_y_scroll,
            children=(text_input(value, set_value, style=width(12)), Text(content="below")),
        )

    frame = await screenshot(root(), dimensions=(14, 2))

    assert lines(frame) == ["╭──────────╮", "│ hi       │"]


async def test_typing_in_a_text_input_scrolled_out_of_a_pane_scrolls_it_back_into_view() -> None:
    pane = ElementHandle()

    @component
    def root() -> Div:
        value, set_value = use_state("hi")
        return Div(
            style=col | height(3) | overflow_y_scroll,
            handle=pane,
            children=(
                text_input(value, set_value, style=width(12), auto_focus=True),
                Text(content="\n".join("below" for _ in range(10))),
            ),
        )

    frame = await screenshot(root(), events=(ScrollBy(pane, y=6), KeyPressed(key="!")), dimensions=(14, 3))

    assert lines(frame)[0] == "│ hi!      │"


async def test_text_input_style_merges_under_the_focused_border_color() -> None:
    frame = await screenshot(field(initial="hi", style=border_color("red", 500)))

    assert next(frame.paint.rows())[0].style.foreground == TextFieldStyles().focused_box.border_style.foreground


async def test_text_input_style_merges_over_the_unfocused_border_color() -> None:
    frame = await screenshot(field(initial="hi", auto_focus=False, style=border_color("red", 500)))

    assert next(frame.paint.rows())[0].style.foreground == border_color("red", 500).border_style.foreground


@pytest.mark.parametrize(
    ("is_focusable", "color"),
    [(True, text_color("red", 500)), (False, TextFieldStyles().unfocusable_box)],
)
async def test_text_input_style_merges_under_the_unfocusable_box_style_while_it_is_not_focusable(
    is_focusable: bool, color: Style
) -> None:
    frame = await screenshot(
        field(initial="hi", auto_focus=False, is_focusable=is_focusable, style=text_color("red", 500))
    )

    _, middle, _ = frame.paint.rows()

    assert middle[2].style.foreground == color.text_style.foreground


async def test_text_input_draws_its_box_cursor_and_placeholder_with_the_given_styles() -> None:
    frame = await screenshot(field(placeholder="Name", styles=CUSTOM))

    assert custom_drawn(frame) == CUSTOM_DRAWN


async def test_an_unfocusable_text_input_takes_no_keys() -> None:
    frame = await screenshot(field(initial="hi", is_focusable=False), events=(KeyPressed(key="!"),))

    assert (lines(frame)[1], cursor_cells(frame)) == ("│ hi       │", [])


def area(
    initial: str = "",
    placeholder: str = "",
    enter_inserts_newline: bool = False,
    tab_size: int = 4,
    style: Style = default,
    styles: TextFieldStyles = TextFieldStyles(),
) -> Component:
    @component
    def root() -> Div:
        value, set_value = use_state(initial)
        return Div(
            style=col,
            children=(
                text_area(
                    value,
                    set_value,
                    placeholder=placeholder,
                    enter_inserts_newline=enter_inserts_newline,
                    tab_size=tab_size,
                    style=width(12) | style,
                    styles=styles,
                    auto_focus=True,
                ),
            ),
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


async def test_text_area_draws_its_box_cursor_and_placeholder_with_the_given_styles() -> None:
    frame = await screenshot(area(placeholder="Name", styles=CUSTOM))

    assert custom_drawn(frame) == CUSTOM_DRAWN


async def test_text_area_passes_on_its_tab_size() -> None:
    frame = await screenshot(area(tab_size=2), events=(Pasted(text="\tx"),))

    assert lines(frame)[1] == "│   x      │"


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


async def test_text_area_scrolls_with_a_style_that_sets_overflow() -> None:
    frame = await screenshot(
        area(style=fill(1) | max_height(4)),
        events=tuple(KeyPressed(key=c) for c in "aaaaaa bbbbbb cccccc dd"),
        dimensions=(14, 5),
    )

    assert lines(frame)[1:3] == ["│ cccccc   │", "│ dd       │"]


async def test_text_area_past_its_max_height_scrolls_to_keep_the_cursor_in_view_as_it_moves() -> None:
    frame = await screenshot(
        area(initial="aaaaaa bbbbbb cccccc dd", style=max_height(4)),
        events=(KeyPressed(key=Key.Left),),
        dimensions=(14, 5),
    )

    assert lines(frame)[1:3] == ["│ cccccc   │", "│ dd       │"]


async def test_text_area_whose_initial_value_overflows_its_max_height_starts_scrolled_to_the_cursor() -> None:
    frame = await screenshot(area(initial="aaaaaa bbbbbb cccccc dd", style=max_height(4)), dimensions=(14, 5))

    assert (lines(frame)[1:3], cursor_cells(frame)) == (["│ cccccc   │", "│ dd       │"], [(4, 2, " ")])


async def test_text_area_in_a_column_that_overflows_keeps_the_height_of_its_rows() -> None:
    @component
    def root() -> Div:
        value, set_value = use_state("hello world")
        return Div(
            style=col | height(4) | overflow_y_scroll,
            children=(
                text_area(value, set_value, style=width(12)),
                Text(content="below"),
            ),
        )

    frame = await screenshot(root(), dimensions=(14, 4))

    assert lines(frame) == ["╭──────────╮", "│ hello    │", "│ world    │", "╰──────────╯"]


async def test_a_press_on_a_text_area_puts_the_cursor_on_the_cell_pressed() -> None:
    frame = await screenshot(
        area(initial="hello world foo"), events=(MouseDown(absolute=Position(x=4, y=2), button=1),), dimensions=(14, 6)
    )

    assert cursor_cells(frame) == [(4, 2, "r")]


async def test_a_press_past_a_rows_text_puts_the_cursor_at_the_end_of_the_row() -> None:
    frame = await screenshot(
        area(initial="hello world foo"), events=(MouseDown(absolute=Position(x=10, y=3), button=1),), dimensions=(14, 6)
    )

    assert cursor_cells(frame) == [(5, 3, " ")]


async def test_a_press_on_a_scrolled_text_area_puts_the_cursor_on_the_cell_pressed() -> None:
    frame = await screenshot(
        area(initial="aaaaaa bbbbbb cccccc dd", style=max_height(4)),
        events=(MouseDown(absolute=Position(x=3, y=1), button=1),),
        dimensions=(14, 5),
    )

    assert cursor_cells(frame) == [(3, 1, "c")]


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


async def test_page_down_in_a_text_area_moves_the_cursor_and_scrolls_the_box_by_a_page() -> None:
    frame = await screenshot(
        area(initial="1\n2\n3\n4\n5\n6\n7\n8\n9", style=max_height(6)),
        events=(KeyPressed(key=Key.ControlHome), KeyPressed(key=Key.PageDown)),
        dimensions=(14, 7),
    )

    assert ([line[2] for line in lines(frame)[1:5]], cursor_cells(frame)) == (["4", "5", "6", "7"], [(2, 1, "4")])


async def test_page_up_in_a_text_area_moves_the_cursor_and_scrolls_the_box_by_a_page() -> None:
    frame = await screenshot(
        area(initial="1\n2\n3\n4\n5\n6\n7\n8\n9", style=max_height(6)),
        events=(KeyPressed(key=Key.PageUp),),
        dimensions=(14, 7),
    )

    assert ([line[2] for line in lines(frame)[1:5]], cursor_cells(frame)) == (["3", "4", "5", "6"], [(3, 4, " ")])


async def test_paging_in_a_text_area_leaves_the_pane_around_it_where_it_is() -> None:
    @component
    def root() -> Div:
        value, set_value = use_state("1\n2\n3")
        return Div(
            style=col | height(5) | overflow_y_scroll,
            on_input=scroll_on_keys(),
            children=(
                text_area(value, set_value, style=width(12), auto_focus=True),
                Text(content="\n".join("below" for _ in range(10))),
            ),
        )

    frame = await screenshot(root(), events=(KeyPressed(key=Key.PageDown),), dimensions=(14, 5))

    assert lines(frame)[0] == "╭──────────╮"


PACKAGES = ("mypy", "pydantic", "pydantic-settings", "pytest", "ruff")
HIGHLIGHTED = ComboboxStyles().highlighted_option.text_style.background


def picking(
    top: int = 0,
    opens: Literal["auto", "below", "above"] = "auto",
    opens_on: Literal["input", "focus"] = "input",
    ends: Literal["wrap", "stop", "release"] = "stop",
    style: Style = width(24),
    styles: ComboboxStyles = ComboboxStyles(),
) -> Component:
    """
    The combobox's value and the keys that reached the root, `top` rows above a combobox,
    which a second field follows.
    """

    @component
    def root() -> Div:
        value, set_value = use_state("")
        other, set_other = use_state("")
        reached, set_reached = use_state("")

        def on_input(event: InputEvent, _: Receiver) -> InputResponse:
            if isinstance(event, KeyPressed):
                set_reached(lambda keys: f"{keys} {event.key}".strip())
            return None

        return Div(
            style=col,
            on_input=first(tab_focus, on_input),
            children=(
                Text(content=f"value={value}"),
                Text(content=f"reached={reached}"),
                Div(style=height(top)),
                combobox(
                    value,
                    set_value,
                    PACKAGES,
                    opens=opens,
                    opens_on=opens_on,
                    ends=ends,
                    shown_rows=3,
                    style=style,
                    styles=styles,
                    auto_focus=True,
                ),
                text_input(other, set_other, style=width(24)),
            ),
        )

    return root()


def highlighted_rows(frame: Frame) -> list[str]:
    """The text of each row drawn in the highlighted option's colors."""
    return [
        "".join(cell.grapheme for cell in row).strip(" │")
        for row in frame.paint.rows()
        if any(cell.style.background == HIGHLIGHTED for cell in row)
    ]


def shown(frame: Frame) -> str:
    return "\n".join(lines(frame))


TYPED_PY = tuple(KeyPressed(key=character) for character in "py")
DOWN = KeyPressed(key=Key.Down)
UP = KeyPressed(key=Key.Up)
ENTER = KeyPressed(key=Key.Enter)
ESCAPE = KeyPressed(key=Key.Escape)
TAB = KeyPressed(key=Key.Tab)


async def test_a_combobox_opens_its_list_below_on_an_edit() -> None:
    frame = await screenshot(picking(), TYPED_PY, (30, 14))

    assert lines(frame)[5:8] == ["╭──────────────────────╮", "│ mypy                 │", "│ pydantic             │"]
    assert highlighted_rows(frame) == ["mypy"]


async def test_a_combobox_stays_closed_until_an_edit() -> None:
    frame = await screenshot(picking(), (), (30, 14))

    assert "mypy" not in shown(frame)


async def test_a_combobox_opens_above_when_told_to() -> None:
    frame = await screenshot(picking(top=6, opens="above"), TYPED_PY, (30, 14))

    assert lines(frame)[3:5] == ["╭──────────────────────╮", "│ mypy                 │"]


async def test_a_combobox_flips_its_list_above_near_the_bottom_of_the_screen() -> None:
    frame = await screenshot(picking(top=5), TYPED_PY, (30, 13))

    assert lines(frame)[2:4] == ["╭──────────────────────╮", "│ mypy                 │"]


async def test_a_combobox_opens_below_near_the_bottom_when_told_to() -> None:
    frame = await screenshot(picking(top=5, opens="below"), TYPED_PY, (30, 13))

    assert lines(frame)[10:12] == ["╭──────────────────────╮", "│ mypy                 │"]


async def test_choosing_fills_in_the_text_and_closes_the_list() -> None:
    frame = await screenshot(picking(), (*TYPED_PY, DOWN, ENTER), (30, 14))

    assert ("value=pydantic" in shown(frame), "pytest" in shown(frame)) == (True, False)


async def test_escape_closes_the_list_and_up_reopens_it_on_the_last_option() -> None:
    closed = await screenshot(picking(), (*TYPED_PY, ESCAPE), (30, 14))
    reopened = await screenshot(picking(), (*TYPED_PY, ESCAPE, UP), (30, 14))

    assert ("mypy" in shown(closed), highlighted_rows(reopened)) == (False, ["pytest"])


async def test_escape_on_a_closed_list_bubbles() -> None:
    frame = await screenshot(picking(), (*TYPED_PY, ESCAPE, ESCAPE), (30, 14))

    assert "reached=Key.Escape" in shown(frame)


async def test_down_in_an_empty_field_lists_every_option() -> None:
    frame = await screenshot(picking(), (DOWN,), (30, 14))

    assert (highlighted_rows(frame), "pydantic-settings" in shown(frame)) == (["mypy"], True)


async def test_a_combobox_that_opens_on_focus_is_open_while_focused_and_again_once_focus_returns() -> None:
    opened = await screenshot(picking(opens_on="focus"), (), (30, 14))
    closed = await screenshot(picking(opens_on="focus"), (ESCAPE,), (30, 14))
    returned = await screenshot(picking(opens_on="focus"), (ESCAPE, TAB, KeyPressed(key=Key.BackTab)), (30, 14))

    assert ("mypy" in shown(opened), "mypy" in shown(closed), "mypy" in shown(returned)) == (True, False, True)


async def test_tab_on_a_list_that_focus_opened_moves_focus_without_choosing() -> None:
    frame = await screenshot(picking(opens_on="focus"), (TAB, KeyPressed(key="!")), (30, 14))

    assert (lines(frame)[0], lines(frame)[6]) == ("value=", "│ !                    │")


async def test_a_list_under_a_field_without_a_border_opens_against_the_field() -> None:
    frame = await screenshot(picking(style=width(24) | border_none), TYPED_PY, (30, 14))

    assert lines(frame)[3:5] == ["╭──────────────────────╮", "│ mypy                 │"]


async def test_the_list_boxs_padding_leaves_room_for_every_shown_row() -> None:
    padded = ComboboxStyles(list_box=ComboboxStyles().list_box | pad_y(1))
    frame = await screenshot(picking(styles=padded), (DOWN,), (30, 14))

    assert lines(frame)[7:10] == ["│ mypy                 │", "│ pydantic             │", "│ pydantic-settings    │"]


@pytest.mark.parametrize(
    ("ends", "moves", "expected"),
    [
        ("stop", (DOWN,) * 5, ["pytest"]),
        ("stop", (UP,), ["mypy"]),
        ("wrap", (DOWN,) * 4, ["mypy"]),
        ("wrap", (UP,), ["pytest"]),
        ("release", (DOWN,) * 4, []),
        ("release", (DOWN,) * 5, ["mypy"]),
    ],
    ids=["stops on the last", "stops on the first", "wraps to the first", "wraps to the last", "releases", "re-enters"],
)
async def test_moving_past_the_ends_does_what_ends_says(
    ends: Literal["wrap", "stop", "release"], moves: tuple[KeyPressed, ...], expected: list[str]
) -> None:
    frame = await screenshot(picking(ends=ends), (*TYPED_PY, *moves), (30, 14))

    assert highlighted_rows(frame) == expected


async def test_enter_with_nothing_highlighted_bubbles() -> None:
    frame = await screenshot(picking(ends="release"), (*TYPED_PY, UP, ENTER), (30, 14))

    assert ("value=py" in shown(frame), "reached=Key.Enter" in shown(frame)) == (True, True)


async def test_tab_chooses_without_moving_focus() -> None:
    frame = await screenshot(picking(), (*TYPED_PY, TAB, KeyPressed(key="!")), (30, 14))

    assert "value=mypy!" in shown(frame)


async def test_tab_on_a_closed_list_moves_focus() -> None:
    frame = await screenshot(picking(), (TAB, KeyPressed(key="!")), (30, 14))

    assert lines(frame)[6] == "│ !                    │"


async def test_the_list_keys_reach_no_parent_while_nothing_matches() -> None:
    nothing = tuple(KeyPressed(key=character) for character in "zz")
    frame = await screenshot(
        picking(), (*nothing, DOWN, UP, ENTER, KeyPressed(key=Key.ControlJ), TAB, ESCAPE, ESCAPE), (30, 14)
    )

    assert ("nothing matches" not in shown(frame), "reached=Key.Escape" in shown(frame)) == (True, True)


async def test_an_open_list_that_nothing_matches_says_so() -> None:
    frame = await screenshot(picking(), tuple(KeyPressed(key=character) for character in "zz"), (30, 14))

    assert "│ nothing matches      │" in lines(frame)


async def test_hovering_an_option_highlights_it() -> None:
    frame = await screenshot(picking(), (*TYPED_PY, MouseMoved(absolute=Position(4, 7), button=None)), (30, 14))

    assert highlighted_rows(frame) == ["pydantic"]


async def test_clicking_an_option_chooses_it_and_keeps_focus_in_the_field() -> None:
    clicked = (
        MouseDown(absolute=Position(4, 7), button=1),
        MouseUp(absolute=Position(4, 7), button=1),
        KeyPressed(key="!"),
    )
    frame = await screenshot(picking(), (*TYPED_PY, *clicked), (30, 14))

    assert "value=pydantic!" in shown(frame)


async def test_the_wheel_scrolls_the_list() -> None:
    frame = await screenshot(picking(), (DOWN, MouseScrolledDown(absolute=Position(4, 7))), (30, 14))

    assert lines(frame)[6] == "│ pydantic             │"


async def test_text_and_enter_typed_before_a_render_choose_from_what_the_text_matches(terminal: Terminal) -> None:
    values: list[str] = []

    @component
    def root() -> Div:
        value, set_value = use_state("")
        values.append(value)

        def quit_on_a_key_the_combobox_lets_bubble(event: InputEvent, _: Receiver) -> InputResponse:
            return Quit() if isinstance(event, KeyPressed) else None

        return Div(
            on_input=quit_on_a_key_the_combobox_lets_bubble,
            children=(combobox(value, set_value, PACKAGES, auto_focus=True),),
        )

    # Written before the app makes the terminal raw, so the terminal turns the Enter into a line feed, Ctrl+J.
    # Enter chooses, and then the Tab on the closed list bubbles; Enter decided from the last render would bubble.
    os.write(terminal.keyboard, b"pyd\r\t")

    await wait_for(app(root(), output_stream=io.StringIO(), input_stream=terminal.stream, dimensions=(30, 10)), TIMEOUT)

    assert values[-1] == "pydantic"


async def test_a_paste_opens_the_list() -> None:
    frame = await screenshot(picking(), (Pasted(text="pyt"),), (30, 14))

    assert highlighted_rows(frame) == ["pydantic"]
