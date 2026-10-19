"""
Layout: Splitting space

Equal splits, sidebars, ratios and nested splits, in flexbox and in grid.
"""

import asyncio
import sys

import waxy

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles.utilities import *

# --8<-- [start:equal-flex]


@component
def equal_flex() -> Div:
    return Div(
        style=row,
        children=(
            Text(style=fill(1) | border, content="fill(1)"),
            Text(style=fill(1) | border, content="fill(1)"),
            Text(style=fill(1) | border, content="fill(1)"),
        ),
    )


# --8<-- [end:equal-flex]

# --8<-- [start:equal-grid]


@component
def equal_grid() -> Div:
    return Div(
        style=display_grid | grid_template_columns(fr(1), fr(1), fr(1)),
        children=(
            Text(style=border, content="fr(1)"),
            Text(style=border, content="fr(1)"),
            Text(style=border, content="fr(1)"),
        ),
    )


# --8<-- [end:equal-grid]

# --8<-- [start:sidebar-flex]


@component
def sidebar_flex() -> Div:
    return Div(
        style=row,
        children=(
            Text(style=length(20) | border, content="length(20)"),
            Text(style=fill(1) | border, content="fill(1)"),
        ),
    )


# --8<-- [end:sidebar-flex]

# --8<-- [start:sidebar-grid]


@component
def sidebar_grid() -> Div:
    return Div(
        style=display_grid | grid_template_columns(20, fr(1)),
        children=(
            Text(style=border, content="20"),
            Text(style=border, content="fr(1)"),
        ),
    )


# --8<-- [end:sidebar-grid]

# --8<-- [start:ratio-flex]


@component
def ratio_flex() -> Div:
    return Div(
        style=row,
        children=(
            Text(style=fill(1) | border, content="fill(1)"),
            Text(style=fill(2) | border, content="fill(2)"),
        ),
    )


# --8<-- [end:ratio-flex]

# --8<-- [start:ratio-exact]


@component
def ratio_exact() -> Div:
    return Div(
        style=row,
        children=(
            Text(style=ratio(1, 3) | border, content="ratio(1, 3)"),
            Text(style=ratio(2, 3) | border, content="ratio(2, 3)"),
        ),
    )


# --8<-- [end:ratio-exact]

# --8<-- [start:ratio-grid]


@component
def ratio_grid() -> Div:
    return Div(
        style=display_grid | grid_template_columns(fr(1), fr(2)),
        children=(
            Text(style=border, content="fr(1)"),
            Text(style=border, content="fr(2)"),
        ),
    )


# --8<-- [end:ratio-grid]

# --8<-- [start:nested-flex]


@component
def nested_flex() -> Div:
    return Div(
        style=row,
        children=(
            Text(style=length(20) | border, content="length(20)"),
            Div(
                style=col | fill(1),
                children=(
                    Text(style=fill(1) | border, content="fill(1)"),
                    Text(style=fill(1) | border, content="fill(1)"),
                ),
            ),
        ),
    )


# --8<-- [end:nested-flex]

# --8<-- [start:nested-grid]


@component
def nested_grid() -> Div:
    return Div(
        style=display_grid | grid_template_columns(20, fr(1)) | grid_template_rows(fr(1), fr(1)),
        children=(
            Text(
                style=grid_row(1, span(2)) | border,
                content="grid_row(\n  1, span(2),\n)",
            ),
            Text(style=border, content="fr(1)"),
            Text(style=border, content="fr(1)"),
        ),
    )


# --8<-- [end:nested-grid]

LONG = "a line of text much longer than half the grid"

# --8<-- [start:overflow-grid]


@component
def overflow_grid() -> Div:
    return Div(
        style=col,
        children=(
            Div(
                style=display_grid | grid_template_columns(waxy.Fraction(1), waxy.Fraction(1)) | border | border_heavy,
                children=(
                    Text(style=border, content=LONG),
                    Text(style=border, content=LONG),
                ),
            ),
            Div(
                style=display_grid | grid_template_columns(fr(1), fr(1)) | border | border_heavy,
                children=(
                    Text(style=border, content=LONG),
                    Text(style=border, content=LONG),
                ),
            ),
            Div(
                style=display_grid | grid_template_columns(fr(1), fr(1)) | border | border_heavy,
                children=(
                    Text(style=border | overflow_hidden, content=LONG),
                    Text(style=border | overflow_hidden, content=LONG),
                ),
            ),
        ),
    )


# --8<-- [end:overflow-grid]

# --8<-- [start:percent-gap]


@component
def percent_gap() -> Div:
    return Div(
        style=col,
        children=(
            Div(
                style=row | gap(2) | border | border_heavy,
                children=(
                    Text(style=percentage(50) | shrink(1) | border, content="percentage(50) | shrink(1)"),
                    Text(style=percentage(50) | shrink(1) | border, content="percentage(50) | shrink(1)"),
                ),
            ),
            Div(
                style=row | gap(2) | border | border_heavy,
                children=(
                    Text(style=percentage(50) | border, content="percentage(50)"),
                    Text(style=percentage(50) | border, content="percentage(50)"),
                ),
            ),
        ),
    )


# --8<-- [end:percent-gap]


ROOTS = (
    equal_flex,
    equal_grid,
    sidebar_flex,
    sidebar_grid,
    ratio_flex,
    ratio_grid,
    ratio_exact,
    nested_flex,
    nested_grid,
    overflow_grid,
    percent_gap,
)

# --8<-- [start:scenes]

from counterweight.examples.scenes import Still

STILLS = [
    Still("layout-split-equal-flex", equal_flex(), (75, 3)),
    Still("layout-split-equal-grid", equal_grid(), (75, 3)),
    Still("layout-split-sidebar-flex", sidebar_flex(), (60, 3)),
    Still("layout-split-sidebar-grid", sidebar_grid(), (60, 3)),
    Still("layout-split-ratio-flex", ratio_flex(), (60, 3)),
    Still("layout-split-ratio-grid", ratio_grid(), (60, 3)),
    Still("layout-split-ratio-exact", ratio_exact(), (60, 3)),
    Still("layout-split-nested-flex", nested_flex(), (60, 8)),
    Still("layout-split-nested-grid", nested_grid(), (60, 8)),
    Still("layout-split-overflow-grid", overflow_grid(), (60, 15)),
    Still("layout-split-percent-gap", percent_gap(), (60, 10)),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
