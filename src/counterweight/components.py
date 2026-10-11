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
    key: str | None = None

    def with_key(self, key: str | None) -> Component:
        """
        Returns a copy of this component with the given `key`.
        Across renders, a keyed component continues the sibling that had the same key last render,
        wherever it sat, so reordering keyed siblings moves their state and effects with them.
        An unkeyed component instead continues the unkeyed sibling at the same index.
        Changing a component's key remounts it with fresh state,
        and adding or removing a key counts as changing it.
        Sibling components MUST NOT share a key other than `None`; reconciling them raises `DuplicateKey`.
        """
        return replace(self, key=key)
