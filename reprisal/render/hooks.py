from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable

from reprisal.render.roots import CURRENT_ROOT
from reprisal.render.types import (
    A,
    Callback,
    Deps,
    H,
    Reducer,
    UseReducerReturn,
    UseRefReturn,
    UseStateReturn,
)


def use_state(initial_value: H | Callable[[], H]) -> UseStateReturn[H]:
    return CURRENT_ROOT.get().use_state(initial_value=initial_value)


def use_reducer(reducer: Reducer[H, A], initial_state: H) -> UseReducerReturn[H, A]:
    return CURRENT_ROOT.get().use_reducer(reducer=reducer, initial_state=initial_state)


def use_ref(initial_value: H) -> UseRefReturn[H]:
    return CURRENT_ROOT.get().use_ref(initial_value=initial_value)


def use_effect(callback: Callback, deps: Deps = None) -> None:
    return CURRENT_ROOT.get().use_effect(callback=callback, deps=deps)


def use_context(context: ContextVar[H]) -> H:
    return context.get()


@contextmanager
def provide_context(context: ContextVar[H], value: H) -> Iterator[None]:
    token = context.set(value)

    yield

    context.reset(token)
