from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence, Union

from counterweight.controls import AnyControl
from counterweight.events import KeyPressed, MouseEvent
from counterweight.styles import CellStyle, Style
from counterweight.styles.styles import _DEFAULT_CELL_STYLE

_DEFAULT_STYLE = Style()


@dataclass(frozen=True, slots=True, kw_only=True)
class Div:
    style: Style = _DEFAULT_STYLE
    children: Sequence[Component | AnyElement] = ()
    on_key: Callable[[KeyPressed], AnyControl | None] | None = None
    on_mouse: Callable[[MouseEvent], AnyControl | None] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Chunk:
    content: str
    style: CellStyle = _DEFAULT_CELL_STYLE

    @property
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


@dataclass(frozen=True, slots=True, kw_only=True)
class Text:
    content: str | Sequence[Chunk]
    style: Style = _DEFAULT_STYLE
    on_key: Callable[[KeyPressed], AnyControl | None] | None = None
    on_mouse: Callable[[MouseEvent], AnyControl | None] | None = None

    @property
    def children(self) -> tuple[Component | AnyElement, ...]:
        return ()

    @property
    def cells(self) -> tuple[CellPaint, ...]:
        if isinstance(self.content, str):
            return tuple(CellPaint(char=char, style=self.style.text_style) for char in self.content)
        else:
            return tuple(cell for chunk in self.content for cell in chunk.cells)


AnyElement = Union[
    Div,
    Text,
]

from counterweight.components import Component  # noqa: E402, deferred to avoid circular import


@dataclass(slots=True)
class CellPaint:
    char: str
    style: CellStyle = _DEFAULT_CELL_STYLE
