import pytest

from counterweight.utils import clamp


@pytest.mark.parametrize(
    ("min_", "val", "max_", "expected"),
    (
        (0, 5, 10, 5),
        (0, -1, 10, 0),
        (0, 11, 10, 10),
        (0, 0, 0, 0),
        (3, 3, 3, 3),
        (-5, -10, 5, -5),
        (-5, 10, 5, 5),
    ),
)
def test_clamp(min_: int, val: int, max_: int, expected: int) -> None:
    assert clamp(min_, val, max_) == expected
