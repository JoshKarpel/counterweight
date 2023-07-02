from __future__ import annotations

from typing import Callable, Coroutine, Generic, TypeVar

from pydantic.generics import GenericModel

T = TypeVar("T")

Getter = Callable[[], T]
Setter = Callable[[T], None]
Setup = Callable[[], Coroutine[None, None, None]]
Deps = tuple[object, ...] | None


class Ref(GenericModel, Generic[T]):
    current: T
