"""
[`use_scroll_area`][counterweight.headless.use_scroll_area], which scrolls a box with the keys, the wheel and controls,
and leaves drawing it to its caller.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal

from counterweight.controls import FocusOn
from counterweight.controls import ScrollBy
from counterweight.controls import ScrollTo
from counterweight.events import InputEvent
from counterweight.events import InputHandler
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseScrolledDown
from counterweight.events import MouseScrolledLeft
from counterweight.events import MouseScrolledRight
from counterweight.events import MouseScrolledUp
from counterweight.events import Receiver
from counterweight.focus import ElementHandle
from counterweight.focus import FocusHandle
from counterweight.geometry import Position
from counterweight.geometry import Scroll
from counterweight.handlers import PAGE_FRACTION
from counterweight.handlers import check_page_fraction
from counterweight.handlers import page_down
from counterweight.handlers import page_up
from counterweight.hooks import Focus
from counterweight.hooks import use_focus
from counterweight.hooks import use_scroll
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles import Style
from counterweight.styles.utilities import default
from counterweight.styles.utilities import overflow_scroll
from counterweight.styles.utilities import overflow_x_hidden
from counterweight.styles.utilities import overflow_x_scroll
from counterweight.styles.utilities import overflow_y_clip
from counterweight.styles.utilities import overflow_y_scroll
from counterweight.styles.utilities import stick_to_end_x
from counterweight.styles.utilities import stick_to_end_y

# Which way a scroll area scrolls: sideways, vertically, or both.
type ScrollAxis = Literal["x", "y", "both"]

# The axis an area doesn't scroll clips, so its content can't spill over its border and its siblings.
# Hidden overflow lets an area that scrolls vertically narrow beside its siblings, as a scroll container can,
# and clipping leaves an area that scrolls sideways as tall as its content, as in a column of a document.
OVERFLOWS: dict[ScrollAxis, Style] = {
    "x": overflow_x_scroll | overflow_y_clip,
    "y": overflow_y_scroll | overflow_x_hidden,
    "both": overflow_scroll,
}
STICKS: dict[ScrollAxis, Style] = {"x": stick_to_end_x, "y": stick_to_end_y, "both": stick_to_end_x | stick_to_end_y}


@dataclass(frozen=True, slots=True)
class ScrollArea:
    """What [`use_scroll_area`][counterweight.headless.use_scroll_area] returns to the calling component."""

    style: Style
    """
    The style that makes the element `viewport` names a scroll container on the area's axes,
    and sticks it to its end on them if `stick_to_end` was passed,
    for the calling component to merge over that element's own style: `style=fill(1) | col | area.style`.
    On the axis it doesn't scroll, it clips the content, so a line too long for an area that scrolls vertically
    doesn't spill over its border: with hidden overflow there, so the area narrows beside its siblings,
    or for an area that scrolls sideways, with clipped overflow, so it stays as tall as its content.
    It MUST be merged after any style that sets overflow,
    such as the constraint utilities `fill`, `length`, `percentage` and `ratio`, which hide it,
    or the element doesn't scroll.
    It sets nothing else, so the element's size and layout are the caller's.
    """

    viewport: ElementHandle
    """
    The element handle for the calling component to give the element that scrolls:
    the one passed to the hook, or one the hook creates.
    The area's handler and its controls scroll that element,
    and [`ScrollTo`][counterweight.controls.ScrollTo], [`ScrollBy`][counterweight.controls.ScrollBy]
    and [`use_scroll`][counterweight.hooks.use_scroll] reach it through the handle from anywhere.
    """

    scroll: Scroll
    """How far the viewport is scrolled, as [`use_scroll`][counterweight.hooks.use_scroll] reports it."""

    is_at_start: bool
    """Whether the viewport is scrolled to the start of its content on each of the area's axes, as of `scroll`."""

    is_at_end: bool
    """
    Whether the viewport is scrolled to the end of its content on each of the area's axes, as of `scroll`,
    which is also true while the content fits, so a "jump to latest" button can show while it's false.
    """

    to_start: ScrollTo
    """The control that scrolls the viewport to the start of its content on the area's axes."""

    to_end: ScrollTo
    """
    The control that scrolls the viewport to the end of its content on the area's axes,
    wherever the end is when it applies, so it reaches the end of content that grew since the last render.
    """

    focus: Focus
    """
    Whether the calling component is focused, and its focus handle,
    as [`use_focus`][counterweight.hooks.use_focus] returns them.
    """

    on_input: InputHandler
    """
    The handler that scrolls the viewport, for the calling component to put on the element it returns,
    which is the one that's focused, and which a wheel event or a press anywhere inside it bubbles to.
    For the keys that scroll a page in a browser, it returns a [`ScrollBy`][counterweight.controls.ScrollBy]
    or [`ScrollTo`][counterweight.controls.ScrollTo] for the viewport:
    `Up` and `Down` by a row, `Left` and `Right` by a column,
    `PageUp`, `PageDown` and `Space` by a page (see [`page_down`][counterweight.handlers.page_down]),
    and `Home` and `End` to the start and the end: vertically, or for an area that only scrolls sideways, sideways.
    For the wheel, it scrolls by `wheel_lines` toward the wheel's direction,
    as [`scroll_on_wheel`][counterweight.handlers.scroll_on_wheel] does, Shift with the vertical wheel included.
    It returns `None` for a key or a wheel event that would move the viewport past the end of its range, as of `scroll`,
    so the event bubbles to the next scroll container out.
    For a `MouseDown`, it returns [`FocusOn`][counterweight.controls.FocusOn] for the component while it's focusable,
    so a press that nothing inside the area claims focuses it, as a click focuses the nearest focusable element
    around it in a browser.
    It returns `None` for anything else.
    """


def use_scroll_area(
    axis: ScrollAxis = "y",
    stick_to_end: bool = False,
    viewport: ElementHandle | None = None,
    wheel_lines: int = 3,
    page: float = PAGE_FRACTION,
    auto_focus: bool = False,
    handle: FocusHandle | None = None,
    is_focusable: bool = True,
    in_focus_order: bool = True,
) -> ScrollArea:
    """
    Scrolls a box with the keys, the wheel and controls, leaving how it's drawn to the calling component,
    as [Radix UI's ScrollArea](https://www.radix-ui.com/primitives/docs/components/scroll-area) does for the web.
    The hook makes the calling component focusable, as browsers make a scroll container focusable,
    so Tab reaches it and the keys scroll it.

    The calling component returns the element that's focused, which takes `on_input`,
    and draws the content in the element that scrolls, which takes `viewport` and `style`.
    They can be one element, or the scrolling one can be inside the other,
    with things that stay put while it scrolls, such as a title or a "jump to latest" button, beside it.

    Parameters:
        axis: Which way the area scrolls: `"y"` vertically, `"x"` sideways, or `"both"`.

        stick_to_end: Whether the viewport stays scrolled to its end on the area's axes as its content grows,
            as for a log or a chat (see [Following the end](../layout/scrolling.md#following-the-end)).

        viewport: The element handle for the element that scrolls, which a parent creates with
            `use_state(ElementHandle)` to scroll the area or read its scroll from outside it.
            If `None`, the hook creates one on the first render and keeps it.

        wheel_lines: How many lines each notch of the wheel scrolls.

        page: How much of the height of the view `PageUp`, `PageDown` and `Space` scroll,
            as for [`scroll_on_keys`][counterweight.handlers.scroll_on_keys].

        auto_focus: Passed to [`use_focus`][counterweight.hooks.use_focus].

        handle: The focus handle passed to [`use_focus`][counterweight.hooks.use_focus].

        is_focusable: Passed to [`use_focus`][counterweight.hooks.use_focus].

        in_focus_order: Passed to [`use_focus`][counterweight.hooks.use_focus],
            where `False` leaves the area out of Tab's order, as `tabindex="-1"` does for a scroll container.

    Returns:
        The style and the element handle for the element that scrolls, how far it's scrolled,
        and the handler that scrolls it, for the element the calling component returns.

    Raises:
        ValueError: If `page` isn't positive.
    """
    check_page_fraction(page)
    focus = use_focus(auto_focus=auto_focus, handle=handle, is_focusable=is_focusable, in_focus_order=in_focus_order)
    own_viewport, _ = use_state(ElementHandle)
    viewport = own_viewport if viewport is None else viewport
    scroll = use_scroll(viewport)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        control: ScrollBy | ScrollTo | None
        match event:
            case MouseDown():
                return FocusOn(focus.handle) if is_focusable else None
            case KeyPressed(key=key):
                control = key_scroll(key, viewport, scroll, axis, page)
            case MouseScrolledUp() | MouseScrolledDown() | MouseScrolledLeft() | MouseScrolledRight():
                control = wheel_scroll(event, viewport, wheel_lines)
            case _:
                return None
        if control is None or scroll.clamp(control.destination(scroll.offset)) == scroll.offset:
            return None
        return control

    has_x = axis != "y"
    has_y = axis != "x"
    return ScrollArea(
        style=OVERFLOWS[axis] | (STICKS[axis] if stick_to_end else default),
        viewport=viewport,
        scroll=scroll,
        is_at_start=(not has_x or scroll.offset.x == 0) and (not has_y or scroll.offset.y == 0),
        is_at_end=(not has_x or scroll.offset.x >= scroll.max_offset.x)
        and (not has_y or scroll.offset.y >= scroll.max_offset.y),
        to_start=ScrollTo(viewport, x=0 if has_x else None, y=0 if has_y else None),
        to_end=ScrollTo(viewport, x=sys.maxsize if has_x else None, y=sys.maxsize if has_y else None),
        focus=focus,
        on_input=on_input,
    )


def key_scroll(
    key: str, viewport: ElementHandle, scroll: Scroll, axis: ScrollAxis, page: float
) -> ScrollBy | ScrollTo | None:
    """The control that scrolls `viewport` for `key`, as a browser scrolls a focused scroll container, or `None`."""
    match key:
        case Key.Up:
            return ScrollBy(viewport, y=-1)
        case Key.Down:
            return ScrollBy(viewport, y=1)
        case Key.Left:
            return ScrollBy(viewport, x=-1)
        case Key.Right:
            return ScrollBy(viewport, x=1)
        case Key.PageUp:
            return page_up(viewport, scroll, page)
        case Key.PageDown | Key.Space:
            return page_down(viewport, scroll, page)
        # Vertical, as in a browser, unless the area only scrolls sideways,
        # and absolute, past any end, so End reaches the end of content that grew since the last render.
        case Key.Home:
            return ScrollTo(viewport, x=0) if axis == "x" else ScrollTo(viewport, y=0)
        case Key.End:
            return ScrollTo(viewport, x=sys.maxsize) if axis == "x" else ScrollTo(viewport, y=sys.maxsize)
        case _:
            return None


def wheel_scroll(
    event: MouseScrolledUp | MouseScrolledDown | MouseScrolledLeft | MouseScrolledRight,
    viewport: ElementHandle,
    lines: int,
) -> ScrollBy:
    """The `ScrollBy` that moves `viewport` by `lines` toward the wheel's direction, sideways for Shift with it."""
    match event:
        case MouseScrolledUp(is_shift_held=True):
            delta = Position(-lines, 0)
        case MouseScrolledDown(is_shift_held=True):
            delta = Position(lines, 0)
        case MouseScrolledUp():
            delta = Position(0, -lines)
        case MouseScrolledDown():
            delta = Position(0, lines)
        case MouseScrolledLeft():
            delta = Position(-lines, 0)
        case _:  # MouseScrolledRight
            delta = Position(lines, 0)
    return ScrollBy(viewport, x=delta.x, y=delta.y)
