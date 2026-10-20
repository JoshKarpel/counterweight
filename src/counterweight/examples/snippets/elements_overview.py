"""
Elements: Elements

A Div laying out a Canvas beside a column of Texts.
"""

import asyncio

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Canvas
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.geometry import Position
from counterweight.painters.pixels import HalfBlocks
from counterweight.painters.pixels import Pixels
from counterweight.styles.utilities import *

# --8<-- [start:example]

HEART_ART = (
    ".XX.XX.",
    "XXXXXXX",
    "XXXXXXX",
    ".XXXXX.",
    "..XXX..",
    "...X...",
)
HEART = Pixels.from_points(
    width=7,
    height=6,
    points={Position(x, y): rose_500 for y, line in enumerate(HEART_ART) for x, c in enumerate(line) if c == "X"},
    default=slate_900,
)


@component
def root() -> Div:
    return Div(
        style=row
        | align_children_center
        | gap(2)
        | border
        | border_lightrounded
        | pad_x(1)
        | content_color("slate", 900),
        children=(
            Canvas(painter=HalfBlocks(HEART)),
            Div(
                style=col | width(30),
                children=(
                    Text(
                        style=text_bg("slate", 900),
                        content=(
                            Chunk(content="Favorites", style=text_color("rose", 400).text_style),
                            Chunk(content=" · 3 new", style=text_color("slate", 500).text_style),
                        ),
                    ),
                    Text(
                        style=text_wrap_pretty | text_bg("slate", 900),
                        content="Everything you've starred, newest first.",
                    ),
                ),
            ),
        ),
    )


# --8<-- [end:example]


ROOTS = (root,)

# --8<-- [start:scenes]

from counterweight.examples.scenes import Still

STILLS = [Still("elements-overview", root(), (44, 5))]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(root()))
