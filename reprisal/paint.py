from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Literal

from pydantic import Field
from structlog import get_logger

from reprisal._utils import wrap_text
from reprisal.components import AnyElement, Div, Text
from reprisal.geometry import Position
from reprisal.layout import BoxDimensions, Edge, LayoutBox, Rect
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


STR_JUSTIFIERS: Mapping[Literal["left", "right", "center"], Callable[[str, int], str]] = {
    "left": str.ljust,
    "right": str.rjust,
    "center": str.center,
}


def paint_text(paragraph: Text, rect: Rect) -> Paint:
    style = paragraph.style.typography.style
    justifier = STR_JUSTIFIERS[paragraph.style.typography.justify]

    paint = {}
    lines = wrap_text(
        paragraph.content,
        wrap=paragraph.style.typography.wrap,
        width=rect.width,
    )

    for y, line in enumerate(lines[: rect.height], start=rect.y):
        justified_line = justifier(line, rect.width)
        for x, char in enumerate(justified_line[: rect.width], start=rect.x):
            paint[Position(x, y)] = CellPaint(char=char, style=style)

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
    left, right, top, bottom, left_top, right_top, left_bottom, right_bottom = border.kind.value  # type: ignore[misc]
    chars = {}

    left_paint = CellPaint(char=left, style=style)
    for p in rect.left_edge():
        chars[p] = left_paint

    right_paint = CellPaint(char=right, style=style)
    for p in rect.right_edge():
        chars[p] = right_paint

    top_paint = CellPaint(char=top, style=style)
    for p in rect.top_edge():
        chars[p] = top_paint

    bottom_paint = CellPaint(char=bottom, style=style)
    for p in rect.bottom_edge():
        chars[p] = bottom_paint

    rect_left = rect.left
    rect_top = rect.top
    rect_right = rect.right
    rect_bottom = rect.bottom
    chars[Position(x=rect_left, y=rect_top)] = CellPaint(char=left_top, style=style)
    chars[Position(x=rect_right, y=rect_top)] = CellPaint(char=right_top, style=style)
    chars[Position(x=rect_left, y=rect_bottom)] = CellPaint(char=left_bottom, style=style)
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
