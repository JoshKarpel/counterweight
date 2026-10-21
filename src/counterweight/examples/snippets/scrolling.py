"""
Layout: Scrolling

Scroll containers, scrolling from a handler, a windowed list, following the end, a pager's keys, and a table of contents.
"""

import asyncio
import sys
from datetime import timedelta
from functools import partial

from counterweight import app
from counterweight.components import component
from counterweight.controls import ScrollIntoView
from counterweight.controls import ScrollTo
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.focus import ElementHandle
from counterweight.handlers import first
from counterweight.handlers import on_click
from counterweight.handlers import page_down
from counterweight.handlers import page_up
from counterweight.handlers import scroll_on_keys
from counterweight.handlers import scroll_on_wheel
from counterweight.hooks import use_clock
from counterweight.hooks import use_focus
from counterweight.hooks import use_scroll
from counterweight.hooks import use_state
from counterweight.styles.utilities import *

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
        children=(
            Text(content=" Deploy log ", style=position_absolute | inset_top(-1) | inset_left(1) | clip_to_border),
            Div(
                style=fill(1) | col | overflow_y_scroll,
                on_input=scroll_on_wheel(),
                children=tuple(Text(content=f"{i:>2} {event}") for i, event in enumerate(EVENTS, start=1)),
            ),
        ),
    )


# --8<-- [end:pane]

# --8<-- [start:controls]


@component
def controlled() -> Div:
    log, _ = use_state(ElementHandle)

    return Div(
        style=col | gap(1),
        children=(
            Div(
                style=row | gap(2),
                children=(
                    Text(content="[ Top ]", on_input=on_click(lambda: ScrollTo(log, y=0))),
                    Text(content="[ Bottom ]", on_input=on_click(lambda: ScrollTo(log, y=len(EVENTS)))),
                ),
            ),
            Div(
                style=col | border | border_lightrounded | size(30, 5) | overflow_y_scroll,
                handle=log,
                children=tuple(Text(content=f"{i:>2} {event}") for i, event in enumerate(EVENTS, start=1)),
            ),
        ),
    )


# --8<-- [end:controls]

# --8<-- [start:windowed]

ROWS = 100_000


@component
def windowed_row(i: int) -> Text:
    return Text(content=f"row {i:,} of {ROWS:,}")


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
        children=(
            Div(style=height(first) | shrink(0)),
            # Keyed, so a row keeps its node as the window moves, and scroll anchoring follows the row.
            *(windowed_row(i).with_key(str(i)) for i in range(first, last)),
            Div(style=height(ROWS - last) | shrink(0)),
        ),
    )


# --8<-- [end:windowed]

# --8<-- [start:tail]

KEPT_LINES = 8


@component
def request_line(number: int) -> Text:
    return Text(content=f"{number:>3} GET /items/{number} 200")


@component
def tail() -> Div:
    tick = use_clock(timedelta(seconds=1))
    # A line a second, keeping the newest few.
    newest = 4 + int(tick.since_mount.total_seconds())

    return Div(
        style=col | border | border_lightrounded | size(30, 6) | overflow_y_scroll | stick_to_end_y,
        on_input=scroll_on_wheel(1),
        # Keyed, so a line keeps its node, which anchoring follows, as older lines drop off the top.
        children=tuple(request_line(n).with_key(str(n)) for n in range(max(0, newest - KEPT_LINES), newest)),
    )


# --8<-- [end:tail]

# --8<-- [start:jump]


@component
def jump_to_end() -> Div:
    log, _ = use_state(ElementHandle)
    scroll = use_scroll(log)

    return Div(
        style=col | border | border_lightrounded | size(30, 6),
        children=(
            Div(
                style=fill(1) | col | overflow_y_scroll | stick_to_end_y,
                handle=log,
                on_input=scroll_on_wheel(1),
                children=tuple(Text(content=f"{i:>2} {event}") for i, event in enumerate(EVENTS, start=1)),
            ),
            # A sibling of the log, not a child, so it stays over the last line as the log scrolls.
            *(
                ()
                if scroll.offset.y == scroll.max_offset.y
                else (
                    Text(
                        content=" ↓ Jump to end ",
                        style=position_absolute
                        | inset_bottom(0)
                        | inset_x(0)
                        | margin_x_auto
                        | fit_content_width
                        | text_bg("sky", 800),
                        on_input=on_click(lambda: ScrollTo(log, y=scroll.max_offset.y)),
                    ),
                )
            ),
        ),
    )


# --8<-- [end:jump]

# --8<-- [start:keys]


def less_keys(event: InputEvent, receiver: Receiver) -> InputResponse:
    # Receiver.scroll is None only off a scroll container, and this handler is only on one.
    if receiver.scroll is None:
        return None
    match event:
        case KeyPressed(key=" "):
            return page_down(receiver.subtree, receiver.scroll, fraction=1.0)
        case KeyPressed(key="d"):
            return page_down(receiver.subtree, receiver.scroll, fraction=0.5)
        case KeyPressed(key="u"):
            return page_up(receiver.subtree, receiver.scroll, fraction=0.5)
        case _:
            return None


@component
def pager() -> Div:
    focus = use_focus(auto_focus=True)

    return Div(
        style=col
        | border
        | border_lightrounded
        | size(30, 8)
        | overflow_y_scroll
        | (border_color("sky", 400) if focus.is_focused else border_color("slate", 600)),
        on_input=first(less_keys, scroll_on_keys(), scroll_on_wheel()),
        children=tuple(Text(content=f"{i:>2} {EVENTS[i % len(EVENTS)]}") for i in range(30)),
    )


# --8<-- [end:keys]

# --8<-- [start:contents]

SECTIONS = (
    ("Install", "Add counterweight to your project with uv."),
    ("Components", "A component is a function that returns an element."),
    ("Hooks", "Hooks keep state and run effects for a component."),
    ("Styles", "Styles are merged from small utilities with |."),
)


@component
def contents() -> Div:
    headings, _ = use_state(lambda: tuple(ElementHandle() for _ in SECTIONS))

    return Div(
        style=row | size(40, 6),
        children=(
            Div(
                style=col | width(14) | border_right | border_lightrounded | pad_x(1),
                children=tuple(
                    Text(
                        content=title,
                        style=text_color("sky", 300),
                        on_input=on_click(partial(ScrollIntoView, heading)),
                    )
                    for (title, _), heading in zip(SECTIONS, headings, strict=True)
                ),
            ),
            Div(
                style=fill(1) | col | gap(1) | pad_x(1) | overflow_y_scroll,
                on_input=scroll_on_wheel(1),
                children=tuple(
                    Div(
                        style=col,
                        children=(
                            Text(content=title, style=text_color("amber", 400), handle=heading),
                            Text(content=body, style=text_wrap_pretty),
                        ),
                    )
                    for (title, body), heading in zip(SECTIONS, headings, strict=True)
                ),
            ),
        ),
    )


# --8<-- [end:contents]


ROOTS = (pane, controlled, windowed, tail, jump_to_end, pager, contents)

# --8<-- [start:scenes]


from counterweight.autopilot import paced
from counterweight.controls import AdvanceClock
from counterweight.controls import AnyControl
from counterweight.controls import Marker
from counterweight.controls import Screenshot
from counterweight.events import AnyEvent
from counterweight.events import MouseDown
from counterweight.events import MouseScrolledDown
from counterweight.events import MouseScrolledUp
from counterweight.events import MouseUp
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still
from counterweight.geometry import Position
from counterweight.keys import Key

WHEEL = MouseScrolledDown(absolute=Position(5, 2))


def click(x: int, y: int) -> tuple[MouseDown, MouseUp]:
    return MouseDown(absolute=Position(x, y), button=1), MouseUp(absolute=Position(x, y), button=1)


# `use_scroll` reports a scroll one render after it changes, so this gives `windowed` that render.
SETTLE = Screenshot(handler=lambda frame: None)

PAGE_DOWN = KeyPressed(key=Key.PageDown)

WHEEL_UP = MouseScrolledUp(absolute=Position(5, 2))
TAILED = AdvanceClock(by=timedelta(seconds=10))
READ_BACK: list[AnyEvent | AnyControl] = [TAILED, WHEEL_UP, WHEEL_UP]

# `use_scroll` reports a scroll one render after it changes, so the button appears, and goes, a render later.
JUMPED_BACK: list[AnyEvent | AnyControl] = [WHEEL_UP, WHEEL_UP, SETTLE]

STILLS = [
    Still("scrolling-pane", pane(), (30, 6)),
    Still("scrolling-pane-wheeled", pane(), (30, 6), steps=[WHEEL, WHEEL]),
    Still("scrolling-controls", controlled(), (30, 7), steps=click(12, 0)),
    Still("scrolling-windowed", windowed(), (30, 6), steps=[WHEEL, WHEEL, SETTLE]),
    Still("scrolling-tail", tail(), (30, 6), steps=[TAILED]),
    Still("scrolling-tail-later", tail(), (30, 6), steps=[TAILED, AdvanceClock(by=timedelta(seconds=2))]),
    Still("scrolling-tail-read-back", tail(), (30, 6), steps=READ_BACK),
    Still("scrolling-tail-read-back-later", tail(), (30, 6), steps=[*READ_BACK, AdvanceClock(by=timedelta(seconds=2))]),
    Still("scrolling-jump", jump_to_end(), (30, 6), steps=JUMPED_BACK),
    Still("scrolling-jump-clicked", jump_to_end(), (30, 6), steps=[*JUMPED_BACK, *click(15, 4), SETTLE]),
    Still("scrolling-keys", pager(), (30, 8), steps=[PAGE_DOWN]),
    Still("scrolling-keys-half", pager(), (30, 8), steps=[PAGE_DOWN, KeyPressed(key="d")]),
    Still("scrolling-contents", contents(), (40, 6)),
    Still("scrolling-contents-jumped", contents(), (40, 6), steps=click(2, 2)),
]

SECOND = AdvanceClock(by=timedelta(seconds=1))
GLANCE = AdvanceClock(by=timedelta(milliseconds=400))

DEMOS = [
    Demo(
        "scrolling-tail",
        tail(),
        (30, 6),
        steps=[
            *[SECOND] * 6,
            Marker("Scrolled back"),
            WHEEL_UP,
            GLANCE,
            WHEEL_UP,
            *[SECOND] * 4,
            Marker("Following again"),
            WHEEL,
            GLANCE,
            WHEEL,
            *[SECOND] * 4,
        ],
    ),
    Demo(
        "scrolling-jump",
        jump_to_end(),
        (30, 6),
        steps=[
            *paced(
                [WHEEL_UP, WHEEL_UP, WHEEL_UP, SETTLE, *click(15, 4), SETTLE],
                pause=AdvanceClock(by=timedelta(milliseconds=600)),
            ),
            AdvanceClock(by=timedelta(seconds=2)),
        ],
    ),
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    roots = {root.__name__: root for root in ROOTS}
    asyncio.run(app(roots[sys.argv[1]]() if len(sys.argv) > 1 else ROOTS[0]()))
