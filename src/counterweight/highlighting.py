"""
Syntax highlighting: source code as styled `Chunk`s, colored by a [Pygments](https://pygments.org/) lexer and style.

Highlighting is a pure function of its arguments, so the results are cached,
and a component can highlight the same code on every render without lexing it again.
"""

from __future__ import annotations

from functools import lru_cache

from pygments.lexers import get_lexer_by_name
from pygments.style import Style as PygmentsStyle
from pygments.styles import get_style_by_name
from pygments.token import Token
from pygments.token import _TokenType

from counterweight.elements import Chunk
from counterweight.elements import Text
from counterweight.styles import UNSET
from counterweight.styles import CellStyle
from counterweight.styles import Color
from counterweight.styles import Style
from counterweight.styles.utilities import default

# A Pygments style, by name (any of `pygments.styles.get_all_styles()`) or as a `pygments.style.Style` subclass.
type CodeTheme = str | type[PygmentsStyle]

DEFAULT_CODE_THEME: CodeTheme = "github-dark"


@lru_cache(maxsize=2**8)
def highlight(code: str, language: str, theme: CodeTheme = DEFAULT_CODE_THEME, tab_size: int = 4) -> tuple[Chunk, ...]:
    """
    `code` as chunks styled by the tokens a Pygments lexer finds in it.

    `language` is any name or alias of a Pygments lexer, such as `python`, `py`, or `toml`;
    `theme` is a Pygments style, by name (any of `pygments.styles.get_all_styles()`)
    or as a `pygments.style.Style` subclass, which is how to define your own.
    An unknown language or theme raises `pygments.util.ClassNotFound`.
    Tabs are expanded to `tab_size` columns.

    The theme's colors are set only where it sets them, so the rest come from the `Text`'s `text_style`:
    put the chunks in a `Text` styled by [`code_style`][counterweight.highlighting.code_style]
    to draw them on the theme's background.
    """
    lexer = get_lexer_by_name(language, stripnl=False, ensurenl=False, tabsize=tab_size)
    pygments_style = resolve_theme(theme)
    return tuple(
        Chunk(content=text, style=cell_style_for_token(pygments_style, token))
        for token, text in lexer.get_tokens(code)
        if text
    )


@lru_cache(maxsize=2**6)
def code_style(theme: CodeTheme = DEFAULT_CODE_THEME) -> Style:
    """The theme's background and its plain text's style, for a `Text` holding chunks from `highlight`."""
    pygments_style = resolve_theme(theme)
    background = Color.from_hex(pygments_style.background_color)
    return Style(
        content_color=background,
        padding_color=background,
        text_style=CellStyle(background=background) | cell_style_for_token(pygments_style, Token.Text),
    )


def code_block(
    code: str,
    language: str,
    theme: CodeTheme = DEFAULT_CODE_THEME,
    style: Style = default,
    tab_size: int = 4,
) -> Text:
    """
    A `Text` of `code` highlighted as `language`, on the theme's background,
    with `style` merged over [`code_style`][counterweight.highlighting.code_style].
    """
    return Text(content=highlight(code, language, theme, tab_size), style=code_style(theme) | style)


@lru_cache(maxsize=2**6)
def resolve_theme(theme: CodeTheme) -> type[PygmentsStyle]:
    """The Pygments style `theme` names, or `theme` itself if it's already one."""
    return get_style_by_name(theme) if isinstance(theme, str) else theme


@lru_cache(maxsize=2**12)
def cell_style_for_token(pygments_style: type[PygmentsStyle], token: _TokenType) -> CellStyle:
    """
    How `pygments_style` draws `token`, or its nearest ancestor that the style knows,
    since a lexer can make token types no style names, like YAML's `Token.Literal.Scalar.Plain`.

    Pygments leaves a color it doesn't set as `None` (and gives a hex approximation for an ANSI color name),
    and a cell style leaves it `UNSET`, so the text's own style shows through.
    """
    styled = next(ancestor for ancestor in reversed(token.split()) if pygments_style.styles_token(ancestor))
    definition = pygments_style.style_for_token(styled)
    color = definition["color"]
    background = definition["bgcolor"]
    return CellStyle(
        foreground=Color.from_hex(color) if color else UNSET,
        background=Color.from_hex(background) if background else UNSET,
        bold=definition["bold"] or UNSET,
        italic=definition["italic"] or UNSET,
        underline=definition["underline"] or UNSET,
    )


__all__ = [
    "DEFAULT_CODE_THEME",
    "CodeTheme",
    "code_block",
    "code_style",
    "highlight",
]
