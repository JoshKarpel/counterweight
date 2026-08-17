from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator, MutableMapping
from dataclasses import dataclass
from functools import lru_cache
from itertools import groupby, islice
from textwrap import dedent
from typing import Literal, Mapping, Self, TypeVar, assert_never
from xml.etree.ElementTree import Element, ElementTree, SubElement

import waxy
from structlog import get_logger

from counterweight._utils import flyweight, halve_integer
from counterweight.elements import AnyElement, CellPaint, Div, Text
from counterweight.geometry import Position
from counterweight.layout import ResolvedLayout, wrap_cells
from counterweight.styles.styles import (
    CellStyle,
    Color,
    JoinedBorderKind,
    JoinedBorderParts,
    Style,
    TextWrap,
)

_T = TypeVar("_T")


class ClipDict(MutableMapping[Position, _T]):
    def __init__(self, clip: waxy.Rect) -> None:
        self._data: dict[Position, _T] = {}
        self._left = int(clip.left)
        self._right = int(clip.right)
        self._top = int(clip.top)
        self._bottom = int(clip.bottom)

    def __setitem__(self, key: Position, value: _T) -> None:
        if self._left <= key.x <= self._right and self._top <= key.y <= self._bottom:
            self._data[key] = value

    def __getitem__(self, key: Position) -> _T:
        return self._data[key]

    def __delitem__(self, key: Position) -> None:
        del self._data[key]

    def __iter__(self) -> Iterator[Position]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __ior__(self, other: Mapping[Position, _T]) -> Self:
        for key, value in other.items():
            self[key] = value
        return self

    def merge_within_clip(self, other: Mapping[Position, _T]) -> None:
        """Merge a mapping whose keys are already guaranteed to be within the clip rect."""
        self._data.update(other)


logger = get_logger()


@flyweight(maxsize=2**14)
@dataclass(slots=True)
class P:
    char: str
    style: CellStyle
    z: int

    @classmethod
    @lru_cache(maxsize=2**10)
    def blank(cls, color: Color, z: int) -> P:
        return cls(
            char=" ",
            style=CellStyle(background=color),
            z=z,
        )


BLANK = P.blank(color=Color.from_name("black"), z=-1_000_000)


Paint = dict[Position, P]
BorderHealingHints = dict[Position, JoinedBorderParts]


def paint_layout(
    elements: list[tuple[AnyElement, ResolvedLayout]],
) -> tuple[Paint, BorderHealingHints]:
    parts: list[tuple[Mapping[Position, P], Mapping[Position, JoinedBorderParts], int, int]] = [
        paint_element(element, resolved) for element, resolved in elements
    ]
    parts.sort(key=lambda p: (p[2], p[3]))
    paint: Paint = {}
    bhh: BorderHealingHints = {}
    for p, b, _, _ in parts:
        paint |= p
        bhh |= b
    return paint, bhh


@lru_cache(maxsize=2**10)
def fill_rect(rect: waxy.Rect, z: int, color: Color) -> Paint:
    return {Position.from_point(p): P.blank(color=color, z=z) for p in rect.points()}


@lru_cache(maxsize=2**10)
def paint_edge(outer: waxy.Rect, inner: waxy.Rect, color: Color, z: int) -> Paint:
    cell_paint = P(char=" ", style=CellStyle(background=color), z=z)
    chars: Paint = {}

    strips = [
        waxy.Rect(left=outer.left, right=outer.right, top=outer.top, bottom=inner.top - 1),
        waxy.Rect(left=outer.left, right=outer.right, top=inner.bottom + 1, bottom=outer.bottom),
        waxy.Rect(left=outer.left, right=inner.left - 1, top=inner.top, bottom=inner.bottom),
        waxy.Rect(left=inner.right + 1, right=outer.right, top=inner.top, bottom=inner.bottom),
    ]
    for strip in strips:
        if strip.top <= strip.bottom and strip.left <= strip.right:
            for p in strip.points():
                chars[Position.from_point(p)] = cell_paint

    return chars


def paint_element(
    element: AnyElement, resolved: ResolvedLayout
) -> tuple[Mapping[Position, P], Mapping[Position, JoinedBorderParts], int, int]:
    m = paint_edge(resolved.margin, resolved.border, element.style.margin_color, element.style.z)
    b, bhh = paint_border(element.style, resolved)
    t = paint_edge(resolved.padding, resolved.content, element.style.padding_color, element.style.z)
    box = m | b | t

    match element:
        case Div():
            paint = box
        case Text() as e:
            paint = box | paint_text(e, resolved.content)
        case _:
            assert_never(element)

    clip = resolved.clip_rect
    if clip is None:
        # Fast path: no clipping needed — use C-level dict merge
        if paint:
            return (
                fill_rect(resolved.margin, element.style.z, element.style.content_color) | paint,
                bhh,
                element.style.z,
                resolved.order,
            )
        return {}, bhh, element.style.z, resolved.order
    else:
        # Clipping path: filter cells through ClipDict
        cell_paint: ClipDict[P] = ClipDict(clip)
        border_hints: ClipDict[JoinedBorderParts] = ClipDict(clip)
        if paint:
            # Intersect the fill rect with the clip before filling — avoids iterating
            # the full content height (e.g. hundreds of rows) when only the viewport is visible.
            fill_region = clip.intersection(resolved.margin)
            if fill_region is not None:
                cell_paint.merge_within_clip(fill_rect(fill_region, element.style.z, element.style.content_color))
            cell_paint |= paint
        border_hints |= bhh
        return cell_paint, border_hints, element.style.z, resolved.order


def justify_line(line: list[CellPaint], width: int, justify: Literal["left", "right", "center"]) -> list[CellPaint]:
    space = width - len(line)
    if space <= 0:
        return line
    elif justify == "left":
        return line + [CellPaint(char=" ")] * space
    elif justify == "right":
        return [CellPaint(char=" ")] * space + line
    elif justify == "center":
        left, right = halve_integer(space)
        return [CellPaint(char=" ")] * left + line + [CellPaint(char=" ")] * right
    else:
        assert_never(justify)


@lru_cache(maxsize=2**10)
def _paint_text(
    cells: tuple[CellPaint, ...],
    wrap: TextWrap,
    justify: Literal["left", "right", "center"],
    text_style: CellStyle,
    z: int,
    rect: waxy.Rect,
) -> Paint:
    # waxy.Rect uses an inclusive coordinate system: width = right - left (one less than the
    # number of cells).  Adding 1 converts to cell count for slicing and iteration.
    width = int(rect.width) + 1
    height = int(rect.height) + 1

    paint = {}
    lines = wrap_cells(cells=cells, wrap=wrap, width=width)

    previous_cell_style = None

    for y, line in enumerate(lines[:height], start=int(rect.top)):
        justified_line = justify_line(line, width, justify)
        for x, cell in enumerate(justified_line[:width], start=int(rect.left)):
            cell_style = cell.style

            if cell_style is not previous_cell_style:
                merged_style = text_style | cell_style
                previous_cell_style = cell_style

            paint[Position(x, y)] = P(
                char=cell.char,
                style=merged_style,  # merged_style will never be unassigned here, since we know previous_cell_style starts as None
                z=z,
            )

    return paint


def paint_text(text: Text, rect: waxy.Rect) -> Paint:
    return _paint_text(
        text.cells, text.style.text_wrap, text.style.text_justify, text.style.text_style, text.style.z, rect
    )


def paint_border(style: Style, resolved: ResolvedLayout) -> tuple[Paint, BorderHealingHints]:
    bk = style.border_kind
    if bk is None:
        return {}, {}

    cell_style = style.border_style
    bv = bk.value
    z = style.z
    contract = style.border_contract

    rect = resolved.border

    draw_left = resolved.padding.left > resolved.border.left
    draw_right = resolved.border.right > resolved.padding.right
    draw_top = resolved.padding.top > resolved.border.top
    draw_bottom = resolved.border.bottom > resolved.padding.bottom

    if contract:
        contract_top = contract if not draw_top else None
        contract_bottom = -contract if not draw_bottom else None
        contract_left = contract if not draw_left else None
        contract_right = -contract if not draw_right else None
    else:
        contract_top = contract_bottom = contract_left = contract_right = None

    chars: Paint = {}

    if draw_left:
        left_paint = P(char=bv.left, style=cell_style, z=z)
        for p in islice(rect.left_edge(), contract_top, contract_bottom):
            chars[Position.from_point(p)] = left_paint

    if draw_right:
        right_paint = P(char=bv.right, style=cell_style, z=z)
        for p in islice(rect.right_edge(), contract_top, contract_bottom):
            chars[Position.from_point(p)] = right_paint

    if draw_top:
        top_paint = P(char=bv.top, style=cell_style, z=z)
        for p in islice(rect.top_edge(), contract_left, contract_right):
            chars[Position.from_point(p)] = top_paint
        if draw_left:
            chars[Position(x=int(rect.left), y=int(rect.top))] = P(char=bv.left_top, style=cell_style, z=z)
        if draw_right:
            chars[Position(x=int(rect.right), y=int(rect.top))] = P(char=bv.right_top, style=cell_style, z=z)

    if draw_bottom:
        bottom_paint = P(char=bv.bottom, style=cell_style, z=z)
        for p in islice(rect.bottom_edge(), contract_left, contract_right):
            chars[Position.from_point(p)] = bottom_paint
        if draw_left:
            chars[Position(x=int(rect.left), y=int(rect.bottom))] = P(char=bv.left_bottom, style=cell_style, z=z)
        if draw_right:
            chars[Position(x=int(rect.right), y=int(rect.bottom))] = P(char=bv.right_bottom, style=cell_style, z=z)

    try:
        jbv = JoinedBorderKind[bk.name].value
    except KeyError:
        bhh: BorderHealingHints = {}
    else:
        bhh = {}
        if draw_top:
            if draw_left:
                bhh[Position(x=int(rect.left), y=int(rect.top))] = jbv
            if draw_right:
                bhh[Position(x=int(rect.right), y=int(rect.top))] = jbv
        if draw_bottom:
            if draw_left:
                bhh[Position(x=int(rect.left), y=int(rect.bottom))] = jbv
            if draw_right:
                bhh[Position(x=int(rect.right), y=int(rect.bottom))] = jbv

    return chars, bhh


def svg(paint: Paint) -> ElementTree:
    max_pos = max(paint.keys())
    w, h = max_pos.x, max_pos.y

    # Measurements start from the top-left corner of each cell, so the width/height need be 1 unit larger for the actual content
    w += 1
    h += 1

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

    rows = defaultdict(list)
    for pos, cell in sorted(paint.items()):
        rows[pos.y].append((pos.x, cell))

    for y, cells in sorted(rows.items()):
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
                if cell.char == " ":  # optimization: don't write spaces
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
                ts.text = cell.char

    return ElementTree(element=root)
