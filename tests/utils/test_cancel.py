from asyncio import CancelledError, create_task, current_task, sleep

import pytest

from counterweight._utils import cancel, forever


async def test_cancel_happy_path() -> None:
    await cancel(create_task(forever()))


async def test_cancel_when_cancel_is_itself_cancelled() -> None:
    async def inner() -> None:
        try:
            await forever()
        except CancelledError:
            ct = current_task()
            if ct:
                ct.uncancel()
            await forever()

    # We need sleeps below to make sure that the tasks actually progress to the awaits inside them,
    # instead of being cancelled before they even start running

    inner_task = create_task(inner())
    await sleep(0.01)

    cancel_task = create_task(cancel(inner_task))
    await sleep(0.01)

    cancel_task.cancel()
    await sleep(0.01)

    with pytest.raises(CancelledError):
        await cancel_task


async def test_cancel_with_task_that_returns_after_cancellation() -> None:
    async def t() -> None:
        try:
            await forever()
        except CancelledError:
            return

    task = create_task(t())

    # Let the task progress to the await forever(),
    # otherwise it gets cancelled before it even starts running
    await sleep(0.01)

    with pytest.raises(RuntimeError):
        await cancel(task)


async def test_cancel_with_task_that_has_already_finished() -> None:
    async def t() -> None:
        return

    task = create_task(t())

    await task  # run the task to completion

    await cancel(task)
