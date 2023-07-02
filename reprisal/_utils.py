from __future__ import annotations

from asyncio import Queue, QueueEmpty
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
