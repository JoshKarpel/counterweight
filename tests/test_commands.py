from __future__ import annotations

import io
import os
import signal
import sys
from asyncio import CancelledError
from asyncio import Event
from asyncio import create_task
from asyncio import wait_for
from collections.abc import Callable
from collections.abc import Mapping
from contextlib import suppress
from datetime import timedelta
from pathlib import Path

import pytest
from more_itertools import unique_justseen

from counterweight.app import app
from counterweight.commands import Cancelled
from counterweight.commands import Command
from counterweight.commands import CommandOutputStyles
from counterweight.commands import CommandRun
from counterweight.commands import Exited
from counterweight.commands import FailedToStart
from counterweight.commands import Outcome
from counterweight.commands import Request
from counterweight.commands import Running
from counterweight.commands import Runs
from counterweight.commands import Starting
from counterweight.commands import TimedOut
from counterweight.commands import command_output
from counterweight.commands import outcome_text
from counterweight.commands import use_command
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import Quit
from counterweight.controls import Screenshot
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.focus import ElementHandle
from counterweight.hooks import use_effect
from counterweight.hooks import use_rects
from counterweight.hooks import use_state
from counterweight.output import Frame
from counterweight.painters.terminal import MAX_LINES
from counterweight.painters.terminal import Transcript
from counterweight.pseudoterminal import has_members
from counterweight.styles import Style
from counterweight.styles.styles import Color
from counterweight.styles.utilities import col
from counterweight.styles.utilities import fill
from counterweight.styles.utilities import full
from counterweight.styles.utilities import size
from counterweight.styles.utilities import text_color
from tests.rendering import TIMEOUT
from tests.rendering import Mounted
from tests.rendering import mounted
from tests.terminal import Terminal


@component
def runner(
    columns: int,
    commands: list[Command],
    rows: int = 24,
    env: Mapping[str, str] = frozendict(),
    clear_env: bool = False,
    timeout: timedelta | None = None,
    max_lines: int = MAX_LINES,
    hangup_grace: timedelta = timedelta(seconds=TIMEOUT),
) -> Text:
    commands.append(
        use_command(
            columns,
            rows,
            env=env,
            clear_env=clear_env,
            timeout=timeout,
            max_lines=max_lines,
            hangup_grace=hangup_grace,
        )
    )
    return Text(content="")


def latest(commands: list[Command]) -> CommandRun:
    run = commands[-1].latest
    assert run is not None
    return run


def has_ended(commands: list[Command]) -> Callable[[], bool]:
    return lambda: commands[-1].latest is not None and not isinstance(commands[-1].latest.outcome, Starting | Running)


def output_text(transcript: Transcript) -> list[str]:
    return ["".join(cell.grapheme for cell in line).rstrip() for line in transcript.lines]


async def run_to_end(argv: tuple[str, ...], columns: int = 20, **kwargs: object) -> CommandRun:
    commands: list[Command] = []
    async with mounted() as m:
        await m.render(runner(columns, commands, **kwargs))  # type: ignore[arg-type]
        commands[-1].run(argv)
        await m.wait_until(has_ended(commands))
    return latest(commands)


def sh(script: str) -> tuple[str, ...]:
    return ("/bin/sh", "-c", script)


# Standard input is /dev/null, so stty asks the terminal for its size through /dev/tty instead.
STTY_SIZE = sh("stty size </dev/tty")


def outcomes(commands: list[Command]) -> list[Outcome]:
    seen: list[Outcome] = []
    for command in commands:
        if command.latest is not None and (not seen or seen[-1] != command.latest.outcome):
            seen.append(command.latest.outcome)
    return seen


async def test_a_run_shows_everything_the_program_printed_and_how_it_exited() -> None:
    run = await run_to_end(sh("echo one; echo two"))

    assert (run.argv, output_text(run.output), run.outcome) == (
        ("/bin/sh", "-c", "echo one; echo two"),
        ["one", "two"],
        Exited(status=0),
    )


async def test_a_run_reports_starting_then_running_then_exiting() -> None:
    commands: list[Command] = []
    async with mounted() as m:
        await m.render(runner(20, commands))
        commands[-1].run(sh("exit 0"))
        await m.wait_until(has_ended(commands))

    assert outcomes(commands) == [Starting(), Running(), Exited(status=0)]


async def test_a_program_that_fails_exits_with_its_status() -> None:
    run = await run_to_end(sh("echo oops; exit 3"))

    assert (output_text(run.output), run.outcome) == (["oops"], Exited(status=3))


async def test_a_program_that_does_not_exist_fails_to_start() -> None:
    run = await run_to_end(("counterweight-no-such-program",))

    assert (run.outcome, run.output.lines) == (FailedToStart(reason="No such file or directory"), ())


async def test_a_run_keeps_the_programs_colors() -> None:
    run = await run_to_end(sh(r"printf '\033[38;2;1;2;3mred\033[0m\n'"))

    assert run.output.lines[0][0].style.foreground == Color(1, 2, 3)


async def test_a_run_shows_the_last_frame_of_a_progress_bar() -> None:
    run = await run_to_end(sh(r"printf '[#  ]\r[## ]\r[###]\ndone\n'"))

    assert output_text(run.output) == ["[###]", "done"]


async def test_a_run_shows_output_that_scrolled_off_its_terminals_screen() -> None:
    run = await run_to_end(sh("seq 1 50"), rows=5)

    assert output_text(run.output) == [str(number) for number in range(1, 51)]


async def test_a_run_keeps_its_last_max_lines() -> None:
    run = await run_to_end(sh("seq 1 50"), rows=5, max_lines=10)

    assert output_text(run.output) == [str(number) for number in range(41, 51)]


async def test_a_program_formats_its_output_for_the_runs_columns_and_rows() -> None:
    run = await run_to_end(STTY_SIZE, columns=37, rows=11)

    assert (output_text(run.output), run.output.natural_size) == (["11 37"], (37, 1))


async def test_a_programs_standard_input_is_at_end_of_file() -> None:
    run = await run_to_end(sh("cat; echo after"))

    assert (output_text(run.output), run.outcome) == (["after"], Exited(status=0))


async def test_a_program_that_asks_its_terminal_where_its_cursor_is_gets_an_answer() -> None:
    script = sh(r"stty -echo raw </dev/tty; printf 'ab\033[6n' >/dev/tty; head -c 6 </dev/tty | tr -d '\033'; echo")

    run = await run_to_end(script, timeout=timedelta(seconds=5))

    assert (output_text(run.output), run.outcome) == (["ab[1;3R"], Exited(status=0))


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        pytest.param(frozendict(), ["cat cat"], id="defaults"),
        pytest.param(frozendict({"PAGER": "less"}), ["less cat"], id="overridden"),
    ],
)
async def test_a_programs_pager_prints_rather_than_waiting_for_keys(
    env: Mapping[str, str], expected: list[str]
) -> None:
    run = await run_to_end(sh('echo "$PAGER $GIT_PAGER"'), env=env)

    assert output_text(run.output) == expected


async def test_a_run_with_clear_env_leaves_out_the_apps_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COUNTERWEIGHT_INHERITED", "inherited")

    run = await run_to_end(("/bin/sh", "-c", 'echo "${COUNTERWEIGHT_INHERITED-unset} $PAGER"'), clear_env=True)

    assert output_text(run.output) == ["unset cat"]


@component
def inheriting_runner(commands: list[Command]) -> Text:
    commands.append(use_command(20))
    return Text(content="")


async def test_a_run_inherits_the_apps_environment_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COUNTERWEIGHT_INHERITED", "inherited")
    commands: list[Command] = []

    async with mounted() as m:
        await m.render(inheriting_runner(commands))
        commands[-1].run(("/bin/sh", "-c", 'echo "${COUNTERWEIGHT_INHERITED-unset}"'))
        await m.wait_until(has_ended(commands))

    assert output_text(latest(commands).output) == ["inherited"]


async def test_a_run_that_outlasts_its_timeout_times_out_with_its_output_so_far() -> None:
    run = await run_to_end(sh("echo started; sleep 30"), timeout=timedelta(milliseconds=500))

    assert (output_text(run.output), run.outcome) == (["started"], TimedOut())


async def wait_for_output(m: Mounted, commands: list[Command], text: str) -> None:
    await m.wait_until(lambda: commands[-1].latest is not None and text in output_text(commands[-1].latest.output))


async def test_cancelling_a_run_hangs_up_its_program_and_keeps_its_output_so_far(tmp_path: Path) -> None:
    signals = tmp_path / "signals"
    commands: list[Command] = []
    async with mounted() as m:
        await m.render(runner(20, commands))
        commands[-1].run(sh(f"trap 'echo HUP > {signals}; exit 1' HUP; echo started; while :; do sleep 0.01; done"))
        await wait_for_output(m, commands, "started")
        commands[-1].cancel()
        await m.wait_until(lambda: latest(commands).outcome == Cancelled())

    assert (output_text(latest(commands).output), latest(commands).outcome) == (["started"], Cancelled())
    assert signals.read_text() == "HUP\n"


async def test_cancelling_a_run_does_not_wait_for_its_program_to_be_hung_up() -> None:
    commands: list[Command] = []
    async with mounted() as m:
        await m.render(runner(20, commands, hangup_grace=timedelta(seconds=1)))
        commands[-1].run(sh("trap '' HUP; echo $$; while :; do sleep 0.01; done"))
        await m.wait_until(lambda: commands[-1].latest is not None and output_text(commands[-1].latest.output) != [])
        group = int(output_text(latest(commands).output)[0])
        commands[-1].cancel()
        await m.wait_until(lambda: latest(commands).outcome == Cancelled())
        is_running_once_cancelled = has_members(group)

    assert is_running_once_cancelled
    assert not has_members(group)


async def test_cancelling_when_no_run_is_in_progress_changes_nothing() -> None:
    commands: list[Command] = []
    async with mounted() as m:
        await m.render(runner(20, commands))
        commands[-1].cancel()
        commands[-1].run(sh("echo done"))
        await m.wait_until(has_ended(commands))
        commands[-1].cancel()
        await m.render(runner(20, commands))

    assert (output_text(latest(commands).output), latest(commands).outcome) == (["done"], Exited(status=0))


async def test_running_again_cancels_the_run_in_progress_and_shows_the_new_one(tmp_path: Path) -> None:
    signals = tmp_path / "signals"
    commands: list[Command] = []
    async with mounted() as m:
        await m.render(runner(20, commands))
        commands[-1].run(sh(f"trap 'echo HUP > {signals}; exit 1' HUP; echo first; while :; do sleep 0.01; done"))
        await wait_for_output(m, commands, "first")
        commands[-1].run(sh("echo second"))
        await m.wait_until(has_ended(commands))

    assert (output_text(latest(commands).output), latest(commands).outcome) == (["second"], Exited(status=0))
    assert signals.read_text() == "HUP\n"


async def test_running_the_same_argv_again_starts_another_run() -> None:
    commands: list[Command] = []
    script = sh("echo run")
    async with mounted() as m:
        await m.render(runner(20, commands))
        commands[-1].run(script)
        await m.wait_until(has_ended(commands))
        commands[-1].run(script)
        await m.wait_until(lambda: isinstance(latest(commands).outcome, Starting))
        await m.wait_until(has_ended(commands))

    assert outcomes(commands) == [Starting(), Running(), Exited(status=0), Starting(), Running(), Exited(status=0)]


async def test_a_run_waits_to_start_until_its_columns_are_positive() -> None:
    commands: list[Command] = []
    async with mounted() as m:
        await m.render(runner(0, commands, rows=7))
        commands[-1].run(STTY_SIZE)
        await m.render(runner(0, commands, rows=7))
        assert latest(commands) == CommandRun(argv=STTY_SIZE, output=Transcript(columns=0), outcome=Starting())
        await m.render(runner(29, commands, rows=7))
        await m.wait_until(has_ended(commands))

    assert output_text(latest(commands).output) == ["7 29"]


async def test_a_run_starts_at_one_column() -> None:
    run = await run_to_end(STTY_SIZE, columns=1, rows=7)

    assert (output_text(run.output), run.output.columns, run.outcome) == (["7", "", "1"], 1, Exited(status=0))


async def test_a_change_to_columns_during_a_run_does_not_rewrap_it() -> None:
    commands: list[Command] = []
    async with mounted() as m:
        await m.render(runner(20, commands))
        commands[-1].run(sh("echo started; sleep 0.2; stty size </dev/tty"))
        await wait_for_output(m, commands, "started")
        await m.render(runner(30, commands))
        await m.wait_until(has_ended(commands))

    assert (output_text(latest(commands).output), latest(commands).output.columns) == (["started", "24 20"], 20)


async def test_unmounting_hangs_up_the_program(tmp_path: Path) -> None:
    signals = tmp_path / "signals"
    commands: list[Command] = []
    async with mounted() as m:
        await m.render(runner(20, commands))
        commands[-1].run(sh(f"trap 'echo HUP > {signals}; exit 1' HUP; echo started; while :; do sleep 0.01; done"))
        await wait_for_output(m, commands, "started")

    assert signals.read_text() == "HUP\n"


async def test_a_running_programs_output_waits_for_the_next_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    # Longer than the run, so the output printed while it runs is only shown once it times out.
    monkeypatch.setattr("counterweight.commands.SNAPSHOT_INTERVAL", timedelta(hours=1))
    commands: list[Command] = []

    async with mounted() as m:
        await m.render(runner(20, commands, timeout=timedelta(milliseconds=500)))
        commands[-1].run(sh("echo early; sleep 30"))
        await m.wait_until(has_ended(commands))

    shown = [(output_text(c.latest.output), c.latest.outcome) for c in commands if c.latest is not None]
    assert list(unique_justseen(shown)) == [([], Starting()), ([], Running()), (["early"], TimedOut())]


async def test_run_and_cancel_are_the_same_functions_on_every_render() -> None:
    commands: list[Command] = []
    async with mounted() as m:
        await m.render(runner(20, commands))
        commands[-1].run(sh("exit 0"))
        await m.wait_until(has_ended(commands))

    assert (commands[0].run, commands[0].cancel) == (commands[-1].run, commands[-1].cancel)
    assert commands[0].latest is None


async def test_a_long_burst_of_output_shows_its_last_max_lines_without_gaps() -> None:
    run = await run_to_end(
        (sys.executable, "-c", "print('\\n'.join(map(str, range(30_000))))"), rows=5, max_lines=2_000
    )

    assert output_text(run.output) == [str(number) for number in range(28_000, 30_000)]


@pytest.mark.parametrize(
    ("outcome", "text"),
    [
        (Starting(), "starting"),
        (Running(), "running"),
        (Exited(status=0), "exited 0"),
        (Exited(status=2), "exited 2"),
        (Exited(status=-signal.SIGTERM), "ended by SIGTERM"),
        (Exited(status=-200), "ended by signal 200"),
        (FailedToStart(reason="No such file or directory"), "failed to start: No such file or directory"),
        (Cancelled(), "cancelled"),
        (TimedOut(), "timed out"),
    ],
)
def test_outcome_text_says_how_a_run_is_going_or_how_it_ended(outcome: Outcome, text: str) -> None:
    assert outcome_text(outcome) == text


STYLES = CommandOutputStyles(
    in_progress=text_color("sky", 300),
    succeeded=text_color("lime", 300),
    failed=text_color("rose", 300),
    cancelled=text_color("orange", 300),
)


@pytest.mark.parametrize(
    ("outcome", "style"),
    [
        (Starting(), STYLES.in_progress),
        (Running(), STYLES.in_progress),
        (Exited(status=0), STYLES.succeeded),
        (Exited(status=1), STYLES.failed),
        (FailedToStart(reason="gone"), STYLES.failed),
        (TimedOut(), STYLES.failed),
        (Cancelled(), STYLES.cancelled),
    ],
)
def test_the_line_beneath_a_run_is_styled_by_its_outcome(outcome: Outcome, style: Style) -> None:
    assert STYLES.outcome_style(outcome) == style


VIEWPORT = ElementHandle()


async def frame_text(root: Component, dimensions: tuple[int, int]) -> list[str]:
    frames: list[Frame] = []
    await app(root, headless=True, dimensions=dimensions, autopilot=[Screenshot(handler=frames.append), Quit()])
    return [line.rstrip() for line in frames[-1].text(ansi=False).splitlines()]


async def test_command_output_shows_a_runs_output_in_a_box_with_its_outcome_beneath() -> None:
    run = CommandRun(argv=("ls",), output=Transcript.of(b"one\r\ntwo\r\n", columns=8), outcome=Exited(status=0))

    rows = await frame_text(command_output(run, VIEWPORT, style=size(12, 5)), (12, 5))

    assert rows == ["╭──────────╮", "│ one      │", "│ two      │", "╰──────────╯", "exited 0"]


async def test_command_output_follows_the_end_of_output_too_long_for_its_box() -> None:
    output = Transcript.of(b"".join(b"%d\r\n" % number for number in range(10)), columns=8)
    run = CommandRun(argv=("seq",), output=output, outcome=Running())

    rows = await frame_text(command_output(run, VIEWPORT, style=size(12, 5)), (12, 5))

    assert rows[1:3] == ["│ 8        │", "│ 9        │"]


async def test_command_output_without_a_run_is_an_empty_box() -> None:
    rows = await frame_text(command_output(None, VIEWPORT, style=size(6, 3)), (6, 3))

    assert rows == ["╭────╮", "│    │", "╰────╯"]


@component
def slide(argv: tuple[str, ...], ended: Event, on_key: Callable[[], Screenshot]) -> Div:
    viewport, _ = use_state(ElementHandle)
    command = use_command(columns=use_rects(viewport).content.width)

    async def start() -> None:
        command.run(argv)

    use_effect(start, deps=(argv,))

    async def signal_end() -> None:
        if command.latest is not None and isinstance(command.latest.outcome, Exited):
            ended.set()

    use_effect(signal_end, deps=(command.latest,))

    return Div(
        style=col | full,
        on_input=lambda event, receiver: on_key(),
        children=(command_output(command.latest, viewport, style=fill(1)),),
    )


async def test_a_slide_runs_its_command_at_the_width_of_the_box_that_shows_it(terminal: Terminal) -> None:
    ended = Event()
    shot = Event()
    frames: list[Frame] = []

    def take(frame: Frame) -> None:
        frames.append(frame)
        shot.set()

    running = create_task(
        app(
            slide(STTY_SIZE, ended, lambda: Screenshot(handler=take)),
            output_stream=io.StringIO(),
            input_stream=terminal.stream,
            dimensions=(20, 5),
        )
    )
    try:
        await wait_for(ended.wait(), TIMEOUT)
        os.write(terminal.keyboard, b"s")
        await wait_for(shot.wait(), TIMEOUT)
    finally:
        running.cancel()
        with suppress(CancelledError):
            await running

    assert [line.rstrip() for line in frames[-1].text(ansi=False).splitlines()] == [
        "╭──────────────────╮",
        "│ 24 16            │",
        "│                  │",
        "╰──────────────────╯",
        "exited 0",
    ]


async def test_cancelling_terminates_a_program_that_ignores_hanging_up_after_its_hangup_grace(tmp_path: Path) -> None:
    signals = tmp_path / "signals"
    commands: list[Command] = []
    # Ignores SIGHUP, and exits by itself after at least half a second, much longer than its grace.
    script = sh(
        f"trap '' HUP; trap 'echo term >> {signals}; exit' TERM; echo ready; "
        f"i=0; while [ $i -lt 50 ]; do sleep 0.01; i=$((i+1)); done; echo exited >> {signals}"
    )
    async with mounted() as m:
        await m.render(runner(20, commands, hangup_grace=timedelta(milliseconds=50)))
        commands[-1].run(script)
        await wait_for_output(m, commands, "ready")
        commands[-1].cancel()
        await m.wait_until(lambda: latest(commands).outcome == Cancelled())

    assert signals.read_text() == "term\n"


REQUEST = Request(argv=("make", "docs"))


def command_run(outcome: Outcome) -> CommandRun:
    return CommandRun(argv=REQUEST.argv, output=Transcript(columns=13), outcome=outcome)


def test_runs_take_a_run_of_the_request_they_are_running() -> None:
    runs = Runs(request=REQUEST, latest=command_run(Starting()))

    assert runs.updated(REQUEST, command_run(Running())) == Runs(request=REQUEST, latest=command_run(Running()))


@pytest.mark.parametrize(
    "runs",
    [
        pytest.param(Runs(request=Request(argv=REQUEST.argv), latest=command_run(Starting())), id="another request"),
        pytest.param(Runs(request=None, latest=command_run(Cancelled())), id="cancelled"),
    ],
)
def test_runs_ignore_a_run_of_a_request_they_are_not_running(runs: Runs) -> None:
    assert runs.updated(REQUEST, command_run(Running())) == runs


@pytest.mark.parametrize(
    ("latest", "expected"),
    [
        pytest.param(None, None, id="none"),
        pytest.param(command_run(Starting()), command_run(Cancelled()), id="starting"),
        pytest.param(command_run(Running()), command_run(Cancelled()), id="running"),
        pytest.param(command_run(Exited(status=4)), command_run(Exited(status=4)), id="exited"),
    ],
)
def test_cancelled_runs_run_nothing_and_cancel_a_run_in_progress(
    latest: CommandRun | None, expected: CommandRun | None
) -> None:
    assert Runs(request=REQUEST, latest=latest).cancelled() == Runs(request=None, latest=expected)
