from __future__ import annotations

from asyncio import Queue, QueueEmpty, Task, get_event_loop, wait
from collections.abc import Iterable
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


async def cancel_tasks(tasks: Iterable[Task[object]]) -> None:
    """
    Cancel every task, then wait until all of them have finished tearing down.

    The tasks tear down concurrently, so the wait lasts as long as the slowest teardown, not their sum.
    A task that is already done is skipped (for example, an effect that aborted itself by returning).
    Every task that raises during teardown, or swallows its cancellation and returns (reported as `RuntimeError`),
    contributes to a single `BaseExceptionGroup` raised once all of them have finished.
    If the caller is cancelled while waiting, its `CancelledError` propagates and the tasks keep tearing down.
    """
    pending = [task for task in tasks if not task.done()]
    if not pending:
        return

    for task in pending:
        task.cancel()

    # `wait` never raises the tasks' own `CancelledError`, so any `CancelledError` out of it is aimed at the caller.
    # Awaiting each task under `suppress(CancelledError)` instead would swallow the caller's cancellation too.
    await wait(pending)

    exceptions = [teardown_failure(task) for task in pending if not task.cancelled()]
    if exceptions:
        raise BaseExceptionGroup("Tasks failed while being cancelled", exceptions)


def teardown_failure(task: Task[object]) -> BaseException:
    """The exception a cancelled task ended with, or a `RuntimeError` if it swallowed its cancellation and returned."""
    return task.exception() or RuntimeError("Cancelled task did not end with an exception")


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
