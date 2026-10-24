"""
Layout: Layering

Relative and absolute positioning, a dialog over the app, dropdowns, and a badge.
"""

import asyncio
import sys

from counterweight import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles import Style
from counterweight.styles.utilities import *

# --8<-- [start:relative]


@component
def relative() -> Div:
    return Div(
        style=row | align_children_start | gap(3),
        children=(
            Text(style=border, content="first"),
            Text(
                style=position_relative | inset_top(2) | inset_left(2) | border | border_heavy,
                content="position_relative\ninset_top(2)\ninset_left(2)",
            ),
            Text(style=border, content="third"),
        ),
    )


# --8<-- [end:relative]

# --8<-- [start:absolute]


@component
def absolute() -> Div:
    return Div(
        style=col | border,
        children=(
            Text(content="first, in flow"),
            Text(
                style=position_absolute | inset_top(2) | inset_left(10) | border | border_heavy,
                content="position_absolute\ninset_top(2)\ninset_left(10)",
            ),
            Text(content="second, in flow"),
        ),
    )


# --8<-- [end:absolute]

# --8<-- [start:dialog]

dialog_box = position_absolute | inset(0) | margin_auto | fit_content_width | fit_content_height


@component
def dialog() -> Div:
    return Div(
        style=col,
        children=(
            Text(style=border, content="header"),
            Text(
                style=fill(1) | border | text_wrap_stable,
                content="The app's content stays where it is, and the dialog draws over it. " * 4,
            ),
            Text(
                style=dialog_box | border | border_double | pad_x(2) | pad_y(1),
                content="a dialog centered over the app",
            ),
        ),
    )


# --8<-- [end:dialog]

# --8<-- [start:dropdown]


def menu_bar(toolbar_style: Style) -> Div:
    return Div(
        style=col,
        children=(
            Div(
                style=toolbar_style | row | gap(2) | border | pad_x(1),
                children=(
                    Text(content="file"),
                    Text(content="edit"),
                    Text(
                        style=z(1) | position_absolute | inset_top(2) | inset_left(0) | border | border_heavy,
                        content="new\nopen\nsave\nquit",
                    ),
                ),
            ),
            Text(style=border, content="The page's content"),
        ),
    )


@component
def dropdown_escapes() -> Div:
    return menu_bar(toolbar_style=Style())


@component
def dropdown_scoped() -> Div:
    return menu_bar(toolbar_style=z(0))


# --8<-- [end:dropdown]

# --8<-- [start:badge]


@component
def badge() -> Div:
    return Div(
        style=row | align_children_start | gap(2),
        children=(
            Div(
                style=border | pad_x(1),
                children=(
                    Text(content="inbox"),
                    Text(
                        style=position_absolute
                        | inset_top(-1)
                        | inset_right(1)
                        | clip_to_border
                        | text_color("red", 500),
                        content="3",
                    ),
                ),
            ),
            Div(
                style=border | pad_x(1),
                children=(
                    Text(content="alerts"),
                    Text(
                        style=position_absolute
                        | inset_top(-1)
                        | inset_right(-1)
                        | clip_to_border
                        | text_bg("red", 600),
                        content="!",
                    ),
                ),
            ),
        ),
    )


# --8<-- [end:badge]


ROOTS = (relative, absolute, dialog, dropdown_escapes, dropdown_scoped, badge)

# --8<-- [start:scenes]

from counterweight.examples.scenes import Still

STILLS = [
    Still("layout-relative", relative(), (39, 7)),
    Still("layout-absolute", absolute(), (50, 9)),
    Still("layout-dialog", dialog(), (60, 12)),
    Still("layout-dropdown-escapes", dropdown_escapes(), (30, 9)),
    Still("layout-dropdown-scoped", dropdown_scoped(), (30, 9)),
    Still("layout-badge", badge(), (21, 3)),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
