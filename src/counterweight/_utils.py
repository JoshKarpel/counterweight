from __future__ import annotations

import dataclasses
from asyncio import CancelledError, Queue, QueueEmpty, Task, current_task, get_event_loop
from functools import lru_cache
from inspect import isawaitable
from math import ceil, floor
from typing import Any, Awaitable, Callable


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
    Class decorator that interns instances of a dataclass by their field values.
    Repeated construction with the same arguments returns the same object.
    """

    def decorator(cls: type[T]) -> type[T]:
        fields = dataclasses.fields(cls)  # type: ignore[arg-type]
        field_names = tuple(f.name for f in fields)
        field_defaults = {f.name: f.default for f in fields if f.default is not dataclasses.MISSING}

        @lru_cache(maxsize=maxsize)
        def _new(*args: Any) -> T:
            return object.__new__(cls)

        def __new__(klass: type[T], *args: Any, **kwargs: Any) -> T:
            if not kwargs:
                key = args
            elif not args:
                key = tuple(kwargs.get(name, field_defaults.get(name, dataclasses.MISSING)) for name in field_names)
            else:
                # Mixed positional + keyword: fill positional slots first, then kwargs
                key_list: list[Any] = list(args) + [dataclasses.MISSING] * (len(field_names) - len(args))
                for i, name in enumerate(field_names[len(args) :], start=len(args)):
                    key_list[i] = kwargs.get(name, field_defaults.get(name, dataclasses.MISSING))
                key = tuple(key_list)
            return _new(*key)

        cls.__new__ = __new__  # type: ignore[method-assign, assignment]
        return cls

    return decorator


def unordered_range(a: int, b: int) -> range:
    """
    A range from a to b (inclusive), regardless of the order of a and b.

    https://stackoverflow.com/a/38036694
    """
    step = -1 if b < a else 1
    return range(a, b + step, step)
