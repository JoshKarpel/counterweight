from datetime import datetime
from itertools import cycle

from reprisal.app import app
from reprisal.components import Div, Text
from reprisal.input import Keys
from reprisal.render import Setter, use_ref, use_state
from reprisal.styles import Border, BorderKind, Padding, Span, Style
from reprisal.types import KeyQueueItem


def time() -> Div:
    now, set_now = use_state(datetime.now())
    buffer: list[str]
    set_buffer: Setter[list[str]]
    buffer, set_buffer = use_state([])
    border_cycle_ref = use_ref(cycle(BorderKind))
    border, set_border = use_state(next(border_cycle_ref.current))

    def on_key(keys: KeyQueueItem) -> None:
        if keys == (Keys.Space,):
            set_now(datetime.now())
        elif keys == (Keys.Backspace,):
            set_buffer(buffer[:-1])
        elif keys == (Keys.Enter,):
            set_border(next(border_cycle_ref.current))
        elif isinstance(keys, str):
            s = [*buffer, keys]
            set_buffer(s)

    return Div(
        children=(
            Text(
                text=f"|   {now} {''.join(buffer)}   |",
                style=Style(
                    span=Span(width="auto", height=1),
                    border=Border(kind=border),
                    padding=Padding(top=0, bottom=0, left=0, right=0),
                ),
            ),
        ),
        style=Style(
            border=Border(kind=BorderKind.Heavy),
        ),
        on_key=on_key,
    )


app(time)
