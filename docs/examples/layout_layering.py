from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:relative]


@component
def relative() -> Div:
    return Div(
        style=row | align_children_start | gap(3) | full,
        children=[
            Text(style=border_light, content="first"),
            Text(
                style=position_relative | inset_top(2) | inset_left(2) | border_heavy,
                content="position_relative\ninset_top(2)\ninset_left(2)",
            ),
            Text(style=border_light, content="third"),
        ],
    )


# --8<-- [end:relative]

# --8<-- [start:absolute]


@component
def absolute() -> Div:
    return Div(
        style=col | full | border_light,
        children=[
            Text(content="first, in flow"),
            Text(
                style=position_absolute | inset_top(2) | inset_left(10) | border_heavy,
                content="position_absolute\ninset_top(2)\ninset_left(10)",
            ),
            Text(content="second, in flow"),
        ],
    )


# --8<-- [end:absolute]

# --8<-- [start:dialog]

overlay = (
    position_absolute
    | inset_top(0)
    | inset_bottom(0)
    | inset_left(0)
    | inset_right(0)
    | align_children_center
    | justify_children_center
)


@component
def dialog() -> Div:
    return Div(
        style=col | full,
        children=[
            Text(style=border_light, content="header"),
            Text(
                style=grow(1) | border_light | text_wrap_stable,
                content="The app's content stays where it is, and the dialog draws over it. " * 4,
            ),
            Div(
                style=overlay,
                children=[
                    Text(
                        style=border_double | pad_x(2) | pad_y(1),
                        content="a dialog centered over the app",
                    ),
                ],
            ),
        ],
    )


# --8<-- [end:dialog]

# --8<-- [start:badge]


@component
def badge() -> Div:
    return Div(
        style=row | align_children_start | gap(2) | full,
        children=[
            Div(
                style=border_light | pad_x(1),
                children=[
                    Text(content="inbox"),
                    Text(
                        style=position_absolute | inset_top(-1) | inset_right(1) | text_color("red", 500),
                        content="3",
                    ),
                ],
            ),
            Div(
                style=border_light | pad_x(1),
                children=[
                    Text(content="alerts"),
                    Text(
                        style=position_absolute | inset_top(-1) | inset_right(-1) | text_bg("red", 600),
                        content="!",
                    ),
                ],
            ),
        ],
    )


# --8<-- [end:badge]

SCREENSHOTS = [
    ScreenshotSpec(relative, "layout-relative", (50, 7)),
    ScreenshotSpec(absolute, "layout-absolute", (50, 9)),
    ScreenshotSpec(dialog, "layout-dialog", (60, 12)),
    ScreenshotSpec(badge, "layout-badge", (40, 3)),
]
