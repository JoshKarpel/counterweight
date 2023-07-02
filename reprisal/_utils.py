from __future__ import annotations

from asyncio import Queue, QueueEmpty
from math import ceil, floor
from typing import List, TypeVar

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


def diff(a: dict[K, V], b: dict[K, V]) -> dict[K, V]:
    d = {}
    for key, val in a.items():
        if val != b.get(key):
            d[key] = val
    return d


async def drain_queue(queue: Queue[T]) -> List[T]:
    items = [await queue.get()]

    while True:
        try:
            items.append(queue.get_nowait())
        except QueueEmpty:
            break

    return items


def halve_integer(x: int) -> tuple[int, int]:
    """Halve an integer, accounting for odd integers by making the second "half" larger by one than the first "half"."""
    half = x / 2
    return floor(half), ceil(half)
