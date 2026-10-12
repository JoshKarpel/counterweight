from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING, assert_never

import waxy

from counterweight.elements import AnyElement, Chunk, Div, StyledChar, Text, text_cells
from counterweight.geometry import Region
from counterweight.styles.styles import CellStyle, Style, TextWrap, resolve_style

if TYPE_CHECKING:
    from counterweight.hooks.impls import NodeKey
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


def text_source(text: Text) -> TextSource:
    """Everything `text`'s measured size depends on, normalized so that equal sources compare equal."""
    content = text.content if isinstance(text.content, str) else tuple(text.content)
    return content, text.style.text_style, resolve_style(text.style).text_wrap


@dataclass(frozen=True, slots=True)
class CreateLeaf:
    key: NodeKey
    style: waxy.Style
    text: TextSource


@dataclass(frozen=True, slots=True)
class CreateContainer:
    key: NodeKey
    style: waxy.Style
    children: tuple[NodeKey, ...]


@dataclass(frozen=True, slots=True)
class SetStyle:
    key: NodeKey
    style: waxy.Style


@dataclass(frozen=True, slots=True)
class SetText:
    key: NodeKey
    text: TextSource


@dataclass(frozen=True, slots=True)
class ClearText:
    key: NodeKey


@dataclass(frozen=True, slots=True)
class SetChildren:
    key: NodeKey
    children: tuple[NodeKey, ...]


@dataclass(frozen=True, slots=True)
class Remove:
    key: NodeKey


type LayoutChange = CreateLeaf | CreateContainer | SetStyle | SetText | ClearText | SetChildren | Remove


def layout_changes(previous: ShadowNode | None, next: ShadowNode) -> list[LayoutChange]:
    """
    The changes that make a layout tree built from `previous` match `next`,
    pairing nodes by key as `update_shadow` paired them.

    Children come before their parents, so a parent's children exist when it's created or given them,
    and removals come last. Every node of an unmounted subtree is removed, not just its root,
    because taffy's remove detaches a node's children rather than removing them.
    """
    changes: list[LayoutChange] = []
    removals: list[LayoutChange] = []

    if previous is not None and previous.key != next.key:
        removals.extend(_removals(previous))
        previous = None

    _reconcile(previous, next, changes, removals)

    changes.extend(removals)
    return changes


def _reconcile(
    previous: ShadowNode | None,
    next: ShadowNode,
    changes: list[LayoutChange],
    removals: list[LayoutChange],
) -> None:
    """
    Appends the changes for `next`'s subtree, given the previous node it continues, if any.
    A subtree `update_shadow` reused is the previous node itself, frozen with all its descendants,
    so it has no changes and isn't descended into.
    """
    if next is previous:
        return

    key = next.key
    element = next.element
    style = layout_style(element.style)

    # Taffy discards a node's cached layout when its text or children are set, even to equal values,
    # so each is set only when it changed.
    match element:
        case Text():
            source = text_source(element)
            if previous is None:
                changes.append(CreateLeaf(key=key, style=style, text=source))
                return

            _append_style_change(previous, key, style, changes)
            match previous.element:
                case Text() as previous_text:
                    if text_source(previous_text) != source:
                        changes.append(SetText(key=key, text=source))
                case Div():
                    for child in previous.children:
                        removals.extend(_removals(child))
                    changes.append(SetText(key=key, text=source))
                case _ as unreachable:
                    assert_never(unreachable)
        case Div():
            previous_children = {} if previous is None else {child.key: child for child in previous.children}
            for child in next.children:
                _reconcile(previous_children.pop(child.key, None), child, changes, removals)
            for unmounted in previous_children.values():
                removals.extend(_removals(unmounted))

            child_keys = tuple(child.key for child in next.children)
            if previous is None:
                changes.append(CreateContainer(key=key, style=style, children=child_keys))
                return

            _append_style_change(previous, key, style, changes)
            match previous.element:
                case Text():
                    changes.append(ClearText(key=key))
                    changes.append(SetChildren(key=key, children=child_keys))
                case Div():
                    if tuple(child.key for child in previous.children) != child_keys:
                        changes.append(SetChildren(key=key, children=child_keys))
                case _ as unreachable:
                    assert_never(unreachable)
        case _ as unreachable:
            assert_never(unreachable)


def _append_style_change(previous: ShadowNode, key: NodeKey, style: waxy.Style, changes: list[LayoutChange]) -> None:
    previous_style = layout_style(previous.element.style)
    if previous_style is not style and previous_style != style:
        changes.append(SetStyle(key=key, style=style))


def _removals(unmounted: ShadowNode) -> Iterator[Remove]:
    return (Remove(key=node.key) for node in unmounted.walk())


@dataclass(frozen=True, slots=True)
class Layouts:
    """One frame's layouts: each visible element's, in paint order, and each visible node's, by key."""

    in_paint_order: tuple[tuple[AnyElement, ResolvedLayout], ...]
    by_key: Mapping[NodeKey, ResolvedLayout]


NO_LAYOUTS = Layouts(in_paint_order=(), by_key={})


@dataclass(eq=False, slots=True)
class LayoutTree:
    """
    The layout tree for one app, kept across frames so that taffy keeps the layout it cached
    for every node whose style, text and children are unchanged.
    Only `apply` and `compute` read or write its taffy nodes.
    """

    tree: waxy.TaffyTree[MeasurableText] = field(default_factory=waxy.TaffyTree)
    nodes: dict[NodeKey, waxy.NodeId] = field(default_factory=dict)

    def compute(
        self,
        changes: Iterable[LayoutChange],
        shadow: ShadowNode,
        available: waxy.AvailableSize,
    ) -> Layouts:
        """Apply `changes`, which make the tree match `shadow`, then lay it out."""
        self.apply(changes)

        root = self.nodes[shadow.key]
        self.tree.compute_layout(root, available, measure=_measure_text)

        shadows = {self.nodes[node.key]: node for node in shadow.walk()}
        in_paint_order: list[tuple[AnyElement, ResolvedLayout]] = []
        by_key: dict[NodeKey, ResolvedLayout] = {}
        for order, (node, position, layout) in enumerate(self.tree.absolute_layouts(root)):
            visible = shadows[node]
            resolved = _resolve_layout(position, layout, order)
            in_paint_order.append((visible.element, resolved))
            by_key[visible.key] = resolved

        return Layouts(in_paint_order=tuple(in_paint_order), by_key=by_key)

    def apply(self, changes: Iterable[LayoutChange]) -> None:
        nodes = self.nodes
        tree = self.tree
        for change in changes:
            match change:
                case CreateLeaf(key=key, style=style, text=text):
                    nodes[key] = tree.new_leaf_with_context(style, MeasurableText.of(text))
                case CreateContainer(key=key, style=style, children=children):
                    nodes[key] = tree.new_with_children(style, [nodes[child] for child in children])
                case SetStyle(key=key, style=style):
                    tree.set_style(nodes[key], style)
                case SetText(key=key, text=text):
                    tree.set_node_context(nodes[key], MeasurableText.of(text))
                case ClearText(key=key):
                    tree.set_node_context(nodes[key], None)
                case SetChildren(key=key, children=children):
                    tree.set_children(nodes[key], [nodes[child] for child in children])
                case Remove(key=key):
                    tree.remove(nodes.pop(key))
                case _ as unreachable:
                    assert_never(unreachable)


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

    cells: tuple[StyledChar, ...]
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
            size = self.sizes[width] = (max((len(line) for line in lines), default=0), len(lines))
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


def _min_content_width(cells: Iterable[StyledChar], wrap: TextWrap) -> int | None:
    """The widest word in `cells`, or `None` (unlimited) if they don't wrap."""
    if wrap == "none":
        return None

    return max(
        (len(word) for paragraph in _split_paragraphs(cells) for word in _extract_words_and_spaces(paragraph)[0]),
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


def _split_paragraphs(cells: Iterable[StyledChar]) -> list[list[StyledChar]]:
    paragraphs: list[list[StyledChar]] = []
    current: list[StyledChar] = []
    for cell in cells:
        if cell.char == "\n":
            paragraphs.append(current)
            current = []
        else:
            current.append(cell)
    paragraphs.append(current)
    return paragraphs


def _extract_words_and_spaces(
    paragraph: list[StyledChar],
) -> tuple[list[list[StyledChar]], list[list[StyledChar]]]:
    """Split a paragraph into (words, spaces).

    words[i] is a non-space run; spaces[i] is the space run between words[i] and words[i+1].
    Leading and trailing spaces are discarded.
    len(spaces) == len(words) - 1.
    """
    words: list[list[StyledChar]] = []
    spaces: list[list[StyledChar]] = []
    current_word: list[StyledChar] = []
    current_space: list[StyledChar] = []

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
    words: list[list[StyledChar]],
    spaces: list[list[StyledChar]],
    width: int,
) -> tuple[list[list[StyledChar]], list[list[StyledChar]]]:
    """Break any word longer than width into width-sized chunks.

    Space runs between chunks of the same word become [] (no space between hyphenated chunks).
    Returns (flat_words, flat_spaces) with len(flat_spaces) == len(flat_words) - 1.
    """
    flat_words: list[list[StyledChar]] = []
    flat_spaces: list[list[StyledChar]] = []

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

    return flat_words, flat_spaces


def _break_long_word(word: list[StyledChar], width: int) -> list[list[StyledChar]]:
    """Break a word that is longer than width into width-sized chunks, hyphenating all but the last."""
    if width <= 1:
        return [word[i : i + width] for i in range(0, len(word), width)]
    chunks: list[list[StyledChar]] = []
    i = 0
    while i < len(word):
        if i + width < len(word):
            hyphen = StyledChar(char="-", style=word[i + width - 2].style)
            chunks.append([*word[i : i + width - 1], hyphen])
            i += width - 1
        else:
            chunks.append(word[i : i + width])
            break
    return chunks


def _wrap_greedy(paragraph: list[StyledChar], width: int) -> list[list[StyledChar]]:
    words, spaces = _extract_words_and_spaces(paragraph)
    flat_words, flat_spaces = _flatten_long_words(words, spaces, width)

    lines: list[list[StyledChar]] = []
    current: list[StyledChar] = []
    pending_space: list[StyledChar] = []

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


def _greedy_line_count(flat_words: list[list[StyledChar]], flat_spaces: list[list[StyledChar]], width: int) -> int:
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
    flat_words: list[list[StyledChar]],
    flat_spaces: list[list[StyledChar]],
    width: int,
    target: int,
) -> list[list[StyledChar]]:
    """Greedy wrap with long-word breaking, targeting `target` width for line breaks."""
    lines: list[list[StyledChar]] = []
    current: list[StyledChar] = []
    pending_space: list[StyledChar] = []

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


def _wrap_balance(paragraph: list[StyledChar], width: int) -> list[list[StyledChar]]:
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


def _wrap_pretty(paragraph: list[StyledChar], width: int) -> list[list[StyledChar]]:
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
        space_prefix[idx] = space_prefix[idx - 1] + len(flat_spaces[idx - 1])

    def line_length(i: int, j: int) -> int:
        word_len = prefix[j] - prefix[i]
        space_len = space_prefix[j - 1] - space_prefix[i] if j > i + 1 else 0
        return word_len + space_len

    # dp[i] = min cost to break flat_words[i..n-1], bp[i] = best j for first break after i.
    # bp[i] is always set to j > i before use because _flatten_long_words ensures every word fits
    # within width, so each word can at minimum occupy its own line.
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
    lines: list[list[StyledChar]] = []
    i = 0
    while i < n:
        j = bp[i]
        line: list[StyledChar] = []
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
    cells: Iterable[StyledChar],
    wrap: TextWrap,
    width: int | None,
) -> list[list[StyledChar]]:
    if width is not None and width <= 0:
        return []

    paragraphs = _split_paragraphs(cells)

    if wrap == "none" or width is None:
        return paragraphs

    result: list[list[StyledChar]] = []
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
