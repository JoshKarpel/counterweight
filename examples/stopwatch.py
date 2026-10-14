import asyncio
import logging
from collections.abc import Callable
from datetime import timedelta
from textwrap import dedent

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputHandler
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.handlers import tab_focus
from counterweight.hooks import use_clock
from counterweight.hooks import use_focus
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *

logger = logging.getLogger(__name__)


@component
def root() -> Div:
    num_stopwatches = 3

    return Div(
        style=col | justify_children_space_between | align_children_center,
        on_input=tab_focus,
        children=(
            Text(
                style=text_color("amber", 600),
                content="Stopwatch",
            ),
            Div(
                style=row | align_self_stretch | align_children_center | justify_children_space_evenly,
                children=tuple(stopwatch() for _ in range(num_stopwatches)),
            ),
            Text(
                style=border_color("slate", 400)
                | text_color("slate", 200)
                | border
                | border_lightrounded
                | pad_x(2)
                | pad_y(1),
                content=dedent(
                    """\
                    - <tab>/<shift+tab> to focus next/previous stopwatch
                    - <space> to start/stop focused stopwatch
                    - <backspace> to reset focused stopwatch
                    """
                ),
            ),
        ),
    )


@component
def stopwatch() -> Div:
    running, set_running = use_state(False)
    banked, set_banked = use_state(timedelta())

    def start() -> None:
        set_running(True)

    def stop(elapsed: timedelta) -> None:
        set_running(False)
        set_banked(elapsed)

    def reset() -> None:
        set_running(False)
        set_banked(timedelta())

    # Starting or stopping swaps one face for the other, and the face that mounts takes focus from the one that left.
    return Div(children=(running_face(banked, stop, reset) if running else stopped_face(banked, start, reset),))


@component
def stopped_face(banked: timedelta, start: Callable[[], None], reset: Callable[[], None]) -> Text:
    focused = use_focus(auto_focus=True).is_focused

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Space):
                start()
                return ()
            case KeyPressed(key=Key.Backspace):
                reset()
                return ()
            case _:
                return None

    return face(focused, False, banked, on_input)


@component
def running_face(banked: timedelta, stop: Callable[[timedelta], None], reset: Callable[[], None]) -> Text:
    focused = use_focus(auto_focus=True).is_focused
    # Starting the stopwatch mounts this component, so the time since it mounted is the time since it started.
    elapsed = banked + use_clock(timedelta(milliseconds=10)).since_mount

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Space):
                stop(elapsed)
                return ()
            case KeyPressed(key=Key.Backspace):
                reset()
                return ()
            case _:
                return None

    return face(focused, True, elapsed, on_input)


def face(focused: bool, running: bool, elapsed: timedelta, on_input: InputHandler) -> Text:
    return Text(
        content=f"{elapsed.total_seconds():.2f}",
        style=(
            (border_color("emerald", 600) if focused else border_color("emerald", 300))
            if running
            else (border_color("rose", 500) if focused else border_color("rose", 400))
        )
        | (border | border_heavy if focused else border | border_double)
        | pad_x(2)
        | pad_y(1),
        on_input=on_input,
    )


if __name__ == "__main__":
    asyncio.run(app(root()))
