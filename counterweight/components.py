from __future__ import annotations

from dataclasses import dataclass, replace
from functools import wraps
from typing import Callable, ParamSpec

from counterweight.elements import AnyElement

P = ParamSpec("P")


def component(func: Callable[P, AnyElement]) -> Callable[P, Component]:
    """
    A decorator that marks a function as a component.
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Component:
        return Component(func=func, args=args, kwargs=kwargs)

    return wrapper


@dataclass(frozen=True, slots=True)
class Component:
    """
    The result of calling a component function.
    These should not be instantiated directly;
    instead, use the `@component` decorator on a function
    and call it normally.
    """

    func: Callable[..., AnyElement]
    args: tuple[object, ...]
    kwargs: dict[str, object]
    key: str | int | None = None

    def with_key(self, key: str | int | None) -> Component:
        return replace(self, key=key)
