from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:shell-flex]


@component
def shell_flex() -> Div:
    return Div(
        style=col | full,
        children=[
            Div(
                style=row | fill(1),
                children=[
                    Text(style=length(20) | border, content="sidebar:\nlength(20)"),
                    Text(style=fill(1) | border, content="main:\nfill(1)"),
                ],
            ),
            Text(style=length(1) | text_bg("slate", 700), content=" status: length(1)"),
        ],
    )


# --8<-- [end:shell-flex]

# --8<-- [start:shell-grid]


@component
def shell_grid() -> Div:
    return Div(
        style=display_grid | grid_template_columns(20, fr(1)) | grid_template_rows(fr(1), 1) | full,
        children=[
            Text(style=border, content="sidebar:\n20"),
            Text(style=border, content="main:\nfr(1)"),
            Text(style=grid_column(1, span(2)) | text_bg("slate", 700), content=" status: 1"),
        ],
    )


# --8<-- [end:shell-grid]

# --8<-- [start:mixed]


@component
def mixed() -> Div:
    return Div(
        style=display_grid | grid_template_columns(20, fr(1)) | grid_template_rows(fr(1), 1) | full,
        children=[
            Div(
                style=col | border,
                children=[Text(content="inbox"), Text(content="drafts"), Text(content="sent")],
            ),
            Text(style=border, content="main: fr(1)"),
            Div(
                style=row | justify_children_space_between | grid_column(1, span(2)),
                children=[
                    Text(style=text_bg("slate", 700), content=" status: row"),
                    Text(style=text_bg("slate", 700), content="justify_children_space_between "),
                ],
            ),
        ],
    )


# --8<-- [end:mixed]

# --8<-- [start:extra-child-grid]


@component
def extra_child_grid() -> Div:
    return Div(
        style=display_grid | grid_template_columns(fr(1), fr(1)) | full,
        children=[
            Text(style=border, content="fr(1)"),
            Text(style=border, content="fr(1)"),
            Text(style=border, content="a third child"),
        ],
    )


# --8<-- [end:extra-child-grid]

# --8<-- [start:extra-child-flex]


@component
def extra_child_flex() -> Div:
    return Div(
        style=row | full,
        children=[
            Text(style=fill(1) | border, content="fill(1)"),
            Text(style=fill(1) | border, content="fill(1)"),
            Text(style=fill(1) | border, content="fill(1)"),
        ],
    )


# --8<-- [end:extra-child-flex]

# --8<-- [start:conflict]


@component
def conflict() -> Div:
    return Div(
        style=col | full,
        children=[
            Div(
                style=row | width(42) | border | border_heavy,
                children=[
                    Text(style=length(30) | border, content="length(30)"),
                    Text(style=length(30) | border, content="length(30)"),
                ],
            ),
            Div(
                style=row | width(42) | border | border_heavy,
                children=[
                    Text(style=length(30) | shrink(1) | border, content="length(30)\n| shrink(1)"),
                    Text(style=length(30) | shrink(1) | border, content="length(30)\n| shrink(1)"),
                ],
            ),
        ],
    )


# --8<-- [end:conflict]

SCREENSHOTS = [
    ScreenshotSpec(shell_flex, "layout-choosing-shell-flex", (60, 8)),
    ScreenshotSpec(shell_grid, "layout-choosing-shell-grid", (60, 8)),
    ScreenshotSpec(mixed, "layout-choosing-mixed", (60, 8)),
    ScreenshotSpec(extra_child_grid, "layout-choosing-extra-child-grid", (45, 6)),
    ScreenshotSpec(extra_child_flex, "layout-choosing-extra-child-flex", (45, 6)),
    ScreenshotSpec(conflict, "layout-choosing-conflict", (64, 11)),
]
