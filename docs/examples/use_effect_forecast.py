import asyncio
from dataclasses import dataclass
from datetime import timedelta

from counterweight.app import app
from counterweight.autopilot import WaitFor
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import use_effect
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.output import Frame
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:example]

FORECASTS = {
    "Lisbon": "Sunny, 24°C",
    "Oslo": "Light snow, -3°C",
    "Lima": "Overcast, 18°C",
}


async def fetch_forecast(city: str) -> str:
    await asyncio.sleep(0.5)  # Stands in for a request to a weather service.
    return FORECASTS[city]


@dataclass(frozen=True, slots=True)
class Fetched:
    city: str
    summary: str


@component
def forecast(city: str) -> Text:
    fetched, set_fetched = use_state(Fetched(city="", summary=""))

    async def fetch() -> None:
        set_fetched(Fetched(city=city, summary=await fetch_forecast(city)))

    use_effect(fetch, deps=(city,))

    if fetched.city != city:
        return Text(content=f"Fetching {city}...", style=text_color("slate", 400))

    return Text(content=fetched.summary, style=text_color("amber", 400))


@component
def weather() -> Div:
    cities = tuple(FORECASTS)
    selected, set_selected = use_state(0)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Right):
                set_selected(lambda i: (i + 1) % len(cities))
                return ()
            case KeyPressed(key=Key.Left):
                set_selected(lambda i: (i - 1) % len(cities))
                return ()
            case _:
                return None

    return Div(
        style=col | border | border_lightrounded | pad_x(1),
        on_input=on_input,
        children=(
            Div(
                style=row | gap(2),
                children=tuple(
                    Text(content=city, style=text_bg("sky", 800) if i == selected else text_color("slate", 400))
                    for i, city in enumerate(cities)
                ),
            ),
            forecast(cities[selected]),
        ),
    )


# --8<-- [end:example]


def shows(text: str) -> WaitFor:
    """Wait until the screen shows `text`, which the effect puts there after its fetch."""

    def condition(frame: Frame) -> bool:
        return text in frame.text(ansi=False)

    return WaitFor(condition, timeout=timedelta(seconds=10))


SCREENSHOTS = [
    ScreenshotSpec(weather(), "use-effect-forecast", (30, 4), events=[shows("Sunny")]),
    ScreenshotSpec(
        weather(),
        "use-effect-forecast-fetching",
        (30, 4),
        events=[shows("Sunny"), KeyPressed(key=Key.Right)],
    ),
]


if __name__ == "__main__":
    asyncio.run(app(weather()))
