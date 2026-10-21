from __future__ import annotations

import os
import signal
import sys
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Literal
from typing import TextIO

from counterweight._utils import maybe_await
from counterweight.focus import ElementHandle
from counterweight.focus import FocusHandle
from counterweight.focus import Subtree
from counterweight.geometry import Position
from counterweight.programs import EditOutcome
from counterweight.programs import ProgramOutcome
from counterweight.programs import TerminalStreams
from counterweight.programs import edit_file
from counterweight.programs import edit_text
from counterweight.programs import run_program

if TYPE_CHECKING:
    from counterweight._output import Frame


@dataclass(frozen=True, slots=True)
class _Control:
    pass


@dataclass(frozen=True, slots=True)
class Quit(_Control):
    """
    Cause the application to quit.

    The quit occurs at the beginning of the next render cycle,
    so all other events that are due to be processed in the current cycle
    will be processed before the application exits.
    """


@dataclass(frozen=True, slots=True)
class Bell(_Control):
    """
    Cause the terminal to emit a bell sound.

    The bell occurs at the beginning of the next render cycle,
    so all other events that are due to be processed in the current cycle
    will be processed before the sound is played.
    """


@dataclass(frozen=True, slots=True)
class SetTitle(_Control):
    """
    Set the title of the terminal window.
    To set it when the application starts, pass `title` to `counterweight._app.app`.

    The title is set at the beginning of the next render cycle,
    so all other events that are due to be processed in the current cycle
    will be processed before it changes.
    Line breaks in the title show as spaces, and other control characters as symbols, such as `␛` for an escape.

    The application saves the title it started with, and restores it when it quits and while it's suspended,
    on terminals that support [xterm's title stack](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html)
    (those that don't keep the last title set).
    [`RestoreTitle`][counterweight.controls.RestoreTitle] restores it while the application runs.
    """

    title: str


@dataclass(frozen=True, slots=True)
class RestoreTitle(_Control):
    """
    Restore the title the terminal window had when the application started,
    undoing any [`SetTitle`][counterweight.controls.SetTitle],
    on terminals that support [xterm's title stack](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html).

    The title is restored at the beginning of the next render cycle,
    so all other events that are due to be processed in the current cycle
    will be processed before it changes.
    """


@dataclass(frozen=True, slots=True)
class CopyToClipboard(_Control):
    """
    Copy `text` to the system clipboard, as a browser's
    [`navigator.clipboard.writeText`](https://developer.mozilla.org/en-US/docs/Web/API/Clipboard/writeText) does,
    for an app's own "copy" buttons and key bindings.

    The text is copied at the beginning of the next render cycle,
    so all other events that are due to be processed in the current cycle
    will be processed before it's copied, and the last copy in a cycle wins.
    Copying `""` empties the clipboard.

    The app asks the terminal to set the clipboard with
    [OSC 52](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h3-Operating-System-Commands),
    so it works only where the terminal supports it, and the app can't tell whether it did.
    A terminal may turn it off, or ask before letting a program set the clipboard,
    and tmux passes it on only with `set -g set-clipboard on`
    (its default, `external`, ignores applications' requests).
    A headless app copies nothing, and a recording doesn't record the copy,
    since replaying it in a terminal would set the viewer's clipboard.
    """

    text: str


# How Screenshot.to_file encodes a frame, by the suffix of the path it writes to.
SCREENSHOT_ENCODINGS: dict[str, Callable[[Frame], str]] = {
    ".svg": lambda frame: frame.svg(),
    ".txt": lambda frame: frame.text(ansi=True),
}


@dataclass(frozen=True, slots=True)
class Screenshot(_Control):
    """
    Take a "screenshot" of the rendered UI,
    and pass it to the given `handler` callback function as a [`Frame`][counterweight.paint.Frame],
    which the handler can encode as an SVG image or as text.

    The screenshot is taken at the beginning of the next render cycle,
    so all other events that are due to be processed in the current cycle
    will be processed before the screenshot is taken
    (but the screenshot will still be of the UI from *before* the next render occurs!).
    Every screenshot requested in the same cycle receives the same frame.
    """

    handler: Callable[[Frame], Awaitable[None] | None]

    @classmethod
    def to_file(cls, path: Path) -> Screenshot:
        """
        A convenience method for producing a `Screenshot` that writes to the given `path`,
        encoded according to its suffix:
        `.svg` for an SVG image, or `.txt` for text with ANSI escape codes for colors and styles.

        Parameters:
            path: The path to write the screenshot to.
                Parent directories will be created if they do not exist.

        Raises:
            ValueError: If the path's suffix is neither `.svg` nor `.txt`.
        """
        try:
            encode = SCREENSHOT_ENCODINGS[path.suffix]
        except KeyError:
            raise ValueError(
                f"Can't tell how to encode a screenshot as {path.name!r}: "
                f"use a path ending in one of {sorted(SCREENSHOT_ENCODINGS)}"
            ) from None

        def handler(frame: Frame) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(encode(frame))

        return cls(handler=handler)

    @classmethod
    def to_stream(cls, stream: TextIO | None = None, ansi: bool = True) -> Screenshot:
        """
        A convenience method for producing a `Screenshot` that prints the frame as text to the given `stream`.

        Parameters:
            stream: The stream to print to. Defaults to `sys.stderr`.
            ansi: Whether to include ANSI escape codes for colors and styles.
        """
        target = stream if stream is not None else sys.stderr

        def handler(frame: Frame) -> None:
            print(frame.text(ansi=ansi), file=target, flush=True)

        return cls(handler=handler)


@dataclass(frozen=True, slots=True)
class Suspend(_Control):
    """
    Suspend the application while the handler function is running,
    handing the terminal back to whatever started the application, and taking it again when the handler returns.
    The handler receives the terminal, as [`TerminalStreams`][counterweight.programs.TerminalStreams].

    The application will be suspended (and then resumed) at the beginning of the next render cycle,
    so all other events that are due to be processed in the current cycle
    will be processed before the application is suspended.
    """

    handler: Callable[[TerminalStreams], Awaitable[None] | None]

    @classmethod
    def to_shell(cls) -> Suspend:
        """
        A `Suspend` that stops the application as a shell job, as Ctrl+Z stops a program in a terminal,
        so the shell takes the terminal back, until it resumes the application with `fg`.
        It's what Ctrl+Z does by default (see `unclaimed_keys` on `counterweight._app.app`).

        It stops the application's whole process group, as the terminal's Ctrl+Z does,
        so whatever started the application and waits on it, such as `uv run`, stops too,
        which is what tells the shell to take the terminal back.
        """
        return cls(handler=stop_process_group)

    @classmethod
    def to_program(
        cls,
        argv: Sequence[str],
        on_exit: Callable[[ProgramOutcome], Awaitable[None] | None] = lambda outcome: None,
        env: Mapping[str, str] = frozendict(),
        clear_env: bool = False,
        cwd: Path | None = None,
    ) -> Suspend:
        """
        A `Suspend` that runs `argv` on the application's terminal until it exits, such as a pager or an editor,
        then calls `on_exit` with how it exited, or why it couldn't start, before the application takes the terminal back.
        See [`run_program`][counterweight.programs.run_program] for `env`, `clear_env` and `cwd`,
        and for what Ctrl+C and Ctrl+Z do while the program runs.
        """
        return cls(
            handler=partial(report_program, argv=tuple(argv), on_exit=on_exit, env=env, clear_env=clear_env, cwd=cwd)
        )

    @classmethod
    def to_edit_file(
        cls,
        path: Path,
        on_exit: Callable[[ProgramOutcome], Awaitable[None] | None] = lambda outcome: None,
        editor: Sequence[str] | None = None,
    ) -> Suspend:
        """
        A `Suspend` that edits the file at `path` in the user's editor on the application's terminal,
        then calls `on_exit` with how the editor exited, or why it couldn't start,
        before the application takes the terminal back.
        See [`edit_file`][counterweight.programs.edit_file] for `editor`.
        """
        return cls(
            handler=partial(
                report_file_edit, path=path, on_exit=on_exit, editor=None if editor is None else tuple(editor)
            )
        )

    @classmethod
    def to_edit_text(
        cls,
        text: str,
        on_edit: Callable[[EditOutcome], Awaitable[None] | None],
        file_name: str = "edit.txt",
        editor: Sequence[str] | None = None,
    ) -> Suspend:
        """
        A `Suspend` that edits `text` in the user's editor on the application's terminal,
        then calls `on_edit` with the edited text, or how the edit failed,
        before the application takes the terminal back.
        See [`edit_text`][counterweight.programs.edit_text] for `file_name` and `editor`.
        """
        return cls(
            handler=partial(
                report_edit,
                text=text,
                on_edit=on_edit,
                file_name=file_name,
                editor=None if editor is None else tuple(editor),
            )
        )


def stop_process_group(terminal: TerminalStreams) -> None:
    """Stops this process's process group, as the terminal's Ctrl+Z does, until something sends it `SIGCONT`."""
    # The suite runs this only in a child process that it stops and then kills, which never writes its coverage.
    os.killpg(os.getpgrp(), signal.SIGTSTP)  # pragma: no cover


async def report_program(
    terminal: TerminalStreams,
    argv: tuple[str, ...],
    on_exit: Callable[[ProgramOutcome], Awaitable[None] | None],
    env: Mapping[str, str],
    clear_env: bool,
    cwd: Path | None,
) -> None:
    """The handler of `Suspend.to_program`: runs `argv` on `terminal`, then passes `on_exit` how it ended."""
    await maybe_await(on_exit(await run_program(argv, terminal, env=env, clear_env=clear_env, cwd=cwd)))


async def report_file_edit(
    terminal: TerminalStreams,
    path: Path,
    on_exit: Callable[[ProgramOutcome], Awaitable[None] | None],
    editor: tuple[str, ...] | None,
) -> None:
    """The handler of `Suspend.to_edit_file`: edits `path` on `terminal`, then passes `on_exit` how the editor ended."""
    await maybe_await(on_exit(await edit_file(path, terminal, editor=editor)))


async def report_edit(
    terminal: TerminalStreams,
    text: str,
    on_edit: Callable[[EditOutcome], Awaitable[None] | None],
    file_name: str,
    editor: tuple[str, ...] | None,
) -> None:
    """The handler of `Suspend.to_edit_text`: edits `text` on `terminal`, then passes `on_edit` how the edit ended."""
    await maybe_await(on_edit(await edit_text(text, terminal, file_name=file_name, editor=editor)))


@dataclass(frozen=True, slots=True)
class ToggleBorderHealing(_Control):
    """Toggle whether border healing occurs."""


@dataclass(frozen=True, slots=True)
class FocusNext(_Control):
    """
    Move focus to the next visible component in the focus order, in tree order, wrapping from the last to the first.
    From nothing focused, or from focus outside `within`, it focuses the first.
    From a focused component that's out of the focus order (see `in_focus_order` on
    [`use_focus`][counterweight.hooks.use_focus]), it moves from that component's place in tree order.
    It does nothing if `within` has unmounted or holds no visible component in the focus order.
    """

    within: ElementHandle | Subtree | None = None
    """
    The element whose focusable descendants, and itself if it's focusable, focus moves among,
    usually the [`subtree`][counterweight.events.Receiver.subtree] of the handler's receiver,
    or an element's handle, from code with no receiver, such as an effect,
    or `None` for the whole tree.
    """


@dataclass(frozen=True, slots=True)
class FocusPrevious(_Control):
    """
    Move focus to the previous visible component in the focus order, in tree order, wrapping from the first to the last.
    From nothing focused, or from focus outside `within`, it focuses the last.
    Otherwise it behaves like [`FocusNext`][counterweight.controls.FocusNext].
    """

    within: ElementHandle | Subtree | None = None
    """
    The element whose focusable descendants, and itself if it's focusable, focus moves among,
    by its subtree or its handle, or `None` for the whole tree.
    """


@dataclass(frozen=True, slots=True)
class FocusOn(_Control):
    """
    Focus the component whose [`use_focus`][counterweight.hooks.use_focus] has `handle`,
    whether or not it's in the focus order.

    If no component can take focus with `handle` yet, such as one that mounts in the render
    a state change beside this control causes, it focuses that component in the next render, before the frame is drawn,
    as `showModal` focuses a dialog's field as the dialog opens,
    unless another control moves focus first.
    Key presses that arrive before that render still go to the component focused when they arrive.
    It does nothing if its batch of input causes no render,
    or no component can take focus with `handle` after that render either,
    because it hasn't mounted, has unmounted, is hidden, or is unfocusable.
    """

    handle: FocusHandle


@dataclass(frozen=True, slots=True)
class ClearFocus(_Control):
    """Clear focus, so key presses go to the root component."""


@dataclass(frozen=True, slots=True)
class AdvanceClock(_Control):
    """
    Move the application's clock forward by `by`, as if that much more time had passed,
    and render the components whose [`use_clock`][counterweight.hooks.use_clock] that makes due.

    This is primarily useful in an autopilot, with a [`FrozenClock`][counterweight.clock.FrozenClock],
    to show how an app changes over time without waiting for it.
    """

    by: timedelta


@dataclass(frozen=True, slots=True)
class Marker(_Control):
    """
    Mark this point in the app's [`Recording`][counterweight.asciicast.Recording] with `label`,
    which asciinema-player shows as a chapter to jump to,
    such as each step of an autopilot's demo, or each view a user opens.
    It does nothing if the app isn't recording.
    """

    label: str = ""


@dataclass(frozen=True, slots=True)
class ScrollTo(_Control):
    """
    Scroll the scroll container `target` names so its offset is `x` and `y`,
    as the web's [`scrollTo`](https://developer.mozilla.org/en-US/docs/Web/API/Element/scrollTo) does,
    leaving an axis given as `None` where it is.
    The offset is clamped to the range the container scrolls through, from 0 to its
    [`max_offset`][counterweight.geometry.Scroll.max_offset],
    so a large `y` scrolls to the end.

    It applies to the layout of the next render, before that render paints,
    after [anchoring](../layout/scrolling.md#keeping-the-content-in-view) and sticking to the end,
    and in order with the other scroll controls returned since the last render,
    so a handler that returns it beside a state change scrolls the content that change lays out.
    It does nothing if `target` names no mounted, visible scroll container then.
    """

    target: ElementHandle | Subtree
    """
    The scroll container, by the [`ElementHandle`][counterweight.focus.ElementHandle] passed to its `handle`,
    or by the [`subtree`][counterweight.events.Receiver.subtree] of a handler's receiver.
    """
    x: int | None = None
    y: int | None = None

    def destination(self, offset: Position) -> Position:
        """Where this moves a container scrolled to `offset`, before clamping."""
        return Position(offset.x if self.x is None else self.x, offset.y if self.y is None else self.y)


@dataclass(frozen=True, slots=True)
class ScrollBy(_Control):
    """
    Scroll the scroll container `target` names by `x` columns and `y` rows,
    as the web's [`scrollBy`](https://developer.mozilla.org/en-US/docs/Web/API/Element/scrollBy) does:
    positive values move toward the end of the content, and negative ones toward its start.
    The offset is clamped, and the control applied, as [`ScrollTo`][counterweight.controls.ScrollTo]'s is.
    """

    target: ElementHandle | Subtree
    """The scroll container, named as [`ScrollTo`][counterweight.controls.ScrollTo] names it."""
    x: int = 0
    y: int = 0

    def destination(self, offset: Position) -> Position:
        """Where this moves a container scrolled to `offset`, before clamping."""
        return Position(offset.x + self.x, offset.y + self.y)


ScrollAlignment = Literal["start", "center", "end", "nearest"]
"""Where [`ScrollIntoView`][counterweight.controls.ScrollIntoView] puts an element in a scroll container's view."""


@dataclass(frozen=True, slots=True)
class ScrollIntoView(_Control):
    """
    Scroll each scroll container above the element `target` names so the element's border box is in view,
    from the innermost container out, as the web's
    [`scrollIntoView`](https://developer.mozilla.org/en-US/docs/Web/API/Element/scrollIntoView) does,
    aligning it as `block` says vertically and as `inline` says horizontally, with the web's defaults.
    On each axis, `"start"` puts the element's start edge at the start edge of the container's view,
    `"center"` its center at the view's center, and `"end"` its end edge at the view's end edge.
    `"nearest"` does whichever of `"start"` and `"end"` scrolls least,
    and doesn't scroll at all if the element is already wholly in view, or covers the whole view.
    Each offset is clamped to the range its container scrolls through.

    It applies as [`ScrollTo`][counterweight.controls.ScrollTo] does, to the layout of the next render,
    so a handler that returns it beside a state change, such as moving a highlight through a long list,
    shows the scroll in the same frame as the change.
    The element `target` names is the one with that element handle in the next render,
    so an element handle moved onto a newly highlighted element names the new one.
    It does nothing if `target` names no mounted, visible element then,
    and it stops at an element with [`clip_to_screen`](../layout/clipping.md#escaping-every-clip),
    since no container above that element clips it.
    """

    target: ElementHandle | Subtree
    """The element, named as [`ScrollTo`][counterweight.controls.ScrollTo] names a scroll container."""
    block: ScrollAlignment = "start"
    """Where to put the element vertically."""
    inline: ScrollAlignment = "nearest"
    """Where to put the element horizontally."""


AnyControl = (
    Quit
    | Bell
    | SetTitle
    | RestoreTitle
    | CopyToClipboard
    | Screenshot
    | Suspend
    | ToggleBorderHealing
    | FocusNext
    | FocusPrevious
    | FocusOn
    | ClearFocus
    | AdvanceClock
    | Marker
    | ScrollTo
    | ScrollBy
    | ScrollIntoView
)
"""Any control: what an input handler returns, what an autopilot sends, and what a `use_controls` sender sends."""


__all__ = [
    "AdvanceClock",
    "AnyControl",
    "Bell",
    "ClearFocus",
    "CopyToClipboard",
    "FocusNext",
    "FocusOn",
    "FocusPrevious",
    "Marker",
    "Quit",
    "RestoreTitle",
    "Screenshot",
    "ScrollAlignment",
    "ScrollBy",
    "ScrollIntoView",
    "ScrollTo",
    "SetTitle",
    "Suspend",
    "ToggleBorderHealing",
]
