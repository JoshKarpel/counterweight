"""
Cookbook: Spinners

A coding agent's progress, with a spinner on the step it's working on.
"""

import asyncio
from datetime import timedelta

from counterweight import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.hooks import use_clock
from counterweight.styles.utilities import *

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


@component
def agent_progress() -> Div:
    """A coding agent's progress, two steps in."""
    return Div(style=col, children=(progress(("Read pyproject.toml", "Ran the tests"), "Fixing the failing test"),))


ROOTS = (agent_progress,)

# --8<-- [start:scenes]

from counterweight.controls import AdvanceClock
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still

STILLS = [Still("spinner", agent_progress(), (40, 3), steps=[AdvanceClock(by=timedelta(seconds=4, milliseconds=160))])]

DEMOS = [Demo("spinner", agent_progress(), (40, 3), steps=[AdvanceClock(by=FRAME_TIME)] * 50)]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(agent_progress()))
