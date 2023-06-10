from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, ParamSpec, TypeVar

R = TypeVar("R")
H = TypeVar("H")
A = TypeVar("A")
P = ParamSpec("P")

Setter = Callable[[H], None]
Reducer = Callable[[H, A], H]
Dispatch = Callable[[A], None]
Callback = Callable[[], None]
Deps = tuple[object, ...] | None


@dataclass
class Ref(Generic[H]):
    current: H


UseStateReturn = tuple[H, Setter[H]]
UseReducerReturn = tuple[H, Dispatch[A]]
UseRefReturn = Ref[H]
