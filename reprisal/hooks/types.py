from __future__ import annotations

from typing import Callable, Coroutine, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")

Getter = Callable[[], T]
Setter = Callable[[Callable[[T], T] | T], None]
Setup = Callable[[], Coroutine[None, None, None]]
Deps = tuple[object, ...] | None


class Ref(BaseModel, Generic[T]):
    current: T
