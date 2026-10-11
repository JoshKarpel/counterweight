"""
Summarizes a Tachyon profile's collapsed stacks: where the render loop's samples go, by stage and by function.

The stages aren't listed here: a stage is whatever function `counterweight.app.app` called,
so a stage split out of an existing one (or renamed) shows up without changes here.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

OUTSIDE_APP = "(outside app: startup, event loop)"
APP_ITSELF = "(app itself)"


@dataclass(frozen=True, slots=True)
class Frame:
    """
    A function on a stack. Tachyon's collapsed stacks name each frame's file by its basename,
    so two functions of the same name in files of the same name are indistinguishable.
    """

    file: str
    function: str

    @property
    def label(self) -> str:
        return f"{self.file}:{self.function}" if self.file else self.function

    @property
    def is_app(self) -> bool:
        return self.file == "app.py" and self.function == "app"


@dataclass(frozen=True, slots=True)
class Stack:
    """Frames outermost first, and how many samples landed on exactly this stack."""

    frames: tuple[Frame, ...]
    samples: int


@dataclass(frozen=True, slots=True)
class Summary:
    total_samples: int
    app_samples: int
    stages: Counter[str]
    self_samples: Counter[str]
    inclusive_samples: Counter[str]


def parse_frame(raw: str) -> Frame:
    """A `file:function:line` frame, or one of Tachyon's artificial frames, such as `<GC>`, as a bare function."""
    match raw.rsplit(":", 2):
        case [file, function, _line]:
            return Frame(file=file, function=function)
        case _:
            return Frame(file="", function=raw)


def parse_collapsed(text: str) -> list[Stack]:
    """Parse Tachyon's `--collapsed` output: `tid:N;file:function:line;... samples` per line."""
    stacks = []
    for line in text.splitlines():
        if not line.strip():
            continue
        frames, samples = line.rsplit(" ", 1)
        _thread, *raw_frames = frames.split(";")
        stacks.append(Stack(frames=tuple(parse_frame(f) for f in raw_frames), samples=int(samples)))
    return stacks


def inside_app(stack: Stack) -> tuple[Frame, ...] | None:
    """The frames `app` called on this stack, outermost first, or `None` if the sample landed outside `app`."""
    for index, frame in enumerate(stack.frames):
        if frame.is_app:
            return stack.frames[index + 1 :]
    return None


def summarize(stacks: Iterable[Stack]) -> Summary:
    """Count samples by stage over every stack, and by function below `app` on the stacks inside it."""
    total = 0
    stages: Counter[str] = Counter()
    self_samples: Counter[str] = Counter()
    inclusive_samples: Counter[str] = Counter()
    for stack in stacks:
        total += stack.samples
        frames = inside_app(stack)
        if frames is None:
            stages[OUTSIDE_APP] += stack.samples
            continue
        stages[frames[0].label if frames else APP_ITSELF] += stack.samples
        self_samples[stack.frames[-1].label] += stack.samples
        for label in {frame.label for frame in frames}:
            inclusive_samples[label] += stack.samples
    return Summary(
        total_samples=total,
        app_samples=total - stages[OUTSIDE_APP],
        stages=stages,
        self_samples=self_samples,
        inclusive_samples=inclusive_samples,
    )
