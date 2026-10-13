"""
Markdown rendering: a Markdown document as a tree of elements, parsed by
[markdown-it-py](https://markdown-it-py.readthedocs.io/) as CommonMark with GitHub's tables and strikethrough.

Rendering is a pure function of the source and the styles, so the result is cached,
and a component can render the same document on every render without parsing it again.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import waxy
from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode
from pygments.util import ClassNotFound

from counterweight.elements import Chunk, Div, Text
from counterweight.highlighting import DEFAULT_CODE_THEME, CodeTheme, code_block
from counterweight.styles import CellStyle, Style
from counterweight.styles.utilities import (
    align_self_start,
    border,
    border_collapse,
    border_color,
    border_left,
    border_light,
    border_top,
    col,
    display_grid,
    fill,
    gap_height,
    gap_width,
    grid_template_columns,
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

PARSER = MarkdownIt("commonmark").enable(["table", "strikethrough"])

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

    code_block: Style = pad_x(1)
    """Merged over the code theme's background, from [`code_style`][counterweight.highlighting.code_style]."""
    code_theme: CodeTheme = DEFAULT_CODE_THEME
    """The theme fenced code blocks are highlighted with, when their info string names a language Pygments knows."""

    thematic_break: Style = border_light | border_top | border_color("slate", 600)
    html_block: Style = Style(text_style=CellStyle(dim=True))
    """Raw HTML blocks, which are shown as written."""

    table: Style = align_self_start
    table_cell: Style = border_light | border | border_color("slate", 600)
    """The `Div` around each cell's text, which draws its border."""
    table_cell_text: Style = pad_x(1) | text_wrap_stable
    table_header: Style = Style(text_style=BOLD)
    """Merged over `table_cell_text` for the header row's cells."""

    emphasis: CellStyle = CellStyle(italic=True)
    strong: CellStyle = BOLD
    strikethrough: CellStyle = CellStyle(strikethrough=True)
    code_inline: CellStyle = text_color("rose", 300).text_style | text_bg("slate", 800).text_style
    link: CellStyle = CellStyle(underline=True) | text_color("sky", 300).text_style
    """Merged under the `CellStyle(link=...)` that makes a link's text a hyperlink to its destination."""
    image: CellStyle = CellStyle(italic=True) | text_color("sky", 300).text_style
    """An image's alt text, which links to the image, since a terminal can't show it."""


@lru_cache(maxsize=2**6)
def markdown(source: str, styles: MarkdownStyles = MarkdownStyles()) -> Div:
    """
    `source`, a Markdown document, as a `Div` of its blocks, drawn with `styles`.

    Links and images are [hyperlinks][counterweight.styles.CellStyle] to their destinations.
    Fenced code blocks are highlighted as the language their info string names,
    or shown as written if it names none or one [Pygments](https://pygments.org/) doesn't know.
    Raw HTML is shown as written, too.
    """
    document = SyntaxTreeNode(PARSER.parse(source))
    return Div(
        style=col | gap_height(styles.block_gap) | styles.document,
        children=blocks(document.children, styles, CellStyle(), list_depth=0),
    )


def blocks(nodes: list[SyntaxTreeNode], styles: MarkdownStyles, text: CellStyle, list_depth: int) -> list[Div | Text]:
    """The elements for a sequence of block nodes, whose inline text is styled over `text`."""
    return [block(node, styles, text, list_depth) for node in nodes]


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
        case "bullet_list" | "ordered_list":
            return list_block(node, styles, text, list_depth)
        case "fence" | "code_block":
            return fenced_code(node.content.removesuffix("\n"), node.info.split(maxsplit=1), styles)
        case "hr":
            return Div(style=styles.thematic_break)
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


def fenced_code(code: str, info: list[str], styles: MarkdownStyles) -> Text:
    """A code block, highlighted if its info string starts with a language Pygments knows."""
    language = info[0] if info else "text"
    try:
        return code_block(code, language, theme=styles.code_theme, style=styles.code_block)
    except ClassNotFound:
        return code_block(code, "text", theme=styles.code_theme, style=styles.code_block)


def list_block(node: SyntaxTreeNode, styles: MarkdownStyles, text: CellStyle, list_depth: int) -> Div:
    """
    A list, with each item's marker in a column beside its blocks.

    A list is loose, with a blank line between its items, when any of its paragraphs are separated by one,
    which markdown-it records by not hiding its items' paragraphs.
    """
    items = node.children
    if node.type == "ordered_list":
        start = int(node.attrs.get("start", 1))
        numbers = [f"{n}." for n in range(start, start + len(items))]
        marker_width = max(len(number) for number in numbers)
        markers = [number.rjust(marker_width) for number in numbers]
    else:
        markers = [styles.bullets[list_depth % len(styles.bullets)]] * len(items)

    is_loose = any(not child.hidden for item in items for child in item.children if child.type == "paragraph")
    gap = gap_height(styles.block_gap if is_loose else 0)
    return Div(
        style=col | gap,
        children=[
            Div(
                style=row | gap_width(1),
                children=[
                    Text(content=marker, style=styles.list_marker),
                    Div(
                        style=col | gap | fill(1),
                        children=blocks(item.children, styles, text, list_depth + 1),
                    ),
                ],
            )
            for marker, item in zip(markers, items, strict=True)
        ],
    )


def table(node: SyntaxTreeNode, styles: MarkdownStyles, text: CellStyle) -> Div:
    """A table, as a grid of bordered cells whose borders collapse into each other."""
    rows = [tr for section in node.children for tr in section.children]
    columns = len(rows[0].children)
    return Div(
        style=display_grid | grid_template_columns(*[waxy.AUTO] * columns) | border_collapse | styles.table,
        children=[
            # The border is on a Div around the Text, not on the Text itself,
            # because a grid row is too short for a wrapped Text with both a border and padding.
            Div(
                style=col | styles.table_cell,
                children=[
                    Text(
                        content=inline(cell, styles, text),
                        style=styles.table_cell_text
                        | (styles.table_header if cell.type == "th" else None)
                        | JUSTIFY[cell_alignment(cell)],
                    )
                ],
            )
            for tr in rows
            for cell in tr.children
        ],
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


def inline(node: SyntaxTreeNode, styles: MarkdownStyles, text: CellStyle) -> list[Chunk]:
    """The chunks of the inline content of a paragraph, heading, or table cell."""
    return [chunk for child in node.children for chunk in spans(child.children, styles, text)]


def spans(nodes: list[SyntaxTreeNode], styles: MarkdownStyles, text: CellStyle) -> list[Chunk]:
    return [chunk for node in nodes for chunk in span(node, styles, text)]


def span(node: SyntaxTreeNode, styles: MarkdownStyles, text: CellStyle) -> list[Chunk]:
    match node.type:
        case "text" | "html_inline":
            return [Chunk(content=node.content, style=text)]
        case "softbreak":
            return [Chunk(content=" ", style=text)]
        case "hardbreak":
            return [Chunk(content="\n", style=text)]
        case "code_inline":
            return [Chunk(content=node.content, style=text | styles.code_inline)]
        case "em":
            return spans(node.children, styles, text | styles.emphasis)
        case "strong":
            return spans(node.children, styles, text | styles.strong)
        case "s":
            return spans(node.children, styles, text | styles.strikethrough)
        case "link":
            return spans(node.children, styles, text | styles.link | CellStyle(link=str(node.attrs["href"]) or None))
        case "image":
            return spans(node.children, styles, text | styles.image | CellStyle(link=str(node.attrs["src"]) or None))
        case _:  # pragma: no cover, PARSER enables no rule that makes any other inline span
            raise ValueError(f"Unexpected Markdown inline span {node.type!r}")
