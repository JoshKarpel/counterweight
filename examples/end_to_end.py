import asyncio
from datetime import datetime
from itertools import cycle

from structlog import get_logger

from reprisal.app import app
from reprisal.components import Div, Text, component
from reprisal.events import KeyPressed
from reprisal.hooks import Setter, use_effect, use_ref, use_state
from reprisal.keys import Key
from reprisal.styles import Border, BorderKind, Style
from reprisal.styles.styles import Flex, Padding
from reprisal.styles.utilities import (
    border_amber_700,
    border_lime_700,
    border_rose_500,
    border_sky_700,
    border_teal_600,
    text_rose_500,
    text_teal_600,
)

logger = get_logger()


@component
def toggle() -> Div:
    border_cycle_ref = use_ref(cycle(BorderKind))

    def advance_border() -> BorderKind:
        return next(border_cycle_ref.current)

    border, set_border = use_state(advance_border)

    border_color_ref = use_ref(cycle([border_lime_700, border_amber_700, border_sky_700]))

    def advance_border_color() -> Style:
        return next(border_color_ref.current)

    border_color, set_border_color = use_state(advance_border_color)

    toggled, set_toggled = use_state(False)

    def on_key(event: KeyPressed) -> None:
        match event.key:
            case Key.Tab:
                set_toggled(not toggled)
            case Key.F1:
                set_border(advance_border())
            case Key.F2:
                set_border_color(advance_border_color())

    return Div(
        children=[
            # TODO: why does putting this here break the layout? it's above the outer div...
            # Paragraph(
            #     content="End-to-End Demo",
            #     style=Style(
            #         span=Span(width="auto"),
            #         border=Border(kind=BorderKind.LightRounded),
            #     ),
            # ),
            Div(
                children=[
                    Text(
                        content="End-to-End Demo",
                        style=border_color
                        | Style(
                            border=Border(kind=border),
                            padding=Padding(top=1, bottom=1, left=1, right=1),
                        ),
                    ),
                    time() if toggled else textpad(),
                ],
                style=Style(
                    display=Flex(direction="row"),
                    border=Border(kind=BorderKind.LightRounded),
                ),
            ),
        ],
        style=Style(
            display=Flex(
                direction="column",
                # TODO: without align_children="stretch", the children don't grow in width, even though they have text in them...
                # maybe I'm applying auto width too late?
                align_children="stretch",
            ),
        ),
        on_key=on_key,
    )


@component
def time() -> Text:
    now, set_now = use_state(datetime.now())

    async def tick() -> None:
        while True:
            await asyncio.sleep(0.01)
            set_now(datetime.now())

    use_effect(tick, deps=())

    return Text(
        content=f"{now:%Y-%m-%d %H:%M:%S}",
        style=text_rose_500
        | border_teal_600
        | Style(
            border=Border(kind=BorderKind.LightRounded),
            padding=Padding(top=1, bottom=1, left=1, right=1),
        ),
    )


@component
def textpad() -> Text:
    buffer: list[str]
    set_buffer: Setter[list[str]]
    buffer, set_buffer = use_state([])

    def on_key(event: KeyPressed) -> None:
        match event.key:
            case Key.Backspace:
                set_buffer(buffer[:-1])
            case _ if event.key.isprintable() and len(event.key) == 1:  # TODO: gross
                s = [*buffer, event.key]
                set_buffer(s)

    content = "".join(buffer) or "..."

    return Text(
        content=content,
        style=text_teal_600
        | border_rose_500
        | Style(
            border=Border(kind=BorderKind.LightRounded),
            padding=Padding(top=1, bottom=1, left=1, right=1),
        ),
        on_key=on_key,
    )


asyncio.run(app(toggle))
