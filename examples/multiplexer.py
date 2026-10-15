"""
A tiny terminal multiplexer: shells side by side, each in its own embedded terminal.

Run it with `uv run python -m examples.multiplexer`.
Ctrl+B is the prefix, as in tmux. After it:
  %       open another shell to the right, focused
  o       focus the next pane
  x       close the focused pane
  q       quit
  Ctrl+Z  suspend to the shell that started the multiplexer, until `fg`
  Ctrl+B  send Ctrl+B to the focused program
A click focuses the pane clicked. Every other key goes to the focused pane's program, Ctrl+C included.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from dataclasses import dataclass

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import FocusNext
from counterweight.controls import FocusOn
from counterweight.controls import Quit
from counterweight.controls import Suspend
from counterweight.elements import Canvas
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputHandler
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.handlers import first
from counterweight.headless import use_terminal
from counterweight.hooks import FocusHandle
from counterweight.hooks import use_effect
from counterweight.hooks import use_rects
from counterweight.hooks import use_ref
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.programs import Exited
from counterweight.programs import FailedToStart
from counterweight.pseudoterminal import PtyStatus
from counterweight.styles.utilities import *

SHELL = (os.environ.get("SHELL", "/bin/sh"),)


@dataclass(frozen=True, slots=True)
class Pane:
    number: int
    handle: FocusHandle


def first_pane() -> tuple[Pane, ...]:
    return (Pane(number=1, handle=FocusHandle()),)


def status_text(title: str, status: PtyStatus) -> str:
    match status:
        case Exited(status=code):
            return f"exited {code}"
        case FailedToStart(reason=reason):
            return f"failed to start: {reason}"
        case _:
            return title


@component
def pane(number: int, handle: FocusHandle, prefix: InputHandler, on_status: Callable[[int, str], None]) -> Canvas:
    content = use_rects().content
    terminal = use_terminal(SHELL, content.width, content.height, handle=handle, auto_focus=True)
    status = status_text(terminal.screen.title, terminal.status)

    async def report_status() -> None:
        on_status(number, status)

    use_effect(report_status, deps=(status,))

    return Canvas(
        painter=terminal.view,
        style=fill(1)
        | border
        | border_lightrounded
        | (border_color("amber", 400) if terminal.focus.is_focused else border_color("slate", 600)),
        on_input=first(prefix, terminal.on_input),
    )


@component
def root() -> Div:
    panes, set_panes = use_state(first_pane)
    statuses, set_statuses = use_state(dict[int, str]())
    # A ref, not state, so a prefix and its key in one read still work: see the Prefix Keys cookbook page.
    is_armed = use_ref(False)
    shows_armed, set_shows_armed = use_state(False)

    def arm(value: bool) -> None:
        is_armed.current = value
        set_shows_armed(value)

    def prefixed(key: str, focused: FocusHandle | None) -> InputResponse:
        match key:
            case "%":
                handle = FocusHandle()
                set_panes(
                    lambda panes: (
                        *panes,
                        Pane(number=max((pane.number for pane in panes), default=0) + 1, handle=handle),
                    )
                )
                return FocusOn(handle)
            case "o":
                return FocusNext()
            case "x":
                set_panes(lambda panes: tuple(pane for pane in panes if pane.handle != focused))
                return FocusNext()
            case "q":
                return Quit()
            case Key.ControlZ:
                return Suspend.to_shell()
            case Key.ControlB:
                return None  # The pane's terminal sends it to its program.
            case _:
                return ()

    def prefix(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.ControlB) if not is_armed.current:
                arm(True)
                return ()
            case KeyPressed(key=key) if is_armed.current:
                arm(False)
                return prefixed(key, receiver.focus_handle)
            case _:
                return None

    def on_status(number: int, status: str) -> None:
        set_statuses(lambda statuses: statuses if statuses.get(number) == status else {**statuses, number: status})

    bar = "  ".join(f"[{p.number}] {statuses.get(p.number, '')}" for p in panes)
    return Div(
        style=col | full,
        on_input=prefix,
        children=(
            Div(
                style=row | grow(1),
                children=tuple(pane(p.number, p.handle, prefix, on_status).with_key(str(p.number)) for p in panes),
            ),
            Text(
                content=("PREFIX " if shows_armed else "") + bar,
                style=text_color("slate", 900) | text_bg("amber", 400 if shows_armed else 200) | text_wrap_none,
            ),
        ),
    )


if __name__ == "__main__":
    asyncio.run(app(root()))
