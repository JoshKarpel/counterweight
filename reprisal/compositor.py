from __future__ import annotations

from textwrap import TextWrapper
from typing import NamedTuple

from typing_extensions import assert_never

from reprisal.elements import Border, Cells, Div, Edge, Text


class Position(NamedTuple):
    x: int
    y: int

    def shift(self, x: int, y: int) -> Position:
        return Position(self.x + x, self.y + y)


class Region(NamedTuple):
    left: int
    right: int
    top: int
    bottom: int

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


# https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_flow_layout/Block_and_inline_layout_in_normal_flow
# https://www.w3.org/TR/CSS2/visudet.html#blockwidth
def compose(
    element: Div | Text,
    region: Region,
):
    margin_comp, inside_margin = edge(edge=element.style.margin, region=region)
    border_comp, inside_border = border(border=element.style.border, region=inside_margin)
    padding_comp, inside_padding = edge(edge=element.style.padding, region=inside_border)

    if isinstance(element, Text):
        # this is implicitly like width = "auto" because we use the full horizontal region
        # what is height implicitly here? not auto because that would shrink, it's more like 100%
        element_comp = text(text=element, region=inside_padding)
    elif isinstance(element, Div):
        element_comp = {}
        for child in element.children:
            child_span = child.style.span
            if child_span.width == "fill":
                child_width = inside_padding.width
            elif isinstance(child_span.width, Cells):
                child_width = child_span.width.cells
            else:
                assert_never(child_span.width)

            if child_span.height == "fit":
                if isinstance(child, Text):
                    child_height = lines_at_width(child.text, width=child_width) + child.style.box_height()
                elif isinstance(child, Div):
                    # how do you drill through the tree here to fit the height?
                    # I guess the problem with this model is that you kind of need to
                    # figure out all the widths first, then use those to calculate the heights
                    # then go back and actually render everything
                    raise Exception()

            elif child_span.height == "fill":
                child_height = inside_padding.height
            elif isinstance(child_span.height, Cells):
                child_height = child_span.height.cells
            else:
                assert_never(child_span.height)

            child_region = Region(
                left=inside_padding.left,
                top=inside_padding.top,
                right=inside_padding.left + child_width,
                bottom=inside_padding.top + child_height,
            )

            element_comp |= compose(child, child_region)
    else:
        assert_never(element)

    return margin_comp | border_comp | padding_comp | element_comp


PLACEHOLDER = " ..."


def lines_at_width(text: str, width: int) -> int:
    wrapper = TextWrapper(width=width, max_lines=None, placeholder=PLACEHOLDER)
    return len(wrapper.wrap(text))


def text(text: Text, region: Region):
    chars = {}
    wrapper = TextWrapper(width=region.width, max_lines=region.height, placeholder=PLACEHOLDER)
    wrapped = wrapper.wrap(text.text)
    for y, line in enumerate(wrapped):
        for x, char in enumerate(line):
            chars[Position(x, y).shift(x=region.left, y=region.top)] = char

    return chars


def edge(edge: Edge, region: Region, char: str = " "):
    chars = {}

    # top
    for y in range(region.top, region.top + edge.top):
        for x in region.x_range():
            chars[Position(x, y)] = char

    # bottom
    for y in range(region.bottom, region.bottom - edge.bottom, -1):
        for x in region.x_range():
            chars[Position(x, y)] = char

    # left
    for x in range(region.left, region.left + edge.left):
        for y in region.y_range():
            chars[Position(x, y)] = char

    # right
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

    # top
    for x in region.x_range():
        chars[Position(x, region.top)] = border.kind.value[1]

    # bottom
    for x in region.x_range():
        chars[Position(x, region.bottom)] = border.kind.value[1]

    # left
    for y in region.y_range():
        chars[Position(region.left, y)] = border.kind.value[0]

    # right
    for y in region.y_range():
        chars[Position(region.right, y)] = border.kind.value[0]

    chars[Position(x=region.left, y=region.top)] = border.kind.value[2]
    chars[Position(x=region.right, y=region.top)] = border.kind.value[3]
    chars[Position(x=region.left, y=region.bottom)] = border.kind.value[4]
    chars[Position(x=region.right, y=region.bottom)] = border.kind.value[5]

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
