from datetime import datetime
from itertools import cycle

from reprisal.app import app
from reprisal.elements.elements import Div, Text
from reprisal.input import Keys
from reprisal.render import use_ref, use_state
from reprisal.styles.styles import Border, BorderKind, Padding, Span, Style


def time():
    now, set_now = use_state(datetime.now())
    buffer, set_buffer = use_state([])
    box, set_box = use_state(BorderKind.Light)
    border_cycle_ref = use_ref(cycle(BorderKind))

    def on_key(keys: tuple[Keys, ...] | str):
        if keys == (Keys.Space,):
            set_now(datetime.now())
        elif keys == (Keys.Backspace,):
            set_buffer(buffer[:-1])
        elif keys == (Keys.Enter,):
            set_box(next(border_cycle_ref.current))
        elif isinstance(keys, str):
            s = [*buffer, keys]
            set_buffer(s)

    return Div(
        children=(
            Text(
                text=f"|   {now} {''.join(buffer)}   |",
                style=Style(
                    span=Span(width="auto", height=1),
                    border=Border(kind=box),
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
