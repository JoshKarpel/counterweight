from asyncio import Queue, timeout

import pytest

from counterweight._utils import drain_queue


@pytest.fixture
def queue() -> Queue[int]:
    return Queue()


async def test_non_empty_queue(queue: Queue[int]) -> None:
    for i in range(2):
        await queue.put(i)

    assert await drain_queue(queue) == [0, 1]


async def test_empty_queue_hangs(queue: Queue[int]) -> None:
    try:
        async with timeout(0.05):  # pragma: unreachable
            await drain_queue(queue)
            assert False, "drain_queue() should have hung"
    except TimeoutError:
        pass
