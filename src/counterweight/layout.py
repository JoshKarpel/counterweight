from __future__ import annotations

from collections.abc import Container, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from functools import lru_cache
from itertools import repeat
from math import inf
from typing import TYPE_CHECKING, assert_never

import waxy

from counterweight.controls import ScrollAlignment
from counterweight.elements import AnyElement, Chunk, Div, StyledGrapheme, Text, text_cells
from counterweight.geometry import Position, Rects, Region, Scroll
from counterweight.graphemes import LINE_BREAKS
from counterweight.styles.styles import CellStyle, ClipTo, ResolvedStyle, Style, TextWrap

if TYPE_CHECKING:
    from counterweight.focus import ElementHandle
    from counterweight.hooks.impls import NodeKey
    from counterweight.shadow import ShadowNode, ShadowTree


_EMPTY_REGION = Region(left=0, top=0, right=0, bottom=0)

INITIAL_RECTS = Rects(
    content=_EMPTY_REGION,
    padding=_EMPTY_REGION,
    border=_EMPTY_REGION,
    margin=_EMPTY_REGION,
    clip=None,
    visible=None,
)


# Everything a `Text`'s measured size depends on: its content, its text style, and how it wraps.
type TextSource = tuple[str | tuple[Chunk, ...], CellStyle, TextWrap]


def text_source(text: Text) -> TextSource:
    """Everything `text`'s measured size depends on, normalized so that equal sources compare equal."""
    content = text.content if isinstance(text.content, str) else tuple(text.content)
    return content, text.style.text_style, text.style.resolved.text_wrap


@dataclass(frozen=True, slots=True)
class CreateLeaf:
    key: NodeKey
    style: waxy.Style
    text: TextSource


@dataclass(frozen=True, slots=True)
class CreateContainer:
    key: NodeKey
    style: waxy.Style
    children: tuple[NodeKey, ...]


@dataclass(frozen=True, slots=True)
class SetStyle:
    key: NodeKey
    style: waxy.Style


@dataclass(frozen=True, slots=True)
class SetText:
    key: NodeKey
    text: TextSource


@dataclass(frozen=True, slots=True)
class ClearText:
    key: NodeKey


@dataclass(frozen=True, slots=True)
class SetChildren:
    key: NodeKey
    children: tuple[NodeKey, ...]


@dataclass(frozen=True, slots=True)
class Remove:
    key: NodeKey


type LayoutChange = CreateLeaf | CreateContainer | SetStyle | SetText | ClearText | SetChildren | Remove


def layout_changes(previous_tree: ShadowTree | None, next_tree: ShadowTree) -> list[LayoutChange]:
    """
    The changes that make a layout tree built from `previous` match `next`,
    pairing nodes by key as `update_shadow` paired them.

    Children come before their parents, so a parent's children exist when it's created or given them,
    and removals come last. Every node of an unmounted subtree is removed, not just its root,
    because taffy's remove detaches a node's children rather than removing them.
    """
    changes: list[LayoutChange] = []
    removals: list[LayoutChange] = []
    previous = None if previous_tree is None else previous_tree.root
    next = next_tree.root

    if previous is not None and previous.key != next.key:
        removals.extend(_removals(previous))
        previous = None

    _reconcile(previous, next, changes, removals)

    changes.extend(removals)
    return changes


def _reconcile(
    previous: ShadowNode | None,
    next: ShadowNode,
    changes: list[LayoutChange],
    removals: list[LayoutChange],
) -> None:
    """
    Appends the changes for `next`'s subtree, given the previous node it continues, if any.
    A subtree `update_shadow` reused is the previous node itself, frozen with all its descendants,
    so it has no changes and isn't descended into.
    """
    if next is previous:
        return

    key = next.key
    element = next.element
    style = layout_style(element.style)

    # Taffy discards a node's cached layout when its text or children are set, even to equal values,
    # so each is set only when it changed.
    match element:
        case Text():
            source = text_source(element)
            if previous is None:
                changes.append(CreateLeaf(key=key, style=style, text=source))
                return

            _append_style_change(previous, key, style, changes)
            match previous.element:
                case Text() as previous_text:
                    if text_source(previous_text) != source:
                        changes.append(SetText(key=key, text=source))
                case Div():
                    for child in previous.children:
                        removals.extend(_removals(child))
                    changes.append(SetText(key=key, text=source))
                case _ as unreachable:
                    assert_never(unreachable)
        case Div():
            previous_children = {} if previous is None else {child.key: child for child in previous.children}
            for child in next.children:
                _reconcile(previous_children.pop(child.key, None), child, changes, removals)
            for unmounted in previous_children.values():
                removals.extend(_removals(unmounted))

            child_keys = tuple(child.key for child in next.children)
            if previous is None:
                changes.append(CreateContainer(key=key, style=style, children=child_keys))
                return

            _append_style_change(previous, key, style, changes)
            match previous.element:
                case Text():
                    changes.append(ClearText(key=key))
                    changes.append(SetChildren(key=key, children=child_keys))
                case Div():
                    if tuple(child.key for child in previous.children) != child_keys:
                        changes.append(SetChildren(key=key, children=child_keys))
                case _ as unreachable:
                    assert_never(unreachable)
        case _ as unreachable:
            assert_never(unreachable)


def _append_style_change(previous: ShadowNode, key: NodeKey, style: waxy.Style, changes: list[LayoutChange]) -> None:
    """Appends a `SetStyle` only when `style` differs from `previous`'s, since resetting it is wasted work."""
    previous_style = layout_style(previous.element.style)
    if previous_style is not style and previous_style != style:
        changes.append(SetStyle(key=key, style=style))


def _removals(unmounted: ShadowNode) -> Iterator[Remove]:
    """A `Remove` for every node of `unmounted`'s subtree, parents first."""
    return (Remove(key=node.key) for node in unmounted.walk())


@dataclass(frozen=True, slots=True)
class Layouts:
    """
    One frame's layouts: each visible node's key, element and layout in paint order, and its layout by key,
    and the scroll of each visible scroll container by key, with the nodes of those scroll containers,
    which the next layout picks anchors in,
    and the key of each element given a `handle`, by its handle, which `use_scroll` reads scrolls through.
    """

    in_paint_order: tuple[tuple[NodeKey, AnyElement, Rects], ...]
    by_key: Mapping[NodeKey, Rects]
    scrolls: Mapping[NodeKey, Scroll]
    scroll_containers: tuple[ShadowNode, ...] = ()
    handles: Mapping[ElementHandle, NodeKey] = field(default_factory=dict)


NO_LAYOUTS = Layouts(in_paint_order=(), by_key={}, scrolls={})


@dataclass(frozen=True, slots=True)
class Anchor:
    """
    The node a scroll container keeps in place as its content changes, as CSS's scroll anchoring does,
    and how far its border box's top edge was below the top of the container's padding box.
    """

    key: NodeKey
    distance: int


@dataclass(frozen=True, slots=True, kw_only=True)
class PriorScroll:
    """How a scroll container was scrolled before a layout, which decides how it's scrolled after it."""

    offset: Position
    is_at_end_x: bool
    is_at_end_y: bool
    anchor: Anchor | None


def prior_scrolls(layouts: Layouts, offsets: Mapping[NodeKey, Position]) -> dict[NodeKey, PriorScroll]:
    """
    How each scroll container in `layouts` is scrolled before the next layout,
    at its offset in `offsets`, which scroll controls may have moved since `layouts` was laid out.
    """
    by_key = layouts.by_key
    priors = {}
    for container in layouts.scroll_containers:
        key = container.key
        scroll = layouts.scrolls[key]
        offset = offsets[key]
        is_at_end_y = offset.y == scroll.max_offset.y
        # The spec skips anchoring at the top, so content added above the top pushes the rest down,
        # and a container that doesn't scroll vertically is always at the top.
        # One that will be scrolled to its end has no use for an anchor.
        is_anchored = offset.y != 0 and not (is_at_end_y and container.element.style.resolved.stick_to_end_y)
        priors[key] = PriorScroll(
            offset=offset,
            is_at_end_x=offset.x == scroll.max_offset.x,
            is_at_end_y=is_at_end_y,
            anchor=anchor_of(container, by_key, offset.y - scroll.offset.y) if is_anchored else None,
        )
    return priors


def anchor_of(container: ShadowNode, by_key: Mapping[NodeKey, Rects], scrolled: int) -> Anchor | None:
    """
    The anchor of the scroll `container`, laid out at `by_key` and since scrolled down by `scrolled` rows,
    picked as the [spec](https://drafts.csswg.org/css-scroll-anchoring/#anchor-node-selection) picks one,
    or `None` if its anchoring is off or nothing in it is in view.
    """
    if container.element.style.resolved.overflow_anchor == "none":
        return None
    view = by_key[container.key].padding
    anchor = _anchor_among(container.children, by_key, scrolled, view.top, view.bottom)
    if anchor is None:
        return None
    return Anchor(key=anchor, distance=by_key[anchor].border.top - scrolled - view.top)


def _anchor_among(
    nodes: Iterable[ShadowNode], by_key: Mapping[NodeKey, Rects], scrolled: int, top: int, bottom: int
) -> NodeKey | None:
    """
    The first of `nodes`, in tree order, that's in the rows from `top` to `bottom` once moved up by `scrolled`,
    where one wholly in them is the anchor, and one partly in them is descended into for a better one,
    unless it's a scroll container, and is the anchor if none of its children is in them.
    A hidden or unclipped node, or one whose anchoring is off, is never the anchor, nor is anything inside it.
    """
    for node in nodes:
        style = node.element.style
        resolved = style.resolved
        if (
            (rects := by_key.get(node.key)) is None
            or resolved.clip_to == "screen"
            or resolved.overflow_anchor == "none"
        ):
            continue
        node_top = rects.border.top - scrolled
        node_bottom = rects.border.bottom - scrolled
        if node_bottom <= top or node_top >= bottom:
            continue
        if (top <= node_top and node_bottom <= bottom) or any(scrolled_axes(style)):
            return node.key
        descendant = _anchor_among(node.children, by_key, scrolled, top, bottom)
        return node.key if descendant is None else descendant
    return None


@dataclass(eq=False, slots=True)
class LayoutTree:
    """
    The layout tree for one app, kept across frames so that taffy keeps the layout it cached
    for every node whose style, text and children are unchanged.
    Only `apply` and `compute` read or write its taffy nodes.
    """

    tree: waxy.TaffyTree[MeasurableText] = field(default_factory=waxy.TaffyTree)
    nodes: dict[NodeKey, waxy.NodeId] = field(default_factory=dict)

    def compute(
        self,
        changes: Iterable[LayoutChange],
        shadow: ShadowTree,
        width: int,
        height: int,
        priors: Mapping[NodeKey, PriorScroll],
        into_view: Sequence[IntoView] = (),
    ) -> Layouts:
        """
        Apply `changes`, which make the tree match `shadow`, then lay it out on a `width` by `height` screen,
        with each scroll container scrolled as `place` scrolls it from how it was scrolled before, in `priors`,
        and then scrolled to bring each node in `into_view` into view, in order.
        """
        self.apply(changes)

        root = self.nodes[shadow.root.key]
        available = waxy.AvailableSize(width=waxy.Definite(width), height=waxy.Definite(height))
        self.tree.compute_layout(root, available, measure=_measure_text)

        keys = {self.nodes[node.key]: node.key for node in shadow.nodes}
        boxes = {keys[node]: (position, layout) for node, position, layout in self.tree.absolute_layouts(root)}
        by_key, scrolls, scroll_containers = place(
            shadow.root,
            boxes,
            Region(left=0, top=0, right=width, bottom=height),
            priors,
            scrolled_into_view(into_view, shadow, boxes, priors),
        )
        in_paint_order = tuple((node.key, node.element, by_key[node.key]) for node in paint_order(shadow.root, by_key))

        return Layouts(
            in_paint_order=in_paint_order,
            by_key=by_key,
            scrolls=scrolls,
            scroll_containers=scroll_containers,
            handles=shadow.handled,
        )

    def apply(self, changes: Iterable[LayoutChange]) -> None:
        """Applies `changes` to the taffy tree in order, so each one may refer to nodes the earlier ones created."""
        nodes = self.nodes
        tree = self.tree
        for change in changes:
            match change:
                case CreateLeaf(key=key, style=style, text=text):
                    nodes[key] = tree.new_leaf_with_context(style, MeasurableText.of(text))
                case CreateContainer(key=key, style=style, children=children):
                    nodes[key] = tree.new_with_children(style, [nodes[child] for child in children])
                case SetStyle(key=key, style=style):
                    tree.set_style(nodes[key], style)
                case SetText(key=key, text=text):
                    tree.set_node_context(nodes[key], MeasurableText.of(text))
                case ClearText(key=key):
                    tree.set_node_context(nodes[key], None)
                case SetChildren(key=key, children=children):
                    tree.set_children(nodes[key], [nodes[child] for child in children])
                case Remove(key=key):
                    tree.remove(nodes.pop(key))
                case _ as unreachable:
                    assert_never(unreachable)


_NO_BORDER = waxy.Style(
    border_top=waxy.Length(0),
    border_bottom=waxy.Length(0),
    border_left=waxy.Length(0),
    border_right=waxy.Length(0),
)


@lru_cache(maxsize=2**12)
def layout_style(style: Style) -> waxy.Style:
    """
    The waxy style an element is laid out with: its `layout`, without border widths
    when its `border_kind` is `None`, as CSS's `border-style: none` makes border widths compute to 0.
    """
    if style.resolved.border_kind is None:
        return style.layout | _NO_BORDER
    return style.layout


def place(
    root: ShadowNode,
    boxes: Mapping[NodeKey, tuple[waxy.Point, waxy.Layout]],
    screen: Region,
    priors: Mapping[NodeKey, PriorScroll],
    scrolled: Mapping[NodeKey, Scroll],
) -> tuple[dict[NodeKey, Rects], dict[NodeKey, Scroll], tuple[ShadowNode, ...]]:
    """
    Where each node with a box in `boxes` is on `screen`, given its absolute position and layout,
    and the scroll and node of each scroll container among them,
    walking down from `root` so each node's clip is built from its parent's,
    and each node is moved by the offsets of the scroll containers above it.
    A node without a box is hidden, and so is every node beneath it.

    A scroll container's scroll is its scroll in `scrolled`, if it has one there,
    and otherwise its `settled_scroll` from how it was scrolled before, in `priors`.

    The walk follows the tree, not paint order, because a raised descendant paints after nodes
    outside its ancestors, and must still be clipped by those ancestors.
    """
    placed: dict[NodeKey, Rects] = {}
    scrolls: dict[NodeKey, Scroll] = {}
    scroll_containers: list[ShadowNode] = []
    stack: list[tuple[ShadowNode, Region | None, int, int]] = [(root, screen, 0, 0)]
    while stack:
        node, clip, scrolled_x, scrolled_y = stack.pop()
        try:
            position, layout = boxes[node.key]
        except KeyError:
            continue
        rects = placed[node.key] = _resolve_layout(position, layout, clip, scrolled_x, scrolled_y)
        style = node.element.style
        scrolls_x, scrolls_y = scrolled_axes(style)
        if scrolls_x or scrolls_y:
            if isinstance(node.element, Text):
                raise ValueError(
                    "A Text doesn't scroll its own text, so its overflow can't be Scroll: "
                    "put it in a Div whose overflow is Scroll, which scrolls it."
                )
            if (scroll := scrolled.get(node.key)) is None:
                scroll = settled_scroll(style, position, layout, priors.get(node.key), boxes)
            scrolls[node.key] = scroll
            scroll_containers.append(node)
            scrolled_x += scroll.offset.x
            scrolled_y += scroll.offset.y
        if not (children := node.children):
            continue
        clips_x, clips_y = clipped_axes(style)
        # Every child's clip is the screen, whatever its clip_to, so there's no need to look at each one.
        if clip == screen and not (clips_x or clips_y):
            stack.extend(zip(reversed(children), repeat(clip), repeat(scrolled_x), repeat(scrolled_y)))
        else:
            stack.extend(
                (
                    child,
                    child_clip(clip, screen, rects, child.element.style.resolved.clip_to, clips_x, clips_y),
                    scrolled_x,
                    scrolled_y,
                )
                for child in reversed(children)
            )
    return placed, scrolls, tuple(scroll_containers)


@lru_cache(maxsize=2**12)
def scrolled_axes(style: Style) -> tuple[bool, bool]:
    """Whether an element with `style` is a scroll container horizontally and vertically: its overflow is `Scroll`."""
    layout = style.layout
    return layout.overflow_x == waxy.Overflow.Scroll, layout.overflow_y == waxy.Overflow.Scroll


def settled_scroll(
    style: Style,
    position: waxy.Point,
    layout: waxy.Layout,
    prior: PriorScroll | None,
    boxes: Mapping[NodeKey, tuple[waxy.Point, waxy.Layout]],
) -> Scroll:
    """
    The scroll of a scroll container with `style`, laid out at `position` with `layout`,
    after a layout that put every node at its box in `boxes`, given how it was scrolled before (`None` if it's new):
    its `requested_offset`, clamped to how far it scrolls on each axis it scrolls.
    """
    scrolls_x, scrolls_y = scrolled_axes(style)
    max_offset = Position(
        int(layout.scroll_width()) if scrolls_x else 0,
        int(layout.scroll_height()) if scrolls_y else 0,
    )
    padding = _resolve_layout(position, layout, None, 0, 0).padding
    return scroll_of(requested_offset(prior, boxes, padding.top, max_offset, style.resolved), max_offset, padding)


@dataclass(frozen=True, slots=True)
class IntoView:
    """A node to scroll into view, aligned in each scroll container above it as `block` and `inline` say."""

    key: NodeKey
    block: ScrollAlignment
    inline: ScrollAlignment


def scrolled_into_view(
    requests: Iterable[IntoView],
    shadow: ShadowTree,
    boxes: Mapping[NodeKey, tuple[waxy.Point, waxy.Layout]],
    priors: Mapping[NodeKey, PriorScroll],
) -> dict[NodeKey, Scroll]:
    """
    The scroll of each scroll container that `requests` move, applied in order,
    each scrolling the containers above its node from the innermost out, as the web's `scrollIntoView` does:
    each container is scrolled to bring the node's border box into its view as the containers inside it left it,
    and clamped, from its `settled_scroll`, or from where an earlier request left it.
    The walk stops at an unclipped node, since no container above it clips it, or anything inside it,
    as the web doesn't scroll a container to show a fixed element that its clip doesn't cut off.
    A request for a node without a box in `boxes`, because it's hidden or unmounted, moves nothing.
    """
    scrolled: dict[NodeKey, Scroll] = {}
    nodes: dict[NodeKey, ShadowNode] | None = None
    for request in requests:
        try:
            position, layout = boxes[request.key]
        except KeyError:
            continue
        if nodes is None:
            nodes = {node.key: node for node in shadow.nodes}
        left, top = int(position.x), int(position.y)
        right, bottom = left + int(layout.size.width), top + int(layout.size.height)
        child = request.key
        while nodes[child].element.style.resolved.clip_to != "screen" and (key := shadow.parents[child]) is not None:
            style = nodes[key].element.style
            if any(scrolled_axes(style)):
                container_position, container_layout = boxes[key]
                if (scroll := scrolled.get(key)) is None:
                    scroll = settled_scroll(style, container_position, container_layout, priors.get(key), boxes)
                view = _resolve_layout(container_position, container_layout, None, 0, 0).padding
                offset = scroll.clamp(
                    Position(
                        aligned(request.inline, left, right, view.left, view.right, scroll.offset.x),
                        aligned(request.block, top, bottom, view.top, view.bottom, scroll.offset.y),
                    )
                )
                scrolled[key] = replace(scroll, offset=offset)
                left, right = left - offset.x, right - offset.x
                top, bottom = top - offset.y, bottom - offset.y
            child = key
    return scrolled


def aligned(alignment: ScrollAlignment, start: int, end: int, view_start: int, view_end: int, offset: int) -> int:
    """
    The offset on one axis that aligns a box from `start` to `end` in a view from `view_start` to `view_end`
    as `alignment` says, where every edge is where it is with no offset, and the container is scrolled to `offset` now.
    `"nearest"` follows the [CSSOM View spec](https://drafts.csswg.org/cssom-view/#determine-the-scroll-into-view-position):
    a box that's wholly in view, or covers the whole view, stays where it is;
    otherwise the edge on the side it's cut off is aligned, if the box fits in the view,
    and the edge on the other side if it doesn't, which scrolls least either way.
    """
    match alignment:
        case "start":
            return start - view_start
        case "end":
            return end - view_end
        case "center":
            return (start + end - view_start - view_end) // 2
        case "nearest":
            is_cut_at_start = start - offset < view_start
            is_cut_at_end = end - offset > view_end
            if is_cut_at_start == is_cut_at_end:
                return offset
            fits = end - start <= view_end - view_start
            return start - view_start if is_cut_at_start == fits else end - view_end
        case _ as unreachable:
            assert_never(unreachable)


def requested_offset(
    prior: PriorScroll | None,
    boxes: Mapping[NodeKey, tuple[waxy.Point, waxy.Layout]],
    padding_top: int,
    max_offset: Position,
    style: ResolvedStyle,
) -> Position:
    """
    Where a scroll container with `style` is scrolled after a layout, before clamping,
    given how it was scrolled before (`None` if it's new), taffy's unscrolled absolute positions in `boxes`,
    its padding box's top among them, `padding_top`, and how far it can scroll, `max_offset`.

    On an axis it sticks to its end on, it's at its end if it was before, or is new.
    Otherwise it's vertically wherever puts its anchor's top edge as far below `padding_top` as it was,
    if its anchor is still laid out, and otherwise where it was.
    """
    if prior is None:
        return Position(max_offset.x if style.stick_to_end_x else 0, max_offset.y if style.stick_to_end_y else 0)
    x = max_offset.x if style.stick_to_end_x and prior.is_at_end_x else prior.offset.x
    if style.stick_to_end_y and prior.is_at_end_y:
        y = max_offset.y
    elif (anchor := prior.anchor) is not None and (box := boxes.get(anchor.key)) is not None:
        y = int(box[0].y) - padding_top - anchor.distance
    else:
        y = prior.offset.y
    return Position(x, y)


def scroll_of(requested: Position, max_offset: Position, padding: Region) -> Scroll:
    """
    The scroll of a container with `padding` box that scrolls up to `max_offset`, scrolled to `requested`,
    clamped to how far it can scroll.
    Taffy's scroll width and height, which `max_offset` comes from, are how far the content reaches
    past the padding box, absolutely positioned descendants included.
    """
    unclamped = Scroll(offset=requested, max_offset=max_offset, view_width=padding.width, view_height=padding.height)
    return replace(unclamped, offset=unclamped.clamp(requested))


@lru_cache(maxsize=2**12)
def clipped_axes(style: Style) -> tuple[bool, bool]:
    """Whether an element with `style` clips its children horizontally and vertically, from its overflow on each axis."""
    layout = style.layout
    return layout.overflow_x != waxy.Overflow.Visible, layout.overflow_y != waxy.Overflow.Visible


def child_clip(
    clip: Region | None, screen: Region, parent: Rects, clip_to: ClipTo, clips_x: bool, clips_y: bool
) -> Region | None:
    """
    The clip of a child with `clip_to` whose `parent` has `clip`:
    `screen` for an unclipped child, and otherwise `clip`,
    cut down to the parent's padding or border box on each axis the parent clips,
    or `None` if nothing is left.
    """
    match clip_to:
        case "screen":
            return screen
        case "padding":
            box = parent.padding
        case "border":
            box = parent.border
        case _ as unreachable:
            assert_never(unreachable)
    if clip is None or not (clips_x or clips_y):
        return clip
    clipped = Region(
        left=max(clip.left, box.left) if clips_x else clip.left,
        top=max(clip.top, box.top) if clips_y else clip.top,
        right=min(clip.right, box.right) if clips_x else clip.right,
        bottom=min(clip.bottom, box.bottom) if clips_y else clip.bottom,
    )
    return None if clipped.is_empty else clipped


def paint_order(root: ShadowNode, visible: Container[NodeKey]) -> list[ShadowNode]:
    """
    The nodes of `root`'s subtree whose keys are in `visible`, in the order they're painted,
    with `root` forming a stacking context whatever its style sets, as CSS's root element does.

    A node whose style sets `z` forms a stacking context:
    it and its descendants paint as a unit at its `z`, and its descendants' `z` orders them only within it.
    A node that doesn't set `z` forms none, so its descendants join the nearest context above it, alongside it.
    A node outside `visible` is hidden, and so is every node beneath it.
    """
    ordered: list[ShadowNode] = []
    _paint_context(root, visible, ordered)
    return ordered


def _paint_context(context: ShadowNode, visible: Container[NodeKey], ordered: list[ShadowNode]) -> None:
    """
    Appends `context` and then its members, sorted by their `z`, where a member that sets none counts as 0.
    The sort is stable, so members with equal `z` keep tree order, and a member that forms a context
    appends its whole context in its place.
    """
    ordered.append(context)
    for member in sorted(_members(context, visible), key=_stacking_z):
        if member.element.style.resolved.z is None:
            ordered.append(member)
        else:
            _paint_context(member, visible, ordered)


def _members(context: ShadowNode, visible: Container[NodeKey]) -> list[ShadowNode]:
    """
    The visible nodes that belong to `context`'s stacking context, in tree order,
    with an explicit stack, since nested generators would pass each node up through every ancestor's.
    """
    members = []
    stack = list(reversed(context.children))
    while stack:
        node = stack.pop()
        if node.key not in visible:
            continue
        members.append(node)
        if node.element.style.resolved.z is None:
            stack.extend(reversed(node.children))
    return members


def _stacking_z(node: ShadowNode) -> int:
    """The `z` a member sorts by within its stacking context, which is 0 for a member that sets none."""
    return node.element.style.resolved.z or 0


UNMEASURED = sentinel("UNMEASURED")


@dataclass(eq=False, slots=True)
class MeasurableText:
    """
    What layout needs to size a `Text`: its cells and how they wrap,
    with the size they wrap to at each width already asked about.

    Taffy asks a leaf about a dozen distinct questions per layout, but the answer depends only on
    one effective width, so most questions repeat one already answered.
    """

    cells: tuple[StyledGrapheme, ...]
    wrap: TextWrap
    sizes: dict[int | None, tuple[int, int]] = field(default_factory=dict)
    min_content_width: int | UNMEASURED | None = UNMEASURED

    @classmethod
    def of(cls, source: TextSource) -> MeasurableText:
        content, text_style, wrap = source
        return cls(cells=text_cells(content, text_style), wrap=wrap)

    def size_at(self, width: int | None) -> tuple[int, int]:
        """The widest line and the line count when wrapped at `width` (unlimited if `None`)."""
        try:
            return self.sizes[width]
        except KeyError:
            lines = wrap_cells(self.cells, self.wrap, width)
            size = self.sizes[width] = (max((cells_width(line) for line in lines), default=0), len(lines))
            return size

    def narrowest_width(self) -> int | None:
        """
        The narrowest width this text takes without breaking a word, as CSS's `min-content` is for text:
        its widest word if it wraps, or `None` (unlimited) if it doesn't.
        """
        if self.min_content_width is UNMEASURED:
            self.min_content_width = _min_content_width(self.cells, self.wrap)
        return self.min_content_width


def _measure_text(
    known: waxy.KnownSize,
    available: waxy.AvailableSize,
    context: MeasurableText,
) -> waxy.Size:
    known_width = known.width
    known_height = known.height

    width: int | None
    if known_width is not None:
        width = int(known_width)
    else:
        match available.width:
            case waxy.Definite(value=value):
                width = int(value)
            case waxy.MinContent():
                width = context.narrowest_width()
            case waxy.MaxContent():
                width = None
            case _ as unreachable:
                assert_never(unreachable)

    widest, line_count = context.size_at(width)

    # Positional, because pyo3 matches keyword arguments by name on every call, which nearly doubles its cost.
    return waxy.Size(
        known_width if known_width is not None else float(widest),
        known_height if known_height is not None else float(line_count),
    )


def _min_content_width(cells: Iterable[StyledGrapheme], wrap: TextWrap) -> int | None:
    """The widest word in `cells`, or `None` (unlimited) if they don't wrap."""
    if wrap == "none":
        return None

    return max(
        (
            cells_width(word)
            for paragraph in _split_paragraphs(cells)
            for word in _extract_words_and_spaces(paragraph)[0]
        ),
        default=None,
    )


@lru_cache(maxsize=2**12)
def _resolve_layout(
    position: waxy.Point, layout: waxy.Layout, clip: Region | None, scrolled_x: int, scrolled_y: int
) -> Rects:
    """
    The cell regions of one node's boxes, from its absolute border-box position,
    moved left by `scrolled_x` and up by `scrolled_y`, the sum of the offsets of the scroll containers above it,
    inside `clip`.

    Taffy's rounding snaps each absolute edge to a whole cell, so every value here is already
    integral and adjacent boxes share edges without gaps or overlaps.
    A scroll container whose `scrollbar_width` isn't 0 reserves that much space for a scrollbar on each axis it scrolls,
    which counterweight doesn't draw. Taffy narrows its children by that space without saying where it is;
    as in CSS, it lies between the border and the padding box, so the padding box excludes it.

    Cached because most nodes keep their position, layout and clip from one frame to the next,
    and building the regions is most of the cost of reading layouts back.
    """
    left = int(position.x) - scrolled_x
    top = int(position.y) - scrolled_y
    border = Region(left=left, top=top, right=left + int(layout.size.width), bottom=top + int(layout.size.height))

    margin_widths = layout.margin
    margin = Region(
        left=border.left - int(margin_widths.left),
        top=border.top - int(margin_widths.top),
        right=border.right + int(margin_widths.right),
        bottom=border.bottom + int(margin_widths.bottom),
    )

    border_widths = layout.border
    scrollbars = layout.scrollbar_size
    padding = Region(
        left=border.left + int(border_widths.left),
        top=border.top + int(border_widths.top),
        right=border.right - int(border_widths.right) - int(scrollbars.width),
        bottom=border.bottom - int(border_widths.bottom) - int(scrollbars.height),
    )

    padding_widths = layout.padding
    content = Region(
        left=padding.left + int(padding_widths.left),
        top=padding.top + int(padding_widths.top),
        right=padding.right - int(padding_widths.right),
        bottom=padding.bottom - int(padding_widths.bottom),
    )

    return Rects(
        content=content,
        padding=padding,
        border=border,
        margin=margin,
        clip=clip,
        visible=None if clip is None else border.intersection(clip),
    )


def cells_width(cells: Iterable[StyledGrapheme]) -> int:
    """How many terminal cells `cells` take side by side."""
    return sum(cell.width for cell in cells)


def _split_paragraphs(cells: Iterable[StyledGrapheme]) -> list[list[StyledGrapheme]]:
    paragraphs: list[list[StyledGrapheme]] = []
    current: list[StyledGrapheme] = []
    for cell in cells:
        if cell.grapheme in LINE_BREAKS:
            paragraphs.append(current)
            current = []
        else:
            current.append(cell)
    paragraphs.append(current)
    return paragraphs


def _extract_words_and_spaces(
    paragraph: list[StyledGrapheme],
) -> tuple[list[list[StyledGrapheme]], list[list[StyledGrapheme]]]:
    """Split a paragraph into (words, spaces).

    words[i] is a non-space run; spaces[i] is the space run between words[i] and words[i+1].
    Leading and trailing spaces are discarded.
    len(spaces) == len(words) - 1.
    """
    words: list[list[StyledGrapheme]] = []
    spaces: list[list[StyledGrapheme]] = []
    current_word: list[StyledGrapheme] = []
    current_space: list[StyledGrapheme] = []

    for cell in paragraph:
        if cell.grapheme == " ":
            if current_word:
                # We are in a word — start collecting the trailing space run.
                current_space.append(cell)
        else:
            if current_space:
                # We just finished a space run between two words.
                words.append(current_word)
                spaces.append(current_space)
                current_word = [cell]
                current_space = []
            elif current_word:
                current_word.append(cell)
            else:
                # Start of the first word (leading spaces already dropped).
                current_word = [cell]

    if current_word:
        words.append(current_word)
    # Trailing spaces in current_space are discarded.

    return words, spaces


def _flatten_long_words(
    words: list[list[StyledGrapheme]],
    spaces: list[list[StyledGrapheme]],
    width: int,
) -> tuple[list[list[StyledGrapheme]], list[list[StyledGrapheme]]]:
    """Break any word wider than width into chunks at most width wide.

    Space runs between chunks of the same word become [] (no space between hyphenated chunks).
    Returns (flat_words, flat_spaces) with len(flat_spaces) == len(flat_words) - 1.
    """
    flat_words: list[list[StyledGrapheme]] = []
    flat_spaces: list[list[StyledGrapheme]] = []

    for i, word in enumerate(words):
        if cells_width(word) > width:
            chunks = _break_long_word(word, width)
        else:
            chunks = [word]

        for j, chunk in enumerate(chunks):
            if flat_words:
                # Insert a space before this chunk:
                # - [] (no space) between hyphenated sub-chunks of the same word
                # - the real inter-word space run between different words
                flat_spaces.append([] if j > 0 else spaces[i - 1] if i > 0 else [])
            flat_words.append(chunk)

    return flat_words, flat_spaces


def _break_long_word(word: list[StyledGrapheme], width: int) -> list[list[StyledGrapheme]]:
    """
    Break a word that is wider than width into chunks at most width wide, hyphenating all but the last,
    without splitting a grapheme cluster.

    A cluster too wide to fit beside a hyphen gets a chunk of its own, without one,
    even if that chunk is wider than width.
    """
    room = width - 1 if width > 1 else width
    chunks: list[list[StyledGrapheme]] = []
    remaining = cells_width(word)
    i = 0
    while remaining > width:
        chunk: list[StyledGrapheme] = []
        chunk_width = 0
        while chunk_width + word[i].width <= room:
            chunk.append(word[i])
            chunk_width += word[i].width
            i += 1
        if not chunk:
            chunk = [word[i]]
            chunk_width = word[i].width
            i += 1
        elif room < width:
            chunk.append(StyledGrapheme(grapheme="-", style=chunk[-1].style))
        chunks.append(chunk)
        remaining -= chunk_width
    if i < len(word):
        chunks.append(word[i:])
    return chunks


def _wrap_greedy(paragraph: list[StyledGrapheme], width: int) -> list[list[StyledGrapheme]]:
    words, spaces = _extract_words_and_spaces(paragraph)
    flat_words, flat_spaces = _flatten_long_words(words, spaces, width)
    return _wrap_at_target(flat_words, [cells_width(word) for word in flat_words], flat_spaces, width)


def _greedy_line_count(word_widths: list[int], flat_spaces: list[list[StyledGrapheme]], width: int) -> int:
    count = 1
    length = 0
    pending_space_len = 0

    for i, wlen in enumerate(word_widths):
        if not length:
            length = wlen
        elif length + pending_space_len + wlen <= width:
            length += pending_space_len + wlen
        else:
            count += 1
            length = wlen
        pending_space_len = len(flat_spaces[i]) if i < len(flat_spaces) else 0

    return count


def _wrap_at_target(
    flat_words: list[list[StyledGrapheme]],
    word_widths: list[int],
    flat_spaces: list[list[StyledGrapheme]],
    target: int,
) -> list[list[StyledGrapheme]]:
    """
    Greedy wrap of already-broken words, targeting `target` width for line breaks.

    Spaces are always one cell wide, so a space run's width is its length.
    """
    lines: list[list[StyledGrapheme]] = []
    current: list[StyledGrapheme] = []
    current_width = 0
    pending_space: list[StyledGrapheme] = []

    for i, (word, word_width) in enumerate(zip(flat_words, word_widths, strict=True)):
        if not current:
            current = list(word)
            current_width = word_width
        elif current_width + len(pending_space) + word_width <= target:
            current.extend(pending_space)
            current.extend(word)
            current_width += len(pending_space) + word_width
        else:
            lines.append(current)
            current = list(word)
            current_width = word_width
        if i < len(flat_spaces):
            pending_space = flat_spaces[i]

    lines.append(current)
    return lines


def _wrap_balance(paragraph: list[StyledGrapheme], width: int) -> list[list[StyledGrapheme]]:
    words, spaces = _extract_words_and_spaces(paragraph)
    if not words:
        return [[]]

    flat_words, flat_spaces = _flatten_long_words(words, spaces, width)
    word_widths = [cells_width(word) for word in flat_words]

    k = _greedy_line_count(word_widths, flat_spaces, width)

    if k <= 1:
        return _wrap_at_target(flat_words, word_widths, flat_spaces, width)

    # Binary search for the narrowest target that still yields k lines.
    lo, hi = 1, width
    while lo < hi:
        mid = (lo + hi) // 2
        if _greedy_line_count(word_widths, flat_spaces, mid) <= k:
            hi = mid
        else:
            lo = mid + 1

    return _wrap_at_target(flat_words, word_widths, flat_spaces, lo)


def _wrap_pretty(paragraph: list[StyledGrapheme], width: int) -> list[list[StyledGrapheme]]:
    """DP optimal line-breaking minimizing sum of squared slack on non-last lines."""
    words, spaces = _extract_words_and_spaces(paragraph)
    if not words:
        return [[]]

    flat_words, flat_spaces = _flatten_long_words(words, spaces, width)

    n = len(flat_words)

    # Precompute prefix sums of word widths so line_length is O(1).
    # prefix[i] = sum of the widths of flat_words[0] .. flat_words[i-1]
    prefix: list[int] = [0] * (n + 1)
    for idx in range(n):
        prefix[idx + 1] = prefix[idx] + cells_width(flat_words[idx])

    # Precompute prefix sums of space lengths between words.
    # space_prefix[k] = sum of len(flat_spaces[0]) .. len(flat_spaces[k-1])
    # (size n, space_prefix[0] = 0)
    space_prefix: list[int] = [0] * n
    for idx in range(1, n):
        space_prefix[idx] = space_prefix[idx - 1] + len(flat_spaces[idx - 1])

    def line_length(i: int, j: int) -> int:
        word_len = prefix[j] - prefix[i]
        space_len = space_prefix[j - 1] - space_prefix[i] if j > i + 1 else 0
        return word_len + space_len

    # dp[i] = min cost to break flat_words[i..n-1], bp[i] = best j for first break after i.
    # bp[i] is always set to j > i before use because every word may occupy a line of its own,
    # even the one-cluster chunks _flatten_long_words leaves wider than width (a wide cluster at width 1).
    dp: list[float] = [inf] * (n + 1)
    bp: list[int] = [0] * (n + 1)
    dp[n] = 0.0

    for i in range(n - 1, -1, -1):
        for j in range(i + 1, n + 1):
            ll = line_length(i, j)
            if ll > width and j > i + 1:
                break
            slack = max(width - ll, 0)
            if j == n:
                cost = 0.0
            else:
                cost = float(slack) ** 2
            total = cost + dp[j]
            if total < dp[i]:
                dp[i] = total
                bp[i] = j

    # Reconstruct lines.
    lines: list[list[StyledGrapheme]] = []
    i = 0
    while i < n:
        j = bp[i]
        line: list[StyledGrapheme] = []
        for k in range(i, j):
            if k > i:
                # Insert the actual space run between flat_words[k-1] and flat_words[k].
                line.extend(flat_spaces[k - 1])
            line.extend(flat_words[k])
        lines.append(line)
        i = j

    return lines


def wrap_cells(
    cells: Iterable[StyledGrapheme],
    wrap: TextWrap,
    width: int | None,
) -> list[list[StyledGrapheme]]:
    if width is not None and width <= 0:
        return []

    paragraphs = _split_paragraphs(cells)

    if wrap == "none" or width is None:
        return paragraphs

    result: list[list[StyledGrapheme]] = []
    for paragraph in paragraphs:
        if wrap == "stable":
            result.extend(_wrap_greedy(paragraph, width))
        elif wrap == "balance":
            result.extend(_wrap_balance(paragraph, width))
        elif wrap == "pretty":
            result.extend(_wrap_pretty(paragraph, width))
        else:
            assert_never(wrap)
    return result
