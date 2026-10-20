import os
import signal
import subprocess
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from counterweight._utils import maybe_await
from counterweight.controls import Suspend
from counterweight.programs import Edited
from counterweight.programs import EditOutcome
from counterweight.programs import Exited
from counterweight.programs import ProgramOutcome
from counterweight.programs import TerminalStreams

TIMEOUT = 5

SUSPEND_TO_SHELL_ON_A_LINE = """
import sys
from counterweight.controls import Suspend
from counterweight.programs import TerminalStreams
input()
Suspend.to_shell().handler(TerminalStreams(input=sys.stdin, output=sys.stdout))
"""


def test_suspending_to_the_shell_stops_the_whole_process_group() -> None:
    # The app and what started it, such as `uv run`, in a process group of their own, so the test doesn't stop itself.
    # Not a session of their own: Linux discards a stop signal sent to a group with no parent outside it in its session.
    with (
        subprocess.Popen(
            [sys.executable, "-c", SUSPEND_TO_SHELL_ON_A_LINE],
            process_group=0,
            stdin=subprocess.PIPE,
            text=True,
        ) as app,
        subprocess.Popen([sys.executable, "-c", "input()"], process_group=app.pid, stdin=subprocess.PIPE) as starter,
        # Waiting on threads, so a process that never stops fails the test once the wait times out rather than hanging it,
        # and the kill ends the wait.
        ThreadPoolExecutor() as executor,
    ):
        try:
            waits = [executor.submit(os.waitpid, process.pid, os.WUNTRACED) for process in (app, starter)]
            assert app.stdin is not None
            app.stdin.write("\n")
            app.stdin.flush()
            statuses = [wait.result(timeout=TIMEOUT)[1] for wait in waits]
        finally:
            os.killpg(app.pid, signal.SIGKILL)

    assert [os.WIFSTOPPED(status) and os.WSTOPSIG(status) for status in statuses] == [signal.SIGTSTP] * 2


def test_suspending_to_the_shell_is_one_value() -> None:
    assert Suspend.to_shell() == Suspend.to_shell()


@pytest.fixture
def streams(tmp_path: Path) -> Iterator[TerminalStreams]:
    with Path(os.devnull).open() as input_stream, (tmp_path / "shown").open("w") as output_stream:
        yield TerminalStreams(input=input_stream, output=output_stream)


async def test_suspending_to_a_program_passes_on_exit_how_it_exited(streams: TerminalStreams) -> None:
    outcomes: list[ProgramOutcome] = []

    await maybe_await(Suspend.to_program(["sh", "-c", "exit 4"], on_exit=outcomes.append).handler(streams))

    assert outcomes == [Exited(status=4)]


async def test_suspending_to_a_program_runs_it_with_its_environment_and_directory(
    streams: TerminalStreams, tmp_path: Path, directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FROM_APP", "app")
    suspend = Suspend.to_program(
        ["sh", "-c", 'echo "${FROM_APP-unset} $FROM_CALLER $(pwd -P)"'],
        env={"FROM_CALLER": "caller"},
        clear_env=True,
        cwd=tmp_path,
    )

    await maybe_await(suspend.handler(streams))

    assert (tmp_path / "shown").read_text() == f"unset caller {directory}\n"


async def test_suspending_to_a_program_needs_no_on_exit(streams: TerminalStreams, tmp_path: Path) -> None:
    await maybe_await(Suspend.to_program(["sh", "-c", "echo ran"]).handler(streams))

    assert (tmp_path / "shown").read_text() == "ran\n"


async def test_suspending_to_a_program_runs_it_with_the_apps_environment_by_default(
    streams: TerminalStreams, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FROM_APP", "inherited")

    await maybe_await(Suspend.to_program(["sh", "-c", 'echo "${FROM_APP-unset}"']).handler(streams))

    assert (tmp_path / "shown").read_text() == "inherited\n"


async def test_suspending_to_edit_a_file_edits_it_with_the_preferred_editor_by_default(
    streams: TerminalStreams, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VISUAL", "sh -c 'echo visual > \"$1\"' sh")
    path = tmp_path / "notes.md"

    await maybe_await(Suspend.to_edit_file(path).handler(streams))

    assert path.read_text() == "visual\n"


async def test_suspending_to_edit_a_file_edits_it_with_editor_and_passes_on_exit_how_it_exited(
    streams: TerminalStreams, tmp_path: Path
) -> None:
    outcomes: list[ProgramOutcome] = []
    path = tmp_path / "notes.md"
    path_editor = ("sh", "-c", 'printf %s "$1" > "$1"; exit 3', "sh")

    await maybe_await(Suspend.to_edit_file(path, on_exit=outcomes.append, editor=path_editor).handler(streams))

    assert (outcomes, path.read_text()) == ([Exited(status=3)], str(path))


async def test_suspending_to_edit_a_file_needs_no_on_exit(streams: TerminalStreams, tmp_path: Path) -> None:
    path = tmp_path / "notes.md"

    await maybe_await(Suspend.to_edit_file(path, editor=("sh", "-c", 'echo edited > "$1"', "sh")).handler(streams))

    assert path.read_text() == "edited\n"


NAME_EDITOR = ("sh", "-c", 'printf "%s %s" "$(cat "$1")" "$(basename "$1")" > "$1"', "sh")


async def test_suspending_to_edit_text_passes_on_edit_the_edited_text(streams: TerminalStreams) -> None:
    outcomes: list[EditOutcome] = []

    await maybe_await(
        Suspend.to_edit_text("draft", on_edit=outcomes.append, file_name="notes.md", editor=NAME_EDITOR).handler(
            streams
        )
    )

    assert outcomes == [Edited(text="draft notes.md")]


async def test_suspending_to_edit_text_names_its_file_edit_txt_by_default(streams: TerminalStreams) -> None:
    outcomes: list[EditOutcome] = []

    await maybe_await(Suspend.to_edit_text("memo", on_edit=outcomes.append, editor=NAME_EDITOR).handler(streams))

    assert outcomes == [Edited(text="memo edit.txt")]


async def test_suspending_to_edit_text_edits_it_with_the_preferred_editor_by_default(
    streams: TerminalStreams, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VISUAL", "sh -c 'printf visual > \"$1\"' sh")
    outcomes: list[EditOutcome] = []

    await maybe_await(Suspend.to_edit_text("draft", on_edit=outcomes.append, file_name="notes.md").handler(streams))

    assert outcomes == [Edited(text="visual")]
