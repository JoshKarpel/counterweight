from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import overload

import waxy
from structlog import get_logger

from counterweight._context_vars import current_hook_state, current_use_mouse_listeners
from counterweight._utils import forever
from counterweight.controls import AnyControl, StopPropagation
from counterweight.events import KeyPressed, MouseEvent, MouseScrolledDown, MouseScrolledUp
from counterweight.geometry import Position
from counterweight.hooks.types import Deps, Getter, Ref, Setter, Setup
from counterweight.keys import Key
from counterweight.styles.styles import Style

logger = get_logger()


@overload
def use_state[T](initial_value: Getter[T]) -> tuple[T, Setter[T]]: ...


@overload
def use_state[T](initial_value: T) -> tuple[T, Setter[T]]: ...


def use_state[T](initial_value: Getter[T] | T) -> tuple[T, Setter[T]]:
    """
    Parameters:
        initial_value: The initial value of the state.
            It can either be the initial value itself, or a zero-argument function that returns the initial value.

    Returns:
        The current value of the state (i.e., for the current render cycle).

        A function that can be called to update the value of the state (e.g., in an event handler).
            It can either be called with the new value of the state,
            or a function that takes the current value of the state and returns the new value of the state.
            If the value is not equal to the current of the state,
            Counterweight will trigger a render cycle.
    """
    return current_hook_state.get().use_state(initial_value)


def use_ref[T](initial_value: Getter[T] | T) -> Ref[T]:
    """
    Parameters:
        initial_value: the initial value of the ref.
            It can either be the initial value itself, or a zero-argument function that returns the initial value.

    Returns:
        A [`Ref`][counterweight.hooks.Ref] that holds a reference to the given value.
    """
    return current_hook_state.get().use_ref(initial_value)


def use_effect(setup: Setup, deps: Deps = None) -> None:
    """
    Parameters:
        setup: The setup function that will be called when the component first mounts
            or if its dependencies have changed (see below).

        deps: The dependencies of the effect.
            If any of the dependencies change, the previous invocation of the `setup` function will be cancelled
            and the `setup` function will be run again.
            If `None`, the `setup` function will be run on every render.
    """
    return current_hook_state.get().use_effect(setup, deps)


@dataclass(frozen=True, slots=True)
class Rects:
    content: waxy.Rect
    padding: waxy.Rect
    border: waxy.Rect
    margin: waxy.Rect


def use_rects() -> Rects:
    """
    Returns:
        A recording describing the rectangular areas of the
            `content`, `padding`, `border`, and `margin` of
            the calling component's top-level element
            *on the previous render cycle*.
            In the initial render, the returned rectangles will all be positioned
            at the top-left corner of the screen with `0` width and height.
    """
    dims = current_hook_state.get().dims

    return Rects(
        content=dims.content,
        padding=dims.padding,
        border=dims.border,
        margin=dims.margin,
    )


@dataclass(frozen=True, slots=True)
class Mouse:
    absolute: Position
    """The absolute position of the mouse on the screen (i.e., the top-left corner of the screen is `Position(x=0, y=0)`)."""

    motion: Position
    """The difference in the `absolute` position of the mouse since the last render cycle."""

    button: int | None
    """The button that is currently pressed, or `None` if no button is pressed."""


_INITIAL_MOUSE = Mouse(absolute=Position(-1, -1), motion=Position(0, 0), button=None)


def use_mouse() -> Mouse:
    """
    Returns:
        A record describing the current state of the mouse.
    """
    # Why bother making this a state hook when we could instead store the mouse state directly in a context var?
    # Triggering a state change is a way to signal to the render loop that a component cares about the mouse state
    # without needing to invent a new mechanism dedicated to mouse events,
    # and thus makes them work a lot more like key events.
    mouse, set_mouse = use_state(_INITIAL_MOUSE)

    async def setup() -> None:
        use_mouse_listeners = current_use_mouse_listeners.get()

        use_mouse_listeners.add(set_mouse)

        try:
            await forever()
        finally:
            use_mouse_listeners.remove(set_mouse)

    use_effect(setup=setup, deps=())

    return mouse


@dataclass(frozen=True, slots=True)
class ScrollState:
    offset_x: int
    offset_y: int
    max_offset_x: int
    max_offset_y: int
    viewport_width: int
    viewport_height: int
    content_width: int
    content_height: int
    scroll_to: Callable[[int, int], None] = field(repr=False, compare=False)


def use_scroll(
    scroll_x: bool = False,
    scroll_y: bool = True,
    initial_offset_x: int = 0,
    initial_offset_y: int = 0,
    mouse_scroll_x: int = 1,
    mouse_scroll_y: int = 1,
    key_scroll_x: int = 1,
    key_scroll_y: int = 1,
    reset_on: object = None,
    auto_scroll_to_x: int | None = None,
    auto_scroll_to_y: int | None = None,
) -> tuple[ScrollState, Style, Callable[[MouseEvent], AnyControl | None], Callable[[KeyPressed], AnyControl | None]]:
    """
    Parameters:
        scroll_x: Whether to enable horizontal scrolling.
        scroll_y: Whether to enable vertical scrolling.
        initial_offset_x: The initial horizontal scroll offset.
        initial_offset_y: The initial vertical scroll offset.
        mouse_scroll_x: Number of columns to scroll per mouse wheel tick (horizontal).
        mouse_scroll_y: Number of rows to scroll per mouse wheel tick (vertical).
        key_scroll_x: Number of columns to scroll per left/right arrow key press.
        key_scroll_y: Number of rows to scroll per up/down arrow key press.
        reset_on: When this value changes between renders, the scroll offset is reset to
            ``(initial_offset_x, initial_offset_y)``. Useful for resetting scroll when the
            content changes (e.g. navigating to a different file).
        auto_scroll_to_x: When set, the scroll offset is adjusted each render so that this
            column is visible in the viewport. Useful for following a cursor horizontally.
            Must be called from a component whose top-level element is the scroll container.
        auto_scroll_to_y: When set, the scroll offset is adjusted each render so that this
            row is visible in the viewport. Useful for following a cursor vertically.
            Must be called from a component whose top-level element is the scroll container.

    Returns:
        A [`ScrollState`][counterweight.hooks.ScrollState] describing the current scroll position and bounds.

        A [`Style`][counterweight.styles.Style] that must be merged onto the scroll container element.

        An ``on_mouse``-compatible handler for scroll events.

        An ``on_key``-compatible handler for arrow key scroll events.
    """
    (offset_x, offset_y), set_offset = use_state((initial_offset_x, initial_offset_y))
    last_reset_key, set_last_reset_key = use_state(reset_on)

    if reset_on != last_reset_key:
        set_last_reset_key(reset_on)
        set_offset((initial_offset_x, initial_offset_y))
        offset_x, offset_y = initial_offset_x, initial_offset_y

    rects = use_rects()
    dims = current_hook_state.get().dims

    viewport_width = int(rects.padding.width) + 1
    viewport_height = int(rects.padding.height) + 1

    # content_size is only available when this component's top-level element IS the scroll
    # container. When it's None (outer wrapper component), skip clamping to avoid blocking scroll.
    content_width = int(dims.content_size.width) if dims.content_size is not None else viewport_width
    content_height = int(dims.content_size.height) if dims.content_size is not None else viewport_height
    max_offset_x = max(0, content_width - viewport_width) if dims.content_size is not None else 2**31
    max_offset_y = max(0, content_height - viewport_height) if dims.content_size is not None else 2**31

    if auto_scroll_to_x is not None:
        if auto_scroll_to_x < offset_x:
            offset_x = max(0, auto_scroll_to_x)
            set_offset((offset_x, offset_y))
        elif auto_scroll_to_x >= offset_x + viewport_width:
            offset_x = min(max_offset_x, auto_scroll_to_x - viewport_width + 1)
            set_offset((offset_x, offset_y))

    if auto_scroll_to_y is not None:
        if auto_scroll_to_y < offset_y:
            offset_y = max(0, auto_scroll_to_y)
            set_offset((offset_x, offset_y))
        elif auto_scroll_to_y >= offset_y + viewport_height:
            offset_y = min(max_offset_y, auto_scroll_to_y - viewport_height + 1)
            set_offset((offset_x, offset_y))

    overflow_x = waxy.Overflow.Scroll if scroll_x else waxy.Overflow.Hidden
    overflow_y = waxy.Overflow.Scroll if scroll_y else waxy.Overflow.Hidden
    flex_dir = waxy.FlexDirection.Row if (scroll_x and not scroll_y) else waxy.FlexDirection.Column

    if scroll_x:
        # When horizontal scrolling is enabled, children must NOT be stretched to the
        # container width — they need to take their natural (content) width so they can
        # overflow horizontally. Override any align_children_stretch the caller may have set.
        layout = waxy.Style(
            overflow_x=overflow_x,
            overflow_y=overflow_y,
            flex_direction=flex_dir,
            align_items=waxy.AlignItems.FlexStart,
        )
    else:
        layout = waxy.Style(
            overflow_x=overflow_x,
            overflow_y=overflow_y,
            flex_direction=flex_dir,
        )

    scroll_style = Style(
        layout=layout,
        scroll_offset_x=offset_x,
        scroll_offset_y=offset_y,
    )

    def _scroll_to(x: int, y: int) -> None:
        set_offset((max(0, min(x, max_offset_x)), max(0, min(y, max_offset_y))))

    state = ScrollState(
        offset_x=offset_x,
        offset_y=offset_y,
        max_offset_x=max_offset_x,
        max_offset_y=max_offset_y,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        content_width=content_width,
        content_height=content_height,
        scroll_to=_scroll_to,
    )

    def _update_offset(dx: int, dy: int) -> None:
        def clamp(current: tuple[int, int]) -> tuple[int, int]:
            cx, cy = current
            new_x = max(0, min(cx + dx, max_offset_x))
            new_y = max(0, min(cy + dy, max_offset_y))
            return (new_x, new_y)

        set_offset(clamp)

    def on_mouse(event: MouseEvent) -> AnyControl | None:
        border_rect = rects.border
        event_point = waxy.Point(x=event.absolute.x, y=event.absolute.y)
        if not border_rect.contains(event_point):
            return None
        if isinstance(event, MouseScrolledDown):
            if scroll_y:
                _update_offset(0, mouse_scroll_y)
                return StopPropagation()
            elif scroll_x:
                _update_offset(mouse_scroll_x, 0)
                return StopPropagation()
        elif isinstance(event, MouseScrolledUp):
            if scroll_y:
                _update_offset(0, -mouse_scroll_y)
                return StopPropagation()
            elif scroll_x:
                _update_offset(-mouse_scroll_x, 0)
                return StopPropagation()
        return None

    def on_key(event: KeyPressed) -> AnyControl | None:
        match event.key:
            case Key.Down if scroll_y:
                _update_offset(0, key_scroll_y)
                return StopPropagation()
            case Key.Up if scroll_y:
                _update_offset(0, -key_scroll_y)
                return StopPropagation()
            case Key.Right if scroll_x:
                _update_offset(key_scroll_x, 0)
                return StopPropagation()
            case Key.Left if scroll_x:
                _update_offset(-key_scroll_x, 0)
                return StopPropagation()
        return None

    return state, scroll_style, on_mouse, on_key


@dataclass(frozen=True, slots=True)
class Hovered:
    content: bool
    padding: bool
    border: bool
    margin: bool


def use_hovered() -> Hovered:
    """
    Returns:
        A record describing which of the calling component's top-level element's
            `content`, `padding`, `border`, and `margin` rectangles the mouse is currently inside.
    """
    mouse = use_mouse()
    rects = use_rects()
    pos = waxy.Point(x=mouse.absolute.x, y=mouse.absolute.y)

    return Hovered(
        content=rects.content.contains(pos),
        padding=rects.padding.contains(pos),
        border=rects.border.contains(pos),
        margin=rects.margin.contains(pos),
    )
