from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:row]


@component
def row_defaults() -> Div:
    return Div(
        style=row | full,
        children=[
            Text(style=border_light, content="one"),
            Text(style=border_light, content="two two"),
            Text(style=border_light, content="three three three"),
        ],
    )


# --8<-- [end:row]

# --8<-- [start:col]


@component
def col_defaults() -> Div:
    return Div(
        style=col | full,
        children=[
            Text(style=border_light, content="one"),
            Text(style=border_light, content="two two"),
            Text(style=border_light, content="three three three"),
        ],
    )


# --8<-- [end:col]

WIDE = "this line is wider than the fifty-column screen it is drawn on"

# --8<-- [start:root-without-full]


@component
def root_without_full() -> Div:
    return Div(
        style=col | border_heavy,
        children=[Text(content="root: col | border_heavy"), Text(content=WIDE)],
    )


# --8<-- [end:root-without-full]

# --8<-- [start:root-with-full]


@component
def root_with_full() -> Div:
    return Div(
        style=col | full | border_heavy,
        children=[Text(content="root: col | full | border_heavy"), Text(content=WIDE)],
    )


# --8<-- [end:root-with-full]

LONG = "a line of text much longer than half the row"

# --8<-- [start:automatic-minimum]


@component
def automatic_minimum() -> Div:
    return Div(
        style=col | full,
        children=[
            Div(
                style=row | border_heavy,
                children=[
                    Text(style=grow(1) | border_light, content=LONG),
                    Text(style=grow(1) | border_light, content=LONG),
                ],
            ),
            Div(
                style=row | border_heavy,
                children=[
                    Text(style=grow(1) | min_width(0) | border_light, content=LONG),
                    Text(style=grow(1) | min_width(0) | border_light, content=LONG),
                ],
            ),
        ],
    )


# --8<-- [end:automatic-minimum]

PARAGRAPH = "Text stays on one line unless its style sets a wrap mode, however narrow its box."

# --8<-- [start:wrapping]


@component
def wrapping() -> Div:
    return Div(
        style=row | full,
        children=[
            Div(style=col | width(24) | border_light, children=[Text(content=PARAGRAPH)]),
            Div(style=col | width(24) | border_light, children=[Text(style=text_wrap_stable, content=PARAGRAPH)]),
        ],
    )


# --8<-- [end:wrapping]

SCREENSHOTS = [
    ScreenshotSpec(row_defaults, "layout-defaults-row", (50, 5)),
    ScreenshotSpec(col_defaults, "layout-defaults-col", (50, 11)),
    ScreenshotSpec(root_without_full, "layout-root-without-full", (50, 5)),
    ScreenshotSpec(root_with_full, "layout-root-with-full", (50, 5)),
    ScreenshotSpec(automatic_minimum, "layout-automatic-minimum", (60, 10)),
    ScreenshotSpec(wrapping, "layout-wrapping", (60, 7)),
]
