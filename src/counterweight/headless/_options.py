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
from typing import Literal
from typing import assert_never
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
    `Highlight()` highlights the first option, `Highlight(index=len(options) - 1)` the last,
    and `Highlight(key=current)` the current one, wherever it is.
    A key of `None` is no key, so options MUST NOT have `None` as their key.

    Each method takes the options, `key`, which is each option's key and defaults to the option itself,
    and `is_disabled`, which marks the options the highlight skips, such as headings,
    as Downshift's `isItemDisabled` does; with no `is_disabled`, every option is enabled.
    """

    key: object = None
    index: int = 0

    def index_in[T](
        self,
        options: Sequence[T],
        key: Callable[[T], object] = identity,
        is_disabled: Callable[[T], bool] | None = None,
    ) -> int | None:
        """
        The highlighted option's index in `options`, or `None` if there are no enabled options to highlight.
        A key or an index on a disabled option resolves to the next enabled option after it,
        or, when none follows, the last enabled one before it,
        so `Highlight()` is the first enabled option and `Highlight(index=len(options) - 1)` the last.
        """
        if not options:
            return None
        index = max(0, min(self.index, len(options) - 1))
        if self.key is not None:
            index = next((at for at, option in enumerate(options) if key(option) == self.key), index)
        if is_disabled is None or not is_disabled(options[index]):
            return index
        after = (at for at in range(index + 1, len(options)) if not is_disabled(options[at]))
        before = (at for at in range(index - 1, -1, -1) if not is_disabled(options[at]))
        return next(after, next(before, None))

    def landed[T](
        self,
        options: Sequence[T],
        key: Callable[[T], object] = identity,
        is_disabled: Callable[[T], bool] | None = None,
    ) -> Highlight:
        """
        The highlight on the option it's on in `options`, by that option's key and index,
        so it follows that option from now on, rather than the one it held before, if that comes back.
        """
        index = self.index_in(options, key, is_disabled)
        return Highlight() if index is None else Highlight(key=key(options[index]), index=index)

    @overload
    def moved[T](
        self,
        options: Sequence[T],
        by: int,
        key: Callable[[T], object] = ...,
        is_disabled: Callable[[T], bool] | None = ...,
        *,
        ends: Literal["wrap", "stop"] = "wrap",
    ) -> Highlight: ...

    @overload
    def moved[T](
        self,
        options: Sequence[T],
        by: int,
        key: Callable[[T], object] = ...,
        is_disabled: Callable[[T], bool] | None = ...,
        *,
        ends: Literal["wrap", "stop", "release"],
    ) -> Highlight | None: ...

    def moved[T](
        self,
        options: Sequence[T],
        by: int,
        key: Callable[[T], object] = identity,
        is_disabled: Callable[[T], bool] | None = None,
        *,
        ends: Literal["wrap", "stop", "release"] = "wrap",
    ) -> Highlight | None:
        """
        The highlight `by` enabled options on in `options`, back for a negative `by`.
        At either end, `ends="wrap"` carries on from the other end;
        `"stop"` stays on the first or the last enabled option, so `by=len(options)` is End;
        and `"release"` is `None` for a move past either end, no highlight,
        as the combobox pattern's Down on the last option "returns focus to the combobox".
        With no enabled option to highlight, it's the highlight unchanged.
        """
        index = self.index_in(options, key, is_disabled)
        if index is None:
            return self
        enabled = (
            range(len(options))
            if is_disabled is None
            else [at for at, option in enumerate(options) if not is_disabled(option)]
        )
        target = enabled.index(index) + by
        match ends:
            case "wrap":
                moved = enabled[target % len(enabled)]
            case "stop":
                moved = enabled[max(0, min(target, len(enabled) - 1))]
            case "release":
                if not 0 <= target < len(enabled):
                    return None
                moved = enabled[target]
            case _ as unreachable:
                assert_never(unreachable)
        return Highlight(key=key(options[moved]), index=moved)


@overload
def subsequence_matches[S: str](text: str, options: Iterable[S]) -> tuple[S, ...]: ...


@overload
def subsequence_matches[T](text: str, options: Iterable[T], key: Callable[[T], str]) -> tuple[T, ...]: ...


def subsequence_matches[T](text: str, options: Iterable[T], key: Callable[[T], str] = str) -> tuple[T, ...]:
    """
    The options whose `key` holds the letters of `text` in order, with anything between them, ignoring case,
    as fzf matches, though without ranking them, in their own order but for the one `text` names exactly, which comes first,
    so typing a whole name and choosing the first match chooses it.
    Every option matches an empty `text`.
    """
    folded = text.casefold()
    # `translate`'s pattern matches case-sensitively on every platform, where `fnmatch` folds case only on Windows,
    # so both sides are folded here. Compiling it once spares a lookup in fnmatch's pattern cache per option.
    is_match = re.compile(translate(f"*{'*'.join(glob.escape(letter) for letter in folded)}*")).match
    return matching(folded, options, key, lambda folded_key: is_match(folded_key) is not None)


@overload
def substring_matches[S: str](text: str, options: Iterable[S]) -> tuple[S, ...]: ...


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


@overload
def prefix_matches[S: str](text: str, options: Iterable[S]) -> tuple[S, ...]: ...


@overload
def prefix_matches[T](text: str, options: Iterable[T], key: Callable[[T], str]) -> tuple[T, ...]: ...


def prefix_matches[T](text: str, options: Iterable[T], key: Callable[[T], str] = str) -> tuple[T, ...]:
    """
    The options whose `key` starts with `text`, ignoring case, as Tab completion matches,
    in their own order but for the one `text` names exactly, which comes first.
    Every option matches an empty `text`.
    """
    folded = text.casefold()
    return matching(folded, options, key, lambda folded_key: folded_key.startswith(folded))


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
