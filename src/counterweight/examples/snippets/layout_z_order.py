"""
Layout: Z order

Overlapping boxes, drawn in the order their z values set.
"""

import asyncio

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles.utilities import *

# --8<-- [start:example]


@component
def root() -> Div:
    return Div(
        style=col,
        children=(
            Text(
                style=z(1)
                | position_absolute
                | inset_left(6)
                | inset_top(6)
                | border
                | border_lightrounded
                | margin(1)
                | margin_color("purple", 600),
                content="z = +1",
            ),
            Text(
                style=z(0)
                | position_absolute
                | inset_left(4)
                | inset_top(3)
                | border
                | border_lightrounded
                | margin(1)
                | margin_color("teal", 600),
                content="z =  0",
            ),
            Text(
                style=z(-1)
                | position_absolute
                | inset_left(0)
                | inset_top(0)
                | border
                | border_lightrounded
                | margin(1)
                | margin_color("red", 600),
                content="z = -1",
            ),
            Text(
                style=z(2)
                | position_absolute
                | inset_left(13)
                | inset_top(3)
                | border
                | border_lightrounded
                | margin(1)
                | margin_color("amber", 600),
                content="z = +2",
            ),
        ),
    )


# --8<-- [end:example]


ROOTS = (root,)

# --8<-- [start:scenes]

from counterweight.examples.scenes import Still

STILLS = [Still("z", root(), (24, 11))]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(root()))
