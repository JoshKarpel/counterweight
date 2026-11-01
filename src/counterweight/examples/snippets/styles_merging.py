"""
Styles: Merging styles

Styles layered with `|`, and a toolbar whose buttons merge in styles as they're selected and hovered.
"""

import asyncio
import sys
from collections.abc import Callable

from counterweight import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.handlers import on_click
from counterweight.hooks import use_hovered
from counterweight.hooks import use_state
from counterweight.styles import CellStyle
from counterweight.styles import Style
from counterweight.styles import merge
from counterweight.styles.utilities import *

# --8<-- [start:layering]

MERGES: tuple[tuple[str, Style], ...] = (
    ('text_color("red", 500) | text_bg("slate", 800)', text_color("red", 500) | text_bg("slate", 800)),
    ('text_color("red", 500) | text_color("sky", 400)', text_color("red", 500) | text_color("sky", 400)),
    (
        "Style(text_style=CellStyle(bold=True)) | Style(text_style=CellStyle(italic=True))",
        Style(text_style=CellStyle(bold=True)) | Style(text_style=CellStyle(italic=True)),
    ),
    ("border | border_heavy", border | border_heavy),
    ("border | border_heavy | border_double", border | border_heavy | border_double),
    ("border | border_heavy | border_none", border | border_heavy | border_none),
)


@component
def layering() -> Div:
    return Div(
        style=col | align_children_start | gap(1),
        children=tuple(Text(style=style, content=expression) for expression, style in MERGES),
    )


# --8<-- [end:layering]

# --8<-- [start:conditional]

BUTTON = border | border_lightrounded | border_color("slate", 500) | pad_x(1)
SELECTED = border_heavy | border_color("amber", 400) | text_color("amber", 300)
HOVERED = text_bg("slate", 700) | padding_color("slate", 700)


@component
def button(label: str, is_selected: bool, select: Callable[[str], object]) -> Text:
    hovered = use_hovered()

    def choose() -> None:
        select(label)

    return Text(
        content=label,
        style=merge(BUTTON, SELECTED if is_selected else None, HOVERED if hovered.border else None),
        on_input=on_click(choose),
    )


@component
def toolbar() -> Div:
    selected, set_selected = use_state("Edit")

    return Div(
        style=row | gap(1),
        children=tuple(button(label, label == selected, set_selected) for label in ("File", "Edit", "View", "Help")),
    )


# --8<-- [end:conditional]


ROOTS = (layering, toolbar)

# --8<-- [start:scenes]

from counterweight.events import MouseMoved
from counterweight.examples.scenes import Still
from counterweight.geometry import Position

STILLS = [
    Still("styles-merging-layering", layering(), (82, 15)),
    Still("styles-merging-conditional", toolbar(), (35, 3), steps=[MouseMoved(absolute=Position(19, 1), button=None)]),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
