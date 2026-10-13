import asyncio
import sys

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

PARAGRAPH = "The quick brown fox jumps over the lazy dog, and then naps in the afternoon sun."

# --8<-- [start:wrap-in-pane]


@component
def wrap_in_pane() -> Div:
    return Div(
        style=row,
        children=(
            Text(style=length(16) | border, content="length(16)"),
            Div(
                style=col | fill(1) | border | pad_x(1),
                children=(Text(style=text_wrap_stable, content=PARAGRAPH),),
            ),
        ),
    )


# --8<-- [end:wrap-in-pane]

# --8<-- [start:wrap-in-row]


@component
def wrap_in_row() -> Div:
    return Div(
        style=row | gap(2) | border | border_heavy,
        children=(
            Text(style=text_wrap_stable | border, content=PARAGRAPH),
            Text(style=text_wrap_stable | border, content=PARAGRAPH),
        ),
    )


# --8<-- [end:wrap-in-row]

# --8<-- [start:justify]


@component
def justify() -> Div:
    return Div(
        style=col,
        children=(
            Text(style=text_justify_center | border, content="text_justify_center, stretched"),
            Text(
                style=text_justify_center | align_self_start | border,
                content="text_justify_center | align_self_start",
            ),
            Text(
                style=text_justify_center | text_wrap_balance | border,
                content="text_justify_center | text_wrap_balance centers each line of a paragraph "
                "within the width of the box",
            ),
        ),
    )


# --8<-- [end:justify]

# --8<-- [start:narrow]


@component
def narrow() -> Div:
    return Div(
        style=row | gap(2),
        children=(
            Div(
                style=col | width(20) | border | border_heavy,
                children=(Text(style=border, content="unwrapped text in a col"),),
            ),
            Div(
                style=row | width(20) | border | border_heavy,
                children=(Text(style=border, content="unwrapped text in a row"),),
            ),
        ),
    )


# --8<-- [end:narrow]

SCREENSHOTS = [
    ScreenshotSpec(wrap_in_pane(), "layout-text-wrap-in-pane", (60, 7)),
    ScreenshotSpec(wrap_in_row(), "layout-text-wrap-in-row", (60, 8)),
    ScreenshotSpec(justify(), "layout-text-justify", (50, 11)),
    ScreenshotSpec(narrow(), "layout-text-narrow", (48, 5)),
]


if __name__ == "__main__":
    roots = {root.__name__: root for root in (wrap_in_pane, wrap_in_row, justify, narrow)}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else wrap_in_pane()))
