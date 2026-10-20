"""
Layout: App shells

A header, body and footer; a sidebar and a status bar; and three panes.
"""

import asyncio
import sys

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles.utilities import *

# --8<-- [start:header-body-footer]


@component
def header_body_footer() -> Div:
    return Div(
        style=col,
        children=(
            Text(style=border | border_heavy | text_justify_center, content="header: content height"),
            Text(style=fill(1) | border, content="body: fill(1)"),
            Text(style=text_bg("slate", 700), content=" footer: one row, no border"),
        ),
    )


# --8<-- [end:header-body-footer]

# --8<-- [start:sidebar-status]


@component
def sidebar_status() -> Div:
    return Div(
        style=col,
        children=(
            Div(
                style=row | fill(1),
                children=(
                    Text(style=length(20) | border, content="sidebar:\nlength(20)"),
                    Text(style=fill(1) | border, content="main: fill(1)"),
                ),
            ),
            Text(style=text_bg("slate", 700), content=" status bar: one row, no border"),
        ),
    )


# --8<-- [end:sidebar-status]

# --8<-- [start:three-panes]


@component
def three_panes() -> Div:
    return Div(
        style=row | border_collapse,
        children=(
            Text(style=length(20) | border, content="files:\nlength(20)"),
            Div(
                style=col | fill(1) | border_collapse,
                children=(
                    Text(style=fill(2) | border, content="editor: fill(2)"),
                    Text(style=fill(1) | border, content="terminal: fill(1)"),
                ),
            ),
            Text(style=length(20) | border, content="outline:\nlength(20)"),
        ),
    )


# --8<-- [end:three-panes]


ROOTS = (header_body_footer, sidebar_status, three_panes)

# --8<-- [start:scenes]

from counterweight.examples.scenes import Still

STILLS = [
    Still("layout-shell-header-body-footer", header_body_footer(), (60, 10)),
    Still("layout-shell-sidebar-status", sidebar_status(), (60, 10)),
    Still("layout-shell-three-panes", three_panes(), (80, 14)),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
