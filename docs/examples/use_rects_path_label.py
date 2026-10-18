import asyncio
from datetime import timedelta

from counterweight.app import app
from counterweight.autopilot import AutopilotStep
from counterweight.components import component
from counterweight.controls import AdvanceClock
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import use_rects
from counterweight.hooks import use_state
from counterweight.keys import Key
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import CastSpec
from docs.examples.screenshot_spec import ScreenshotSpec

PATH = "src/counterweight/hooks/hooks.py"

# --8<-- [start:example]


def shortened(path: str, width: int) -> str:
    """`path` with as many leading directories as it takes to fit in `width` cells replaced by `…`."""
    parts = path.split("/")
    for start in range(len(parts)):
        candidate = "/".join(("…", *parts[start:]) if start else parts)
        if len(candidate) <= width:
            return candidate
    return parts[-1][:width]


@component
def path_label(path: str) -> Text:
    width = use_rects().content.width
    return Text(
        content=shortened(path, width), style=full_width | min_width(0) | text_wrap_none | text_color("amber", 400)
    )


@component
def split() -> Div:
    left_width, set_left_width = use_state(24)

    def on_input(event: InputEvent, _: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=Key.Left):
                set_left_width(lambda width: max(width - 4, 8))
                return ()
            case KeyPressed(key=Key.Right):
                set_left_width(lambda width: min(width + 4, 40))
                return ()
            case _:
                return None

    pane = border | border_lightrounded | pad_x(1)

    return Div(
        style=row,
        on_input=on_input,
        children=(
            Div(style=pane | width(left_width), children=(path_label(PATH),)),
            Div(style=pane | fill(1), children=(path_label(PATH),)),
        ),
    )


# --8<-- [end:example]

LEFT = KeyPressed(key=Key.Left)
RIGHT = KeyPressed(key=Key.Right)

# An autopilot hands the app its next step along with the render use_rects asks for after a layout moves what it read,
# so in a recording that render would wait for the next pause; a step that takes no time lets it happen right away.
SETTLE = AdvanceClock(by=timedelta())


def settled(keys: list[KeyPressed]) -> list[AutopilotStep]:
    """`keys` paced as a person presses them, each followed by the render its new layout asks for."""
    gap = AdvanceClock(by=timedelta(milliseconds=500))
    return [*(step for key in keys for step in (gap, key, SETTLE)), AdvanceClock(by=timedelta(seconds=2))]


SCREENSHOTS = [
    ScreenshotSpec(split(), "use-rects-path-label", (48, 3), events=[RIGHT, RIGHT, RIGHT, SETTLE]),
]

CASTS = [
    CastSpec(
        split(),
        "use-rects-path-label",
        (48, 3),
        steps=settled([RIGHT, RIGHT, RIGHT, RIGHT, LEFT, LEFT, LEFT, LEFT, LEFT, LEFT, LEFT]),
    ),
]


if __name__ == "__main__":
    asyncio.run(app(split()))
