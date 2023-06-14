from __future__ import annotations

from math import ceil, floor
from typing import Literal, NamedTuple

from typing_extensions import assert_never

from reprisal.elements import Border, Div, Text


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


class Rect(NamedTuple):
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


class Edge(NamedTuple):
    left: int = 0
    right: int = 0
    top: int = 0
    bottom: int = 0


class Dimensions(NamedTuple):
    content: Rect
    margin: Edge
    border: Border | None
    padding: Edge


class LeftRight(NamedTuple):
    left: int = 0
    right: int = 0


class Widths(NamedTuple):
    width: int
    margin: LeftRight
    border: LeftRight
    padding: LeftRight


class LayoutBox(NamedTuple):
    dims: Dimensions
    type: Literal["block", "inline", "anonymous"]
    children: list[Dimensions]


def layout(element: Div | Text, containing_box: Dimensions) -> LayoutBox:
    match element.style.display:
        case "block":
            widths = calculate_widths(element.style, containing_box)
            print(widths)
        case display:
            assert_never(display)


def calculate_widths(element_style, containing_block: Dimensions) -> Widths:
    width = element_style.span.width

    margin_left = element_style.margin.left
    margin_right = element_style.margin.right

    border_left = 1 if element_style.border is not None else 0
    border_right = 1 if element_style.border is not None else 0

    padding_left = element_style.padding.left
    padding_right = element_style.padding.right

    # Add up all the widths, excluding any that can be automatically set
    # by treating them as zeros. We'll fill in their values later,
    # based on the minimum block width.
    minimum_block_width = sum(
        w if isinstance(w, int) else 0
        for w in (
            width,
            margin_left,
            margin_right,
            border_left,
            border_right,
            padding_left,
            padding_right,
        )
    )

    # This block is going to be laid out inside the content region of the containing block.
    # If it's already too wide, the content width of this box is fixed, and the margins are expandable,
    # we definitely cannot expand the margins, so set them to zero.
    if minimum_block_width > containing_block.content.width:
        if margin_left == "auto":
            margin_left = 0
        if margin_right == "auto":
            margin_right = 0

    # The underflow is how much extra space we have (it may be negative if the minimum width is too wide)
    underflow = containing_block.content.width - minimum_block_width

    match (width == "auto", margin_left == "auto", margin_right == "auto"):
        # Woops, overconstrained dimensions!
        # We have to do something, so we move the right margin, since we're effectively in left-to-right mode.
        case (False, False, False):
            margin_right = margin_right + underflow

        # If the width is not auto and only one margin is auto, put the underflow on that margin.
        case (False, True, False):
            margin_left = underflow
        case (False, False, True):
            margin_right = underflow

        # If the width is not auto and both margins are auto, divide the underflow evenly between them.
        case (False, True, True):
            margin_left, margin_right = halve_integer(underflow)

        # If the width is auto, we put all the underflow there, regardless of whether the margins are auto.
        case (True, _, _):
            # If the margins were auto, they shrink to 0.
            if margin_left == "auto":
                margin_left = 0
            if margin_right == "auto":
                margin_right = 0

            if underflow > 0:
                width = underflow
            else:
                # Oops, we overflowed! Set the width to 0 and adjust the right margin instead.
                width = 0
                margin_right = margin_right + underflow

    return Widths(
        width=width,
        margin=LeftRight(left=margin_left, right=margin_right),
        border=LeftRight(left=border_left, right=border_right),
        padding=LeftRight(left=padding_left, right=padding_right),
    )


def halve_integer(x: int) -> tuple[int, int]:
    """Halve an integer, accounting for odd integers by making the second "half" larger by one than the first "half"."""
    half = x / 2
    return floor(half), ceil(half)


#
#
# def compose(
#     element: Div | Text,
#     region: Region,
# ):
#     margin_comp, inside_margin = edge(edge=element.style.margin, region=region)
#     border_comp, inside_border = border(border=element.style.border, region=inside_margin)
#     padding_comp, inside_padding = edge(edge=element.style.padding, region=inside_border)
#
#     if isinstance(element, Text):
#         # this is implicitly like width = "auto" because we use the full horizontal region
#         # what is height implicitly here? not auto because that would shrink, it's more like 100%
#         element_comp = text(text=element, region=inside_padding)
#     elif isinstance(element, Div):
#         element_comp = {}
#         for child in element.children:
#             child_span = child.style.span
#             if child_span.width == "fill":
#                 child_width = inside_padding.width
#             elif isinstance(child_span.width, Cells):
#                 child_width = child_span.width
#             else:
#                 assert_never(child_span.width)
#
#             if child_span.height == "fit":
#                 if isinstance(child, Text):
#                     child_height = lines_at_width(child.text, width=child_width) + child.style.box_height()
#                     print(child_height)
#                 elif isinstance(child, Div):
#                     # how do you drill through the tree here to fit the height?
#                     # I guess the problem with this model is that you kind of need to
#                     # figure out all the widths first, then use those to calculate the heights
#                     # then go back and actually render everything
#                     raise Exception()
#
#             elif child_span.height == "fill":
#                 child_height = inside_padding.height
#             elif isinstance(child_span.height, Cells):
#                 child_height = child_span.height
#             else:
#                 assert_never(child_span.height)
#
#             child_region = Region(
#                 left=inside_padding.left,
#                 top=inside_padding.top,
#                 right=inside_padding.left + child_width,
#                 bottom=inside_padding.top + child_height - 1,  # I don't understand this off-by-one...
#             )
#
#             element_comp |= compose(child, child_region)
#             inside_padding = Region(
#                 left=inside_padding.left,
#                 right=inside_padding.right,
#                 top=child_region.bottom + 1,
#                 bottom=inside_padding.bottom,
#             )
#     else:
#         assert_never(element)
#
#     return margin_comp | border_comp | padding_comp | element_comp
#
#
# PLACEHOLDER = " ..."
#
#
# def lines_at_width(text: str, width: int) -> int:
#     wrapper = TextWrapper(width=width, max_lines=None, placeholder=PLACEHOLDER)
#     return len(wrapper.wrap(text))
#
#
# def text(text: Text, region: Region):
#     chars = {}
#     wrapper = TextWrapper(width=region.width, max_lines=region.height, placeholder=PLACEHOLDER)
#     wrapped = wrapper.wrap(text.text)
#     for y, line in enumerate(wrapped):
#         for x, char in enumerate(line):
#             chars[Position(x, y).shift(x=region.left, y=region.top)] = char
#
#     return chars
#
#
# def edge(edge: Edge, region: Region, char: str = " "):
#     chars = {}
#
#     # top
#     for y in range(region.top, region.top + edge.top):
#         for x in region.x_range():
#             chars[Position(x, y)] = char
#
#     # bottom
#     for y in range(region.bottom, region.bottom - edge.bottom, -1):
#         for x in region.x_range():
#             chars[Position(x, y)] = char
#
#     # left
#     for x in range(region.left, region.left + edge.left):
#         for y in region.y_range():
#             chars[Position(x, y)] = char
#
#     # right
#     for x in range(region.right, region.right - edge.right, -1):
#         for y in region.y_range():
#             chars[Position(x, y)] = char
#
#     return chars, Region(
#         left=region.left + edge.left,
#         right=region.right - edge.right,
#         top=region.top + edge.top,
#         bottom=region.bottom - edge.bottom,
#     )
#
#
# def border(border: Border, region: Region):
#     chars = {}
#
#     # top
#     for x in region.x_range():
#         chars[Position(x, region.top)] = border.kind.value[1]
#
#     # bottom
#     for x in region.x_range():
#         chars[Position(x, region.bottom)] = border.kind.value[1]
#
#     # left
#     for y in region.y_range():
#         chars[Position(region.left, y)] = border.kind.value[0]
#
#     # right
#     for y in region.y_range():
#         chars[Position(region.right, y)] = border.kind.value[0]
#
#     chars[Position(x=region.left, y=region.top)] = border.kind.value[2]
#     chars[Position(x=region.right, y=region.top)] = border.kind.value[3]
#     chars[Position(x=region.left, y=region.bottom)] = border.kind.value[4]
#     chars[Position(x=region.right, y=region.bottom)] = border.kind.value[5]
#
#     return (
#         chars,
#         Region(
#             left=region.left + 1,
#             right=region.right - 1,
#             top=region.top + 1,
#             bottom=region.bottom - 1,
#         ),
#     )
#
#
# def debug(chars, region) -> str:
#     lines = []
#     for y in region.y_range():
#         line = []
#         for x in region.x_range():
#             line.append(chars.get(Position(x, y), " "))
#
#         lines.append(line)
#
#     return "\n".join("".join(line) for line in lines)
