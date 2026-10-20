"""
Layout: Choosing a layout model

The same app shell in flexbox and in grid, and where each does better.
"""

import asyncio
import sys

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles.utilities import *

# --8<-- [start:shell-flex]


@component
def shell_flex() -> Div:
    return Div(
        style=col,
        children=(
            Div(
                style=row | fill(1),
                children=(
                    Text(style=length(20) | border, content="sidebar:\nlength(20)"),
                    Text(style=fill(1) | border, content="main:\nfill(1)"),
                ),
            ),
            Text(style=length(1) | text_bg("slate", 700), content=" status: length(1)"),
        ),
    )


# --8<-- [end:shell-flex]

# --8<-- [start:shell-grid]


@component
def shell_grid() -> Div:
    return Div(
        style=display_grid | grid_template_columns(20, fr(1)) | grid_template_rows(fr(1), 1),
        children=(
            Text(style=border, content="sidebar:\n20"),
            Text(style=border, content="main:\nfr(1)"),
            Text(style=grid_column(1, span(2)) | text_bg("slate", 700), content=" status: 1"),
        ),
    )


# --8<-- [end:shell-grid]

# --8<-- [start:mixed]


@component
def mixed() -> Div:
    return Div(
        style=display_grid | grid_template_columns(20, fr(1)) | grid_template_rows(fr(1), 1),
        children=(
            Div(
                style=col | border,
                children=(Text(content="inbox"), Text(content="drafts"), Text(content="sent")),
            ),
            Text(style=border, content="main: fr(1)"),
            Div(
                style=row | justify_children_space_between | grid_column(1, span(2)),
                children=(
                    Text(style=text_bg("slate", 700), content=" status: row"),
                    Text(style=text_bg("slate", 700), content="justify_children_space_between "),
                ),
            ),
        ),
    )


# --8<-- [end:mixed]

# --8<-- [start:extra-child-grid]


@component
def extra_child_grid() -> Div:
    return Div(
        style=display_grid | grid_template_columns(fr(1), fr(1)),
        children=(
            Text(style=border, content="fr(1)"),
            Text(style=border, content="fr(1)"),
            Text(style=border, content="a third child"),
        ),
    )


# --8<-- [end:extra-child-grid]

# --8<-- [start:extra-child-flex]


@component
def extra_child_flex() -> Div:
    return Div(
        style=row,
        children=(
            Text(style=fill(1) | border, content="fill(1)"),
            Text(style=fill(1) | border, content="fill(1)"),
            Text(style=fill(1) | border, content="fill(1)"),
        ),
    )


# --8<-- [end:extra-child-flex]

# --8<-- [start:conflict]


@component
def conflict() -> Div:
    return Div(
        style=col,
        children=(
            Div(
                style=row | width(42) | border | border_heavy,
                children=(
                    Text(style=length(30) | border, content="length(30)"),
                    Text(style=length(30) | border, content="length(30)"),
                ),
            ),
            Div(
                style=row | width(42) | border | border_heavy,
                children=(
                    Text(style=length(30) | shrink(1) | border, content="length(30)\n| shrink(1)"),
                    Text(style=length(30) | shrink(1) | border, content="length(30)\n| shrink(1)"),
                ),
            ),
        ),
    )


# --8<-- [end:conflict]


ROOTS = (shell_flex, shell_grid, mixed, extra_child_grid, extra_child_flex, conflict)

# --8<-- [start:scenes]

from counterweight.examples.scenes import Still

STILLS = [
    Still("layout-choosing-shell-flex", shell_flex(), (60, 8)),
    Still("layout-choosing-shell-grid", shell_grid(), (60, 8)),
    Still("layout-choosing-mixed", mixed(), (60, 8)),
    Still("layout-choosing-extra-child-grid", extra_child_grid(), (45, 6)),
    Still("layout-choosing-extra-child-flex", extra_child_flex(), (45, 6)),
    Still("layout-choosing-conflict", conflict(), (61, 11)),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
