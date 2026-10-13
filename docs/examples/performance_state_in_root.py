import asyncio

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Chunk, Div, Text
from counterweight.headless import TextInput, use_text_input
from counterweight.hooks import use_state
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

METRICS = (("CPU", "23.4%"), ("Memory", "1.21 GB"), ("Disk", "44.8 MB/s"), ("Network", "8.33 MB/s"))

CURSOR = (text_color("slate", 900) | text_bg("slate", 100)).text_style

# --8<-- [start:example]


def note_line(field: TextInput) -> list[Chunk]:
    return [
        Chunk(content=f"Note: {field.before_cursor}"),
        Chunk(content=field.at_cursor, style=CURSOR),
        Chunk(content=field.after_cursor),
    ]


@component
def metric_card(label: str, value: str) -> Div:
    return Div(
        style=fill(1) | col | border | border_lightrounded | pad_x(1),
        children=[
            Text(content=label, style=text_color("slate", 400)),
            Text(content=value),
        ],
    )


@component
def dashboard() -> Div:
    note, set_note = use_state("")
    field = use_text_input(note, set_note, auto_focus=True)

    return Div(
        style=col,
        on_input=field.on_input,
        children=[
            Text(content=note_line(field)),
            Div(style=row, children=[metric_card(label, value) for label, value in METRICS]),
        ],
    )


# --8<-- [end:example]

SCREENSHOTS: list[ScreenshotSpec] = []


if __name__ == "__main__":
    asyncio.run(app(dashboard()))
