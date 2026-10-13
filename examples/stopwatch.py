import asyncio
import logging
from textwrap import dedent
from time import monotonic

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.events import InputEvent, KeyPressed, Receiver
from counterweight.hooks import use_effect, use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *

logger = logging.getLogger(__name__)


@component
def root() -> Div:
    num_stopwatches = 3

    selected_stopwatch, set_selected_stopwatch = use_state(0)

    def on_input(event: InputEvent, _: Receiver) -> None:
        match event:
            case KeyPressed(key=Key.Tab):
                set_selected_stopwatch(lambda s: (s + 1) % num_stopwatches)
            case KeyPressed(key=Key.BackTab):
                set_selected_stopwatch(lambda s: (s - 1) % num_stopwatches)
            case _:
                pass

    return Div(
        style=col | justify_children_space_between | align_children_center,
        children=[
            Text(
                style=text_color("amber", 600),
                content="Stopwatch",
            ),
            Div(
                style=row | align_self_stretch | align_children_center | justify_children_space_evenly,
                on_input=on_input,
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
def stopwatch(selected: bool) -> Text:
    running, set_running = use_state(False)
    elapsed_time, set_elapsed_time = use_state(0.0)

    def on_input(event: InputEvent, _: Receiver) -> None:
        if not selected:
            return

        match event:
            case KeyPressed(key=Key.Space):
                set_running(not running)
            case KeyPressed(key=Key.Backspace):
                set_running(False)
                set_elapsed_time(0)
            case _:
                pass

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
            (border_color("emerald", 600) if selected else border_color("emerald", 300))
            if running
            else (border_color("rose", 500) if selected else border_color("rose", 400))
        )
        | (border | border_heavy if selected else border | border_double)
        | pad_x(2)
        | pad_y(1),
        on_input=on_input,
    )


if __name__ == "__main__":
    asyncio.run(app(root))
