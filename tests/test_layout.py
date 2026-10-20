from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal
from typing import assert_never
from typing import get_args

import pytest
import waxy
from hypothesis import example
from hypothesis import given
from hypothesis import strategies as st
from more_itertools import one

from counterweight.app import screen_element_style
from counterweight.elements import AnyElement
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.geometry import Rects
from counterweight.hooks.impls import Hooks
from counterweight.layout import NO_LAYOUTS
from counterweight.layout import Layouts
from counterweight.layout import LayoutTree
from counterweight.layout import Lines
from counterweight.layout import MeasurableText
from counterweight.layout import cells_width
from counterweight.layout import layout_changes
from counterweight.shadow import ShadowNode
from counterweight.shadow import ShadowTree
from counterweight.shadow import update_shadow
from counterweight.styles.styles import CellStyle
from counterweight.styles.styles import Style
from counterweight.styles.styles import TextWrap
from counterweight.styles.utilities import align_children_center
from counterweight.styles.utilities import align_children_center_unsafe
from counterweight.styles.utilities import align_children_end
from counterweight.styles.utilities import align_children_end_unsafe
from counterweight.styles.utilities import align_children_start
from counterweight.styles.utilities import aspect_ratio
from counterweight.styles.utilities import border
from counterweight.styles.utilities import border_collapse
from counterweight.styles.utilities import border_lightrounded
from counterweight.styles.utilities import col
from counterweight.styles.utilities import display_grid
from counterweight.styles.utilities import display_none
from counterweight.styles.utilities import fill
from counterweight.styles.utilities import fit_content_width
from counterweight.styles.utilities import fr
from counterweight.styles.utilities import full_height
from counterweight.styles.utilities import full_width
from counterweight.styles.utilities import gap
from counterweight.styles.utilities import gap_height
from counterweight.styles.utilities import grid_column
from counterweight.styles.utilities import grid_row
from counterweight.styles.utilities import grid_template_columns
from counterweight.styles.utilities import grid_template_rows
from counterweight.styles.utilities import grow
from counterweight.styles.utilities import height
from counterweight.styles.utilities import inset_bottom
from counterweight.styles.utilities import inset_bottom_center
from counterweight.styles.utilities import inset_left
from counterweight.styles.utilities import inset_top
from counterweight.styles.utilities import justify_children_center
from counterweight.styles.utilities import justify_children_center_unsafe
from counterweight.styles.utilities import justify_children_end
from counterweight.styles.utilities import justify_children_end_unsafe
from counterweight.styles.utilities import justify_children_space_around
from counterweight.styles.utilities import justify_children_space_evenly
from counterweight.styles.utilities import length
from counterweight.styles.utilities import margin_x
from counterweight.styles.utilities import margin_y
from counterweight.styles.utilities import max_content_width
from counterweight.styles.utilities import max_height
from counterweight.styles.utilities import max_width
from counterweight.styles.utilities import min_content_width
from counterweight.styles.utilities import min_height
from counterweight.styles.utilities import min_width
from counterweight.styles.utilities import pad
from counterweight.styles.utilities import pad_x
from counterweight.styles.utilities import percentage
from counterweight.styles.utilities import position_absolute
from counterweight.styles.utilities import ratio
from counterweight.styles.utilities import row
from counterweight.styles.utilities import shrink
from counterweight.styles.utilities import size
from counterweight.styles.utilities import span
from counterweight.styles.utilities import stretch_width
from counterweight.styles.utilities import text_wrap_balance
from counterweight.styles.utilities import text_wrap_pretty
from counterweight.styles.utilities import text_wrap_stable
from counterweight.styles.utilities import width
from counterweight.styles.utilities import z


def _shadow(element: AnyElement, children: Sequence[ShadowNode] = ()) -> ShadowNode:
    return ShadowNode(component=None, element=element, hooks=Hooks(), children=tuple(children))


def _layouts(root: ShadowNode, w: int = 60, h: int = 20) -> Layouts:
    shadow = ShadowTree(root=root)
    return LayoutTree().compute(layout_changes(None, shadow), shadow, w, h, {})


def _layout(root: ShadowNode, w: int = 60, h: int = 20) -> tuple[tuple[AnyElement, Rects], ...]:
    return tuple((element, layout) for _, element, layout, _, _ in _layouts(root, w, h).in_paint_order)


def _layout_screened(root: ShadowNode, w: int = 60, h: int = 20) -> tuple[tuple[AnyElement, Rects], ...]:
    """Wrap root in the element the app places the root component in."""
    screen = _shadow(Div(style=screen_element_style(w, h)), children=[root])
    return _layout(screen, w, h)


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


def test_text_with_border_and_padding_wraps_at_its_content_width() -> None:
    # Width 9 less the border and padding leaves 5 cells: "aaa bbb ccc" wraps to 3 lines, plus 2 for the border.
    # Wrapped at the border box's 9 cells instead, it would measure 2 lines.
    text_node = _shadow(Text(content="aaa bbb ccc", style=text_wrap_stable | border | pad_x(1)))
    container = _shadow(
        Div(style=col | Style(layout=waxy.Style(size_width=waxy.Length(9)))),
        children=[text_node],
    )

    results = _layout(container, w=20, h=20)
    text_layout = next(rl for el, rl in results if isinstance(el, Text))

    assert text_layout.border.height == 5


Sides = tuple[int, int, int, int]


def boxed(
    borders: Sides, paddings: Sides, box_sizing: waxy.BoxSizing, size_width: waxy.Length | waxy.Percent | waxy.Auto
) -> waxy.Style:
    """A layout with the given border and padding on its left, right, top and bottom sides."""
    return waxy.Style(
        box_sizing=box_sizing,
        size_width=size_width,
        border_left=waxy.Length(borders[0]),
        border_right=waxy.Length(borders[1]),
        border_top=waxy.Length(borders[2]),
        border_bottom=waxy.Length(borders[3]),
        padding_left=waxy.Length(paddings[0]),
        padding_right=waxy.Length(paddings[1]),
        padding_top=waxy.Length(paddings[2]),
        padding_bottom=waxy.Length(paddings[3]),
    )


borders = st.tuples(*[st.integers(0, 1)] * 4)
paddings = st.tuples(*[st.integers(0, 2)] * 4)
box_sizings = st.sampled_from([waxy.BoxSizing.BorderBox, waxy.BoxSizing.ContentBox])

TextSizing = Literal[
    "stretched in a column",
    "fit to its content in a column",
    "own width",
    "percentage of its parent",
    "shrunk in a row",
    "squeezed by a sibling in a row",
]
WRAPPING: tuple[TextWrap, ...] = ("stable", "pretty", "balance")


@dataclass(frozen=True, slots=True)
class TextInBox:
    """A text with a border and padding, sized by `width` in the way `sizing` names, for properties of its layout."""

    content: str
    wrap: TextWrap
    borders: Sides
    paddings: Sides
    box_sizing: waxy.BoxSizing
    sizing: TextSizing
    width: int

    def element(self) -> Div:
        """The text in its parent, beside a sibling as wide as the parent if it's squeezed."""
        width = waxy.Length(self.width)
        match self.sizing:
            case "stretched in a column":
                return self.parent(col, width, waxy.Auto())
            case "fit to its content in a column":
                return self.parent(col | align_children_start, width, waxy.Auto())
            case "own width":
                return self.parent(col, waxy.Length(40), width)
            case "percentage of its parent":
                return self.parent(col, waxy.Length(40), waxy.Percent(self.width / 40))
            case "shrunk in a row":
                return self.parent(row, width, waxy.Auto())
            case "squeezed by a sibling in a row":
                sibling = Div(style=Style(layout=waxy.Style(size_width=width, flex_shrink=0.0)))
                return self.parent(row, width, waxy.Auto(), sibling)
            case _ as unreachable:
                assert_never(unreachable)

    def parent(
        self,
        style: Style,
        width: waxy.Length,
        text_width: waxy.Length | waxy.Percent | waxy.Auto,
        *siblings: AnyElement,
    ) -> Div:
        """The text, `text_width` wide with its border and padding, first in a `width`-wide parent styled `style`."""
        layout = boxed(self.borders, self.paddings, self.box_sizing, text_width)
        text = Text(content=self.content, style=Style(text_wrap=self.wrap, layout=layout))
        return Div(style=style | Style(layout=waxy.Style(size_width=width)), children=(text, *siblings))

    def laid_out(self) -> tuple[Rects, Lines]:
        """The text's layout and the rows it paints."""
        shadow = update_shadow(self.element(), None, NO_LAYOUTS).tree
        layouts = LayoutTree().compute(layout_changes(None, shadow), shadow, 60, 200, {})
        return one((rects, rows) for _, element, rects, rows, _ in layouts.in_paint_order if isinstance(element, Text))


def texts_in_boxes(
    wraps: Sequence[TextWrap] = get_args(TextWrap), sizings: Sequence[TextSizing] = get_args(TextSizing)
) -> st.SearchStrategy[TextInBox]:
    """Texts of words with wide clusters among them, wrapped one of the `wraps` ways and sized one of the `sizings`."""
    return st.builds(
        TextInBox,
        content=st.lists(st.text(alphabet="abあ", min_size=1, max_size=6), min_size=1, max_size=12).map(" ".join),
        wrap=st.sampled_from(wraps),
        borders=borders,
        paddings=paddings,
        box_sizing=box_sizings,
        sizing=st.sampled_from(sizings),
        width=st.integers(1, 30),
    )


@given(texts_in_boxes())
@example(TextInBox("a", "stable", (0, 0, 0, 0), (0, 1, 0, 0), waxy.BoxSizing.BorderBox, "stretched in a column", 1))
@example(TextInBox("a", "none", (0, 0, 0, 0), (0, 1, 0, 0), waxy.BoxSizing.BorderBox, "stretched in a column", 1))
@example(
    TextInBox(
        "あaa", "stable", (0, 0, 0, 0), (0, 0, 0, 0), waxy.BoxSizing.BorderBox, "fit to its content in a column", 1
    )
)
def test_text_content_box_is_as_tall_as_the_rows_it_paints(text: TextInBox) -> None:
    rects, rows = text.laid_out()

    assert len(rows) == rects.content.height


@given(texts_in_boxes(wraps=WRAPPING))
def test_wrapping_text_rows_fit_in_its_content_box_unless_one_cluster_is_wider(text: TextInBox) -> None:
    rects, rows = text.laid_out()

    assert all(cells_width(line) <= rects.content.width or len(line) == 1 for line in rows)


@given(texts_in_boxes(wraps=WRAPPING, sizings=["squeezed by a sibling in a row"]))
def test_wrapping_text_squeezed_by_a_sibling_is_as_wide_as_its_widest_word(text: TextInBox) -> None:
    rects, _ = text.laid_out()

    assert rects.content.width == MeasurableText.of((text.content, CellStyle(), text.wrap)).narrowest_width()


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


def test_hidden_subtree_has_no_layout_by_key() -> None:
    visible = _shadow(Text(content="visible"))
    hidden_child = _shadow(Text(content="hidden child"))
    hidden = _shadow(Div(style=display_none), children=[hidden_child])
    root = _shadow(Div(style=col), children=[visible, hidden])

    assert _layouts(root).by_key.keys() == {root.key, visible.key}


def _painted(root: ShadowNode, /, **named: ShadowNode) -> list[str]:
    """The names of `named`'s nodes in the order `root`'s layouts paint them, skipping unnamed ones."""
    names = {id(node.element): name for name, node in named.items()}
    return [names[id(element)] for element, _ in _layout(root) if id(element) in names]


def test_elements_without_z_paint_in_tree_order() -> None:
    first_child = _shadow(Text(content="first child"))
    first = _shadow(Div(), children=[first_child])
    second = _shadow(Text(content="second"))
    root = _shadow(Div(), children=[first, second])

    assert _painted(root, root=root, first=first, first_child=first_child, second=second) == [
        "root",
        "first",
        "first_child",
        "second",
    ]


def test_children_of_an_element_with_z_paint_over_it() -> None:
    child = _shadow(Text(content="child"))
    parent = _shadow(Div(style=z(1)), children=[child])
    root = _shadow(Div(), children=[parent])

    assert _painted(root, parent=parent, child=child) == ["parent", "child"]


def test_child_that_sets_a_lower_z_than_its_parent_still_paints_over_it() -> None:
    child = _shadow(Text(content="child", style=z(-2)))
    parent = _shadow(Div(style=z(3)), children=[child])
    root = _shadow(Div(), children=[parent])

    assert _painted(root, parent=parent, child=child) == ["parent", "child"]


def test_raised_child_of_an_element_without_z_paints_over_that_elements_later_siblings() -> None:
    dropdown = _shadow(Text(content="dropdown", style=z(1)))
    toolbar = _shadow(Div(), children=[dropdown])
    content = _shadow(Text(content="content"))
    root = _shadow(Div(), children=[toolbar, content])

    assert _painted(root, toolbar=toolbar, dropdown=dropdown, content=content) == ["toolbar", "content", "dropdown"]


def test_raised_child_of_an_element_with_z_0_paints_beneath_that_elements_later_siblings() -> None:
    dropdown = _shadow(Text(content="dropdown", style=z(1)))
    toolbar = _shadow(Div(style=z(0)), children=[dropdown])
    content = _shadow(Text(content="content"))
    root = _shadow(Div(), children=[toolbar, content])

    assert _painted(root, toolbar=toolbar, dropdown=dropdown, content=content) == ["toolbar", "dropdown", "content"]


def test_lowered_member_paints_over_its_contexts_element_and_beneath_its_other_members() -> None:
    first = _shadow(Text(content="first"))
    lowered = _shadow(Text(content="lowered", style=z(-1)))
    context = _shadow(Div(style=z(1)), children=[first, lowered])
    root = _shadow(Div(), children=[context])

    assert _painted(root, context=context, first=first, lowered=lowered) == ["context", "lowered", "first"]


def test_root_forms_a_stacking_context_whatever_it_sets() -> None:
    lowered = _shadow(Text(content="lowered", style=z(-1)))
    root = _shadow(Div(), children=[lowered])

    assert _painted(root, root=root, lowered=lowered) == ["root", "lowered"]


def test_members_of_one_context_sort_by_z_then_tree_order_at_any_depth() -> None:
    deep_raised = _shadow(Text(content="deep raised", style=z(2)))
    deep = _shadow(Text(content="deep"))
    wrapper = _shadow(Div(), children=[deep_raised, deep])
    raised = _shadow(Text(content="raised", style=z(2)))
    lowered = _shadow(Text(content="lowered", style=z(-1)))
    root = _shadow(Div(), children=[wrapper, raised, lowered])

    assert _painted(root, wrapper=wrapper, deep_raised=deep_raised, deep=deep, raised=raised, lowered=lowered) == [
        "lowered",
        "wrapper",
        "deep",
        "deep_raised",
        "raised",
    ]


def test_hidden_subtree_is_left_out_of_its_stacking_context() -> None:
    hidden_child = _shadow(Text(content="hidden child", style=z(1)))
    hidden = _shadow(Div(style=display_none), children=[hidden_child])
    visible = _shadow(Text(content="visible", style=z(1)))
    root = _shadow(Div(), children=[hidden, visible])

    assert _painted(root, root=root, hidden=hidden, hidden_child=hidden_child, visible=visible) == ["root", "visible"]


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


def test_lengths_keep_their_size_when_they_overflow_the_row() -> None:
    root = _shadow(Div(style=row | width(40)), children=_boxes_with_wide_content(length(30), length(25)))

    assert _border_widths(root) == [30, 25]


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
    def placed(placement: Style) -> Rects:
        child = _shadow(Div(style=placement))
        root = _shadow(Div(style=display_grid | size(40, 12) | grid_template_rows(3, 3, 3, 3)), children=[child])
        return _layout(root)[1][1]

    assert placed(grid_row(2, span(3))) == placed(grid_row(waxy.GridLine(2), waxy.GridSpan(3)))
    assert placed(grid_row(2, span(3))).border.height == 9


def _border_boxes(root: ShadowNode) -> list[tuple[int, int, int, int]]:
    """The left, top, width and height of each child of `root`'s border box."""
    return [
        (layout.border.left, layout.border.top, layout.border.width, layout.border.height)
        for _, layout in _layout(root)[1:]
    ]


@pytest.mark.parametrize(
    ("parent", "child", "expected"),
    [
        pytest.param(col | height(10), min_height(4), (0, 0, 0, 4), id="min-height"),
        pytest.param(col | height(10), fill(1) | max_height(3), (0, 0, 0, 3), id="max-height"),
        pytest.param(row | width(40), fill(1) | max_width(12), (0, 0, 12, 0), id="max-width"),
        pytest.param(col | align_children_start, width(8) | aspect_ratio(2.0), (0, 0, 8, 4), id="aspect-ratio"),
        pytest.param(
            display_grid | size(40, 12) | grid_template_columns(10, 10, 10, 10),
            grid_column(2, span(2)),
            (10, 0, 20, 12),
            id="grid-column",
        ),
    ],
)
def test_size_and_placement_utilities_shape_a_child(parent: Style, child: Style, expected: tuple[int, ...]) -> None:
    assert _border_boxes(_shadow(Div(style=parent), children=[_shadow(Div(style=child))])) == [expected]


def test_gap_height_spaces_a_columns_children() -> None:
    children = [_shadow(Div(style=height(2))), _shadow(Div(style=height(2)))]

    assert _border_boxes(_shadow(Div(style=col | gap_height(3)), children=children)) == [(0, 0, 0, 2), (0, 5, 0, 2)]


def test_gap_spaces_grid_cells_both_ways() -> None:
    grid = display_grid | grid_template_columns(3, 3) | grid_template_rows(3, 3) | gap(2)

    assert _border_boxes(_shadow(Div(style=grid), children=[_shadow(Div()) for _ in range(4)])) == [
        (0, 0, 3, 3),
        (5, 0, 3, 3),
        (0, 5, 3, 3),
        (5, 5, 3, 3),
    ]
