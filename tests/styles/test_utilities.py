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
