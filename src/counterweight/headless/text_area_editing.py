"""
Editing text that wraps onto rows, the pure core of [`use_text_area`][counterweight.headless.use_text_area]:
where the text wraps, which edit each key press or paste makes, and what each edit does to a value and a cursor.

Positions are offsets into the value in code points, always at a grapheme cluster boundary,
so finding the line around one is a `str` search rather than a walk over the whole value,
and each line's clusters and rows are cached, so an edit only measures the line it changes.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from functools import lru_cache
from itertools import accumulate

from counterweight.graphemes import grapheme_width, graphemes, visible
from counterweight.headless.text_editing import NAMED_KEYS, is_blank, is_word
from counterweight.keys import Key


@dataclass(frozen=True, slots=True)
class EditableArea:
    """
    A value, a cursor in it, and the column Up and Down aim for,
    which a run of them keeps so the cursor returns to it after passing through shorter rows.
    """

    value: str
    cursor: int
    goal_column: int | None

    def following(self, value: str) -> EditableArea:
        """
        This text if its value is still `value`,
        or else `value` with the cursor at its end, since something other than an edit changed it.
        """
        if value == self.value:
            return self
        return EditableArea(value=value, cursor=len(value), goal_column=None)


# One editing action, such as moving the cursor up a row or deleting the cluster before it.
type AreaEdit = Callable[[EditableArea], EditableArea]

# Where in a value an edit reaches, from the cursor.
type AreaTarget = Callable[[str, int], int]


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


@lru_cache(maxsize=2**12)
def row_starts(line: str, width: int) -> tuple[int, ...]:
    """
    The offset in `line` where each of its rows starts, wrapping it at `width` cells.

    A row breaks after the last whitespace that fits, or wherever it fills when a word is wider than a row.
    Unlike text wrapped for reading, whitespace at a break stays at the end of its row and takes its cells,
    and one more cell is kept after the end of the line,
    so wherever the cursor is, it has a cell to be drawn in.
    """
    clusters = line_clusters(line)
    count = len(clusters.widths)
    starts = [0]
    row_width = 0
    # The cluster after the row's last whitespace, where it can break without splitting a word.
    break_at: int | None = None
    for index in range(count + 1):
        cell = clusters.widths[index] if index < count else 1
        # A second pass breaks again at this cluster when the word carried onto the new row still overflows it.
        while row_width + cell > width and index > starts[-1]:
            start = break_at if break_at is not None else index
            starts.append(start)
            row_width = sum(clusters.widths[start:index])
            break_at = None
        row_width += cell
        if index < count and is_blank(line[clusters.starts[index] : clusters.starts[index + 1]]):
            break_at = index + 1
    return tuple(clusters.starts[start] for start in starts)


@dataclass(frozen=True, slots=True)
class Row:
    """
    Where one row of the wrapped value starts and ends.
    A soft row wraps onto the next, which starts where it ends;
    any other row ends at a line break or the end of the value.
    """

    start: int
    end: int
    is_soft: bool


def line_start_at(value: str, offset: int) -> int:
    """The start of the line `offset` is in."""
    return value.rfind("\n", 0, offset) + 1


def line_end_at(value: str, offset: int) -> int:
    """The end of the line `offset` is in: the offset of its line break, or the end of the value."""
    end = value.find("\n", offset)
    return len(value) if end == -1 else end


def line_rows(value: str, start: int, width: int) -> list[Row]:
    """The rows of the line that starts at `start`."""
    end = line_end_at(value, start)
    starts = row_starts(value[start:end], width)
    return [
        Row(start=start + row_start, end=start + row_end, is_soft=index < len(starts) - 1)
        for index, (row_start, row_end) in enumerate(zip(starts, (*starts[1:], end - start), strict=True))
    ]


def row_at(value: str, offset: int, width: int) -> Row:
    """The row `offset` is in, which at a soft break is the row that starts there."""
    return next(row for row in reversed(line_rows(value, line_start_at(value, offset), width)) if row.start <= offset)


def previous_row(value: str, row: Row, width: int) -> Row | None:
    """The row before `row`, or `None` if it's the first."""
    # The offset before a row is in the soft row before it, or is the line break that ends the line before.
    return row_at(value, row.start - 1, width) if row.start > 0 else None


def next_row(value: str, row: Row, width: int) -> Row | None:
    """The row after `row`, or `None` if it's the last."""
    if row.is_soft:
        return row_at(value, row.end, width)
    return row_at(value, row.end + 1, width) if row.end < len(value) else None


def rows(value: str, width: int) -> list[Row]:
    """Every row of `value`, wrapped at `width` cells."""
    result: list[Row] = []
    start = 0
    while True:
        result.extend(line_rows(value, start, width))
        if result[-1].end == len(value):
            return result
        start = result[-1].end + 1


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


def row_start(width: int) -> AreaTarget:
    """The start of the cursor's row."""

    def target(value: str, cursor: int) -> int:
        return row_at(value, cursor, width).start

    return target


def row_end(width: int) -> AreaTarget:
    """
    The end of the cursor's row, or for a soft row, the start of its last cluster,
    since its end is the start of the next row.
    """

    def target(value: str, cursor: int) -> int:
        row = row_at(value, cursor, width)
        return previous_cluster(value, row.end) if row.is_soft else row.end

    return target


def row_text_end(width: int) -> AreaTarget:
    """The end of the cursor's row, past any whitespace a soft row ends with."""

    def target(value: str, cursor: int) -> int:
        return row_at(value, cursor, width).end

    return target


def column_of(value: str, row: Row, offset: int) -> int:
    """How many cells the clusters of `row` before `offset` take."""
    return sum(grapheme_width(visible(cluster)) for cluster in graphemes(value[row.start : offset]))


def position_in(value: str, row: Row, column: int) -> int:
    """
    The position in `row` nearest `column` without passing it,
    which in a soft row is at most the start of its last cluster.
    """
    position = row.start
    for cluster in graphemes(value[row.start : row.end]):
        cell = grapheme_width(visible(cluster))
        if column < cell or (row.is_soft and position + len(cluster) == row.end):
            break
        column -= cell
        position += len(cluster)
    return position


def move_to(target: AreaTarget) -> AreaEdit:
    """An edit that moves the cursor to `target`, leaving the value alone."""

    def edit(area: EditableArea) -> EditableArea:
        return EditableArea(value=area.value, cursor=target(area.value, area.cursor), goal_column=None)

    return edit


def delete_to(target: AreaTarget) -> AreaEdit:
    """An edit that deletes the text between the cursor and `target`, leaving the cursor where it started."""

    def edit(area: EditableArea) -> EditableArea:
        start, end = sorted((area.cursor, target(area.value, area.cursor)))
        value = area.value[:start] + area.value[end:]
        return EditableArea(value=value, cursor=at_boundary(value, start), goal_column=None)

    return edit


def insert(inserted: str) -> AreaEdit:
    """An edit that inserts `inserted` at the cursor, and moves the cursor to the end of it."""

    def edit(area: EditableArea) -> EditableArea:
        value = area.value[: area.cursor] + inserted + area.value[area.cursor :]
        return EditableArea(value=value, cursor=at_boundary(value, area.cursor + len(inserted)), goal_column=None)

    return edit


def transpose(area: EditableArea) -> EditableArea:
    """
    Swap the cluster before the cursor with the one at it, and move the cursor past both,
    or at the end of a line, swap its last two clusters, as Readline's `transpose-chars` does,
    without moving a line break.
    """
    value = area.value
    end = area.cursor if area.cursor == line_end_at(value, area.cursor) else next_cluster(value, area.cursor)
    middle = previous_cluster(value, end)
    start = previous_cluster(value, middle)
    if middle <= line_start_at(value, area.cursor):
        return area
    swapped = value[:start] + value[middle:end] + value[start:middle] + value[end:]
    return EditableArea(value=swapped, cursor=at_boundary(swapped, end), goal_column=None)


def value_start(value: str, cursor: int) -> int:
    """The start of the value."""
    return 0


def value_end(value: str, cursor: int) -> int:
    """The end of the value."""
    return len(value)


def or_further(target: AreaTarget, further: AreaTarget) -> AreaTarget:
    """`target`, or `further` if the cursor is already at `target`, so pressing the same key again goes on."""

    def combined(value: str, cursor: int) -> int:
        position = target(value, cursor)
        return further(value, cursor) if position == cursor else position

    return combined


def move_vertically(width: int, neighbor: Callable[[str, Row, int], Row | None], edge: AreaTarget) -> AreaEdit:
    """
    An edit that moves the cursor to the row `neighbor` finds, as near the goal column as that row reaches,
    or to `edge` from the first row or the last, as a browser's text area does.
    """

    def edit(area: EditableArea) -> EditableArea:
        row = row_at(area.value, area.cursor, width)
        goal = area.goal_column if area.goal_column is not None else column_of(area.value, row, area.cursor)
        if (target := neighbor(area.value, row, width)) is None:
            return EditableArea(value=area.value, cursor=edge(area.value, area.cursor), goal_column=None)
        return EditableArea(value=area.value, cursor=position_in(area.value, target, goal), goal_column=goal)

    return edit


def settled(before: EditableArea, edited: EditableArea, value: str) -> EditableArea:
    """
    The text after an edit from `before` to `edited`, once whoever owns the value has settled it at `value`:
    with the edit's cursor if they kept its change to the value, even transformed, or it didn't change the value,
    and with the cursor from `before` if they discarded its change, so an edit they reject doesn't move the cursor.
    """
    kept = before if edited.value != before.value and value == before.value else edited
    return replace(kept, value=value, cursor=at_boundary(value, min(kept.cursor, len(value))))


@lru_cache(maxsize=2**6)
def key_edits(width: int, enter_inserts_newline: bool) -> Mapping[str, AreaEdit]:
    """
    The edit each key makes in text wrapped at `width`,
    following Readline's default (Emacs) bindings where it has one, on rows rather than the whole value.
    Ctrl+J inserts a line break, and so does Enter if `enter_inserts_newline`.
    """
    newline_keys: tuple[str, ...] = (Key.ControlJ, Key.Enter) if enter_inserts_newline else (Key.ControlJ,)
    edits: dict[str, AreaEdit] = dict.fromkeys(newline_keys, insert("\n"))
    return edits | {
        Key.Left: move_to(previous_cluster),
        Key.ControlB: move_to(previous_cluster),
        Key.Right: move_to(next_cluster),
        Key.ControlF: move_to(next_cluster),
        Key.Up: move_vertically(width, previous_row, value_start),
        Key.Down: move_vertically(width, next_row, value_end),
        Key.ControlP: move_vertically(width, previous_row, value_start),
        Key.ControlN: move_vertically(width, next_row, value_end),
        Key.Home: move_to(row_start(width)),
        Key.ControlA: move_to(or_further(row_start(width), value_start)),
        Key.End: move_to(row_end(width)),
        Key.ControlE: move_to(or_further(row_end(width), value_end)),
        Key.ControlHome: move_to(value_start),
        Key.ControlEnd: move_to(value_end),
        Key.ControlLeft: move_to(word_start),
        Key.ControlRight: move_to(word_end),
        Key.Backspace: delete_to(previous_cluster),
        Key.Delete: delete_to(next_cluster),
        Key.ControlD: delete_to(next_cluster),
        Key.ControlW: delete_to(blank_separated_word_start),
        Key.ControlDelete: delete_to(word_end),
        Key.ControlU: delete_to(row_start(width)),
        Key.ControlK: delete_to(row_text_end(width)),
        Key.ControlT: transpose,
    }


def key_edit(key: str, width: int, enter_inserts_newline: bool) -> AreaEdit | None:
    """The edit a press of `key` makes: inserting it if it's text, or a `key_edits` entry, or `None` for neither."""
    if (edit := key_edits(width, enter_inserts_newline).get(key)) is not None:
        return edit
    if key in NAMED_KEYS:
        return None
    return insert(key)


# What each control character in a paste becomes: each line break, however it's written, starts a line,
# a tab separates words, so it's a space, and any other is dropped, as it isn't text and typing can't insert it.
PASTE_CONTROLS: Mapping[int, str | None] = {
    **dict.fromkeys([*range(0x20), *range(0x7F, 0xA0)]),
    **dict.fromkeys(map(ord, "\n\v\f\r\x1c\x1d\x1e\x85\u2028\u2029"), "\n"),
    ord("\t"): " ",
}


def paste_edit(text: str) -> AreaEdit:
    """
    The edit pasting `text` makes: inserting it with each line break as `\\n` and each tab as a space,
    and without any other control characters.
    """
    return insert(text.replace("\r\n", "\n").translate(PASTE_CONTROLS))


@dataclass(frozen=True, slots=True)
class DrawnArea:
    """A value's rows, joined by line breaks, split around the cursor."""

    before_cursor: str
    at_cursor: str
    after_cursor: str


def drawn(value: str, cursor: int, width: int) -> DrawnArea:
    """
    `value` wrapped at `width` cells, with a line break between rows, split around `cursor`:
    `at_cursor` is the cluster there, or a space at the end of a row that isn't soft, so the cursor has a cell.
    """
    texts: list[str] = []
    for row in rows(value, width):
        texts.append(value[row.start : row.end])
        if row.start <= cursor < row.end or (cursor == row.end and not row.is_soft):
            cursor_row = row
            before = len(texts) - 1
    at_cursor = graphemes(value[cursor : cursor_row.end])[0] if cursor < cursor_row.end else " "
    after_cursor = value[cursor + len(at_cursor) : cursor_row.end] if cursor < cursor_row.end else ""
    return DrawnArea(
        before_cursor="".join(text + "\n" for text in texts[:before]) + value[cursor_row.start : cursor],
        at_cursor=at_cursor,
        after_cursor=after_cursor + "".join("\n" + text for text in texts[before + 1 :]),
    )
