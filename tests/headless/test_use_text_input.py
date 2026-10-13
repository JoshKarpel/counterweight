from collections.abc import Callable, Sequence
from dataclasses import dataclass

from counterweight import app
from counterweight.components import component
from counterweight.controls import AnyControl, Quit
from counterweight.elements import Div, Text
from counterweight.events import InputEvent, InputHandler, InputResponse, KeyPressed, MouseDown, Pasted, Receiver
from counterweight.geometry import Position
from counterweight.handlers import each, first
from counterweight.headless import TextInput, use_text_input
from counterweight.hooks import use_state
from counterweight.keys import Key

type Wrap = Callable[[Callable[[Callable[[str], str]], None]], Callable[[Callable[[str], str]], None]]


@dataclass(frozen=True, slots=True)
class Shown:
    """What a field's render saw: its value, and the hook's split of it around the cursor."""

    value: str
    before: str
    at: str
    after: str

    @classmethod
    def of(cls, value: str, field: TextInput) -> Shown:
        return cls(value=value, before=field.before_cursor, at=field.at_cursor, after=field.after_cursor)


def typed(text: str) -> tuple[KeyPressed, ...]:
    return tuple(KeyPressed(key=character) for character in text)


async def run(
    events: Sequence[InputEvent | AnyControl],
    initial: str = "",
    auto_focus: bool = True,
    wrap: Wrap = lambda set_value: set_value,
    compose: Callable[[InputHandler], InputHandler] = lambda handler: handler,
    on_parent: InputHandler | None = None,
) -> list[Shown]:
    """
    Runs a field whose root element takes `compose(field.on_input)`, inside a parent with `on_parent`,
    and returns what each of the field's renders showed.
    """
    shown: list[Shown] = []

    @component
    def field() -> Text:
        value, set_value = use_state(initial)
        text_input = use_text_input(value, wrap(set_value), auto_focus=auto_focus)
        shown.append(Shown.of(value, text_input))
        return Text(content=value, on_input=compose(text_input.on_input))

    @component
    def parent() -> Div:
        return Div(on_input=on_parent, children=(field(),))

    await app(parent(), headless=True, dimensions=(20, 3), autopilot=(*events, Quit()), check_purity=True)
    return shown


async def test_typing_inserts_at_the_cursor_and_splits_the_value_around_it() -> None:
    shown = await run((*typed("abc"), KeyPressed(key=Key.Left), KeyPressed(key=Key.Left), *typed("x")))

    assert shown[-1] == Shown(value="axbc", before="ax", at="b", after="c")


async def test_at_cursor_is_a_space_at_the_end_of_the_value() -> None:
    shown = await run(typed("ab"))

    assert shown[-1] == Shown(value="ab", before="ab", at=" ", after="")


async def test_the_cursor_starts_at_the_end_of_the_initial_value() -> None:
    shown = await run((), initial="hello")

    assert shown[-1] == Shown(value="hello", before="hello", at=" ", after="")


async def test_edits_before_the_next_render_each_start_from_the_one_before() -> None:
    shown = await run(
        (*typed("ab"), KeyPressed(key=Key.Left), *typed("x")),
        compose=lambda handler: each(handler, handler),
    )

    assert shown[-1] == Shown(value="aaxxbb", before="aaxx", at="b", after="b")


async def test_a_paste_inserts_its_text_in_one_edit() -> None:
    edits: list[Callable[[str], str]] = []

    def counted(set_value: Callable[[Callable[[str], str]], None]) -> Callable[[Callable[[str], str]], None]:
        def set_counted(edit: Callable[[str], str]) -> None:
            edits.append(edit)
            set_value(edit)

        return set_counted

    shown = await run((*typed("<>"), KeyPressed(key=Key.Left), Pasted(text="one\ntwo")), wrap=counted)

    assert shown[-1] == Shown(value="<one two>", before="<one two", at=">", after="")
    # Each edit reads the value before and after, so a paste is three calls, as one key press is.
    assert len(edits) == 3 * 4


def digits_only(set_value: Callable[[Callable[[str], str]], None]) -> Callable[[Callable[[str], str]], None]:
    def set_digits(edit: Callable[[str], str]) -> None:
        set_value(lambda value: edited if (edited := edit(value)).isdigit() else value)

    return set_digits


async def test_an_edit_the_setter_rejects_leaves_the_value_and_the_cursor() -> None:
    shown = await run((KeyPressed(key=Key.Left), *typed("x5")), initial="12", wrap=digits_only)

    assert shown[-1] == Shown(value="152", before="15", at="2", after="")


async def test_a_setter_that_ignores_edits_leaves_the_cursor() -> None:
    shown = await run((KeyPressed(key=Key.Left), *typed("x")), initial="ab", wrap=lambda set_value: lambda edit: None)

    assert shown[-1] == Shown(value="ab", before="a", at="b", after="")


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
        field = use_text_input(value, set_value, auto_focus=True)
        shown.append(Shown.of(value, field))

        def replace(event: InputEvent, _: Receiver) -> InputResponse:
            set_value(replacement)
            return ()

        return Text(content=value, on_input=compose(field.on_input, replace))

    await app(root(), headless=True, dimensions=(30, 3), autopilot=(*events, Quit()), check_purity=True)
    return shown


async def test_a_value_changed_other_than_by_an_edit_puts_the_cursor_at_its_end() -> None:
    shown = await run_replacing(
        (KeyPressed(key=Key.Left), KeyPressed(key=Key.Enter), *typed("!")),
        initial="ab",
        replacement="hello",
        compose=first,
    )

    assert [shown[-3], shown[-1]] == [
        Shown(value="hello", before="hello", at=" ", after=""),
        Shown(value="hello!", before="hello!", at=" ", after=""),
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

    assert shown[-1] == Shown(value="hello!", before="hello!", at=" ", after="")


async def test_keys_the_field_does_not_edit_with_bubble_to_its_parent() -> None:
    reached: list[InputEvent] = []

    def record(event: InputEvent, _: Receiver) -> InputResponse:
        reached.append(event)
        return ()

    shown = await run((*typed("a"), KeyPressed(key=Key.Enter), KeyPressed(key=Key.Tab)), on_parent=record)

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
        field = use_text_input(value, set_value)
        return Text(content=value, on_input=first(field.on_input, record))

    await app(root(), headless=True, dimensions=(20, 3), autopilot=(*typed("a"), Pasted(text="b"), Quit()))

    assert reached == [KeyPressed(key="a"), Pasted(text="b")]


async def test_the_field_reports_its_focus() -> None:
    focused: list[bool] = []

    @component
    def root() -> Text:
        value, set_value = use_state("")
        field = use_text_input(value, set_value, auto_focus=True)
        focused.append(field.focus.is_focused)
        return Text(content=value, on_input=field.on_input)

    await app(root(), headless=True, dimensions=(20, 3), autopilot=(Quit(),))

    assert focused[-1]
