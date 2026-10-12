"""
How text divides into grapheme clusters, the unit that counterweight measures, wraps and paints text in,
and how many terminal cells each cluster takes.
"""

from __future__ import annotations

from functools import lru_cache
from unicodedata import category, iter_graphemes

from wcwidth import wcswidth

LINE_BREAKS = frozenset({"\n", "\r\n"})

DELETE = "\x7f"
SYMBOL_FOR_DELETE = "\N{SYMBOL FOR DELETE}"
SYMBOL_FOR_NULL = "\N{SYMBOL FOR NULL}"
REPLACEMENT_CHARACTER = "\N{REPLACEMENT CHARACTER}"


def graphemes(text: str) -> list[str]:
    """`text` split into extended grapheme clusters, the units a reader sees as one character."""
    # CRLF is the only ASCII cluster longer than one code point.
    if text.isascii() and "\r\n" not in text:
        return list(text)
    return [str(segment) for segment in iter_graphemes(text)]


@lru_cache(maxsize=2**12)
def visible(grapheme: str) -> str:
    """
    `grapheme`, or a symbol standing in for it if it's a control character other than a line break,
    since writing a control character to the terminal runs it as a command rather than drawing it.

    C0 controls (including tab) and delete become their Control Pictures (`␉`, `␛`, `␡`),
    and C1 controls, which have none, become `�`.
    """
    if grapheme in LINE_BREAKS or category(grapheme[0]) != "Cc":
        return grapheme
    if grapheme == DELETE:
        return SYMBOL_FOR_DELETE
    if grapheme < " ":
        return chr(ord(SYMBOL_FOR_NULL) + ord(grapheme))
    return REPLACEMENT_CHARACTER


@lru_cache(maxsize=2**12)
def grapheme_width(grapheme: str) -> int:
    """
    How many terminal cells a grapheme cluster takes, as [wcwidth](https://github.com/jquast/wcwidth) measures it:
    0 (zero-width spaces and joiners, bidirectional marks, a combining mark with nothing to combine with),
    1, or 2 (CJK, most emoji, flags).

    A line break takes none. Any other control character raises `ValueError`, since terminals don't draw it;
    pass it through `visible` first.
    """
    if grapheme in LINE_BREAKS:
        return 0
    width = wcswidth(grapheme)
    if width < 0:
        raise ValueError(f"{grapheme!r} is a control character, which has no width; pass it through visible()")
    return width
