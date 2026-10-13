import asyncio
import random
from collections.abc import Callable, Sequence

from counterweight.app import app
from counterweight.components import Component, component
from counterweight.controls import AnyControl, Quit, ScrollBy, ScrollTo
from counterweight.elements import AnyElement, Chunk, Div, Text
from counterweight.events import InputEvent, InputResponse, KeyPressed, Receiver
from counterweight.handlers import first, focus_receiver_on_press, on_click, scroll_on_wheel, tab_focus
from counterweight.hooks import ElementHandle, use_effect, use_focus, use_scroll, use_state
from counterweight.keys import Key
from counterweight.styles import CellStyle, Style
from counterweight.styles.utilities import *

LEVELS = (("INFO", cyan_400), ("WARN", amber_400), ("ERROR", red_400), ("DEBUG", slate_500))
WORDS = (
    "request served cache miss retrying connection pool exhausted reloaded config from disk "
    "worker started shutting down slow query took longer than expected lease renewed for shard"
).split()

COLUMNS = ("host", "region", "cpu", "memory", "disk", "requests", "errors", "latency p50", "latency p99", "uptime")


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


@component
def scrolling_body(
    children: Sequence[AnyElement],
    axes: Style,
    handle: ElementHandle,
    auto_focus: bool,
    report_focus: Callable[[bool], None],
) -> Div:
    """
    The part of a pane that scrolls: with the wheel, and with the keys while it's focused.
    The pane reads how far it's scrolled through `handle`, but only the body knows whether it's focused,
    so it reports that from an effect, which is how a component tells its parent about something only it can see,
    as a React component calls an `onFocus` prop.
    """
    focus = use_focus(auto_focus=auto_focus)

    async def tell() -> None:
        report_focus(focus.is_focused)

    use_effect(tell, deps=(focus.is_focused,))

    def on_key(event: InputEvent, receiver: Receiver) -> InputResponse:
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
        handle=handle,
        on_input=first(on_key, scroll_on_wheel(), focus_receiver_on_press),
        children=children,
    )


@component
def pane(
    title: str, children: Sequence[AnyElement], axes: Style, auto_focus: bool = False, has_jump_to_end: bool = False
) -> Div:
    """
    A titled, bordered pane around a body that scrolls.
    The border, the title, and the button that jumps to the end are on the pane, outside the part that scrolls,
    so they stay put while it scrolls.
    """
    body, _ = use_state(ElementHandle)
    is_focused, set_is_focused = use_state(False)
    scroll = use_scroll(body)

    total = scroll.max_offset.y + scroll.view_height
    position = f" rows {scroll.offset.y + 1}-{scroll.offset.y + scroll.view_height} of {total} "
    if scroll.max_offset.x:
        position += f"· column {scroll.offset.x + 1} of {scroll.max_offset.x + scroll.view_width} "

    accent = border_color("sky", 400) if is_focused else border_color("slate", 600)
    return Div(
        style=fill(1) | col | border | border_lightrounded | accent,
        children=[
            Text(content=f" {title} ", style=position_absolute | inset_top(-1) | inset_left(1) | clip_to_border),
            Text(
                content=position,
                style=position_absolute | inset_bottom(-1) | inset_right(1) | clip_to_border | text_color("slate", 400),
            ),
            scrolling_body(children, axes, body, auto_focus, set_is_focused),
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
                        on_input=on_click(lambda: ScrollTo(body, y=scroll.max_offset.y)),
                    ),
                )
                if has_jump_to_end and scroll.offset.y != scroll.max_offset.y
                else ()
            ),
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
        pane("Log", log_lines(80), overflow_y_scroll | stick_to_end_y, auto_focus=True, has_jump_to_end=True),
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
