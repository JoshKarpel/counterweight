from __future__ import annotations

from collections.abc import Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable, Generic, ParamSpec, TypeVar

T = TypeVar("T")
A = TypeVar("A")
P = ParamSpec("P")

HookRoot = Callable[P, T]

current_hook_context: ContextVar[HookContext[Any, Any]] = ContextVar("current_context")


class HookContext(Generic[P, T]):
    def __init__(self, root: HookRoot[P, T]):
        self.root = root

        self.current_hook = 0
        self.state: dict[int, object] = {}

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T:
        current_hook_context.set(self)
        self.current_hook = 0
        return self.root(*args, **kwargs)


Setter = Callable[[T], None]


def use_state(initial_value: T) -> tuple[T, Setter[T]]:
    ctx = current_hook_context.get()

    value: T = ctx.state.setdefault(ctx.current_hook, initial_value)  # type: ignore[assignment]

    i = ctx.current_hook  # capture value now for setter closure

    def setter(value: T) -> None:
        ctx.state[i] = value

    ctx.current_hook += 1

    return value, setter


Reducer = Callable[[T, A], T]
Dispatch = Callable[[A], None]


def use_reducer(reducer: Callable[[T, A], T], initial_state: T) -> tuple[T, Dispatch[A]]:
    ctx = current_hook_context.get()

    reducer_: Reducer[T, A] = ctx.state.setdefault(ctx.current_hook, reducer)  # type: ignore[assignment]

    state_idx = ctx.current_hook + 1
    state: T = ctx.state.setdefault(state_idx, initial_state)  # type: ignore[assignment]

    def dispatch(action: A) -> None:
        ctx.state[state_idx] = reducer_(ctx.state[state_idx], action)  # type: ignore[arg-type]

    ctx.current_hook += 2

    return state, dispatch


@dataclass
class Ref(Generic[T]):
    current: T


def use_ref(initial_value: T) -> Ref[T]:
    ctx = current_hook_context.get()

    ref: Ref[T] = ctx.state.setdefault(ctx.current_hook, Ref(initial_value))  # type: ignore[assignment]

    ctx.current_hook += 1

    return ref


def use_effect(callback, deps: Sequence[object] | None = None) -> None:  # type: ignore[no-untyped-def]
    ctx = current_hook_context.get()

    previous_deps = ctx.state.get(ctx.current_hook, [])
    if deps is None:
        callback()
    elif deps != previous_deps:
        callback()
        ctx.state[ctx.current_hook] = list(deps)

    ctx.current_hook += 1
