import pytest
from hypothesis import assume, given
from hypothesis.strategies import integers, lists

from counterweight._utils import partition_int


@pytest.mark.parametrize(
    ("total", "weights", "expected"),
    (
        (0, (1,), [0]),
        (0, (1, 1), [0, 0]),
        (1, (1,), [1]),
        (3, (1,), [3]),
        (3, (3,), [3]),
        (2, (1, 1), [1, 1]),
        (3, (2, 1), [2, 1]),
        (3, (1, 2), [1, 2]),
        (4, (1, 2, 1), [1, 2, 1]),
        (5, (2, 1), [3, 2]),
        (5, (1, 2), [2, 3]),
        (3, (1, 1), [2, 1]),
        (100, (1, 1, 1), [33, 34, 33]),
        (101, (1, 1, 1), [34, 33, 34]),
        (102, (1, 1, 1), [34, 34, 34]),
        (103, (1, 1, 1), [34, 35, 34]),
        (104, (1, 1, 1), [35, 34, 35]),
        (105, (1, 1, 1), [35, 35, 35]),
        (201, (50, 100, 50), [50, 101, 50]),
        (201, (50, 50, 100), [50, 50, 101]),
        (201, (100, 50, 50), [100, 51, 50]),
    ),
)
def test_examples(total: int, weights: tuple[int], expected: list[int]) -> None:
    assert partition_int(total, weights) == expected


@pytest.mark.parametrize(
    ("total", "weights", "exc"),
    (
        (5, (-1,), ValueError),
        (5, (-1, 1), ValueError),
        (5, (0,), ValueError),
    ),
)
def test_errors(total: int, weights: tuple[int], exc: type[Exception]) -> None:
    with pytest.raises(exc):
        partition_int(total, weights)


@given(
    total=integers(
        min_value=0,
        # The algorithm is inaccurate once you start hitting float precision problems,
        # but we only care about ints that could plausibly represent screen sizes in at most pixels
        # but more likely terminal cells, which are even coarser.
        max_value=10_000,
    ),
    weights=lists(integers(min_value=0), min_size=1),
)
def test_properties(total: int, weights: list[int]) -> None:
    assume(sum(weights) > 0)

    result = partition_int(total, tuple(weights))

    assert sum(result) == total

    assert len(result) == len(weights)
