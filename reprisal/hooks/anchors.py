from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from typing import Any, Generic

from reprisal.constants import PACKAGE_NAME
from reprisal.hooks.types import A, Dispatch, P, Reducer, Ref, Setter, T

CURRENT_ANCHOR: ContextVar[Anchor[Any, Any]] = ContextVar(f"{PACKAGE_NAME}-current-anchor")


class Anchor(Generic[P, T]):
    def __init__(self, func: Callable[P, T]):
        self.func = func

        self.current_hook_idx = 0
        self.hook_state: dict[int, object] = {}

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T:
        token = CURRENT_ANCHOR.set(self)
        self.current_hook_idx = 0

        rv = self.func(*args, **kwargs)

        self.current_hook_idx = 0
        CURRENT_ANCHOR.reset(token)

        return rv

    def use_state(self, initial_value: T) -> tuple[T, Setter[T]]:
        value: T = self.hook_state.setdefault(self.current_hook_idx, initial_value)  # type: ignore[assignment]

        hook_idx = self.current_hook_idx  # capture value now for setter closure

        def setter(value: T) -> None:
            self.hook_state[hook_idx] = value

        self.current_hook_idx += 1

        return value, setter

    def use_reducer(self, reducer: Callable[[T, A], T], initial_state: T) -> tuple[T, Dispatch[A]]:
        reducer_: Reducer[T, A] = self.hook_state.setdefault(self.current_hook_idx, reducer)  # type: ignore[assignment]

        state_idx = self.current_hook_idx + 1
        state: T = self.hook_state.setdefault(state_idx, initial_state)  # type: ignore[assignment]

        def dispatch(action: A) -> None:
            self.hook_state[state_idx] = reducer_(self.hook_state[state_idx], action)  # type: ignore[arg-type]

        self.current_hook_idx += 2

        return state, dispatch

    def use_ref(self, initial_value: T) -> Ref[T]:
        ref: Ref[T] = self.hook_state.setdefault(self.current_hook_idx, Ref(initial_value))  # type: ignore[assignment]

        self.current_hook_idx += 1

        return ref

    def use_effect(self, callback: Callable[[], None], deps: tuple[object, ...] | None = None) -> None:
        previous_deps = self.hook_state.get(self.current_hook_idx, ())
        if deps is None:
            callback()
        elif deps != previous_deps:
            callback()
            self.hook_state[self.current_hook_idx] = deps

        self.current_hook_idx += 1
