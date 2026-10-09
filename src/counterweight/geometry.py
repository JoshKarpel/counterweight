from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from itertools import product

from counterweight._utils import flyweight, unordered_range


@flyweight(maxsize=2**14)
@dataclass(frozen=True, slots=True, order=True)
class Position:
    x: int
    y: int

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


@dataclass(frozen=True, slots=True, kw_only=True)
class Region:
    """
    A rectangular area of terminal cells.

    The edges are half-open: `left` and `top` are the first column and row inside the region,
    while `right` and `bottom` are the first column and row *outside* it.
    So `width` and `height` count cells, and a region with zero (or negative) width or height is empty.
    """

    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def is_empty(self) -> bool:
        return self.width <= 0 or self.height <= 0

    @property
    def top_left(self) -> Position:
        """The top-left cell of the region."""
        return Position(x=self.left, y=self.top)

    @property
    def top_right(self) -> Position:
        """The top-right cell of the region."""
        return Position(x=self.right - 1, y=self.top)

    @property
    def bottom_left(self) -> Position:
        """The bottom-left cell of the region."""
        return Position(x=self.left, y=self.bottom - 1)

    @property
    def bottom_right(self) -> Position:
        """The bottom-right cell of the region."""
        return Position(x=self.right - 1, y=self.bottom - 1)

    def contains(self, position: Position) -> bool:
        return self.left <= position.x < self.right and self.top <= position.y < self.bottom

    def positions(self) -> Iterator[Position]:
        """Every cell in the region, row by row."""
        return (Position(x=x, y=y) for y in range(self.top, self.bottom) for x in range(self.left, self.right))

    def top_edge(self) -> Iterator[Position]:
        """The cells along the top row of the region, left to right."""
        if self.is_empty:
            return iter(())
        return (Position(x=x, y=self.top) for x in range(self.left, self.right))

    def bottom_edge(self) -> Iterator[Position]:
        """The cells along the bottom row of the region, left to right."""
        if self.is_empty:
            return iter(())
        return (Position(x=x, y=self.bottom - 1) for x in range(self.left, self.right))

    def left_edge(self) -> Iterator[Position]:
        """The cells along the left column of the region, top to bottom."""
        if self.is_empty:
            return iter(())
        return (Position(x=self.left, y=y) for y in range(self.top, self.bottom))

    def right_edge(self) -> Iterator[Position]:
        """The cells along the right column of the region, top to bottom."""
        if self.is_empty:
            return iter(())
        return (Position(x=self.right - 1, y=y) for y in range(self.top, self.bottom))

    def intersection(self, other: Region) -> Region | None:
        """The cells shared by both regions, or `None` if they share no cells."""
        overlap = Region(
            left=max(self.left, other.left),
            top=max(self.top, other.top),
            right=min(self.right, other.right),
            bottom=min(self.bottom, other.bottom),
        )
        return None if overlap.is_empty else overlap
