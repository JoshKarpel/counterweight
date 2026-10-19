"""
[`use_terminal`][counterweight.headless.use_terminal], which runs an interactive program in a terminal it emulates,
sends it the input its component receives, and leaves drawing its screen to the component.
"""

from __future__ import annotations

from asyncio import TimerHandle
from asyncio import get_running_loop
from collections.abc import Callable
from collections.abc import Collection
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from counterweight._utils import forever
from counterweight.controls import FocusOn
from counterweight.emulator import BLANK_SCREEN
from counterweight.emulator import SNAPSHOT_INTERVAL
from counterweight.emulator import Emulator
from counterweight.emulator import Screen
from counterweight.events import InputEvent
from counterweight.events import InputHandler
from counterweight.events import InputResponse
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseEvent
from counterweight.events import MouseMoved
from counterweight.events import MouseUp
from counterweight.events import Pasted
from counterweight.events import Receiver
from counterweight.focus import FocusHandle
from counterweight.geometry import Position
from counterweight.hooks import Focus
from counterweight.hooks import Ref
from counterweight.hooks import use_effect
from counterweight.hooks import use_focus
from counterweight.hooks import use_ref
from counterweight.hooks import use_state
from counterweight.input_encoding import encode_focus
from counterweight.input_encoding import encode_key
from counterweight.input_encoding import encode_mouse
from counterweight.input_encoding import encode_paste
from counterweight.painters.terminal import ScreenView
from counterweight.pseudoterminal import HANGUP_GRACE
from counterweight.pseudoterminal import PtyStatus
from counterweight.pseudoterminal import Running
from counterweight.pseudoterminal import use_pty
from counterweight.styles.styles import Color


@dataclass(frozen=True, slots=True)
class EmbeddedTerminal:
    """What [`use_terminal`][counterweight.headless.use_terminal] returns to the calling component."""

    screen: Screen
    """What the program's terminal shows, as of the last snapshot, with its title and modes."""

    view: ScreenView
    """
    The painter for the [`Canvas`][counterweight.elements.Canvas] the calling component shows the terminal in,
    which draws the cursor while the component is focused.
    """

    status: PtyStatus
    """Whether the program is starting, running, or exited, or why it couldn't start."""

    focus: Focus
    """
    Whether the calling component is focused, and its focus handle,
    as [`use_focus`][counterweight.hooks.use_focus] returns them.
    """

    on_input: InputHandler
    """
    The handler for the canvas, which is the element the calling component returns.

    While the component is focused and the program is running, it sends the program every key press and paste,
    encoded as a terminal sends them for the modes the program set, and claims them, so they don't bubble:
    Ctrl+C and Ctrl+Z go to the program rather than to the app.
    It sends the program the mouse events on its screen that it asked for, translated to the screen's cells,
    and claims them; once it has claimed a press, the drag and release that follow are clamped to the screen's edges.
    A press anywhere on the canvas focuses the component, and one off the program's screen, such as on its border,
    only focuses it. It returns `None` for anything else, such as the wheel over a program that didn't ask for it.

    Put a handler before it with [`first`][counterweight.handlers.first] to take keys before the program sees them,
    as a multiplexer's prefix key does, or name keys in `skips` to let them bubble past it:
    the app needs some key the terminal doesn't claim to leave it.
    """

    write: Callable[[bytes], None]
    """
    Sends bytes to the program, as typing into its terminal does.
    It does nothing while the program isn't running, and is the same function on every render.
    """


@dataclass(frozen=True, slots=True)
class LiveEmulator:
    """The emulator of the program that's running, and what schedules a snapshot of it after it changes."""

    emulator: Emulator
    schedule_snapshot: Callable[[], None]


def use_terminal(
    argv: Sequence[str],
    columns: int,
    rows: int,
    env: Mapping[str, str] = frozendict(),
    clear_env: bool = False,
    cwd: Path | None = None,
    hangup_grace: timedelta = HANGUP_GRACE,
    foreground: Color = BLANK_SCREEN.foreground,
    background: Color = BLANK_SCREEN.background,
    auto_focus: bool = False,
    handle: FocusHandle | None = None,
    is_focusable: bool = True,
    in_focus_order: bool = True,
    skips: Collection[str] = frozenset(),
) -> EmbeddedTerminal:
    """
    Runs an interactive program, such as a shell or an editor, while the calling component is mounted,
    on a pseudo-terminal `columns` by `rows` (see [`use_pty`][counterweight.pseudoterminal.use_pty]),
    emulating the terminal it draws on, and sends it the input the component receives, as a terminal window
    or a multiplexer's pane does.
    It makes the component focusable, and leaves drawing the terminal to it:
    the component returns a [`Canvas`][counterweight.elements.Canvas] with the hook's `view` and `on_input`.

    The emulator is fed as the program writes, and snapshotted at most once a frame, which renders the component again.
    The emulator answers the program's queries, such as for the cursor's position, from its own state.
    A component that sizes the terminal from its own box, with `use_rects().content`, resizes the program's terminal
    along with it, which sends the program `SIGWINCH`; until the program redraws, the old screen shows,
    cropped or padded.
    While the component is focused and the program set `?1004`, it's sent focus events as the component gains and
    loses focus.

    Parameters:
        argv: The program and its arguments. A change hangs the program up and starts the new one,
            as a change to `env`, `clear_env` or `cwd` does.

        env: Passed to `use_pty`, as are `clear_env`, `cwd` and `hangup_grace`.

        foreground: What the program's default colors stand for wherever a cell has to name them,
            as for [`Emulator`][counterweight.emulator.Emulator], as `background` is.
            A change to either recolors the program's terminal, keeping what it shows.

        auto_focus: Passed to [`use_focus`][counterweight.hooks.use_focus], as are `handle`, `is_focusable`
            and `in_focus_order`.

        skips: Keys the program isn't sent, which `on_input` returns `None` for, so they bubble up to the app's
            handlers, as VS Code's terminal skips the keys bound to its own commands.
            An app that embeds a terminal and binds keys on an element around it, rather than before it,
            such as an app that embeds the whole app this terminal is in, skips those keys.
    """
    focus = use_focus(auto_focus=auto_focus, handle=handle, is_focusable=is_focusable, in_focus_order=in_focus_order)
    screen, set_screen = use_state(BLANK_SCREEN)
    live: Ref[LiveEmulator | None] = use_ref(None)

    def on_output(data: bytes) -> None:
        if (current := live.current) is None:  # pragma: no cover, output racing the emulator's teardown
            return
        current.emulator.feed(data)
        current.schedule_snapshot()

    pty = use_pty(argv, columns, rows, on_output, env=env, clear_env=clear_env, cwd=cwd, hangup_grace=hangup_grace)

    async def run_emulator() -> None:
        loop = get_running_loop()
        emulator = Emulator(
            max(columns, 1),
            max(rows, 1),
            on_reply=pty.write,
            foreground=foreground,
            background=background,
        )
        snapshot_due: TimerHandle | None = None
        last_snapshot = loop.time()

        def publish() -> None:
            nonlocal snapshot_due, last_snapshot
            snapshot_due = None
            last_snapshot = loop.time()
            set_screen(emulator.snapshot())

        def schedule_snapshot() -> None:
            nonlocal snapshot_due
            if snapshot_due is None:
                snapshot_due = loop.call_at(last_snapshot + SNAPSHOT_INTERVAL.total_seconds(), publish)

        live.current = LiveEmulator(emulator=emulator, schedule_snapshot=schedule_snapshot)
        try:
            set_screen(emulator.snapshot())
            await forever()
        finally:
            live.current = None
            if snapshot_due is not None:
                snapshot_due.cancel()
            emulator.close()

    # A program started again gets a fresh terminal, as use_pty starts it again, so these deps must stay use_pty's.
    use_effect(run_emulator, deps=(tuple(argv), env, clear_env, cwd))

    async def recolor() -> None:
        if (current := live.current) is None:  # pragma: no cover, a recolor racing the emulator's teardown
            return
        current.emulator.set_default_colors(foreground, background)
        current.schedule_snapshot()

    use_effect(recolor, deps=(foreground, background))

    async def resize() -> None:
        if columns <= 0 or rows <= 0 or (current := live.current) is None:
            return
        current.emulator.resize(columns, rows)
        current.schedule_snapshot()

    use_effect(resize, deps=(columns, rows))

    modes = screen.modes

    async def send_focus() -> None:
        if (encoded := encode_focus(focus.is_focused, modes)) is not None:
            pty.write(encoded)

    use_effect(send_focus, deps=(focus.is_focused,))

    is_running = isinstance(pty.status, Running)

    def on_input(event: InputEvent, receiver: Receiver) -> InputResponse:
        match event:
            case KeyPressed(key=key):
                if not (receiver.is_focused and is_running) or key in skips:
                    return None
                pty.write(encode_key(key, modes))
                return ()
            case Pasted(text=text):
                if not (receiver.is_focused and is_running):
                    return None
                pty.write(encode_paste(text, modes))
                return ()
            case _:
                return on_mouse(event, receiver)

    def on_mouse(event: MouseEvent, receiver: Receiver) -> InputResponse:
        focus_on = FocusOn(focus.handle) if isinstance(event, MouseDown) and is_focusable else None
        position = on_screen(event, receiver.relative(event.absolute), screen)
        if position is None or not is_running or (encoded := encode_mouse(event, position, modes)) is None:
            return focus_on
        pty.write(encoded)
        return (focus_on,)

    return EmbeddedTerminal(
        screen=screen,
        view=ScreenView(screen=screen, show_cursor=focus.is_focused),
        status=pty.status,
        focus=focus,
        on_input=on_input,
        write=pty.write,
    )


def on_screen(event: MouseEvent, position: Position, screen: Screen) -> Position | None:
    """
    Where `event`, at `position` from the canvas's content box, is on the program's screen, or `None` if it's off it.
    A drag or a release, which only reach the canvas after it claimed the press, are clamped to the screen's edges,
    as a terminal reports a drag that leaves its window.
    """
    if isinstance(event, MouseUp) or (isinstance(event, MouseMoved) and event.button is not None):
        if screen.columns == 0 or screen.rows == 0:
            return None
        return Position(min(max(position.x, 0), screen.columns - 1), min(max(position.y, 0), screen.rows - 1))
    if 0 <= position.x < screen.columns and 0 <= position.y < screen.rows:
        return position
    return None


__all__ = ["EmbeddedTerminal", "use_terminal"]
