from asyncio import CancelledError, create_task, sleep

import pytest

from counterweight._utils import cancel, forever


async def test_cancel_happy_path() -> None:
    await cancel(create_task(forever()))


async def test_cancel_when_cancel_is_itself_cancelled() -> None:
    inner_task = create_task(forever())
    cancel_task = create_task(cancel(inner_task))

    cancel_task.cancel()

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
