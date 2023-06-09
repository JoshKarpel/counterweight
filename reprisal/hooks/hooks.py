from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from reprisal.hooks.anchors import CURRENT_ANCHOR
from reprisal.hooks.types import A, Dispatch, Ref, Setter, T


def use_state(initial_value: T) -> tuple[T, Setter[T]]:
    return CURRENT_ANCHOR.get().use_state(initial_value=initial_value)


def use_reducer(reducer: Callable[[T, A], T], initial_state: T) -> tuple[T, Dispatch[A]]:
    return CURRENT_ANCHOR.get().use_reducer(reducer=reducer, initial_state=initial_state)


def use_ref(initial_value: T) -> Ref[T]:
    return CURRENT_ANCHOR.get().use_ref(initial_value=initial_value)


def use_effect(callback: Callable[[], None], deps: tuple[object, ...] | None = None) -> None:
    return CURRENT_ANCHOR.get().use_effect(callback=callback, deps=deps)


def use_context(context: ContextVar[T]) -> T:
    return context.get()


@contextmanager
def provide_context(context: ContextVar[T], value: T) -> Iterator[None]:
    token = context.set(value)

    yield

    context.reset(token)
