"""
Inline apps: A dev loop

Several processes' log lines, printed above a status bar that stays at the bottom,
each with the time and the process's name in its color, and the line wrapping under itself.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta

from counterweight import Inline
from counterweight import app
from counterweight.components import component
from counterweight.controls import Print
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.hooks import use_clock
from counterweight.hooks import use_controls
from counterweight.hooks import use_effect
from counterweight.hooks import use_ref
from counterweight.styles.utilities import *

VIEWPORT = Inline()


# --8<-- [start:processes]


@dataclass(frozen=True, slots=True)
class Process:
    """A process that writes its `lines` one every `every` ticks, then stops."""

    name: str
    color: ColorName
    every: int
    lines: tuple[str, ...]

    def line_at(self, tick: int) -> str | None:
        """The line the process writes at `tick`, if it writes one then."""
        count, rest = divmod(tick, self.every)
        return self.lines[count - 1] if rest == 0 and 0 < count <= len(self.lines) else None

    def is_done(self, tick: int) -> bool:
        return tick >= self.every * len(self.lines)


PROCESSES = (
    Process(
        "api",
        "cyan",
        every=2,
        lines=(
            "listening on http://127.0.0.1:8000",
            "GET /api/projects 200 in 18ms",
            "GET /api/projects/42/builds?status=running 200 in 31ms",
            "POST /api/builds 201 in 112ms",
        ),
    ),
    Process(
        "worker",
        "amber",
        every=3,
        lines=(
            "connected to the queue at redis://127.0.0.1:6379",
            "job 9f3c2a picked up after waiting 120ms, running sync_repositories for 14 repositories",
            "job 9f3c2a done in 2.4s",
        ),
    ),
    Process(
        "web",
        "emerald",
        every=5,
        lines=("compiled 214 modules in 1.42s", "ready on http://127.0.0.1:5173"),
    ),
)

TICK = timedelta(milliseconds=500)


# --8<-- [end:processes]

# --8<-- [start:log-line]


def log_line(time: datetime, process: Process, line: str) -> Div:
    return Div(
        style=row,
        children=(
            Text(content=f"{time:%H:%M:%S} {process.name}", style=length(16) | text_color(process.color, 400)),
            Text(content=line, style=fill() | text_wrap_stable),
        ),
    )


# --8<-- [end:log-line]

# --8<-- [start:dev-loop]


@component
def dev_loop() -> Div:
    reading = use_clock(TICK)
    tick = reading.since_mount // TICK
    printed_through = use_ref(0)
    send = use_controls()

    async def print_new_lines() -> None:
        # The clock can move on several ticks between renders, so print every line since the last one printed.
        for earlier in range(printed_through.current + 1, tick + 1):
            for process in PROCESSES:
                if (line := process.line_at(earlier)) is not None:
                    send(Print(log_line(reading.now - (tick - earlier) * TICK, process, line)))
        printed_through.current = tick

    use_effect(print_new_lines, deps=(tick,))

    return Div(
        style=col,
        children=(
            Text(content="─" * 200, style=text_wrap_none | text_color("slate", 600)),
            Div(
                style=row | gap_width(3),
                children=tuple(
                    Text(
                        content=f"{process.name} {'done' if process.is_done(tick) else 'running'}",
                        style=text_color(process.color, 400) | (text_dim if process.is_done(tick) else text_bold),
                    )
                    for process in PROCESSES
                ),
            ),
        ),
    )


# --8<-- [end:dev-loop]


ROOTS = (dev_loop,)

# --8<-- [start:scenes]

from counterweight.controls import AdvanceClock
from counterweight.examples.scenes import Demo
from counterweight.examples.scenes import Still

DIMENSIONS = (60, 12)

STILLS = [Still("inline-dev-loop", dev_loop(), DIMENSIONS, steps=[AdvanceClock(by=TICK * 7)], viewport=VIEWPORT)]

DEMOS = [
    Demo(
        "inline-dev-loop",
        dev_loop(),
        DIMENSIONS,
        steps=[*[AdvanceClock(by=TICK)] * 12, AdvanceClock(by=timedelta(seconds=2))],
        viewport=VIEWPORT,
    )
]

# --8<-- [end:scenes]


if __name__ == "__main__":
    asyncio.run(app(dev_loop(), viewport=VIEWPORT))
