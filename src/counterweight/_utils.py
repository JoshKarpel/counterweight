from __future__ import annotations

from asyncio import CancelledError, Queue, QueueEmpty, Task, current_task, get_event_loop
from functools import lru_cache
from inspect import isawaitable
from math import ceil, floor
from typing import Awaitable, Callable


async def drain_queue[T](queue: Queue[T]) -> list[T]:
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


async def maybe_await[R](val: Awaitable[R] | R) -> R:
    if isawaitable(val):
        return await val
    else:
        return val


async def forever() -> None:
    await get_event_loop().create_future()  # This waits forever since the future will never resolve on its own


async def cancel[T](task: Task[T]) -> None:
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


def flyweight[T](maxsize: int = 2**10) -> Callable[[type[T]], type[T]]:
    """
    Class decorator that interns instances of a frozen dataclass by value,
    so constructing equal values returns the same object while it stays cached.
    Painting relies on this to compare cells by identity before falling back to equality.

    The decorator returns a slotless subclass whose metaclass caches `__call__` on the raw call arguments,
    so repeating a call is one cache hit in C that skips `__new__`, `__init__` and `__post_init__`.
    On a miss, the instance is built normally (so bad arguments raise as usual),
    then interned by its own equality and hash, so `C(1, 2)`, `C(1, y=2)` and `C(x=1, y=2)`
    share one instance even though each spelling has its own entry in the first cache.
    """

    def decorator(cls: type[T]) -> type[T]:
        if cls.__hash__ is None:
            raise TypeError(
                f"@flyweight needs hashable instances, but {cls.__qualname__} is unhashable (make it frozen)"
            )

        construct: Callable[..., T] = type(cls).__call__

        @lru_cache(maxsize=maxsize)
        def canonical(instance: T) -> T:
            return instance

        def by_arguments(klass: type[T], *args: object, **kwargs: object) -> T:
            return canonical(construct(klass, *args, **kwargs))

        metaclass = type(
            f"Flyweight{cls.__name__}Meta", (type(cls),), {"__call__": lru_cache(maxsize=maxsize)(by_arguments)}
        )
        interned: type[T] = metaclass(
            cls.__name__,
            (cls,),
            {"__slots__": (), "__module__": cls.__module__, "__qualname__": cls.__qualname__, "__doc__": cls.__doc__},
        )
        return interned

    return decorator


def unordered_range(a: int, b: int) -> range:
    """
    A range from a to b (inclusive), regardless of the order of a and b.

    https://stackoverflow.com/a/38036694
    """
    step = -1 if b < a else 1
    return range(a, b + step, step)
