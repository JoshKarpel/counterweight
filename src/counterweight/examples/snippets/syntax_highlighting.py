"""
Rich text: Syntax highlighting

Source code highlighted for its language.
"""

import asyncio

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.highlighting import code_block
from counterweight.styles.utilities import *

# --8<-- [start:example]

SOURCE = '''\
@component
def greeting(name: str) -> Text:
    """Say hello."""
    return Text(content=f"Hello, {name}!")
'''


@component
def root() -> Div:
    return Div(
        style=col | gap(1),
        children=tuple(
            Div(
                style=col,
                children=(
                    Text(content=f" {theme} ", style=text_color("slate", 400)),
                    code_block(SOURCE.rstrip("\n"), "python", theme=theme, style=pad(1)),
                ),
            )
            for theme in ("github-dark", "monokai", "solarized-light")
        ),
    )


# --8<-- [end:example]


ROOTS = (root,)

# --8<-- [start:scenes]

from counterweight.examples.scenes import Still

STILLS = [Still("syntax-highlighting", root(), (50, 24))]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(root()))
