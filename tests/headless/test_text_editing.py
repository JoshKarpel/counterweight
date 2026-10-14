import pytest

from counterweight.headless.text_editing import KEY_EDITS
from counterweight.headless.text_editing import EditableText
from counterweight.headless.text_editing import Target
from counterweight.headless.text_editing import cell_offset
from counterweight.headless.text_editing import delete_to
from counterweight.headless.text_editing import is_text
from counterweight.headless.text_editing import key_edit
from counterweight.headless.text_editing import move_to
from counterweight.headless.text_editing import move_to_column
from counterweight.headless.text_editing import paste_edit
from counterweight.headless.text_editing import settled
from counterweight.headless.text_editing import word_end
from counterweight.headless.text_editing import word_start
from counterweight.keys import Key


def marked(text: str, goal_column: int | None = None) -> EditableText:
    """`text` with a `|` marking the cursor, as an `EditableText` without the `|`."""
    before, after = text.split("|")
    return EditableText(value=before + after, cursor=len(before), goal_column=goal_column)


@pytest.mark.parametrize(
    ("before", "key", "after"),
    [
        ("ab|cd", "x", "abx|cd"),
        ("|", "x", "x|"),
        ("ab|", Key.Space, "ab |"),
        ("a|b", "👩‍💻", "a👩‍💻|b"),
        ("ab|cd", Key.Left, "a|bcd"),
        ("|abcd", Key.Left, "|abcd"),
        ("ab|cd", Key.ControlB, "a|bcd"),
        ("ab|cd", Key.Right, "abc|d"),
        ("abcd|", Key.Right, "abcd|"),
        ("ab|cd", Key.ControlF, "abc|d"),
        ("ab|cd", Key.Home, "|abcd"),
        ("ab|cd", Key.ControlA, "|abcd"),
        ("ab|cd", Key.End, "abcd|"),
        ("ab|cd", Key.ControlE, "abcd|"),
        ("ab|cd", Key.ControlHome, "|abcd"),
        ("ab|cd", Key.ControlEnd, "abcd|"),
        ("ab|cd", Key.ControlT, "acb|d"),
        ("abcd|", Key.ControlT, "abdc|"),
        ("|abcd", Key.ControlT, "|abcd"),
        ("a|", Key.ControlT, "a|"),
        ("é|👩‍💻x", Key.ControlT, "👩‍💻é|x"),
        ("́|x", Key.ControlT, "x́|"),
        ("ab|cd", Key.Backspace, "a|cd"),
        ("|abcd", Key.Backspace, "|abcd"),
        ("ab|cd", Key.Delete, "ab|d"),
        ("abcd|", Key.Delete, "abcd|"),
        ("ab|cd", Key.ControlD, "ab|d"),
        ("ab|cd", Key.ControlU, "|cd"),
        ("ab|cd", Key.ControlK, "ab|"),
        # a cluster is one step, however many code points it has
        ("é|x", Key.Left, "|éx"),
        ("👩‍💻|x", Key.Backspace, "|x"),
        ("x|🇺🇸", Key.Delete, "x|"),
        # words are runs of letters and digits
        ("one two|", Key.ControlLeft, "one |two"),
        ("one tw|o", Key.ControlLeft, "one |two"),
        ("one |two", Key.ControlLeft, "|one two"),
        ("one, -- |two", Key.ControlLeft, "|one, -- two"),
        ("|one two", Key.ControlLeft, "|one two"),
        (" |one", Key.ControlLeft, "| one"),
        ("|one two", Key.ControlRight, "one| two"),
        ("o|ne two", Key.ControlRight, "one| two"),
        ("one| -- two", Key.ControlRight, "one -- two|"),
        ("one two|", Key.ControlRight, "one two|"),
        ("café x|", Key.ControlLeft, "café |x"),
        ("|one two", Key.ControlDelete, "| two"),
        ("one| -- two", Key.ControlDelete, "one|"),
        # Ctrl+W deletes back to whitespace, punctuation included
        ("cd ../src|", Key.ControlW, "cd |"),
        ("cd ../src  |", Key.ControlW, "cd |"),
        ("cd ../s|rc", Key.ControlW, "cd |rc"),
        ("|cd", Key.ControlW, "|cd"),
        (" |cd", Key.ControlW, "|cd"),
        # Readline's Alt bindings, with Alt+Backspace deleting back to the start of a word, as Ctrl+Left moves
        ("one two|", "alt+b", "one |two"),
        ("one, -- |two", "alt+b", "|one, -- two"),
        ("|one two", "alt+f", "one| two"),
        ("one| -- two", "alt+f", "one -- two|"),
        ("|one two", "alt+d", "| two"),
        ("one| -- two", "alt+d", "one|"),
        ("cd ../src|", Key.AltBackspace, "cd ../|"),
        ("one, -- |two", Key.AltBackspace, "|two"),
        ("one tw|o", Key.AltBackspace, "one |o"),
        ("one two|", Key.AltLeft, "one |two"),
        ("|one two", Key.AltRight, "one| two"),
        ("|one two", Key.AltDelete, "| two"),
    ],
)
def test_key_edits_value_and_cursor(before: str, key: str, after: str) -> None:
    edit = key_edit(key)

    assert edit is not None
    assert edit(marked(before)) == marked(after)


@pytest.mark.parametrize(
    "key",
    [
        Key.Enter,
        Key.Tab,
        Key.BackTab,
        Key.Up,
        Key.Down,
        Key.Escape,
        Key.F1,
        Key.ControlC,
        Key.AltEnter,
        Key.AltSpace,
        Key.ControlAltA,
        "alt+x",
        "alt+é",
    ],
)
def test_key_that_is_not_text_and_has_no_edit_has_none(key: str) -> None:
    assert key_edit(key) is None


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("a", True),
        (Key.Space, True),
        ("é", True),
        ("e\u0301", True),
        ("👩‍💻", True),
        (Key.Enter, False),
        (Key.F1, False),
        ("alt+b", False),
        ("alt+é", False),
        (Key.ControlAltA, False),
    ],
)
def test_text_is_one_grapheme_cluster_and_a_key_name_is_not(key: str, expected: bool) -> None:
    assert is_text(key) is expected


def test_every_key_with_an_edit_is_not_text() -> None:
    assert not any(is_text(key) for key in KEY_EDITS)


@pytest.mark.parametrize(
    ("pasted", "after"),
    [
        pytest.param("one\ntwo\n", "<one two |>", id="line-breaks"),
        pytest.param("a\u2028b\x85c", "<a b c|>", id="unicode-line-breaks"),
        pytest.param("cell\tcell", "<cell cell|>", id="tab"),
        pytest.param("a\x1b[1mb\x7fc\x9bd\x00", "<a[1mbcd|>", id="other-controls"),
    ],
)
def test_paste_inserts_its_text_on_one_line(pasted: str, after: str) -> None:
    assert paste_edit(pasted)(marked("<|>")) == marked(after)


@pytest.mark.parametrize(
    ("text", "value", "following"),
    [
        pytest.param("ab|c", "abc", "ab|c", id="unchanged"),
        pytest.param("ab|c", "a", "a|", id="shrunk"),
        pytest.param("a|bc", "wxyz", "wxyz|", id="grown"),
        pytest.param("a|bc", "👩‍💻é", "👩‍💻é|", id="clusters"),
    ],
)
def test_following_moves_the_cursor_to_the_end_of_a_changed_value(text: str, value: str, following: str) -> None:
    assert marked(text).following(value) == marked(following)


def test_following_the_same_value_keeps_the_cursor_and_goal_column() -> None:
    text = marked("ab|c", goal_column=4)

    assert text.following("abc") is text


def test_following_a_changed_value_forgets_the_goal_column() -> None:
    assert marked("a|bc", goal_column=4).following("wxyz") == marked("wxyz|")


def test_insert_that_joins_the_cluster_after_it_leaves_the_cursor_after_the_joined_cluster() -> None:
    edit = key_edit("e")

    assert edit is not None
    assert edit(marked("|\u0301x")) == marked("e\u0301|x")


@pytest.mark.parametrize(
    ("before", "edited", "value", "after"),
    [
        pytest.param("1|2", "1x|2", "1x2", "1x|2", id="kept"),
        pytest.param("a|b", "ax|b", "AXB", "AX|B", id="transformed"),
        pytest.param("1|2", "1x|2", "12", "1|2", id="rejected"),
        pytest.param("ab|c", "abx|c", "abx", "abx|", id="truncated"),
        pytest.param("ab|c", "a|bc", "abc", "a|bc", id="moved"),
        pytest.param("ab|c", "abx|c", "z", "z|", id="replaced"),
        pytest.param("a|b", "ax|b", "aé", "aé|", id="inside-a-cluster"),
    ],
)
def test_settled_keeps_the_edits_cursor_unless_the_value_was_left_as_before(
    before: str, edited: str, value: str, after: str
) -> None:
    assert settled(marked(before), marked(edited), value) == marked(after)


def test_settled_keeps_the_goal_column_of_the_edit_it_keeps() -> None:
    assert settled(marked("ab|c"), marked("a|bc", goal_column=3), "abc").goal_column == 3


@pytest.mark.parametrize(
    ("line", "column", "expected"),
    [
        ("abc", 1, 1),
        ("a日b", 1, 1),
        ("a日b", 2, 1),
        ("a日b", 3, 2),
        ("a日b", 4, 3),
        ("abc", 9, 3),
        ("abc", -1, 0),
        ("", 4, 0),
    ],
)
def test_cell_offset_is_the_start_of_the_cluster_drawn_across_the_cell_or_the_end_of_the_line(
    line: str, column: int, expected: int
) -> None:
    assert cell_offset(line, column) == expected


def test_moving_to_a_column_puts_the_cursor_on_the_cluster_there_and_forgets_the_goal_column() -> None:
    moved = move_to_column(2)(EditableText(value="hello", cursor=5, goal_column=3))

    assert moved == EditableText(value="hello", cursor=2, goal_column=None)


# `KEY_EDITS` builds its edits when the module is imported, so these build theirs in the test, to pin what they do.
@pytest.mark.parametrize(
    ("target", "before", "after"),
    [
        (word_start, "one tw|o", "one |two"),
        (word_end, "o|ne two", "one| two"),
    ],
)
def test_moving_to_a_target_moves_the_cursor_there_and_forgets_the_goal_column(
    target: Target, before: str, after: str
) -> None:
    assert move_to(target)(marked(before, goal_column=3)) == marked(after)


@pytest.mark.parametrize(
    ("target", "before", "after"),
    [
        (word_start, "one tw|o", "one |o"),
        (word_end, "o|ne two", "o| two"),
    ],
)
def test_deleting_to_a_target_deletes_between_it_and_the_cursor_and_forgets_the_goal_column(
    target: Target, before: str, after: str
) -> None:
    assert delete_to(target)(marked(before, goal_column=3)) == marked(after)
