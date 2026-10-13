"""[`use_text_input`][counterweight.headless.use_text_input], which edits one line of text and leaves drawing it to its caller."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from counterweight.events import InputEvent, InputHandler, InputResponse, KeyPressed, Pasted, Receiver
from counterweight.focus import FocusHandle
from counterweight.graphemes import graphemes
from counterweight.headless.text_editing import Edit, EditableText, key_edit, paste_edit, settled
from counterweight.hooks import Focus, use_focus, use_state


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
    """How many of the value's grapheme clusters come before the cursor."""

    focus: Focus
    """Whether the calling component is focused, and its handle, as [`use_focus`][counterweight.hooks.use_focus] returns them."""

    on_input: InputHandler
    """
    The handler that edits the value, for the calling component to put on the element it returns.
    It returns `None` for every event while that element isn't focused,
    and for the key presses it doesn't edit with, such as Enter, Tab, Up and Down,
    so they bubble to the element's ancestors.
    """


def use_text_input(
    value: str,
    set_value: Callable[[Callable[[str], str]], None],
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
            which it MUST call before returning, as a [`use_state`][counterweight.hooks.use_state] setter does.
            Several key presses can arrive between renders, as when typing fast,
            so an edit applies to the latest value rather than to `value`, which is the one this render saw.
            Validate or transform an edit by wrapping the setter:
            `lambda edit: set_value(lambda v: new if (new := edit(v)).isdigit() or not new else v)`
            keeps only digits, and lets the value be emptied.
            Each edit also calls it before and after with a function that returns the value it's given,
            to read the latest value, and then the one the edit settled at:
            the cursor moves with an edit unless the setter left the value as it was before it.

        auto_focus: Passed to [`use_focus`][counterweight.hooks.use_focus].

        handle: Passed to [`use_focus`][counterweight.hooks.use_focus].

        is_focusable: Passed to [`use_focus`][counterweight.hooks.use_focus].

        in_focus_order: Passed to [`use_focus`][counterweight.hooks.use_focus].

    Returns:
        The value split around the cursor, for the calling component to draw,
        and the handler that edits it, for the calling component to put on the element it returns.
        The cursor starts at the end of the value, and moves to the end when the value changes other than by an edit.
    """
    focus = use_focus(auto_focus=auto_focus, handle=handle, is_focusable=is_focusable, in_focus_order=in_focus_order)
    # The value the cursor was last placed in, so a value that differs from it was changed other than by an edit.
    text, set_text = use_state(lambda: EditableText(value=value, cursor=len(graphemes(value))))

    def apply(edit: Edit) -> None:
        # Both setters apply an updater immediately, so this reads the latest text, then the latest value,
        # and a second edit before the next render starts from the first one's result.
        def edit_text(latest_text: EditableText) -> EditableText:
            # This render's value stands until the setter reports a later one, which one that ignores calls never does.
            values = [value]

            def read_value(latest_value: str) -> str:
                values.append(latest_value)
                return latest_value

            set_value(read_value)
            before = latest_text.following(values[-1])
            edited = edit(before)
            set_value(lambda _: edited.value)
            # A setter that validates or transforms the edit decides the value, so read back what it kept.
            set_value(read_value)
            return settled(before, edited, values[-1])

        set_text(edit_text)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        if not receiver.is_focused:
            return None

        match event:
            case KeyPressed(key=key):
                edit = key_edit(key)
            case Pasted(text=text):
                edit = paste_edit(text)
            case _:
                return None

        if edit is None:
            return None

        apply(edit)
        return ()

    clusters = graphemes(value)
    cursor = text.cursor if value == text.value else len(clusters)
    return TextInput(
        before_cursor="".join(clusters[:cursor]),
        at_cursor=clusters[cursor] if cursor < len(clusters) else " ",
        after_cursor="".join(clusters[cursor + 1 :]),
        cursor=cursor,
        focus=focus,
        on_input=on_input,
    )
