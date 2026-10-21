"""
Layout: Absolute positioning

Boxes taken out of the flow and placed by insets from their parent's padding box.
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
                style=row | fill(1) | border | border_heavy | center_children,
                children=(
                    Text(
                        style=position_absolute | inset_left(3) | inset_top(3),
                        content="position_absolute | inset_left(3) | inset_top(3)",
                    ),
                    Text(
                        style=inset_center_center | margin_left(-2) | margin_top(-4),
                        content="inset_center_center | margin_left(-2) | margin_top(-4)",
                    ),
                    Text(
                        style=inset_bottom_right | margin_bottom(4),
                        content="inset_bottom_right | margin_bottom(4)",
                    ),
                    Text(
                        style=inset_top_left,
                        content="inset_top_left",
                    ),
                    Text(
                        style=inset_top_center,
                        content="inset_top_center",
                    ),
                    Text(
                        style=inset_top_right,
                        content="inset_top_right",
                    ),
                    Text(
                        style=inset_center_left,
                        content="inset_center_left",
                    ),
                    Text(
                        style=inset_center_center,
                        content="inset_center_center",
                    ),
                    Text(
                        style=inset_center_right,
                        content="inset_center_right",
                    ),
                    Text(
                        style=inset_bottom_left,
                        content="inset_bottom_left",
                    ),
                    Text(
                        style=inset_bottom_center,
                        content="inset_bottom_center",
                    ),
                    Text(
                        style=inset_bottom_right,
                        content="inset_bottom_right",
                    ),
                ),
            ),
        ),
    )


# --8<-- [end:example]


ROOTS = (root,)

# --8<-- [start:scenes]

from counterweight.examples.scenes import Still

STILLS = [Still("absolute-positioning-insets", root(), (60, 25))]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(root()))
