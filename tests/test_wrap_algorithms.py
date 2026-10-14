"""
The balance and pretty wrapping algorithms, checked against slow reference implementations
on paragraphs of words, including words of zero-width clusters.
"""

from __future__ import annotations

from itertools import combinations
from itertools import pairwise

from hypothesis import assume
from hypothesis import example
from hypothesis import given
from hypothesis import settings
from hypothesis import strategies as st

from counterweight.elements import StyledGrapheme
from counterweight.elements import text_cells
from counterweight.layout import _extract_words_and_spaces
from counterweight.layout import _flatten_long_words
from counterweight.layout import _greedy_line_count
from counterweight.layout import _wrap_at_target
from counterweight.layout import _wrap_balance
from counterweight.layout import _wrap_pretty
from counterweight.layout import cells_width
from counterweight.styles.styles import CellStyle

type Line = list[StyledGrapheme]

words = st.text(alphabet="ab日\u200b", min_size=1, max_size=5)


@st.composite
def paragraphs(draw: st.DrawFn) -> str:
    """Words separated by runs of spaces, with optional spaces at either end."""
    drawn = draw(st.lists(words, min_size=0, max_size=6))
    gaps = ["" if i == 0 else " " * draw(st.integers(min_value=1, max_value=3)) for i in range(len(drawn))]
    joined = "".join(gap + word for gap, word in zip(gaps, drawn, strict=True))
    return " " * draw(st.integers(0, 2)) + joined + " " * draw(st.integers(0, 2))


widths = st.integers(min_value=1, max_value=12)


def cells(text: str) -> Line:
    return list(text_cells(text, CellStyle()))


def text(lines: list[Line]) -> list[str]:
    return ["".join(cell.grapheme for cell in line) for line in lines]


def flattened(paragraph: Line, width: int) -> tuple[list[Line], list[int], list[Line]]:
    flat_words, flat_spaces = _flatten_long_words(*_extract_words_and_spaces(paragraph), width)
    return flat_words, [cells_width(word) for word in flat_words], flat_spaces


@settings(deadline=None)
@given(paragraph=paragraphs(), width=widths, data=st.data())
def test_greedy_line_count_counts_the_lines_wrapping_at_the_target_makes(
    paragraph: str, width: int, data: st.DataObject
) -> None:
    flat_words, word_widths, flat_spaces = flattened(cells(paragraph), width)
    target = data.draw(st.integers(min_value=1, max_value=width))

    assert _greedy_line_count(word_widths, flat_spaces, target) == len(
        _wrap_at_target(flat_words, word_widths, flat_spaces, target)
    )


def test_greedy_line_count_counts_the_space_after_a_line_of_only_zero_width_words() -> None:
    _, word_widths, flat_spaces = flattened(cells("\u200b a"), 1)

    assert _greedy_line_count(word_widths, flat_spaces, 1) == 2


def reference_balance(paragraph: Line, width: int) -> list[Line]:
    """The greedy wrap at the narrowest target that takes no more lines than wrapping at `width`."""
    flat_words, word_widths, flat_spaces = flattened(paragraph, width)
    if not flat_words:
        return [[]]

    def wrap(target: int) -> list[Line]:
        return _wrap_at_target(flat_words, word_widths, flat_spaces, target)

    line_count = len(wrap(width))
    return wrap(min(target for target in range(1, width + 1) if len(wrap(target)) <= line_count))


@settings(deadline=None)
@given(paragraph=paragraphs(), width=widths)
@example(paragraph="a a a a a 日", width=3)
@example(paragraph=" \u200b 日日  日", width=7)
def test_balance_wraps_at_the_narrowest_target_that_keeps_the_line_count(paragraph: str, width: int) -> None:
    assert text(_wrap_balance(cells(paragraph), width)) == text(reference_balance(cells(paragraph), width))


def test_balance_evens_out_lines_that_greedy_wrapping_leaves_ragged() -> None:
    assert text(_wrap_balance(cells("a b c d e f"), 9)) == ["a b c", "d e f"]


def reference_pretty(paragraph: Line, width: int) -> list[Line]:
    """
    Of every way to break the words into lines that fit (or hold a single word),
    the one with the least sum of squared slack on every line but the last,
    taking the earliest breaks among equally good ones.
    """
    flat_words, _, flat_spaces = flattened(paragraph, width)
    if not flat_words:
        return [[]]

    def line(start: int, stop: int) -> Line:
        built = list(flat_words[start])
        for k in range(start + 1, stop):
            built += flat_spaces[k - 1] + flat_words[k]
        return built

    n = len(flat_words)
    candidates = []
    for break_count in range(n):
        for breaks in combinations(range(1, n), break_count):
            ends = (*breaks, n)
            bounds = list(pairwise((0, *ends)))
            lines = [line(start, stop) for start, stop in bounds]
            if any(
                cells_width(built) > width and stop - start > 1
                for built, (start, stop) in zip(lines, bounds, strict=True)
            ):
                continue
            cost = sum(max(width - cells_width(built), 0) ** 2 for built in lines[:-1])
            candidates.append((cost, ends, lines))

    return min(candidates, key=lambda candidate: candidate[:2])[2]


@settings(deadline=None)
@given(paragraph=paragraphs(), width=widths)
# Each separates the squared slack cost and its tie-breaking from a near miss that random paragraphs rarely do.
@example(paragraph="aa日日 a   aaa日日 aaaa", width=11)
@example(paragraph="a a aa aa", width=4)
@example(paragraph="日 a a a  a", width=3)
@example(paragraph="a a a  a a  a", width=5)
@example(paragraph="日 日 a aaaaa aa", width=7)
def test_pretty_minimizes_squared_slack_on_every_line_but_the_last(paragraph: str, width: int) -> None:
    # The reference tries every way to break the words, so it's only practical for a few of them.
    assume(len(flattened(cells(paragraph), width)[0]) <= 10)

    assert text(_wrap_pretty(cells(paragraph), width)) == text(reference_pretty(cells(paragraph), width))


def test_pretty_breaks_early_to_avoid_a_short_middle_line() -> None:
    assert text(_wrap_pretty(cells("aaa bb cc ddddd"), 6)) == ["aaa", "bb cc", "ddddd"]


def test_pretty_keeps_a_single_word_that_fits() -> None:
    assert text(_wrap_pretty(cells("hello"), 10)) == ["hello"]
