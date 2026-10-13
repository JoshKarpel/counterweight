"""
Styled components for the common cases, each built on a headless hook that leaves drawing to its caller,
so an app that wants another look starts from the hook rather than from these.
"""

from __future__ import annotations

from collections.abc import Callable

from counterweight.components import component
from counterweight.elements import Chunk, Text
from counterweight.focus import FocusHandle
from counterweight.graphemes import graphemes
from counterweight.handlers import first, focus_receiver_on_press
from counterweight.headless import TextArea, TextInput, use_text_area, use_text_input
from counterweight.hooks import use_rects
from counterweight.styles import CellStyle, Style
from counterweight.styles.utilities import (
    border,
    border_color,
    border_lightrounded,
    default,
    pad_x,
    text_bg,
    text_color,
    text_wrap_none,
)

CURSOR = (text_color("slate", 900) | text_bg("slate", 100)).text_style
PLACEHOLDER = text_color("slate", 500).text_style


@component
def text_input(
    value: str,
    set_value: Callable[[Callable[[str], str]], None],
    placeholder: str = "",
    style: Style = default,
    auto_focus: bool = False,
    handle: FocusHandle | None = None,
    is_focusable: bool = True,
    in_focus_order: bool = True,
) -> Text:
    """
    A bordered box for editing one line of text, built on [`use_text_input`][counterweight.headless.use_text_input],
    which takes `value`, `set_value` and the focus parameters.
    It draws the cursor as a highlighted cell while it's focused, and a press on it focuses it.

    Parameters:
        placeholder: Shown in place of an empty value.

        style: Merged over the box's own style, as for a size (`width(20)`) or another border color.
    """
    field = use_text_input(
        value,
        set_value,
        auto_focus=auto_focus,
        handle=handle,
        is_focusable=is_focusable,
        in_focus_order=in_focus_order,
    )
    is_focused = field.focus.is_focused

    return Text(
        content=cursor_content(field, value, placeholder),
        style=border
        | border_lightrounded
        | pad_x(1)
        | (border_color("indigo", 400) if is_focused else border_color("slate", 600))
        | (default if is_focusable else text_color("slate", 600))
        | style,
        on_input=first(field.on_input, focus_receiver_on_press),
    )


@component
def text_area(
    value: str,
    set_value: Callable[[Callable[[str], str]], None],
    placeholder: str = "",
    style: Style = default,
    enter_inserts_newline: bool = False,
    auto_focus: bool = False,
    handle: FocusHandle | None = None,
    is_focusable: bool = True,
    in_focus_order: bool = True,
) -> Text:
    """
    A bordered box for editing text that wraps onto rows, built on [`use_text_area`][counterweight.headless.use_text_area],
    which takes `value`, `set_value`, `enter_inserts_newline` and the focus parameters.
    It draws the cursor as a highlighted cell while it's focused, and a press on it focuses it.
    It's as wide as its parent or its `style` makes it, and grows to fit its rows.

    Parameters:
        placeholder: Shown in place of an empty value.

        style: Merged over the box's own style, as for a size (`width(40)`) or another border color.
    """
    rects = use_rects()
    field = use_text_area(
        value,
        set_value,
        width=rects.content.width,
        enter_inserts_newline=enter_inserts_newline,
        auto_focus=auto_focus,
        handle=handle,
        is_focusable=is_focusable,
        in_focus_order=in_focus_order,
    )
    is_focused = field.focus.is_focused
    return Text(
        content=cursor_content(field, value, placeholder),
        style=border
        | border_lightrounded
        | pad_x(1)
        | text_wrap_none
        | (border_color("indigo", 400) if is_focused else border_color("slate", 600))
        | (default if is_focusable else text_color("slate", 600))
        | style,
        on_input=first(field.on_input, focus_receiver_on_press),
    )


def cursor_content(field: TextInput | TextArea, value: str, placeholder: str) -> list[Chunk]:
    """
    The field's text split around the cursor, with the cursor highlighted while it's focused,
    or the placeholder if the value is empty, with the cursor on its first cluster, where typing will start.
    """
    is_focused = field.focus.is_focused
    if value or not placeholder:
        return [
            Chunk(content=field.before_cursor),
            Chunk(content=field.at_cursor, style=CURSOR if is_focused else CellStyle()),
            Chunk(content=field.after_cursor),
        ]
    head, *tail = graphemes(placeholder)
    return [
        Chunk(content=head, style=CURSOR if is_focused else PLACEHOLDER),
        Chunk(content="".join(tail), style=PLACEHOLDER),
    ]
