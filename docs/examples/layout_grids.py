from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:tiles]


@component
def tiles() -> Div:
    return Div(
        style=display_grid
        | grid_template_columns(fr(1), fr(1), fr(1))
        | grid_template_rows(fr(1), fr(1))
        | gap(1)
        | full,
        children=[Text(style=border, content=f"tile {n}") for n in range(1, 7)],
    )


# --8<-- [end:tiles]

# --8<-- [start:spans]


@component
def spans() -> Div:
    return Div(
        style=display_grid
        | grid_template_columns(fr(1), fr(1), fr(1))
        | grid_template_rows(fr(1), fr(1), fr(1))
        | full,
        children=[
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
        ],
    )


# --8<-- [end:spans]

# --8<-- [start:auto-flow]


@component
def auto_flow() -> Div:
    return Div(
        style=row | gap(2) | full,
        children=[
            Div(
                style=display_grid | grid_template_columns(fr(1), fr(1), fr(1)) | fill(1) | border | border_heavy,
                children=[
                    Text(
                        content=" grid_template_columns(fr(1), fr(1), fr(1)) ", style=position_absolute | inset_top(-1)
                    ),
                    *(Text(style=border, content=str(n)) for n in range(1, 8)),
                ],
            ),
            Div(
                style=display_grid
                | grid_template_rows(fr(1), fr(1), fr(1))
                | grid_auto_flow_column
                | fill(1)
                | border
                | border_heavy,
                children=[
                    Text(content=" grid_template_rows(fr(1), fr(1), fr(1)) ", style=position_absolute | inset_top(-1)),
                    Text(content=" grid_auto_flow_column ", style=position_absolute | inset_bottom(-1)),
                    *(Text(style=border, content=str(n)) for n in range(1, 8)),
                ],
            ),
        ],
    )


# --8<-- [end:auto-flow]

TAGS = ["layout", "flexbox", "grid", "wrapping", "alignment", "text", "borders", "z", "positioning", "gap"]

# --8<-- [start:wrap]


@component
def wrap() -> Div:
    return Div(
        style=row | flex_wrap | align_children_start | gap_width(1) | full,
        children=[Text(style=border | pad_x(1), content=tag) for tag in TAGS],
    )


# --8<-- [end:wrap]

SCREENSHOTS = [
    ScreenshotSpec(tiles, "layout-grid-tiles", (60, 12)),
    ScreenshotSpec(spans, "layout-grid-spans", (60, 12)),
    ScreenshotSpec(auto_flow, "layout-grid-auto-flow", (96, 11)),
    ScreenshotSpec(wrap, "layout-flex-wrap", (50, 9)),
]
