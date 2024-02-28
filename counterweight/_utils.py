from __future__ import annotations

from asyncio import CancelledError, Queue, QueueEmpty, Task, current_task, get_event_loop
from functools import lru_cache
from inspect import isawaitable
from math import ceil, floor
from typing import Awaitable, List, TypeVar, cast

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


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


async def forever() -> None:
    await get_event_loop().create_future()  # This waits forever since the future will never resolve on its own


async def cancel(task: Task[T]) -> None:
    # Based on https://discuss.python.org/t/asyncio-cancel-a-cancellation-utility-as-a-coroutine-this-time-with-feeling/26304/2
    if task.done():
        # If the task has already completed, there's nothing to cancel.
        # This can happen if, for example, an effect aborts itself by returning,
        # and then we try to cancel it when reconciling effects.
        return

    task.cancel()

    try:
        await task
    except CancelledError:
        ct = current_task()
        if ct and ct.cancelling() == 0:
            # The CancelledError is from the task we cancelled, so this is the normal flow
            return
        else:
            # cancel() is itself being cancelled, propagate the CancelledError
            raise
    else:
        raise RuntimeError("Cancelled task did not end with an exception")


def unordered_range(a: int, b: int) -> range:
    """
    A range from a to b (inclusive), regardless of the order of a and b.

    https://stackoverflow.com/a/38036694
    """
    step = -1 if b < a else 1
    return range(a, b + step, step)
