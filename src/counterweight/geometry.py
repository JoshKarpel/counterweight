from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from itertools import product

import waxy

from counterweight._utils import flyweight, unordered_range


@flyweight(maxsize=2**14)
@dataclass(frozen=True, slots=True, order=True)
class Position:
    x: int
    y: int

    @classmethod
    def from_point(cls, point: waxy.Point) -> Position:
        return cls(int(point.x), int(point.y))

    def __add__(self, other: Position) -> Position:
        return Position(x=self.x + other.x, y=self.y + other.y)

    def __sub__(self, other: Position) -> Position:
        return Position(x=self.x - other.x, y=self.y - other.y)

    def fill_to(self, other: Position) -> Iterator[Position]:
        return (
            Position(x=x, y=y)
            for x, y in product(
                unordered_range(self.x, other.x),
                unordered_range(self.y, other.y),
            )
        )
