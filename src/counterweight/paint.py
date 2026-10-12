from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from functools import lru_cache
from itertools import groupby
from textwrap import dedent
from typing import assert_never
from xml.etree.ElementTree import Element, SubElement

from counterweight._utils import flyweight, halve_integer
from counterweight.elements import AnyElement, Div, StyledGrapheme, Text
from counterweight.geometry import Position, Region
from counterweight.layout import ResolvedLayout, cells_width, wrap_cells
from counterweight.styles.styles import (
    UNSET,
    BorderKind,
    CellStyle,
    Color,
    JoinedBorderKind,
    JoinedBorderParts,
    ResolvedCellStyle,
    ResolvedStyle,
    TextJustify,
    TextWrap,
    resolve_cell_style,
    resolve_style,
)

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
    def blank(cls, color: Color) -> Cell:
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

    def get(self, position: Position) -> Cell | None:
        """The cell at `position`, or `None` if it's off the screen."""
        if 0 <= position.x < self.width and 0 <= position.y < self.height:
            return self.cells[position.y * self.width + position.x]
        return None

    def fill(self, region: Region, cell: Cell) -> None:
        """Set every cell of `region` that is on the screen to `cell`."""
        left, right = max(region.left, 0), min(region.right, self.width)
        if left >= right:
            return
        top, bottom = max(region.top, 0), min(region.bottom, self.height)
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

    def write_row(self, x: int, y: int, row: Sequence[Cell]) -> None:
        """
        Set the cells from `(x, y)` rightward to `row`, dropping any that fall off the screen,
        and erasing the half left on screen of a two-cell-wide cluster that straddles its edge.
        """
        if not 0 <= y < self.height:
            return
        skip = -x if x < 0 else 0
        keep = min(len(row), self.width - x)
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
Run = tuple[int, int, list[Cell]]  # cells to draw left to right from (x, y)


def paint_layout(
    elements: Iterable[tuple[AnyElement, ResolvedLayout]],
    width: int,
    height: int,
) -> tuple[Paint, BorderHealingHints]:
    styled = sorted(
        ((element, resolve_style(element.style), resolved) for element, resolved in elements),
        key=lambda esr: (esr[1].z, esr[2].order),
    )
    paint = Paint.blank(width, height)
    hints: BorderHealingHints = {}
    for element, style, resolved in styled:
        hints.update(paint_element(paint, element, style, resolved))
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
        for x, (new_cell, current_cell) in enumerate(zip(new_row, current_row)):
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
    paint: Paint, element: AnyElement, style: ResolvedStyle, resolved: ResolvedLayout
) -> tuple[tuple[Position, JoinedBorderParts], ...]:
    """
    Paint one element onto `paint`, returning its border healing hints.

    The margin edge, border, padding edge and text each cover different cells,
    so only the background fill underneath them has to come first.
    An element with none of them and no `content_color` of its own paints nothing, not even its background,
    so an undecorated container laid over other elements leaves them visible.
    """
    border, hints = border_fills(
        style.border_kind, style.border_style, style.border_contract, resolved.border, resolved.padding
    )
    fills = (
        edge_fills(resolved.margin, resolved.border, style.margin_color)
        + border
        + edge_fills(resolved.padding, resolved.content, style.padding_color)
    )

    match element:
        case Div():
            lines: tuple[tuple[Cell, ...], ...] = ()
        case Text() as e:
            content = resolved.content
            lines = text_lines(
                e.cells, style.text_wrap, style.text_justify, style.text_style, content.width, content.height
            )
        case _:
            assert_never(element)

    if not fills and not lines and element.style.content_color is UNSET:
        return hints

    paint.fill(resolved.margin, Cell.blank(color=style.content_color))
    for region, cell in fills:
        paint.fill(region, cell)
    for y, line in enumerate(lines, start=resolved.content.top):
        paint.write_row(resolved.content.left, y, line)

    return hints


@lru_cache(maxsize=2**12)
def edge_fills(outer: Region, inner: Region, color: Color) -> tuple[Fill, ...]:
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
    elif justify == "left":
        return line + [StyledGrapheme(grapheme=" ")] * space
    elif justify == "right":
        return [StyledGrapheme(grapheme=" ")] * space + line
    elif justify == "center":
        left, right = halve_integer(space)
        return [StyledGrapheme(grapheme=" ")] * left + line + [StyledGrapheme(grapheme=" ")] * right
    else:
        assert_never(justify)


@lru_cache(maxsize=2**12)
def text_lines(
    graphemes: tuple[StyledGrapheme, ...],
    wrap: TextWrap,
    justify: TextJustify,
    text_style: ResolvedCellStyle,
    width: int,
    height: int,
) -> tuple[tuple[Cell, ...], ...]:
    """
    The rows of cells that text fills a `width` by `height` region with, each exactly `width` cells long.
    They don't depend on where the region is, so text that moves keeps its cache entry.

    A zero-width cluster takes no cell, so it isn't drawn.
    A two-cell-wide cluster that would straddle the right edge is left out, and spaces fill the rest of its row.
    """
    if width <= 0:
        return ()

    lines = []
    previous_style = None
    for line in wrap_cells(cells=graphemes, wrap=wrap, width=width)[:height]:
        cells: list[Cell] = []
        for styled in justify_line(line, width, justify):
            if not styled.width:
                continue
            if styled.style is not previous_style:
                resolved_style = resolve_cell_style(styled.style, text_style)
                previous_style = styled.style
            room = width - len(cells)
            if styled.width > room:
                # resolved_style is always bound here, since previous_style starts as None
                cells.extend([Cell(" ", resolved_style)] * room)
                break
            cells.append(Cell(styled.grapheme, resolved_style))
            if styled.width == 2:
                cells.append(Cell("", resolved_style))
        lines.append(tuple(cells))
    return tuple(lines)


@lru_cache(maxsize=2**12)
def border_fills(
    kind: BorderKind | None,
    cell_style: ResolvedCellStyle,
    contract: int,
    region: Region,
    padding: Region,
) -> tuple[tuple[Fill, ...], tuple[tuple[Position, JoinedBorderParts], ...]]:
    """
    A border's edges and corners as one-cell-wide fills, in the order they overwrite each other,
    and the corners that border healing may join to a neighboring border.
    """
    if kind is None:
        return (), ()

    bv = kind.value

    draw_left = padding.left > region.left
    draw_right = region.right > padding.right
    draw_top = padding.top > region.top
    draw_bottom = region.bottom > padding.bottom

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
            "fill": Color.from_name("black").hex,
        },
    )

    text_root = SubElement(
        root,
        "text",
        {
            "fill": Color.from_name("white").hex,
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

        for bg_color, x_cells_group in groupby(cells, key=lambda x_cell: x_cell[1].style.background.hex):
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

                # optimization: don't write white, it's the default
                if cell.style.foreground != Color.from_name("white"):
                    ts.attrib["fill"] = cell.style.foreground.hex
                ts.text = cell.grapheme

    return root
