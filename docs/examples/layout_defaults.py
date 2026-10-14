import asyncio
import sys

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:row]


@component
def row_defaults() -> Div:
    return Div(
        style=row,
        children=(
            Text(style=border, content="one"),
            Text(style=border, content="two two"),
            Text(style=border, content="three three three"),
        ),
    )


# --8<-- [end:row]

# --8<-- [start:col]


@component
def col_defaults() -> Div:
    return Div(
        style=col,
        children=(
            Text(style=border, content="one"),
            Text(style=border, content="two two"),
            Text(style=border, content="three three three"),
        ),
    )


# --8<-- [end:col]

WIDE = "this line is wider than the fifty-column screen it is drawn on"

# --8<-- [start:root]


@component
def root_fills_screen() -> Div:
    return Div(
        style=col | border | border_heavy,
        children=(Text(content="root: col | border | border_heavy"), Text(content=WIDE)),
    )


# --8<-- [end:root]

LONG = "a line of text much longer than half the row"

# --8<-- [start:automatic-minimum]


@component
def automatic_minimum() -> Div:
    return Div(
        style=col,
        children=(
            Div(
                style=row | border | border_heavy,
                children=(
                    Text(style=grow(1) | border, content=LONG),
                    Text(style=grow(1) | border, content=LONG),
                ),
            ),
            Div(
                style=row | border | border_heavy,
                children=(
                    Text(style=fill(1) | border, content=LONG),
                    Text(style=fill(1) | border, content=LONG),
                ),
            ),
        ),
    )


# --8<-- [end:automatic-minimum]

PARAGRAPH = "Text stays on one line unless its style sets a wrap mode, however narrow its box."

# --8<-- [start:wrapping]


@component
def wrapping() -> Div:
    return Div(
        style=col,
        children=(
            Text(style=width(24) | border, content=PARAGRAPH),
            Text(style=width(24) | border | overflow_hidden, content=PARAGRAPH),
            Text(style=width(24) | border | text_wrap_stable, content=PARAGRAPH),
        ),
    )


# --8<-- [end:wrapping]

SCREENSHOTS = [
    ScreenshotSpec(row_defaults(), "layout-defaults-row", (50, 5)),
    ScreenshotSpec(col_defaults(), "layout-defaults-col", (50, 11)),
    ScreenshotSpec(root_fills_screen(), "layout-root", (50, 5)),
    ScreenshotSpec(automatic_minimum(), "layout-automatic-minimum", (60, 10)),
    ScreenshotSpec(wrapping(), "layout-wrapping", (84, 12)),
]


if __name__ == "__main__":
    roots = {
        root.__name__: root for root in (row_defaults, col_defaults, root_fills_screen, automatic_minimum, wrapping)
    }
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else row_defaults()))
