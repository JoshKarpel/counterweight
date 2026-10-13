from __future__ import annotations

from copy import copy

import pytest
from hypothesis import given
from hypothesis import strategies as st

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit, Screenshot
from counterweight.elements import Div, Text
from counterweight.geometry import Position, Region
from counterweight.graphemes import grapheme_width
from counterweight.output import Frame
from counterweight.paint import BLANK, Cell, Paint, border_fills, diff_paint, text_lines
from counterweight.styles import Style
from counterweight.styles.styles import BorderKind, CellStyle, Color, resolve_cell_style
from counterweight.styles.utilities import (
    _COLOR_MAP,
    border,
    border_bg,
    border_light,
    col,
    content_color,
    fit_content_height,
    fit_content_width,
    full,
    inset,
    inset_left,
    inset_top,
    margin,
    margin_auto,
    margin_color,
    margin_left,
    pad,
    padding_color,
    position_absolute,
    size,
    z,
)

RED = resolve_cell_style(CellStyle(foreground=Color.from_name("red")))
BLUE = resolve_cell_style(CellStyle(foreground=Color.from_name("blue")))
X = Cell("x", RED)
Y = Cell("y", RED)
WIDE = Cell("日", BLUE)
CONTINUATION = Cell("", BLUE)


# A clip larger than any test's paint, so the screen's edges are what clip.
BEYOND_THE_SCREEN = Region(left=-9, top=-9, right=9, bottom=9)


def grid(paint: Paint) -> list[str]:
    """Each row of `paint`, with `.` for a blank cell and `·` for a continuation cell."""
    return [
        "".join("." if cell is BLANK else "·" if cell.is_continuation else cell.grapheme for cell in row)
        for row in paint.rows()
    ]


def test_blank_paint_is_all_blank() -> None:
    assert grid(Paint.blank(3, 2)) == ["...", "..."]


@pytest.mark.parametrize("key", [Position(2, 1), (2, 1)])
def test_set_and_get_by_position_or_pair(key: Position | tuple[int, int]) -> None:
    paint = Paint.blank(4, 3)
    paint[key] = X
    assert paint[key] is X
    assert grid(paint) == ["....", "..x.", "...."]


@pytest.mark.parametrize("key", [(-1, 0), (0, -1), (4, 0), (0, 3)])
def test_indexing_off_screen_raises_naming_the_position_and_size(key: tuple[int, int]) -> None:
    with pytest.raises(IndexError, match=rf"\({key[0]}, {key[1]}\).*\b4x3\b"):
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
        (Region(left=3, top=0, right=9, bottom=1), ["...x", "....", "...."]),
        (Region(left=-5, top=1, right=-1, bottom=2), ["....", "....", "...."]),
        (Region(left=1, top=1, right=1, bottom=3), ["....", "....", "...."]),
    ],
    ids=["inside", "overhangs-top-left", "overhangs-bottom-right", "overhangs-right", "entirely-off-screen", "empty"],
)
def test_fill_clips_to_screen(region: Region, expected: list[str]) -> None:
    paint = Paint.blank(4, 3)
    paint.fill(region, X, BEYOND_THE_SCREEN)
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
    paint.write_row(x, y, (X, Y), BEYOND_THE_SCREEN)
    assert grid(paint) == expected


@pytest.mark.parametrize(
    ("x", "expected"),
    [
        (1, [".x日·"]),
        (-2, [" ..."]),
        (2, ["..x "]),
    ],
    ids=["inside", "clips-left-half", "clips-right-half"],
)
def test_write_row_erases_the_half_of_a_wide_cluster_left_on_screen(x: int, expected: list[str]) -> None:
    paint = Paint.blank(4, 1)
    paint.write_row(x, 0, (X, WIDE, CONTINUATION), paint.bounds)
    assert grid(paint) == expected


def test_write_row_overhanging_the_left_edge_leaves_the_row_above_alone() -> None:
    paint = Paint.blank(4, 2)
    paint.write_row(0, 0, (X, WIDE, CONTINUATION, X), paint.bounds)

    paint.write_row(-1, 1, (Y, Y, Y), paint.bounds)

    assert grid(paint) == ["x日·x", "yy.."]


@pytest.mark.parametrize(("x", "other_half"), [(1, 2), (2, 1)], ids=["over-left-half", "over-right-half"])
def test_writing_over_half_a_wide_cluster_erases_the_other_half_in_its_style(x: int, other_half: int) -> None:
    paint = Paint.blank(4, 1)
    paint.write_row(1, 0, (WIDE, CONTINUATION), paint.bounds)
    paint[x, 0] = X
    assert paint[x, 0] is X
    assert paint[other_half, 0] == Cell(" ", BLUE)


def test_fill_over_half_of_wide_clusters_erases_their_other_halves() -> None:
    paint = Paint.blank(6, 2)
    for y in range(2):
        paint.write_row(0, y, (WIDE, CONTINUATION, WIDE, CONTINUATION, WIDE, CONTINUATION), paint.bounds)
    paint.fill(Region(left=1, top=0, right=3, bottom=1), X, paint.bounds)
    assert grid(paint) == [" xx 日·", "日·日·日·"]


paint_rows = st.lists(st.sampled_from([(X,), (Y,), (WIDE, CONTINUATION)]), max_size=5).map(
    lambda pieces: tuple(cell for piece in pieces for cell in piece)
)
paint_writes = st.one_of(
    st.tuples(st.just("row"), st.integers(-3, 6), st.integers(0, 1), paint_rows),
    st.tuples(st.just("fill"), st.integers(-1, 6), st.integers(0, 1), st.integers(0, 3)),
    st.tuples(st.just("set"), st.integers(0, 4), st.integers(0, 1), st.just(())),
)


@given(st.lists(paint_writes, max_size=8))
def test_every_wide_cluster_keeps_its_continuation_through_any_writes(
    writes: list[tuple[str, int, int, object]],
) -> None:
    paint = Paint.blank(5, 2)
    for kind, x, y, extra in writes:
        if kind == "row":
            assert isinstance(extra, tuple)
            paint.write_row(x, y, extra, paint.bounds)
        elif kind == "fill":
            assert isinstance(extra, int)
            paint.fill(Region(left=x, top=y, right=x + extra, bottom=y + 1), Y, paint.bounds)
        else:
            paint[x, y] = X

    for row in paint.rows():
        for left, right in zip([BLANK, *row], [*row, BLANK]):
            assert (grapheme_width(left.grapheme) == 2 if left.grapheme else False) == right.is_continuation


@pytest.mark.parametrize(
    ("width", "expected"),
    [(5, "日·本· "), (4, "日·本·"), (3, "日· ")],
)
def test_text_lines_never_split_a_wide_cluster_at_the_right_edge(width: int, expected: str) -> None:
    (line,) = text_lines(Text(content="日本").cells, "none", "left", resolve_cell_style(CellStyle()), width, 1)
    assert "".join(cell.grapheme or "·" for cell in line) == expected


def test_text_lines_draw_no_cell_for_a_zero_width_cluster() -> None:
    (line,) = text_lines(
        Text(content="a\N{ZERO WIDTH SPACE}b").cells, "none", "left", resolve_cell_style(CellStyle()), 3, 1
    )
    assert "".join(cell.grapheme for cell in line) == "ab "


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


def test_diff_of_different_sizes_raises_naming_both_sizes() -> None:
    with pytest.raises(ValueError, match=r"\b4x3\b.*\b3x4\b"):
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


async def render(root: Div, dimensions: tuple[int, int] = (6, 2)) -> Paint:
    frames: list[Frame] = []

    @component
    def screen() -> Div:
        return root

    await app(
        screen(),
        headless=True,
        dimensions=dimensions,
        autopilot=[Screenshot(handler=frames.append), Quit()],
        check_purity=True,
    )
    return frames[0].paint


async def test_undecorated_element_with_content_color_paints_its_background() -> None:
    green = Color.from_name("green")
    paint = await render(Div(style=Style(content_color=green) | size(4, 2)))

    assert backgrounds(paint, green) == [
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

    assert "".join(cell.grapheme for cell in next(paint.rows())) == "under "


def graphemes(paint: Paint) -> list[str]:
    return ["".join(cell.grapheme for cell in row) for row in paint.rows()]


def backgrounds(paint: Paint, color: Color) -> list[list[bool]]:
    return [[cell.style.background == color for cell in row] for row in paint.rows()]


UNDER = Text(content="abcdef", style=size(6, 1))
OVER = position_absolute | inset_top(0) | inset_left(0) | margin_left(3)


async def test_margin_without_margin_color_leaves_what_lies_beneath_it_visible() -> None:
    paint = await render(Div(children=[UNDER, Text(content="x", style=OVER)]))

    assert graphemes(paint)[0] == "abcxef"


async def test_margin_with_margin_color_paints_it() -> None:
    red = Color.from_name("red")
    paint = await render(Div(children=[UNDER, Text(content="x", style=OVER | Style(margin_color=red))]))

    assert graphemes(paint)[0] == "   xef"
    assert backgrounds(paint, red)[0] == [True, True, True, False, False, False]


async def test_content_color_fills_the_border_box_but_not_the_margin() -> None:
    green = Color.from_name("green")
    paint = await render(Div(style=Style(content_color=green) | margin_left(1) | size(2, 2)))

    assert backgrounds(paint, green) == [
        [False, True, True, False, False, False],
        [False, True, True, False, False, False],
    ]


async def test_dialog_recipe_centers_over_a_parent_that_does_not_center_and_leaves_its_children_visible() -> None:
    dialog = position_absolute | inset(0) | margin_auto | fit_content_width | fit_content_height
    paint = await render(
        Div(
            style=col | full,
            children=[
                Text(content="\n".join(["abcdefg"] * 5)),
                Text(content="x", style=dialog | border | border_light),
            ],
        ),
        dimensions=(7, 5),
    )

    assert graphemes(paint) == ["abcdefg", "ab┌─┐fg", "ab│x│fg", "ab└─┘fg", "abcdefg"]


async def test_child_with_content_color_paints_over_its_raised_parents_content_color() -> None:
    green = Color.from_name("green")
    blue = Color.from_name("blue")
    paint = await render(
        Div(
            style=z(1) | Style(content_color=green) | size(4, 2),
            children=[Div(style=Style(content_color=blue) | size(2, 1))],
        )
    )

    assert backgrounds(paint, blue) == [
        [True, True, False, False, False, False],
        [False, False, False, False, False, False],
    ]
    assert backgrounds(paint, green) == [
        [False, False, True, True, False, False],
        [True, True, True, True, False, False],
    ]


DROPDOWN = Text(content="menu", style=z(1) | position_absolute | inset_top(1) | inset_left(0))


@pytest.mark.parametrize(
    ("toolbar_style", "expected"),
    [(Style(), "menuef"), (z(0), "abcdef")],
    ids=["toolbar-without-z", "toolbar-with-z-0"],
)
async def test_dropdown_escapes_a_toolbar_only_when_the_toolbar_sets_no_z(toolbar_style: Style, expected: str) -> None:
    paint = await render(
        Div(
            style=col,
            children=[
                Div(style=toolbar_style | size(6, 1), children=[DROPDOWN]),
                Text(content="abcdef", style=size(6, 1)),
            ],
        )
    )

    assert graphemes(paint)[1] == expected


async def test_wide_characters_take_two_cells_each() -> None:
    paint = await render(
        Div(style=border | border_light | size(10, 3), children=[Text(content="日本語ab")]),
        dimensions=(10, 3),
    )

    assert grid(paint) == ["┌────────┐", "│日·本·語·ab│", "└────────┘"]


async def test_text_taller_than_its_content_box_is_cut_off_at_the_box() -> None:
    frames: list[str] = []

    @component
    def root() -> Div:
        return Div(children=[Text(content="a\nb", style=size(3, 1))])

    await app(
        root(),
        headless=True,
        dimensions=(3, 2),
        autopilot=[Screenshot(handler=lambda frame: frames.append(frame.text(ansi=False))), Quit()],
    )

    assert frames == ["a  \n   "]


def test_text_lines_are_empty_at_no_width() -> None:
    assert text_lines(tuple(Text(content="hi").cells), "stable", "left", resolve_cell_style(CellStyle()), 0, 3) == ()


def test_a_border_around_a_zero_width_region_draws_nothing() -> None:
    region = Region(left=2, top=0, right=2, bottom=3)

    assert border_fills(BorderKind.Light, resolve_cell_style(CellStyle()), 0, region, (False, False, True, True)) == (
        (),
        (),
    )


def test_a_border_kind_without_joined_parts_draws_its_edges_but_gives_no_healing_hints() -> None:
    region = Region(left=0, top=0, right=3, bottom=3)

    fills, hints = border_fills(BorderKind.Star, resolve_cell_style(CellStyle()), 0, region, (True, True, True, True))

    assert (len(fills), hints) == (8, ())


async def test_color_utilities_fill_the_margin_border_padding_and_content() -> None:
    frames: list[Frame] = []

    @component
    def root() -> Div:
        return Div(
            style=margin(1)
            | border
            | pad(1)
            | margin_color("red", 500)
            | border_bg("green", 500)
            | padding_color("blue", 500)
            | content_color("amber", 500)
        )

    await app(root(), headless=True, dimensions=(9, 9), autopilot=[Screenshot(handler=frames.append), Quit()])

    [frame] = frames
    backgrounds = [frame.paint[x, x].style.background for x in (0, 1, 2, 4)]
    assert backgrounds == [_COLOR_MAP[(color, 500)] for color in ("red", "green", "blue", "amber")]
