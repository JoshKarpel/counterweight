"""[`use_text_area`][counterweight.headless.use_text_area], which edits text that wraps onto rows and leaves drawing it to its caller."""

from __future__ import annotations

from dataclasses import dataclass

from counterweight.controls import FocusOn
from counterweight.controls import ScrollBy
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
from counterweight.handlers import PAGE_FRACTION
from counterweight.handlers import page_down
from counterweight.handlers import page_rows
from counterweight.handlers import page_up
from counterweight.headless._text_area_editing import drawn
from counterweight.headless._text_area_editing import key_edit
from counterweight.headless._text_area_editing import move_down
from counterweight.headless._text_area_editing import move_to_cell
from counterweight.headless._text_area_editing import move_up
from counterweight.headless._text_area_editing import paste_edit
from counterweight.headless._text_editing import Edit
from counterweight.headless._text_editing import EditableText
from counterweight.headless._text_input import cell_pressed
from counterweight.headless._text_input import edited
from counterweight.hooks import Editor
from counterweight.hooks import Focus
from counterweight.hooks import Getter
from counterweight.hooks import get_state
from counterweight.hooks import use_focus
from counterweight.hooks import use_state
from counterweight.keys import Key


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
    """
    How many of the value's code points come before the cursor, so `value[:cursor]` is the text before it,
    where this render placed it, for drawing.
    """

    latest_cursor: Getter[int]
    """
    Where the cursor is after every edit since this render, as the DOM's `selectionStart` is,
    for a handler that decides from it, since several key presses can arrive before the next render.
    A value the calling component changed other than by an edit puts it at the end, as a render would.
    """

    cursor_row: ElementHandle
    """
    The element handle for the calling component to give the element it draws the cursor's row in,
    which `on_input` scrolls into view as the cursor moves,
    so a text area in a [scroll container](../layout/scrolling.md) keeps the cursor in view.
    """

    focus: Focus
    """
    Whether the calling component is focused, and its focus handle,
    as [`use_focus`][counterweight.hooks.use_focus] returns them.
    """

    on_input: InputHandler
    """
    The handler that edits the value, for the calling component to put on the element it returns.
    It returns [`ScrollIntoView`][counterweight.controls.ScrollIntoView] for `cursor_row` for each event it edits with,
    after a [`ScrollBy`][counterweight.controls.ScrollBy] of a page for PageUp and PageDown
    when that element is a scroll container,
    and `None` for every event while that element isn't focused,
    and for the key presses it doesn't edit with, such as Tab, Escape, and Enter unless it inserts a line break,
    so they bubble to the element's ancestors.
    """

    on_press: InputHandler
    """
    The handler that moves the cursor to where a press lands, as a click in a browser's `<textarea>` does,
    for the calling component to put on the element it draws the rows in,
    from the top-left corner of that element's content box,
    scrolled by that element's scroll if it's a scroll container.
    For a press of the left button, it moves the cursor to the cluster drawn across the cell pressed,
    or to the end of its row past the row's text, or to the first row or the last from above or below them,
    and returns [`FocusOn`][counterweight.controls.FocusOn] for the component
    with [`ScrollIntoView`][counterweight.controls.ScrollIntoView] for `cursor_row`.
    It returns `None` for every other event, and for every event while the component isn't focusable.
    """


def use_text_area(
    value: str,
    set_value: Editor[str],
    width: int,
    enter_inserts_newline: bool = False,
    tab_size: int = 4,
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
            returning the value it settled at, as for [`use_text_input`][counterweight.headless.use_text_input].

        width: How many cells wide each row is, such as the content width
            [`use_rects`][counterweight.hooks.use_rects] reports for the element the text is drawn in.
            The element MUST get its width from its style or its parent rather than from its text,
            which is wrapped to fit it.

        enter_inserts_newline: Whether Enter inserts a line break, as in a text editor,
            rather than bubbling to the element's ancestors, as for a form that submits on Enter.
            Alt+Enter and Ctrl+J insert one either way.

        tab_size: How many columns apart the tab stops a paste expands each tab to are,
            as for [`highlight`][counterweight.highlighting.highlight],
            so pasted code keeps its indentation and alignment.

        auto_focus: Passed to [`use_focus`][counterweight.hooks.use_focus].

        handle: The focus handle passed to [`use_focus`][counterweight.hooks.use_focus].

        is_focusable: Passed to [`use_focus`][counterweight.hooks.use_focus].

        in_focus_order: Passed to [`use_focus`][counterweight.hooks.use_focus].

    Returns:
        The value wrapped into rows and split around the cursor, for the calling component to draw without wrapping it again,
        the handler that edits it, for the calling component to put on the element it returns,
        and the handler that moves the cursor to a press, for the element it draws the rows in.
        The cursor starts at the end of the value, and moves to the end when the value changes other than by an edit.
    """
    focus = use_focus(auto_focus=auto_focus, handle=handle, is_focusable=is_focusable, in_focus_order=in_focus_order)
    # The value the cursor was last placed in, so a value that differs from it was changed other than by an edit.
    text, set_text = use_state(lambda: EditableText(value=value, cursor=len(value), goal_column=None))
    cursor_row, _ = use_state(ElementHandle)

    def apply(edit: Edit) -> None:
        set_text(lambda latest: edited(latest, edit, set_value))

    def latest_cursor() -> int:
        return get_state(set_text).following(get_state(set_value)).cursor

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        if not receiver.is_focused:
            return None

        edit: Edit | None
        paging: ScrollBy | None = None
        match event:
            case KeyPressed(key=Key.PageUp):
                edit = move_up(width, page_rows_in(receiver))
                paging = page_up(receiver.subtree, receiver.scroll) if receiver.scroll is not None else None
            case KeyPressed(key=Key.PageDown):
                edit = move_down(width, page_rows_in(receiver))
                paging = page_down(receiver.subtree, receiver.scroll) if receiver.scroll is not None else None
            case KeyPressed(key=key):
                edit = key_edit(key, width, enter_inserts_newline)
            case Pasted(text=pasted):
                edit = paste_edit(pasted, tab_size)
            case _:
                return None

        if edit is None:
            return None

        apply(edit)
        cursor_in_view = ScrollIntoView(cursor_row, block="nearest")
        return cursor_in_view if paging is None else (paging, cursor_in_view)

    def on_press(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case MouseDown(absolute=position, button=1) if is_focusable:
                cell = cell_pressed(position, receiver)
                apply(move_to_cell(width, cell.y, cell.x))
                return FocusOn(focus.handle), ScrollIntoView(cursor_row, block="nearest")
            case _:
                return None

    cursor = text.following(value).cursor
    shown = drawn(value, cursor, width)
    return TextArea(
        before_cursor=shown.before_cursor,
        at_cursor=shown.at_cursor,
        after_cursor=shown.after_cursor,
        cursor=cursor,
        latest_cursor=latest_cursor,
        cursor_row=cursor_row,
        focus=focus,
        on_input=on_input,
        on_press=on_press,
    )


def page_rows_in(receiver: Receiver) -> int:
    """
    How many rows PageUp and PageDown move the cursor:
    a page of the receiving element's view, as [`scroll_on_keys`][counterweight.handlers.scroll_on_keys] pages it,
    or if it isn't a scroll container, a page of its content box, which shows every row.
    """
    if receiver.scroll is not None:
        return page_rows(receiver.scroll, PAGE_FRACTION)
    return max(1, int(receiver.rects.content.height * PAGE_FRACTION))
