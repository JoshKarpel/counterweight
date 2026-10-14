import asyncio

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div
from counterweight.events import KeyPressed
from counterweight.headless import use_text_input
from counterweight.hooks import use_state
from counterweight.styles.utilities import *
from docs.examples.performance_state_in_root import METRICS, metric_card, note_line
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:example]


@component
def note() -> Div:
    text, set_text = use_state("")
    field = use_text_input(text, set_text, auto_focus=True)
    return Div(style=row, on_input=field.on_input, children=note_line(field))


@component
def dashboard() -> Div:
    return Div(
        style=col,
        children=(
            note(),
            Div(style=row, children=tuple(metric_card(label, value) for label, value in METRICS)),
        ),
    )


# --8<-- [end:example]

SCREENSHOTS = [
    ScreenshotSpec(
        dashboard(),
        "performance-dashboard",
        (80, 5),
        events=[KeyPressed(key=key) for key in "disk is busy"],
    )
]


if __name__ == "__main__":
    asyncio.run(app(dashboard()))
