import pytest

from counterweight.elements import NEWLINE, Chunk
from counterweight.styles.styles import CellStyle, Color
from counterweight.utils import canvas

RED = Color.from_name("red")
BLUE = Color.from_name("blue")
GREEN = Color.from_name("green")


def half_block(top: Color, bottom: Color) -> Chunk:
    return Chunk(content="▀", style=CellStyle(foreground=top, background=bottom))


def test_canvas_draws_each_pair_of_pixel_rows_as_one_row_of_half_blocks() -> None:
    assert canvas(2, 4, {(0, 0): RED, (1, 3): BLUE}, default=GREEN) == (
        half_block(RED, GREEN),
        half_block(GREEN, GREEN),
        NEWLINE,
        half_block(GREEN, GREEN),
        half_block(GREEN, BLUE),
    )


@pytest.mark.parametrize("height", [3, 5])
def test_canvas_rejects_an_odd_height(height: int) -> None:
    with pytest.raises(ValueError, match=rf"\b{height}\b"):
        canvas(2, height, {})
