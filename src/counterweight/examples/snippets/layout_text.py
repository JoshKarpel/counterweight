"""
Layout: Text in layout

Text wrapping in a pane and in a row, justified, and in a narrow box.
"""

import asyncio
import sys

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles.styles import Style
from counterweight.styles.utilities import *

PARAGRAPH = "The quick brown fox jumps over the lazy dog, and then naps in the afternoon sun."

# --8<-- [start:wrap-in-pane]


@component
def wrap_in_pane() -> Div:
    return Div(
        style=row,
        children=(
            Text(style=length(16) | border, content="length(16)"),
            Div(
                style=col | fill(1) | border | pad_x(1),
                children=(Text(style=text_wrap_stable, content=PARAGRAPH),),
            ),
        ),
    )


# --8<-- [end:wrap-in-pane]

# --8<-- [start:wrap-in-row]


@component
def wrap_in_row() -> Div:
    return Div(
        style=row | gap(2) | border | border_heavy,
        children=(
            Text(style=text_wrap_stable | border, content=PARAGRAPH),
            Text(style=text_wrap_stable | border, content=PARAGRAPH),
        ),
    )


# --8<-- [end:wrap-in-row]

# --8<-- [start:justify]


@component
def justify() -> Div:
    return Div(
        style=col,
        children=(
            Text(style=text_justify_center | border, content="text_justify_center, stretched"),
            Text(
                style=text_justify_center | align_self_start | border,
                content="text_justify_center | align_self_start",
            ),
            Text(
                style=text_justify_center | text_wrap_balance | border,
                content="text_justify_center | text_wrap_balance centers each line of a paragraph "
                "within the width of the box",
            ),
        ),
    )


# --8<-- [end:justify]

# --8<-- [start:narrow]


@component
def narrow_panes(text_style: Style) -> Div:
    return Div(
        style=row | gap(8),
        children=(
            Div(
                style=col | width(20) | border | border_heavy,
                children=(Text(style=text_style, content="unwrapped text in a col"),),
            ),
            Div(
                style=row | width(20) | border | border_heavy,
                children=(Text(style=text_style, content="unwrapped text in a row"),),
            ),
        ),
    )


@component
def narrow() -> Div:
    return Div(
        style=col,
        children=(narrow_panes(border), narrow_panes(border | overflow_hidden)),
    )


# --8<-- [end:narrow]


ROOTS = (wrap_in_pane, wrap_in_row, justify, narrow)

# --8<-- [start:scenes]

from counterweight.examples.scenes import Still

STILLS = [
    Still("layout-text-wrap-in-pane", wrap_in_pane(), (60, 7)),
    Still("layout-text-wrap-in-row", wrap_in_row(), (60, 8)),
    Still("layout-text-justify", justify(), (50, 11)),
    Still("layout-text-narrow", narrow(), (56, 10)),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
