from asyncio import sleep

from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.hooks import use_effect, use_state
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
    seconds, set_seconds = use_state(0)

    async def tick() -> None:
        while True:
            await sleep(1)
            set_seconds(lambda previous: previous + 1)

    use_effect(tick, deps=())

    return Div(
        style=col,
        children=[
            Text(content=f"Up for {seconds} s"),
            Div(style=row, children=[metric_card(label, value) for label, value in METRICS]),
        ],
    )


# --8<-- [end:example]

SCREENSHOTS: list[ScreenshotSpec] = []
