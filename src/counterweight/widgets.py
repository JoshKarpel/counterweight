"""
Styled components for the common cases, each built on a headless hook that leaves drawing to its caller,
so an app that wants another look starts from the hook rather than from these.
"""

from __future__ import annotations

from collections.abc import Callable

from counterweight.components import component
from counterweight.elements import Chunk, Div, Text
from counterweight.focus import FocusHandle
from counterweight.graphemes import graphemes
from counterweight.handlers import first, focus_receiver_on_press, scroll_on_wheel
from counterweight.headless import use_text_area, use_text_input
from counterweight.hooks import use_rects
from counterweight.styles import CellStyle, Style
from counterweight.styles.utilities import (
    border,
    border_color,
    border_lightrounded,
    col,
    default,
    overflow_y_scroll,
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
        content=placeholder_chunks(placeholder, is_focused)
        if placeholder and not value
        else cursor_chunks(field.before_cursor, field.at_cursor, field.after_cursor, is_focused),
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
) -> Div:
    """
    A bordered box for editing text that wraps onto rows, built on [`use_text_area`][counterweight.headless.use_text_area],
    which takes `value`, `set_value`, `enter_inserts_newline` and the focus parameters.
    It draws the cursor as a highlighted cell while it's focused, and a press on it focuses it.
    It's as wide as its parent or its `style` makes it, and grows to fit its rows,
    up to a `max_height`, past which it scrolls, keeping the cursor in view, and the wheel scrolls it.

    Parameters:
        placeholder: Shown in place of an empty value.

        style: Merged over the box's own style, as for a size (`width(40)`, `max_height(8)`) or another border color.
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
    box = (
        col
        | overflow_y_scroll
        | border
        | border_lightrounded
        | pad_x(1)
        | (border_color("indigo", 400) if is_focused else border_color("slate", 600))
        | (default if is_focusable else text_color("slate", 600))
        | style
    )
    row_style = text_wrap_none | Style(text_style=box.text_style)

    rows: tuple[Text, ...]
    if placeholder and not value:
        rows = (Text(content=placeholder_chunks(placeholder, is_focused), style=row_style, handle=field.cursor_row),)
    else:
        # The cursor's row is drawn on its own, to carry the handle that scrolls it into view.
        *above, before_cursor = field.before_cursor.split("\n")
        after_cursor, *below = field.after_cursor.split("\n")
        rows = (
            *([Text(content="\n".join(above), style=row_style)] if above else []),
            Text(
                content=cursor_chunks(before_cursor, field.at_cursor, after_cursor, is_focused),
                style=row_style,
                handle=field.cursor_row,
            ),
            *([Text(content="\n".join(below), style=row_style)] if below else []),
        )

    return Div(
        style=box,
        on_input=first(field.on_input, focus_receiver_on_press, scroll_on_wheel()),
        children=rows,
    )


def cursor_chunks(before_cursor: str, at_cursor: str, after_cursor: str, is_focused: bool) -> tuple[Chunk, ...]:
    """Text split around the cursor, with the cursor highlighted while it's focused."""
    return (
        Chunk(content=before_cursor),
        Chunk(content=at_cursor, style=CURSOR if is_focused else CellStyle()),
        Chunk(content=after_cursor),
    )


def placeholder_chunks(placeholder: str, is_focused: bool) -> tuple[Chunk, ...]:
    """The placeholder, with the cursor on its first cluster while it's focused, where typing will start."""
    head, *tail = graphemes(placeholder)
    return (
        Chunk(content=head, style=CURSOR if is_focused else PLACEHOLDER),
        Chunk(content="".join(tail), style=PLACEHOLDER),
    )
