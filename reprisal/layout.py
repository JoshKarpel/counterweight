from __future__ import annotations

from collections.abc import Iterator
from typing import NamedTuple

from pydantic import Field
from typing_extensions import assert_never

from reprisal._utils import halve_integer
from reprisal.components import Element
from reprisal.types import ForbidExtras


class Position(NamedTuple):
    x: int
    y: int


class Rect(ForbidExtras):
    x: int = Field(default=0)
    y: int = Field(default=0)
    width: int = Field(default=0)
    height: int = Field(default=0)

    def expand_by(self, edge: Edge) -> Rect:
        return Rect(
            x=self.x - edge.left,
            y=self.y - edge.top,
            width=self.width + edge.left + edge.right,
            height=self.height + edge.top + edge.bottom,
        )

    def x_range(self) -> list[int]:
        return list(range(self.x, self.x + self.width))

    def y_range(self) -> list[int]:
        return list(range(self.y, self.y + self.height))

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


class LayoutBox(ForbidExtras):
    element: Element
    dims: BoxDimensions = Field(default_factory=BoxDimensions)
    children: list[LayoutBox] = Field(default_factory=list)

    def walk_from_bottom(self) -> Iterator[Element]:
        for child in self.children:
            yield from child.walk_from_bottom()
        yield self.element

    def layout(self, parent_dims: BoxDimensions) -> None:
        match self.element.style.display:
            case "block":
                self.determine_width(parent_dims)
                self.determine_position(parent_dims)
                self.layout_children(parent_dims)
                self.determine_height(parent_dims)
            case display:
                assert_never(display)

    def determine_width(self, parent_dims: BoxDimensions) -> None:
        element_style = self.element.style

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
        if minimum_block_width > parent_dims.content.width:
            if margin_left == "auto":
                margin_left = 0
            if margin_right == "auto":
                margin_right = 0

        # The underflow is how much extra space we have (it may be negative if the minimum width is too wide)
        underflow = parent_dims.content.width - minimum_block_width

        match width == "auto", margin_left == "auto", margin_right == "auto":
            # Woops, overconstrained dimensions!
            # We have to do something, so we move the right margin, since we're effectively in left-to-right mode.
            case False, False, False:
                margin_right = margin_right + underflow  # type: ignore[operator]

            # If the width is not auto and only one margin is auto, put the underflow on that margin.
            case False, True, False:
                margin_left = underflow
            case False, False, True:
                margin_right = underflow

            # If the width is not auto and both margins are auto, divide the underflow evenly between them.
            case False, True, True:
                margin_left, margin_right = halve_integer(underflow)

            # If the width is auto, we put all the underflow there, regardless of whether the margins are auto.
            case True, _, _:
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

        dims = self.dims

        dims.content.width = width  # type: ignore[assignment]

        dims.margin.left = margin_left  # type: ignore[assignment]
        dims.margin.right = margin_right  # type: ignore[assignment]

        dims.border.left = border_left
        dims.border.right = border_right

        dims.padding.left = padding_left
        dims.padding.right = padding_right

    def determine_position(self, parent_dims: BoxDimensions) -> None:
        element_style = self.element.style
        dims = self.dims

        # Transfer top and bottom box params from style to self
        dims.margin.top = element_style.margin.top
        dims.margin.bottom = element_style.margin.bottom

        dims.border.top = 1 if element_style.border else 0
        dims.border.bottom = 1 if element_style.border else 0

        dims.padding.top = element_style.padding.top
        dims.padding.bottom = element_style.padding.bottom

        # These left and right box params were set previously by self.calculate_block_width()
        dims.content.x = parent_dims.content.x + dims.margin.left + dims.border.left + dims.padding.left

        # containing_block.content.height is going to be updated *between* each child layout,
        # so that when each child of a block calls this method, it sees a different height
        # for the containing block. It's really the "current height" during layout, then becomes
        # the final height when the layout is complete.
        dims.content.y = (
            parent_dims.content.y + parent_dims.content.height + dims.margin.top + dims.border.top + dims.padding.top
        )

    def layout_children(self, parent_dims: BoxDimensions) -> None:
        for child in self.children:
            child.layout(parent_dims=self.dims)

            # Update our own height between child layouts, so that our height
            # reflects the "current height" that each child sees and lays itself out below.
            # This is for "block" layout, not "inline"!
            self.dims.content.height += child.dims.margin_rect().height

    def determine_height(self, parent_dims: BoxDimensions) -> None:
        # If a height was set explicitly, use it to override.
        # Note that this can override the "current height" calculations done in self.layout_block_children()
        if self.element.style.span.height != "auto":
            self.dims.content.height = self.element.style.span.height


def build_layout_tree(element: Element) -> LayoutBox:
    children = []
    for child in element.children:
        if not isinstance(child, Element):
            raise Exception("Layout tree must be built from concrete Elements, not Components")

        match child.style.display:
            case "block":
                children.append(build_layout_tree(child))
            case "none":
                # Don't recurse into children with display="none".
                pass
            case _:
                assert_never(child.style.display)

    return LayoutBox(element=element, children=children)
