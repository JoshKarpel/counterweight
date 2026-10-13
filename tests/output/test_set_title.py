import pytest

from counterweight.output import set_title


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        pytest.param("notes.txt - editor", "\x1b]2;notes.txt - editor\x1b\\", id="plain"),
        pytest.param("日本語 🇯🇵", "\x1b]2;日本語 🇯🇵\x1b\\", id="wide-graphemes"),
        pytest.param("a\nb\r\nc", "\x1b]2;a b c\x1b\\", id="line-breaks-become-spaces"),
        pytest.param("x\x07\x1b\\y", "\x1b]2;x␇␛\\y\x1b\\", id="c0-controls-become-control-pictures"),
        pytest.param("x\x9cy", "\x1b]2;x\N{REPLACEMENT CHARACTER}y\x1b\\", id="c1-controls-become-replacements"),
    ],
)
def test_set_title_makes_control_characters_visible_so_the_title_cannot_end_early(title: str, expected: str) -> None:
    assert set_title(title) == expected
