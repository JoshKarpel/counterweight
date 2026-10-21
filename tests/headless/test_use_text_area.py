from collections.abc import Callable
from collections.abc import Sequence
from dataclasses import dataclass

import pytest

from counterweight import app
from counterweight._input_parsing import parse_input
from counterweight.components import component
from counterweight.controls import AnyControl
from counterweight.controls import FocusNext
from counterweight.controls import FocusOn
from counterweight.controls import Quit
from counterweight.controls import ScrollIntoView
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputHandler
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import Pasted
from counterweight.events import Receiver
from counterweight.focus import ElementHandle
from counterweight.focus import FocusHandle
from counterweight.geometry import Position
from counterweight.handlers import each
from counterweight.handlers import first
from counterweight.headless import TextArea
from counterweight.headless import use_text_area
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles.utilities import height

type Wrap = Callable[[Callable[[Callable[[str], str]], None]], Callable[[Callable[[str], str]], None]]

WIDTH = 8


@dataclass(frozen=True, slots=True)
class Shown:
    """What a field's render saw: its value, and the hook's split of its rows around the cursor."""

    value: str
    before: str
    at: str
    after: str
    cursor: int

    @classmethod
    def of(cls, value: str, field: TextArea) -> Shown:
        return cls(
            value=value, before=field.before_cursor, at=field.at_cursor, after=field.after_cursor, cursor=field.cursor
        )


def typed(text: str) -> tuple[KeyPressed, ...]:
    return tuple(KeyPressed(key=character) for character in text)


def pressed(*keys: Key) -> tuple[KeyPressed, ...]:
    return tuple(KeyPressed(key=key) for key in keys)


def sent(data: bytes) -> tuple[KeyPressed, ...]:
    """The key presses a terminal's input of `data` parses to, which MUST all be key presses."""
    events = parse_input(data, is_final=True).events
    keys = tuple(event for event in events if isinstance(event, KeyPressed))
    assert keys == events
    return keys


async def run(
    events: Sequence[InputEvent | AnyControl],
    initial: str = "",
    enter_inserts_newline: bool = False,
    auto_focus: bool = True,
    wrap: Wrap = lambda set_value: set_value,
    compose: Callable[[InputHandler], InputHandler] = lambda handler: handler,
    on_parent: InputHandler | None = None,
) -> list[Shown]:
    """
    Runs a field `WIDTH` cells wide whose root element takes `compose(field.on_input)`, inside a parent with `on_parent`,
    and returns what each of the field's renders showed.
    """
    shown: list[Shown] = []

    @component
    def field() -> Text:
        value, set_value = use_state(initial)
        text_area = use_text_area(
            value, wrap(set_value), width=WIDTH, enter_inserts_newline=enter_inserts_newline, auto_focus=auto_focus
        )
        shown.append(Shown.of(value, text_area))
        return Text(content=value, on_input=compose(text_area.on_input))

    @component
    def parent() -> Div:
        return Div(on_input=on_parent, children=(field(),))

    await app(parent(), headless=True, dimensions=(20, 5), autopilot=(*events, Quit()), check_purity=True)
    return shown


async def test_typing_inserts_at_the_cursor_and_splits_the_value_around_it() -> None:
    shown = await run((*typed("abc"), *pressed(Key.Left, Key.Left), *typed("x")))

    assert shown[-1] == Shown(value="axbc", before="ax", at="b", after="c", cursor=2)


async def test_the_value_is_split_into_rows_of_the_given_width() -> None:
    shown = await run((), initial="hello world foo")

    assert shown[-1] == Shown(value="hello world foo", before="hello \nworld \nfoo", at=" ", after="", cursor=15)


async def test_up_moves_the_cursor_to_the_row_above() -> None:
    shown = await run((*pressed(Key.Up), *typed("X")), initial="hello world foo")

    assert shown[-1] == Shown(value="hello worXld foo", before="hello \nworX", at="l", after="d \nfoo", cursor=10)


async def test_ctrl_j_inserts_a_line_break() -> None:
    shown = await run((*typed("ab"), *pressed(Key.ControlJ), *typed("c")))

    assert shown[-1] == Shown(value="ab\nc", before="ab\nc", at=" ", after="", cursor=4)


async def test_enter_inserts_a_line_break_if_asked_to() -> None:
    shown = await run((*typed("ab"), *pressed(Key.Enter), *typed("c")), enter_inserts_newline=True)

    assert shown[-1].value == "ab\nc"


async def test_alt_enter_from_the_terminal_inserts_a_line_break_where_enter_bubbles() -> None:
    reached: list[InputEvent] = []

    def record(event: InputEvent, _: Receiver) -> InputResponse:
        reached.append(event)
        return ()

    shown = await run(sent(b"ab\x1b\rc\r"), on_parent=record)

    assert reached == [KeyPressed(key=Key.Enter)]
    assert shown[-1] == Shown(value="ab\nc", before="ab\nc", at=" ", after="", cursor=4)


async def test_edits_before_the_next_render_each_start_from_the_one_before() -> None:
    shown = await run(
        (*typed("ab"), KeyPressed(key=Key.Left), *typed("x")),
        compose=lambda handler: each(handler, handler),
    )

    assert shown[-1] == Shown(value="aaxxbb", before="aaxx", at="b", after="b", cursor=4)


async def test_a_paste_inserts_its_text_with_its_line_breaks_in_one_edit() -> None:
    edits: list[Callable[[str], str]] = []

    def counted(set_value: Callable[[Callable[[str], str]], None]) -> Callable[[Callable[[str], str]], None]:
        def set_counted(edit: Callable[[str], str]) -> None:
            edits.append(edit)
            set_value(edit)

        return set_counted

    shown = await run((*typed("<>"), KeyPressed(key=Key.Left), Pasted(text="one\ntwo")), wrap=counted)

    assert shown[-1] == Shown(value="<one\ntwo>", before="<one\ntwo", at=">", after="", cursor=8)
    # Each edit reads the value before and after, so a paste is three calls, as one key press is.
    assert len(edits) == 3 * 4


def digits_only(set_value: Callable[[Callable[[str], str]], None]) -> Callable[[Callable[[str], str]], None]:
    def set_digits(edit: Callable[[str], str]) -> None:
        set_value(lambda value: edited if (edited := edit(value)).isdigit() else value)

    return set_digits


async def test_an_edit_the_setter_rejects_leaves_the_value_and_the_cursor() -> None:
    shown = await run((KeyPressed(key=Key.Left), *typed("x5")), initial="12", wrap=digits_only)

    assert shown[-1] == Shown(value="152", before="15", at="2", after="", cursor=2)


async def test_a_setter_that_ignores_edits_leaves_the_cursor() -> None:
    shown = await run((KeyPressed(key=Key.Left), *typed("x")), initial="ab", wrap=lambda set_value: lambda edit: None)

    assert shown[-1] == Shown(value="ab", before="a", at="b", after="", cursor=1)


async def run_replacing(
    events: Sequence[InputEvent | AnyControl],
    initial: str,
    replacement: str,
    compose: Callable[[InputHandler, InputHandler], InputHandler],
) -> list[Shown]:
    """
    Runs a field whose root element takes `compose(field.on_input, replace)`,
    where `replace` sets the value to `replacement` on any event that reaches it, other than by an edit,
    and returns what each of the field's renders showed.
    """
    shown: list[Shown] = []

    @component
    def root() -> Text:
        value, set_value = use_state(initial)
        field = use_text_area(value, set_value, width=WIDTH, auto_focus=True)
        shown.append(Shown.of(value, field))

        def replace(event: InputEvent, _: Receiver) -> InputResponse:
            set_value(replacement)
            return ()

        return Text(content=value, on_input=compose(field.on_input, replace))

    await app(root(), headless=True, dimensions=(30, 5), autopilot=(*events, Quit()), check_purity=True)
    return shown


async def test_a_value_changed_other_than_by_an_edit_puts_the_cursor_at_its_end() -> None:
    shown = await run_replacing(
        (KeyPressed(key=Key.Left), KeyPressed(key=Key.Enter), *typed("!")),
        initial="ab",
        replacement="hello",
        compose=first,
    )

    assert [shown[-3], shown[-1]] == [
        Shown(value="hello", before="hello", at=" ", after="", cursor=5),
        Shown(value="hello!", before="hello!", at=" ", after="", cursor=6),
    ]


async def test_an_edit_after_a_change_before_the_next_render_starts_from_the_end() -> None:
    shown = await run_replacing(
        (KeyPressed(key=Key.Enter),),
        initial="ab",
        replacement="hello",
        # Enter replaces the value, then types "!" before the next render.
        compose=lambda on_input, replace: each(
            replace, lambda event, receiver: on_input(KeyPressed(key="!"), receiver)
        ),
    )

    assert shown[-1] == Shown(value="hello!", before="hello!", at=" ", after="", cursor=6)


async def test_keys_the_field_does_not_edit_with_bubble_to_its_parent() -> None:
    reached: list[InputEvent] = []

    def record(event: InputEvent, _: Receiver) -> InputResponse:
        reached.append(event)
        return ()

    shown = await run((*typed("a"), *pressed(Key.Enter, Key.Tab)), on_parent=record)

    assert reached == [KeyPressed(key=Key.Enter), KeyPressed(key=Key.Tab)]
    assert shown[-1].value == "a"


async def test_mouse_events_bubble_past_a_focused_field() -> None:
    reached: list[InputEvent] = []

    def record(event: InputEvent, _: Receiver) -> InputResponse:
        reached.append(event)
        return ()

    press = MouseDown(absolute=Position(x=0, y=0), button=1)
    shown = await run((press,), initial="ab", on_parent=record)

    assert (reached, shown[-1].value) == ([press], "ab")


async def test_an_unfocused_field_ignores_keys_and_pastes_that_reach_it() -> None:
    reached: list[InputEvent] = []

    def record(event: InputEvent, _: Receiver) -> InputResponse:
        reached.append(event)
        return ()

    @component
    def root() -> Text:
        value, set_value = use_state("")
        field = use_text_area(value, set_value, width=WIDTH)
        return Text(content=value, on_input=first(field.on_input, record))

    await app(root(), headless=True, dimensions=(20, 3), autopilot=(*typed("a"), Pasted(text="b"), Quit()))

    assert reached == [KeyPressed(key="a"), Pasted(text="b")]


async def test_the_field_reports_its_focus() -> None:
    focused: list[bool] = []

    @component
    def root() -> Text:
        value, set_value = use_state("")
        field = use_text_area(value, set_value, width=WIDTH, auto_focus=True)
        focused.append(field.focus.is_focused)
        return Text(content=value, on_input=field.on_input)

    await app(root(), headless=True, dimensions=(20, 3), autopilot=(Quit(),))

    assert focused[-1]


async def test_each_edit_scrolls_the_element_with_the_cursor_rows_handle_into_view() -> None:
    handles: list[ElementHandle] = []
    responses: list[InputResponse] = []

    def recorded(handler: InputHandler) -> InputHandler:
        def record(event: InputEvent, receiver: Receiver) -> InputResponse:
            responses.append(response := handler(event, receiver))
            return response

        return record

    @component
    def root() -> Text:
        value, set_value = use_state("")
        field = use_text_area(value, set_value, width=WIDTH, auto_focus=True)
        handles.append(field.cursor_row)
        return Text(content=value, on_input=recorded(field.on_input))

    await app(root(), headless=True, dimensions=(20, 3), autopilot=(*typed("a"), *pressed(Key.Left), Quit()))

    assert responses == [ScrollIntoView(handles[0], block="nearest")] * 2


@pytest.mark.parametrize(
    ("keys", "cursor"),
    [
        pytest.param((Key.ControlHome, Key.PageDown), 14, id="down"),
        pytest.param((Key.PageUp,), 3, id="up"),
    ],
)
async def test_paging_outside_a_scroll_container_moves_a_page_of_the_elements_height_without_scrolling_it(
    keys: tuple[Key, ...], cursor: int
) -> None:
    shown: list[Shown] = []
    handles: list[ElementHandle] = []
    responses: list[InputResponse] = []

    @component
    def root() -> Text:
        value, set_value = use_state("a\nb\nc\nd\ne\nf\ng\nh\nij")
        field = use_text_area(value, set_value, width=WIDTH, auto_focus=True)
        shown.append(Shown.of(value, field))
        handles.append(field.cursor_row)

        def record(event: InputEvent, receiver: Receiver) -> InputResponse:
            responses.append(response := field.on_input(event, receiver))
            return response

        return Text(content=value, style=height(8), on_input=record)

    await app(root(), headless=True, dimensions=(20, 9), autopilot=(*pressed(*keys), Quit()))

    assert (shown[-1].cursor, responses[-1]) == (cursor, ScrollIntoView(handles[0], block="nearest"))


async def test_paging_in_an_element_one_row_tall_moves_the_cursor_a_row() -> None:
    shown: list[Shown] = []

    @component
    def root() -> Text:
        value, set_value = use_state("a\nb\nc\nd")
        field = use_text_area(value, set_value, width=WIDTH, auto_focus=True)
        shown.append(Shown.of(value, field))
        return Text(content=value, style=height(1), on_input=field.on_input)

    await app(root(), headless=True, dimensions=(20, 3), autopilot=(*pressed(Key.ControlHome, Key.PageDown), Quit()))

    assert shown[-1].cursor == 2


async def test_a_paste_expands_tabs_to_stops_four_columns_apart_by_default() -> None:
    shown = await run((Pasted(text="\tx"),))

    assert shown[-1].value == "    x"


async def test_the_field_is_in_the_focus_order_by_default() -> None:
    focused: list[bool] = []

    @component
    def root() -> Text:
        value, set_value = use_state("")
        field = use_text_area(value, set_value, width=WIDTH)
        focused.append(field.focus.is_focused)
        return Text(content=value, on_input=field.on_input)

    await app(root(), headless=True, dimensions=(20, 3), autopilot=(FocusNext(), Quit()))

    assert focused[-1]


@pytest.mark.parametrize("in_focus_order", [True, False])
async def test_the_field_is_in_the_focus_order_unless_asked_not_to_be(in_focus_order: bool) -> None:
    focused: list[bool] = []

    @component
    def root() -> Text:
        value, set_value = use_state("")
        field = use_text_area(value, set_value, width=WIDTH, in_focus_order=in_focus_order)
        focused.append(field.focus.is_focused)
        return Text(content=value, on_input=field.on_input)

    await app(root(), headless=True, dimensions=(20, 3), autopilot=(FocusNext(), Quit()))

    assert focused[-1] == in_focus_order


async def test_an_unfocusable_field_does_not_take_focus_when_it_mounts() -> None:
    focused: list[bool] = []

    @component
    def root() -> Text:
        value, set_value = use_state("")
        field = use_text_area(value, set_value, width=WIDTH, auto_focus=True, is_focusable=False)
        focused.append(field.focus.is_focused)
        return Text(content=value, on_input=field.on_input)

    await app(root(), headless=True, dimensions=(20, 3), autopilot=(Quit(),))

    assert not focused[-1]


async def test_the_field_focuses_with_the_handle_it_is_given() -> None:
    handle = FocusHandle()
    handles: list[FocusHandle] = []

    @component
    def root() -> Text:
        value, set_value = use_state("")
        field = use_text_area(value, set_value, width=WIDTH, handle=handle)
        handles.append(field.focus.handle)
        return Text(content=value, on_input=field.on_input)

    await app(root(), headless=True, dimensions=(20, 3), autopilot=(Quit(),))

    assert handles[-1] is handle


async def test_a_press_focuses_the_field_and_scrolls_the_cursor_row_into_view() -> None:
    responses: list[InputResponse] = []
    fields: list[TextArea] = []

    @component
    def root() -> Text:
        value, set_value = use_state("hello world")
        field = use_text_area(value, set_value, width=WIDTH)
        fields.append(field)

        def record(event: InputEvent, receiver: Receiver) -> InputResponse:
            responses.append(response := field.on_press(event, receiver))
            return response

        return Text(content=value, on_input=record)

    await app(
        root(), headless=True, dimensions=(20, 3), autopilot=(MouseDown(absolute=Position(x=2, y=1), button=1), Quit())
    )

    assert responses == [(FocusOn(fields[0].focus.handle), ScrollIntoView(fields[0].cursor_row, block="nearest"))]
