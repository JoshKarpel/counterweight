"""
Terminal multiplexer

A tiny terminal multiplexer: shells side by side, each in its own embedded terminal.

Its keys are direct hotkeys, as zellij's are, rather than tmux's prefix, and the bar along the bottom shows them:
Alt+N opens another shell to the right, focused; Alt+Left and Alt+Right move focus between panes;
and Alt+X closes the focused pane.
A click focuses the pane clicked. Every other key goes to the focused pane's program, Ctrl+C and Ctrl+Z included.
A pane closes when its shell exits, and the multiplexer quits when its last pane closes, as tmux does.
In macOS terminals, Alt keys need Option set to send Meta (Use Option as Meta key, in Terminal's profile settings),
as zellij's do.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from collections.abc import Sequence
from dataclasses import dataclass

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import FocusNext
from counterweight.controls import FocusOn
from counterweight.controls import FocusPrevious
from counterweight.controls import Quit
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
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.programs import Exited
from counterweight.programs import FailedToStart
from counterweight.pseudoterminal import PtyStatus
from counterweight.styles.utilities import *

SHELL = (os.environ.get("SHELL", "/bin/sh"),)

HOTKEYS = (
    ("Alt n", "NEW PANE"),
    ("Alt ←/→", "FOCUS"),
    ("Alt x", "CLOSE"),
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


def key_hints() -> tuple[Chunk, ...]:
    """Each hotkey and what it does."""
    key = text_color(amber_400) | text_bg(slate_700) | text_bold
    label = text_color(slate_100) | text_bg(slate_700)
    return tuple(
        chunk
        for hotkey, name in HOTKEYS
        for chunk in (Chunk(content=f" <{hotkey}> ", style=key), Chunk(content=f"{name} ", style=label), Chunk.space())
    )


@component
def pane(
    number: int,
    command: Sequence[str],
    handle: FocusHandle,
    hotkeys: InputHandler,
    close: Callable[[FocusHandle, bool], None],
) -> Div:
    content = use_rects().content
    # Ctrl+] bubbles past the shell, so an app that embeds this one, such as the examples' gallery, gets it.
    terminal = use_terminal(
        command, content.width, content.height, handle=handle, auto_focus=True, skips={Key.ControlRightBracket}
    )
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
        on_input=first(hotkeys, terminal.on_input),
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
def root(command: Sequence[str] = SHELL) -> Div:
    panes, set_panes = use_state(first_pane)
    send_control = use_controls()

    async def quit_when_empty() -> None:
        if not panes:
            send_control(Quit())

    use_effect(quit_when_empty, deps=(bool(panes),))

    def close(handle: FocusHandle, was_focused: bool) -> None:
        set_panes(lambda panes: tuple(pane for pane in panes if pane.handle != handle))
        if was_focused:
            send_control(FocusNext())

    def hotkeys(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key="alt+n"):
                handle = FocusHandle()
                set_panes(
                    lambda panes: (
                        *panes,
                        Pane(number=max((pane.number for pane in panes), default=0) + 1, handle=handle),
                    )
                )
                return FocusOn(handle)
            case KeyPressed(key=Key.AltRight):
                return FocusNext()
            case KeyPressed(key=Key.AltLeft):
                return FocusPrevious()
            case KeyPressed(key="alt+x"):
                set_panes(lambda panes: tuple(pane for pane in panes if pane.handle != receiver.focus_handle))
                return FocusNext()
            case _:
                return None

    return Div(
        style=col | full,
        on_input=hotkeys,
        children=(
            Div(
                style=row | grow(1),
                children=tuple(
                    pane(p.number, command, p.handle, hotkeys, close).with_key(str(p.number)) for p in panes
                ),
            ),
            Text(content=key_hints(), style=text_wrap_none),
        ),
    )


# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import WaitFor
from counterweight.examples.scenes import Still

# A shell whose prompt and environment are the same for everyone, so its scenes come out the same on every machine.
PLAIN_SHELL = ("env", "-i", "PATH=/usr/bin:/bin", "PS1=$ ", "sh")


def shows(text: str, times: int = 1) -> WaitFor:
    """Wait until the screen shows `text` at least `times` times, which a shell prints in its own time."""
    return WaitFor(lambda frame: frame.text(ansi=False).count(text) >= times, timeout=timedelta(seconds=30))


def typed(command: str) -> list[KeyPressed]:
    return [*(KeyPressed(key=character) for character in command), KeyPressed(key=Key.Enter)]


# Each prompt is a `$`, as is the one in `$((6 * 7))`, so counting them waits for each shell to be ready.
STILLS = [
    Still(
        "multiplexer",
        root(PLAIN_SHELL),
        (80, 12),
        steps=[
            shows("$"),
            *typed("echo hello from the first pane"),
            shows("$", times=2),
            KeyPressed(key="alt+n"),
            shows("$", times=3),
            *typed("echo $((6 * 7))"),
            shows("$", times=5),
        ],
    ),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(root()))
