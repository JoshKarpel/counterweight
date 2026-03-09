"""Mostly-static dashboard profiling workload.

Unlike canvas.py (every cell changes every frame), the vast majority of
content here is stable between renders. A single frame counter increments
every asyncio.sleep(0) tick to drive high-frequency renders; everything
else is static text and borders.

This exercises paint_text and paint_edge lru_cache hit rates. Compare
median cycle times against canvas.py to see the cache impact.
"""

import asyncio
import time
from collections import deque

from counterweight.app import app
from counterweight.components import component
from counterweight.elements import Chunk, Div, Text
from counterweight.hooks import use_effect, use_state
from counterweight.styles.styles import CellStyle
from counterweight.styles.utilities import *

_frame_times: deque[float] = deque(maxlen=300)

_METRICS: list[tuple[str, str]] = [
    ("CPU usage", "23.4%"),
    ("Memory", "1.21 GB"),
    ("Disk read", "44.8 MB/s"),
    ("Disk write", "12.1 MB/s"),
    ("Net in", "8.33 MB/s"),
    ("Net out", "2.17 MB/s"),
    ("Requests/s", "8,421"),
    ("Error rate", "0.02%"),
    ("P50 latency", "18 ms"),
    ("P99 latency", "142 ms"),
    ("Uptime", "14d 6h 22m"),
    ("Active conns", "1,047"),
]


@component
def fps_display() -> Text:
    fps, set_fps = use_state(0.0)

    async def tick() -> None:
        while True:
            await asyncio.sleep(0.25)
            if len(_frame_times) >= 2:
                elapsed = _frame_times[-1] - _frame_times[0]
                set_fps((len(_frame_times) - 1) / elapsed if elapsed > 0 else 0.0)

    use_effect(tick, deps=())

    return Text(content=[Chunk(content=f"FPS: {fps:.1f}", style=CellStyle(foreground=green_400))])


@component
def frame_counter() -> Text:
    """Increments every asyncio.sleep(0) tick — drives high-frequency renders."""
    count, set_count = use_state(0)

    async def tick() -> None:
        while True:
            set_count(lambda n: n + 1)
            await asyncio.sleep(0)

    use_effect(tick, deps=())

    return Text(content=[Chunk(content=f"Frame: {count:,}", style=CellStyle(foreground=slate_400))])


@component
def metric_card(label: str, value: str) -> Div:
    """Static content — paint_text should hit the cache every frame."""
    return Div(
        style=border_light | border_color("slate", 700) | pad(1) | grow(1),
        children=[
            Text(content=[Chunk(content=label, style=CellStyle(foreground=slate_400))]),
            Text(content=[Chunk(content=value, style=CellStyle(foreground=slate_100, bold=True))]),
        ],
    )


@component
def header() -> Text:
    return Text(
        content=[
            Chunk(content="System", style=CellStyle(foreground=amber_400, bold=True)),
            Chunk.space(),
            Chunk(content="Dashboard", style=CellStyle(foreground=cyan_400, bold=True)),
        ],
        style=text_justify_center,
    )


@component
def root() -> Div:
    _frame_times.append(time.monotonic())
    return Div(
        style=col | pad(1) | full,
        children=[
            header(),
            Div(
                style=row | justify_children_space_between,
                children=[fps_display(), frame_counter()],
            ),
            Div(
                style=col | grow(1) | border_collapse,
                children=[
                    Div(
                        style=row | grow(1) | border_collapse,
                        children=[metric_card(label=label, value=value) for label, value in _METRICS[:6]],
                    ),
                    Div(
                        style=row | grow(1) | border_collapse,
                        children=[metric_card(label=label, value=value) for label, value in _METRICS[6:]],
                    ),
                ],
            ),
        ],
    )


if __name__ == "__main__":

    async def run() -> None:
        try:
            await asyncio.wait_for(app(root), timeout=60)
        except asyncio.TimeoutError:
            pass

    asyncio.run(run())
