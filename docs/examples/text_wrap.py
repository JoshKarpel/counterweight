from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.styles.styles import Style, TextWrap
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:example]

SAMPLE = "It was the best of times, it was the worst of times, it was the age of wisdom, it was the age of foolishness."

WRAP_STYLE: dict[TextWrap, Style] = {
    "none": text_wrap_none,
    "stable": text_wrap_stable,
    "pretty": text_wrap_pretty,
    "balance": text_wrap_balance,
}


@component
def wrap_pane(mode: TextWrap) -> Div:
    return Div(
        style=grow(1) | min_width(0) | col | border | pad_x(1),
        children=[
            Text(
                content=f" {mode} ",
                style=position_absolute | inset_top(-1) | inset_left(1),
            ),
            Text(
                content=SAMPLE,
                style=grow(1) | WRAP_STYLE[mode],
            ),
        ],
    )


@component
def root() -> Div:
    return Div(
        style=col | full,
        children=[
            Div(
                style=row | grow(1),
                children=[wrap_pane(mode) for mode in WRAP_STYLE],
            ),
        ],
    )


# --8<-- [end:example]

SCREENSHOTS = [ScreenshotSpec(root, "text-wrap", (120, 14))]
