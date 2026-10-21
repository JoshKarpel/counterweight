import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from counterweight._graphemes import graphemes
from counterweight._graphemes import visible
from counterweight.elements import Chunk
from counterweight.elements import StyledGrapheme
from counterweight.elements import Text
from counterweight.styles import CellStyle
from counterweight.styles import Color
from counterweight.styles import Style


def test_texts_have_no_children() -> None:
    assert Text(content="foo").children == ()


@pytest.mark.parametrize(
    ("content", "style", "expected"),
    [
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
    ],
)
def test_text_cells(
    content: str | tuple[Chunk, ...],
    style: Style,
    expected: tuple[StyledGrapheme],
) -> None:
    assert tuple(Text(content=content, style=style).cells) == expected


def test_chunk_space() -> None:
    assert Chunk.space() == Chunk(content=" ")


def test_chunk_newline() -> None:
    assert Chunk.newline() == Chunk(content="\n")


def test_chunk_cells_are_its_clusters_in_its_style() -> None:
    bold = CellStyle(bold=True)

    assert Chunk(content="hé", style=bold).cells == (
        StyledGrapheme(grapheme="h", style=bold),
        StyledGrapheme(grapheme="é", style=bold),
    )


def test_chunk_takes_the_text_style_of_a_style() -> None:
    italic_teal = CellStyle(italic=True, foreground=Color(20, 184, 166))

    assert Chunk(content="hi", style=Style(text_style=italic_teal, border_kind=None)).style == italic_teal


def test_chunk_given_a_style_equals_the_chunk_given_its_text_style() -> None:
    struck = CellStyle(strikethrough=True)

    assert Chunk(content="old", style=Style(text_style=struck)) == Chunk(content="old", style=struck)


def test_chunk_without_a_style_has_an_empty_cell_style() -> None:
    assert Chunk(content="plain").style == CellStyle()


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
    with pytest.raises(ValueError, match="is a control character"):
        StyledGrapheme(grapheme="\x1b")


LINE_BREAKS_AND_CLUSTERS = st.lists(
    st.sampled_from(
        [
            "a",
            " ",
            "\n",
            "\r",
            "\r\n",
            "\x0b",
            "\x0c",
            "\x1c",
            "\x85",
            "\N{LINE SEPARATOR}",
            "\N{COMBINING ACUTE ACCENT}",
            "\N{ZERO WIDTH JOINER}",
            "👩",
            "\U0001f1fa",
            "\U0001f1f8",
            "\t",
        ]
    ),
    max_size=12,
).map("".join)


@given(content=LINE_BREAKS_AND_CLUSTERS)
def test_text_cells_are_the_clusters_of_the_whole_content_though_built_line_by_line(content: str) -> None:
    assert [cell.grapheme for cell in Text(content=content).cells] == [visible(g) for g in graphemes(content)]
