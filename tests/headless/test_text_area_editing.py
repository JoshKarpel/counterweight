from collections.abc import Callable

import pytest

from counterweight.headless.text_area_editing import (
    DrawnArea,
    drawn,
    key_edit,
    key_edits,
    move_down,
    move_to_cell,
    move_up,
    move_vertically,
    or_further,
    paste_edit,
    previous_row,
    row_end,
    rows,
)
from counterweight.headless.text_editing import Edit, EditableText, is_text, value_start, word_end
from counterweight.keys import Key

WIDTH = 8


def marked(text: str, goal_column: int | None = None) -> EditableText:
    """`text` with a `|` marking the cursor, as an `EditableText` without the `|`."""
    before, after = text.split("|")
    return EditableText(value=before + after, cursor=len(before), goal_column=goal_column)


def marking(area: EditableText) -> str:
    """The value with a `|` marking the cursor."""
    return area.value[: area.cursor] + "|" + area.value[area.cursor :]


@pytest.mark.parametrize(
    ("value", "width", "expected"),
    [
        pytest.param("hello world foo", 8, ["hello ", "world ", "foo"], id="breaks-after-whitespace"),
        pytest.param("abc", 4, ["abc"], id="fits"),
        pytest.param("abcd", 4, ["abcd", ""], id="keeps-a-cell-after-the-end-of-a-line"),
        pytest.param("aaaa\nbb", 4, ["aaaa", "", "bb"], id="keeps-a-cell-before-a-line-break"),
        pytest.param("abcdefgh", 3, ["abc", "def", "gh"], id="breaks-a-word-wider-than-a-row"),
        pytest.param("a    b", 3, ["a  ", "  ", "b"], id="whitespace-takes-cells"),
        pytest.param(" ab日", 3, [" ", "ab", "日"], id="breaks-again-when-a-carried-word-overflows"),
        pytest.param("日本語", 4, ["日本", "語"], id="wide-clusters"),
        pytest.param("éx", 1, ["é", "x", ""], id="clusters-stay-whole"),
        pytest.param("a\x07b", 4, ["a\x07b"], id="control-characters-take-the-cell-their-symbol-does"),
        pytest.param("a\n\nb", 5, ["a", "", "b"], id="empty-line"),
        pytest.param("", 5, [""], id="empty"),
        pytest.param("ab", 0, ["a", "b", ""], id="no-width"),
    ],
)
def test_rows_wrap_so_every_cursor_position_has_a_cell(value: str, width: int, expected: list[str]) -> None:
    assert [value[row.start : row.end] for row in rows(value, width)] == expected


@pytest.mark.parametrize(
    ("before", "key", "after"),
    [
        ("ab|cd", "x", "abx|cd"),
        ("|", "x", "x|"),
        ("ab|", Key.Space, "ab |"),
        ("|́x", "e", "é|x"),
        ("ab|cd", Key.ControlJ, "ab\n|cd"),
        ("ab|cd", Key.Left, "a|bcd"),
        ("ab\n|cd", Key.Left, "ab|\ncd"),
        ("\na|b", Key.Left, "\n|ab"),
        ("|abcd", Key.Left, "|abcd"),
        ("ab|cd", Key.ControlB, "a|bcd"),
        ("ab|cd", Key.Right, "abc|d"),
        ("ab|\ncd", Key.Right, "ab\n|cd"),
        ("a|b\ncd", Key.Right, "ab|\ncd"),
        ("abcd|", Key.Right, "abcd|"),
        ("ab|cd", Key.ControlF, "abc|d"),
        # a cluster is one step, however many code points it has
        ("é|x", Key.Left, "|éx"),
        ("a|👩‍💻b", Key.Right, "a👩‍💻|b"),
        # Up and Down move between rows, soft or not, keeping the column
        ("hello world foo|", Key.Up, "hello wor|ld foo"),
        ("he|llo world foo", Key.Down, "hello wo|rld foo"),
        ("abc\nde|f", Key.Up, "ab|c\ndef"),
        ("a\nbcd|", Key.Up, "a|\nbcd"),
        ("ab cd efghijk|", Key.Up, "ab cd| efghijk"),
        ("日本\na|bc", Key.Up, "|日本\nabc"),
        ("日本\nab|c", Key.Up, "日|本\nabc"),
        ("hel|lo world foo", Key.Up, "|hello world foo"),
        ("a\n\nb|", Key.Up, "a\n|\nb"),
        ("a|\n\nb", Key.Down, "a\n|\nb"),
        ("hello world f|oo", Key.Down, "hello world foo|"),
        ("hello world foo|", Key.ControlP, "hello wor|ld foo"),
        ("he|llo world foo", Key.ControlN, "hello wo|rld foo"),
        ("hel|lo world foo", Key.ControlP, "|hello world foo"),
        ("hello world f|oo", Key.ControlN, "hello world foo|"),
        # Ctrl+T swaps clusters within a line, and never moves a line break
        ("ab|cd", Key.ControlT, "acb|d"),
        ("ab|\ncd", Key.ControlT, "ba|\ncd"),
        ("ab\ncd|", Key.ControlT, "ab\ndc|"),
        ("ab\ncd|\nef", Key.ControlT, "ab\ndc|\nef"),
        ("ab\n|cd", Key.ControlT, "ab\n|cd"),
        ("a|\ncd", Key.ControlT, "a|\ncd"),
        ("ab\n|\ncd", Key.ControlT, "ab\n|\ncd"),
        ("|", Key.ControlT, "|"),
        ("é|👩‍💻x", Key.ControlT, "👩‍💻é|x"),
        ("́|x", Key.ControlT, "x́|"),
        # Home and End, and the deletes to them, reach the ends of the cursor's row
        ("hello wor|ld foo", Key.Home, "hello |world foo"),
        ("hello wor|ld foo", Key.ControlA, "hello |world foo"),
        ("ab\ncd|", Key.Home, "ab\n|cd"),
        ("hello wor|ld foo", Key.End, "hello world| foo"),
        ("hello wor|ld foo", Key.ControlE, "hello world| foo"),
        ("hello world f|oo", Key.End, "hello world foo|"),
        # Ctrl+A and Ctrl+E from the end of the row they reach go on to that end of the value, and Home and End don't
        ("ab\n|cd", Key.ControlA, "|ab\ncd"),
        ("ab\n|cd", Key.Home, "ab\n|cd"),
        ("hello world| foo", Key.ControlE, "hello world foo|"),
        ("ab|\ncd", Key.ControlE, "ab\ncd|"),
        ("ab|\ncd", Key.End, "ab|\ncd"),
        # Ctrl+Home and Ctrl+End reach the ends of the value from anywhere
        ("ab\nc|d", Key.ControlHome, "|ab\ncd"),
        ("a|b\ncd", Key.ControlEnd, "ab\ncd|"),
        ("hello wor|ld foo", Key.ControlU, "hello |ld foo"),
        ("hello wo|rld foo", Key.ControlK, "hello wo|foo"),
        ("ab|cd\nef", Key.ControlK, "ab|\nef"),
        # words are runs of letters and digits, and a line break separates them
        ("one two|", Key.ControlLeft, "one |two"),
        ("one\n|two", Key.ControlLeft, "|one\ntwo"),
        ("café x|", Key.ControlLeft, "café |x"),
        ("one|\ntwo", Key.ControlRight, "one\ntwo|"),
        ("|one two", Key.ControlDelete, "| two"),
        ("cd ../src|", Key.ControlW, "cd |"),
        ("one\n|two", Key.ControlW, "|two"),
        ("|cd", Key.ControlW, "|cd"),
        ("one\n|two", "alt+b", "|one\ntwo"),
        ("one|\ntwo", "alt+f", "one\ntwo|"),
        ("one|\ntwo", "alt+d", "one|"),
        ("one\n|two", Key.AltBackspace, "|two"),
        # deleting a line break joins its lines
        ("ab|cd", Key.Backspace, "a|cd"),
        ("ab\n|cd", Key.Backspace, "ab|cd"),
        ("|abcd", Key.Backspace, "|abcd"),
        ("ab|\ncd", Key.Delete, "ab|cd"),
        ("abcd|", Key.Delete, "abcd|"),
        ("ab|cd", Key.ControlD, "ab|d"),
        ("x|🇺🇸", Key.Delete, "x|"),
        ("🇺|x🇸", Key.Delete, "🇺🇸|"),
    ],
)
def test_key_edits_value_and_cursor(before: str, key: str, after: str) -> None:
    edit = key_edit(key, WIDTH, enter_inserts_newline=False)

    assert edit is not None
    assert marking(edit(marked(before))) == after


@pytest.mark.parametrize("key", [Key.Enter, Key.Tab, Key.BackTab, Key.Escape, Key.F1, Key.ControlC])
def test_key_that_is_not_text_and_has_no_edit_has_none(key: Key) -> None:
    assert key_edit(key, WIDTH, enter_inserts_newline=False) is None


def test_enter_inserts_a_line_break_if_asked_to() -> None:
    edit = key_edit(Key.Enter, WIDTH, enter_inserts_newline=True)

    assert edit is not None
    assert marking(edit(marked("ab|cd"))) == "ab\n|cd"


@pytest.mark.parametrize("key", [Key.ControlJ, Key.AltEnter])
@pytest.mark.parametrize("enter_inserts_newline", [False, True])
def test_ctrl_j_and_alt_enter_insert_a_line_break_whatever_enter_does(key: Key, enter_inserts_newline: bool) -> None:
    edit = key_edit(key, WIDTH, enter_inserts_newline=enter_inserts_newline)

    assert edit is not None
    assert marking(edit(marked("ab|cd"))) == "ab\n|cd"


@pytest.mark.parametrize("enter_inserts_newline", [False, True])
def test_every_key_with_an_edit_is_not_text(enter_inserts_newline: bool) -> None:
    assert not any(is_text(key) for key in key_edits(WIDTH, enter_inserts_newline))


def press(area: EditableText, *keys: Key) -> EditableText:
    for key in keys:
        edit = key_edit(key, WIDTH, enter_inserts_newline=False)
        assert edit is not None
        area = edit(area)
    return area


def test_up_and_down_return_to_the_column_they_started_from_after_a_shorter_row() -> None:
    area = press(marked("abcdef\nab\nabcde|f"), Key.Up)

    assert (marking(area), area.goal_column) == ("abcdef\nab|\nabcdef", 5)
    assert marking(press(area, Key.Up)) == "abcde|f\nab\nabcdef"


def test_up_onto_the_first_row_keeps_the_column_it_aims_for() -> None:
    area = press(marked("\nab|"), Key.Up)

    assert (marking(area), area.goal_column) == ("|\nab", 2)


def test_a_move_along_the_row_forgets_the_column_up_and_down_aim_for() -> None:
    area = press(marked("abcdef\nab\nabcde|f"), Key.Up, Key.Left, Key.Down)

    assert marking(area) == "abcdef\nab\na|bcdef"


@pytest.mark.parametrize(
    ("before", "move", "count", "after"),
    [
        pytest.param("a\nbc|d\ne\nfgh\ni", move_down, 2, "a\nbcd\ne\nfg|h\ni", id="down-keeps-the-column"),
        pytest.param("a\nb|cd\nef", move_down, 5, "a\nbcd\ne|f", id="down-stops-at-the-last-row"),
        pytest.param("a\nbcd\ne|f", move_down, 5, "a\nbcd\nef|", id="down-from-the-last-row-to-the-end"),
        pytest.param("a\nbcd\ne\nfg|h", move_up, 2, "a\nbc|d\ne\nfgh", id="up-keeps-the-column"),
        pytest.param("abc\nd\nef|g", move_up, 5, "ab|c\nd\nefg", id="up-stops-at-the-first-row"),
        pytest.param("a|bc\nd", move_up, 5, "|abc\nd", id="up-from-the-first-row-to-the-start"),
        pytest.param("hello world foo|", move_up, 2, "hel|lo world foo", id="soft-rows"),
    ],
)
def test_moving_several_rows_stops_at_the_furthest_row(
    before: str, move: Callable[[int, int], Edit], count: int, after: str
) -> None:
    assert marking(move(WIDTH, count)(marked(before))) == after


@pytest.mark.parametrize(
    ("cursor", "expected"),
    [
        pytest.param(2, 0, id="target"),
        pytest.param(0, 3, id="further-from-the-target"),
    ],
)
def test_or_further_reaches_the_target_or_from_it_the_further_target(cursor: int, expected: int) -> None:
    assert or_further(value_start, word_end)("one two", cursor) == expected


def test_moving_vertically_past_the_first_row_moves_to_the_edge_reached_from_the_cursor() -> None:
    move = move_vertically(WIDTH, previous_row, row_end(WIDTH))

    assert move(marked("a|bc\nd")) == marked("abc|\nd")


@pytest.mark.parametrize(
    ("pasted", "after"),
    [
        pytest.param("one\r\ntwo\rthree\n", "<one\ntwo\nthree\n|>", id="line-breaks"),
        pytest.param("a\u2028b\x85c\vd", "<a\nb\nc\nd|>", id="unicode-line-breaks"),
        pytest.param("a\x1b[1mb\x7fc\x9bd\x00", "<a[1mbcd|>", id="other-controls"),
    ],
)
def test_paste_inserts_its_text_with_its_line_breaks(pasted: str, after: str) -> None:
    assert marking(paste_edit(pasted, 4)(marked("<|>"))) == after


@pytest.mark.parametrize(
    ("before", "pasted", "tab_size", "after"),
    [
        pytest.param("|", "\tif x:\n\t\ty", 4, "    if x:\n        y|", id="indentation"),
        pytest.param("|", "a\tbc\tdef\tg", 4, "a   bc  def g|", id="alignment"),
        pytest.param("ab\ncd|", "\tx", 4, "ab\ncd  x|", id="counts-the-line-before-the-cursor"),
        pytest.param("ab|\ncd", "\tx", 4, "ab  x|\ncd", id="counts-only-the-cursors-line"),
        pytest.param("a\t|", "\tx", 4, "a\t    x|", id="counts-a-tab-before-the-cursor-as-expanded"),
        pytest.param("|", "\tx\r\n\ty", 2, "  x\n  y|", id="line-breaks-reset-the-column"),
        pytest.param("|", "a\tb", 8, "a       b|", id="tab-size"),
    ],
)
def test_paste_expands_each_tab_to_the_next_tab_stop(before: str, pasted: str, tab_size: int, after: str) -> None:
    assert marking(paste_edit(pasted, tab_size)(marked(before))) == after


@pytest.mark.parametrize(
    ("value", "cursor", "width", "expected"),
    [
        pytest.param("abc", 1, 5, DrawnArea("a", "b", "c"), id="middle"),
        pytest.param("ab", 2, 5, DrawnArea("ab", " ", ""), id="end"),
        pytest.param("", 0, 5, DrawnArea("", " ", ""), id="empty"),
        pytest.param("a👩‍💻b", 1, 9, DrawnArea("a", "👩‍💻", "b"), id="cluster"),
        pytest.param("hello world foo", 15, 8, DrawnArea("hello \nworld \nfoo", " ", ""), id="after-soft-rows"),
        pytest.param("hello world foo", 6, 8, DrawnArea("hello \n", "w", "orld \nfoo"), id="soft-break"),
        pytest.param("ab\ncd", 2, 5, DrawnArea("ab", " ", "\ncd"), id="end-of-a-line"),
        pytest.param("a\n\nb", 2, 5, DrawnArea("a\n", " ", "\nb"), id="empty-line"),
        pytest.param("abcd", 4, 4, DrawnArea("abcd\n", " ", ""), id="after-a-full-row"),
        pytest.param("a\nb\nc", 0, 5, DrawnArea("", "a", "\nb\nc"), id="rows-after-the-cursor"),
    ],
)
def test_drawn_splits_the_rows_around_the_cursor(value: str, cursor: int, width: int, expected: DrawnArea) -> None:
    assert drawn(value, cursor, width) == expected


@pytest.mark.parametrize(
    ("row", "column", "expected"),
    [
        (1, 2, 8),
        (0, 7, 5),
        (2, 9, 15),
        (5, 0, 12),
        (-3, 1, 1),
    ],
)
def test_moving_to_a_cell_puts_the_cursor_on_the_cluster_there_or_the_nearest_position_in_the_nearest_row(
    row: int, column: int, expected: int
) -> None:
    moved = move_to_cell(8, row, column)(EditableText(value="hello world foo", cursor=0, goal_column=4))

    assert moved == EditableText(value="hello world foo", cursor=expected, goal_column=None)
