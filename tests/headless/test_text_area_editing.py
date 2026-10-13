import pytest

from counterweight.headless.text_area_editing import (
    DrawnArea,
    EditableArea,
    drawn,
    key_edit,
    key_edits,
    paste_edit,
    rows,
    settled,
)
from counterweight.keys import Key

WIDTH = 8


def marked(text: str, goal_column: int | None = None) -> EditableArea:
    """`text` with a `|` marking the cursor, as an `EditableArea` without the `|`."""
    before, after = text.split("|")
    return EditableArea(value=before + after, cursor=len(before), goal_column=goal_column)


def marking(area: EditableArea) -> str:
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
        ("|abcd", Key.Left, "|abcd"),
        ("ab|cd", Key.ControlB, "a|bcd"),
        ("ab|cd", Key.Right, "abc|d"),
        ("ab|\ncd", Key.Right, "ab\n|cd"),
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
        ("hello world f|oo", Key.Down, "hello world foo|"),
        ("hello world foo|", Key.ControlP, "hello wor|ld foo"),
        ("he|llo world foo", Key.ControlN, "hello wo|rld foo"),
        ("hel|lo world foo", Key.ControlP, "|hello world foo"),
        ("hello world f|oo", Key.ControlN, "hello world foo|"),
        # Ctrl+T swaps clusters within a line, and never moves a line break
        ("ab|cd", Key.ControlT, "acb|d"),
        ("ab|\ncd", Key.ControlT, "ba|\ncd"),
        ("ab\ncd|", Key.ControlT, "ab\ndc|"),
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


@pytest.mark.parametrize("enter_inserts_newline", [False, True])
def test_every_key_with_an_edit_is_a_named_key(enter_inserts_newline: bool) -> None:
    assert all(isinstance(key, Key) for key in key_edits(WIDTH, enter_inserts_newline))


def press(area: EditableArea, *keys: Key) -> EditableArea:
    for key in keys:
        edit = key_edit(key, WIDTH, enter_inserts_newline=False)
        assert edit is not None
        area = edit(area)
    return area


def test_up_and_down_return_to_the_column_they_started_from_after_a_shorter_row() -> None:
    area = press(marked("abcdef\nab\nabcde|f"), Key.Up)

    assert (marking(area), area.goal_column) == ("abcdef\nab|\nabcdef", 5)
    assert marking(press(area, Key.Up)) == "abcde|f\nab\nabcdef"


def test_a_move_along_the_row_forgets_the_column_up_and_down_aim_for() -> None:
    area = press(marked("abcdef\nab\nabcde|f"), Key.Up, Key.Left, Key.Down)

    assert marking(area) == "abcdef\nab\na|bcdef"


@pytest.mark.parametrize(
    ("pasted", "after"),
    [
        pytest.param("one\r\ntwo\rthree\n", "<one\ntwo\nthree\n|>", id="line-breaks"),
        pytest.param("a\u2028b\x85c\vd", "<a\nb\nc\nd|>", id="unicode-line-breaks"),
        pytest.param("cell\tcell", "<cell cell|>", id="tab"),
        pytest.param("a\x1b[1mb\x7fc\x9bd\x00", "<a[1mbcd|>", id="other-controls"),
    ],
)
def test_paste_inserts_its_text_with_its_line_breaks(pasted: str, after: str) -> None:
    assert marking(paste_edit(pasted)(marked("<|>"))) == after


def test_following_the_same_value_keeps_the_cursor_and_goal_column() -> None:
    area = marked("ab|c", goal_column=4)

    assert area.following("abc") is area


def test_following_a_changed_value_moves_the_cursor_to_its_end() -> None:
    assert marked("a|bc", goal_column=4).following("wxyz") == marked("wxyz|")


@pytest.mark.parametrize(
    ("before", "edited", "value", "after"),
    [
        pytest.param("1|2", "1x|2", "1x2", "1x|2", id="kept"),
        pytest.param("a|b", "ax|b", "AXB", "AX|B", id="transformed"),
        pytest.param("1|2", "1x|2", "12", "1|2", id="rejected"),
        pytest.param("ab|c", "abx|c", "abx", "abx|", id="truncated"),
        pytest.param("ab|c", "a|bc", "abc", "a|bc", id="moved"),
        pytest.param("ab|c", "abx|c", "z", "z|", id="replaced"),
        pytest.param("a|b", "ax|b", "aé", "aé|", id="inside-a-cluster"),
    ],
)
def test_settled_keeps_the_edits_cursor_unless_the_value_was_left_as_before(
    before: str, edited: str, value: str, after: str
) -> None:
    assert marking(settled(marked(before), marked(edited), value)) == after


def test_settled_keeps_the_goal_column_of_the_edit_it_keeps() -> None:
    assert settled(marked("ab|c"), marked("a|bc", goal_column=3), "abc").goal_column == 3


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
    ],
)
def test_drawn_splits_the_rows_around_the_cursor(value: str, cursor: int, width: int, expected: DrawnArea) -> None:
    assert drawn(value, cursor, width) == expected
