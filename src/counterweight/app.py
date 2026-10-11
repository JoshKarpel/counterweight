from __future__ import annotations

import dataclasses
import logging
import shutil
import sys
from asyncio import CancelledError, Queue, QueueEmpty, Task, TaskGroup, get_running_loop
from collections import deque
from collections.abc import Callable
from itertools import chain, repeat
from signal import SIG_DFL, SIGWINCH, signal
from threading import Event, Thread
from typing import Iterable, TextIO
from weakref import WeakSet

import waxy

from counterweight._context_vars import current_event_queue, current_use_mouse_listeners
from counterweight._utils import cancel, drain_queue, maybe_await
from counterweight.border_healing import heal_borders
from counterweight.components import Component, component
from counterweight.controls import (
    AnyControl,
    Bell,
    Quit,
    Screenshot,
    Suspend,
    ToggleBorderHealing,
    _Control,
)
from counterweight.elements import AnyElement, Div
from counterweight.events import (
    AnyEvent,
    Dummy,
    KeyPressed,
    MouseDown,
    MouseMoved,
    MouseScrolledDown,
    MouseScrolledUp,
    MouseUp,
    StateSet,
    TerminalResized,
)
from counterweight.geometry import Position
from counterweight.hooks import Mouse
from counterweight.input import read_keys, start_input_control, stop_input_control
from counterweight.layout import ResolvedLayout, compute_layout
from counterweight.logging import devlog
from counterweight.output import (
    CLEAR_SCREEN,
    Frame,
    paint_to_instructions,
    start_mouse_tracking,
    start_output_control,
    stop_mouse_tracking,
    stop_output_control,
)
from counterweight.paint import BLANK, Paint, paint_layout
from counterweight.shadow import ShadowNode, update_shadow
from counterweight.styles import Style

logger = logging.getLogger(__name__)


def start_handling_resize_signal(put_event: Callable[[AnyEvent], None]) -> None:
    signal(SIGWINCH, lambda _, __: put_event(TerminalResized()))


def stop_handling_resize_signal() -> None:
    signal(SIGWINCH, SIG_DFL)


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
        autopilot: An iterable of events and controls to be processed by the application.
            This is primarily useful for testing or generating screenshots programmatically.
            Note that the autopilot will not be processed until after the initial render cycle,
            and that using the autopilot does not automatically cause the application to quit!
    """
    async with devlog():
        await render_loop(root, output_stream, input_stream, headless, dimensions, autopilot)


async def render_loop(
    root: Callable[[], Component],
    output_stream: TextIO,
    input_stream: TextIO,
    headless: bool,
    dimensions: tuple[int, int] | None,
    autopilot: Iterable[AnyEvent | AnyControl],
) -> None:
    def handle_screen_size_change(override: tuple[int, int] | None = None) -> tuple[Style, Paint, int, int]:
        w, h = override or dimensions or shutil.get_terminal_size()

        cp = {Position(x, y): BLANK for x in range(w) for y in range(h)}

        if not headless:
            output_stream.write(CLEAR_SCREEN + paint_to_instructions(paint=cp))

        return screen_element_style(w, h), cp, w, h

    @component
    def screen() -> Div:
        return Div(children=(root(),), style=screen_style)

    logger.info("Application starting...")

    event_queue: Queue[AnyEvent] = Queue()
    current_event_queue.set(event_queue)

    use_mouse_listeners: WeakSet[Callable[[Mouse], None]] = WeakSet()
    current_use_mouse_listeners.set(use_mouse_listeners)

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

        screen_style, current_paint, w, h = handle_screen_size_change()

        should_render = True
        shadow: ShadowNode | None = None
        active_effects: set[Task[None]] = set()
        elements_and_layouts: list[tuple[AnyElement, ResolvedLayout]] = []

        should_quit = False
        should_bell = False
        pending_screenshots: list[Screenshot] = []
        should_suspend: Suspend | None = None

        do_heal_borders = True

        # Warmup: render and lay out once without painting so that use_rects()
        # returns real dimensions on the first visible render.
        warmup_available = waxy.AvailableSize(width=waxy.Definite(w), height=waxy.Definite(h))
        shadow = update_shadow(screen(), shadow)
        compute_layout(shadow, warmup_available)

        def handle_control(control: AnyControl | None) -> None:
            nonlocal should_render

            nonlocal should_quit
            nonlocal should_bell
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
                    pending_screenshots.append(control)
                case Suspend():
                    should_suspend = control
                    should_render = True
                case ToggleBorderHealing():
                    do_heal_borders = not do_heal_borders
                    should_render = True

        mouse_position = Position(x=-1, y=-1)

        async with TaskGroup() as tg:
            for ap in chain(autopilot, repeat(None)):
                if should_quit:
                    logger.info("Quitting application...")
                    raise KeyboardInterrupt

                if should_bell:
                    if not headless:
                        output_stream.write("\a")
                        output_stream.flush()
                    should_bell = False

                if pending_screenshots:
                    # A copy, because current_paint is updated in place by later render cycles.
                    frame = Frame(paint=dict(current_paint))
                    for screenshot in pending_screenshots:
                        try:
                            await maybe_await(screenshot.handler(frame))
                            logger.debug("Took screenshot", extra={"handler": screenshot.handler})
                        except Exception as ex:
                            logger.error(
                                "Error in screenshot handler", extra={"error": repr(ex), "handler": screenshot.handler}
                            )

                    pending_screenshots.clear()

                if should_suspend:
                    logger.debug("Suspending application", extra={"handler": should_suspend.handler})

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
                            "Error in suspend handler", extra={"handler": should_suspend.handler, "error": repr(ex)}
                        )

                    if not headless:
                        original = start_input_control(stream=input_stream)
                        start_handling_resize_signal(put_event=put_event)
                        start_output_control(stream=output_stream)
                        start_mouse_tracking(stream=output_stream)

                        allow_key_thread.set()

                    screen_style, current_paint, w, h = handle_screen_size_change()

                    logger.debug("Resuming application", extra={"handler": should_suspend.handler})

                    should_suspend = None

                if should_render:
                    shadow = update_shadow(screen(), shadow)
                    logger.debug("Updated shadow tree")

                    available = waxy.AvailableSize(
                        width=waxy.Definite(w),
                        height=waxy.Definite(h),
                    )
                    elements_and_layouts = compute_layout(shadow, available)
                    logger.debug("Calculated layout")

                    new_paint, border_healing_hints = paint_layout(elements_and_layouts)
                    logger.debug("Generated new paint")

                    if do_heal_borders:
                        healing_diff = heal_borders(new_paint, border_healing_hints)
                        new_paint |= healing_diff
                        logger.debug(
                            "Healed borders in new paint",
                            extra={"hint_cells": len(border_healing_hints), "diff_cells": len(healing_diff)},
                        )

                    diff = diff_paint(new_paint, current_paint)
                    current_paint |= diff
                    logger.debug("Diffed new paint from current paint", extra={"diff_cells": len(diff)})

                    instructions = paint_to_instructions(diff)
                    logger.debug("Generated instructions from paint diff")

                    if not headless:
                        output_stream.write(instructions)
                        output_stream.flush()
                        logger.debug(
                            "Wrote and flushed instructions to output stream", extra={"bytes": f"{len(instructions):_}"}
                        )

                    active_effects = await handle_effects(shadow, active_effects=active_effects, task_group=tg)
                    logger.debug("Reconciled effects", extra={"num_active_effects": len(active_effects)})

                    should_render = False

                    logger.debug("Completed render cycle")

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

                num_events_handled = 0
                events = deque(await drain_queue(event_queue))

                while events:
                    event = events.popleft()

                    match event:
                        case StateSet():
                            should_render = True
                        case TerminalResized(dimensions=override):
                            should_render = True
                            screen_style, current_paint, w, h = handle_screen_size_change(override)
                        case KeyPressed():
                            for element, _ in reversed(elements_and_layouts):
                                if element.on_key:
                                    handle_control(element.on_key(event))
                        case MouseMoved() | MouseDown() | MouseUp() | MouseScrolledDown() | MouseScrolledUp() as m:
                            for element, resolved in reversed(elements_and_layouts):
                                # Send mouse events if the current *or previous* position is in the border region
                                if resolved.border.contains(mouse_position) or resolved.border.contains(m.absolute):
                                    if element.on_mouse:
                                        handle_control(element.on_mouse(event))

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
        for effect in node.hooks.effects:
            if effect.deps != effect.new_deps or effect.new_deps is None:
                effect.deps = effect.new_deps
                t = task_group.create_task(effect.setup())
                new_effects.add(t)
                effect.task = t
            else:
                if effect.task is None:
                    raise Exception("Effect task should never be None at this point")
                new_effects.add(effect.task)

    for task in active_effects - new_effects:
        await cancel(task)

    return new_effects


def build_concrete_element_tree(root: ShadowNode) -> AnyElement:
    match root.element:
        case Div():
            return dataclasses.replace(
                root.element, children=tuple(build_concrete_element_tree(child) for child in root.children)
            )
        case _:
            return root.element


def diff_paint(new_paint: Paint, current_paint: Paint) -> Paint:
    diff = {}

    for pos, current_cell in current_paint.items():
        new_cell = new_paint.get(pos, BLANK)

        # This looks duplicative, but each of these checks is faster than the next,
        # but less precise, so we can short-circuit earlier on cheaper operations.
        if new_cell is not current_cell and new_cell != current_cell:
            diff[pos] = new_cell

    return diff
