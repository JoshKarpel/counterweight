from __future__ import annotations

import os
import signal
import sys
from asyncio import CancelledError
from asyncio import Event
from asyncio import create_subprocess_exec
from asyncio import create_task
from asyncio import get_running_loop
from asyncio import sleep
from asyncio import wait_for
from asyncio.subprocess import PIPE
from collections.abc import Callable
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from datetime import timedelta
from pathlib import Path
from unittest.mock import call

import pytest
from more_itertools import unique_justseen
from pytest_mock import MockerFixture

from counterweight.components import component
from counterweight.elements import Text
from counterweight.programs import NO_PROGRAM
from counterweight.programs import TimedOut
from counterweight.pseudoterminal import Exited
from counterweight.pseudoterminal import FailedToStart
from counterweight.pseudoterminal import Pty
from counterweight.pseudoterminal import PtyConnection
from counterweight.pseudoterminal import PtyStatus
from counterweight.pseudoterminal import Running
from counterweight.pseudoterminal import Starting
from counterweight.pseudoterminal import end_process_group
from counterweight.pseudoterminal import group_ended
from counterweight.pseudoterminal import has_members
from counterweight.pseudoterminal import program_environment
from counterweight.pseudoterminal import read_output
from counterweight.pseudoterminal import run_pty
from counterweight.pseudoterminal import use_pty
from tests.rendering import TIMEOUT
from tests.rendering import mounted


def open_fds() -> set[str]:
    return {path.name for path in Path("/dev/fd").iterdir()}


def assert_group_ended(group: int) -> None:
    with pytest.raises(ProcessLookupError):
        os.killpg(group, 0)


@dataclass(slots=True)
class Output:
    """Collects what a program writes, and wakes a test waiting for some of it."""

    data: bytearray = field(default_factory=bytearray)
    arrived: Event = field(default_factory=Event)

    def __call__(self, data: bytes) -> None:
        self.data += data
        self.arrived.set()

    async def wait_for(self, expected: bytes) -> None:
        while expected not in self.data:
            self.arrived.clear()
            await wait_for(self.arrived.wait(), TIMEOUT)


@dataclass(slots=True)
class Started:
    """Keeps the connection `run_pty` hands out, and wakes a test waiting for it."""

    connection: PtyConnection | None = None
    event: Event = field(default_factory=Event)

    def __call__(self, connection: PtyConnection) -> None:
        self.connection = connection
        self.event.set()

    async def wait(self) -> PtyConnection:
        await wait_for(self.event.wait(), TIMEOUT)
        assert self.connection is not None
        return self.connection


async def test_run_pty_returns_the_exit_status_with_everything_the_program_wrote() -> None:
    output = Output()

    outcome = await run_pty(["sh", "-c", "printf out; printf err >&2; exit 3"], 20, 4, on_output=output)

    assert outcome == Exited(status=3)
    assert output.data == b"outerr"


async def test_run_pty_reports_a_program_ended_by_a_signal_as_its_negated_number() -> None:
    assert await run_pty(["sh", "-c", "kill -TERM $$"], 20, 4, on_output=Output()) == Exited(status=-15)


async def test_run_pty_starts_the_program_at_the_given_size() -> None:
    output = Output()

    await run_pty(["stty", "size"], 37, 11, on_output=output)

    assert output.data.split() == [b"11", b"37"]


async def test_run_pty_tells_the_program_its_terminals_size_in_pixels_is_unknown() -> None:
    output = Output()
    script = (
        "import fcntl, struct, termios; print(*struct.unpack('HHHH', fcntl.ioctl(1, termios.TIOCGWINSZ, bytes(8))))"
    )

    await run_pty([sys.executable, "-c", script], 37, 11, on_output=output)

    assert output.data.split() == [b"11", b"37", b"0", b"0"]


async def test_run_pty_stops_reading_at_end_of_file_while_the_program_keeps_running() -> None:
    loop = get_running_loop()
    errors: list[dict[str, object]] = []
    loop.set_exception_handler(lambda loop, context: errors.append(context))
    try:
        outcome = await run_pty(
            ["sh", "-c", "echo closing; exec >/dev/null 2>&1; sleep 0.2"], 20, 4, on_output=Output(), stdin="devnull"
        )
    finally:
        loop.set_exception_handler(None)

    assert outcome == Exited(status=0)
    assert errors == []


async def test_run_pty_makes_the_terminal_the_programs_controlling_terminal_and_its_standard_streams() -> None:
    output = Output()

    await run_pty(["sh", "-c", "test -t 0 && test -t 1 && test -t 2 && : < /dev/tty && echo yes"], 20, 4, output)

    assert output.data.strip() == b"yes"


async def test_run_pty_with_stdin_from_devnull_gives_the_program_end_of_file_on_a_controlling_terminal() -> None:
    output = Output()

    outcome = await run_pty(
        ["sh", "-c", "cat; test -t 0 || echo devnull; test -t 1 && : < /dev/tty && echo tty"],
        20,
        4,
        on_output=output,
        stdin="devnull",
    )

    assert outcome == Exited(status=0)
    assert output.data.split() == [b"devnull", b"tty"]


async def test_run_pty_returns_once_the_program_exits_despite_a_background_job_holding_the_terminal_open() -> None:
    output = Output()
    started = Started()

    outcome = await wait_for(
        # Linux hangs up the terminal's foreground process group when the program exits,
        # so only a job that ignores that keeps the terminal open.
        run_pty(
            ["sh", "-c", "trap '' HUP; sleep 30 & echo started; exit 3"],
            20,
            4,
            on_output=output,
            on_start=started,
            hangup_grace=timedelta(milliseconds=100),
        ),
        TIMEOUT,
    )

    assert outcome == Exited(status=3)
    assert output.data.strip() == b"started"
    assert_group_ended((await started.wait()).pid)


async def test_run_pty_hangs_up_a_program_still_running_when_its_timeout_runs_out(tmp_path: Path) -> None:
    signals = tmp_path / "signals"
    output = Output()

    outcome = await wait_for(
        run_pty(
            ["sh", "-c", f"trap 'echo hup >> {signals}; exit' HUP; echo started; while :; do sleep 0.01; done"],
            20,
            4,
            on_output=output,
            timeout=timedelta(milliseconds=100),
        ),
        TIMEOUT,
    )

    assert outcome == TimedOut()
    assert output.data.strip() == b"started"
    assert signals.read_text() == "hup\n"


async def test_run_pty_returns_how_a_program_exited_in_time_however_long_its_background_job_holds_the_terminal() -> (
    None
):
    # Reading until the background job lets go of the terminal, and hanging it up, both outlast the timeout.
    outcome = await wait_for(
        run_pty(
            ["sh", "-c", "trap '' HUP; sleep 30 & exit 3"],
            20,
            4,
            on_output=Output(),
            hangup_grace=timedelta(milliseconds=100),
            timeout=timedelta(milliseconds=100),
        ),
        TIMEOUT,
    )

    assert outcome == Exited(status=3)


async def test_run_pty_signals_nothing_once_a_program_exits_leaving_nothing_running(mocker: MockerFixture) -> None:
    killpg = mocker.patch("os.killpg", wraps=os.killpg)
    started = Started()

    assert await run_pty(["true"], 20, 4, on_output=Output(), on_start=started) == Exited(status=0)

    assert killpg.call_args_list == [call((await started.wait()).pid, 0)]


async def test_run_pty_reports_a_program_that_does_not_exist_as_failing_to_start_and_closes_its_terminal() -> None:
    before = open_fds()

    outcome = await run_pty(["counterweight-no-such-program"], 20, 4, on_output=Output())

    assert outcome == FailedToStart(reason="No such file or directory")
    assert open_fds() == before


async def test_run_pty_reports_an_empty_argv_as_failing_to_start_and_opens_no_terminal() -> None:
    before = open_fds()

    outcome = await run_pty([], 20, 4, on_output=Output())

    assert outcome == NO_PROGRAM
    assert open_fds() == before


async def test_run_pty_closes_its_terminal_when_cancelled_while_spawning() -> None:
    before = open_fds()
    task = create_task(run_pty(["sleep", "30"], 20, 4, on_output=Output()))
    await sleep(0)

    task.cancel()

    with pytest.raises(CancelledError):
        await task
    assert open_fds() == before


async def test_run_pty_resizing_the_terminal_changes_the_size_the_program_sees() -> None:
    output = Output()
    started = Started()
    task = create_task(run_pty(["sh", "-c", "read line; stty size"], 20, 4, on_output=output, on_start=started))
    connection = await started.wait()

    connection.resize(43, 13)
    connection.write(b"\n")
    assert not connection.is_writing

    assert await wait_for(task, TIMEOUT) == Exited(status=0)
    assert output.data.split() == [b"13", b"43"]


async def test_run_pty_buffers_writes_the_program_is_not_reading_yet() -> None:
    output = Output()
    started = Started()
    lines = 2_000
    task = create_task(
        run_pty(["sh", "-c", "stty -echo; echo ready; sleep 0.2; wc -c"], 20, 4, on_output=output, on_start=started)
    )
    connection = await started.wait()
    await output.wait_for(b"ready")

    # Far more than the terminal holds, so some of it waits until the program reads, then a ^D ends its input.
    connection.write((b"x" * 99 + b"\n") * lines)
    assert connection.is_writing
    connection.write(b"\x04")

    assert await wait_for(task, TIMEOUT) == Exited(status=0)
    assert output.data.split() == [b"ready", str(100 * lines).encode()]


async def test_cancelling_run_pty_drops_writes_the_program_never_read() -> None:
    started = Started()
    task = create_task(run_pty(["sleep", "30"], 20, 4, on_output=Output(), on_start=started))
    connection = await started.wait()
    connection.write(b"x\n" * 100_000)
    assert connection.is_writing

    task.cancel()

    with pytest.raises(CancelledError):
        await task
    assert (connection.is_writing, connection.pending) == (False, b"")


async def test_a_connection_does_nothing_once_its_program_has_exited() -> None:
    started = Started()
    await run_pty(["true"], 20, 4, on_output=Output(), on_start=started)
    connection = await started.wait()

    connection.write(b"ignored")
    connection.resize(1, 1)

    assert connection.is_closed
    assert connection.pending == b""


async def test_cancelling_run_pty_hangs_up_the_program(tmp_path: Path) -> None:
    signals = tmp_path / "signals"
    output = Output()
    started = Started()
    task = create_task(
        run_pty(
            ["sh", "-c", f"trap 'echo hup >> {signals}; exit' HUP; echo ready; while :; do sleep 0.01; done"],
            20,
            4,
            on_output=output,
            on_start=started,
            hangup_grace=timedelta(seconds=TIMEOUT),
        )
    )
    connection = await started.wait()
    await output.wait_for(b"ready")

    task.cancel()

    with pytest.raises(CancelledError):
        await task
    assert signals.read_text() == "hup\n"
    assert_group_ended(connection.pid)


async def test_hanging_up_run_pty_reads_and_drops_what_the_program_writes_meanwhile(tmp_path: Path) -> None:
    signals = tmp_path / "signals"
    output = Output()
    started = Started()
    # Hung up, it writes far more than its terminal holds, which it can only finish if the terminal is read.
    task = create_task(
        run_pty(
            [
                "sh",
                "-c",
                f"trap 'head -c 1000000 /dev/zero; echo done >> {signals}; exit' HUP; "
                "echo ready; while :; do sleep 0.01; done",
            ],
            20,
            4,
            on_output=output,
            on_start=started,
            hangup_grace=timedelta(seconds=TIMEOUT),
        )
    )
    await started.wait()
    await output.wait_for(b"ready")

    task.cancel()

    with pytest.raises(CancelledError):
        await task
    assert signals.read_text() == "done\n"
    assert output.data == b"ready\r\n"


async def test_cancelling_run_pty_terminates_then_kills_a_program_that_ignores_hanging_up(tmp_path: Path) -> None:
    signals = tmp_path / "signals"
    output = Output()
    started = Started()
    task = create_task(
        run_pty(
            [
                "sh",
                "-c",
                f"trap 'echo hup >> {signals}' HUP; trap 'echo term >> {signals}' TERM; "
                "echo ready; while :; do sleep 0.01; done",
            ],
            20,
            4,
            on_output=output,
            on_start=started,
            hangup_grace=timedelta(milliseconds=100),
        )
    )
    connection = await started.wait()
    await output.wait_for(b"ready")

    task.cancel()

    with pytest.raises(CancelledError):
        await task
    assert signals.read_text() == "hup\nterm\n"
    assert_group_ended(connection.pid)


async def test_run_pty_gives_the_program_the_inherited_environment_under_the_terminals_and_envs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COUNTERWEIGHT_INHERITED", "inherited")
    monkeypatch.setenv("COLUMNS", "200")
    output = Output()

    await run_pty(
        ["sh", "-c", 'echo "$COUNTERWEIGHT_INHERITED|$TERM|$COLORTERM|${COLUMNS-unset}|$COUNTERWEIGHT_GIVEN"'],
        20,
        4,
        on_output=output,
        env={"COLORTERM": "24bit", "COUNTERWEIGHT_GIVEN": "given"},
    )

    assert output.data.strip() == b"inherited|xterm-256color|24bit|unset|given"


async def test_run_pty_with_clear_env_leaves_out_the_inherited_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COUNTERWEIGHT_INHERITED", "inherited")
    output = Output()

    await run_pty(
        ["/bin/sh", "-c", 'echo "${COUNTERWEIGHT_INHERITED-unset}|${HOME-unset}|$TERM"'],
        20,
        4,
        on_output=output,
        clear_env=True,
    )

    assert output.data.strip() == b"unset|unset|xterm-256color"


@pytest.mark.parametrize(
    ("inherited", "env", "expected"),
    [
        ({"HOME": "/home/ada"}, {}, {"HOME": "/home/ada", "TERM": "xterm-256color", "COLORTERM": "truecolor"}),
        ({"TERM": "dumb"}, {}, {"TERM": "xterm-256color", "COLORTERM": "truecolor"}),
        ({"TERM": "dumb"}, {"TERM": "vt100"}, {"TERM": "vt100", "COLORTERM": "truecolor"}),
        ({"COLUMNS": "200", "LINES": "50"}, {}, {"TERM": "xterm-256color", "COLORTERM": "truecolor"}),
        ({}, {"COLUMNS": "80"}, {"COLUMNS": "80", "TERM": "xterm-256color", "COLORTERM": "truecolor"}),
    ],
)
def test_program_environment_layers_env_over_the_terminals_over_the_inherited_without_its_size(
    inherited: Mapping[str, str], env: Mapping[str, str], expected: dict[str, str]
) -> None:
    assert program_environment(inherited, env) == expected


@component
def terminal(
    argv: tuple[str, ...],
    columns: int,
    rows: int,
    on_output: Callable[[bytes], None],
    ptys: list[Pty],
    env: Mapping[str, str] = frozendict(),
    clear_env: bool = False,
    hangup_grace: timedelta = timedelta(seconds=TIMEOUT),
) -> Text:
    ptys.append(
        use_pty(argv, columns, rows, on_output=on_output, env=env, clear_env=clear_env, hangup_grace=hangup_grace)
    )
    return Text(content="")


def statuses(ptys: list[Pty]) -> list[PtyStatus]:
    return list(unique_justseen(pty.status for pty in ptys))


async def test_use_pty_starts_the_program_once_it_has_a_positive_size_and_at_that_size() -> None:
    ptys: list[Pty] = []
    output = Output()
    argv = ("stty", "size")

    async with mounted() as m:
        await m.render(terminal(argv, 0, 0, output, ptys))
        await m.render(terminal(argv, 37, 0, output, ptys))
        # Nothing signals that a program hasn't started, so give one started at 0 by 0 a while to say so.
        with pytest.raises(TimeoutError):
            await wait_for(output.wait_for(b"\n"), 0.2)
        await m.render(terminal(argv, 37, 11, output, ptys))
        await m.wait_until(lambda: isinstance(ptys[-1].status, Exited))

    assert output.data.split() == [b"11", b"37"]


async def test_use_pty_reports_the_program_starting_running_and_exiting() -> None:
    ptys: list[Pty] = []

    async with mounted() as m:
        await m.render(terminal(("sh", "-c", "read line; exit 3"), 20, 4, Output(), ptys))
        await m.wait_until(lambda: ptys[-1].status == Running())
        ptys[-1].write(b"\n")
        await m.wait_until(lambda: ptys[-1].status != Running())
        ptys[-1].write(b"ignored")

    assert statuses(ptys) == [Starting(), Running(), Exited(status=3)]


async def test_use_pty_reports_a_program_that_does_not_exist_as_failing_to_start() -> None:
    ptys: list[Pty] = []

    async with mounted() as m:
        await m.render(terminal(("counterweight-no-such-program",), 20, 4, Output(), ptys))
        await m.wait_until(lambda: ptys[-1].status != Starting())

    assert ptys[-1].status == FailedToStart(reason="No such file or directory")


async def test_use_pty_write_is_the_same_function_on_every_render_and_does_nothing_before_the_program_starts() -> None:
    ptys: list[Pty] = []

    async with mounted() as m:
        await m.render(terminal(("cat",), 0, 0, Output(), ptys))
        ptys[-1].write(b"ignored")
        await m.render(terminal(("cat",), 0, 1, Output(), ptys))

    assert ptys[0].write is ptys[-1].write
    assert statuses(ptys) == [Starting()]


async def test_use_pty_sends_output_to_the_latest_renders_on_output() -> None:
    ptys: list[Pty] = []
    first = Output()
    latest = Output()
    argv = ("sh", "-c", "stty -echo; echo ready; read line; echo done")

    async with mounted() as m:
        await m.render(terminal(argv, 20, 4, first, ptys))
        await first.wait_for(b"ready")
        await m.render(terminal(argv, 20, 4, latest, ptys))
        ptys[-1].write(b"\n")
        await latest.wait_for(b"done")

    assert first.data.split() == [b"ready"]
    assert latest.data.split() == [b"done"]


async def test_use_pty_resizes_the_terminal_when_its_size_changes() -> None:
    ptys: list[Pty] = []
    output = Output()
    argv = ("sh", "-c", "trap 'stty size; exit' WINCH; echo ready; while :; do sleep 0.01; done")

    async with mounted() as m:
        await m.render(terminal(argv, 20, 4, output, ptys))
        await output.wait_for(b"ready")
        await m.render(terminal(argv, 43, 13, output, ptys))
        await m.wait_until(lambda: isinstance(ptys[-1].status, Exited))

    assert output.data.split() == [b"ready", b"13", b"43"]


async def test_use_pty_applies_a_size_that_changed_while_the_program_was_starting() -> None:
    ptys: list[Pty] = []
    output = Output()
    argv = ("sh", "-c", "stty -echo; echo ready; read line; stty size")

    async with mounted() as m:
        await m.render(terminal(argv, 20, 4, output, ptys))
        await m.render(terminal(argv, 43, 13, output, ptys))
        await output.wait_for(b"ready")
        ptys[-1].write(b"\n")
        await m.wait_until(lambda: isinstance(ptys[-1].status, Exited))

    assert output.data.split() == [b"ready", b"13", b"43"]


async def test_use_pty_keeps_the_terminals_size_when_given_one_that_is_not_positive() -> None:
    ptys: list[Pty] = []
    output = Output()
    argv = ("sh", "-c", "stty -echo; echo ready; read line; stty size")

    async with mounted() as m:
        await m.render(terminal(argv, 20, 4, output, ptys))
        await output.wait_for(b"ready")
        await m.render(terminal(argv, 0, 13, output, ptys))
        ptys[-1].write(b"\n")
        await m.wait_until(lambda: isinstance(ptys[-1].status, Exited))

    assert output.data.split() == [b"ready", b"4", b"20"]


def hangs_up(signals: Path, message: str) -> tuple[str, ...]:
    """A program that writes `message`, then records being hung up in `signals`, naming itself by `message`."""
    return (
        "sh",
        "-c",
        f"trap 'echo hup {message} >> {signals}; exit' HUP; echo {message}; while :; do sleep 0.01; done",
    )


async def test_use_pty_hangs_up_the_program_and_starts_it_again_when_argv_changes(tmp_path: Path) -> None:
    signals = tmp_path / "signals"
    ptys: list[Pty] = []
    output = Output()

    async with mounted() as m:
        await m.render(terminal(hangs_up(signals, "first"), 20, 4, output, ptys))
        await output.wait_for(b"first")
        await m.render(terminal(hangs_up(signals, "second"), 20, 4, output, ptys))
        await output.wait_for(b"second")

    # The first is hung up when argv changes, and the second only when it unmounts.
    assert signals.read_text() == "hup first\nhup second\n"


async def test_use_pty_starts_the_program_again_when_env_changes() -> None:
    ptys: list[Pty] = []
    output = Output()
    argv = ("sh", "-c", 'echo "<$COUNTERWEIGHT_GIVEN>"; while :; do sleep 0.01; done')

    async with mounted() as m:
        await m.render(terminal(argv, 20, 4, output, ptys, env={"COUNTERWEIGHT_GIVEN": "first"}))
        await output.wait_for(b"<first>")
        await m.render(terminal(argv, 20, 4, output, ptys, env={"COUNTERWEIGHT_GIVEN": "second"}))
        await output.wait_for(b"<second>")


async def test_use_pty_hangs_up_the_program_when_its_component_unmounts(tmp_path: Path) -> None:
    signals = tmp_path / "signals"
    ptys: list[Pty] = []
    output = Output()

    async with mounted() as m:
        await m.render(terminal(hangs_up(signals, "ready"), 20, 4, output, ptys))
        await output.wait_for(b"ready")
        await m.render(Text(content="gone"))

    assert signals.read_text() == "hup ready\n"


async def test_use_pty_unmounts_without_waiting_for_its_program_to_be_hung_up() -> None:
    ptys: list[Pty] = []
    output = Output()
    argv = ("sh", "-c", "trap '' HUP; echo $$; while :; do sleep 0.01; done")

    async with mounted() as m:
        await m.render(terminal(argv, 20, 4, output, ptys, hangup_grace=timedelta(seconds=1)))
        await output.wait_for(b"\n")
        group = int(output.data)
        await m.render(Text(content="gone"))
        is_running_once_unmounted = has_members(group)

    assert is_running_once_unmounted
    assert_group_ended(group)


async def test_use_pty_starts_a_terminal_one_cell_across() -> None:
    ptys: list[Pty] = []
    output = Output()

    async with mounted() as m:
        await m.render(terminal(("stty", "size"), 1, 1, output, ptys))
        await m.wait_until(lambda: isinstance(ptys[-1].status, Exited))

    assert output.data.split() == [b"1", b"1"]


@component
def inheriting_terminal(argv: tuple[str, ...], on_output: Callable[[bytes], None], ptys: list[Pty]) -> Text:
    ptys.append(use_pty(argv, 20, 4, on_output=on_output))
    return Text(content="")


ECHO_INHERITED = ("/bin/sh", "-c", 'echo "${COUNTERWEIGHT_INHERITED-unset}"')


async def test_use_pty_inherits_the_apps_environment_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COUNTERWEIGHT_INHERITED", "inherited")
    ptys: list[Pty] = []
    output = Output()

    async with mounted() as m:
        await m.render(inheriting_terminal(ECHO_INHERITED, output, ptys))
        await m.wait_until(lambda: isinstance(ptys[-1].status, Exited))

    assert output.data.strip() == b"inherited"


async def test_use_pty_with_clear_env_leaves_out_the_apps_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COUNTERWEIGHT_INHERITED", "inherited")
    ptys: list[Pty] = []
    output = Output()

    async with mounted() as m:
        await m.render(terminal(ECHO_INHERITED, 20, 4, output, ptys, clear_env=True))
        await m.wait_until(lambda: isinstance(ptys[-1].status, Exited))

    assert output.data.strip() == b"unset"


async def test_use_pty_terminates_a_program_that_ignores_hanging_up_after_its_hangup_grace(tmp_path: Path) -> None:
    signals = tmp_path / "signals"
    ptys: list[Pty] = []
    output = Output()
    # Ignores SIGHUP, and exits by itself after at least half a second, much longer than its grace.
    argv = (
        "sh",
        "-c",
        f"trap '' HUP; trap 'echo term >> {signals}; exit' TERM; echo ready; "
        f"i=0; while [ $i -lt 50 ]; do sleep 0.01; i=$((i+1)); done; echo exited >> {signals}",
    )

    async with mounted() as m:
        await m.render(terminal(argv, 20, 4, output, ptys, hangup_grace=timedelta(milliseconds=50)))
        await output.wait_for(b"ready")
        await m.render(Text(content="gone"))

    assert signals.read_text() == "term\n"


def test_a_terminal_that_cant_be_read_has_ended() -> None:
    # As Linux fails reading a terminal that nothing holds the program's side of open, a pipe's write end fails anywhere.
    read_end, write_end = os.pipe()
    try:
        assert read_output(write_end) == b""
    finally:
        os.close(read_end)
        os.close(write_end)


async def test_a_group_that_refuses_to_be_signalled_has_ended(mocker: MockerFixture) -> None:
    # As macOS refuses, for a group whose members have all exited but haven't been reaped.
    mocker.patch("os.killpg", side_effect=PermissionError)

    await wait_for(group_ended(os.getpgrp()), TIMEOUT)


async def test_ending_a_group_that_refuses_to_be_signalled_stops_signalling_it(mocker: MockerFixture) -> None:
    process = await create_subprocess_exec("true", start_new_session=True)
    await process.wait()
    killpg = mocker.patch("os.killpg", side_effect=PermissionError)

    await wait_for(end_process_group(process, timedelta(seconds=10)), TIMEOUT)

    assert killpg.call_count == 1


async def test_cancelling_the_end_of_a_process_group_partway_kills_it_at_once() -> None:
    process = await create_subprocess_exec(
        "sh", "-c", "trap '' HUP TERM; echo ready; while :; do sleep 0.01; done", stdout=PIPE, start_new_session=True
    )
    assert process.stdout is not None
    await wait_for(process.stdout.readline(), TIMEOUT)
    task = create_task(end_process_group(process, timedelta(seconds=TIMEOUT)))
    await sleep(0)  # The group is sent SIGHUP, which it ignores, and given its grace.

    task.cancel()

    with pytest.raises(CancelledError):
        await task
    await wait_for(process.communicate(), TIMEOUT)
    assert process.returncode == -signal.SIGKILL
