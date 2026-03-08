from __future__ import annotations

from functools import lru_cache

from more_itertools import grouper

from counterweight.elements import NEWLINE, Chunk
from counterweight.styles.styles import CellStyle, Color

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
) -> list[Chunk]:
    """
    Render a pixel grid as a list of Chunks using half-block characters (▀).

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
    return chunks


__all__ = ["canvas", "clamp"]
