import asyncio
from datetime import datetime
from itertools import cycle

from reprisal.app import app
from reprisal.components import Div, Text
from reprisal.components.components import Setter, component, use_effect, use_ref, use_state
from reprisal.events import KeyPressed
from reprisal.keys import Key
from reprisal.styles import Border, BorderKind, Padding, Span, Style, ml_auto, mr_auto, mx_auto


@component
def time() -> Div:
    now, set_now = use_state(datetime.now())

    buffer: list[str]
    set_buffer: Setter[list[str]]
    buffer, set_buffer = use_state([])

    border: BorderKind
    set_border: Setter[BorderKind]
    border_cycle_ref = use_ref(cycle(BorderKind))

    def advance_border() -> BorderKind:
        return next(border_cycle_ref.current)

    border, set_border = use_state(advance_border)  # type: ignore[arg-type]

    margin_style: Style
    set_margin_style: Setter[Style]
    margin_cycle_ref = use_ref(cycle([mr_auto, mx_auto, ml_auto]))

    def advance_margin() -> Style:
        return next(margin_cycle_ref.current)

    margin_style, set_margin_style = use_state(advance_margin)  # type: ignore[arg-type]

    def on_key(event: KeyPressed) -> None:
        if event.key == Key.Space:
            set_now(datetime.now())
        elif event.key == Key.Enter:
            set_border(advance_border())
        elif event.key == Key.Tab:
            set_margin_style(advance_margin())
        elif event.key == Key.Backspace:
            set_buffer(buffer[:-1])
        elif event.key.isprintable() and len(event.key) == 1:  # TODO: gross
            s = [*buffer, event.key]
            set_buffer(s)

    async def tick() -> None:
        while True:
            await asyncio.sleep(1 / 60)
            set_now(datetime.now())

    use_effect(tick, deps=())

    n = f"{now}"
    text = "".join(buffer)
    m = f"{margin_style.margin}"

    return Div(
        children=(
            Text(
                text=n,
                style=Style(
                    span=Span(width=len(n), height=1),
                    border=Border(kind=border),
                    padding=Padding(top=1, bottom=1, left=1, right=1),
                )
                | margin_style,
            ),
            Text(
                text=text,
                style=Style(
                    span=Span(width=len(text), height=1),
                    border=Border(kind=border),
                    padding=Padding(top=1, bottom=1, left=1, right=1),
                )
                | margin_style,
            ),
            Text(
                text=m,
                style=Style(
                    span=Span(width=len(m), height=1),
                    border=Border(kind=border),
                    padding=Padding(top=1, bottom=1, left=1, right=1),
                )
                | margin_style,
            ),
        ),
        style=Style(
            border=Border(kind=BorderKind.Heavy),
        ),
        on_key=on_key,
    )


asyncio.run(app(time))
