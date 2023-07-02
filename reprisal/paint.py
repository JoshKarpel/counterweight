from __future__ import annotations

from pydantic import Field
from pydantic.color import Color

from reprisal.components import Div, Element, Text
from reprisal.layout import BoxDimensions, Edge, LayoutBox, Position, Rect
from reprisal.styles import Border
from reprisal.types import FrozenForbidExtras


class CellStyle(FrozenForbidExtras):
    fg: Color = Field(default=Color("white"))
    bg: Color = Field(default=Color("black"))
    bold: bool = False
    dim: bool = False
    italic: bool = False


class CellPaint(FrozenForbidExtras):
    char: str
    style: CellStyle = Field(default_factory=CellStyle)


Paint = dict[Position, CellPaint]


def paint(layout: LayoutBox) -> Paint:
    painted = paint_element(layout.element, layout.dims)
    for child in layout.children:
        painted |= paint(child)  # no Z-level support! need something like a chainmap
    return painted


def paint_element(element: Element, dims: BoxDimensions) -> Paint:
    m = paint_edge(dims.margin, dims.margin_rect())
    b = (
        paint_border(element.style.border, dims.border_rect(), style=CellStyle(fg=element.style.border_color))
        if element.style.border
        else {}
    )
    t = paint_edge(dims.padding, dims.padding_rect())

    box = m | b | t

    match element:
        case Div():
            return box
        case Text() as e:
            return paint_text(e, dims.content) | box
        case _:
            raise NotImplementedError(f"Painting {element} is not implemented")


def paint_text(text: Text, rect: Rect) -> Paint:
    return {Position(x, rect.y): CellPaint(char=c) for c, x in zip(text.text, rect.x_range())}


def paint_edge(edge: Edge, rect: Rect, char: str = " ") -> Paint:
    chars = {}

    # top
    for y in range(rect.top, rect.top + edge.top):
        for x in rect.x_range():
            chars[Position(x, y)] = CellPaint(char=char)

    # bottom
    for y in range(rect.bottom, rect.bottom - edge.bottom, -1):
        for x in rect.x_range():
            chars[Position(x, y)] = CellPaint(char=char)

    # left
    for x in range(rect.left, rect.left + edge.left):
        for y in rect.y_range():
            chars[Position(x, y)] = CellPaint(char=char)

    # right
    for x in range(rect.right, rect.right - edge.right, -1):
        for y in rect.y_range():
            chars[Position(x, y)] = CellPaint(char=char)

    return chars


def paint_border(border: Border, rect: Rect, style: CellStyle) -> Paint:
    chars = {}

    # left
    for y in rect.y_range():
        chars[Position(rect.left, y)] = CellPaint(char=border.kind.value[0], style=style)

    # right
    for y in rect.y_range():
        chars[Position(rect.right, y)] = CellPaint(char=border.kind.value[1], style=style)

    # top
    for x in rect.x_range():
        chars[Position(x, rect.top)] = CellPaint(char=border.kind.value[2], style=style)

    # bottom
    for x in rect.x_range():
        chars[Position(x, rect.bottom)] = CellPaint(char=border.kind.value[3], style=style)

    chars[Position(x=rect.left, y=rect.top)] = CellPaint(char=border.kind.value[4], style=style)
    chars[Position(x=rect.right, y=rect.top)] = CellPaint(char=border.kind.value[5], style=style)
    chars[Position(x=rect.left, y=rect.bottom)] = CellPaint(char=border.kind.value[6], style=style)
    chars[Position(x=rect.right, y=rect.bottom)] = CellPaint(char=border.kind.value[7], style=style)

    return chars


def debug_paint(paint: dict[Position, CellPaint], rect: Rect) -> str:
    lines = []
    for y in rect.y_range():
        line = []
        for x in rect.x_range():
            line.append(paint.get(Position(x, y), CellPaint(char=" ")).char)

        lines.append(line)

    return "\n".join("".join(line) for line in lines)
