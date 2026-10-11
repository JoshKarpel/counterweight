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
    inner_started = Event()
    inner_resisting = Event()

    async def inner() -> None:
        inner_started.set()
        try:
            await forever()
        except CancelledError:
            ct = current_task()
            if ct:
                ct.uncancel()
            inner_resisting.set()
            await forever()

    inner_task = create_task(inner())
    await inner_started.wait()

    cancel_task = create_task(cancel_tasks([inner_task]))
    await inner_resisting.wait()

    cancel_task.cancel()

    with pytest.raises(CancelledError):
        await cancel_task

    await cancel_tasks([inner_task])


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


async def fails_in_teardown(message: str) -> None:
    try:
        await forever()
    finally:
        raise ValueError(message)


async def test_cancel_tasks_reraises_an_exception_from_teardown() -> None:
    task = create_task(fails_in_teardown("teardown failed"))
    await sleep(0)

    with pytest.RaisesGroup(pytest.RaisesExc(ValueError, match="teardown failed")):
        await cancel_tasks([task])


async def test_cancel_tasks_reraises_every_exception_from_teardown() -> None:
    tasks = [create_task(fails_in_teardown("first failed")), create_task(fails_in_teardown("second failed"))]
    await sleep(0)

    with pytest.RaisesGroup(
        pytest.RaisesExc(ValueError, match="first failed"),
        pytest.RaisesExc(ValueError, match="second failed"),
    ):
        await cancel_tasks(tasks)


async def test_cancel_tasks_with_task_that_returns_after_cancellation() -> None:
    started = Event()

    async def t() -> None:
        started.set()
        try:
            await forever()
        except CancelledError:
            return

    task = create_task(t())
    await started.wait()

    with pytest.RaisesGroup(RuntimeError):
        await cancel_tasks([task])


async def test_cancel_tasks_with_task_that_has_already_finished() -> None:
    async def t() -> None:
        return

    task = create_task(t())

    await task  # run the task to completion

    await cancel_tasks([task])
