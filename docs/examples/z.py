from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:example]


@component
def root() -> Div:
    return Div(
        style=col,
        children=[
            Text(
                style=z(1)
                | position_absolute
                | inset_left(6)
                | inset_top(6)
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
                | border_lightrounded
                | margin(1)
                | margin_color("amber", 600),
                content="z = +2",
            ),
        ],
    )


# --8<-- [end:example]

SCREENSHOTS = [ScreenshotSpec(root, "z", (30, 15))]
