"""
Runs a workload headless for a fixed number of frames, timing each one.

A workload is a pure model: `step` advances it by one frame and `view` renders it.
The harness holds the model in a root component and advances it on every autopilot key press,
so each run renders exactly `frames` frames after the first, and two runs of the same workload
do the same work frame for frame, whatever the machine's speed.

A frame's time is the interval between two consecutive key presses, as seen by a key handler on the
root element. The autopilot presses one key per loop iteration, and the render loop calls every element's
key handler whether or not its component re-ran, so the interval covers one whole iteration:
the shadow tree, layout, paint, output, effects and events. `frames` key presses time `frames - 1` frames.
Where that time goes is Tachyon's job (see `benchmarks.stacks`).
"""

import asyncio
import json
import statistics
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import timedelta
from itertools import pairwise
from pathlib import Path
from time import perf_counter_ns
from typing import Protocol

import counterweight
from counterweight.app import app
from counterweight.components import Component, component
from counterweight.controls import AnyControl, Quit, Screenshot
from counterweight.elements import Div
from counterweight.events import AnyEvent, KeyPressed
from counterweight.hooks import use_effect, use_state
from counterweight.output import Frame


class Runnable(Protocol):
    """What the harness needs of a workload, whatever its model's type."""

    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def dimensions(self) -> tuple[int, int]: ...

    def root(self, key_press_times: list[int]) -> Callable[[], Component]: ...

    def live_root(self, frame_interval: timedelta) -> Callable[[], Component]: ...


@dataclass(frozen=True, slots=True)
class Workload[M]:
    """
    `initial` builds the first model and `step` the next one from it; both must be deterministic,
    so seed any randomness from the model rather than from global state.
    """

    name: str
    description: str
    initial: Callable[[], M]
    step: Callable[[M], M]
    view: Callable[[M], Div]
    dimensions: tuple[int, int]

    def root(self, key_press_times: list[int]) -> Callable[[], Component]:
        """
        A root component that renders the model, with a key handler on the view's root that steps it
        and appends the time to `key_press_times`.
        """

        @component
        def benchmark_root() -> Div:
            model, set_model = use_state(self.initial)

            def on_key(_: KeyPressed) -> None:
                key_press_times.append(perf_counter_ns())
                set_model(self.step)

            return replace(self.view(model), on_key=on_key)

        return benchmark_root

    def live_root(self, frame_interval: timedelta) -> Callable[[], Component]:
        """A root component that renders the model and steps it every `frame_interval`, to watch it run by hand."""
        seconds = frame_interval.total_seconds()

        @component
        def live_benchmark_root() -> Div:
            model, set_model = use_state(self.initial)

            async def tick() -> None:
                while True:
                    await asyncio.sleep(seconds)
                    set_model(self.step)

            use_effect(tick, deps=())

            return self.view(model)

        return live_benchmark_root


@dataclass(frozen=True, slots=True)
class Timings:
    """One run's frame times, in milliseconds, without its warmup frames."""

    workload: str
    source: str
    dimensions: tuple[int, int]
    warmup: int
    frame_ms: list[float]

    @classmethod
    def load(cls, path: Path) -> Timings:
        raw = json.loads(path.read_text())
        return cls(
            workload=raw["workload"],
            source=raw["source"],
            dimensions=(raw["dimensions"][0], raw["dimensions"][1]),
            warmup=raw["warmup"],
            frame_ms=raw["frame_ms"],
        )

    def dump(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = {
            "workload": self.workload,
            "source": self.source,
            "dimensions": self.dimensions,
            "warmup": self.warmup,
            "frame_ms": self.frame_ms,
        }
        path.write_text(json.dumps(raw, indent=2) + "\n")

    @property
    def median_ms(self) -> float:
        return statistics.median(self.frame_ms)

    @property
    def mean_ms(self) -> float:
        return statistics.mean(self.frame_ms)

    @property
    def p95_ms(self) -> float:
        return sorted(self.frame_ms)[int(len(self.frame_ms) * 0.95)]

    @property
    def max_ms(self) -> float:
        return max(self.frame_ms)


def autopilot(frames: int, snapshot: Path | None) -> list[AnyEvent | AnyControl]:
    """One key press per frame, then an optional text snapshot of the last frame, then quit."""
    end: list[AnyEvent | AnyControl] = [Quit()]
    if snapshot is not None:
        end.insert(0, Screenshot(handler=lambda frame: write_snapshot(frame, snapshot)))
    return [*(KeyPressed(key="n") for _ in range(frames)), *end]


def write_snapshot(frame: Frame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frame.text(ansi=False) + "\n")


async def run(
    workload: Runnable,
    frames: int,
    warmup: int,
    dimensions: tuple[int, int] | None = None,
    snapshot: Path | None = None,
    check_purity: bool = False,
) -> Timings:
    """
    Run `workload` headless and time every frame after the first `warmup`.
    `check_purity` is for tests: it runs every component again after each frame, which the timings would include.
    """
    dims = dimensions or workload.dimensions
    key_press_times: list[int] = []
    await app(
        workload.root(key_press_times),
        headless=True,
        dimensions=dims,
        autopilot=autopilot(frames, snapshot),
        check_purity=check_purity,
    )
    frame_ms = [(end - start) / 1e6 for start, end in pairwise(key_press_times)]
    return Timings(
        workload=workload.name,
        source=str(Path(counterweight.__file__).parent),
        dimensions=dims,
        warmup=warmup,
        frame_ms=frame_ms[warmup:],
    )
