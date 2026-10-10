from asyncio import CancelledError, Event, create_task, current_task, sleep, timeout, wait

import pytest

from counterweight._utils import cancel_tasks, forever


async def test_cancel_tasks_cancels_every_task() -> None:
    tasks = [create_task(forever()), create_task(forever())]

    await cancel_tasks(tasks)

    assert [task.cancelled() for task in tasks] == [True, True]


async def test_cancel_tasks_runs_teardowns_concurrently() -> None:
    first_tearing_down = Event()
    second_tearing_down = Event()

    async def waits_for_other_teardown(mine: Event, other: Event) -> None:
        try:
            await forever()
        finally:
            mine.set()
            await other.wait()

    tasks = [
        create_task(waits_for_other_teardown(first_tearing_down, second_tearing_down)),
        create_task(waits_for_other_teardown(second_tearing_down, first_tearing_down)),
    ]
    await sleep(0)

    # Each teardown finishes only once the other has started, so tearing down one at a time would deadlock.
    async with timeout(1):
        await cancel_tasks(tasks)


async def test_cancel_tasks_propagates_cancellation_of_the_caller() -> None:
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

    cancel_task = create_task(cancel_tasks([inner_task]))
    await sleep(0.01)

    cancel_task.cancel()
    await sleep(0.01)

    with pytest.raises(CancelledError):
        await cancel_task


async def test_cancel_tasks_lets_an_enclosing_timeout_expire() -> None:
    teardown_may_finish = Event()

    async def slow_teardown() -> None:
        try:
            await forever()
        finally:
            await teardown_may_finish.wait()

    async def cancel_under_expired_timeout() -> None:
        async with timeout(0):
            await cancel_tasks([task])

    task = create_task(slow_teardown())
    await sleep(0)

    # Bounded with `wait`, which doesn't forward cancellation, so a regression fails here instead of hanging.
    attempt = create_task(cancel_under_expired_timeout())
    await wait([attempt], timeout=1)
    teardown_may_finish.set()

    assert attempt.done()
    with pytest.raises(TimeoutError):
        await attempt


async def test_cancel_tasks_reraises_an_exception_from_teardown() -> None:
    async def fails_in_teardown() -> None:
        try:
            await forever()
        finally:
            raise ValueError("teardown failed")

    task = create_task(fails_in_teardown())
    await sleep(0)

    with pytest.raises(ValueError, match="teardown failed"):
        await cancel_tasks([task])


async def test_cancel_tasks_with_task_that_returns_after_cancellation() -> None:
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
        await cancel_tasks([task])


async def test_cancel_tasks_with_task_that_has_already_finished() -> None:
    async def t() -> None:
        return

    task = create_task(t())

    await task  # run the task to completion

    await cancel_tasks([task])
