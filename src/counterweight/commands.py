"""
One-shot commands: running a program that's expected to exit, though not necessarily to succeed,
and showing everything it printed, colors and all, as a terminal would have shown it.

[`use_command`][counterweight.commands.use_command] runs one when its `run` is called,
on a pseudo-terminal, feeding what it prints to an emulator, which snapshots at most once a frame
into a [`CommandRun`][counterweight.commands.CommandRun] value
whose output is a [`Transcript`][counterweight.painters.terminal.Transcript] painter.
"""

from __future__ import annotations

import signal
from asyncio import Event
from asyncio import TimerHandle
from asyncio import get_running_loop
from collections.abc import Callable
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import assert_never

from counterweight.components import component
from counterweight.elements import Canvas
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.emulator import SNAPSHOT_INTERVAL
from counterweight.emulator import Emulator
from counterweight.focus import ElementHandle
from counterweight.focus import FocusHandle
from counterweight.hooks import Ref
from counterweight.hooks import use_effect
from counterweight.hooks import use_memo
from counterweight.hooks import use_ref
from counterweight.hooks import use_state
from counterweight.painters.terminal import MAX_LINES
from counterweight.painters.terminal import Transcript
from counterweight.programs import Exited
from counterweight.programs import FailedToStart
from counterweight.programs import TimedOut
from counterweight.pseudoterminal import HANGUP_GRACE
from counterweight.pseudoterminal import PtyConnection
from counterweight.pseudoterminal import Running
from counterweight.pseudoterminal import Starting
from counterweight.pseudoterminal import run_pty
from counterweight.pseudoterminal import tear_down_in_background
from counterweight.styles import Style
from counterweight.styles.utilities import col
from counterweight.styles.utilities import default
from counterweight.styles.utilities import grow
from counterweight.styles.utilities import text_color
from counterweight.widgets import ScrollAreaStyles
from counterweight.widgets import scroll_area

COMMAND_ENVIRONMENT = frozendict({"PAGER": "cat", "GIT_PAGER": "cat"})
"""
What every one-shot command's environment sets, under the caller's `env`:
pagers that print rather than wait for keys that never come.
"""


@dataclass(frozen=True, slots=True)
class Cancelled:
    """The run was cancelled, by [`Command.cancel`][counterweight.commands.Command.cancel], before the program exited."""


type Outcome = Starting | Running | Exited | FailedToStart | Cancelled | TimedOut
"""
How a run is going, or how it ended.
A program that exits with a failing status has exited as much as one that succeeds: check its `status`.
"""


@dataclass(frozen=True, slots=True)
class CommandRun:
    """One run of a program, which outlives the program, so it can be kept, shown again, or shown beside the next."""

    argv: tuple[str, ...]
    output: Transcript
    """Everything the program printed, so far while it runs."""
    outcome: Outcome


@dataclass(frozen=True, slots=True)
class Command:
    """What [`use_command`][counterweight.commands.use_command] returns."""

    run: Callable[[Sequence[str]], None]
    """
    Starts running `argv`, cancelling the run in progress, if there is one.
    It's the same function on every render.
    """

    cancel: Callable[[], None]
    """
    Cancels the run in progress, hanging its program up, and makes its outcome `Cancelled`.
    It does nothing if no run is in progress, and is the same function on every render.
    """

    latest: CommandRun | None
    """The latest run, while it runs and after it ends, or `None` before the first."""


@dataclass(frozen=True, slots=True, eq=False)
class Request:
    """A call to `run`, compared by identity, so running the same `argv` again starts another run."""

    argv: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Runs:
    """The request a `use_command` is running, if any, and its latest run."""

    request: Request | None = None
    latest: CommandRun | None = None

    def updated(self, request: Request, latest: CommandRun) -> Runs:
        """These runs with `latest` as the run of `request`, unless another request or a cancel replaced it."""
        return replace(self, latest=latest) if self.request is request else self

    def cancelled(self) -> Runs:
        """These runs with none in progress, and the latest `Cancelled` if it hadn't ended."""
        latest = self.latest
        if latest is not None and isinstance(latest.outcome, Starting | Running):
            latest = replace(latest, outcome=Cancelled())
        return replace(self, request=None, latest=latest)


def use_command(
    columns: int,
    rows: int = 24,
    env: Mapping[str, str] = frozendict(),
    clear_env: bool = False,
    cwd: Path | None = None,
    timeout: timedelta | None = None,
    max_lines: int = MAX_LINES,
    hangup_grace: timedelta = HANGUP_GRACE,
) -> Command:
    """
    Runs a program, when its `run` is called, on a pseudo-terminal `columns` by `rows`,
    with its standard input on `/dev/null`, so a program that reads input gets end of file rather than waiting,
    and returns the latest run, with everything it printed so far, which updates at most once a frame while it runs.
    Starting another run, cancelling, and unmounting the component each hang the program up
    (see [`run_pty`][counterweight.pseudoterminal.run_pty]) in the background,
    so a program slow to exit doesn't hold up the app's rendering, and an app that stops waits for it.

    Parameters:
        columns: How wide the program's terminal is, which it formats its output for,
            such as the content width that [`use_rects`][counterweight.hooks.use_rects] reports for the box
            the output is shown in.
            It's read when the run starts, and a run waits to start until it's positive,
            since `use_rects` reports zero on the first render.
            A later change doesn't rewrap a run's output: running it again at the new width does.

        rows: How tall the program's terminal is, which a program that draws a live display sizes it to.
            It doesn't bound the output, which grows with what the program prints.

        env: Variables to set in the program's environment.
            It gets `PAGER=cat` and `GIT_PAGER=cat`, so a command such as `git log` prints rather than paging,
            over the environment `run_pty` gives it, and `env` over those.

        clear_env: Leave out the app's environment (see [`run_pty`][counterweight.pseudoterminal.run_pty]).

        cwd: The directory to run the program in, or `None` for the app's working directory.
            It's read when a run starts, as `columns` is.

        timeout: How long the program may run before it's hung up and its outcome is `TimedOut`, or `None` for no limit
            (see [`run_pty`][counterweight.pseudoterminal.run_pty]).

        max_lines: How many lines of output a run keeps, dropping the oldest, at most `MAX_SCROLLBACK`.

        hangup_grace: How long the program has to exit after each signal that hangs it up
            (see [`run_pty`][counterweight.pseudoterminal.run_pty]).
    """
    width: Ref[int] = use_ref(0)
    is_sized: Ref[Event] = use_ref(Event)
    runs, set_runs = use_state(Runs())

    async def apply_width() -> None:
        if columns <= 0:
            return
        width.current = columns
        is_sized.current.set()

    # Before running the program, so that a run requested on mount starts at this render's width.
    use_effect(apply_width, deps=(columns,))

    request = runs.request

    async def run_request() -> None:
        if request is None:
            return

        await is_sized.current.wait()
        await tear_down_in_background(run_to_end(request, width.current))

    async def run_to_end(request: Request, run_columns: int) -> None:
        transcript = Transcript(columns=run_columns, max_lines=max_lines)
        # Set before the program's first output, and so before any reply to it.
        connection: PtyConnection
        last_snapshot: float
        loop = get_running_loop()
        snapshot_due: TimerHandle | None = None

        def reply(data: bytes) -> None:
            connection.write(data)

        def report(outcome: Running | Exited | FailedToStart | TimedOut) -> None:
            nonlocal transcript, last_snapshot, snapshot_due
            snapshot_due = None
            last_snapshot = loop.time()
            transcript = transcript.followed_by(emulator.scrolled_off(), emulator.snapshot())
            run = CommandRun(argv=request.argv, output=transcript, outcome=outcome)
            set_runs(lambda current: current.updated(request, run))

        def start(c: PtyConnection) -> None:
            nonlocal connection
            connection = c
            report(Running())

        def output(data: bytes) -> None:
            nonlocal snapshot_due
            emulator.feed(data)
            if snapshot_due is None:
                snapshot_due = loop.call_at(last_snapshot + SNAPSHOT_INTERVAL.total_seconds(), report, Running())

        with Emulator(run_columns, rows, on_reply=reply, scrollback=max_lines) as emulator:
            try:
                outcome = await run_pty(
                    request.argv,
                    run_columns,
                    rows,
                    on_output=output,
                    on_start=start,
                    env={**COMMAND_ENVIRONMENT, **env},
                    clear_env=clear_env,
                    cwd=cwd,
                    stdin="devnull",
                    hangup_grace=hangup_grace,
                    timeout=timeout,
                )
            finally:
                if snapshot_due is not None:
                    snapshot_due.cancel()
            report(outcome)

    use_effect(run_request, deps=(request,))

    def run(argv: Sequence[str]) -> None:
        requested = Request(argv=tuple(argv))
        starting = CommandRun(argv=requested.argv, output=Transcript(columns=0), outcome=Starting())
        set_runs(Runs(request=requested, latest=starting))

    def cancel() -> None:
        set_runs(Runs.cancelled)

    return Command(
        run=use_memo(lambda: run, ()),
        cancel=use_memo(lambda: cancel, ()),
        latest=runs.latest,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class CommandOutputStyles:
    """
    How [`command_output`][counterweight.commands.command_output] draws the box around a run's output,
    and the line beneath it that says how the run is going, or how it ended.
    """

    area: ScrollAreaStyles = ScrollAreaStyles()
    """The box around the output."""
    in_progress: Style = text_color("slate", 400)
    """The line beneath, while the program starts and runs."""
    succeeded: Style = text_color("green", 400)
    """The line beneath, once the program exits with status 0."""
    failed: Style = text_color("red", 400)
    """The line beneath, once the program exits with any other status, fails to start, or times out."""
    cancelled: Style = text_color("amber", 400)
    """The line beneath, once the run is cancelled."""

    def outcome_style(self, outcome: Outcome) -> Style:
        """The style of the line beneath for `outcome`."""
        match outcome:
            case Starting() | Running():
                return self.in_progress
            case Exited(status=0):
                return self.succeeded
            case Exited() | FailedToStart() | TimedOut():
                return self.failed
            case Cancelled():
                return self.cancelled
            case _ as unreachable:
                assert_never(unreachable)


@component
def command_output(
    run: CommandRun | None,
    viewport: ElementHandle,
    style: Style = default,
    styles: CommandOutputStyles = CommandOutputStyles(),
    auto_focus: bool = False,
    handle: FocusHandle | None = None,
    is_focusable: bool = True,
    in_focus_order: bool = True,
) -> Div:
    """
    A run from [`use_command`][counterweight.commands.use_command], its output in a
    [`scroll_area`][counterweight.widgets.scroll_area] that sticks to its end, so it follows the output while
    the program runs, with a line beneath that says how the run is going, or how it ended.
    The scroll area takes `viewport` and the focus parameters, `handle` being a focus handle.

    The program formats its output for the scroll area's content width, which the component that calls `use_command`
    reads with `use_rects(viewport)`, so the box has to take its width from its parent (by stretching, `fill`,
    or a styled width), never from its content, whose width is the run's: a box sized by its content stays zero wide,
    and the run never starts.

    Parameters:
        run: The run to show, such as `Command.latest`, or `None` for an empty box.

        style: Merged over the outer box, which holds the scroll area and the line beneath it,
            as for a size (`fill(1)`, `height(12)`): the scroll area takes the height left over,
            and scrolls the output that doesn't fit.

        styles: How the box and the line beneath it are drawn.
    """
    area = scroll_area(
        children=() if run is None else (Canvas(painter=run.output),),
        stick_to_end=True,
        style=grow(1),
        styles=styles.area,
        viewport=viewport,
        auto_focus=auto_focus,
        handle=handle,
        is_focusable=is_focusable,
        in_focus_order=in_focus_order,
    )
    if run is None:
        return Div(style=col | style, children=(area,))
    return Div(
        style=col | style,
        children=(area, Text(content=outcome_text(run.outcome), style=styles.outcome_style(run.outcome))),
    )


def outcome_text(outcome: Outcome) -> str:
    """What the line beneath a run's output says about `outcome`."""
    match outcome:
        case Starting():
            return "starting"
        case Running():
            return "running"
        case Exited(status=status) if status < 0:
            return f"ended by {signal_name(-status)}"
        case Exited(status=status):
            return f"exited {status}"
        case FailedToStart(reason=reason):
            return f"failed to start: {reason}"
        case Cancelled():
            return "cancelled"
        case TimedOut():
            return "timed out"
        case _ as unreachable:
            assert_never(unreachable)


def signal_name(number: int) -> str:
    """The name of the signal `number`, such as `SIGTERM`, or its number for one Python doesn't name."""
    try:
        return signal.Signals(number).name
    except ValueError:
        return f"signal {number}"


__all__ = [
    "COMMAND_ENVIRONMENT",
    "Cancelled",
    "Command",
    "CommandOutputStyles",
    "CommandRun",
    "Exited",
    "FailedToStart",
    "Outcome",
    "Running",
    "Starting",
    "TimedOut",
    "command_output",
    "use_command",
]
