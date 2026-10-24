"""
The benchmark CLI: `uv run python -m benchmarks --help`.

A workload run named `NAME` leaves its files in the output directory: `NAME.json` (frame times),
`NAME.txt` (the last frame), and, under `just profile`, `NAME.bin` (the Tachyon profile)
and `NAME.html` (its flamegraph). A `parse` run leaves `NAME.parsing.json` (time per read of input),
and a `snapshot` run `NAME.snapshots.json` (time per emulator snapshot).
`report` and `compare` read runs back by name.
"""

import subprocess
import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from without_cli import FLOAT
from without_cli import INT
from without_cli import PATH
from without_cli import STR
from without_cli import Converter
from without_cli import Streams
from without_cli import argument
from without_cli import command
from without_cli import default
from without_cli import flag
from without_cli import group
from without_cli import once
from without_cli import option
from without_cli import optional
from without_cli import run as run_cli

from benchmarks.harness import Runnable
from benchmarks.harness import Timings
from benchmarks.harness import run
from benchmarks.parsing import INPUTS
from benchmarks.parsing import ParsingTimings
from benchmarks.parsing import parsing_table
from benchmarks.parsing import time_parsing
from benchmarks.snapshots import SCENARIOS
from benchmarks.snapshots import SnapshotTimings
from benchmarks.snapshots import snapshots_table
from benchmarks.snapshots import time_snapshots
from benchmarks.stacks import STARTUP
from benchmarks.stacks import Summary
from benchmarks.stacks import parse_collapsed
from benchmarks.stacks import summarize
from benchmarks.tables import Column
from benchmarks.tables import render_table
from benchmarks.workloads import WORKLOADS
from counterweight import app


def parse_workload(name: str) -> Runnable:
    """Look up a workload by name, rejecting an unknown one as a bad command line rather than a crash."""
    try:
        return WORKLOADS[name]
    except KeyError:
        raise ValueError(name) from None


WORKLOAD = Converter("WORKLOAD", parse_workload)
OUTPUT = option(
    "--output", default(Path("profiles"), PATH), summary="Where runs are written and read (default profiles)."
)


@command("list")
async def list_workloads(streams: Streams) -> int:
    """List the workloads."""
    streams.stdout.write(
        render_table(
            (Column("Workload"), Column("Dimensions"), Column("Description")),
            (
                (workload.name, f"{workload.dimensions[0]}x{workload.dimensions[1]}", workload.description.strip())
                for workload in WORKLOADS.values()
            ),
        )
    )
    return 0


@command(
    "run",
    argument("workload", once(WORKLOAD), summary="The workload to run (see `list`)."),
    option("--name", optional(STR), summary="The run's name. Defaults to the workload's."),
    option("--frames", default(500, INT), summary="Frames to render after the first (default 500)."),
    option("--warmup", default(20, INT), summary="Leading frames left out of the timings (default 20)."),
    option("--width", optional(INT), summary="Override the workload's width."),
    option("--height", optional(INT), summary="Override the workload's height."),
    OUTPUT,
)
async def run_workload(
    streams: Streams,
    workload: Runnable,
    name: str | None,
    frames: int,
    warmup: int,
    width: int | None,
    height: int | None,
    output: Path,
) -> int:
    """Run a workload headless, then write and print its frame times."""
    name = name or workload.name
    dimensions = (width or workload.dimensions[0], height or workload.dimensions[1])
    timings = await run(workload, frames=frames, warmup=warmup, dimensions=dimensions, snapshot=output / f"{name}.txt")
    timings.dump(output / f"{name}.json")
    streams.stdout.write(frames_table({name: timings}))
    return 0


@command(
    "show",
    argument("workload", once(WORKLOAD), summary="The workload to show (see `list`)."),
    option("--fps", default(30.0, FLOAT), summary="Frames to step the workload per second (default 30)."),
    flag("--fixed-size", summary="Use the workload's own dimensions rather than the terminal's."),
)
async def show(streams: Streams, workload: Runnable, fps: float, fixed_size: bool) -> int:
    """Run a workload in this terminal, stepping it on a timer, to see what it draws. Quit with Ctrl-C."""
    await app(
        workload.live_root(timedelta(seconds=1 / fps)),
        dimensions=workload.dimensions if fixed_size else None,
    )
    return 0


@command(
    "parse",
    option("--name", default("parse", STR), summary="The run's name (default parse)."),
    option("--repeat", default(5, INT), summary="Rounds to time each input, keeping the best (default 5)."),
    OUTPUT,
)
async def parse(streams: Streams, name: str, repeat: int, output: Path) -> int:
    """Time parsing reads of terminal input, then write and print the time per read."""
    timings = time_parsing(INPUTS, repeat=repeat)
    timings.dump(output / f"{name}.parsing.json")
    streams.stdout.write(parsing_table({name: timings}))
    return 0


@command(
    "snapshot",
    option("--name", default("snapshot", STR), summary="The run's name (default snapshot)."),
    option("--repeat", default(5, INT), summary="Rounds to time each scenario, keeping the best (default 5)."),
    option("--number", default(50, INT), summary="Snapshots to time in each round (default 50)."),
    OUTPUT,
)
async def snapshot(streams: Streams, name: str, repeat: int, number: int, output: Path) -> int:
    """Time terminal emulator snapshots after pieces of a program's output, then write and print the time per snapshot."""
    timings = time_snapshots(SCENARIOS, repeat=repeat, number=number)
    timings.dump(output / f"{name}.snapshots.json")
    streams.stdout.write(snapshots_table({name: timings}))
    return 0


@command(
    "report",
    argument("name", once(STR), summary="The run to report on."),
    option("--top", default(25, INT), summary="Functions to show in each hotspot table (default 25)."),
    OUTPUT,
)
async def report(streams: Streams, name: str, top: int, output: Path) -> int:
    """Show a run's frame times and, if it was profiled, where the time went."""
    timings = Timings.load(output / f"{name}.json")
    streams.stdout.write(frames_table({name: timings}))

    profile = output / f"{name}.bin"
    if not profile.exists():
        return 0
    summary = summarize(parse_collapsed(collapsed_stacks(profile)))
    streams.stdout.write(stages_table({name: (timings, summary)}))
    for title, counter in (("Self", summary.self_samples), ("Inclusive", summary.inclusive_samples)):
        streams.stdout.write(
            render_table(
                (
                    Column("Function"),
                    Column("Samples", is_right_aligned=True),
                    Column("% of running", is_right_aligned=True),
                ),
                (
                    (label, str(samples), percent(samples, summary.running_samples))
                    for label, samples in counter.most_common(top)
                ),
                title=f"{title} samples while running",
            )
        )
    return 0


@command(
    "compare",
    argument("before", once(STR), summary="The run to compare against."),
    argument("after", once(STR), summary="The run to compare."),
    OUTPUT,
)
async def compare(streams: Streams, before: str, after: str, output: Path) -> int:
    """
    Compare two workload runs' frame times and, if both were profiled, their stages,
    two `parse` runs' times per read, or two `snapshot` runs' times per snapshot.
    """
    parsing = {name: output / f"{name}.parsing.json" for name in (before, after)}
    if all(path.exists() for path in parsing.values()):
        streams.stdout.write(parsing_table({name: ParsingTimings.load(path) for name, path in parsing.items()}))
        return 0

    snapshots = {name: output / f"{name}.snapshots.json" for name in (before, after)}
    if all(path.exists() for path in snapshots.values()):
        streams.stdout.write(snapshots_table({name: SnapshotTimings.load(path) for name, path in snapshots.items()}))
        return 0

    timings = {name: Timings.load(output / f"{name}.json") for name in (before, after)}
    streams.stdout.write(frames_table(timings))

    profiles = {name: output / f"{name}.bin" for name in (before, after)}
    if all(profile.exists() for profile in profiles.values()):
        streams.stdout.write(
            stages_table(
                {name: (timings[name], summarize(parse_collapsed(collapsed_stacks(p)))) for name, p in profiles.items()}
            )
        )
    return 0


def collapsed_stacks(profile: Path) -> str:
    """Replay a binary profile to collapsed stacks, through Tachyon's own converter."""
    with TemporaryDirectory() as directory:
        stacks = Path(directory) / "stacks.txt"
        subprocess.run(
            [sys.executable, "-m", "profiling.sampling", "replay", "--collapsed", "-o", str(stacks), str(profile)],
            check=True,
            capture_output=True,
        )
        return stacks.read_text()


def frames_table(runs: dict[str, Timings]) -> str:
    return render_table(
        (
            Column("Run"),
            Column("Workload"),
            Column("Size"),
            *(
                Column(header, is_right_aligned=True)
                for header in ("Frames", "Median", "Mean", "P95", "Max", "Frames/s")
            ),
        ),
        (
            (
                name,
                timings.workload,
                f"{timings.dimensions[0]}x{timings.dimensions[1]}",
                str(len(timings.frame_ms)),
                ms(timings.median_ms),
                ms(timings.mean_ms),
                ms(timings.p95_ms),
                ms(timings.max_ms),
                f"{1000 / timings.mean_ms:.1f}",
            )
            for name, timings in runs.items()
        ),
        title="Frame times",
    )


def stages_table(runs: dict[str, tuple[Timings, Summary]]) -> str:
    """
    Each stage's share of the samples taken while the app ran, and that share of the mean frame time.
    Every frame does the same work in every run, so the per-frame times compare across runs.
    """
    stages: Counter[str] = Counter()
    for _, summary in runs.values():
        stages.update({stage: samples for stage, samples in summary.stages.items() if stage != STARTUP})

    columns = [Column("Stage")]
    for name in runs:
        columns += [Column(f"{name} %", is_right_aligned=True), Column(f"{name} ms/frame", is_right_aligned=True)]
    if len(runs) == 2:
        columns.append(Column("Change", is_right_aligned=True))

    rows = []
    for stage, _ in stages.most_common():
        cells = []
        per_frame = []
        for timings, summary in runs.values():
            share = summary.stages[stage] / summary.running_samples
            per_frame.append(share * timings.mean_ms)
            cells += [f"{share:.1%}", ms(per_frame[-1])]
        if len(runs) == 2:
            before, after = per_frame
            cells.append(f"{(after - before) / before:+.0%}" if before else "new")
        rows.append((stage, *cells))
    return render_table(columns, rows, title="Stages: share of samples while running, and of the mean frame")


def ms(value: float) -> str:
    return f"{value:.3f} ms"


def percent(part: float, whole: float) -> str:
    return f"{part / whole:.1%}" if whole else "—"


cli = group(
    "benchmarks",
    commands=(list_workloads, run_workload, show, parse, snapshot, report, compare),
    summary="Run, profile, and compare the render-loop benchmark workloads, and time input parsing and emulator snapshots.",
)

raise SystemExit(run_cli(cli))
