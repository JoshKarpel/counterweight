from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import lru_cache
from itertools import chain
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
        return styled_cells(self.content, self.style)

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


class _StyledGraphemes(dict[str, StyledGrapheme]):
    """
    Each grapheme cluster met so far, styled with `style`,
    so styling a long text looks each distinct cluster up in the flyweight once rather than once per occurrence.
    """

    __slots__ = ("style",)

    def __init__(self, style: CellStyle) -> None:
        super().__init__()
        self.style = style

    def __missing__(self, grapheme: str) -> StyledGrapheme:
        cell = self[grapheme] = StyledGrapheme(grapheme=visible(grapheme), style=self.style)
        return cell


@lru_cache(maxsize=2**12)
def styled_cells(content: str, style: CellStyle) -> tuple[StyledGrapheme, ...]:
    """
    The grapheme clusters of `content`, each styled with `style`.

    Cached because short pieces of text, such as a table's values, recur across texts and frames.
    Layout asks for a one-line text's cells, and for the pieces a longer text doesn't already have
    from its previous version (see `MeasurableText.of`), so a long text being edited asks for the pieces the edit touched,
    not every piece every frame.
    """
    return tuple(map(_StyledGraphemes(style).__getitem__, graphemes(content)))


def text_pieces(content: str | tuple[Chunk, ...], text_style: CellStyle) -> Iterator[tuple[str, CellStyle]]:
    """
    A `Text`'s content as pieces whose cells, laid end to end, are its cells: each chunk, or each line of a string.
    Layout keeps each text's cells by piece, so a long text that changes, such as a document being edited,
    rebuilds only the pieces that changed.
    A line break always ends a grapheme cluster, so splitting at them splits no cluster.
    """
    if isinstance(content, str):
        return ((line, text_style) for line in content.splitlines(keepends=True))
    return ((chunk.content, chunk.style) for chunk in content)


def text_cells(content: str | tuple[Chunk, ...], text_style: CellStyle) -> tuple[StyledGrapheme, ...]:
    """The styled grapheme clusters of a `Text`'s content."""
    return tuple(chain.from_iterable(styled_cells(*piece) for piece in text_pieces(content, text_style)))
