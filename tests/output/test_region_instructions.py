"""The instructions an inline app draws its region with: relative cursor moves, and growing, shrinking and leaving it."""

from __future__ import annotations

from hypothesis import given
from hypothesis import settings
from hypothesis import strategies as st

from counterweight import Inline
from counterweight._app import frame_changes
from counterweight._output import ERASE_DOWN
from counterweight._output import RESET_STYLE
from counterweight._output import leave_region
from counterweight._output import paint_to_instructions
from counterweight._output import region_change
from counterweight._output import reserve_rows
from counterweight._output import rows_down
from counterweight._output import rows_up
from counterweight._output import sgr_from_cell_style
from counterweight._output import to_column
from counterweight._paint import BLANK
from counterweight._paint import Cell
from counterweight._paint import Paint
from counterweight._paint import paint_of_rows
from counterweight.emulator import Emulator
from counterweight.geometry import Position
from counterweight.styles import CellStyle
from counterweight.styles._styles import Color
from counterweight.styles._styles import as_solid
from counterweight.styles._styles import resolve_cell_style

DEFAULT = as_solid(resolve_cell_style(CellStyle()))
RED = as_solid(resolve_cell_style(CellStyle(foreground=Color.from_name("red"))))
BOLD = as_solid(resolve_cell_style(CellStyle(bold=True)))

A = Cell("A", DEFAULT)
B = Cell("B", DEFAULT)
R = Cell("R", RED)


def test_a_move_by_no_rows_writes_nothing() -> None:
    assert (rows_down(0), rows_up(0)) == ("", "")


def test_moves_by_rows_name_how_many() -> None:
    assert (rows_down(3), rows_up(2)) == ("\x1b[3B", "\x1b[2A")


def test_to_column_counts_from_one() -> None:
    assert to_column(4) == "\x1b[5G"


def test_reserving_rows_feeds_lines_down_then_moves_back_up() -> None:
    assert reserve_rows(3) == "\n\n\x1b[2A"


def test_reserving_one_row_or_none_writes_nothing() -> None:
    assert (reserve_rows(0), reserve_rows(1)) == ("", "")


def test_a_region_drawn_from_scratch_erases_down_then_reserves_its_rows() -> None:
    assert region_change(None, 3) == ERASE_DOWN + reserve_rows(3)


def test_a_region_that_grows_reserves_its_rows() -> None:
    assert region_change(2, 4) == reserve_rows(4)


def test_a_region_that_shrinks_erases_below_its_new_last_row() -> None:
    assert region_change(4, 2) == "\x1b[2B\x1b[J\x1b[2A"


def test_a_region_that_shrinks_to_nothing_erases_from_its_top() -> None:
    assert region_change(3, 0) == "\x1b[J"


def test_a_region_that_keeps_its_height_writes_nothing() -> None:
    assert region_change(3, 3) == ""


def test_leaving_a_region_kept_moves_to_the_start_of_the_row_below_it() -> None:
    assert leave_region(3, keep=True) == "\n\n\n\r"


def test_leaving_a_region_erased_erases_from_its_top() -> None:
    assert leave_region(3, keep=False) == ERASE_DOWN


def test_relative_moves_go_by_rows_from_the_top_left_and_return_there() -> None:
    assert paint_to_instructions([(2, 1, [A, B]), (0, 0, [R])], "relative") == (
        f"\x1b[1B\x1b[3G{RESET_STYLE}{sgr_from_cell_style(DEFAULT)}AB\x1b[1A\x1b[1G\x1b[38;2;255;0;0mR{RESET_STYLE}\r"
    )


def test_relative_moves_within_the_first_row_return_by_carriage_return() -> None:
    assert paint_to_instructions([(1, 0, [A])], "relative") == (
        f"\x1b[2G{RESET_STYLE}{sgr_from_cell_style(DEFAULT)}A{RESET_STYLE}\r"
    )


def test_no_runs_move_nowhere_relatively() -> None:
    assert paint_to_instructions([], "relative") == ""


COLUMNS = 6
ROWS = 4

cells = st.sampled_from([A, B, R, BLANK, Cell(" ", BOLD), Cell("x", RED)])


@st.composite
def paints(draw: st.DrawFn) -> Paint:
    height = draw(st.integers(min_value=0, max_value=ROWS))
    return Paint(COLUMNS, height, draw(st.lists(cells, min_size=COLUMNS * height, max_size=COLUMNS * height)))


def history_line(index: int) -> str:
    return f"h{index}"


@settings(deadline=None)
@given(
    history=st.integers(min_value=0, max_value=ROWS + 2),
    frames=st.lists(st.one_of(st.none(), paints()), min_size=1, max_size=4),
)
def test_frames_leave_the_history_then_the_region_then_blank_rows(history: int, frames: list[Paint | None]) -> None:
    """
    Whatever rows the region starts below, and however it grows and shrinks, scrolling the history up,
    the terminal holds the history, then the region's last frame, then nothing.
    A `None` frame is drawn from scratch, as after a resize.
    """
    with Emulator(COLUMNS, ROWS, on_reply=lambda reply: None, scrollback=100) as emulator:
        emulator.feed("".join(history_line(index) + "\r\n" for index in range(history)).encode())

        previous: Paint | None = None
        shown = Paint(COLUMNS, 0, [])
        for frame in frames:
            paint = shown if frame is None else frame
            before, runs = frame_changes(Inline(), previous if frame is not None else None, paint)
            emulator.feed((before + paint_to_instructions(runs, "relative")).encode())
            previous = shown = paint

        scrolled_off = len(emulator.history())
        held = list(paint_of_rows(emulator.history() + emulator.snapshot().lines, COLUMNS).rows())
        cursor = emulator.snapshot().cursor

    assert ["".join(cell.grapheme for cell in row).rstrip() for row in held[:history]] == [
        history_line(index) for index in range(history)
    ]
    assert held[history : history + shown.height] == list(shown.rows())
    assert all(cell == BLANK for row in held[history + shown.height :] for cell in row)
    assert cursor == Position(0, history - scrolled_off)
