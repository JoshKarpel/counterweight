from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Sequence, Union

from counterweight._utils import flyweight
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
        return _chunk_cells(self.content, self.style)

    @classmethod
    def space(cls) -> Chunk:
        return SPACE

    @classmethod
    def newline(cls) -> Chunk:
        return NEWLINE


SPACE = Chunk(content=" ")
NEWLINE = Chunk(content="\n")


@lru_cache(maxsize=2**12)
def _chunk_cells(content: str, style: CellStyle) -> tuple[CellPaint, ...]:
    return tuple(CellPaint(char=char, style=style) for char in content)


@lru_cache(maxsize=2**12)
def _text_cells(content: str | tuple[Chunk, ...], text_style: CellStyle) -> tuple[CellPaint, ...]:
    if isinstance(content, str):
        return tuple(CellPaint(char=char, style=text_style) for char in content)
    else:
        return tuple(cell for chunk in content for cell in chunk.cells)


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
        content = self.content if isinstance(self.content, str) else tuple(self.content)
        return _text_cells(content, self.style.text_style)


AnyElement = Union[
    Div,
    Text,
]

from counterweight.components import Component  # noqa: E402, deferred to avoid circular import


@flyweight(maxsize=2**12)
@dataclass(slots=True, frozen=True, kw_only=True)
class CellPaint:
    char: str
    style: CellStyle = _DEFAULT_CELL_STYLE
