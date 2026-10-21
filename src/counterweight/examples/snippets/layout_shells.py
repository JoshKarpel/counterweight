"""
Layout: App shells

A header, body and footer; a sidebar and a status bar; three panes; and panes that hide.
"""

import asyncio
import sys
from datetime import timedelta

from counterweight import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import toggle
from counterweight.hooks import use_clock
from counterweight.hooks import use_state
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

# --8<-- [start:hiding]


@component
def pane(name: str) -> Text:
    mounted_for = use_clock(timedelta(seconds=1)).since_mount
    return Text(
        style=length(18) | border,
        content=f"{name}\n\nmounted for\n{mounted_for // timedelta(seconds=1)} s",
    )


@component
def hiding() -> Div:
    is_hidden, set_hidden = use_state(False)
    is_left_out, set_left_out = use_state(False)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key="h"):
                set_hidden(toggle)
                return ()
            case KeyPressed(key="l"):
                set_left_out(toggle)
                return ()
            case _:
                return None

    return Div(
        style=col,
        on_input=on_input,
        children=(
            Div(
                style=row | fill(1),
                children=(
                    # Hidden, the pane takes no space and draws nothing, but stays mounted.
                    Div(style=display_none if is_hidden else default, children=(pane("display_none"),)),
                    Text(style=fill(1) | border, content="main: fill(1)"),
                    # Left out, the pane unmounts, and mounts afresh when it comes back.
                    *(() if is_left_out else (pane("left out"),)),
                ),
            ),
            Text(style=text_bg("slate", 700), content=" h: hide the left pane   l: leave out the right pane"),
        ),
    )


# --8<-- [end:hiding]


ROOTS = (header_body_footer, sidebar_status, three_panes, hiding)

# --8<-- [start:scenes]

from counterweight.controls import AdvanceClock
from counterweight.controls import Marker
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still

SECOND = AdvanceClock(by=timedelta(seconds=1))

STILLS = [
    Still("layout-shell-header-body-footer", header_body_footer(), (60, 10)),
    Still("layout-shell-sidebar-status", sidebar_status(), (60, 10)),
    Still("layout-shell-three-panes", three_panes(), (80, 14)),
    Still(
        "layout-shell-hiding",
        hiding(),
        (70, 8),
        steps=[
            AdvanceClock(by=timedelta(seconds=5)),
            KeyPressed(key="h"),
            KeyPressed(key="l"),
            AdvanceClock(by=timedelta(seconds=3)),
        ],
    ),
    Still(
        "layout-shell-hiding-back",
        hiding(),
        (70, 8),
        steps=[
            AdvanceClock(by=timedelta(seconds=5)),
            KeyPressed(key="h"),
            KeyPressed(key="l"),
            AdvanceClock(by=timedelta(seconds=3)),
            KeyPressed(key="h"),
            KeyPressed(key="l"),
            AdvanceClock(by=timedelta(seconds=2)),
        ],
    ),
]

DEMOS = [
    Demo(
        "layout-shell-hiding",
        hiding(),
        (70, 8),
        steps=[
            *[SECOND] * 3,
            Marker("Hide one pane, leave the other out"),
            KeyPressed(key="h"),
            KeyPressed(key="l"),
            *[SECOND] * 3,
            Marker("Bring both back"),
            KeyPressed(key="h"),
            KeyPressed(key="l"),
            *[SECOND] * 4,
        ],
    ),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
