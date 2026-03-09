import pytest

from counterweight.geometry import Position
from counterweight.output import move_to, paint_to_instructions, sgr_from_cell_style
from counterweight.paint import P
from counterweight.styles import CellStyle
from counterweight.styles.styles import Color

DEFAULT = CellStyle()
RED_FG = CellStyle(foreground=Color.from_name("red"))
RESET = "\x1b[0m"


def sgr(style: CellStyle) -> str:
    return sgr_from_cell_style(style)


def mt(x: int, y: int) -> str:
    return move_to(Position(x, y))


def cell(char: str, style: CellStyle = DEFAULT, z: int = 0) -> P:
    return P(char=char, style=style, z=z)


@pytest.mark.parametrize(
    ("paint", "expected"),
    (
        # single cell
        (
            {Position(0, 0): cell("A")},
            f"{mt(0, 0)}{sgr(DEFAULT)}A{RESET}",
        ),
        # two adjacent cells — each gets its own escape sequence
        (
            {Position(0, 0): cell("A"), Position(1, 0): cell("B")},
            f"{mt(0, 0)}{sgr(DEFAULT)}A{RESET}{mt(1, 0)}{sgr(DEFAULT)}B{RESET}",
        ),
        # style change mid-row
        (
            {Position(0, 0): cell("A"), Position(1, 0): cell("B", RED_FG)},
            f"{mt(0, 0)}{sgr(DEFAULT)}A{RESET}{mt(1, 0)}{sgr(RED_FG)}B{RESET}",
        ),
        # different rows
        (
            {Position(0, 0): cell("A"), Position(0, 1): cell("B")},
            f"{mt(0, 0)}{sgr(DEFAULT)}A{RESET}{mt(0, 1)}{sgr(DEFAULT)}B{RESET}",
        ),
    ),
)
def test_paint_to_instructions(paint: dict[Position, P], expected: str) -> None:
    assert paint_to_instructions(paint) == expected
