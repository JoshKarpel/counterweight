from __future__ import annotations

from collections.abc import Iterable
from typing import Iterator, Literal

from pydantic import Field

from counterweight.styles.styles import CellStyle
from counterweight.types import FrozenForbidExtras


class CellPaint(FrozenForbidExtras):
    char: str = Field(default=..., min_length=1, max_length=1)
    style: CellStyle = Field(default_factory=CellStyle)

    @property
    def cells(self) -> Iterator[CellPaint]:
        yield self


def wrap_cells(
    cells: Iterable[CellPaint],
    wrap: Literal["none", "paragraphs"],
    width: int,
) -> list[list[CellPaint]]:
    if width <= 0:
        return []

    if wrap == "none":
        lines: list[list[CellPaint]] = []
        current_line: list[CellPaint] = []
        for cell in cells:
            if cell.char == "\n":
                lines.append(current_line)
                current_line = []
            else:
                current_line.append(cell)
        lines.append(current_line)
        return lines

    raise NotImplementedError("non-none wrapping not yet implemented")

    # wrapper = TextWrapper(width=width)
    #
    # paragraphs = text.split("\n\n")  # double newline = paragraph break
    #
    # lines = []
    # for paragraph in paragraphs:
    #     lines.extend(wrapper.wrap(paragraph))
    #     lines.append("")  # empty line between paragraphs
    #
    # return lines[:-1]  # remove last empty line
