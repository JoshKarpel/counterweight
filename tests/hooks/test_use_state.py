import pytest

from reprisal.hooks import HookContext, use_state


def count(inc: int = 1) -> int:
    x, set_x = use_state(0)

    set_x(x + inc)

    return x


@pytest.fixture
def counter() -> HookContext[[int], int]:
    return HookContext(count)


@pytest.fixture
def two_counters() -> HookContext[[], tuple[int, int]]:
    def two_counts() -> tuple[int, int]:
        return count(inc=1), count(inc=-1)

    return HookContext(two_counts)


def test_setter_affects_subsequent_returns(counter: HookContext[[], int]) -> None:
    assert counter() == 0
    assert counter() == 1
    assert counter() == 2


def test_states_are_isolated_from_each_other(
    two_counters: HookContext[[], tuple[int, int]]
) -> None:
    assert two_counters() == (0, 0)
    assert two_counters() == (1, -1)
    assert two_counters() == (2, -2)


def test_HookContexts_are_isolated_from_each_other() -> None:
    a = HookContext(count)
    b = HookContext(count)

    assert a() == 0
    assert a() == 1

    assert b() == 0
    assert b() == 1

    assert a() == 2

    assert b() == 2
