import asyncio
import logging
from datetime import timedelta
from itertools import cycle

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.events import InputEvent, InputResponse, KeyPressed, Receiver
from counterweight.hooks import Setter, use_clock, use_focus, use_ref, use_state
from counterweight.keys import Key
from counterweight.styles import BorderKind, Style
from counterweight.styles.utilities import (
    border,
    border_color,
    border_lightrounded,
    col,
    pad,
    row,
    text_color,
)

logger = logging.getLogger(__name__)


@component
def toggle() -> Div:
    border_cycle_ref = use_ref(cycle(BorderKind))

    def advance_border() -> BorderKind:
        return next(border_cycle_ref.current)

    border_kind, set_border_kind = use_state(advance_border)

    border_color_ref = use_ref(cycle([border_color("lime", 700), border_color("amber", 700), border_color("sky", 700)]))

    def advance_border_color() -> Style:
        return next(border_color_ref.current)

    border_color_style, set_border_color_style = use_state(advance_border_color)

    toggled, set_toggled = use_state(False)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Tab):
                set_toggled(not toggled)
                return ()
            case KeyPressed(key=Key.F1):
                set_border_kind(advance_border())
                return ()
            case KeyPressed(key=Key.F2):
                set_border_color_style(advance_border_color())
                return ()
            case _:
                return None

    return Div(
        children=(
            Div(
                children=(
                    Text(
                        content="End-to-End Demo",
                        style=border_color_style | pad(1) | border | Style(border_kind=border_kind),
                    ),
                    time() if toggled else textpad(),
                ),
                style=row | border | border_lightrounded,
            ),
        ),
        style=col,
        on_input=on_input,
    )


@component
def time() -> Text:
    tick = use_clock(timedelta(seconds=1))

    return Text(
        content=f"{tick.now:%Y-%m-%d %H:%M:%S}",
        style=text_color("rose", 500) | border_color("teal", 600) | pad(1) | border | border_lightrounded,
    )


@component
def textpad() -> Text:
    # Takes focus each time it mounts, which is each time the root swaps it back in.
    use_focus(auto_focus=True)
    buffer: list[str]
    set_buffer: Setter[list[str]]
    buffer, set_buffer = use_state([])

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Backspace):
                set_buffer(buffer[:-1])
                return ()
            case KeyPressed(key=key) if key.isprintable() and len(key) == 1:
                set_buffer([*buffer, key])
                return ()
            case _:
                return None

    content = "".join(buffer) or "..."

    return Text(
        content=content,
        style=text_color("teal", 600) | border_color("rose", 500) | pad(1) | border | border_lightrounded,
        on_input=on_input,
    )


if __name__ == "__main__":
    asyncio.run(app(toggle()))
