from __future__ import annotations

import logging
import shutil
import sys
from asyncio import Queue
from asyncio import QueueEmpty
from asyncio import TaskGroup
from asyncio import get_running_loop
from asyncio import timeout
from collections import deque
from collections.abc import Callable
from collections.abc import Collection
from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Mapping
from datetime import timedelta
from itertools import chain
from itertools import repeat
from signal import SIG_DFL
from signal import SIGINT
from signal import SIGWINCH
from signal import getsignal
from signal import signal
from types import FrameType
from typing import TextIO
from typing import assert_never
from weakref import WeakSet

import waxy

from counterweight._context_vars import current_event_queue
from counterweight._context_vars import current_use_mouse_listeners
from counterweight._utils import cancel_tasks
from counterweight._utils import drain_queue
from counterweight._utils import maybe_await
from counterweight.border_healing import heal_borders
from counterweight.clock import Clock
from counterweight.clock import Instant
from counterweight.clock import system_clock
from counterweight.components import Component
from counterweight.components import component
from counterweight.controls import AdvanceClock
from counterweight.controls import AnyControl
from counterweight.controls import Bell
from counterweight.controls import ClearFocus
from counterweight.controls import FocusNext
from counterweight.controls import FocusOn
from counterweight.controls import FocusPrevious
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
from counterweight.elements import Div
from counterweight.events import AnyEvent
from counterweight.events import Dummy
from counterweight.events import KeyPressed
from counterweight.events import MouseDown
from counterweight.events import MouseMoved
from counterweight.events import MouseScrolledDown
from counterweight.events import MouseScrolledLeft
from counterweight.events import MouseScrolledRight
from counterweight.events import MouseScrolledUp
from counterweight.events import MouseUp
from counterweight.events import Pasted
from counterweight.events import StateSet
from counterweight.events import TerminalResized
from counterweight.focus import Subtree
from counterweight.geometry import Position
from counterweight.hooks import Mouse
from counterweight.hooks.hooks import rects_in
from counterweight.hooks.hooks import scroll_in
from counterweight.hooks.impls import Hooks
from counterweight.hooks.impls import NodeKey
from counterweight.input import start_input_control
from counterweight.input import start_reading_keys
from counterweight.input import stop_input_control
from counterweight.input import stop_reading_keys
from counterweight.layout import NO_LAYOUTS
from counterweight.layout import Layouts
from counterweight.layout import LayoutTree
from counterweight.layout import ScrollRequest
from counterweight.layout import layout_changes
from counterweight.layout import prior_scrolls
from counterweight.logging import app_log_levels
from counterweight.logging import devlog
from counterweight.output import CLEAR_SCREEN
from counterweight.output import Frame
from counterweight.output import paint_to_instructions
from counterweight.output import start_bracketed_paste
from counterweight.output import start_mouse_tracking
from counterweight.output import start_output_control
from counterweight.output import stop_bracketed_paste
from counterweight.output import stop_mouse_tracking
from counterweight.output import stop_output_control
from counterweight.output import synchronized
from counterweight.output import title_instructions
from counterweight.paint import Paint
from counterweight.paint import diff_paint
from counterweight.paint import paint_layout
from counterweight.paint import runs_of
from counterweight.routing import Press
from counterweight.routing import RoutingTable
from counterweight.routing import UnsettledFocus
from counterweight.routing import named_key
from counterweight.routing import route_key
from counterweight.routing import route_mouse
from counterweight.shadow import ShadowTree
from counterweight.shadow import until_due
from counterweight.shadow import update_shadow
from counterweight.styles import Style

logger = logging.getLogger(__name__)


def start_handling_resize_signal(put_event: Callable[[AnyEvent], None]) -> None:
    signal(SIGWINCH, lambda _, __: put_event(TerminalResized()))


def stop_handling_resize_signal() -> None:
    signal(SIGWINCH, SIG_DFL)


type SignalHandler = Callable[[int, FrameType | None], object] | int | None


def start_handling_interrupt_signal(request_quit: Callable[[], object]) -> SignalHandler:
    """
    Makes the first interrupt `request_quit`, so ctrl+c quits the app and `app` returns,
    and returns the handler it replaced, which takes any interrupt after that,
    so a second ctrl+c still stops an app whose render loop is stuck and can't quit.
    """
    previous = getsignal(SIGINT)

    def interrupted(signum: int, frame: FrameType | None) -> None:
        signal(SIGINT, previous)
        request_quit()

    signal(SIGINT, interrupted)
    return previous


def stop_handling_interrupt_signal(previous: SignalHandler) -> None:
    signal(SIGINT, previous)


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


async def app(
    root: Component,
    output_stream: TextIO = sys.stdout,
    input_stream: TextIO = sys.stdin,
    headless: bool = False,
    dimensions: tuple[int, int] | None = None,
    autopilot: Iterable[AnyEvent | AnyControl] = (),
    check_purity: bool = False,
    clock: Clock = system_clock,
    log_levels: Mapping[str, int] = frozendict(),
    title: str | None = None,
) -> None:
    """
    Parameters:
        root: The root [component][counterweight.components.component] of the application, already called
            with its arguments, such as `app(root(path))`.
        output_stream: The stream to which the application will write its output.
        input_stream: The stream from which the application will read its input.
        headless: If `True`, the application will not attempt to read from the input stream or write to the output stream.
            This is primarily useful when combined with the `autopilot` parameter.
        dimensions: The dimensions of the terminal window, in characters.
            If `None`, the dimensions of the terminal window will be used.
        autopilot: An iterable of events and controls to be processed by the application.
            This is primarily useful for testing or generating screenshots programmatically.
            Note that the autopilot will not be processed until after the initial render cycle,
            and that using the autopilot does not automatically cause the application to quit!
        check_purity: If `True`, check that components are pure: that their output depends only on their arguments
            and their hooks. A render keeps the previous output of every component it doesn't re-run
            (because its state didn't change and its parent didn't re-run, or because it's a `memo` component
            whose arguments didn't change), so an impure one goes stale.
            With this on, each render is followed by a second one that re-runs every component
            against copies of its hooks, and if that builds a different tree, the application raises
            `ImpureComponent`, naming the first component whose output differs.
            Elements are compared with `==`, and where that fails, piece by piece,
            so handlers are compared by their code and the values they captured, since a re-run builds new ones.
            The second run also raises `InconsistentHookExecution` for a component that calls a different number
            of hooks, and computes each `use_memo` that keeps its cached value again,
            raising `StaleMemo` if the result differs, naming the component and the hook.
            It costs as much as a render that re-runs everything, so turn it on in tests rather than in production.
        clock: Where [`use_clock`][counterweight.hooks.use_clock] reads the time, once per render.
            Pass a [`frozen_clock`][counterweight.clock.frozen_clock] to make output that doesn't depend on
            when the application runs, such as a screenshot, and move it with the
            [`AdvanceClock`][counterweight.controls.AdvanceClock] control.
        log_levels: Levels by logger name, with `""` the root logger, as in `logging.config`,
            for the records the devlog captures while the app runs.
            They're merged over a base that captures counterweight's records and the app's own at every level,
            and everyone else's from `INFO` up, where the app's own are those of the top-level package
            of the module that defines `root`'s function (`__main__` for an app run as a script).
            Pass `{"some_library": logging.DEBUG}` to see a library's debug records too,
            or `{"my_app": logging.INFO}` to hide the app's own.
        title: The title to give the terminal window when the application starts,
            as [`SetTitle`][counterweight.controls.SetTitle] would, before the first frame is drawn.
            If `None`, the terminal keeps the title it has.
    """
    async with devlog(levels=app_log_levels(root.func.__module__, log_levels)):
        try:
            await render_loop(
                root, output_stream, input_stream, headless, dimensions, autopilot, check_purity, clock, title
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
    autopilot: Iterable[AnyEvent | AnyControl],
    check_purity: bool,
    clock: Clock,
    title: str | None,
) -> None:
    # Whether the screen may not show the current paint, so the next frame clears it and draws every cell,
    # instead of drawing only the cells that changed.
    should_clear = True

    def handle_screen_size_change(override: tuple[int, int] | None = None) -> tuple[Component, Paint, int, int]:
        nonlocal should_clear

        w, h = override or dimensions or shutil.get_terminal_size()
        should_clear = True

        return screen(screen_element_style(w, h)), Paint.blank(w, h), w, h

    @component
    def screen(style: Style) -> Div:
        return Div(children=(root,), style=style)

    logger.info("Application starting...")

    event_queue: Queue[AnyEvent] = Queue()
    current_event_queue.set(event_queue)

    use_mouse_listeners: WeakSet[Callable[[Mouse], None]] = WeakSet()
    current_use_mouse_listeners.set(use_mouse_listeners)

    loop = get_running_loop()

    def put_event(event: AnyEvent) -> None:
        loop.call_soon_threadsafe(event_queue.put_nowait, event)

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

    # Taking output control is the first thing the try does, since the finally block hands it back,
    # and restoring a title the app never saved would pop one off the terminal's title stack that isn't the app's.
    try:
        if not headless:
            start_output_control(stream=output_stream)
            start_mouse_tracking(stream=output_stream)
            start_bracketed_paste(stream=output_stream)

        root_component, current_paint, w, h = handle_screen_size_change()

        should_render = True
        dirty: set[NodeKey] = set()

        should_quit = False
        should_bell = False
        pending_screenshots: list[Screenshot] = []
        should_suspend: Suspend | None = None

        # The title the terminal shows, which is the one it started with if it's None,
        # so the first pass of the loop sets the title `app` was given.
        shown_title: str | None = None

        do_heal_borders = True

        started = clock()
        clock_offset = timedelta()

        def read_clock() -> Instant:
            """The time now, moved on by any `AdvanceClock`, with its monotonic time measured from the start."""
            reading = clock()
            return Instant(
                wall=reading.wall + clock_offset,
                monotonic=reading.monotonic - started.monotonic + clock_offset,
            )

        # Warmup: render and lay out once without painting so that use_rects()
        # returns real dimensions on the first visible render.
        layout_tree = LayoutTree()
        warmup = update_shadow(root_component, None, NO_LAYOUTS, instant=read_clock())
        shadow = warmup.tree
        layouts = layout_tree.compute(layout_changes(None, shadow), shadow, w, h, {})
        routing = RoutingTable.of(shadow, layouts)
        focused = routing.reconciled_focus(None, warmup.mounted)
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
            nonlocal should_suspend
            nonlocal title

            nonlocal do_heal_borders
            nonlocal clock_offset
            nonlocal routing

            match control:
                case Quit():
                    should_quit = True
                case Bell():
                    should_bell = True
                case SetTitle():
                    title = control.title
                case RestoreTitle():
                    title = None
                case Screenshot():
                    pending_screenshots.append(control)
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
                    refocus(routing.focus_keys.get(handle, focused))
                case ClearFocus():
                    refocus(None)
                case AdvanceClock(by=by):
                    clock_offset += by
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

        async with TaskGroup() as tg:
            for ap in chain(autopilot, repeat(None)):  # pragma: no branch
                if should_quit:
                    logger.info("Quitting application...")
                    raise KeyboardInterrupt

                if should_bell:
                    if not headless:
                        output_stream.write("\a")
                        output_stream.flush()
                    should_bell = False

                if pending_screenshots:
                    # A copy, so a screenshot handler that changes its frame can't change current_paint.
                    frame = Frame(paint=current_paint.copy())
                    for screenshot in pending_screenshots:
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

                    if not headless:
                        stop_reading_keys(key_reader)
                        stop_bracketed_paste(stream=output_stream)
                        stop_mouse_tracking(stream=output_stream)
                        stop_output_control(stream=output_stream)
                        stop_input_control(stream=input_stream, original=original)
                        stop_handling_resize_signal()
                        stop_handling_interrupt_signal(previous_interrupt_handler)
                    is_suspended = True

                    try:
                        await maybe_await(should_suspend.handler())
                    except Exception as ex:  # noqa: BLE001 (a failing user handler is logged, not fatal)
                        logger.error(
                            "Error in suspend handler", extra={"handler": should_suspend.handler, "error": repr(ex)}
                        )

                    is_suspended = False
                    if not headless:
                        original = start_input_control(stream=input_stream)
                        previous_interrupt_handler = start_handling_interrupt_signal(request_quit=quit_from_signal)
                        start_handling_resize_signal(put_event=put_event)
                        start_output_control(stream=output_stream)
                        start_mouse_tracking(stream=output_stream)
                        start_bracketed_paste(stream=output_stream)
                        key_reader = start_reading_keys(stream=input_stream, put_event=event_queue.put_nowait)

                    root_component, current_paint, w, h = handle_screen_size_change()
                    rerun_everything()
                    shown_title = None

                    logger.debug("Resuming application", extra={"handler": should_suspend.handler})

                    should_suspend = None

                # After a suspension, so the app that resumes sets its title again.
                if not headless and title != shown_title:
                    output_stream.write(title_instructions(title))
                    output_stream.flush()
                    shown_title = title

                instant = read_clock()
                if should_render or until_due(shadow, instant) == timedelta():
                    previous_layouts = layouts
                    # Picked from the frame on screen, before the update below changes what's in it.
                    priors = prior_scrolls(layouts)
                    update = update_shadow(
                        root_component,
                        shadow,
                        layouts,
                        frozenset(dirty),
                        check_purity,
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
                        h,
                        priors,
                        scroll_requests(pending_scrolls, shadow),
                    )
                    logger.debug("Calculated layout")

                    routing = RoutingTable.of(shadow, layouts)
                    settled = routing.reconciled_focus(focused, update.mounted)

                    # Re-render the components whose focus changed before painting,
                    # so no frame shows focus where it was before the render moved it.
                    if settled != focused:
                        refocused = update_shadow(
                            root_component,
                            shadow,
                            previous_layouts,
                            frozenset(key for key in (focused, settled) if key is not None),
                            check_purity,
                            focused=settled,
                            instant=instant,
                        )
                        previous_shadow, shadow = shadow, refocused.tree
                        if settled is not None:
                            pending_scrolls.append(focus_into_view(settled))
                        layouts = layout_tree.compute(
                            layout_changes(previous_shadow, shadow),
                            shadow,
                            w,
                            h,
                            priors,
                            scroll_requests(pending_scrolls, shadow),
                        )
                        routing = RoutingTable.of(shadow, layouts)
                        if routing.reconciled_focus(settled, refocused.mounted) != settled:
                            raise UnsettledFocus(
                                "Focus changed again after re-rendering the components that gained and lost it, "
                                "so a component hid itself because it gained focus."
                            )
                        update = update.followed_by(refocused)
                        focused = settled
                        logger.debug("Settled focus", extra={"components_run": len(refocused.ran)})

                    pending_scrolls.clear()
                    for key in stale_readers(shadow, layouts):
                        event_queue.put_nowait(StateSet(key=key))

                    new_paint, border_healing_hints = paint_layout(
                        ((element, layout, lines) for _, element, layout, lines in layouts.in_paint_order),
                        w,
                        h,
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

                    diff = runs_of(new_paint) if should_clear else diff_paint(new_paint, current_paint)
                    current_paint = new_paint
                    logger.debug(
                        "Diffed new paint from current paint",
                        extra={"diff_runs": len(diff), "diff_cells": sum(len(cells) for _, _, cells in diff)},
                    )

                    # The clear goes in the same synchronized update as the frame, so the blank screen never shows.
                    instructions = synchronized((CLEAR_SCREEN if should_clear else "") + paint_to_instructions(diff))
                    should_clear = False
                    logger.debug("Generated instructions from paint diff")

                    if not headless:
                        output_stream.write(instructions)
                        output_stream.flush()
                        logger.debug(
                            "Wrote and flushed instructions to output stream", extra={"bytes": f"{len(instructions):_}"}
                        )

                    await handle_effects(ran=update.ran, unmounted=update.unmounted, task_group=tg)
                    logger.debug("Reconciled effects")

                    should_render = False

                    logger.debug("Completed render cycle")
                else:
                    # Without a render, every pending control moves nothing, and mustn't wait to move a later layout.
                    pending_scrolls.clear()

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
                try:
                    async with timeout(None if next_tick is None else next_tick.total_seconds()):
                        events = deque(await drain_queue(event_queue))
                except TimeoutError:
                    events = deque()

                while events:
                    event = events.popleft()

                    match event:
                        case StateSet(key=key):
                            should_render = True
                            dirty.add(key)
                        case TerminalResized(dimensions=override):
                            should_render = True
                            root_component, current_paint, w, h = handle_screen_size_change(override)
                            rerun_everything()
                        case KeyPressed() | Pasted():
                            for control in route_key(event, focused, routing):
                                handle_control(control)
                        case (
                            MouseMoved()
                            | MouseDown()
                            | MouseUp()
                            | MouseScrolledDown()
                            | MouseScrolledUp()
                            | MouseScrolledLeft()
                            | MouseScrolledRight()
                        ) as m:
                            press, controls = route_mouse(m, press, focused, routing)
                            for control in controls:
                                handle_control(control)

                            if isinstance(m, (MouseMoved, MouseDown, MouseUp)):
                                mouse = Mouse(
                                    absolute=m.absolute,
                                    motion=m.absolute - mouse_position,
                                    # We want the button attribute to reflect whether the button is *currently pressed*,
                                    # so on MouseUp the button should be None, not the button that was released.
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
    finally:
        logger.info("Application stopping...")

        if not headless and not is_suspended:
            # Stop reading input before handing the terminal back, so it can't take input meant for whatever runs next.
            stop_reading_keys(key_reader)
            stop_bracketed_paste(stream=output_stream)
            stop_mouse_tracking(stream=output_stream)
            stop_output_control(stream=output_stream)
            stop_input_control(stream=input_stream, original=original)
            stop_handling_resize_signal()
            stop_handling_interrupt_signal(previous_interrupt_handler)

        logger.info("Application stopped")


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
