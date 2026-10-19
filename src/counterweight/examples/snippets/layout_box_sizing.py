"""
Layout: Sizing one box

Fixed sizes, sizes fit to content, filling, clamping, aspect ratios, and what a size includes.
"""

import asyncio
import sys

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles.utilities import *

# --8<-- [start:fixed]


@component
def fixed() -> Div:
    return Div(
        style=col,
        children=(
            Text(style=size(24, 4) | border, content="size(24, 4)"),
            Text(style=width(36) | border, content="width(36)"),
            Text(style=height(4) | border, content="height(4)"),
        ),
    )


# --8<-- [end:fixed]

# --8<-- [start:fit]


@component
def fit() -> Div:
    return Div(
        style=col,
        children=(
            Text(style=border, content="stretched by its col"),
            Text(style=align_self_start | border, content="align_self_start"),
        ),
    )


# --8<-- [end:fit]

# --8<-- [start:content-keywords]


KEYWORDS = {
    "min_content_width": min_content_width,
    "max_content_width": max_content_width,
    "fit_content_width": fit_content_width,
    "stretch_width": stretch_width,
}


@component
def content_keywords() -> Div:
    return Div(
        style=col,
        children=tuple(
            Div(
                style=row,
                children=(Text(style=keyword | border | text_wrap_stable, content=f"{name} sizes this"),),
            )
            for name, keyword in KEYWORDS.items()
        ),
    )


# --8<-- [end:content-keywords]

# --8<-- [start:content-keywords-col]


@component
def content_keywords_col() -> Div:
    return Div(
        style=col,
        children=tuple(
            Text(style=keyword | border | text_wrap_stable, content=f"{name} sizes this")
            for name, keyword in KEYWORDS.items()
        ),
    )


# --8<-- [end:content-keywords-col]

# --8<-- [start:fill]


@component
def filling() -> Div:
    return Div(
        style=col,
        children=(
            Text(style=border, content="content height"),
            Text(style=fill(1) | border, content="fill(1): the rest of the col"),
            Div(
                style=row,
                children=(Text(style=full_width | border, content="full_width: the whole row"),),
            ),
        ),
    )


# --8<-- [end:fill]

# --8<-- [start:clamped]


@component
def clamped() -> Div:
    return Div(
        style=col,
        children=(
            Div(
                style=row,
                children=(
                    Text(style=fill(1) | max_width(20) | border, content="fill(1)\nmax_width(20)"),
                    Text(style=fill(1) | border, content="fill(1)"),
                ),
            ),
            Div(
                style=row | width(40) | border | border_heavy,
                children=(
                    Text(style=width(30) | min_width(24) | border, content="width(30)\nmin_width(24)"),
                    Text(style=width(30) | border, content="width(30)"),
                ),
            ),
        ),
    )


# --8<-- [end:clamped]

# --8<-- [start:aspect-ratio]


@component
def aspect() -> Div:
    return Div(
        style=row | align_children_start,
        children=(
            Text(style=width(18) | aspect_ratio(1) | border, content="width(18)\naspect_ratio(1)"),
            Text(style=width(18) | aspect_ratio(2) | border, content="width(18)\naspect_ratio(2)"),
        ),
    )


# --8<-- [end:aspect-ratio]

# --8<-- [start:box-sizing]


@component
def box_sizing() -> Div:
    return Div(
        style=col | align_children_start,
        children=(
            Text(style=width(24) | pad_x(2) | border, content="width(24)"),
            Text(style=content_box | width(24) | pad_x(2) | border, content="content_box | width(24)"),
        ),
    )


# --8<-- [end:box-sizing]


ROOTS = (fixed, fit, content_keywords, content_keywords_col, filling, clamped, aspect, box_sizing)

# --8<-- [start:scenes]

from counterweight.examples.scenes import Still

STILLS = [
    Still("layout-size-fixed", fixed(), (50, 11)),
    Still("layout-size-fit", fit(), (50, 6)),
    Still("layout-size-content-keywords", content_keywords(), (40, 13)),
    Still("layout-size-content-keywords-col", content_keywords_col(), (40, 12)),
    Still("layout-size-fill", filling(), (50, 10)),
    Still("layout-size-clamped", clamped(), (60, 10)),
    Still("layout-size-aspect-ratio", aspect(), (36, 18)),
    Still("layout-size-box-sizing", box_sizing(), (30, 6)),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
