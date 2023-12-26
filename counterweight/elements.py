from __future__ import annotations

from typing import Callable, Iterator, Literal, Sequence, Union

from pydantic import Field

from counterweight.cell_paint import CellPaint
from counterweight.control import Control
from counterweight.events import KeyPressed, MouseDown, MouseUp
from counterweight.styles import CellStyle, Style
from counterweight.types import FrozenForbidExtras


class Div(FrozenForbidExtras):
    type: Literal["div"] = "div"
    style: Style = Field(default=Style())
    children: Sequence[Component | AnyElement] = Field(default=())
    on_hover: Style = Field(default=Style())
    on_key: Callable[[KeyPressed], Control | None] | None = None
    on_mouse_down: Callable[[MouseDown], Control | None] | None = None
    on_mouse_up: Callable[[MouseUp], Control | None] | None = None


class Chunk(FrozenForbidExtras):
    content: str
    style: CellStyle = Field(default_factory=CellStyle)

    @property
    def cells(self) -> Iterator[CellPaint]:
        yield from (CellPaint(char=char, style=self.style) for char in self.content)

    @classmethod
    def space(cls) -> Chunk:
        return Chunk(content=" ")

    @classmethod
    def newline(cls) -> Chunk:
        return Chunk(content="\n")


class Text(FrozenForbidExtras):
    type: Literal["text"] = "text"
    content: str | Sequence[Chunk | CellPaint]
    style: Style = Field(default=Style())
    on_hover: Style | None = Field(default=None)
    on_key: Callable[[KeyPressed], Control | None] | None = None
    on_mouse_down: Callable[[MouseDown], Control | None] | None = None
    on_mouse_up: Callable[[MouseUp], Control | None] | None = None

    @property
    def children(self) -> Sequence[Component | AnyElement]:
        return ()

    @property
    def cells(self) -> Iterator[CellPaint]:
        if isinstance(self.content, str):
            yield from (CellPaint(char=char, style=self.style.typography.style) for char in self.content)
        else:
            for c in self.content:
                yield from c.cells


AnyElement = Union[
    Div,
    Text,
]

from counterweight.components import Component  # noqa: E402, deferred to avoid circular import

Div.model_rebuild()
Text.model_rebuild()
