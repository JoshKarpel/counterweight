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
    x: int
    y: int
    width: int
    height: int

    def span(self) -> Span:
        return Span(width=self.width, height=self.height)


class Composition(NamedTuple):
    span: Span
    chars: dict[Position, str]

    def underlay(self, composition: Composition, region: Region) -> Composition:
        overlay = {pos.shift(region.x, region.y): c for pos, c in composition.chars.items()}

        return Composition(chars=self.chars | overlay, span=self.span)


def compose(
    element: Text,
    span: Span,
) -> Composition:
    base = Composition(chars={}, span=span)

    margin_comp, inside_margin = edge(edge=element.style.margin, span=span)
    border_comp, inside_border = border(border=element.style.border, span=inside_margin.span())
    padding_comp, inside_padding = edge(edge=element.style.padding, span=inside_border.span())
    element_comp, inside_element = text(element, inside_padding.span())

    with_margin = base.underlay(margin_comp, inside_margin)
    with_border = with_margin.underlay(border_comp, inside_border)
    with_padding = with_border.underlay(padding_comp, inside_padding)
    with_padding.underlay(element_comp, inside_element)

    print(inside_margin)
    print(inside_border)
    print(inside_padding)

    return with_padding


def text(
    text: Text,
    span: Span,
) -> tuple[Composition, Region]:
    chars = {}
    wrapper = TextWrapper(width=span.width, max_lines=span.height)
    wrapped = wrapper.wrap(text.text)
    for y, line in enumerate(wrapped):
        for x, char in enumerate(line):
            chars[Position(x, y)] = char

    return (
        Composition(
            span=span,
            chars=chars,
        ),
        Region(
            x=1,
            y=1,
            width=span.width - 1,
            height=span.height - 1,
        ),
    )


def edge(edge: Edge, span: Span) -> tuple[Composition, Region]:
    chars = {}

    for y in range(edge.top):
        for x in range(span.width):
            chars[Position(x, y)] = " "

    for y in range(edge.bottom):
        for x in range(span.width):
            chars[Position(x, span.height - y - 1)] = " "

    for x in range(edge.left):
        for y in range(span.height):
            chars[Position(x, y)] = " "

    for x in range(edge.right):
        for y in range(span.height):
            chars[Position(span.width - x - 1, y)] = " "

    return (
        Composition(
            chars=chars,
            span=span,
        ),
        Region(
            x=edge.left,
            y=edge.top,
            width=span.width - (edge.left + edge.right),
            height=span.height - (edge.top + edge.bottom),
        ),
    )


def border(border: Border, span: Span) -> tuple[Composition, Region]:
    chars = {}

    for x in range(span.width):
        chars[Position(x, 0)] = "T"
        chars[Position(x, span.height - 1)] = "B"

    for y in range(span.height):
        chars[Position(0, y)] = "L"
        chars[Position(span.width - 1, y)] = "R"

    return (
        Composition(
            chars=chars,
            span=span,
        ),
        Region(
            x=1,
            y=1,
            width=span.width - 1,
            height=span.height - 1,
        ),
    )


def debug(comp: Composition) -> str:
    lines = []
    for y in range(comp.span.height):
        line = []

        for x in range(comp.span.width):
            line.append(comp.chars.get(Position(x, y), " "))

        lines.append(line)

    return "\n".join("".join(line) for line in lines)
