import asyncio
import random

from counterweight.app import app
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import AnyControl
from counterweight.controls import Quit
from counterweight.elements import AnyElement
from counterweight.elements import Chunk
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.events import InputEvent
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.handlers import first
from counterweight.handlers import on_click
from counterweight.handlers import tab_focus
from counterweight.headless import ScrollAxis
from counterweight.headless import use_scroll_area
from counterweight.keys import Key
from counterweight.styles.utilities import *

LEVELS = (("INFO", cyan_400), ("WARN", amber_400), ("ERROR", red_400), ("DEBUG", slate_500))
WORDS = [
    "request",
    "served",
    "cache",
    "miss",
    "retrying",
    "connection",
    "pool",
    "exhausted",
    "reloaded",
    "config",
    "from",
    "disk",
    "worker",
    "started",
    "shutting",
    "down",
    "slow",
    "query",
    "took",
    "longer",
    "than",
    "expected",
    "lease",
    "renewed",
    "for",
    "shard",
]

COLUMNS = ("host", "region", "cpu", "memory", "disk", "requests", "errors", "latency p50", "latency p99", "uptime")


def log_lines(count: int) -> tuple[Text, ...]:
    """Log entries of mixed lengths, which wrap to different heights, so no row estimate could scroll them."""
    rng = random.Random(0)
    entries = []
    for i in range(count):
        level, color = rng.choice(LEVELS)
        message = " ".join(rng.choice(WORDS) for _ in range(rng.randrange(3, 30)))
        entries.append(
            Text(
                content=(
                    Chunk(content=f"{i:03} ", style=text_color(slate_500)),
                    Chunk(content=f"{level:<5} ", style=text_color(color)),
                    Chunk(content=message),
                ),
                style=text_wrap_stable,
            )
        )
    return tuple(entries)


def table_rows(count: int) -> tuple[Text, ...]:
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
    return (header, *rows)


@component
def pane(
    title: str,
    children: tuple[AnyElement, ...],
    axis: ScrollAxis,
    stick_to_end: bool = False,
    auto_focus: bool = False,
    has_jump_to_end: bool = False,
) -> Div:
    """
    A titled, bordered pane around a body that scrolls: with the wheel, and with the keys while the pane is focused.
    The border, the title, and the button that jumps to the end are on the pane, outside the part that scrolls,
    so they stay put while it scrolls, and the pane is the element that's focused, so its border can show it.
    """
    area = use_scroll_area(axis, stick_to_end, auto_focus=auto_focus)
    scroll = area.scroll

    total = scroll.max_offset.y + scroll.view_height
    position = f" rows {scroll.offset.y + 1}-{scroll.offset.y + scroll.view_height} of {total} "
    if scroll.max_offset.x:
        position += f"· column {scroll.offset.x + 1} of {scroll.max_offset.x + scroll.view_width} "

    accent = border_color("sky", 400) if area.focus.is_focused else border_color("slate", 600)
    return Div(
        style=fill(1) | col | border | border_lightrounded | accent,
        on_input=area.on_input,
        children=(
            Text(content=f" {title} ", style=position_absolute | inset_top(-1) | inset_left(1) | clip_to_border),
            Text(
                content=position,
                style=position_absolute | inset_bottom(-1) | inset_right(1) | clip_to_border | text_color("slate", 400),
            ),
            Div(style=fill(1) | col | area.style, handle=area.viewport, children=children),
            # Over the body's last line, as Claude Code shows one over its transcript once it's scrolled back.
            *(
                (
                    Text(
                        content=" ↓ jump to end ",
                        style=position_absolute
                        | inset_bottom(0)
                        | inset_x(0)
                        | margin_x_auto
                        | fit_content_width
                        | text_bg("sky", 800)
                        | text_color("sky", 100),
                        on_input=on_click(lambda: area.to_end),
                    ),
                )
                if has_jump_to_end and not area.is_at_end
                else ()
            ),
        ),
    )


@component
def root() -> Div:
    def on_key(event: InputEvent, _: Receiver) -> AnyControl | None:
        match event:
            case KeyPressed(key=Key.ControlC):
                return Quit()
            case _:
                return None

    panes: tuple[Component, ...] = (
        pane("Log", log_lines(80), "y", stick_to_end=True, auto_focus=True, has_jump_to_end=True),
        pane("Hosts", table_rows(40), "both"),
    )
    return Div(
        style=col | full,
        on_input=first(on_key, tab_focus),
        children=(
            Div(style=row | fill(1) | gap(1), children=panes),
            Text(
                content="wheel: scroll the pane under the pointer  ·  tab or click: focus a pane  ·  "
                "arrows, page up/down, home/end: scroll the focused pane  ·  ctrl+c: quit",
                style=text_justify_center | text_wrap_pretty | text_color("slate", 500),
            ),
        ),
    )


if __name__ == "__main__":
    asyncio.run(app(root()))
