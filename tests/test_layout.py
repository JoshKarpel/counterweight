from __future__ import annotations

import pytest
import waxy

from counterweight.app import screen_element_style
from counterweight.elements import AnyElement, Div, Text
from counterweight.hooks.impls import Hooks
from counterweight.layout import INITIAL_RESOLVED_LAYOUT, ResolvedLayout, compute_layout
from counterweight.shadow import ShadowNode
from counterweight.styles.styles import Style
from counterweight.styles.utilities import (
    align_children_center,
    align_children_center_unsafe,
    align_children_end,
    align_children_end_unsafe,
    border,
    border_collapse,
    border_lightrounded,
    col,
    display_grid,
    display_none,
    fill,
    fit_content_width,
    fr,
    full_height,
    full_width,
    grid_row,
    grid_template_columns,
    grid_template_rows,
    grow,
    height,
    inset_bottom,
    inset_bottom_center,
    inset_left,
    inset_top,
    justify_children_center,
    justify_children_center_unsafe,
    justify_children_end,
    justify_children_end_unsafe,
    justify_children_space_around,
    justify_children_space_evenly,
    length,
    margin_x,
    margin_y,
    max_content_width,
    min_content_width,
    min_width,
    pad,
    percentage,
    position_absolute,
    ratio,
    row,
    shrink,
    size,
    span,
    stretch_width,
    text_wrap_balance,
    text_wrap_pretty,
    text_wrap_stable,
    width,
)


def _shadow(element: AnyElement, children: list[ShadowNode] | None = None) -> ShadowNode:
    return ShadowNode(component=None, element=element, hooks=Hooks(), children=children or [])


def _layout(root: ShadowNode, w: int = 60, h: int = 20) -> list[tuple[AnyElement, ResolvedLayout]]:
    return compute_layout(root, waxy.AvailableSize(width=waxy.Definite(w), height=waxy.Definite(h)))


def _layout_screened(root: ShadowNode, w: int = 60, h: int = 20) -> list[tuple[AnyElement, ResolvedLayout]]:
    """Wrap root in the element the app places the root component in."""
    screen = _shadow(Div(style=screen_element_style(w, h)), children=[root])
    return compute_layout(screen, waxy.AvailableSize(width=waxy.Definite(w), height=waxy.Definite(h)))


# ---------------------------------------------------------------------------
# Shared-edge invariant: right border of A == left border of B (and analogously
# for top/bottom) when border_collapse is active.
# ---------------------------------------------------------------------------


def test_row_collapse_two_siblings_share_edge() -> None:
    child_a = _shadow(Div(style=border | size(10, 5)))
    child_b = _shadow(Div(style=border | size(10, 5)))
    root = _shadow(Div(style=row | border_collapse), children=[child_a, child_b])

    _, layout_a, layout_b = [rl for _, rl in _layout(root)]

    assert layout_a.border.right - 1 == layout_b.border.left


def test_col_collapse_two_siblings_share_edge() -> None:
    child_a = _shadow(Div(style=border | size(10, 5)))
    child_b = _shadow(Div(style=border | size(10, 5)))
    root = _shadow(Div(style=col | border_collapse), children=[child_a, child_b])

    _, layout_a, layout_b = [rl for _, rl in _layout(root)]

    assert layout_a.border.bottom - 1 == layout_b.border.top


def test_row_collapse_three_siblings_both_seams_share() -> None:
    child_a = _shadow(Div(style=border | size(10, 5)))
    child_b = _shadow(Div(style=border | size(10, 5)))
    child_c = _shadow(Div(style=border | size(10, 5)))
    root = _shadow(Div(style=row | border_collapse), children=[child_a, child_b, child_c])

    _, layout_a, layout_b, layout_c = [rl for _, rl in _layout(root)]

    assert layout_a.border.right - 1 == layout_b.border.left
    assert layout_b.border.right - 1 == layout_c.border.left


def test_col_collapse_three_siblings_both_seams_share() -> None:
    child_a = _shadow(Div(style=border | size(10, 5)))
    child_b = _shadow(Div(style=border | size(10, 5)))
    child_c = _shadow(Div(style=border | size(10, 5)))
    root = _shadow(Div(style=col | border_collapse), children=[child_a, child_b, child_c])

    _, layout_a, layout_b, layout_c = [rl for _, rl in _layout(root)]

    assert layout_a.border.bottom - 1 == layout_b.border.top
    assert layout_b.border.bottom - 1 == layout_c.border.top


def test_row_no_collapse_siblings_are_adjacent_not_overlapping() -> None:
    child_a = _shadow(Div(style=border | size(10, 5)))
    child_b = _shadow(Div(style=border | size(10, 5)))
    root = _shadow(Div(style=row), children=[child_a, child_b])

    _, layout_a, layout_b = [rl for _, rl in _layout(root)]

    assert layout_a.border.right == layout_b.border.left


def test_col_no_collapse_siblings_are_adjacent_not_overlapping() -> None:
    child_a = _shadow(Div(style=border | size(10, 5)))
    child_b = _shadow(Div(style=border | size(10, 5)))
    root = _shadow(Div(style=col), children=[child_a, child_b])

    _, layout_a, layout_b = [rl for _, rl in _layout(root)]

    assert layout_a.border.bottom == layout_b.border.top


# ---------------------------------------------------------------------------
# Fractional flex widths: when children don't divide the container evenly,
# taffy produces fractional unrounded positions. Rounding to cells must still
# produce shared seams under border_collapse.
# ---------------------------------------------------------------------------


def test_row_collapse_fractional_flex_widths_share_edges() -> None:
    # 31px / 3 = 10.333... → fractional unrounded positions
    child_a = _shadow(Div(style=border | grow(1)))
    child_b = _shadow(Div(style=border | grow(1)))
    child_c = _shadow(Div(style=border | grow(1)))
    root = _shadow(Div(style=row | border_collapse), children=[child_a, child_b, child_c])

    _, layout_a, layout_b, layout_c = [rl for _, rl in _layout(root, w=31)]

    assert layout_a.border.right - 1 == layout_b.border.left
    assert layout_b.border.right - 1 == layout_c.border.left


def test_col_collapse_fractional_flex_heights_share_edges() -> None:
    # 21px / 3 = 7.0 → no fractions, but 22px / 3 = 7.333...
    child_a = _shadow(Div(style=border | grow(1)))
    child_b = _shadow(Div(style=border | grow(1)))
    child_c = _shadow(Div(style=border | grow(1)))
    root = _shadow(Div(style=col | border_collapse), children=[child_a, child_b, child_c])

    _, layout_a, layout_b, layout_c = [rl for _, rl in _layout(root, h=22)]

    assert layout_a.border.bottom - 1 == layout_b.border.top
    assert layout_b.border.bottom - 1 == layout_c.border.top


# ---------------------------------------------------------------------------
# Fixed-size children: border box dimensions must match the specified size.
# ---------------------------------------------------------------------------


def test_fixed_size_border_box_dimensions() -> None:
    child = _shadow(Div(style=border | size(12, 7)))
    root = _shadow(Div(style=row), children=[child])

    _, layout_child = [rl for _, rl in _layout(root)]

    assert layout_child.border.width == 12
    assert layout_child.border.height == 7


# ---------------------------------------------------------------------------
# Absolute positioning with negative insets: negative coordinates must come out
# exact, without truncation toward zero moving an edge.
# ---------------------------------------------------------------------------


def test_absolute_negative_inset_left() -> None:
    child = _shadow(Div(style=border | size(5, 3) | position_absolute | inset_left(-2)))
    root = _shadow(Div(style=size(20, 10)), children=[child])

    _, layout_child = [rl for _, rl in _layout(root)]

    assert layout_child.border.left == -2


def test_absolute_negative_inset_top() -> None:
    child = _shadow(Div(style=border | size(5, 3) | position_absolute | inset_top(-1)))
    root = _shadow(Div(style=size(20, 10)), children=[child])

    _, layout_child = [rl for _, rl in _layout(root)]

    assert layout_child.border.top == -1


def test_absolute_negative_insets_preserve_size() -> None:
    # Shifting via insets should not change the element's width or height.
    child = _shadow(Div(style=border | size(5, 3) | position_absolute | inset_left(-3) | inset_top(-2)))
    root = _shadow(Div(style=size(20, 10)), children=[child])

    _, layout_child = [rl for _, rl in _layout(root)]

    assert layout_child.border.width == 5
    assert layout_child.border.height == 3


# ---------------------------------------------------------------------------
# Last-child bottom edge: when taffy produces a bottom float slightly above
# an integer (e.g. 20.000000048 instead of 20.0), rounding must snap it to
# the screen boundary rather than one row past it.
# ---------------------------------------------------------------------------


def test_col_collapse_last_child_bottom_on_screen() -> None:
    # 3 equal-grow rows that together fill a 20-row screen.  The last row's
    # bottom border must land on row 19 (0-indexed), not row 20 (off-screen),
    # so its exclusive bottom edge is 20.
    # Uses _layout_screened to match the app's screen-wrapper, which causes
    # taffy to produce a bottom float slightly above 20.0 (e.g. 20.000000048).
    child_a = _shadow(Div(style=border | grow(1)))
    child_b = _shadow(Div(style=border | grow(1)))
    child_c = _shadow(Div(style=border | grow(1)))
    root = _shadow(Div(style=col | border_collapse), children=[child_a, child_b, child_c])

    # screen=0, root_div=1, child_a=2, child_b=3, child_c=4
    _, _, _layout_a, _layout_b, layout_c = [rl for _, rl in _layout_screened(root, h=20)]

    assert layout_c.border.bottom == 20


# ---------------------------------------------------------------------------
# Auto-centering via inset_left=Auto / inset_right=Auto produces a fractional
# location.x (e.g. 24.5) when the element width and container width have
# different parities.  The rounding must not inflate the element's cell width.
# ---------------------------------------------------------------------------


def test_auto_centered_text_has_correct_width() -> None:
    # " Bottom-Center Title " is 21 chars.  The parent is 70 wide with a 1-cell
    # border and 1-cell pad, giving a padding box of 68.  (68 - 21) / 2 = 23.5,
    # so taffy places the element at x=24.5 (padding_box_left=1 + 23.5).
    # Python's banker's rounding would round 45.5 → 46 giving width 22; we
    # must get exactly 21.
    title_shadow = ShadowNode(
        component=None,
        element=Text(content=" Bottom-Center Title ", style=inset_bottom_center | inset_bottom(-1)),
        hooks=Hooks(),
    )
    container_shadow = _shadow(
        Div(
            style=row
            | grow(1)
            | justify_children_center
            | align_children_center
            | border
            | border_lightrounded
            | pad(1)
        ),
        children=[title_shadow],
    )
    root = _shadow(Div(style=col), children=[container_shadow])

    results = _layout_screened(root, w=70, h=5)
    title_layouts = [rl for elem, rl in results if isinstance(elem, Text)]
    assert len(title_layouts) == 1
    layout = title_layouts[0]
    assert layout.border.width == 21


# ---------------------------------------------------------------------------
# justify_content fractional placement: a fixed-size child must not gain an
# extra row/column when space_evenly or space_around places it at a fractional
# position whose end coordinate has frac > 0.5.
# ---------------------------------------------------------------------------


def test_space_evenly_col_does_not_inflate_child_height() -> None:
    # H=29, child_a=6, child_b=4: gap=(29-6-4)/3=19/3=6.333...
    # child_b floats to y=18.667, end=22.667 → height must stay 4, not 5.
    child_a = _shadow(Div(style=size(20, 6)))
    child_b = _shadow(Div(style=size(20, 4)))
    root = _shadow(Div(style=col | justify_children_space_evenly), children=[child_a, child_b])

    _, _, _layout_a, layout_b = [rl for _, rl in _layout_screened(root, w=60, h=29)]

    assert layout_b.border.height == 4


def test_space_around_col_does_not_inflate_child_height() -> None:
    # H=31, child_a=6, child_b=4: G=(31-6-4)/2=10.5 per item.
    # child_b floats to y=21.75, end=25.75 → height must stay 4, not 5.
    child_a = _shadow(Div(style=size(20, 6)))
    child_b = _shadow(Div(style=size(20, 4)))
    root = _shadow(Div(style=col | justify_children_space_around), children=[child_a, child_b])

    _, _, _layout_a, layout_b = [rl for _, rl in _layout_screened(root, w=60, h=31)]

    assert layout_b.border.height == 4


def test_space_evenly_row_does_not_inflate_child_width() -> None:
    # W=29, child_a=6, child_b=4: gap=(29-6-4)/3=19/3=6.333...
    # child_b floats to x=18.667, end=22.667 → width must stay 4, not 5.
    child_a = _shadow(Div(style=size(6, 3)))
    child_b = _shadow(Div(style=size(4, 3)))
    root = _shadow(Div(style=row | justify_children_space_evenly), children=[child_a, child_b])

    _, _, _layout_a, layout_b = [rl for _, rl in _layout_screened(root, w=29, h=20)]

    assert layout_b.border.width == 4


def test_text_wrap_stable_measures_correct_height() -> None:
    # "hello world" at width=8 → greedy wraps to 2 lines: ["hello", "world"]
    # Use col (flex-direction: column) so the text's width is cross-axis stretched
    # to 8, giving taffy a definite known.width to pass to the measure callback.
    text_node = _shadow(Text(content="hello world", style=text_wrap_stable))
    container = _shadow(
        Div(style=col | Style(layout=waxy.Style(size_width=waxy.Length(8)))),
        children=[text_node],
    )

    results = _layout(container, w=20, h=20)
    text_layout = next(rl for el, rl in results if isinstance(el, Text))

    assert text_layout.border.height == 2


def test_text_wrap_balance_measures_correct_height() -> None:
    # "hello world" at width=8 → balance wraps to 2 lines (same line count as greedy)
    text_node = _shadow(Text(content="hello world", style=text_wrap_balance))
    container = _shadow(
        Div(style=col | Style(layout=waxy.Style(size_width=waxy.Length(8)))),
        children=[text_node],
    )

    results = _layout(container, w=20, h=20)
    text_layout = next(rl for el, rl in results if isinstance(el, Text))

    assert text_layout.border.height == 2


def test_text_wrap_pretty_measures_correct_height() -> None:
    # "hello world" at width=8 → pretty wraps to 2 lines (same line count as greedy)
    text_node = _shadow(Text(content="hello world", style=text_wrap_pretty))
    container = _shadow(
        Div(style=col | Style(layout=waxy.Style(size_width=waxy.Length(8)))),
        children=[text_node],
    )

    results = _layout(container, w=20, h=20)
    text_layout = next(rl for el, rl in results if isinstance(el, Text))

    assert text_layout.border.height == 2


def test_hidden_subtree_produces_no_resolved_layout() -> None:
    visible = _shadow(Text(content="visible"))
    hidden_child = _shadow(Text(content="hidden child"))
    hidden = _shadow(Div(style=display_none), children=[hidden_child])
    root = _shadow(Div(style=col), children=[visible, hidden])

    elements = [element for element, _ in _layout(root)]

    assert elements == [root.element, visible.element]


def test_node_hidden_after_a_visible_frame_reports_empty_regions() -> None:
    hooks = Hooks()
    shown = ShadowNode(component=None, element=Div(style=size(5, 3)), hooks=hooks)
    _layout(_shadow(Div(style=col), children=[shown]))
    assert hooks.dims != INITIAL_RESOLVED_LAYOUT

    hidden = ShadowNode(component=None, element=Div(style=size(5, 3) | display_none), hooks=hooks)
    _layout(_shadow(Div(style=col), children=[hidden]))

    assert hooks.dims == INITIAL_RESOLVED_LAYOUT


@pytest.mark.parametrize(
    "alignment",
    [justify_children_center, justify_children_end, align_children_center, align_children_end],
)
def test_child_larger_than_its_container_starts_at_the_start_edge(alignment: Style) -> None:
    child = _shadow(Div(style=size(8, 8) | shrink(0)))
    root = _shadow(Div(style=row | size(5, 5) | alignment), children=[child])

    _, layout_child = [rl for _, rl in _layout(root)]

    assert (layout_child.border.left, layout_child.border.top) == (0, 0)


@pytest.mark.parametrize(
    ("alignment", "start_edge"),
    [
        (justify_children_center_unsafe, "left"),
        (justify_children_end_unsafe, "left"),
        (align_children_center_unsafe, "top"),
        (align_children_end_unsafe, "top"),
    ],
)
def test_unsafe_alignment_overflows_child_past_the_start_edge(alignment: Style, start_edge: str) -> None:
    child = _shadow(Div(style=size(8, 8) | shrink(0)))
    root = _shadow(Div(style=row | size(5, 5) | alignment), children=[child])

    _, layout_child = [rl for _, rl in _layout(root)]

    assert getattr(layout_child.border, start_edge) < 0


@pytest.mark.parametrize(
    ("keyword", "expected_width"),
    [(min_content_width, 5), (max_content_width, 11), (fit_content_width, 11), (stretch_width, 40)],
)
def test_width_keyword_sizes_wrapping_text_in_a_column(keyword: Style, expected_width: int) -> None:
    text = _shadow(Text(content="hello world", style=text_wrap_stable | keyword))
    root = _shadow(Div(style=col | width(40)), children=[text])

    _, layout_text = [rl for _, rl in _layout(root)]

    assert layout_text.border.width == expected_width


def test_wrapping_texts_share_a_row_too_narrow_for_either_unwrapped() -> None:
    first = _shadow(Text(content="hello world", style=text_wrap_stable))
    second = _shadow(Text(content="lorem ipsum", style=text_wrap_stable))
    root = _shadow(Div(style=row | width(12)), children=[first, second])

    _, layout_first, layout_second = [rl for _, rl in _layout(root)]

    assert (layout_first.border.width, layout_first.border.height) == (6, 2)
    assert (layout_second.border.left, layout_second.border.right) == (6, 12)


@pytest.mark.parametrize(
    ("parent", "child"),
    [(col | width(40), full_width | margin_x(3) | height(1)), (row | height(10), full_height | margin_y(3) | width(1))],
)
def test_full_size_fits_inside_its_parent_after_margins(parent: Style, child: Style) -> None:
    root = _shadow(Div(style=parent), children=[_shadow(Div(style=child))])

    layout_root, layout_child = [rl for _, rl in _layout(root)]

    assert layout_child.margin == layout_root.content


WIDE = "x" * 50


def _boxes_with_wide_content(*styles: Style) -> list[ShadowNode]:
    return [_shadow(Div(style=style), children=[_shadow(Text(content=WIDE))]) for style in styles]


def _border_widths(root: ShadowNode) -> list[int]:
    return [layout.border.width for _, layout in _layout(root)[1::2]]


def test_constraints_split_a_row_whatever_the_content() -> None:
    root = _shadow(Div(style=row | width(40)), children=_boxes_with_wide_content(length(10), fill(1), fill(2)))

    assert _border_widths(root) == [10, 10, 20]


def test_constraints_split_a_column_whatever_the_content() -> None:
    tall = "x\n" * 50
    children = [_shadow(Div(style=s), children=[_shadow(Text(content=tall))]) for s in (length(2), fill(1), fill(2))]
    root = _shadow(Div(style=col | height(10)), children=children)

    assert [layout.border.height for _, layout in _layout(root)[1::2]] == [2, 3, 5]


def test_min_width_holds_whichever_side_of_fill_it_is_merged_on() -> None:
    before = _shadow(Div(style=row | width(40)), children=_boxes_with_wide_content(min_width(15) | fill(1), fill(3)))
    after = _shadow(Div(style=row | width(40)), children=_boxes_with_wide_content(fill(1) | min_width(15), fill(3)))

    assert _border_widths(before) == _border_widths(after) == [15, 25]


def test_percentage_and_ratio_give_the_same_width() -> None:
    by_percentage = _shadow(Div(style=row | width(40)), children=_boxes_with_wide_content(percentage(25), fill(1)))
    by_ratio = _shadow(Div(style=row | width(40)), children=_boxes_with_wide_content(ratio(1, 4), fill(1)))

    assert _border_widths(by_percentage) == _border_widths(by_ratio) == [10, 30]


def test_fr_tracks_split_a_grid_like_constraints_split_a_row() -> None:
    root = _shadow(
        Div(style=display_grid | width(40) | grid_template_columns(10, fr(1), fr(2))),
        children=_boxes_with_wide_content(Style(), Style(), Style()),
    )

    assert [layout.border.width for _, layout in _layout(root)[1::2]] == [10, 10, 20]


def test_int_track_gives_the_same_widths_as_length() -> None:
    def widths(template: Style) -> list[int]:
        root = _shadow(
            Div(style=display_grid | width(40) | template), children=_boxes_with_wide_content(Style(), Style())
        )
        return [layout.border.width for _, layout in _layout(root)[1::2]]

    assert widths(grid_template_columns(7, fr(1))) == widths(grid_template_columns(waxy.Length(7), fr(1))) == [7, 33]


def test_int_grid_line_and_span_place_a_child_like_their_waxy_values() -> None:
    def placed(placement: Style) -> ResolvedLayout:
        child = _shadow(Div(style=placement))
        root = _shadow(Div(style=display_grid | size(40, 12) | grid_template_rows(3, 3, 3, 3)), children=[child])
        return _layout(root)[1][1]

    assert placed(grid_row(2, span(3))) == placed(grid_row(waxy.GridLine(2), waxy.GridSpan(3)))
    assert placed(grid_row(2, span(3))).border.height == 9
