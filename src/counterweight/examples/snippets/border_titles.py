"""
Cookbook: Border titles

A title drawn over a box's top border.
"""

import asyncio

from counterweight import app
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
            Div(
                style=row | fill(1) | center_children | border | border_lightrounded | pad(1),
                children=(
                    Text(
                        style=position_absolute | inset_left(1) | inset_top(-1) | clip_to_border,
                        content=" Top-Left Title ",
                    ),
                    Text(
                        style=inset_top_center | inset_top(-1) | clip_to_border,
                        content=" Top-Center Title ",
                    ),
                    Text(
                        style=position_absolute | inset_top(-1) | inset_right(1) | clip_to_border,
                        content=" Top-Right Title ",
                    ),
                    Text(
                        style=position_absolute | inset_bottom(-1) | inset_left(1) | clip_to_border,
                        content=" Bottom-Left Title ",
                    ),
                    Text(
                        style=inset_bottom_center | inset_bottom(-1) | clip_to_border,
                        content=" Bottom-Center Title ",
                    ),
                    Text(
                        style=position_absolute | inset_bottom(-1) | inset_right(1) | clip_to_border,
                        content=" Bottom-Right Title ",
                    ),
                    Text(
                        content="Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
                    ),
                ),
            ),
        ),
    )


# --8<-- [end:example]


ROOTS = (root,)

# --8<-- [start:scenes]

from counterweight.examples.scenes import Still

STILLS = [Still("border-titles", root(), (70, 5))]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(root()))
