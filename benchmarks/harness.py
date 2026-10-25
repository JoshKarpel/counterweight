"""
Runs a workload headless for a fixed number of frames, timing each one.

A workload is a pure model: `step` advances it by one frame and `view` renders it.
The harness holds the model in a root component and advances it on every autopilot key press,
so each run renders exactly `frames` frames after the first, and two runs of the same workload
do the same work frame for frame, whatever the machine's speed.

A frame's time is the interval between two consecutive presses of the workload's step key, as seen by a key handler
on the root element. The autopilot sends one event or control per loop iteration, and every key that no focused
component stops bubbles to the root element's handler, whether or not its component re-ran, so the interval covers
one whole iteration (the shadow tree, layout, paint, output, effects and events) and one more for each interjection
the autopilot sent between the two presses, and the handlers of the burst a press queues, which the same iteration runs.
`frames` key presses time `frames - 1` frames.
Where that time goes is Tachyon's job (see `benchmarks.stacks`).
"""

import asyncio
import json
import statistics
from collections.abc import Callable
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from datetime import timedelta
from itertools import pairwise
from pathlib import Path
from time import perf_counter_ns
from typing import Protocol

import counterweight
from counterweight import FullScreen
from counterweight import Inline
from counterweight import app
from counterweight._context_vars import current_event_queue
from counterweight._output import Frame
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import AnyControl
from counterweight.controls import Print
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.elements import AnyElement
from counterweight.elements import Div
from counterweight.events import AnyEvent
from counterweight.events import InputEvent
from counterweight.events import KeyPressed
from counterweight.events import Receiver
from counterweight.hooks import use_controls
from counterweight.hooks import use_effect
from counterweight.hooks import use_state


class Runnable(Protocol):
    """What the harness needs of a workload, whatever its model's type."""

    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def dimensions(self) -> tuple[int, int]: ...

    @property
    def interjections(self) -> Mapping[int, tuple[AnyEvent | AnyControl, ...]]: ...

    @property
    def cycled_interjections(self) -> tuple[AnyEvent | AnyControl, ...]: ...

    @property
    def step_key(self) -> str: ...

    @property
    def viewport(self) -> FullScreen | Inline: ...

    def root(self, key_press_times: list[int]) -> Component: ...

    def live_root(self, frame_interval: timedelta) -> Component: ...


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
    interjections: Mapping[int, tuple[AnyEvent | AnyControl, ...]] = field(default_factory=dict)
    """
    Events and controls the autopilot sends before the key press that steps the model to each frame, by frame,
    such as a scroll partway through a run.
    """
    cycled_interjections: tuple[AnyEvent | AnyControl, ...] = ()
    """
    Events and controls the autopilot sends one a frame, in turn and starting over after the last,
    after that frame's `interjections` and before its key press, such as typing into a focused text area.
    """
    step_key: str = "n"
    """The key the autopilot presses to step the model, which no focused component may stop from bubbling to the root."""
    viewport: FullScreen | Inline = FullScreen()
    printed: Callable[[M], tuple[AnyElement, ...]] = lambda model: ()
    """What each frame prints, from the model it steps to, as the app's handlers would print finished output."""
    burst: Callable[[M], tuple[AnyEvent, ...]] = lambda model: ()
    """
    The events each frame's key press queues onto the app's event queue, from the model it steps to,
    which the loop handles in the same batch as that key press, before it renders,
    as it does keys typed faster than the app renders.
    """

    @component
    def root(self, key_press_times: list[int]) -> Div:
        """
        A root component that renders the model, with a key handler on the view's root that steps it
        on each press of `step_key`, queues the next model's burst, prints what it prints,
        and appends the time to `key_press_times`.
        """
        model, set_model = use_state(self.initial)
        queue = current_event_queue.get()

        def on_input(event: InputEvent, _: Receiver) -> tuple[Print, ...]:
            if not (isinstance(event, KeyPressed) and event.key == self.step_key):
                return ()
            key_press_times.append(perf_counter_ns())
            stepped = self.step(model)
            set_model(stepped)
            for queued in self.burst(stepped):
                queue.put_nowait(queued)
            return tuple(Print(content) for content in self.printed(stepped))

        return replace(self.view(model), on_input=on_input)

    @component
    def live_root(self, frame_interval: timedelta) -> Div:
        """A root component that renders the model and steps it every `frame_interval`, to watch it run by hand."""
        model, set_model = use_state(self.initial)
        send = use_controls()
        seconds = frame_interval.total_seconds()

        async def tick() -> None:
            while True:
                await asyncio.sleep(seconds)
                set_model(self.step)

        async def print_model() -> None:
            for content in self.printed(model):
                send(Print(content))

        use_effect(tick, deps=())
        use_effect(print_model, deps=(model,))

        return self.view(model)


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


def autopilot(
    frames: int,
    snapshot: Path | None,
    interjections: Mapping[int, tuple[AnyEvent | AnyControl, ...]],
    cycled_interjections: tuple[AnyEvent | AnyControl, ...],
    step_key: str,
) -> list[AnyEvent | AnyControl]:
    """
    One press of `step_key` per frame, each after that frame's `interjections` and then its `cycled_interjections`,
    then an optional text snapshot of the last frame, then quit.
    """
    end: list[AnyEvent | AnyControl] = [Quit()]
    if snapshot is not None:
        end.insert(0, Screenshot(handler=lambda frame: write_snapshot(frame, snapshot)))
    step = KeyPressed(key=step_key)

    def cycled(frame: int) -> tuple[AnyEvent | AnyControl, ...]:
        return (cycled_interjections[frame % len(cycled_interjections)],) if cycled_interjections else ()

    return [
        *(item for frame in range(frames) for item in (*interjections.get(frame, ()), *cycled(frame), step)),
        *end,
    ]


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
        autopilot=autopilot(frames, snapshot, workload.interjections, workload.cycled_interjections, workload.step_key),
        check_purity=check_purity,
        viewport=workload.viewport,
    )
    frame_ms = [(end - start) / 1e6 for start, end in pairwise(key_press_times)]
    return Timings(
        workload=workload.name,
        source=str(Path(counterweight.__file__).parent),
        dimensions=dims,
        warmup=warmup,
        frame_ms=frame_ms[warmup:],
    )
