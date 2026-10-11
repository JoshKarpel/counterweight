import pytest
import waxy

from counterweight.styles import BorderKind, Style
from counterweight.styles.utilities import *


def test_position_relative() -> None:
    assert position_relative.layout.position == waxy.Position.Relative


def test_position_absolute() -> None:
    assert position_absolute.layout.position == waxy.Position.Absolute


def test_inset_top() -> None:
    result = inset_top(5)
    assert result.layout.inset_top == waxy.Length(5)


def test_inset_bottom() -> None:
    result = inset_bottom(3)
    assert result.layout.inset_bottom == waxy.Length(3)


def test_inset_left() -> None:
    result = inset_left(3)
    assert result.layout.inset_left == waxy.Length(3)


def test_inset_right() -> None:
    result = inset_right(7)
    assert result.layout.inset_right == waxy.Length(7)


def test_inset_top_left() -> None:
    assert inset_top_left.layout.position == waxy.Position.Absolute
    assert inset_top_left.layout.inset_top == waxy.Length(0)
    assert inset_top_left.layout.inset_left == waxy.Length(0)


def test_inset_top_center() -> None:
    assert inset_top_center.layout.position == waxy.Position.Absolute
    assert inset_top_center.layout.inset_top == waxy.Length(0)
    assert inset_top_center.layout.inset_left == waxy.Auto()
    assert inset_top_center.layout.inset_right == waxy.Auto()


def test_inset_top_right() -> None:
    assert inset_top_right.layout.position == waxy.Position.Absolute
    assert inset_top_right.layout.inset_top == waxy.Length(0)
    assert inset_top_right.layout.inset_right == waxy.Length(0)


def test_inset_center_left() -> None:
    assert inset_center_left.layout.position == waxy.Position.Absolute
    assert inset_center_left.layout.inset_top == waxy.Auto()
    assert inset_center_left.layout.inset_bottom == waxy.Auto()
    assert inset_center_left.layout.inset_left == waxy.Length(0)


def test_inset_center_center() -> None:
    assert inset_center_center.layout.position == waxy.Position.Absolute
    assert inset_center_center.layout.inset_top == waxy.Auto()
    assert inset_center_center.layout.inset_bottom == waxy.Auto()
    assert inset_center_center.layout.inset_left == waxy.Auto()
    assert inset_center_center.layout.inset_right == waxy.Auto()


def test_inset_center_right() -> None:
    assert inset_center_right.layout.position == waxy.Position.Absolute
    assert inset_center_right.layout.inset_top == waxy.Auto()
    assert inset_center_right.layout.inset_bottom == waxy.Auto()
    assert inset_center_right.layout.inset_right == waxy.Length(0)


def test_inset_bottom_left() -> None:
    assert inset_bottom_left.layout.position == waxy.Position.Absolute
    assert inset_bottom_left.layout.inset_bottom == waxy.Length(0)
    assert inset_bottom_left.layout.inset_left == waxy.Length(0)


def test_inset_bottom_center() -> None:
    assert inset_bottom_center.layout.position == waxy.Position.Absolute
    assert inset_bottom_center.layout.inset_bottom == waxy.Length(0)
    assert inset_bottom_center.layout.inset_left == waxy.Auto()
    assert inset_bottom_center.layout.inset_right == waxy.Auto()


def test_inset_bottom_right() -> None:
    assert inset_bottom_right.layout.position == waxy.Position.Absolute
    assert inset_bottom_right.layout.inset_bottom == waxy.Length(0)
    assert inset_bottom_right.layout.inset_right == waxy.Length(0)


def test_border_kind_sets_only_border_kind() -> None:
    assert border_heavy == Style(border_kind=BorderKind.Heavy)


def test_border_sets_every_side() -> None:
    assert border == Style(
        layout=waxy.Style(
            border_top=waxy.Length(1),
            border_bottom=waxy.Length(1),
            border_left=waxy.Length(1),
            border_right=waxy.Length(1),
        )
    )


def test_border_side_sets_only_its_side() -> None:
    assert border_left == Style(layout=waxy.Style(border_left=waxy.Length(1)))


def test_border_side_zero_sets_only_its_side() -> None:
    assert border_left_0 == Style(layout=waxy.Style(border_left=waxy.Length(0)))


def test_border_axis_sets_its_pair_of_sides() -> None:
    assert border_y == Style(layout=waxy.Style(border_top=waxy.Length(1), border_bottom=waxy.Length(1)))


def test_border_sides() -> None:
    assert border_sides(frozenset({"top", "left"})) == Style(
        layout=waxy.Style(
            border_top=waxy.Length(1),
            border_bottom=waxy.Length(0),
            border_left=waxy.Length(1),
            border_right=waxy.Length(0),
        )
    )


def test_margin_top() -> None:
    result = margin_top(-4)
    assert result.layout.margin_top == waxy.Length(-4)


def test_margin_bottom() -> None:
    result = margin_bottom(4)
    assert result.layout.margin_bottom == waxy.Length(4)


def test_margin_left() -> None:
    result = margin_left(-2)
    assert result.layout.margin_left == waxy.Length(-2)


def test_margin_right() -> None:
    result = margin_right(1)
    assert result.layout.margin_right == waxy.Length(1)


def test_pad() -> None:
    result = pad(2)
    assert result.layout.padding_top == waxy.Length(2)
    assert result.layout.padding_bottom == waxy.Length(2)
    assert result.layout.padding_left == waxy.Length(2)
    assert result.layout.padding_right == waxy.Length(2)


def test_pad_x() -> None:
    result = pad_x(3)
    assert result.layout.padding_left == waxy.Length(3)
    assert result.layout.padding_right == waxy.Length(3)


def test_pad_y() -> None:
    result = pad_y(1)
    assert result.layout.padding_top == waxy.Length(1)
    assert result.layout.padding_bottom == waxy.Length(1)


def test_pad_top() -> None:
    result = pad_top(4)
    assert result.layout.padding_top == waxy.Length(4)


def test_pad_bottom() -> None:
    result = pad_bottom(2)
    assert result.layout.padding_bottom == waxy.Length(2)


def test_pad_left() -> None:
    result = pad_left(3)
    assert result.layout.padding_left == waxy.Length(3)


def test_pad_right() -> None:
    result = pad_right(1)
    assert result.layout.padding_right == waxy.Length(1)


@pytest.mark.parametrize(
    ("utility", "expected"),
    [
        (min_content_width, {"size_width": waxy.MIN_CONTENT}),
        (max_content_width, {"size_width": waxy.MAX_CONTENT}),
        (fit_content_width, {"size_width": waxy.FIT_CONTENT}),
        (stretch_width, {"size_width": waxy.STRETCH}),
        (min_content_height, {"size_height": waxy.MIN_CONTENT}),
        (max_content_height, {"size_height": waxy.MAX_CONTENT}),
        (fit_content_height, {"size_height": waxy.FIT_CONTENT}),
        (stretch_height, {"size_height": waxy.STRETCH}),
        (full_width, {"size_width": waxy.STRETCH}),
        (full_height, {"size_height": waxy.STRETCH}),
        (full, {"size_width": waxy.STRETCH, "size_height": waxy.STRETCH}),
    ],
)
def test_sizing_keyword_utility_sets_only_its_own_fields(utility: Style, expected: dict[str, object]) -> None:
    assert utility.layout.fields_set == expected.keys()
    assert {field: getattr(utility.layout, field) for field in expected} == expected


HIDDEN = waxy.Overflow.Hidden


@pytest.mark.parametrize(
    ("utility", "expected"),
    [
        (grow(3), {"flex_grow": 3.0}),
        (shrink(3), {"flex_shrink": 3.0}),
        (
            length(7),
            {
                "flex_basis": waxy.Length(7),
                "flex_grow": 0.0,
                "flex_shrink": 0.0,
                "overflow_x": HIDDEN,
                "overflow_y": HIDDEN,
            },
        ),
        (
            percentage(30),
            {
                "flex_basis": waxy.Percent(0.3),
                "flex_grow": 0.0,
                "flex_shrink": 0.0,
                "overflow_x": HIDDEN,
                "overflow_y": HIDDEN,
            },
        ),
        (
            ratio(2, 5),
            {
                "flex_basis": waxy.Percent(0.4),
                "flex_grow": 0.0,
                "flex_shrink": 0.0,
                "overflow_x": HIDDEN,
                "overflow_y": HIDDEN,
            },
        ),
        (
            fill(3),
            {
                "flex_basis": waxy.Length(0),
                "flex_grow": 3.0,
                "flex_shrink": 1.0,
                "overflow_x": HIDDEN,
                "overflow_y": HIDDEN,
            },
        ),
        (
            center_children,
            {"align_items": waxy.AlignItems.SafeCenter, "justify_content": waxy.AlignContent.SafeCenter},
        ),
    ],
)
def test_constraint_utility_sets_only_its_own_fields(utility: Style, expected: dict[str, object]) -> None:
    assert utility.layout.fields_set == expected.keys()
    assert {field: getattr(utility.layout, field) for field in expected} == expected


def test_fill_defaults_to_one_share() -> None:
    assert fill() == fill(1)


def test_overriding_one_field_of_a_constraint_keeps_the_rest() -> None:
    assert (fill(2) | shrink(0)).layout == waxy.Style(
        flex_basis=waxy.Length(0),
        flex_grow=2.0,
        flex_shrink=0.0,
        overflow_x=HIDDEN,
        overflow_y=HIDDEN,
    )


def test_fr_is_a_track_with_no_content_minimum() -> None:
    assert fr(3) == waxy.Minmax(waxy.Length(0), waxy.Fraction(3))


def test_span_is_a_grid_span() -> None:
    assert span(3) == waxy.GridSpan(3)


def test_int_track_stands_for_length() -> None:
    assert grid_template_columns(7, fr(2)) == grid_template_columns(waxy.Length(7), fr(2))


def test_int_grid_line_stands_for_grid_line() -> None:
    assert grid_row(2, span(3)) == grid_row(waxy.GridLine(2), waxy.GridSpan(3))
