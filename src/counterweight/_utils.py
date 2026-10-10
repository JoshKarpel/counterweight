from __future__ import annotations

import dataclasses
from asyncio import Queue, QueueEmpty, Task, get_event_loop, wait
from collections.abc import Iterable
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


async def cancel_tasks[T](tasks: Iterable[Task[T]]) -> None:
    """
    Cancel every task, then wait until all of them have finished tearing down.

    The tasks tear down concurrently, so the wait lasts as long as the slowest teardown, not their sum.
    A task that is already done is skipped (for example, an effect that aborted itself by returning).
    A task that raises during teardown has its exception re-raised,
    and one that swallows its cancellation and returns raises `RuntimeError`.
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

    for task in pending:
        if task.cancelled():
            continue
        if (exception := task.exception()) is not None:
            raise exception
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
