"""
Running a program on a pseudo-terminal, as a terminal window or a multiplexer's pane does:
[`run_pty`][counterweight.pseudoterminal.run_pty], which runs one until it exits,
and [`use_pty`][counterweight.pseudoterminal.use_pty], which runs one while a component is mounted.

Both hand back the bytes the program writes, and know nothing about what they mean:
feed them to an [`Emulator`][counterweight.emulator.Emulator] to see what the program's terminal shows.
Linux and macOS only.
"""

from __future__ import annotations

import errno
import fcntl
import os
import signal
import struct
import termios
from asyncio import CancelledError
from asyncio import Event
from asyncio import TaskGroup
from asyncio import create_subprocess_exec
from asyncio import get_running_loop
from asyncio import shield
from asyncio import sleep
from asyncio import timeout as time_limit
from asyncio import wait_for
from asyncio.subprocess import DEVNULL
from asyncio.subprocess import Process
from collections.abc import Callable
from collections.abc import Coroutine
from collections.abc import Mapping
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from dataclasses import field
from datetime import timedelta
from typing import Literal
from typing import overload

from counterweight._context_vars import current_task_group
from counterweight.hooks import Ref
from counterweight.hooks import use_effect
from counterweight.hooks import use_memo
from counterweight.hooks import use_ref
from counterweight.hooks import use_state
from counterweight.programs import NO_PROGRAM
from counterweight.programs import Exited
from counterweight.programs import FailedToStart
from counterweight.programs import TimedOut

READ_SIZE = 2**16

TERMINAL_ENVIRONMENT = frozendict({"TERM": "xterm-256color", "COLORTERM": "truecolor"})
"""What every program is told about the terminal it's on, under the caller's `env`."""

SIZE_VARIABLES = frozenset({"COLUMNS", "LINES"})
"""
Variables describing the size of the terminal the app started in, which the inherited environment drops.
Some programs read them before asking their terminal (Python's `shutil.get_terminal_size` does),
and they'd be wrong for the pseudo-terminal from the start, or once it resizes.
"""

HANGUP_GRACE = timedelta(seconds=1)

DRAIN_TIMEOUT = timedelta(milliseconds=500)
"""
How long to keep reading after the program exits, for what it wrote just before.
Reading ends sooner at end of file, which comes once nothing holds the terminal open,
but a background job the program started can hold it open indefinitely.
"""

# Nothing signals when a process group empties (its members aren't our children, so they can't be waited on),
# so ending one checks this often whether any of them are left.
GROUP_POLL_INTERVAL = timedelta(milliseconds=10)

NOTHING_TO_SIGNAL = (ProcessLookupError, PermissionError)
"""
What signalling a process group with nothing left running in it raises:
`ProcessLookupError` once every member is gone, and on macOS, `PermissionError` while the members that are left
have all exited but haven't been reaped yet, as the program has until `run_pty` waits for it.
"""

type StandardInput = Literal["pty", "devnull"]
"""
Where the program reads its standard input from: its terminal, for a program that takes keys,
or `/dev/null`, so a program that reads input gets end of file rather than waiting for keys that never come.
"""


@dataclass(frozen=True, slots=True)
class Starting:
    """The program hasn't started yet: its terminal is waiting for a size, or the program is being spawned."""


@dataclass(frozen=True, slots=True)
class Running:
    """The program is running."""


type PtyStatus = Starting | Running | Exited | FailedToStart


def program_environment(inherited: Mapping[str, str], env: Mapping[str, str]) -> dict[str, str]:
    """
    The environment a program runs with: `inherited` without its size variables,
    then the terminal's variables over it, and `env` over those.
    """
    return {
        **{name: value for name, value in inherited.items() if name not in SIZE_VARIABLES},
        **TERMINAL_ENVIRONMENT,
        **env,
    }


def window_size(columns: int, rows: int) -> bytes:
    """The `struct winsize` that `TIOCSWINSZ` takes."""
    return struct.pack("HHHH", rows, columns, 0, 0)


@dataclass(slots=True)
class PtyConnection:
    """
    The master side of a running program's pseudo-terminal, which `run_pty` hands out while the program runs.
    Writes that the program isn't reading yet are buffered and flushed when the terminal is writable,
    so a handler that writes never blocks the event loop.
    Once `run_pty` returns, writing and resizing do nothing.
    """

    master: int
    pid: int
    pending: bytearray = field(default_factory=bytearray)
    is_writing: bool = False
    is_closed: bool = False

    def write(self, data: bytes) -> None:
        if self.is_closed:
            return
        self.pending += data
        self.flush()

    def flush(self) -> None:
        try:
            written = os.write(self.master, self.pending)
        except BlockingIOError:
            written = 0
        del self.pending[:written]
        if self.pending and not self.is_writing:
            get_running_loop().add_writer(self.master, self.flush)
            self.is_writing = True
        elif not self.pending and self.is_writing:
            self.stop_writing()

    def stop_writing(self) -> None:
        get_running_loop().remove_writer(self.master)
        self.is_writing = False

    def resize(self, columns: int, rows: int) -> None:
        """Sets the terminal's size, which sends the program `SIGWINCH`, as resizing a terminal window does."""
        if self.is_closed:
            return
        fcntl.ioctl(self.master, termios.TIOCSWINSZ, window_size(columns, rows))

    def close(self) -> None:
        if self.is_writing:
            self.stop_writing()
        self.is_closed = True
        self.pending.clear()
        os.close(self.master)


def make_controlling_terminal() -> None:  # pragma: no cover, runs in the child between fork and exec
    """
    Run in the child, after `setsid`: makes the pseudo-terminal its controlling terminal.
    Standard output is always the pseudo-terminal, while standard input may be `/dev/null`, where this would fail.
    """
    fcntl.ioctl(1, termios.TIOCSCTTY, 0)


@overload
async def run_pty(
    argv: Sequence[str],
    columns: int,
    rows: int,
    on_output: Callable[[bytes], None],
    on_start: Callable[[PtyConnection], None] = ...,
    env: Mapping[str, str] = ...,
    clear_env: bool = ...,
    stdin: StandardInput = ...,
    hangup_grace: timedelta = ...,
    timeout: None = None,  # noqa: ASYNC109 (see the implementation)
) -> Exited | FailedToStart: ...


@overload
async def run_pty(
    argv: Sequence[str],
    columns: int,
    rows: int,
    on_output: Callable[[bytes], None],
    on_start: Callable[[PtyConnection], None] = ...,
    env: Mapping[str, str] = ...,
    clear_env: bool = ...,
    stdin: StandardInput = ...,
    hangup_grace: timedelta = ...,
    timeout: timedelta | None = ...,  # noqa: ASYNC109 (see the implementation)
) -> Exited | FailedToStart | TimedOut: ...


async def run_pty(
    argv: Sequence[str],
    columns: int,
    rows: int,
    on_output: Callable[[bytes], None],
    on_start: Callable[[PtyConnection], None] = lambda connection: None,
    env: Mapping[str, str] = frozendict(),
    clear_env: bool = False,
    stdin: StandardInput = "pty",
    hangup_grace: timedelta = HANGUP_GRACE,
    # An `asyncio.timeout` around the call would also cut short reading the program's last output and hanging it up.
    timeout: timedelta | None = None,  # noqa: ASYNC109
) -> Exited | FailedToStart | TimedOut:
    """
    Runs `argv` on a new pseudo-terminal `columns` by `rows`, in its own session with the terminal as its controlling
    terminal, until it exits.

    Parameters:
        on_output: Called on the event loop with each read of what the program writes, standard output and standard
            error together, as a terminal shows them.
        on_start: Called once the program is running, with the connection to write to it and resize its terminal.
        env: Variables to set in the program's environment.
            The program gets the app's environment (unless `clear_env`), without `COLUMNS` and `LINES`,
            then `TERM=xterm-256color` and `COLORTERM=truecolor` over it, then `env` over those.
        clear_env: Leave out the app's environment, so the program gets only the terminal's variables and `env`.
        stdin: Where the program reads its standard input from.
        hangup_grace: How long the program has to exit after each signal that ends it (see below).
        timeout: How long the program may run before it's hung up and `TimedOut` is returned, or `None` for no limit.
            Only the program's own run counts against it: once it exits, it has exited,
            however long reading what it wrote last and hanging up what it left running take.

    Returns:
        How the program exited, why it couldn't start, or that it ran out of time.

    Once the program exits, what it wrote just before is read for up to `DRAIN_TIMEOUT`.
    Then, or when cancelled or out of time, the program is hung up, as closing a terminal window does:
    its process group, which includes anything it started in the background, gets `SIGHUP`,
    and whatever is still running `hangup_grace` later gets `SIGTERM`, then `SIGKILL` after another,
    so no program outlives the call that ran it.
    Cancelled while hanging up, it sends `SIGKILL` at once.
    What the program writes while it's hung up isn't passed to `on_output`.
    """
    if not argv:
        return NO_PROGRAM
    master, slave = os.openpty()
    try:
        os.set_blocking(master, False)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, window_size(columns, rows))
        process = await create_subprocess_exec(
            *argv,
            stdin={"pty": slave, "devnull": DEVNULL}[stdin],
            stdout=slave,
            stderr=slave,
            env=program_environment({} if clear_env else os.environ, env),
            start_new_session=True,
            preexec_fn=make_controlling_terminal,
        )
    except OSError as e:
        os.close(master)
        return FailedToStart(reason=e.strerror or repr(e))
    except BaseException:  # cancelled while spawning
        os.close(master)
        raise
    finally:
        os.close(slave)

    connection = PtyConnection(master=master, pid=process.pid)
    loop = get_running_loop()
    closed = Event()

    def read() -> None:
        if (data := read_output(master)) is None:  # pragma: no cover, only a wakeup the suite can't arrange
            return
        if not data:
            loop.remove_reader(master)
            closed.set()
            return
        on_output(data)

    def discard() -> None:
        if read_output(master) == b"":
            loop.remove_reader(master)

    loop.add_reader(master, read)
    is_group_empty = False
    try:
        on_start(connection)
        try:
            async with time_limit(None if timeout is None else timeout.total_seconds()):
                status = await process.wait()
        except TimeoutError:
            return TimedOut()
        # The group's id is the program's pid, which the kernel won't reuse while the group has members.
        # asyncio has just reaped the program, so an empty group's id is already free, and signalling it could reach
        # whatever process reuses it, so an empty group isn't hung up at all.
        # Remaining risk: the id is free and unchecked from the reap to this check (one turn of the event loop),
        # and from the group's last member exiting, during the drain or the hangup, to the next signal or poll
        # (up to `DRAIN_TIMEOUT` or `GROUP_POLL_INTERVAL` later). That signals an unrelated group only if pids
        # wrap around within the window and the process given this pid leads a group of its own, as a shell's jobs do.
        is_group_empty = not has_members(process.pid)
        with suppress(TimeoutError):
            await wait_for(closed.wait(), timeout=DRAIN_TIMEOUT.total_seconds())
        return Exited(status=status)
    finally:
        # What the program writes while it's hung up, such as the report a shell prints when a signal kills its job,
        # is read and dropped: on macOS, a session leader's exit waits until its terminal's output has been read,
        # so a terminal nobody reads keeps it exiting forever, which `killpg` reports as nothing left to signal.
        loop.remove_reader(master)
        loop.add_reader(master, discard)
        try:
            if not is_group_empty:
                await end_process_group(process, hangup_grace)
        finally:
            loop.remove_reader(master)
            connection.close()


def read_output(master: int) -> bytes | None:
    """
    The next read of what the program on the terminal `master` wrote, `b""` at end of file,
    which comes once nothing holds the program's side of the terminal open
    (macOS reads it as nothing, and Linux fails the read with `EIO`),
    or `None` if there's nothing to read yet, as a reader woken with nothing waiting finds.
    Raises any other error reading.
    """
    try:
        return os.read(master, READ_SIZE)
    except BlockingIOError:
        return None
    except OSError as e:
        if e.errno == errno.EIO:  # pragma: linux only
            return b""
        raise


async def end_process_group(process: Process, grace: timedelta) -> None:
    """
    Signals `process`'s group with `SIGHUP`, `SIGTERM` and `SIGKILL` in turn, `grace` apart,
    until nothing in it is running, then waits for `process` itself.
    Cancelled partway, such as by an app quitting while a program it cancelled is still being hung up,
    it sends `SIGKILL` at once, so nothing in the group outlives it.
    """
    try:
        with suppress(*NOTHING_TO_SIGNAL):
            for signal_number in (signal.SIGHUP, signal.SIGTERM, signal.SIGKILL):
                os.killpg(process.pid, signal_number)
                with suppress(TimeoutError):
                    async with time_limit(grace.total_seconds()):
                        await group_ended(process.pid)
    except CancelledError:
        with suppress(*NOTHING_TO_SIGNAL):
            os.killpg(process.pid, signal.SIGKILL)
        raise
    await process.wait()


async def group_ended(group: int) -> None:
    """Returns once nothing in the process group `group` is running."""
    while has_members(group):  # noqa: ASYNC110 (nothing signals when a group empties: it's polled)
        await sleep(GROUP_POLL_INTERVAL.total_seconds())


def has_members(group: int) -> bool:
    """Whether anything in the process group `group` is still running."""
    try:
        os.killpg(group, 0)
    except NOTHING_TO_SIGNAL:
        return False
    return True


async def tear_down_in_background[T](task_group: TaskGroup, run: Coroutine[object, object, T]) -> T:
    """
    Awaits `run` in a task of `task_group`, the app's, so that cancelling the caller, such as an effect,
    cancels `run` and returns at once, leaving `run` to tear down, such as hanging up its program, in the background,
    where it doesn't hold up the render loop, which waits for a cancelled effect to finish before it renders again.
    The task group waits for `run` when the app stops.
    """
    task = task_group.create_task(run)
    try:
        return await shield(task)
    except CancelledError:
        task.cancel()
        raise


@dataclass(frozen=True, slots=True)
class Pty:
    """What [`use_pty`][counterweight.pseudoterminal.use_pty] returns."""

    write: Callable[[bytes], None]
    """
    Sends bytes to the program, as typing into its terminal does.
    It does nothing while the program isn't running, and is the same function on every render.
    """

    status: PtyStatus


def use_pty(
    argv: Sequence[str],
    columns: int,
    rows: int,
    on_output: Callable[[bytes], None],
    env: Mapping[str, str] = frozendict(),
    clear_env: bool = False,
    hangup_grace: timedelta = HANGUP_GRACE,
) -> Pty:
    """
    Runs `argv` on a pseudo-terminal while the calling component is mounted, as a terminal window does,
    with its terminal `columns` by `rows`, reading its standard input from the terminal.
    See [`run_pty`][counterweight.pseudoterminal.run_pty] for `env`, `clear_env` and `hangup_grace`,
    and for how the program is hung up when the component unmounts.

    The program starts once `columns` and `rows` are both positive, so a component that sizes the terminal
    from its own box with `use_rects`, which is zero on its first render, starts the program at its real size.
    Later changes to them resize the terminal, which sends the program `SIGWINCH`, except to a size that isn't positive.
    A change to `argv`, `env` or `clear_env` hangs the program up and starts it again.
    Hanging up goes on in the background, so a program slow to exit doesn't hold up the app's rendering,
    and an app that stops waits for it.

    Parameters:
        on_output: Called, from the event loop rather than during a render, with each read of what the program writes.
            The latest render's `on_output` is the one called.
    """
    output: Ref[Callable[[bytes], None]] = use_ref(lambda: on_output)
    output.current = on_output

    connection: Ref[PtyConnection | None] = use_ref(None)
    size: Ref[tuple[int, int]] = use_ref((0, 0))
    is_sized: Ref[Event] = use_ref(Event)
    initial_status: PtyStatus = Starting()
    status, set_status = use_state(initial_status)
    task_group = current_task_group.get()

    async def apply_size() -> None:
        if columns <= 0 or rows <= 0:
            return
        size.current = (columns, rows)
        is_sized.current.set()
        if (c := connection.current) is not None:
            c.resize(columns, rows)

    # Before running the program, so that on mount the program starts at this render's size.
    use_effect(apply_size, deps=(columns, rows))

    async def run() -> None:
        set_status(Starting())
        await is_sized.current.wait()
        spawned_size = size.current

        def start(c: PtyConnection) -> None:
            connection.current = c
            # The terminal may have resized while the program was spawning, when there was nothing to resize.
            if size.current != spawned_size:
                c.resize(*size.current)
            set_status(Running())

        def forward(data: bytes) -> None:
            # Through the ref, so the latest render's callback gets the output, not this one's.
            output.current(data)

        try:
            outcome = await tear_down_in_background(
                task_group,
                run_pty(
                    argv,
                    *spawned_size,
                    on_output=forward,
                    on_start=start,
                    env=env,
                    clear_env=clear_env,
                    hangup_grace=hangup_grace,
                ),
            )
        finally:
            connection.current = None
        set_status(outcome)

    use_effect(run, deps=(tuple(argv), env, clear_env))

    def write(data: bytes) -> None:
        if (c := connection.current) is not None:
            c.write(data)

    return Pty(write=use_memo(lambda: write, ()), status=status)
