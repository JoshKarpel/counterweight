from __future__ import annotations

from pathlib import Path
from typing import get_args

import pytest
import waxy

from counterweight.styles import BorderKind, CellStyle, Color, Style
from counterweight.styles import utilities as utilities_module
from mkdocs_hooks.utility_tables import describe_style, public_utilities, render_utility_tables

UTILITIES_PAGE = Path(__file__).parent.parent / "docs" / "styles" / "utilities.md"


def indent_by(n: int) -> Style:
    """Indent by `n` cells.

    Only the first paragraph is shown.
    """
    return Style(layout=waxy.Style(padding_left=waxy.Length(n)))  # pragma: never runs


def undocumented(n: int) -> Style:
    return Style(z=n)  # pragma: never runs


WIDE = Style(layout=waxy.Style(size_width=waxy.Length(7)))
HEAVY = Style(border_kind=BorderKind.Heavy)


def render(markdown: str, utilities: dict[str, object]) -> str:
    return render_utility_tables(markdown, utilities, colors=(), shades=())


@pytest.mark.parametrize(
    ("style", "expected"),
    [
        (Style(), []),
        (
            Style(layout=waxy.Style(padding_top=waxy.Length(3), flex_grow=2.0)),
            ["layout.flex_grow = 2.0", "layout.padding_top = Length(3)"],
        ),
        (
            Style(border_style=CellStyle(foreground=Color.from_hex("#fecdd3"), bold=True)),
            ["border_style.foreground = #fecdd3", "border_style.bold = True"],
        ),
        (Style(text_wrap="pretty", z=4), ["z = 4", "text_wrap = 'pretty'"]),
        (Style(border_kind=None), ["border_kind = None"]),
    ],
)
def test_describe_style_lists_each_field_the_style_sets(style: Style, expected: list[str]) -> None:
    assert describe_style(style) == expected


def test_marker_becomes_constants_table_then_functions_table() -> None:
    markdown = "Intro.\n\n<!-- utilities: wide indent_* -->\n\nOutro.\n"

    result = render(markdown, {"wide": WIDE, "indent_by": indent_by})

    assert result == "\n".join(
        [
            "Intro.",
            "",
            "| Utility | Sets |",
            "| --- | --- |",
            "| `wide` | `layout.size_width = Length(7)` |",
            "",
            "| Function | Description |",
            "| --- | --- |",
            "| `indent_by(n: int) -> Style` | Indent by `n` cells. |",
            "",
            "Outro.",
            "",
        ]
    )


def test_markdown_without_markers_is_left_alone() -> None:
    markdown = "Just prose about `wide`.\n"

    assert render(markdown, {"wide": WIDE}) == markdown


def test_utility_missing_from_every_marker_fails() -> None:
    with pytest.raises(ValueError, match=r"Missing: \['heavy'\]"):
        render("<!-- utilities: wide -->\n", {"wide": WIDE, "heavy": HEAVY})


def test_utility_claimed_by_two_markers_fails() -> None:
    with pytest.raises(ValueError, match=r"Repeated: \['wide'\]"):
        render("<!-- utilities: wide -->\n\n<!-- utilities: w* -->\n", {"wide": WIDE})


def test_pattern_matching_nothing_fails() -> None:
    with pytest.raises(ValueError, match="'typo_\\*' matches nothing"):
        render("<!-- utilities: wide typo_* -->\n", {"wide": WIDE})


def test_function_without_docstring_fails() -> None:
    with pytest.raises(ValueError, match="undocumented has no docstring"):
        render("<!-- utilities: undocumented -->\n", {"undocumented": undocumented})


def test_palette_has_a_swatch_per_color_and_shade() -> None:
    utilities: dict[str, object] = {
        "rose_200": Color.from_hex("#fecdd3"),
        "rose_900": Color.from_hex("#881337"),
        "sky_200": Color.from_hex("#bae6fd"),
        "sky_900": Color.from_hex("#0c4a6e"),
    }

    result = render_utility_tables("<!-- utilities-palette -->\n", utilities, colors=("rose", "sky"), shades=(200, 900))

    assert "<thead><tr><th></th><th>200</th><th>900</th></tr></thead>" in result
    assert (
        '<tr><th>sky</th><td><span class="swatch" style="background-color: #bae6fd" title="sky_200 #bae6fd"></span></td>'
        in result
    )
    assert result.count('class="swatch"') == 4


def test_public_utilities_leave_out_imports_and_type_aliases() -> None:
    names = public_utilities(utilities_module).keys()

    assert {"pad", "border_heavy", "rose_200"} <= names
    assert names.isdisjoint({"waxy", "lru_cache", "Style", "Color", "ColorName", "Shade", "Side"})


def test_utilities_page_covers_every_utility_once() -> None:
    rendered = render_utility_tables(
        UTILITIES_PAGE.read_text(),
        public_utilities(utilities_module),
        colors=get_args(utilities_module.ColorName),
        shades=get_args(utilities_module.Shade),
    )

    assert "<!-- utilities" not in rendered
