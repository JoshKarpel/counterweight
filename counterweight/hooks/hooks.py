from __future__ import annotations

from typing import TypeVar, overload

from counterweight._context_vars import current_hook_state, current_mouse_event_queue
from counterweight.events import MouseMoved
from counterweight.geometry import Position
from counterweight.hooks.types import Deps, Getter, Ref, Setter, Setup

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


def use_effect(setup: Setup, deps: Deps | None = None) -> None:
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


def use_mouse() -> Position:
    pos, set_pos = use_state(Position.flyweight(0, 0))

    async def setup() -> None:
        mouse_event_queue = current_mouse_event_queue.get().tee()
        while True:
            match await mouse_event_queue.get():
                case MouseMoved(position=p):
                    set_pos(p)

            mouse_event_queue.task_done()

    use_effect(setup=setup, deps=())

    return pos
