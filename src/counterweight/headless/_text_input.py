"""[`use_text_input`][counterweight.headless.use_text_input], which edits one line of text and leaves drawing it to its caller."""

from __future__ import annotations

from dataclasses import dataclass

from counterweight.controls import FocusOn
from counterweight.controls import ScrollIntoView
from counterweight.events import InputEvent
from counterweight.events import InputHandler
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import Pasted
from counterweight.events import Receiver
from counterweight.focus import ElementHandle
from counterweight.focus import FocusHandle
from counterweight.geometry import ORIGIN
from counterweight.geometry import Position
from counterweight.headless._text_editing import Edit
from counterweight.headless._text_editing import EditableText
from counterweight.headless._text_editing import key_edit
from counterweight.headless._text_editing import move_to_column
from counterweight.headless._text_editing import next_cluster
from counterweight.headless._text_editing import paste_edit
from counterweight.headless._text_editing import settled
from counterweight.hooks import Editor
from counterweight.hooks import Focus
from counterweight.hooks import Getter
from counterweight.hooks import get_state
from counterweight.hooks import use_focus
from counterweight.hooks import use_state


@dataclass(frozen=True, slots=True)
class TextInput:
    """What [`use_text_input`][counterweight.headless.use_text_input] returns to the calling component."""

    before_cursor: str
    """The value's text before the cursor."""

    at_cursor: str
    """
    The grapheme cluster at the cursor,
    or a space when the cursor is at the end of the value, so there's always a cell to draw the cursor in.
    """

    after_cursor: str
    """The value's text after `at_cursor`."""

    cursor: int
    """
    How many of the value's code points come before the cursor, so `value[:cursor]` is the text before it,
    where this render placed it, for drawing.
    """

    latest_cursor: Getter[int]
    """
    Where the cursor is after every edit since this render, as the DOM's `selectionStart` is,
    for a handler that decides from it, such as one that accepts a completion on Right only at the end of the text,
    since several key presses can arrive before the next render.
    A value the calling component changed other than by an edit puts it at the end, as a render would.
    """

    cursor_cell: ElementHandle
    """
    The element handle for the calling component to give the element it draws `at_cursor` in,
    which `on_input` scrolls into view as the cursor moves,
    so a value wider than its box, drawn in a [scroll container](../layout/scrolling.md), keeps the cursor in view,
    as a browser's `<input>` does.
    """

    focus: Focus
    """
    Whether the calling component is focused, and its focus handle,
    as [`use_focus`][counterweight.hooks.use_focus] returns them.
    """

    on_input: InputHandler
    """
    The handler that edits the value, for the calling component to put on the element it returns.
    It returns [`ScrollIntoView`][counterweight.controls.ScrollIntoView] for `cursor_cell` for each event it edits with,
    and `None` for every event while that element isn't focused,
    and for the key presses it doesn't edit with, such as Enter, Tab, Up and Down,
    so they bubble to the element's ancestors.
    """

    on_press: InputHandler
    """
    The handler that moves the cursor to where a press lands, as a click in a browser's `<input>` does,
    for the calling component to put on the element it draws the value in,
    from the left edge of that element's content box, scrolled by that element's scroll if it's a scroll container.
    For a press of the left button, it moves the cursor to the cluster drawn across the cell pressed,
    or to the end of the value past it, and returns [`FocusOn`][counterweight.controls.FocusOn] for the component
    with [`ScrollIntoView`][counterweight.controls.ScrollIntoView] for `cursor_cell`.
    It returns `None` for every other event, and for every event while the component isn't focusable.
    """


def use_text_input(
    value: str,
    set_value: Editor[str],
    auto_focus: bool = False,
    handle: FocusHandle | None = None,
    is_focusable: bool = True,
    in_focus_order: bool = True,
) -> TextInput:
    """
    Edits one line of text, leaving how it's drawn to the calling component.
    The calling component owns the value, and the hook owns the cursor and makes the component focusable.

    Parameters:
        value: The text being edited.

        set_value: Called with a function from the latest value to the edited one for each edit,
            which it MUST call before returning, as a [`use_state`][counterweight.hooks.use_state] setter does,
            and return the value it settled at, as a `use_state` setter does.
            Several key presses can arrive between renders, as when typing fast,
            so an edit applies to the latest value rather than to `value`, which is the one this render saw.
            Validate or transform an edit by wrapping the setter:
            `lambda edit: set_value(lambda v: new if (new := edit(v)).isdigit() or not new else v)`
            keeps only digits, and lets the value be emptied.
            Each edit also calls it first with a function that returns the value it's given, to read the latest value,
            and the cursor moves with an edit unless the setter left the value as it was before it.

        auto_focus: Passed to [`use_focus`][counterweight.hooks.use_focus].

        handle: The focus handle passed to [`use_focus`][counterweight.hooks.use_focus].

        is_focusable: Passed to [`use_focus`][counterweight.hooks.use_focus].

        in_focus_order: Passed to [`use_focus`][counterweight.hooks.use_focus].

    Returns:
        The value split around the cursor, for the calling component to draw,
        the handler that edits it, for the calling component to put on the element it returns,
        and the handler that moves the cursor to a press, for the element it draws the value in.
        The cursor starts at the end of the value, and moves to the end when the value changes other than by an edit.
    """
    focus = use_focus(auto_focus=auto_focus, handle=handle, is_focusable=is_focusable, in_focus_order=in_focus_order)
    # The value the cursor was last placed in, so a value that differs from it was changed other than by an edit.
    text, set_text = use_state(lambda: EditableText(value=value, cursor=len(value), goal_column=None))
    cursor_cell, _ = use_state(ElementHandle)

    def apply(edit: Edit) -> None:
        set_text(lambda latest: edited(latest, edit, set_value))

    def latest_cursor() -> int:
        return get_state(set_text).following(get_state(set_value)).cursor

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        if not receiver.is_focused:
            return None

        match event:
            case KeyPressed(key=key):
                edit = key_edit(key)
            case Pasted(text=pasted):
                edit = paste_edit(pasted)
            case _:
                return None

        if edit is None:
            return None

        apply(edit)
        return ScrollIntoView(cursor_cell, block="nearest", inline="nearest")

    def on_press(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case MouseDown(absolute=position, button=1) if is_focusable:
                apply(move_to_column(cell_pressed(position, receiver).x))
                return FocusOn(focus.handle), ScrollIntoView(cursor_cell, block="nearest", inline="nearest")
            case _:
                return None

    cursor = text.following(value).cursor
    at_cursor_end = next_cluster(value, cursor)
    return TextInput(
        before_cursor=value[:cursor],
        at_cursor=value[cursor:at_cursor_end] if cursor < len(value) else " ",
        after_cursor=value[at_cursor_end:],
        cursor=cursor,
        latest_cursor=latest_cursor,
        cursor_cell=cursor_cell,
        focus=focus,
        on_input=on_input,
        on_press=on_press,
    )


def cell_pressed(position: Position, receiver: Receiver) -> Position:
    """
    Where `position` is in the content the receiving element draws, from the top-left corner of its content box:
    where it is in the content box, moved by how far the content is scrolled if the element is a scroll container.
    """
    return receiver.relative(position) + (receiver.scroll.offset if receiver.scroll is not None else ORIGIN)


def edited(latest: EditableText, edit: Edit, set_value: Editor[str]) -> EditableText:
    """
    The text after `edit`, for a hook's state updater given the `latest` text:
    it reads the latest value through `set_value`, writes the edited one, and takes the value the setter settled at,
    so a setter that validates or transforms the edit decides the value, and a second edit before the next render
    starts from this one's result, since a state setter applies an updater immediately.
    """
    before = latest.following(get_state(set_value))
    after = edit(before)
    return settled(before, after, set_value(lambda _: after.value))
