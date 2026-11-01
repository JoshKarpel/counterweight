from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Literal
from typing import assert_type

import pytest
from hypothesis import given
from hypothesis import strategies as st

from counterweight.headless import Highlight
from counterweight.headless import prefix_matches
from counterweight.headless import subsequence_matches
from counterweight.headless import substring_matches


@dataclass(frozen=True, slots=True)
class Port:
    number: int
    command: str


def number_of(port: Port) -> int:
    return port.number


WEB = Port(number=3000, command="zellij web")
CODE = Port(number=3001, command="code serve-web")
ATLAS = Port(number=8000, command="atlas serve")


@pytest.mark.parametrize(
    ("highlight", "options", "expected"),
    [
        (Highlight(), ("tea", "coffee"), 0),
        (Highlight(key="coffee"), ("tea", "coffee"), 1),
        (Highlight(key="milk", index=1), ("tea", "coffee", "juice"), 1),
        (Highlight(index=5), ("tea", "coffee"), 1),
        (Highlight(index=-1), ("tea", "coffee"), 0),
        (Highlight(key="tea"), (), None),
    ],
    ids=[
        "first",
        "by key",
        "by index when the key is gone",
        "clamped to the last",
        "clamped to the first",
        "nothing to highlight",
    ],
)
def test_highlight_index_in(highlight: Highlight, options: tuple[str, ...], expected: int | None) -> None:
    assert highlight.index_in(options) == expected


def test_highlight_stays_on_its_option_as_one_before_it_appears() -> None:
    highlight = Highlight().moved((WEB, CODE), 1, number_of)

    assert highlight.index_in((ATLAS, WEB, CODE), number_of) == 2


def test_highlight_lands_on_the_option_that_took_its_place_when_its_own_goes() -> None:
    highlight = Highlight().moved((WEB, CODE, ATLAS), 1, number_of)

    assert highlight.index_in((WEB, ATLAS), number_of) == 1


def test_landed_follows_the_option_it_landed_on_rather_than_the_one_it_held() -> None:
    landed = Highlight(key=CODE.number, index=1).landed((WEB, ATLAS), number_of)

    assert landed.index_in((WEB, CODE, ATLAS), number_of) == 2


def test_landed_on_nothing_highlights_the_first() -> None:
    assert Highlight(key="tea", index=3).landed(()) == Highlight()


@pytest.mark.parametrize(
    ("by", "expected"),
    [(1, "coffee"), (-1, "juice"), (3, "tea"), (-4, "juice")],
    ids=["next", "previous wraps to the last", "a whole lap", "more than a lap back"],
)
def test_highlight_moved(by: int, expected: str) -> None:
    options = ("tea", "coffee", "juice")

    assert Highlight().moved(options, by) == Highlight(key=expected, index=options.index(expected))


def test_moving_over_nothing_leaves_the_highlight() -> None:
    highlight = Highlight(key="tea", index=2)

    assert highlight.moved((), 1) is highlight


@given(st.lists(st.integers(), min_size=1, max_size=20, unique=True), st.integers(min_value=0, max_value=19))
def test_moving_once_per_option_returns_to_the_start(options: list[int], start: int) -> None:
    highlight = Highlight(index=start).landed(options)
    moved = highlight
    for _ in options:
        moved = moved.moved(options, 1)

    assert moved == highlight


def test_highlight_lands_on_the_new_last_when_the_last_goes() -> None:
    highlight = Highlight().moved((WEB, CODE, ATLAS), -1, number_of)

    assert highlight.index_in((WEB, CODE), number_of) == 1


@pytest.mark.parametrize(
    ("start", "by", "expected"),
    [(0, 1, "coffee"), (2, 1, "juice"), (0, -1, "tea"), (0, 3, "juice"), (2, -5, "tea")],
    ids=["next", "stays on the last", "stays on the first", "End", "Home"],
)
def test_highlight_moved_stopping_at_the_ends(start: int, by: int, expected: str) -> None:
    options = ("tea", "coffee", "juice")

    assert Highlight(index=start).moved(options, by, ends="stop") == Highlight(
        key=expected, index=options.index(expected)
    )


@pytest.mark.parametrize(
    ("start", "by", "expected"),
    [(0, 1, Highlight(key="coffee", index=1)), (2, 1, None), (0, -1, None), (1, -1, Highlight(key="tea", index=0))],
    ids=["next", "past the last", "past the first", "back to the first"],
)
def test_highlight_moved_releasing_past_the_ends(start: int, by: int, expected: Highlight | None) -> None:
    assert Highlight(index=start).moved(("tea", "coffee", "juice"), by, ends="release") == expected


HEADING_LIST = ("# drinks", "tea", "coffee", "# food", "toast", "# empty")


def is_heading(option: str) -> bool:
    return option.startswith("#")


@pytest.mark.parametrize(
    ("highlight", "expected"),
    [
        (Highlight(), 1),
        (Highlight(index=3), 4),
        (Highlight(index=5), 4),
        (Highlight(key="# food"), 4),
        (Highlight(key="coffee"), 2),
    ],
    ids=[
        "the first enabled option",
        "forward from a disabled option",
        "backward when nothing enabled follows",
        "forward from a disabled option's key",
        "an enabled option's key",
    ],
)
def test_highlight_index_in_skips_disabled_options(highlight: Highlight, expected: int) -> None:
    assert highlight.index_in(HEADING_LIST, is_disabled=is_heading) == expected


@pytest.mark.parametrize(
    ("ends", "by", "expected"),
    [("wrap", 1, "toast"), ("wrap", 2, "tea"), ("stop", 5, "toast"), ("release", 2, None)],
    ids=["over a heading", "wrapping over headings", "stopping on the last enabled", "releasing past the last"],
)
def test_highlight_moved_passes_over_disabled_options(
    ends: Literal["wrap", "stop", "release"], by: int, expected: str | None
) -> None:
    moved = Highlight(key="coffee").moved(HEADING_LIST, by, is_disabled=is_heading, ends=ends)

    assert moved == (None if expected is None else Highlight(key=expected, index=HEADING_LIST.index(expected)))


def test_with_every_option_disabled_nothing_is_highlighted() -> None:
    highlight = Highlight(key="# food", index=1)
    headings = ("# drinks", "# food")

    assert (
        highlight.index_in(headings, is_disabled=is_heading),
        highlight.moved(headings, 1, is_disabled=is_heading),
        highlight.landed(headings, is_disabled=is_heading),
    ) == (None, highlight, Highlight())


@given(st.lists(st.booleans(), min_size=1, max_size=20), st.integers(min_value=-25, max_value=25))
def test_resolving_never_lands_on_a_disabled_option(disabled: list[bool], start: int) -> None:
    options = list(range(len(disabled)))

    index = Highlight(index=start).index_in(options, is_disabled=lambda option: disabled[option])

    assert (index is None) == all(disabled)
    assert index is None or not disabled[index]


@given(st.lists(st.booleans(), min_size=1, max_size=20), st.integers(min_value=0, max_value=19))
def test_moving_once_per_enabled_option_returns_to_the_start(disabled: list[bool], start: int) -> None:
    options = list(range(len(disabled)))

    def is_disabled(option: int) -> bool:
        return disabled[option]

    highlight = Highlight(index=start).landed(options, is_disabled=is_disabled)
    moved = highlight
    for _ in range(disabled.count(False)):
        moved = moved.moved(options, 1, is_disabled=is_disabled)

    assert moved == highlight


@given(
    st.lists(st.booleans(), min_size=1, max_size=20),
    st.integers(min_value=0, max_value=19),
    st.integers(min_value=-25, max_value=25),
)
def test_stopping_never_leaves_the_enabled_options(disabled: list[bool], start: int, by: int) -> None:
    options = list(range(len(disabled)))

    moved = Highlight(index=start).moved(options, by, is_disabled=lambda option: disabled[option], ends="stop")

    assert all(disabled) or not disabled[moved.index]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", ("testpypi", "pypi", "pytorch-cpu")),
        ("pypi", ("pypi", "testpypi")),
        ("tpi", ("testpypi",)),
        ("PYT", ("pytorch-cpu",)),
        ("ptu", ("pytorch-cpu",)),
        ("[", ()),
    ],
    ids=["empty keeps every option", "exact first", "letters in order", "case folded", "gaps", "glob characters"],
)
def test_subsequence_matches(text: str, expected: tuple[str, ...]) -> None:
    assert subsequence_matches(text, ("testpypi", "pypi", "pytorch-cpu")) == expected


def test_subsequence_matches_a_glob_character_as_itself() -> None:
    assert subsequence_matches("*", ("a*b", "ab")) == ("a*b",)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", ("testpypi", "pypi", "pytorch-cpu")),
        ("pypi", ("pypi", "testpypi")),
        ("tpi", ()),
        ("CPU", ("pytorch-cpu",)),
    ],
    ids=["empty keeps every option", "exact first", "letters apart don't match", "case folded"],
)
def test_substring_matches(text: str, expected: tuple[str, ...]) -> None:
    assert substring_matches(text, ("testpypi", "pypi", "pytorch-cpu")) == expected


def test_matchers_fold_case_rather_than_lowering_it() -> None:
    assert substring_matches("SS", ("straße", "strase")) == ("straße",)


def test_subsequence_matches_by_key_and_returns_the_options() -> None:
    assert subsequence_matches("srv", (WEB, CODE, ATLAS), key=lambda port: port.command) == (CODE, ATLAS)


def test_substring_matches_by_key_and_returns_the_options() -> None:
    assert substring_matches("serve", (WEB, CODE, ATLAS), key=lambda port: port.command) == (CODE, ATLAS)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", ("testpypi", "pypi", "pytorch-cpu")),
        ("py", ("pypi", "pytorch-cpu")),
        ("pypi", ("pypi",)),
        ("PYT", ("pytorch-cpu",)),
        ("pi", ()),
    ],
    ids=["empty keeps every option", "only the options that start with it", "exact", "case folded", "not a prefix"],
)
def test_prefix_matches(text: str, expected: tuple[str, ...]) -> None:
    assert prefix_matches(text, ("testpypi", "pypi", "pytorch-cpu")) == expected


def test_prefix_matches_put_the_exact_option_first() -> None:
    assert prefix_matches("git", ("git-lfs", "git")) == ("git", "git-lfs")


def test_prefix_matches_by_key_and_returns_the_options() -> None:
    assert prefix_matches("co", (WEB, CODE, ATLAS), key=lambda port: port.command) == (CODE,)


if TYPE_CHECKING:

    def moves(highlight: Highlight, ends: Literal["wrap", "stop", "release"]) -> None:
        assert_type(highlight.moved(("tea",), 1), Highlight)
        assert_type(highlight.moved(("tea",), 1, ends="stop"), Highlight)
        assert_type(highlight.moved(("tea",), 1, ends="release"), Highlight | None)
        assert_type(highlight.moved(("tea",), 1, ends=ends), Highlight | None)
