import pytest

from counterweight._output import sgr_color
from counterweight._output import sgr_from_cell_style
from counterweight.styles import TERMINAL_DEFAULT
from counterweight.styles import AnyColor
from counterweight.styles import CellStyle
from counterweight.styles import Color
from counterweight.styles import IndexedColor
from counterweight.styles._styles import resolve_cell_style


@pytest.mark.parametrize(
    ("style", "expected"),
    [
        (CellStyle(), "\x1b[38;2;255;255;255m\x1b[48;2;0;0;0m"),
        (CellStyle(bold=True), "\x1b[38;2;255;255;255m\x1b[48;2;0;0;0m\x1b[1m"),
        (CellStyle(dim=True), "\x1b[38;2;255;255;255m\x1b[48;2;0;0;0m\x1b[2m"),
        (CellStyle(italic=True), "\x1b[38;2;255;255;255m\x1b[48;2;0;0;0m\x1b[3m"),
        (CellStyle(underline=True), "\x1b[38;2;255;255;255m\x1b[48;2;0;0;0m\x1b[4m"),
        (CellStyle(strikethrough=True), "\x1b[38;2;255;255;255m\x1b[48;2;0;0;0m\x1b[9m"),
    ],
)
def test_examples(style: CellStyle, expected: str) -> None:
    assert sgr_from_cell_style(resolve_cell_style(style)) == expected


@pytest.mark.parametrize(
    ("color", "foreground", "background"),
    [
        (Color(1, 2, 3), "38;2;1;2;3", "48;2;1;2;3"),
        (IndexedColor(0), "30", "40"),
        (IndexedColor(7), "37", "47"),
        (IndexedColor(8), "90", "100"),
        (IndexedColor(15), "97", "107"),
        (IndexedColor(16), "38;5;16", "48;5;16"),
        (IndexedColor(255), "38;5;255", "48;5;255"),
        (TERMINAL_DEFAULT, "39", "49"),
    ],
)
def test_sgr_color_sets_each_kind_of_color_in_its_shortest_form(
    color: AnyColor, foreground: str, background: str
) -> None:
    assert (sgr_color(color, 30), sgr_color(color, 40)) == (foreground, background)


def test_a_style_in_terminal_colors_sets_them() -> None:
    style = CellStyle(foreground=IndexedColor(1), background=TERMINAL_DEFAULT)

    assert sgr_from_cell_style(resolve_cell_style(style)) == "\x1b[31m\x1b[49m"
