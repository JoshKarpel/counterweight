from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from counterweight.elements import Chunk
from counterweight.elements import StyledGrapheme
from counterweight.elements import styled_cells
from counterweight.elements import text_cells
from counterweight.layout import MeasurableText
from counterweight.layout import wrap_cells
from counterweight.styles.styles import CellStyle
from counterweight.styles.styles import TextWrap


def cells(text: str) -> list[StyledGrapheme]:
    return list(text_cells(text, CellStyle()))


def text(line: list[StyledGrapheme]) -> str:
    return "".join(c.grapheme for c in line)


def lines_text(ls: list[list[StyledGrapheme]]) -> list[str]:
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
    styled_cells = [StyledGrapheme(grapheme=c, style=style) for c in "hello world"]
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
    # balance should produce shorter max line and longer min line than greedy.
    c = cells("aaa bbb ccc")
    result = wrap_cells(c, "balance", 8)
    greedy_result = wrap_cells(cells("aaa bbb ccc"), "stable", 8)
    assert max(len(l) for l in result) <= max(len(l) for l in greedy_result)
    assert min(len(l) for l in result) >= min(len(l) for l in greedy_result)


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


def test_pretty_each_word_own_line_when_narrow() -> None:
    # Each word is exactly width; every word must go on its own line.
    # Exercises the bp[i] > i invariant: every bp[i] must be set to i+1.
    result = wrap_cells(cells("ab cd ef"), "pretty", 2)
    assert lines_text(result) == ["ab", "cd", "ef"]


def test_pretty_multi_space_run_in_line_length() -> None:
    # "a   b c" has a 3-space run after "a".
    # At width=6, "a   b" (5 chars) fits on line 1 and "c" on line 2.
    # Verifies space_prefix accumulation counts multi-space runs correctly.
    result = wrap_cells(cells("a   b c"), "pretty", 6)
    assert lines_text(result)[0] == "a   b"
    assert lines_text(result)[-1] == "c"


# ---------------------------------------------------------------------------
# Whitespace preservation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["stable", "balance", "pretty"])
def test_multiple_spaces_preserved_when_fits(mode: TextWrap) -> None:
    # "a   b" has a 3-space run; width is large enough to fit everything on one line.
    result = wrap_cells(cells("a   b"), mode, 10)
    assert lines_text(result) == ["a   b"]


@pytest.mark.parametrize("mode", ["stable", "balance", "pretty"])
def test_multiple_spaces_preserved_within_line_dropped_at_break(mode: TextWrap) -> None:
    # "aa   bb   cc" has 3-space runs between words.
    # At width=9, "aa   bb" (7 chars) fits on line 1; "cc" goes to line 2.
    # The 3-space run within line 1 is preserved; the run at the break boundary is dropped.
    result = wrap_cells(cells("aa   bb   cc"), mode, 9)
    assert lines_text(result)[0] == "aa   bb"
    assert lines_text(result)[-1] == "cc"


# ---------------------------------------------------------------------------
# Wide characters
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["stable", "balance", "pretty"])
def test_wraps_wide_words_by_their_width(mode: TextWrap) -> None:
    result = wrap_cells(cells("日本 語ab 日本語"), mode, 7)
    assert lines_text(result) == ["日本", "語ab", "日本語"]


@pytest.mark.parametrize("mode", ["stable", "balance", "pretty"])
def test_long_word_breaks_between_wide_clusters(mode: TextWrap) -> None:
    result = wrap_cells(cells("日本語日本語"), mode, 5)
    assert lines_text(result) == ["日本-", "語日-", "本語"]


def test_long_word_hyphenates_before_a_wide_cluster_that_does_not_fit() -> None:
    result = wrap_cells(cells("ab日c"), "stable", 3)
    assert lines_text(result) == ["ab-", "日c"]


def test_long_word_keeps_multi_code_point_clusters_whole() -> None:
    result = wrap_cells(cells("e\N{COMBINING ACUTE ACCENT}" * 3), "stable", 2)
    assert lines_text(result) == ["e\N{COMBINING ACUTE ACCENT}-", "e\N{COMBINING ACUTE ACCENT}" * 2]


def test_wide_cluster_too_wide_to_share_a_line_with_a_hyphen_gets_its_own() -> None:
    result = wrap_cells(cells("日本"), "stable", 2)
    assert lines_text(result) == ["日", "本"]


@pytest.mark.parametrize("mode", ["stable", "balance", "pretty"])
def test_wide_clusters_wider_than_the_width_each_get_a_line(mode: TextWrap) -> None:
    result = wrap_cells(cells("日本 a"), mode, 1)
    assert lines_text(result) == ["日", "本", "a"]


def test_crlf_separates_paragraphs() -> None:
    result = wrap_cells(cells("hi\r\nthere"), "none", None)
    assert lines_text(result) == ["hi", "there"]


@pytest.mark.parametrize(("width", "expected"), [(None, (13, 1)), (7, (6, 2))])
def test_measured_size_counts_wide_clusters_as_two_cells(width: int | None, expected: tuple[int, int]) -> None:
    assert MeasurableText(cells=tuple(cells("日本語 ab日本")), wrap="stable").size_at(width) == expected


def test_narrowest_width_is_the_widest_word_in_cells() -> None:
    assert MeasurableText(cells=tuple(cells("ab 日本語 abcde")), wrap="stable").narrowest_width() == 6


def test_zero_width_clusters_take_no_width() -> None:
    assert MeasurableText(cells=tuple(cells("a\N{ZERO WIDTH SPACE}b")), wrap="none").size_at(None) == (2, 1)


@pytest.mark.parametrize("mode", ["stable", "balance", "pretty"])
@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("\N{ZERO WIDTH SPACE}ab", ["\N{ZERO WIDTH SPACE}a", "b"]),
        ("a\N{ZERO WIDTH SPACE}b", ["a\N{ZERO WIDTH SPACE}", "b"]),
    ],
)
def test_long_word_at_width_one_keeps_zero_width_clusters_on_a_line_with_a_visible_one(
    mode: TextWrap, content: str, expected: list[str]
) -> None:
    assert lines_text(wrap_cells(cells(content), mode, 1)) == expected


def test_balance_keeps_a_paragraph_that_fits_on_one_line_when_it_starts_with_a_zero_width_word() -> None:
    assert lines_text(wrap_cells(cells("\N{ZERO WIDTH SPACE} a"), "balance", 3)) == ["\N{ZERO WIDTH SPACE} a"]


def test_hyphen_takes_the_style_of_the_cluster_before_it() -> None:
    bold = CellStyle(bold=True)

    lines = wrap_cells(list(text_cells("abcdef", bold)), "stable", 4)

    assert [(cell.grapheme, cell.style) for cell in lines[0]] == [(grapheme, bold) for grapheme in "abc-"]


def test_text_measures_nothing_at_no_width() -> None:
    assert MeasurableText.of(("hello", CellStyle(), "stable")).size_at(0) == (0, 0)


@pytest.mark.parametrize(
    ("content", "wrap", "expected"),
    [
        ("ab cde f", "stable", 3),
        ("ab cde f", "none", None),
        ("", "stable", None),
    ],
)
def test_narrowest_width_is_the_widest_word_or_unlimited_if_text_does_not_wrap(
    content: str, wrap: TextWrap, expected: int | None
) -> None:
    assert MeasurableText.of((content, CellStyle(), wrap)).narrowest_width() == expected


def test_text_that_does_not_wrap_has_the_same_rows_at_every_width_with_room_for_a_cluster() -> None:
    text = MeasurableText.of(("ab\ncd", CellStyle(), "none"))

    assert text.lines_at(1) is text.lines_at(9) is text.lines_at(None)


def test_text_on_one_row_has_its_cells_as_that_row() -> None:
    text = MeasurableText.of(("ab cd", CellStyle(), "stable"))

    (row,) = text.lines_at(10)

    assert row is text.cells


BOLD = CellStyle(bold=True)


def test_text_reuses_the_cells_of_each_line_the_previous_text_of_its_node_had() -> None:
    previous = MeasurableText.of(("kept\nedited", BOLD, "stable"))
    styled_cells.cache_clear()

    text = MeasurableText.of(("kept\nedits", BOLD, "stable"), previous)

    assert text.pieces[("kept\n", BOLD)] is previous.pieces[("kept\n", BOLD)]


def test_text_reuses_the_cells_of_each_chunk_the_previous_text_of_its_node_had() -> None:
    kept = Chunk(content="kept", style=BOLD)
    previous = MeasurableText.of(((kept, Chunk(content="edited")), CellStyle(), "stable"))
    styled_cells.cache_clear()

    text = MeasurableText.of(((kept, Chunk(content="edits")), CellStyle(), "stable"), previous)

    assert text.pieces[("kept", BOLD)] is previous.pieces[("kept", BOLD)]


def test_text_keeps_only_the_cells_of_its_own_pieces() -> None:
    previous = MeasurableText.of(("gone\nkept", BOLD, "stable"))

    text = MeasurableText.of(("kept", BOLD, "stable"), previous)

    assert set(text.pieces) == {("kept", BOLD)}


def test_text_reuses_no_cells_of_a_previous_text_in_another_style() -> None:
    previous = MeasurableText.of(("same", CellStyle(), "stable"))

    text = MeasurableText.of(("same", BOLD, "stable"), previous)

    assert text.cells == text_cells("same", BOLD)


LINES = st.lists(
    st.sampled_from(["a", "b c", "\n", "\r\n", "\N{LINE SEPARATOR}", "\N{COMBINING ACUTE ACCENT}"]), max_size=8
).map("".join)


@given(previous=LINES, content=LINES)
def test_a_text_built_from_a_previous_one_has_the_cells_of_its_own_content(previous: str, content: str) -> None:
    text = MeasurableText.of((content, BOLD, "stable"), MeasurableText.of((previous, BOLD, "stable")))

    assert text.cells == text_cells(content, BOLD)


def test_texts_of_one_equal_line_share_their_cells() -> None:
    assert MeasurableText.of(("same", BOLD, "stable")).cells is MeasurableText.of(("same", BOLD, "none")).cells
