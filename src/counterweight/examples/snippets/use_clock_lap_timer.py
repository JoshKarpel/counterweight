"""
Hooks: use_clock: a lap timer

A timer that starts again from zero on each lap.
"""

import asyncio
from datetime import timedelta

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import use_clock
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *

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
        children=(
            Text(content=f"Lap {laps}:", style=text_color("slate", 400)),
            # A new key each lap remounts lap_time, so its time since mounting starts again from zero.
            lap_time().with_key(str(laps)),
        ),
    )


# --8<-- [end:example]


ROOTS = (lap_timer,)

# --8<-- [start:scenes]

from counterweight.controls import AdvanceClock
from counterweight.controls import Marker
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still

STILLS = [
    Still(
        "use-clock-lap-timer",
        lap_timer(),
        (20, 1),
        steps=[
            AdvanceClock(by=timedelta(seconds=75)),
            KeyPressed(key=Key.Space),
            AdvanceClock(by=timedelta(seconds=42)),
        ],
    )
]

SECOND = AdvanceClock(by=timedelta(seconds=1))
SPACE = KeyPressed(key=Key.Space)

DEMOS = [
    Demo(
        "use-clock-lap-timer",
        lap_timer(),
        (20, 1),
        steps=[*[SECOND] * 4, SPACE, Marker("Lap 2"), *[SECOND] * 3, SPACE, Marker("Lap 3"), *[SECOND] * 3],
    )
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(lap_timer()))
