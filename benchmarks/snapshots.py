"""
Times `Emulator.snapshot` on a 120x40 terminal after fixed pieces of output, outside the render loop.

Each scenario fills the screen once, then times snapshots that each follow one more piece of its output.
A piece that ends in a line break scrolls the screen, after which libghostty marks every row dirty,
so those snapshots convert the whole screen: plain text, every word colored, and wide characters.
A progress bar rewrites only its own row, and a snapshot after no output converts nothing.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import counterweight
from benchmarks.tables import Column
from benchmarks.tables import render_table
from counterweight.emulator import Emulator

COLUMNS = 120
ROWS = 40

WORDS = b"the quick brown fox jumps over the lazy dog".split()


def colored(words: list[bytes]) -> bytes:
    return b" ".join(b"\x1b[3%dm%s\x1b[0m" % (1 + index % 7, word) for index, word in enumerate(words))


@dataclass(frozen=True, slots=True)
class Scenario:
    setup: bytes
    """Fed once, before any snapshot is timed."""

    step: bytes
    """Fed before each timed snapshot."""


PLAIN_LINE = b" ".join(WORDS * 2) + b"\r\n"
COLORED_LINE = colored(WORDS * 2) + b"\r\n"
WIDE_LINE = "日本語のテキスト".encode() * 7 + b"\r\n"

SCENARIOS: Mapping[str, Scenario] = {
    "unchanged": Scenario(setup=PLAIN_LINE * ROWS, step=b""),
    "plain-line": Scenario(setup=PLAIN_LINE * ROWS, step=PLAIN_LINE),
    "colored-line": Scenario(setup=COLORED_LINE * ROWS, step=COLORED_LINE),
    "wide-line": Scenario(setup=WIDE_LINE * ROWS, step=WIDE_LINE),
    "progress-bar": Scenario(setup=PLAIN_LINE * ROWS, step=b"\r[" + b"#" * 50 + b" " * 50 + b"] 50%"),
}


@dataclass(frozen=True, slots=True)
class SnapshotTimings:
    """One run's best time per snapshot of each scenario, in microseconds, by name."""

    source: str
    snapshot_us: dict[str, float]

    @classmethod
    def load(cls, path: Path) -> SnapshotTimings:
        raw = json.loads(path.read_text())
        return cls(source=raw["source"], snapshot_us=raw["snapshot_us"])

    def dump(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"source": self.source, "snapshot_us": self.snapshot_us}, indent=2) + "\n")


def time_snapshots(scenarios: Mapping[str, Scenario], repeat: int, number: int) -> SnapshotTimings:
    """
    Time `number` snapshots of each scenario, each after one more `step` of its output,
    taking the best mean of `repeat` rounds, the one least disturbed by the rest of the machine.
    Only the snapshots are timed, not feeding the emulator.
    """
    timings = {}
    for name, scenario in scenarios.items():
        with Emulator(COLUMNS, ROWS, on_reply=lambda _: None) as emulator:
            emulator.feed(scenario.setup)
            emulator.snapshot()
            rounds = []
            for _ in range(repeat):
                elapsed = 0.0
                for _ in range(number):
                    emulator.feed(scenario.step)
                    start = perf_counter()
                    emulator.snapshot()
                    elapsed += perf_counter() - start
                rounds.append(elapsed / number)
        timings[name] = min(rounds) * 1e6
    return SnapshotTimings(source=str(Path(counterweight.__file__).parent), snapshot_us=timings)


def snapshots_table(runs: dict[str, SnapshotTimings]) -> str:
    """Each run's time per snapshot of the scenarios every run timed, with the change between them when there are two."""
    columns = [Column("Scenario")]
    columns += [Column(f"{name} µs/snapshot", is_right_aligned=True) for name in runs]
    if len(runs) == 2:
        columns.append(Column("Change", is_right_aligned=True))

    first, *rest = runs.values()
    rows = []
    for scenario in first.snapshot_us:
        if any(scenario not in timings.snapshot_us for timings in rest):
            continue
        per_snapshot = [timings.snapshot_us[scenario] for timings in runs.values()]
        cells = [scenario, *(f"{us:.1f}" for us in per_snapshot)]
        if len(runs) == 2:
            before, after = per_snapshot
            cells.append(f"{(after - before) / before:+.0%}")
        rows.append(tuple(cells))
    return render_table(
        columns, rows, title=f"Emulator snapshots of a {COLUMNS}x{ROWS} terminal: best time per snapshot"
    )
