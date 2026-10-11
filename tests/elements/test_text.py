from collections.abc import Sequence

import pytest

from counterweight.elements import Chunk, StyledChar, Text
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
            (StyledChar(char=" "),),
        ),
        (
            "f",
            Style(),
            (StyledChar(char="f"),),
        ),
        (
            "foo",
            Style(),
            (StyledChar(char="f"), StyledChar(char="o"), StyledChar(char="o")),
        ),
        (
            (Chunk(content="f"), Chunk(content="o"), Chunk(content="o")),
            Style(),
            (StyledChar(char="f"), StyledChar(char="o"), StyledChar(char="o")),
        ),
    ),
)
def test_text_cells(
    content: str | Sequence[Chunk],
    style: Style,
    expected: tuple[StyledChar],
) -> None:
    assert tuple(Text(content=content, style=style).cells) == expected


def test_chunk_space() -> None:
    assert Chunk.space() == Chunk(content=" ")


def test_chunk_newline() -> None:
    assert Chunk.newline() == Chunk(content="\n")
