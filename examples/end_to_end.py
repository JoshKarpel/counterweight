import asyncio
from datetime import datetime
from itertools import cycle

import waxy
from structlog import get_logger

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.hooks import Setter, use_effect, use_ref, use_state
from counterweight.keys import Key
from counterweight.styles import BorderKind, Style
from counterweight.styles.utilities import (
    border_amber_700,
    border_lime_700,
    border_rose_500,
    border_sky_700,
    border_teal_600,
    col,
    text_rose_500,
    text_teal_600,
)

logger = get_logger()

_PAD_BORDER_1 = waxy.Style(
    padding_top=waxy.Length(1),
    padding_bottom=waxy.Length(1),
    padding_left=waxy.Length(1),
    padding_right=waxy.Length(1),
    border_top=waxy.Length(1),
    border_bottom=waxy.Length(1),
    border_left=waxy.Length(1),
    border_right=waxy.Length(1),
)


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
            Div(
                children=[
                    Text(
                        content="End-to-End Demo",
                        style=border_color
                        | Style(
                            layout=_PAD_BORDER_1,
                            border_kind=border,
                        ),
                    ),
                    time() if toggled else textpad(),
                ],
                style=Style(
                    layout=waxy.Style(
                        flex_direction=waxy.FlexDirection.Row,
                        border_top=waxy.Length(1),
                        border_bottom=waxy.Length(1),
                        border_left=waxy.Length(1),
                        border_right=waxy.Length(1),
                    ),
                    border_kind=BorderKind.LightRounded,
                ),
            ),
        ],
        style=col,
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
            layout=_PAD_BORDER_1,
            border_kind=BorderKind.LightRounded,
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
            layout=_PAD_BORDER_1,
            border_kind=BorderKind.LightRounded,
        ),
        on_key=on_key,
    )


if __name__ == "__main__":
    asyncio.run(app(toggle))
