from __future__ import annotations

import re
from copy import copy

from hypothesis import given
from hypothesis import strategies as st

from counterweight.geometry import Position
from counterweight.graphemes import grapheme_width
from counterweight.output import HYPERLINK_END
from counterweight.output import RESET_STYLE
from counterweight.output import hyperlink
from counterweight.output import move_to
from counterweight.output import paint_to_instructions
from counterweight.output import sgr_from_cell_style
from counterweight.paint import Cell
from counterweight.paint import Paint
from counterweight.paint import diff_paint
from counterweight.paint import runs_of
from counterweight.styles import CellStyle
from counterweight.styles.styles import Color
from counterweight.styles.styles import resolve_cell_style

DEFAULT = resolve_cell_style(CellStyle())
RED_FG = resolve_cell_style(CellStyle(foreground=Color.from_name("red")))
BOLD = resolve_cell_style(CellStyle(bold=True))
LINKED = resolve_cell_style(CellStyle(link="https://example.com/a"))
OTHER_LINKED = resolve_cell_style(CellStyle(link="https://example.com/b"))

A = Cell("A", DEFAULT)
B = Cell("B", DEFAULT)
R = Cell("R", RED_FG)
L = Cell("L", LINKED)


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


def test_link_opens_with_its_style_and_closes_at_the_end() -> None:
    assert paint_to_instructions([(0, 0, [A, L, L])]) == (
        f"{mt(0, 0)}{RESET_STYLE}{sgr_from_cell_style(DEFAULT)}A"
        f"{RESET_STYLE}{sgr_from_cell_style(LINKED)}{hyperlink(LINKED.link)}LL{RESET_STYLE}{HYPERLINK_END}"
    )


def test_link_stays_open_across_runs() -> None:
    assert paint_to_instructions([(0, 0, [L]), (0, 1, [L])]) == (
        f"{mt(0, 0)}{RESET_STYLE}{sgr_from_cell_style(LINKED)}{hyperlink(LINKED.link)}L{mt(0, 1)}L"
        f"{RESET_STYLE}{HYPERLINK_END}"
    )


def test_unlinked_cell_after_a_link_closes_it() -> None:
    assert paint_to_instructions([(0, 0, [L, A])]) == (
        f"{mt(0, 0)}{RESET_STYLE}{sgr_from_cell_style(LINKED)}{hyperlink(LINKED.link)}L"
        f"{RESET_STYLE}{sgr_from_cell_style(DEFAULT)}{HYPERLINK_END}A{RESET_STYLE}"
    )


INSTRUCTION = re.compile(r"\x1b\[(\d+);(\d+)f|(\x1b\[[\d;]*m)|\x1b\]8;;(.*?)\x1b\\|(.)", re.DOTALL)

Appearance = tuple[str, str, str | None]


def apply(instructions: str, screen: list[list[Appearance]]) -> str | None:
    """
    Run `instructions` on `screen`, a grid of (char, active SGR, active hyperlink) triples, the way a terminal would,
    for the subset of escape sequences that `paint_to_instructions` emits,
    returning the hyperlink still open at the end.

    A wide character fills its own column and the next, which holds `""`, and drawing over its left half
    erases its right half to a space, as terminals do. Every character here is one code point.
    Runs never start on a right half, so drawing over one without its left half first fails.
    """
    x = y = 0
    sgr = ""
    link = None
    for match in INSTRUCTION.finditer(instructions):
        row, column, escape, uri, char = match.groups()
        if row is not None:
            y, x = int(row) - 1, int(column) - 1
        elif escape is not None:
            sgr = "" if escape == RESET_STYLE else sgr + escape
        elif uri is not None:
            link = uri or None
        else:
            line = screen[y]
            width = grapheme_width(char)
            for covered in range(x, x + width):
                erase_other_half(line, covered)
            line[x] = (char, sgr, link)
            if width == 2:
                line[x + 1] = ("", sgr, link)
            x += width
    return link


def erase_other_half(line: list[Appearance], x: int) -> None:
    char, _, _ = line[x]
    assert char, f"drew over the right half of a wide character at column {x} before its left half"
    if grapheme_width(char) == 2:
        _, sgr, link = line[x + 1]
        line[x + 1] = (" ", sgr, link)


def appearance(paint: Paint) -> list[list[Appearance]]:
    return [[(cell.grapheme, sgr_from_cell_style(cell.style), cell.style.link) for cell in row] for row in paint.rows()]


narrow_cells = st.sampled_from(
    [A, B, R, L, Cell("A", BOLD), Cell(" ", BOLD), Cell(" ", DEFAULT), Cell(" ", LINKED), Cell("O", OTHER_LINKED)]
)
wide_cells = st.sampled_from([Cell("日", DEFAULT), Cell("本", DEFAULT), Cell("日", RED_FG), Cell("本", LINKED)])


@st.composite
def paint_rows(draw: st.DrawFn, width: int) -> list[Cell]:
    """A row of `width` cells, where each wide cell is followed by its continuation."""
    row: list[Cell] = []
    while len(row) < width:
        if len(row) + 2 <= width and draw(st.booleans()):
            wide = draw(wide_cells)
            row += [wide, Cell("", wide.style)]
        else:
            row.append(draw(narrow_cells))
    return row


@st.composite
def paints(draw: st.DrawFn, width: int, height: int) -> Paint:
    return Paint(width, height, [cell for _ in range(height) for cell in draw(paint_rows(width))])


@st.composite
def paint_pairs(draw: st.DrawFn) -> tuple[Paint, Paint]:
    width = draw(st.integers(min_value=1, max_value=6))
    height = draw(st.integers(min_value=1, max_value=4))
    return draw(paints(width, height)), draw(paints(width, height))


@given(paint_pairs())
def test_drawing_the_diff_over_the_current_paint_shows_the_new_paint(pair: tuple[Paint, Paint]) -> None:
    current, new = pair
    screen = appearance(current)

    open_link = apply(paint_to_instructions(diff_paint(new, current)), screen)

    assert screen == appearance(new)
    assert open_link is None


@given(paint_pairs())
def test_drawing_every_run_shows_the_paint(pair: tuple[Paint, Paint]) -> None:
    _, paint = pair
    screen: list[list[Appearance]] = [[("?", "", None)] * paint.width for _ in range(paint.height)]

    open_link = apply(paint_to_instructions(runs_of(paint)), screen)

    assert screen == appearance(paint)
    assert open_link is None
