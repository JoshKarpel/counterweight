"""
Terminals: Embedded terminals

A shell in a terminal widget, which Ctrl+Q quits since the shell gets every other key.
"""

import asyncio
import os
import sys
from functools import cache

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.elements import Canvas
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.emulator import Emulator
from counterweight.events import InputEvent
from counterweight.events import InputHandler
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.handlers import first
from counterweight.headless import use_terminal
from counterweight.hooks import use_rects
from counterweight.keys import Key
from counterweight.painters.terminal import ScreenView
from counterweight.styles.utilities import *
from counterweight.widgets import TerminalStyles
from counterweight.widgets import terminal

# --8<-- [start:widget]

SHELL = (os.environ.get("SHELL", "/bin/sh"),)


def quit_on_ctrl_q(event: InputEvent, receiver: Receiver) -> InputResponse:
    match event:
        case KeyPressed(key=Key.ControlQ):
            return Quit()
        case _:
            return None


@component
def shell(command: tuple[str, ...] = SHELL) -> Div:
    return Div(
        style=col | full,
        children=(
            # Ctrl+] bubbles past the shell, so an app that embeds this one, such as the examples' gallery, gets it.
            terminal(
                command,
                style=fill(1),
                intercept=quit_on_ctrl_q,
                auto_focus=True,
                skips={Key.ControlRightBracket},
            ),
            Text(content="Ctrl+Q quits", style=text_color("slate", 500)),
        ),
    )


# --8<-- [end:widget]

# --8<-- [start:pane]


@component
def pane(argv: tuple[str, ...], prefix: InputHandler) -> Canvas:
    # The terminal is the canvas's content box, so it resizes with the pane.
    content = use_rects().content
    embedded = use_terminal(argv, content.width, content.height, auto_focus=True)

    return Canvas(
        painter=embedded.view,
        style=fill(1) | border | border_heavy | (border_color("amber", 400) if embedded.focus.is_focused else default),
        on_input=first(prefix, embedded.on_input),
    )


# --8<-- [end:pane]

LISTING = (
    b"\x1b]0;~/project\x07"
    b"\x1b[1;32m~/project\x1b[0m $ ls --color\r\n"
    b"\x1b[1;34mdocs\x1b[0m  \x1b[1;34msrc\x1b[0m  \x1b[1;34mtests\x1b[0m  README.md  \x1b[1;32mbuild.sh\x1b[0m\r\n"
    b"\x1b[1;32m~/project\x1b[0m $ git status --short\r\n"
    b" \x1b[31mM\x1b[0m src/app.py\r\n"
    b"\x1b[32mA\x1b[0m  tests/test_app.py\r\n"
    b"\x1b[1;32m~/project\x1b[0m $ "
)


@cache
def recorded_screen(output: bytes, columns: int, rows: int) -> ScreenView:
    """What `output` draws on a terminal, fed to an emulator the first time it's asked for."""
    with Emulator(columns, rows, on_reply=lambda reply: None) as emulator:
        emulator.feed(output)
        return ScreenView(emulator.snapshot(), show_cursor=True)


@component
def recorded_terminal() -> Div:
    styles = TerminalStyles()
    listing = recorded_screen(LISTING, columns=38, rows=6)
    return Div(children=(Canvas(painter=listing, style=styles.box_style(size(40, 8), is_focused=True)),))


ROOTS = (shell, recorded_terminal)

# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import WaitFor
from counterweight.examples.scenes import Still

# A shell whose prompt and environment are the same for everyone, so its still comes out the same on every machine.
PLAIN_SHELL = ("env", "-i", "PATH=/usr/bin:/bin", "PS1=$ ", "sh")


def prompts(count: int) -> WaitFor:
    """Wait until the screen shows `count` prompts, which the shell prints in its own time."""
    return WaitFor(lambda frame: frame.text(ansi=False).count("$ ") >= count, timeout=timedelta(seconds=30))


STILLS = [
    Still("terminals-shell", recorded_terminal(), (40, 8)),
    Still(
        "terminals-widget",
        shell(PLAIN_SHELL),
        (40, 6),
        steps=[
            prompts(1),
            *(KeyPressed(key=character) for character in "echo hi"),
            KeyPressed(key=Key.Enter),
            prompts(2),
        ],
    ),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
