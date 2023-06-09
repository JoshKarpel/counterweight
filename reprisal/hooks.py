from __future__ import annotations

from collections.abc import Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable, Generic, ParamSpec, TypeVar

T = TypeVar("T")
A = TypeVar("A")
P = ParamSpec("P")

HookRoot = Callable[P, T]

CURRENT_ANCHOR: ContextVar[Anchor[Any, Any]] = ContextVar("current_context")


class Anchor(Generic[P, T]):
    def __init__(self, root: HookRoot[P, T]):
        self.root = root

        self.current_hook = 0
        self.hook_state: dict[int, object] = {}

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T:
        CURRENT_ANCHOR.set(self)
        self.current_hook = 0
        return self.root(*args, **kwargs)


Setter = Callable[[T], None]


def use_state(initial_value: T) -> tuple[T, Setter[T]]:
    anchor = CURRENT_ANCHOR.get()

    value: T = anchor.hook_state.setdefault(anchor.current_hook, initial_value)  # type: ignore[assignment]

    i = anchor.current_hook  # capture value now for setter closure

    def setter(value: T) -> None:
        anchor.hook_state[i] = value

    anchor.current_hook += 1

    return value, setter


Reducer = Callable[[T, A], T]
Dispatch = Callable[[A], None]


def use_reducer(reducer: Callable[[T, A], T], initial_state: T) -> tuple[T, Dispatch[A]]:
    anchor = CURRENT_ANCHOR.get()

    reducer_: Reducer[T, A] = anchor.hook_state.setdefault(anchor.current_hook, reducer)  # type: ignore[assignment]

    state_idx = anchor.current_hook + 1
    state: T = anchor.hook_state.setdefault(state_idx, initial_state)  # type: ignore[assignment]

    def dispatch(action: A) -> None:
        anchor.hook_state[state_idx] = reducer_(anchor.hook_state[state_idx], action)  # type: ignore[arg-type]

    anchor.current_hook += 2

    return state, dispatch


@dataclass
class Ref(Generic[T]):
    current: T


def use_ref(initial_value: T) -> Ref[T]:
    anchor = CURRENT_ANCHOR.get()

    ref: Ref[T] = anchor.hook_state.setdefault(anchor.current_hook, Ref(initial_value))  # type: ignore[assignment]

    anchor.current_hook += 1

    return ref


def use_effect(callback, deps: Sequence[object] | None = None) -> None:  # type: ignore[no-untyped-def]
    anchor = CURRENT_ANCHOR.get()

    previous_deps = anchor.hook_state.get(anchor.current_hook, [])
    if deps is None:
        callback()
    elif deps != previous_deps:
        callback()
        anchor.hook_state[anchor.current_hook] = list(deps)

    anchor.current_hook += 1
