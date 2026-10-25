from __future__ import annotations

import gc
import logging
import os
import sys
from asyncio import Queue
from asyncio import QueueEmpty
from asyncio import TaskGroup
from asyncio import get_running_loop
from asyncio import sleep
from asyncio import timeout
from collections import deque
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Collection
from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Mapping
from collections.abc import Sequence
from contextlib import AbstractContextManager
from contextlib import contextmanager
from contextlib import nullcontext
from dataclasses import dataclass
from dataclasses import replace
from datetime import timedelta
from itertools import chain
from itertools import groupby
from signal import SIG_DFL
from signal import SIGINT
from signal import SIGWINCH
from signal import getsignal
from signal import signal
from threading import get_ident
from types import FrameType
from typing import Literal
from typing import TextIO
from typing import assert_never
from weakref import WeakSet

import waxy

from counterweight._border_healing import heal_borders
from counterweight._capture import Capture
from counterweight._capture import resume_capturing
from counterweight._capture import start_capturing
from counterweight._capture import stop_capturing
from counterweight._context_vars import app_scope
from counterweight._input import start_input_control
from counterweight._input import start_reading_keys
from counterweight._input import stop_input_control
from counterweight._input import stop_reading_keys
from counterweight._input_parsing import parse_input
from counterweight._layout import NO_LAYOUTS
from counterweight._layout import Layouts
from counterweight._layout import LayoutTree
from counterweight._layout import ScrollRequest
from counterweight._layout import layout_changes
from counterweight._layout import prior_scrolls
from counterweight._logging import app_log_levels
from counterweight._logging import devlog
from counterweight._output import CLEAR_SCREEN
from counterweight._output import ERASE_DOWN
from counterweight._output import REQUEST_CURSOR_POSITION
from counterweight._output import CursorMoves
from counterweight._output import Frame
from counterweight._output import clipboard_instructions
from counterweight._output import leave_region
from counterweight._output import output_control_start
from counterweight._output import paint_to_instructions
from counterweight._output import plain_rows
from counterweight._output import printed_rows
from counterweight._output import region_change
from counterweight._output import start_bracketed_paste
from counterweight._output import start_mouse_tracking
from counterweight._output import start_output_control
from counterweight._output import stop_bracketed_paste
from counterweight._output import stop_mouse_tracking
from counterweight._output import stop_output_control
from counterweight._output import synchronized
from counterweight._output import title_instructions
from counterweight._paint import DEFAULT_CELL_ASPECT_RATIO
from counterweight._paint import Paint
from counterweight._paint import Run
from counterweight._paint import diff_paint
from counterweight._paint import paint_layout
from counterweight._paint import paint_of_rows
from counterweight._paint import runs_of
from counterweight._paint import with_height
from counterweight._routing import Press
from counterweight._routing import RoutingTable
from counterweight._routing import named_key
from counterweight._routing import route_key
from counterweight._routing import route_mouse
from counterweight._shadow import ShadowTree
from counterweight._shadow import check_is_pure
from counterweight._shadow import until_due
from counterweight._shadow import update_shadow
from counterweight._utils import cancel_tasks
from counterweight._utils import drain_queue
from counterweight._utils import maybe_await
from counterweight._viewports import FullScreen
from counterweight._viewports import Inline
from counterweight._viewports import Viewport
from counterweight.asciicast import Recorder
from counterweight.asciicast import Recording
from counterweight.autopilot import Autopilot
from counterweight.autopilot import AutopilotStep
from counterweight.clock import Clock
from counterweight.clock import Instant
from counterweight.clock import SystemClock
from counterweight.clock import reading
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import AdvanceClock
from counterweight.controls import AnyControl
from counterweight.controls import Bell
from counterweight.controls import ClearFocus
from counterweight.controls import CopyToClipboard
from counterweight.controls import FocusNext
from counterweight.controls import FocusOn
from counterweight.controls import FocusPrevious
from counterweight.controls import Marker
from counterweight.controls import Print
from counterweight.controls import PrintStream
from counterweight.controls import Quit
from counterweight.controls import RestoreTitle
from counterweight.controls import Screenshot
from counterweight.controls import ScrollBy
from counterweight.controls import ScrollIntoView
from counterweight.controls import ScrollTo
from counterweight.controls import SetTitle
from counterweight.controls import Suspend
from counterweight.controls import ToggleBorderHealing
from counterweight.controls import _Control
from counterweight.elements import AnyElement
from counterweight.elements import Div
from counterweight.elements import Text
from counterweight.emulator import Emulator
from counterweight.events import AnyEvent
from counterweight.events import ControlSent
from counterweight.events import CursorPositionReported
from counterweight.events import Dummy
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseEvent
from counterweight.events import MouseMoved
from counterweight.events import MouseScrolledDown
from counterweight.events import MouseScrolledLeft
from counterweight.events import MouseScrolledRight
from counterweight.events import MouseScrolledUp
from counterweight.events import MouseUp
from counterweight.events import Pasted
from counterweight.events import StateSet
from counterweight.events import TerminalResized
from counterweight.focus import FocusHandle
from counterweight.focus import Subtree
from counterweight.focus import UnsettledFocus
from counterweight.geometry import Position
from counterweight.hooks import Mouse
from counterweight.hooks import UnsettledMeasurements
from counterweight.hooks._hooks import rects_in
from counterweight.hooks._hooks import scroll_in
from counterweight.hooks._impls import Hooks
from counterweight.hooks._impls import NodeKey
from counterweight.keys import Key
from counterweight.programs import TerminalStreams
from counterweight.styles import Style
from counterweight.styles.utilities import text_wrap_stable

logger = logging.getLogger(__name__)

UNKNOWN_TERMINAL_DIMENSIONS = (80, 24)
"""The dimensions of a stream that isn't a terminal, and of each that a terminal reports as 0, as `shutil`'s are."""

SETTLING_PASSES = 5
"""
How many times a frame re-renders the components whose focus or measurements changed before it paints anyway,
which leaves room for a chain of components that each measure what the one before placed, and a focus change on top.
"""


def terminal_dimensions(stream: TextIO) -> tuple[int, int]:
    """
    The columns and rows of the terminal `stream` writes to,
    so an app drawing on `/dev/tty` while its standard output is a pipe, as in `$(picker)`, fills the terminal.
    Unlike `shutil.get_terminal_size`, which asks standard output, this ignores `COLUMNS` and `LINES`,
    which describe the terminal when the process started and go stale once it resizes.
    """
    try:
        size = os.get_terminal_size(stream.fileno())
    # A stream with no file descriptor raises io.UnsupportedOperation, a closed one ValueError, a non-terminal OSError.
    except OSError, ValueError:
        return UNKNOWN_TERMINAL_DIMENSIONS
    columns, rows = UNKNOWN_TERMINAL_DIMENSIONS
    return size.columns or columns, size.lines or rows


def start_handling_resize_signal(put_event: Callable[[AnyEvent], None]) -> None:
    signal(SIGWINCH, lambda _, __: put_event(TerminalResized()))


def stop_handling_resize_signal() -> None:
    signal(SIGWINCH, SIG_DFL)


type SignalHandler = Callable[[int, FrameType | None], object] | int | None


def start_handling_interrupt_signal(request_quit: Callable[[], object]) -> SignalHandler:
    """
    Makes the first interrupt `request_quit`, so an interrupt sent from outside (`kill -INT`) quits the app
    and `app` returns, and returns the handler it replaced, which takes any interrupt after that,
    so a second one still stops an app whose render loop is stuck and can't quit.
    Ctrl+C is a key press, not an interrupt, since the app reads the terminal raw.
    """
    previous = getsignal(SIGINT)

    def interrupted(signum: int, frame: FrameType | None) -> None:
        signal(SIGINT, previous)
        request_quit()

    signal(SIGINT, interrupted)
    return previous


def stop_handling_interrupt_signal(previous: SignalHandler) -> None:
    signal(SIGINT, previous)


@contextmanager
def collection_paused() -> Iterator[None]:
    """
    Disables the cyclic garbage collector while the block runs, if it's enabled,
    and enables it again when the block exits, so it runs at the next allocation if the block's allocations call for it.
    A collector that's disabled when the block starts is left alone, since something else disabled it.
    """
    if not gc.isenabled():
        yield
        return

    gc.disable()
    try:
        yield
    finally:
        gc.enable()


DEFAULT_UNCLAIMED_KEYS: Mapping[str, AnyControl] = frozendict({Key.ControlC: Quit(), Key.ControlZ: Suspend.to_shell()})
"""
What `app` does with a key press no handler claims, by default:
Ctrl+C quits, and Ctrl+Z suspends the application as a shell job, as they do to a program in a terminal.
"""


def screen_element_style(width: int, height: int) -> Style:
    """
    The style of the element the app places the root component in:
    a single grid cell the size of the terminal, which the root stretches to fill.
    """
    return Style(
        # Explicit tracks keep the root's content from widening the cell,
        # which an implicit auto track would size to the root's min-content.
        layout=waxy.Style(
            display=waxy.Display.Grid,
            size_width=waxy.Length(width),
            size_height=waxy.Length(height),
            grid_template_columns=[waxy.Length(width)],
            grid_template_rows=[waxy.Length(height)],
        ),
    )


def region_element_style(width: int | None, max_height: int | None) -> Style:
    """
    The style of the element an inline app places the root component in, and what it prints:
    `width` wide, or as wide as its content if that's `None`,
    and as tall as the root, at most `max_height`, or as tall as it is if that's `None`.

    It's a flex column rather than a grid, so a root that can shrink, such as a scroll container, shrinks to fit,
    where a grid's auto row would keep the root as tall as its content and cut it off.
    The root stretches across its width whatever its content's width.
    """
    return Style(
        layout=waxy.Style(
            display=waxy.Display.Flex,
            flex_direction=waxy.FlexDirection.Column,
            size_width=waxy.AUTO if width is None else waxy.Length(width),
            max_size_height=waxy.AUTO if max_height is None else waxy.Length(max_height),
        ),
    )


def start_output(stream: TextIO, viewport: Viewport) -> None:
    """Takes the terminal's output over for an app drawing in `viewport`."""
    start_output_control(stream=stream, viewport=viewport)
    if tracks_mouse(viewport):
        start_mouse_tracking(stream=stream)
    start_bracketed_paste(stream=stream)


def stop_output(stream: TextIO, viewport: Viewport) -> None:
    """Hands the terminal's output back from an app drawing in `viewport`, undoing `start_output`."""
    stop_bracketed_paste(stream=stream)
    if tracks_mouse(viewport):
        stop_mouse_tracking(stream=stream)
    stop_output_control(stream=stream, viewport=viewport)


def tracks_mouse(viewport: Viewport) -> bool:
    """Whether an app drawing in `viewport` tracks the mouse."""
    match viewport:
        case FullScreen(mouse=mouse) | Inline(mouse=mouse):
            return mouse
        case _ as unreachable:
            assert_never(unreachable)


def next_region_top(top: int, move: RegionMove) -> int:
    """
    The screen row an inline region starts on after `move`, from the row `top` it started on:
    the rows printed above it push it down, and growing past the bottom of the screen scrolls it up.
    """
    printed, height, rows = move
    return min(top + printed, rows - height)


type RegionMove = tuple[int, int, int]
"""How a frame moved an inline region: the rows it printed above it, the region's height, and the screen's."""


@dataclass(frozen=True, slots=True)
class RegionTop:
    """
    The screen row an inline region that tracks the mouse starts on, or `None` until the terminal says where,
    and for each request for the cursor's position the terminal hasn't answered, oldest first,
    the moves of the frames since it, which the answer is moved by.
    The app asks after each frame that draws the region from scratch, where the cursor is at the region's top-left,
    and works out where the region is from the answer and the moves of the frames written since,
    since asking after every frame would cost a round trip to the terminal each time.
    """

    top: int | None = None
    unanswered: tuple[tuple[RegionMove, ...], ...] = ()

    def asked(self) -> RegionTop:
        """After a frame that drew the region from scratch and asked where it is."""
        return RegionTop(top=None, unanswered=(*self.unanswered, ()))

    def moved(self, move: RegionMove) -> RegionTop:
        """After a frame that moved the region by `move`."""
        return RegionTop(
            top=None if self.top is None else next_region_top(self.top, move),
            unanswered=tuple((*moves, move) for moves in self.unanswered),
        )

    def answered(self, row: int) -> RegionTop:
        """
        After the terminal said the cursor was on `row`, answering the oldest request.
        Only the answer to the latest request says where the region is now,
        since each request follows a frame that drew the region from scratch, wherever the one before left it.
        """
        if not self.unanswered:
            return self
        moves, *later = self.unanswered
        if later:
            return RegionTop(top=None, unanswered=tuple(later))
        top = row
        for move in moves:
            top = next_region_top(top, move)
        return RegionTop(top=top)

    def lost(self) -> RegionTop:
        """After the terminal was resized, which rewraps what's above the region and moves it where the app can't tell."""
        return RegionTop(top=None, unanswered=self.unanswered)


def on_viewport[M: MouseEvent](event: M, viewport: Viewport, region_top: int | None, is_pressed: bool) -> M | None:
    """
    `event`, which the terminal reports where it is on the screen, where it is on what the app draws:
    on an inline region, as far below the region's top as it is, starting on the screen row `region_top`,
    or `None` if the app doesn't know where the region is yet,
    or if it's above the region, over the scrollback, unless a press `is_pressed`,
    whose captor gets the rest of it wherever the pointer goes, as on the web.
    """
    match viewport:
        case FullScreen():
            return event
        case Inline():
            if region_top is None or (event.absolute.y < region_top and not is_pressed):
                return None
            return replace(event, absolute=event.absolute - Position(x=0, y=region_top))
        case _ as unreachable:
            assert_never(unreachable)


def layout_height(viewport: Viewport, height: int) -> int | None:
    """
    How tall the screen is that an app drawing in `viewport` on a terminal `height` rows tall lays its root out on:
    the terminal's height, or `None` for an inline region, which is as tall as the root.
    """
    match viewport:
        case FullScreen():
            return height
        case Inline():
            return None
        case _ as unreachable:
            assert_never(unreachable)


def cursor_moves(viewport: Viewport) -> CursorMoves:
    """How an app drawing in `viewport` moves the cursor between the cells it draws."""
    match viewport:
        case FullScreen():
            return "absolute"
        case Inline():
            return "relative"
        case _ as unreachable:
            assert_never(unreachable)


def frame_changes(viewport: Viewport, previous: Paint | None, paint: Paint) -> tuple[str, list[Run]]:
    """
    What a frame that draws `paint` in `viewport` writes before its cells, and the runs of cells it draws,
    when the screen shows `previous`, or may not show the last frame at all if it's `None`,
    so the frame clears it and draws every cell.

    An inline region's height changes with its content, so the frame first grows or shrinks it (see `region_change`),
    and then draws only the cells that differ from what's in its rows, erased cells in any rows it added.
    """
    match viewport:
        case FullScreen():
            if previous is None:
                return CLEAR_SCREEN, runs_of(paint)
            return "", diff_paint(paint, previous)
        case Inline():
            if previous is None:
                return region_change(None, paint.height), runs_of(paint)
            return region_change(previous.height, paint.height), diff_paint(paint, with_height(previous, paint.height))
        case _ as unreachable:
            assert_never(unreachable)


async def app(
    root: Component,
    output_stream: TextIO = sys.stdout,
    input_stream: TextIO = sys.stdin,
    headless: bool = False,
    dimensions: tuple[int, int] | None = None,
    autopilot: Iterable[AutopilotStep] = (),
    check_purity: bool = False,
    clock: Clock = SystemClock(),
    log_levels: Mapping[str, int] = frozendict(),
    title: str | None = None,
    unclaimed_keys: Mapping[str, AnyControl] = DEFAULT_UNCLAIMED_KEYS,
    cell_aspect_ratio: float = DEFAULT_CELL_ASPECT_RATIO,
    recording: Recording | None = None,
    clipboard_handler: Callable[[str], Awaitable[None] | None] | None = None,
    collect_garbage_between_frames: bool = True,
    viewport: FullScreen | Inline = FullScreen(),
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    capture_output: bool = True,
) -> None:
    """
    Parameters:
        root: The root [component][counterweight.components.component] of the application, already called
            with its arguments, such as `app(root(path))`.
        output_stream: The stream to which the application will write its output.
            To draw on the terminal while standard output is a pipe, as a picker run in `vim $(picker)` does,
            pass `/dev/tty` opened for writing.
        input_stream: The stream from which the application will read its input.
        headless: If `True`, the application will not attempt to read from the input stream or write to the output stream.
            This is primarily useful when combined with the `autopilot` parameter.
        dimensions: The dimensions of the terminal window, in characters.
            If `None`, the size of the terminal `output_stream` writes to, read again on each resize,
            or 80 by 24 if it isn't a terminal. The `COLUMNS` and `LINES` environment variables are ignored.
        autopilot: An iterable of events and controls to be processed by the application,
            and of [`Wait`][counterweight.autopilot.Wait] and [`WaitFor`][counterweight.autopilot.WaitFor],
            which hold the rest back until real time has passed or the screen shows something.
            This is primarily useful for testing or generating screenshots and recordings programmatically.
            Each step is handled once the renders the last one caused are painted,
            and the effects they started have run up to where each first waits on something,
            as a person's next key press would be.
            An app that never settles, such as one showing a program that prints without pause,
            holds a step back for at most [`SETTLE_LIMIT`][counterweight.autopilot.SETTLE_LIMIT] passes
            of the render loop, after which the autopilot takes it anyway.
            A `Wait` or `WaitFor` is checked on every pass, settled or not, so a `WaitFor` times out on time.
            Note that the autopilot will not be processed until after the initial render cycle,
            and that using the autopilot does not automatically cause the application to quit!
        check_purity: If `True`, check that components are pure: that their output depends only on their arguments
            and their hooks. A render keeps the previous output of every component it doesn't re-run
            (because its state didn't change and its parent didn't re-run, or because it's a `memo` component
            whose arguments didn't change), so an impure one goes stale.
            With this on, each frame's tree, once its focus and measurements settle, is built a second time,
            re-running every component against copies of its hooks, and if that builds a different tree,
            the application raises `ImpureComponent`, naming the first component whose output differs.
            Elements are compared with `==`, and where that fails, piece by piece,
            so handlers are compared by their code and the values they captured, since a re-run builds new ones.
            The second run also raises `InconsistentHookExecution` for a component that calls a different number
            of hooks, and computes each `use_memo` that keeps its cached value again,
            raising `StaleMemo` if the result differs, naming the component and the hook.
            A frame whose `use_rects` and `use_scroll` reads don't settle before it paints raises
            `UnsettledMeasurements`, rather than logging a warning and settling in the next frame.
            It costs as much as a render that re-runs everything, so turn it on in tests rather than in production.
        clock: Where [`use_clock`][counterweight.hooks.use_clock] reads the time, once per render.
            The [`SystemClock`][counterweight.clock.SystemClock] reads the time in UTC unless it's given a timezone.
            Pass a [`FrozenClock`][counterweight.clock.FrozenClock] to make output that doesn't depend on
            when the application runs, such as a screenshot, and move it with the
            [`AdvanceClock`][counterweight.controls.AdvanceClock] control.
        log_levels: Levels by logger name, with `""` the root logger, as in `logging.config`,
            for the records the devlog captures while the app runs.
            They're merged over a base that captures counterweight's records and the app's own at every level,
            and everyone else's from `INFO` up, where the app's own are those of the top-level package
            of the module that defines `root`'s function (`__main__` for an app run as a script).
            Pass `{"some_library": logging.DEBUG}` to see a library's debug records too,
            or `{"my_app": logging.INFO}` to hide the app's own.
            An app that runs while another has the devlog open, such as one run headless in another's handler,
            writes its records into that devlog, at the levels the other app set.
        title: The title to give the terminal window when the application starts,
            as [`SetTitle`][counterweight.controls.SetTitle] would, before the first frame is drawn.
            If `None`, the terminal keeps the title it has.
        unclaimed_keys: What a key press does when no handler claims it, by its key,
            as a browser takes a key's default action unless a listener prevents it.
            The application reads the terminal raw, so every key reaches it as a key press,
            including Ctrl+C and Ctrl+Z, which a terminal otherwise turns into signals,
            and the defaults, [`DEFAULT_UNCLAIMED_KEYS`][counterweight.DEFAULT_UNCLAIMED_KEYS],
            give those two what they'd do there:
            Ctrl+C returns [`Quit`][counterweight.controls.Quit],
            and Ctrl+Z [`Suspend.to_shell()`][counterweight.controls.Suspend.to_shell].
            A handler that claims one of those keys, such as one that passes keys on to a program,
            keeps it from taking its default.
            Pass `{}` to give unclaimed keys no defaults, or merge onto the defaults to change some,
            as in `DEFAULT_UNCLAIMED_KEYS | {Key.ControlQ: Quit()}`.
        cell_aspect_ratio: How many times taller than it is wide a cell of the terminal's font is,
            which [gradients][counterweight.gradients.Gradient] compute their angles and circles with,
            so that a 45 degree gradient or a circle looks like one.
            Most terminal fonts are about 2.
        recording: Where and how to record the application as an asciicast,
            which asciinema-player plays back, whether it's headless or not.
            If `None`, the application isn't recorded.
        clipboard_handler: What a [`CopyToClipboard`][counterweight.controls.CopyToClipboard] without a `handler`
            of its own does with its text, awaited if it returns an awaitable,
            such as `copied.append` in a test, which can't reach the controls the app's handlers return.
            If `None`, the text goes to the terminal's clipboard over OSC 52, or nowhere when headless.
            An error it raises is logged rather than stopping the app.
        collect_garbage_between_frames: If `True`, the default,
            Python's cyclic garbage collector doesn't run while a frame is generated,
            from re-running components to writing the frame to the terminal,
            and runs once after the frame is written instead, if the objects the frame allocated and didn't free
            call for it, as a browser schedules garbage collection in the idle time between frames.
            The temporary objects a frame frees before it ends then never trigger a collection,
            a frame that keeps enough for several triggers one,
            and the older generations, collected once every so many collections of the youngest,
            are collected less often, so cyclic garbage is freed later than it would be.
            Nothing frees the cyclic garbage a frame makes until the frame is written,
            so memory grows with every cycle a frame drops.
            The collector is paused for every thread of the process, not just the app's,
            and isn't touched by a frame that starts with it disabled, such as by `gc.disable()`,
            though a frame that paused it enables it again once it's written,
            even if another thread disabled it meanwhile.
            Pass `False` to let it run whenever it would,
            as an app whose frames make and drop a lot of cyclic garbage should
            (see [When not to pause it](performance.md#when-not-to-pause-it)).
        viewport: Where the application draws on its terminal:
            [`FullScreen`][counterweight.FullScreen], the whole of the alternate screen,
            or [`Inline`][counterweight.Inline], a region below the prompt as tall as the root's content,
            which stays in the terminal when the application stops.
        stdout: Where a [`Print`][counterweight.controls.Print] to `"stdout"` goes, as `print` writes to `sys.stdout`.
            A stream that's the application's terminal, `output_stream` itself or the same terminal device,
            shows what's printed above an inline application's region,
            and any other gets it as it is, as plain text if it isn't a terminal.
        stderr: Where a [`Print`][counterweight.controls.Print] to `"stderr"` goes, as `stdout` does for `"stdout"`.
        capture_output: If `True`, the default, `sys.stdout` and `sys.stderr` are replaced while the application runs,
            unless it's headless, with streams that print each line written to them,
            as a [`Print`][counterweight.controls.Print] of its text to `stdout` or `stderr`, from any thread,
            so a stray `print` or a warning doesn't land in the middle of what the application draws.
            They're put back while it's suspended, and when it stops, which writes out any line left unfinished.
            A program that writes to the terminal itself, rather than through `sys.stdout`, isn't caught.
    """
    async with devlog(levels=app_log_levels(root.func.__module__, log_levels)):
        try:
            await render_loop(
                root,
                output_stream,
                input_stream,
                headless,
                dimensions,
                autopilot,
                check_purity,
                clock,
                title,
                unclaimed_keys,
                cell_aspect_ratio,
                recording,
                clipboard_handler,
                collect_garbage_between_frames,
                viewport,
                {"stdout": stdout, "stderr": stderr},
                capture_output,
            )
        except BaseExceptionGroup as group:
            # The render loop's task group wraps even a lone error, which buries it in asyncio's frames
            # and keeps callers from catching it by its own type.
            if len(group.exceptions) != 1:
                raise
            error = group.exceptions[0]
        else:
            return

        # Raised outside the except block, so the group doesn't become the error's __context__.
        raise error


async def render_loop(
    root: Component,
    output_stream: TextIO,
    input_stream: TextIO,
    headless: bool,
    dimensions: tuple[int, int] | None,
    autopilot: Iterable[AutopilotStep],
    check_purity: bool,
    clock: Clock,
    title: str | None,
    unclaimed_keys: Mapping[str, AnyControl],
    cell_aspect_ratio: float,
    recording: Recording | None,
    clipboard_handler: Callable[[str], Awaitable[None] | None] | None,
    collect_garbage_between_frames: bool,
    viewport: Viewport,
    print_streams: Mapping[PrintStream, TextIO],
    capture_output: bool,
) -> None:
    # Whether the screen may not show the current paint, so the next frame clears it and draws every cell,
    # instead of drawing only the cells that changed.
    should_clear = True

    # Started once the clock and the screen's size are known, and stopped when the app stops.
    recorder: Recorder | None = None

    # What an inline app's terminal holds, fed what the app writes to it, headless or not,
    # which a screenshot that includes the scrollback shows.
    # Made once the screen's size is known, and closed when the app stops.
    emulator: Emulator | None = None

    region_top = RegionTop()

    def answer_from_emulator(reply: bytes) -> None:
        """A headless app's terminal is its emulator, so the emulator's replies to its queries are its input."""
        for event in parse_input(reply, is_final=True).events:
            event_queue.put_nowait(event)

    def handle_screen_size_change(override: tuple[int, int] | None = None) -> tuple[Component, Paint, int, int]:
        nonlocal should_clear
        nonlocal emulator
        nonlocal region_top

        w, h = override or dimensions or terminal_dimensions(output_stream)
        should_clear = True
        region_top = region_top.lost()
        if recorder is not None:
            recorder.resize(w, h)

        match viewport:
            case FullScreen():
                return screen(screen_element_style(w, h)), Paint.blank(w, h), w, h
            case Inline():
                if emulator is None:
                    emulator = Emulator(
                        w, h, on_reply=answer_from_emulator if headless else ignore_reply, scrollback=SCROLLBACK
                    )
                else:
                    emulator.resize(w, h)
                return screen(region_element_style(w, h)), Paint.blank(w, 0), w, h
            case _ as unreachable:
                assert_never(unreachable)

    def write(instructions: str) -> None:
        """Writes `instructions` to the terminal, unless the app is headless, and records them."""
        if not headless:
            output_stream.write(instructions)
            output_stream.flush()
        if emulator is not None:
            emulator.feed(instructions.encode())
        if recorder is not None:
            recorder.output(instructions)

    def frame_now(include_scrollback: bool) -> Frame:
        """
        What a screenshot shows: everything the terminal holds if it `include_scrollback` and the app is inline,
        and otherwise a copy of the frame on screen, so a handler that changes its frame can't change `current_paint`.
        """
        if include_scrollback and emulator is not None:
            return Frame(paint=paint_of_rows(emulator.history() + emulator.snapshot().lines, w))
        return Frame(paint=current_paint.copy())

    @component
    def screen(style: Style) -> Div:
        return Div(children=(root,), style=style)

    logger.info("Application starting...")

    event_queue: Queue[AnyEvent] = Queue()
    use_mouse_listeners: WeakSet[Callable[[Mouse], None]] = WeakSet()
    # Made before the warmup render, so the hooks can capture it, and entered before any effect starts in it.
    task_group = TaskGroup()

    def rendering() -> AbstractContextManager[None]:
        """What this app's components run in, so its hooks capture this app's queue, task group and listeners."""
        return app_scope(event_queue, task_group, use_mouse_listeners)

    loop = get_running_loop()

    def put_event(event: AnyEvent) -> None:
        loop.call_soon_threadsafe(event_queue.put_nowait, event)

    loop_thread = get_ident()

    def print_captured(line: str, stream: PrintStream) -> None:
        """
        Prints a line written to `sys.stdout` or `sys.stderr` while they're captured, from any thread.
        On the loop's thread it's queued at once, so a handler that prints and then quits prints before it quits.
        """
        event = ControlSent(control=Print(Text(content=line, style=text_wrap_stable), stream=stream))
        if get_ident() == loop_thread:
            event_queue.put_nowait(event)
        else:
            put_event(event)

    # The streams that replace `sys.stdout` and `sys.stderr` while the app runs, if it captures them.
    capture: Capture | None = None

    def start_capture() -> None:
        """
        Captures `sys.stdout` and `sys.stderr`, if the app does, with the same streams after a suspension,
        so code that kept a reference to one, such as a logging handler, is captured again too.
        """
        nonlocal capture
        if not capture_output or headless:
            return
        if capture is None:
            capture = start_capturing(print_captured)
        else:
            resume_capturing(capture)

    def stop_capture() -> None:
        if capture is not None:
            stop_capturing(capture)

    def quit_from_signal() -> None:
        """Quits as an autopilot `Quit` does, from a signal handler, which runs outside the loop."""

        def apply_quit() -> None:
            handle_control(Quit())
            event_queue.put_nowait(Dummy())

        loop.call_soon_threadsafe(apply_quit)

    if not headless:
        original = start_input_control(stream=input_stream)
        previous_interrupt_handler = start_handling_interrupt_signal(request_quit=quit_from_signal)
        start_handling_resize_signal(put_event=put_event)
        key_reader = start_reading_keys(stream=input_stream, put_event=event_queue.put_nowait)

    # Whether a suspension has handed the terminal back, so a suspend handler that raises an interrupt
    # doesn't hand it back again: restoring the title a second time would pop a title the app never saved.
    is_suspended = False

    print_targets = {name: print_target(stream, output_stream, headless) for name, stream in print_streams.items()}
    # The prints that arrived since the last frame, in order, which the next frame prints.
    pending_prints: list[Print] = []
    # What a full-screen app printed to its own terminal, which it holds until it hands the main screen back.
    held_prints: list[Print] = []

    def rendered(prints: Sequence[Print], width: int | None) -> Paint:
        """The contents of `prints`, rendered once at `width`, one below another (see `render_once`)."""
        with rendering():
            return render_once(
                [printed.content for printed in prints], width, read_clock(), cell_aspect_ratio, do_heal_borders
            )

    def print_pending() -> tuple[str, int]:
        """
        Prints what's pending, in order, returning the instructions that print what goes above an inline region,
        which go in the frame, and how many rows they print,
        and holding what a full-screen app prints to its own terminal.
        Each run of prints to the same stream is rendered at once, so a burst of lines builds one tree, not one each.
        """
        above = []
        rows = 0
        for name, run in groupby(pending_prints, key=lambda printed: printed.stream):
            prints = list(run)
            stream = print_streams[name]
            match print_targets[name]:
                case "screen" if isinstance(viewport, Inline):
                    paint = rendered(prints, w)
                    above.append(printed_rows(paint, "\r\n"))
                    rows += paint.height
                case "screen":
                    held_prints.extend(prints)
                case "terminal":
                    width = os.get_terminal_size(stream.fileno()).columns
                    stream.write(printed_rows(rendered(prints, width), "\n"))
                    stream.flush()
                case "text":
                    stream.write(plain_rows(rendered(prints, None)))
                    stream.flush()
                case _ as unreachable:
                    assert_never(unreachable)
        pending_prints.clear()
        return "".join(above), rows

    def print_sent_while_stopping() -> None:
        """
        Prints what was sent after the last frame, as the app stopped, such as a line an effect printed
        as the app cancelled it, above an inline region, which it draws again below what it printed.
        """
        while True:
            try:
                queued = event_queue.get_nowait()
            except QueueEmpty:
                break
            if isinstance(queued, ControlSent) and isinstance(queued.control, Print):
                pending_prints.append(queued.control)
        printed, _ = print_pending()
        if printed:
            before, diff = frame_changes(viewport, None, current_paint)
            write(synchronized(ERASE_DOWN + printed + before + paint_to_instructions(diff, cursor_moves(viewport))))

    def print_held() -> None:
        """
        Prints what a full-screen app held, on the main screen it has just handed back, at the terminal's width now.
        A headless app has no main screen to print on.
        """
        if held_prints and not headless:
            output_stream.write(printed_rows(rendered(held_prints, w), "\r\n"))
            output_stream.flush()
        held_prints.clear()

    # What the recording says the app exited with: 0 once it quits, and 1 if it stops any other way.
    exit_status = 1

    # Taking output control is the first thing the try does, since the finally block hands it back,
    # and restoring a title the app never saved would pop one off the terminal's title stack that isn't the app's.
    try:
        if not headless:
            start_output(stream=output_stream, viewport=viewport)
        start_capture()

        root_component, current_paint, w, h = handle_screen_size_change()

        should_render = True
        dirty: set[NodeKey] = set()

        should_quit = False
        should_bell = False
        pending_copy: CopyToClipboard | None = None
        pending_screenshots: list[Screenshot] = []
        should_suspend: Suspend | None = None

        # The title the terminal shows, which is the one it started with if it's None,
        # so the first pass of the loop sets the title `app` was given.
        shown_title: str | None = None

        do_heal_borders = True

        # Whether the last frame painted before its measurements or focus settled.
        was_unsettled = False

        pilot = Autopilot(steps=iter(autopilot))
        started = reading(clock, timedelta())
        clock_offset = timedelta()

        def read_clock() -> Instant:
            """
            The time now, after the autopilot's waits so far, moved on by any `AdvanceClock`,
            with its monotonic time measured from the start.
            """
            now = reading(clock, pilot.time_waited(loop.time()))
            return Instant(
                wall=now.wall + clock_offset,
                monotonic=now.monotonic - started.monotonic + clock_offset,
            )

        if recording is not None:
            recorder = Recorder.start(
                recording,
                elapsed=lambda: read_clock().monotonic,
                cols=w,
                rows=h,
                started=started.wall,
                preamble=output_control_start(viewport),
            )

        # Warmup: render and lay out once without painting so that use_rects()
        # returns real dimensions on the first visible render.
        layout_tree = LayoutTree()
        with rendering():
            warmup = update_shadow(root_component, None, NO_LAYOUTS, instant=read_clock())
        shadow = warmup.tree
        layouts = layout_tree.compute(layout_changes(None, shadow), shadow, w, layout_height(viewport, h), {})
        routing = RoutingTable.of(shadow, layouts)
        focused = routing.reconciled_focus(None, warmup.mounted, requested=None)
        # The handle of a `FocusOn` that named no focusable component when it arrived,
        # which the next render focuses if a component with it can take focus then.
        requested_focus: FocusHandle | None = None
        # The scroll controls to apply in the next layout, in order, including the ones focus moving adds.
        pending_scrolls: list[ScrollTo | ScrollBy | ScrollIntoView] = (
            [] if focused is None else [focus_into_view(focused)]
        )

        def rerun_everything() -> None:
            """Marks every node dirty, so the next render re-runs every component, `memo` ones included."""
            dirty.update(node.key for node in shadow.nodes)

        # The warmup started no effects, so the first painted frame has to re-run every component to start them.
        # It re-runs them with the focus the warmup reconciled, too.
        rerun_everything()

        def refocus(key: NodeKey | None) -> None:
            """
            Focuses the node with `key`, or nothing if it's `None`,
            and re-renders the mounted nodes that gain and lose focus, as a `use_state` setter would.
            """
            nonlocal focused
            nonlocal requested_focus

            # A later control that moves focus wins over a request that waits for the next render.
            requested_focus = None
            if key == focused:
                return

            for changed in (focused, key):
                if changed is not None:
                    event_queue.put_nowait(StateSet(key=changed))
            focused = key
            if key is not None:
                pending_scrolls.append(focus_into_view(key))

        def handle_control(control: AnyControl) -> None:
            nonlocal should_render

            nonlocal should_quit
            nonlocal should_bell
            nonlocal pending_copy
            nonlocal should_suspend
            nonlocal title

            nonlocal do_heal_borders
            nonlocal clock_offset
            nonlocal routing
            nonlocal requested_focus

            match control:
                case Quit():
                    should_quit = True
                case Bell():
                    should_bell = True
                case SetTitle():
                    title = control.title
                case RestoreTitle():
                    title = None
                case CopyToClipboard():
                    pending_copy = control
                case Screenshot():
                    pending_screenshots.append(control)
                case Print():
                    pending_prints.append(control)
                    should_render = True
                case Suspend():
                    should_suspend = control
                    should_render = True
                case ToggleBorderHealing():
                    do_heal_borders = not do_heal_borders
                    should_render = True
                case FocusNext(within=within):
                    refocus(routing.moved_focus(focused, within, is_forward=True))
                case FocusPrevious(within=within):
                    refocus(routing.moved_focus(focused, within, is_forward=False))
                case FocusOn(handle=handle):
                    if (key := routing.focus_keys.get(handle)) is not None:
                        refocus(key)
                    else:
                        requested_focus = handle
                case ClearFocus():
                    refocus(None)
                case AdvanceClock(by=by):
                    clock_offset += by
                case Marker(label=label):
                    if recorder is not None:
                        recorder.marker(label)
                case ScrollTo() | ScrollBy():
                    # Pending even if it moves nothing now, since a render this batch causes may give it room to.
                    pending_scrolls.append(control)
                    if (scrolled := routing.scrolled(control)) is not routing:
                        routing = scrolled
                        should_render = True
                case ScrollIntoView():
                    pending_scrolls.append(control)
                    should_render = True
                case _ as unreachable:
                    assert_never(unreachable)

        mouse_position = Position(x=-1, y=-1)
        press: Press | None = None

        def frame_on_screen() -> Frame:
            """A copy of the frame on screen, so a condition that changes its frame can't change `current_paint`."""
            return frame_now(include_scrollback=False)

        async with task_group:
            while True:
                if should_bell:
                    write("\a")
                    should_bell = False

                if pending_copy is not None:
                    copy, pending_copy = pending_copy, None
                    copy_handler = copy.handler if copy.handler is not None else clipboard_handler
                    if copy_handler is not None:
                        try:
                            await maybe_await(copy_handler(copy.text))
                            logger.debug("Copied text", extra={"handler": copy_handler})
                        except Exception as ex:  # noqa: BLE001 (a failing user handler is logged, not fatal)
                            logger.error("Error in copy handler", extra={"error": repr(ex), "handler": copy_handler})
                    elif not headless:
                        # Not through `write`, which records: a player replaying it would set the viewer's clipboard.
                        output_stream.write(clipboard_instructions(copy.text))
                        output_stream.flush()

                if pending_screenshots:
                    frames: dict[bool, Frame] = {}
                    for screenshot in pending_screenshots:
                        if (frame := frames.get(screenshot.include_scrollback)) is None:
                            frame = frames[screenshot.include_scrollback] = frame_now(screenshot.include_scrollback)
                        try:
                            await maybe_await(screenshot.handler(frame))
                            logger.debug("Took screenshot", extra={"handler": screenshot.handler})
                        except Exception as ex:  # noqa: BLE001 (a failing user handler is logged, not fatal)
                            logger.error(
                                "Error in screenshot handler", extra={"error": repr(ex), "handler": screenshot.handler}
                            )

                    pending_screenshots.clear()

                if should_suspend:
                    logger.debug("Suspending application", extra={"handler": should_suspend.handler})

                    # What arrived with the suspension prints before the program the app hands the terminal to,
                    # which starts where an inline region was.
                    printed, _ = print_pending()
                    if isinstance(viewport, Inline):
                        write(ERASE_DOWN + printed)
                    if not headless:
                        stop_reading_keys(key_reader)
                        stop_output(stream=output_stream, viewport=viewport)
                        stop_input_control(stream=input_stream, original=original)
                        stop_handling_resize_signal()
                        stop_handling_interrupt_signal(previous_interrupt_handler)
                    is_suspended = True
                    print_held()
                    stop_capture()
                    if recorder is not None:
                        recorder.suspend()

                    try:
                        await maybe_await(
                            should_suspend.handler(TerminalStreams(input=input_stream, output=output_stream))
                        )
                    except Exception as ex:  # noqa: BLE001 (a failing user handler is logged, not fatal)
                        logger.error(
                            "Error in suspend handler", extra={"handler": should_suspend.handler, "error": repr(ex)}
                        )

                    is_suspended = False
                    if recorder is not None:
                        recorder.resume()
                    if not headless:
                        original = start_input_control(stream=input_stream)
                        previous_interrupt_handler = start_handling_interrupt_signal(request_quit=quit_from_signal)
                        start_handling_resize_signal(put_event=put_event)
                        start_output(stream=output_stream, viewport=viewport)
                        key_reader = start_reading_keys(stream=input_stream, put_event=event_queue.put_nowait)
                    start_capture()

                    root_component, current_paint, w, h = handle_screen_size_change()
                    rerun_everything()
                    shown_title = None

                    logger.debug("Resuming application", extra={"handler": should_suspend.handler})

                    should_suspend = None

                # After a suspension, so the app that resumes sets its title again.
                if title != shown_title:
                    write(title_instructions(title))
                    shown_title = title

                # A handler above that set state queued a `StateSet`, which the render below shows,
                # so it's taken now rather than after the render, which would render again to show nothing new.
                carried: deque[AnyEvent] = deque()
                while True:
                    try:
                        queued = event_queue.get_nowait()
                    except QueueEmpty:
                        break
                    if isinstance(queued, StateSet):
                        should_render = True
                        dirty.add(queued.key)
                    else:
                        carried.append(queued)

                instant = read_clock()
                if should_render or until_due(shadow, instant) == timedelta():
                    # Nothing in the block awaits, so no other task runs with the collector paused.
                    with collection_paused() if collect_garbage_between_frames else nullcontext():
                        previous_layouts = layouts
                        # Picked from the frame on screen, before the update below changes what's in it.
                        priors = prior_scrolls(layouts)
                        with rendering():
                            update = update_shadow(
                                root_component,
                                shadow,
                                layouts,
                                frozenset(dirty),
                                focused=focused,
                                instant=instant,
                            )
                        dirty.clear()
                        previous_shadow, shadow = shadow, update.tree
                        logger.debug("Updated shadow tree", extra={"components_run": len(update.ran)})

                        layouts = layout_tree.compute(
                            layout_changes(previous_shadow, shadow),
                            shadow,
                            w,
                            layout_height(viewport, h),
                            priors,
                            scroll_requests(pending_scrolls, shadow),
                        )
                        logger.debug("Calculated layout")

                        routing = RoutingTable.of(shadow, layouts)
                        # The layouts the components in `shadow` read, which a purity check has to read too.
                        read_layouts = previous_layouts
                        mounted = update.mounted
                        passes = 0
                        is_refocus_only = False

                        # Re-render the components whose focus changed, or whose `use_rects` or `use_scroll` read went
                        # stale, and lay out again, before painting, as browsers deliver `ResizeObserver` notifications
                        # before they paint, so no frame shows focus or a measurement from before the render changed it.
                        while True:
                            settled = routing.reconciled_focus(focused, mounted, requested_focus)
                            requested_focus = None
                            if is_refocus_only and settled != focused:
                                raise UnsettledFocus(
                                    "Focus changed again after re-rendering the components that gained and lost it, "
                                    "so a component hid itself because it gained focus."
                                )
                            stale = frozenset(stale_readers(shadow, layouts))
                            refocused = (
                                frozenset(key for key in (focused, settled) if key is not None)
                                if settled != focused
                                else frozenset()
                            )
                            if not (stale or refocused) or passes == SETTLING_PASSES:
                                break

                            with rendering():
                                settling = update_shadow(
                                    root_component,
                                    shadow,
                                    layouts,
                                    stale | refocused,
                                    focused=settled,
                                    instant=instant,
                                )
                            read_layouts = layouts
                            previous_shadow, shadow = shadow, settling.tree
                            if refocused and settled is not None:
                                pending_scrolls.append(focus_into_view(settled))
                            layouts = layout_tree.compute(
                                layout_changes(previous_shadow, shadow),
                                shadow,
                                w,
                                layout_height(viewport, h),
                                priors,
                                scroll_requests(pending_scrolls, shadow),
                            )
                            routing = RoutingTable.of(shadow, layouts)
                            update = update.followed_by(settling)
                            mounted = settling.mounted
                            # Only a pass that re-rendered nothing but focus can be what moved it again.
                            is_refocus_only = not stale
                            focused = settled
                            passes += 1
                            logger.debug(
                                "Settled focus and measurements",
                                extra={"components_run": len(settling.ran), "stale_readers": len(stale)},
                            )

                        pending_scrolls.clear()

                        if check_purity:
                            with rendering():
                                check_is_pure(root_component, shadow, read_layouts, focused, instant)

                        # What's still unsettled renders in the next frame, which paints this one first.
                        if stale or refocused:
                            if check_purity and stale:
                                names = sorted(
                                    {
                                        reader.func.__qualname__
                                        for key in stale
                                        if (reader := shadow.by_key[key].component) is not None
                                    }
                                )
                                raise UnsettledMeasurements(
                                    f"{', '.join(names)} still read stale measurements after {SETTLING_PASSES} passes "
                                    "of re-rendering before painting, "
                                    "so a component's size may depend on what it measures."
                                )
                            # Once until a frame settles, since a component that never settles would warn every frame.
                            if not was_unsettled:
                                logger.warning(
                                    f"Painted a frame after {SETTLING_PASSES} passes of re-rendering "
                                    "without its measurements and focus settling, "
                                    "so a component's size may depend on what it measures "
                                    "(not repeated until a frame settles)",
                                    extra={"stale_readers": len(stale), "is_focus_settled": not refocused},
                                )
                            for key in stale:
                                event_queue.put_nowait(StateSet(key=key))
                            refocus(settled)
                        was_unsettled = bool(stale or refocused)

                        new_paint, border_healing_hints = paint_layout(
                            layouts.in_paint_order,
                            w,
                            layouts.by_key[shadow.root.key].border.height,
                            layout_tree.fields,
                            cell_aspect_ratio,
                        )
                        logger.debug("Generated new paint")

                        if do_heal_borders:
                            healing_diff = heal_borders(new_paint, border_healing_hints)
                            for position, cell in healing_diff.items():
                                new_paint[position] = cell
                            logger.debug(
                                "Healed borders in new paint",
                                extra={"hint_cells": len(border_healing_hints), "diff_cells": len(healing_diff)},
                            )

                        printed, printed_rows_count = print_pending()
                        was_cleared = should_clear
                        before, diff = frame_changes(
                            viewport, None if should_clear or printed else current_paint, new_paint
                        )
                        current_paint = new_paint
                        logger.debug(
                            "Diffed new paint from current paint",
                            extra={"diff_runs": len(diff), "diff_cells": sum(len(cells) for _, _, cells in diff)},
                        )

                        # A frame that changes nothing isn't written, so a recording doesn't play an empty one.
                        if diff or before:
                            # What goes before the cells, such as the clear, goes in the same synchronized update,
                            # so the blank screen never shows.
                            instructions = synchronized(
                                (ERASE_DOWN + printed if printed else "")
                                + before
                                + paint_to_instructions(diff, cursor_moves(viewport))
                            )
                            should_clear = False
                            logger.debug("Generated instructions from paint diff")

                            write(instructions)
                            if not headless:
                                logger.debug(
                                    "Wrote and flushed instructions to output stream",
                                    extra={"bytes": f"{len(instructions):_}"},
                                )

                            if isinstance(viewport, Inline) and viewport.mouse:
                                if was_cleared:
                                    # Asked while the cursor is at the region's first column, so the reply can't be
                                    # mistaken for a modified F3 (see `CURSOR_POSITION_REPORT`).
                                    write(REQUEST_CURSOR_POSITION)
                                    region_top = region_top.asked()
                                else:
                                    region_top = region_top.moved((printed_rows_count, new_paint.height, h))

                    # The app stops after this render, so the effects it would start never would.
                    if not should_quit:
                        await handle_effects(ran=update.ran, unmounted=update.unmounted, task_group=task_group)
                        logger.debug("Reconciled effects")

                    should_render = False

                    logger.debug("Completed render cycle")
                else:
                    # Without a render, every pending control moves nothing, and mustn't wait to move a later layout.
                    pending_scrolls.clear()
                    requested_focus = None

                # After the render, so the last frame shows the state the last handlers set,
                # which stays on the screen after an inline app stops.
                if should_quit:
                    logger.info("Quitting application...")
                    raise KeyboardInterrupt

                # Neither putting to nor getting from a queue that has room or items suspends,
                # so without this the effects the render started wouldn't run until the autopilot waited.
                await sleep(0)

                # The next step waits for the renders the last one caused, as a person's next key press would:
                # the ones that what the render measured or the effects it started queued.
                ap = pilot.next(loop.time(), frame=frame_on_screen, is_settled=not carried and event_queue.empty())
                if ap is not None:
                    if isinstance(ap, _Control):
                        handle_control(ap)
                        await event_queue.put(Dummy())  # Force a render cycle when the autopilot emits a control
                    else:  # i.e., an event
                        await event_queue.put(ap)
                    logger.debug("Handled autopilot command", extra={"command": ap})

                # Goal: wait for an event, then process all pending events, and any events created by those events,
                # until there are no more events immediately available in the queue.
                # This makes sure that (for example) if you use autopilot to press a key which causes a state change,
                # the state change will be processed before the next render cycle.
                # Note that there are some tricky async semantics here. Right now, event handlers are sync,
                # so there's no way for an effect to add events to the queue once we get past the `await drain_queue()` below,
                # since we don't await again until we hit this point again in the next render cycle.

                # With nothing in the queue, wake when a component's clock is due, so it can re-run.
                # The check above decides whether it is: the timer runs on the monotonic clock and ticks follow the
                # wall clock, so the timer can fire a little early while the system adjusts the wall clock.
                num_events_handled = 0
                next_tick = until_due(shadow, read_clock())
                wakes = [
                    seconds
                    for seconds in (
                        None if next_tick is None else next_tick.total_seconds(),
                        pilot.until_deadline(loop.time()),
                    )
                    if seconds is not None
                ]
                if carried:
                    # The events taken before the render go first, and the loop below takes what was queued since.
                    events = carried
                else:
                    try:
                        async with timeout(min(wakes, default=None)):
                            events = deque(await drain_queue(event_queue))
                    except TimeoutError:
                        events = deque()

                while events:
                    event = events.popleft()

                    match event:
                        case StateSet(key=key):
                            should_render = True
                            dirty.add(key)
                        case ControlSent(control=control):
                            handle_control(control)
                        case TerminalResized(dimensions=override):
                            should_render = True
                            root_component, current_paint, w, h = handle_screen_size_change(override)
                            rerun_everything()
                        case CursorPositionReported(position=position):
                            region_top = region_top.answered(position.y)
                        case KeyPressed() | Pasted():
                            if recorder is not None:
                                recorder.input(event)
                            for control in route_key(event, focused, routing, unclaimed_keys):
                                handle_control(control)
                        case (
                            MouseMoved()
                            | MouseDown()
                            | MouseUp()
                            | MouseScrolledDown()
                            | MouseScrolledUp()
                            | MouseScrolledLeft()
                            | MouseScrolledRight()
                        ) as on_screen:
                            if recorder is not None:
                                recorder.input(on_screen)
                            m = on_viewport(on_screen, viewport, region_top.top, is_pressed=press is not None)
                            if m is not None:
                                press, controls = route_mouse(m, press, focused, routing)
                                for control in controls:
                                    handle_control(control)

                                if isinstance(m, (MouseMoved, MouseDown, MouseUp)):
                                    mouse = Mouse(
                                        absolute=m.absolute,
                                        motion=m.absolute - mouse_position,
                                        # The button that's *currently pressed*,
                                        # so on MouseUp it's None, not the button that was released.
                                        button=m.button if not isinstance(m, MouseUp) else None,
                                    )
                                    for listener in use_mouse_listeners:
                                        listener(mouse)

                                mouse_position = m.absolute

                    while True:
                        try:
                            events.append(event_queue.get_nowait())
                        except QueueEmpty:
                            break

                    num_events_handled += 1

                logger.debug("Handled events", extra={"num_events": num_events_handled})

    except KeyboardInterrupt as ex:
        logger.debug(f"Caught {ex!r}")
        exit_status = 0
        # The task group has stopped the effects by now, which can print as they stop.
        if not is_suspended:
            print_sent_while_stopping()
    finally:
        logger.info("Application stopping...")

        # An inline app has an emulator once it knows where its region is, so one that failed before then drew none.
        if isinstance(viewport, Inline) and emulator is not None and not is_suspended:
            write(leave_region(current_paint.height, keep=viewport.keep_last_frame))

        if emulator is not None:
            emulator.close()

        if recorder is not None:
            recorder.stop(exit_status)

        if not headless and not is_suspended:
            # Stop reading input before handing the terminal back, so it can't take input meant for whatever runs next.
            stop_reading_keys(key_reader)
            stop_output(stream=output_stream, viewport=viewport)
            stop_input_control(stream=input_stream, original=original)
            stop_handling_resize_signal()
            stop_handling_interrupt_signal(previous_interrupt_handler)
        # The held prints render the app's components, which can raise, after the terminal is handed back,
        # and before the captured streams write out their unfinished lines, which came after them.
        try:
            if not is_suspended:
                print_held()
        finally:
            stop_capture()

        logger.info("Application stopped")


type PrintTarget = Literal["screen", "terminal", "text"]
"""
Where a print to one of the app's streams goes: the app's own terminal, above an inline region,
a terminal of its own, or a stream that isn't a terminal, such as a pipe or a file.
"""


def print_target(stream: TextIO, output_stream: TextIO, headless: bool) -> PrintTarget:
    """
    Where a print to `stream` goes, from an app drawing on `output_stream`:
    the app's terminal if `stream` is `output_stream`, or, unless the app is headless,
    the same terminal device, as standard output and standard error are at a prompt with nothing redirected.
    """
    if stream is output_stream:
        return "screen"
    if not stream.isatty():
        return "text"
    if not headless and is_same_terminal(stream, output_stream):
        return "screen"
    return "terminal"


def is_same_terminal(stream: TextIO, other: TextIO) -> bool:
    """Whether `stream`, a terminal, is the same terminal device as `other`."""
    return other.isatty() and os.fstat(stream.fileno()).st_rdev == os.fstat(other.fileno()).st_rdev


def render_once(
    contents: Sequence[Component | AnyElement],
    width: int | None,
    instant: Instant,
    cell_aspect_ratio: float,
    heal: bool,
) -> Paint:
    """
    `contents` rendered once, as React's `renderToStaticMarkup` does, one below another,
    `width` wide, or each as wide as it is if that's `None`, and as tall as they are:
    their components run with each hook's initial state, and their effects never start.
    Borders are healed if `heal` is set, as the app heals its own.

    Each is laid out as it would be alone, as the root of an inline region,
    and, among several, clipped to its own box, so nothing it draws outside it lands on another,
    as it would be dropped alone.
    """
    style = region_element_style(width, None) | (BATCH_AT_CONTENT_WIDTH if width is None else Style())
    children = (
        tuple(contents)
        if len(contents) == 1
        else tuple(Div(style=PRINTED_STYLE, children=(content,)) for content in contents)
    )
    root = Div(style=style, children=children)
    shadow = update_shadow(root, None, NO_LAYOUTS, instant=instant).tree
    tree = LayoutTree()
    layouts = tree.compute(layout_changes(None, shadow), shadow, width, None, {})
    border = layouts.by_key[shadow.root.key].border
    paint, hints = paint_layout(layouts.in_paint_order, border.width, border.height, tree.fields, cell_aspect_ratio)
    if heal:
        for position, cell in heal_borders(paint, hints).items():
            paint[position] = cell
    return paint


PRINTED_STYLE = Style(
    layout=waxy.Style(
        flex_direction=waxy.FlexDirection.Column, overflow_x=waxy.Overflow.Clip, overflow_y=waxy.Overflow.Clip
    )
)
"""
The style of the box around each of the contents `render_once` renders together:
a flex column, the context each would be laid out in alone, which clips what it holds to the box.
"""

BATCH_AT_CONTENT_WIDTH = Style(layout=waxy.Style(align_items=waxy.AlignItems.Start))
"""
What keeps each of the contents `render_once` renders at no width as wide as it is alone,
rather than stretched as wide as the widest.
"""

SCROLLBACK = 10_000
"""How many rows scrolled off the top of an inline app's terminal a screenshot that includes the scrollback shows."""


def ignore_reply(reply: bytes) -> None:
    """Drops a reply to a query the app wrote, which the terminal the app draws on answers instead."""


def focus_into_view(key: NodeKey) -> ScrollIntoView:
    """What focusing the node with `key` scrolls into view: the node, by as little as it takes, as browsers do."""
    return ScrollIntoView(Subtree(key=key), block="nearest", inline="nearest")


def scroll_requests(pending: Iterable[ScrollTo | ScrollBy | ScrollIntoView], shadow: ShadowTree) -> list[ScrollRequest]:
    """What `pending` asks of a layout of `shadow`, skipping a handle that names no mounted element."""
    return [
        ScrollRequest(key=key, control=control)
        for control in pending
        if (key := named_key(control.target, shadow.handled)) is not None
    ]


def stale_readers(shadow: ShadowTree, layouts: Layouts) -> Iterator[NodeKey]:
    """
    The keys of the nodes whose `use_rects` or `use_scroll` returned something different from what they'd read
    from `layouts`, so that they render again as soon as it changes, as a `ResizeObserver` reports a resize.
    """
    stale_rects = (
        node.key
        for node in shadow.measured
        if any(rects != rects_in(layouts, node.key, handle) for handle, rects in (node.hooks.rects or {}).items())
    )
    stale_scrolls = (
        node.key
        for node in shadow.scroll_readers
        if any(scroll != scroll_in(layouts, node.key, handle) for handle, scroll in (node.hooks.scrolls or {}).items())
    )
    return chain(stale_rects, stale_scrolls)


async def handle_effects(ran: Collection[Hooks], unmounted: Collection[Hooks], task_group: TaskGroup) -> None:
    """
    Restarts the effects of the components that `ran` whose deps changed, or that have none,
    and cancels every effect of the nodes that were `unmounted`.
    The effects of components that didn't run keep running.
    """
    reruns = [
        effect for hooks in ran for effect in hooks.effects if effect.new_deps is None or effect.deps != effect.new_deps
    ]
    stale = chain(
        (effect.task for effect in reruns if effect.task is not None),
        (effect.task for hooks in unmounted for effect in hooks.effects if effect.task is not None),
    )

    # Every stale task is cancelled before any rerun starts, so an effect holding something exclusive
    # (a subscription, a terminal mode) releases it before its replacement or a sibling acquires it.
    await cancel_tasks(stale)

    for effect in reruns:
        effect.deps = effect.new_deps
        effect.task = task_group.create_task(effect.setup())
