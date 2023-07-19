from __future__ import annotations

from collections.abc import Iterator
from typing import NamedTuple

from more_itertools import take
from pydantic import Field, NonNegativeInt
from structlog import get_logger

from reprisal._utils import halve_integer, partition_int, wrap_text
from reprisal.components import AnyElement, Component, Element
from reprisal.types import ForbidExtras

logger = get_logger()


class Position(NamedTuple):
    x: int
    y: int


class Rect(ForbidExtras):
    x: int = Field(default=0)
    y: int = Field(default=0)
    width: NonNegativeInt = Field(default=0)
    height: NonNegativeInt = Field(default=0)

    def expand_by(self, edge: Edge) -> Rect:
        return Rect(
            x=self.x - edge.left,
            y=self.y - edge.top,
            width=self.width + edge.left + edge.right,
            height=self.height + edge.top + edge.bottom,
        )

    def x_range(self) -> range:
        return range(self.x, self.x + self.width)

    def y_range(self) -> range:
        return range(self.y, self.y + self.height)

    @property
    def left(self) -> int:
        return self.x

    @property
    def right(self) -> int:
        return self.x + self.width - 1

    @property
    def top(self) -> int:
        return self.y

    @property
    def bottom(self) -> int:
        return self.y + self.height - 1

    def left_edge(self) -> list[Position]:
        left = self.left
        return [Position(left, y) for y in self.y_range()]

    def right_edge(self) -> list[Position]:
        right = self.right
        return [Position(right, y) for y in self.y_range()]

    def top_edge(self) -> list[Position]:
        top = self.top
        return [Position(x, top) for x in self.x_range()]

    def bottom_edge(self) -> list[Position]:
        bottom = self.bottom
        return [Position(x, bottom) for x in self.x_range()]

    def __contains__(self, item: object) -> bool:
        if isinstance(item, Position):
            return item.x in self.x_range() and item.y in self.y_range()
        else:
            return False


class Edge(ForbidExtras):
    left: int = Field(default=0)
    right: int = Field(default=0)
    top: int = Field(default=0)
    bottom: int = Field(default=0)


class BoxDimensions(ForbidExtras):
    content: Rect = Field(default_factory=Rect)
    margin: Edge = Field(default_factory=Edge)
    border: Edge = Field(default_factory=Edge)
    padding: Edge = Field(default_factory=Edge)

    def padding_rect(self) -> Rect:
        return self.content.expand_by(self.padding)

    def border_rect(self) -> Rect:
        return self.padding_rect().expand_by(self.border)

    def margin_rect(self) -> Rect:
        return self.border_rect().expand_by(self.margin)

    def padding_border_margin_rects(self) -> tuple[Rect, Rect, Rect]:
        padding = self.content.expand_by(self.padding)
        border = padding.expand_by(self.border)
        margin = border.expand_by(self.margin)
        return padding, border, margin

    def left_edge_width(self) -> int:
        return self.margin.left + self.border.left + self.padding.left

    def right_edge_width(self) -> int:
        return self.margin.right + self.border.right + self.padding.right

    def top_edge_width(self) -> int:
        return self.margin.top + self.border.top + self.padding.top

    def bottom_edge_width(self) -> int:
        return self.margin.bottom + self.border.bottom + self.padding.bottom

    def horizontal_edge_width(self) -> int:
        return self.left_edge_width() + self.right_edge_width()

    def vertical_edge_width(self) -> int:
        return self.top_edge_width() + self.bottom_edge_width()

    def width(self) -> int:
        return self.content.width + self.horizontal_edge_width()

    def height(self) -> int:
        return self.content.height + self.vertical_edge_width()


class LayoutBox(ForbidExtras):
    element: AnyElement
    dims: BoxDimensions = Field(default_factory=BoxDimensions)
    children: list[LayoutBox] = Field(default_factory=list)

    def walk_from_bottom(self) -> Iterator[Element]:
        for child in self.children:
            yield from child.walk_from_bottom()
        yield self.element

    def walk_levels(self) -> Iterator[LayoutBox]:
        yield self

        next_level: list[LayoutBox] = []
        for child in self.children:
            c = child.walk_levels()
            yield take(1, c)[0]
            next_level.extend(c)
        yield from next_level

    def compute_layout(self) -> None:
        top_down = list(self.walk_levels())

        for node in reversed(top_down):
            node.first_pass()

        for node in top_down:
            node.second_pass()

    def first_pass(self) -> None:
        style = self.element.style
        display = style.display

        # transfer margin/border/padding to dimensions
        # TODO handle "auto" here -> 0, or maybe get rid of auto margins/padding?
        self.dims.margin.top = style.margin.top
        self.dims.margin.bottom = style.margin.bottom
        self.dims.margin.left = style.margin.left
        self.dims.margin.right = style.margin.right

        self.dims.border.top = 1 if style.border else 0
        self.dims.border.bottom = 1 if style.border else 0
        self.dims.border.left = 1 if style.border else 0
        self.dims.border.right = 1 if style.border else 0

        self.dims.padding.top = style.padding.top
        self.dims.padding.bottom = style.padding.bottom
        self.dims.padding.left = style.padding.left
        self.dims.padding.right = style.padding.right

        if style.span.width != "auto":  # i.e., if it's a fixed width
            self.dims.content.width = style.span.width
        if style.span.height != "auto":  # i.e., if it's a fixed height
            self.dims.content.height = style.span.height

        # # text boxes with auto width get their width from their content (no wrapping)
        # # TODO: revisit this, kind of want to differentiate between "auto" and "flex" here, or maybe width=Weight(1) ?
        # if style.span.width == "auto" and self.element.type == "text":
        #     self.dims.content.width = len(self.element.content)

        # grow to fit children with fixed sizes
        if style.span.width == "auto":
            for child_box in self.children:
                child_element = child_box.element
                child_style = child_element.style

                child_display = child_style.display

                if child_style.span.width != "auto":
                    if child_display.position == "relative":
                        if display.direction == "row":
                            # We are growing the box to the right
                            self.dims.content.width += child_box.dims.width()
                        elif display.direction == "column":
                            # The box is as wide as its widest child
                            self.dims.content.width = max(self.dims.content.width, child_box.dims.width())

        if style.span.height == "auto":
            for child_box in self.children:
                child_element = child_box.element
                child_style = child_element.style

                child_display = child_style.display
                if child_display.type != "flex":
                    raise Exception("Flex children must be flex")

                if child_style.span.height != "auto":
                    if child_display.position == "relative":
                        if display.direction == "column":
                            # We are growing the box downward
                            self.dims.content.height += child_box.dims.height()
                        elif display.direction == "row":
                            # The box is as tall as its tallest child
                            self.dims.content.height = max(self.dims.content.height, child_box.dims.height())

    def second_pass(self) -> None:
        # TODO: positions

        # TODO: align self

        # calculate available width for children, minus how much they use,
        # then divide that between them based on the content justification
        # We are in the parent, justifying the children!
        style = self.element.style
        display = style.display

        available_width = self.dims.content.width
        available_height = self.dims.content.height

        relative_children = [child for child in self.children if child.element.style.display.position == "relative"]
        relative_children_with_weights = [
            child for child in relative_children if child.element.style.display.weight is not None
        ]
        num_relative_children = len(relative_children)
        # subtract off fixed-width/height children from what's available to flex
        for child in relative_children:
            if child.element.style.display.weight is None:
                if display.direction == "row":
                    available_width -= child.dims.width()
                elif display.direction == "column":
                    available_height -= child.dims.height()

        logger.debug("available_width", t=self.element.type, available_width=available_width)

        # when does flex element width get set for space-* justify?
        # space-* justify assumes children have fixed widths! it distributes the leftover space
        # but what if you DO put flex children in there? who sets their widths?
        # TODO: note that if a child element has a weight, a fixed width/height would be overriden here by the parent
        if relative_children_with_weights and display.justify_children not in (
            "space-between",
            "space-around",
            "space-evenly",
        ):
            weights: tuple[int] = tuple(child.element.style.display.weight for child in relative_children_with_weights)  # type: ignore[assignment]
            if display.direction == "row":
                for child, flex_portion in zip(
                    relative_children_with_weights, partition_int(total=available_width, weights=weights)
                ):
                    child.dims.content.width = max(flex_portion - child.dims.horizontal_edge_width(), 0)
                available_width = 0
            elif display.direction == "column":
                for child, flex_portion in zip(
                    relative_children_with_weights, partition_int(total=available_height, weights=weights)
                ):
                    child.dims.content.height = max(flex_portion - child.dims.vertical_edge_width(), 0)
                available_height = 0
        elif display.justify_children in ("space-between", "space-around", "space-evenly"):
            for child in relative_children:
                # TODO: if we don't do this, flex elements never get their width set if justify_children is space-*, but this seems wrong...
                if child.element.type == "text" and child.element.style.span.width == "auto":
                    child.dims.content.width = max(
                        (len(line) for line in wrap_text(child.element.content, available_width)), default=0
                    )
                    available_width -= child.dims.width()

        # at this point we know how wide each child is, so we can do text wrapping and set heights
        for child in relative_children:
            if child.element.type == "text":
                h = len(wrap_text(child.element.content, child.dims.content.width))
                logger.debug("wrapped text", h=h, w=child.dims.content.width)
                child.dims.content.height = max(min(h, available_height - child.dims.vertical_edge_width()), 0)

        # determine positions

        # shift nominal content box position set by parent by own margin, border, and padding
        self.dims.content.x += self.dims.margin.left + self.dims.border.left + self.dims.padding.left
        self.dims.content.y += self.dims.margin.top + self.dims.border.top + self.dims.padding.top

        # these x and y persist between children and set the top left corner of their margin box
        # start in top left corner of our own context box
        x = self.dims.content.x
        y = self.dims.content.y

        # justification (main axis placement)
        if display.direction == "row":
            if display.justify_children == "center":
                x += available_width // 2
            elif display.justify_children == "end":
                x += available_width
        elif display.direction == "column":
            if display.justify_children == "center":
                y += available_height // 2
            elif display.justify_children == "end":
                y += available_height

        if display.justify_children == "space-between":
            if display.direction == "row":
                for child, gap in zip(
                    relative_children,
                    partition_int(available_width, (1,) * (num_relative_children - 1) + (0,)),
                ):
                    child.dims.content.x = x
                    child.dims.content.y = y
                    x += child.dims.width() + gap
            elif display.direction == "column":
                for child, gap in zip(
                    relative_children,
                    partition_int(available_height, (1,) * (num_relative_children - 1) + (0,)),
                ):
                    child.dims.content.x = x
                    child.dims.content.y = y
                    y += child.dims.height() + gap

        elif display.justify_children == "space-around":
            if display.direction == "row":
                for child, gap in zip(
                    relative_children,
                    partition_int(available_width, (1,) * num_relative_children),
                ):
                    child.dims.content.x = x + halve_integer(gap)[0]
                    child.dims.content.y = y
                    x += child.dims.width() + gap
            elif display.direction == "column":
                for child, gap in zip(
                    relative_children,
                    partition_int(available_height, (1,) * num_relative_children),
                ):
                    child.dims.content.x = x
                    child.dims.content.y = y + halve_integer(gap)[0]
                    y += child.dims.height() + gap

        elif display.justify_children == "space-evenly":
            if display.direction == "row":
                for child, gap in zip(
                    relative_children,
                    partition_int(available_width, (1,) * (num_relative_children + 1)),
                ):
                    child.dims.content.x = x + gap
                    child.dims.content.y = y
                    x += child.dims.width() + gap
            elif display.direction == "column":
                for child, gap in zip(
                    relative_children,
                    partition_int(available_height, (1,) * (num_relative_children + 1)),
                ):
                    child.dims.content.x = x
                    child.dims.content.y = y + gap
                    y += child.dims.height() + gap

        else:
            for child in relative_children:
                child.dims.content.x = x
                child.dims.content.y = y
                if display.direction == "row":
                    x += child.dims.width()
                elif display.direction == "column":
                    y += child.dims.height()

        # alignment (cross-axis placement)
        # content width/height of self, but full width/height of children
        for child in relative_children:
            if display.direction == "row":
                if display.align_children == "center":
                    # TODO: these floordivs aren't great
                    child.dims.content.y = self.dims.content.y + ((self.dims.content.height - child.dims.height()) // 2)
                elif display.align_children == "end":
                    child.dims.content.y = self.dims.content.y + self.dims.content.height - child.dims.height()
                elif display.align_children == "stretch" and child.element.style.span.height == "auto":
                    child.dims.content.height = self.dims.content.height - child.dims.vertical_edge_width()
            elif display.direction == "column":
                if display.align_children == "center":
                    # TODO: these floordivs aren't great
                    child.dims.content.x = self.dims.content.x + ((self.dims.content.width - child.dims.width()) // 2)
                elif display.align_children == "end":
                    child.dims.content.x = self.dims.content.y + self.dims.content.width - child.dims.width()
                elif display.align_children == "stretch" and child.element.style.span.width == "auto":
                    child.dims.content.width = self.dims.content.width - child.dims.horizontal_edge_width()


def build_layout_tree(element: AnyElement) -> LayoutBox:
    if element.style.hidden:
        raise Exception("Root element cannot have display='hidden'")

    children = []
    for child in element.children:
        if isinstance(child, Component):
            raise Exception("Layout tree must be built from concrete Elements, not Components")

        if not child.style.hidden == "hidden":
            children.append(build_layout_tree(child))

    return LayoutBox(element=element, children=children)
