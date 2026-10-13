"""
Library input handlers for behaviors that apps compose onto their elements,
and the combinators that compose several handlers into the one an element takes.
Each is a pure function of an event and a receiver, so it can be tested without running an app.
"""

from __future__ import annotations

from collections.abc import Callable

from counterweight.controls import ClearFocus, FocusNext, FocusOn, FocusPrevious, ScrollBy
from counterweight.events import (
    InputEvent,
    InputHandler,
    InputResponse,
    KeyPressed,
    MouseDown,
    MouseMoved,
    MouseScrolledDown,
    MouseScrolledLeft,
    MouseScrolledRight,
    MouseScrolledUp,
    MouseUp,
    Receiver,
    response_controls,
)
from counterweight.focus import ElementHandle, FocusHandle, Subtree
from counterweight.geometry import Position, Scroll
from counterweight.keys import Key


def first(*handlers: InputHandler) -> InputHandler:
    """
    A handler that calls each of `handlers` in turn with the same event and receiver,
    and returns the first response that isn't `None`, `()` included, without calling the rest.
    It returns `None` if none of them responds.
    """

    def handler(event: InputEvent, receiver: Receiver) -> InputResponse:
        for inner in handlers:
            if (response := inner(event, receiver)) is not None:
                return response
        return None

    return handler


def each(*handlers: InputHandler) -> InputHandler:
    """
    A handler that calls every one of `handlers` with the same event and receiver.
    If any responds with something other than `None`,
    it returns a tuple of every control they returned, in the order of `handlers`,
    which is `()` if every response was `()`.
    It returns `None` if none of them responds.
    """

    def handler(event: InputEvent, receiver: Receiver) -> InputResponse:
        responses = [response_controls(inner(event, receiver)) for inner in handlers]
        if all(response is None for response in responses):
            return None
        return tuple(control for response in responses for control in response or ())

    return handler


def on_click(action: Callable[[], InputResponse]) -> InputHandler:
    """
    A handler that claims a button `1` `MouseDown`, and so every later event of the press,
    and on the press's `MouseUp`, calls `action` if the release is over the element:
    inside its border box, and inside its clip, where it's painted.
    It returns the controls `action` returns, or `()` if `action` returns `None`.
    It returns `None` for anything else, such as a key or a pointer move with no button held.
    """

    def handler(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case MouseDown(button=1) | MouseMoved(button=1):
                return ()
            case MouseUp(absolute=position, button=1):
                if (visible := receiver.rects.visible) is None or not visible.contains(position):
                    return ()
                response = action()
                return () if response is None else response
            case _:
                return None

    return handler


def tab_focus(event: InputEvent, receiver: Receiver) -> InputResponse:
    """
    A handler that moves focus to the next focusable component inside its element for Tab,
    and to the previous one for Shift+Tab, wrapping at the ends.
    On the root component's element it moves through the whole tree;
    on a modal's, it keeps Tab inside the modal.
    It returns `None` for anything else.
    """
    match event:
        case KeyPressed(key=Key.Tab):
            return FocusNext(within=receiver.subtree)
        case KeyPressed(key=Key.BackTab):
            return FocusPrevious(within=receiver.subtree)
        case _:
            return None


def focus_receiver_on_press(event: InputEvent, receiver: Receiver) -> InputResponse:
    """
    A handler that claims a `MouseDown` and focuses the component whose element received it.
    It goes on the element a focusable component returns, the one whose receiver carries its
    [`focus_handle`][counterweight.events.Receiver.focus_handle].
    It returns `None` for anything else.

    Raises:
        ValueError: For a `MouseDown` whose receiver has no `focus_handle`,
            because the component never called `use_focus`, or the handler is on an inner element.
    """
    match event:
        case MouseDown():
            if receiver.focus_handle is None:
                raise ValueError(
                    "focus_receiver_on_press received a press on an element that isn't focusable. "
                    "Put it on the element a component that calls use_focus returns, "
                    "or use focus_on_press(handle) to focus another component."
                )
            return FocusOn(receiver.focus_handle)
        case _:
            return None


def focus_on_press(handle: FocusHandle) -> InputHandler:
    """
    A handler that claims a `MouseDown` and focuses the component with `handle`,
    such as a label focusing the input beside it, whatever element received the press.
    It returns `None` for anything else.
    """

    def handler(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case MouseDown():
                return FocusOn(handle)
            case _:
                return None

    return handler


def clear_focus(event: InputEvent, receiver: Receiver) -> InputResponse:
    """
    A handler that claims a `MouseDown` and clears focus.
    On the root component's element it blurs on a press nothing below it claimed;
    composed into a non-focusable element's own press handler, it blurs on the presses that element claims.
    It returns `None` for anything else.
    """
    match event:
        case MouseDown():
            return ClearFocus()
        case _:
            return None


def scroll_on_wheel(lines: int = 3) -> InputHandler:
    """
    A handler that scrolls the scroll container it's on by `lines` toward the wheel's direction
    for each `MouseScrolledUp`, `MouseScrolledDown`, `MouseScrolledLeft` and `MouseScrolledRight`,
    which is three lines by default, as desktop platforms scroll for each notch of the wheel.
    It returns `None` for a wheel event that would move the container past the end of its range,
    so the event bubbles to the next scroll container out, as the web chains scrolling,
    and for anything else.

    Raises:
        ValueError: For a wheel event whose receiver isn't a [scroll container](../layout/scrolling.md).
    """

    def handler(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case MouseScrolledUp():
                delta = Position(0, -lines)
            case MouseScrolledDown():
                delta = Position(0, lines)
            case MouseScrolledLeft():
                delta = Position(-lines, 0)
            case MouseScrolledRight():
                delta = Position(lines, 0)
            case _:
                return None
        if (scroll := receiver.scroll) is None:
            raise ValueError(
                "scroll_on_wheel received a wheel event on an element that isn't a scroll container. "
                "Put it on an element whose overflow is Scroll, such as with overflow_y_scroll."
            )
        if scroll.clamp(scroll.offset + delta) == scroll.offset:
            return None
        return ScrollBy(receiver.subtree, x=delta.x, y=delta.y)

    return handler


# How much of the view a page scrolls by default: Chrome's page step,
# `kMinFractionToStepWhenPaging` in Chromium's `ScrollableArea`,
# which keeps the last eighth of one page in view at the top of the next, to read on from.
PAGE_FRACTION = 0.875


def scroll_on_keys(page: float = PAGE_FRACTION) -> InputHandler:
    """
    A handler that scrolls the scroll container it's on for the keys that scroll a page in a browser:
    `Up` and `Down` by a row, `Left` and `Right` by a column,
    `PageUp` and `PageDown` by `page` times the height of the view (see [`page_down`][counterweight.handlers.page_down]),
    and `Home` and `End` to the start and the end of the content.
    A key press reaches it while the container, or an element inside it, is focused,
    so the container is usually the top-level element of a component that calls
    [`use_focus`][counterweight.hooks.use_focus], and a focused element inside that handles a key itself stops it first.
    It returns `None` for a key that would move the container past the end of its range,
    so the key bubbles to the next scroll container out, as `scroll_on_wheel` does with the wheel,
    and for anything else.

    Raises:
        ValueError: For one of those keys when its receiver isn't a [scroll container](../layout/scrolling.md).
    """

    def handler(event: InputEvent, receiver: Receiver) -> InputResponse:
        if not isinstance(event, KeyPressed) or event.key not in SCROLL_KEYS:
            return None
        if (scroll := receiver.scroll) is None:
            raise ValueError(
                "scroll_on_keys received a key press on an element that isn't a scroll container. "
                "Put it on an element whose overflow is Scroll, such as with overflow_y_scroll."
            )
        match event.key:
            case Key.Up:
                control = ScrollBy(receiver.subtree, y=-1)
            case Key.Down:
                control = ScrollBy(receiver.subtree, y=1)
            case Key.Left:
                control = ScrollBy(receiver.subtree, x=-1)
            case Key.Right:
                control = ScrollBy(receiver.subtree, x=1)
            case Key.PageUp:
                control = page_up(receiver.subtree, scroll, page)
            case Key.PageDown:
                control = page_down(receiver.subtree, scroll, page)
            case Key.Home:
                control = ScrollBy(receiver.subtree, y=-scroll.offset.y)
            case _:  # Key.End, the last of SCROLL_KEYS
                control = ScrollBy(receiver.subtree, y=scroll.max_offset.y - scroll.offset.y)
        if scroll.clamp(control.destination(scroll.offset)) == scroll.offset:
            return None
        return control

    return handler


SCROLL_KEYS = frozenset({Key.Up, Key.Down, Key.Left, Key.Right, Key.PageUp, Key.PageDown, Key.Home, Key.End})


def page_down(target: ElementHandle | Subtree, scroll: Scroll, fraction: float = PAGE_FRACTION) -> ScrollBy:
    """
    The `ScrollBy` that scrolls the scroll container `target` names, scrolled as `scroll` says,
    down by `fraction` of the height of its view, rounded down, and at least one row.

    The default is Chrome's, so on a 24-row view a page is 21 rows, and 3 stay in view.
    `fraction=0.5` is `less`'s half page for `d`, and `fraction=1.0` its whole page for `Space`, with nothing kept.

    Raises:
        ValueError: If `fraction` isn't positive.
    """
    return ScrollBy(target, y=page_rows(scroll, fraction))


def page_up(target: ElementHandle | Subtree, scroll: Scroll, fraction: float = PAGE_FRACTION) -> ScrollBy:
    """
    The `ScrollBy` that scrolls the scroll container `target` names up by a page,
    as [`page_down`][counterweight.handlers.page_down] scrolls it down.

    Raises:
        ValueError: If `fraction` isn't positive.
    """
    return ScrollBy(target, y=-page_rows(scroll, fraction))


def page_rows(scroll: Scroll, fraction: float) -> int:
    """How many rows a page of `fraction` of `scroll`'s view is: rounded down, and at least one."""
    if fraction <= 0:
        raise ValueError(f"A page must be a positive fraction of the view, but got {fraction!r}")
    return max(1, int(scroll.view_height * fraction))
