from __future__ import annotations

from dataclasses import replace

from counterweight import app
from counterweight._output import Frame
from counterweight._paint import BLANK
from counterweight._paint import Cell
from counterweight._paint import Paint
from counterweight._paint import rows_of
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.elements import Canvas
from counterweight.elements import Div
from counterweight.elements import Rows
from counterweight.elements import StyledGrapheme
from counterweight.elements import Text
from counterweight.geometry import Region
from counterweight.painters._frames import PaintView
from counterweight.styles import CellStyle
from counterweight.styles._styles import CELL_STYLE_DEFAULTS
from counterweight.styles._styles import Color
from counterweight.styles._styles import with_colors

TEAL = with_colors(replace(CELL_STYLE_DEFAULTS, bold=True), Color.from_hex("#2dd4bf"), Color.from_hex("#134e4a"))
WIDE = Cell("日", TEAL)
CONTINUATION = Cell("", TEAL)


def painted(*rows: str) -> Paint:
    """A paint of `rows`, each character a cell in `TEAL`, with `日` taking two."""
    paint = Paint.blank(max(len(row) for row in rows), len(rows))
    for y, row in enumerate(rows):
        for x, character in enumerate(row):
            if character == "日":
                paint[x, y] = WIDE
            elif character == "_":
                paint[x, y] = CONTINUATION
            else:
                paint[x, y] = Cell(character, TEAL)
    return paint


def text_of(rows: Rows) -> list[str]:
    return ["".join(styled.grapheme for styled in row) for row in rows]


def test_cells_in_is_the_regions_cells_row_by_row() -> None:
    cells = painted("abc", "def").cells_in(Region(left=1, top=0, right=3, bottom=2))

    assert [[cell.grapheme for cell in row] for row in cells] == [["b", "c"], ["e", "f"]]


def test_cells_in_nothing_is_the_whole_paints() -> None:
    paint = painted("ab", "cd")

    assert paint.cells_in() == tuple(tuple(row) for row in paint.rows())


def test_cells_in_a_region_off_the_paint_are_blank() -> None:
    cells = painted("ab").cells_in(Region(left=1, top=0, right=3, bottom=2))

    assert cells == ((Cell("b", TEAL), BLANK), (BLANK, BLANK))


def test_cells_in_keeps_its_cells_when_the_paint_changes() -> None:
    paint = painted("ab")
    cells = paint.cells_in()

    paint[0, 0] = Cell("z", TEAL)

    assert cells[0][0] == Cell("a", TEAL)


def test_rows_of_draws_each_cell_in_its_style() -> None:
    (row,) = rows_of(painted("a").cells_in())

    assert row == (
        StyledGrapheme(
            grapheme="a",
            style=CellStyle(
                foreground=Color.from_hex("#2dd4bf"),
                background=Color.from_hex("#134e4a"),
                bold=True,
                dim=False,
                italic=False,
                underline=False,
                strikethrough=False,
                link=None,
            ),
        ),
    )


def test_rows_of_draws_a_two_cell_cluster_once() -> None:
    assert text_of(rows_of(painted("a日_b").cells_in())) == ["a日b"]


def test_rows_of_draws_a_continuation_cut_from_its_cluster_as_a_space() -> None:
    rows = rows_of(painted("日_b").cells_in(Region(left=1, top=0, right=3, bottom=1)))

    assert (text_of(rows), rows[0][0].style.background) == ([" b"], Color.from_hex("#134e4a"))


def test_rows_of_draws_a_cluster_cut_from_its_continuation_as_a_space() -> None:
    assert text_of(rows_of(painted("a日_").cells_in(Region(left=0, top=0, right=2, bottom=1)))) == ["a "]


def test_rows_of_draws_cells_put_together_from_two_pictures_as_a_terminal_would() -> None:
    assert text_of(rows_of([(Cell("a", TEAL), CONTINUATION, WIDE, Cell("b", TEAL))])) == ["a  b"]


def test_a_paint_view_is_as_big_as_its_region() -> None:
    painter = painted("abc", "def").as_painter(Region(left=0, top=0, right=3, bottom=1))

    assert (painter.natural_size, painter.keeps_aspect_ratio) == ((3, 1), False)


def test_a_paint_view_draws_the_rows_that_fit() -> None:
    assert text_of(painted("abc", "def").as_painter().draw(3, 1)) == ["abc"]


async def test_a_canvas_drawing_a_screenshot_shows_what_the_screen_showed() -> None:
    frames: list[Frame] = []

    @component
    def shown() -> Div:
        return Div(children=(Text(content="seen 日本"),))

    await app(shown(), headless=True, dimensions=(9, 1), autopilot=(Screenshot(handler=frames.append), Quit()))
    painter: PaintView = frames[0].paint.as_painter()

    @component
    def picture() -> Div:
        return Div(children=(Canvas(painter=painter),))

    await app(picture(), headless=True, dimensions=(9, 1), autopilot=(Screenshot(handler=frames.append), Quit()))

    assert frames[1].paint == frames[0].paint
