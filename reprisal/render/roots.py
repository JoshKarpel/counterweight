from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from typing import Any, Generic

from structlog import get_logger

from reprisal.constants import PACKAGE_NAME
from reprisal.render.types import (
    A,
    Callback,
    Deps,
    H,
    P,
    R,
    Reducer,
    Ref,
    UseReducerReturn,
    UseRefReturn,
    UseStateReturn,
)

CURRENT_ROOT: ContextVar[Root[Any, Any]] = ContextVar(f"{PACKAGE_NAME}-current-root")

logger = get_logger()


class Root(Generic[P, R]):
    def __init__(self, func: Callable[P, R]):
        self.func = func

        self.current_hook_idx = 0
        self.hook_state: dict[int, object] = {}

        self.needs_render = True

    def render(self, *args: P.args, **kwargs: P.kwargs) -> R:
        token = CURRENT_ROOT.set(self)
        self.current_hook_idx = 0

        result = self.func(*args, **kwargs)

        self.current_hook_idx = 0
        CURRENT_ROOT.reset(token)

        self.needs_render = False

        return result

    def use_state(self, initial_value: H | Callable[[], H]) -> UseStateReturn[H]:
        if self.current_hook_idx not in self.hook_state:
            self.hook_state[self.current_hook_idx] = initial_value() if callable(initial_value) else initial_value

        value: H = self.hook_state[self.current_hook_idx]  # type: ignore[assignment]

        hook_idx = self.current_hook_idx  # capture value now for setter closure

        def setter(value: H) -> None:
            self.hook_state[hook_idx] = value
            self.needs_render = True

        self.current_hook_idx += 1

        return value, setter

    def use_reducer(self, reducer: Reducer[H, A], initial_state: H) -> UseReducerReturn[H, A]:
        reducer_: Reducer[H, A] = self.hook_state.setdefault(self.current_hook_idx, reducer)  # type: ignore[assignment]

        state_idx = self.current_hook_idx + 1
        state: H = self.hook_state.setdefault(state_idx, initial_state)  # type: ignore[assignment]

        def dispatch(action: A) -> None:
            self.hook_state[state_idx] = reducer_(self.hook_state[state_idx], action)  # type: ignore[arg-type]

        self.current_hook_idx += 2

        return state, dispatch

    def use_ref(self, initial_value: H) -> UseRefReturn[H]:
        ref: Ref[H] = self.hook_state.setdefault(self.current_hook_idx, Ref(initial_value))  # type: ignore[assignment]

        self.current_hook_idx += 1

        return ref

    def use_effect(self, callback: Callback, deps: Deps = None) -> None:
        previous_deps = self.hook_state.get(self.current_hook_idx, ())
        if deps is None:
            callback()
        elif deps != previous_deps:
            callback()
            self.hook_state[self.current_hook_idx] = deps

        self.current_hook_idx += 1
