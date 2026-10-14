from typing import ClassVar

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pygments.style import Style as PygmentsStyle
from pygments.styles import get_style_by_name
from pygments.token import Comment, Keyword, Name, Token, _TokenType
from pygments.util import ClassNotFound

from counterweight.highlighting import cell_style_for_token, code_block, code_style, highlight
from counterweight.styles import UNSET, CellStyle, Color
from counterweight.styles.utilities import pad_x


class LoudStyle(PygmentsStyle):
    background_color = "#102030"
    styles: ClassVar[dict[_TokenType, str]] = {
        Token: "#aabbcc",
        Keyword: "bold italic underline #ff0000 bg:#00ff00",
        Comment: "ansiblue",
    }


def contents(code: str, language: str = "python") -> list[str]:
    return [chunk.content for chunk in highlight(code, language)]


@given(st.text(alphabet=st.characters(blacklist_characters="\r", blacklist_categories=["Cs"])))
def test_chunks_spell_out_the_code_with_tabs_expanded(code: str) -> None:
    assert "".join(contents(code)) == code.expandtabs(4)


def test_tabs_expand_to_tab_size() -> None:
    assert "".join(chunk.content for chunk in highlight("\tx", "python", tab_size=2)) == "  x"


def test_no_newline_is_added_or_stripped() -> None:
    assert "".join(contents("\nx = 1\n\n")) == "\nx = 1\n\n"
    assert "".join(contents("x")) == "x"


def test_no_chunk_is_empty() -> None:
    assert all(contents("def f():\n    pass\n"))


def test_tokens_are_styled_by_the_theme() -> None:
    (keyword, *_) = highlight("def f(): pass", "python", theme="monokai")

    expected = get_style_by_name("monokai").style_for_token(Keyword)["color"]
    assert keyword.content == "def"
    assert keyword.style.foreground == Color.from_hex(expected)


def test_language_aliases_work() -> None:
    assert highlight("x = 1", "py") == highlight("x = 1", "python")


def test_unknown_language_raises() -> None:
    with pytest.raises(ClassNotFound):
        highlight("x", "not-a-real-language")


def test_unknown_theme_raises() -> None:
    with pytest.raises(ClassNotFound):
        highlight("x", "python", theme="not-a-real-theme")


def test_pygments_style_class_is_a_theme() -> None:
    (keyword, *_) = highlight("def f(): pass", "python", theme=LoudStyle)

    assert keyword.style == CellStyle(
        foreground=Color.from_hex("#ff0000"),
        background=Color.from_hex("#00ff00"),
        bold=True,
        italic=True,
        underline=True,
    )


def test_what_the_theme_does_not_set_is_left_unset() -> None:
    style = cell_style_for_token(LoudStyle, Name)

    assert style == CellStyle(foreground=Color.from_hex("#aabbcc"))
    assert style.background is UNSET
    assert style.bold is UNSET


def test_token_type_the_theme_does_not_name_is_styled_as_its_nearest_named_ancestor() -> None:
    assert cell_style_for_token(LoudStyle, Keyword.Unnamed.Deeper) == cell_style_for_token(LoudStyle, Keyword)


def test_yaml_highlights_although_its_lexer_makes_token_types_no_theme_names() -> None:
    assert "".join(contents("key: value\n", "yaml")) == "key: value\n"


def test_ansi_color_names_become_their_hex_approximations() -> None:
    expected = LoudStyle.style_for_token(Comment)["color"]

    assert cell_style_for_token(LoudStyle, Comment).foreground == Color.from_hex(expected)


def test_code_style_draws_on_the_theme_background_in_its_text_color() -> None:
    background = Color.from_hex("#102030")

    style = code_style(LoudStyle)

    assert style.content_color == background
    assert style.padding_color == background
    assert style.text_style == CellStyle(foreground=Color.from_hex("#aabbcc"), background=background)


def test_code_style_reads_a_shorthand_background() -> None:
    class ShorthandStyle(PygmentsStyle):
        background_color = "#123"

    assert code_style(ShorthandStyle).content_color == Color.from_hex("#112233")


def test_code_block_merges_its_style_over_the_code_style() -> None:
    block = code_block("x = 1", "python", theme=LoudStyle, style=pad_x(2))

    assert block.content == highlight("x = 1", "python", theme=LoudStyle)
    assert block.style == code_style(LoudStyle) | pad_x(2)


def test_code_block_without_a_style_is_drawn_in_the_code_style() -> None:
    assert code_block("x = 1", "python", theme=LoudStyle).style == code_style(LoudStyle)
