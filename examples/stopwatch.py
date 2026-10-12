import asyncio
import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from textwrap import dedent

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.hooks import use_clock, use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *

logger = logging.getLogger(__name__)


@component
def root() -> Div:
    num_stopwatches = 3

    selected_stopwatch, set_selected_stopwatch = use_state(0)

    def on_key(event: KeyPressed) -> None:
        match event.key:
            case Key.Tab:
                set_selected_stopwatch(lambda s: (s + 1) % num_stopwatches)
            case Key.BackTab:
                set_selected_stopwatch(lambda s: (s - 1) % num_stopwatches)

    return Div(
        style=col | justify_children_space_between | align_children_center,
        children=[
            Text(
                style=text_color("amber", 600),
                content="Stopwatch",
            ),
            Div(
                style=row | align_self_stretch | align_children_center | justify_children_space_evenly,
                on_key=on_key,
                children=[stopwatch(selected=selected_stopwatch == n) for n in range(num_stopwatches)],
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
                    - <tab>/<shift+tab> to select next/previous stopwatch
                    - <space> to start/stop selected stopwatch
                    - <backspace> to reset selected stopwatch
                    """
                ),
            ),
        ],
    )


@component
def stopwatch(selected: bool) -> Div:
    running, set_running = use_state(False)
    banked, set_banked = use_state(timedelta())

    def stop(elapsed: timedelta) -> None:
        set_running(False)
        set_banked(elapsed)

    def on_key(event: KeyPressed) -> None:
        if not selected:
            return

        match event.key:
            case Key.Space if not running:
                set_running(True)
            case Key.Backspace:
                set_running(False)
                set_banked(timedelta())

    return Div(
        on_key=on_key,
        children=[running_face(selected, banked, stop) if running else face(selected, running, banked)],
    )


@component
def running_face(selected: bool, banked: timedelta, stop: Callable[[timedelta], None]) -> Text:
    # Starting the stopwatch mounts this component, so the time since it mounted is the time since it started.
    elapsed = banked + use_clock(timedelta(milliseconds=10)).since_mount

    def on_key(event: KeyPressed) -> None:
        if selected and event.key == Key.Space:
            stop(elapsed)

    return replace(face(selected, True, elapsed), on_key=on_key)


def face(selected: bool, running: bool, elapsed: timedelta) -> Text:
    return Text(
        content=f"{elapsed.total_seconds():.2f}",
        style=(
            (border_color("emerald", 600) if selected else border_color("emerald", 300))
            if running
            else (border_color("rose", 500) if selected else border_color("rose", 400))
        )
        | (border | border_heavy if selected else border | border_double)
        | pad_x(2)
        | pad_y(1),
    )


if __name__ == "__main__":
    asyncio.run(app(root))
