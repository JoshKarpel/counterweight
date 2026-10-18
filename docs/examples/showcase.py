"""
Screenshots and recordings of the complete example apps in `examples/`, which the home page shows off.

The apps' code lives in `examples/`, so this module has no sections for a page to show,
only the steps that put each app in a state worth a picture.
"""

import asyncio
import sys
from datetime import timedelta

from counterweight.app import app
from counterweight.autopilot import WaitFor
from counterweight.controls import AdvanceClock
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseMoved
from counterweight.events import MouseUp
from counterweight.events import Pasted
from counterweight.geometry import Position
from counterweight.keys import Key
from counterweight.output import Frame
from docs.examples.screenshot_spec import CastSpec
from docs.examples.screenshot_spec import ScreenshotSpec
from docs.examples.screenshot_spec import paced
from examples.chat import root as chat
from examples.chess import root as chess
from examples.markdown_gallery import root as markdown_gallery
from examples.mouse import root as mouse
from examples.scrolling import root as scrolling
from examples.stopwatch import root as stopwatch
from examples.table import root as table
from examples.text_wrap import root as text_wrap
from examples.wordle import root as wordle


def typed(text: str) -> list[KeyPressed]:
    return [KeyPressed(key=character) for character in text]


ENTER = KeyPressed(key=Key.Enter)


def shows(text: str) -> WaitFor:
    """Wait until the screen shows `text`, for an app whose work takes real time, such as the chat's streamed reply."""

    def condition(frame: Frame) -> bool:
        return text in frame.text(ansi=False)

    return WaitFor(condition, timeout=timedelta(seconds=30))


SCREENSHOTS = [
    ScreenshotSpec(chess(), "showcase-chess", (16, 8)),
    ScreenshotSpec(
        wordle(),
        "showcase-wordle",
        (100, 40),
        events=[KeyPressed(key=Key.F1), *typed("CRANE"), ENTER, *typed("LASER"), ENTER, *typed("GAZ")],
    ),
    ScreenshotSpec(table(), "showcase-table", (72, 37), events=[KeyPressed(key="4"), *[KeyPressed(key=Key.Down)] * 2]),
    ScreenshotSpec(
        chat(),
        "showcase-chat",
        (100, 30),
        events=[
            Pasted(text="How do I reverse a list?"),
            ENTER,
            shows("without copying"),
            Pasted(text="Which sort should I use?"),
            ENTER,
            shows("sort by several keys in turn"),
        ],
    ),
    ScreenshotSpec(markdown_gallery(), "showcase-markdown-gallery", (100, 30)),
    ScreenshotSpec(scrolling(), "showcase-scrolling", (100, 24)),
    ScreenshotSpec(text_wrap(), "showcase-text-wrap", (120, 36)),
]


def ticks(duration: timedelta, every: timedelta = timedelta(milliseconds=50)) -> list[AdvanceClock]:
    """`duration` passing a little at a time, so a clock on screen counts up through it."""
    return [AdvanceClock(by=every)] * (duration // every)


def pointer_path(start: Position, end: Position, moves: int, button: int | None) -> list[MouseMoved]:
    """The pointer moving from `start` to `end` in `moves` even steps, holding `button`."""
    return [
        MouseMoved(
            absolute=Position(start.x + (end.x - start.x) * step // moves, start.y + (end.y - start.y) * step // moves),
            button=button,
        )
        for step in range(1, moves + 1)
    ]


def drag(start: Position, end: Position, moves: int) -> list[MouseDown | MouseMoved | MouseUp]:
    return [MouseDown(absolute=start, button=1), *pointer_path(start, end, moves, 1), MouseUp(absolute=end, button=1)]


def click(position: Position) -> list[MouseDown | MouseUp]:
    return [MouseDown(absolute=position, button=1), MouseUp(absolute=position, button=1)]


SPACE = KeyPressed(key=Key.Space)
TAB = KeyPressed(key=Key.Tab)
SHIFT_TAB = KeyPressed(key=Key.BackTab)
SECOND = timedelta(seconds=1)

CASTS = [
    CastSpec(
        stopwatch(),
        "showcase-stopwatch",
        (60, 16),
        steps=[
            AdvanceClock(by=SECOND),
            SPACE,
            *ticks(2 * SECOND),
            TAB,
            SPACE,
            *ticks(1.5 * SECOND),
            TAB,
            SPACE,
            *ticks(SECOND),
            SHIFT_TAB,
            SHIFT_TAB,
            SPACE,
            *ticks(SECOND),
            TAB,
            SPACE,
            *ticks(0.5 * SECOND),
            TAB,
            SPACE,
            AdvanceClock(by=2 * SECOND),
        ],
    ),
    CastSpec(
        mouse(),
        "showcase-mouse",
        (80, 26),
        steps=paced(
            [
                *pointer_path(Position(3, 8), Position(28, 11), moves=25, button=None),
                *pointer_path(Position(28, 11), Position(36, 7), moves=8, button=None),
                *click(Position(36, 7)),
                *pointer_path(Position(36, 7), Position(56, 5), moves=10, button=None),
                *drag(Position(56, 5), Position(69, 12), moves=13),
                *pointer_path(Position(69, 12), Position(41, 21), moves=14, button=None),
                *drag(Position(41, 21), Position(37, 18), moves=6),
            ],
            every=timedelta(milliseconds=40),
        ),
    ),
]

if __name__ == "__main__":
    apps = {spec.asset.removeprefix("showcase-"): spec.root for spec in SCREENSHOTS}
    apps |= {spec.asset.removeprefix("showcase-"): spec.root for spec in CASTS}
    asyncio.run(app(apps[sys.argv[1]]))
