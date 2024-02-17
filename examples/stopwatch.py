import asyncio
from textwrap import dedent
from time import monotonic

from structlog import get_logger

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.hooks import use_effect, use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *

logger = get_logger()


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
                style=text_amber_600,
                content="Stopwatch",
            ),
            Div(
                style=row | align_self_stretch | align_children_center | justify_children_space_evenly,
                on_key=on_key,
                children=[stopwatch(selected=selected_stopwatch == n) for n in range(num_stopwatches)],
            ),
            Text(
                style=border_slate_400 | text_slate_200 | border_lightrounded | pad_x_2 | pad_y_1,
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

    def on_key(event: KeyPressed) -> None:
        if not selected:
            return

        match event.key:
            case Key.Space:
                set_running(not running)
            case Key.Backspace:
                set_running(False)
                set_elapsed_time(0)

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
            (border_emerald_600 if selected else border_emerald_300)
            if running
            else (border_rose_500 if selected else border_rose_400)
        )
        | (border_heavy if selected else border_double)
        | pad_x_2
        | pad_y_1,
        on_key=on_key,
    )


if __name__ == "__main__":
    asyncio.run(app(root))
