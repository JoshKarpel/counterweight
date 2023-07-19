import asyncio
from time import monotonic

from structlog import get_logger

from reprisal.app import app
from reprisal.components import Div, Paragraph, component
from reprisal.events import KeyPressed
from reprisal.hooks import use_effect, use_state
from reprisal.keys import Key
from reprisal.styles import Border, BorderKind, Style
from reprisal.styles.styles import Flex, Padding, Span
from reprisal.styles.utilities import (
    border_emerald_500,
    border_rose_500,
)

logger = get_logger()


@component
def stopwatch() -> Div:
    running, set_running = use_state(False)
    elapsed_time, set_elapsed_time = use_state(0)

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

    border_color = border_emerald_500 if running else border_rose_500

    content = f"{elapsed_time:.6f}"

    return Div(
        style=Style(
            display=Flex(
                direction="column",
                align_children="center",
            ),
        ),
        children=[
            Div(
                style=Style(
                    display=Flex(
                        direction="row",
                        align_children="center",
                    ),
                ),
                children=[
                    Paragraph(
                        content=content,
                        style=border_color
                        | Style(
                            span=Span(
                                # TODO: width should get set automatically for this element, but its not
                                # the problem is that the available width in this block is zero because when the column div
                                # lays out, it decides the width of the row div is zero because its stretch,
                                # and the row div doesn't know how its supposed to be yet
                                # does align self solve this problem? you set parent to stretch, then center the text box?
                                # width=len(content)
                            ),
                            border=Border(kind=BorderKind.Double),
                            padding=Padding(top=1, bottom=1, left=2, right=2),
                        ),
                    ),
                ],
            ),
            # Div(
            #     style=Style(
            #         display=Flex(
            #             direction="row",
            #             align_children="center",
            #         ),
            #     ),
            #     children=[
            #         Paragraph(
            #             content=dedent(
            #                 """\
            #                 <space> to start/stop
            #
            #                 <backspace> to reset
            #                 """
            #             ),
            #             style=border_slate_400
            #             | text_slate_200
            #             | Style(
            #                 span=Span(width=30),
            #                 border=Border(kind=BorderKind.LightRounded),
            #                 padding=Padding(top=1, bottom=1, left=2, right=2),
            #                 text=Text(justify="center"),
            #             ),
            #         ),
            #     ],
            # ),
        ],
        on_key=on_key,
    )


asyncio.run(app(stopwatch))
