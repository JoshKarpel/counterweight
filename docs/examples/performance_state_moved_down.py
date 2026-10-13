import asyncio

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Div, Text
from counterweight.events import InputEvent, KeyPressed, Receiver
from counterweight.hooks import use_focus, use_state
from counterweight.styles.utilities import *
from docs.examples.performance_state_in_root import METRICS, metric_card
from docs.examples.screenshot_spec import ScreenshotSpec

# --8<-- [start:example]


@component
def note() -> Text:
    use_focus(auto_focus=True)
    text, set_text = use_state("")

    def on_input(event: InputEvent, _: Receiver) -> None:
        if isinstance(event, KeyPressed) and len(event.key) == 1:
            set_text(text + event.key)

    return Text(content=f"Note: {text}", on_input=on_input)


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
