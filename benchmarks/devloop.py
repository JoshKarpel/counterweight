"""
An inline dev loop in synth's shape: each frame, several processes' log lines are printed above a status bar,
each with a colored, fixed-width prefix and a body that wraps with a hanging indent.

The region is small and changes a little each frame, so this measures what printing costs:
rendering each line once, writing it above the region, and redrawing the region below it,
on top of feeding all of that to the emulator an inline app keeps of its terminal.
"""

from dataclasses import dataclass

from benchmarks.harness import Workload
from counterweight import Inline
from counterweight.elements import AnyElement
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles._styles import Color
from counterweight.styles.utilities import amber_400
from counterweight.styles.utilities import col
from counterweight.styles.utilities import cyan_400
from counterweight.styles.utilities import emerald_400
from counterweight.styles.utilities import fill
from counterweight.styles.utilities import fuchsia_400
from counterweight.styles.utilities import gap_width
from counterweight.styles.utilities import length
from counterweight.styles.utilities import row
from counterweight.styles.utilities import slate_500
from counterweight.styles.utilities import text_color
from counterweight.styles.utilities import text_wrap_stable

PROCESSES: tuple[tuple[str, Color], ...] = (
    ("api", cyan_400),
    ("worker", amber_400),
    ("web", emerald_400),
    ("docs", fuchsia_400),
)
LINES_PER_FRAME = 3
PREFIX_WIDTH = 16

MESSAGES = (
    "GET /api/v1/projects/42/builds?status=running 200 in 18ms",
    "compiled 214 modules in 1.42s, watching for changes",
    "job 9f3c2a picked up from queue default after waiting 120ms, running handler sync_repositories",
    "warning: deprecated option --legacy-peer-deps will be removed in the next major release",
    "ready",
)


@dataclass(frozen=True, slots=True)
class Model:
    tick: int


def initial() -> Model:
    return Model(tick=0)


def step(model: Model) -> Model:
    return Model(tick=model.tick + 1)


def log_line(tick: int, index: int) -> Div:
    """One line a process printed: its time and name in its color, then the line, wrapping under itself."""
    name, color = PROCESSES[(tick + index) % len(PROCESSES)]
    seconds = tick * LINES_PER_FRAME + index
    return Div(
        style=row,
        children=(
            Text(
                content=f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02} {name}",
                style=text_color(color) | length(PREFIX_WIDTH),
            ),
            Text(content=MESSAGES[seconds % len(MESSAGES)], style=fill() | text_wrap_stable),
        ),
    )


def printed(model: Model) -> tuple[AnyElement, ...]:
    return tuple(log_line(model.tick, index) for index in range(LINES_PER_FRAME))


def view(model: Model) -> Div:
    return Div(
        style=col,
        children=(
            Text(content="─" * 120, style=text_color(slate_500)),
            Div(
                style=row | gap_width(2),
                children=tuple(
                    Text(
                        content=f"{name} {'running' if (model.tick + index) % 5 else 'restarting'}",
                        style=text_color(color),
                    )
                    for index, (name, color) in enumerate(PROCESSES)
                ),
            ),
        ),
    )


WORKLOAD = Workload(
    name="devloop",
    description="An inline status bar under processes' log lines, three printed above it each frame.",
    initial=initial,
    step=step,
    view=view,
    dimensions=(120, 40),
    viewport=Inline(),
    printed=printed,
)
