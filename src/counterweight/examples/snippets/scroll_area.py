"""
Headless components: Scroll areas

A deploy log that follows its newest line, a log scrolled from outside, and panes that scroll.
"""

import asyncio
import sys

from counterweight import app
from counterweight.components import component
from counterweight.controls import ScrollBy
from counterweight.controls import ScrollTo
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.focus import ElementHandle
from counterweight.handlers import on_click
from counterweight.handlers import tab_focus
from counterweight.headless import use_scroll_area
from counterweight.hooks import use_scroll
from counterweight.hooks import use_state
from counterweight.styles.utilities import *
from counterweight.widgets import scroll_area

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

# --8<-- [start:hook]


@component
def deploy_log() -> Div:
    area = use_scroll_area(stick_to_end=True, auto_focus=True)

    return Div(
        style=col
        | border
        | border_lightrounded
        | size(30, 6)
        | (border_color("sky", 400) if area.focus.is_focused else border_color("slate", 600)),
        # The element that's focused, which keys, and wheel events and presses anywhere inside, reach.
        on_input=area.on_input,
        children=(
            Text(content=" Deploy log ", style=position_absolute | inset_top(-1) | inset_left(1) | clip_to_border),
            # The element that scrolls, with the area's style merged after fill(1), which hides overflow.
            Div(
                style=fill(1) | col | area.style,
                handle=area.viewport,
                children=tuple(Text(content=f"{i:>2} {event}") for i, event in enumerate(EVENTS, start=1)),
            ),
            # Beside the part that scrolls, so it stays over the last line.
            *(
                ()
                if area.is_at_end
                else (
                    Text(
                        content=" ↓ Jump to latest ",
                        style=position_absolute
                        | inset_bottom(0)
                        | inset_x(0)
                        | margin_x_auto
                        | fit_content_width
                        | text_bg("sky", 800),
                        on_input=on_click(lambda: area.to_end),
                    ),
                )
            ),
        ),
    )


# --8<-- [end:hook]

# --8<-- [start:outside]


@component
def reader() -> Div:
    viewport, _ = use_state(ElementHandle)
    scroll = use_scroll(viewport)
    top = scroll.offset.y

    def vim_keys(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key="g"):
                return ScrollTo(viewport, y=0)
            case KeyPressed(key="G"):
                return ScrollTo(viewport, y=len(EVENTS))
            case _:
                return None

    return Div(
        style=col | width(36),
        # The keys the area doesn't scroll for bubble up to here from it.
        on_input=vim_keys,
        children=(
            scroll_area(
                tuple(Text(content=f"{i:>2} {event}") for i, event in enumerate(EVENTS, start=1)),
                viewport=viewport,
                style=height(6),
                auto_focus=True,
            ),
            Div(
                style=row | gap(1) | pad_x(1),
                children=(
                    Text(content=f"lines {top + 1}-{top + scroll.view_height} of {len(EVENTS)}", style=grow(1)),
                    Text(content="[ Top ]", on_input=on_click(lambda: ScrollTo(viewport, y=0))),
                    Text(content="[ Next ]", on_input=on_click(lambda: ScrollBy(viewport, y=scroll.view_height))),
                ),
            ),
        ),
    )


# --8<-- [end:outside]

# --8<-- [start:widget]

SOURCE = (
    "def deploy(image: str, steps: tuple[int, ...] = (10, 50, 100)) -> None:",
    "    for percent in steps:",
    "        shift_traffic(image, percent)",
)


@component
def panes() -> Div:
    return Div(
        style=row | gap(1),
        on_input=tab_focus,
        children=(
            scroll_area(
                tuple(Text(content=event) for event in EVENTS),
                style=size(24, 6),
                auto_focus=True,
            ),
            scroll_area(
                tuple(Text(content=line) for line in SOURCE),
                axis="x",
                style=size(24, 6),
            ),
        ),
    )


# --8<-- [end:widget]


ROOTS = (deploy_log, reader, panes)

# --8<-- [start:scenes]

from datetime import timedelta

from counterweight.autopilot import paced
from counterweight.controls import AdvanceClock
from counterweight.controls import AnyControl
from counterweight.controls import Screenshot
from counterweight.events import AnyEvent
from counterweight.events import MouseDown
from counterweight.events import MouseUp
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still
from counterweight.geometry import Position
from counterweight.keys import Key


def pressed(*keys: str) -> tuple[KeyPressed, ...]:
    return tuple(KeyPressed(key=key) for key in keys)


def click(x: int, y: int) -> tuple[MouseDown, MouseUp]:
    return MouseDown(absolute=Position(x, y), button=1), MouseUp(absolute=Position(x, y), button=1)


# `use_scroll` reports a scroll one render after it changes, so the button appears, and goes, a render later.
SETTLE = Screenshot(handler=lambda frame: None)
PAGED_UP: tuple[AnyEvent | AnyControl, ...] = (*pressed(Key.PageUp), SETTLE)

NEXT = click(31, 6)
TOP = click(23, 6)

STILLS = [
    Still("scroll-area-log", deploy_log(), (30, 6)),
    Still("scroll-area-log-paged-up", deploy_log(), (30, 6), steps=PAGED_UP),
    Still("scroll-area-log-jumped", deploy_log(), (30, 6), steps=(*PAGED_UP, *click(15, 4), SETTLE)),
    Still("scroll-area-outside", reader(), (36, 7)),
    Still("scroll-area-outside-next", reader(), (36, 7), steps=(*NEXT, SETTLE)),
    Still("scroll-area-outside-end", reader(), (36, 7), steps=(*pressed("G"), SETTLE)),
    Still("scroll-area-widgets", panes(), (49, 6)),
    Still("scroll-area-widgets-sideways", panes(), (49, 6), steps=pressed(Key.Tab, *(Key.Right,) * 12)),
]

DEMOS = [
    Demo(
        "scroll-area-outside",
        reader(),
        (36, 7),
        steps=[
            *paced(
                [
                    *NEXT,
                    SETTLE,
                    *NEXT,
                    SETTLE,
                    *TOP,
                    SETTLE,
                    *pressed(Key.Down),
                    SETTLE,
                    *pressed("G"),
                    SETTLE,
                    *pressed("g"),
                    SETTLE,
                ],
                pause=AdvanceClock(by=timedelta(milliseconds=800)),
            ),
            AdvanceClock(by=timedelta(seconds=2)),
        ],
    ),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
