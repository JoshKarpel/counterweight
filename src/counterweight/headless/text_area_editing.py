"""
Editing text that wraps onto rows, the pure core of [`use_text_area`][counterweight.headless.use_text_area]
with the edits `text_editing` makes on a line:
where the text wraps, which edit each key press or paste makes, and what each edit does to the value and the cursor.
Each line's rows are cached, as its clusters are, so an edit only wraps the line it changes.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import lru_cache

from counterweight.graphemes import grapheme_width, graphemes, visible
from counterweight.headless.text_editing import (
    DROPPED_CONTROLS,
    KEY_EDITS,
    LINE_BREAKS,
    Edit,
    EditableText,
    Target,
    cell_offset,
    delete_to,
    insert,
    is_blank,
    key_edit_in,
    line_clusters,
    line_end_at,
    line_start_at,
    move_to,
    previous_cluster,
    value_end,
    value_start,
)
from counterweight.keys import Key


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


def row_start(width: int) -> Target:
    """The start of the cursor's row."""

    def target(value: str, cursor: int) -> int:
        return row_at(value, cursor, width).start

    return target


def row_end(width: int) -> Target:
    """
    The end of the cursor's row, or for a soft row, the start of its last cluster,
    since its end is the start of the next row.
    """

    def target(value: str, cursor: int) -> int:
        row = row_at(value, cursor, width)
        return previous_cluster(value, row.end) if row.is_soft else row.end

    return target


def row_text_end(width: int) -> Target:
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
    position = row.start + cell_offset(value[row.start : row.end], column)
    return previous_cluster(value, row.end) if row.is_soft and position == row.end else position


def or_further(target: Target, further: Target) -> Target:
    """`target`, or `further` if the cursor is already at `target`, so pressing the same key again goes on."""

    def combined(value: str, cursor: int) -> int:
        position = target(value, cursor)
        return further(value, cursor) if position == cursor else position

    return combined


# The row next to a row in one direction, in a value wrapped at a width, or `None` past the first row or the last.
type Neighbor = Callable[[str, Row, int], Row | None]


def rows_away(count: int, neighbor: Neighbor) -> Neighbor:
    """The row `count` rows away in `neighbor`'s direction, or the furthest there is, or `None` if there's none."""

    def find(value: str, row: Row, width: int) -> Row | None:
        found = None
        for _ in range(count):
            if (step := neighbor(value, row, width)) is None:
                break
            row = found = step
        return found

    return find


def move_vertically(width: int, neighbor: Neighbor, edge: Target) -> Edit:
    """
    An edit that moves the cursor to the row `neighbor` finds, as near the goal column as that row reaches,
    or to `edge` from the first row or the last, as a browser's text area does.
    """

    def edit(text: EditableText) -> EditableText:
        row = row_at(text.value, text.cursor, width)
        goal = text.goal_column if text.goal_column is not None else column_of(text.value, row, text.cursor)
        if (target := neighbor(text.value, row, width)) is None:
            return EditableText(value=text.value, cursor=edge(text.value, text.cursor), goal_column=None)
        return EditableText(value=text.value, cursor=position_in(text.value, target, goal), goal_column=goal)

    return edit


def move_to_cell(width: int, row: int, column: int) -> Edit:
    """
    An edit that moves the cursor to the cell at `row` and `column` of the value wrapped at `width`,
    as a press on that cell does: to the cluster drawn across it, or to the end of the row past its text,
    with a row above the first or below the last meaning that row.
    """

    def edit(text: EditableText) -> EditableText:
        wrapped = rows(text.value, width)
        target = wrapped[min(max(row, 0), len(wrapped) - 1)]
        return EditableText(value=text.value, cursor=position_in(text.value, target, column), goal_column=None)

    return edit


def move_up(width: int, count: int) -> Edit:
    """
    An edit that moves the cursor `count` rows up, keeping the goal column, or to the first row if it's nearer,
    or to the start of the value from the first row.
    """
    return move_vertically(width, rows_away(count, previous_row), value_start)


def move_down(width: int, count: int) -> Edit:
    """
    An edit that moves the cursor `count` rows down, keeping the goal column, or to the last row if it's nearer,
    or to the end of the value from the last row.
    """
    return move_vertically(width, rows_away(count, next_row), value_end)


@lru_cache(maxsize=2**6)
def key_edits(width: int, enter_inserts_newline: bool) -> Mapping[str, Edit]:
    """
    The edit each key makes in text wrapped at `width`: those it makes in one line of text,
    with the ones that reach along a line reaching along a row instead, and Up and Down moving between rows.
    Ctrl+J and Alt+Enter insert a line break, and so does Enter if `enter_inserts_newline`.
    """
    newline_keys: tuple[str, ...] = (Key.ControlJ, Key.AltEnter, *((Key.Enter,) if enter_inserts_newline else ()))
    return {
        **KEY_EDITS,
        **dict.fromkeys(newline_keys, insert("\n")),
        Key.Up: move_up(width, 1),
        Key.Down: move_down(width, 1),
        Key.ControlP: move_up(width, 1),
        Key.ControlN: move_down(width, 1),
        Key.Home: move_to(row_start(width)),
        Key.ControlA: move_to(or_further(row_start(width), value_start)),
        Key.End: move_to(row_end(width)),
        Key.ControlE: move_to(or_further(row_end(width), value_end)),
        Key.ControlU: delete_to(row_start(width)),
        Key.ControlK: delete_to(row_text_end(width)),
    }


def key_edit(key: str, width: int, enter_inserts_newline: bool) -> Edit | None:
    """The edit a press of `key` makes: a `key_edits` entry, or inserting it if it's text, or `None` for neither."""
    return key_edit_in(key_edits(width, enter_inserts_newline), key)


# What each control character in a paste becomes: each line break, however it's written, starts a line,
# and a tab stays, for `paste_edit` to expand.
PASTE_CONTROLS: Mapping[int, str | None] = {
    **DROPPED_CONTROLS,
    **dict.fromkeys(map(ord, LINE_BREAKS), "\n"),
    ord("\t"): "\t",
}


def paste_edit(pasted: str, tab_size: int) -> Edit:
    """
    The edit pasting `pasted` makes: inserting it with each line break as `\\n`,
    each tab expanded to spaces up to the next multiple of `tab_size` columns along its line,
    counting the line's text before the cursor, as `str.expandtabs` counts columns,
    and without any other control characters.
    """
    lines = pasted.replace("\r\n", "\n").translate(PASTE_CONTROLS)

    def edit(text: EditableText) -> EditableText:
        before = text.value[line_start_at(text.value, text.cursor) : text.cursor].expandtabs(tab_size)
        return insert((before + lines).expandtabs(tab_size)[len(before) :])(text)

    return edit


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
