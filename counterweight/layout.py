from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Iterable, Literal

from more_itertools import take
from structlog import get_logger

from counterweight._utils import halve_integer, partition_int
from counterweight.components import Component
from counterweight.elements import AnyElement, CellPaint
from counterweight.geometry import Edge, Rect
from counterweight.styles.styles import BorderEdge

logger = get_logger()


@dataclass(slots=True)
class LayoutBoxDimensions:
    content: Rect = field(default_factory=Rect)
    margin: Edge = field(default_factory=Edge)
    border: Edge = field(default_factory=Edge)
    padding: Edge = field(default_factory=Edge)

    def padding_border_margin_rects(self) -> tuple[Rect, Rect, Rect]:
        padding = self.content.expand_by(self.padding)
        border = padding.expand_by(self.border)
        margin = border.expand_by(self.margin)
        return padding, border, margin

    def horizontal_edge_width(self) -> int:
        return (
            self.margin.left
            + self.border.left
            + self.padding.left
            + self.margin.right
            + self.border.right
            + self.padding.right
        )

    def vertical_edge_width(self) -> int:
        return (
            self.margin.top
            + self.border.top
            + self.padding.top
            + self.margin.bottom
            + self.border.bottom
            + self.padding.bottom
        )

    def width(self) -> int:
        return self.content.width + self.horizontal_edge_width()

    def height(self) -> int:
        return self.content.height + self.vertical_edge_width()


@dataclass(slots=True)
class LayoutBox:
    element: AnyElement
    parent: LayoutBox | None
    children: list[LayoutBox] = field(default_factory=list)
    dims: LayoutBoxDimensions = field(default_factory=LayoutBoxDimensions)

    def walk_from_top(self) -> Iterator[LayoutBox]:
        yield self
        for child in self.children:
            yield from child.walk_from_top()

    def walk_from_bottom(self) -> Iterator[LayoutBox]:
        for child in self.children:
            yield from child.walk_from_bottom()
        yield self

    def walk_elements_from_bottom(self) -> Iterator[AnyElement]:
        yield from (node.element for node in self.walk_from_bottom())

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
        layout = style.layout

        # transfer margin/border/padding to dimensions
        self.dims.margin.top = style.margin.top
        self.dims.margin.bottom = style.margin.bottom
        self.dims.margin.left = style.margin.left
        self.dims.margin.right = style.margin.right

        if style.border:
            self.dims.border.top = 1 if BorderEdge.Top in style.border.edges else 0
            self.dims.border.bottom = 1 if BorderEdge.Bottom in style.border.edges else 0
            self.dims.border.left = 1 if BorderEdge.Left in style.border.edges else 0
            self.dims.border.right = 1 if BorderEdge.Right in style.border.edges else 0

        self.dims.padding.top = style.padding.top
        self.dims.padding.bottom = style.padding.bottom
        self.dims.padding.left = style.padding.left
        self.dims.padding.right = style.padding.right

        # text boxes with auto width get their width from their content (no wrapping)
        # TODO: revisit this, kind of want to differentiate between "auto" and "flex" here, or maybe width=Weight(1) ?
        if self.element.type == "text" and self.element.style.typography.wrap == "none":
            if style.span.width == "auto" or style.span.height == "auto":
                wrapped_lines = wrap_cells(
                    cells=self.element.cells,
                    wrap=style.typography.wrap,
                    width=100_000,  # any large number
                )

                if style.span.width == "auto":
                    self.dims.content.width = max(
                        (len(line) for line in wrapped_lines),
                        default=0,
                    )
                if style.span.height == "auto":
                    self.dims.content.height = len(wrapped_lines)

        num_gaps = max(
            sum(1 for child in self.children if child.element.style.layout.position.type == "relative") - 1, 0
        )

        if style.span.width == "auto":
            # grow to fit children with fixed sizes
            if layout.direction == "row":
                self.dims.content.width += num_gaps * layout.gap_children

            for child_box in self.children:
                # if child_style.span.width != "auto" or (
                #     child_element.type == "text" and child_style.typography.wrap == "none"
                # ):
                if child_box.dims.content.width != 0:  # i.e., it has been set
                    if child_box.element.style.layout.position.type == "relative":
                        if layout.direction == "row":
                            # We are growing the box to the right
                            self.dims.content.width += child_box.dims.width()
                        elif layout.direction == "column":
                            # The box is as wide as its widest child
                            self.dims.content.width = max(self.dims.content.width, child_box.dims.width())
        else:
            self.dims.content.width = style.span.width

        if style.span.height == "auto":
            if layout.direction == "column":
                self.dims.content.height += num_gaps * layout.gap_children

            for child_box in self.children:
                # if child_style.span.height != "auto" or (
                #     child_element.type == "text" and child_style.typography.wrap == "none"
                # ):
                if child_box.dims.content.height != 0:  # i.e., it has been set
                    if child_box.element.style.layout.position.type == "relative":
                        if layout.direction == "column":
                            # We are growing the box downward
                            self.dims.content.height += child_box.dims.height()
                        elif layout.direction == "row":
                            # The box is as tall as its tallest child
                            self.dims.content.height = max(self.dims.content.height, child_box.dims.height())
        else:
            self.dims.content.height = style.span.height

    def second_pass(self) -> None:
        style = self.element.style
        layout = style.layout
        parent = self.parent

        # handle align self
        if layout.position.type == "relative" and parent:
            if parent.element.style.layout.direction == "row":
                match layout.align_self:
                    case "center":
                        self.dims.content.y += (parent.dims.content.height - self.dims.height()) // 2
                    case "end":
                        self.dims.content.y += parent.dims.content.height - self.dims.height()
                    case "stretch":
                        self.dims.content.height = parent.dims.content.height - self.dims.vertical_edge_width()
            elif parent.element.style.layout.direction == "column":
                match layout.align_self:
                    case "center":
                        self.dims.content.x += (parent.dims.content.width - self.dims.width()) // 2
                    case "end":
                        self.dims.content.x += parent.dims.content.width - self.dims.width()
                    case "stretch":
                        self.dims.content.width = parent.dims.content.width - self.dims.horizontal_edge_width()

        # calculate available width for children, minus how much they use,
        # then divide that between them based on the content justification
        # We are in the parent, justifying the children!

        available_width = self.dims.content.width
        available_height = self.dims.content.height

        relative_children = []
        relative_children_with_weights = []
        weights_ = []
        for child in self.children:
            child_layout = child.element.style.layout
            if child_layout.position.type == "relative":
                relative_children.append(child)
                if child_layout.weight is not None:
                    relative_children_with_weights.append(child)
                    weights_.append(child_layout.weight)
        weights = tuple(weights_)
        num_relative_children = len(relative_children)
        num_gaps = max(num_relative_children - 1, 0)
        total_gap = num_gaps * layout.gap_children

        # subtract off fixed-width/height children from what's available to flex
        for child in relative_children:
            if child.element.style.layout.weight is None:
                if layout.direction == "row":
                    available_width -= child.dims.width()
                elif layout.direction == "column":
                    available_height -= child.dims.height()

        # when does flex element width get set for space-* justify?
        # space-* justify assumes children have fixed widths! it distributes the leftover space
        # but what if you DO put flex children in there? who sets their widths?
        # TODO: note that if a child element has a weight, a fixed width/height would be overriden here by the parent
        if relative_children_with_weights and layout.justify_children not in (
            "space-between",
            "space-around",
            "space-evenly",
        ):
            if layout.direction == "row":
                available_width -= total_gap

                for child, flex_portion in zip(
                    relative_children_with_weights, partition_int(total=available_width, weights=weights)
                ):
                    child.dims.content.width = max(flex_portion - child.dims.horizontal_edge_width(), 0)

                available_width = 0

            elif layout.direction == "column":
                available_height -= total_gap

                for child, flex_portion in zip(
                    relative_children_with_weights, partition_int(total=available_height, weights=weights)
                ):
                    child.dims.content.height = max(flex_portion - child.dims.vertical_edge_width(), 0)

                available_height = 0

        elif layout.justify_children in ("space-between", "space-around", "space-evenly"):
            for child in relative_children:
                available_width -= child.dims.width()
                available_height -= child.dims.height()

        # at this point we know how wide each child is, so we can do text wrapping and set heights
        for child in relative_children:
            if child.element.type == "text" and child.element.style.typography.wrap != "none":
                h = len(
                    wrap_cells(
                        cells=child.element.cells,
                        wrap=child.element.style.typography.wrap,
                        width=child.dims.content.width,
                    )
                )
                child.dims.content.height = max(min(h, available_height - child.dims.vertical_edge_width()), 0)

        # determine positions

        if layout.position.type == "relative":
            # For relative position, shift anything the parent set for us by the given offsets
            self.dims.content.x += layout.position.x
            self.dims.content.y += layout.position.y
        elif layout.position.type == "absolute" and parent:
            # For absolute position, start from the inset position on the parent's context box, then shift by the offset

            match layout.position.inset.horizontal:
                case "left":
                    self.dims.content.x = parent.dims.content.x
                case "center":
                    self.dims.content.x = parent.dims.content.x + ((parent.dims.content.width - self.dims.width()) // 2)
                case "right":
                    self.dims.content.x = parent.dims.content.x + parent.dims.content.width - self.dims.width()

            match layout.position.inset.vertical:
                case "top":
                    self.dims.content.y = parent.dims.content.y
                case "center":
                    self.dims.content.y = parent.dims.content.y + (
                        (parent.dims.content.height - self.dims.height()) // 2
                    )
                case "bottom":
                    self.dims.content.y = parent.dims.content.y + parent.dims.content.height - self.dims.height()

            self.dims.content.x += layout.position.x
            self.dims.content.y += layout.position.y
        elif layout.position.type == "fixed":
            # For fixed position, override anything that the parent tried to set for us
            self.dims.content.x = layout.position.x
            self.dims.content.y = layout.position.y

        # shift nominal content box position set by parent by own margin, border, and padding
        self.dims.content.x += self.dims.margin.left + self.dims.border.left + self.dims.padding.left
        self.dims.content.y += self.dims.margin.top + self.dims.border.top + self.dims.padding.top

        # these x and y persist between children and set the top left corner of their margin box
        # start in top left corner of our own context box
        x = self.dims.content.x
        y = self.dims.content.y

        # TODO: available width can be negative here, but that doesn't make sense
        # seems to happen when this element isn't stretch but it has fixed-width children

        # justification (main axis placement)
        # TODO: need to subtract total_gap here, even though it was handled above?
        if layout.direction == "row":
            if layout.justify_children == "center":
                x += (available_width - total_gap) // 2
            elif layout.justify_children == "end":
                x += available_width - total_gap
        elif layout.direction == "column":
            if layout.justify_children == "center":
                y += (available_height - total_gap) // 2
            elif layout.justify_children == "end":
                y += available_height - total_gap

        if layout.justify_children == "space-between":
            if layout.direction == "row":
                for child, gap in zip(
                    relative_children,
                    partition_int(available_width, (1,) * (num_relative_children - 1) + (0,)),
                ):
                    child.dims.content.x = x
                    child.dims.content.y = y
                    x += child.dims.width() + gap
            elif layout.direction == "column":
                for child, gap in zip(
                    relative_children,
                    partition_int(available_height, (1,) * (num_relative_children - 1) + (0,)),
                ):
                    child.dims.content.x = x
                    child.dims.content.y = y
                    y += child.dims.height() + gap

        elif layout.justify_children == "space-around":
            if layout.direction == "row":
                for child, gap in zip(
                    relative_children,
                    partition_int(available_width, (1,) * num_relative_children),
                ):
                    child.dims.content.x = x + halve_integer(gap)[0]
                    child.dims.content.y = y
                    x += child.dims.width() + gap
            elif layout.direction == "column":
                for child, gap in zip(
                    relative_children,
                    partition_int(available_height, (1,) * num_relative_children),
                ):
                    child.dims.content.x = x
                    child.dims.content.y = y + halve_integer(gap)[0]
                    y += child.dims.height() + gap

        elif layout.justify_children == "space-evenly":
            if layout.direction == "row":
                for child, gap in zip(
                    relative_children,
                    partition_int(available_width, (1,) * (num_relative_children + 1)),
                ):
                    child.dims.content.x = x + gap
                    child.dims.content.y = y
                    x += child.dims.width() + gap
            elif layout.direction == "column":
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
                if layout.direction == "row":
                    x += child.dims.width() + layout.gap_children
                elif layout.direction == "column":
                    y += child.dims.height() + layout.gap_children

        # alignment (cross-axis placement)
        # content width/height of self, but full width/height of children
        for child in relative_children:
            # Skip children that will align themselves
            if child.element.style.layout.align_self != "none":
                continue

            if layout.direction == "row":
                if layout.align_children == "center":
                    # TODO: these floordivs aren't great
                    child.dims.content.y = self.dims.content.y + ((self.dims.content.height - child.dims.height()) // 2)
                elif layout.align_children == "end":
                    child.dims.content.y = self.dims.content.y + self.dims.content.height - child.dims.height()
                elif layout.align_children == "stretch" and child.element.style.span.height == "auto":
                    child.dims.content.height = self.dims.content.height - child.dims.vertical_edge_width()
            elif layout.direction == "column":
                if layout.align_children == "center":
                    # TODO: these floordivs aren't great
                    child.dims.content.x = self.dims.content.x + ((self.dims.content.width - child.dims.width()) // 2)
                elif layout.align_children == "end":
                    child.dims.content.x = self.dims.content.y + self.dims.content.width - child.dims.width()
                elif layout.align_children == "stretch" and child.element.style.span.width == "auto":
                    child.dims.content.width = self.dims.content.width - child.dims.horizontal_edge_width()


def build_layout_tree_from_concrete_element_tree(element: AnyElement, parent: LayoutBox | None = None) -> LayoutBox:
    box = LayoutBox(element=element, parent=parent)

    box.children.extend(
        build_layout_tree_from_concrete_element_tree(
            element=child,
            parent=box,
        )
        for child in element.children
        if not isinstance(child, Component)
    )

    return box


def wrap_cells(
    cells: Iterable[CellPaint],
    wrap: Literal["none", "paragraphs"],
    width: int,
) -> list[list[CellPaint]]:
    if width <= 0:
        return []

    if wrap == "none":
        lines: list[list[CellPaint]] = []
        current_line: list[CellPaint] = []
        for cell in cells:
            if cell.char == "\n":
                lines.append(current_line)
                current_line = []
            else:
                current_line.append(cell)
        lines.append(current_line)
        return lines

    raise NotImplementedError("non-none wrapping not yet implemented")

    # wrapper = TextWrapper(width=width)
    #
    # paragraphs = text.split("\n\n")  # double newline = paragraph break
    #
    # lines = []
    # for paragraph in paragraphs:
    #     lines.extend(wrapper.wrap(paragraph))
    #     lines.append("")  # empty line between paragraphs
    #
    # return lines[:-1]  # remove last empty line
