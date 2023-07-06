from __future__ import annotations

from collections.abc import Iterator
from typing import NamedTuple

from pydantic import Field
from typing_extensions import assert_never

from reprisal._utils import halve_integer
from reprisal.components import AnyElement, Div, Element
from reprisal.styles.styles import AnonymousBlock, Block, Inline
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
    element: AnyElement
    display: Block | Inline | AnonymousBlock
    dims: BoxDimensions = Field(default_factory=BoxDimensions)
    children: list[LayoutBox] = Field(default_factory=list)

    def walk_from_bottom(self) -> Iterator[Element]:
        for child in self.children:
            yield from child.walk_from_bottom()
        yield self.element

    def layout(self, parent_content: Rect) -> None:
        match self.display.type:
            case "block":
                self.determine_block_width(parent_content)
                self.determine_block_position(parent_content)
                self.layout_block_children(parent_content)
                self.determine_block_height(parent_content)
            case "inline":
                self.determine_inline_width(parent_content=parent_content)
                self.determine_inline_position(parent_content=parent_content)
                self.layout_inline_children(parent_content=parent_content)
                self.determine_inline_height(parent_content=parent_content)
            case "anonymous-block":
                self.determine_block_width(parent_content)
                self.determine_block_position(parent_content)
                self.layout_inline_children(parent_content=parent_content)
                self.determine_inline_height(parent_content=parent_content)
            case display:
                assert_never(display)

    def layout_block(self, parent_content: Rect) -> None:
        self.determine_block_width(parent_content)
        self.determine_block_position(parent_content)
        self.layout_block_children(parent_content)
        self.determine_block_height(parent_content)

    def determine_block_width(self, parent_content: Rect) -> None:
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
        if minimum_block_width > parent_content.width:
            if margin_left == "auto":
                margin_left = 0
            if margin_right == "auto":
                margin_right = 0

        # The underflow is how much extra space we have (it may be negative if the minimum width is too wide)
        underflow = parent_content.width - minimum_block_width

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

    def determine_block_position(self, parent_content: Rect) -> None:
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
        dims.content.x = parent_content.x + dims.margin.left + dims.border.left + dims.padding.left

        # parent_content.height is going to be updated *between* each child layout,
        # so that when each child of a block calls this method, it sees a different height
        # for the containing block. It's really the "current height" during layout, then becomes
        # the final height when the layout is complete.
        dims.content.y = parent_content.y + parent_content.height + dims.margin.top + dims.border.top + dims.padding.top

    def layout_block_children(self, parent_content: Rect) -> None:
        for child in self.children:
            child.layout(parent_content=self.dims.content)

            # Update our own height between child layouts, so that our height
            # reflects the "current height" that each child sees and lays itself out below.
            # This is for "block" layout, not "inline"!
            self.dims.content.height += child.dims.margin_rect().height

    def determine_block_height(self, parent_content: Rect) -> None:
        # If a height was set explicitly, use it to override.
        # Note that this can override the "current height" calculations done in self.layout_block_children()
        if self.element.style.span.height != "auto":
            self.dims.content.height = self.element.style.span.height

    def layout_inline(self, parent_content: Rect) -> None:
        self.determine_inline_width(parent_content=parent_content)
        self.determine_inline_position(parent_content=parent_content)
        self.layout_inline_children(parent_content=parent_content)
        self.determine_inline_height(parent_content=parent_content)

    def determine_inline_width(self, parent_content: Rect) -> None:
        element_style = self.element.style

        width = element_style.span.width

        margin_left = element_style.margin.left
        margin_right = element_style.margin.right

        border_left = 1 if element_style.border is not None else 0
        border_right = 1 if element_style.border is not None else 0

        padding_left = element_style.padding.left
        padding_right = element_style.padding.right

        # auto margins are treated as 0 for inline elements
        if margin_left == "auto":
            margin_left = 0
        if margin_right == "auto":
            margin_right = 0

        if width == "auto" and self.element.type == "text":
            width = len(self.element.content)

        dims = self.dims

        dims.content.width = width  # type: ignore[assignment]

        dims.margin.left = margin_left  # type: ignore[assignment]
        dims.margin.right = margin_right  # type: ignore[assignment]

        dims.border.left = border_left
        dims.border.right = border_right

        dims.padding.left = padding_left
        dims.padding.right = padding_right

    def determine_inline_position(self, parent_content: Rect) -> None:
        element_style = self.element.style
        dims = self.dims

        # Transfer top and bottom box params from style to self
        dims.margin.top = element_style.margin.top
        dims.margin.bottom = element_style.margin.bottom

        dims.border.top = 1 if element_style.border else 0
        dims.border.bottom = 1 if element_style.border else 0

        dims.padding.top = element_style.padding.top
        dims.padding.bottom = element_style.padding.bottom

        match self.display.justify:
            case "left":
                dims.content.x = parent_content.x + dims.margin.left + dims.border.left + dims.padding.left
            case "right":
                # TODO: This is wrong, because you are supposed to adjust the whole line after the line is laid out
                # TODO: move this up, do wrapping
                # how does this even work when there are multiple inline elements on a line with different justify settings?
                dims.content.x = (
                    parent_content.right
                    - dims.margin.right
                    - dims.border.right
                    - dims.padding.right
                    - dims.content.width
                    + 1  # TODO: Why is this needed?
                )
        dims.content.y = parent_content.y + dims.margin.top + dims.border.top + dims.padding.top

    def layout_inline_children(self, parent_content: Rect) -> None:
        left = 0
        for child in self.children:
            child.layout(
                parent_content=Rect(
                    x=self.dims.content.x + left,
                    y=self.dims.content.y,
                    width=self.dims.content.width - left,
                    height=self.dims.content.height,
                )
            )

            left += child.dims.margin_rect().width

            # The height of an inline block is the height of its tallest child
            self.dims.content.height = max(self.dims.content.height, child.dims.margin_rect().height)

    def determine_inline_height(self, parent_content: Rect) -> None:
        # If a height was set explicitly, use it to override.
        # Note that this can override the "current height" calculations done in self.layout_inline_children()
        if self.element.style.span.height != "auto":
            self.dims.content.height = self.element.style.span.height


def build_layout_tree(element: Element) -> LayoutBox:
    display = element.style.display

    if display == "none":
        raise Exception("Root element cannot have display='none'")

    children = []
    for child in element.children:
        if not isinstance(child, Element):
            raise Exception("Layout tree must be built from concrete Elements, not Components")

        # Each block must only have children of one type: block or inline.
        match display.type, child.style.display.type:
            case ("block", "block") | ("inline", "inline"):
                children.append(build_layout_tree(child))
            case "block", "inline":
                if children and children[-1].display.type == "anonymous-block":
                    # Re-use previous anonymous block
                    children[-1].children.append(build_layout_tree(child))
                else:
                    # Create a new anonymous block level box and put the child inline box inside it.
                    box = LayoutBox(element=Div(), display=AnonymousBlock(), children=[build_layout_tree(child)])
                    children.append(box)
            case "inline", "block":
                raise NotImplementedError("Inline blocks cannot have block children yet")
            case _, "none":
                # Don't recurse into children with display="none".
                pass
            case foo:
                assert_never(foo)

    return LayoutBox(element=element, display=display, children=children)
