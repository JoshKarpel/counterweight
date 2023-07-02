from __future__ import annotations

from pydantic import Field
from structlog import get_logger

from reprisal.components import Div, Element, Paragraph
from reprisal.layout import BoxDimensions, Edge, LayoutBox, Position, Rect
from reprisal.styles import Border
from reprisal.styles.styles import CellStyle, Margin, Padding
from reprisal.types import FrozenForbidExtras

logger = get_logger()


class CellPaint(FrozenForbidExtras):
    char: str
    style: CellStyle = Field(default_factory=CellStyle)


Paint = dict[Position, CellPaint]


def paint_layout(layout: LayoutBox) -> Paint:
    painted = paint_element(layout.element, layout.dims)
    for child in layout.children:
        painted |= paint_layout(child)  # no Z-level support! need something like a chainmap
    return painted


def paint_element(element: Element, dims: BoxDimensions) -> Paint:
    m = paint_edge(element.style.margin, dims.margin, dims.margin_rect())
    b = paint_border(element.style.border, dims.border_rect()) if element.style.border else {}
    t = paint_edge(element.style.padding, dims.padding, dims.padding_rect())

    box = m | b | t

    match element:
        case Div():
            return box
        case Paragraph() as e:
            return paint_paragraph(e, dims.content) | box
        case _:
            raise NotImplementedError(f"Painting {element} is not implemented")


def paint_paragraph(paragraph: Paragraph, rect: Rect) -> Paint:
    style = paragraph.style.text.style.copy(deep=True)
    return {Position(x, rect.y): CellPaint(char=c, style=style) for c, x in zip(paragraph.content, rect.x_range())}


def paint_edge(mp: Margin | Padding, edge: Edge, rect: Rect, char: str = " ") -> Paint:
    style = CellStyle(background=mp.color)

    chars = {}
    cell_paint = CellPaint(char=char, style=style)

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
    style = border.style.copy(deep=True)
    left, right, top, bottom, left_top, right_top, left_bottom, right_bottom = border.kind.value
    chars = {}

    for y in rect.y_range():
        chars[Position(rect.left, y)] = CellPaint(char=left, style=style)

    for y in rect.y_range():
        chars[Position(rect.right, y)] = CellPaint(char=right, style=style)

    for x in rect.x_range():
        chars[Position(x, rect.top)] = CellPaint(char=top, style=style)

    for x in rect.x_range():
        chars[Position(x, rect.bottom)] = CellPaint(char=bottom, style=style)

    chars[Position(x=rect.left, y=rect.top)] = CellPaint(char=left_top, style=style)
    chars[Position(x=rect.right, y=rect.top)] = CellPaint(char=right_top, style=style)
    chars[Position(x=rect.left, y=rect.bottom)] = CellPaint(char=left_bottom, style=style)
    chars[Position(x=rect.right, y=rect.bottom)] = CellPaint(char=right_bottom, style=style)

    return chars


def debug_paint(paint: dict[Position, CellPaint], rect: Rect) -> str:
    lines = []
    for y in rect.y_range():
        line = []
        for x in rect.x_range():
            line.append(paint.get(Position(x, y), CellPaint(char=" ")).char)

        lines.append(line)

    return "\n".join("".join(line) for line in lines)
