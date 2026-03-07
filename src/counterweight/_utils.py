from __future__ import annotations

from asyncio import CancelledError, Queue, QueueEmpty, Task, current_task, get_event_loop
from functools import lru_cache
from inspect import isawaitable
from math import ceil, floor
from typing import Awaitable, List, TypeVar

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


R = TypeVar("R")


async def maybe_await(val: Awaitable[R] | R) -> R:
    if isawaitable(val):
        return await val
    else:
        return val


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


def clamp[C: (int, float)](min_: C, val: C, max_: C) -> C:
    return max(min_, min(val, max_))


def unordered_range(a: int, b: int) -> range:
    """
    A range from a to b (inclusive), regardless of the order of a and b.

    https://stackoverflow.com/a/38036694
    """
    step = -1 if b < a else 1
    return range(a, b + step, step)
