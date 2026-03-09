from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass

type Getter[T] = Callable[[], T]
type Setter[T] = Callable[[Callable[[T], T] | T], None]
type Setup = Callable[[], Coroutine[None, None, None]]
type Deps = tuple[object, ...] | None


@dataclass(slots=True)
class Ref[T]:
    current: T
