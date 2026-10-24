"""
Styles: Ending a line with an ellipsis

Lines too long for their box, clipped and ended with an ellipsis.
"""

import asyncio

from counterweight import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles import Style
from counterweight.styles.utilities import *

# --8<-- [start:example]

PATHS = (
    "README.md",
    "src/counterweight/_layout.py",
    "docs/styles/text-wrapping.md",
    "tests/日本語/e2eテスト.py",
)

STATUS = content_color("slate", 800)


def files(title: str, overflow: Style) -> Div:
    return Div(
        style=col | width(20) | border | border_light | overflow_hidden,
        children=(
            Text(content=title, style=text_bold),
            *(Text(content=path, style=overflow) for path in PATHS),
        ),
    )


@component
def root() -> Div:
    return Div(
        style=col | gap(1) | pad_x(1),
        children=(
            Div(
                style=row | gap(2),
                children=(files("clip", text_overflow_clip), files("ellipsis", text_overflow_ellipsis)),
            ),
            Div(
                style=row | width(42),
                children=(
                    Text(
                        content="~/projects/counterweight/src/counterweight/styles/_styles.py",
                        style=grow(1) | overflow_x_hidden | text_overflow_ellipsis | STATUS,
                    ),
                    Text(content=" Ln 12, Col 4 ", style=STATUS | text_color("sky", 300)),
                ),
            ),
        ),
    )


# --8<-- [end:example]


ROOTS = (root,)

# --8<-- [start:scenes]

from counterweight.examples.scenes import Still

STILLS = [Still("text-overflow", root(), (46, 9))]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(root()))
