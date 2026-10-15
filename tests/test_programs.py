import signal
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from counterweight.programs import DEFAULT_EDITOR
from counterweight.programs import NO_PROGRAM
from counterweight.programs import Edited
from counterweight.programs import Exited
from counterweight.programs import FailedToStart
from counterweight.programs import TerminalStreams
from counterweight.programs import edit_file
from counterweight.programs import edit_text
from counterweight.programs import preferred_editor
from counterweight.programs import run_program

UPPERCASE_EDITOR = ("sh", "-c", 'tr a-z A-Z < "$1" > "$1.new" && mv "$1.new" "$1"', "sh")
"""An editor that uppercases the file, replacing it rather than writing into it, as vim does by default."""

PATH_EDITOR = ("sh", "-c", 'printf %s "$1" > "$1"', "sh")
"""An editor that replaces the file's text with its path."""


@dataclass(frozen=True, slots=True)
class FileTerminal:
    """Streams on files: what a program reads comes from `typed`, and what it writes lands in `shown`."""

    streams: TerminalStreams
    shown: Path


@pytest.fixture
def file_terminal(tmp_path: Path) -> Iterator[FileTerminal]:
    typed = tmp_path / "typed"
    typed.write_text("from the keyboard\n")
    shown = tmp_path / "shown"
    with typed.open() as input_stream, shown.open("w") as output_stream:
        yield FileTerminal(streams=TerminalStreams(input=input_stream, output=output_stream), shown=shown)


@pytest.fixture
def recorded_signals() -> Iterator[list[int]]:
    """Installs handlers for the app to replace that record `SIGINT` and `SIGQUIT`, and records those that reach them."""
    received: list[int] = []

    def record(signum: int, frame: object) -> None:
        received.append(signum)

    previous = {number: signal.signal(number, record) for number in (signal.SIGINT, signal.SIGQUIT)}
    yield received
    for number, handler in previous.items():
        signal.signal(number, handler)


async def test_a_program_writes_its_output_and_errors_to_the_terminal_and_reports_its_exit_status(
    file_terminal: FileTerminal,
) -> None:
    outcome = await run_program(["sh", "-c", "echo out; echo err >&2; exit 3"], file_terminal.streams)

    assert (outcome, file_terminal.shown.read_text()) == (Exited(status=3), "out\nerr\n")


async def test_a_program_reads_from_the_terminal(file_terminal: FileTerminal) -> None:
    await run_program(["sh", "-c", 'read line; echo "got $line"'], file_terminal.streams)

    assert file_terminal.shown.read_text() == "got from the keyboard\n"


async def test_a_program_that_does_not_exist_fails_to_start(file_terminal: FileTerminal) -> None:
    assert await run_program(["/no/such/program"], file_terminal.streams) == FailedToStart(
        reason="No such file or directory"
    )


async def test_an_empty_argv_fails_to_start(file_terminal: FileTerminal) -> None:
    assert await run_program([], file_terminal.streams) == NO_PROGRAM


async def test_a_program_gets_the_apps_environment_with_env_over_it(
    file_terminal: FileTerminal, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FROM_APP", "app")
    monkeypatch.setenv("REPLACED", "app")

    await run_program(
        ["sh", "-c", 'echo "$FROM_APP $REPLACED $FROM_CALLER"'],
        file_terminal.streams,
        env={"REPLACED": "caller", "FROM_CALLER": "caller"},
    )

    assert file_terminal.shown.read_text() == "app caller caller\n"


async def test_a_program_with_a_cleared_environment_gets_only_env(
    file_terminal: FileTerminal, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FROM_APP", "app")

    await run_program(
        ["sh", "-c", 'echo "${FROM_APP-unset} $FROM_CALLER"'],
        file_terminal.streams,
        env={"FROM_CALLER": "caller"},
        clear_env=True,
    )

    assert file_terminal.shown.read_text() == "unset caller\n"


async def test_a_program_runs_in_cwd(file_terminal: FileTerminal, tmp_path: Path) -> None:
    directory = tmp_path / "elsewhere"
    directory.mkdir()

    await run_program(["sh", "-c", "pwd -P"], file_terminal.streams, cwd=directory)

    assert file_terminal.shown.read_text() == f"{directory.resolve()}\n"


async def test_the_app_swallows_the_interrupts_the_terminal_sends_the_program_which_gets_its_usual_handling(
    file_terminal: FileTerminal, recorded_signals: list[int]
) -> None:
    # As Ctrl+C and Ctrl+\ do, the program's parent gets each signal too, and the program dies of the interrupt.
    outcome = await run_program(
        ["sh", "-c", "kill -INT $PPID; kill -QUIT $PPID; kill -INT $$"],
        file_terminal.streams,
    )

    assert (outcome, recorded_signals) == (Exited(status=-signal.SIGINT), [])


async def test_the_apps_signal_handlers_are_restored_once_the_program_exits(
    file_terminal: FileTerminal, recorded_signals: list[int]
) -> None:
    await run_program(["true"], file_terminal.streams)
    signal.raise_signal(signal.SIGINT)
    signal.raise_signal(signal.SIGQUIT)

    assert recorded_signals == [signal.SIGINT, signal.SIGQUIT]


@pytest.mark.parametrize(
    ("environ", "expected"),
    [
        ({"VISUAL": "nvim", "EDITOR": "nano"}, ("nvim",)),
        ({"EDITOR": "nano"}, ("nano",)),
        ({"VISUAL": " ", "EDITOR": "nano"}, ("nano",)),
        ({"EDITOR": "code --wait"}, ("code", "--wait")),
        ({"EDITOR": "'/opt/my editor/ed' -n"}, ("/opt/my editor/ed", "-n")),
        ({"VISUAL": "", "EDITOR": ""}, DEFAULT_EDITOR),
    ],
)
def test_the_preferred_editor_is_visual_then_editor_then_vi(environ: dict[str, str], expected: tuple[str, ...]) -> None:
    assert preferred_editor(environ) == expected


async def test_editing_a_file_edits_it_in_place_and_reports_how_the_editor_exited(
    file_terminal: FileTerminal, tmp_path: Path
) -> None:
    path = tmp_path / "notes.md"
    path.write_text("before\n")

    outcome = await edit_file(path, file_terminal.streams, editor=UPPERCASE_EDITOR)

    assert (outcome, path.read_text()) == (Exited(status=0), "BEFORE\n")


async def test_editing_a_file_runs_the_preferred_editor_by_default(
    file_terminal: FileTerminal, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "notes.md"
    monkeypatch.setenv("VISUAL", """sh -c 'printf %s "$1" > "$1"' sh""")

    await edit_file(path, file_terminal.streams)

    assert path.read_text() == str(path)


async def test_editing_a_file_with_an_editor_that_fails_reports_its_status(
    file_terminal: FileTerminal, tmp_path: Path
) -> None:
    assert await edit_file(tmp_path / "notes.md", file_terminal.streams, editor=("sh", "-c", "exit 2")) == Exited(
        status=2
    )


async def test_editing_text_returns_what_the_editor_left_in_the_file(file_terminal: FileTerminal) -> None:
    assert await edit_text("before\n", file_terminal.streams, editor=UPPERCASE_EDITOR) == Edited(text="BEFORE\n")


async def test_editing_text_edits_a_file_with_file_name_that_is_removed_afterwards(
    file_terminal: FileTerminal,
) -> None:
    outcome = await edit_text("", file_terminal.streams, file_name="notes.md", editor=PATH_EDITOR)

    assert isinstance(outcome, Edited)
    path = Path(outcome.text)
    assert (path.name, path.parent.exists()) == ("notes.md", False)


async def test_editing_text_runs_the_preferred_editor_by_default(
    file_terminal: FileTerminal, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    editor = tmp_path / "my editor"
    editor.write_text('#!/bin/sh\nprintf "%s %s" "$1" "$(basename "$2")" > "$2"\n')
    editor.chmod(0o755)
    monkeypatch.setenv("VISUAL", f"'{editor}' --flag")

    assert await edit_text("", file_terminal.streams) == Edited(text="--flag edit.txt")


async def test_an_editor_that_fails_abandons_the_edit(file_terminal: FileTerminal) -> None:
    assert await edit_text("before", file_terminal.streams, editor=("sh", "-c", "exit 1")) == Exited(status=1)


async def test_an_editor_that_does_not_exist_fails_to_start(file_terminal: FileTerminal) -> None:
    assert await edit_text("before", file_terminal.streams, editor=("/no/such/editor",)) == FailedToStart(
        reason="No such file or directory"
    )
