from __future__ import annotations

from typing import NamedTuple

from pydantic import Field, NonNegativeInt

from counterweight.types import ForbidExtras


class Position(NamedTuple):
    x: int
    y: int


class Rect(ForbidExtras):
    x: int = Field(default=0)
    y: int = Field(default=0)
    width: NonNegativeInt = Field(default=0)
    height: NonNegativeInt = Field(default=0)

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

    def left_edge(self) -> list[Position]:
        left = self.left
        return [Position(left, y) for y in self.y_range()]

    def right_edge(self) -> list[Position]:
        right = self.right
        return [Position(right, y) for y in self.y_range()]

    def top_edge(self) -> list[Position]:
        top = self.top
        return [Position(x, top) for x in self.x_range()]

    def bottom_edge(self) -> list[Position]:
        bottom = self.bottom
        return [Position(x, bottom) for x in self.x_range()]

    def __contains__(self, item: object) -> bool:
        if isinstance(item, Position):
            return item.x in self.x_range() and item.y in self.y_range()
        else:
            return False


class Edge(ForbidExtras):
    left: int = Field(default=0)
    right: int = Field(default=0)
    top: int = Field(default=0)
    bottom: int = Field(default=0)
