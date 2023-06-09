from __future__ import annotations

from typing import Callable, ParamSpec, TypeVar

T = TypeVar("T")
A = TypeVar("A")
P = ParamSpec("P")

Setter = Callable[[T], None]
