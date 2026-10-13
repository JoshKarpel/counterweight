import asyncio
from datetime import timedelta

from counterweight.app import app
from counterweight.components import Component, component
from counterweight.controls import AdvanceClock
from counterweight.elements import Div, Text
from counterweight.hooks import use_clock
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:example]

FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
FRAME_TIME = timedelta(milliseconds=80)


@component
def spinner(label: str) -> Text:
    elapsed = use_clock(FRAME_TIME).since_mount
    frame = FRAMES[elapsed // FRAME_TIME % len(FRAMES)]
    return Text(content=f"{frame} {label} ({elapsed // timedelta(seconds=1)}s)", style=text_color("amber", 400))


@component
def progress(done: tuple[str, ...], current: str) -> Div:
    return Div(
        style=col,
        children=(
            *(Text(content=f"✓ {step}", style=text_color("emerald", 500)) for step in done),
            # Keyed by the step, so each new step remounts the spinner and restarts its time.
            spinner(current).with_key(current),
        ),
    )


# --8<-- [end:example]


def agent_progress() -> Component:
    return progress(("Read pyproject.toml", "Ran the tests"), "Fixing the failing test")


SCREENSHOTS = [
    ScreenshotSpec(
        agent_progress(),
        "spinner",
        (40, 3),
        events=[AdvanceClock(by=timedelta(seconds=4, milliseconds=160))],
    )
]


if __name__ == "__main__":
    asyncio.run(app(agent_progress()))
