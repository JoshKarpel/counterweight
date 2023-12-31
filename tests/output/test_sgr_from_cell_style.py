import pytest

from counterweight.output import sgr_from_cell_style
from counterweight.styles import CellStyle


@pytest.mark.parametrize(
    ("style", "expected"),
    (
        (CellStyle(), "\x1b[38;2;255;255;255m\x1b[48;2;0;0;0m"),
        (CellStyle(bold=True), "\x1b[38;2;255;255;255m\x1b[48;2;0;0;0m\x1b[1m"),
        (CellStyle(dim=True), "\x1b[38;2;255;255;255m\x1b[48;2;0;0;0m\x1b[2m"),
        (CellStyle(italic=True), "\x1b[38;2;255;255;255m\x1b[48;2;0;0;0m\x1b[3m"),
        (CellStyle(underline=True), "\x1b[38;2;255;255;255m\x1b[48;2;0;0;0m\x1b[4m"),
        (CellStyle(strikethrough=True), "\x1b[38;2;255;255;255m\x1b[48;2;0;0;0m\x1b[9m"),
    ),
)
def test_examples(style: CellStyle, expected: str) -> None:
    assert sgr_from_cell_style(style) == expected
