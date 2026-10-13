import asyncio
import sys

from counterweight.app import app
from counterweight.components import component
from counterweight.controls import Screenshot, ScrollTo
from counterweight.elements import Div, Text
from counterweight.events import MouseDown, MouseScrolledDown, MouseUp
from counterweight.geometry import Position
from counterweight.handlers import on_click, scroll_on_wheel
from counterweight.hooks import ElementHandle, use_scroll, use_state
from counterweight.styles.utilities import *
from docs.examples.screenshot_spec import ScreenshotSpec

EVENTS = [
    "deploy started",
    "pulled image web:4.2.0",
    "migrations applied",
    "health check passed",
    "traffic shifted to 10%",
    "error rate nominal",
    "traffic shifted to 50%",
    "latency p99 within budget",
    "traffic shifted to 100%",
    "old replicas drained",
    "deploy finished",
]

# --8<-- [start:pane]


@component
def pane() -> Div:
    return Div(
        style=col | border | border_lightrounded | size(30, 6),
        children=[
            Text(content=" Deploy log ", style=position_absolute | inset_top(-1) | inset_left(1) | clip_to_border),
            Div(
                style=fill(1) | col | overflow_y_scroll,
                on_input=scroll_on_wheel(),
                children=[Text(content=f"{i:>2} {event}") for i, event in enumerate(EVENTS, start=1)],
            ),
        ],
    )


# --8<-- [end:pane]

# --8<-- [start:controls]


@component
def controlled() -> Div:
    log, _ = use_state(ElementHandle)

    return Div(
        style=col | gap(1),
        children=[
            Div(
                style=row | gap(2),
                children=[
                    Text(content="[ Top ]", on_input=on_click(lambda: ScrollTo(log, y=0))),
                    Text(content="[ Bottom ]", on_input=on_click(lambda: ScrollTo(log, y=len(EVENTS)))),
                ],
            ),
            Div(
                style=col | border | border_lightrounded | size(30, 5) | overflow_y_scroll,
                handle=log,
                children=[Text(content=f"{i:>2} {event}") for i, event in enumerate(EVENTS, start=1)],
            ),
        ],
    )


# --8<-- [end:controls]

# --8<-- [start:windowed]

ROWS = 100_000


@component
def windowed() -> Div:
    scroll = use_scroll()

    # Render the rows in view, with a screen's worth of rows on each side
    # so a scroll shows rows, not blank space, before this re-renders,
    # and an empty box above and below for the rest, so the content is as tall as every row.
    overscan = scroll.view_height
    first = max(0, scroll.offset.y - overscan)
    last = min(ROWS, scroll.offset.y + scroll.view_height + overscan)

    return Div(
        style=col | border | border_lightrounded | size(30, 6) | overflow_y_scroll,
        on_input=scroll_on_wheel(),
        children=[
            Div(style=height(first) | shrink(0)),
            *(Text(content=f"row {i:,} of {ROWS:,}") for i in range(first, last)),
            Div(style=height(ROWS - last) | shrink(0)),
        ],
    )


# --8<-- [end:windowed]

WHEEL = MouseScrolledDown(absolute=Position(5, 2))


def click(x: int, y: int) -> tuple[MouseDown, MouseUp]:
    return MouseDown(absolute=Position(x, y), button=1), MouseUp(absolute=Position(x, y), button=1)


# `use_scroll` reports a scroll one render after it changes, so this gives `windowed` that render.
SETTLE = Screenshot(handler=lambda frame: None)

SCREENSHOTS = [
    ScreenshotSpec(pane(), "scrolling-pane", (30, 6)),
    ScreenshotSpec(pane(), "scrolling-pane-wheeled", (30, 6), events=[WHEEL, WHEEL]),
    ScreenshotSpec(controlled(), "scrolling-controls", (30, 7), events=click(12, 0)),
    ScreenshotSpec(windowed(), "scrolling-windowed", (30, 6), events=[WHEEL, WHEEL, SETTLE]),
]


if __name__ == "__main__":
    roots = {root.__name__: root for root in (pane, controlled, windowed)}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else pane()))
