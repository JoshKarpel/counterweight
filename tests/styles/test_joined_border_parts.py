from itertools import product

import pytest

from counterweight.styles.styles import JoinedBorderKind, JoinedBorderParts

PARTS = JoinedBorderParts(*JoinedBorderParts._fields)

SELECTED = {
    (True, True, True, True): "horizontal_vertical",
    (True, True, True, False): "vertical_left",
    (True, True, False, True): "vertical_right",
    (True, False, True, True): "horizontal_top",
    (False, True, True, True): "horizontal_bottom",
    (True, True, False, False): "vertical",
    (False, False, True, True): "horizontal",
    (True, False, True, False): "right_bottom",
    (True, False, False, True): "left_bottom",
    (False, True, True, False): "right_top",
    (False, True, False, True): "left_top",
}


@pytest.mark.parametrize(("top", "bottom", "left", "right"), list(product([True, False], repeat=4)))
def test_select_picks_the_part_connecting_exactly_the_given_sides(
    top: bool, bottom: bool, left: bool, right: bool
) -> None:
    assert PARTS.select(top=top, bottom=bottom, left=left, right=right) == SELECTED.get((top, bottom, left, right))


def test_joined_border_kind_repr_is_its_qualified_name() -> None:
    assert repr(JoinedBorderKind.Light) == "JoinedBorderKind.Light"
