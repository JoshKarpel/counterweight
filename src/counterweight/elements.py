from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Union

from counterweight._utils import flyweight
from counterweight.events import InputHandler
from counterweight.focus import ElementHandle
from counterweight.graphemes import grapheme_width, graphemes, visible
from counterweight.styles import CellStyle, Style
from counterweight.styles.styles import _DEFAULT_CELL_STYLE

_DEFAULT_STYLE = Style()


@dataclass(frozen=True, slots=True, kw_only=True)
class Div:
    style: Style = _DEFAULT_STYLE
    children: tuple[Component | AnyElement, ...] = ()
    on_input: InputHandler | None = None
    handle: ElementHandle | None = None
    """
    The element handle that names this element for controls such as [`ScrollTo`][counterweight.controls.ScrollTo],
    and for [`use_scroll`][counterweight.hooks.use_scroll].
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class Chunk:
    content: str
    style: CellStyle = _DEFAULT_CELL_STYLE

    @property
    def cells(self) -> tuple[StyledGrapheme, ...]:
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
def _chunk_cells(content: str, style: CellStyle) -> tuple[StyledGrapheme, ...]:
    return tuple(StyledGrapheme(grapheme=visible(grapheme), style=style) for grapheme in graphemes(content))


@lru_cache(maxsize=2**12)
def text_cells(content: str | tuple[Chunk, ...], text_style: CellStyle) -> tuple[StyledGrapheme, ...]:
    if isinstance(content, str):
        return _chunk_cells(content, text_style)
    else:
        return tuple(cell for chunk in content for cell in chunk.cells)


@dataclass(frozen=True, slots=True, kw_only=True)
class Text:
    content: str | tuple[Chunk, ...]
    style: Style = _DEFAULT_STYLE
    on_input: InputHandler | None = None
    handle: ElementHandle | None = None
    """
    The element handle that names this element for controls such as [`ScrollTo`][counterweight.controls.ScrollTo],
    and for [`use_scroll`][counterweight.hooks.use_scroll].
    """

    @property
    def children(self) -> tuple[Component | AnyElement, ...]:
        return ()

    @property
    def cells(self) -> tuple[StyledGrapheme, ...]:
        return text_cells(self.content, self.style.text_style)


AnyElement = Union[
    Div,
    Text,
]

from counterweight.components import Component  # noqa: E402, deferred to avoid circular import


@flyweight(maxsize=2**12)
@dataclass(slots=True, frozen=True, kw_only=True)
class StyledGrapheme:
    """One grapheme cluster of text, the style it's drawn with, and how many terminal cells it takes."""

    grapheme: str
    style: CellStyle = _DEFAULT_CELL_STYLE
    width: int = field(init=False, compare=False, repr=False)

    def __post_init__(self) -> None:
        if len(self.grapheme) != 1 and len(graphemes(self.grapheme)) != 1:
            raise ValueError(f"A StyledGrapheme holds exactly one grapheme cluster, not {self.grapheme!r}")
        object.__setattr__(self, "width", grapheme_width(self.grapheme))
