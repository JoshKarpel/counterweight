import pytest
from hypothesis import given
from hypothesis.strategies import dictionaries, text

from reprisal._utils import diff


@pytest.mark.parametrize(
    ["a", "b", "expected"],
    [
        ({}, {}, {}),
        ({"a": 1}, {}, {"a": 1}),
        ({"a": 1}, {"a": 1}, {}),
        ({"a": 1}, {"a": 2}, {"a": 1}),
        ({"a": 1}, {"b": 1}, {"a": 1}),
    ],
)
def test_examples(a: dict[object, object], b: dict[object, object], expected: dict[object, object]) -> None:
    assert diff(a, b) == expected


@given(
    a=dictionaries(keys=text(), values=text()),
    b=dictionaries(keys=text(), values=text()),
)
def test_properties(a: dict[str, str], b: dict[str, str]) -> None:
    result = diff(a, b)

    # all keys in the diff are from the left
    assert result.keys() <= a.keys()

    # all values in diff are from the left
    assert all(v == a[k] for k, v in result.items())
