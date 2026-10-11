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
            Div(
                style=row
                | grow(1)
                | justify_children_center
                | align_children_center
                | border
                | border_lightrounded
                | pad(1),
                children=[
                    Text(
                        style=position_absolute | inset_left(1) | inset_top(-1),
                        content=" Top-Left Title ",
                    ),
                    Text(
                        style=inset_top_center | inset_top(-1),
                        content=" Top-Center Title ",
                    ),
                    Text(
                        style=position_absolute | inset_top(-1) | inset_right(1),
                        content=" Top-Right Title ",
                    ),
                    Text(
                        style=position_absolute | inset_bottom(-1) | inset_left(1),
                        content=" Bottom-Left Title ",
                    ),
                    Text(
                        style=inset_bottom_center | inset_bottom(-1),
                        content=" Bottom-Center Title ",
                    ),
                    Text(
                        style=position_absolute | inset_bottom(-1) | inset_right(1),
                        content=" Bottom-Right Title ",
                    ),
                    Text(
                        content="Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
                    ),
                ],
            )
        ],
    )


# --8<-- [end:example]

SCREENSHOTS = [ScreenshotSpec(root, "border-titles", (70, 5))]
