from __future__ import annotations

from textwrap import dedent
from typing import Literal, assert_never
from xml.etree.ElementTree import Element, SubElement, indent

from structlog import get_logger

from counterweight._utils import halve_integer
from counterweight.cell_paint import CellPaint, wrap_cells
from counterweight.elements import AnyElement, Div, Text
from counterweight.geometry import Position
from counterweight.layout import BoxDimensions, Edge, LayoutBox, Rect
from counterweight.styles import Border
from counterweight.styles.styles import BorderEdge, CellStyle, Color, Margin, Padding

logger = get_logger()

Paint = dict[Position, CellPaint]


def paint_layout(layout: LayoutBox) -> Paint:
    painted = paint_element(layout.element, layout.dims)
    for child in layout.children:
        painted |= paint_layout(child)  # no Z-level support! need something like a chainmap
    return painted


def paint_element(element: AnyElement, dims: BoxDimensions) -> Paint:
    padding_rect, border_rect, margin_rect = dims.padding_border_margin_rects()
    m = paint_edge(element.style.margin, dims.margin, margin_rect)
    b = paint_border(element.style.border, border_rect) if element.style.border else {}
    t = paint_edge(element.style.padding, dims.padding, padding_rect)

    box = m | b | t

    match element:
        case Div():
            return box
        case Text() as e:
            return paint_text(e, dims.content) | box
        case _:
            raise NotImplementedError(f"Painting {element} is not implemented")


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

    for y, line in enumerate(lines[: rect.height], start=rect.y):
        justified_line = justify_line(line, rect.width, text.style.typography.justify)
        for x, cell in enumerate(justified_line[: rect.width], start=rect.x):
            pos = Position(x, y)
            s = style | cell.style
            paint[pos] = CellPaint(char=cell.char, style=s)

    return paint


def paint_edge(mp: Margin | Padding, edge: Edge, rect: Rect, char: str = " ") -> Paint:
    cell_paint = CellPaint(char=char, style=CellStyle(background=mp.color))

    chars = {}

    # top
    for y in range(rect.top, rect.top + edge.top):
        for x in rect.x_range():
            chars[Position(x, y)] = cell_paint

    # bottom
    for y in range(rect.bottom, rect.bottom - edge.bottom, -1):
        for x in rect.x_range():
            chars[Position(x, y)] = cell_paint

    # left
    for x in range(rect.left, rect.left + edge.left):
        for y in rect.y_range():
            chars[Position(x, y)] = cell_paint

    # right
    for x in range(rect.right, rect.right - edge.right, -1):
        for y in rect.y_range():
            chars[Position(x, y)] = cell_paint

    return chars


def paint_border(border: Border, rect: Rect) -> Paint:
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
        left_paint = CellPaint(char=left, style=style)
        for p in rect.left_edge()[v_slice]:
            chars[p] = left_paint

    if draw_right:
        right_paint = CellPaint(char=right, style=style)
        for p in rect.right_edge()[v_slice]:
            chars[p] = right_paint

    if draw_top:
        top_paint = CellPaint(char=top, style=style)
        for p in rect.top_edge()[h_slice]:
            chars[p] = top_paint

    if draw_bottom:
        bottom_paint = CellPaint(char=bottom, style=style)
        for p in rect.bottom_edge()[h_slice]:
            chars[p] = bottom_paint

    if draw_top:
        if draw_left:
            chars[Position(x=rect_left, y=rect_top)] = CellPaint(char=left_top, style=style)
        if draw_right:
            chars[Position(x=rect_right, y=rect_top)] = CellPaint(char=right_top, style=style)

    if draw_bottom:
        if draw_left:
            chars[Position(x=rect_left, y=rect_bottom)] = CellPaint(char=left_bottom, style=style)
        if draw_right:
            chars[Position(x=rect_right, y=rect_bottom)] = CellPaint(char=right_bottom, style=style)

    return chars


def debug_paint(paint: dict[Position, CellPaint], rect: Rect) -> str:
    lines = []
    for y in rect.y_range():
        line = []
        for x in rect.x_range():
            line.append(paint.get(Position(x, y), CellPaint(char=" ")).char)

        lines.append(line)

    return "\n".join("".join(line) for line in lines)


def svg(paint: Paint) -> Element:
    w, h = max(paint.keys())

    # Measurements start from the top-left corner of each cell, so the width/height need be 1 unit larger for the actual content
    w += 1
    h += 1

    x_mul = 0.55  # x coordinates get cut roughly in half because monospace cells are twice as tall as they are wide
    y_mul = 1

    fmt = "0.6f"
    unit = "em"

    root = Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": f"{w * x_mul:{fmt}}{unit}",
            "height": f"{w * y_mul:{fmt}}{unit}",
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
        {},
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
            "font-family": "monospace",
        },
    )

    # Sort by y, then x, so that the SVG is written top to bottom, left to right
    for pos, cell in sorted(paint.items(), key=lambda pos_cell: (pos_cell[0].y, pos_cell[0].x)):
        # black is the default background color, so don't write it (optimization)
        if cell.style.background != Color.from_name("black"):
            SubElement(
                background_root,
                "rect",
                {
                    "x": f"{pos.x * x_mul:{fmt}}{unit}",
                    "y": f"{pos.y * y_mul:{fmt}}{unit}",
                    "width": f"{1.05 * x_mul:{fmt}}{unit}",  # go over the edge a bit on the right to cover gaps
                    "height": f"{1 * y_mul:{fmt}}{unit}",
                    "fill": cell.style.background.hex,
                },
            )

        ts = SubElement(
            text_root,
            "tspan",
            {
                "x": f"{pos.x * x_mul:{fmt}}{unit}",
                "y": f"{pos.y * y_mul:{fmt}}{unit}",
                "fill": cell.style.foreground.hex,  # text color
            },
        )
        ts.text = cell.char

    indent(root)

    return root
