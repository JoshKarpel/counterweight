import asyncio
import sys
from datetime import timedelta

from counterweight.animation import between
from counterweight.animation import ease_in_out
from counterweight.animation import ease_out
from counterweight.app import app
from counterweight.autopilot import advance
from counterweight.components import component
from counterweight.controls import AdvanceClock
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import use_loop
from counterweight.hooks import use_progress
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import CastSpec
from docs.examples.screenshot_spec import ScreenshotSpec

WIDTH = 24


def bar(fraction: float) -> str:
    filled = round(fraction * WIDTH)
    return "█" * filled + "░" * (WIDTH - filled)


# --8<-- [start:progress]


@component
def filling_bar(plays: int) -> Text:
    # Starts again from 0 each time `plays` changes, and stops reading the clock once it's full.
    progress = use_progress(timedelta(seconds=2), deps=(plays,))
    return Text(content=bar(ease_in_out(progress)), style=text_color("teal", 400))


@component
def replayable() -> Div:
    plays, set_plays = use_state(0)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Space):
                set_plays(lambda plays: plays + 1)
                return ()
            case _:
                return None

    return Div(
        style=col | gap(1),
        on_input=on_input,
        children=(filling_bar(plays), Text(content="Space plays it again", style=text_color("slate", 400))),
    )


# --8<-- [end:progress]

# --8<-- [start:phases]


@component
def staggered() -> Div:
    progress = use_progress(timedelta(seconds=3))
    return Div(
        style=col,
        children=tuple(
            # Each bar fills in its own half of the animation, a quarter after the one above it.
            Text(content=bar(ease_out(between(progress, start, start + 0.5))), style=text_color("amber", 300))
            for start in (0, 0.25, 0.5)
        ),
    )


# --8<-- [end:phases]

# --8<-- [start:loop]


@component
def bouncing() -> Div:
    is_playing, set_playing = use_state(True)
    there_and_back = 1 - abs(2 * use_loop(timedelta(seconds=2), is_playing=is_playing) - 1)
    position = round(ease_in_out(there_and_back) * (WIDTH - 1))

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Space):
                set_playing(lambda is_playing: not is_playing)
                return ()
            case _:
                return None

    return Div(
        style=col | gap(1),
        on_input=on_input,
        children=(
            Text(content="·" * position + "●" + "·" * (WIDTH - 1 - position), style=text_color("rose", 400)),
            Text(content="Space pauses and plays", style=text_color("slate", 400)),
        ),
    )


# --8<-- [end:loop]

SPACE = KeyPressed(key=Key.Space)

SCREENSHOTS = [
    ScreenshotSpec(replayable(), "animation-progress", (WIDTH, 3), events=[AdvanceClock(by=timedelta(seconds=1))]),
    ScreenshotSpec(staggered(), "animation-phases", (WIDTH, 3), events=[AdvanceClock(by=timedelta(seconds=2))]),
    ScreenshotSpec(bouncing(), "animation-loop", (WIDTH, 3), events=[AdvanceClock(by=timedelta(seconds=0.6))]),
]

CASTS = [
    CastSpec(
        replayable(),
        "animation-progress",
        (WIDTH, 3),
        steps=[
            *advance(timedelta(seconds=1)),
            SPACE,
            *advance(timedelta(seconds=3)),
            SPACE,
            *advance(timedelta(seconds=3)),
        ],
    ),
    CastSpec(staggered(), "animation-phases", (WIDTH, 3), steps=advance(timedelta(seconds=4))),
    CastSpec(
        bouncing(),
        "animation-loop",
        (WIDTH, 3),
        steps=[
            *advance(timedelta(seconds=3)),
            SPACE,
            AdvanceClock(by=timedelta(seconds=1)),
            SPACE,
            *advance(timedelta(seconds=2)),
        ],
    ),
]

if __name__ == "__main__":
    roots = {root.__name__: root for root in (replayable, staggered, bouncing)}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else replayable()))
