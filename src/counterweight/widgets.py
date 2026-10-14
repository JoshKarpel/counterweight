"""
Styled components for the common cases, each built on a headless hook that leaves drawing to its caller,
so an app that wants another look starts from the hook rather than from these.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from counterweight.components import Component
from counterweight.components import component
from counterweight.elements import AnyElement
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.focus import ElementHandle
from counterweight.focus import FocusHandle
from counterweight.graphemes import graphemes
from counterweight.handlers import PAGE_FRACTION
from counterweight.handlers import first
from counterweight.handlers import focus_receiver_on_press
from counterweight.handlers import scroll_on_wheel
from counterweight.headless import ScrollAxis
from counterweight.headless import use_scroll_area
from counterweight.headless import use_text_area
from counterweight.headless import use_text_input
from counterweight.hooks import use_rects
from counterweight.styles import CellStyle
from counterweight.styles import Style
from counterweight.styles.utilities import border
from counterweight.styles.utilities import border_color
from counterweight.styles.utilities import border_lightrounded
from counterweight.styles.utilities import col
from counterweight.styles.utilities import default
from counterweight.styles.utilities import min_width
from counterweight.styles.utilities import overflow_x_scroll
from counterweight.styles.utilities import overflow_y_scroll
from counterweight.styles.utilities import pad_x
from counterweight.styles.utilities import row
from counterweight.styles.utilities import shrink
from counterweight.styles.utilities import stick_to_end_x
from counterweight.styles.utilities import stick_to_end_y
from counterweight.styles.utilities import text_bg
from counterweight.styles.utilities import text_color
from counterweight.styles.utilities import text_wrap_none


@dataclass(frozen=True, slots=True, kw_only=True)
class TextFieldStyles:
    """
    How [`text_input`][counterweight.widgets.text_input] and [`text_area`][counterweight.widgets.text_area]
    draw their box, their cursor, and their placeholder.

    A widget's box is styled by `box`, then the `style` passed to the widget,
    then `focused_box` while it's focused, or `unfocusable_box` while it isn't focusable,
    as a CSS rule for `input:focus` or `input:disabled` overrides one for `input`,
    so a `style` with another border color still shows which widget is focused.
    Pass the fields you want to change: `TextFieldStyles(focused_box=border_color("amber", 400))`.
    """

    box: Style = border | border_lightrounded | border_color("slate", 600) | pad_x(1)
    """The box around the text."""
    focused_box: Style = border_color("indigo", 400)
    """Merged over `box` and the widget's `style` while the widget is focused."""
    unfocusable_box: Style = text_color("slate", 600)
    """Merged over `box` and the widget's `style` while the widget isn't focusable."""
    cursor: CellStyle = (text_color("slate", 900) | text_bg("slate", 100)).text_style
    """Merged over the text for the cell the cursor is on, while the widget is focused."""
    placeholder: CellStyle = text_color("slate", 500).text_style
    """Merged over the text for the placeholder, which the widget shows in place of an empty value."""

    def box_style(self, style: Style, is_focused: bool, is_focusable: bool) -> Style:
        """The style of a widget's box, with `style` merged over `box`, under the styles for its state."""
        return (
            self.box
            | style
            | (self.focused_box if is_focused else default)
            | (default if is_focusable else self.unfocusable_box)
        )


@component
def text_input(
    value: str,
    set_value: Callable[[Callable[[str], str]], None],
    placeholder: str = "",
    style: Style = default,
    styles: TextFieldStyles = TextFieldStyles(),
    auto_focus: bool = False,
    handle: FocusHandle | None = None,
    is_focusable: bool = True,
    in_focus_order: bool = True,
) -> Div:
    """
    A bordered box for editing one line of text, built on [`use_text_input`][counterweight.headless.use_text_input],
    which takes `value`, `set_value` and the focus parameters, `handle` being a focus handle.
    It draws the cursor as a highlighted cell while it's focused, and a press on it focuses it,
    and on its text moves the cursor there.
    A value wider than the box scrolls sideways inside it, keeping the cursor in view,
    as a browser's `<input>` does, and starts scrolled to its end, where the cursor starts.

    Parameters:
        placeholder: Shown in place of an empty value.

        style: Merged over the box's style from `styles`, as for a size (`width(20)`).

        styles: How the box, the cursor and the placeholder are drawn.
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
    # The box's minimum width would otherwise be its value's, so a long value would push its siblings aside
    # rather than scroll.
    box = min_width(0) | styles.box_style(style, is_focused, is_focusable)
    text_style = text_wrap_none | Style(text_style=box.text_style)
    cursor = styles.cursor if is_focused else CellStyle()
    before_cursor, at_cursor, after_cursor = (
        placeholder_chunks(placeholder, cursor, styles.placeholder)
        if placeholder and not value
        else cursor_chunks(field.before_cursor, field.at_cursor, field.after_cursor, cursor)
    )

    return Div(
        style=box,
        on_input=first(field.on_input, focus_receiver_on_press),
        children=(
            # The value scrolls inside the border and padding, and the cell the cursor is on is an element of its own,
            # to carry the handle that scrolls it into view.
            Div(
                style=row | overflow_x_scroll | stick_to_end_x,
                on_input=first(field.on_press, scroll_on_wheel()),
                children=(
                    Text(content=(before_cursor,), style=text_style),
                    Text(content=(at_cursor,), style=text_style, handle=field.cursor_cell),
                    # A cell past the end of the value, which the cursor takes there, so moving the cursor off the end
                    # keeps the value as wide and leaves it where it is under a press.
                    Text(
                        content=(after_cursor, Chunk(content=" ")) if field.cursor < len(value) else (after_cursor,),
                        style=text_style,
                    ),
                ),
            ),
        ),
    )


@component
def text_area(
    value: str,
    set_value: Callable[[Callable[[str], str]], None],
    placeholder: str = "",
    style: Style = default,
    styles: TextFieldStyles = TextFieldStyles(),
    enter_inserts_newline: bool = False,
    tab_size: int = 4,
    auto_focus: bool = False,
    handle: FocusHandle | None = None,
    is_focusable: bool = True,
    in_focus_order: bool = True,
) -> Div:
    """
    A bordered box for editing text that wraps onto rows, built on [`use_text_area`][counterweight.headless.use_text_area],
    which takes `value`, `set_value`, `enter_inserts_newline`, `tab_size` and the focus parameters,
    `handle` being a focus handle.
    It draws the cursor as a highlighted cell while it's focused, and a press on it focuses it,
    and on its text moves the cursor there.
    It's as wide as its parent or its `style` makes it, and grows to fit its rows,
    up to a `max_height`, past which it scrolls, keeping the cursor in view, and the wheel scrolls it.
    It starts scrolled to its end, where the cursor starts.

    Parameters:
        placeholder: Shown in place of an empty value.

        style: Merged over the box's style from `styles`, as for a size (`width(40)`, `max_height(8)`, `fill(1)`).
            The box scrolls whatever overflow `style` sets.

        styles: How the box, the cursor and the placeholder are drawn.
    """
    rects = use_rects()
    field = use_text_area(
        value,
        set_value,
        width=rects.content.width,
        enter_inserts_newline=enter_inserts_newline,
        tab_size=tab_size,
        auto_focus=auto_focus,
        handle=handle,
        is_focusable=is_focusable,
        in_focus_order=in_focus_order,
    )
    is_focused = field.focus.is_focused
    # A scroll container's automatic minimum height is 0, so without shrink(0) a column that overflows would
    # shrink the box rather than let it grow to fit its rows.
    # Its overflow merges last, since a `style` such as `fill(1)` sets overflow too, and the box must scroll.
    box = col | stick_to_end_y | shrink(0) | styles.box_style(style, is_focused, is_focusable) | overflow_y_scroll
    row_style = text_wrap_none | Style(text_style=box.text_style)
    cursor = styles.cursor if is_focused else CellStyle()

    rows: tuple[Text, ...]
    if placeholder and not value:
        rows = (
            Text(
                content=placeholder_chunks(placeholder, cursor, styles.placeholder),
                style=row_style,
                handle=field.cursor_row,
            ),
        )
    else:
        # The cursor's row is drawn on its own, to carry the handle that scrolls it into view.
        *above, before_cursor = field.before_cursor.split("\n")
        after_cursor, *below = field.after_cursor.split("\n")
        rows = (
            *([Text(content="\n".join(above), style=row_style)] if above else []),
            Text(
                content=cursor_chunks(before_cursor, field.at_cursor, after_cursor, cursor),
                style=row_style,
                handle=field.cursor_row,
            ),
            *([Text(content="\n".join(below), style=row_style)] if below else []),
        )

    return Div(
        style=box,
        on_input=first(field.on_input, field.on_press, focus_receiver_on_press, scroll_on_wheel()),
        children=rows,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class ScrollAreaStyles:
    """
    How [`scroll_area`][counterweight.widgets.scroll_area] draws its box.

    The box is styled by `box`, then the `style` passed to the widget, then `focused_box` while it's focused,
    as [`TextFieldStyles`][counterweight.widgets.TextFieldStyles] styles a field's box.
    A browser draws a focus ring around a focused scroll container as an outline, which takes no space;
    a terminal has nothing drawn outside a box, so the box has a border whose color shows focus instead,
    which keeps its content where it is as focus comes and goes.
    For a box without a border, pass `box=default` with a `focused_box` that takes no space,
    such as a background color.
    """

    box: Style = border | border_lightrounded | border_color("slate", 600) | pad_x(1)
    """The box around the content."""
    focused_box: Style = border_color("indigo", 400)
    """Merged over `box` and the widget's `style` while the widget is focused."""

    def box_style(self, style: Style, is_focused: bool) -> Style:
        """The style of the widget's box, with `style` merged over `box`, under `focused_box` while it's focused."""
        return self.box | style | (self.focused_box if is_focused else default)


@component
def scroll_area(
    children: tuple[Component | AnyElement, ...],
    axis: ScrollAxis = "y",
    stick_to_end: bool = False,
    style: Style = default,
    styles: ScrollAreaStyles = ScrollAreaStyles(),
    viewport: ElementHandle | None = None,
    wheel_lines: int = 3,
    page: float = PAGE_FRACTION,
    auto_focus: bool = False,
    handle: FocusHandle | None = None,
    is_focusable: bool = True,
    in_focus_order: bool = True,
) -> Div:
    """
    A bordered box that scrolls its `children`, built on [`use_scroll_area`][counterweight.headless.use_scroll_area],
    which takes `axis`, `stick_to_end`, `viewport`, `wheel_lines`, `page` and the focus parameters,
    `handle` being a focus handle.
    The keys scroll it while it, or something inside it, is focused, a press on it focuses it,
    and the wheel scrolls it, and its border shows whether it's focused.
    Its children are laid out in a column, unless `style` says otherwise.

    Parameters:
        children: What scrolls.

        style: Merged over the box's style from `styles`, as for a size (`fill(1)`, `height(10)`)
            or a layout (`gap(1)`, `row`).
            The box scrolls whatever overflow `style` sets.

        styles: How the box is drawn.
    """
    area = use_scroll_area(
        axis,
        stick_to_end,
        viewport=viewport,
        wheel_lines=wheel_lines,
        page=page,
        auto_focus=auto_focus,
        handle=handle,
        is_focusable=is_focusable,
        in_focus_order=in_focus_order,
    )
    # The area's style merges last, since a `style` such as `fill(1)` sets overflow too, and the box must scroll.
    box = col | styles.box_style(style, area.focus.is_focused) | area.style
    return Div(style=box, handle=area.viewport, on_input=area.on_input, children=children)


def cursor_chunks(
    before_cursor: str, at_cursor: str, after_cursor: str, cursor: CellStyle
) -> tuple[Chunk, Chunk, Chunk]:
    """Text split around the cursor, with `cursor` on the cursor's cell."""
    return (
        Chunk(content=before_cursor),
        Chunk(content=at_cursor, style=cursor),
        Chunk(content=after_cursor),
    )


def placeholder_chunks(placeholder: str, cursor: CellStyle, style: CellStyle) -> tuple[Chunk, Chunk, Chunk]:
    """
    The placeholder in `style`, split as `cursor_chunks` splits text,
    with the cursor on its first cluster, where typing will start.
    """
    head, *tail = graphemes(placeholder)
    return (
        Chunk(content=""),
        Chunk(content=head, style=style | cursor),
        Chunk(content="".join(tail), style=style),
    )
