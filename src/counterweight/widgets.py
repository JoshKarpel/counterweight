"""
Styled components for the common cases, each built on a headless hook that leaves drawing to its caller,
so an app that wants another look starts from the hook rather than from these.
"""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Collection
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import replace
from datetime import timedelta
from functools import partial
from pathlib import Path
from typing import Literal
from typing import assert_never

import waxy

from counterweight._graphemes import graphemes
from counterweight._layout import layout_style
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import ScrollIntoView
from counterweight.elements import AnyElement
from counterweight.elements import Canvas
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputHandler
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import MouseMoved
from counterweight.events import Receiver
from counterweight.events import response_controls
from counterweight.focus import ElementHandle
from counterweight.focus import FocusHandle
from counterweight.handlers import PAGE_FRACTION
from counterweight.handlers import first
from counterweight.handlers import focus_receiver_on_press
from counterweight.handlers import on_click
from counterweight.handlers import scroll_on_wheel
from counterweight.headless import Highlight
from counterweight.headless import ScrollAxis
from counterweight.headless import TextInput
from counterweight.headless import subsequence_matches
from counterweight.headless import use_scroll_area
from counterweight.headless import use_terminal
from counterweight.headless import use_text_area
from counterweight.headless import use_text_input
from counterweight.hooks import Editor
from counterweight.hooks import get_state
from counterweight.hooks import use_effect
from counterweight.hooks import use_rects
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.pseudoterminal import HANGUP_GRACE
from counterweight.styles import CellStyle
from counterweight.styles import Style
from counterweight.styles.utilities import border
from counterweight.styles.utilities import border_color
from counterweight.styles.utilities import border_lightrounded
from counterweight.styles.utilities import clip_to_screen
from counterweight.styles.utilities import col
from counterweight.styles.utilities import content_color
from counterweight.styles.utilities import default
from counterweight.styles.utilities import max_height
from counterweight.styles.utilities import min_width
from counterweight.styles.utilities import overflow_x_scroll
from counterweight.styles.utilities import overflow_y_scroll
from counterweight.styles.utilities import pad_x
from counterweight.styles.utilities import padding_color
from counterweight.styles.utilities import position_absolute
from counterweight.styles.utilities import row
from counterweight.styles.utilities import shrink
from counterweight.styles.utilities import stick_to_end_x
from counterweight.styles.utilities import stick_to_end_y
from counterweight.styles.utilities import text_bg
from counterweight.styles.utilities import text_color
from counterweight.styles.utilities import text_wrap_none
from counterweight.styles.utilities import z


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
    set_value: Editor[str],
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
    box = text_field_box(styles, style, field.focus.is_focused, is_focusable)
    return Div(
        style=box,
        on_input=first(field.on_input, focus_receiver_on_press),
        children=(text_field_row(field, value, placeholder, styles, box),),
    )


def text_field_box(styles: TextFieldStyles, style: Style, is_focused: bool, is_focusable: bool) -> Style:
    """The style of the box a one-line text field draws its value in."""
    # The box's minimum width would otherwise be its value's, so a long value would push its siblings aside
    # rather than scroll.
    return min_width(0) | styles.box_style(style, is_focused, is_focusable)


def text_field_row(field: TextInput, value: str, placeholder: str, styles: TextFieldStyles, box: Style) -> Div:
    """
    The row a one-line text field draws `value` in, inside its `box`, with the cursor while it's focused,
    or `placeholder` in place of an empty value.
    """
    text_style = text_wrap_none | Style(text_style=box.text_style)
    cursor = styles.cursor if field.focus.is_focused else CellStyle()
    before_cursor, at_cursor, after_cursor = (
        placeholder_chunks(placeholder, cursor, styles.placeholder)
        if placeholder and not value
        else cursor_chunks(field.before_cursor, field.at_cursor, field.after_cursor, cursor)
    )
    # The value scrolls inside the border and padding, and the cell the cursor is on is an element of its own,
    # to carry the handle that scrolls it into view.
    return Div(
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
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class ComboboxStyles:
    """
    How [`combobox`][counterweight.widgets.combobox] draws its field and its list.
    Pass the fields you want to change: `ComboboxStyles(highlighted_option=text_bg("teal", 800))`.
    """

    field: TextFieldStyles = TextFieldStyles()
    """How the field's box, its cursor and its placeholder are drawn, as for [`text_input`][counterweight.widgets.text_input]."""
    list_box: Style = (
        border
        | border_lightrounded
        | border_color("slate", 600)
        | content_color("slate", 900)
        | padding_color("slate", 900)
    )
    """The box around the list, which draws over the content beside the field, so its colors fill it."""
    option: Style = pad_x(1) | text_bg("slate", 900)
    """Each option's row."""
    highlighted_option: Style = text_bg("indigo", 800)
    """Merged over `option` for the highlighted option's row."""
    no_matches: Style = text_color("slate", 500)
    """Merged over `option` for the row that says nothing matches the text."""


@dataclass(frozen=True, slots=True)
class Suggesting:
    """Whether a combobox's list is open, and which of its options is highlighted, if any."""

    is_open: bool
    highlight: Highlight | None = Highlight()


@component
def combobox(
    value: str,
    set_value: Editor[str],
    options: Sequence[str],
    placeholder: str = "",
    opens: Literal["auto", "below", "above"] = "auto",
    opens_on: Literal["input", "focus"] = "input",
    ends: Literal["wrap", "stop", "release"] = "stop",
    shown_rows: int = 5,
    style: Style = default,
    styles: ComboboxStyles = ComboboxStyles(),
    auto_focus: bool = False,
    handle: FocusHandle | None = None,
    is_focusable: bool = True,
    in_focus_order: bool = True,
) -> Div:
    """
    A [`text_input`][counterweight.widgets.text_input] whose text suggests options in a list
    over the content below it, or above it, as the WAI-ARIA combobox pattern does.
    The list holds the options [`subsequence_matches`][counterweight.headless.subsequence_matches] keeps for the text,
    every option for an empty text, at most `shown_rows` of them in view, scrolling the rest,
    and is clipped only by the screen.
    It takes `value`, `set_value`, `placeholder` and the focus parameters as `text_input` does,
    and keeps which option is highlighted and whether the list is open itself.
    Choosing an option sets the text to it and closes the list.

    | Key | Open, with an option highlighted | Open, nothing highlighted | Closed |
    |---|---|---|---|
    | Down, Up | Highlight the next or previous option, at the ends as `ends` says | Highlight the first or the last | Open, highlighting the first or the last |
    | Enter, Ctrl+J, Tab | Choose it | Bubble | Bubble |
    | Escape | Close | Close | Bubble |
    | Anything else | The text field's | The text field's | The text field's |

    Tab chooses, as in editors' completion lists, since a field that completes as you type has nothing better for it
    to do while its list is open.
    An open list that nothing matches says so, and keeps Down, Up, Enter, Ctrl+J and Tab, doing nothing with them,
    so a key meant for the list never reaches a parent that has a use of its own for it.
    Ctrl+J chooses as Enter does, since a terminal still in cooked mode turns an Enter typed ahead into a line feed.
    Each key decides from the text and the highlight as every key before it left them, even before a render.
    Hovering a row highlights it, and clicking it chooses it, keeping focus in the field.
    For other keys, build a picker of your own from [`Highlight`][counterweight.headless.Highlight] and the matchers.

    Parameters:
        options: What the text suggests, in the order the list shows them, but for the one the text names exactly,
            which comes first.

        opens: Where the list opens: `"below"` or `"above"` the field,
            or `"auto"`, below while it fits between the field and the bottom of the screen
            ([`Rects.screen`][counterweight.geometry.Rects.screen]), and otherwise on the side with more room,
            which it decides from the last layout before the frame is painted,
            as the web's `position-try-fallbacks: flip-block` does in layout.

        opens_on: When the list opens, as React Aria's `menuTrigger` says:
            `"input"` on an edit, and `"focus"` whenever the field is focused,
            until Escape or choosing closes it, opening again when the field is focused again,
            with nothing highlighted until Down, Up or an edit, so Tab and Enter move on as they would without it.
            In either, Down or Up opens it.

        ends: What Down on the last option and Up on the first do, as for
            [`Highlight.moved`][counterweight.headless.Highlight.moved]:
            `"stop"` stays, as the combobox pattern and fzf do, `"wrap"` carries on from the other end,
            and `"release"` highlights nothing, so Enter bubbles, until Down or Up highlights an end again.

        shown_rows: How many options the list shows before it scrolls.

        style: Merged over the field's box's style from `styles`, as for a size (`width(24)`).

        styles: How the field and the list are drawn.
    """
    closed = Suggesting(is_open=opens_on == "focus", highlight=None)
    suggesting, set_suggesting = use_state(closed)
    highlighted_row, _ = use_state(ElementHandle)
    rects = use_rects()

    def edit(edit_text: Callable[[str], str]) -> str:
        before = get_state(set_value)
        if (after := set_value(edit_text)) != before:
            set_suggesting(Suggesting(is_open=True))
        return after

    field = use_text_input(
        value, edit, auto_focus=auto_focus, handle=handle, is_focusable=is_focusable, in_focus_order=in_focus_order
    )
    is_focused = field.focus.is_focused

    async def close_on_blur() -> None:
        if not is_focused:
            set_suggesting(closed)

    use_effect(close_on_blur, deps=(is_focused, closed))

    def choose(option: str) -> InputResponse:
        set_value(lambda _: option)
        set_suggesting(Suggesting(is_open=False))
        return ()

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        # Only the focused field receives key presses, so only they need the latest state.
        if not isinstance(event, KeyPressed):
            return field.on_input(event, receiver)
        now = get_state(set_suggesting)
        highlighted_in_view = ScrollIntoView(highlighted_row, block="nearest")
        match event:
            case KeyPressed(key=Key.Down | Key.Up as key):
                by = 1 if key == Key.Down else -1
                now_shown = subsequence_matches(get_state(set_value), options)
                if now.is_open and now.highlight is not None:
                    highlight = now.highlight.moved(now_shown, by, ends=ends)
                else:
                    highlight = Highlight(index=0 if by == 1 else len(now_shown) - 1)
                set_suggesting(Suggesting(is_open=True, highlight=highlight))
                return highlighted_in_view
            case KeyPressed(key=Key.Enter | Key.ControlJ | Key.Tab) if now.is_open:
                if not (now_shown := subsequence_matches(get_state(set_value), options)):
                    return ()
                index = None if now.highlight is None else now.highlight.index_in(now_shown)
                return None if index is None else choose(now_shown[index])
            case KeyPressed(key=Key.Escape) if now.is_open:
                set_suggesting(replace(now, is_open=False))
                return ()
            case _:
                if (controls := response_controls(field.on_input(event, receiver))) is None:
                    return None
                return (*controls, highlighted_in_view)

    def hovered(index: int, option: str) -> InputHandler:
        def on_hover(event: InputEvent, _: Receiver) -> InputResponse:
            if isinstance(event, MouseMoved) and event.button is None:
                set_suggesting(lambda now: replace(now, highlight=Highlight(key=option, index=index)))
            return None

        return on_hover

    box = text_field_box(styles.field, style, is_focused, is_focusable)
    children: tuple[Div, ...] = (text_field_row(field, value, placeholder, styles.field, box),)
    if is_focused and suggesting.is_open:
        shown = subsequence_matches(value, options)
        highlighted = None if suggesting.highlight is None else suggesting.highlight.index_in(shown)
        rows = tuple(
            Text(
                content=option,
                style=text_wrap_none | styles.option | (styles.highlighted_option if index == highlighted else default),
                handle=highlighted_row if index == highlighted else None,
                on_input=first(hovered(index, option), on_click(partial(choose, option))),
            )
            for index, option in enumerate(shown)
        ) or (Text(content="nothing matches", style=text_wrap_none | styles.option | styles.no_matches),)
        list_layout = layout_style(styles.list_box)
        list_frame = sum(
            cells(length)
            for length in (
                list_layout.border_top,
                list_layout.border_bottom,
                list_layout.padding_top,
                list_layout.padding_bottom,
            )
        )
        list_rows = min(len(rows), shown_rows) + list_frame
        room_below = rects.screen.bottom - rects.border.bottom
        room_above = rects.border.top - rects.screen.top
        match opens:
            case "below":
                is_above = False
            case "above":
                is_above = True
            case "auto":
                is_above = list_rows > room_below and room_above > room_below
            case _ as unreachable:
                assert_never(unreachable)
        children = (
            *children,
            Div(
                style=z(1)
                | position_absolute
                | beside_box(box, is_above)
                | clip_to_screen
                | col
                | styles.list_box
                | max_height(shown_rows + list_frame)
                | overflow_y_scroll,
                on_input=scroll_on_wheel(1),
                children=rows,
            ),
        )

    return Div(style=box, on_input=first(on_input, focus_receiver_on_press), children=children)


def cells(length: waxy.Length | waxy.Percent) -> int:
    """How many cells a border or padding is wide, which a percentage of nothing isn't."""
    return int(length.value) if isinstance(length, waxy.Length) else 0


def beside_box(box: Style, is_above: bool) -> Style:
    """
    The insets that put an absolutely positioned child of an element styled `box` against its border box,
    as wide as it, and below it or above it, rather than inside its padding box, from which insets are measured.
    """
    layout = layout_style(box)
    left, right = cells(layout.border_left), cells(layout.border_right)
    if is_above:
        return Style(
            layout=waxy.Style(
                inset_bottom=waxy.Percent(1.0),
                margin_bottom=waxy.Length(cells(layout.border_top)),
                inset_left=waxy.Length(-left),
                inset_right=waxy.Length(-right),
            )
        )
    return Style(
        layout=waxy.Style(
            inset_top=waxy.Percent(1.0),
            margin_top=waxy.Length(cells(layout.border_bottom)),
            inset_left=waxy.Length(-left),
            inset_right=waxy.Length(-right),
        )
    )


@component
def text_area(
    value: str,
    set_value: Editor[str],
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


@dataclass(frozen=True, slots=True, kw_only=True)
class TerminalStyles:
    """
    How [`terminal`][counterweight.widgets.terminal] draws its box.

    The box is styled by `box`, then the `style` passed to the widget, then `focused_box` while it's focused,
    as [`ScrollAreaStyles`][counterweight.widgets.ScrollAreaStyles] styles a scroll area's box.
    """

    box: Style = border | border_lightrounded | border_color("slate", 600)
    """The box around the terminal."""
    focused_box: Style = border_color("indigo", 400)
    """Merged over `box` and the widget's `style` while the widget is focused."""

    def box_style(self, style: Style, is_focused: bool) -> Style:
        """The style of the widget's box, with `style` merged over `box`, under `focused_box` while it's focused."""
        return self.box | style | (self.focused_box if is_focused else default)


@component
def terminal(
    argv: Sequence[str],
    style: Style = default,
    styles: TerminalStyles = TerminalStyles(),
    intercept: InputHandler | None = None,
    env: Mapping[str, str] = frozendict(),
    clear_env: bool = False,
    cwd: Path | None = None,
    hangup_grace: timedelta = HANGUP_GRACE,
    auto_focus: bool = False,
    handle: FocusHandle | None = None,
    is_focusable: bool = True,
    in_focus_order: bool = True,
    skips: Collection[str] = frozenset(),
) -> Canvas:
    """
    A bordered box that runs an interactive program, such as a shell or an editor, in a terminal the size of its content,
    built on [`use_terminal`][counterweight.headless.use_terminal],
    which takes `argv`, `env`, `clear_env`, `cwd`, `hangup_grace`, `skips` and the focus parameters,
    `handle` being a focus handle.
    While it's focused, the program gets every key, the cursor shows, and its border shows it's focused;
    a press on it focuses it.

    The box takes no size from the program, so size it with `style`, as with `fill(1)` or `size(82, 26)`:
    the program starts once the box has room, and its terminal resizes with the box.

    Parameters:
        style: Merged over the box's style from `styles`, as for a size.

        styles: How the box is drawn.

        intercept: A handler that sees each event before the terminal does, and keeps an event from the program
            by claiming it, as a multiplexer's prefix key does.
            The terminal claims every key while it's focused, Ctrl+C included,
            so an app needs some key here, or in `skips`, or some other way, to move focus out of it.
    """
    content = use_rects().content
    embedded = use_terminal(
        argv,
        content.width,
        content.height,
        env=env,
        clear_env=clear_env,
        cwd=cwd,
        hangup_grace=hangup_grace,
        auto_focus=auto_focus,
        handle=handle,
        is_focusable=is_focusable,
        in_focus_order=in_focus_order,
        skips=skips,
    )
    return Canvas(
        painter=embedded.view,
        style=styles.box_style(style, embedded.focus.is_focused),
        on_input=embedded.on_input if intercept is None else first(intercept, embedded.on_input),
    )


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


__all__ = [
    "ComboboxStyles",
    "ScrollAreaStyles",
    "TerminalStyles",
    "TextFieldStyles",
    "combobox",
    "scroll_area",
    "terminal",
    "text_area",
    "text_input",
]
