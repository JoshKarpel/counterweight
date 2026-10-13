import asyncio
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from counterweight.app import app
from counterweight.components import Component, component
from counterweight.controls import AnyControl, Quit, ScrollBy, ScrollTo
from counterweight.elements import AnyElement, Chunk, Div, Text
from counterweight.events import InputEvent, InputResponse, KeyPressed, Receiver
from counterweight.geometry import ORIGIN, Scroll
from counterweight.handlers import first, focus_receiver_on_press, scroll_on_wheel, tab_focus
from counterweight.hooks import use_effect, use_focus, use_scroll, use_state
from counterweight.keys import Key
from counterweight.styles import CellStyle, Style
from counterweight.styles.utilities import *

LEVELS = (("INFO", cyan_400), ("WARN", amber_400), ("ERROR", red_400), ("DEBUG", slate_500))
WORDS = (
    "request served cache miss retrying connection pool exhausted reloaded config from disk "
    "worker started shutting down slow query took longer than expected lease renewed for shard"
).split()

COLUMNS = ("host", "region", "cpu", "memory", "disk", "requests", "errors", "latency p50", "latency p99", "uptime")

NO_SCROLL = Scroll(offset=ORIGIN, max_offset=ORIGIN, view_width=0, view_height=0)


def log_lines(count: int) -> list[Text]:
    """Log entries of mixed lengths, which wrap to different heights, so no row estimate could scroll them."""
    rng = random.Random(0)
    entries = []
    for i in range(count):
        level, color = rng.choice(LEVELS)
        message = " ".join(rng.choice(WORDS) for _ in range(rng.randrange(3, 30)))
        entries.append(
            Text(
                content=[
                    Chunk(content=f"{i:03} ", style=CellStyle(foreground=slate_500)),
                    Chunk(content=f"{level:<5} ", style=CellStyle(foreground=color)),
                    Chunk(content=message),
                ],
                style=text_wrap_stable,
            )
        )
    return entries


def table_rows(count: int) -> list[Text]:
    """A table wider than its pane, so it scrolls on both axes."""
    rng = random.Random(1)
    header = Text(
        content="".join(f"{column:<12}" for column in COLUMNS), style=text_bg("slate", 800) | text_color("sky", 300)
    )
    rows = [
        Text(
            content="".join(
                f"{value:<12}"
                for value in (
                    f"web-{i:02}",
                    rng.choice(("us-east", "eu-west", "ap-south")),
                    f"{rng.uniform(0, 100):.0f}%",
                    f"{rng.uniform(0.5, 32):.1f} GiB",
                    f"{rng.uniform(0, 100):.0f}%",
                    f"{rng.randrange(10_000):,}",
                    f"{rng.randrange(50)}",
                    f"{rng.uniform(1, 40):.0f} ms",
                    f"{rng.uniform(40, 900):.0f} ms",
                    f"{rng.randrange(1, 90)}d",
                )
            )
        )
        for i in range(count)
    ]
    return [header, *rows]


@dataclass(frozen=True, slots=True)
class BodyState:
    """What a pane's body tells the pane, to show around it: how far it's scrolled, and whether it's focused."""

    scroll: Scroll
    is_focused: bool


@component
def scrolling_body(
    children: Sequence[AnyElement], axes: Style, auto_focus: bool, report: Callable[[BodyState], None]
) -> Div:
    """
    The part of a pane that scrolls: with the wheel, and with the keys while it's focused.
    It reports how far it's scrolled from an effect, which is how a component tells its parent
    about something only it can see, as a React component calls an `onScroll` prop.
    """
    focus = use_focus(auto_focus=auto_focus)
    scroll = use_scroll()

    async def tell() -> None:
        report(BodyState(scroll=scroll, is_focused=focus.is_focused))

    use_effect(tell, deps=(scroll, focus.is_focused))

    def on_key(event: InputEvent, receiver: Receiver) -> InputResponse:
        # The receiver's scroll is the body's own, so paging needs nothing reported.
        if (current := receiver.scroll) is None:
            return None
        page = max(1, current.view_height - 1)
        target = receiver.subtree
        match event:
            case KeyPressed(key=Key.Up):
                return ScrollBy(target, y=-1)
            case KeyPressed(key=Key.Down):
                return ScrollBy(target, y=1)
            case KeyPressed(key=Key.Left):
                return ScrollBy(target, x=-4)
            case KeyPressed(key=Key.Right):
                return ScrollBy(target, x=4)
            case KeyPressed(key=Key.PageUp):
                return ScrollBy(target, y=-page)
            case KeyPressed(key=Key.PageDown):
                return ScrollBy(target, y=page)
            case KeyPressed(key=Key.Home):
                return ScrollTo(target, x=0, y=0)
            case KeyPressed(key=Key.End):
                return ScrollTo(target, y=current.max_offset.y)
            case _:
                return None

    return Div(
        style=fill(1) | col | axes,
        on_input=first(on_key, scroll_on_wheel(), focus_receiver_on_press),
        children=children,
    )


@component
def pane(title: str, children: Sequence[AnyElement], axes: Style, auto_focus: bool = False) -> Div:
    """
    A titled, bordered pane around a body that scrolls.
    The border and the title are on the pane, outside the part that scrolls, so they stay put.
    """
    body, set_body = use_state(BodyState(scroll=NO_SCROLL, is_focused=False))
    scroll = body.scroll

    total = scroll.max_offset.y + scroll.view_height
    position = f" rows {scroll.offset.y + 1}-{scroll.offset.y + scroll.view_height} of {total} "
    if scroll.max_offset.x:
        position += f"· column {scroll.offset.x + 1} of {scroll.max_offset.x + scroll.view_width} "

    accent = border_color("sky", 400) if body.is_focused else border_color("slate", 600)
    return Div(
        style=fill(1) | col | border | border_lightrounded | accent,
        children=[
            Text(content=f" {title} ", style=position_absolute | inset_top(-1) | inset_left(1) | clip_to_border),
            Text(
                content=position,
                style=position_absolute | inset_bottom(-1) | inset_right(1) | clip_to_border | text_color("slate", 400),
            ),
            scrolling_body(children, axes, auto_focus, set_body),
        ],
    )


@component
def root() -> Div:
    def on_key(event: InputEvent, _: Receiver) -> AnyControl | None:
        match event:
            case KeyPressed(key=Key.ControlC):
                return Quit()
            case _:
                return None

    panes: list[Component] = [
        pane("Log", log_lines(80), overflow_y_scroll, auto_focus=True),
        pane("Hosts", table_rows(40), overflow_scroll | align_children_start),
    ]
    return Div(
        style=col | full,
        on_input=first(on_key, tab_focus),
        children=[
            Div(style=row | fill(1) | gap(1), children=panes),
            Text(
                content="wheel: scroll the pane under the pointer  ·  tab or click: focus a pane  ·  "
                "arrows, page up/down, home/end: scroll the focused pane  ·  ctrl+c: quit",
                style=text_justify_center | text_wrap_pretty | text_color("slate", 500),
            ),
        ],
    )


if __name__ == "__main__":
    asyncio.run(app(root()))
