from datetime import datetime

from reprisal.app import app
from reprisal.elements.elements import Div, Text
from reprisal.render import use_state
from reprisal.styles.styles import Border, BorderKind, Padding, Span, Style
from reprisal.vtparser import (
    Keys,
)


def time():
    print("rendering...")
    now, set_now = use_state(datetime.now())
    buffer, set_buffer = use_state([])

    def on_key(keys: tuple[Keys, ...] | str):
        print("on key", buffer, keys)
        if keys == (Keys.Space,):
            set_now(datetime.now())
        elif keys == (Keys.Backspace,):
            set_buffer(buffer[:-1])
        elif isinstance(keys, str):
            s = [*buffer, keys]
            set_buffer(s)

    return Div(
        children=(
            Text(
                text=f"s   {now} {''.join(buffer)}   e",
                style=Style(
                    span=Span(width="auto", height=1),
                    border=Border(kind=BorderKind.Light),
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
