from __future__ import annotations

import waxy

from counterweight.elements import AnyElement, Div
from counterweight.hooks.impls import Hooks
from counterweight.layout import ResolvedLayout, compute_layout
from counterweight.shadow import ShadowNode
from counterweight.styles.styles import Style
from counterweight.styles.utilities import (
    border_all,
    border_collapse,
    col,
    grow,
    inset_left,
    inset_top,
    position_absolute,
    row,
    size,
)


def _shadow(element: Div, children: list[ShadowNode] | None = None) -> ShadowNode:
    return ShadowNode(component=None, element=element, hooks=Hooks(), children=children or [])


def _layout(root: ShadowNode, w: int = 60, h: int = 20) -> list[tuple[AnyElement, ResolvedLayout]]:
    return compute_layout(root, waxy.AvailableSize(width=waxy.Definite(w), height=waxy.Definite(h)))


def _layout_screened(root: ShadowNode, w: int = 60, h: int = 20) -> list[tuple[AnyElement, ResolvedLayout]]:
    """Wrap root in a fixed-size grid container, matching what app.py does."""
    screen_style = Style(
        layout=waxy.Style(display=waxy.Display.Grid, size_width=waxy.Length(w), size_height=waxy.Length(h))
    )
    screen = _shadow(Div(style=screen_style), children=[root])
    return compute_layout(screen, waxy.AvailableSize(width=waxy.Definite(w), height=waxy.Definite(h)))


# ---------------------------------------------------------------------------
# Shared-edge invariant: right border of A == left border of B (and analogously
# for top/bottom) when border_collapse is active.
# ---------------------------------------------------------------------------


def test_row_collapse_two_siblings_share_edge() -> None:
    child_a = _shadow(Div(style=border_all | size(10, 5)))
    child_b = _shadow(Div(style=border_all | size(10, 5)))
    root = _shadow(Div(style=row | border_collapse), children=[child_a, child_b])

    _, layout_a, layout_b = [rl for _, rl in _layout(root)]

    assert layout_a.border.right == layout_b.border.left


def test_col_collapse_two_siblings_share_edge() -> None:
    child_a = _shadow(Div(style=border_all | size(10, 5)))
    child_b = _shadow(Div(style=border_all | size(10, 5)))
    root = _shadow(Div(style=col | border_collapse), children=[child_a, child_b])

    _, layout_a, layout_b = [rl for _, rl in _layout(root)]

    assert layout_a.border.bottom == layout_b.border.top


def test_row_collapse_three_siblings_both_seams_share() -> None:
    child_a = _shadow(Div(style=border_all | size(10, 5)))
    child_b = _shadow(Div(style=border_all | size(10, 5)))
    child_c = _shadow(Div(style=border_all | size(10, 5)))
    root = _shadow(Div(style=row | border_collapse), children=[child_a, child_b, child_c])

    _, layout_a, layout_b, layout_c = [rl for _, rl in _layout(root)]

    assert layout_a.border.right == layout_b.border.left
    assert layout_b.border.right == layout_c.border.left


def test_col_collapse_three_siblings_both_seams_share() -> None:
    child_a = _shadow(Div(style=border_all | size(10, 5)))
    child_b = _shadow(Div(style=border_all | size(10, 5)))
    child_c = _shadow(Div(style=border_all | size(10, 5)))
    root = _shadow(Div(style=col | border_collapse), children=[child_a, child_b, child_c])

    _, layout_a, layout_b, layout_c = [rl for _, rl in _layout(root)]

    assert layout_a.border.bottom == layout_b.border.top
    assert layout_b.border.bottom == layout_c.border.top


def test_row_no_collapse_siblings_are_adjacent_not_overlapping() -> None:
    child_a = _shadow(Div(style=border_all | size(10, 5)))
    child_b = _shadow(Div(style=border_all | size(10, 5)))
    root = _shadow(Div(style=row), children=[child_a, child_b])

    _, layout_a, layout_b = [rl for _, rl in _layout(root)]

    assert layout_a.border.right + 1 == layout_b.border.left


def test_col_no_collapse_siblings_are_adjacent_not_overlapping() -> None:
    child_a = _shadow(Div(style=border_all | size(10, 5)))
    child_b = _shadow(Div(style=border_all | size(10, 5)))
    root = _shadow(Div(style=col), children=[child_a, child_b])

    _, layout_a, layout_b = [rl for _, rl in _layout(root)]

    assert layout_a.border.bottom + 1 == layout_b.border.top


# ---------------------------------------------------------------------------
# Fractional flex widths: when children don't divide the container evenly,
# taffy produces fractional unrounded positions. floor/ceil rounding must still
# produce shared seams under border_collapse.
# ---------------------------------------------------------------------------


def test_row_collapse_fractional_flex_widths_share_edges() -> None:
    # 31px / 3 = 10.333... → fractional unrounded positions
    child_a = _shadow(Div(style=border_all | grow(1)))
    child_b = _shadow(Div(style=border_all | grow(1)))
    child_c = _shadow(Div(style=border_all | grow(1)))
    root = _shadow(Div(style=row | border_collapse), children=[child_a, child_b, child_c])

    _, layout_a, layout_b, layout_c = [rl for _, rl in _layout(root, w=31)]

    assert layout_a.border.right == layout_b.border.left
    assert layout_b.border.right == layout_c.border.left


def test_col_collapse_fractional_flex_heights_share_edges() -> None:
    # 21px / 3 = 7.0 → no fractions, but 22px / 3 = 7.333...
    child_a = _shadow(Div(style=border_all | grow(1)))
    child_b = _shadow(Div(style=border_all | grow(1)))
    child_c = _shadow(Div(style=border_all | grow(1)))
    root = _shadow(Div(style=col | border_collapse), children=[child_a, child_b, child_c])

    _, layout_a, layout_b, layout_c = [rl for _, rl in _layout(root, h=22)]

    assert layout_a.border.bottom == layout_b.border.top
    assert layout_b.border.bottom == layout_c.border.top


# ---------------------------------------------------------------------------
# Fixed-size children: border box dimensions must match the specified size.
# ---------------------------------------------------------------------------


def test_fixed_size_border_box_dimensions() -> None:
    child = _shadow(Div(style=border_all | size(12, 7)))
    root = _shadow(Div(style=row), children=[child])

    _, layout_child = [rl for _, rl in _layout(root)]

    assert layout_child.border.right - layout_child.border.left + 1 == 12
    assert layout_child.border.bottom - layout_child.border.top + 1 == 7


# ---------------------------------------------------------------------------
# Absolute positioning with negative insets: left/top edges must use floor,
# not truncation-toward-zero, so negative coordinates are correct.
# ---------------------------------------------------------------------------


def test_absolute_negative_inset_left() -> None:
    child = _shadow(Div(style=border_all | size(5, 3) | position_absolute | inset_left(-2)))
    root = _shadow(Div(style=size(20, 10)), children=[child])

    _, layout_child = [rl for _, rl in _layout(root)]

    assert layout_child.border.left == -2


def test_absolute_negative_inset_top() -> None:
    child = _shadow(Div(style=border_all | size(5, 3) | position_absolute | inset_top(-1)))
    root = _shadow(Div(style=size(20, 10)), children=[child])

    _, layout_child = [rl for _, rl in _layout(root)]

    assert layout_child.border.top == -1


def test_absolute_negative_insets_preserve_size() -> None:
    # Shifting via insets should not change the element's width or height.
    child = _shadow(Div(style=border_all | size(5, 3) | position_absolute | inset_left(-3) | inset_top(-2)))
    root = _shadow(Div(style=size(20, 10)), children=[child])

    _, layout_child = [rl for _, rl in _layout(root)]

    assert layout_child.border.right - layout_child.border.left + 1 == 5
    assert layout_child.border.bottom - layout_child.border.top + 1 == 3


# ---------------------------------------------------------------------------
# Last-child bottom edge: when taffy produces a bottom float slightly above
# an integer (e.g. 20.000000048 instead of 20.0), rounding must snap it to
# the screen boundary rather than one row past it.
# ---------------------------------------------------------------------------


def test_col_collapse_last_child_bottom_on_screen() -> None:
    # 3 equal-grow rows that together fill a 20-row screen.  The last row's
    # bottom border must land on row 19 (0-indexed), not row 20 (off-screen).
    # Uses _layout_screened to match the app's screen-wrapper, which causes
    # taffy to produce a bottom float slightly above 20.0 (e.g. 20.000000048).
    child_a = _shadow(Div(style=border_all | grow(1)))
    child_b = _shadow(Div(style=border_all | grow(1)))
    child_c = _shadow(Div(style=border_all | grow(1)))
    root = _shadow(Div(style=col | border_collapse), children=[child_a, child_b, child_c])

    # screen=0, root_div=1, child_a=2, child_b=3, child_c=4
    _, _, _layout_a, _layout_b, layout_c = [rl for _, rl in _layout_screened(root, h=20)]

    assert layout_c.border.bottom == 19
