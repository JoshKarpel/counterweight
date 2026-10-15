from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from dataclasses import field
from functools import lru_cache
from itertools import chain
from typing import Protocol

from counterweight._utils import flyweight
from counterweight.events import InputHandler
from counterweight.focus import ElementHandle
from counterweight.graphemes import grapheme_width
from counterweight.graphemes import graphemes
from counterweight.graphemes import visible
from counterweight.styles import CellStyle
from counterweight.styles import Style
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


class Painter(Protocol):
    """
    What draws a [`Canvas`][counterweight.elements.Canvas]'s content box.

    A painter is compared with `==` to the one its canvas had in the last frame,
    and `draw` isn't called again while it's equal and the box is the same size,
    so what `draw` returns must depend only on the painter and the size it's given.
    A frozen dataclass built from the same values in each render is equal to the last one,
    so a component can build its painter in every render.
    """

    @property
    def natural_size(self) -> tuple[int, int]:
        """
        The canvas's intrinsic size in cells, as `(width, height)`,
        which it takes on each axis that its style and its parent's layout leave undetermined.
        """

    @property
    def keeps_aspect_ratio(self) -> bool:
        """
        Whether a canvas sized on one axis takes its size on the other from the ratio of `natural_size`,
        as an `<img>` with only a `width` keeps its picture's proportions.
        A natural size of zero on either axis has no ratio to keep.
        """

    def draw(self, width: int, height: int) -> Rows:
        """
        The rows of cells to show in a `width` by `height` content box, top to bottom,
        each drawn rightward from the box's left edge.

        Each cell's style is resolved against the canvas's, so whatever a cell leaves unset comes from the canvas:
        its foreground from the `text_style`, and its background as the `Canvas` describes.
        Cells past the box's edges are cut off, and any part of the box the rows don't reach shows the canvas's background.
        It isn't called for a box with no cells.
        """


@dataclass(frozen=True, slots=True, kw_only=True)
class Canvas:
    """
    A leaf element whose content box its `painter` draws, cell by cell, instead of laying out text.

    It's sized as HTML's replaced elements (`<img>`, `<canvas>`) are:
    its painter's `natural_size` is its intrinsic size, which it takes on each axis that its style
    and its parent's layout leave undetermined, and `draw` is called with the size its content box ends up.
    A painter that keeps its aspect ratio gives a canvas sized on only one axis the other by that ratio.
    In a flex row, a canvas shrinks no narrower than its intrinsic width, as an `<img>` doesn't,
    unless its style sets `min_width(0)`.

    A background that its painter leaves unset is the canvas's `text_style` background if its style sets one,
    and its `content_color` otherwise, so a cell the painter leaves transparent matches the rest of the box.
    """

    painter: Painter
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


AnyElement = Div | Text | Canvas

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


# Rows of grapheme clusters, top to bottom, each drawn left to right.
type Rows = tuple[tuple[StyledGrapheme, ...], ...]


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
