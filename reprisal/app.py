from __future__ import annotations

import shutil
import sys
from asyncio import CancelledError, Queue, Task, TaskGroup, get_running_loop
from collections.abc import Callable
from signal import SIG_DFL, SIGWINCH, signal
from threading import Thread
from time import perf_counter_ns
from typing import TextIO

from structlog import get_logger

from reprisal._context_vars import current_event_queue
from reprisal._utils import drain_queue
from reprisal.components import AnyElement, Component, Div, component
from reprisal.events import AnyEvent, KeyPressed, StateSet, TerminalResized
from reprisal.hooks.impls import UseEffect
from reprisal.input import read_keys, start_input_control, stop_input_control
from reprisal.layout import Position, build_layout_tree
from reprisal.logging import configure_logging
from reprisal.output import (
    CLEAR_SCREEN,
    paint_to_instructions,
    start_output_control,
    stop_output_control,
)
from reprisal.paint import CellPaint, Paint, paint_layout
from reprisal.shadow import ShadowNode, render_shadow_node_from_previous
from reprisal.styles import Span, Style
from reprisal.styles.styles import CellStyle, Color, Flex

BLANK = CellPaint(
    char=" ",
    style=CellStyle(background=Color.from_name("black")),
)

logger = get_logger()


def start_handling_resize_signal(put_event: Callable[[AnyEvent], None]) -> None:
    signal(SIGWINCH, lambda _, __: put_event(TerminalResized()))


def stop_handling_resize_signal() -> None:
    signal(SIGWINCH, SIG_DFL)


async def app(
    root: Callable[[], Component],
    output_stream: TextIO = sys.stdout,
    input_stream: TextIO = sys.stdin,
) -> None:
    configure_logging()

    w, h = shutil.get_terminal_size()

    @component
    def screen() -> Div:
        return Div(
            children=[root()],
            style=Style(
                display=Flex(
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

    original = start_input_control(stream=input_stream)

    try:
        start_handling_resize_signal(put_event=put_event)
        start_output_control(stream=output_stream)
        # start_mouse_reporting(stream=output_stream)

        key_thread = Thread(target=read_keys, args=(input_stream, put_event), daemon=True)
        key_thread.start()

        current_paint: Paint = {Position(x, y): BLANK for x in range(w) for y in range(h)}
        instructions = paint_to_instructions(paint=current_paint)
        output_stream.write(instructions)
        output_stream.flush()

        needs_render = True
        shadow = render_shadow_node_from_previous(screen(), None)
        active_effects: set[Task[None]] = set()

        async with TaskGroup() as tg:
            while True:
                if needs_render:
                    start_render = perf_counter_ns()
                    shadow = render_shadow_node_from_previous(screen(), shadow)
                    logger.debug(
                        "Rendered shadow tree",
                        elapsed_ns=f"{perf_counter_ns() - start_render:_}",
                    )

                    start_concrete = perf_counter_ns()
                    element_tree = build_concrete_element_tree(shadow)
                    logger.debug(
                        "Derived concrete element tree from shadow tree",
                        elapsed_ns=f"{perf_counter_ns() - start_concrete:_}",
                    )

                    start_layout = perf_counter_ns()
                    layout_tree = build_layout_tree(element_tree)
                    layout_tree.compute_layout()
                    logger.debug(
                        "Calculated layout",
                        elapsed_ns=f"{perf_counter_ns() - start_layout:_}",
                    )

                    start_paint = perf_counter_ns()
                    new_paint = paint_layout(layout_tree)
                    logger.debug(
                        "Generated new paint",
                        elapsed_ns=f"{perf_counter_ns() - start_paint:_}",
                    )

                    start_diff = perf_counter_ns()
                    diff = diff_paint(new_paint, current_paint)
                    current_paint |= diff
                    logger.debug(
                        "Diffed new paint from current paint",
                        elapsed_ns=f"{perf_counter_ns() - start_diff:_}",
                        cells=len(diff),
                    )

                    start_instructions = perf_counter_ns()
                    instructions = paint_to_instructions(diff)
                    logger.debug(
                        "Generated instructions from paint diff",
                        elapsed_ns=f"{perf_counter_ns() - start_instructions:_}",
                    )

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

                events = await drain_queue(event_queue)

                start_event_handling = perf_counter_ns()
                for event in events:
                    start_handle_event = perf_counter_ns()
                    match event:
                        case TerminalResized():
                            needs_render = True
                            w, h = shutil.get_terminal_size()

                            # start from scratch
                            current_paint: Paint = {Position(x, y): BLANK for x in range(w) for y in range(h)}
                            instructions = paint_to_instructions(paint=current_paint)
                            output_stream.write(CLEAR_SCREEN)
                            output_stream.write(instructions)
                            # don't flush here, we don't necessarily need to flush until the next render
                            # probably we can even store this until the next render happens and output it then
                        case KeyPressed():
                            for c in layout_tree.walk_from_bottom():
                                if c.on_key:
                                    c.on_key(event)
                        case StateSet():
                            needs_render = True
                    logger.debug(
                        "Handled event",
                        event_obj=event,
                        elapsed_ns=f"{perf_counter_ns() - start_handle_event:_}",
                    )

                logger.debug(
                    "Handled events",
                    num_events=len(events),
                    elapsed_ns=f"{perf_counter_ns() - start_event_handling:_}",
                )

    except (KeyboardInterrupt, CancelledError) as e:
        logger.debug(f"Caught {e!r}")
    finally:
        logger.info("Application stopping...")

        # stop_mouse_reporting(stream=output_stream)
        stop_output_control(stream=output_stream)
        stop_input_control(stream=input_stream, original=original)
        stop_handling_resize_signal()

        logger.info("Application stopped")


async def handle_effects(shadow: ShadowNode, active_effects: set[Task[None]], task_group: TaskGroup) -> set[Task[None]]:
    new_effects: set[Task[None]] = set()
    for node in shadow.walk():
        for effect in node.hooks.data:  # TODO: reaching pretty deep here
            if isinstance(effect, UseEffect):
                if effect.deps != effect.new_deps:
                    effect.deps = effect.new_deps
                    t = task_group.create_task(effect.setup())
                    new_effects.add(t)
                    effect.task = t
                    logger.debug("Created effect", task=t, effect=effect)
                else:
                    if effect.task is None:
                        raise Exception("Effect task should never be None at this point")
                    new_effects.add(effect.task)

    for task in active_effects - new_effects:
        task.cancel()
        logger.debug("Cancelled effect task", task=task)

    return new_effects


def build_concrete_element_tree(root: ShadowNode | AnyElement) -> AnyElement:
    return root.element.copy(update={"children": [build_concrete_element_tree(child) for child in root.children]})


def diff_paint(new_paint: Paint, current_paint: Paint) -> Paint:
    diff = {}

    for pos, current_cell in current_paint.items():
        new_cell = new_paint.get(pos, BLANK)

        # This looks duplicative, but each of these checks is faster than the next,
        # but less precise, so we can short-circuit earlier on cheaper operations.
        if new_cell is not current_cell and hash(new_cell) != hash(current_cell):
            diff[pos] = new_cell

    return diff
