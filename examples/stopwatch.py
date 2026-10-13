import asyncio
import logging
from textwrap import dedent
from time import monotonic

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.events import InputEvent, InputResponse, KeyPressed, Receiver
from counterweight.handlers import tab_focus
from counterweight.hooks import use_effect, use_focus, use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *

logger = logging.getLogger(__name__)


@component
def root() -> Div:
    num_stopwatches = 3

    return Div(
        style=col | justify_children_space_between | align_children_center,
        on_input=tab_focus,
        children=[
            Text(
                style=text_color("amber", 600),
                content="Stopwatch",
            ),
            Div(
                style=row | align_self_stretch | align_children_center | justify_children_space_evenly,
                children=[stopwatch() for _ in range(num_stopwatches)],
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
        ],
    )


@component
def stopwatch() -> Text:
    focused = use_focus(auto_focus=True).is_focused
    running, set_running = use_state(False)
    elapsed_time, set_elapsed_time = use_state(0.0)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Space):
                set_running(not running)
                return ()
            case KeyPressed(key=Key.Backspace):
                set_running(False)
                set_elapsed_time(0)
                return ()
            case _:
                return None

    async def tick() -> None:
        if running:
            previous = monotonic()
            while True:
                now = monotonic()
                set_elapsed_time(lambda e: e + (now - previous))
                previous = now

                await asyncio.sleep(0.01)

    use_effect(tick, deps=(running,))

    return Text(
        content=f"{elapsed_time:.6f}",
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
    asyncio.run(app(root))
