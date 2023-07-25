import pytest

from reprisal._utils import wrap_text


@pytest.mark.parametrize(
    ["text", "width", "expected"],
    [
        ("", 0, []),
        ("", 1, []),
        ("foo", 1, ["f", "o", "o"]),
        (
            """\
foo bar

baz""",
            3,
            ["foo", "bar", "", "baz"],
        ),
        (
            """\
foobar
wiz

baz""",
            6,
            ["foobar", "wiz", "", "baz"],
        ),
    ],
)
def test_examples(text: str, width: int, expected: list[str]) -> None:
    assert wrap_text(text, wrap="paragraphs", width=width) == expected
