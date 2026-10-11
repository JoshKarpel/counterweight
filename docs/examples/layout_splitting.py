import waxy

from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.styles import Style
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:equal-flex]


@component
def equal_flex() -> Div:
    return Div(
        style=row | full,
        children=[
            Text(style=grow(1) | min_width(0) | border, content="grow(1) | min_width(0)"),
            Text(style=grow(1) | min_width(0) | border, content="grow(1) | min_width(0)"),
            Text(style=grow(1) | min_width(0) | border, content="grow(1) | min_width(0)"),
        ],
    )


# --8<-- [end:equal-flex]

# --8<-- [start:equal-grid]


@component
def equal_grid() -> Div:
    return Div(
        style=display_grid | grid_template_columns(waxy.Fraction(1), waxy.Fraction(1), waxy.Fraction(1)) | full,
        children=[
            Text(style=border, content="Fraction(1)"),
            Text(style=border, content="Fraction(1)"),
            Text(style=border, content="Fraction(1)"),
        ],
    )


# --8<-- [end:equal-grid]

# --8<-- [start:sidebar-flex]


@component
def sidebar_flex() -> Div:
    return Div(
        style=row | full,
        children=[
            Text(style=width(20) | border, content="width(20)"),
            Text(style=grow(1) | min_width(0) | border, content="grow(1) | min_width(0)"),
        ],
    )


# --8<-- [end:sidebar-flex]

# --8<-- [start:sidebar-grid]


@component
def sidebar_grid() -> Div:
    return Div(
        style=display_grid | grid_template_columns(waxy.Length(20), waxy.Fraction(1)) | full,
        children=[
            Text(style=border, content="Length(20)"),
            Text(style=border, content="Fraction(1)"),
        ],
    )


# --8<-- [end:sidebar-grid]

# --8<-- [start:ratio-flex]


@component
def ratio_flex() -> Div:
    return Div(
        style=row | full,
        children=[
            Text(style=grow(1) | min_width(0) | border, content="grow(1)"),
            Text(style=grow(2) | min_width(0) | border, content="grow(2)"),
        ],
    )


# --8<-- [end:ratio-flex]

# --8<-- [start:ratio-grid]


@component
def ratio_grid() -> Div:
    return Div(
        style=display_grid | grid_template_columns(waxy.Fraction(1), waxy.Fraction(2)) | full,
        children=[
            Text(style=border, content="Fraction(1)"),
            Text(style=border, content="Fraction(2)"),
        ],
    )


# --8<-- [end:ratio-grid]

# --8<-- [start:nested-flex]


@component
def nested_flex() -> Div:
    return Div(
        style=row | full,
        children=[
            Text(style=width(20) | border, content="width(20)"),
            Div(
                style=col | grow(1) | min_width(0),
                children=[
                    Text(style=grow(1) | min_height(0) | border, content="grow(1) | min_height(0)"),
                    Text(style=grow(1) | min_height(0) | border, content="grow(1) | min_height(0)"),
                ],
            ),
        ],
    )


# --8<-- [end:nested-flex]

# --8<-- [start:nested-grid]


@component
def nested_grid() -> Div:
    return Div(
        style=display_grid
        | grid_template_columns(waxy.Length(20), waxy.Fraction(1))
        | grid_template_rows(waxy.Fraction(1), waxy.Fraction(1))
        | full,
        children=[
            Text(
                style=grid_row(waxy.GridLine(1), waxy.GridSpan(2)) | border,
                content="grid_row(\n  GridLine(1),\n  GridSpan(2),\n)",
            ),
            Text(style=border, content="Fraction(1)"),
            Text(style=border, content="Fraction(1)"),
        ],
    )


# --8<-- [end:nested-grid]

LONG = "a line of text much longer than half the grid"

# --8<-- [start:overflow-grid]


@component
def overflow_grid() -> Div:
    return Div(
        style=col | full,
        children=[
            Div(
                style=display_grid | grid_template_columns(waxy.Fraction(1), waxy.Fraction(1)) | border | border_heavy,
                children=[
                    Text(style=border, content=LONG),
                    Text(style=border, content=LONG),
                ],
            ),
            Div(
                style=display_grid
                | grid_template_columns(
                    waxy.Minmax(waxy.Length(0), waxy.Fraction(1)),
                    waxy.Minmax(waxy.Length(0), waxy.Fraction(1)),
                )
                | border
                | border_heavy,
                children=[
                    Text(style=border, content=LONG),
                    Text(style=border, content=LONG),
                ],
            ),
        ],
    )


# --8<-- [end:overflow-grid]

half = Style(layout=waxy.Style(flex_basis=waxy.Percent(0.5)))

# --8<-- [start:percent-gap]


@component
def percent_gap() -> Div:
    return Div(
        style=col | full,
        children=[
            Div(
                style=row | gap(2) | border | border_heavy,
                children=[
                    Text(style=half | border, content="half"),
                    Text(style=half | border, content="half"),
                ],
            ),
            Div(
                style=row | gap(2) | border | border_heavy,
                children=[
                    Text(style=half | shrink(0) | border, content="half | shrink(0)"),
                    Text(style=half | shrink(0) | border, content="half | shrink(0)"),
                ],
            ),
        ],
    )


# --8<-- [end:percent-gap]

SCREENSHOTS = [
    ScreenshotSpec(equal_flex, "layout-split-equal-flex", (75, 3)),
    ScreenshotSpec(equal_grid, "layout-split-equal-grid", (75, 3)),
    ScreenshotSpec(sidebar_flex, "layout-split-sidebar-flex", (60, 3)),
    ScreenshotSpec(sidebar_grid, "layout-split-sidebar-grid", (60, 3)),
    ScreenshotSpec(ratio_flex, "layout-split-ratio-flex", (60, 3)),
    ScreenshotSpec(ratio_grid, "layout-split-ratio-grid", (60, 3)),
    ScreenshotSpec(nested_flex, "layout-split-nested-flex", (60, 8)),
    ScreenshotSpec(nested_grid, "layout-split-nested-grid", (60, 8)),
    ScreenshotSpec(overflow_grid, "layout-split-overflow-grid", (60, 10)),
    ScreenshotSpec(percent_gap, "layout-split-percent-gap", (60, 10)),
]
