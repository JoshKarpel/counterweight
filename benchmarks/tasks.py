"""
Parallel downloads drawn inline, as `uv`, `docker pull` or `cargo` draws them: a row per download in progress,
each with its name, a bar, and how much of it has arrived, above a line counting the downloads done,
and a line printed above the region for each download as it finishes.

Every bar moves every frame, and how many download at once rises and falls,
so the region is small, changes in every row, and grows or shrinks a row now and then.
So this measures the fixed cost of an inline frame where the region is cheap to draw:
the relative cursor moves, the region's changing height, short prints, and feeding all of it to the emulator.
"""

import random
from dataclasses import dataclass

from benchmarks.agent import SPINNER
from benchmarks.harness import Workload
from counterweight import Inline
from counterweight.elements import AnyElement
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.styles.utilities import amber_400
from counterweight.styles.utilities import col
from counterweight.styles.utilities import cyan_400
from counterweight.styles.utilities import emerald_400
from counterweight.styles.utilities import gap_width
from counterweight.styles.utilities import length
from counterweight.styles.utilities import row
from counterweight.styles.utilities import slate_500
from counterweight.styles.utilities import slate_700
from counterweight.styles.utilities import text_bold
from counterweight.styles.utilities import text_color
from counterweight.styles.utilities import text_wrap_none

NAMES = tuple(
    f"{prefix}{suffix}"
    for prefix in ("py", "lib", "async", "fast", "web", "data", "type", "test", "cloud", "rich")
    for suffix in ("-core", "kit", "-utils", "parse", "io", "-client", "lang", "frame", "-schema", "stream")
)
BAR_WIDTH = 40
NAME_WIDTH = 18
# How many download at once, by the frame, rising and falling over a cycle of frames.
CONCURRENCY = (3, 4, 5, 6, 7, 8, 8, 7, 6, 5, 4, 3)
FRAMES_PER_CONCURRENCY = 25


@dataclass(frozen=True, slots=True)
class Download:
    name: str
    size: int
    """In kilobytes."""
    arrived: int
    started: int
    """The tick it started on."""


@dataclass(frozen=True, slots=True)
class Model:
    tick: int
    downloads: tuple[Download, ...]
    finished: tuple[Download, ...]
    """The downloads the step to this model finished, which it prints."""
    done: int
    started: int


def initial() -> Model:
    return Model(tick=0, downloads=(), finished=(), done=0, started=0)


def step(model: Model) -> Model:
    rng = random.Random(model.tick)
    advanced = [
        Download(
            download.name,
            download.size,
            min(download.size, download.arrived + rng.randint(download.size // 80, download.size // 25)),
            download.started,
        )
        for download in model.downloads
    ]
    finished = tuple(download for download in advanced if download.arrived == download.size)
    downloads = [download for download in advanced if download.arrived < download.size]
    started = model.started
    while len(downloads) < CONCURRENCY[model.tick // FRAMES_PER_CONCURRENCY % len(CONCURRENCY)]:
        downloads.append(Download(NAMES[started % len(NAMES)], rng.randint(200, 90_000), 0, model.tick))
        started += 1
    return Model(
        tick=model.tick + 1,
        downloads=tuple(downloads),
        finished=finished,
        done=model.done + len(finished),
        started=started,
    )


def megabytes(kilobytes: int) -> str:
    return f"{kilobytes / 1000:.1f} MB"


def printed(model: Model) -> tuple[AnyElement, ...]:
    return tuple(
        Div(
            style=row | gap_width(1),
            children=(
                Text(content="✓", style=text_color(emerald_400)),
                Text(content=download.name, style=text_bold),
                Text(
                    content=f"{megabytes(download.size)} in {(model.tick - download.started) / 30:.1f}s",
                    style=text_color(slate_500),
                ),
            ),
        )
        for download in model.finished
    )


def progress(download: Download) -> Div:
    filled = BAR_WIDTH * download.arrived // download.size
    return Div(
        style=row | gap_width(1),
        children=(
            Text(content=download.name, style=length(NAME_WIDTH) | text_color(cyan_400)),
            Div(
                style=row,
                children=(
                    Text(content="━" * filled, style=text_color(amber_400) | text_wrap_none),
                    Text(content="━" * (BAR_WIDTH - filled), style=text_color(slate_700) | text_wrap_none),
                ),
            ),
            Text(
                content=f"{megabytes(download.arrived):>8} / {megabytes(download.size)}",
                style=text_color(slate_500) | text_wrap_none,
            ),
        ),
    )


def view(model: Model) -> Div:
    return Div(
        style=col,
        children=(
            *(progress(download) for download in model.downloads),
            Text(
                content=f"{SPINNER[model.tick % len(SPINNER)]} Downloaded {model.done} packages, {len(model.downloads)} in progress",
                style=text_color(slate_500),
            ),
        ),
    )


WORKLOAD = Workload(
    name="tasks",
    description=__doc__ or "",
    initial=initial,
    step=step,
    view=view,
    dimensions=(100, 30),
    viewport=Inline(),
    printed=printed,
)
