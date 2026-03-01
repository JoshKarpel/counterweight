import waxy

from counterweight.styles.utilities import *


def test_relative() -> None:
    result = relative(x=3, y=5)
    assert result.layout.position == waxy.Position.Relative
    assert result.layout.inset_left == waxy.Length(3)
    assert result.layout.inset_top == waxy.Length(5)


def test_absolute() -> None:
    result = absolute(x=3, y=5)
    assert result.layout.position == waxy.Position.Absolute
    assert result.layout.inset_left == waxy.Length(3)
    assert result.layout.inset_top == waxy.Length(5)


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


def test_border_edges() -> None:
    result = border_edges({"top", "left"})
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
