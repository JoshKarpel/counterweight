from __future__ import annotations

from copy import copy

import pytest

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit, Screenshot
from counterweight.elements import Div, Text
from counterweight.geometry import Position, Region
from counterweight.output import Frame
from counterweight.paint import BLANK, Cell, Paint, diff_paint
from counterweight.styles import Style
from counterweight.styles.styles import CellStyle, Color, resolve_cell_style
from counterweight.styles.utilities import inset_left, inset_top, position_absolute, size, z

RED = resolve_cell_style(CellStyle(foreground=Color.from_name("red")))
X = Cell("x", RED)
Y = Cell("y", RED)


def grid(paint: Paint) -> list[str]:
    return ["".join("." if cell is BLANK else cell.char for cell in row) for row in paint.rows()]


def test_blank_paint_is_all_blank() -> None:
    assert grid(Paint.blank(3, 2)) == ["...", "..."]


@pytest.mark.parametrize("key", [Position(2, 1), (2, 1)])
def test_set_and_get_by_position_or_pair(key: Position | tuple[int, int]) -> None:
    paint = Paint.blank(4, 3)
    paint[key] = X
    assert paint[key] is X
    assert grid(paint) == ["....", "..x.", "...."]


@pytest.mark.parametrize("key", [(-1, 0), (0, -1), (4, 0), (0, 3)])
def test_indexing_off_screen_raises(key: tuple[int, int]) -> None:
    with pytest.raises(IndexError):
        Paint.blank(4, 3)[key]


@pytest.mark.parametrize("position", [Position(-1, 0), Position(0, -1), Position(4, 0), Position(0, 3)])
def test_get_off_screen_returns_none(position: Position) -> None:
    assert Paint.blank(4, 3).get(position) is None


@pytest.mark.parametrize(
    ("region", "expected"),
    [
        (Region(left=1, top=0, right=3, bottom=2), [".xx.", ".xx.", "...."]),
        (Region(left=-2, top=-1, right=2, bottom=1), ["xx..", "....", "...."]),
        (Region(left=3, top=2, right=9, bottom=9), ["....", "....", "...x"]),
        (Region(left=-5, top=1, right=-1, bottom=2), ["....", "....", "...."]),
        (Region(left=1, top=1, right=1, bottom=3), ["....", "....", "...."]),
    ],
    ids=["inside", "overhangs-top-left", "overhangs-bottom-right", "entirely-off-screen", "empty"],
)
def test_fill_clips_to_screen(region: Region, expected: list[str]) -> None:
    paint = Paint.blank(4, 3)
    paint.fill(region, X)
    assert grid(paint) == expected


@pytest.mark.parametrize(
    ("x", "y", "expected"),
    [
        (1, 1, ["....", ".xy.", "...."]),
        (-1, 0, ["y...", "....", "...."]),
        (3, 2, ["....", "....", "...x"]),
        (-2, 0, ["....", "....", "...."]),
        (4, 0, ["....", "....", "...."]),
        (0, 3, ["....", "....", "...."]),
        (0, -1, ["....", "....", "...."]),
    ],
    ids=["inside", "overhangs-left", "overhangs-right", "off-left", "off-right", "below", "above"],
)
def test_write_row_clips_to_screen(x: int, y: int, expected: list[str]) -> None:
    paint = Paint.blank(4, 3)
    paint.write_row(x, y, (X, Y))
    assert grid(paint) == expected


def test_diff_of_identical_paints_is_empty() -> None:
    paint = Paint.blank(4, 3)
    paint[1, 1] = X
    assert diff_paint(paint, paint.copy()) == []


def test_diff_has_only_changed_cells() -> None:
    current = Paint.blank(4, 3)
    current[0, 2] = X
    new = current.copy()
    new[1, 0] = X
    new[0, 2] = Y
    assert diff_paint(new, current) == [(1, 0, [X]), (0, 2, [Y])]


def test_diff_groups_adjacent_changes_into_runs() -> None:
    current = Paint.blank(6, 1)
    new = current.copy()
    for x in (0, 1, 3, 4, 5):
        new[x, 0] = X
    assert diff_paint(new, current) == [(0, 0, [X, X]), (3, 0, [X, X, X])]


def test_diff_compares_equal_cells_by_value() -> None:
    current = Paint.blank(2, 1)
    current[0, 0] = X
    new = Paint.blank(2, 1)
    new[0, 0] = copy(X)
    new[1, 0] = Y
    assert new[0, 0] is not X
    assert diff_paint(new, current) == [(1, 0, [Y])]


def test_diff_of_different_sizes_raises() -> None:
    with pytest.raises(ValueError):
        diff_paint(Paint.blank(4, 3), Paint.blank(3, 4))


def test_copy_is_independent() -> None:
    paint = Paint.blank(2, 1)
    copy = paint.copy()
    copy[0, 0] = X
    assert paint[0, 0] is BLANK


def test_items_pairs_cells_with_positions_row_by_row() -> None:
    paint = Paint.blank(2, 2)
    paint[1, 0] = X
    paint[0, 1] = Y
    assert list(paint.items()) == [
        (Position(0, 0), BLANK),
        (Position(1, 0), X),
        (Position(0, 1), Y),
        (Position(1, 1), BLANK),
    ]


async def render(root: Div) -> Paint:
    frames: list[Frame] = []

    @component
    def screen() -> Div:
        return root

    await app(screen, headless=True, dimensions=(6, 2), autopilot=[Screenshot(handler=frames.append), Quit()])
    return frames[0].paint


async def test_undecorated_element_with_content_color_paints_its_background() -> None:
    green = Color.from_name("green")
    paint = await render(Div(style=Style(content_color=green) | size(4, 2)))

    assert [[cell.style.background == green for cell in row] for row in paint.rows()] == [
        [True, True, True, True, False, False],
        [True, True, True, True, False, False],
    ]


async def test_undecorated_element_over_another_leaves_it_visible() -> None:
    paint = await render(
        Div(
            children=[
                Text(content="under", style=size(6, 1)),
                Div(style=z(1) | position_absolute | inset_top(0) | inset_left(0) | size(6, 2)),
            ]
        )
    )

    assert "".join(cell.char for cell in next(paint.rows())) == "under "
