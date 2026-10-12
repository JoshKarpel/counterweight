from __future__ import annotations

import pytest

from counterweight.graphemes import grapheme_width, graphemes, visible


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", []),
        ("ab c", ["a", "b", " ", "c"]),
        ("a\r\nb", ["a", "\r\n", "b"]),
        ("日本", ["日", "本"]),
        ("e\N{COMBINING ACUTE ACCENT}x", ["e\N{COMBINING ACUTE ACCENT}", "x"]),
        ("👩\N{ZERO WIDTH JOINER}💻!", ["👩\N{ZERO WIDTH JOINER}💻", "!"]),
        ("🇯🇵🇫🇷", ["🇯🇵", "🇫🇷"]),
        ("❤\N{VARIATION SELECTOR-16}a", ["❤\N{VARIATION SELECTOR-16}", "a"]),
    ],
    ids=["empty", "ascii", "crlf", "cjk", "combining-mark", "zwj-sequence", "flags", "variation-selector"],
)
def test_graphemes_splits_text_into_clusters(text: str, expected: list[str]) -> None:
    assert graphemes(text) == expected


@pytest.mark.parametrize(
    ("grapheme", "expected"),
    [
        ("a", 1),
        ("e\N{COMBINING ACUTE ACCENT}", 1),
        ("日", 2),
        ("👩\N{ZERO WIDTH JOINER}💻", 2),
        ("❤\N{VARIATION SELECTOR-16}", 2),
        ("🇯🇵", 2),
        ("\N{ZERO WIDTH SPACE}", 0),
        ("\N{LEFT-TO-RIGHT MARK}", 0),
        ("\N{COMBINING ACUTE ACCENT}", 0),
        ("\n", 0),
        ("\r\n", 0),
    ],
    ids=[
        "ascii",
        "combining-mark",
        "cjk-ideograph",
        "zwj-sequence",
        "emoji-presentation",
        "flag",
        "zero-width-space",
        "bidi-mark",
        "lone-combining-mark",
        "newline",
        "crlf",
    ],
)
def test_grapheme_width(grapheme: str, expected: int) -> None:
    assert grapheme_width(grapheme) == expected


@pytest.mark.parametrize("grapheme", ["\t", "\x1b", "\x7f", "\x85"])
def test_grapheme_width_rejects_control_characters(grapheme: str) -> None:
    with pytest.raises(ValueError):
        grapheme_width(grapheme)


@pytest.mark.parametrize(
    ("grapheme", "expected"),
    [
        ("\t", "\N{SYMBOL FOR HORIZONTAL TABULATION}"),
        ("\x1b", "\N{SYMBOL FOR ESCAPE}"),
        ("\r", "\N{SYMBOL FOR CARRIAGE RETURN}"),
        ("\x00", "\N{SYMBOL FOR NULL}"),
        ("\x7f", "\N{SYMBOL FOR DELETE}"),
        ("\x85", "\N{REPLACEMENT CHARACTER}"),
        ("\n", "\n"),
        ("\r\n", "\r\n"),
        ("a", "a"),
        ("\N{ZERO WIDTH SPACE}", "\N{ZERO WIDTH SPACE}"),
    ],
    ids=["tab", "escape", "carriage-return", "null", "delete", "c1", "newline", "crlf", "ascii", "zero-width-space"],
)
def test_visible_replaces_control_characters_other_than_line_breaks(grapheme: str, expected: str) -> None:
    assert visible(grapheme) == expected
