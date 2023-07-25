import asyncio
from textwrap import dedent
from time import monotonic

from structlog import get_logger

from reprisal.app import app
from reprisal.components import Div, Text, component
from reprisal.events import KeyPressed
from reprisal.hooks import use_effect, use_state
from reprisal.keys import Key
from reprisal.styles.utilities import *

logger = get_logger()


@component
def stopwatch() -> Div:
    running, set_running = use_state(False)
    elapsed_time, set_elapsed_time = use_state(0.0)

    def on_key(event: KeyPressed) -> None:
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

    content = f"{elapsed_time:.6f}"

    return Div(
        style=col | align_children_center,
        children=[
            Div(
                style=row | weight_none,
                children=[
                    Text(
                        content="Stopwatch Example",
                        style=text_amber_600,
                    )
                ],
            ),
            Div(
                style=row | align_children_center,
                children=[
                    Text(
                        content=content,
                        style=(border_emerald_500 if running else border_rose_500) | border_double | pad_x_2 | pad_y_1,
                    ),
                ],
            ),
            Div(
                style=row | align_children_center,
                children=[
                    Text(
                        content=dedent(
                            """\
                            - <space> to start/stop
                            - <backspace> to reset
                            """
                        ),
                        style=border_slate_400 | text_slate_200 | border_lightrounded | pad_x_2 | pad_y_1,
                    ),
                ],
            ),
        ],
        on_key=on_key,
    )


asyncio.run(app(stopwatch))
