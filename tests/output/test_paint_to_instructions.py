from __future__ import annotations

import re
from copy import copy

from hypothesis import given
from hypothesis import strategies as st

from counterweight.geometry import Position
from counterweight.output import RESET_STYLE, move_to, paint_to_instructions, sgr_from_cell_style
from counterweight.paint import Cell, Paint, diff_paint, runs_of
from counterweight.styles import CellStyle
from counterweight.styles.styles import Color, resolve_cell_style

DEFAULT = resolve_cell_style(CellStyle())
RED_FG = resolve_cell_style(CellStyle(foreground=Color.from_name("red")))
BOLD = resolve_cell_style(CellStyle(bold=True))

A = Cell("A", DEFAULT)
B = Cell("B", DEFAULT)
R = Cell("R", RED_FG)


def mt(x: int, y: int) -> str:
    return move_to(Position(x, y))


def test_no_runs_is_no_instructions() -> None:
    assert paint_to_instructions([]) == ""


def test_run_moves_once_and_sets_style_once() -> None:
    assert (
        paint_to_instructions([(2, 1, [A, B])])
        == f"{mt(2, 1)}{RESET_STYLE}{sgr_from_cell_style(DEFAULT)}AB{RESET_STYLE}"
    )


def test_style_change_mid_run_resets_then_sets_style() -> None:
    assert paint_to_instructions([(0, 0, [A, R])]) == (
        f"{mt(0, 0)}{RESET_STYLE}{sgr_from_cell_style(DEFAULT)}A{RESET_STYLE}{sgr_from_cell_style(RED_FG)}R{RESET_STYLE}"
    )


def with_uninterned_style(cell: Cell) -> Cell:
    """A copy of `cell` whose style equals its own but is a different object, which interning would never produce."""
    uninterned = copy(cell)
    object.__setattr__(uninterned, "style", copy(cell.style))
    return uninterned


def test_equal_styles_that_are_different_objects_set_style_once() -> None:
    b = with_uninterned_style(B)
    assert b.style is not A.style

    assert (
        paint_to_instructions([(0, 0, [A, b])])
        == f"{mt(0, 0)}{RESET_STYLE}{sgr_from_cell_style(DEFAULT)}AB{RESET_STYLE}"
    )


def test_style_carries_across_runs() -> None:
    assert paint_to_instructions([(0, 0, [A]), (0, 1, [B])]) == (
        f"{mt(0, 0)}{RESET_STYLE}{sgr_from_cell_style(DEFAULT)}A{mt(0, 1)}B{RESET_STYLE}"
    )


INSTRUCTION = re.compile(r"\x1b\[(\d+);(\d+)f|(\x1b\[[\d;]*m)|(.)", re.DOTALL)


def apply(instructions: str, screen: list[list[tuple[str, str]]]) -> None:
    """
    Run `instructions` on `screen`, a grid of (char, active SGR) pairs, the way a terminal would,
    for the subset of escape sequences that `paint_to_instructions` emits.
    """
    x = y = 0
    sgr = ""
    for match in INSTRUCTION.finditer(instructions):
        row, column, escape, char = match.groups()
        if row is not None:
            y, x = int(row) - 1, int(column) - 1
        elif escape is not None:
            sgr = "" if escape == RESET_STYLE else sgr + escape
        else:
            screen[y][x] = (char, sgr)
            x += 1


def appearance(paint: Paint) -> list[list[tuple[str, str]]]:
    return [[(cell.char, sgr_from_cell_style(cell.style)) for cell in row] for row in paint.rows()]


cells = st.sampled_from([A, B, R, Cell("A", BOLD), Cell(" ", BOLD), Cell(" ", DEFAULT)])


@st.composite
def paint_pairs(draw: st.DrawFn) -> tuple[Paint, Paint]:
    width = draw(st.integers(min_value=1, max_value=6))
    height = draw(st.integers(min_value=1, max_value=4))
    size = width * height
    current = draw(st.lists(cells, min_size=size, max_size=size))
    new = draw(st.lists(cells, min_size=size, max_size=size))
    return Paint(width, height, current), Paint(width, height, new)


@given(paint_pairs())
def test_drawing_the_diff_over_the_current_paint_shows_the_new_paint(pair: tuple[Paint, Paint]) -> None:
    current, new = pair
    screen = appearance(current)

    apply(paint_to_instructions(diff_paint(new, current)), screen)

    assert screen == appearance(new)


@given(paint_pairs())
def test_drawing_every_run_shows_the_paint(pair: tuple[Paint, Paint]) -> None:
    _, paint = pair
    screen = [[("?", "")] * paint.width for _ in range(paint.height)]

    apply(paint_to_instructions(runs_of(paint)), screen)

    assert screen == appearance(paint)
