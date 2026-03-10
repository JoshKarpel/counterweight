from __future__ import annotations

import pytest

from counterweight.elements import CellPaint
from counterweight.layout import wrap_cells
from counterweight.styles.styles import CellStyle, TextWrap


def cells(text: str) -> list[CellPaint]:
    return [CellPaint(char=c) for c in text]


def text(line: list[CellPaint]) -> str:
    return "".join(c.char for c in line)


def lines_text(ls: list[list[CellPaint]]) -> list[str]:
    return [text(l) for l in ls]


# ---------------------------------------------------------------------------
# "none" mode
# ---------------------------------------------------------------------------


def test_none_no_width() -> None:
    result = wrap_cells(cells("hello world"), "none", None)
    assert lines_text(result) == ["hello world"]


def test_none_splits_newlines() -> None:
    result = wrap_cells(cells("hello\nworld"), "none", None)
    assert lines_text(result) == ["hello", "world"]


def test_none_ignores_width() -> None:
    result = wrap_cells(cells("hello world"), "none", 5)
    assert lines_text(result) == ["hello world"]


def test_none_width_zero_returns_empty() -> None:
    assert wrap_cells(cells("hello"), "none", 0) == []


# ---------------------------------------------------------------------------
# width=None → no wrapping regardless of mode
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["stable", "balance", "pretty"])
def test_no_width_no_wrap(mode: TextWrap) -> None:
    result = wrap_cells(cells("hello world foo"), mode, None)
    assert lines_text(result) == ["hello world foo"]


# ---------------------------------------------------------------------------
# "stable" mode
# ---------------------------------------------------------------------------


def test_stable_basic_wrap() -> None:
    result = wrap_cells(cells("hello world"), "stable", 8)
    assert lines_text(result) == ["hello", "world"]


def test_stable_exact_fit() -> None:
    result = wrap_cells(cells("hello world"), "stable", 11)
    assert lines_text(result) == ["hello world"]


def test_stable_long_word_mid_break() -> None:
    result = wrap_cells(cells("abcdefghij"), "stable", 4)
    assert lines_text(result) == ["abc-", "def-", "ghij"]


def test_stable_multiple_paragraphs() -> None:
    result = wrap_cells(cells("hi there\nbye now"), "stable", 6)
    assert lines_text(result) == ["hi", "there", "bye", "now"]


def test_stable_empty_content() -> None:
    result = wrap_cells(cells(""), "stable", 10)
    assert lines_text(result) == [""]


def test_stable_width_one() -> None:
    result = wrap_cells(cells("abc"), "stable", 1)
    assert lines_text(result) == ["a", "b", "c"]


def test_stable_all_spaces() -> None:
    result = wrap_cells(cells("   "), "stable", 10)
    assert lines_text(result) == [""]


def test_stable_preserves_cell_style() -> None:
    style = CellStyle(bold=True)
    styled_cells = [CellPaint(char=c, style=style) for c in "hello world"]
    result = wrap_cells(styled_cells, "stable", 8)
    for line in result:
        for cell in line:
            assert cell.style == style


# ---------------------------------------------------------------------------
# "balance" mode
# ---------------------------------------------------------------------------


def test_balance_line_count_matches_greedy() -> None:
    c = cells("the quick brown fox jumps")
    greedy = wrap_cells(c, "stable", 12)
    balanced = wrap_cells(cells("the quick brown fox jumps"), "balance", 12)
    assert len(balanced) == len(greedy)


def test_balance_is_more_even() -> None:
    # "aaa bbb ccc" at width 8: greedy → ["aaa bbb", "ccc"] (7, 3)
    # balance → ["aaa", "bbb ccc"] (3, 7) or similar — max line len <= greedy's max
    c = cells("aaa bbb ccc")
    result = wrap_cells(c, "balance", 8)
    max_len = max(len(l) for l in result)
    greedy_result = wrap_cells(cells("aaa bbb ccc"), "stable", 8)
    greedy_max = max(len(l) for l in greedy_result)
    assert max_len <= greedy_max


def test_balance_empty() -> None:
    result = wrap_cells(cells(""), "balance", 10)
    assert lines_text(result) == [""]


# ---------------------------------------------------------------------------
# "pretty" mode
# ---------------------------------------------------------------------------


def test_pretty_line_count_matches_greedy() -> None:
    c = cells("the quick brown fox jumps over the lazy dog")
    greedy = wrap_cells(c, "stable", 15)
    pretty = wrap_cells(cells("the quick brown fox jumps over the lazy dog"), "pretty", 15)
    assert len(pretty) == len(greedy)


def test_pretty_avoids_short_orphan() -> None:
    # "one two three four five" at width 14 → should not produce empty lines
    c = cells("one two three four five")
    result = wrap_cells(c, "pretty", 14)
    assert all(len(l) > 0 for l in result)


def test_pretty_empty() -> None:
    result = wrap_cells(cells(""), "pretty", 10)
    assert lines_text(result) == [""]


def test_pretty_long_word_break() -> None:
    result = wrap_cells(cells("abcdefghij"), "pretty", 4)
    assert lines_text(result) == ["abc-", "def-", "ghij"]
