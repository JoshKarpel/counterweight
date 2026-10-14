"""
Markdown rendering: a Markdown document as a tree of elements, parsed by
[markdown-it-py](https://markdown-it-py.readthedocs.io/) as GitHub Flavored Markdown, with math and YAML front matter.

Rendering is a pure function of the source and the styles, so the result is cached,
and a component can render the same document on every render without parsing it again.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import waxy
from markdown_it import MarkdownIt
from markdown_it.parser_inline import RuleFuncInlineType
from markdown_it.rules_inline import StateInline
from markdown_it.tree import SyntaxTreeNode
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.gfm import gfm_plugin
from pygments.util import ClassNotFound

from counterweight.elements import Chunk, Div, Text
from counterweight.events import InputEvent, InputResponse, Receiver
from counterweight.handlers import scroll_on_wheel
from counterweight.highlighting import DEFAULT_CODE_THEME, CodeTheme, code_block, code_style
from counterweight.styles import CellStyle, Style
from counterweight.styles.utilities import (
    border,
    border_collapse,
    border_color,
    border_left,
    border_light,
    border_top,
    col,
    default,
    display_grid,
    fill,
    gap_height,
    gap_width,
    grid_template_columns,
    grow,
    min_width,
    overflow_x_scroll,
    pad_left,
    pad_x,
    row,
    text_bg,
    text_color,
    text_justify_center,
    text_justify_left,
    text_justify_right,
    text_wrap_stable,
)

# Math is enabled here rather than by `gfm_plugin(dollarmath=True)`, whose defaults parse `$5 and $10` as math.
# These options follow Pandoc's rule instead (no space just inside the dollars, no digit right after the closing one),
# which keeps prices as text.
PARSER = (
    MarkdownIt("commonmark")
    .use(gfm_plugin, front_matter=True)
    .use(dollarmath_plugin, allow_space=False, allow_digits=False, double_inline=True, allow_blank_lines=False)
)


def unmatched_when_silent(rule: RuleFuncInlineType) -> RuleFuncInlineType:
    """
    `rule`, but never matching in silent mode, which is how markdown-it skips a token inside a link's text.

    mdit-py-plugins' GFM autolink rules match in silent mode without moving past the match,
    so `see [www.example.com](https://example.com)` loops forever skipping the same token.
    Autolinks are never made inside a link's text anyway, so skipping them a character at a time loses nothing.
    (An image's description is parsed on its own, so it can hold autolinks; `span` draws them as plain text.)
    """

    def wrapped(state: StateInline, silent: bool) -> bool:
        return not silent and rule(state, silent)

    return wrapped


def wrap_gfm_autolink_rules(parser: MarkdownIt) -> None:
    """Replace `parser`'s GFM autolink rules with `unmatched_when_silent` ones."""
    rules = dict(zip(parser.inline.ruler.get_active_rules(), parser.inline.ruler.getRules(""), strict=True))
    for name in ("gfm_autolink_www", "gfm_autolink_protocol", "gfm_autolink_email"):
        parser.inline.ruler.at(name, unmatched_when_silent(rules[name]))


wrap_gfm_autolink_rules(PARSER)

BOLD = CellStyle(bold=True)


@dataclass(frozen=True, slots=True, kw_only=True)
class MarkdownStyles:
    """
    How [`markdown`][counterweight.markdown.markdown] draws each kind of Markdown block and inline span.

    Each block becomes an element styled by its `Style` here, merged over the layout `markdown` gives it.
    Each inline span's `CellStyle` is merged over the text around it, so `***both***` is bold and italic.
    Pass the fields you want to change: `MarkdownStyles(paragraph=text_wrap_pretty)`.
    """

    document: Style = Style()
    """The `Div` holding the document's blocks."""
    block_gap: int = 1
    """Rows between blocks: in the document, a block quote, and a loose list and its items."""

    paragraph: Style = text_wrap_stable
    heading_1: Style = text_wrap_stable | Style(text_style=BOLD) | text_color("sky", 300)
    heading_2: Style = text_wrap_stable | Style(text_style=BOLD) | text_color("sky", 400)
    heading_3: Style = text_wrap_stable | Style(text_style=BOLD) | text_color("sky", 500)
    heading_4: Style = text_wrap_stable | Style(text_style=BOLD)
    heading_5: Style = text_wrap_stable | Style(text_style=BOLD)
    heading_6: Style = text_wrap_stable | Style(text_style=BOLD | CellStyle(dim=True))

    block_quote: Style = border_light | border_left | border_color("slate", 500) | pad_left(1)
    block_quote_text: CellStyle = CellStyle(italic=True) | text_color("slate", 400).text_style
    """Merged over the text of everything inside a block quote."""

    list_marker: Style = text_color("slate", 400)
    bullets: tuple[str, ...] = ("•", "◦", "▪")
    """The bullet for each depth of nested bullet lists, starting again from the first past the last."""
    unchecked_task: str = "☐"
    """The box of a task list item that isn't done, which takes the place of its bullet, or follows its number."""
    checked_task: str = "☑"
    """The box of a task list item that is done."""
    checked_task_marker: Style = text_color("emerald", 400)
    """Merged over `list_marker` for the box of a task list item that is done."""

    alert: Style = border_light | border_left | pad_left(1)
    """A GitHub alert (`> [!NOTE]`), which is a block quote with a title."""
    alert_title: Style = text_wrap_stable | Style(text_style=BOLD)
    alert_note: Style = border_color("blue", 400) | text_color("blue", 400)
    """
    Merged over `alert` for a `NOTE` alert, and over `alert_title` for its title,
    so its border color colors the alert's bar and its text color the title.
    """
    alert_tip: Style = border_color("green", 400) | text_color("green", 400)
    """Merged over `alert` and `alert_title` for a `TIP` alert, like `alert_note`."""
    alert_important: Style = border_color("violet", 400) | text_color("violet", 400)
    """Merged over `alert` and `alert_title` for an `IMPORTANT` alert, like `alert_note`."""
    alert_warning: Style = border_color("amber", 400) | text_color("amber", 400)
    """Merged over `alert` and `alert_title` for a `WARNING` alert, like `alert_note`."""
    alert_caution: Style = border_color("red", 400) | text_color("red", 400)
    """Merged over `alert` and `alert_title` for a `CAUTION` alert, like `alert_note`."""

    code_block: Style = pad_x(1)
    """
    The box around a code block, merged over the code theme's background
    (from [`code_style`][counterweight.highlighting.code_style])
    and a layout that scrolls the block sideways with the wheel when a line is wider than the box.
    """
    code_block_text: Style = default
    """
    The `Text` of a code block's lines, inside `code_block`, merged over the code theme's background and text color.
    Pass `text_wrap_stable` to wrap long lines instead of scrolling them.
    """
    code_theme: CodeTheme = DEFAULT_CODE_THEME
    """The theme fenced code blocks are highlighted with, when their info string names a language Pygments knows."""
    front_matter: Style = default
    """
    Merged over `code_block` for the document's YAML front matter, which is highlighted as YAML.
    Pass `display_none` to hide it.
    """
    front_matter_text: Style = Style(text_style=CellStyle(dim=True))
    """Merged over `code_block_text` for the front matter's text."""

    thematic_break: Style = border_light | border_top | border_color("slate", 600)
    math_block: Style = text_wrap_stable | text_justify_center | text_color("violet", 300)
    """Display math, between `$$` lines, which is shown as written, since a terminal can't typeset it."""
    math_label: Style = text_color("slate", 400)
    """The label of display math written `$$...$$ (label)`, shown as `(label)` to its right."""
    html_block: Style = Style(text_style=CellStyle(dim=True))
    """Raw HTML blocks, which are shown as written."""

    table: Style = default
    """
    The box around a table, merged over a layout that scrolls the table sideways with the wheel
    when it's wider than the box with its cells wrapped as narrow as their words allow.
    """
    table_grid: Style = default
    """The grid of the table's cells, inside `table`, which is only as wide as its cells need."""
    table_cell: Style = border_light | border | border_color("slate", 600)
    """The `Div` around each cell's text, which draws its border."""
    table_cell_text: Style = pad_x(1) | text_wrap_stable
    table_header: Style = Style(text_style=BOLD)
    """Merged over `table_cell_text` for the header row's cells."""

    emphasis: CellStyle = CellStyle(italic=True)
    strong: CellStyle = BOLD
    strikethrough: CellStyle = CellStyle(strikethrough=True)
    code_inline: CellStyle = text_color("rose", 300).text_style | text_bg("slate", 800).text_style
    math_inline: CellStyle = text_color("violet", 300).text_style
    """Math within a line, between `$`s or `$$`s, which is shown as written."""
    link: CellStyle = CellStyle(underline=True) | text_color("sky", 300).text_style
    """Merged under the `CellStyle(link=...)` that makes a link's text a hyperlink to its destination."""
    image: CellStyle = CellStyle(italic=True) | text_color("sky", 300).text_style
    """An image's alt text, which links to the image, since a terminal can't show it."""

    footnote_ref: CellStyle = text_color("sky", 300).text_style
    """A footnote's number, `[1]`, where it's referenced and beside its definition."""
    footnotes: Style = border_light | border_top | border_color("slate", 600)
    """The footnotes' definitions, which follow the rest of the document, numbered in the order they're referenced."""


@lru_cache(maxsize=2**6)
def markdown(source: str, styles: MarkdownStyles = MarkdownStyles(), keeps_line_breaks: bool = False) -> Div:
    """
    `source`, a Markdown document, as a `Div` of its blocks, drawn with `styles`.

    Links, bare URLs, and images are [hyperlinks][counterweight.styles.CellStyle] to their destinations.
    Fenced code blocks are highlighted as the language their info string names,
    or shown as written if it names none or one [Pygments](https://pygments.org/) doesn't know.
    Code blocks and tables wider than the space they're given scroll sideways with the wheel.
    Math and raw HTML are shown as written, too.

    Parameters:
        keeps_line_breaks: Whether a line break inside a paragraph breaks the line where it's drawn,
            as GitHub's comments and chat apps draw what people type,
            rather than joining the lines with a space, as CommonMark does.
    """
    tokens = PARSER.parse(source)
    if keeps_line_breaks:
        for token in tokens:
            for child in token.children or ():
                if child.type == "softbreak":
                    child.type = "hardbreak"
    document = SyntaxTreeNode(tokens)
    return Div(
        style=col | gap_height(styles.block_gap) | styles.document,
        children=blocks(document.children, styles, CellStyle(), list_depth=0),
    )


def blocks(
    nodes: list[SyntaxTreeNode], styles: MarkdownStyles, text: CellStyle, list_depth: int
) -> tuple[Div | Text, ...]:
    """The elements for a sequence of block nodes, whose inline text is styled over `text`."""
    return tuple(block(node, styles, text, list_depth) for node in nodes)


def block(node: SyntaxTreeNode, styles: MarkdownStyles, text: CellStyle, list_depth: int) -> Div | Text:
    match node.type:
        case "paragraph":
            return Text(content=inline(node, styles, text), style=styles.paragraph)
        case "heading":
            return Text(content=inline(node, styles, text), style=heading_style(styles, node.tag))
        case "blockquote":
            return Div(
                style=col | gap_height(styles.block_gap) | styles.block_quote,
                children=blocks(node.children, styles, text | styles.block_quote_text, list_depth),
            )
        case "alert":
            return alert(node, styles, text, list_depth)
        case "bullet_list" | "ordered_list":
            return list_block(node, styles, text, list_depth)
        case "footnote_block":
            return footnotes(node, styles, text, list_depth)
        case "fence" | "code_block":
            return fenced_code(node.content.removesuffix("\n"), node.info.split(maxsplit=1), styles)
        case "front_matter":
            return scrolling_box(
                code_style(styles.code_theme) | styles.code_block | styles.front_matter,
                code_block(
                    node.content,
                    "yaml",
                    theme=styles.code_theme,
                    style=styles.code_block_text | styles.front_matter_text,
                ),
            )
        case "hr":
            return Div(style=styles.thematic_break)
        case "math_block":
            return Text(content=node.content.strip("\n"), style=styles.math_block)
        case "math_block_label":
            return Div(
                style=row | gap_width(1),
                children=(
                    Text(content=node.content.strip("\n"), style=fill(1) | styles.math_block),
                    Text(content=f"({node.info})", style=styles.math_label),
                ),
            )
        case "html_block":
            return Text(content=node.content.removesuffix("\n"), style=styles.html_block)
        case "table":
            return table(node, styles, text)
        case _:  # pragma: no cover, PARSER enables no rule that makes any other block
            raise ValueError(f"Unexpected Markdown block {node.type!r}")


def heading_style(styles: MarkdownStyles, tag: str) -> Style:
    match tag:
        case "h1":
            return styles.heading_1
        case "h2":
            return styles.heading_2
        case "h3":
            return styles.heading_3
        case "h4":
            return styles.heading_4
        case "h5":
            return styles.heading_5
        case _:
            return styles.heading_6


def fenced_code(code: str, info: list[str], styles: MarkdownStyles) -> Div:
    """A code block, highlighted if its info string starts with a language Pygments knows."""
    language = info[0] if info else "text"
    try:
        text = code_block(code, language, theme=styles.code_theme, style=styles.code_block_text)
    except ClassNotFound:
        text = code_block(code, "text", theme=styles.code_theme, style=styles.code_block_text)
    return scrolling_box(code_style(styles.code_theme) | styles.code_block, text)


def scrolling_box(style: Style, child: Div | Text) -> Div:
    """
    `child` in a box that scrolls sideways with the wheel when it's wider than the box,
    as GitHub's styles scroll a code block or a table with `overflow: auto`.

    Only its horizontal overflow scrolls, so its automatic minimum height is still `child`'s,
    and it isn't squeezed shorter than its lines in a column too short for the document.
    """
    return Div(style=row | overflow_x_scroll | style, on_input=scroll_on_wheel_if_scrollable, children=(child,))


SCROLL_ON_WHEEL = scroll_on_wheel()


def scroll_on_wheel_if_scrollable(event: InputEvent, receiver: Receiver) -> InputResponse:
    """
    `scroll_on_wheel`, or nothing on a box whose style turned its scrolling off,
    on which `scroll_on_wheel` would raise `ValueError`.
    """
    return None if receiver.scroll is None else SCROLL_ON_WHEEL(event, receiver)


def alert(node: SyntaxTreeNode, styles: MarkdownStyles, text: CellStyle, list_depth: int) -> Div:
    """A GitHub alert: its title, then its blocks, beside a bar colored for its kind."""
    title, *body = node.children
    kind = alert_style(styles, node.meta["kind"])
    return Div(
        style=col | styles.alert | kind,
        children=(
            Text(content=inline(title, styles, text), style=styles.alert_title | kind),
            Div(style=col | gap_height(styles.block_gap), children=blocks(body, styles, text, list_depth)),
        ),
    )


def alert_style(styles: MarkdownStyles, kind: str) -> Style:
    match kind:
        case "NOTE":
            return styles.alert_note
        case "TIP":
            return styles.alert_tip
        case "IMPORTANT":
            return styles.alert_important
        case "WARNING":
            return styles.alert_warning
        case _:
            return styles.alert_caution


def list_block(node: SyntaxTreeNode, styles: MarkdownStyles, text: CellStyle, list_depth: int) -> Div:
    """
    A list, with each item's markers in columns beside its blocks.

    A list is loose, with a blank line between its items, when any of its paragraphs are separated by one,
    which markdown-it records by not hiding its items' paragraphs.
    """
    items = node.children
    is_ordered = node.type == "ordered_list"
    if is_ordered:
        start = int(node.attrs.get("start", 1))
        markers = right_aligned([f"{n}." for n in range(start, start + len(items))])
    else:
        markers = [styles.bullets[list_depth % len(styles.bullets)]] * len(items)

    is_loose = any(not child.hidden for item in items for child in item.children if child.type == "paragraph")
    gap = gap_height(styles.block_gap if is_loose else 0)
    return Div(
        style=col | gap,
        children=tuple(
            marked(
                item_markers(marker, item.meta.get("checked"), is_ordered, styles),
                blocks(item.children, styles, text, list_depth + 1),
                gap,
            )
            for marker, item in zip(markers, items, strict=True)
        ),
    )


def item_markers(marker: str, checked: bool | None, is_ordered: bool, styles: MarkdownStyles) -> tuple[Text, ...]:
    """A list item's bullet or number, and its box if it's a task, which takes the place of a bullet."""
    if checked is None:
        return (Text(content=marker, style=styles.list_marker),)

    box = (
        Text(content=styles.checked_task, style=styles.list_marker | styles.checked_task_marker)
        if checked
        else Text(content=styles.unchecked_task, style=styles.list_marker)
    )
    return (Text(content=marker, style=styles.list_marker), box) if is_ordered else (box,)


def footnotes(node: SyntaxTreeNode, styles: MarkdownStyles, text: CellStyle, list_depth: int) -> Div:
    """
    The footnotes' definitions, each beside the number its references show.

    A footnote that doesn't end in a paragraph has its `footnote_anchor`s as blocks of their own, which are dropped,
    as they are from the end of a paragraph by `inline`.
    """
    numbers = right_aligned([footnote_number(footnote) for footnote in node.children])
    return Div(
        style=col | styles.footnotes,
        children=tuple(
            marked(
                (Text(content=(Chunk(content=number, style=styles.footnote_ref),)),),
                blocks(
                    [child for child in footnote.children if child.type != "footnote_anchor"], styles, text, list_depth
                ),
                gap_height(styles.block_gap),
            )
            for number, footnote in zip(numbers, node.children, strict=True)
        ),
    )


def footnote_number(node: SyntaxTreeNode) -> str:
    """A footnote's number, counting from one in the order the footnotes are first referenced."""
    return f"[{node.meta['id'] + 1}]"


def right_aligned(markers: list[str]) -> list[str]:
    width = max(len(marker) for marker in markers)
    return [marker.rjust(width) for marker in markers]


def marked(markers: tuple[Text, ...], children: tuple[Div | Text, ...], gap: Style) -> Div:
    """`children` in a column beside `markers`, as a list item is beside its bullet."""
    return Div(
        style=row | gap_width(1),
        children=(*markers, Div(style=col | gap | grow(1) | min_width(0), children=children)),
    )


def table(node: SyntaxTreeNode, styles: MarkdownStyles, text: CellStyle) -> Div:
    """A table, as a grid of bordered cells whose borders collapse into each other."""
    rows = [tr for section in node.children for tr in section.children]
    columns = len(rows[0].children)
    return scrolling_box(styles.table, grid(rows, columns, styles, text))


def grid(rows: list[SyntaxTreeNode], columns: int, styles: MarkdownStyles, text: CellStyle) -> Div:
    """A table's `rows` of cells, as a grid with a column for each of their `columns`."""
    return Div(
        style=display_grid | grid_template_columns(*[waxy.AUTO] * columns) | border_collapse | styles.table_grid,
        children=tuple(
            # The border is on a Div around the Text, not on the Text itself,
            # because a grid row is too short for a wrapped Text with both a border and padding.
            Div(
                style=col | styles.table_cell,
                children=(
                    Text(
                        content=inline(cell, styles, text),
                        style=styles.table_cell_text
                        | (styles.table_header if cell.type == "th" else None)
                        | JUSTIFY[cell_alignment(cell)],
                    ),
                ),
            )
            for tr in rows
            for cell in tr.children
        ),
    )


type Alignment = Literal["left", "center", "right"]

JUSTIFY: dict[Alignment, Style] = {
    "left": text_justify_left,
    "center": text_justify_center,
    "right": text_justify_right,
}


def cell_alignment(cell: SyntaxTreeNode) -> Alignment:
    """A table cell's alignment, from the `text-align` that markdown-it puts in its `style` attribute."""
    match cell.attrs.get("style"):
        case "text-align:center":
            return "center"
        case "text-align:right":
            return "right"
        case _:
            return "left"


def inline(node: SyntaxTreeNode, styles: MarkdownStyles, text: CellStyle) -> tuple[Chunk, ...]:
    """
    The chunks of the inline content of a paragraph, heading, or table cell.

    The last paragraph of a footnote also holds `footnote_anchor`s beside its inline content:
    links back to the footnote's references, which a terminal can't follow.
    They have no children, so they add no chunks.
    """
    return tuple(chunk for child in node.children for chunk in spans(child.children, styles, text))


def spans(nodes: list[SyntaxTreeNode], styles: MarkdownStyles, text: CellStyle) -> tuple[Chunk, ...]:
    return tuple(chunk for node in nodes for chunk in span(node, styles, text))


def span(node: SyntaxTreeNode, styles: MarkdownStyles, text: CellStyle) -> tuple[Chunk, ...]:
    match node.type:
        case "text" | "html_inline":
            return (Chunk(content=node.content, style=text),)
        case "softbreak":
            return (Chunk(content=" ", style=text),)
        case "hardbreak":
            return (Chunk(content="\n", style=text),)
        case "math_inline" | "math_inline_double":
            return (Chunk(content=node.content, style=text | styles.math_inline),)
        case "code_inline":
            return (Chunk(content=node.content, style=text | styles.code_inline),)
        case "em":
            return spans(node.children, styles, text | styles.emphasis)
        case "strong":
            return spans(node.children, styles, text | styles.strong)
        case "s":
            return spans(node.children, styles, text | styles.strikethrough)
        case "link" if is_in_image(node):
            return spans(node.children, styles, text)
        case "link":
            return spans(node.children, styles, text | styles.link | CellStyle(link=str(node.attrs["href"]) or None))
        case "image":
            return spans(node.children, styles, text | styles.image | CellStyle(link=str(node.attrs["src"]) or None))
        case "footnote_ref":
            return (Chunk(content=footnote_number(node), style=text | styles.footnote_ref),)
        case _:  # pragma: no cover, PARSER enables no rule that makes any other inline span
            raise ValueError(f"Unexpected Markdown inline span {node.type!r}")


def is_in_image(node: SyntaxTreeNode) -> bool:
    """
    Whether `node` is part of an image's description, whose text links to the image,
    so a link in it, written out or a bare URL, is drawn as the rest of the description is.
    """
    return node.parent is not None and (node.parent.type == "image" or is_in_image(node.parent))
