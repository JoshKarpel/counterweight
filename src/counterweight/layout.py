from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, assert_never

import waxy

from counterweight.elements import AnyElement, CellPaint, Div, Text
from counterweight.styles.styles import TextWrap

if TYPE_CHECKING:
    from counterweight.shadow import ShadowNode


@dataclass(frozen=True, slots=True)
class ResolvedLayout:
    content: waxy.Rect
    padding: waxy.Rect
    border: waxy.Rect
    margin: waxy.Rect
    order: int


# right < left and bottom < top → zero-width/height in the inclusive coordinate system
_EMPTY_RECT = waxy.Rect(left=0, right=-1, top=0, bottom=-1)

INITIAL_RESOLVED_LAYOUT = ResolvedLayout(
    content=_EMPTY_RECT,
    padding=_EMPTY_RECT,
    border=_EMPTY_RECT,
    margin=_EMPTY_RECT,
    order=0,
)


def compute_layout(
    shadow: ShadowNode,
    available: waxy.AvailableSize,
) -> list[tuple[AnyElement, ResolvedLayout]]:
    """
    Build a waxy tree from the shadow tree, compute layout, and return
    a flat list of (element, resolved_layout) pairs.
    """
    tree: waxy.TaffyTree[Text] = waxy.TaffyTree()
    node_map: dict[waxy.NodeId, ShadowNode] = {}

    root_id = _build_node(tree, shadow, node_map)

    tree.compute_layout(root_id, available, measure=_measure_text)

    results: list[tuple[AnyElement, ResolvedLayout]] = []
    _extract_layout(tree, root_id, node_map, abs_x=0.0, abs_y=0.0, results=results)

    return results


def _build_node(
    tree: waxy.TaffyTree[Text],
    shadow: ShadowNode,
    node_map: dict[waxy.NodeId, ShadowNode],
) -> waxy.NodeId:
    element = shadow.element

    match element:
        case Text():
            node_id = tree.new_leaf_with_context(element.style.layout, element)
        case Div():
            child_ids = [_build_node(tree, child_shadow, node_map) for child_shadow in shadow.children]
            node_id = tree.new_with_children(element.style.layout, child_ids)
        case _:
            assert_never(element)

    node_map[node_id] = shadow
    return node_id


def _measure_text(
    known: waxy.KnownSize,
    available: waxy.AvailableSize,
    context: Text,
) -> waxy.Size:
    width: float | None = known.width
    if width is None and isinstance(available.width, waxy.Definite):
        width = available.width.value

    lines = wrap_cells(
        context.cells,
        context.style.text_wrap,
        int(width) if width is not None else None,
    )

    return waxy.Size(
        width=known.width if known.width is not None else float(max((len(l) for l in lines), default=0)),
        height=known.height if known.height is not None else float(len(lines)),
    )


def _extract_layout(
    tree: waxy.TaffyTree[Text],
    node_id: waxy.NodeId,
    node_map: dict[waxy.NodeId, ShadowNode],
    abs_x: float,
    abs_y: float,
    results: list[tuple[AnyElement, ResolvedLayout]],
) -> None:
    """Walk tree top-down, accumulating absolute positions.

    abs_x/abs_y is the absolute position of the current node's parent's border box origin,
    i.e. the origin that taffy's relative ``layout.location`` is measured from.
    For the root node, pass (0, 0).
    """
    layout = tree.unrounded_layout(node_id)
    shadow = node_map[node_id]

    # display:nil hides the entire subtree, matching CSS display:none semantics
    if shadow.element.style.layout.display == waxy.Display.Nil:
        return

    border_abs_x = abs_x + layout.location.x
    border_abs_y = abs_y + layout.location.y

    # floor for left/top (round toward -inf) so negative coordinates work.
    # floor(end) - 1 for right/bottom: always rounds down, so a fractional start
    # position (e.g. 18.667 from justify_content:space_evenly) doesn't inflate the
    # element's discrete row/column count when the size is an exact integer (e.g.
    # start=18.667, size=4.0 → end=22.667 → floor=22 → bb=21, height=4, not 5).
    # This also correctly handles fractional flex sizes where frac(start)+frac(size)
    # reaches an exact integer boundary (e.g. start=12.667, size=7.333 → end=20.0).
    bx = math.floor(border_abs_x)
    by = math.floor(border_abs_y)
    br = math.floor(border_abs_x + layout.size.width) - 1
    bb = math.floor(border_abs_y + layout.size.height) - 1

    border_rect = waxy.Rect(left=bx, right=br, top=by, bottom=bb)

    margin_rect = waxy.Rect(
        left=bx - int(layout.margin.left),
        right=br + int(layout.margin.right),
        top=by - int(layout.margin.top),
        bottom=bb + int(layout.margin.bottom),
    )

    pl = bx + int(layout.border.left)
    pt = by + int(layout.border.top)
    pr = br - int(layout.border.right)
    pb = bb - int(layout.border.bottom)
    padding_rect = waxy.Rect(left=pl, right=pr, top=pt, bottom=pb)

    content_rect = waxy.Rect(
        left=pl + int(layout.padding.left),
        right=pr - int(layout.padding.right),
        top=pt + int(layout.padding.top),
        bottom=pb - int(layout.padding.bottom),
    )

    resolved = ResolvedLayout(
        content=content_rect,
        padding=padding_rect,
        border=border_rect,
        margin=margin_rect,
        order=len(results),
    )
    results.append((shadow.element, resolved))

    shadow.hooks.dims = resolved

    for child_node_id in tree.children(node_id):
        _extract_layout(tree, child_node_id, node_map, border_abs_x, border_abs_y, results)


def _split_paragraphs(cells: Iterable[CellPaint]) -> list[list[CellPaint]]:
    paragraphs: list[list[CellPaint]] = []
    current: list[CellPaint] = []
    for cell in cells:
        if cell.char == "\n":
            paragraphs.append(current)
            current = []
        else:
            current.append(cell)
    paragraphs.append(current)
    return paragraphs


def _extract_words_and_spaces(
    paragraph: list[CellPaint],
) -> tuple[list[list[CellPaint]], list[list[CellPaint]]]:
    """Split a paragraph into (words, spaces).

    words[i] is a non-space run; spaces[i] is the space run between words[i] and words[i+1].
    Leading and trailing spaces are discarded.
    len(spaces) == len(words) - 1.
    """
    words: list[list[CellPaint]] = []
    spaces: list[list[CellPaint]] = []
    current_word: list[CellPaint] = []
    current_space: list[CellPaint] = []

    for cell in paragraph:
        if cell.char == " ":
            if current_word:
                # We are in a word — start collecting the trailing space run.
                current_space.append(cell)
        else:
            if current_space:
                # We just finished a space run between two words.
                words.append(current_word)
                spaces.append(current_space)
                current_word = [cell]
                current_space = []
            elif current_word:
                current_word.append(cell)
            else:
                # Start of the first word (leading spaces already dropped).
                current_word = [cell]

    if current_word:
        words.append(current_word)
    # Trailing spaces in current_space are discarded.

    return words, spaces


def _flatten_long_words(
    words: list[list[CellPaint]],
    spaces: list[list[CellPaint]],
    width: int,
) -> tuple[list[list[CellPaint]], list[list[CellPaint]]]:
    """Break any word longer than width into width-sized chunks.

    Space runs between chunks of the same word become [] (no space between hyphenated chunks).
    Returns (flat_words, flat_spaces) with len(flat_spaces) == len(flat_words) - 1.
    """
    flat_words: list[list[CellPaint]] = []
    flat_spaces: list[list[CellPaint]] = []

    for i, word in enumerate(words):
        if len(word) > width:
            chunks = _break_long_word(word, width)
        else:
            chunks = [word]

        for j, chunk in enumerate(chunks):
            if flat_words:
                # Insert a space before this chunk:
                # - [] (no space) between hyphenated sub-chunks of the same word
                # - the real inter-word space run between different words
                flat_spaces.append([] if j > 0 else spaces[i - 1] if i > 0 else [])
            flat_words.append(chunk)

        # After all chunks of this word, if there's a following inter-word space, it will be
        # appended when the next word's first chunk is processed (spaces[i] referenced as spaces[i-1]
        # with i incremented). Nothing to do here.

    return flat_words, flat_spaces


def _break_long_word(word: list[CellPaint], width: int) -> list[list[CellPaint]]:
    """Break a word that is longer than width into width-sized chunks, hyphenating all but the last."""
    if width <= 1:
        return [word[i : i + width] for i in range(0, len(word), width)]
    chunks: list[list[CellPaint]] = []
    i = 0
    while i < len(word):
        if i + width < len(word):
            hyphen = CellPaint(char="-", style=word[i + width - 2].style)
            chunks.append([*word[i : i + width - 1], hyphen])
            i += width - 1
        else:
            chunks.append(word[i : i + width])
            break
    return chunks


def _wrap_greedy(paragraph: list[CellPaint], width: int) -> list[list[CellPaint]]:
    words, spaces = _extract_words_and_spaces(paragraph)
    flat_words, flat_spaces = _flatten_long_words(words, spaces, width)

    lines: list[list[CellPaint]] = []
    current: list[CellPaint] = []
    pending_space: list[CellPaint] = []

    for i, word in enumerate(flat_words):
        if not current:
            current = list(word)
        elif len(current) + len(pending_space) + len(word) <= width:
            current.extend(pending_space)
            current.extend(word)
        else:
            lines.append(current)
            current = list(word)
        if i < len(flat_spaces):
            pending_space = flat_spaces[i]

    lines.append(current)
    return lines


def _greedy_line_count(flat_words: list[list[CellPaint]], flat_spaces: list[list[CellPaint]], width: int) -> int:
    count = 1
    length = 0
    pending_space_len = 0

    for i, word in enumerate(flat_words):
        wlen = len(word)
        if not length:
            length = wlen
        elif length + pending_space_len + wlen <= width:
            length += pending_space_len + wlen
        else:
            count += 1
            length = wlen
        pending_space_len = len(flat_spaces[i]) if i < len(flat_spaces) else 0

    return count


def _wrap_at_target(
    flat_words: list[list[CellPaint]],
    flat_spaces: list[list[CellPaint]],
    width: int,
    target: int,
) -> list[list[CellPaint]]:
    """Greedy wrap with long-word breaking, targeting `target` width for line breaks."""
    lines: list[list[CellPaint]] = []
    current: list[CellPaint] = []
    pending_space: list[CellPaint] = []

    for i, word in enumerate(flat_words):
        if not current:
            current = list(word)
        elif len(current) + len(pending_space) + len(word) <= target:
            current.extend(pending_space)
            current.extend(word)
        else:
            lines.append(current)
            current = list(word)
        if i < len(flat_spaces):
            pending_space = flat_spaces[i]

    lines.append(current)
    return lines


def _wrap_balance(paragraph: list[CellPaint], width: int) -> list[list[CellPaint]]:
    words, spaces = _extract_words_and_spaces(paragraph)
    if not words:
        return [[]]

    flat_words, flat_spaces = _flatten_long_words(words, spaces, width)

    k = _greedy_line_count(flat_words, flat_spaces, width)

    if k <= 1:
        return _wrap_at_target(flat_words, flat_spaces, width, width)

    # Binary search for the narrowest target that still yields k lines.
    lo, hi = 1, width
    while lo < hi:
        mid = (lo + hi) // 2
        if _greedy_line_count(flat_words, flat_spaces, mid) <= k:
            hi = mid
        else:
            lo = mid + 1

    return _wrap_at_target(flat_words, flat_spaces, width, lo)


def _wrap_pretty(paragraph: list[CellPaint], width: int) -> list[list[CellPaint]]:
    """DP optimal line-breaking minimizing sum of squared slack on non-last lines."""
    words, spaces = _extract_words_and_spaces(paragraph)
    if not words:
        return [[]]

    flat_words, flat_spaces = _flatten_long_words(words, spaces, width)

    n = len(flat_words)
    INF = float("inf")

    # Precompute prefix sums of word lengths so line_length is O(1).
    # prefix[i] = sum of len(flat_words[0]) .. len(flat_words[i-1])
    prefix: list[int] = [0] * (n + 1)
    for idx in range(n):
        prefix[idx + 1] = prefix[idx] + len(flat_words[idx])

    # Precompute prefix sums of space lengths between words.
    # space_prefix[k] = sum of len(flat_spaces[0]) .. len(flat_spaces[k-1])
    # (size n, space_prefix[0] = 0)
    space_prefix: list[int] = [0] * n
    for idx in range(1, n):
        space_prefix[idx] = space_prefix[idx - 1] + (len(flat_spaces[idx - 1]) if idx - 1 < len(flat_spaces) else 0)

    def line_length(i: int, j: int) -> int:
        word_len = prefix[j] - prefix[i]
        space_len = space_prefix[j - 1] - space_prefix[i] if j > i + 1 else 0
        return word_len + space_len

    # dp[i] = min cost to break flat_words[i..n-1], bp[i] = best j for first break.
    dp: list[float] = [INF] * (n + 1)
    bp: list[int] = [0] * (n + 1)
    dp[n] = 0.0

    for i in range(n - 1, -1, -1):
        for j in range(i + 1, n + 1):
            ll = line_length(i, j)
            if ll > width:
                break
            slack = width - ll
            if j == n:
                cost = 0.0
            else:
                cost = float(slack) ** 2
            total = cost + dp[j]
            if total < dp[i]:
                dp[i] = total
                bp[i] = j

    # Reconstruct lines.
    lines: list[list[CellPaint]] = []
    i = 0
    while i < n:
        j = bp[i]
        line: list[CellPaint] = []
        for k in range(i, j):
            if k > i:
                # Insert the actual space run between flat_words[k-1] and flat_words[k].
                if k - 1 < len(flat_spaces):
                    line.extend(flat_spaces[k - 1])
            line.extend(flat_words[k])
        lines.append(line)
        i = j

    return lines if lines else [[]]


def wrap_cells(
    cells: Iterable[CellPaint],
    wrap: TextWrap,
    width: int | None,
) -> list[list[CellPaint]]:
    if width is not None and width <= 0:
        return []

    paragraphs = _split_paragraphs(cells)

    if wrap == "none" or width is None:
        return paragraphs

    result: list[list[CellPaint]] = []
    for paragraph in paragraphs:
        if wrap == "stable":
            result.extend(_wrap_greedy(paragraph, width))
        elif wrap == "balance":
            result.extend(_wrap_balance(paragraph, width))
        elif wrap == "pretty":
            result.extend(_wrap_pretty(paragraph, width))
        else:
            assert_never(wrap)
    return result
