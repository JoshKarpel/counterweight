from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar, overload

from structlog import get_logger

from counterweight._context_vars import current_hook_state, current_use_mouse_listeners
from counterweight._utils import forever
from counterweight.geometry import Position, Rect
from counterweight.hooks.types import Deps, Getter, Ref, Setter, Setup

logger = get_logger()

T = TypeVar("T")


@overload
def use_state(initial_value: Getter[T]) -> tuple[T, Setter[T]]: ...


@overload
def use_state(initial_value: T) -> tuple[T, Setter[T]]: ...


def use_state(initial_value: Getter[T] | T) -> tuple[T, Setter[T]]:
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


def use_ref(initial_value: Getter[T] | T) -> Ref[T]:
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
    content: Rect
    padding: Rect
    border: Rect
    margin: Rect


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

    p, b, m = dims.padding_border_margin_rects()

    return Rects(
        content=dims.content,
        padding=p,
        border=b,
        margin=m,
    )


@dataclass(frozen=True, slots=True)
class Mouse:
    absolute: Position
    """The absolute position of the mouse on the screen (i.e., the top-left corner of the screen is `Position(x=0, y=0)`)."""

    motion: Position
    """The difference in the `absolute` position of the mouse since the last render cycle."""

    button: int | None
    """The button that is currently pressed, or `None` if no button is pressed."""


_INITIAL_MOUSE = Mouse(absolute=Position.flyweight(-1, -1), motion=Position.flyweight(0, 0), button=None)


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

    return Hovered(
        content=mouse.absolute in rects.content,
        padding=mouse.absolute in rects.padding,
        border=mouse.absolute in rects.border,
        margin=mouse.absolute in rects.margin,
    )
