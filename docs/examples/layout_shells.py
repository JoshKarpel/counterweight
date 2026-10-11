from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:header-body-footer]


@component
def header_body_footer() -> Div:
    return Div(
        style=col | full,
        children=[
            Text(style=border | border_heavy | text_justify_center, content="header"),
            Text(style=grow(1) | min_height(0) | border, content="body: grow(1) | min_height(0)"),
            Text(style=text_bg("slate", 700), content=" footer: one row, no border"),
        ],
    )


# --8<-- [end:header-body-footer]

# --8<-- [start:sidebar-status]


@component
def sidebar_status() -> Div:
    return Div(
        style=col | full,
        children=[
            Div(
                style=row | grow(1) | min_height(0),
                children=[
                    Text(style=width(20) | border, content="sidebar: width(20)"),
                    Text(style=grow(1) | min_width(0) | border, content="main: grow(1) | min_width(0)"),
                ],
            ),
            Text(style=text_bg("slate", 700), content=" status bar"),
        ],
    )


# --8<-- [end:sidebar-status]

# --8<-- [start:three-panes]


@component
def three_panes() -> Div:
    return Div(
        style=row | full | border_collapse,
        children=[
            Text(style=width(20) | border, content="files: width(20)"),
            Div(
                style=col | grow(1) | min_width(0) | border_collapse,
                children=[
                    Text(style=grow(2) | min_height(0) | border, content="editor: grow(2)"),
                    Text(style=grow(1) | min_height(0) | border, content="terminal: grow(1)"),
                ],
            ),
            Text(style=width(20) | border, content="outline: width(20)"),
        ],
    )


# --8<-- [end:three-panes]

SCREENSHOTS = [
    ScreenshotSpec(header_body_footer, "layout-shell-header-body-footer", (60, 10)),
    ScreenshotSpec(sidebar_status, "layout-shell-sidebar-status", (60, 10)),
    ScreenshotSpec(three_panes, "layout-shell-three-panes", (80, 14)),
]
