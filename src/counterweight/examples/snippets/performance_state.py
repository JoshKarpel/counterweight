"""
Performance: Moving state down

A dashboard with a note, which re-runs everything while its root holds the note and only the note once the state moves down.
"""

import asyncio
import sys

from counterweight import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.headless import TextInput
from counterweight.headless import use_text_input
from counterweight.hooks import use_state
from counterweight.styles.utilities import *

METRICS = (("CPU", "23.4%"), ("Memory", "1.21 GB"), ("Disk", "44.8 MB/s"), ("Network", "8.33 MB/s"))

CURSOR = text_color("slate", 900) | text_bg("slate", 100)

# --8<-- [start:in-root]


def note_line(field: TextInput) -> tuple[Text, Div]:
    return (
        Text(content="Note: "),
        Div(
            style=row | overflow_x_scroll | stick_to_end_x,
            on_input=field.on_press,
            children=(
                Text(content=field.before_cursor, style=text_wrap_none),
                Text(content=field.at_cursor, style=text_wrap_none | CURSOR, handle=field.cursor_cell),
                Text(content=field.after_cursor, style=text_wrap_none),
            ),
        ),
    )


@component
def metric_card(label: str, value: str) -> Div:
    return Div(
        style=fill(1) | col | border | border_lightrounded | pad_x(1),
        children=(
            Text(content=label, style=text_color("slate", 400)),
            Text(content=value),
        ),
    )


@component
def busy_dashboard() -> Div:
    note, set_note = use_state("")
    field = use_text_input(note, set_note, auto_focus=True)

    return Div(
        style=col,
        on_input=field.on_input,
        children=(
            Div(style=row, children=note_line(field)),
            Div(style=row, children=tuple(metric_card(label, value) for label, value in METRICS)),
        ),
    )


# --8<-- [end:in-root]

# --8<-- [start:moved-down]


@component
def note() -> Div:
    text, set_text = use_state("")
    field = use_text_input(text, set_text, auto_focus=True)
    return Div(style=row, on_input=field.on_input, children=note_line(field))


@component
def dashboard() -> Div:
    return Div(
        style=col,
        children=(
            note(),
            Div(style=row, children=tuple(metric_card(label, value) for label, value in METRICS)),
        ),
    )


# --8<-- [end:moved-down]


ROOTS = (busy_dashboard, dashboard)

# --8<-- [start:scenes]

from counterweight.events import KeyPressed
from counterweight.examples.scenes import Still

NOTE = [KeyPressed(key=key) for key in "disk is busy"]

STILLS = [
    Still("performance-busy-dashboard", busy_dashboard(), (80, 5), steps=NOTE),
    Still("performance-dashboard", dashboard(), (80, 5), steps=NOTE),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
