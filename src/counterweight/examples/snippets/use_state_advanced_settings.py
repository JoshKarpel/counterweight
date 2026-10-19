"""
Hooks: Hooks

Settings whose advanced part is a component of its own, rendered only when it's needed.
"""

import asyncio

from counterweight.app import app
from counterweight.components import component
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


ROOTS = (settings,)

# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import paced
from counterweight.controls import Marker
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still

A = KeyPressed(key="a")
PLUS = KeyPressed(key="+")

STILLS = [
    Still("use-state-advanced-settings", settings(), (32, 4), steps=[A, PLUS, PLUS]),
]

DEMOS = [
    Demo(
        "use-state-advanced-settings",
        settings(),
        (32, 4),
        steps=paced(
            [A, PLUS, PLUS, A, Marker("Hidden"), A, Marker("Shown again")],
            every=timedelta(milliseconds=800),
        ),
    ),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(settings()))
