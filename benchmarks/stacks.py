"""
Summarizes a Tachyon profile's collapsed stacks: where a running app's samples go, by stage and by function.

The stages aren't listed here, they come from the stack. A sample inside `counterweight.app.render_loop`
belongs to whatever function the loop called, so a stage split out of an existing one shows up
without changes here. A sample in another asyncio task (such as the devlog's sink) belongs to that task,
and one in the event loop's own machinery (waiting in `select`, scheduling) to the event loop.
Everything else ran before the event loop started or after it stopped, or in the benchmark command
outside the workload's run (reading its arguments, reporting), and is left out.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

STARTUP = "(startup and shutdown)"
LOOP_ITSELF = "(render_loop itself)"
EVENT_LOOP = "(event loop: waiting, scheduling)"


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


@dataclass(frozen=True, slots=True)
class Stack:
    """Frames outermost first, and how many samples landed on exactly this stack."""

    frames: tuple[Frame, ...]
    samples: int


@dataclass(frozen=True, slots=True)
class Attribution:
    """The stage a stack's samples belong to, and the frames below that stage's root."""

    stage: str
    frames: tuple[Frame, ...]


@dataclass(frozen=True, slots=True)
class Summary:
    total_samples: int
    running_samples: int
    stages: Counter[str]
    self_samples: Counter[str]
    inclusive_samples: Counter[str]


RENDER_LOOP = Frame(file="app.py", function="render_loop")
TASK_STEP = Frame(file="events.py", function="Handle._run")
LOOP_ITERATION = Frame(file="base_events.py", function="BaseEventLoop._run_once")
RUN_COMMAND = Frame(file="__main__.py", function="run_workload")
HARNESS_RUN = Frame(file="harness.py", function="run")


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


def below(frames: tuple[Frame, ...], root: Frame) -> tuple[Frame, ...] | None:
    """The frames `root` called, outermost first, or `None` if `root` isn't on the stack."""
    try:
        return frames[frames.index(root) + 1 :]
    except ValueError:
        return None


def attribute(stack: Stack) -> Attribution | None:
    """
    Which stage a stack belongs to: the render loop's callee, another task's outermost frame,
    or the event loop itself; `None` for samples from before the event loop started or after it stopped.
    """
    if (loop_frames := below(stack.frames, RENDER_LOOP)) is not None:
        return Attribution(stage=loop_frames[0].label if loop_frames else LOOP_ITSELF, frames=loop_frames)
    # The command's task outlives the workload's run, so it's named for the run rather than its outermost frame,
    # which is the CLI framework's own wrapper.
    if (command_frames := below(stack.frames, RUN_COMMAND)) is not None:
        is_running = command_frames[:1] == (HARNESS_RUN,)
        return Attribution(stage=f"task {HARNESS_RUN.label}", frames=command_frames) if is_running else None
    if task_frames := below(stack.frames, TASK_STEP):
        return Attribution(stage=f"task {task_frames[0].label}", frames=task_frames)
    if (iteration_frames := below(stack.frames, LOOP_ITERATION)) is not None:
        return Attribution(stage=EVENT_LOOP, frames=iteration_frames)
    return None


def summarize(stacks: Iterable[Stack]) -> Summary:
    """Count samples by stage, and by function below each stage's root, over every sample taken while the app ran."""
    total = 0
    stages: Counter[str] = Counter()
    self_samples: Counter[str] = Counter()
    inclusive_samples: Counter[str] = Counter()
    for stack in stacks:
        total += stack.samples
        attribution = attribute(stack)
        if attribution is None:
            stages[STARTUP] += stack.samples
            continue
        stages[attribution.stage] += stack.samples
        self_samples[stack.frames[-1].label] += stack.samples
        for label in {frame.label for frame in attribution.frames}:
            inclusive_samples[label] += stack.samples
    return Summary(
        total_samples=total,
        running_samples=total - stages[STARTUP],
        stages=stages,
        self_samples=self_samples,
        inclusive_samples=inclusive_samples,
    )
