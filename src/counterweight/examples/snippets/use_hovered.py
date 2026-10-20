"""
Hooks: use_hovered

A menu that lights the item under the pointer, and which parts of a box the pointer is over.
"""

import asyncio
import sys

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.hooks import use_hovered
from counterweight.styles.utilities import *

# --8<-- [start:menu]


@component
def menu_item(label: str) -> Text:
    hovered = use_hovered()

    return Text(
        content=f"{'>' if hovered.border else ' '} {label}",
        style=pad_right(1) | (text_bg("sky", 800) if hovered.border else text_color("slate", 300)),
    )


@component
def menu() -> Div:
    return Div(
        style=col | border | border_lightrounded | fit_content_width,
        children=tuple(menu_item(label) for label in ("New file", "Open...", "Save", "Save as...", "Quit")),
    )


# --8<-- [end:menu]

# --8<-- [start:boxes]


@component
def boxes() -> Div:
    hovered = use_hovered()

    return Div(
        style=col
        | margin(1)
        | margin_color("slate", 800)
        | border
        | border_lightrounded
        | (border_color("amber", 400) if hovered.border else None)
        | pad(1)
        | padding_color("slate", 700)
        | content_color("slate", 900)
        | fit_content_width,
        children=tuple(
            Text(
                content=f"{name:<7} {'yes' if is_hovered else 'no'}",
                style=text_color("emerald" if is_hovered else "slate", 400),
            )
            for name, is_hovered in (
                ("content", hovered.content),
                ("padding", hovered.padding),
                ("border", hovered.border),
                ("margin", hovered.margin),
            )
        ),
    )


# --8<-- [end:boxes]


ROOTS = (menu, boxes)

# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import paced
from counterweight.controls import AdvanceClock
from counterweight.events import MouseMoved
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still
from counterweight.geometry import Position


def moves(*positions: tuple[int, int]) -> list[MouseMoved]:
    return [MouseMoved(absolute=Position(x, y), button=None) for x, y in positions]


STILLS = [
    Still("use-hovered-menu", menu(), (24, 7), steps=[*moves((20, 1), (6, 3))]),
    Still("use-hovered-boxes", boxes(), (24, 10), steps=[*moves((2, 3))]),
]


DEMOS = [
    Demo(
        "use-hovered-menu",
        menu(),
        (24, 7),
        steps=[
            *paced(
                moves((20, 0), (14, 1), (8, 2), (7, 3), (6, 4), (6, 5), (12, 6), (20, 6)),
                pause=AdvanceClock(by=timedelta(milliseconds=300)),
            ),
            AdvanceClock(by=timedelta(seconds=2)),
        ],
    ),
    Demo(
        "use-hovered-boxes",
        boxes(),
        (24, 10),
        steps=[
            *paced(
                moves((20, 4), (16, 4), (15, 4), (14, 4), (10, 4), (10, 7), (10, 8), (10, 9), (20, 9)),
                pause=AdvanceClock(by=timedelta(milliseconds=400)),
            ),
            AdvanceClock(by=timedelta(seconds=2)),
        ],
    ),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
