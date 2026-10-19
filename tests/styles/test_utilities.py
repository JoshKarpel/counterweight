from collections.abc import Callable
from typing import TYPE_CHECKING

import pytest
import waxy

from counterweight.gradients import Gradient
from counterweight.gradients import linear_gradient
from counterweight.styles import TERMINAL_DEFAULT
from counterweight.styles import AnyColor
from counterweight.styles import BorderKind
from counterweight.styles import CellStyle
from counterweight.styles import Color
from counterweight.styles import IndexedColor
from counterweight.styles import Style
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


AUTO = waxy.Auto()


@pytest.mark.parametrize(
    ("utility", "expected"),
    [
        (inset(2), {f"inset_{side}": waxy.Length(2) for side in ("top", "right", "bottom", "left")}),
        (inset_x(3), {"inset_left": waxy.Length(3), "inset_right": waxy.Length(3)}),
        (inset_y(4), {"inset_top": waxy.Length(4), "inset_bottom": waxy.Length(4)}),
        (
            inset_sides(1, 2, 3, -4),
            {
                "inset_top": waxy.Length(1),
                "inset_right": waxy.Length(2),
                "inset_bottom": waxy.Length(3),
                "inset_left": waxy.Length(-4),
            },
        ),
        (
            margin_sides(5, 6, -7, 8),
            {
                "margin_top": waxy.Length(5),
                "margin_right": waxy.Length(6),
                "margin_bottom": waxy.Length(-7),
                "margin_left": waxy.Length(8),
            },
        ),
        (
            pad_sides(9, 10, 11, 12),
            {
                "padding_top": waxy.Length(9),
                "padding_right": waxy.Length(10),
                "padding_bottom": waxy.Length(11),
                "padding_left": waxy.Length(12),
            },
        ),
        (margin_auto, {f"margin_{side}": AUTO for side in ("top", "right", "bottom", "left")}),
        (margin_x_auto, {"margin_left": AUTO, "margin_right": AUTO}),
        (margin_y_auto, {"margin_top": AUTO, "margin_bottom": AUTO}),
        (margin_top_auto, {"margin_top": AUTO}),
        (margin_bottom_auto, {"margin_bottom": AUTO}),
        (margin_left_auto, {"margin_left": AUTO}),
        (margin_right_auto, {"margin_right": AUTO}),
    ],
)
def test_side_utility_sets_only_its_own_sides(utility: Style, expected: dict[str, object]) -> None:
    assert utility.layout.fields_set == expected.keys()
    assert {field: getattr(utility.layout, field) for field in expected} == expected


@pytest.mark.parametrize(
    ("utility", "expected"),
    [
        (text_indexed, lambda c: Style(text_style=CellStyle(foreground=c))),
        (text_bg_indexed, lambda c: Style(text_style=CellStyle(background=c))),
        (border_indexed, lambda c: Style(border_style=CellStyle(foreground=c))),
        (border_bg_indexed, lambda c: Style(border_style=CellStyle(background=c))),
        (margin_indexed, lambda c: Style(margin_color=c)),
        (padding_indexed, lambda c: Style(padding_color=c)),
        (content_indexed, lambda c: Style(content_color=c)),
    ],
)
def test_indexed_utilities_set_their_place_to_the_palette_entry(
    utility: Callable[[int], Style], expected: Callable[[IndexedColor], Style]
) -> None:
    assert utility(9) == expected(IndexedColor(9))


GRADIENT = linear_gradient(Color(10, 20, 30), Color(200, 100, 0), angle=30)


@pytest.mark.parametrize(
    ("utility", "expected"),
    [
        (text_gradient, Style(text_style=CellStyle(foreground=GRADIENT))),
        (text_bg_gradient, Style(text_style=CellStyle(background=GRADIENT))),
        (border_gradient, Style(border_style=CellStyle(foreground=GRADIENT))),
        (border_bg_gradient, Style(border_style=CellStyle(background=GRADIENT))),
        (margin_gradient, Style(margin_color=GRADIENT)),
        (padding_gradient, Style(padding_color=GRADIENT)),
        (content_gradient, Style(content_color=GRADIENT)),
    ],
)
def test_gradient_utilities_put_the_gradient_in_their_place(
    utility: Callable[[Gradient], Style], expected: Style
) -> None:
    assert utility(GRADIENT) == expected


COLOR_UTILITIES: list[tuple[Callable[..., Style], Callable[[AnyColor | Gradient], Style]]] = [
    (text_color, lambda c: Style(text_style=CellStyle(foreground=c))),
    (text_bg, lambda c: Style(text_style=CellStyle(background=c))),
    (border_color, lambda c: Style(border_style=CellStyle(foreground=c))),
    (border_bg, lambda c: Style(border_style=CellStyle(background=c))),
    (margin_color, lambda c: Style(margin_color=c)),
    (padding_color, lambda c: Style(padding_color=c)),
    (content_color, lambda c: Style(content_color=c)),
]


@pytest.mark.parametrize(("utility", "expected"), COLOR_UTILITIES)
def test_color_utilities_take_a_palette_name_and_shade(
    utility: Callable[..., Style], expected: Callable[[AnyColor | Gradient], Style]
) -> None:
    assert utility("teal", 700) == expected(teal_700)


@pytest.mark.parametrize(("utility", "expected"), COLOR_UTILITIES)
@pytest.mark.parametrize(
    "color",
    [Color(12, 34, 56), IndexedColor(11), TERMINAL_DEFAULT, GRADIENT],
    ids=["rgb", "indexed", "terminal-default", "gradient"],
)
def test_color_utilities_take_any_color(
    utility: Callable[..., Style], expected: Callable[[AnyColor | Gradient], Style], color: AnyColor | Gradient
) -> None:
    assert utility(color) == expected(color)


@pytest.mark.parametrize(
    ("utility", "expected"),
    [
        (text_bold, Style(text_style=CellStyle(bold=True))),
        (text_not_bold, Style(text_style=CellStyle(bold=False))),
        (text_dim, Style(text_style=CellStyle(dim=True))),
        (text_not_dim, Style(text_style=CellStyle(dim=False))),
        (text_italic, Style(text_style=CellStyle(italic=True))),
        (text_not_italic, Style(text_style=CellStyle(italic=False))),
        (text_underline, Style(text_style=CellStyle(underline=True))),
        (text_not_underline, Style(text_style=CellStyle(underline=False))),
        (text_strikethrough, Style(text_style=CellStyle(strikethrough=True))),
        (text_not_strikethrough, Style(text_style=CellStyle(strikethrough=False))),
        (border_bold, Style(border_style=CellStyle(bold=True))),
        (border_not_bold, Style(border_style=CellStyle(bold=False))),
        (border_dim, Style(border_style=CellStyle(dim=True))),
        (border_not_dim, Style(border_style=CellStyle(dim=False))),
        (border_italic, Style(border_style=CellStyle(italic=True))),
        (border_not_italic, Style(border_style=CellStyle(italic=False))),
        (border_underline, Style(border_style=CellStyle(underline=True))),
        (border_not_underline, Style(border_style=CellStyle(underline=False))),
        (border_strikethrough, Style(border_style=CellStyle(strikethrough=True))),
        (border_not_strikethrough, Style(border_style=CellStyle(strikethrough=False))),
    ],
)
def test_attribute_utilities_set_their_attribute_in_their_place(utility: Style, expected: Style) -> None:
    assert utility == expected


@pytest.mark.parametrize(
    ("on", "off", "place", "attribute"),
    [
        (text_bold, text_not_bold, "text_style", "bold"),
        (text_dim, text_not_dim, "text_style", "dim"),
        (text_italic, text_not_italic, "text_style", "italic"),
        (text_underline, text_not_underline, "text_style", "underline"),
        (text_strikethrough, text_not_strikethrough, "text_style", "strikethrough"),
        (border_bold, border_not_bold, "border_style", "bold"),
        (border_dim, border_not_dim, "border_style", "dim"),
        (border_italic, border_not_italic, "border_style", "italic"),
        (border_underline, border_not_underline, "border_style", "underline"),
        (border_strikethrough, border_not_strikethrough, "border_style", "strikethrough"),
    ],
)
def test_not_attribute_turns_off_the_attribute_merged_under_it(
    on: Style, off: Style, place: str, attribute: str
) -> None:
    assert getattr(getattr((on | off).resolved, place), attribute) is False


if TYPE_CHECKING:

    def color_utilities_take_a_name_and_shade_or_one_color(color: Color) -> None:
        text_color("teal", 700)
        text_color(color)
        text_color("teal")  # type: ignore[call-overload]
        text_color(color, 700)  # type: ignore[call-overload]


@pytest.mark.parametrize("uri", ["https://example.com/a", None])
def test_text_link_sets_the_text_link(uri: str | None) -> None:
    assert text_link(uri) == Style(text_style=CellStyle(link=uri))


def star_import_names() -> set[str]:
    namespace: dict[str, object] = {}
    exec("from counterweight.styles.utilities import *", namespace)
    return set(namespace) - {"__builtins__"}


@pytest.mark.parametrize("name", ["text_color", "pad_sides", "text_bold", "rose_200", "ColorName", "Shade", "Side"])
def test_star_import_brings_in_the_utilities_and_their_types(name: str) -> None:
    assert name in star_import_names()


@pytest.mark.parametrize("name", ["cast", "overload", "lru_cache", "Literal", "waxy", "Style", "AnyColor", "Gradient"])
def test_star_import_leaves_out_what_the_module_imports(name: str) -> None:
    assert name not in star_import_names()
