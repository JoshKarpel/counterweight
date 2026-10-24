"""
Styles: Attributes

Text and borders drawn bold, dim, italic, underlined and struck through, and the `not_` forms that turn them off.
"""

import asyncio

from counterweight import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles import Style
from counterweight.styles.utilities import *

# --8<-- [start:example]

TEXT_ATTRIBUTES: tuple[tuple[str, Style], ...] = (
    ("text_bold", text_bold),
    ("text_dim", text_dim),
    ("text_italic", text_italic),
    ("text_underline", text_underline),
    ("text_strikethrough", text_strikethrough),
)

EMPHASIS = text_bold | text_italic | text_underline | text_color("amber", 300)


def bordered(utility: str, style: Style) -> Text:
    return Text(content=utility, style=border | border_heavy | border_color("sky", 400) | pad_x(1) | style)


@component
def attributes() -> Div:
    return Div(
        style=col | gap(1),
        children=(
            Div(
                style=col,
                children=tuple(Text(content=utility, style=style) for utility, style in TEXT_ATTRIBUTES),
            ),
            Div(
                style=col,
                children=(
                    Text(content="EMPHASIS", style=EMPHASIS),
                    Text(content="EMPHASIS | text_not_italic", style=EMPHASIS | text_not_italic),
                    Text(content="EMPHASIS | text_not_underline", style=EMPHASIS | text_not_underline),
                ),
            ),
            Div(
                style=row | gap(1),
                children=(
                    bordered("border_bold", border_bold),
                    bordered("border_dim", border_dim),
                    bordered("border_dim | border_not_dim", border_dim | border_not_dim),
                ),
            ),
        ),
    )


# --8<-- [end:example]


ROOTS = (attributes,)

# --8<-- [start:scenes]

from counterweight.examples.scenes import Still

STILLS = [
    Still("styles-attributes", attributes(), (62, 13)),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(attributes()))
