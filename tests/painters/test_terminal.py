from __future__ import annotations

from more_itertools import first

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.elements import Canvas
from counterweight.elements import Div
from counterweight.elements import StyledGrapheme
from counterweight.emulator import Emulator
from counterweight.emulator import Modes
from counterweight.emulator import Screen
from counterweight.geometry import Position
from counterweight.output import Frame
from counterweight.painters.terminal import ScreenView
from counterweight.painters.terminal import column_index
from counterweight.styles import CellStyle
from counterweight.styles import Style
from counterweight.styles.styles import Color
from counterweight.styles.utilities import size

FOREGROUND = Color(230, 220, 210)
BACKGROUND = Color(10, 20, 30)
RED = Color(200, 10, 20)
BLUE = Color(20, 10, 200)


def ignore_replies(data: bytes) -> None:
    """An `on_reply` for tests that don't read replies."""


def snapshot(data: str, columns: int = 4, rows: int = 2) -> Screen:
    with Emulator(columns, rows, ignore_replies, foreground=FOREGROUND, background=BACKGROUND) as emulator:
        emulator.feed(data.encode())
        return emulator.snapshot()


def graphemes(line: tuple[StyledGrapheme, ...]) -> str:
    return "".join(cell.grapheme for cell in line)


def test_a_screen_view_has_no_natural_size_or_aspect_ratio() -> None:
    view = ScreenView(snapshot("ab"))

    assert (view.natural_size, view.keeps_aspect_ratio) == ((0, 0), False)


def test_a_screen_view_draws_the_screens_top_rows_that_fit() -> None:
    screen = snapshot("ab\r\ncd\r\nef", rows=3)

    assert [graphemes(line) for line in ScreenView(screen).draw(4, 2)] == ["ab  ", "cd  "]


def test_a_screen_view_without_its_cursor_draws_the_screens_rows_as_they_are() -> None:
    screen = snapshot("ab")

    assert ScreenView(screen, show_cursor=False).draw(4, 2) == screen.lines


def test_the_cursor_is_drawn_with_its_cells_default_colors_named_and_swapped() -> None:
    screen = snapshot("ab\x1b[D")

    drawn = ScreenView(screen, show_cursor=True).draw(4, 2)

    assert drawn[0][1] == StyledGrapheme(grapheme="b", style=CellStyle(foreground=BACKGROUND, background=FOREGROUND))
    assert (drawn[0][0], drawn[0][2:], drawn[1]) == (screen.lines[0][0], screen.lines[0][2:], screen.lines[1])


def test_the_cursor_on_a_colored_cell_swaps_its_colors() -> None:
    screen = snapshot("\x1b[38;2;200;10;20;48;2;20;10;200ma\x1b[D")

    cursor = ScreenView(screen, show_cursor=True).draw(4, 2)[0][0]

    assert (cursor.style.foreground, cursor.style.background) == (BLUE, RED)


def test_the_cursor_after_a_wide_character_is_drawn_on_the_cell_at_its_column() -> None:
    screen = snapshot("日ab\x1b[D", columns=5)

    drawn = ScreenView(screen, show_cursor=True).draw(5, 2)

    assert [cell.style.background for cell in drawn[0]][:3] == [
        CellStyle().background,
        CellStyle().background,
        FOREGROUND,
    ]


def test_a_hidden_cursor_isnt_drawn() -> None:
    screen = snapshot("ab\x1b[?25l")

    assert ScreenView(screen, show_cursor=True).draw(4, 2) == screen.lines


def test_a_cursor_below_the_rows_drawn_isnt_drawn() -> None:
    screen = snapshot("ab\r\ncd")

    assert ScreenView(screen, show_cursor=True).draw(4, 1) == screen.lines[:1]


def test_a_cursor_past_the_end_of_its_line_isnt_drawn() -> None:
    line = (StyledGrapheme(grapheme="a"),)
    screen = Screen(
        columns=3,
        rows=1,
        lines=(line,),
        cursor=Position(2, 0),
        modes=Modes(),
        title="",
        foreground=FOREGROUND,
        background=BACKGROUND,
    )

    assert ScreenView(screen, show_cursor=True).draw(3, 1) == (line,)


def test_column_index_counts_each_cells_width_and_skips_zero_width_cells() -> None:
    line = (
        StyledGrapheme(grapheme="日"),
        StyledGrapheme(grapheme="a"),
        StyledGrapheme(grapheme="\u200b"),
        StyledGrapheme(grapheme="b"),
    )

    assert [column_index(line, column) for column in range(5)] == [0, 0, 1, 3, None]


async def test_a_canvas_shows_a_screens_default_colors_in_its_own_text_style() -> None:
    frames: list[Frame] = []
    screen = snapshot("a\x1b[38;2;200;10;20mb")

    @component
    def root() -> Div:
        return Div(
            children=(
                Canvas(painter=ScreenView(screen), style=size(4, 2) | Style(text_style=CellStyle(background=BLUE))),
            )
        )

    await app(root(), headless=True, dimensions=(4, 2), autopilot=[Screenshot(handler=frames.append), Quit()])

    cells = first(frames[0].paint.rows())
    assert [(cell.grapheme, cell.style.background) for cell in cells[:2]] == [("a", BLUE), ("b", BLUE)]
    assert cells[1].style.foreground == RED
