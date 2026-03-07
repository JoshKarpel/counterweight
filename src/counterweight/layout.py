from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, assert_never

import waxy

from counterweight.elements import AnyElement, CellPaint, Div, Text
from counterweight.styles.styles import TextWrap

if TYPE_CHECKING:
    from counterweight.shadow import ShadowNode


@dataclass(frozen=True, slots=True)
class ResolvedLayout:
    content: waxy.Rect
    padding: waxy.Rect
    border: waxy.Rect
    margin: waxy.Rect
    order: int


# right < left and bottom < top → zero-width/height in the inclusive coordinate system
_EMPTY_RECT = waxy.Rect(left=0, right=-1, top=0, bottom=-1)

INITIAL_RESOLVED_LAYOUT = ResolvedLayout(
    content=_EMPTY_RECT,
    padding=_EMPTY_RECT,
    border=_EMPTY_RECT,
    margin=_EMPTY_RECT,
    order=0,
)


def compute_layout(
    shadow: ShadowNode,
    available: waxy.AvailableSize,
) -> list[tuple[AnyElement, ResolvedLayout]]:
    """
    Build a waxy tree from the shadow tree, compute layout, and return
    a flat list of (element, resolved_layout) pairs.
    """
    tree: waxy.TaffyTree[Text] = waxy.TaffyTree()
    node_map: dict[waxy.NodeId, ShadowNode] = {}

    root_id = _build_node(tree, shadow, node_map)

    tree.compute_layout(root_id, available, measure=_measure_text)

    results: list[tuple[AnyElement, ResolvedLayout]] = []
    _extract_layout(tree, root_id, node_map, abs_x=0.0, abs_y=0.0, results=results)

    return results


def _build_node(
    tree: waxy.TaffyTree[Text],
    shadow: ShadowNode,
    node_map: dict[waxy.NodeId, ShadowNode],
) -> waxy.NodeId:
    element = shadow.element

    match element:
        case Text():
            node_id = tree.new_leaf_with_context(element.style.layout, element)
        case Div():
            child_ids = [_build_node(tree, child_shadow, node_map) for child_shadow in shadow.children]
            node_id = tree.new_with_children(element.style.layout, child_ids)
        case _:
            assert_never(element)

    node_map[node_id] = shadow
    return node_id


def _measure_text(
    known: waxy.KnownSize,
    available: waxy.AvailableSize,
    context: Text,
) -> waxy.Size:
    width: float | None = known.width
    if width is None and isinstance(available.width, waxy.Definite):
        width = available.width.value

    lines = wrap_cells(
        context.cells,
        context.style.text_wrap,
        int(width) if width is not None else None,
    )

    return waxy.Size(
        width=known.width if known.width is not None else float(max((len(l) for l in lines), default=0)),
        height=known.height if known.height is not None else float(len(lines)),
    )


def _extract_layout(
    tree: waxy.TaffyTree[Text],
    node_id: waxy.NodeId,
    node_map: dict[waxy.NodeId, ShadowNode],
    abs_x: float,
    abs_y: float,
    results: list[tuple[AnyElement, ResolvedLayout]],
) -> None:
    """Walk tree top-down, accumulating absolute positions.

    abs_x/abs_y is the absolute position of the current node's parent's border box origin,
    i.e. the origin that taffy's relative ``layout.location`` is measured from.
    For the root node, pass (0, 0).
    """
    layout = tree.unrounded_layout(node_id)
    shadow = node_map[node_id]

    # display:nil hides the entire subtree, matching CSS display:none semantics
    if shadow.element.style.layout.display == waxy.Display.Nil:
        return

    border_abs_x = abs_x + layout.location.x
    border_abs_y = abs_y + layout.location.y

    # floor for left/top (round toward -inf) so negative coordinates work.
    # ceil(sum - 0.5) - 1 is "round half down" for the right/bottom edge:
    #   - avoids Python's banker's rounding of exact half-integers (e.g. 45.5
    #     from auto-centering a 21-wide element at x=24.5 rounds to 45, not 46)
    #   - snaps near-integer taffy floats (e.g. 20.000000048 → 19, not 20)
    bx = math.floor(border_abs_x)
    by = math.floor(border_abs_y)
    br = math.ceil(border_abs_x + layout.size.width - 0.5) - 1
    bb = math.ceil(border_abs_y + layout.size.height - 0.5) - 1

    border_rect = waxy.Rect(left=bx, right=br, top=by, bottom=bb)

    margin_rect = waxy.Rect(
        left=bx - int(layout.margin.left),
        right=br + int(layout.margin.right),
        top=by - int(layout.margin.top),
        bottom=bb + int(layout.margin.bottom),
    )

    pl = bx + int(layout.border.left)
    pt = by + int(layout.border.top)
    pr = br - int(layout.border.right)
    pb = bb - int(layout.border.bottom)
    padding_rect = waxy.Rect(left=pl, right=pr, top=pt, bottom=pb)

    content_rect = waxy.Rect(
        left=pl + int(layout.padding.left),
        right=pr - int(layout.padding.right),
        top=pt + int(layout.padding.top),
        bottom=pb - int(layout.padding.bottom),
    )

    resolved = ResolvedLayout(
        content=content_rect,
        padding=padding_rect,
        border=border_rect,
        margin=margin_rect,
        order=len(results),
    )
    results.append((shadow.element, resolved))

    shadow.hooks.dims = resolved

    for child_node_id in tree.children(node_id):
        _extract_layout(tree, child_node_id, node_map, border_abs_x, border_abs_y, results)


def wrap_cells(
    cells: Iterable[CellPaint],
    wrap: TextWrap,
    width: int | None,
) -> list[list[CellPaint]]:
    if width is not None and width <= 0:
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
