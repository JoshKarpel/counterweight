from asyncio import timeout

import pytest

from counterweight._utils import forever


async def test_forever() -> None:
    # Not the most inspiring test, but it's hard to test that it will *never* return...
    with pytest.raises(TimeoutError):
        async with timeout(0.01):
            await forever()
