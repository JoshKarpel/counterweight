from datetime import datetime
from itertools import cycle

from reprisal.app import app
from reprisal.components import Div, Text
from reprisal.input import Keys
from reprisal.render import Setter, use_ref, use_state
from reprisal.styles import Border, BorderKind, Padding, Span, Style, ml_auto, mr_auto, mx_auto
from reprisal.types import KeyQueueItem


def time() -> Div:
    now, set_now = use_state(datetime.now())
    buffer: list[str]
    set_buffer: Setter[list[str]]
    buffer, set_buffer = use_state([])
    border_cycle_ref = use_ref(cycle(BorderKind))
    border, set_border = use_state(next(border_cycle_ref.current))
    margin_cycle_ref = use_ref(cycle([mr_auto, mx_auto, ml_auto]))
    margin, set_margin = use_state(next(margin_cycle_ref.current))

    def on_key(keys: KeyQueueItem) -> None:
        if keys == (Keys.Space,):
            set_now(datetime.now())
        elif keys == (Keys.Enter,):
            set_border(next(border_cycle_ref.current))
        elif keys == (Keys.Tab,):
            set_margin(next(margin_cycle_ref.current))
        elif keys == (Keys.Backspace,):
            set_buffer(buffer[:-1])
        elif isinstance(keys, str):
            s = [*buffer, keys]
            set_buffer(s)

    now = f"{now}"
    text = "".join(buffer)
    m = f"{margin.margin}"

    return Div(
        children=(
            Text(
                text=now,
                style=Style(
                    span=Span(width=len(now), height=1),
                    border=Border(kind=border),
                    padding=Padding(top=1, bottom=1, left=1, right=1),
                )
                | margin,
            ),
            Text(
                text=text,
                style=Style(
                    span=Span(width=len(text), height=1),
                    border=Border(kind=border),
                    padding=Padding(top=1, bottom=1, left=1, right=1),
                )
                | margin,
            ),
            Text(
                text=m,
                style=Style(
                    span=Span(width=len(m), height=1),
                    border=Border(kind=border),
                    padding=Padding(top=1, bottom=1, left=1, right=1),
                )
                | margin,
            ),
        ),
        style=Style(
            border=Border(kind=BorderKind.Heavy),
        ),
        on_key=on_key,
    )


app(time)
