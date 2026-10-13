"""[`use_text_area`][counterweight.headless.use_text_area], which edits text that wraps onto rows and leaves drawing it to its caller."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from counterweight.controls import ScrollIntoView
from counterweight.events import InputEvent, InputHandler, InputResponse, KeyPressed, Pasted, Receiver
from counterweight.focus import ElementHandle, FocusHandle
from counterweight.headless.text_area_editing import AreaEdit, EditableArea, drawn, key_edit, paste_edit, settled
from counterweight.hooks import Focus, use_focus, use_state


@dataclass(frozen=True, slots=True)
class TextArea:
    """What [`use_text_area`][counterweight.headless.use_text_area] returns to the calling component."""

    before_cursor: str
    """The value's rows before the cursor, each followed by a line break, then its row's text before the cursor."""

    at_cursor: str
    """
    The grapheme cluster at the cursor,
    or a space when the cursor is at the end of a line or of the value, so there's always a cell to draw the cursor in.
    """

    after_cursor: str
    """The text of the cursor's row after `at_cursor`, then each row after it, following a line break."""

    cursor: int
    """How many of the value's code points come before the cursor, so `value[:cursor]` is the text before it."""

    cursor_row: ElementHandle
    """
    The handle for the calling component to give the element it draws the cursor's row in,
    which `on_input` scrolls into view as the cursor moves,
    so a text area in a [scroll container](../layout/scrolling.md) keeps the cursor in view.
    """

    focus: Focus
    """Whether the calling component is focused, and its handle, as [`use_focus`][counterweight.hooks.use_focus] returns them."""

    on_input: InputHandler
    """
    The handler that edits the value, for the calling component to put on the element it returns.
    It returns [`ScrollIntoView`][counterweight.controls.ScrollIntoView] for `cursor_row` for each event it edits with,
    and `None` for every event while that element isn't focused,
    and for the key presses it doesn't edit with, such as Tab, Escape, and Enter unless it inserts a line break,
    so they bubble to the element's ancestors.
    """


def use_text_area(
    value: str,
    set_value: Callable[[Callable[[str], str]], None],
    width: int,
    enter_inserts_newline: bool = False,
    auto_focus: bool = False,
    handle: FocusHandle | None = None,
    is_focusable: bool = True,
    in_focus_order: bool = True,
) -> TextArea:
    """
    Edits text that wraps onto rows, leaving how it's drawn to the calling component.
    The calling component owns the value, and the hook owns the cursor, makes the component focusable,
    and wraps the value, so the cursor can move between the rows it's drawn on.

    Parameters:
        value: The text being edited.

        set_value: Called with a function from the latest value to the edited one for each edit,
            as for [`use_text_input`][counterweight.headless.use_text_input].

        width: How many cells wide each row is, such as the content width
            [`use_rects`][counterweight.hooks.use_rects] reports for the element the text is drawn in.
            The element MUST get its width from its style or its parent rather than from its text,
            which is wrapped to fit it.

        enter_inserts_newline: Whether Enter inserts a line break, as in a text editor,
            rather than bubbling to the element's ancestors, as for a form that submits on Enter.
            Ctrl+J inserts one either way.

        auto_focus: Passed to [`use_focus`][counterweight.hooks.use_focus].

        handle: Passed to [`use_focus`][counterweight.hooks.use_focus].

        is_focusable: Passed to [`use_focus`][counterweight.hooks.use_focus].

        in_focus_order: Passed to [`use_focus`][counterweight.hooks.use_focus].

    Returns:
        The value wrapped into rows and split around the cursor, for the calling component to draw without wrapping it again,
        and the handler that edits it, for the calling component to put on the element it returns.
        The cursor starts at the end of the value, and moves to the end when the value changes other than by an edit.
    """
    focus = use_focus(auto_focus=auto_focus, handle=handle, is_focusable=is_focusable, in_focus_order=in_focus_order)
    # The value the cursor was last placed in, so a value that differs from it was changed other than by an edit.
    area, set_area = use_state(lambda: EditableArea(value=value, cursor=len(value), goal_column=None))
    cursor_row, _ = use_state(ElementHandle)

    def apply(edit: AreaEdit) -> None:
        # As in use_text_input: read the latest value, write the edited one, and read back what the setter kept.
        def edit_area(latest_area: EditableArea) -> EditableArea:
            values = [value]

            def read_value(latest_value: str) -> str:
                values.append(latest_value)
                return latest_value

            set_value(read_value)
            before = latest_area.following(values[-1])
            edited = edit(before)
            set_value(lambda _: edited.value)
            set_value(read_value)
            return settled(before, edited, values[-1])

        set_area(edit_area)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        if not receiver.is_focused:
            return None

        match event:
            case KeyPressed(key=key):
                edit = key_edit(key, width, enter_inserts_newline)
            case Pasted(text=text):
                edit = paste_edit(text)
            case _:
                return None

        if edit is None:
            return None

        apply(edit)
        return ScrollIntoView(cursor_row, block="nearest")

    cursor = area.following(value).cursor
    shown = drawn(value, cursor, width)
    return TextArea(
        before_cursor=shown.before_cursor,
        at_cursor=shown.at_cursor,
        after_cursor=shown.after_cursor,
        cursor=cursor,
        cursor_row=cursor_row,
        focus=focus,
        on_input=on_input,
    )
