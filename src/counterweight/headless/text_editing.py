"""
Editing text at a cursor, the pure core of [`use_text_input`][counterweight.headless.use_text_input],
and of [`use_text_area`][counterweight.headless.use_text_area] with the rows `text_area_editing` adds:
which edit each key press or paste makes, and what each edit does to a value and a cursor.

Positions are offsets into the value in code points, always at a grapheme cluster boundary,
so finding the line around one is a `str` search rather than a walk over the whole value,
and each line's clusters are cached, so an edit only measures the line it changes.
A line break is a cluster of its own, so the edits here move and delete across one as across any other character.
"""

from __future__ import annotations

from bisect import bisect_left
from bisect import bisect_right
from collections.abc import Callable
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import replace
from functools import lru_cache
from itertools import accumulate

from counterweight.graphemes import grapheme_width
from counterweight.graphemes import graphemes
from counterweight.graphemes import visible
from counterweight.keys import Key


@dataclass(frozen=True, slots=True)
class EditableText:
    """
    A value, a cursor in it, and the column Up and Down aim for in a text area,
    which a run of them keeps so the cursor returns to it after passing through shorter rows.
    """

    value: str
    cursor: int
    goal_column: int | None

    def following(self, value: str) -> EditableText:
        """
        This text if its value is still `value`,
        or else `value` with the cursor at its end, since something other than an edit changed it.
        """
        if value == self.value:
            return self
        return EditableText(value=value, cursor=len(value), goal_column=None)


# One editing action, such as moving the cursor a word left or deleting the cluster before it.
type Edit = Callable[[EditableText], EditableText]

# Where in a value an edit reaches, from the cursor.
type Target = Callable[[str, int], int]


@dataclass(frozen=True, slots=True)
class LineClusters:
    """Where each grapheme cluster of a line starts, then the line's length, and how many cells each takes."""

    starts: tuple[int, ...]
    widths: tuple[int, ...]


@lru_cache(maxsize=2**12)
def line_clusters(line: str) -> LineClusters:
    """The clusters of `line`, which holds no line break."""
    clusters = graphemes(line)
    return LineClusters(
        starts=tuple(accumulate((len(cluster) for cluster in clusters), initial=0)),
        widths=tuple(grapheme_width(visible(cluster)) for cluster in clusters),
    )


def cell_offset(line: str, column: int) -> int:
    """
    The offset in `line`, which holds no line break, of the cluster drawn across the cell at `column`,
    counting cells from the start of the line, or the end of the line for a column past it.
    """
    clusters = line_clusters(line)
    return clusters.starts[bisect_right(tuple(accumulate(clusters.widths)), column)]


def line_start_at(value: str, offset: int) -> int:
    """The start of the line `offset` is in."""
    return value.rfind("\n", 0, offset) + 1


def line_end_at(value: str, offset: int) -> int:
    """The end of the line `offset` is in: the offset of its line break, or the end of the value."""
    end = value.find("\n", offset)
    return len(value) if end == -1 else end


def previous_cluster(value: str, cursor: int) -> int:
    """The position one cluster before the cursor, where a line break is a cluster of its own."""
    start = line_start_at(value, cursor)
    if cursor == start:
        return max(cursor - 1, 0)
    starts = line_clusters(value[start : line_end_at(value, start)]).starts
    return start + starts[bisect_left(starts, cursor - start) - 1]


def next_cluster(value: str, cursor: int) -> int:
    """The position one cluster after the cursor, where a line break is a cluster of its own."""
    end = line_end_at(value, cursor)
    if cursor == end:
        return min(cursor + 1, len(value))
    start = line_start_at(value, cursor)
    starts = line_clusters(value[start:end]).starts
    return start + starts[bisect_right(starts, cursor - start)]


def at_boundary(value: str, offset: int) -> int:
    """`offset`, or the end of the cluster it's inside of, as when an edit joins the clusters on either side of it."""
    start = line_start_at(value, offset)
    starts = line_clusters(value[start : line_end_at(value, start)]).starts
    return start + starts[bisect_left(starts, offset - start)]


def is_word(cluster: str) -> bool:
    """Whether `cluster` is part of a word: a letter or digit, as Readline's word commands count them."""
    return cluster[0].isalnum()


def is_blank(cluster: str) -> bool:
    """Whether `cluster` is whitespace, which separates the words Readline's `unix-word-rubout` deletes."""
    return cluster.isspace()


def word_start(value: str, cursor: int) -> int:
    """The start of the word the cursor is in or after, past any non-word clusters before the cursor."""
    position = cursor
    while position > 0 and not is_word(value[(before := previous_cluster(value, position)) : position]):
        position = before
    while position > 0 and is_word(value[(before := previous_cluster(value, position)) : position]):
        position = before
    return position


def word_end(value: str, cursor: int) -> int:
    """The end of the word the cursor is in or before, past any non-word clusters after the cursor."""
    position = cursor
    while position < len(value) and not is_word(value[position : (after := next_cluster(value, position))]):
        position = after
    while position < len(value) and is_word(value[position : (after := next_cluster(value, position))]):
        position = after
    return position


def blank_separated_word_start(value: str, cursor: int) -> int:
    """The start of the run of non-whitespace the cursor is in or after, past any whitespace before the cursor."""
    position = cursor
    while position > 0 and is_blank(value[(before := previous_cluster(value, position)) : position]):
        position = before
    while position > 0 and not is_blank(value[(before := previous_cluster(value, position)) : position]):
        position = before
    return position


def value_start(value: str, cursor: int) -> int:
    """The start of the value."""
    return 0


def value_end(value: str, cursor: int) -> int:
    """The end of the value."""
    return len(value)


def move_to(target: Target) -> Edit:
    """An edit that moves the cursor to `target`, leaving the value alone."""

    def edit(text: EditableText) -> EditableText:
        return EditableText(value=text.value, cursor=target(text.value, text.cursor), goal_column=None)

    return edit


def move_to_column(column: int) -> Edit:
    """
    An edit that moves the cursor to the cluster drawn across the cell at `column` of a one-line value,
    or to the end of the value for a column past it, as a press on that cell does.
    """

    def edit(text: EditableText) -> EditableText:
        return EditableText(value=text.value, cursor=cell_offset(text.value, column), goal_column=None)

    return edit


def delete_to(target: Target) -> Edit:
    """An edit that deletes the text between the cursor and `target`, leaving the cursor where it started."""

    def edit(text: EditableText) -> EditableText:
        start, end = sorted((text.cursor, target(text.value, text.cursor)))
        value = text.value[:start] + text.value[end:]
        return EditableText(value=value, cursor=at_boundary(value, start), goal_column=None)

    return edit


def insert(inserted: str) -> Edit:
    """An edit that inserts `inserted` at the cursor, and moves the cursor to the end of it."""

    def edit(text: EditableText) -> EditableText:
        value = text.value[: text.cursor] + inserted + text.value[text.cursor :]
        return EditableText(value=value, cursor=at_boundary(value, text.cursor + len(inserted)), goal_column=None)

    return edit


def transpose(text: EditableText) -> EditableText:
    """
    Swap the cluster before the cursor with the one at it, and move the cursor past both,
    or at the end of a line, swap its last two clusters, as Readline's `transpose-chars` does,
    without moving a line break.
    """
    value = text.value
    end = text.cursor if text.cursor == line_end_at(value, text.cursor) else next_cluster(value, text.cursor)
    middle = previous_cluster(value, end)
    start = previous_cluster(value, middle)
    if middle <= line_start_at(value, text.cursor):
        return text
    swapped = value[:start] + value[middle:end] + value[start:middle] + value[end:]
    return EditableText(value=swapped, cursor=at_boundary(swapped, end), goal_column=None)


def settled(before: EditableText, edited: EditableText, value: str) -> EditableText:
    """
    The text after an edit from `before` to `edited`, once whoever owns the value has settled it at `value`:
    with the edit's cursor if they kept its change to the value, even transformed, or it didn't change the value,
    and with the cursor from `before` if they discarded its change, so an edit they reject doesn't move the cursor.
    """
    kept = before if edited.value != before.value and value == before.value else edited
    return replace(kept, value=value, cursor=at_boundary(value, min(kept.cursor, len(value))))


# The edit each key makes in one line of text, following Readline's default (Emacs) bindings where it has one.
KEY_EDITS: Mapping[str, Edit] = {
    Key.Left: move_to(previous_cluster),
    Key.ControlB: move_to(previous_cluster),
    Key.Right: move_to(next_cluster),
    Key.ControlF: move_to(next_cluster),
    Key.Home: move_to(value_start),
    Key.ControlA: move_to(value_start),
    Key.End: move_to(value_end),
    Key.ControlE: move_to(value_end),
    Key.ControlHome: move_to(value_start),
    Key.ControlEnd: move_to(value_end),
    Key.ControlLeft: move_to(word_start),
    Key.AltLeft: move_to(word_start),
    "alt+b": move_to(word_start),
    Key.ControlRight: move_to(word_end),
    Key.AltRight: move_to(word_end),
    "alt+f": move_to(word_end),
    Key.Backspace: delete_to(previous_cluster),
    Key.Delete: delete_to(next_cluster),
    Key.ControlD: delete_to(next_cluster),
    Key.ControlW: delete_to(blank_separated_word_start),
    Key.AltBackspace: delete_to(word_start),
    Key.ControlDelete: delete_to(word_end),
    Key.AltDelete: delete_to(word_end),
    "alt+d": delete_to(word_end),
    Key.ControlU: delete_to(value_start),
    Key.ControlK: delete_to(value_end),
    Key.ControlT: transpose,
}


def is_text(key: str) -> bool:
    """
    Whether a `KeyPressed.key` is text typed, which is one grapheme cluster,
    rather than the name of a key or of a key pressed with Alt, such as `"enter"` or `"alt+b"`.
    """
    return len(graphemes(key)) == 1


def key_edit_in(edits: Mapping[str, Edit], key: str) -> Edit | None:
    """The edit a press of `key` makes: an `edits` entry, or inserting it if it's text, or `None` for neither."""
    if (edit := edits.get(key)) is not None:
        return edit
    if is_text(key):
        return insert(key)
    return None


def key_edit(key: str) -> Edit | None:
    """The edit a press of `key` makes in one line of text: a `KEY_EDITS` entry, or inserting it if it's text."""
    return key_edit_in(KEY_EDITS, key)


# Each way of writing a line break, which a paste turns into a space on one line, or `\n` in a text area.
LINE_BREAKS = "\n\v\f\r\x1c\x1d\x1e\x85\u2028\u2029"

# The control characters a paste drops, as they aren't text and typing can't insert them,
# other than the line breaks and the tab, which each paste edit turns into text.
DROPPED_CONTROLS: Mapping[int, None] = dict.fromkeys([*range(0x20), *range(0x7F, 0xA0)])

# What each control character in a paste becomes on one line: a line break or a tab separates words, so it's a space.
PASTE_CONTROLS: Mapping[int, str | None] = {**DROPPED_CONTROLS, **dict.fromkeys(map(ord, f"{LINE_BREAKS}\t"), " ")}


def paste_edit(text: str) -> Edit:
    """
    The edit pasting `text` makes in one line of text: inserting it with each line break and tab as a space,
    and without any other control characters.
    """
    return insert(text.translate(PASTE_CONTROLS))
