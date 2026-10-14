"""
A tiny terminal multiplexer: shells side by side, each on its own pseudo-terminal.

Ctrl+B is the prefix, as in tmux. After it:
  %  split: open another shell to the right
  o  focus the next pane
  x  close the focused pane
  q  quit
Ctrl+B Ctrl+B sends a Ctrl+B to the focused program.
"""

import asyncio
import os
from collections.abc import Callable

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import ClearFocus, FocusNext, Quit
from counterweight.elements import Canvas, Div, Text
from counterweight.events import InputEvent, InputHandler, InputResponse, KeyPressed, Receiver
from counterweight.handlers import first
from counterweight.headless.terminal import use_terminal
from counterweight.hooks import FocusHandle, use_effect, use_rects, use_ref, use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *

SHELL = (os.environ.get("SHELL", "/bin/sh"),)


@component
def root() -> Div:
    panes, set_panes = use_state((0,))
    next_id, set_next_id = use_state(1)
    # A ref, not state: keys in one read are all handled before the next render, so each must see the last one's effect.
    armed = use_ref(False)
    is_armed, set_shown_armed = use_state(False)

    def set_armed(value: bool) -> None:
        armed.current = value
        set_shown_armed(value)

    titles, set_titles = use_state({})
    handles, _ = use_state(dict)

    def handle_of(pane_id: int) -> FocusHandle:
        return handles.setdefault(pane_id, FocusHandle())

    def prefix(pane_id: int) -> InputHandler:
        def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
            if not isinstance(event, KeyPressed) or not receiver.is_focused:
                return None
            if not armed.current:
                if event.key == Key.ControlB:
                    set_armed(True)
                    return ()
                return None
            set_armed(False)
            match event.key:
                case Key.ControlB:
                    return None  # the pane's own handler sends it on
                case "%":
                    set_panes(lambda p: (*p, next_id))
                    set_next_id(lambda n: n + 1)
                    # FocusOn can't name a pane that mounts in this update, so clear focus for the new pane's auto_focus.
                    return ClearFocus()
                case "o":
                    return FocusNext()
                case "x":
                    set_panes(lambda p: tuple(i for i in p if i != pane_id) or p)
                    return FocusNext()
                case "q":
                    return Quit()
                case _:
                    return ()

        return on_input

    def set_title(pane_id: int) -> Callable[[str], None]:
        return lambda title: set_titles(lambda t: t if t.get(pane_id) == title else {**t, pane_id: title})

    status = "  ".join(f"[{i}] {titles.get(i, '')}" for i in panes)
    return Div(
        style=col | full,
        children=(
            Div(
                style=row | grow(1),
                children=tuple(
                    pane(pane_id, prefix(pane_id), handle_of(pane_id), set_title(pane_id)).with_key(str(pane_id))
                    for pane_id in panes
                ),
            ),
            Text(
                content=("PREFIX " if is_armed else "") + status,
                style=text_color("slate", 900) | text_bg("amber", 400 if is_armed else 200) | text_wrap_none,
            ),
        ),
    )


@component
def pane(pane_id: int, prefix: InputHandler, handle: FocusHandle, on_title: Callable[[str], None]) -> Canvas:
    content = use_rects().content
    terminal = use_terminal(SHELL, content.width, content.height, auto_focus=True, handle=handle)
    title = terminal.screen.title if terminal.exit_status is None else f"exited {terminal.exit_status}"

    async def report_title() -> None:
        on_title(title)

    use_effect(report_title, deps=(title,))
    return Canvas(
        draw=terminal.view,
        style=fill(1)
        | border
        | border_lightrounded
        | (border_color("amber", 400) if terminal.focus.is_focused else border_color("slate", 600)),
        on_input=first(prefix, terminal.on_input),
    )


if __name__ == "__main__":
    asyncio.run(app(root()))
