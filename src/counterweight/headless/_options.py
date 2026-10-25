"""
The pure parts of a control that offers a list of options to choose from, such as a picker or a combobox:
which options a typed text matches, and which option is highlighted as the options change.
They hold no state and handle no input, so a component wires them to its own state and keys.
"""

from __future__ import annotations

import glob
import re
from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass
from fnmatch import translate
from typing import overload


def identity(option: object) -> object:
    """An option as its own key, for options that are already what identifies them, such as names."""
    return option


@dataclass(frozen=True, slots=True)
class Highlight:
    """
    Which of a list of options is highlighted: the one whose key is `key`, or, when none is,
    the one at `index`, clamped to the first and the last.
    The key keeps the highlight on its option while options before it come and go,
    as React Aria's `focusedKey` does, and the index is where it lands when its own option goes.
    `Highlight()` highlights the first option, and `Highlight(key=current)` the current one, wherever it is.
    A key of `None` is no key, so options MUST NOT have `None` as their key.
    """

    key: object = None
    index: int = 0

    def index_in[T](self, options: Sequence[T], key: Callable[[T], object] = identity) -> int | None:
        """The highlighted option's index in `options`, or `None` if there are none."""
        if not options:
            return None
        if self.key is not None:
            for index, option in enumerate(options):
                if key(option) == self.key:
                    return index
        return max(0, min(self.index, len(options) - 1))

    def landed[T](self, options: Sequence[T], key: Callable[[T], object] = identity) -> Highlight:
        """
        The highlight on the option it's on in `options`, by that option's key and index,
        so it follows that option from now on, rather than the one it held before, if that comes back.
        """
        index = self.index_in(options, key)
        return Highlight() if index is None else Highlight(key=key(options[index]), index=index)

    def moved[T](self, options: Sequence[T], by: int, key: Callable[[T], object] = identity) -> Highlight:
        """The highlight `by` options on in `options`, back for a negative `by`, wrapping at either end."""
        index = self.index_in(options, key)
        if index is None:
            return self
        moved = (index + by) % len(options)
        return Highlight(key=key(options[moved]), index=moved)


@overload
def subsequence_matches(text: str, options: Iterable[str]) -> tuple[str, ...]: ...


@overload
def subsequence_matches[T](text: str, options: Iterable[T], key: Callable[[T], str]) -> tuple[T, ...]: ...


def subsequence_matches[T](text: str, options: Iterable[T], key: Callable[[T], str] = str) -> tuple[T, ...]:
    """
    The options whose `key` holds the letters of `text` in order, with anything between them, ignoring case,
    in their own order but for the one `text` names exactly, which comes first,
    so typing a whole name and choosing the first match chooses it.
    Every option matches an empty `text`.
    """
    folded = text.casefold()
    # `translate`'s pattern matches case-sensitively on every platform, where `fnmatch` folds case only on Windows,
    # so both sides are folded here. Compiling it once spares a lookup in fnmatch's pattern cache per option.
    is_match = re.compile(translate(f"*{'*'.join(glob.escape(letter) for letter in folded)}*")).match
    return matching(folded, options, key, lambda folded_key: is_match(folded_key) is not None)


@overload
def substring_matches(text: str, options: Iterable[str]) -> tuple[str, ...]: ...


@overload
def substring_matches[T](text: str, options: Iterable[T], key: Callable[[T], str]) -> tuple[T, ...]: ...


def substring_matches[T](text: str, options: Iterable[T], key: Callable[[T], str] = str) -> tuple[T, ...]:
    """
    The options whose `key` contains `text`, ignoring case,
    in their own order but for the one `text` names exactly, which comes first.
    Every option matches an empty `text`.
    """
    folded = text.casefold()
    return matching(folded, options, key, lambda folded_key: folded in folded_key)


def matching[T](
    folded: str, options: Iterable[T], key: Callable[[T], str], is_match: Callable[[str], bool]
) -> tuple[T, ...]:
    """
    The `options` whose folded key `is_match`, in order, but for those whose folded key is `folded`, which come first,
    folding each key once.
    """
    exact: list[T] = []
    rest: list[T] = []
    for option in options:
        folded_key = key(option).casefold()
        if is_match(folded_key):
            (exact if folded_key == folded else rest).append(option)
    return (*exact, *rest)
