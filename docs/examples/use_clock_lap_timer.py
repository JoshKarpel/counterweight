import asyncio
from datetime import timedelta

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import AdvanceClock
from counterweight.elements import Div, Text
from counterweight.events import InputEvent, InputResponse, KeyPressed, Receiver
from counterweight.hooks import use_clock, use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:example]


@component
def lap_time() -> Text:
    elapsed = use_clock(timedelta(seconds=1)).since_mount
    return Text(content=f"{elapsed // timedelta(seconds=1)} s")


@component
def lap_timer() -> Div:
    laps, set_laps = use_state(1)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Space):
                set_laps(lambda laps: laps + 1)
                return ()
            case _:
                return None

    return Div(
        style=row | gap(1),
        on_input=on_input,
        children=[
            Text(content=f"Lap {laps}:", style=text_color("slate", 400)),
            # A new key each lap remounts lap_time, so its time since mounting starts again from zero.
            lap_time().with_key(str(laps)),
        ],
    )


# --8<-- [end:example]

SCREENSHOTS = [
    ScreenshotSpec(
        lap_timer(),
        "use-clock-lap-timer",
        (20, 1),
        events=[
            AdvanceClock(by=timedelta(seconds=75)),
            KeyPressed(key=Key.Space),
            AdvanceClock(by=timedelta(seconds=42)),
        ],
    )
]


if __name__ == "__main__":
    asyncio.run(app(lap_timer()))
