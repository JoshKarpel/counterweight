"""
[`use_pty`][counterweight.headless.terminal.use_pty], which runs a program on a pseudo-terminal,
and [`use_terminal`][counterweight.headless.terminal.use_terminal], which emulates the terminal that program draws on,
leaving where and how to show it to the calling component.

Spike: Linux and macOS only.
"""

from __future__ import annotations

import asyncio
import fcntl
import logging
import os
import signal
import struct
import termios
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta

from counterweight.controls import FocusOn
from counterweight.emulator import BLANK_SCREEN, Emulator, Screen, ScreenView
from counterweight.events import (
    InputEvent,
    InputHandler,
    InputResponse,
    KeyPressed,
    MouseDown,
    MouseEvent,
    Pasted,
    Receiver,
)
from counterweight.focus import FocusHandle
from counterweight.hooks import Focus, Ref, use_effect, use_focus, use_ref, use_state
from counterweight.input_encoding import encode_key, encode_mouse, encode_paste

logger = logging.getLogger(__name__)

READ_SIZE = 2**16

# The shortest time between two snapshots of a busy terminal, so a program writing as fast as it can
# (`cat` of a big file) costs one snapshot per frame rather than one per read.
SNAPSHOT_INTERVAL = timedelta(milliseconds=1000 / 60)


@dataclass(slots=True)
class PtyConnection:
    """
    The master side of a running program's pseudo-terminal, which `use_pty`'s effect owns.
    Writes that the program isn't reading yet are buffered and flushed when the master is writable,
    so a handler never blocks the event loop.
    """

    master: int
    pid: int
    pending: bytearray = field(default_factory=bytearray)
    is_writing: bool = False

    def write(self, data: bytes) -> None:
        if not data:
            return
        self.pending += data
        self.flush()

    def flush(self) -> None:
        loop = asyncio.get_running_loop()
        try:
            written = os.write(self.master, self.pending)
        except BlockingIOError:
            written = 0
        except OSError:
            # The program exited and the slave side closed, so there's no one left to read this.
            self.pending.clear()
            written = 0
        del self.pending[:written]
        if self.pending and not self.is_writing:
            loop.add_writer(self.master, self.flush)
            self.is_writing = True
        elif not self.pending and self.is_writing:
            loop.remove_writer(self.master)
            self.is_writing = False

    def resize(self, columns: int, rows: int) -> None:
        """Sets the terminal's size, which sends the program `SIGWINCH`, as resizing a terminal window does."""
        fcntl.ioctl(self.master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))


def make_controlling_terminal() -> None:
    """In the child, after `setsid`: make its stdin, the pty's slave side, its controlling terminal."""
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


async def run_pty(
    argv: Sequence[str],
    columns: int,
    rows: int,
    env: Mapping[str, str] | None,
    on_output: Callable[[bytes], None],
    on_connect: Callable[[PtyConnection | None], None],
) -> int:
    """
    Runs `argv` on a new pseudo-terminal `columns` by `rows` in its own session, as its controlling terminal,
    calling `on_output` with what it writes, until it exits, returning its exit status.
    Cancelled, it hangs the program up (`SIGHUP` to its process group), as closing a terminal window does.
    """
    master, slave = os.openpty()
    os.set_blocking(master, False)
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))
    environment = {**os.environ, "TERM": "xterm-256color", "COLORTERM": "truecolor", **(env or {})}
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdin=slave,
        stdout=slave,
        stderr=slave,
        env=environment,
        start_new_session=True,
        preexec_fn=make_controlling_terminal,
    )
    os.close(slave)
    connection = PtyConnection(master=master, pid=process.pid)
    loop = asyncio.get_running_loop()
    closed = loop.create_future()

    def read() -> None:
        try:
            data = os.read(master, READ_SIZE)
        except BlockingIOError:
            return
        except OSError:  # EIO once the slave side closes, on Linux
            data = b""
        if not data:
            loop.remove_reader(master)
            if not closed.done():
                closed.set_result(None)
            return
        on_output(data)

    loop.add_reader(master, read)
    on_connect(connection)
    try:
        status = await process.wait()
        # Drain what the program wrote just before it exited.
        await asyncio.wait_for(asyncio.shield(closed), timeout=0.5)
        return status
    except asyncio.CancelledError, TimeoutError:
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGHUP)
            except ProcessLookupError:
                pass
        raise
    finally:
        on_connect(None)
        loop.remove_reader(master)
        if connection.is_writing:
            loop.remove_writer(master)
        os.close(master)


@dataclass(frozen=True, slots=True)
class Pty:
    """What `use_pty` returns: how to write to the program and resize its terminal, and whether it exited."""

    write: Callable[[bytes], None]
    exit_status: int | None
    """The program's exit status, or `None` while it's running (or before it starts)."""


def use_pty(
    argv: Sequence[str],
    columns: int,
    rows: int,
    on_output: Callable[[bytes], None],
    env: Mapping[str, str] | None = None,
) -> Pty:
    """
    Runs `argv` on a pseudo-terminal while the calling component is mounted, and again if `argv` changes,
    calling `on_output` with the bytes it writes (from an effect, not during a render),
    and keeping its terminal `columns` by `rows`.
    """
    connection: Ref[PtyConnection | None] = use_ref(None)
    initial_status: int | None = None
    exit_status, set_exit_status = use_state(initial_status)
    size = use_ref((columns, rows))
    size.current = (columns, rows)

    # Wrapped in a getter, since use_ref would call a bare callable as its initializer.
    def initial_output() -> Callable[[bytes], None]:
        return on_output

    output: Ref[Callable[[bytes], None]] = use_ref(initial_output)
    output.current = on_output

    def connect(c: PtyConnection | None) -> None:
        connection.current = c

    def forward(data: bytes) -> None:
        # Through the ref, so the latest render's callback gets the output, not the first one's.
        output.current(data)

    async def run() -> None:
        set_exit_status(None)
        status = await run_pty(argv, *size.current, env, on_output=forward, on_connect=connect)
        set_exit_status(status)

    use_effect(run, deps=(tuple(argv),))

    async def resize() -> None:
        if (c := connection.current) is not None and columns > 0 and rows > 0:
            c.resize(columns, rows)

    use_effect(resize, deps=(columns, rows))

    def write(data: bytes) -> None:
        if (c := connection.current) is not None:
            c.write(data)

    return Pty(write=write, exit_status=exit_status)


@dataclass(frozen=True, slots=True)
class EmbeddedTerminal:
    """What `use_terminal` returns to the calling component."""

    screen: Screen
    """What the program's terminal shows, as of the last snapshot."""

    view: ScreenView
    """The painter for the `Canvas` the calling component shows the terminal in, with the cursor drawn when focused."""

    exit_status: int | None
    focus: Focus

    on_input: InputHandler
    """
    The handler for the `Canvas`: while it's focused, it sends the program every key press and paste
    it has an encoding for, and claims them, so they don't bubble.
    It sends mouse events in the canvas to the program when the program asked for them,
    and focuses the canvas on a press.
    Put a handler before it with `first` to take keys before the program sees them, as a multiplexer's prefix key does.
    """

    write: Callable[[bytes], None]


def use_terminal(
    argv: Sequence[str],
    columns: int,
    rows: int,
    env: Mapping[str, str] | None = None,
    auto_focus: bool = False,
    handle: FocusHandle | None = None,
) -> EmbeddedTerminal:
    """
    Runs `argv` on a pseudo-terminal `columns` by `rows`, emulating the terminal it draws on.

    The emulator is fed on the event loop as the program writes, and snapshotted into a `Screen` value at most once
    per `SNAPSHOT_INTERVAL`, which re-renders the calling component.
    """
    focus = use_focus(auto_focus=auto_focus, handle=handle)
    screen, set_screen = use_state(BLANK_SCREEN)
    emulator_ref: Ref[Emulator | None] = use_ref(None)
    scheduled = use_ref(False)
    last_snapshot = use_ref(0.0)

    def publish() -> None:
        scheduled.current = False
        if (emulator := emulator_ref.current) is not None:
            last_snapshot.current = asyncio.get_running_loop().time()
            set_screen(emulator.snapshot())

    def schedule_snapshot() -> None:
        if scheduled.current:
            return
        scheduled.current = True
        loop = asyncio.get_running_loop()
        wait = last_snapshot.current + SNAPSHOT_INTERVAL.total_seconds() - loop.time()
        if wait <= 0:
            loop.call_soon(publish)
        else:
            loop.call_later(wait, publish)

    def on_output(data: bytes) -> None:
        if (emulator := emulator_ref.current) is None:
            return
        emulator.feed(data)
        schedule_snapshot()

    pty = use_pty(argv, columns, rows, on_output=on_output, env=env)

    async def own_emulator() -> None:
        emulator = emulator_ref.current = Emulator(max(columns, 1), max(rows, 1), replies=pty.write)
        try:
            await asyncio.Event().wait()
        finally:
            emulator.close()
            emulator_ref.current = None

    use_effect(own_emulator, deps=(tuple(argv),))

    async def resize() -> None:
        if (emulator := emulator_ref.current) is not None and columns > 0 and rows > 0:
            emulator.resize(columns, rows)
            schedule_snapshot()

    use_effect(resize, deps=(columns, rows))

    modes = screen.modes

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=key):
                if not receiver.is_focused or (encoded := encode_key(key, modes)) is None:
                    return None
                pty.write(encoded)
                return ()
            case Pasted(text=text):
                if not receiver.is_focused:
                    return None
                pty.write(encode_paste(text, modes))
                return ()
            case _:
                return on_mouse(event, receiver)

    def on_mouse(event: MouseEvent, receiver: Receiver) -> InputResponse:
        position = receiver.relative(event.absolute)
        if not (0 <= position.x < screen.columns and 0 <= position.y < screen.rows) and not isinstance(
            event, MouseDown
        ):
            return None
        if (encoded := encode_mouse(event, position, modes)) is not None:
            pty.write(encoded)
            return FocusOn(focus.handle) if isinstance(event, MouseDown) else ()
        if isinstance(event, MouseDown):
            return FocusOn(focus.handle)
        return None

    return EmbeddedTerminal(
        screen=screen,
        view=ScreenView(screen=screen, show_cursor=focus.is_focused),
        exit_status=pty.exit_status,
        focus=focus,
        on_input=on_input,
        write=pty.write,
    )
