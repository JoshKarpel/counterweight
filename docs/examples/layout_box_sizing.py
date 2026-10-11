from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:fixed]


@component
def fixed() -> Div:
    return Div(
        style=col | full,
        children=[
            Text(style=size(24, 4) | border, content="size(24, 4)"),
            Text(style=width(36) | border, content="width(36)"),
            Text(style=height(4) | border, content="height(4)"),
        ],
    )


# --8<-- [end:fixed]

# --8<-- [start:fit]


@component
def fit() -> Div:
    return Div(
        style=col | full,
        children=[
            Text(style=border, content="stretched by its col"),
            Text(style=align_self_start | border, content="align_self_start"),
        ],
    )


# --8<-- [end:fit]

# --8<-- [start:fill]


@component
def fill() -> Div:
    return Div(
        style=col | full,
        children=[
            Text(style=border, content="content height"),
            Text(style=grow(1) | border, content="grow(1): the rest of the col"),
            Div(
                style=row,
                children=[Text(style=full_width | border, content="full_width: the whole row")],
            ),
        ],
    )


# --8<-- [end:fill]

# --8<-- [start:clamped]


@component
def clamped() -> Div:
    return Div(
        style=col | full,
        children=[
            Div(
                style=row,
                children=[
                    Text(style=grow(1) | max_width(20) | border, content="grow(1)\nmax_width(20)"),
                    Text(style=grow(1) | border, content="grow(1)"),
                ],
            ),
            Div(
                style=row | width(40) | border | border_heavy,
                children=[
                    Text(style=width(30) | min_width(24) | border, content="width(30)\nmin_width(24)"),
                    Text(style=width(30) | border, content="width(30)"),
                ],
            ),
        ],
    )


# --8<-- [end:clamped]

# --8<-- [start:aspect-ratio]


@component
def aspect() -> Div:
    return Div(
        style=row | align_children_start | full,
        children=[
            Text(style=width(18) | aspect_ratio(1) | border, content="width(18)\naspect_ratio(1)"),
            Text(style=width(18) | aspect_ratio(2) | border, content="width(18)\naspect_ratio(2)"),
        ],
    )


# --8<-- [end:aspect-ratio]

# --8<-- [start:box-sizing]


@component
def box_sizing() -> Div:
    return Div(
        style=col | align_children_start | full,
        children=[
            Text(style=width(24) | pad_x(2) | border, content="width(24)"),
            Text(style=content_box | width(24) | pad_x(2) | border, content="content_box | width(24)"),
        ],
    )


# --8<-- [end:box-sizing]

SCREENSHOTS = [
    ScreenshotSpec(fixed, "layout-size-fixed", (50, 11)),
    ScreenshotSpec(fit, "layout-size-fit", (50, 6)),
    ScreenshotSpec(fill, "layout-size-fill", (50, 10)),
    ScreenshotSpec(clamped, "layout-size-clamped", (60, 10)),
    ScreenshotSpec(aspect, "layout-size-aspect-ratio", (50, 18)),
    ScreenshotSpec(box_sizing, "layout-size-box-sizing", (50, 6)),
]
