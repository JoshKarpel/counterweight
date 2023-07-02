from __future__ import annotations

import shutil
import sys
from asyncio import CancelledError, Queue, Task, TaskGroup, get_running_loop
from collections.abc import Callable
from signal import SIG_DFL, SIGWINCH, signal
from threading import Thread
from time import perf_counter
from typing import TextIO

from structlog import get_logger

from reprisal._context_vars import current_event_queue
from reprisal._utils import diff, drain_queue
from reprisal.components import Component, Element
from reprisal.events import AnyEvent, KeyPressed, StateSet, TerminalResized
from reprisal.hooks.impls import UseEffect
from reprisal.input import read_keys, start_input_control, stop_input_control
from reprisal.layout import BoxDimensions, Edge, Position, Rect, build_layout_tree, paint
from reprisal.logging import configure_logging
from reprisal.output import (
    apply_paint,
    start_mouse_reporting,
    start_output_control,
    stop_mouse_reporting,
    stop_output_control,
)
from reprisal.shadow import ShadowNode, render_shadow_node_from_previous

logger = get_logger()


def start_handling_resize_signal(queue: Queue[AnyEvent]) -> None:
    signal(SIGWINCH, lambda _, __: queue.put_nowait(TerminalResized()))


def stop_handling_resize_signal() -> None:
    signal(SIGWINCH, SIG_DFL)


async def app(
    root: Callable[[], Component],
    output_stream: TextIO = sys.stdout,
    input_stream: TextIO = sys.stdin,
) -> None:
    configure_logging()

    logger.info("Application starting...")

    event_queue: Queue[AnyEvent] = Queue()

    original = start_input_control(stream=input_stream)
    try:
        start_handling_resize_signal(queue=event_queue)
        start_output_control(stream=output_stream)
        start_mouse_reporting(stream=output_stream)

        key_thread = Thread(target=read_keys, args=(event_queue, input_stream, get_running_loop()), daemon=True)
        key_thread.start()

        previous_full_paint: dict[Position, str] = {}

        current_event_queue.set(event_queue)

        needs_render = True
        shadow = render_shadow_node_from_previous(root(), None)
        active_effects: set[Task[None]] = set()

        async with TaskGroup() as tg:
            while True:
                if needs_render:
                    w, h = shutil.get_terminal_size()
                    b = BoxDimensions(
                        # height is always zero here because this is the starting height of the context box in the layout algorithm
                        # screen boundary will need to be controlled by max height style and paint cutoff
                        content=Rect(x=0, y=0, width=w, height=0),
                        margin=Edge(),
                        border=Edge(),
                        padding=Edge(),
                    )

                    start_render = perf_counter()
                    shadow = render_shadow_node_from_previous(root(), shadow)
                    logger.debug("Rendered shadow tree", elapsed_ms=(perf_counter() - start_render) * 1000)

                    start_concrete = perf_counter()
                    element_tree = build_concrete_element_tree(shadow)
                    logger.debug(
                        "Derived concrete element tree from shadow tree",
                        elapsed_ms=(perf_counter() - start_concrete) * 1000,
                    )

                    start_layout = perf_counter()
                    layout_tree = build_layout_tree(element_tree)
                    layout_tree.layout(b)
                    logger.debug("Calculated layout", elapsed_ms=(perf_counter() - start_layout) * 1000)

                    start_paint = perf_counter()
                    full_paint = paint(layout_tree)
                    logger.debug("Generated full paint", elapsed_ms=(perf_counter() - start_paint) * 1000)

                    start_diff = perf_counter()
                    diffed_paint = diff(full_paint, previous_full_paint)
                    logger.debug(
                        "Diffed full paint from previous full paint", elapsed_ms=(perf_counter() - start_diff) * 1000
                    )

                    apply_paint(stream=output_stream, paint=diffed_paint)

                    previous_full_paint = full_paint

                    start_effects = perf_counter()
                    active_effects = await handle_effects(shadow, active_effects=active_effects, task_group=tg)
                    logger.debug(
                        "Handled effects",
                        elapsed_ms=(perf_counter() - start_effects) * 1000,
                        num_effects=len(active_effects),
                    )

                    needs_render = False

                events = await drain_queue(event_queue)

                start_event_handling = perf_counter()
                components = layout_tree.walk_from_bottom()
                for event in events:
                    start_handle_event = perf_counter()
                    match event:
                        case TerminalResized():
                            needs_render = True
                            previous_full_paint = {}
                        case KeyPressed():
                            for component in components:
                                if component.on_key:
                                    component.on_key(event)
                        case StateSet():
                            needs_render = True
                    logger.debug(
                        "Handled event", event_obj=event, elapsed_ms=(perf_counter() - start_handle_event) * 1000
                    )

                logger.debug(
                    "Handled events", num_events=len(events), elapsed_ms=(perf_counter() - start_event_handling) * 1000
                )

    except (KeyboardInterrupt, CancelledError) as e:
        logger.debug(f"Caught {e!r}")
    finally:
        logger.info("Application stopping...")

        stop_mouse_reporting(stream=output_stream)
        stop_output_control(stream=output_stream)
        stop_input_control(stream=input_stream, original=original)
        stop_handling_resize_signal()

        logger.info("Application stopped")


async def handle_effects(shadow: ShadowNode, active_effects: set[Task[None]], task_group: TaskGroup) -> set[Task[None]]:
    new_effects: set[Task[None]] = set()
    for node in shadow.walk_shadow_tree():
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


def build_concrete_element_tree(root: ShadowNode) -> Element:
    return root.element.copy(
        update={"children": [child.element if isinstance(child, ShadowNode) else child for child in root.children]}
    )
