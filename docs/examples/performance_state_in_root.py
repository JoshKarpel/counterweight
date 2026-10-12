import asyncio

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.hooks import use_state
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

METRICS = (("CPU", "23.4%"), ("Memory", "1.21 GB"), ("Disk", "44.8 MB/s"), ("Network", "8.33 MB/s"))

# --8<-- [start:example]


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

    def on_key(event: KeyPressed) -> None:
        if len(event.key) == 1:
            set_note(note + event.key)

    return Div(
        style=col,
        on_key=on_key,
        children=[
            Text(content=f"Note: {note}"),
            Div(style=row, children=[metric_card(label, value) for label, value in METRICS]),
        ],
    )


# --8<-- [end:example]

SCREENSHOTS: list[ScreenshotSpec] = []


if __name__ == "__main__":
    asyncio.run(app(dashboard()))
