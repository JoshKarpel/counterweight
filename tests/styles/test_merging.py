import pytest
import waxy

from counterweight.styles.styles import BorderKind, CellStyle, Color, Style
from counterweight.styles.utilities import border_heavy, inset_left, inset_top, position_absolute, position_relative


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    (
        (Style(), Style(), Style()),
        (
            Style(border_style=CellStyle(bold=True)),
            Style(),
            Style(border_style=CellStyle(bold=True)),
        ),
        (
            Style(),
            Style(border_style=CellStyle(bold=True)),
            Style(border_style=CellStyle(bold=True)),
        ),
        (
            Style(border_style=CellStyle(bold=False)),
            Style(border_style=CellStyle(bold=True)),
            Style(border_style=CellStyle(bold=True)),
        ),
        (
            Style(border_style=CellStyle(bold=True)),
            Style(border_style=CellStyle(bold=False)),
            Style(border_style=CellStyle(bold=True)),
        ),
        (
            Style(),
            Style(border_style=CellStyle(foreground=Color.from_name("green"))),
            Style(border_style=CellStyle(foreground=Color.from_name("green"))),
        ),
        (
            Style(border_kind=BorderKind.LightRounded),
            Style(border_style=CellStyle(foreground=Color.from_name("green"))),
            Style(border_kind=BorderKind.LightRounded, border_style=CellStyle(foreground=Color.from_name("green"))),
        ),
        (
            Style(border_style=CellStyle(foreground=Color.from_name("green"))),
            Style(border_kind=BorderKind.LightRounded),
            Style(border_kind=BorderKind.LightRounded, border_style=CellStyle(foreground=Color.from_name("green"))),
        ),
    ),
)
def test_style_merging(left: Style, right: Style, expected: Style) -> None:
    assert (left | right) == expected


def test_layout_retained_from_left() -> None:
    result = Style(layout=waxy.Style(size_width=waxy.Length(5))) | Style()
    assert result.layout.size_width == waxy.Length(5)


def test_layout_retained_from_right() -> None:
    result = Style() | Style(layout=waxy.Style(size_width=waxy.Length(5)))
    assert result.layout.size_width == waxy.Length(5)


def test_layout_right_overrides_left() -> None:
    result = Style(layout=waxy.Style(flex_direction=waxy.FlexDirection.Row)) | Style(
        layout=waxy.Style(flex_direction=waxy.FlexDirection.Column)
    )
    assert result.layout.flex_direction == waxy.FlexDirection.Column


def test_layout_left_overrides_right() -> None:
    result = Style(layout=waxy.Style(flex_direction=waxy.FlexDirection.Column)) | Style(
        layout=waxy.Style(flex_direction=waxy.FlexDirection.Row)
    )
    assert result.layout.flex_direction == waxy.FlexDirection.Row


def test_layout_merges_independent_fields() -> None:
    result = Style(layout=waxy.Style(flex_direction=waxy.FlexDirection.Row)) | Style(layout=waxy.Style(flex_grow=0.0))
    assert result.layout.flex_direction == waxy.FlexDirection.Row
    assert result.layout.flex_grow == 0.0


def test_layout_merges_left_non_default_retained() -> None:
    result = Style(layout=waxy.Style(flex_direction=waxy.FlexDirection.Column, flex_grow=5.0)) | Style(
        layout=waxy.Style(flex_direction=waxy.FlexDirection.Row)
    )
    assert result.layout.flex_direction == waxy.FlexDirection.Row
    assert result.layout.flex_grow == 5.0


def test_layout_merge_with_visual() -> None:
    """Layout fields merge independently from visual fields."""
    result = position_relative | inset_left(3) | inset_top(5) | border_heavy
    assert result.border_kind == BorderKind.Heavy
    assert result.layout.position == waxy.Position.Relative
    assert result.layout.inset_left == waxy.Length(3)
    assert result.layout.inset_top == waxy.Length(5)
    assert result.layout.border_top == waxy.Length(1)


def test_absolute_merge_with_visual() -> None:
    result = position_absolute | inset_left(3) | inset_top(5) | border_heavy
    assert result.border_kind == BorderKind.Heavy
    assert result.layout.position == waxy.Position.Absolute
    assert result.layout.inset_left == waxy.Length(3)
    assert result.layout.inset_top == waxy.Length(5)
    assert result.layout.border_top == waxy.Length(1)
