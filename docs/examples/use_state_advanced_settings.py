import asyncio
from datetime import timedelta

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Marker
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import toggle
from counterweight.hooks import use_focus
from counterweight.hooks import use_state
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import CastSpec
from docs.examples.screenshot_spec import ScreenshotSpec
from docs.examples.screenshot_spec import paced

# --8<-- [start:example]


@component
def advanced_settings() -> Text:
    use_focus(auto_focus=True)
    level, set_level = use_state(3)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key="+"):
                set_level(lambda level: level + 1)
                return ()
            case _:
                return None

    return Text(content=f"Level: {level} (+ raises it)", style=text_color("amber", 400), on_input=on_input)


@component
def settings() -> Div:
    is_advanced, set_advanced = use_state(False)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key="a"):
                set_advanced(toggle)
                return ()
            case _:
                return None

    return Div(
        style=col | border | border_lightrounded | pad_x(1),
        on_input=on_input,
        children=(
            Text(content=f"[{'x' if is_advanced else ' '}] Advanced (a toggles it)"),
            *((advanced_settings(),) if is_advanced else ()),
        ),
    )


# --8<-- [end:example]

A = KeyPressed(key="a")
PLUS = KeyPressed(key="+")

SCREENSHOTS = [
    ScreenshotSpec(settings(), "use-state-advanced-settings", (32, 4), events=[A, PLUS, PLUS]),
]

CASTS = [
    CastSpec(
        settings(),
        "use-state-advanced-settings",
        (32, 4),
        steps=paced(
            [A, PLUS, PLUS, A, Marker("Hidden"), A, Marker("Shown again")],
            every=timedelta(milliseconds=800),
        ),
    ),
]


if __name__ == "__main__":
    asyncio.run(app(settings()))
