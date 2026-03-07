import waxy

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


def test_border_all() -> None:
    assert border_all.layout.border_top == waxy.Length(1)
    assert border_all.layout.border_bottom == waxy.Length(1)
    assert border_all.layout.border_left == waxy.Length(1)
    assert border_all.layout.border_right == waxy.Length(1)
    assert border_all.border_kind is None


def test_border_none_overrides_kind() -> None:
    assert (border_light | border_none).border_kind is None


def test_border_sides() -> None:
    result = border_sides(frozenset({"top", "left"}))
    assert result.layout.border_top == waxy.Length(1)
    assert result.layout.border_bottom == waxy.Length(0)
    assert result.layout.border_left == waxy.Length(1)
    assert result.layout.border_right == waxy.Length(0)


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


def test_full_width() -> None:
    assert full_width.layout.size_width == waxy.Percent(1.0)


def test_full_height() -> None:
    assert full_height.layout.size_height == waxy.Percent(1.0)


def test_full() -> None:
    assert full.layout.size_width == waxy.Percent(1.0)
    assert full.layout.size_height == waxy.Percent(1.0)
