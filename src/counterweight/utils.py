from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache

from more_itertools import grouper

from counterweight.elements import NEWLINE, Chunk, Rows
from counterweight.paint import Cell
from counterweight.styles.styles import CELL_STYLE_DEFAULTS, CellStyle, Color

_BLACK = Color.from_name("black")


def clamp[C: (int, float)](min_: C, val: C, max_: C) -> C:
    return max(min_, min(val, max_))


@lru_cache(maxsize=64)
def _canvas_rows(width: int, height: int) -> list[list[tuple[tuple[int, int], tuple[int, int]]]]:
    return [[((x, y_top), (x, y_bot)) for x in range(width)] for y_top, y_bot in grouper(range(height), 2)]


@lru_cache(maxsize=2**10)
def _canvas_chunk(fg: Color, bg: Color) -> Chunk:
    return Chunk(content="▀", style=CellStyle(foreground=fg, background=bg))


def canvas(
    width: int,
    height: int,
    cells: dict[tuple[int, int], Color],
    default: Color = _BLACK,
) -> tuple[Chunk, ...]:
    """
    Render a pixel grid as a tuple of Chunks using half-block characters (▀).

    Each character cell represents two vertically-stacked pixels: the upper pixel maps to
    the foreground color and the lower pixel maps to the background color. This doubles the
    effective vertical resolution of a terminal canvas.

    `width` and `height` are in pixels; `height` must be even. `cells` is a sparse mapping
    of `(x, y)` pixel coordinates to colors — unmapped pixels use `default` (black).
    The returned chunks are suitable for use as the `content` of a `Text` element.
    """
    if height % 2 != 0:
        raise ValueError(f"canvas height must be even, got {height}")
    rows = _canvas_rows(width, height)
    chunks: list[Chunk] = []
    for i, row in enumerate(rows):
        if i > 0:
            chunks.append(NEWLINE)
        for top, bot in row:
            chunks.append(_canvas_chunk(cells.get(top, default), cells.get(bot, default)))
    return tuple(chunks)


@lru_cache(maxsize=2**12)
def _half_block(top: Color, bottom: Color) -> Cell:
    return Cell("▀", replace(CELL_STYLE_DEFAULTS, foreground=top, background=bottom))


@dataclass(frozen=True, slots=True)
class HalfBlocks:
    """
    A `Canvas` painter for a pixel grid drawn with half blocks (▀), two pixels to a cell, as `canvas` draws it.

    `pixels` pairs `(x, y)` positions with colors (a later pair wins over an earlier one at the same position),
    and every other pixel of the `width` by `height` grid is `default`.
    It's a tuple rather than a dict so the painter is hashable, which caches what it draws.
    """

    width: int
    height: int
    pixels: tuple[tuple[tuple[int, int], Color], ...]
    default: Color = _BLACK

    @property
    def cells(self) -> tuple[int, int]:
        """The canvas's intrinsic size, in cells."""
        return self.width, (self.height + 1) // 2

    def __call__(self, width: int, height: int) -> Rows:
        colors = dict(self.pixels)
        default = self.default
        get = colors.get
        return tuple(
            tuple(
                _half_block(get((x, top), default), get((x, top + 1), default)) for x in range(min(width, self.width))
            )
            for top in range(0, min(height * 2, self.height), 2)
        )


__all__ = ["HalfBlocks", "canvas", "clamp"]
