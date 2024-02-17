from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import lru_cache
from itertools import product
from typing import NamedTuple

from counterweight._utils import unordered_range


class Position(NamedTuple):
    x: int
    y: int

    @classmethod
    @lru_cache(maxsize=2**14)
    def flyweight(cls, x: int, y: int) -> Position:
        return cls(x, y)

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


@dataclass(slots=True)
class Rect:
    x: int = field(default=0)
    y: int = field(default=0)
    width: int = field(default=0)
    height: int = field(default=0)

    def expand_by(self, edge: Edge) -> Rect:
        return Rect(
            x=self.x - edge.left,
            y=self.y - edge.top,
            width=self.width + edge.left + edge.right,
            height=self.height + edge.top + edge.bottom,
        )

    def x_range(self) -> range:
        return range(self.x, self.x + self.width)

    def y_range(self) -> range:
        return range(self.y, self.y + self.height)

    def xy_range(self) -> Iterator[tuple[int, int]]:
        return product(self.x_range(), self.y_range())

    @property
    def left(self) -> int:
        return self.x

    @property
    def right(self) -> int:
        return self.x + self.width - 1

    @property
    def top(self) -> int:
        return self.y

    @property
    def bottom(self) -> int:
        return self.y + self.height - 1

    def left_edge(self) -> tuple[Position, ...]:
        left = self.left
        return tuple(Position.flyweight(left, y) for y in self.y_range())

    def right_edge(self) -> tuple[Position, ...]:
        right = self.right
        return tuple(Position.flyweight(right, y) for y in self.y_range())

    def top_edge(self) -> tuple[Position, ...]:
        top = self.top
        return tuple(Position.flyweight(x, top) for x in self.x_range())

    def bottom_edge(self) -> tuple[Position, ...]:
        bottom = self.bottom
        return tuple(Position.flyweight(x, bottom) for x in self.x_range())

    def top_left(self) -> Position:
        return Position.flyweight(x=self.left, y=self.top)

    def __contains__(self, item: object) -> bool:
        if isinstance(item, Position):
            return item.x in self.x_range() and item.y in self.y_range()
        else:
            return False


@dataclass(slots=True)
class Edge:
    left: int = field(default=0)
    right: int = field(default=0)
    top: int = field(default=0)
    bottom: int = field(default=0)
