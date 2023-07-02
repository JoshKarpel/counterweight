from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Coroutine, Generic, TypeVar

T = TypeVar("T")

Getter = Callable[[], T]
Setter = Callable[[T], None]
Setup = Callable[[], Coroutine[None, None, None]]
Deps = tuple[object, ...] | None


@dataclass(slots=True)
class Ref(Generic[T]):
    current: T
