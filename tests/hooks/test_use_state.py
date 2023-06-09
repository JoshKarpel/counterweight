import pytest

from reprisal.render import Root, use_state


def count(inc: int = 1) -> int:
    x, set_x = use_state(0)

    set_x(x + inc)

    return x


@pytest.fixture
def counter() -> Root[[int], int]:
    return Root(count)


@pytest.fixture
def two_counters() -> Root[[], tuple[int, int]]:
    def two_counts() -> tuple[int, int]:
        return count(inc=1), count(inc=-1)

    return Root(two_counts)


def test_setter_affects_subsequent_returns(counter: Root[[], int]) -> None:
    assert counter.render() == 0
    assert counter.render() == 1
    assert counter.render() == 2


def test_states_are_isolated_from_each_other(two_counters: Root[[], tuple[int, int]]) -> None:
    assert two_counters.render() == (0, 0)
    assert two_counters.render() == (1, -1)
    assert two_counters.render() == (2, -2)


def test_roots_are_isolated_from_each_other() -> None:
    a = Root(count)
    b = Root(count)

    assert a.render() == 0
    assert a.render() == 1

    assert b.render() == 0
    assert b.render() == 1

    assert a.render() == 2

    assert b.render() == 2
