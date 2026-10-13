import asyncio

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.events import KeyPressed
from counterweight.hooks import use_state, use_text_input
from counterweight.styles.utilities import *
from docs.examples.performance_state_in_root import METRICS, metric_card, note_line
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:example]


@component
def note() -> Text:
    text, set_text = use_state("")
    field = use_text_input(text, set_text, auto_focus=True)
    return Text(content=note_line(field), on_input=field.on_input)


@component
def dashboard() -> Div:
    return Div(
        style=col,
        children=[
            note(),
            Div(style=row, children=[metric_card(label, value) for label, value in METRICS]),
        ],
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
