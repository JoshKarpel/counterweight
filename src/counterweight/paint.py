from __future__ import annotations

import logging
from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from itertools import groupby
from textwrap import dedent
from typing import assert_never
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import SubElement

import waxy

from counterweight._utils import flyweight
from counterweight._utils import halve_integer
from counterweight.elements import AnyElement
from counterweight.elements import Canvas
from counterweight.elements import StyledGrapheme
from counterweight.geometry import Position
from counterweight.geometry import Rects
from counterweight.geometry import Region
from counterweight.layout import Lines
from counterweight.layout import cells_width
from counterweight.layout import child_clip
from counterweight.layout import clipped_axes
from counterweight.styles.styles import UNSET
from counterweight.styles.styles import AnyColor
from counterweight.styles.styles import BorderKind
from counterweight.styles.styles import CellStyle
from counterweight.styles.styles import Color
from counterweight.styles.styles import JoinedBorderKind
from counterweight.styles.styles import JoinedBorderParts
from counterweight.styles.styles import ResolvedCellStyle
from counterweight.styles.styles import ResolvedStyle
from counterweight.styles.styles import Style
from counterweight.styles.styles import TextJustify
from counterweight.styles.styles import resolve_cell_style
from counterweight.styles.styles import rgb_of

logger = logging.getLogger(__name__)


@flyweight(maxsize=2**14)
@dataclass(frozen=True, slots=True)
class Cell:
    """
    What one terminal cell shows: a grapheme cluster and the resolved style it's drawn with.

    A cluster two cells wide is followed by a continuation cell, whose `grapheme` is empty,
    because the terminal draws the cluster across both.
    """

    grapheme: str
    style: ResolvedCellStyle

    @classmethod
    @lru_cache(maxsize=2**10)
    def blank(cls, color: AnyColor) -> Cell:
        """A space on a `color` background."""
        return cls(" ", resolve_cell_style(CellStyle(background=color)))

    @property
    def is_continuation(self) -> bool:
        """Whether this is the right half of a two-cell-wide cluster, which the cell to its left draws."""
        return not self.grapheme

    def erased(self) -> Cell:
        """
        A space in this cell's style, which is what a terminal leaves in the other half of a two-cell-wide
        cluster when one half is drawn over.
        """
        return Cell(" ", self.style)


BLANK = Cell.blank(color=Color.from_name("black"))


@dataclass(slots=True)
class Paint:
    """
    A screen's worth of cells, stored row by row.

    Index it with a `Position` or an `(x, y)` pair.
    Indexing outside the screen raises `IndexError` (negative coordinates don't wrap around),
    while [`get`][counterweight.paint.Paint.get] returns `None` there instead.

    Every two-cell-wide cluster is followed by its continuation cell on the same row, and every continuation
    cell follows one. Writing over one half of a pair erases the other half to a space, as a terminal does,
    so the cells written must not split a pair themselves (except where `write_row` clips them).
    """

    width: int
    height: int
    cells: list[Cell]

    @classmethod
    def blank(cls, width: int, height: int) -> Paint:
        """A `width` by `height` paint of [`BLANK`][counterweight.paint.BLANK] cells."""
        return cls(width, height, [BLANK] * (width * height))

    def index(self, x: int, y: int) -> int:
        """The offset of the cell at `(x, y)` in `cells`."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError(f"({x}, {y}) is outside a {self.width}x{self.height} paint")
        return y * self.width + x

    def __getitem__(self, position: Position | tuple[int, int]) -> Cell:
        x, y = position if isinstance(position, tuple) else (position.x, position.y)
        return self.cells[self.index(x, y)]

    def __setitem__(self, position: Position | tuple[int, int], cell: Cell) -> None:
        x, y = position if isinstance(position, tuple) else (position.x, position.y)
        start = self.index(x, y)
        self._erase_split_pairs(start, start + 1)
        self.cells[start] = cell

    def _erase_split_pairs(self, start: int, stop: int) -> None:
        """
        Before `cells[start:stop]`, part of one row, are overwritten, erase the half outside them
        of any two-cell-wide cluster that straddles either end.
        """
        # A continuation cell never starts a row, so a pair split at either end lies within this row.
        cells = self.cells
        if (first := cells[start]).is_continuation:
            cells[start - 1] = first.erased()
        if stop < len(cells) and (after := cells[stop]).is_continuation:
            cells[stop] = after.erased()

    @property
    def bounds(self) -> Region:
        """The region the paint covers, which clips nothing when given as a clip."""
        return Region(left=0, top=0, right=self.width, bottom=self.height)

    def get(self, position: Position) -> Cell | None:
        """The cell at `position`, or `None` if it's off the screen."""
        if 0 <= position.x < self.width and 0 <= position.y < self.height:
            return self.cells[position.y * self.width + position.x]
        return None

    def fill(self, region: Region, cell: Cell, clip: Region) -> None:
        """Set every cell of `region` that is inside `clip` and on the screen to `cell`."""
        left, right = max(region.left, clip.left, 0), min(region.right, clip.right, self.width)
        if left >= right:
            return
        top, bottom = max(region.top, clip.top, 0), min(region.bottom, clip.bottom, self.height)
        w = self.width
        width = right - left
        row = [cell] * width
        cells = self.cells
        has_cells_after = right < w
        # _erase_split_pairs, inlined because every border and background fills row by row.
        for start in range(top * w + left, bottom * w + left, w):
            stop = start + width
            if not cells[start].grapheme:
                cells[start - 1] = cells[start].erased()
            if has_cells_after and not cells[stop].grapheme:
                cells[stop] = cells[stop].erased()
            cells[start:stop] = row

    def write_row(self, x: int, y: int, row: Sequence[Cell], clip: Region) -> None:
        """
        Set the cells from `(x, y)` rightward to `row`, dropping any that fall outside `clip` or off the screen,
        and erasing the half left inside of a two-cell-wide cluster that straddles their edge.
        """
        if not max(clip.top, 0) <= y < min(clip.bottom, self.height):
            return
        low = max(clip.left, 0)
        skip = low - x if x < low else 0
        keep = min(len(row), min(clip.right, self.width) - x)
        if skip >= keep:
            return
        start = y * self.width + x
        self._erase_split_pairs(start + skip, start + keep)
        if skip == 0 and keep == len(row):
            self.cells[start : start + keep] = row
            return
        visible = list(row[skip:keep])
        if visible[0].is_continuation:
            visible[0] = visible[0].erased()
        if keep < len(row) and row[keep].is_continuation:
            visible[-1] = visible[-1].erased()
        self.cells[start + skip : start + keep] = visible

    def rows(self) -> Iterator[list[Cell]]:
        """Each row of cells, top to bottom."""
        w = self.width
        return (self.cells[start : start + w] for start in range(0, w * self.height, w))

    def items(self) -> Iterator[tuple[Position, Cell]]:
        """Each cell with its position, row by row."""
        w = self.width
        return ((Position(i % w, i // w), cell) for i, cell in enumerate(self.cells))

    def copy(self) -> Paint:
        """A paint with the same cells, which changing this one doesn't affect."""
        return Paint(self.width, self.height, list(self.cells))


CellMap = dict[Position, Cell]
BorderHealingHints = dict[Position, JoinedBorderParts]
Fill = tuple[Region, Cell]
BorderSides = tuple[bool, bool, bool, bool]
Run = tuple[int, int, list[Cell]]  # cells to draw left to right from (x, y)


def paint_layout(
    elements: Iterable[tuple[AnyElement, Rects, Lines]],
    width: int,
    height: int,
) -> tuple[Paint, BorderHealingHints]:
    """Paint `elements` in the order given, which is paint order, so later elements are drawn over earlier ones."""
    paint = Paint.blank(width, height)
    hints: BorderHealingHints = {}
    for element, resolved, lines in elements:
        hints.update(paint_element(paint, element, element.style.resolved, resolved, lines))
    return paint, hints


def diff_paint(new: Paint, current: Paint) -> list[Run]:
    """
    The cells of `new` that differ from `current`, which must be the same size,
    as runs of adjacent changed cells, row by row.
    """
    if (new.width, new.height) != (current.width, current.height):
        raise ValueError(f"Can't diff a {new.width}x{new.height} paint against a {current.width}x{current.height} one")

    w = new.width
    runs: list[Run] = []
    for y, start in enumerate(range(0, w * new.height, w)):
        new_row = new.cells[start : start + w]
        current_row = current.cells[start : start + w]
        # Comparing whole rows runs in C and checks identity before equality, so unchanged rows are cheap to skip.
        if new_row == current_row:
            continue
        run_start = None
        for x, (new_cell, current_cell) in enumerate(zip(new_row, current_row, strict=True)):
            if new_cell is not current_cell and new_cell != current_cell:
                if run_start is None:
                    run_start = x
            elif run_start is not None:
                runs.append((run_start, y, new_row[run_start:x]))
                run_start = None
        if run_start is not None:
            runs.append((run_start, y, new_row[run_start:]))
    return runs


def runs_of(paint: Paint) -> list[Run]:
    """Every row of `paint` as one run, for drawing it in full."""
    return [(0, y, row) for y, row in enumerate(paint.rows())]


def paint_element(
    paint: Paint, element: AnyElement, style: ResolvedStyle, resolved: Rects, lines: Lines
) -> tuple[tuple[Position, JoinedBorderParts], ...]:
    """
    Paint the part of one element inside its clip onto `paint`,
    returning the border healing hints for its corners inside the clip.

    `lines` are the rows a `Text` wraps to, which layout wrapped it to, or the rows a `Canvas`'s painter drew,
    and are empty for a `Div`.
    Only the rows inside the clip are built, so a long text in a scroll container costs only the rows in view,
    and an element paints nothing if its border box, its text and any `margin_color` margin all miss the clip.
    Text overflows its box down and to the right, so the border box alone can't decide that.
    A canvas's rows never leave its content box, which clips them.

    The margin edge, border, padding edge and text each cover different cells,
    so only the background fill underneath them has to come first.
    The background fills the border box, and the margin is painted only where the element's own style
    sets `margin_color`, so a margin leaves whatever lies beneath it visible, as on the web.
    An element with no border, padding, text, `margin_color` or `content_color` paints nothing,
    not even its background, so an undecorated container laid over other elements leaves them visible.

    A hint for a corner outside the clip is dropped, because healing only checks that the cell under a hint
    is a border character, so it would rewrite whatever border was drawn there instead.
    """
    clip = resolved.clip
    if clip is None:
        return ()

    content = resolved.content
    rows = range(0)
    text_clip = clip
    text_justify = style.text_justify
    text_style = style.text_style
    if lines:
        if isinstance(element, Canvas):
            own_clip = clip.intersection(content)
            text_justify = "left"
            text_style = canvas_text_style(element.style)
        else:
            # Text overflows its box, as CSS's does, unless the Text's own overflow clips it to its padding box.
            own_clip = child_clip(clip, clip, resolved, "padding", *clipped_axes(element.style))
        if own_clip is not None:
            text_clip = own_clip
            rows = range(max(text_clip.top, content.top), min(text_clip.bottom, content.top + len(lines)))

    has_margin_color = element.style.margin_color is not UNSET
    if (
        resolved.visible is None
        and not rows
        and not (has_margin_color and resolved.margin.intersection(clip) is not None)
    ):
        return ()

    border, corners = border_fills(
        style.border_kind,
        style.border_style,
        style.border_contract,
        resolved.border,
        border_sides(element.style),
    )
    # A border box wholly inside the clip is its own visible part, so all of its corners are too.
    hints = (
        corners
        if resolved.visible is resolved.border
        else tuple((position, parts) for position, parts in corners if clip.contains(position))
    )
    margin = edge_fills(resolved.margin, resolved.border, style.margin_color) if has_margin_color else ()
    fills = margin + border + edge_fills(resolved.padding, resolved.content, style.padding_color)

    if not fills and not lines and element.style.content_color is UNSET:
        return hints

    paint.fill(resolved.border, Cell.blank(color=style.content_color), clip)
    for region, cell in fills:
        paint.fill(region, cell, clip)
    for y in rows:
        paint.write_row(
            content.left,
            y,
            line_cells(lines[y - content.top], text_justify, text_style, content.width),
            text_clip,
        )

    return hints


@lru_cache(maxsize=2**8)
def canvas_text_style(style: Style) -> ResolvedCellStyle:
    """
    The style a `Canvas` with `style` resolves its painter's cells against:
    its `text_style`, whose background is its `content_color` unless the `text_style` sets one.
    """
    resolved = style.resolved
    if style.text_style.background is not UNSET:
        return resolved.text_style
    return resolve_cell_style(CellStyle(background=resolved.content_color), resolved.text_style)


@lru_cache(maxsize=2**12)
def edge_fills(outer: Region, inner: Region, color: AnyColor) -> tuple[Fill, ...]:
    """The parts of `outer` outside `inner`, as up to four strips filled with blank cells of `color`."""
    cell = Cell.blank(color=color)
    strips = (
        Region(left=outer.left, top=outer.top, right=outer.right, bottom=inner.top),
        Region(left=outer.left, top=inner.bottom, right=outer.right, bottom=outer.bottom),
        Region(left=outer.left, top=inner.top, right=inner.left, bottom=inner.bottom),
        Region(left=inner.right, top=inner.top, right=outer.right, bottom=inner.bottom),
    )
    return tuple((strip, cell) for strip in strips if not strip.is_empty)


def justify_line(line: list[StyledGrapheme], width: int, justify: TextJustify) -> list[StyledGrapheme]:
    space = width - cells_width(line)
    if space <= 0:
        return line
    if justify == "left":
        return line + [StyledGrapheme(grapheme=" ")] * space
    if justify == "right":
        return [StyledGrapheme(grapheme=" ")] * space + line
    if justify == "center":
        left, right = halve_integer(space)
        return [StyledGrapheme(grapheme=" ")] * left + line + [StyledGrapheme(grapheme=" ")] * right
    assert_never(justify)


@lru_cache(maxsize=2**12)
def line_cells(
    line: tuple[StyledGrapheme, ...], justify: TextJustify, text_style: ResolvedCellStyle, width: int
) -> tuple[Cell, ...]:
    """
    The cells one wrapped row of text fills when justified at `width`, at least `width` cells long.
    A zero-width cluster takes no cell, so it isn't drawn.
    """
    cells: list[Cell] = []
    previous_style = None
    for styled in justify_line(list(line), width, justify):
        if not styled.width:
            continue
        if styled.style is not previous_style:
            resolved_style = resolve_cell_style(styled.style, text_style)
            previous_style = styled.style
        cells.append(Cell(styled.grapheme, resolved_style))
        if styled.width == 2:
            cells.append(Cell("", resolved_style))
    return tuple(cells)


_ONE_CELL = waxy.Length(1)


@lru_cache(maxsize=2**12)
def border_sides(style: Style) -> BorderSides:
    """
    Which sides of the border an element with `style` draws, left, right, top and bottom:
    those whose width is one cell.
    They come from the style rather than from the gap between the border and padding boxes,
    because a scroll container's `scrollbar_width` widens that gap without drawing anything in it.
    """
    layout = style.layout
    return (
        layout.border_left == _ONE_CELL,
        layout.border_right == _ONE_CELL,
        layout.border_top == _ONE_CELL,
        layout.border_bottom == _ONE_CELL,
    )


@lru_cache(maxsize=2**12)
def border_fills(
    kind: BorderKind | None,
    cell_style: ResolvedCellStyle,
    contract: int,
    region: Region,
    sides: BorderSides,
) -> tuple[tuple[Fill, ...], tuple[tuple[Position, JoinedBorderParts], ...]]:
    """
    A border's edges and corners as one-cell-wide fills, in the order they overwrite each other,
    and the corners that border healing may join to a neighboring border.

    The border runs around the edge of the border box `region`, on the `sides` (left, right, top and bottom) it's drawn on.
    """
    if kind is None:
        return (), ()

    bv = kind.value

    draw_left, draw_right, draw_top, draw_bottom = sides

    if contract:
        contract_top = contract if not draw_top else None
        contract_bottom = -contract if not draw_bottom else None
        contract_left = contract if not draw_left else None
        contract_right = -contract if not draw_right else None
    else:
        contract_top = contract_bottom = contract_left = contract_right = None

    rows = range(region.top, region.bottom)[contract_top:contract_bottom] if not region.is_empty else range(0)
    columns = range(region.left, region.right)[contract_left:contract_right] if not region.is_empty else range(0)

    def column(x: int) -> Region:
        return Region(left=x, top=rows.start, right=x + 1, bottom=rows.start + len(rows))

    def row(y: int) -> Region:
        return Region(left=columns.start, top=y, right=columns.start + len(columns), bottom=y + 1)

    def point(position: Position) -> Region:
        return Region(left=position.x, top=position.y, right=position.x + 1, bottom=position.y + 1)

    fills: list[Fill] = []
    if draw_left and rows:
        fills.append((column(region.left), Cell(bv.left, cell_style)))
    if draw_right and rows:
        fills.append((column(region.right - 1), Cell(bv.right, cell_style)))
    if draw_top:
        if columns:
            fills.append((row(region.top), Cell(bv.top, cell_style)))
        if draw_left:
            fills.append((point(region.top_left), Cell(bv.left_top, cell_style)))
        if draw_right:
            fills.append((point(region.top_right), Cell(bv.right_top, cell_style)))
    if draw_bottom:
        if columns:
            fills.append((row(region.bottom - 1), Cell(bv.bottom, cell_style)))
        if draw_left:
            fills.append((point(region.bottom_left), Cell(bv.left_bottom, cell_style)))
        if draw_right:
            fills.append((point(region.bottom_right), Cell(bv.right_bottom, cell_style)))

    try:
        jbv = JoinedBorderKind[kind.name].value
    except KeyError:
        return tuple(fills), ()

    corners = []
    if draw_top:
        if draw_left:
            corners.append(region.top_left)
        if draw_right:
            corners.append(region.top_right)
    if draw_bottom:
        if draw_left:
            corners.append(region.bottom_left)
        if draw_right:
            corners.append(region.bottom_right)

    return tuple(fills), tuple((corner, jbv) for corner in corners)


SVG_FOREGROUND = Color.from_name("white")
SVG_BACKGROUND = Color.from_name("black")
"""What `svg` draws the terminal's default foreground and background in."""


def svg(paint: Paint) -> Element:
    w, h = paint.width, paint.height

    x_mul = 0.55  # x coordinates get cut roughly in half because monospace cells are twice as tall as they are wide
    y_mul = 1.13  # seems to make border connect up just right

    fmt = "0.2f"
    unit = "em"

    root = Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": f"{w * x_mul:{fmt}}{unit}",
            "height": f"{h * y_mul:{fmt}}{unit}",
        },
    )

    style = SubElement(
        root,
        "style",
        {},
    )
    style.text = dedent(
        """\
        svg {
          dominant-baseline: hanging;
          font-size: 1rem;
        }
        """
    )

    background_root = SubElement(
        root,
        "g",
        {
            "shape-rendering": "crispEdges",
        },
    )
    SubElement(  # default background color is black, so do a single black rectangle to cover the whole background as an optimization
        background_root,
        "rect",
        {
            "x": f"{0 * x_mul:{fmt}}{unit}",
            "y": f"{0 * y_mul:{fmt}}{unit}",
            "width": f"{w * x_mul:{fmt}}{unit}",
            "height": f"{h * y_mul:{fmt}}{unit}",
            "fill": SVG_BACKGROUND.hex,
        },
    )

    text_root = SubElement(
        root,
        "text",
        {
            "fill": SVG_FOREGROUND.hex,
            "font-family": "monospace",
        },
    )

    for y, row in enumerate(paint.rows()):
        cells = list(enumerate(row))
        row_tspan_root = SubElement(
            text_root,
            "tspan",
            {
                "y": f"{y * y_mul:{fmt}}{unit}",
            },
        )

        for bg_color, x_cells_group in groupby(
            cells, key=lambda x_cell: rgb_of(x_cell[1].style.background, SVG_BACKGROUND).hex
        ):
            # Optimization: write out long horizontal rectangles of the same background color as rectangles instead of individual cell-sized rectangles
            x_cells = tuple(x_cells_group)
            first_x, _first_cell = x_cells[0]

            SubElement(
                background_root,
                "rect",
                {
                    "x": f"{first_x * x_mul:{fmt}}{unit}",
                    "y": f"{y * y_mul:{fmt}}{unit}",
                    "width": f"{len(x_cells) * x_mul:{fmt}}{unit}",
                    "height": f"{1 * y_mul:{fmt}}{unit}",
                    "fill": bg_color,
                },
            )

            for x, cell in x_cells:
                # optimization: don't write spaces; continuation cells are drawn by the cluster to their left
                if cell.grapheme == " " or cell.is_continuation:
                    continue

                ts = SubElement(
                    row_tspan_root,
                    "tspan",
                    {
                        "x": f"{x * x_mul:{fmt}}{unit}",
                    },
                )

                # optimization: don't write the default foreground
                if (foreground := rgb_of(cell.style.foreground, SVG_FOREGROUND)) != SVG_FOREGROUND:
                    ts.attrib["fill"] = foreground.hex
                ts.attrib.update(svg_text_style(cell.style))
                ts.text = cell.grapheme

    return root


def svg_text_style(style: ResolvedCellStyle) -> dict[str, str]:
    """The SVG attributes that draw a cell's bold, dim, italic, underline, and strikethrough, which are off by default."""
    attributes = {}
    if style.bold:
        attributes["font-weight"] = "bold"
    if style.dim:
        attributes["fill-opacity"] = "0.5"
    if style.italic:
        attributes["font-style"] = "italic"
    if decorations := " ".join(
        decoration
        for decoration, is_on in (("underline", style.underline), ("line-through", style.strikethrough))
        if is_on
    ):
        attributes["text-decoration"] = decorations
    return attributes
