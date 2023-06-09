from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from reprisal.hooks.anchors import CURRENT_ANCHOR
from reprisal.hooks.types import (
    A,
    Callback,
    Deps,
    Reducer,
    T,
    UseReducerReturn,
    UseRefReturn,
    UseStateReturn,
)


def use_state(initial_value: T) -> UseStateReturn[T]:
    return CURRENT_ANCHOR.get().use_state(initial_value=initial_value)


def use_reducer(reducer: Reducer[T, A], initial_state: T) -> UseReducerReturn[T, A]:
    return CURRENT_ANCHOR.get().use_reducer(reducer=reducer, initial_state=initial_state)


def use_ref(initial_value: T) -> UseRefReturn[T]:
    return CURRENT_ANCHOR.get().use_ref(initial_value=initial_value)


def use_effect(callback: Callback, deps: Deps = None) -> None:
    return CURRENT_ANCHOR.get().use_effect(callback=callback, deps=deps)


def use_context(context: ContextVar[T]) -> T:
    return context.get()


@contextmanager
def provide_context(context: ContextVar[T], value: T) -> Iterator[None]:
    token = context.set(value)

    yield

    context.reset(token)
