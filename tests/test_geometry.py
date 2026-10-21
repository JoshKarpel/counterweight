from __future__ import annotations

import pytest

from counterweight.geometry import Position
from counterweight.geometry import Region
from counterweight.geometry import clamp

REGION = Region(left=3, top=5, right=7, bottom=8)


def test_width_and_height_count_cells() -> None:
    assert (REGION.width, REGION.height) == (4, 3)


@pytest.mark.parametrize(
    "region",
    [
        Region(left=3, top=5, right=3, bottom=8),
        Region(left=3, top=5, right=7, bottom=5),
        Region(left=3, top=5, right=1, bottom=8),
    ],
)
def test_region_without_area_is_empty(region: Region) -> None:
    assert region.is_empty
    assert list(region.positions()) == []
    assert list(region.top_edge()) == []
    assert list(region.bottom_edge()) == []
    assert list(region.left_edge()) == []
    assert list(region.right_edge()) == []


def test_region_with_area_is_not_empty() -> None:
    assert not REGION.is_empty


def test_positions_are_row_major_and_cover_every_cell() -> None:
    assert list(REGION.positions()) == [Position(x=x, y=y) for y in (5, 6, 7) for x in (3, 4, 5, 6)]


def test_single_cell_region() -> None:
    cell = Region(left=2, top=9, right=3, bottom=10)

    assert list(cell.positions()) == [Position(x=2, y=9)]
    assert cell.top_left == cell.top_right == cell.bottom_left == cell.bottom_right == Position(x=2, y=9)


def test_corners_are_cells_inside_the_region() -> None:
    assert (REGION.top_left, REGION.top_right, REGION.bottom_left, REGION.bottom_right) == (
        Position(x=3, y=5),
        Position(x=6, y=5),
        Position(x=3, y=7),
        Position(x=6, y=7),
    )


def test_edges_are_the_outermost_rows_and_columns() -> None:
    assert list(REGION.top_edge()) == [Position(x=x, y=5) for x in (3, 4, 5, 6)]
    assert list(REGION.bottom_edge()) == [Position(x=x, y=7) for x in (3, 4, 5, 6)]
    assert list(REGION.left_edge()) == [Position(x=3, y=y) for y in (5, 6, 7)]
    assert list(REGION.right_edge()) == [Position(x=6, y=y) for y in (5, 6, 7)]


@pytest.mark.parametrize(
    ("position", "expected"),
    [
        (Position(x=3, y=5), True),
        (Position(x=6, y=7), True),
        (Position(x=4, y=6), True),
        (Position(x=2, y=6), False),
        (Position(x=7, y=6), False),
        (Position(x=4, y=4), False),
        (Position(x=4, y=8), False),
    ],
)
def test_contains_includes_left_and_top_edges_but_not_right_and_bottom(position: Position, expected: bool) -> None:
    assert REGION.contains(position) is expected


@pytest.mark.parametrize(
    ("other", "expected"),
    [
        (Region(left=5, top=6, right=10, bottom=12), Region(left=5, top=6, right=7, bottom=8)),
        (Region(left=0, top=0, right=20, bottom=20), REGION),
        (Region(left=4, top=6, right=5, bottom=7), Region(left=4, top=6, right=5, bottom=7)),
        (Region(left=7, top=5, right=9, bottom=8), None),
        (Region(left=3, top=8, right=7, bottom=11), None),
        (Region(left=10, top=10, right=12, bottom=12), None),
    ],
)
def test_intersection(other: Region, expected: Region | None) -> None:
    assert REGION.intersection(other) == expected
    assert other.intersection(REGION) == expected


@pytest.mark.parametrize(
    "other",
    [
        Region(left=3, top=4, right=8, bottom=9),
        Region(left=2, top=5, right=8, bottom=9),
        Region(left=2, top=4, right=7, bottom=9),
        Region(left=2, top=4, right=8, bottom=8),
        Region(left=3, top=5, right=7, bottom=8),
    ],
    ids=["sharing-left-edge", "sharing-top-edge", "sharing-right-edge", "sharing-bottom-edge", "equal"],
)
def test_intersection_with_a_region_containing_it_is_the_region_itself(other: Region) -> None:
    assert REGION.intersection(other) is REGION


def test_intersection_of_an_empty_region_with_a_region_containing_it_is_none() -> None:
    assert Region(left=4, top=6, right=4, bottom=7).intersection(REGION) is None


def test_adding_positions_adds_each_coordinate() -> None:
    assert Position(x=3, y=5) + Position(x=11, y=17) == Position(x=14, y=22)


def test_subtracting_positions_subtracts_each_coordinate() -> None:
    assert Position(x=3, y=5) - Position(x=11, y=17) == Position(x=-8, y=-12)


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (Position(x=2, y=7), Position(x=4, y=8)),
        (Position(x=4, y=8), Position(x=2, y=7)),
    ],
)
def test_fill_to_covers_the_rectangle_between_corners_column_by_column(start: Position, end: Position) -> None:
    xs = (2, 3, 4) if start.x < end.x else (4, 3, 2)
    ys = (7, 8) if start.y < end.y else (8, 7)

    assert list(start.fill_to(end)) == [Position(x=x, y=y) for x in xs for y in ys]


@pytest.mark.parametrize(
    ("min_", "val", "max_", "expected"),
    [
        (0, 5, 10, 5),
        (0, -1, 10, 0),
        (0, 11, 10, 10),
        (0, 0, 0, 0),
        (3, 3, 3, 3),
        (-5, -10, 5, -5),
        (-5, 10, 5, 5),
    ],
)
def test_clamp(min_: int, val: int, max_: int, expected: int) -> None:
    assert clamp(min_, val, max_) == expected
