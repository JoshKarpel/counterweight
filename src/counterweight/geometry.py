from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from itertools import product
from typing import TYPE_CHECKING, NamedTuple

from counterweight._utils import unordered_range

if TYPE_CHECKING:
    import waxy


class Position(NamedTuple):
    x: int
    y: int

    @classmethod
    @lru_cache(maxsize=2**14)
    def flyweight(cls, x: int, y: int) -> Position:
        return cls(x, y)

    @classmethod
    def from_point(cls, point: waxy.Point) -> Position:
        return cls.flyweight(int(point.x), int(point.y))

    def __add__(self, other: Position) -> Position:  # type: ignore[override]
        return Position.flyweight(x=self.x + other.x, y=self.y + other.y)

    def __sub__(self, other: Position) -> Position:
        return Position.flyweight(x=self.x - other.x, y=self.y - other.y)

    def fill_to(self, other: Position) -> Iterator[Position]:
        return (
            Position.flyweight(x=x, y=y)
            for x, y in product(
                unordered_range(self.x, other.x),
                unordered_range(self.y, other.y),
            )
        )
