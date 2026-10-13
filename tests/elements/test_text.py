import re
from collections.abc import Sequence

import pytest

from counterweight.elements import Chunk, StyledGrapheme, Text
from counterweight.styles import Style


def test_texts_have_no_children() -> None:
    assert Text(content="foo").children == ()


@pytest.mark.parametrize(
    ("content", "style", "expected"),
    (
        (
            "",
            Style(),
            (),
        ),
        (
            " ",
            Style(),
            (StyledGrapheme(grapheme=" "),),
        ),
        (
            "f",
            Style(),
            (StyledGrapheme(grapheme="f"),),
        ),
        (
            "foo",
            Style(),
            (StyledGrapheme(grapheme="f"), StyledGrapheme(grapheme="o"), StyledGrapheme(grapheme="o")),
        ),
        (
            (Chunk(content="f"), Chunk(content="o"), Chunk(content="o")),
            Style(),
            (StyledGrapheme(grapheme="f"), StyledGrapheme(grapheme="o"), StyledGrapheme(grapheme="o")),
        ),
    ),
)
def test_text_cells(
    content: str | Sequence[Chunk],
    style: Style,
    expected: tuple[StyledGrapheme],
) -> None:
    assert tuple(Text(content=content, style=style).cells) == expected


def test_chunk_space() -> None:
    assert Chunk.space() == Chunk(content=" ")


def test_chunk_newline() -> None:
    assert Chunk.newline() == Chunk(content="\n")


def test_text_cells_are_grapheme_clusters() -> None:
    assert [cell.grapheme for cell in Text(content="日e\N{COMBINING ACUTE ACCENT}👩\N{ZERO WIDTH JOINER}💻").cells] == [
        "日",
        "e\N{COMBINING ACUTE ACCENT}",
        "👩\N{ZERO WIDTH JOINER}💻",
    ]


@pytest.mark.parametrize(("grapheme", "expected"), [("a", 1), ("日", 2), ("👩\N{ZERO WIDTH JOINER}💻", 2)])
def test_styled_grapheme_carries_its_width(grapheme: str, expected: int) -> None:
    assert StyledGrapheme(grapheme=grapheme).width == expected


@pytest.mark.parametrize("grapheme", ["", "ab", "日本"])
def test_styled_grapheme_rejects_anything_but_one_cluster(grapheme: str) -> None:
    with pytest.raises(ValueError, match=re.escape(repr(grapheme))):
        StyledGrapheme(grapheme=grapheme)


def test_text_replaces_control_characters_but_keeps_line_breaks() -> None:
    assert [cell.grapheme for cell in Text(content="a\tb\x1b[31m\nc").cells] == [
        "a",
        "\N{SYMBOL FOR HORIZONTAL TABULATION}",
        "b",
        "\N{SYMBOL FOR ESCAPE}",
        "[",
        "3",
        "1",
        "m",
        "\n",
        "c",
    ]


def test_styled_grapheme_rejects_control_characters() -> None:
    with pytest.raises(ValueError):
        StyledGrapheme(grapheme="\x1b")
