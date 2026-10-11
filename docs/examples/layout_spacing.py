from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:gap-margin-pad]


@component
def gap_margin_pad() -> Div:
    return Div(
        style=col | full,
        children=[
            Div(
                style=row | gap(2) | border | border_heavy,
                children=[Text(style=border, content=f"gap(2) on the row {n}") for n in range(2)],
            ),
            Div(
                style=row | border | border_heavy,
                children=[
                    Text(style=margin_x(1) | margin_color("red", 600) | border, content=f"margin_x(1) {n}")
                    for n in range(2)
                ],
            ),
            Div(
                style=row | pad_x(2) | padding_color("blue", 600) | border | border_heavy,
                children=[Text(style=border, content=f"pad_x(2) on the row {n}") for n in range(2)],
            ),
        ],
    )


# --8<-- [end:gap-margin-pad]

# --8<-- [start:collapse]


@component
def collapse() -> Div:
    return Div(
        style=col | full,
        children=[
            Div(
                style=row,
                children=[Text(style=border, content="side by side") for _ in range(3)],
            ),
            Div(
                style=row | border_collapse,
                children=[Text(style=border, content="border_collapse") for _ in range(3)],
            ),
        ],
    )


# --8<-- [end:collapse]

# --8<-- [start:sides]


@component
def sides() -> Div:
    return Div(
        style=row | align_children_start | gap(2) | full,
        children=[
            Text(style=border_y, content="border_y"),
            Text(style=border_top | border_left, content="border_top\n| border_left"),
            Text(style=border | border_right_0, content="border\n| border_right_0"),
            Text(style=border_right_0 | border, content="border_right_0\n| border"),
        ],
    )


# --8<-- [end:sides]

# --8<-- [start:contract]


@component
def contract() -> Div:
    return Div(
        style=row | align_children_start | gap(2) | full,
        children=[
            Text(
                style=border_top | border_left | pad_x(1),
                content="top and left\nsides",
            ),
            Text(
                style=border_top | border_left | border_contract(2) | pad_x(1),
                content="top and left\nsides\nborder_contract(2)",
            ),
        ],
    )


# --8<-- [end:contract]

SCREENSHOTS = [
    ScreenshotSpec(gap_margin_pad, "layout-gap-margin-pad", (60, 15)),
    ScreenshotSpec(collapse, "layout-border-collapse", (60, 6)),
    ScreenshotSpec(sides, "layout-border-sides", (70, 5)),
    ScreenshotSpec(contract, "layout-border-contract", (50, 5)),
]
