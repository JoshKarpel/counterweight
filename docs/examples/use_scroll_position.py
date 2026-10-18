import asyncio
from datetime import timedelta

from counterweight.app import app
from counterweight.autopilot import AutopilotStep
from counterweight.components import component
from counterweight.controls import AdvanceClock
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import MouseScrolledDown
from counterweight.events import MouseScrolledUp
from counterweight.geometry import Position
from counterweight.handlers import scroll_on_wheel
from counterweight.hooks import ElementHandle
from counterweight.hooks import use_scroll
from counterweight.hooks import use_state
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import CastSpec
from docs.examples.screenshot_spec import ScreenshotSpec

LINES = tuple(f"{n:>2} GET /items/{n * 37 % 1000} {404 if n % 7 == 0 else 200}" for n in range(1, 31))

# --8<-- [start:example]


@component
def document(lines: tuple[str, ...]) -> Div:
    body, _ = use_state(ElementHandle)
    scroll = use_scroll(body)

    first = scroll.offset.y + 1
    last = min(scroll.offset.y + scroll.view_height, len(lines))
    percent = 100 * scroll.offset.y // scroll.max_offset.y if scroll.max_offset.y else 100

    return Div(
        style=col | border | border_lightrounded | size(30, 9),
        children=(
            Text(
                content=f" Lines {first}-{last} of {len(lines)} ({percent}%) ",
                style=position_absolute | inset_top(-1) | inset_left(1) | clip_to_border | text_color("amber", 400),
            ),
            Div(
                style=fill(1) | col | pad_x(1) | overflow_y_scroll,
                handle=body,
                on_input=scroll_on_wheel(),
                children=tuple(Text(content=line) for line in lines),
            ),
            Text(
                content=f" ↓ {len(lines) - last} more " if last < len(lines) else "",
                style=position_absolute | inset_bottom(-1) | inset_right(1) | clip_to_border | text_color("slate", 400),
            ),
        ),
    )


# --8<-- [end:example]

DOWN = MouseScrolledDown(absolute=Position(5, 4))
UP = MouseScrolledUp(absolute=Position(5, 4))

# An autopilot hands the app its next step along with the render use_scroll asks for after the scroll it read moves,
# so in a recording that render would wait for the next pause; a step that takes no time lets it happen right away.
SETTLE = AdvanceClock(by=timedelta())


def settled(events: list[MouseScrolledDown | MouseScrolledUp]) -> list[AutopilotStep]:
    """`events` paced as a person turns the wheel, each followed by the render the scroll it makes asks for."""
    gap = AdvanceClock(by=timedelta(milliseconds=400))
    return [*(step for event in events for step in (gap, event, SETTLE)), AdvanceClock(by=timedelta(seconds=2))]


SCREENSHOTS = [
    ScreenshotSpec(document(LINES), "use-scroll-position", (30, 9), events=[DOWN, DOWN, SETTLE]),
]

CASTS = [
    CastSpec(document(LINES), "use-scroll-position", (30, 9), steps=settled([*[DOWN] * 9, *[UP] * 9])),
]


if __name__ == "__main__":
    asyncio.run(app(document(LINES)))
