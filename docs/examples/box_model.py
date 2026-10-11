from counterweight.components import component
from counterweight.elements import Div
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:example]


@component
def root() -> Div:
    return Div(
        style=col,
        children=[
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
            )
        ],
    )


# --8<-- [end:example]

SCREENSHOTS = [ScreenshotSpec(root, "box-model", (30, 10))]
