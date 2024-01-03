from collections.abc import Sequence

import pytest

from counterweight.cell_paint import CellPaint
from counterweight.elements import Chunk, Text
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
            (CellPaint(char=" "),),
        ),
        (
            "f",
            Style(),
            (CellPaint(char="f"),),
        ),
        (
            "foo",
            Style(),
            (CellPaint(char="f"), CellPaint(char="o"), CellPaint(char="o")),
        ),
        (
            (Chunk(content="f"), Chunk(content="o"), Chunk(content="o")),
            Style(),
            (CellPaint(char="f"), CellPaint(char="o"), CellPaint(char="o")),
        ),
        (
            (CellPaint(char="f"), CellPaint(char="o"), CellPaint(char="o")),
            Style(),
            (CellPaint(char="f"), CellPaint(char="o"), CellPaint(char="o")),
        ),
    ),
)
def test_text_cells(
    content: str | Sequence[Chunk | CellPaint],
    style: Style,
    expected: tuple[CellPaint],
) -> None:
    assert tuple(Text(content=content, style=style).cells) == expected


def test_chunk_space() -> None:
    assert Chunk.space() == Chunk(content=" ")


def test_chunk_newline() -> None:
    assert Chunk.newline() == Chunk(content="\n")
