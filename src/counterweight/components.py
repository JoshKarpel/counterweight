from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from functools import wraps
from typing import overload

from counterweight.elements import AnyElement


@overload
def component[**P](func: Callable[P, AnyElement], /) -> Callable[P, Component]: ...


@overload
def component[**P](*, memo: bool = False) -> Callable[[Callable[P, AnyElement]], Callable[P, Component]]: ...


def component[**P](
    func: Callable[P, AnyElement] | None = None, /, *, memo: bool = False
) -> Callable[P, Component] | Callable[[Callable[P, AnyElement]], Callable[P, Component]]:
    """
    A decorator that marks a function as a component, used bare (`@component`) or with options.

    Parameters:
        memo: If `True`, a render that would re-run this component only because its parent re-ran
            reuses its previous output instead when its arguments equal last render's, as React's `memo` does.
            It still re-runs when its own state changes.
            Its output MUST depend only on its arguments and its hooks,
            or the output it keeps goes stale; `check_purity` on `counterweight.app.app` catches that in tests.
    """

    def decorate(func: Callable[P, AnyElement]) -> Callable[P, Component]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Component:
            return Component(func=func, args=args, kwargs=kwargs, memo=memo)

        return wrapper

    if func is None:
        return decorate

    return decorate(func)


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
    memo: bool = field(default=False, compare=False)
    """
    Whether the decorator that built this was given `memo=True`.
    It says how to reuse the component rather than what it renders, so it isn't compared:
    one function decorated both ways builds equal `Component`s, which continue each other's hooks.
    """

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


class DuplicateKey(Exception):
    """Raised when keyed sibling components share a key, which leaves no single previous child for each to continue."""


class ImpureComponent(Exception):
    """
    Raised when `check_purity` is on and re-running every component builds a different tree from the one a render built,
    so some component's output depends on something besides its arguments and hooks:
    the output a render kept for it is stale, or calling it twice doesn't give the same result.
    """
