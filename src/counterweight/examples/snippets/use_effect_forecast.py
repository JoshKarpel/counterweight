"""
Hooks: use_effect

A forecast fetched for the city selected, which a change of city cancels.
"""

import asyncio
from dataclasses import dataclass

from counterweight import app
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
from counterweight.styles.utilities import *

# --8<-- [start:example]

FOREDEMOS = {
    "Lisbon": "Sunny, 24°C",
    "Oslo": "Light snow, -3°C",
    "Lima": "Overcast, 18°C",
}


async def fetch_forecast(city: str) -> str:
    await asyncio.sleep(0.5)  # Stands in for a request to a weather service.
    return FOREDEMOS[city]


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
    cities = tuple(FOREDEMOS)
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


ROOTS = (weather,)

# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import WaitFor
from counterweight.examples.scenes import Still
from counterweight.paint import Frame


def shows(text: str) -> WaitFor:
    """Wait until the screen shows `text`, which the effect puts there after its fetch."""

    def condition(frame: Frame) -> bool:
        return text in frame.text(ansi=False)

    return WaitFor(condition, timeout=timedelta(seconds=10))


STILLS = [
    Still("use-effect-forecast", weather(), (30, 4), steps=[shows("Sunny")]),
    Still("use-effect-forecast-fetching", weather(), (30, 4), steps=[shows("Sunny"), KeyPressed(key=Key.Right)]),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(weather()))
