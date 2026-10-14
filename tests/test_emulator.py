from __future__ import annotations

import pytest

from counterweight.elements import Rows
from counterweight.elements import StyledGrapheme
from counterweight.emulator import MAX_SCROLLBACK
from counterweight.emulator import PLAIN_CELLS_KEPT
from counterweight.emulator import Emulator
from counterweight.emulator import Modes
from counterweight.emulator import MouseTracking
from counterweight.emulator import Screen
from counterweight.geometry import Position
from counterweight.styles import CellStyle
from counterweight.styles.styles import UNSET
from counterweight.styles.styles import Color

FOREGROUND = Color(230, 220, 210)
BACKGROUND = Color(10, 20, 30)


def ignore_replies(data: bytes) -> None:
    """An `on_reply` for tests that don't read replies."""


def snapshot(data: str | bytes, columns: int = 8, rows: int = 2) -> Screen:
    """What a `columns` by `rows` terminal fed `data` shows."""
    with Emulator(columns, rows, ignore_replies, foreground=FOREGROUND, background=BACKGROUND) as emulator:
        emulator.feed(data.encode() if isinstance(data, str) else data)
        return emulator.snapshot()


def text(screen: Screen) -> list[str]:
    return ["".join(cell.grapheme for cell in line) for line in screen.lines]


def first_cell(screen: Screen) -> StyledGrapheme:
    return screen.lines[0][0]


def test_a_screen_has_a_row_of_cells_for_each_of_its_rows_each_as_wide_as_the_terminal() -> None:
    screen = snapshot("hi\r\nthere", columns=6, rows=3)

    assert (screen.columns, screen.rows) == (6, 3)
    assert text(screen) == ["hi    ", "there ", "      "]


def test_output_past_the_last_row_scrolls_the_screen() -> None:
    assert text(snapshot("one\r\ntwo\r\nthree", columns=5, rows=2)) == ["two  ", "three"]


def test_cells_in_the_default_colors_leave_them_unset() -> None:
    assert first_cell(snapshot("a")).style == CellStyle()


@pytest.mark.parametrize(
    ("sequence", "style"),
    [
        ("\x1b[38;2;1;2;3m", CellStyle(foreground=Color(1, 2, 3))),
        ("\x1b[48;2;4;5;6m", CellStyle(background=Color(4, 5, 6))),
        ("\x1b[1m", CellStyle(bold=True)),
        ("\x1b[2m", CellStyle(dim=True)),
        ("\x1b[3m", CellStyle(italic=True)),
        ("\x1b[4m", CellStyle(underline=True)),
        ("\x1b[4:3m", CellStyle(underline=True)),
        ("\x1b[9m", CellStyle(strikethrough=True)),
    ],
    ids=["foreground", "background", "bold", "dim", "italic", "underline", "curly underline", "strikethrough"],
)
def test_styled_cells_carry_their_colors_and_attributes(sequence: str, style: CellStyle) -> None:
    unset = CellStyle(bold=False, dim=False, italic=False, underline=False, strikethrough=False)

    assert first_cell(snapshot(f"{sequence}a")).style == unset | style


def test_palette_colors_are_resolved_through_the_palette() -> None:
    assert (
        snapshot("\x1b[38;5;196ma\x1b[38;5;21mb").lines[0][:2]
        == snapshot("\x1b[38;2;255;0;0ma\x1b[38;2;0;0;255mb").lines[0][:2]
    )


@pytest.mark.parametrize(
    ("sequence", "foreground", "background"),
    [
        ("\x1b[7m", BACKGROUND, FOREGROUND),
        ("\x1b[7;38;2;1;2;3m", BACKGROUND, Color(1, 2, 3)),
        ("\x1b[7;48;2;4;5;6m", Color(4, 5, 6), FOREGROUND),
        ("\x1b[8m", BACKGROUND, UNSET),
        ("\x1b[8;48;2;4;5;6m", Color(4, 5, 6), Color(4, 5, 6)),
    ],
    ids=[
        "inverse of the defaults",
        "inverse of a foreground",
        "inverse of a background",
        "invisible on the default background",
        "invisible on a background",
    ],
)
def test_swapped_and_invisible_cells_name_the_default_colors_they_take(
    sequence: str, foreground: Color, background: Color | UNSET
) -> None:
    style = first_cell(snapshot(f"{sequence}a")).style

    assert (style.foreground, style.background) == (foreground, background)


def test_a_blank_cell_erased_with_a_background_has_it() -> None:
    style = first_cell(snapshot("\x1b[48;2;4;5;6m\x1b[K")).style

    assert style.background == Color(4, 5, 6)


def test_a_styled_character_repeated_in_a_row_is_the_same_cell_each_time() -> None:
    line = snapshot("\x1b[31maba").lines[0]

    assert line[0] is line[2]
    assert line[0] != line[1]


def test_a_wide_character_is_one_cell_and_takes_two_columns() -> None:
    line = snapshot("日本x", columns=6, rows=1).lines[0]

    assert [(cell.grapheme, cell.width) for cell in line] == [("日", 2), ("本", 2), ("x", 1), (" ", 1)]


def test_a_styled_wide_character_is_one_cell_and_takes_two_columns() -> None:
    line = snapshot("\x1b[31m日本", columns=4, rows=1).lines[0]

    assert [(cell.grapheme, cell.width) for cell in line] == [("日", 2), ("本", 2)]


def test_a_grapheme_cluster_of_several_code_points_is_one_cell() -> None:
    line = snapshot("éx", columns=3, rows=1).lines[0]

    assert [cell.grapheme for cell in line] == ["é", "x", " "]


def test_a_zero_width_character_libghostty_puts_in_the_cell_before_is_kept_and_takes_no_column() -> None:
    line = snapshot("a\u200bb", columns=3, rows=1).lines[0]

    assert [(cell.grapheme, cell.width) for cell in line] == [("a", 1), ("\u200b", 0), ("b", 1), (" ", 1)]


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ("❤️x", [" ", "x", " "]),
        ("किx", ["क", " ", "x"]),
    ],
    ids=["one column to libghostty, two here", "one column to libghostty, none here"],
)
def test_a_cell_measured_wider_here_or_with_no_width_is_drawn_as_spaces_in_libghosttys_columns(
    data: str, expected: list[str]
) -> None:
    line = snapshot(data, columns=3, rows=1).lines[0]

    assert [cell.grapheme for cell in line] == expected
    assert sum(cell.width for cell in line) == 3


def test_a_cell_measured_narrower_here_is_followed_by_spaces_to_keep_libghosttys_columns() -> None:
    # libghostty gives a two-em dash two columns, and wcwidth one.
    line = snapshot("⸺x", columns=4, rows=1).lines[0]

    assert [(cell.grapheme, cell.width) for cell in line] == [("⸺", 1), (" ", 1), ("x", 1), (" ", 1)]


def test_snapshotting_a_terminal_that_didnt_change_returns_the_same_screen() -> None:
    with Emulator(4, 2, ignore_replies) as emulator:
        emulator.feed(b"ab")
        first = emulator.snapshot()

        assert emulator.snapshot() is first


def test_snapshotting_a_changed_terminal_returns_a_new_screen_sharing_the_rows_that_didnt_change() -> None:
    with Emulator(4, 2, ignore_replies) as emulator:
        emulator.feed(b"ab\r\ncd")
        first = emulator.snapshot()
        emulator.feed(b"e")
        second = emulator.snapshot()

    assert second is not first
    assert second.lines[0] is first.lines[0]
    assert text(second) == ["ab  ", "cde "]


def test_changing_the_default_colors_converts_the_rows_that_name_them_again() -> None:
    with Emulator(4, 1, ignore_replies, foreground=FOREGROUND, background=BACKGROUND) as emulator:
        emulator.feed(b"\x1b[7ma")
        before = emulator.snapshot()
        emulator.feed(b"\x1b]11;rgb:12/34/56\x07")
        after = emulator.snapshot()

    assert (before.background, after.background) == (BACKGROUND, Color(0x12, 0x34, 0x56))
    assert first_cell(after).style.foreground == Color(0x12, 0x34, 0x56)


def test_the_cursor_is_where_the_program_left_it() -> None:
    assert snapshot("ab\r\nc").cursor == Position(1, 1)


def test_the_cursor_on_the_second_column_of_a_wide_character_is_at_its_first() -> None:
    assert snapshot("日\x1b[D", columns=4, rows=1).cursor == Position(0, 0)


def test_a_hidden_cursor_is_none() -> None:
    assert snapshot("ab\x1b[?25l").cursor is None


def test_the_title_is_what_the_program_set() -> None:
    assert snapshot("\x1b]2;my title\x07").title == "my title"


def test_the_title_is_empty_until_the_program_sets_one() -> None:
    assert snapshot("a").title == ""


def test_the_default_modes_are_unset() -> None:
    assert snapshot("a").modes == Modes()


@pytest.mark.parametrize(
    ("sequence", "modes"),
    [
        ("\x1b[?1h", Modes(application_cursor_keys=True)),
        ("\x1b[?2004h", Modes(bracketed_paste=True)),
        ("\x1b[?1006h", Modes(sgr_mouse=True)),
        ("\x1b[?1004h", Modes(focus_events=True)),
        ("\x1b[?1049h", Modes(alternate_screen=True)),
        ("\x1b[?1047h", Modes(alternate_screen=True)),
        ("\x1b[?47h", Modes(alternate_screen=True)),
    ],
)
def test_modes_are_what_the_program_set(sequence: str, modes: Modes) -> None:
    assert snapshot(sequence).modes == modes


@pytest.mark.parametrize(
    ("sequence", "tracking"),
    [
        ("\x1b[?9h", "x10"),
        ("\x1b[?1000h", "normal"),
        ("\x1b[?1002h", "button"),
        ("\x1b[?1003h", "any"),
        ("\x1b[?1000h\x1b[?1003h\x1b[?1002h", "any"),
    ],
)
def test_the_most_detailed_mouse_tracking_set_wins(sequence: str, tracking: MouseTracking) -> None:
    assert snapshot(sequence).modes.mouse_tracking == tracking


def test_the_alternate_screen_shows_its_own_cells_and_leaving_it_restores_the_main_screen() -> None:
    with Emulator(5, 1, ignore_replies) as emulator:
        emulator.feed(b"shell")
        emulator.feed(b"\x1b[?1049h\x1b[2J\x1b[Hvim")
        alternate = emulator.snapshot()
        emulator.feed(b"\x1b[?1049l")
        main = emulator.snapshot()

    assert (text(alternate), text(main)) == (["vim  "], ["shell"])


def test_queries_are_answered_through_on_reply() -> None:
    replies: list[bytes] = []
    with Emulator(8, 3, replies.append) as emulator:
        emulator.feed(b"ab\r\nc\x1b[6n")

    assert replies == [b"\x1b[2;2R"]


def test_an_exception_from_on_reply_is_raised_by_the_feed_that_asked() -> None:
    def fail(data: bytes) -> None:
        raise RuntimeError(data)

    with Emulator(8, 3, fail) as emulator, pytest.raises(RuntimeError, match="R"):
        emulator.feed(b"\x1b[6n")


def test_resizing_reflows_the_screen() -> None:
    with Emulator(6, 2, ignore_replies) as emulator:
        emulator.feed(b"abcdef")
        emulator.resize(3, 2)
        screen = emulator.snapshot()

    assert (screen.columns, screen.rows, text(screen)) == (3, 2, ["abc", "def"])


def test_more_distinct_plain_characters_than_are_kept_are_all_drawn() -> None:
    characters = "".join(chr(0x4E00 + index) for index in range(PLAIN_CELLS_KEPT + 1))
    columns = 200
    rows = -(-len(characters) * 2 // columns)

    screen = snapshot(characters, columns=columns, rows=rows)

    assert "".join(text(screen)).strip() == characters


def rows_text(rows: Rows) -> list[str]:
    return ["".join(cell.grapheme for cell in row).rstrip() for row in rows]


def numbered_lines(start: int, stop: int) -> bytes:
    return b"".join(b"line %d\r\n" % number for number in range(start, stop))


def test_scrolled_off_returns_the_rows_that_scrolled_off_the_top_of_the_screen_oldest_first() -> None:
    with Emulator(10, 3, ignore_replies, scrollback=20) as emulator:
        emulator.feed(numbered_lines(0, 4))

        assert rows_text(emulator.scrolled_off()) == ["line 0", "line 1"]


def test_scrolled_off_returns_each_row_once() -> None:
    with Emulator(10, 3, ignore_replies, scrollback=20) as emulator:
        emulator.feed(numbered_lines(0, 4))
        emulator.scrolled_off()
        emulator.feed(numbered_lines(4, 5))

        assert (rows_text(emulator.scrolled_off()), emulator.scrolled_off()) == (["line 2"], ())


def test_scrolled_off_returns_the_newest_rows_up_to_its_scrollback() -> None:
    with Emulator(10, 3, ignore_replies, scrollback=4) as emulator:
        emulator.feed(numbered_lines(0, 30))

        assert rows_text(emulator.scrolled_off()) == ["line 24", "line 25", "line 26", "line 27"]


def test_scrolled_off_returns_nothing_without_scrollback() -> None:
    with Emulator(10, 3, ignore_replies) as emulator:
        emulator.feed(numbered_lines(0, 10))

        assert emulator.scrolled_off() == ()


def test_scrolled_off_keeps_the_styles_of_the_rows_it_returns() -> None:
    with Emulator(10, 2, ignore_replies, scrollback=4) as emulator:
        emulator.feed(b"\x1b[38;2;1;2;3ma\x1b[0m\r\n\r\n\r\n")

        assert emulator.scrolled_off()[0][0].style.foreground == Color(1, 2, 3)


def test_scrolled_off_returns_the_rows_after_the_scrollback_is_erased() -> None:
    with Emulator(10, 2, ignore_replies, scrollback=20) as emulator:
        emulator.feed(numbered_lines(0, 4))
        emulator.scrolled_off()
        emulator.feed(b"\x1b[3J" + numbered_lines(4, 6))

        assert rows_text(emulator.scrolled_off()) == ["line 3", "line 4"]


def test_drawing_on_the_alternate_screen_scrolls_nothing_off() -> None:
    with Emulator(10, 2, ignore_replies, scrollback=20) as emulator:
        emulator.feed(b"\x1b[?1049h" + numbered_lines(0, 6))

        assert emulator.scrolled_off() == ()


@pytest.mark.parametrize("columns", [5, 20, 300])
def test_scrolled_off_returns_every_row_since_the_last_call_up_to_its_scrollback_however_many_scrolled(
    columns: int,
) -> None:
    # libghostty drops its scrollback a page at a time, and a page's rows depend on the terminal's width.
    scrollback = 3_000
    with Emulator(columns, 2, ignore_replies, scrollback=scrollback) as emulator:
        returned: list[tuple[StyledGrapheme, ...]] = []
        for chunk in range(5):
            emulator.feed(b"%d\r\n" % chunk * 1_500)
            returned.extend(emulator.scrolled_off())
        emulator.feed(b"\r\n".join(b"%d" % number for number in range(10_000)) + b"\r\n")
        newest = emulator.scrolled_off()

    assert (len(returned), len(newest)) == (5 * 1_500 - 1, scrollback)
    # The last line printed is on the screen, with the cursor on the row below it.
    assert rows_text(newest) == [str(number) for number in range(9_999 - scrollback, 9_999)]


@pytest.mark.parametrize("scrollback", [-1, MAX_SCROLLBACK + 1])
def test_an_emulators_scrollback_must_fit_what_libghostty_captures_at_once(scrollback: int) -> None:
    with pytest.raises(ValueError, match="scrollback"):
        Emulator(10, 2, ignore_replies, scrollback=scrollback)
