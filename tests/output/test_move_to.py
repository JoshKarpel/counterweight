import pytest
from hypothesis import given
from hypothesis.strategies import integers

from counterweight.geometry import Position
from counterweight.output import move_to


@pytest.mark.parametrize(
    ("pos", "expected"),
    (
        (Position(0, 0), "\x1b[1;1f"),
        (Position(1, 0), "\x1b[1;2f"),
        (Position(0, 1), "\x1b[2;1f"),
        (Position(1, 1), "\x1b[2;2f"),
    ),
)
def test_examples(pos: Position, expected: str) -> None:
    assert move_to(pos) == expected


@given(x=integers(min_value=0, max_value=1000), y=integers(min_value=0, max_value=1000))
def test_properties(x: int, y: int) -> None:
    m = move_to(position=Position(x, y))

    assert m.startswith("\x1b[")
    assert m.endswith("f")
    assert m.count(";") == 1
