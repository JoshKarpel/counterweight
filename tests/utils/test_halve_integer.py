import pytest
from hypothesis import given
from hypothesis.strategies import integers

from counterweight._utils import halve_integer


@pytest.mark.parametrize(
    ("x", "result"),
    (
        (0, (0, 0)),
        (1, (1, 0)),  # leftover favors the left result
        (2, (1, 1)),
    ),
)
def test_examples(x: int, result: tuple[int, int]) -> None:
    assert halve_integer(x) == result


@given(
    x=integers(
        min_value=0,
        max_value=10_000,
    ),
)
def test_properties(x: int) -> None:
    result = halve_integer(x)

    assert len(result) == 2
    assert sum(result) == x
