from asyncio import sleep

from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.hooks import use_effect, use_state
from counterweight.styles.utilities import *
from docs.examples.performance_state_in_root import METRICS, metric_card
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:example]


@component
def uptime() -> Text:
    seconds, set_seconds = use_state(0)

    async def tick() -> None:
        while True:
            await sleep(1)
            set_seconds(lambda previous: previous + 1)

    use_effect(tick, deps=())

    return Text(content=f"Up for {seconds} s")


@component
def dashboard() -> Div:
    return Div(
        style=col,
        children=[
            uptime(),
            Div(style=row, children=[metric_card(label, value) for label, value in METRICS]),
        ],
    )


# --8<-- [end:example]

SCREENSHOTS = [ScreenshotSpec(dashboard(), "performance-dashboard", (80, 5))]
