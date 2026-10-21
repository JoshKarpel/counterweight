"""
Layout: Alignment

Children justified and aligned along each axis, centered, and overflowing.
"""

import asyncio
import sys

from counterweight import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles.utilities import *

# --8<-- [start:title]


def title(content: str) -> Text:
    return Text(content=f" {content} ", style=position_absolute | inset_top(-1) | inset_left(1) | clip_to_border)


# --8<-- [end:title]

# --8<-- [start:justify]


@component
def justify() -> Div:
    return Div(
        style=col,
        children=tuple(
            Div(
                style=row | justify | border,
                children=(
                    title(name),
                    Text(style=border | border_heavy, content="a"),
                    Text(style=border | border_heavy, content="bb"),
                    Text(style=border | border_heavy, content="ccc"),
                ),
            )
            for name, justify in (
                ("justify_children_start", justify_children_start),
                ("justify_children_center", justify_children_center),
                ("justify_children_end", justify_children_end),
                ("justify_children_space_between", justify_children_space_between),
                ("justify_children_space_around", justify_children_space_around),
                ("justify_children_space_evenly", justify_children_space_evenly),
            )
        ),
    )


# --8<-- [end:justify]

# --8<-- [start:align]


@component
def align() -> Div:
    return Div(
        style=row,
        children=tuple(
            Div(
                style=row | align | fill(1) | border,
                children=(
                    title(name),
                    Text(style=border | border_heavy, content="a"),
                    Text(style=border | border_heavy, content="b\nb"),
                    Text(style=border | border_heavy, content="c\nc\nc"),
                ),
            )
            for name, align in (
                ("align_children_start", align_children_start),
                ("align_children_center", align_children_center),
                ("align_children_end", align_children_end),
                ("align_children_stretch", align_children_stretch),
            )
        ),
    )


# --8<-- [end:align]

# --8<-- [start:align-self]


@component
def align_self() -> Div:
    return Div(
        style=row | align_children_start | gap(1) | border,
        children=(
            title("row | align_children_start"),
            Text(style=border | border_heavy, content="no align_self"),
            Text(style=align_self_center | border | border_heavy, content="align_self_center"),
            Text(style=align_self_end | border | border_heavy, content="align_self_end"),
            Text(style=align_self_stretch | border | border_heavy, content="align_self_stretch"),
        ),
    )


# --8<-- [end:align-self]

# --8<-- [start:reverse]


@component
def reverse() -> Div:
    def items() -> tuple[Text, ...]:
        return tuple(Text(style=border | border_heavy, content=content) for content in ("1", "22", "333"))

    return Div(
        style=col,
        children=(
            *(
                Div(style=direction | border, children=(title(name), *items()))
                for name, direction in (
                    ("row", row),
                    ("row_reverse", row_reverse),
                    ("row_reverse | justify_children_start", row_reverse | justify_children_start),
                )
            ),
            Div(
                style=row,
                children=tuple(
                    Div(
                        style=direction | align_children_start | height(13) | fill(1) | border,
                        children=(title(name), *items()),
                    )
                    for name, direction in (
                        ("col", col),
                        ("col_reverse", col_reverse),
                        ("… | justify_children_start", col_reverse | justify_children_start),
                    )
                ),
            ),
        ),
    )


# --8<-- [end:reverse]

# --8<-- [start:center]


@component
def center() -> Div:
    return Div(
        style=row,
        children=(
            Div(
                style=row | center_children | fill(1) | border,
                children=(title("flexbox"), Text(style=border | border_heavy, content="centered")),
            ),
            Div(
                style=display_grid | center_children | fill(1) | border,
                children=(title("grid"), Text(style=border | border_heavy, content="centered")),
            ),
        ),
    )


# --8<-- [end:center]

# --8<-- [start:grid-items]


@component
def grid_items() -> Div:
    return Div(
        style=row,
        children=tuple(
            Div(
                style=display_grid | grid_template_columns(fr(1)) | justify | fill(1) | border,
                children=(
                    title(name),
                    Text(style=border | border_heavy, content="a"),
                    Text(style=border | border_heavy, content="bb"),
                    Text(style=border | border_heavy, content="ccc"),
                ),
            )
            for name, justify in (
                ("justify_items_start", justify_items_start),
                ("justify_items_center", justify_items_center),
                ("justify_items_end", justify_items_end),
                ("justify_items_stretch", justify_items_stretch),
            )
        ),
    )


# --8<-- [end:grid-items]

# --8<-- [start:grid-self]


@component
def grid_self() -> Div:
    return Div(
        style=display_grid | grid_template_columns(fr(1), fr(1)) | justify_items_start | gap_width(1) | border,
        children=(
            title("display_grid | justify_items_start"),
            Text(style=border | border_heavy, content="no justify_self"),
            Text(style=justify_self_center | border | border_heavy, content="justify_self_center"),
            Text(style=justify_self_end | border | border_heavy, content="justify_self_end"),
            Text(style=justify_self_stretch | border | border_heavy, content="justify_self_stretch"),
        ),
    )


# --8<-- [end:grid-self]

TALL = "\n".join(f"line {n}" for n in range(1, 13))

# --8<-- [start:overflow]


@component
def overflow() -> Div:
    return Div(
        style=row,
        children=tuple(
            Div(
                style=col | justify | fill(1) | border,
                children=(title(name), Text(content=TALL)),
            )
            for name, justify in (
                ("justify_children_center", justify_children_center),
                ("justify_children_center_unsafe", justify_children_center_unsafe),
            )
        ),
    )


# --8<-- [end:overflow]


ROOTS = (justify, align, align_self, reverse, center, grid_items, grid_self, overflow)

# --8<-- [start:scenes]

from counterweight.examples.scenes import Still

STILLS = [
    Still("layout-justify-children", justify(), (50, 30)),
    Still("layout-align-children", align(), (120, 9)),
    Still("layout-align-self", align_self(), (80, 9)),
    Still("layout-reverse", reverse(), (96, 28)),
    Still("layout-center", center(), (50, 9)),
    Still("layout-justify-items", grid_items(), (100, 11)),
    Still("layout-justify-self", grid_self(), (60, 8)),
    Still("layout-center-overflow", overflow(), (70, 9)),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
