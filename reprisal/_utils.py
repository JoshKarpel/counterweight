from __future__ import annotations

from asyncio import Queue, QueueEmpty
from functools import lru_cache
from math import ceil, floor
from typing import List, TypeVar

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")

UNSET = object()


def merge(a: dict[str, object], b: dict[str, object]) -> dict[str, object]:
    merged: dict[str, object] = {}

    for key in a.keys() | b.keys():
        a_val, b_val = a.get(key, UNSET), b.get(key, UNSET)

        if isinstance(a_val, dict) and isinstance(b_val, dict):
            merged[key] = merge(a_val, b_val)
        elif b_val is not UNSET:
            merged[key] = b_val
        elif a_val is not UNSET:
            merged[key] = a_val

    return merged


async def drain_queue(queue: Queue[T]) -> List[T]:
    items = [await queue.get()]

    while True:
        try:
            items.append(queue.get_nowait())
        except QueueEmpty:
            break

    return items


@lru_cache(maxsize=2**10)
def halve_integer(x: int) -> tuple[int, int]:
    """Halve an integer, accounting for odd integers by making the first "half" larger by one than the second "half"."""
    half = x / 2
    return ceil(half), floor(half)


@lru_cache(maxsize=2**12)
def partition_int(total: int, weights: tuple[int]) -> list[int]:
    """Partition an integer into a list of integers, with each integer in the list corresponding to the weight at the same index in the weights list."""
    # https://stackoverflow.com/questions/62914824/c-sharp-split-integer-in-parts-given-part-weights-algorithm

    if total == 0:  # optimization
        return [0] * len(weights)

    total_weight = sum(weights)

    if not total_weight > 0:
        raise ValueError("Total weight must be positive")

    partition = []
    accumulated_diff = 0.0
    for w in weights:
        exact = total * (w / total_weight)
        rounded = round(exact)
        accumulated_diff += exact - rounded

        if accumulated_diff > 0.5:
            rounded += 1
            accumulated_diff -= 1
        elif accumulated_diff < -0.5:
            rounded -= 1
            accumulated_diff += 1

        partition.append(rounded)

    return partition
