from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache, reduce
from itertools import groupby, product
from operator import itemgetter, or_
from textwrap import dedent
from typing import Literal, assert_never
from xml.etree.ElementTree import Element, ElementTree, SubElement

from structlog import get_logger

from counterweight._utils import halve_integer
from counterweight.elements import AnyElement, CellPaint, Div, Text
from counterweight.geometry import Edge, Position, Rect
from counterweight.layout import LayoutBox, LayoutBoxDimensions, wrap_cells
from counterweight.styles import Border
from counterweight.styles.styles import BorderEdge, CellStyle, Color, Margin, Padding

logger = get_logger()


@dataclass(slots=True)
class P:
    char: str
    style: CellStyle
    z: int

    @classmethod
    @lru_cache(maxsize=2**10)
    def blank(cls, z: int) -> P:
        return cls(
            char=" ",
            style=CellStyle(background=Color.from_name("black")),
            z=z,
        )


BLANK = P.blank(z=-1_000_000)


Paint = dict[Position, P]


def combine_paints(paints: Iterable[Paint]) -> Paint:
    return reduce(or_, paints, {})


def paint_layout(layout: LayoutBox) -> Paint:
    return combine_paints(
        map(
            itemgetter(0),
            sorted(
                (paint_element(l.element, l.dims) for l in layout.walk_from_top()),
                key=lambda pz: pz[1],
            ),
        ),
    )


@lru_cache(maxsize=2**10)
def paint_bg(x_range: range, y_range: range, z: int) -> Paint:
    return {Position.flyweight(x, y): P.blank(z=z) for x, y in product(x_range, y_range)}


def paint_element(element: AnyElement, dims: LayoutBoxDimensions) -> tuple[Paint, int]:
    padding_rect, border_rect, margin_rect = dims.padding_border_margin_rects()

    m = paint_edge(element, element.style.margin, dims.margin, margin_rect)
    b = paint_border(element, element.style.border, border_rect) if element.style.border else {}
    t = paint_edge(element, element.style.padding, dims.padding, padding_rect)

    box = m | b | t

    match element:
        case Div():
            paint = box
        case Text() as e:
            paint = box | paint_text(e, dims.content)
        case _:
            raise NotImplementedError(f"Painting {element} is not implemented")

    # Drawing the background explicitly makes sure that when elements overlaps,
    # the element with lower z is actually hidden and doesn't show through.
    # However, we only want to do this for elements that actually have anything in their paint,
    # so that "anonymous" grouping elements don't hide things behind them.
    return (
        (paint_bg(margin_rect.x_range(), margin_rect.y_range(), element.style.layout.z) | paint) if paint else paint,
        element.style.layout.z,
    )


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


def paint_text(text: Text, rect: Rect) -> Paint:
    style = text.style.typography.style

    paint = {}
    lines = wrap_cells(
        cells=text.cells,
        wrap=text.style.typography.wrap,
        width=rect.width,
    )

    previous_cell_style = None

    for y, line in enumerate(lines[: rect.height], start=rect.y):
        justified_line = justify_line(line, rect.width, text.style.typography.justify)
        for x, cell in enumerate(justified_line[: rect.width], start=rect.x):
            cell_style = cell.style

            # Optimization: reuse the same merged style object if the cell style is the same object.
            # This helps when painting a lot of text with the same style.
            if cell_style is not previous_cell_style:
                merged_style = style | cell_style
                previous_cell_style = cell_style

            paint[Position.flyweight(x, y)] = P(
                char=cell.char,
                style=merged_style,  # merged_style will never be unassigned here, since we know previous_cell_style starts as None
                z=text.style.layout.z,
            )

    return paint


def paint_edge(element: AnyElement, mp: Margin | Padding, edge: Edge, rect: Rect, char: str = " ") -> Paint:
    cell_paint = P(char=char, style=CellStyle(background=mp.color), z=element.style.layout.z)

    chars = {}

    # top
    for y in range(rect.top, rect.top + edge.top):
        for x in rect.x_range():
            chars[Position.flyweight(x, y)] = cell_paint

    # bottom
    for y in range(rect.bottom, rect.bottom - edge.bottom, -1):
        for x in rect.x_range():
            chars[Position.flyweight(x, y)] = cell_paint

    # left
    for x in range(rect.left, rect.left + edge.left):
        for y in rect.y_range():
            chars[Position.flyweight(x, y)] = cell_paint

    # right
    for x in range(rect.right, rect.right - edge.right, -1):
        for y in rect.y_range():
            chars[Position.flyweight(x, y)] = cell_paint

    return chars


def paint_border(element: AnyElement, border: Border, rect: Rect) -> Paint:
    style = border.style

    bv = border.kind.value
    left = bv.left
    right = bv.right
    top = bv.top
    bottom = bv.bottom
    left_top = bv.left_top
    right_top = bv.right_top
    left_bottom = bv.left_bottom
    right_bottom = bv.right_bottom

    contract = border.contract
    chars = {}

    rect_left = rect.left
    rect_top = rect.top
    rect_right = rect.right
    rect_bottom = rect.bottom

    draw_left = BorderEdge.Left in border.edges
    draw_right = BorderEdge.Right in border.edges
    draw_top = BorderEdge.Top in border.edges
    draw_bottom = BorderEdge.Bottom in border.edges

    if contract:
        contract_top = contract if not draw_top else None
        contract_bottom = -contract if not draw_bottom else None
        contract_left = contract if not draw_left else None
        contract_right = -contract if not draw_right else None
    else:
        contract_top = contract_bottom = contract_left = contract_right = None

    v_slice = slice(contract_top, contract_bottom)
    h_slice = slice(contract_left, contract_right)

    if draw_left:
        left_paint = P(char=left, style=style, z=element.style.layout.z)
        for p in rect.left_edge()[v_slice]:
            chars[p] = left_paint

    if draw_right:
        right_paint = P(char=right, style=style, z=element.style.layout.z)
        for p in rect.right_edge()[v_slice]:
            chars[p] = right_paint

    if draw_top:
        top_paint = P(char=top, style=style, z=element.style.layout.z)
        for p in rect.top_edge()[h_slice]:
            chars[p] = top_paint

        if draw_left:
            chars[Position.flyweight(x=rect_left, y=rect_top)] = P(char=left_top, style=style, z=element.style.layout.z)
        if draw_right:
            chars[Position.flyweight(x=rect_right, y=rect_top)] = P(
                char=right_top, style=style, z=element.style.layout.z
            )

    if draw_bottom:
        bottom_paint = P(char=bottom, style=style, z=element.style.layout.z)
        for p in rect.bottom_edge()[h_slice]:
            chars[p] = bottom_paint

        if draw_left:
            chars[Position.flyweight(x=rect_left, y=rect_bottom)] = P(
                char=left_bottom, style=style, z=element.style.layout.z
            )
        if draw_right:
            chars[Position.flyweight(x=rect_right, y=rect_bottom)] = P(
                char=right_bottom, style=style, z=element.style.layout.z
            )

    return chars


def svg(paint: Paint) -> ElementTree:
    w, h = max(paint.keys())

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
            first_x, first_cell = x_cells[0]

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
