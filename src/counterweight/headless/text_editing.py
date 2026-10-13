"""
Editing one line of text at a cursor, the pure core of [`use_text_input`][counterweight.headless.use_text_input]:
which edit each key press or paste makes, and what each edit does to a value and a cursor.
The cursor counts grapheme clusters, so it never lands inside one.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from counterweight.graphemes import graphemes
from counterweight.keys import Key


@dataclass(frozen=True, slots=True)
class EditableText:
    """A value, and a cursor in it: how many of its grapheme clusters come before the cursor."""

    value: str
    cursor: int

    @classmethod
    def at(cls, value: str, cursor: int) -> EditableText:
        """`value` with `cursor` clamped to it, for a cursor kept while the value changed underneath it."""
        return cls(value=value, cursor=max(0, min(cursor, len(graphemes(value)))))

    def following(self, value: str) -> EditableText:
        """
        This text if its value is still `value`,
        or else `value` with the cursor at its end, since something other than an edit changed it.
        """
        if value == self.value:
            return self
        return EditableText(value=value, cursor=len(graphemes(value)))


# One editing action, such as moving the cursor a word left or deleting the cluster before it.
type Edit = Callable[[EditableText], EditableText]

# Where in a value's grapheme clusters an edit reaches, from the cursor.
type Target = Callable[[Sequence[str], int], int]


def previous_cluster(clusters: Sequence[str], cursor: int) -> int:
    """The position one cluster before the cursor."""
    return max(cursor - 1, 0)


def next_cluster(clusters: Sequence[str], cursor: int) -> int:
    """The position one cluster after the cursor."""
    return min(cursor + 1, len(clusters))


def line_start(clusters: Sequence[str], cursor: int) -> int:
    """The position before the first cluster."""
    return 0


def line_end(clusters: Sequence[str], cursor: int) -> int:
    """The position after the last cluster."""
    return len(clusters)


def is_word(cluster: str) -> bool:
    """Whether `cluster` is part of a word: a letter or digit, as Readline's word commands count them."""
    return cluster[0].isalnum()


def is_blank(cluster: str) -> bool:
    """Whether `cluster` is whitespace, which separates the words Readline's `unix-word-rubout` deletes."""
    return cluster.isspace()


def word_start(clusters: Sequence[str], cursor: int) -> int:
    """The start of the word the cursor is in or after, past any non-word clusters before the cursor."""
    position = cursor
    while position > 0 and not is_word(clusters[position - 1]):
        position -= 1
    while position > 0 and is_word(clusters[position - 1]):
        position -= 1
    return position


def word_end(clusters: Sequence[str], cursor: int) -> int:
    """The end of the word the cursor is in or before, past any non-word clusters after the cursor."""
    position = cursor
    while position < len(clusters) and not is_word(clusters[position]):
        position += 1
    while position < len(clusters) and is_word(clusters[position]):
        position += 1
    return position


def blank_separated_word_start(clusters: Sequence[str], cursor: int) -> int:
    """The start of the run of non-whitespace the cursor is in or after, past any whitespace before the cursor."""
    position = cursor
    while position > 0 and is_blank(clusters[position - 1]):
        position -= 1
    while position > 0 and not is_blank(clusters[position - 1]):
        position -= 1
    return position


def move_to(target: Target) -> Edit:
    """An edit that moves the cursor to `target`, leaving the value alone."""

    def edit(text: EditableText) -> EditableText:
        return EditableText(value=text.value, cursor=target(graphemes(text.value), text.cursor))

    return edit


def delete_to(target: Target) -> Edit:
    """An edit that deletes the clusters between the cursor and `target`, leaving the cursor where they started."""

    def edit(text: EditableText) -> EditableText:
        clusters = graphemes(text.value)
        start, end = sorted((text.cursor, target(clusters, text.cursor)))
        return EditableText.at(value="".join(clusters[:start] + clusters[end:]), cursor=start)

    return edit


def insert(inserted: str) -> Edit:
    """An edit that inserts `inserted` at the cursor, and moves the cursor to the end of it."""

    def edit(text: EditableText) -> EditableText:
        clusters = graphemes(text.value)
        before = "".join(clusters[: text.cursor]) + inserted
        return EditableText.at(value=before + "".join(clusters[text.cursor :]), cursor=len(graphemes(before)))

    return edit


def settled(before: EditableText, edited: EditableText, value: str) -> EditableText:
    """
    The text after an edit from `before` to `edited`, once whoever owns the value has settled it at `value`:
    with the edit's cursor if they kept its change to the value, even transformed, or it didn't change the value,
    and with the cursor from `before` if they discarded its change, so an edit they reject doesn't move the cursor.
    """
    is_rejected = edited.value != before.value and value == before.value
    return EditableText.at(value, before.cursor if is_rejected else edited.cursor)


# The edit each key makes, following Readline's default (Emacs) bindings where it has one.
KEY_EDITS: Mapping[str, Edit] = {
    Key.Left: move_to(previous_cluster),
    Key.ControlB: move_to(previous_cluster),
    Key.Right: move_to(next_cluster),
    Key.ControlF: move_to(next_cluster),
    Key.Home: move_to(line_start),
    Key.ControlA: move_to(line_start),
    Key.End: move_to(line_end),
    Key.ControlE: move_to(line_end),
    Key.ControlLeft: move_to(word_start),
    Key.ControlRight: move_to(word_end),
    Key.Backspace: delete_to(previous_cluster),
    Key.Delete: delete_to(next_cluster),
    Key.ControlD: delete_to(next_cluster),
    Key.ControlW: delete_to(blank_separated_word_start),
    Key.ControlDelete: delete_to(word_end),
    Key.ControlU: delete_to(line_start),
    Key.ControlK: delete_to(line_end),
}

# The `KeyPressed.key` of every key that isn't text, which is every `Key` but Space.
NAMED_KEYS = frozenset(key.value for key in Key) - {Key.Space.value}


def key_edit(key: str) -> Edit | None:
    """The edit a press of `key` makes: inserting it if it's text, or a `KEY_EDITS` entry, or `None` for neither."""
    if (edit := KEY_EDITS.get(key)) is not None:
        return edit
    if key in NAMED_KEYS:
        return None
    return insert(key)


# What each control character in a paste becomes on one line: a line break or a tab separates words, so it's a space,
# and any other is dropped, as it isn't text and typing can't insert it.
PASTE_CONTROLS: Mapping[int, str | None] = {
    **dict.fromkeys([*range(0x20), *range(0x7F, 0xA0)]),
    **dict.fromkeys(map(ord, "\n\v\f\r\x1c\x1d\x1e\x85\u2028\u2029\t"), " "),
}


def paste_edit(text: str) -> Edit:
    """
    The edit pasting `text` makes: inserting it on one line, with each line break and tab as a space,
    and without any other control characters.
    """
    return insert(text.translate(PASTE_CONTROLS))
