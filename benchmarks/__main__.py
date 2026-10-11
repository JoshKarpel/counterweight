"""
The benchmark CLI: `uv run python -m benchmarks --help`.

A run named `NAME` leaves its files in the output directory: `NAME.json` (frame times),
`NAME.txt` (the last frame), and, under `just profile`, `NAME.bin` (the Tachyon profile)
and `NAME.html` (its flamegraph). `report` and `compare` read runs back by name.
"""

import asyncio
import subprocess
import sys
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from rich.console import Console
from rich.table import Table
from typer import Argument, Option, Typer

from benchmarks.harness import Timings, run
from benchmarks.stacks import STARTUP, Summary, parse_collapsed, summarize
from benchmarks.workloads import WORKLOADS

OUTPUT = Option(Path("profiles"), help="Where runs are written and read.")

cli = Typer(no_args_is_help=True, add_completion=False)
console = Console(width=None if sys.stdout.isatty() else 160)


@cli.command("list")
def list_workloads() -> None:
    """List the workloads."""
    table = Table("Workload", "Dimensions", "Description")
    for workload in WORKLOADS.values():
        width, height = workload.dimensions
        table.add_row(workload.name, f"{width}x{height}", workload.description.strip())
    console.print(table)


@cli.command("run")
def run_workload(
    workload: str = Argument(help="The workload to run (see `list`)."),
    name: str | None = Option(None, help="The run's name. Defaults to the workload's."),
    frames: int = Option(500, help="Frames to render after the first."),
    warmup: int = Option(20, help="Leading frames left out of the timings."),
    width: int | None = Option(None, help="Override the workload's width."),
    height: int | None = Option(None, help="Override the workload's height."),
    output: Path = OUTPUT,
) -> None:
    """Run a workload headless, then write and print its frame times."""
    chosen = WORKLOADS[workload]
    name = name or workload
    dimensions = (width or chosen.dimensions[0], height or chosen.dimensions[1])
    timings = asyncio.run(
        run(chosen, frames=frames, warmup=warmup, dimensions=dimensions, snapshot=output / f"{name}.txt")
    )
    timings.dump(output / f"{name}.json")
    console.print(frames_table({name: timings}))


@cli.command()
def report(
    name: str = Argument(help="The run to report on."),
    top: int = Option(25, help="Functions to show in each hotspot table."),
    output: Path = OUTPUT,
) -> None:
    """Show a run's frame times and, if it was profiled, where the time went."""
    timings = Timings.load(output / f"{name}.json")
    console.print(frames_table({name: timings}))

    profile = output / f"{name}.bin"
    if not profile.exists():
        return
    summary = summarize(parse_collapsed(collapsed_stacks(profile)))
    console.print(stages_table({name: (timings, summary)}))
    for title, counter in (("Self", summary.self_samples), ("Inclusive", summary.inclusive_samples)):
        table = Table("Function", "Samples", "% of running", title=f"{title} samples while running")
        for label, samples in counter.most_common(top):
            table.add_row(label, str(samples), percent(samples, summary.running_samples))
        console.print(table)


@cli.command()
def compare(
    before: str = Argument(help="The run to compare against."),
    after: str = Argument(help="The run to compare."),
    output: Path = OUTPUT,
) -> None:
    """Compare two runs' frame times and, if both were profiled, their stages."""
    timings = {name: Timings.load(output / f"{name}.json") for name in (before, after)}
    console.print(frames_table(timings))

    profiles = {name: output / f"{name}.bin" for name in (before, after)}
    if all(profile.exists() for profile in profiles.values()):
        console.print(
            stages_table(
                {name: (timings[name], summarize(parse_collapsed(collapsed_stacks(p)))) for name, p in profiles.items()}
            )
        )


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


def frames_table(runs: dict[str, Timings]) -> Table:
    table = Table("Run", "Workload", "Size", "Frames", "Median", "Mean", "P95", "Max", "Frames/s", title="Frame times")
    for name, timings in runs.items():
        width, height = timings.dimensions
        table.add_row(
            name,
            timings.workload,
            f"{width}x{height}",
            str(len(timings.frame_ms)),
            ms(timings.median_ms),
            ms(timings.mean_ms),
            ms(timings.p95_ms),
            ms(timings.max_ms),
            f"{1000 / timings.mean_ms:.1f}",
        )
    return table


def stages_table(runs: dict[str, tuple[Timings, Summary]]) -> Table:
    """
    Each stage's share of the samples taken while the app ran, and that share of the mean frame time.
    Every frame does the same work in every run, so the per-frame times compare across runs.
    """
    stages: Counter[str] = Counter()
    for _, summary in runs.values():
        stages.update({stage: samples for stage, samples in summary.stages.items() if stage != STARTUP})

    table = Table("Stage", title="Stages: share of samples while running, and of the mean frame")
    for name in runs:
        table.add_column(f"{name} %", justify="right")
        table.add_column(f"{name} ms/frame", justify="right")
    if len(runs) == 2:
        table.add_column("Change", justify="right")

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
        table.add_row(stage, *cells)
    return table


def ms(value: float) -> str:
    return f"{value:.3f} ms"


def percent(part: float, whole: float) -> str:
    return f"{part / whole:.1%}" if whole else "—"


cli()
