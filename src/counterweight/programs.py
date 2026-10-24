"""
Running a program on the app's own terminal while the app is suspended, as `git commit` runs an editor
and `git log` a pager: [`run_program`][counterweight.programs.run_program], which runs one until it exits,
and [`edit_file`][counterweight.programs.edit_file] and [`edit_text`][counterweight.programs.edit_text],
which edit a file or a string in the user's editor.
[`Suspend.to_program`][counterweight.controls.Suspend.to_program],
[`Suspend.to_edit_file`][counterweight.controls.Suspend.to_edit_file] and
[`Suspend.to_edit_text`][counterweight.controls.Suspend.to_edit_text] are the controls that run them.

It also holds how a program ends, [`Exited`][counterweight.programs.Exited] or
[`FailedToStart`][counterweight.programs.FailedToStart],
which programs run on a pseudo-terminal share, and [`TimedOut`][counterweight.programs.TimedOut],
for one run there with a time limit.
"""

from __future__ import annotations

import os
import shlex
import signal
from asyncio import create_subprocess_exec
from collections.abc import Iterator
from collections.abc import Mapping
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from types import FrameType
from typing import TextIO

DEFAULT_EDITOR = ("vi",)
"""The editor [`preferred_editor`][counterweight.programs.preferred_editor] falls back to, as git does."""

FOREGROUND_SIGNALS = (signal.SIGINT, signal.SIGQUIT)
"""
The signals the terminal sends its whole foreground process group for Ctrl+C and Ctrl+\\,
which the app and the program it's running are both in.
"""


@dataclass(frozen=True, slots=True)
class TerminalStreams:
    """The terminal a suspended app hands back, which a [`Suspend`][counterweight.controls.Suspend] handler receives."""

    input: TextIO
    """The stream the app reads input from, `input_stream` on `counterweight._app.app`."""

    output: TextIO
    """The stream the app draws on, `output_stream` on `counterweight._app.app`."""


@dataclass(frozen=True, slots=True)
class Exited:
    """The program exited."""

    status: int
    """Its exit status, or the negated number of the signal that ended it, as `asyncio` reports it."""


@dataclass(frozen=True, slots=True)
class FailedToStart:
    """The program couldn't be started, such as for an `argv` naming a file that doesn't exist."""

    reason: str
    """Why, from the operating system, such as `"No such file or directory"`."""


@dataclass(frozen=True, slots=True)
class TimedOut:
    """The program was still running when its `timeout` ran out, so it was hung up."""


NO_PROGRAM = FailedToStart(reason="No program to run: argv is empty")
"""How running an empty `argv` ends, rather than with the `TypeError` spawning nothing raises."""

type ProgramOutcome = Exited | FailedToStart
"""How a program that ran until it exited ended."""


@dataclass(frozen=True, slots=True)
class Edited:
    """The editor exited successfully, leaving `text` in the file."""

    text: str


type EditOutcome = Edited | Exited | FailedToStart
"""
How an edit ended: with the edited text, or without it, if the editor exited with a failing status
(as `:cq` makes vim do, to abandon an edit) or couldn't start.
An `Exited` outcome of an edit always has a failing status.
"""


def swallow_signal(signum: int, frame: FrameType | None) -> None:
    """
    A handler that does nothing, for a signal meant for the program the app is running.
    A handler rather than `SIG_IGN`, since a program inherits ignored signals but not handled ones,
    so the program gets the default handling of a signal the app swallows.
    """


@contextmanager
def swallowed_signals(signal_numbers: Sequence[int]) -> Iterator[None]:
    """Swallows `signal_numbers` while the block runs, then restores their handlers."""
    previous = {number: signal.signal(number, swallow_signal) for number in signal_numbers}
    try:
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


async def run_program(
    argv: Sequence[str],
    terminal: TerminalStreams,
    env: Mapping[str, str] = frozendict(),
    clear_env: bool = False,
    cwd: Path | None = None,
) -> ProgramOutcome:
    """
    Runs `argv` on `terminal` until it exits, reading from its input and writing to its output,
    standard error included, as a shell runs a program in the foreground.
    Run it while the app is suspended, so the program has the terminal to itself,
    as [`Suspend.to_program`][counterweight.controls.Suspend.to_program] does.

    While it runs, the app swallows `SIGINT` and `SIGQUIT`, as POSIX's `system()` does:
    the terminal sends the keys that interrupt and quit, Ctrl+C and Ctrl+Backslash,
    to the app as well as the program, since they share it,
    so they don't quit the app, while the program handles them as it would in a shell.
    Ctrl+Z stops both, as it stops any program in a terminal with whatever started it,
    until the shell resumes them with `fg`.

    Parameters:
        env: Variables to set in the program's environment, over the app's.
        clear_env: Leave out the app's environment, so the program gets only `env`.
        cwd: The directory to run the program in, or `None` for the app's working directory.

    Returns:
        How the program exited, or why it couldn't start.
    """
    if not argv:
        return NO_PROGRAM
    with swallowed_signals(FOREGROUND_SIGNALS):
        try:
            process = await create_subprocess_exec(
                *argv,
                stdin=terminal.input,
                stdout=terminal.output,
                stderr=terminal.output,
                env={**({} if clear_env else os.environ), **env},
                cwd=cwd,
            )
        except OSError as e:
            return FailedToStart(reason=e.strerror or repr(e))
        return Exited(status=await process.wait())


def preferred_editor(environ: Mapping[str, str]) -> tuple[str, ...]:
    """
    The `argv` of the editor the user prefers, as git finds it:
    `$VISUAL`, then `$EDITOR`, skipping one that's unset or blank, then `vi`.
    The variable is split as a shell splits words, so one with arguments, such as `code --wait`, works.
    """
    for name in ("VISUAL", "EDITOR"):
        if editor := tuple(shlex.split(environ.get(name, ""))):
            return editor
    return DEFAULT_EDITOR


async def edit_file(
    path: Path,
    terminal: TerminalStreams,
    editor: Sequence[str] | None = None,
) -> ProgramOutcome:
    """
    Edits the file at `path` in an editor on `terminal`,
    running the editor with the path after its `argv` (see [`run_program`][counterweight.programs.run_program]).
    A file that doesn't exist yet is created if the user saves it, as vim and nano do.

    An editor that exits with a failing status, as `:cq` makes vim do, signals that the user abandoned the edit,
    though what it saved before then stays saved.

    Parameters:
        editor: The editor's `argv`, or `None` for the [`preferred_editor`][counterweight.programs.preferred_editor].

    Returns:
        How the editor exited, or why it couldn't start.
    """
    argv = preferred_editor(os.environ) if editor is None else editor
    return await run_program([*argv, str(path)], terminal)


async def edit_text(
    text: str,
    terminal: TerminalStreams,
    file_name: str = "edit.txt",
    editor: Sequence[str] | None = None,
) -> EditOutcome:
    """
    Edits `text` in an editor on `terminal`, as `git commit` edits a commit message:
    writes it to a file named `file_name` in a new temporary directory,
    edits the file (see [`edit_file`][counterweight.programs.edit_file]),
    and reads it back if the editor exits successfully.
    The directory is removed afterwards.

    The text is written and read as UTF-8.
    Many editors, such as vim, end a file they save with a line break, which the edited text then ends with too.

    Parameters:
        file_name: The file's name, which an editor picks its syntax highlighting by,
            such as `notes.md` for Markdown, or `COMMIT_EDITMSG` for a commit message.
        editor: The editor's `argv`, or `None` for the [`preferred_editor`][counterweight.programs.preferred_editor].

    Returns:
        The edited text, or how the editor exited if it didn't succeed, or why it couldn't start.
    """
    with TemporaryDirectory(prefix="counterweight-") as directory:
        path = Path(directory) / file_name
        path.write_text(text, encoding="utf-8")
        match outcome := await edit_file(path, terminal, editor=editor):
            case Exited(status=0):
                return Edited(text=path.read_text(encoding="utf-8"))
            case _:
                return outcome


__all__ = [
    "DEFAULT_EDITOR",
    "EditOutcome",
    "Edited",
    "Exited",
    "FailedToStart",
    "ProgramOutcome",
    "TerminalStreams",
    "TimedOut",
    "edit_file",
    "edit_text",
    "preferred_editor",
    "run_program",
]
