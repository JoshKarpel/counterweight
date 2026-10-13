import pytest

from counterweight.graphemes import graphemes
from counterweight.headless.text_editing import KEY_EDITS, EditableText, key_edit, paste_edit, settled
from counterweight.keys import Key


def marked(text: str) -> EditableText:
    """`text` with a `|` marking the cursor, as an `EditableText` without the `|`."""
    before, after = text.split("|")
    return EditableText(value=before + after, cursor=len(graphemes(before)))


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
    ],
)
def test_key_edits_value_and_cursor(before: str, key: str, after: str) -> None:
    edit = key_edit(key)

    assert edit is not None
    assert edit(marked(before)) == marked(after)


@pytest.mark.parametrize("key", [Key.Enter, Key.Tab, Key.BackTab, Key.Up, Key.Down, Key.Escape, Key.F1, Key.ControlC])
def test_key_that_is_not_text_and_has_no_edit_has_none(key: Key) -> None:
    assert key_edit(key) is None


def test_every_key_with_an_edit_is_a_named_key() -> None:
    assert all(isinstance(key, Key) for key in KEY_EDITS)


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


@pytest.mark.parametrize(
    ("value", "cursor", "clamped"),
    [
        ("abc", 2, 2),
        ("abc", 7, 3),
        ("abc", -1, 0),
        ("👩‍💻é", 5, 2),
    ],
)
def test_at_clamps_the_cursor_to_the_value(value: str, cursor: int, clamped: int) -> None:
    assert EditableText.at(value, cursor) == EditableText(value=value, cursor=clamped)


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
    ],
)
def test_settled_keeps_the_edits_cursor_unless_the_value_was_left_as_before(
    before: str, edited: str, value: str, after: str
) -> None:
    assert settled(marked(before), marked(edited), value) == marked(after)
