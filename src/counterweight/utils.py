from __future__ import annotations

from functools import lru_cache

from more_itertools import grouper

from counterweight.elements import Chunk
from counterweight.styles.styles import CellStyle, Color

_BLACK = Color(0, 0, 0)


def clamp[C: (int, float)](min_: C, val: C, max_: C) -> C:
    return max(min_, min(val, max_))


@lru_cache(maxsize=64)
def _canvas_coords(width: int, height: int) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    coords: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for y_top, y_bot in grouper(range(height), 2):
        for x in range(width):
            coords.append(((x, y_top), (x, y_bot)))
    return coords


def canvas(
    width: int,
    height: int,
    cells: dict[tuple[int, int], Color],
    default: Color = _BLACK,
) -> list[Chunk]:
    coords = _canvas_coords(width, height)
    chunks: list[Chunk] = []
    for i, (top, bot) in enumerate(coords):
        if i > 0 and i % width == 0:
            chunks.append(Chunk.newline())
        chunks.append(
            Chunk(
                content="▀",
                style=CellStyle(
                    foreground=cells.get(top, default),
                    background=cells.get(bot, default),
                ),
            )
        )
    return chunks


__all__ = ["canvas", "clamp"]
