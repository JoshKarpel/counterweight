import pytest
from hypothesis import given
from hypothesis.strategies import integers

from counterweight._utils import unordered_range


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    (
        (0, 0, (0,)),
        (0, 1, (0, 1)),
        (0, 2, (0, 1, 2)),
        (0, 3, (0, 1, 2, 3)),
        (1, 1, (1,)),
        (1, 2, (1, 2)),
        (2, 1, (2, 1)),
        (1, -1, (1, 0, -1)),
    ),
)
def test_examples(a: int, b: int, expected: tuple[int, ...]) -> None:
    assert tuple(unordered_range(a, b)) == expected


@pytest.mark.slow
@given(
    a=integers(min_value=-10_000, max_value=10_000),
    b=integers(min_value=-10_000, max_value=10_000),
)
def test_properties(a: int, b: int) -> None:
    result = tuple(unordered_range(a, b))

    assert a in result
    assert b in result

    assert result[0] <= result[-1] if a <= b else result[0] >= result[-1]

    assert len(result) == abs(a - b) + 1
