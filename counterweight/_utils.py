from __future__ import annotations

from asyncio import Queue, QueueEmpty, get_event_loop
from collections.abc import Iterator
from functools import lru_cache
from inspect import isawaitable
from math import ceil, floor
from typing import Awaitable, List, NoReturn, TypeVar, cast

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


async def drain_queue(queue: Queue[T]) -> List[T]:
    items = [await queue.get()]
    queue.task_done()

    while True:
        try:
            items.append(queue.get_nowait())
            queue.task_done()
        except QueueEmpty:
            break

    return items


@lru_cache(maxsize=2**10)
def halve_integer(x: int) -> tuple[int, int]:
    """Halve an integer, accounting for odd integers by making the first "half" larger by one than the second "half"."""
    half = x / 2
    return ceil(half), floor(half)


@lru_cache(maxsize=2**12)
def partition_int(total: int, weights: tuple[int, ...]) -> list[int]:
    """Partition an integer into a list of integers, with each integer in the list corresponding to the weight at the same index in the weights list."""
    # https://stackoverflow.com/questions/62914824/c-sharp-split-integer-in-parts-given-part-weights-algorithm

    if any(w < 0 for w in weights):
        raise ValueError("Weights must be non-negative")

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


R = TypeVar("R")


async def maybe_await(val: Awaitable[R] | R) -> R:
    if isawaitable(val):
        return await val
    else:
        return cast(R, val)  # mypy doesn't narrow the type when isawaitable() is False, so we have to cast


async def forever() -> NoReturn:
    await get_event_loop().create_future()  # This waits forever since the future will never resolve on its own


# TODO: test unordered_range
def unordered_range(a: int, b: int) -> Iterator[int]:
    """
    Iterate from a to b (inclusive), regardless of the order of a and b.

    https://stackoverflow.com/a/38036694
    """
    step = -1 if b < a else 1
    for x in range(a, b + step, step):
        yield x
