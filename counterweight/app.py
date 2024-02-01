from __future__ import annotations

import shutil
import sys
from asyncio import CancelledError, Queue, QueueEmpty, Task, TaskGroup, get_running_loop
from collections import deque
from collections.abc import Callable
from itertools import chain, repeat
from signal import SIG_DFL, SIGWINCH, signal
from threading import Event, Thread
from time import perf_counter_ns
from typing import Iterable, TextIO

from structlog import get_logger

from counterweight._context_vars import current_event_queue
from counterweight._utils import drain_queue, maybe_await
from counterweight.border_healing import heal_borders
from counterweight.components import Component, component
from counterweight.controls import AnyControl, Bell, Quit, Screenshot, Suspend, ToggleBorderHealing, _Control
from counterweight.elements import AnyElement, Div
from counterweight.events import (
    AnyEvent,
    Dummy,
    KeyPressed,
    MouseDown,
    MouseMoved,
    MouseUp,
    StateSet,
    TerminalResized,
)
from counterweight.geometry import Position
from counterweight.hooks.impls import UseEffect
from counterweight.input import read_keys, start_input_control, stop_input_control
from counterweight.layout import build_layout_tree_from_concrete_element_tree
from counterweight.logging import configure_logging
from counterweight.output import (
    CLEAR_SCREEN,
    paint_to_instructions,
    start_mouse_tracking,
    start_output_control,
    stop_mouse_tracking,
    stop_output_control,
)
from counterweight.paint import BLANK, Paint, paint_layout, svg
from counterweight.shadow import ShadowNode, update_shadow
from counterweight.styles import Span, Style
from counterweight.styles.styles import Flex

logger = get_logger()


def start_handling_resize_signal(put_event: Callable[[AnyEvent], None]) -> None:
    signal(SIGWINCH, lambda _, __: put_event(TerminalResized()))


def stop_handling_resize_signal() -> None:
    signal(SIGWINCH, SIG_DFL)


async def app(
    root: Callable[[], Component],
    output_stream: TextIO = sys.stdout,
    input_stream: TextIO = sys.stdin,
    headless: bool = False,
    dimensions: tuple[int, int] | None = None,
    autopilot: Iterable[AnyEvent | AnyControl] = (),
) -> None:
    """
    Parameters:
        root: The root [component][counterweight.components.component] of the application.
        output_stream: The stream to which the application will write its output.
        input_stream: The stream from which the application will read its input.
        headless: If `True`, the application will not attempt to read from the input stream or write to the output stream.
            This is primarily useful when combined with the `autopilot` parameter.
        dimensions: The dimensions of the terminal window, in characters.
            If `None`, the dimensions of the terminal window will be used.
            Note that if the terminal is resized, the application will still be notified and will update its dimensions accordingly.
        autopilot: An iterable of events and controls to be processed by the application.
            This is primarily useful for testing or generating screenshots programmatically.
            Note that the autopilot will not be processed until after the initial render cycle,
            and that using the autopilot does not automatically cause the application to quit!
    """
    configure_logging()

    w, h = dimensions or shutil.get_terminal_size()

    @component
    def screen() -> Div:
        return Div(
            children=[root()],
            style=Style(
                layout=Flex(
                    direction="column",
                    justify_children="start",
                    align_children="stretch",
                ),
                span=Span(
                    width=w,
                    height=h,
                ),
            ),
        )

    logger.info("Application starting...")

    event_queue: Queue[AnyEvent] = Queue()
    current_event_queue.set(event_queue)

    loop = get_running_loop()

    def put_event(event: AnyEvent) -> None:
        loop.call_soon_threadsafe(event_queue.put_nowait, event)

    if not headless:
        original = start_input_control(stream=input_stream)

    allow_key_thread = Event()
    allow_key_thread.set()

    waiting_key_thread = Event()

    try:
        if not headless:
            start_handling_resize_signal(put_event=put_event)
            start_output_control(stream=output_stream)
            start_mouse_tracking(stream=output_stream)

            key_thread = Thread(
                target=read_keys,
                args=(
                    input_stream,
                    put_event,
                    allow_key_thread,
                    waiting_key_thread,
                ),
                daemon=True,
            )
            key_thread.start()

        current_paint: Paint = {Position.flyweight(x, y): BLANK for x in range(w) for y in range(h)}
        instructions = paint_to_instructions(paint=current_paint)

        if not headless:
            output_stream.write(instructions)
            output_stream.flush()

        needs_render = True
        shadow = update_shadow(screen(), None)
        active_effects: set[Task[None]] = set()

        should_quit = False
        should_bell = False
        should_screenshot: Screenshot | None = None
        should_suspend: Suspend | None = None

        do_heal_borders = True

        def handle_control(control: AnyControl | None) -> None:
            nonlocal needs_render

            nonlocal should_quit
            nonlocal should_bell
            nonlocal should_screenshot
            nonlocal should_suspend

            nonlocal do_heal_borders

            match control:
                case None:
                    pass
                case Quit():
                    should_quit = True
                case Bell():
                    should_bell = True
                case Screenshot():
                    should_screenshot = control
                case Suspend():
                    should_suspend = control
                    needs_render = True
                case ToggleBorderHealing():
                    do_heal_borders = not do_heal_borders
                    needs_render = True

        mouse_position = Position.flyweight(x=-1, y=-1)

        async with TaskGroup() as tg:
            for ap in chain(autopilot, repeat(None)):
                if should_quit:
                    break

                if should_bell:
                    if not headless:
                        output_stream.write("\a")
                        output_stream.flush()
                    should_bell = False

                if should_screenshot:
                    try:
                        start_screenshot = perf_counter_ns()
                        await maybe_await(should_screenshot.handler(svg(current_paint)))
                        logger.debug(
                            "Took screenshot",
                            handler=should_screenshot.handler,
                            elapsed_ns=f"{perf_counter_ns() - start_screenshot:_}",
                        )
                    except Exception as ex:
                        logger.error(
                            "Error in screenshot handler",
                            error=repr(ex),
                            handler=should_screenshot.handler,
                            elapsed_ns=f"{perf_counter_ns() - start_screenshot:_}",
                        )

                    should_screenshot = None

                if should_suspend:
                    start_suspend = perf_counter_ns()
                    logger.debug(
                        "Suspending application",
                        handler=should_suspend.handler,
                    )

                    if not headless:
                        stop_mouse_tracking(stream=output_stream)
                        stop_output_control(stream=output_stream)
                        stop_input_control(stream=input_stream, original=original)
                        stop_handling_resize_signal()

                        # Coordinate with the key thread to tell it to pause,
                        # and to actually wait for it to pause.
                        allow_key_thread.clear()
                        waiting_key_thread.wait()

                    try:
                        await maybe_await(should_suspend.handler())
                    except Exception as ex:
                        logger.error(
                            "Error in suspend handler",
                            handler=should_suspend.handler,
                            error=repr(ex),
                        )

                    if not headless:
                        original = start_input_control(stream=input_stream)
                        start_handling_resize_signal(put_event=put_event)
                        start_output_control(stream=output_stream)
                        start_mouse_tracking(stream=output_stream)

                        allow_key_thread.set()

                    # TODO: below is the same as a terminal resize, should probably refactor
                    # note: we may have missed resize events while suspended, so we definitely want to get term size here

                    w, h = shutil.get_terminal_size()

                    # start from scratch
                    current_paint = {Position.flyweight(x, y): BLANK for x in range(w) for y in range(h)}
                    instructions = paint_to_instructions(paint=current_paint)
                    if not headless:
                        output_stream.write(CLEAR_SCREEN + instructions)
                        # don't flush here, we don't necessarily need to flush until the next render
                        # probably we can even store this until the next render happens and output it then

                    logger.debug(
                        "Resuming application",
                        handler=should_suspend.handler,
                        elapsed_ns=f"{perf_counter_ns() - start_suspend:_}",
                    )

                    should_suspend = None

                if needs_render:
                    start_render = perf_counter_ns()
                    shadow = update_shadow(screen(), shadow)
                    logger.debug(
                        "Updated shadow tree",
                        elapsed_ns=f"{perf_counter_ns() - start_render:_}",
                    )

                    start_concrete = perf_counter_ns()
                    element_tree = build_concrete_element_tree(shadow)
                    logger.debug(
                        "Extracted concrete element tree from shadow tree",
                        elapsed_ns=f"{perf_counter_ns() - start_concrete:_}",
                    )

                    start_layout = perf_counter_ns()
                    layout_tree = build_layout_tree_from_concrete_element_tree(element_tree)
                    layout_tree.compute_layout()
                    logger.debug(
                        "Calculated layout",
                        elapsed_ns=f"{perf_counter_ns() - start_layout:_}",
                    )

                    start_hover = perf_counter_ns()
                    for b in layout_tree.walk_from_bottom():
                        _, border_rect, _ = b.dims.padding_border_margin_rects()
                        if mouse_position in border_rect:
                            # TODO: hover changing layout doesn't really make sense here...
                            b.element = b.element.model_copy(update={"style": b.element.style | b.element.on_hover})
                    logger.debug(
                        "Applied hover styles",
                        elapsed_ns=f"{perf_counter_ns() - start_hover:_}",
                    )

                    start_paint = perf_counter_ns()
                    new_paint = paint_layout(layout_tree)
                    logger.debug(
                        "Generated new paint",
                        elapsed_ns=f"{perf_counter_ns() - start_paint:_}",
                    )

                    if do_heal_borders:
                        start_border_join = perf_counter_ns()
                        new_paint |= heal_borders(new_paint)
                        logger.debug(
                            "Healed borders in new paint",
                            elapsed_ns=f"{perf_counter_ns() - start_border_join:_}",
                        )

                    start_diff = perf_counter_ns()
                    diff = diff_paint(new_paint, current_paint)
                    current_paint |= diff
                    logger.debug(
                        "Diffed new paint from current paint",
                        elapsed_ns=f"{perf_counter_ns() - start_diff:_}",
                        diff_cells=len(diff),
                    )

                    start_instructions = perf_counter_ns()
                    instructions = paint_to_instructions(diff)
                    logger.debug(
                        "Generated instructions from paint diff",
                        elapsed_ns=f"{perf_counter_ns() - start_instructions:_}",
                    )

                    if not headless:
                        start_write = perf_counter_ns()
                        output_stream.write(instructions)
                        output_stream.flush()
                        logger.debug(
                            "Wrote and flushed instructions to output stream",
                            elapsed_ns=f"{perf_counter_ns() - start_write:_}",
                            bytes=f"{len(instructions):_}",
                        )

                    start_effects = perf_counter_ns()
                    active_effects = await handle_effects(shadow, active_effects=active_effects, task_group=tg)
                    logger.debug(
                        "Handled effects",
                        elapsed_ns=f"{perf_counter_ns() - start_effects:_}",
                        num_effects=len(active_effects),
                    )

                    needs_render = False

                    logger.debug("Completed render cycle", elapsed_ns=f"{perf_counter_ns() - start_render:_}")

                if ap is not None:
                    if isinstance(ap, _Control):
                        handle_control(ap)
                        await event_queue.put(Dummy())  # Force a render cycle when the autopilot emits a control
                    else:  # i.e., an event
                        await event_queue.put(ap)
                    logger.debug("Handled autopilot command", command=ap)

                # Goal: wait for an event, then process all pending events, and any events created by those events,
                # until there are no more events immediately available in the queue.
                # This makes sure that (for example) if you use autopilot to press a key which causes a state change,
                # the state change will be processed before the next render cycle.
                # Note that there are some tricky async semantics here. Right now, event handlers are sync,
                # so there's no way for an effect to add events to the queue once we get past the `await drain_queue()` below,
                # since we don't await again until we hit this point again in the next render cycle.

                num_events_handled = 0
                events = deque(await drain_queue(event_queue))

                start_event_handling = perf_counter_ns()
                while events:
                    start_handle_event = perf_counter_ns()

                    event = events.popleft()

                    match event:
                        case StateSet():
                            needs_render = True
                        case TerminalResized():
                            needs_render = True
                            w, h = shutil.get_terminal_size()

                            # start from scratch
                            current_paint = {Position.flyweight(x, y): BLANK for x in range(w) for y in range(h)}
                            instructions = paint_to_instructions(paint=current_paint)
                            if not headless:
                                output_stream.write(CLEAR_SCREEN + instructions)
                                # don't flush here, we don't necessarily need to flush until the next render
                                # probably we can even store this until the next render happens and output it then
                        case KeyPressed():
                            for e in layout_tree.walk_elements_from_bottom():
                                if e.on_key:
                                    handle_control(e.on_key(event))
                        case MouseMoved(position=p):
                            needs_render = True
                            mouse_position = p
                        case MouseDown():
                            for b in layout_tree.walk_from_bottom():
                                _, border_rect, _ = b.dims.padding_border_margin_rects()
                                if mouse_position in border_rect:
                                    if b.element.on_mouse_down:
                                        handle_control(b.element.on_mouse_down(event))
                        case MouseUp():
                            for b in layout_tree.walk_from_bottom():
                                _, border_rect, _ = b.dims.padding_border_margin_rects()
                                if mouse_position in border_rect:
                                    if b.element.on_mouse_up:
                                        handle_control(b.element.on_mouse_up(event))

                    while True:
                        try:
                            events.append(event_queue.get_nowait())
                        except QueueEmpty:
                            break

                    num_events_handled += 1

                    logger.debug(
                        "Handled event",
                        event_obj=event,
                        elapsed_ns=f"{perf_counter_ns() - start_handle_event:_}",
                    )

                logger.debug(
                    "Handled events",
                    num_events=num_events_handled,
                    elapsed_ns=f"{perf_counter_ns() - start_event_handling:_}",
                )

    except (KeyboardInterrupt, CancelledError) as ex:
        logger.debug(f"Caught {ex!r}")
    finally:
        logger.info("Application stopping...")

        if not headless:
            stop_mouse_tracking(stream=output_stream)
            stop_output_control(stream=output_stream)
            stop_input_control(stream=input_stream, original=original)
            stop_handling_resize_signal()

        logger.info("Application stopped")


async def handle_effects(shadow: ShadowNode, active_effects: set[Task[None]], task_group: TaskGroup) -> set[Task[None]]:
    new_effects: set[Task[None]] = set()
    for node in shadow.walk():
        for effect in node.hooks.data:  # TODO: reaching pretty deep here
            if isinstance(effect, UseEffect):
                if effect.deps != effect.new_deps or effect.new_deps is None:
                    effect.deps = effect.new_deps
                    t = task_group.create_task(effect.setup())
                    new_effects.add(t)
                    effect.task = t
                    logger.debug("Created effect", effect=effect)
                else:
                    if effect.task is None:
                        raise Exception("Effect task should never be None at this point")
                    new_effects.add(effect.task)

    for task in active_effects - new_effects:
        task.cancel()
        logger.debug("Cancelled effect task", task=task)

    return new_effects


def build_concrete_element_tree(root: ShadowNode) -> AnyElement:
    return root.element.model_copy(update={"children": [build_concrete_element_tree(child) for child in root.children]})


def diff_paint(new_paint: Paint, current_paint: Paint) -> Paint:
    diff = {}

    for pos, current_cell in current_paint.items():
        new_cell = new_paint.get(pos, BLANK)

        # This looks duplicative, but each of these checks is faster than the next,
        # but less precise, so we can short-circuit earlier on cheaper operations.
        if new_cell is not current_cell and new_cell != current_cell:
            diff[pos] = new_cell

    return diff
