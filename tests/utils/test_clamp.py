import pytest
from hypothesis import assume, given
from hypothesis.strategies import integers

from counterweight._utils import clamp


@pytest.mark.parametrize(
    ("min", "val", "max", "expected"),
    (
        (0, 5, 10, 5),
        (0, 15, 10, 10),
        (0, -5, 10, 0),
        (None, 5, 10, 5),
        (None, 15, 10, 10),
        (0, 5, None, 5),
        (0, -5, None, 0),
    ),
)
def test_examples(min: int | None, val: int, max: int | None, expected: int) -> None:
    assert clamp(min, val, max) == expected


@given(
    min=integers(
        min_value=-10_000,
        max_value=10_000,
    ),
    val=integers(
        min_value=-20_000,
        max_value=20_000,
    ),
    max=integers(
        min_value=-10_000,
        max_value=10_000,
    ),
)
def test_properties(min: int, val: int, max: int) -> None:
    assume(min <= max)

    result = clamp(min, val, max)

    assert min <= result <= max


def test_min_must_be_less_or_equal_max() -> None:
    with pytest.raises(ValueError):
        clamp(1, 0, 0)
