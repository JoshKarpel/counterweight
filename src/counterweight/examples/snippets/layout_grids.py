"""
Layout: Grids and wrapping

Tiles in a grid, cells spanning tracks, auto flow, and rows that wrap.
"""

import asyncio
import sys

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles.utilities import *

# --8<-- [start:tiles]


@component
def tiles() -> Div:
    return Div(
        style=display_grid | grid_template_columns(fr(1), fr(1), fr(1)) | grid_template_rows(fr(1), fr(1)) | gap(1),
        children=tuple(Text(style=border, content=f"tile {n}") for n in range(1, 7)),
    )


# --8<-- [end:tiles]

# --8<-- [start:spans]


@component
def spans() -> Div:
    return Div(
        style=display_grid | grid_template_columns(fr(1), fr(1), fr(1)) | grid_template_rows(fr(1), fr(1), fr(1)),
        children=(
            Text(
                style=grid_row(1) | grid_column(1, span(2)) | border | border_heavy,
                content="grid_row(1)\ngrid_column(1, span(2))",
            ),
            Text(
                style=grid_row(1, span(3)) | grid_column(3) | border | border_heavy,
                content="grid_row(\n  1, span(3),\n)\ngrid_column(3)",
            ),
            Text(style=border, content="auto"),
            Text(style=border, content="auto"),
            Text(style=border, content="auto"),
            Text(style=border, content="auto"),
        ),
    )


# --8<-- [end:spans]

# --8<-- [start:auto-flow]


@component
def auto_flow() -> Div:
    return Div(
        style=row | gap(2),
        children=(
            Div(
                style=display_grid | grid_template_columns(fr(1), fr(1), fr(1)) | fill(1) | border | border_heavy,
                children=(
                    Text(
                        content=" grid_template_columns(fr(1), fr(1), fr(1)) ",
                        style=position_absolute | inset_top(-1) | inset_left(1) | clip_to_border,
                    ),
                    *(Text(style=border, content=str(n)) for n in range(1, 8)),
                ),
            ),
            Div(
                style=display_grid
                | grid_template_rows(fr(1), fr(1), fr(1))
                | grid_auto_flow_column
                | fill(1)
                | border
                | border_heavy,
                children=(
                    Text(
                        content=" grid_template_rows(fr(1), fr(1), fr(1)) ",
                        style=position_absolute | inset_top(-1) | inset_left(1) | clip_to_border,
                    ),
                    Text(
                        content=" grid_auto_flow_column ",
                        style=position_absolute | inset_bottom(-1) | inset_left(1) | clip_to_border,
                    ),
                    *(Text(style=border, content=str(n)) for n in range(1, 8)),
                ),
            ),
        ),
    )


# --8<-- [end:auto-flow]

TAGS = ["layout", "flexbox", "grid", "wrapping", "alignment", "text", "borders", "z", "positioning", "gap"]

# --8<-- [start:wrap]


@component
def wrap() -> Div:
    return Div(
        style=row | flex_wrap | align_children_start | gap_width(1),
        children=tuple(Text(style=border | pad_x(1), content=tag) for tag in TAGS),
    )


# --8<-- [end:wrap]


ROOTS = (tiles, spans, auto_flow, wrap)

# --8<-- [start:scenes]

from counterweight.examples.scenes import Still

STILLS = [
    Still("layout-grid-tiles", tiles(), (60, 12)),
    Still("layout-grid-spans", spans(), (60, 12)),
    Still("layout-grid-auto-flow", auto_flow(), (100, 11)),
    Still("layout-flex-wrap", wrap(), (50, 9)),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
