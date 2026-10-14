from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from itertools import product

from counterweight._utils import unordered_range


@dataclass(frozen=True, slots=True, order=True)
class Position:
    x: int
    y: int

    def __add__(self, other: Position) -> Position:
        return Position(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Position) -> Position:
        return Position(self.x - other.x, self.y - other.y)

    def fill_to(self, other: Position) -> Iterator[Position]:
        return (
            Position(x, y)
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
    _hash: int = field(init=False, repr=False, compare=False, hash=False, default=0)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_hash", hash((self.left, self.top, self.right, self.bottom)))

    def __hash__(self) -> int:
        return self._hash

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
        return Position(self.left, self.top)

    @property
    def top_right(self) -> Position:
        """The top-right cell of the region."""
        return Position(self.right - 1, self.top)

    @property
    def bottom_left(self) -> Position:
        """The bottom-left cell of the region."""
        return Position(self.left, self.bottom - 1)

    @property
    def bottom_right(self) -> Position:
        """The bottom-right cell of the region."""
        return Position(self.right - 1, self.bottom - 1)

    def contains(self, position: Position) -> bool:
        return self.left <= position.x < self.right and self.top <= position.y < self.bottom

    def positions(self) -> Iterator[Position]:
        """Every cell in the region, row by row."""
        return (Position(x, y) for y in range(self.top, self.bottom) for x in range(self.left, self.right))

    def top_edge(self) -> Iterator[Position]:
        """The cells along the top row of the region, left to right."""
        if self.is_empty:
            return iter(())
        return (Position(x, self.top) for x in range(self.left, self.right))

    def bottom_edge(self) -> Iterator[Position]:
        """The cells along the bottom row of the region, left to right."""
        if self.is_empty:
            return iter(())
        return (Position(x, self.bottom - 1) for x in range(self.left, self.right))

    def left_edge(self) -> Iterator[Position]:
        """The cells along the left column of the region, top to bottom."""
        if self.is_empty:
            return iter(())
        return (Position(self.left, y) for y in range(self.top, self.bottom))

    def right_edge(self) -> Iterator[Position]:
        """The cells along the right column of the region, top to bottom."""
        if self.is_empty:
            return iter(())
        return (Position(self.right - 1, y) for y in range(self.top, self.bottom))

    def intersection(self, other: Region) -> Region | None:
        """
        The cells shared by both regions, or `None` if they share no cells.
        It's this region itself when `other` contains all of it, so callers can tell by identity.
        """
        if (
            other.left <= self.left
            and other.top <= self.top
            and self.right <= other.right
            and self.bottom <= other.bottom
        ):
            return None if self.is_empty else self
        overlap = Region(
            left=max(self.left, other.left),
            top=max(self.top, other.top),
            right=min(self.right, other.right),
            bottom=min(self.bottom, other.bottom),
        )
        return None if overlap.is_empty else overlap


@dataclass(frozen=True, slots=True, kw_only=True)
class Rects:
    """
    Where an element is on the screen: the regions its box model occupies, from its content box out to its margin box,
    and how much of it its ancestors' clips leave visible.

    The boxes are whole, never cut down by the clip,
    so `content` is always the region text wraps to, even when part of it is clipped away.
    """

    content: Region
    padding: Region
    border: Region
    margin: Region

    clip: Region | None
    """
    The region the element's ancestors let it draw in: its parent's clip (the screen, for the root),
    cut down on each axis where the parent's overflow is `Hidden`, `Clip` or `Scroll`
    to the parent's padding box, or its border box when the element's `clip_to` is `"border"`.
    It's the screen when the element's `clip_to` is `"screen"`, whatever its ancestors clip.
    It's `None` when nothing is left, so the element draws nothing.
    """
    visible: Region | None
    """The part of the border box inside `clip`, or `None` when none of it is."""


ORIGIN = Position(0, 0)


@dataclass(frozen=True, slots=True, kw_only=True)
class Scroll:
    """How far a scroll container's content is scrolled, and how far it can be."""

    offset: Position
    """
    How far the content is scrolled from where layout put it: `x` columns left and `y` rows up,
    so `Position(0, 0)` shows the start of the content, as the web's `scrollLeft` and `scrollTop` do.
    """
    max_offset: Position
    """
    The largest `offset` on each axis, which shows the end of the content,
    as the web's `scrollWidth` minus `clientWidth` does.
    It's 0 on an axis the container doesn't scroll, and on one whose content fits.
    """
    view_width: int
    """The width of the container's padding box, the part of the content in view, as the web's `clientWidth`."""
    view_height: int
    """The height of the container's padding box, the part of the content in view, as the web's `clientHeight`."""

    def clamp(self, offset: Position) -> Position:
        """`offset`, moved onto the range the content scrolls through on each axis, from 0 to `max_offset`."""
        return Position(
            max(0, min(offset.x, self.max_offset.x)),
            max(0, min(offset.y, self.max_offset.y)),
        )
