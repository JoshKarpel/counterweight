from __future__ import annotations

from collections.abc import Awaitable
from typing import Callable, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")

Getter = Callable[[], T]
Setter = Callable[[Callable[[T], T] | T], None]
Setup = Callable[[], Awaitable[None]]
Deps = tuple[object, ...] | None


class Ref(BaseModel, Generic[T]):
    current: T
