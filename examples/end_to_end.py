import asyncio
from datetime import datetime
from itertools import cycle

from structlog import get_logger

from reprisal.app import app
from reprisal.components import Div, Text
from reprisal.components.components import Setter, component, use_effect, use_ref, use_state
from reprisal.events import KeyPressed
from reprisal.keys import Key
from reprisal.styles import Border, BorderKind, Padding, Span, Style, ml_auto, mr_auto, mx_auto

logger = get_logger()


@component
def toggle() -> Div:
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

    toggled, set_toggled = use_state(False)

    def on_key(event: KeyPressed) -> None:
        match event.key:
            case Key.Tab:
                logger.debug("toggle")
                set_toggled(not toggled)
            case Key.Space:
                logger.debug("border")
                set_border(advance_border())
            case Key.Enter:
                logger.debug("margin")
                set_margin_style(advance_margin())

    return Div(
        children=[time(margin_style) if toggled else textpad(margin_style)],
        style=Style(
            border=Border(kind=border),
        ),
        on_key=on_key,
    )


@component
def time(margin_style: Style) -> Div:
    now, set_now = use_state(datetime.now())

    async def tick() -> None:
        while True:
            await asyncio.sleep(1)
            set_now(datetime.now())

    use_effect(tick, deps=())

    n = f"{now}"

    return Div(
        children=[
            Text(
                text=n,
                style=Style(
                    span=Span(width=len(n), height=1),
                    border=Border(kind=BorderKind.LightRounded),
                    padding=Padding(top=1, bottom=1, left=1, right=1),
                )
                | margin_style,
            )
        ]
    )


@component
def textpad(margin_style: Style) -> Div:
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

    text = "".join(buffer)

    return Div(
        children=[
            Text(
                text=text,
                style=Style(
                    span=Span(width=len(text), height=1),
                    border=Border(kind=BorderKind.MediumShade),
                    padding=Padding(top=1, bottom=1, left=1, right=1),
                )
                | margin_style,
            )
        ],
        on_key=on_key,
    )


asyncio.run(app(toggle))
