from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import overload

from counterweight._context_vars import (
    current_focused,
    current_hook_state,
    current_layouts,
    current_use_mouse_listeners,
)
from counterweight._utils import forever
from counterweight.focus import FocusHandle
from counterweight.geometry import Position, Rects
from counterweight.hooks.impls import NodeKey
from counterweight.hooks.types import Deps, Getter, Ref, Setter, Setup
from counterweight.layout import INITIAL_RECTS, Layouts

logger = logging.getLogger(__name__)


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
            It is the same object on every render,
            so it can be left out of an effect's `deps`, and including it never reruns the effect.
            Once the component unmounts, calling it does nothing.
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
            If `None`, the `setup` function will be run every time the component renders.
    """
    return current_hook_state.get().use_effect(setup, deps)


def use_memo[T](compute: Getter[T], deps: tuple[object, ...]) -> T:
    """
    Parameters:
        compute: A zero-argument function that computes the value.
            It runs while the component renders: on the first render, and on every render whose `deps` changed.

        deps: The values `compute` depends on.
            If any of them change (compared with `==`), `compute` runs again.
            `()` computes the value once, when the component mounts.
            Unlike `use_effect`'s, these can't be `None`: to compute on every render, don't use this hook.

    Returns:
        The value `compute` returned when `deps` last changed.
            It is the same object on every render until then,
            so an element returned from it keeps the components below it from re-running,
            and a handler returned from it can be passed to a `memo` component without making it re-run.
            The cached value MUST depend only on `deps`;
            `check_purity` on `counterweight.app.app` catches a value that goes stale.
    """
    return current_hook_state.get().use_memo(compute, deps)


def use_rects() -> Rects:
    """
    Returns:
        A recording describing the rectangular areas of the
            `content`, `padding`, `border`, and `margin` of
            the calling component's top-level element
            *on the previous render cycle*.
            In the initial render, the returned rectangles will all be positioned
            at the top-left corner of the screen with `0` width and height.
            A component that calls `use_rects` also renders on the next render cycle after its rectangles move.
    """
    hooks = current_hook_state.get()
    rects = rects_in(current_layouts.get(), hooks.key)
    hooks.rects = rects
    return rects


def rects_in(layouts: Layouts, key: NodeKey) -> Rects:
    """The rectangles `use_rects` reports for the node with `key`, given the previous frame's `layouts`."""
    # A node absent from the previous frame's layouts was hidden or not yet mounted.
    return layouts.by_key.get(key, INITIAL_RECTS)


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
        content=rects.content.contains(mouse.absolute),
        padding=rects.padding.contains(mouse.absolute),
        border=rects.border.contains(mouse.absolute),
        margin=rects.margin.contains(mouse.absolute),
    )


@dataclass(frozen=True, slots=True)
class Focus:
    """What [`use_focus`][counterweight.hooks.use_focus] returns to the calling component."""

    is_focused: bool
    """Whether the calling component is focused, so it receives key presses, as of this render."""

    handle: FocusHandle
    """The handle that names the calling component, for [`FocusOn`][counterweight.controls.FocusOn]."""


def use_focus(
    auto_focus: bool = False,
    handle: FocusHandle | None = None,
    is_focusable: bool = True,
    in_focus_order: bool = True,
) -> Focus:
    """
    Makes the calling component focusable.
    Its top-level element, the one it returns, is the one that's focused,
    so a component that handles key presses puts its handler on that element.
    A component can call it only once.

    Parameters:
        auto_focus: Whether the component takes focus when it mounts visible and focusable while nothing is focused.
            When several mount in the same render, the first in tree order takes focus.
            A component that mounts hidden or unfocusable doesn't take focus when it's shown or made focusable later.

        handle: The handle that names the component, which a parent creates with `use_state(FocusHandle)`
            to focus a child it renders with [`FocusOn`][counterweight.controls.FocusOn].
            If `None`, `use_focus` creates one on the first render and keeps it.
            Every render MUST pass the same handle as the first,
            or `use_focus` raises `ChangedFocusHandle`,
            and two mounted components given the same handle raise `DuplicateFocusHandle`.

        is_focusable: Whether the component can be focused, like a browser's `disabled` attribute when `False`.
            Nothing can focus an unfocusable component,
            and making the focused component unfocusable clears focus.
            It still receives the mouse events routed to it.

        in_focus_order: Whether [`FocusNext`][counterweight.controls.FocusNext]
            and [`FocusPrevious`][counterweight.controls.FocusPrevious] stop on the component,
            like a browser's `tabindex="-1"` when `False`.
            A component out of the focus order can still be focused with
            [`FocusOn`][counterweight.controls.FocusOn], `auto_focus`, or a press,
            and keeps focus once it has it.

    Returns:
        Whether the component is focused, and its handle, which is the same object on every render.
    """
    hooks = current_hook_state.get()
    focus = hooks.use_focus(
        auto_focus=auto_focus, handle=handle, is_focusable=is_focusable, in_focus_order=in_focus_order
    )
    return Focus(is_focused=is_focusable and current_focused.get() == hooks.key, handle=focus.handle)
