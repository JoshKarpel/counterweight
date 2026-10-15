"""
A tiny terminal multiplexer: shells side by side, each in its own embedded terminal.

Run it with `uv run python -m examples.multiplexer`.
Ctrl+B is the prefix, as in tmux, and the bar along the bottom shows the keys that follow it, as zellij's does:
  %       open another shell to the right, focused
  o       focus the next pane
  x       close the focused pane
  q       quit
  Ctrl+Z  suspend to the shell that started the multiplexer, until `fg`
  Ctrl+B  send Ctrl+B to the focused program
A click focuses the pane clicked. Every other key goes to the focused pane's program, Ctrl+C included.
A pane closes when its shell exits, and the multiplexer quits when its last pane closes.
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
from counterweight.elements import Chunk
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
from counterweight.hooks import use_controls
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

COMMANDS = (
    ("%", "SPLIT"),
    ("o", "NEXT"),
    ("x", "CLOSE"),
    ("q", "QUIT"),
    ("Ctrl z", "SUSPEND"),
    ("Ctrl b", "SEND Ctrl b"),
)


@dataclass(frozen=True, slots=True)
class Pane:
    number: int
    handle: FocusHandle


def first_pane() -> tuple[Pane, ...]:
    return (Pane(number=1, handle=FocusHandle()),)


def status_text(title: str, status: PtyStatus) -> str:
    match status:
        case FailedToStart(reason=reason):
            return f"failed to start: {reason}"
        case _:
            return title


def key_hints(is_armed: bool) -> tuple[Chunk, ...]:
    """The prefix, then each key that can follow it, lit while the prefix is armed."""
    mode = Chunk(
        content=" PREFIX " if is_armed else " Ctrl b ",
        style=CellStyle(foreground=slate_900, background=emerald_400 if is_armed else slate_400, bold=True),
    )
    key = CellStyle(foreground=amber_400 if is_armed else slate_500, background=slate_700, bold=is_armed)
    label = CellStyle(foreground=slate_100 if is_armed else slate_500, background=slate_700)
    hints = (
        chunk
        for command, name in COMMANDS
        for chunk in (Chunk.space(), Chunk(content=f" <{command}> ", style=key), Chunk(content=f"{name} ", style=label))
    )
    return (mode, *hints)


@component
def pane(number: int, handle: FocusHandle, prefix: InputHandler, close: Callable[[FocusHandle, bool], None]) -> Div:
    content = use_rects().content
    terminal = use_terminal(SHELL, content.width, content.height, handle=handle, auto_focus=True)
    is_focused = terminal.focus.is_focused
    has_exited = isinstance(terminal.status, Exited)

    async def close_on_exit() -> None:
        if has_exited:
            close(handle, is_focused)

    use_effect(close_on_exit, deps=(has_exited,))
    status = status_text(terminal.screen.title, terminal.status)
    title = f" Pane #{number} · {status} " if status else f" Pane #{number} "

    return Div(
        style=fill(1)
        | border
        | border_lightrounded
        | (border_color("emerald", 400) if is_focused else border_color("slate", 600)),
        on_input=first(prefix, terminal.on_input),
        children=(
            Canvas(painter=terminal.view, style=fill(1)),
            # A box that stops short of the corner clips the title, since a Text stretched that wide would blank the border.
            Div(
                style=position_absolute
                | inset_top(-1)
                | inset_left(1)
                | inset_right(1)
                | clip_to_border
                | overflow_x_clip,
                children=(
                    Text(
                        content=title,
                        style=text_wrap_none | (text_color("emerald", 400) if is_focused else text_color("slate", 400)),
                    ),
                ),
            ),
        ),
    )


@component
def root() -> Div:
    panes, set_panes = use_state(first_pane)
    send_control = use_controls()
    # A ref, not state, so a prefix and its key in one read still work: see the Prefix Keys cookbook page.
    is_armed = use_ref(False)
    shows_armed, set_shows_armed = use_state(False)

    def arm(value: bool) -> None:
        is_armed.current = value
        set_shows_armed(value)

    async def quit_when_empty() -> None:
        if not panes:
            send_control(Quit())

    use_effect(quit_when_empty, deps=(bool(panes),))

    def close(handle: FocusHandle, was_focused: bool) -> None:
        set_panes(lambda panes: tuple(pane for pane in panes if pane.handle != handle))
        if was_focused:
            send_control(FocusNext())

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

    return Div(
        style=col | full,
        on_input=prefix,
        children=(
            Div(
                style=row | grow(1),
                children=tuple(pane(p.number, p.handle, prefix, close).with_key(str(p.number)) for p in panes),
            ),
            Text(content=key_hints(shows_armed), style=text_wrap_none),
        ),
    )


if __name__ == "__main__":
    asyncio.run(app(root()))
