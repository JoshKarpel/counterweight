from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import Callable, Literal, Sequence, Union

from pydantic import Field

from counterweight.controls import AnyControl
from counterweight.events import KeyPressed, MouseEvent
from counterweight.styles import CellStyle, Style
from counterweight.types import FrozenForbidExtras


class Div(FrozenForbidExtras):
    type: Literal["div"] = "div"
    style: Style = Field(default=Style())
    children: Sequence[Component | AnyElement] = Field(default=())
    on_key: Callable[[KeyPressed], AnyControl | None] | None = None
    on_mouse: Callable[[MouseEvent], AnyControl | None] | None = None


class Chunk(FrozenForbidExtras):
    content: str
    style: CellStyle = Field(default_factory=CellStyle)

    @cached_property
    def cells(self) -> tuple[CellPaint, ...]:
        return tuple(CellPaint(char=char, style=self.style) for char in self.content)

    @classmethod
    def space(cls) -> Chunk:
        return SPACE

    @classmethod
    def newline(cls) -> Chunk:
        return NEWLINE


SPACE = Chunk(content=" ")
NEWLINE = Chunk(content="\n")


class Text(FrozenForbidExtras):
    type: Literal["text"] = "text"
    content: str | Sequence[Chunk]
    style: Style = Field(default=Style())
    on_key: Callable[[KeyPressed], AnyControl | None] | None = None
    on_mouse: Callable[[MouseEvent], AnyControl | None] | None = None

    @property
    def children(self) -> Sequence[Component | AnyElement]:
        return ()

    @cached_property
    def cells(self) -> tuple[CellPaint, ...]:
        if isinstance(self.content, str):
            return tuple(CellPaint(char=char, style=self.style.typography.style) for char in self.content)
        else:
            return sum((chunk.cells for chunk in self.content), ())


AnyElement = Union[
    Div,
    Text,
]

from counterweight.components import Component  # noqa: E402, deferred to avoid circular import

Div.model_rebuild()
Text.model_rebuild()


@dataclass(slots=True)
class CellPaint:
    char: str
    style: CellStyle = field(default=CellStyle())
