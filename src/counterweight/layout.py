from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING, assert_never

import waxy

from counterweight.elements import AnyElement, Chunk, Div, StyledGrapheme, Text, text_cells
from counterweight.geometry import Region
from counterweight.graphemes import LINE_BREAKS
from counterweight.styles.styles import CellStyle, Style, TextWrap, resolve_style

if TYPE_CHECKING:
    from counterweight.shadow import ShadowNode


@dataclass(frozen=True, slots=True)
class ResolvedLayout:
    content: Region
    padding: Region
    border: Region
    margin: Region
    order: int


_EMPTY_REGION = Region(left=0, top=0, right=0, bottom=0)

INITIAL_RESOLVED_LAYOUT = ResolvedLayout(
    content=_EMPTY_REGION,
    padding=_EMPTY_REGION,
    border=_EMPTY_REGION,
    margin=_EMPTY_REGION,
    order=0,
)


# Everything a `Text`'s measured size depends on: its content, its text style, and how it wraps.
type TextSource = tuple[str | tuple[Chunk, ...], CellStyle, TextWrap]


@dataclass(eq=False, slots=True)
class LayoutTree:
    """
    The layout tree for one app, kept across frames so that taffy keeps the layout it cached
    for every node whose style, text and children are unchanged.

    Each `ShadowNode` remembers its node in `layout_node`, which `update_shadow` carries over
    wherever it carries over the node's hooks.
    """

    tree: waxy.TaffyTree[MeasurableText] = field(default_factory=waxy.TaffyTree)
    texts: dict[waxy.NodeId, TextSource] = field(default_factory=dict)
    children: dict[waxy.NodeId, list[waxy.NodeId]] = field(default_factory=dict)
    shadows: dict[waxy.NodeId, ShadowNode] = field(default_factory=dict)

    def compute(
        self,
        shadow: ShadowNode,
        available: waxy.AvailableSize,
    ) -> list[tuple[AnyElement, ResolvedLayout]]:
        """Lay out the shadow tree, and return each visible element with its layout, in paint order."""
        root = self.update(shadow)

        self.tree.compute_layout(root, available, measure=_measure_text)

        results: list[tuple[AnyElement, ResolvedLayout]] = []
        for order, (node, position, layout) in enumerate(self.tree.absolute_layouts(root)):
            visible = self.shadows[node]
            resolved = _resolve_layout(position, layout, order)
            visible.hooks.dims = resolved
            results.append((visible.element, resolved))

        return results

    def update(self, shadow: ShadowNode) -> waxy.NodeId:
        """Make the tree match the shadow tree, and return the root's node."""
        shadows: dict[waxy.NodeId, ShadowNode] = {}
        root = self._update_node(shadow, shadows)

        # Taffy's remove detaches a node's children rather than removing them,
        # so every unmounted node is removed, not just the root of an unmounted subtree.
        for unmounted in self.shadows.keys() - shadows.keys():
            self.tree.remove(unmounted)
            self.texts.pop(unmounted, None)
            self.children.pop(unmounted, None)

        self.shadows = shadows
        return root

    def _update_node(self, shadow: ShadowNode, shadows: dict[waxy.NodeId, ShadowNode]) -> waxy.NodeId:
        element = shadow.element
        style = layout_style(element.style)
        node = shadow.layout_node

        # set_style keeps the node's cached layout when the style is equal,
        # but set_node_context and set_children always discard it, so they're called only on a change.
        match element:
            case Text():
                content = element.content if isinstance(element.content, str) else tuple(element.content)
                source = (content, element.style.text_style, resolve_style(element.style).text_wrap)
                if node is None:
                    node = self.tree.new_leaf_with_context(style, MeasurableText.of(source))
                else:
                    self.tree.set_style(node, style)
                    # A Div's children unmount along with it, and taffy's remove detaches them.
                    self.children.pop(node, None)
                    if self.texts.get(node) != source:
                        self.tree.set_node_context(node, MeasurableText.of(source))
                self.texts[node] = source
            case Div():
                child_nodes = [self._update_node(child, shadows) for child in shadow.children]
                if node is None:
                    node = self.tree.new_with_children(style, child_nodes)
                else:
                    self.tree.set_style(node, style)
                    if self.texts.pop(node, None) is not None:
                        self.tree.set_node_context(node, None)
                    if self.children.get(node) != child_nodes:
                        self.tree.set_children(node, child_nodes)
                self.children[node] = child_nodes
            case _:
                assert_never(element)

        shadow.layout_node = node
        # Hidden subtrees are absent from absolute_layouts, so their components would otherwise
        # keep reporting the regions from the last frame they were visible in.
        shadow.hooks.dims = INITIAL_RESOLVED_LAYOUT
        shadows[node] = shadow
        return node


_NO_BORDER = waxy.Style(
    border_top=waxy.Length(0),
    border_bottom=waxy.Length(0),
    border_left=waxy.Length(0),
    border_right=waxy.Length(0),
)


@lru_cache(maxsize=2**12)
def layout_style(style: Style) -> waxy.Style:
    """
    The waxy style an element is laid out with: its `layout`, without border widths
    when its `border_kind` is `None`, as CSS's `border-style: none` makes border widths compute to 0.
    """
    if resolve_style(style).border_kind is None:
        return style.layout | _NO_BORDER
    return style.layout


UNMEASURED = sentinel("UNMEASURED")


@dataclass(eq=False, slots=True)
class MeasurableText:
    """
    What layout needs to size a `Text`: its cells and how they wrap,
    with the size they wrap to at each width already asked about.

    Taffy asks a leaf about a dozen distinct questions per layout, but the answer depends only on
    one effective width, so most questions repeat one already answered.
    """

    cells: tuple[StyledGrapheme, ...]
    wrap: TextWrap
    sizes: dict[int | None, tuple[int, int]] = field(default_factory=dict)
    min_content_width: int | UNMEASURED | None = UNMEASURED

    @classmethod
    def of(cls, source: TextSource) -> MeasurableText:
        content, text_style, wrap = source
        return cls(cells=text_cells(content, text_style), wrap=wrap)

    def size_at(self, width: int | None) -> tuple[int, int]:
        """The widest line and the line count when wrapped at `width` (unlimited if `None`)."""
        try:
            return self.sizes[width]
        except KeyError:
            lines = wrap_cells(self.cells, self.wrap, width)
            size = self.sizes[width] = (max((cells_width(line) for line in lines), default=0), len(lines))
            return size

    def narrowest_width(self) -> int | None:
        """
        The narrowest width this text takes without breaking a word, as CSS's `min-content` is for text:
        its widest word if it wraps, or `None` (unlimited) if it doesn't.
        """
        if self.min_content_width is UNMEASURED:
            self.min_content_width = _min_content_width(self.cells, self.wrap)
        return self.min_content_width


def _measure_text(
    known: waxy.KnownSize,
    available: waxy.AvailableSize,
    context: MeasurableText,
) -> waxy.Size:
    known_width = known.width
    known_height = known.height

    width: int | None
    if known_width is not None:
        width = int(known_width)
    else:
        match available.width:
            case waxy.Definite(value=value):
                width = int(value)
            case waxy.MinContent():
                width = context.narrowest_width()
            case waxy.MaxContent():
                width = None
            case _ as unreachable:
                assert_never(unreachable)

    widest, line_count = context.size_at(width)

    # Positional, because pyo3 matches keyword arguments by name on every call, which nearly doubles its cost.
    return waxy.Size(
        known_width if known_width is not None else float(widest),
        known_height if known_height is not None else float(line_count),
    )


def _min_content_width(cells: Iterable[StyledGrapheme], wrap: TextWrap) -> int | None:
    """The widest word in `cells`, or `None` (unlimited) if they don't wrap."""
    if wrap == "none":
        return None

    return max(
        (
            cells_width(word)
            for paragraph in _split_paragraphs(cells)
            for word in _extract_words_and_spaces(paragraph)[0]
        ),
        default=None,
    )


@lru_cache(maxsize=2**12)
def _resolve_layout(position: waxy.Point, layout: waxy.Layout, order: int) -> ResolvedLayout:
    """
    The cell regions of one node's boxes, from its absolute border-box position.

    Taffy's rounding snaps each absolute edge to a whole cell, so every value here is already
    integral and adjacent boxes share edges without gaps or overlaps.

    Cached because most nodes keep their position and layout from one frame to the next,
    and building the regions is most of the cost of reading layouts back.
    """
    left = int(position.x)
    top = int(position.y)
    border = Region(left=left, top=top, right=left + int(layout.size.width), bottom=top + int(layout.size.height))

    margin_widths = layout.margin
    margin = Region(
        left=border.left - int(margin_widths.left),
        top=border.top - int(margin_widths.top),
        right=border.right + int(margin_widths.right),
        bottom=border.bottom + int(margin_widths.bottom),
    )

    border_widths = layout.border
    padding = Region(
        left=border.left + int(border_widths.left),
        top=border.top + int(border_widths.top),
        right=border.right - int(border_widths.right),
        bottom=border.bottom - int(border_widths.bottom),
    )

    padding_widths = layout.padding
    content = Region(
        left=padding.left + int(padding_widths.left),
        top=padding.top + int(padding_widths.top),
        right=padding.right - int(padding_widths.right),
        bottom=padding.bottom - int(padding_widths.bottom),
    )

    return ResolvedLayout(content=content, padding=padding, border=border, margin=margin, order=order)


def cells_width(cells: Iterable[StyledGrapheme]) -> int:
    """How many terminal cells `cells` take side by side."""
    return sum(cell.width for cell in cells)


def _split_paragraphs(cells: Iterable[StyledGrapheme]) -> list[list[StyledGrapheme]]:
    paragraphs: list[list[StyledGrapheme]] = []
    current: list[StyledGrapheme] = []
    for cell in cells:
        if cell.grapheme in LINE_BREAKS:
            paragraphs.append(current)
            current = []
        else:
            current.append(cell)
    paragraphs.append(current)
    return paragraphs


def _extract_words_and_spaces(
    paragraph: list[StyledGrapheme],
) -> tuple[list[list[StyledGrapheme]], list[list[StyledGrapheme]]]:
    """Split a paragraph into (words, spaces).

    words[i] is a non-space run; spaces[i] is the space run between words[i] and words[i+1].
    Leading and trailing spaces are discarded.
    len(spaces) == len(words) - 1.
    """
    words: list[list[StyledGrapheme]] = []
    spaces: list[list[StyledGrapheme]] = []
    current_word: list[StyledGrapheme] = []
    current_space: list[StyledGrapheme] = []

    for cell in paragraph:
        if cell.grapheme == " ":
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
    words: list[list[StyledGrapheme]],
    spaces: list[list[StyledGrapheme]],
    width: int,
) -> tuple[list[list[StyledGrapheme]], list[list[StyledGrapheme]]]:
    """Break any word wider than width into chunks at most width wide.

    Space runs between chunks of the same word become [] (no space between hyphenated chunks).
    Returns (flat_words, flat_spaces) with len(flat_spaces) == len(flat_words) - 1.
    """
    flat_words: list[list[StyledGrapheme]] = []
    flat_spaces: list[list[StyledGrapheme]] = []

    for i, word in enumerate(words):
        if cells_width(word) > width:
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

    return flat_words, flat_spaces


def _break_long_word(word: list[StyledGrapheme], width: int) -> list[list[StyledGrapheme]]:
    """
    Break a word that is wider than width into chunks at most width wide, hyphenating all but the last,
    without splitting a grapheme cluster.

    A cluster too wide to fit beside a hyphen gets a chunk of its own, without one,
    even if that chunk is wider than width.
    """
    room = width - 1 if width > 1 else width
    chunks: list[list[StyledGrapheme]] = []
    remaining = cells_width(word)
    i = 0
    while remaining > width:
        chunk: list[StyledGrapheme] = []
        chunk_width = 0
        while chunk_width + word[i].width <= room:
            chunk.append(word[i])
            chunk_width += word[i].width
            i += 1
        if not chunk:
            chunk = [word[i]]
            chunk_width = word[i].width
            i += 1
        elif room < width:
            chunk.append(StyledGrapheme(grapheme="-", style=chunk[-1].style))
        chunks.append(chunk)
        remaining -= chunk_width
    if i < len(word):
        chunks.append(word[i:])
    return chunks


def _wrap_greedy(paragraph: list[StyledGrapheme], width: int) -> list[list[StyledGrapheme]]:
    words, spaces = _extract_words_and_spaces(paragraph)
    flat_words, flat_spaces = _flatten_long_words(words, spaces, width)
    return _wrap_at_target(flat_words, [cells_width(word) for word in flat_words], flat_spaces, width)


def _greedy_line_count(word_widths: list[int], flat_spaces: list[list[StyledGrapheme]], width: int) -> int:
    count = 1
    length = 0
    pending_space_len = 0

    for i, wlen in enumerate(word_widths):
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
    flat_words: list[list[StyledGrapheme]],
    word_widths: list[int],
    flat_spaces: list[list[StyledGrapheme]],
    target: int,
) -> list[list[StyledGrapheme]]:
    """
    Greedy wrap of already-broken words, targeting `target` width for line breaks.

    Spaces are always one cell wide, so a space run's width is its length.
    """
    lines: list[list[StyledGrapheme]] = []
    current: list[StyledGrapheme] = []
    current_width = 0
    pending_space: list[StyledGrapheme] = []

    for i, (word, word_width) in enumerate(zip(flat_words, word_widths, strict=True)):
        if not current:
            current = list(word)
            current_width = word_width
        elif current_width + len(pending_space) + word_width <= target:
            current.extend(pending_space)
            current.extend(word)
            current_width += len(pending_space) + word_width
        else:
            lines.append(current)
            current = list(word)
            current_width = word_width
        if i < len(flat_spaces):
            pending_space = flat_spaces[i]

    lines.append(current)
    return lines


def _wrap_balance(paragraph: list[StyledGrapheme], width: int) -> list[list[StyledGrapheme]]:
    words, spaces = _extract_words_and_spaces(paragraph)
    if not words:
        return [[]]

    flat_words, flat_spaces = _flatten_long_words(words, spaces, width)
    word_widths = [cells_width(word) for word in flat_words]

    k = _greedy_line_count(word_widths, flat_spaces, width)

    if k <= 1:
        return _wrap_at_target(flat_words, word_widths, flat_spaces, width)

    # Binary search for the narrowest target that still yields k lines.
    lo, hi = 1, width
    while lo < hi:
        mid = (lo + hi) // 2
        if _greedy_line_count(word_widths, flat_spaces, mid) <= k:
            hi = mid
        else:
            lo = mid + 1

    return _wrap_at_target(flat_words, word_widths, flat_spaces, lo)


def _wrap_pretty(paragraph: list[StyledGrapheme], width: int) -> list[list[StyledGrapheme]]:
    """DP optimal line-breaking minimizing sum of squared slack on non-last lines."""
    words, spaces = _extract_words_and_spaces(paragraph)
    if not words:
        return [[]]

    flat_words, flat_spaces = _flatten_long_words(words, spaces, width)

    n = len(flat_words)
    INF = float("inf")

    # Precompute prefix sums of word widths so line_length is O(1).
    # prefix[i] = sum of the widths of flat_words[0] .. flat_words[i-1]
    prefix: list[int] = [0] * (n + 1)
    for idx in range(n):
        prefix[idx + 1] = prefix[idx] + cells_width(flat_words[idx])

    # Precompute prefix sums of space lengths between words.
    # space_prefix[k] = sum of len(flat_spaces[0]) .. len(flat_spaces[k-1])
    # (size n, space_prefix[0] = 0)
    space_prefix: list[int] = [0] * n
    for idx in range(1, n):
        space_prefix[idx] = space_prefix[idx - 1] + len(flat_spaces[idx - 1])

    def line_length(i: int, j: int) -> int:
        word_len = prefix[j] - prefix[i]
        space_len = space_prefix[j - 1] - space_prefix[i] if j > i + 1 else 0
        return word_len + space_len

    # dp[i] = min cost to break flat_words[i..n-1], bp[i] = best j for first break after i.
    # bp[i] is always set to j > i before use because every word may occupy a line of its own,
    # even the one-cluster chunks _flatten_long_words leaves wider than width (a wide cluster at width 1).
    dp: list[float] = [INF] * (n + 1)
    bp: list[int] = [0] * (n + 1)
    dp[n] = 0.0

    for i in range(n - 1, -1, -1):
        for j in range(i + 1, n + 1):
            ll = line_length(i, j)
            if ll > width and j > i + 1:
                break
            slack = max(width - ll, 0)
            if j == n:
                cost = 0.0
            else:
                cost = float(slack) ** 2
            total = cost + dp[j]
            if total < dp[i]:
                dp[i] = total
                bp[i] = j

    # Reconstruct lines.
    lines: list[list[StyledGrapheme]] = []
    i = 0
    while i < n:
        j = bp[i]
        line: list[StyledGrapheme] = []
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
    cells: Iterable[StyledGrapheme],
    wrap: TextWrap,
    width: int | None,
) -> list[list[StyledGrapheme]]:
    if width is not None and width <= 0:
        return []

    paragraphs = _split_paragraphs(cells)

    if wrap == "none" or width is None:
        return paragraphs

    result: list[list[StyledGrapheme]] = []
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
