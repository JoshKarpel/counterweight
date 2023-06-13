from __future__ import annotations

from textwrap import TextWrapper
from typing import NamedTuple

from reprisal.elements import Border, Edge, Text


class Position(NamedTuple):
    x: int
    y: int

    def shift(self, x: int, y: int) -> Position:
        return Position(self.x + x, self.y + y)


class Span(NamedTuple):
    width: int
    height: int


class Region(NamedTuple):
    left: int
    right: int
    top: int
    bottom: int

    def span(self) -> Span:
        return Span(width=self.width, height=self.height)

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def x_range(self) -> list[int]:
        return list(range(self.left, self.right + 1))

    def y_range(self) -> list[int]:
        return list(range(self.top, self.bottom + 1))

    def origin(self) -> Position:
        return Position(x=self.left, y=self.top)


def compose(
    element: Text,
    region: Region,
):
    margin_comp, inside_margin = edge(edge=element.style.margin, region=region, char="M")
    border_comp, inside_border = border(border=element.style.border, region=inside_margin)
    padding_comp, inside_padding = edge(edge=element.style.padding, region=inside_border, char="P")
    element_comp = text(text=element, region=inside_padding)

    return margin_comp | border_comp | padding_comp | element_comp


def text(text: Text, region: Region):
    chars = {}
    wrapper = TextWrapper(width=region.width, max_lines=region.height)
    wrapped = wrapper.wrap(text.text)
    for y, line in enumerate(wrapped):
        for x, char in enumerate(line):
            chars[Position(x, y).shift(x=region.left, y=region.top)] = char

    return chars


def edge(edge: Edge, region: Region, char: str = " "):
    chars = {}

    for y in range(region.top, region.top + edge.top):
        for x in region.x_range():
            chars[Position(x, y)] = char

    for y in range(region.bottom, region.bottom - edge.bottom, -1):
        for x in region.x_range():
            chars[Position(x, y)] = char

    for x in range(region.left, region.left + edge.left):
        for y in region.y_range():
            chars[Position(x, y)] = char

    for x in range(region.right, region.right - edge.right, -1):
        for y in region.y_range():
            chars[Position(x, y)] = char

    return chars, Region(
        left=region.left + edge.left,
        right=region.right - edge.right,
        top=region.top + edge.top,
        bottom=region.bottom - edge.bottom,
    )


def border(border: Border, region: Region):
    chars = {}

    for x in region.x_range():
        chars[Position(x, region.top)] = "T"

    for x in region.x_range():
        chars[Position(x, region.bottom)] = "B"

    for y in region.y_range():
        chars[Position(region.left, y)] = "L"

    for y in region.y_range():
        chars[Position(region.right, y)] = "R"

    for x in (region.left, region.right):
        for y in (region.top, region.bottom):
            chars[Position(x, y)] = "C"

    return (
        chars,
        Region(
            left=region.left + 1,
            right=region.right - 1,
            top=region.top + 1,
            bottom=region.bottom - 1,
        ),
    )


def debug(chars, region) -> str:
    lines = []
    for y in region.y_range():
        line = []
        for x in region.x_range():
            line.append(chars.get(Position(x, y), " "))

        lines.append(line)

    return "\n".join("".join(line) for line in lines)
