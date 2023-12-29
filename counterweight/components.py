from __future__ import annotations

from functools import wraps
from typing import Callable, ParamSpec

from counterweight.elements import AnyElement
from counterweight.types import FrozenForbidExtras

P = ParamSpec("P")

Key = str | int | None


def component(func: Callable[P, AnyElement]) -> Callable[P, Component]:
    """
    A decorator that marks a function as a component.
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Component:
        return Component(func=func, args=args, kwargs=kwargs)

    return wrapper


class Component(FrozenForbidExtras):
    """
    The result of calling a component function.
    These should not be instantiated directly;
    instead, use the `@component` decorator on a function
    and call it normally.
    """

    func: Callable[..., AnyElement]
    args: tuple[object, ...]
    kwargs: dict[str, object]
    key: Key = None

    def with_key(self, key: Key) -> Component:
        return self.model_copy(update={"key": key})


Component.model_rebuild()
