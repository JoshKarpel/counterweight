"""
Layout: The box model

A box's content, padding, border and margin, each in its own color.
"""

import asyncio

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.styles.utilities import *

# --8<-- [start:example]


@component
def root() -> Div:
    return Div(
        style=col,
        children=(
            Div(
                style=fill(1)
                | content_color("green", 500)
                | padding_color("orange", 500)
                | pad_x(2)
                | pad_y(1)
                | border
                | border_lightrounded
                | border_bg("blue", 500)
                | margin_color("red", 500)
                | margin_x(2)
                | margin_y(1)
            ),
        ),
    )


# --8<-- [end:example]


ROOTS = (root,)

# --8<-- [start:scenes]

from counterweight.examples.scenes import Still

STILLS = [Still("box-model", root(), (30, 10))]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(root()))
