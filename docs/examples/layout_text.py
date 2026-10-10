from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

PARAGRAPH = "The quick brown fox jumps over the lazy dog, and then naps in the afternoon sun."

# --8<-- [start:wrap-in-pane]


@component
def wrap_in_pane() -> Div:
    return Div(
        style=row | full,
        children=[
            Text(style=width(16) | border_light, content="sidebar"),
            Div(
                style=col | grow(1) | min_width(0) | border_light | pad_x(1),
                children=[Text(style=text_wrap_stable, content=PARAGRAPH)],
            ),
        ],
    )


# --8<-- [end:wrap-in-pane]

# --8<-- [start:wrap-in-row]


@component
def wrap_in_row() -> Div:
    return Div(
        style=col | full,
        children=[
            Div(
                style=row | gap(2) | border_heavy,
                children=[
                    Text(style=text_wrap_stable | text_bg("blue", 900), content=PARAGRAPH),
                    Text(style=text_wrap_stable | text_bg("green", 900), content=PARAGRAPH),
                ],
            ),
            Div(
                style=row | gap(2) | border_heavy,
                children=[
                    Text(style=text_wrap_stable | min_width(0) | text_bg("blue", 900), content=PARAGRAPH),
                    Text(style=text_wrap_stable | min_width(0) | text_bg("green", 900), content=PARAGRAPH),
                ],
            ),
        ],
    )


# --8<-- [end:wrap-in-row]

# --8<-- [start:justify]


@component
def justify() -> Div:
    return Div(
        style=col | full,
        children=[
            Text(style=text_justify_center | border_light, content="text_justify_center, stretched"),
            Text(
                style=text_justify_center | align_self_start | border_light,
                content="text_justify_center | align_self_start",
            ),
            Div(
                style=col | border_light,
                children=[
                    Text(
                        style=text_justify_center | text_wrap_balance,
                        content="text_justify_center | text_wrap_balance centers each line of a paragraph "
                        "within the width of the box",
                    ),
                ],
            ),
        ],
    )


# --8<-- [end:justify]

# --8<-- [start:narrow]


@component
def narrow() -> Div:
    return Div(
        style=row | gap(2) | full,
        children=[
            Div(
                style=col | width(20) | border_heavy,
                children=[Text(style=border_light, content="unwrapped text in a col")],
            ),
            Div(
                style=row | width(20) | border_heavy,
                children=[Text(style=border_light, content="unwrapped text in a row")],
            ),
        ],
    )


# --8<-- [end:narrow]

SCREENSHOTS = [
    ScreenshotSpec(wrap_in_pane, "layout-text-wrap-in-pane", (60, 7)),
    ScreenshotSpec(wrap_in_row, "layout-text-wrap-in-row", (60, 8)),
    ScreenshotSpec(justify, "layout-text-justify", (50, 11)),
    ScreenshotSpec(narrow, "layout-text-narrow", (60, 5)),
]
