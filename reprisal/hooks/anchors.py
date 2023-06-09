from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Callable, Generic

from reprisal.constants import PACKAGE_NAME
from reprisal.hooks.types import P, T

CURRENT_ANCHOR: ContextVar[Anchor[Any, Any]] = ContextVar(f"{PACKAGE_NAME}-current-anchor")


class Anchor(Generic[P, T]):
    def __init__(self, func: Callable[P, T]):
        self.func = func

        self.current_hook = 0
        self.hook_state: dict[int, object] = {}

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T:
        token = CURRENT_ANCHOR.set(self)
        self.current_hook = 0

        rv = self.func(*args, **kwargs)

        self.current_hook = 0
        CURRENT_ANCHOR.reset(token)

        return rv
