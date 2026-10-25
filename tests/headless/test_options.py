from __future__ import annotations

from dataclasses import dataclass

import pytest
from hypothesis import given
from hypothesis import strategies as st

from counterweight.headless import Highlight
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
