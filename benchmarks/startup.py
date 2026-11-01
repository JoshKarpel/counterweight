"""
Times how long a fresh process takes to show a workload's first frame, as a short-lived app's user waits for it.

Each launch runs `python -c` on one workload, headless, through its first frame, then quits.
`perf_counter_ns` reads a clock the whole machine shares on Linux and macOS,
so the parent's readings around the launch and the child's inside it fall on one timeline:

- **interpreter**: from spawning the process to its first statement, Python's own startup.
- **imports**: counterweight, the benchmark harness, and the one module that defines the workload.
- **first frame**: from calling `app` to its first frame, which for an `Inline` app includes making its emulator.
- **exit**: from the first frame to the process ending, stopping the app and the interpreter.
"""

import asyncio
import importlib
import json
import statistics
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter_ns

from more_itertools import one

import counterweight
from benchmarks.harness import Runnable
from benchmarks.tables import Column
from benchmarks.tables import render_table
from counterweight import app
from counterweight.controls import Quit
from counterweight.controls import Screenshot

# The child reads the clock before importing anything, so its imports are timed.
CHILD = """
from time import perf_counter_ns
started = perf_counter_ns()
import sys
from benchmarks.startup import show_first_frame
show_first_frame(started, *sys.argv[1:])
"""

STAGES = ("interpreter", "imports", "first frame", "exit", "to first frame")


@dataclass(frozen=True, slots=True)
class Launch:
    """One process's stages, in milliseconds."""

    interpreter_ms: float
    imports_ms: float
    first_frame_ms: float
    exit_ms: float

    @property
    def to_first_frame_ms(self) -> float:
        return self.interpreter_ms + self.imports_ms + self.first_frame_ms

    def stage_ms(self, stage: str) -> float:
        return {
            "interpreter": self.interpreter_ms,
            "imports": self.imports_ms,
            "first frame": self.first_frame_ms,
            "exit": self.exit_ms,
            "to first frame": self.to_first_frame_ms,
        }[stage]


@dataclass(frozen=True, slots=True)
class StartupTimings:
    """One run's launches of each workload, by name."""

    source: str
    launches: dict[str, list[Launch]]

    @classmethod
    def load(cls, path: Path) -> StartupTimings:
        raw = json.loads(path.read_text())
        return cls(
            source=raw["source"],
            launches={
                name: [
                    Launch(
                        interpreter_ms=launch["interpreter_ms"],
                        imports_ms=launch["imports_ms"],
                        first_frame_ms=launch["first_frame_ms"],
                        exit_ms=launch["exit_ms"],
                    )
                    for launch in launches
                ]
                for name, launches in raw["launches"].items()
            },
        )

    def dump(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = {
            "source": self.source,
            "launches": {
                name: [
                    {
                        "interpreter_ms": launch.interpreter_ms,
                        "imports_ms": launch.imports_ms,
                        "first_frame_ms": launch.first_frame_ms,
                        "exit_ms": launch.exit_ms,
                    }
                    for launch in launches
                ]
                for name, launches in self.launches.items()
            },
        }
        path.write_text(json.dumps(raw, indent=2) + "\n")

    def median_ms(self, workload: str, stage: str) -> float:
        return statistics.median(launch.stage_ms(stage) for launch in self.launches[workload])


def show_first_frame(started: int, module: str, attribute: str, result: str) -> None:
    """The child's side of a launch: run the workload through its first frame, and write when each stage ended."""
    workload: Runnable = getattr(importlib.import_module(module), attribute)
    imported = perf_counter_ns()
    painted: list[int] = []
    asyncio.run(
        app(
            workload.root([]),
            headless=True,
            dimensions=workload.dimensions,
            viewport=workload.viewport,
            autopilot=[Screenshot(handler=lambda _: painted.append(perf_counter_ns())), Quit()],
        )
    )
    Path(result).write_text(json.dumps({"started": started, "imported": imported, "painted": painted[0]}))


def defined_at(workload: Runnable) -> tuple[str, str]:
    """
    The module and attribute that define `workload`, so a launch imports only that module,
    as an app imports only what it uses, rather than every workload through `benchmarks.workloads`.
    """
    return one(
        (name, attribute)
        for name, module in tuple(sys.modules.items())
        if name.startswith("benchmarks.") and name != "benchmarks.workloads"
        for attribute, value in vars(module).items()
        if value is workload
    )


def launch(workload: Runnable) -> Launch:
    """Launch `workload` once in a fresh process, through its first frame."""
    module, attribute = defined_at(workload)
    with TemporaryDirectory() as directory:
        result = Path(directory) / "result.json"
        spawned = perf_counter_ns()
        subprocess.run([sys.executable, "-c", CHILD, module, attribute, str(result)], check=True)
        exited = perf_counter_ns()
        child = json.loads(result.read_text())
    return Launch(
        interpreter_ms=(child["started"] - spawned) / 1e6,
        imports_ms=(child["imported"] - child["started"]) / 1e6,
        first_frame_ms=(child["painted"] - child["imported"]) / 1e6,
        exit_ms=(exited - child["painted"]) / 1e6,
    )


def time_startup(workloads: Sequence[Runnable], repeat: int) -> StartupTimings:
    """Launch each workload `repeat` times, interleaving them so a slow moment on the machine doesn't land on one."""
    launches: dict[str, list[Launch]] = {workload.name: [] for workload in workloads}
    for _ in range(repeat):
        for workload in workloads:
            launches[workload.name].append(launch(workload))
    return StartupTimings(source=str(Path(counterweight.__file__).parent), launches=launches)


def startup_table(runs: dict[str, StartupTimings]) -> str:
    """
    Each run's median time in each stage of launching the workloads every run launched,
    with the change between them when there are two.
    """
    columns = [Column("Workload"), Column("Stage")]
    columns += [Column(f"{name} ms", is_right_aligned=True) for name in runs]
    if len(runs) == 2:
        columns.append(Column("Change", is_right_aligned=True))

    first, *rest = runs.values()
    rows = []
    for workload in first.launches:
        if any(workload not in timings.launches for timings in rest):
            continue
        for stage in STAGES:
            medians = [timings.median_ms(workload, stage) for timings in runs.values()]
            cells = [workload, stage, *(f"{ms:.1f}" for ms in medians)]
            if len(runs) == 2:
                before, after = medians
                cells.append(f"{(after - before) / before:+.0%}")
            rows.append(tuple(cells))
    return render_table(columns, rows, title="Startup: median time in each stage of a fresh process's first frame")
