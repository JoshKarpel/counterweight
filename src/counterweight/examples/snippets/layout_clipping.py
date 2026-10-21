"""
Layout: Clipping

Overflow hidden on both axes or one, clipping to a box, and what escapes the clip.
"""

import asyncio
import sys

import waxy

from counterweight import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.focus import ElementHandle
from counterweight.styles import Style
from counterweight.styles.utilities import *

LINES = "\n".join(f"line {i} of a long paragraph" for i in range(1, 7))

# --8<-- [start:hidden]


@component
def hidden() -> Div:
    return Div(
        style=row | gap(2),
        children=tuple(
            Div(
                style=col,
                children=(
                    Div(
                        style=col | border | height(4) | width(20) | overflow,
                        children=tuple(Text(content=f"line {i}") for i in range(1, 7)),
                    ),
                    Text(content="below"),
                ),
            )
            for overflow in (overflow_visible, overflow_hidden)
        ),
    )


# --8<-- [end:hidden]

# --8<-- [start:one-axis]


@component
def one_axis() -> Div:
    return Div(
        style=row | gap(8),
        children=tuple(
            Div(
                style=border | height(4) | width(16) | overflow,
                children=(Text(content=LINES, style=height(6)),),
            )
            for overflow in (overflow_x_hidden, overflow_y_hidden)
        ),
    )


# --8<-- [end:one-axis]

# --8<-- [start:clip-to]


@component
def clip_to() -> Div:
    return Div(
        style=row,
        children=tuple(
            Div(
                style=fill(1) | border | pad_x(1),
                children=(
                    Text(content=f" {name} ", style=position_absolute | inset_top(-1) | inset_left(1) | clip),
                    Text(content="fill(1) hides its overflow"),
                ),
            )
            for name, clip in (("clip_to_padding", clip_to_padding), ("clip_to_border", clip_to_border))
        ),
    )


# --8<-- [end:clip-to]

# --8<-- [start:raised]


@component
def raised() -> Div:
    return Div(
        style=col,
        children=(
            Div(
                style=col | border | size(30, 5) | overflow_hidden,
                children=(
                    Text(content="File  Edit  View"),
                    Text(
                        content="Open…\nSave\nSave As…\nQuit",
                        style=z(1) | position_absolute | inset_top(1) | inset_left(0) | border | border_heavy,
                    ),
                ),
            ),
            Text(content="The menu is cut off inside the box's border,\nhowever high its z."),
        ),
    )


# --8<-- [end:raised]

# --8<-- [start:unclipped]


@component
def unclipped() -> Div:
    return Div(
        style=col,
        children=(
            Div(
                style=col | border | size(30, 5) | overflow_hidden,
                children=(
                    Text(content="File  Edit  View"),
                    Text(
                        content="Open…\nSave\nSave As…\nQuit",
                        style=z(1)
                        | position_absolute
                        | inset_top(1)
                        | inset_left(0)
                        | clip_to_screen
                        | border
                        | border_heavy,
                    ),
                ),
            ),
            Text(content="With clip_to_screen, the menu\nreaches past the box.", style=pad_left(11)),
        ),
    )


# --8<-- [end:unclipped]

# --8<-- [start:percent-inset]

below_parent = Style(layout=waxy.Style(position=waxy.Position.Absolute, inset_top=waxy.Percent(1.0)))


@component
def percent_inset() -> Div:
    return Div(
        style=border | width(30) | pad_x(1),
        children=(
            Text(content="inset_top=Percent(1.0)"),
            Text(content=" on the border row ", style=below_parent | inset_left(1) | clip_to_border),
        ),
    )


# --8<-- [end:percent-inset]

# --8<-- [start:scrolled-panels]

PANELS = ElementHandle()


@component
def scrolled_panels() -> Div:
    return Div(
        style=col | size(24, 6) | overflow_y_scroll,
        handle=PANELS,
        children=tuple(
            Div(
                style=border | border_lightrounded | height(3) | shrink(0),
                children=(
                    Text(
                        content=f" {title} ", style=position_absolute | inset_top(-1) | inset_left(1) | clip_to_border
                    ),
                    Text(content=body),
                ),
            )
            for title, body in (("web", "3 replicas"), ("worker", "8 replicas"), ("cron", "1 replica"))
        ),
    )


# --8<-- [end:scrolled-panels]


ROOTS = (hidden, one_axis, clip_to, raised, unclipped, percent_inset, scrolled_panels)

# --8<-- [start:scenes]

from counterweight.controls import ScrollTo
from counterweight.examples.scenes import Still

STILLS = [
    Still("layout-clipping-hidden", hidden(), (42, 9)),
    Still("layout-clipping-one-axis", one_axis(), (40, 8)),
    Still("layout-clipping-clip-to", clip_to(), (60, 3)),
    Still("layout-clipping-raised", raised(), (48, 7)),
    Still("layout-clipping-unclipped", unclipped(), (48, 7)),
    Still("layout-clipping-percent-inset", percent_inset(), (30, 3)),
    Still("layout-clipping-scrolled-panels", scrolled_panels(), (24, 6), steps=[ScrollTo(PANELS, y=1)]),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
