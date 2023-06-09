from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, ParamSpec, TypeVar

T = TypeVar("T")
A = TypeVar("A")
P = ParamSpec("P")

Setter = Callable[[T], None]
Reducer = Callable[[T, A], T]
Dispatch = Callable[[A], None]
Callback = Callable[[], None]
Deps = tuple[object, ...] | None


@dataclass
class Ref(Generic[T]):
    current: T


UseStateReturn = tuple[T, Setter[T]]
UseReducerReturn = tuple[T, Dispatch[A]]
UseRefReturn = Ref[T]
