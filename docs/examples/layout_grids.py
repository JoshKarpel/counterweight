import waxy

from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:tiles]

fr = waxy.Fraction(1)


@component
def tiles() -> Div:
    return Div(
        style=display_grid | grid_template_columns(fr, fr, fr) | grid_template_rows(fr, fr) | gap(1) | full,
        children=[Text(style=border_light, content=f"tile {n}") for n in range(1, 7)],
    )


# --8<-- [end:tiles]

# --8<-- [start:spans]


@component
def spans() -> Div:
    return Div(
        style=display_grid | grid_template_columns(fr, fr, fr) | grid_template_rows(fr, fr, fr) | full,
        children=[
            Text(
                style=grid_row(waxy.GridLine(1)) | grid_column(waxy.GridLine(1), waxy.GridSpan(2)) | border_heavy,
                content="grid_row(GridLine(1))\ngrid_column(GridLine(1), GridSpan(2))",
            ),
            Text(
                style=grid_row(waxy.GridLine(1), waxy.GridSpan(3)) | grid_column(waxy.GridLine(3)) | border_heavy,
                content="grid_row(\n  GridLine(1),\n  GridSpan(3),\n)\ngrid_column(\n  GridLine(3),\n)",
            ),
            Text(style=border_light, content="auto"),
            Text(style=border_light, content="auto"),
            Text(style=border_light, content="auto"),
            Text(style=border_light, content="auto"),
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
                style=display_grid | grid_template_columns(fr, fr, fr) | grow(1) | border_heavy,
                children=[
                    Text(content=" grid_template_columns(fr, fr, fr) ", style=position_absolute | inset_top(-1)),
                    *(Text(style=border_light, content=str(n)) for n in range(1, 8)),
                ],
            ),
            Div(
                style=display_grid | grid_template_rows(fr, fr, fr) | grid_auto_flow_column | grow(1) | border_heavy,
                children=[
                    Text(content=" grid_template_rows(fr, fr, fr) ", style=position_absolute | inset_top(-1)),
                    Text(content=" grid_auto_flow_column ", style=position_absolute | inset_bottom(-1)),
                    *(Text(style=border_light, content=str(n)) for n in range(1, 8)),
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
        children=[Text(style=border_light | pad_x(1), content=tag) for tag in TAGS],
    )


# --8<-- [end:wrap]

SCREENSHOTS = [
    ScreenshotSpec(tiles, "layout-grid-tiles", (60, 12)),
    ScreenshotSpec(spans, "layout-grid-spans", (60, 12)),
    ScreenshotSpec(auto_flow, "layout-grid-auto-flow", (80, 11)),
    ScreenshotSpec(wrap, "layout-flex-wrap", (50, 9)),
]
