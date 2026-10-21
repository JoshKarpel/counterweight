"""
Times `parse_input` on fixed reads of terminal input, outside the render loop.

The inputs cover the cases that matter for parsing: a single key press (the common case, one per read),
a read full of mouse motion reports (the most input any-event tracking produces at once),
full reads of text pasted without bracketed paste, ASCII and not, which arrive as key presses,
and a full read of one bracketed paste. Each is a whole read, so nothing is held over to the next one.
"""

import json
import timeit
from collections.abc import Mapping
from dataclasses import dataclass
from functools import partial
from pathlib import Path

import counterweight
from benchmarks.tables import Column
from benchmarks.tables import render_table
from counterweight._input_parsing import parse_input

# How many bytes each timed read holds. A terminal hands over at most a few kilobytes per read,
# whatever counterweight._input.READ_SIZE asks for; this stays at 1 KB so timings compare across runs.
READ_SIZE = 2**10


def fill_read(pieces: list[bytes]) -> bytes:
    """As many whole `pieces` as fit in one read, so the read doesn't end partway through one."""
    read = b""
    for piece in pieces:
        if len(read) + len(piece) > READ_SIZE:
            break
        read += piece
    return read


INPUTS: Mapping[str, bytes] = {
    "key": b"a",
    "arrow-key": b"\x1b[A",
    "mouse-move": b"\x1b[<35;12;4M",
    "mouse-flood": fill_read([b"\x1b[<35;%d;%dM" % (column, 1 + column // 3) for column in range(1, 200)]),
    "ascii-paste": fill_read(
        [f"{word} ".encode() for word in ["the", "quick", "brown", "fox", "jumps", "over", "the", "lazy", "dog"]] * 30
    ),
    "non-ascii-paste": fill_read([character.encode() for character in "naïve café 日本語 👩‍💻 " * 100]),
    "bracketed-paste": b"\x1b[200~" + b"the quick brown fox jumps over the lazy dog\r" * 22 + b"\x1b[201~",
}


@dataclass(frozen=True, slots=True)
class InputTiming:
    size: int
    """The input's length in bytes."""

    read_us: float
    """The best time to parse it, in microseconds."""


@dataclass(frozen=True, slots=True)
class ParsingTimings:
    """One run's timing of each input, by name."""

    source: str
    inputs: dict[str, InputTiming]

    @classmethod
    def load(cls, path: Path) -> ParsingTimings:
        raw = json.loads(path.read_text())
        return cls(
            source=raw["source"],
            inputs={
                name: InputTiming(size=timing["size"], read_us=timing["read_us"])
                for name, timing in raw["inputs"].items()
            },
        )

    def dump(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = {
            "source": self.source,
            "inputs": {name: {"size": timing.size, "read_us": timing.read_us} for name, timing in self.inputs.items()},
        }
        path.write_text(json.dumps(raw, indent=2) + "\n")


def time_parsing(inputs: Mapping[str, bytes], repeat: int) -> ParsingTimings:
    """
    Time parsing each input as one read, taking the best of `repeat` rounds,
    each long enough (by `timeit`'s autorange) to measure reliably.
    The best round is the one least disturbed by the rest of the machine.
    """
    timings = {}
    for name, read in inputs.items():
        timer = timeit.Timer(partial(parse_input, read, is_final=False))
        number, _ = timer.autorange()
        best = min(timer.repeat(repeat=repeat, number=number)) / number
        timings[name] = InputTiming(size=len(read), read_us=best * 1e6)
    return ParsingTimings(source=str(Path(counterweight.__file__).parent), inputs=timings)


def parsing_table(runs: dict[str, ParsingTimings]) -> str:
    """
    Each run's time per read of the inputs every run timed, with the change between them when there are two runs.
    Sizes are the first run's.
    """
    columns = [Column("Input"), Column("Bytes", is_right_aligned=True)]
    columns += [Column(f"{name} µs/read", is_right_aligned=True) for name in runs]
    if len(runs) == 2:
        columns.append(Column("Change", is_right_aligned=True))

    first, *rest = runs.values()
    rows = []
    for input_name, timing in first.inputs.items():
        if any(input_name not in timings.inputs for timings in rest):
            continue
        per_read = [timings.inputs[input_name].read_us for timings in runs.values()]
        cells = [input_name, str(timing.size), *(f"{us:.2f}" for us in per_read)]
        if len(runs) == 2:
            before, after = per_read
            cells.append(f"{(after - before) / before:+.0%}")
        rows.append(tuple(cells))
    return render_table(columns, rows, title="Input parsing: best time per read")
