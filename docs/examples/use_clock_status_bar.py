import asyncio
from datetime import timedelta

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import AdvanceClock
from counterweight.elements import Div, Text
from counterweight.hooks import use_clock
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:example]


@component
def wall_clock() -> Text:
    tick = use_clock(timedelta(minutes=1))
    return Text(content=f"{tick.now:%H:%M}", style=text_color("amber", 400))


@component
def uptime() -> Text:
    tick = use_clock(timedelta(seconds=1))
    seconds = tick.since_start // timedelta(seconds=1)
    return Text(content=f"Up {seconds // 3600}:{seconds // 60 % 60:02}:{seconds % 60:02}")


@component
def status_bar() -> Div:
    return Div(
        style=row | justify_children_space_between | border | border_lightrounded | pad_x(1),
        children=[uptime(), wall_clock()],
    )


# --8<-- [end:example]

SCREENSHOTS = [
    ScreenshotSpec(
        status_bar(),
        "use-clock-status-bar",
        (40, 3),
        events=[AdvanceClock(by=timedelta(hours=1, minutes=2, seconds=5))],
    )
]


if __name__ == "__main__":
    asyncio.run(app(status_bar()))
