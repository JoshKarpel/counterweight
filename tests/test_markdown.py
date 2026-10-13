import io
from collections.abc import Iterator
from textwrap import dedent

import pytest

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit, Screenshot
from counterweight.elements import AnyElement, Chunk, Div, Text
from counterweight.highlighting import code_block, highlight
from counterweight.markdown import MarkdownStyles, markdown
from counterweight.styles import CellStyle
from counterweight.styles.utilities import col, display_none, pad_x, text_justify_left, text_wrap_none


async def render(source: str, width: int, styles: MarkdownStyles = MarkdownStyles()) -> str:
    @component
    def root() -> Div:
        return Div(style=col, children=(markdown(dedent(source), styles),))

    capture = io.StringIO()
    await app(
        root(),
        headless=True,
        dimensions=(width, 40),
        autopilot=[Screenshot.to_stream(capture, ansi=False), Quit()],
        check_purity=True,
    )
    return "\n".join(line.rstrip() for line in capture.getvalue().rstrip().split("\n"))


def walk(element: AnyElement) -> Iterator[AnyElement]:
    yield element
    if isinstance(element, Div):
        for child in element.children:
            assert isinstance(child, Div | Text)
            yield from walk(child)


def texts(source: str, styles: MarkdownStyles = MarkdownStyles()) -> list[Text]:
    return [element for element in walk(markdown(dedent(source), styles)) if isinstance(element, Text)]


def chunks(source: str, styles: MarkdownStyles = MarkdownStyles()) -> list[Chunk]:
    (text,) = texts(source, styles)
    assert not isinstance(text.content, str)
    return list(text.content)


def chunk_for(source: str, content: str) -> Chunk:
    (chunk,) = (chunk for chunk in chunks(source) if chunk.content == content)
    return chunk


async def test_paragraphs_wrap_and_are_separated_by_a_blank_line() -> None:
    source = """\
        The quick brown fox
        jumps over the lazy dog.

        Second paragraph.
        """

    assert await render(source, 20) == dedent(
        """\
        The quick brown fox
        jumps over the lazy
        dog.

        Second paragraph."""
    )


async def test_hard_break_starts_a_new_line() -> None:
    assert await render("one  \ntwo\n", 20) == "one\ntwo"


async def test_block_gap_sets_the_rows_between_blocks() -> None:
    assert await render("one\n\ntwo\n", 20, MarkdownStyles(block_gap=0)) == "one\ntwo"


@pytest.mark.parametrize("level", range(1, 7))
def test_each_heading_level_has_its_own_style(level: int) -> None:
    (heading,) = texts(f"{'#' * level} Title\n")

    assert heading.style == getattr(MarkdownStyles(), f"heading_{level}")
    assert heading.content == (Chunk(content="Title"),)


def test_nested_emphasis_merges_styles() -> None:
    assert chunk_for("***both***\n", "both").style == CellStyle(bold=True, italic=True)


@pytest.mark.parametrize(
    ("source", "content", "field"),
    [
        ("*a*\n", "a", "emphasis"),
        ("**a**\n", "a", "strong"),
        ("~~a~~\n", "a", "strikethrough"),
        ("~a~\n", "a", "strikethrough"),
        ("`a`\n", "a", "code_inline"),
    ],
)
def test_inline_spans_are_styled(source: str, content: str, field: str) -> None:
    assert chunk_for(source, content).style == getattr(MarkdownStyles(), field)


@pytest.mark.parametrize("source", ["$a*b*c$\n", "$$a*b*c$$\n"])
def test_inline_math_is_shown_as_written(source: str) -> None:
    assert chunks(f"x {source}") == [Chunk(content="x "), Chunk(content="a*b*c", style=MarkdownStyles().math_inline)]


@pytest.mark.parametrize(
    "source",
    [
        "It costs $5 and $10.",
        "Between $20,000 and $30,000.",
        "$x$5",
        "$ x $",
    ],
)
def test_dollars_that_pandoc_would_not_parse_as_math_are_text(source: str) -> None:
    assert chunks(f"{source}\n") == [Chunk(content=source)]


async def test_display_math_is_shown_as_written_and_centered() -> None:
    source = """\
        $$
        a^2 + b^2
        $$
        """

    assert await render(source, 15) == "   a^2 + b^2"
    (math,) = texts(source)
    assert math.style == MarkdownStyles().math_block


async def test_display_math_label_is_to_its_right() -> None:
    assert await render("$$x = 1$$ (eq)\n", 15) == "   x = 1   (eq)"


def test_link_text_is_a_hyperlink_to_its_destination() -> None:
    link = chunk_for("see [the docs](https://example.com/docs) here\n", "the docs")

    assert link.style == MarkdownStyles().link | CellStyle(link="https://example.com/docs")


def test_link_destination_is_percent_encoded() -> None:
    assert chunk_for("[x](https://example.com/é)\n", "x").style.link == "https://example.com/%C3%A9"


def test_autolink_is_a_hyperlink() -> None:
    assert chunk_for("<https://example.com>\n", "https://example.com").style.link == "https://example.com"


@pytest.mark.parametrize(
    ("text", "destination"),
    [
        ("https://example.com/a", "https://example.com/a"),
        ("www.example.com", "http://www.example.com"),
        ("someone@example.com", "mailto:someone@example.com"),
    ],
)
def test_bare_url_is_a_hyperlink(text: str, destination: str) -> None:
    link = chunk_for(f"see {text} here\n", text)

    assert link.style == MarkdownStyles().link | CellStyle(link=destination)


@pytest.mark.parametrize("text", ["www.example.com", "https://example.com", "someone@example.com"])
def test_link_whose_text_is_a_bare_url_links_to_its_destination(text: str) -> None:
    link = chunk_for(f"see [{text}](https://example.com/docs) here\n", text)

    assert link.style == MarkdownStyles().link | CellStyle(link="https://example.com/docs")


def test_empty_link_destination_is_not_a_hyperlink() -> None:
    assert chunk_for("[x]()\n", "x").style.link is None


def test_unsafe_link_is_left_as_text() -> None:
    assert [chunk.content for chunk in chunks("[x](javascript:alert(1))\n")] == ["[x](javascript:alert(1))"]


def test_image_alt_text_is_a_hyperlink_to_the_image() -> None:
    image = chunk_for("![a cat](cat.png)\n", "a cat")

    assert image.style == MarkdownStyles().image | CellStyle(link="cat.png")


def test_inline_html_is_shown_as_written() -> None:
    assert "".join(chunk.content for chunk in chunks("a <b>b</b>\n")) == "a <b>b</b>"


async def test_html_block_is_shown_as_written() -> None:
    assert await render("<div>\nhi\n</div>\n", 20) == "<div>\nhi\n</div>"


async def test_block_quote_has_a_bar_and_styles_its_text() -> None:
    source = "> one\n>\n> two\n"

    assert await render(source, 20) == "│ one\n│\n│ two"
    assert {chunk.style for text in texts(source) for chunk in text.content if isinstance(chunk, Chunk)} == {
        MarkdownStyles().block_quote_text
    }


async def test_tight_list_has_no_gaps_and_nests() -> None:
    source = """\
        - one
        - two
          - nested
        - three
        """

    assert await render(source, 20) == dedent(
        """\
        • one
        • two
          ◦ nested
        • three"""
    )


async def test_loose_list_has_gaps_between_items() -> None:
    assert await render("- one\n\n- two\n", 20) == "• one\n\n• two"


async def test_list_item_text_wraps_beside_its_marker() -> None:
    assert await render("- one two three four\n", 12) == "• one two\n  three four"


async def test_bullets_cycle_with_depth() -> None:
    source = """\
        - a
          - b
            - c
              - d
        """

    assert await render(source, 20, MarkdownStyles(bullets=("*", "-"))) == dedent(
        """\
        * a
          - b
            * c
              - d"""
    )


async def test_ordered_list_counts_from_its_start_with_markers_aligned_right() -> None:
    source = "".join(f"{n}. item\n" for n in range(9, 12))

    assert await render(source, 20) == " 9. item\n10. item\n11. item"


async def test_task_boxes_take_the_place_of_bullets() -> None:
    source = """\
        - [x] done
        - [ ] not done
        - plain
        """

    assert await render(source, 20) == "☑ done\n☐ not done\n• plain"


async def test_task_boxes_follow_numbers() -> None:
    assert await render("1. [x] done\n2. [ ] not done\n", 20) == "1. ☑ done\n2. ☐ not done"


async def test_task_boxes_are_configurable() -> None:
    styles = MarkdownStyles(unchecked_task="[ ]", checked_task="[x]")

    assert await render("- [x] a\n- [ ] b\n", 20, styles) == "[x] a\n[ ] b"


def test_checked_task_box_is_styled() -> None:
    checked, _, unchecked, _ = texts("- [x] a\n- [ ] b\n")

    styles = MarkdownStyles()
    assert checked.style == styles.list_marker | styles.checked_task_marker
    assert unchecked.style == styles.list_marker


@pytest.mark.parametrize("kind", ["note", "tip", "important", "warning", "caution"])
def test_alert_is_styled_by_its_kind(kind: str) -> None:
    alert = markdown(f"> [!{kind.upper()}]\n> body\n").children[0]
    assert isinstance(alert, Div)
    title = alert.children[0]

    styles = MarkdownStyles()
    kind_style = getattr(styles, f"alert_{kind}")
    assert alert.style == col | styles.alert | kind_style
    assert title == Text(content=(Chunk(content=kind.title()),), style=styles.alert_title | kind_style)


async def test_alert_shows_its_title_above_its_blocks() -> None:
    assert await render("> [!tip]\n> one\n>\n> two\n", 20) == "│ Tip\n│ one\n│\n│ two"


async def test_unknown_alert_kind_is_a_block_quote() -> None:
    assert await render("> [!HINT]\n> body\n", 20) == "│ [!HINT] body"


async def test_footnotes_are_numbered_in_the_order_they_are_referenced() -> None:
    source = """\
        b[^b] a[^a] b[^b]

        [^a]: A.
        [^b]: B.
        """

    assert await render(source, 12) == dedent(
        """\
        b[1] a[2]
        b[1]

        ────────────
        [1] B.
        [2] A."""
    )


def test_footnote_numbers_are_styled() -> None:
    paragraph, number, definition = texts("a[^x]\n\n[^x]: X.\n")

    footnote_ref = MarkdownStyles().footnote_ref
    assert paragraph.content == (Chunk(content="a"), Chunk(content="[1]", style=footnote_ref))
    assert number.content == (Chunk(content="[1]", style=footnote_ref),)
    assert definition.content == (Chunk(content="X."),)


async def test_footnote_ending_in_code_drops_its_back_link() -> None:
    source = """\
        a[^x]

        [^x]:
            ```
            code
            ```
        """

    assert await render(source, 10) == "a[1]\n\n──────────\n[1]  code"


async def test_footnote_paragraphs_are_separated_by_a_blank_line() -> None:
    source = """\
        a[^x]

        [^x]: one

            two
        """

    assert await render(source, 10) == "a[1]\n\n──────────\n[1] one\n\n    two"


def test_front_matter_is_dim_yaml() -> None:
    (front_matter, _) = texts("---\nkey: value\n---\n\nbody\n")

    styles = MarkdownStyles()
    assert front_matter == code_block(
        "key: value", "yaml", theme=styles.code_theme, style=styles.code_block | styles.front_matter
    )


async def test_front_matter_can_be_hidden() -> None:
    assert await render("---\nkey: value\n---\n\nbody\n", 20, MarkdownStyles(front_matter=display_none)) == "body"


async def test_fenced_code_is_highlighted_in_its_language() -> None:
    (block,) = texts("```python\nx = 1\n```\n")

    styles = MarkdownStyles()
    assert block == code_block("x = 1", "python", theme=styles.code_theme, style=styles.code_block)


@pytest.mark.parametrize("info", ["", "not-a-real-language", "  "])
def test_fenced_code_without_a_known_language_is_plain(info: str) -> None:
    (block,) = texts(f"```{info}\nx = 1\n```\n")

    assert block.content == highlight("x = 1", "text")


def test_info_string_words_after_the_language_are_ignored() -> None:
    (block,) = texts("```python title=x.py\nx = 1\n```\n")

    assert block.content == highlight("x = 1", "python")


def test_code_theme_is_used_for_fences() -> None:
    (block,) = texts("```python\nx = 1\n```\n", MarkdownStyles(code_theme="monokai"))

    assert block.content == highlight("x = 1", "python", theme="monokai")


async def test_indented_code_keeps_its_lines() -> None:
    assert await render("p\n\n    a\n      b\n", 20) == "p\n\n a\n   b"


async def test_thematic_break_is_a_line_across() -> None:
    assert await render("a\n\n---\n\nb\n", 5) == "a\n\n─────\n\nb"


async def test_table_collapses_borders_and_aligns_columns() -> None:
    source = """\
        | Left | Middle | Right |
        |:-----|:------:|------:|
        | a | b | c |
        """

    assert await render(source, 40) == dedent(
        """\
        ┌──────┬────────┬───────┐
        │ Left │ Middle │ Right │
        ├──────┼────────┼───────┤
        │ a    │    b   │     c │
        └──────┴────────┴───────┘"""
    )


def test_table_header_cells_are_styled() -> None:
    header, body = texts("| h |\n|---|\n| b |\n")

    styles = MarkdownStyles()
    assert header.style == styles.table_cell_text | styles.table_header | text_justify_left
    assert body.style == styles.table_cell_text | text_justify_left


async def test_table_cells_wrap_when_the_table_is_narrow() -> None:
    source = """\
        | a | b |
        |---|---|
        | one two | x |
        """

    assert await render(source, 11) == dedent(
        """\
        ┌─────┬───┐
        │ a   │ b │
        ├─────┼───┤
        │ one │ x │
        │ two │   │
        └─────┴───┘"""
    )


def test_styles_are_merged_over_the_layout() -> None:
    document = markdown("a\n", MarkdownStyles(paragraph=text_wrap_none | pad_x(1)))

    (paragraph,) = document.children
    assert isinstance(paragraph, Text)
    assert paragraph.style == text_wrap_none | pad_x(1)


def test_rendering_is_cached() -> None:
    assert markdown("# a\n") is markdown("# a\n")
