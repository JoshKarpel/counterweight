import asyncio
from collections.abc import Iterable
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from pathlib import Path

from more_itertools import intersperse

from counterweight.app import app
from counterweight.asciicast import Recording
from counterweight.autopilot import AutopilotStep
from counterweight.clock import FrozenClock
from counterweight.controls import AdvanceClock
from counterweight.controls import Marker
from counterweight.controls import Quit
from counterweight.events import KeyPressed
from counterweight.keys import Key
from docs.examples.screenshot_spec import CastSpec
from docs.examples.screenshot_spec import ScreenshotSpec
from docs.examples.text_input import search

TYPED = [KeyPressed(key="a"), KeyPressed(key="n")]
MANGO = [KeyPressed(key=character) for character in "mango"]

# --8<-- [start:chapters]

PAUSE = AdvanceClock(by=timedelta(milliseconds=400))


def chapter(label: str, steps: Iterable[AutopilotStep]) -> list[AutopilotStep]:
    return [Marker(label), PAUSE, *intersperse(PAUSE, steps), PAUSE]


DEMO = [
    *chapter("Scroll the results", [KeyPressed(key=Key.Down)] * 2),
    *chapter("Search", [KeyPressed(key="a"), KeyPressed(key="n")]),
    *chapter("Clear the search", [KeyPressed(key=Key.Backspace)] * 2),
]


async def record_demo() -> None:
    await app(
        search(),
        headless=True,
        dimensions=(30, 8),
        clock=FrozenClock(datetime(2026, 3, 14, tzinfo=UTC)),
        recording=Recording(Path("search.cast"), input=True),
        autopilot=[*DEMO, Quit()],
    )


# --8<-- [end:chapters]

SCREENSHOTS = [ScreenshotSpec(search(), "autopilot-typed", (30, 8), events=TYPED)]

CASTS = [
    CastSpec(
        search(),
        "autopilot-mango",
        (30, 8),
        steps=[
            *intersperse(AdvanceClock(by=timedelta(milliseconds=300)), MANGO),
            AdvanceClock(by=timedelta(seconds=2)),
        ],
    ),
    CastSpec(search(), "autopilot-chapters", (30, 8), steps=[*DEMO, AdvanceClock(by=timedelta(seconds=2))]),
]


if __name__ == "__main__":
    asyncio.run(record_demo())
